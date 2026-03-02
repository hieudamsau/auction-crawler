import httpx
import asyncio
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from src.utils.logger import get_logger

logger = get_logger(__name__)


class ThrottledHttpClient:
    """HTTP client with rate limiting, retry, and proper headers."""

    def __init__(
        self,
        delay: float = 1.5,
        timeout: float = 30.0,
        max_retries: int = 3,
        user_agent: str = "AuctionCrawler/0.1",
    ):
        self._delay = delay
        self._max_retries = max_retries
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, text/html, */*",
                "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
            },
            follow_redirects=True,
            http2=True,
        )
        self._lock = asyncio.Lock()
        self._last_request_time = 0.0

    async def _throttle(self):
        async with self._lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_request_time
            if elapsed < self._delay:
                await asyncio.sleep(self._delay - elapsed)
            self._last_request_time = asyncio.get_event_loop().time()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout)),
    )
    async def get(self, url: str, params: dict = None) -> httpx.Response:
        await self._throttle()
        logger.debug("HTTP GET", url=url, params=params)

        response = await self._client.get(url, params=params)
        response.raise_for_status()
        return response

    async def close(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
