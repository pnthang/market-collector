import json
import logging
from datetime import datetime
from typing import Dict, Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_ERROR
from sqlalchemy.exc import IntegrityError
import threading
import signal

from .playwright_manager import BrowserManager
from ..db import SessionLocal, init_db
from ..db.models import IndexPrice, IndexMetadata
from ..config import SNAPSHOT_INTERVAL, MARKET_TZ, DRY_RUN
from ..utils import is_market_open_at

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


SCRAPER_READY = False
SCRAPER_INSTANCE = None


class VNScraper:
    def __init__(self):
        self.browser = BrowserManager()
        self.cache: Dict[str, Dict] = {}
        self.scheduler = BackgroundScheduler(timezone="UTC")

    def _on_ws_frame(self, payload: str):
        LOG.debug("WS frame received (len=%d)", len(payload) if payload is not None else 0)
        for entry in _parse_payload(payload):
            LOG.debug("Parsed entry from WS: %s %s", entry.get("code"), entry.get("price"))
            self.cache[entry["code"]] = entry

    def _attach_ws(self, page):
        def on_ws(ws):
            LOG.info("WebSocket opened: %s", getattr(ws, 'url', '<unknown>'))
            def _on_frame(frame):
                try:
                    self._on_ws_frame(frame.payload)
                except Exception:
                    LOG.exception("Error handling WS frame")
            ws.on("framereceived", _on_frame)

        page.on("websocket", on_ws)

    def _take_snapshot(self):
        if not self.cache:
            LOG.info("No data in cache to snapshot")
            return
        now = datetime.utcnow()
        if not is_market_open_at(now, MARKET_TZ):
            LOG.info("Market closed — skipping snapshot")
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

        LOG.info("Snapshot: cache=%d prepared_rows=%d", len(self.cache), len(rows))

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

            # Avoid inserting duplicates: check existing (index_code, timestamp) pairs
            codes = list({r['index_code'] for r in rows})
            timestamps = list({r['timestamp'] for r in rows})
            existing = set()
            if codes and timestamps:
                q = session.query(IndexPrice.index_code, IndexPrice.timestamp).filter(IndexPrice.index_code.in_(codes), IndexPrice.timestamp.in_(timestamps)).all()
                existing = {(c, t) for c, t in q}

            new_rows = [r for r in rows if (r['index_code'], r['timestamp']) not in existing]
            if not new_rows:
                LOG.info("No new rows to insert after deduplication")
            else:
                objs = [IndexPrice(**r) for r in new_rows]
                session.bulk_save_objects(objs)
                session.commit()
                LOG.info("Inserted %d price rows", len(new_rows))
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
        global SCRAPER_READY
        SCRAPER_READY = True

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


def start_scraper():
    global SCRAPER_INSTANCE
    if SCRAPER_INSTANCE is None:
        SCRAPER_INSTANCE = VNScraper()
        SCRAPER_INSTANCE.start()
    return SCRAPER_INSTANCE


def stop_scraper():
    global SCRAPER_INSTANCE
    if SCRAPER_INSTANCE is not None:
        SCRAPER_INSTANCE.stop()
        SCRAPER_INSTANCE = None


def set_snapshot_interval(seconds: int):
    """Change the snapshot interval (seconds) at runtime."""
    global SCRAPER_INSTANCE
    if SCRAPER_INSTANCE is None:
        return False
    try:
        try:
            SCRAPER_INSTANCE.scheduler.remove_job('snapshot')
        except Exception:
            pass
        SCRAPER_INSTANCE.scheduler.add_job(SCRAPER_INSTANCE._take_snapshot, 'interval', seconds=seconds, id='snapshot')
        return True
    except Exception:
        LOG.exception("Failed to set snapshot interval")
        return False


def run():
    scraper = start_scraper()

    def _shutdown(signum, frame):
        LOG.info("Signal %s received, shutting down", signum)
        stop_scraper()

    # Only install signal handlers if running in the main thread
    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)
    else:
        LOG.debug("Not installing signal handlers (not main thread)")

    # wait indefinitely until interrupted
    stop_event = threading.Event()
    try:
        stop_event.wait()
    except KeyboardInterrupt:
        stop_scraper()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
