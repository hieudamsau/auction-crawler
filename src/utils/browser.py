import asyncio
from playwright.async_api import async_playwright, Browser, BrowserContext
from src.utils.logger import get_logger

logger = get_logger(__name__)

STEALTH_INIT_SCRIPT = """
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    Object.defineProperty(navigator, 'languages', { get: () => ['vi-VN', 'vi', 'en-US', 'en'] });
    window.chrome = { runtime: {} };
"""


class BrowserManager:
    """
    Manage a Playwright browser with anti-detection measures.
    Required for dgts.moj.gov.vn which uses FEC WAF with bot detection.
    """

    def __init__(self, headless: bool = True):
        self._headless = headless
        self._playwright = None
        self._browser: Browser | None = None

    async def start(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self._headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        logger.info("Browser started", headless=self._headless)

    async def stop(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser stopped")

    async def new_stealth_context(self) -> BrowserContext:
        """Create a new browser context with anti-detection measures."""
        context = await self._browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh",
        )
        await context.add_init_script(STEALTH_INIT_SCRIPT)
        return context

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.stop()
