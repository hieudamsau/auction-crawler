from abc import ABC, abstractmethod
from typing import AsyncGenerator

from src.models.domain import RawAuctionItem
from src.models.enums import SourceId
from src.utils.http_client import ThrottledHttpClient
from src.utils.logger import get_logger


class BaseCrawler(ABC):
    """Abstract base for all source-specific crawlers."""

    source_id: SourceId

    def __init__(self, http_client: ThrottledHttpClient):
        self._http_client = http_client
        self._total_pages: int = 0
        self._total_records: int = 0
        self._logger = get_logger(self.__class__.__name__)

    @abstractmethod
    async def crawl_list(self, page: int = 1) -> AsyncGenerator[RawAuctionItem, None]:
        """Yield raw items from a list page."""
        ...

    @abstractmethod
    async def crawl_detail(self, raw_item: RawAuctionItem) -> RawAuctionItem:
        """Enrich a raw item with detail page data. Return as-is if no detail page."""
        ...

    @abstractmethod
    def has_next_page(self, current_page: int) -> bool:
        ...

    @property
    def total_pages(self) -> int:
        return self._total_pages

    @property
    def total_records(self) -> int:
        return self._total_records
