import re

from src.models.domain import NormalizedAuctionItem
from src.models.enums import (
    AssetType,
    AssetSubType,
    AuctionCategory,
    DGTS_REAL_ESTATE_PROPERTY_TYPE_IDS,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AssetClassifier:
    """
    Classify auction items into asset types based on keyword matching
    and propertyTypeId from dgts.moj.gov.vn.
    Phase 1: Rule-based. Phase 2: upgrade to ML if needed.
    """

    REAL_ESTATE_PATTERNS = [
        re.compile(r"quyền\s+sử\s+dụng\s+đất", re.IGNORECASE),
        re.compile(r"quyền\s+sở\s+hữu\s+nhà", re.IGNORECASE),
        re.compile(r"tài\s+sản\s+gắn\s+liền\s+với\s+đất", re.IGNORECASE),
        re.compile(r"bất\s+động\s+sản", re.IGNORECASE),
        re.compile(r"thửa\s+đất\s+số", re.IGNORECASE),
        re.compile(r"tờ\s+bản\s+đồ\s+số", re.IGNORECASE),
        re.compile(r"lô\s+đất", re.IGNORECASE),
        re.compile(r"căn\s+hộ", re.IGNORECASE),
        re.compile(r"nhà\s+ở", re.IGNORECASE),
        re.compile(r"chung\s+cư", re.IGNORECASE),
        re.compile(r"biệt\s+thự", re.IGNORECASE),
        re.compile(r"khu\s+đất", re.IGNORECASE),
        re.compile(r"khu\s+dân\s+cư", re.IGNORECASE),
        re.compile(r"khu\s+phức\s+hợp", re.IGNORECASE),
        re.compile(r"đất\s+ở\s+tại", re.IGNORECASE),
        re.compile(r"QSDĐ", re.IGNORECASE),
        re.compile(r"đất\s+nông\s+nghiệp", re.IGNORECASE),
        re.compile(r"đất\s+trồng", re.IGNORECASE),
    ]

    REAL_ESTATE_EXCLUDE_PATTERNS = [
        re.compile(r"cho\s+thuê\s+mặt\s+bằng\s+căn\s+tin", re.IGNORECASE),
        re.compile(r"cho\s+thuê.*giữ\s+xe", re.IGNORECASE),
        re.compile(r"ki\s*[oố]t", re.IGNORECASE),
        re.compile(r"quầy\s+nước", re.IGNORECASE),
    ]

    # Phân loại theo Luật Đấu giá tài sản 2016 (sửa đổi 2024) — thứ tự ưu tiên từ cụ thể → chung.
    AUCTION_CATEGORY_RULES: list[tuple[AuctionCategory, list[re.Pattern]]] = [
        (
            AuctionCategory.TAI_SAN_CONG_GAN_BDS,
            [
                re.compile(r"nhà\s+công\s+vụ", re.IGNORECASE),
                re.compile(r"đất\s+công\s+bị\s+tịch\s+thu", re.IGNORECASE),
                re.compile(r"tịch\s+thu", re.IGNORECASE),
                re.compile(r"vốn\s+nhà\s+nước", re.IGNORECASE),
                re.compile(r"tài\s+sản\s+nhà\s+nước", re.IGNORECASE),
                re.compile(r"sở\s+hữu\s+100\s*%\s*vốn", re.IGNORECASE),
            ],
        ),
        (
            AuctionCategory.NHA_DAT_THI_HANH_AN,
            [
                re.compile(r"thi\s+hành\s+án", re.IGNORECASE),
                re.compile(r"tài\s+sản\s+bảo\s+đảm", re.IGNORECASE),
                re.compile(r"thế\s+chấp", re.IGNORECASE),
                re.compile(r"nợ\s+xấu", re.IGNORECASE),
                re.compile(r"khoản\s+nợ\s+xấu", re.IGNORECASE),
                re.compile(r"tổ\s+chức\s+tín\s+dụng", re.IGNORECASE),
                re.compile(r"bảo\s+đảm\s+của\s+khoản", re.IGNORECASE),
            ],
        ),
        (
            AuctionCategory.DAT_DU_AN,
            [
                re.compile(r"đất\s+dự\s+án", re.IGNORECASE),
                re.compile(r"khu\s+đô\s+thị", re.IGNORECASE),
                re.compile(r"đất\s+làm\s+nhà\s+ở\s+thấp\s+tầng", re.IGNORECASE),
                re.compile(r"dự\s+án\s+khu", re.IGNORECASE),
                re.compile(r"khu\s+dân\s+cư", re.IGNORECASE),
                re.compile(r"khu\s+[aà]\s*xếnh|vườn\s+gàn", re.IGNORECASE),
            ],
        ),
        (
            AuctionCategory.NHA_O_CAN_HO,
            [
                re.compile(r"căn\s+hộ", re.IGNORECASE),
                re.compile(r"chung\s+cư", re.IGNORECASE),
                re.compile(r"nhà\s+ở\s+riêng\s+lẻ", re.IGNORECASE),
                re.compile(r"shophouse", re.IGNORECASE),
                re.compile(r"nhà\s+thấp\s+tầng", re.IGNORECASE),
                re.compile(r"biệt\s+thự", re.IGNORECASE),
                re.compile(r"dự\s+án.*căn\s+hộ", re.IGNORECASE),
            ],
        ),
        (
            AuctionCategory.QUYEN_SU_DUNG_DAT,
            [
                re.compile(r"quyền\s+sử\s+dụng\s+đất", re.IGNORECASE),
                re.compile(r"QSDĐ", re.IGNORECASE),
                re.compile(r"đất\s+ở\s+đô\s+thị", re.IGNORECASE),
                re.compile(r"đất\s+nông\s+nghiệp", re.IGNORECASE),
                re.compile(r"đất\s+công\s+nghiệp", re.IGNORECASE),
                re.compile(r"đất\s+tái\s+định\s+cư", re.IGNORECASE),
                re.compile(r"thửa\s+đất\s+số", re.IGNORECASE),
                re.compile(r"tờ\s+bản\s+đồ", re.IGNORECASE),
                re.compile(r"khu\s+đất\s+\d", re.IGNORECASE),
            ],
        ),
    ]

    SUB_TYPE_RULES: list[tuple[AssetSubType, re.Pattern]] = [
        (AssetSubType.DAT_VA_TAI_SAN_GAN_LIEN, re.compile(
            r"quyền\s+sử\s+dụng\s+đất.*tài\s+sản\s+gắn\s+liền", re.IGNORECASE
        )),
        (AssetSubType.QUYEN_SU_DUNG_DAT, re.compile(
            r"quyền\s+sử\s+dụng\s+đất|QSDĐ", re.IGNORECASE
        )),
        (AssetSubType.DU_AN_KHU_DAN_CU, re.compile(
            r"khu\s+dân\s+cư|khu\s+phức\s+hợp|dự\s+án.*khu", re.IGNORECASE
        )),
        (AssetSubType.CAN_HO, re.compile(r"căn\s+hộ|chung\s+cư", re.IGNORECASE)),
        (AssetSubType.NHA_O, re.compile(r"nhà\s+ở|biệt\s+thự", re.IGNORECASE)),
        (AssetSubType.DAT_NONG_NGHIEP, re.compile(
            r"đất\s+nông\s+nghiệp|nuôi\s+trồng|đất\s+trồng", re.IGNORECASE
        )),
        (AssetSubType.MAT_BANG_CHO_THUE, re.compile(r"mặt\s+bằng", re.IGNORECASE)),
    ]

    def classify(self, item: NormalizedAuctionItem) -> NormalizedAuctionItem:
        text = f"{item.title} {item.description or ''}"
        type_name = (item.property_type_name or "").strip()

        if item.property_type_id in DGTS_REAL_ESTATE_PROPERTY_TYPE_IDS:
            item.asset_type = AssetType.REAL_ESTATE
            item.asset_sub_type = self._detect_sub_type(text)
            item.auction_category = self._detect_auction_category(text, type_name)
            return item

        if self._matches_real_estate(text):
            item.asset_type = AssetType.REAL_ESTATE
            item.asset_sub_type = self._detect_sub_type(text)
            item.auction_category = self._detect_auction_category(text, type_name)
        else:
            item.asset_type = AssetType.OTHER
            item.auction_category = AuctionCategory.OTHER

        return item

    def _matches_real_estate(self, text: str) -> bool:
        is_excluded = any(p.search(text) for p in self.REAL_ESTATE_EXCLUDE_PATTERNS)
        if is_excluded:
            return False
        return any(p.search(text) for p in self.REAL_ESTATE_PATTERNS)

    def _detect_sub_type(self, text: str) -> AssetSubType | None:
        for sub_type, pattern in self.SUB_TYPE_RULES:
            if pattern.search(text):
                return sub_type
        return AssetSubType.OTHER_RE

    def _detect_auction_category(
        self, text: str, property_type_name: str
    ) -> AuctionCategory:
        """Phân loại theo 5 nhóm Luật Đấu giá tài sản (chỉ cho BĐS)."""
        combined = f"{text} {property_type_name}"
        for category, patterns in self.AUCTION_CATEGORY_RULES:
            if any(p.search(combined) for p in patterns):
                return category
        return AuctionCategory.OTHER

    def is_real_estate(self, item: NormalizedAuctionItem) -> bool:
        return item.asset_type == AssetType.REAL_ESTATE
