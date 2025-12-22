import logging
from playwright.sync_api import sync_playwright

LOG = logging.getLogger("playwright_manager")


class BrowserManager:
    def __init__(self, disable_images=True):
        self._pw = None
        self._browser = None
        self.disable_images = disable_images

    def start(self):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)
        LOG.info("Playwright browser started")

    def new_page(self):
        if not self._browser:
            self.start()
        context = self._browser.new_context()
        if self.disable_images:
            context.set_default_navigation_timeout(30_000)
        page = context.new_page()
        return page

    def stop(self):
        try:
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
            LOG.info("Playwright browser stopped")
        except Exception:
            LOG.exception("Error stopping Playwright")
