from src.crawlers.base import BaseCrawler
from src.crawlers.dgts_moj import DgtsMojCrawler
from src.crawlers.taisancong import TaiSanCongCrawler
from src.models.enums import SourceId
from src.utils.http_client import ThrottledHttpClient


CRAWLER_REGISTRY: dict[SourceId, type[BaseCrawler]] = {
    SourceId.DGTS_MOJ: DgtsMojCrawler,
    SourceId.TAISANCONG: TaiSanCongCrawler,
}


def create_crawler(source_id: SourceId, http_client: ThrottledHttpClient, **kwargs) -> BaseCrawler:
    crawler_cls = CRAWLER_REGISTRY.get(source_id)
    if not crawler_cls:
        raise ValueError(f"No crawler registered for source: {source_id}")
    return crawler_cls(http_client=http_client, **kwargs)
