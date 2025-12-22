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

        rows = []
        metadata_to_upsert = []
        for code, entry in list(self.cache.items()):
            prefixed = f"VN:{code}"
            rows.append({
                "index_code": prefixed,
                "source": "vnboard",
                "price": entry["price"],
                "change": entry.get("change"),
                "change_percent": entry.get("change_percent"),
                "timestamp": now,
            })
            # prepare metadata upsert (store prefixed code)
            metadata_to_upsert.append({"code": prefixed, "name": code, "source": "vnboard"})

        if DRY_RUN:
            for r in rows:
                LOG.info("Dry-run insert: %s %s", r["index_code"], r["price"])
            return

        session = SessionLocal()
        try:
            # upsert metadata (simple check-then-insert to remain DB-agnostic)
            for md in metadata_to_upsert:
                exists = session.query(IndexMetadata).filter_by(code=md["code"]).one_or_none()
                if not exists:
                    session.add(IndexMetadata(code=md["code"], name=md.get("name"), source=md.get("source")))
            session.commit()

            # batch insert price rows
            objs = [IndexPrice(**r) for r in rows]
            session.bulk_save_objects(objs)
            session.commit()
        except IntegrityError:
            session.rollback()
            LOG.warning("Integrity error during batch insert — falling back to individual inserts")
            for r in rows:
                try:
                    ip = IndexPrice(**r)
                    session.add(ip)
                    session.commit()
                except IntegrityError:
                    session.rollback()
                except Exception:
                    LOG.exception("DB error on single insert")
        except Exception:
            LOG.exception("Unexpected DB error during batch insert")
        finally:
            session.close()

    def start(self):
        init_db()
        self.browser.start()
        page = self.browser.new_page()
        self._attach_ws(page)
        page.goto("https://iboard.ssi.com.vn/", timeout=60_000)

        # schedule snapshot job
        self.scheduler.add_job(self._take_snapshot, 'interval', seconds=SNAPSHOT_INTERVAL, id='snapshot')
        # schedule analysis/news job every 2 hours
        self.scheduler.add_job(self._scrape_analysis_news, 'interval', hours=2, id='analysis_news')
        self.scheduler.add_listener(lambda ev: LOG.exception("Job error: %s", ev.exception) if ev.code == EVENT_JOB_ERROR else None)
        self.scheduler.start()

    def stop(self):
        try:
            self.scheduler.shutdown(wait=False)
        except Exception:
            LOG.debug("Scheduler shutdown failed")
        self.browser.stop()

    def _scrape_analysis_news(self):
        """Stub job for scraping analysis and news every 2 hours.

        This is intentionally minimal — it should be expanded to navigate to
        analysis/news pages for discovered symbols, extract articles, and write
        to `index_analysis` / `index_news` tables. For now it logs and clears
        the cache periodically to avoid unbounded growth.
        """
        LOG.info("Running analysis/news job — found %d symbols", len(self.cache))
        # TODO: implement detailed scraping of analysis/news pages
        # conservative maintenance: trim cache keys not updated recently (not implemented)
        return


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
