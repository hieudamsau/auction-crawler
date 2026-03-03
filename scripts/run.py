import asyncio
import click

from src.utils.logger import setup_logging, get_logger
from config.settings import settings


@click.group()
def cli():
    """Vietnam Auction Crawler Service"""
    setup_logging(settings.log_level)


@cli.command()
@click.option("--source", type=click.Choice(["dgts_moj", "taisancong", "all"]), default="all")
@click.option("--start-page", type=int, default=1)
@click.option("--max-pages", type=int, default=None)
@click.option("--with-detail", is_flag=True, default=False, help="Fetch detail pages (taisancong)")
@click.option("--all-types", is_flag=True, default=False, help="Crawl all asset types, not just BĐS")
def full_crawl(source, start_page, max_pages, with_detail, all_types):
    """Run a full historical crawl."""
    asyncio.run(_full_crawl(source, start_page, max_pages, with_detail, all_types))


@cli.command()
@click.option("--source", type=click.Choice(["dgts_moj", "taisancong", "all"]), default="all")
@click.option("--max-pages", type=int, default=50)
def incremental(source, max_pages):
    """Run an incremental crawl (new items only)."""
    asyncio.run(_incremental_crawl(source, max_pages))


@cli.command()
def scheduler():
    """Start the scheduled crawler (runs continuously)."""
    asyncio.run(_run_scheduler())


@cli.command()
def init_db():
    """Create database tables."""
    asyncio.run(_init_db())


@cli.command()
@click.option("--source", type=click.Choice(["dgts_moj"]), default="dgts_moj")
def seed_reference(source):
    """Fetch and save reference data (provinces, property types, orgs)."""
    asyncio.run(_seed_reference(source))


@cli.command()
def stats():
    """Show crawl statistics."""
    asyncio.run(_show_stats())


async def _full_crawl(source, start_page, max_pages, with_detail, all_types):
    from src.crawlers.dgts_moj import DgtsMojCrawler
    from src.crawlers.taisancong import TaiSanCongCrawler
    from src.parsers.dgts_moj import DgtsMojParser
    from src.parsers.taisancong import TaiSanCongParser
    from src.pipeline.orchestrator import CrawlPipeline
    from src.storage.raw_store import RawStore
    from src.database.engine import AsyncSessionLocal
    from src.utils.http_client import ThrottledHttpClient

    logger = get_logger("full_crawl")

    from src.utils.browser import BrowserManager

    async with ThrottledHttpClient(
        delay=settings.crawl.delay_between_pages,
        timeout=settings.crawl.request_timeout,
        user_agent=settings.crawl.user_agent,
    ) as http_client:
        raw_store = RawStore(settings.raw_data_dir)

        if source in ("dgts_moj", "all"):
            logger.info("Starting full crawl: dgts_moj")
            async with BrowserManager(headless=True) as browser:
                crawler = DgtsMojCrawler(http_client, page_size=settings.crawl.page_size_dgts, browser=browser)
                parser = DgtsMojParser()

                async with AsyncSessionLocal() as session:
                    pipeline = CrawlPipeline(
                        crawler=crawler,
                        parser=parser,
                        session=session,
                        raw_store=raw_store,
                        crawl_detail=with_detail,
                        only_real_estate=not all_types,
                        delay_between_pages=settings.crawl.delay_between_pages,
                        delay_between_details=settings.crawl.delay_between_details,
                    )
                    result = await pipeline.run_full_crawl(
                        start_page=start_page,
                        max_pages=max_pages,
                    )
                    logger.info("dgts_moj full crawl done", stats=result)

        if source in ("taisancong", "all"):
            logger.info("Starting full crawl: taisancong")
            crawler = TaiSanCongCrawler(http_client)
            parser = TaiSanCongParser()

            async with AsyncSessionLocal() as session:
                pipeline = CrawlPipeline(
                    crawler=crawler,
                    parser=parser,
                    session=session,
                    raw_store=raw_store,
                    crawl_detail=with_detail,
                    only_real_estate=not all_types,
                    delay_between_pages=settings.crawl.delay_between_details,
                )
                result = await pipeline.run_full_crawl(
                    start_page=0,
                    max_pages=max_pages,
                )
                logger.info("taisancong full crawl done", stats=result)


