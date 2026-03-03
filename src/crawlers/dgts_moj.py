import asyncio
from typing import AsyncGenerator

from src.crawlers.base import BaseCrawler
from src.models.domain import RawAuctionItem
from src.models.enums import SourceId
from src.utils.http_client import ThrottledHttpClient
from src.utils.browser import BrowserManager
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DgtsMojCrawler(BaseCrawler):
    """
    Crawl dgts.moj.gov.vn via Playwright with stealth mode.
    Site is protected by FEC WAF with TLS fingerprinting + bot detection.

    Strategy:
      1. Launch stealth browser, navigate to search page
      2. Wait for WAF challenge + AngularJS to load (auto-fires first API call)
      3. For subsequent pages, use fetch() inside the browser context
    """

    source_id = SourceId.DGTS_MOJ

    MAIN_PAGE = "https://dgts.moj.gov.vn/thong-bao-cong-khai-viec-dau-gia.html"
    SEARCH_URL = "https://dgts.moj.gov.vn/portal/search/auction-notice"
    DETAIL_URL_TEMPLATE = "https://dgts.moj.gov.vn/chi-tiet-viec-dau-gia/{item_id}"
    PROPERTY_INFO_URL = "https://dgts.moj.gov.vn/portal/propertyInfo"
    VIEW_DETAIL_AUCTION_URL = "https://dgts.moj.gov.vn/portal/viewDetailAuctionInfo"

    REFERENCE_URLS = {
        "property_types": "https://dgts.moj.gov.vn/common/getListPropertyType",
        "provinces": "https://dgts.moj.gov.vn/common/getListProvince",
        "organizations": "https://dgts.moj.gov.vn/portal/getListOrgTtTcCn",
        "news_categories": "https://dgts.moj.gov.vn/common/getListCategoryNews",
    }

    def __init__(
        self,
        http_client: ThrottledHttpClient,
        page_size: int = 50,
        browser: BrowserManager | None = None,
    ):
        super().__init__(http_client)
        self._page_size = page_size
        self._browser = browser
        self._context = None
        self._page = None
        self._initialized = False

    async def _ensure_browser_page(self):
        if self._initialized:
            return

        if self._browser is None:
            self._browser = BrowserManager(headless=True)
            await self._browser.start()

        self._context = await self._browser.new_stealth_context()
        self._page = await self._context.new_page()

        logger.info("Navigating to search page (waiting for WAF + AngularJS)...")
        await self._page.goto(self.MAIN_PAGE, wait_until="domcontentloaded", timeout=30000)
        await self._page.wait_for_timeout(12000)

        self._initialized = True
        logger.info("Browser page ready")

    async def crawl_list(
        self,
        page: int = 1,
        property_type_id: str = "",
        province_id: str = "",
        start_publish_date: str = "",
        end_publish_date: str = "",
    ) -> AsyncGenerator[RawAuctionItem, None]:
        await self._ensure_browser_page()

        url = (
            f"{self.SEARCH_URL}"
            f"?p={page}"
            f"&numberPerPage={self._page_size}"
            f"&typeOrder=2"
            f"&assetName="
            f"&propertyTypeId={property_type_id}"
            f"&provinceId={province_id}"
            f"&selectedOrganizationId="
            f"&fullName="
            f"&startDate="
            f"&endDate="
            f"&startPublishDate={start_publish_date}"
            f"&endPublishDate={end_publish_date}"
            f"&fromFirstPrice="
            f"&toFirstPrice="
            f"&searchSimple="
        )

        data = await self._page.evaluate(f"""
            async () => {{
                try {{
                    const resp = await fetch("{url}");
                    return await resp.json();
                }} catch(e) {{
                    return {{ error: e.message }};
                }}
            }}
        """)

        if not data or (isinstance(data, dict) and "error" in data):
            logger.warning("API call failed", page=page, error=data.get("error") if data else "no data")
            return

        self._total_pages = data.get("pageCount", 0)
        self._total_records = data.get("rowCount", 0)

        items = data.get("items", [])
        self._logger.info(
            "Fetched list page",
            page=page,
            items_on_page=len(items),
            total_records=self._total_records,
            total_pages=self._total_pages,
        )

        for item in items:
            item_id = item.get("id")
            yield RawAuctionItem(
                source_id=self.source_id,
                source_item_id=str(item_id),
                source_url=self.DETAIL_URL_TEMPLATE.format(item_id=item_id),
                raw_title=item.get("titleName", ""),
                raw_description=item.get("propertyName", ""),
                raw_fields=item,
            )

    async def crawl_detail(self, raw_item: RawAuctionItem) -> RawAuctionItem:
        """Fetch detail APIs (propertyInfo + viewDetailAuctionInfo) and merge into raw_fields."""
        await self._ensure_browser_page()
        item_id = raw_item.source_item_id

        property_url = f"{self.PROPERTY_INFO_URL}?auctionInfoId={item_id}"
        auction_url = f"{self.VIEW_DETAIL_AUCTION_URL}?auctionInfoId={item_id}"

        def _fetch(url: str):
            return self._page.evaluate(
                f"""
                async () => {{
                    try {{
                        const resp = await fetch("{url}");
                        return await resp.json();
                    }} catch (e) {{
                        return {{ error: e.message }};
                    }}
                }}
                """
            )

        property_data = await _fetch(property_url)
        await asyncio.sleep(1.0)
        auction_data = await _fetch(auction_url)

        if isinstance(property_data, dict) and "error" not in property_data:
            raw_item.raw_fields["detail_property"] = property_data
        if isinstance(auction_data, dict) and "error" not in auction_data:
            raw_item.raw_fields["detail_auction"] = auction_data

        return raw_item

    def has_next_page(self, current_page: int) -> bool:
        return current_page < self._total_pages

    async def fetch_reference_data(self, ref_type: str) -> list[dict]:
        await self._ensure_browser_page()

        url = self.REFERENCE_URLS.get(ref_type)
        if not url:
            raise ValueError(f"Unknown reference type: {ref_type}")

        result = await self._page.evaluate(f"""
            async () => {{
                try {{
                    const resp = await fetch("{url}");
                    return await resp.json();
                }} catch(e) {{
                    return {{ error: e.message }};
                }}
            }}
        """)

        if isinstance(result, dict) and "error" in result:
            raise RuntimeError(f"Failed to fetch {ref_type}: {result['error']}")

        return result

    async def cleanup(self):
        if self._page:
            await self._page.close()
        if self._context:
            await self._context.close()
