# Tài liệu kiến trúc tổng thể — Auction Crawler Service

## 1. Tổng quan hệ thống

Auction Crawler Service là service backend chuyên crawl, chuẩn hóa, phân loại và lưu trữ dữ liệu đấu giá từ các nền tảng đấu giá Việt Nam vào một master database duy nhất, phục vụ cho trang web listing.

**Phase 1 hiện tại** tập trung vào tài sản **Bất động sản (BĐS)** từ 2 nguồn:

| Nguồn | URL | Tổng records | Phương pháp crawl |
|-------|-----|-------------|-------------------|
| Bộ Tư pháp (DGTS) | dgts.moj.gov.vn | ~524,000 | Playwright stealth + JSON API |
| Tài sản công | taisancong.vn | ~32,000 | httpx + HTML scraping |

---

## 2. Sơ đồ luồng tổng thể

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              CLI (scripts/run.py)                            │
│         full-crawl  │  incremental  │  scheduler  │  seed-reference          │
└────────────┬────────┴───────┬───────┴──────┬──────┴──────────────────────────┘
             │                │              │
             ▼                ▼              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                        Pipeline Orchestrator                                 │
│                    (src/pipeline/orchestrator.py)                             │
│                                                                              │
│   ┌─────────┐    ┌──────────┐    ┌────────┐    ┌───────────┐    ┌────────┐  │
│   │ CRAWL   │ →  │ RAW STORE│ →  │ PARSE  │ →  │ ENRICH    │ →  │ SAVE   │  │
│   │         │    │          │    │        │    │           │    │ TO DB  │  │
│   └─────────┘    └──────────┘    └────────┘    └───────────┘    └────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
      │                │               │              │                │
      ▼                ▼               ▼              ▼                ▼
  Crawlers         Filesystem       Parsers      Enrichment       PostgreSQL
  (Bước 1)         (Bước 2)        (Bước 3)     (Bước 4)         (Bước 5)
