from threading import Thread
import logging

from .logging_config import configure_logging
from .vn_scraper import run as run_scraper
from .health import run as run_health
from . import yahoo_scraper


def main():
    configure_logging()
    # start scraper in background thread
    t = Thread(target=run_scraper, daemon=True)
    t.start()
    # start yahoo scheduled fetcher (runs periodically in background)
    try:
        yahoo_scraper.start_scheduler()
    except Exception:
        pass
    # start FastAPI/uvicorn health server in foreground
    run_health(host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()
