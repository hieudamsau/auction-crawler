import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db import AuctionItemDB, AuctionAttachmentDB, CrawlLogDB
from src.models.domain import NormalizedAuctionItem
from src.models.enums import CrawlStatus
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AuctionRepository:
    """CRUD operations for auction items."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def upsert_item(self, item: NormalizedAuctionItem) -> tuple[uuid.UUID, bool]:
        """
        Insert or update an auction item.
        Returns (item_id, is_new).
        Uses PostgreSQL ON CONFLICT for atomic upsert.
        """
        now = datetime.now(timezone.utc)

        stmt = pg_insert(AuctionItemDB).values(
            source_id=item.source_id.value,
            source_item_id=item.source_item_id,
            source_url=item.source_url,
            title=item.title,
            description=item.description,
            asset_type=item.asset_type.value,
            asset_sub_type=item.asset_sub_type.value if item.asset_sub_type else None,
            auction_category=item.auction_category.value if item.auction_category else None,
            starting_price=item.starting_price,
            deposit_amount=item.deposit_amount,
            price_step=item.price_step,
            auction_org_name=item.auction_org_name,
            auction_org_address=item.auction_org_address,
            asset_owner_name=item.asset_owner_name,
            asset_owner_address=item.asset_owner_address,
            doc_sale_start=item.doc_sale_start,
            doc_sale_end=item.doc_sale_end,
            viewing_start=item.viewing_start,
            viewing_end=item.viewing_end,
            auction_datetime=item.auction_datetime,
            publish_date=item.publish_date,
            auction_location=item.auction_location,
            asset_location=item.asset_location,
            province_code=item.province_code,
            district_code=item.district_code,
            land_area=item.land_area,
            land_purpose=item.land_purpose,
            contact_phone=item.contact_phone,
            contact_email=item.contact_email,
            status=item.status.value,
            auction_method=item.auction_method,
            property_type_id=item.property_type_id,
            property_type_name=item.property_type_name,
            fingerprint=item.fingerprint,
            first_crawled_at=now,
            last_crawled_at=now,
            created_at=now,
            updated_at=now,
        )

        stmt = stmt.on_conflict_do_update(
            index_elements=["source_id", "source_item_id"],
            set_={
                "title": stmt.excluded.title,
                "description": stmt.excluded.description,
                "asset_type": stmt.excluded.asset_type,
                "asset_sub_type": stmt.excluded.asset_sub_type,
                "auction_category": stmt.excluded.auction_category,
                "starting_price": stmt.excluded.starting_price,
                "auction_org_name": stmt.excluded.auction_org_name,
                "asset_owner_name": stmt.excluded.asset_owner_name,
                "auction_datetime": stmt.excluded.auction_datetime,
                "auction_location": stmt.excluded.auction_location,
                "province_code": stmt.excluded.province_code,
                "land_area": stmt.excluded.land_area,
                "land_purpose": stmt.excluded.land_purpose,
                "status": stmt.excluded.status,
                "fingerprint": stmt.excluded.fingerprint,
                "last_crawled_at": now,
                "updated_at": now,
            },
        ).returning(AuctionItemDB.id, AuctionItemDB.first_crawled_at)

        result = await self._session.execute(stmt)
        row = result.one()
        is_new = row.first_crawled_at == now

        if is_new and item.attachments:
            for att in item.attachments:
                att_db = AuctionAttachmentDB(
                    auction_item_id=row.id,
                    file_name=att.file_name,
                    file_url=att.file_url,
                    file_type=att.file_type,
                )
                self._session.add(att_db)

        return row.id, is_new

    async def find_by_source(self, source_id: str, source_item_id: str) -> Optional[AuctionItemDB]:
        stmt = select(AuctionItemDB).where(
            AuctionItemDB.source_id == source_id,
            AuctionItemDB.source_item_id == source_item_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_fingerprint(self, fingerprint: str) -> Optional[AuctionItemDB]:
        stmt = select(AuctionItemDB).where(AuctionItemDB.fingerprint == fingerprint)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_by_source(self, source_id: str) -> int:
        stmt = select(func.count()).select_from(AuctionItemDB).where(
            AuctionItemDB.source_id == source_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def count_real_estate(self) -> int:
        stmt = select(func.count()).select_from(AuctionItemDB).where(
            AuctionItemDB.asset_type == "REAL_ESTATE"
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def create_crawl_log(
        self,
        source_id: str,
        crawl_type: str,
    ) -> CrawlLogDB:
        log = CrawlLogDB(
            source_id=source_id,
            crawl_type=crawl_type,
            started_at=datetime.now(timezone.utc),
            status=CrawlStatus.RUNNING.value,
        )
        self._session.add(log)
        await self._session.flush()
        return log

    async def finish_crawl_log(
        self,
        log: CrawlLogDB,
        status: CrawlStatus,
        items_found: int = 0,
        items_new: int = 0,
        items_updated: int = 0,
        items_skipped: int = 0,
        items_failed: int = 0,
        error_message: str = None,
    ):
        log.finished_at = datetime.now(timezone.utc)
        log.status = status.value
        log.items_found = items_found
        log.items_new = items_new
        log.items_updated = items_updated
        log.items_skipped = items_skipped
        log.items_failed = items_failed
        log.error_message = error_message

    async def commit(self):
        await self._session.commit()

    async def flush(self):
        await self._session.flush()
