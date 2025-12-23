"""Data scraper package.

This package collects the scraper-related modules under `app.data_scraper`.
It re-exports the existing top-level scraper modules for compatibility.
"""
from .. import vn_scraper  # noqa: F401
from .. import yahoo_scraper  # noqa: F401
from .. import playwright_manager  # noqa: F401
from .. import fetch_group, fetch_group_playwright, fetch_group_auto, fetch_groups  # noqa: F401
