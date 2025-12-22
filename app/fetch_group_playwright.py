"""Fetch a group JSON using Playwright by opening the iBoard page and
capturing the network response for /stock/group/{GROUP}.

This bypasses HTTP 403 blocks by running a real browser session and capturing
the XHR that the page performs.

Usage:
    python -m app.fetch_group_playwright VN30
"""
import sys
import json
import logging
import time

from playwright.sync_api import sync_playwright

from .db import init_db
from .fetch_group import save_group

LOG = logging.getLogger("fetch_group_playwright")


def fetch_group_via_playwright(group: str, timeout: int = 15):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context()
        page = context.new_page()

        result = {}

        def handle_response(response):
            try:
                url = response.url
                if f"/stock/group/{group}" in url:
                    # attempt to parse JSON response
                    try:
                        data = response.json()
                    except Exception:
                        text = response.text()
                        data = json.loads(text)
                    result['json'] = data
            except Exception:
                LOG.exception("Error handling response")

        page.on("response", handle_response)
        page.goto("https://iboard.ssi.com.vn/", timeout=60_000)

        start = time.time()
        while 'json' not in result and (time.time() - start) < timeout:
            time.sleep(0.5)

        try:
            browser.close()
        except Exception:
            pass

        return result.get('json')


def main(argv):
    if len(argv) < 1:
        print("Usage: python -m app.fetch_group_playwright GROUP")
        return 1
    group = argv[0]
    init_db()
    payload = fetch_group_via_playwright(group)
    if not payload:
        LOG.error("No payload captured for group %s", group)
        return 2
    save_group(group, payload)
    print("Saved group", group)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main(sys.argv[1:]))
