from datetime import datetime, timezone
from urllib.parse import quote

from src.parsers.base import BaseParser
from src.models.domain import (
    RawAuctionItem,
    NormalizedAuctionItem,
    AuctionAttachment,
)
from src.models.enums import SourceId, AuctionStatus


# Endpoint tải file đính kèm (query: name=fileName, path=linkFile).
DGTS_DOWNLOAD_BASE = "https://dgts.moj.gov.vn/common/download"


class DgtsMojParser(BaseParser):
    """Parse raw JSON fields from dgts.moj.gov.vn API into normalized schema."""

    def parse(self, raw_item: RawAuctionItem) -> NormalizedAuctionItem:
        fields = raw_item.raw_fields
        detail_prop = (fields.get("detail_property") or {}).get("items") or []
        detail_auc = fields.get("detail_auction") or {}
        prop0 = detail_prop[0] if detail_prop else {}

        title = (fields.get("titleName") or "") + (fields.get("subPropertyName") or "")
        description = (
            (prop0.get("propertyName") or fields.get("propertyName") or "")
            .strip()
            or raw_item.raw_description
            or ""
        )

        auction_dt = self._parse_timestamp(fields.get("aucTime"))
        status = self._determine_status(auction_dt)

        starting_price = self._int_or_none(
            prop0.get("propertyStartPrice") or fields.get("propertyStartPrice")
        )
        deposit_amount = self._int_or_none(
            prop0.get("deposit") or fields.get("deposit")
        )
        asset_location = (
            (prop0.get("propertyPlace") or fields.get("propertyPlace") or "").strip()
            or None
        )
        property_type_id = self._int_or_none(
            prop0.get("propertyTypeId") or fields.get("propertyTypeId")
        )
        property_type_name = (
            prop0.get("propertyTypeName") or fields.get("propertyTypeName") or ""
        ).strip() or None

        attachments = self._parse_list_file(detail_auc.get("listFile") or [])

        return NormalizedAuctionItem(
            source_id=SourceId.DGTS_MOJ,
            source_item_id=raw_item.source_item_id,
            source_url=raw_item.source_url,
            title=title.strip(),
            description=description,
            auction_org_name=(
                detail_auc.get("orgFullName") or fields.get("org_name")
            ),
            asset_owner_name=fields.get("fullname"),
            doc_sale_start=self._parse_timestamp(
                detail_auc.get("aucRegTimeStart") or fields.get("aucRegTimeStart")
            ),
            doc_sale_end=self._parse_timestamp(
                detail_auc.get("aucRegTimeEnd") or fields.get("aucRegTimeEnd")
            ),
            auction_datetime=auction_dt,
            publish_date=self._parse_timestamp(
                fields.get("publishTime2") or fields.get("publishTime1")
            ),
            property_type_id=property_type_id,
            property_type_name=property_type_name,
            starting_price=starting_price,
            deposit_amount=deposit_amount,
            asset_location=asset_location,
            auction_location=detail_auc.get("aucAddr") or None,
            auction_org_address=detail_auc.get("orgAddress") or None,
            contact_phone=detail_auc.get("tellNumber") or detail_auc.get("foneNumber"),
            contact_email=detail_auc.get("email"),
            status=status,
            attachments=attachments,
            fingerprint="",
        )

    @staticmethod
    def _int_or_none(value) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_list_file(list_file: list) -> list[AuctionAttachment]:
        out = []
        for item in list_file:
            name = item.get("fileName") or ""
            link = item.get("linkFile") or ""
            if not link:
                continue
            file_url = (
                f"{DGTS_DOWNLOAD_BASE}?name={quote(name or 'document.pdf')}&path={quote(link)}"
            )
            out.append(
                AuctionAttachment(
                    file_name=name or None,
                    file_url=file_url,
                    file_type="application/pdf",
                )
            )
        return out

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
