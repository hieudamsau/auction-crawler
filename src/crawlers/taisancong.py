from typing import AsyncGenerator
from bs4 import BeautifulSoup
import re

from src.crawlers.base import BaseCrawler
from src.models.domain import RawAuctionItem
from src.models.enums import SourceId
from src.utils.http_client import ThrottledHttpClient


class TaiSanCongCrawler(BaseCrawler):
    """
    Crawl taisancong.vn via HTML scraping.
    SSR site using div-based layout (NOT tables).

    HTML structure per item:
      <div class="b-stt">1</div>
      <div class="b-tsb"><a href="..."><span>Title</span></a></div>
      <div class="b-dvico">Asset owner</div>
      <div class="b-dvb">Auction org</div>
      <div class="b-tdban">DD-MM-YYYY HH:MM - DD-MM-YYYY HH:MM</div>
      <div class="b-ngayban">DD-MM-YYYY HH:MM</div>
      <div class="b-address">Location</div>

    Pagination: &BRSR=0, &BRSR=20, &BRSR=40 ... (20 items/page).
    """

    source_id = SourceId.TAISANCONG

    BASE_URL = "https://taisancong.vn/niem-yet-gia-dau-gia-dau-thau/thong-tin-ban-dau-gia"
    DETAIL_BASE = "https://taisancong.vn"
    PAGE_SIZE = 20

    def __init__(self, http_client: ThrottledHttpClient):
        super().__init__(http_client)
        self._estimated_total_pages = 0

    async def crawl_list(self, page: int = 0) -> AsyncGenerator[RawAuctionItem, None]:
        offset = page * self.PAGE_SIZE
        url = f"{self.BASE_URL}&BRSR={offset}"

        response = await self._http_client.get(url)
        soup = BeautifulSoup(response.text, "lxml")

        self._update_pagination_info(soup)

        stt_divs = soup.select("div.b-stt")
        items_found = 0

        for stt_div in stt_divs:
            parent = stt_div.parent
            if not parent:
                continue

            title_div = parent.select_one("div.b-tsb")
            owner_div = parent.select_one("div.b-dvico")
            org_div = parent.select_one("div.b-dvb")
            period_div = parent.select_one("div.b-tdban")
            date_div = parent.select_one("div.b-ngayban")
            location_div = parent.select_one("div.b-address")

            if not title_div:
                continue

            link_tag = title_div.select_one("a")
            if not link_tag:
                continue

            detail_href = link_tag.get("href", "")
            if not detail_href.startswith("http"):
                detail_href = f"{self.DETAIL_BASE}/{detail_href.lstrip('/')}"

            source_item_id = self._extract_id_from_url(detail_href)
            title_text = link_tag.get_text(strip=True)

            raw_fields = {
                "asset_owner": owner_div.get_text(strip=True) if owner_div else "",
                "auction_org": org_div.get_text(strip=True) if org_div else "",
                "doc_sale_period": period_div.get_text(strip=True) if period_div else "",
                "auction_date": date_div.get_text(strip=True) if date_div else "",
                "auction_location": location_div.get_text(strip=True) if location_div else "",
            }

            items_found += 1
            yield RawAuctionItem(
                source_id=self.source_id,
                source_item_id=source_item_id,
                source_url=detail_href,
                raw_title=title_text,
                raw_description=None,
                raw_fields=raw_fields,
            )

        self._logger.info(
            "Fetched list page",
            page=page,
            offset=offset,
            items_found=items_found,
        )

    async def crawl_detail(self, raw_item: RawAuctionItem) -> RawAuctionItem:
        try:
            response = await self._http_client.get(raw_item.source_url)
        except Exception as e:
            self._logger.warning("Failed to fetch detail", url=raw_item.source_url, error=str(e))
            return raw_item

        soup = BeautifulSoup(response.text, "lxml")

        detail_fields = {}
        rows = soup.select("table tr")
        for row in rows:
            cells = row.select("td")
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True).rstrip(":").strip()
                value = cells[1].get_text(strip=True)
                detail_fields[label] = value

        pdf_links = []
        for a_tag in soup.select("a[href$='.pdf']"):
            href = a_tag.get("href", "")
            if not href.startswith("http"):
                href = f"{self.DETAIL_BASE}/{href.lstrip('/')}"
            pdf_links.append({
                "file_name": a_tag.get_text(strip=True) or href.split("/")[-1],
                "file_url": href,
                "file_type": "pdf",
            })

        raw_item.raw_fields.update({
            "detail": detail_fields,
            "pdf_links": pdf_links,
        })
        raw_item.raw_description = detail_fields.get(
            "7. Nội dung tài sản bán",
            detail_fields.get("Nội dung tài sản bán", raw_item.raw_title),
        )

        return raw_item

    def has_next_page(self, current_page: int) -> bool:
        return current_page < self._estimated_total_pages

    def _update_pagination_info(self, soup: BeautifulSoup):
        last_page_link = None
        for a_tag in soup.select("a[href*='BRSR=']"):
            href = a_tag.get("href", "")
            match = re.search(r"BRSR=(\d+)", href)
            if match:
                offset = int(match.group(1))
                page_num = offset // self.PAGE_SIZE
                if last_page_link is None or page_num > last_page_link:
                    last_page_link = page_num

        if last_page_link is not None:
            self._estimated_total_pages = last_page_link
            self._total_pages = last_page_link
            self._total_records = last_page_link * self.PAGE_SIZE

    @staticmethod
    def _extract_id_from_url(url: str) -> str:
        match = re.search(r"-(\d+)\.html", url)
        if match:
            return match.group(1)
        return url.split("/")[-1].replace(".html", "")
