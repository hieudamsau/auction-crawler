from enum import Enum


class SourceId(str, Enum):
    DGTS_MOJ = "dgts_moj"
    TAISANCONG = "taisancong"


class AssetType(str, Enum):
    REAL_ESTATE = "REAL_ESTATE"
    VEHICLE = "VEHICLE"
    EQUIPMENT = "EQUIPMENT"
    OTHER = "OTHER"


class AssetSubType(str, Enum):
    QUYEN_SU_DUNG_DAT = "QUYEN_SU_DUNG_DAT"
    DAT_VA_TAI_SAN_GAN_LIEN = "DAT_VA_TAI_SAN_GAN_LIEN"
    CAN_HO = "CAN_HO"
    NHA_O = "NHA_O"
    DAT_NONG_NGHIEP = "DAT_NONG_NGHIEP"
    MAT_BANG_CHO_THUE = "MAT_BANG_CHO_THUE"
    DU_AN_KHU_DAN_CU = "DU_AN_KHU_DAN_CU"
    OTHER_RE = "OTHER_RE"


class AuctionCategory(str, Enum):
    """
    Phân loại theo Luật Đấu giá tài sản 2016 (sửa đổi 2024) — nhóm mặt hàng hay đấu giá.
    Chỉ gán cho BĐS; mặt khác để None hoặc OTHER.
    """
    QUYEN_SU_DUNG_DAT = "quyen_su_dung_dat"           # Đất ở đô thị, nông nghiệp, công nghiệp, tái định cư
    NHA_O_CAN_HO = "nha_o_can_ho_chung_cu"            # Nhà ở riêng lẻ, căn hộ, shophouse, nhà thấp tầng
    NHA_DAT_THI_HANH_AN = "nha_dat_thi_hanh_an"      # Tài sản bảo đảm, thế chấp ngân hàng, nợ xấu
    DAT_DU_AN = "dat_du_an"                           # Đất dự án, khu đô thị, đất làm nhà ở thấp tầng
    TAI_SAN_CONG_GAN_BDS = "tai_san_cong_gan_bds"    # Nhà công vụ, đất công tịch thu, dự án vốn NN
    OTHER = "other"


class AuctionStatus(str, Enum):
    UPCOMING = "UPCOMING"
    ONGOING = "ONGOING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class CrawlStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    RUNNING = "running"


# dgts.moj.gov.vn property type IDs relevant to BĐS
DGTS_REAL_ESTATE_PROPERTY_TYPE_IDS = {
    173,  # LTS_03: Quyền sử dụng đất
}

DGTS_POSSIBLY_REAL_ESTATE_TYPE_IDS = {
    174,  # LTS_04: Tài sản bảo đảm (often BĐS as collateral)
    176,  # LTS_01: Tài sản nhà nước
    178,  # LTS_05: Tài sản thi hành án
    326,  # LTS_KHAC: Tài sản cá nhân, tổ chức
}
