"""Auto fetcher: try HTTP request first, fall back to Playwright if blocked.

Usage:
    python -m app.data_scraper.fetch_group_auto VN30
"""
import sys
import logging

import requests

from .fetch_group import fetch_group as http_fetch, save_group, init_db
from .fetch_group_playwright import fetch_group_via_playwright

LOG = logging.getLogger("fetch_group_auto")


def fetch_group_auto(group: str):
    # Try HTTP first
    try:
        LOG.info("Attempting HTTP fetch for %s", group)
        payload = http_fetch(group)
        LOG.info("HTTP fetch succeeded for %s", group)
        return payload
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else None
        LOG.warning("HTTP fetch failed for %s: %s", group, e)
        if status == 403:
            LOG.info("403 detected — falling back to Playwright for %s", group)
        else:
            LOG.info("Falling back to Playwright for %s due to HTTP error", group)
    except Exception as e:
        LOG.warning("HTTP fetch error for %s: %s — falling back to Playwright", group, e)

    # Fallback to Playwright
    try:
        payload = fetch_group_via_playwright(group)
        if payload:
            LOG.info("Playwright fetch succeeded for %s", group)
            return payload
        else:
            LOG.error("Playwright fetch returned no payload for %s", group)
            return None
    except Exception:
        LOG.exception("Playwright fetch failed for %s", group)
        return None


def main(argv):
    if len(argv) < 1:
        print("Usage: python -m app.data_scraper.fetch_group_auto GROUP")
        return 1
    group = argv[0]
    init_db()
    payload = fetch_group_auto(group)
    if not payload:
        LOG.error("Failed to fetch group %s via both HTTP and Playwright", group)
        return 2
    save_group(group, payload)
    print("Saved group", group)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main(sys.argv[1:]))
