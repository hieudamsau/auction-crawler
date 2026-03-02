import re
from typing import Optional

from src.models.domain import NormalizedAuctionItem
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AreaExtractor:
    """
    Extract land area (m²) from auction title/description using regex patterns.
    Handles various Vietnamese formats:
      - "diện tích 1926,8 m2"
      - "DT: 179,5m2"
      - "diện tích: 73.051,30m2"
      - "diện tích 300m2"
      - "2.025,3 m²"
    """

    AREA_PATTERNS = [
        re.compile(
            r"(?:diện\s+tích|DT)[:\s]*(\d[\d.,]*)\s*m[²2]",
            re.IGNORECASE,
        ),
        re.compile(
            r"(\d[\d.,]*)\s*m[²2].*(?:đất|thửa|lô)",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:đất|thửa|lô).*?(\d[\d.,]*)\s*m[²2]",
            re.IGNORECASE,
        ),
        re.compile(
            r"tổng\s+diện\s+tích\s+(\d[\d.,]*)\s*m[²2]",
            re.IGNORECASE,
        ),
    ]

    LAND_PURPOSE_PATTERNS = [
        re.compile(r"mục\s+đích\s+(?:SD|sử\s+dụng)[:\s]*(.*?)(?:[;.]|\s*$)", re.IGNORECASE),
        re.compile(r"(?:MĐSD)[:\s]*(.*?)(?:[;.]|\s*$)", re.IGNORECASE),
    ]

    def enrich(self, item: NormalizedAuctionItem) -> NormalizedAuctionItem:
        text = f"{item.title} {item.description or ''}"

        if item.land_area is None:
            item.land_area = self._extract_area(text)

        if item.land_purpose is None:
            item.land_purpose = self._extract_purpose(text)

        return item

    def _extract_area(self, text: str) -> Optional[float]:
        for pattern in self.AREA_PATTERNS:
            match = pattern.search(text)
            if match:
                return self._parse_vn_number(match.group(1))
        return None

    def _extract_purpose(self, text: str) -> Optional[str]:
        for pattern in self.LAND_PURPOSE_PATTERNS:
            match = pattern.search(text)
            if match:
                purpose = match.group(1).strip()
                if len(purpose) > 5:
                    return purpose[:200]
        return None

    @staticmethod
    def _parse_vn_number(raw: str) -> Optional[float]:
        """
        Parse Vietnamese number format where '.' is thousands separator
        and ',' is decimal separator.
        "73.051,30" → 73051.30
        "179,5" → 179.5
        "300" → 300.0
        """
        try:
            cleaned = raw.replace(".", "").replace(",", ".")
            return float(cleaned)
        except ValueError:
            return None
