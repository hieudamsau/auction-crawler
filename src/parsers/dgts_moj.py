from datetime import datetime, timezone

from src.parsers.base import BaseParser
from src.models.domain import RawAuctionItem, NormalizedAuctionItem
from src.models.enums import SourceId, AuctionStatus


class DgtsMojParser(BaseParser):
    """Parse raw JSON fields from dgts.moj.gov.vn API into normalized schema."""

    def parse(self, raw_item: RawAuctionItem) -> NormalizedAuctionItem:
        fields = raw_item.raw_fields

        title = (fields.get("titleName") or "") + (fields.get("subPropertyName") or "")
        description = fields.get("propertyName") or raw_item.raw_description or ""

        auction_dt = self._parse_timestamp(fields.get("aucTime"))
        status = self._determine_status(auction_dt)

        return NormalizedAuctionItem(
            source_id=SourceId.DGTS_MOJ,
            source_item_id=raw_item.source_item_id,
            source_url=raw_item.source_url,
            title=title.strip(),
            description=description.strip(),
            auction_org_name=fields.get("org_name"),
            asset_owner_name=fields.get("fullname"),
            doc_sale_start=self._parse_timestamp(fields.get("aucRegTimeStart")),
            doc_sale_end=self._parse_timestamp(fields.get("aucRegTimeEnd")),
            auction_datetime=auction_dt,
            publish_date=self._parse_timestamp(
                fields.get("publishTime2") or fields.get("publishTime1")
            ),
            property_type_id=fields.get("propertyTypeId"),
            property_type_name=fields.get("propertyTypeName"),
            status=status,
            fingerprint="",
        )

    @staticmethod
    def _parse_timestamp(ts) -> datetime | None:
        if ts is None:
            return None
        try:
            return datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc)
        except (ValueError, TypeError, OSError):
            return None

    @staticmethod
    def _determine_status(auction_dt: datetime | None) -> AuctionStatus:
        if auction_dt is None:
            return AuctionStatus.UPCOMING

        now = datetime.now(timezone.utc)
        if auction_dt > now:
            return AuctionStatus.UPCOMING
        return AuctionStatus.COMPLETED
