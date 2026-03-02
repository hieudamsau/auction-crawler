import asyncio
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.crawlers.base import BaseCrawler
from src.parsers.base import BaseParser
from src.enrichment.classifier import AssetClassifier
from src.enrichment.geo import GeoNormalizer
from src.enrichment.area_extractor import AreaExtractor
from src.enrichment.dedup import Deduplicator
from src.storage.raw_store import RawStore
from src.database.repository import AuctionRepository
from src.models.enums import CrawlStatus, AssetType
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CrawlPipeline:
    """
    Full pipeline: Crawl → Store Raw → Parse → Enrich → Classify → Save to DB.
    Supports both full historical crawl and incremental crawl.
    """

    def __init__(
        self,
        crawler: BaseCrawler,
        parser: BaseParser,
        session: AsyncSession,
        raw_store: RawStore,
        crawl_detail: bool = False,
        only_real_estate: bool = True,
        delay_between_pages: float = 1.5,
    ):
        self._crawler = crawler
        self._parser = parser
        self._session = session
        self._raw_store = raw_store
        self._crawl_detail = crawl_detail
        self._only_real_estate = only_real_estate
        self._delay = delay_between_pages

        self._classifier = AssetClassifier()
        self._geo = GeoNormalizer()
        self._area_extractor = AreaExtractor()
        self._dedup = Deduplicator()
        self._repo = AuctionRepository(session)

    async def run_full_crawl(
        self,
        start_page: int = 1,
        max_pages: int | None = None,
    ):
        """Crawl all pages from start_page."""
        source_id = self._crawler.source_id.value
        crawl_log = await self._repo.create_crawl_log(source_id, "full")
        await self._repo.commit()

        checkpoint = self._raw_store.load_checkpoint(source_id)
        current_page = checkpoint.get("last_page", start_page)

        stats = {
            "found": 0, "new": 0, "updated": 0,
            "skipped": 0, "failed": 0,
        }

        logger.info(
            "Starting full crawl",
            source=source_id,
            start_page=current_page,
        )

        try:
            while True:
                if max_pages and (current_page - start_page) >= max_pages:
                    logger.info("Reached max_pages limit", max_pages=max_pages)
                    break

                page_items = []
                async for raw_item in self._crawler.crawl_list(current_page):
                    page_items.append(raw_item)

                if not page_items:
                    logger.info("No items on page, stopping", page=current_page)
                    break

                raw_data = [item.model_dump(mode="json") for item in page_items]
                self._raw_store.save_page(source_id, current_page, raw_data)

                for raw_item in page_items:
                    result = await self._process_item(raw_item, stats)

                await self._repo.commit()

                if current_page % 10 == 0:
                    self._raw_store.save_checkpoint(source_id, {
                        "last_page": current_page,
                        "total_pages": self._crawler.total_pages,
                        "total_records": self._crawler.total_records,
                        "items_processed": stats["found"],
                        "last_crawled_at": datetime.now(timezone.utc).isoformat(),
                    })

                logger.info(
                    "Page processed",
                    page=current_page,
                    total_pages=self._crawler.total_pages,
                    stats=stats,
                )

                if not self._crawler.has_next_page(current_page):
                    break

                current_page += 1
                await asyncio.sleep(self._delay)

            await self._repo.finish_crawl_log(
                crawl_log, CrawlStatus.SUCCESS,
                items_found=stats["found"],
                items_new=stats["new"],
                items_updated=stats["updated"],
                items_skipped=stats["skipped"],
                items_failed=stats["failed"],
            )
            await self._repo.commit()

            logger.info("Full crawl completed", source=source_id, stats=stats)

        except Exception as e:
            logger.error("Crawl failed", source=source_id, error=str(e))
            await self._repo.finish_crawl_log(
                crawl_log, CrawlStatus.FAILED,
                items_found=stats["found"],
                items_new=stats["new"],
                items_updated=stats["updated"],
                items_failed=stats["failed"],
                error_message=str(e),
            )
            await self._repo.commit()
            raise

        return stats

    async def run_incremental_crawl(self, max_pages: int = 50):
        """Crawl only the most recent pages (new items since last crawl)."""
        source_id = self._crawler.source_id.value
        crawl_log = await self._repo.create_crawl_log(source_id, "incremental")
        await self._repo.commit()

        stats = {
            "found": 0, "new": 0, "updated": 0,
            "skipped": 0, "failed": 0,
        }

        logger.info("Starting incremental crawl", source=source_id)

        try:
            for page in range(1, max_pages + 1):
                page_items = []
                async for raw_item in self._crawler.crawl_list(page):
                    page_items.append(raw_item)

                if not page_items:
                    break

                raw_data = [item.model_dump(mode="json") for item in page_items]
                self._raw_store.save_page(source_id, page, raw_data)

                new_on_page = 0
                for raw_item in page_items:
                    result = await self._process_item(raw_item, stats)
                    if result == "new":
                        new_on_page += 1

                await self._repo.commit()

                logger.info(
                    "Incremental page",
                    page=page,
                    new_on_page=new_on_page,
                    stats=stats,
                )

                if new_on_page == 0:
                    logger.info("No new items on page, stopping incremental crawl")
                    break

                if not self._crawler.has_next_page(page):
                    break

                await asyncio.sleep(self._delay)

            await self._repo.finish_crawl_log(
                crawl_log, CrawlStatus.SUCCESS,
                items_found=stats["found"],
                items_new=stats["new"],
                items_updated=stats["updated"],
                items_skipped=stats["skipped"],
            )
            await self._repo.commit()

            logger.info("Incremental crawl completed", source=source_id, stats=stats)

        except Exception as e:
            logger.error("Incremental crawl failed", error=str(e))
            await self._repo.finish_crawl_log(
                crawl_log, CrawlStatus.FAILED,
                error_message=str(e),
            )
            await self._repo.commit()
            raise

        return stats

    async def _process_item(self, raw_item, stats: dict) -> str:
        """Process a single raw item through the pipeline. Returns 'new', 'updated', 'skipped', or 'failed'."""
        stats["found"] += 1

        try:
            if self._crawl_detail:
                raw_item = await self._crawler.crawl_detail(raw_item)

            normalized = self._parser.parse(raw_item)

            normalized = self._classifier.classify(normalized)

            if self._only_real_estate and normalized.asset_type != AssetType.REAL_ESTATE:
                stats["skipped"] += 1
                return "skipped"

            normalized = self._geo.enrich(normalized)
            normalized = self._area_extractor.enrich(normalized)
            normalized.fingerprint = self._dedup.generate_fingerprint(normalized)

            item_id, is_new = await self._repo.upsert_item(normalized)

            if is_new:
                stats["new"] += 1
                return "new"
            else:
                stats["updated"] += 1
                return "updated"

        except Exception as e:
            stats["failed"] += 1
            logger.warning(
                "Failed to process item",
                source_item_id=raw_item.source_item_id,
                error=str(e),
            )
            return "failed"
