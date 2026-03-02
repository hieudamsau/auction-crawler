import hashlib
import re

from src.models.domain import NormalizedAuctionItem
from src.utils.logger import get_logger

logger = get_logger(__name__)


class Deduplicator:
    """
    Generate fingerprint hashes for auction items to detect duplicates
    across sources and within the same source.

    Fingerprint = SHA-256(normalized_title + auction_date + org_name + price)
    """

    def generate_fingerprint(self, item: NormalizedAuctionItem) -> str:
        components = [
            self._normalize_text(item.title),
            item.auction_datetime.strftime("%Y%m%d") if item.auction_datetime else "",
            self._normalize_text(item.auction_org_name or ""),
            str(item.starting_price or 0),
        ]
        raw = "|".join(components)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def are_duplicates(self, a: NormalizedAuctionItem, b: NormalizedAuctionItem) -> bool:
        return a.fingerprint == b.fingerprint

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Lowercase, collapse whitespace, strip punctuation for comparison."""
        text = text.lower().strip()
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"[^\w\s]", "", text)
        return text
