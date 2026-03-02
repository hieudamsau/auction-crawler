from abc import ABC, abstractmethod

from src.models.domain import RawAuctionItem, NormalizedAuctionItem


class BaseParser(ABC):
    """Transform source-specific raw data into the unified normalized schema."""

    @abstractmethod
    def parse(self, raw_item: RawAuctionItem) -> NormalizedAuctionItem:
        ...
