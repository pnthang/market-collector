import json
import logging
from datetime import datetime
from typing import Dict, Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_ERROR
from sqlalchemy.exc import IntegrityError

from .playwright_manager import BrowserManager
from .db import SessionLocal, init_db
from .models import IndexPrice
from .config import SNAPSHOT_INTERVAL, MARKET_TZ, DRY_RUN
from .utils import is_market_open_at

LOG = logging.getLogger("vn_scraper")


def _find_messages(obj: Any):
    """Recursively yield dicts from nested payloads that look like index messages."""
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _find_messages(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from _find_messages(item)


def _parse_payload(payload: str):
    # payload may be JSON string or already JSON
    try:
        data = json.loads(payload)
    except Exception:
        # sometimes frames wrap JSON in quotes
        try:
            payload = payload.strip('"')
            data = json.loads(payload)
        except Exception:
            return []
    found = []
    for d in _find_messages(data):
        # heuristics for iboard.ssi messages: keys like 'symbol'/'code' and 'last'/'price'
        code = d.get("code") or d.get("symbol") or d.get("indexCode")
        price = d.get("last") or d.get("lastPrice") or d.get("price")
        change = d.get("change") or d.get("chg")
        pct = d.get("percent") or d.get("percentChange") or d.get("chgPercent")
        ts = d.get("time") or d.get("timestamp") or d.get("t")
        if code and price is not None:
            try:
                price_f = float(price)
            except Exception:
                continue
            entry = {
                "code": str(code),
                "price": price_f,
                "change": float(change) if change is not None else None,
                "change_percent": float(pct) if pct is not None else None,
                "ts": ts,
            }
            found.append(entry)
    return found


class VNScraper:
    def __init__(self):
        self.browser = BrowserManager()
        self.cache: Dict[str, Dict] = {}
        self.scheduler = BackgroundScheduler(timezone="UTC")

    def _on_ws_frame(self, payload: str):
        for entry in _parse_payload(payload):
            self.cache[entry["code"]] = entry

    def _attach_ws(self, page):
        def on_ws(ws):
            ws.on("framereceived", lambda frame: self._on_ws_frame(frame.payload))

        page.on("websocket", on_ws)

    def _take_snapshot(self):
        if not self.cache:
            LOG.debug("No data in cache to snapshot")
            return
        now = datetime.utcnow()
        if not is_market_open_at(now, MARKET_TZ):
            LOG.debug("Market closed — skipping snapshot")
            return
        session = SessionLocal()
        for code, entry in list(self.cache.items()):
            ts = now
            ip = IndexPrice(index_code=code, source="vnboard", price=entry["price"], change=entry.get("change"), change_percent=entry.get("change_percent"), timestamp=ts)
            if DRY_RUN:
                LOG.info("Dry-run insert: %s %s", code, entry["price"])
                continue
            session.add(ip)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
            except Exception:
                LOG.exception("DB error")
        session.close()

    def start(self):
        init_db()
        self.browser.start()
        page = self.browser.new_page()
        self._attach_ws(page)
        page.goto("https://iboard.ssi.com.vn/", timeout=60_000)

        # schedule snapshot job
        self.scheduler.add_job(self._take_snapshot, 'interval', seconds=SNAPSHOT_INTERVAL, id='snapshot')
        self.scheduler.add_listener(lambda ev: LOG.exception("Job error: %s", ev.exception) if ev.code == EVENT_JOB_ERROR else None)
        self.scheduler.start()

    def stop(self):
        try:
            self.scheduler.shutdown(wait=False)
        except Exception:
            LOG.debug("Scheduler shutdown failed")
        self.browser.stop()


def run():
    import signal

    scraper = VNScraper()
    scraper.start()

    def _shutdown(signum, frame):
        LOG.info("Signal %s received, shutting down", signum)
        scraper.stop()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # keep running until stopped
    try:
        while True:
            pass
    except KeyboardInterrupt:
        scraper.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
