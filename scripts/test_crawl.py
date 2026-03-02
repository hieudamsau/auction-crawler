"""
Quick smoke test: Crawl 1 page from each source, parse, classify, and print results.
No database required.
"""
import asyncio
import sys
import os
import json

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.logger import setup_logging, get_logger
from src.utils.http_client import ThrottledHttpClient
from src.crawlers.dgts_moj import DgtsMojCrawler
from src.crawlers.taisancong import TaiSanCongCrawler
from src.parsers.dgts_moj import DgtsMojParser
from src.parsers.taisancong import TaiSanCongParser
from src.enrichment.classifier import AssetClassifier
from src.enrichment.geo import GeoNormalizer
from src.enrichment.area_extractor import AreaExtractor
from src.enrichment.dedup import Deduplicator


async def test_dgts_moj():
    logger = get_logger("test_dgts")
    logger.info("=== Testing dgts.moj.gov.vn crawler ===")

    from src.utils.browser import BrowserManager

    async with ThrottledHttpClient(delay=1.0, timeout=30.0) as http:
        async with BrowserManager(headless=True) as browser:
            crawler = DgtsMojCrawler(http, page_size=10, browser=browser)
            parser = DgtsMojParser()
            classifier = AssetClassifier()
            geo = GeoNormalizer()
            area_ext = AreaExtractor()
            dedup = Deduplicator()

            items = []
            async for raw_item in crawler.crawl_list(page=1):
                items.append(raw_item)

            logger.info(f"Fetched {len(items)} raw items from page 1")
            logger.info(f"Total records on server: {crawler.total_records}")
            logger.info(f"Total pages: {crawler.total_pages}")

            re_count = 0
            for raw_item in items:
                normalized = parser.parse(raw_item)
                normalized = classifier.classify(normalized)
                normalized = geo.enrich(normalized)
                normalized = area_ext.enrich(normalized)
                normalized.fingerprint = dedup.generate_fingerprint(normalized)

                is_re = "BĐS" if normalized.asset_type.value == "REAL_ESTATE" else "---"
                logger.info(
                    f"[{is_re}] {normalized.title[:80]}...",
                    asset_type=normalized.asset_type.value,
                    sub_type=normalized.asset_sub_type.value if normalized.asset_sub_type else None,
                    province=normalized.province_code,
                    area=normalized.land_area,
                    auction_date=str(normalized.auction_datetime)[:10] if normalized.auction_datetime else None,
                )
                if normalized.asset_type.value == "REAL_ESTATE":
                    re_count += 1

            logger.info(f"Real estate items: {re_count}/{len(items)}")
            return items


async def test_taisancong():
    logger = get_logger("test_tsc")
    logger.info("=== Testing taisancong.vn crawler ===")

    async with ThrottledHttpClient(delay=1.5, timeout=30.0) as http:
        crawler = TaiSanCongCrawler(http)
        parser = TaiSanCongParser()
        classifier = AssetClassifier()
        geo = GeoNormalizer()
        area_ext = AreaExtractor()
        dedup = Deduplicator()

        items = []
        async for raw_item in crawler.crawl_list(page=0):
            items.append(raw_item)

        logger.info(f"Fetched {len(items)} raw items from page 0")

        if items:
            logger.info("Fetching detail for first item...")
            items[0] = await crawler.crawl_detail(items[0])

        re_count = 0
        for raw_item in items:
            normalized = parser.parse(raw_item)
            normalized = classifier.classify(normalized)
            normalized = geo.enrich(normalized)
            normalized = area_ext.enrich(normalized)
            normalized.fingerprint = dedup.generate_fingerprint(normalized)

            is_re = "BĐS" if normalized.asset_type.value == "REAL_ESTATE" else "---"
            logger.info(
                f"[{is_re}] {normalized.title[:80]}...",
                asset_type=normalized.asset_type.value,
                sub_type=normalized.asset_sub_type.value if normalized.asset_sub_type else None,
                province=normalized.province_code,
                area=normalized.land_area,
            )
            if normalized.asset_type.value == "REAL_ESTATE":
                re_count += 1

        logger.info(f"Real estate items: {re_count}/{len(items)}")
        return items


async def main():
    setup_logging("INFO")
    logger = get_logger("test")

    logger.info("Starting crawler smoke test...")

    await test_dgts_moj()
    print("\n" + "=" * 80 + "\n")
    await test_taisancong()

    logger.info("Smoke test completed!")


if __name__ == "__main__":
    asyncio.run(main())
