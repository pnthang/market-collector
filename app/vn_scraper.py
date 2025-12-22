import time
import json
import logging
from datetime import datetime, time as dtime
from threading import Event, Thread
from typing import Dict

import pytz
from sqlalchemy.exc import IntegrityError

from .playwright_manager import BrowserManager
from .db import SessionLocal, init_db
from .models import IndexPrice, Index
from .config import SNAPSHOT_INTERVAL, MARKET_TZ, DRY_RUN

LOG = logging.getLogger("vn_scraper")


class VNScraper:
    def __init__(self):
        self.browser = BrowserManager()
        self._stop = Event()
        self.cache: Dict[str, Dict] = {}

    def is_market_open(self):
        tz = pytz.timezone(MARKET_TZ)
        now = datetime.now(tz)
        if now.weekday() >= 5:
            return False
        morning_start = dtime(9, 0)
        morning_end = dtime(11, 30)
        afternoon_start = dtime(13, 0)
        afternoon_end = dtime(15, 0)
        cur = now.time()
        return (morning_start <= cur <= morning_end) or (afternoon_start <= cur <= afternoon_end)

    def _on_ws_frame(self, payload: str):
        try:
            data = json.loads(payload)
        except Exception:
            return
        # Heuristics: find objects with index code and price
        if isinstance(data, dict):
            # common keys to check
            code = data.get("code") or data.get("symbol") or data.get("indexCode")
            price = data.get("last") or data.get("lastPrice") or data.get("price")
            change = data.get("change")
            pct = data.get("percent") or data.get("percentChange")
            ts = data.get("time") or data.get("timestamp")
            if code and price is not None:
                try:
                    price_f = float(price)
                except Exception:
                    return
                entry = {
                    "code": str(code),
                    "price": price_f,
                    "change": float(change) if change is not None else None,
                    "change_percent": float(pct) if pct is not None else None,
                    "ts": ts,
                }
                self.cache[entry["code"]] = entry

    def start(self):
        init_db()
        self.browser.start()
        page = self.browser.new_page()
        # attach websocket listeners
        def on_ws(ws):
            ws.on("framereceived", lambda frame: self._on_ws_frame(frame.payload))

        page.on("websocket", on_ws)
        page.goto("https://iboard.ssi.com.vn/", timeout=60_000)

        # Start snapshot thread
        t = Thread(target=self._snapshot_loop, daemon=True)
        t.start()

        try:
            while not self._stop.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            LOG.info("Interrupted, stopping")
            self.stop()

    def stop(self):
        self._stop.set()
        self.browser.stop()

    def _snapshot_loop(self):
        while not self._stop.is_set():
            if self.is_market_open():
                self._take_snapshot()
            else:
                LOG.debug("Market closed — skipping snapshot")
            self._stop.wait(SNAPSHOT_INTERVAL)

    def _take_snapshot(self):
        if not self.cache:
            LOG.debug("No data in cache to snapshot")
            return
        session = SessionLocal()
        for code, entry in list(self.cache.items()):
            ts = None
            try:
                ts = datetime.utcnow()
            except Exception:
                ts = datetime.utcnow()
            ip = IndexPrice(index_code=code, price=entry["price"], change=entry.get("change"), change_percent=entry.get("change_percent"), timestamp=ts)
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


def run():
    scraper = VNScraper()
    scraper.start()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
