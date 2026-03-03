from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

from src.models.enums import AssetType, AssetSubType, AuctionCategory, AuctionStatus, SourceId


class RawAuctionItem(BaseModel):
    """Raw data straight from source — not yet normalized."""
    source_id: SourceId
    source_item_id: str
    source_url: str
    raw_title: str
    raw_description: Optional[str] = None
    raw_fields: dict = Field(default_factory=dict)


class AuctionAttachment(BaseModel):
    file_name: Optional[str] = None
    file_url: str
    file_type: Optional[str] = None


class NormalizedAuctionItem(BaseModel):
    """Normalized data ready for DB insertion."""
    source_id: SourceId
    source_item_id: str
    source_url: str

    title: str
    description: Optional[str] = None

    asset_type: AssetType = AssetType.OTHER
    asset_sub_type: Optional[AssetSubType] = None
    auction_category: Optional[AuctionCategory] = None  # Phân loại theo Luật Đấu giá (5 nhóm BĐS)

    starting_price: Optional[int] = None
    deposit_amount: Optional[int] = None
    price_step: Optional[int] = None

    auction_org_name: Optional[str] = None
    auction_org_address: Optional[str] = None
    asset_owner_name: Optional[str] = None
    asset_owner_address: Optional[str] = None

    doc_sale_start: Optional[datetime] = None
    doc_sale_end: Optional[datetime] = None
    viewing_start: Optional[datetime] = None
    viewing_end: Optional[datetime] = None
    auction_datetime: Optional[datetime] = None
    publish_date: Optional[datetime] = None

    auction_location: Optional[str] = None
    asset_location: Optional[str] = None
    province_code: Optional[str] = None
    district_code: Optional[str] = None

    land_area: Optional[float] = None
    land_purpose: Optional[str] = None

    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None

    status: AuctionStatus = AuctionStatus.UPCOMING
    auction_method: Optional[str] = None

    property_type_id: Optional[int] = None
    property_type_name: Optional[str] = None

    fingerprint: str = ""
    attachments: list[AuctionAttachment] = Field(default_factory=list)


class CrawlCheckpoint(BaseModel):
    source_id: SourceId
    last_page: int = 0
    total_pages: int = 0
    total_records: int = 0
    items_processed: int = 0
    last_crawled_at: Optional[datetime] = None
