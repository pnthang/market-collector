import logging
from playwright.sync_api import sync_playwright

LOG = logging.getLogger("playwright_manager")


class BrowserManager:
    def __init__(self, disable_images=True, user_agent=None):
        self._pw = None
        self._browser = None
        self._context = None
        self.disable_images = disable_images
        self.user_agent = user_agent

    def start(self):
        self._pw = sync_playwright().start()
        # launch with no-sandbox in container-friendly mode
        self._browser = self._pw.chromium.launch(headless=True, args=["--no-sandbox"])
        LOG.info("Playwright browser started")

    def new_page(self):
        if not self._browser:
            self.start()
        if not self._context:
            context_args = {}
            if self.user_agent:
                context_args["user_agent"] = self.user_agent
            self._context = self._browser.new_context(**context_args)
        page = self._context.new_page()
        if self.disable_images:
            try:
                page.route("**/*", lambda route, request: route.abort() if request.resource_type in ("image", "font", "media") else route.continue_())
            except Exception:
                LOG.debug("Could not set resource blocking route")
        return page

    def stop(self):
        try:
            if self._context:
                try:
                    self._context.close()
                except Exception:
                    LOG.debug("error closing context")
                self._context = None
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
            LOG.info("Playwright browser stopped")
        except Exception:
            LOG.exception("Error stopping Playwright")