```

---

## 3. Chi tiết từng bước

### Bước 1 — CRAWL (Thu thập dữ liệu thô)

Mỗi nguồn có một crawler adapter riêng, nhưng đều kế thừa chung interface `BaseCrawler`.

#### dgts.moj.gov.vn

- **Phương pháp**: Playwright headless browser (stealth mode) → gọi REST API bằng `fetch()` bên trong browser context
- **Lý do**: Trang này có **FEC WAF** (Web Application Firewall) với:
  - JavaScript challenge bắt buộc giải trước khi truy cập
  - TLS fingerprinting → cookies từ browser không chuyển được sang httpx
  - Bot detection phát hiện Playwright mặc định
- **Giải pháp stealth**: Vô hiệu hóa `navigator.webdriver`, giả lập plugins/languages, set timezone `Asia/Ho_Chi_Minh`
- **Thời gian khởi tạo**: ~12 giây (chờ WAF challenge + AngularJS load)
- **API endpoint**: `GET /portal/search/auction-notice?p={page}&numberPerPage={size}&typeOrder=2`
- **Response**: JSON với `items[]`, `pageCount`, `rowCount`
- **Không cần crawl detail**: API list đã trả đủ dữ liệu (field `propertyName` chứa full text)
- **Pagination**: page-based (1-indexed), mặc định 50 items/page

#### taisancong.vn

- **Phương pháp**: httpx (HTTP GET) + BeautifulSoup4 (parse HTML)
- **Không cần Playwright**: Trang SSR, không có WAF
- **Cấu trúc HTML**: Div-based layout (KHÔNG phải `<table>`)
  - `div.b-stt` → STT
  - `div.b-tsb` → Tiêu đề + link chi tiết
  - `div.b-dvico` → Đơn vị có tài sản
  - `div.b-dvb` → Đơn vị đấu giá
  - `div.b-tdban` → Thời gian bán hồ sơ
  - `div.b-ngayban` → Ngày đấu giá
  - `div.b-address` → Địa điểm
- **Cần crawl detail**: Trang list chỉ có thông tin tóm tắt. Trang chi tiết có table 14 fields + link PDF
- **Pagination**: Offset-based `&BRSR=0`, `&BRSR=20`, `&BRSR=40`... (20 items/page, 0-indexed)

#### Output chung của Bước 1

Mỗi item trở thành một `RawAuctionItem` gồm:
- `source_id`: Nguồn (dgts_moj / taisancong)
- `source_item_id`: ID gốc trên nguồn
- `source_url`: URL chi tiết
- `raw_title`: Tiêu đề gốc
- `raw_description`: Mô tả gốc (nếu có)
- `raw_fields`: Dict chứa toàn bộ dữ liệu gốc chưa xử lý

---

### Bước 2 — RAW STORE (Lưu trữ dữ liệu thô)

Toàn bộ dữ liệu thô được lưu ra filesystem **trước khi** parse/enrich.

**Cấu trúc thư mục**:
```
data/raw/
├── dgts_moj/
│   ├── 2026-03-01/
│   │   ├── page_1.json
│   │   ├── page_2.json
│   │   └── ...
│   └── checkpoint.json       ← Vị trí crawl cuối cùng
├── taisancong/
│   ├── 2026-03-01/
│   │   ├── page_0.json
│   │   └── ...
│   └── checkpoint.json
```

**Mục đích**:
- Cho phép **re-parse** mà không cần re-crawl (tiết kiệm thời gian + tránh bị block)
- Debug khi parser/enricher có bug
- Audit trail

**Checkpoint**: Mỗi 10 trang ghi lại `last_page`, `total_pages`, `items_processed`, `last_crawled_at`. Khi restart, crawl tiếp từ checkpoint.

---

### Bước 3 — PARSE (Chuẩn hóa dữ liệu)

Mỗi nguồn có parser riêng, chuyển `RawAuctionItem` → `NormalizedAuctionItem` với schema thống nhất.

#### dgts_moj parser
- Timestamp: Unix milliseconds → UTC datetime (field `aucTime`, `aucRegTimeStart`, `publishTime2`)
- Title: Nối `titleName` + `subPropertyName`
- Description: `propertyName` (full text, không bị cắt)
- Org: `org_name`, Owner: `fullname`
- Property type: Giữ nguyên `propertyTypeId` + `propertyTypeName` để classifier dùng

#### taisancong parser
- Ngày giờ: Parse format `DD-MM-YYYY HH:MM` từ text tiếng Việt
- Khoảng thời gian: Tách "từ ngày ... đến ngày ..." thành start/end datetime
- PDF attachments: Giữ link, không download
- Chi tiết: Map từ label tiếng Việt (vd: "7. Nội dung tài sản bán") sang field chuẩn

#### Output: NormalizedAuctionItem
Schema thống nhất ~30 fields: title, description, asset_type, starting_price, auction_datetime, auction_location, province_code, land_area, fingerprint, attachments...

---

### Bước 4 — ENRICH (Làm giàu dữ liệu)

4 bộ enricher chạy tuần tự trên mỗi item:

#### 4a. Asset Classifier — Phân loại BĐS

**Logic phân loại 3 tầng** (theo thứ tự ưu tiên):

1. **propertyTypeId** (chỉ dgts): Nếu `propertyTypeId = 173` → chắc chắn BĐS
2. **Keyword matching**: Tìm trong title + description:
   - **Include patterns** (18 regex): "quyền sử dụng đất", "thửa đất số", "căn hộ", "nhà ở", "chung cư", "biệt thự", "lô đất", "QSDĐ", "đất nông nghiệp"...
   - **Exclude patterns** (4 regex): "cho thuê mặt bằng căn tin", "giữ xe", "kiốt", "quầy nước" → loại ra dù có từ khóa BĐS
3. **Mặc định**: `OTHER`

**Sub-type classification** (7 loại BĐS):
- `QUYEN_SU_DUNG_DAT`: "quyền sử dụng đất", "QSDĐ"
- `DAT_VA_TAI_SAN_GAN_LIEN`: "quyền sử dụng đất...tài sản gắn liền"
- `CAN_HO`: "căn hộ", "chung cư"
- `NHA_O`: "nhà ở", "biệt thự"
- `DAT_NONG_NGHIEP`: "đất nông nghiệp", "nuôi trồng"
- `DU_AN_KHU_DAN_CU`: "khu dân cư", "khu phức hợp"
- `MAT_BANG_CHO_THUE`: "mặt bằng"

> **Lưu ý**: Nhiều BĐS trên dgts có `propertyTypeId = null` (thuộc nhóm "tài sản bảo đảm", "tài sản thi hành án"). Keyword matching là bắt buộc, không thể chỉ dựa vào propertyTypeId.

#### 4b. Geo Normalizer — Chuẩn hóa địa lý

- Ghép 4 trường text: `auction_location` + `asset_location` + `description` + `title`
- Tìm **alias dài nhất trước** (longest match first) trong danh sách 63 tỉnh/thành
- Mỗi tỉnh có 3-6 aliases (vd: "hồ chí minh", "tp hcm", "sài gòn", "saigon")
- Output: `province_code` (mã tỉnh 2 chữ số theo chuẩn Việt Nam)

> **Lưu ý**: Thuật toán tìm alias dài nhất giúp tránh false positive. Vd: "Bà Rịa - Vũng Tàu" match trước "Bà Rịa" hoặc "Vũng Tàu".

#### 4c. Area Extractor — Trích diện tích

- 4 regex patterns: "diện tích 1.926,8 m2", "DT: 179,5m²", "tổng diện tích 300m2"
- **Parse số kiểu Việt Nam**: Dấu `.` là phân cách hàng nghìn, dấu `,` là phần thập phân
  - `73.051,30` → `73051.30` m²
  - `179,5` → `179.5` m²
- Trích mục đích sử dụng đất: "MĐSD: đất ở tại nông thôn"

> **Lưu ý**: Regex có thể trùng với diện tích mặt bằng cho thuê (10m2, 40m2). Kết hợp với classifier đã loại exclude patterns, nhưng vẫn nên kiểm tra khi review data.

#### 4d. Deduplicator — Loại trùng

- Tạo fingerprint: `SHA-256(normalized_title | auction_date | org_name | starting_price)`
- Normalize: lowercase, collapse whitespace, strip punctuation
- Dùng cho:
  - **Cross-source**: Cùng một BĐS đăng trên cả 2 trang
  - **Within-source**: Cùng item crawl nhiều lần

> **Lưu ý**: Fingerprint không phải unique constraint chính. Primary dedup dựa vào `(source_id, source_item_id)`. Fingerprint dùng để detect cross-source duplicates.

---

### Bước 5 — SAVE TO DB (Lưu vào PostgreSQL)

- **Upsert** (INSERT ... ON CONFLICT DO UPDATE) trên `(source_id, source_item_id)`
- Nếu item đã tồn tại → update các field thay đổi + `last_crawled_at`
- Nếu item mới → insert + tạo attachments
- **Crawl log**: Mỗi lần chạy tạo 1 record trong `crawl_logs` với thống kê: found, new, updated, skipped, failed

---

## 4. Hai chế độ crawl

### Full Crawl (Lần đầu / Lịch sử)

```
python scripts/run.py full-crawl --source dgts_moj --max-pages 100
```

- Crawl từ page 1 (hoặc từ checkpoint) → cuối cùng
- Có checkpoint mỗi 10 trang → restart an toàn
- dgts: ~52,000 pages × 1.5s delay = **~22 giờ** cho toàn bộ (50 items/page)
- Chỉ lưu BĐS mặc định (flag `--all-types` để lưu tất cả)

### Incremental Crawl (Hàng ngày)

```
python scripts/run.py incremental --source all
```

- Crawl từ page 1 (mới nhất) → dừng khi gặp page không có item mới
- Thường chỉ cần 1-5 pages
- Scheduler chạy tự động mỗi 6 giờ

---

## 5. Các lưu ý quan trọng

### WAF & Anti-bot

- **dgts.moj.gov.vn** có FEC WAF rất nghiêm ngặt:
  - Headless browser mặc định bị chặn (phải dùng stealth patches)
  - Cookies từ browser không chuyển được sang httpx (TLS fingerprinting)
  - Mỗi lần khởi tạo browser mất ~12 giây để giải WAF challenge
  - **Giải pháp**: Giữ browser context sống suốt session, gọi API bằng `page.evaluate(fetch())` bên trong browser
- **taisancong.vn** hiện chưa có anti-bot, nhưng nên tuân thủ rate limit

### Rate Limiting

- dgts: **1.5 giây** giữa mỗi page request
- taisancong list: **1.5 giây** giữa mỗi page
- taisancong detail: **1.0 giây** giữa mỗi request
- Tất cả có retry exponential backoff (2s → 4s → 8s, tối đa 3 lần)

### Dữ liệu & Chất lượng

- **propertyTypeId = null** chiếm tỉ lệ lớn trên dgts → keyword matching là bắt buộc
- Một số item BĐS không match bất kỳ pattern nào (mô tả quá chung chung) → sẽ bị phân loại `OTHER`. Có thể cải thiện bằng ML ở phase sau
- Diện tích có thể sai nếu text chứa nhiều con số + "m2" (vd: "2 thửa đất 100m2 và 200m2") → lấy giá trị đầu tiên match
- Province detection có thể sai nếu text nhắc đến nhiều tỉnh → lấy tỉnh match đầu tiên (đã sort dài nhất trước)

### Hiệu năng & Tài nguyên

- Playwright headless browser dùng ~200-400MB RAM
- Full crawl dgts 524K items → database ~2-3GB (chỉ BĐS ~50% = ~260K items)
- Raw storage: ~500MB-1GB cho toàn bộ JSON pages
- Checkpoint cho phép resume sau crash/restart mà không mất dữ liệu

### Mở rộng

- Thêm nguồn mới: Tạo crawler + parser mới kế thừa `BaseCrawler` + `BaseParser`, đăng ký trong `registry.py`
- Thêm loại tài sản: Bổ sung patterns trong `classifier.py`, thêm enum trong `enums.py`
- Full-text search: MeiliSearch đã có trong docker-compose, cần thêm indexer module
- ML classification: Thay thế/bổ sung rule-based classifier bằng trained model

---

## 6. Sơ đồ quan hệ các module

```
scripts/run.py (CLI entry)
    │
    ├── CrawlPipeline (orchestrator.py)
    │       │
    │       ├── BaseCrawler ──────────────────────────────┐
    │       │       ├── DgtsMojCrawler (Playwright)       │
    │       │       │       └── BrowserManager (stealth)  │
    │       │       └── TaiSanCongCrawler (httpx + BS4)   │
    │       │                                              │
    │       ├── RawStore ← save_page(), checkpoint         │
    │       │                                              │
    │       ├── BaseParser ────────────────────────────────┤
    │       │       ├── DgtsMojParser                      │ Shared
    │       │       └── TaiSanCongParser                   │ Models
    │       │                                              │
    │       ├── AssetClassifier ───────────────────────────┤
    │       ├── GeoNormalizer                              │
    │       ├── AreaExtractor                              │
    │       ├── Deduplicator                               │
    │       │                                              │
    │       └── AuctionRepository ─────────────────────────┘
    │               └── PostgreSQL (upsert + crawl_log)
    │
    └── APScheduler (mỗi 6h gọi incremental)
