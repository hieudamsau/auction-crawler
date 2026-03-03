import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from src.pipeline.orchestrator import CrawlPipeline
from src.crawlers.dgts_moj import DgtsMojCrawler
from src.crawlers.taisancong import TaiSanCongCrawler
from src.parsers.dgts_moj import DgtsMojParser
from src.parsers.taisancong import TaiSanCongParser
from src.storage.raw_store import RawStore
from src.database.engine import AsyncSessionLocal
from src.utils.http_client import ThrottledHttpClient
from config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def run_incremental_dgts():
    """Scheduled job: incremental crawl dgts.moj.gov.vn"""
    from src.utils.browser import BrowserManager

    logger.info("Scheduled: incremental crawl dgts_moj")
    async with ThrottledHttpClient(
        delay=settings.crawl.delay_between_pages,
        timeout=settings.crawl.request_timeout,
        user_agent=settings.crawl.user_agent,
    ) as http_client:
        async with BrowserManager(headless=True) as browser:
            crawler = DgtsMojCrawler(http_client, page_size=settings.crawl.page_size_dgts, browser=browser)
            parser = DgtsMojParser()
            raw_store = RawStore(settings.raw_data_dir)

            async with AsyncSessionLocal() as session:
                pipeline = CrawlPipeline(
                    crawler=crawler,
                    parser=parser,
                    session=session,
                    raw_store=raw_store,
                    crawl_detail=True,
                    only_real_estate=True,
                    delay_between_pages=settings.crawl.delay_between_pages,
                    delay_between_details=settings.crawl.delay_between_details,
                )
                await pipeline.run_incremental_crawl(max_pages=50)


async def run_incremental_taisancong():
    """Scheduled job: incremental crawl taisancong.vn"""
    logger.info("Scheduled: incremental crawl taisancong")
    async with ThrottledHttpClient(
        delay=settings.crawl.delay_between_pages,
        timeout=settings.crawl.request_timeout,
        user_agent=settings.crawl.user_agent,
    ) as http_client:
        crawler = TaiSanCongCrawler(http_client)
        parser = TaiSanCongParser()
        raw_store = RawStore(settings.raw_data_dir)

        async with AsyncSessionLocal() as session:
            pipeline = CrawlPipeline(
                crawler=crawler,
                parser=parser,
                session=session,
                raw_store=raw_store,
                crawl_detail=True,
                only_real_estate=True,
                delay_between_pages=settings.crawl.delay_between_details,
            )
            await pipeline.run_incremental_crawl(max_pages=30)


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        run_incremental_dgts,
        trigger=IntervalTrigger(hours=6),
        id="dgts_incremental",
        name="DGTS Moj Incremental Crawl",
        replace_existing=True,
    )

    scheduler.add_job(
        run_incremental_taisancong,
        trigger=IntervalTrigger(hours=6),
        id="taisancong_incremental",
        name="TaiSanCong Incremental Crawl",
        replace_existing=True,
    )

    return scheduler
