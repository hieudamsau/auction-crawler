import re
from typing import Optional

from src.models.domain import NormalizedAuctionItem
from src.utils.logger import get_logger

logger = get_logger(__name__)


# 63 tỉnh/thành Việt Nam with normalized names and aliases
PROVINCE_DATA: list[dict] = [
    {"code": "01", "name": "Hà Nội", "aliases": ["ha noi", "hà nội", "tp. hà nội", "tp hà nội", "thành phố hà nội"]},
    {"code": "02", "name": "Hà Giang", "aliases": ["ha giang", "hà giang", "tỉnh hà giang"]},
    {"code": "04", "name": "Cao Bằng", "aliases": ["cao bang", "cao bằng", "tỉnh cao bằng"]},
    {"code": "06", "name": "Bắc Kạn", "aliases": ["bac kan", "bắc kạn", "tỉnh bắc kạn"]},
    {"code": "08", "name": "Tuyên Quang", "aliases": ["tuyen quang", "tuyên quang", "tỉnh tuyên quang"]},
    {"code": "10", "name": "Lào Cai", "aliases": ["lao cai", "lào cai", "tỉnh lào cai"]},
    {"code": "11", "name": "Điện Biên", "aliases": ["dien bien", "điện biên", "tỉnh điện biên"]},
    {"code": "12", "name": "Lai Châu", "aliases": ["lai chau", "lai châu", "tỉnh lai châu"]},
    {"code": "14", "name": "Sơn La", "aliases": ["son la", "sơn la", "tỉnh sơn la"]},
    {"code": "15", "name": "Yên Bái", "aliases": ["yen bai", "yên bái", "tỉnh yên bái"]},
    {"code": "17", "name": "Hoà Bình", "aliases": ["hoa binh", "hoà bình", "hòa bình", "tỉnh hoà bình"]},
    {"code": "19", "name": "Thái Nguyên", "aliases": ["thai nguyen", "thái nguyên", "tỉnh thái nguyên"]},
    {"code": "20", "name": "Lạng Sơn", "aliases": ["lang son", "lạng sơn", "tỉnh lạng sơn"]},
    {"code": "22", "name": "Quảng Ninh", "aliases": ["quang ninh", "quảng ninh", "tỉnh quảng ninh"]},
    {"code": "24", "name": "Bắc Giang", "aliases": ["bac giang", "bắc giang", "tỉnh bắc giang"]},
    {"code": "25", "name": "Phú Thọ", "aliases": ["phu tho", "phú thọ", "tỉnh phú thọ"]},
    {"code": "26", "name": "Vĩnh Phúc", "aliases": ["vinh phuc", "vĩnh phúc", "tỉnh vĩnh phúc"]},
    {"code": "27", "name": "Bắc Ninh", "aliases": ["bac ninh", "bắc ninh", "tỉnh bắc ninh"]},
    {"code": "30", "name": "Hải Dương", "aliases": ["hai duong", "hải dương", "tỉnh hải dương"]},
    {"code": "31", "name": "Hải Phòng", "aliases": ["hai phong", "hải phòng", "tp. hải phòng", "tp hải phòng", "thành phố hải phòng"]},
    {"code": "33", "name": "Hưng Yên", "aliases": ["hung yen", "hưng yên", "tỉnh hưng yên"]},
    {"code": "34", "name": "Thái Bình", "aliases": ["thai binh", "thái bình", "tỉnh thái bình"]},
    {"code": "35", "name": "Hà Nam", "aliases": ["ha nam", "hà nam", "tỉnh hà nam"]},
    {"code": "36", "name": "Nam Định", "aliases": ["nam dinh", "nam định", "tỉnh nam định"]},
    {"code": "37", "name": "Ninh Bình", "aliases": ["ninh binh", "ninh bình", "tỉnh ninh bình"]},
    {"code": "38", "name": "Thanh Hoá", "aliases": ["thanh hoa", "thanh hoá", "thanh hóa", "tỉnh thanh hoá"]},
    {"code": "40", "name": "Nghệ An", "aliases": ["nghe an", "nghệ an", "tỉnh nghệ an"]},
    {"code": "42", "name": "Hà Tĩnh", "aliases": ["ha tinh", "hà tĩnh", "tỉnh hà tĩnh"]},
    {"code": "44", "name": "Quảng Bình", "aliases": ["quang binh", "quảng bình", "tỉnh quảng bình"]},
    {"code": "45", "name": "Quảng Trị", "aliases": ["quang tri", "quảng trị", "tỉnh quảng trị"]},
    {"code": "46", "name": "Thừa Thiên Huế", "aliases": ["thua thien hue", "thừa thiên huế", "tỉnh thừa thiên huế", "huế"]},
    {"code": "48", "name": "Đà Nẵng", "aliases": ["da nang", "đà nẵng", "tp. đà nẵng", "tp đà nẵng", "thành phố đà nẵng"]},
    {"code": "49", "name": "Quảng Nam", "aliases": ["quang nam", "quảng nam", "tỉnh quảng nam"]},
    {"code": "51", "name": "Quảng Ngãi", "aliases": ["quang ngai", "quảng ngãi", "tỉnh quảng ngãi"]},
    {"code": "52", "name": "Bình Định", "aliases": ["binh dinh", "bình định", "tỉnh bình định"]},
    {"code": "54", "name": "Phú Yên", "aliases": ["phu yen", "phú yên", "tỉnh phú yên"]},
    {"code": "56", "name": "Khánh Hoà", "aliases": ["khanh hoa", "khánh hoà", "khánh hòa", "tỉnh khánh hoà"]},
    {"code": "58", "name": "Ninh Thuận", "aliases": ["ninh thuan", "ninh thuận", "tỉnh ninh thuận"]},
    {"code": "60", "name": "Bình Thuận", "aliases": ["binh thuan", "bình thuận", "tỉnh bình thuận"]},
    {"code": "62", "name": "Kon Tum", "aliases": ["kon tum", "tỉnh kon tum"]},
    {"code": "64", "name": "Gia Lai", "aliases": ["gia lai", "tỉnh gia lai"]},
    {"code": "66", "name": "Đắk Lắk", "aliases": ["dak lak", "đắk lắk", "đăk lăk", "tỉnh đắk lắk"]},
    {"code": "67", "name": "Đắk Nông", "aliases": ["dak nong", "đắk nông", "tỉnh đắk nông"]},
    {"code": "68", "name": "Lâm Đồng", "aliases": ["lam dong", "lâm đồng", "tỉnh lâm đồng", "đà lạt"]},
    {"code": "70", "name": "Bình Phước", "aliases": ["binh phuoc", "bình phước", "tỉnh bình phước"]},
    {"code": "72", "name": "Tây Ninh", "aliases": ["tay ninh", "tây ninh", "tỉnh tây ninh"]},
    {"code": "74", "name": "Bình Dương", "aliases": ["binh duong", "bình dương", "tỉnh bình dương"]},
    {"code": "75", "name": "Đồng Nai", "aliases": ["dong nai", "đồng nai", "tỉnh đồng nai"]},
    {"code": "77", "name": "Bà Rịa - Vũng Tàu", "aliases": ["ba ria vung tau", "bà rịa", "vũng tàu", "tỉnh bà rịa"]},
    {"code": "79", "name": "TP. Hồ Chí Minh", "aliases": ["ho chi minh", "hồ chí minh", "tp. hcm", "tp hcm", "tp. hồ chí minh", "sài gòn", "saigon", "thành phố hồ chí minh"]},
    {"code": "80", "name": "Long An", "aliases": ["long an", "tỉnh long an"]},
    {"code": "82", "name": "Tiền Giang", "aliases": ["tien giang", "tiền giang", "tỉnh tiền giang"]},
    {"code": "83", "name": "Bến Tre", "aliases": ["ben tre", "bến tre", "tỉnh bến tre"]},
    {"code": "84", "name": "Trà Vinh", "aliases": ["tra vinh", "trà vinh", "tỉnh trà vinh"]},
    {"code": "86", "name": "Vĩnh Long", "aliases": ["vinh long", "vĩnh long", "tỉnh vĩnh long"]},
    {"code": "87", "name": "Đồng Tháp", "aliases": ["dong thap", "đồng tháp", "tỉnh đồng tháp"]},
    {"code": "89", "name": "An Giang", "aliases": ["an giang", "tỉnh an giang"]},
    {"code": "91", "name": "Kiên Giang", "aliases": ["kien giang", "kiên giang", "tỉnh kiên giang", "phú quốc"]},
    {"code": "92", "name": "Cần Thơ", "aliases": ["can tho", "cần thơ", "tp. cần thơ", "tp cần thơ", "thành phố cần thơ"]},
    {"code": "93", "name": "Hậu Giang", "aliases": ["hau giang", "hậu giang", "tỉnh hậu giang"]},
    {"code": "94", "name": "Sóc Trăng", "aliases": ["soc trang", "sóc trăng", "tỉnh sóc trăng"]},
    {"code": "95", "name": "Bạc Liêu", "aliases": ["bac lieu", "bạc liêu", "tỉnh bạc liêu"]},
    {"code": "96", "name": "Cà Mau", "aliases": ["ca mau", "cà mau", "tỉnh cà mau"]},
]


class GeoNormalizer:
    """
    Extract and normalize province/district from free-text location fields.
    Uses the official 63 provinces of Vietnam.
    """

    def __init__(self):
        self._province_lookup: list[tuple[str, str]] = []
        self._build_lookup()

    def _build_lookup(self):
        """Build lookup sorted by alias length descending (longest match first)."""
        entries = []
        for prov in PROVINCE_DATA:
            for alias in prov["aliases"]:
                entries.append((alias.lower(), prov["code"]))
            entries.append((prov["name"].lower(), prov["code"]))

        self._province_lookup = sorted(entries, key=lambda x: len(x[0]), reverse=True)

    def enrich(self, item: NormalizedAuctionItem) -> NormalizedAuctionItem:
        location_text = " ".join(filter(None, [
            item.auction_location,
            item.asset_location,
            item.description,
            item.title,
        ]))

        item.province_code = self._extract_province(location_text)
        return item

    def _extract_province(self, text: str) -> Optional[str]:
        if not text:
            return None

        text_lower = text.lower()
        for alias, code in self._province_lookup:
            if alias in text_lower:
                return code
        return None