async def _incremental_crawl(source, max_pages):
    from src.crawlers.dgts_moj import DgtsMojCrawler
    from src.crawlers.taisancong import TaiSanCongCrawler
    from src.parsers.dgts_moj import DgtsMojParser
    from src.parsers.taisancong import TaiSanCongParser
    from src.pipeline.orchestrator import CrawlPipeline
    from src.storage.raw_store import RawStore
    from src.database.engine import AsyncSessionLocal
    from src.utils.http_client import ThrottledHttpClient

    from src.utils.browser import BrowserManager

    logger = get_logger("incremental")

    async with ThrottledHttpClient(
        delay=settings.crawl.delay_between_pages,
        timeout=settings.crawl.request_timeout,
        user_agent=settings.crawl.user_agent,
    ) as http_client:
        raw_store = RawStore(settings.raw_data_dir)

        if source in ("dgts_moj", "all"):
            async with BrowserManager(headless=True) as browser:
                crawler = DgtsMojCrawler(http_client, page_size=settings.crawl.page_size_dgts, browser=browser)
                parser = DgtsMojParser()
                async with AsyncSessionLocal() as session:
                    pipeline = CrawlPipeline(
                        crawler=crawler, parser=parser, session=session,
                        raw_store=raw_store, crawl_detail=True,
                        only_real_estate=True,
                        delay_between_pages=settings.crawl.delay_between_pages,
                        delay_between_details=settings.crawl.delay_between_details,
                    )
                    await pipeline.run_incremental_crawl(max_pages=max_pages)

        if source in ("taisancong", "all"):
            crawler = TaiSanCongCrawler(http_client)
            parser = TaiSanCongParser()
            async with AsyncSessionLocal() as session:
                pipeline = CrawlPipeline(
                    crawler=crawler, parser=parser, session=session,
                    raw_store=raw_store, crawl_detail=True,
                    only_real_estate=True,
                    delay_between_pages=settings.crawl.delay_between_details,
                )
                await pipeline.run_incremental_crawl(max_pages=max_pages)


async def _run_scheduler():
    from src.pipeline.scheduler import create_scheduler
    logger = get_logger("scheduler")
    logger.info("Starting scheduler...")

    scheduler = create_scheduler()
    scheduler.start()

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Scheduler stopped")


async def _init_db():
    from src.models.db import Base
    from src.database.engine import async_engine

    logger = get_logger("init_db")
    logger.info("Creating database tables...")

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables created successfully")


async def _seed_reference(source):
    from src.crawlers.dgts_moj import DgtsMojCrawler
    from src.storage.raw_store import RawStore
    from src.utils.http_client import ThrottledHttpClient
    from src.utils.browser import BrowserManager

    logger = get_logger("seed_reference")

    async with ThrottledHttpClient(
        delay=1.0,
        timeout=settings.crawl.request_timeout,
        user_agent=settings.crawl.user_agent,
    ) as http_client:
        async with BrowserManager(headless=True) as browser:
            crawler = DgtsMojCrawler(http_client, browser=browser)
            raw_store = RawStore(settings.raw_data_dir)

            for ref_type in ["property_types", "provinces", "organizations"]:
                logger.info(f"Fetching {ref_type}...")
                data = await crawler.fetch_reference_data(ref_type)
                path = raw_store.save_api_response(source, ref_type, data)
                logger.info(f"Saved {ref_type}", count=len(data), path=path)

            import json, os
            ref_dir = os.path.join("src", "reference_data")

            provinces = await crawler.fetch_reference_data("provinces")
            with open(os.path.join(ref_dir, "provinces.json"), "w", encoding="utf-8") as f:
                json.dump(provinces, f, ensure_ascii=False, indent=2)

            prop_types = await crawler.fetch_reference_data("property_types")
            with open(os.path.join(ref_dir, "property_types.json"), "w", encoding="utf-8") as f:
                json.dump(prop_types, f, ensure_ascii=False, indent=2)

            orgs = await crawler.fetch_reference_data("organizations")
            with open(os.path.join(ref_dir, "organizations.json"), "w", encoding="utf-8") as f:
                json.dump(orgs, f, ensure_ascii=False, indent=2)

            logger.info("Reference data seeded successfully")


async def _show_stats():
    from src.database.engine import AsyncSessionLocal
    from src.database.repository import AuctionRepository

    logger = get_logger("stats")

    async with AsyncSessionLocal() as session:
        repo = AuctionRepository(session)
        dgts_count = await repo.count_by_source("dgts_moj")
        tsc_count = await repo.count_by_source("taisancong")
        re_count = await repo.count_real_estate()

        logger.info(
            "Database statistics",
            dgts_moj_items=dgts_count,
            taisancong_items=tsc_count,
            total=dgts_count + tsc_count,
            real_estate=re_count,
        )


if __name__ == "__main__":
    cli()
