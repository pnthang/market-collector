from threading import Thread
import logging

from .vn_scraper import run as run_scraper
from .health import run as run_health


def main():
    logging.basicConfig(level=logging.INFO)
    # start scraper in background thread
    t = Thread(target=run_scraper, daemon=True)
    t.start()
    # start FastAPI/uvicorn health server in foreground
    run_health(host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()
