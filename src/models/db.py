import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Text,
    BigInteger,
    Numeric,
    DateTime,
    Index,
    ForeignKey,
    JSON,
    Integer,
    ARRAY,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID


class Base(DeclarativeBase):
    pass


class AuctionItemDB(Base):
    __tablename__ = "auction_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[str] = mapped_column(String(50), nullable=False)
    source_item_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)

    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    asset_type: Mapped[str] = mapped_column(String(50), nullable=False, default="OTHER")
    asset_sub_type: Mapped[str | None] = mapped_column(String(100))

    starting_price: Mapped[int | None] = mapped_column(BigInteger)
    deposit_amount: Mapped[int | None] = mapped_column(BigInteger)
    price_step: Mapped[int | None] = mapped_column(BigInteger)

    auction_org_name: Mapped[str | None] = mapped_column(Text)
    auction_org_address: Mapped[str | None] = mapped_column(Text)
    asset_owner_name: Mapped[str | None] = mapped_column(Text)
    asset_owner_address: Mapped[str | None] = mapped_column(Text)

    doc_sale_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    doc_sale_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    viewing_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    viewing_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    auction_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    publish_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    auction_location: Mapped[str | None] = mapped_column(Text)
    asset_location: Mapped[str | None] = mapped_column(Text)
    province_code: Mapped[str | None] = mapped_column(String(10))
    district_code: Mapped[str | None] = mapped_column(String(10))

    land_area: Mapped[float | None] = mapped_column(Numeric(15, 2))
    land_purpose: Mapped[str | None] = mapped_column(String(200))

    contact_phone: Mapped[str | None] = mapped_column(String(50))
    contact_email: Mapped[str | None] = mapped_column(String(255))

    status: Mapped[str] = mapped_column(String(30), default="UPCOMING")
    auction_method: Mapped[str | None] = mapped_column(String(100))

    property_type_id: Mapped[int | None] = mapped_column(Integer)
    property_type_name: Mapped[str | None] = mapped_column(Text)

    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

    raw_storage_path: Mapped[str | None] = mapped_column(Text)
    first_crawled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_crawled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    attachments: Mapped[list["AuctionAttachmentDB"]] = relationship(
        back_populates="auction_item", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("uq_source_item", "source_id", "source_item_id", unique=True),
        Index("idx_fingerprint", "fingerprint", unique=True),
        Index("idx_asset_type", "asset_type"),
        Index("idx_province", "province_code"),
        Index("idx_auction_date", "auction_datetime"),
        Index("idx_status", "status"),
        Index("idx_publish_date", "publish_date"),
    )


class AuctionAttachmentDB(Base):
    __tablename__ = "auction_attachments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    auction_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auction_items.id", ondelete="CASCADE"), nullable=False
    )
    file_name: Mapped[str | None] = mapped_column(String(255))
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    local_path: Mapped[str | None] = mapped_column(Text)
    file_type: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    auction_item: Mapped["AuctionItemDB"] = relationship(back_populates="attachments")


class CrawlLogDB(Base):
    __tablename__ = "crawl_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[str] = mapped_column(String(50), nullable=False)
    crawl_type: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    items_found: Mapped[int] = mapped_column(Integer, default=0)
    items_new: Mapped[int] = mapped_column(Integer, default=0)
    items_updated: Mapped[int] = mapped_column(Integer, default=0)
    items_skipped: Mapped[int] = mapped_column(Integer, default=0)
    items_failed: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)


class ProvinceDB(Base):
    __tablename__ = "provinces"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    dgts_id: Mapped[int | None] = mapped_column(Integer)
    aliases: Mapped[list | None] = mapped_column(ARRAY(String))


class DistrictDB(Base):
    __tablename__ = "districts"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    province_code: Mapped[str] = mapped_column(String(10), ForeignKey("provinces.code"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    aliases: Mapped[list | None] = mapped_column(ARRAY(String))