```

---

## 7. Bảng tham chiếu nhanh

| Thành phần | File | Vai trò |
|-----------|------|---------|
| Config | `config/settings.py` | Toàn bộ cấu hình (env vars) |
| Enums | `src/models/enums.py` | SourceId, AssetType, AssetSubType, Status |
| Domain Models | `src/models/domain.py` | RawAuctionItem, NormalizedAuctionItem |
| DB Models | `src/models/db.py` | SQLAlchemy ORM (7 indexes trên auction_items) |
| dgts Crawler | `src/crawlers/dgts_moj.py` | Playwright stealth + fetch() API |
| tsc Crawler | `src/crawlers/taisancong.py` | httpx + BeautifulSoup div parsing |
| dgts Parser | `src/parsers/dgts_moj.py` | Unix ms timestamp → datetime |
| tsc Parser | `src/parsers/taisancong.py` | DD-MM-YYYY HH:MM parsing |
| Classifier | `src/enrichment/classifier.py` | 18 include + 4 exclude patterns |
| Geo | `src/enrichment/geo.py` | 63 tỉnh, longest-match-first |
| Area | `src/enrichment/area_extractor.py` | 4 regex, VN number format |
| Dedup | `src/enrichment/dedup.py` | SHA-256 fingerprint |
| Pipeline | `src/pipeline/orchestrator.py` | Full + Incremental + checkpoint |
| Repository | `src/database/repository.py` | Upsert ON CONFLICT |
| Raw Store | `src/storage/raw_store.py` | JSON filesystem |
| Browser | `src/utils/browser.py` | Playwright anti-detect patches |
| HTTP | `src/utils/http_client.py` | Throttle + retry + exponential backoff |
| CLI | `scripts/run.py` | 6 commands (Click) |
