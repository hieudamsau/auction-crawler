import re
from datetime import datetime, timezone

from src.parsers.base import BaseParser
from src.models.domain import RawAuctionItem, NormalizedAuctionItem, AuctionAttachment
from src.models.enums import SourceId, AuctionStatus


class TaiSanCongParser(BaseParser):
    """Parse raw HTML-scraped fields from taisancong.vn into normalized schema."""

    DATE_PATTERN = re.compile(r"(\d{2})-(\d{2})-(\d{4})\s+(\d{2}):(\d{2})")

    def parse(self, raw_item: RawAuctionItem) -> NormalizedAuctionItem:
        fields = raw_item.raw_fields
        detail = fields.get("detail", {})

        description = (
            detail.get("7. Nội dung tài sản bán")
            or detail.get("Nội dung tài sản bán")
            or raw_item.raw_description
            or raw_item.raw_title
        )

        doc_start, doc_end = self._parse_period(
            detail.get("8. Thời gian bán hồ sơ", fields.get("doc_sale_period", ""))
        )
        view_start, view_end = self._parse_period(
            detail.get("9. Thời gian xem tài sản", "")
        )

        auction_dt_str = detail.get("10. Thời gian bán đấu giá", fields.get("auction_date", ""))
        auction_dt = self._parse_single_date(auction_dt_str)

        auction_location = (
            detail.get("4. Địa điểm bán đấu giá")
            or detail.get("Địa điểm bán đấu giá")
            or fields.get("auction_location", "")
        )

        attachments = [
            AuctionAttachment(**pdf)
            for pdf in fields.get("pdf_links", [])
        ]

        status = self._determine_status(auction_dt)

        return NormalizedAuctionItem(
            source_id=SourceId.TAISANCONG,
            source_item_id=raw_item.source_item_id,
            source_url=raw_item.source_url,
            title=raw_item.raw_title.strip(),
            description=description.strip() if description else None,
            auction_org_name=(
                detail.get("2. Tên đơn vị đấu giá")
                or detail.get("Tên đơn vị đấu giá")
                or fields.get("auction_org", "")
            ),
            auction_org_address=(
                detail.get("3. Địa chỉ đơn vị đấu giá")
                or detail.get("Địa chỉ đơn vị đấu giá")
            ),
            asset_owner_name=(
                detail.get("5. Tên đơn vị có tài sản")
                or detail.get("Tên đơn vị có tài sản")
                or fields.get("asset_owner", "")
            ),
            asset_owner_address=(
                detail.get("6. Địa chỉ đơn vị có tài sản")
                or detail.get("Địa chỉ đơn vị có tài sản")
            ),
            doc_sale_start=doc_start,
            doc_sale_end=doc_end,
            viewing_start=view_start,
            viewing_end=view_end,
            auction_datetime=auction_dt,
            auction_location=auction_location,
            contact_phone=(
                detail.get("11. Số điện thoại liên hệ")
                or detail.get("Số điện thoại liên hệ")
            ),
            contact_email=(
                detail.get("12. Địa chỉ Email")
                or detail.get("Địa chỉ Email")
            ),
            status=status,
            fingerprint="",
            attachments=attachments,
        )

    def _parse_period(self, text: str) -> tuple[datetime | None, datetime | None]:
        """Parse 'từ ngày: DD-MM-YYYY HH:MM đến ngày: DD-MM-YYYY HH:MM'"""
        if not text:
            return None, None

        matches = list(self.DATE_PATTERN.finditer(text))
        start = self._match_to_datetime(matches[0]) if len(matches) >= 1 else None
        end = self._match_to_datetime(matches[1]) if len(matches) >= 2 else None
        return start, end

    def _parse_single_date(self, text: str) -> datetime | None:
        if not text:
            return None
        match = self.DATE_PATTERN.search(text)
        return self._match_to_datetime(match) if match else None

    @staticmethod
    def _match_to_datetime(match) -> datetime | None:
        if not match:
            return None
        try:
            day, month, year, hour, minute = (int(g) for g in match.groups())
            return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _determine_status(auction_dt: datetime | None) -> AuctionStatus:
        if auction_dt is None:
            return AuctionStatus.UPCOMING
        now = datetime.now(timezone.utc)
        if auction_dt > now:
            return AuctionStatus.UPCOMING
        return AuctionStatus.COMPLETED
