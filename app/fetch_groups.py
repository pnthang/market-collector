"""Fetch multiple index groups (e.g., VN30, VNALL) and store them.

Usage:
    python -m app.fetch_groups VN30 VNALL
If no args provided, defaults to VN30 and VNALL.
"""
import sys
import logging

from .fetch_group import fetch_group, save_group, init_db

LOG = logging.getLogger("fetch_groups")


def main(argv):
    groups = argv or ["VN30", "VNALL"]
    init_db()
    for g in groups:
        try:
            LOG.info("Fetching group %s", g)
            payload = fetch_group(g)
            save_group(g, payload)
            LOG.info("Saved group %s", g)
        except Exception:
            LOG.exception("Failed to fetch/save group %s", g)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main(sys.argv[1:])
