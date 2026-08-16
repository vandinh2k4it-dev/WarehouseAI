# Backend — Hệ thống Quản lý Kho hàng Thông minh

Khung API + schema DB + module OCR, khớp mục 6.5 / 6.6 / 7 của đề cương.
Đã kiểm tra: schema tạo bảng OK, FastAPI load 13 endpoint OK (test bằng SQLite
in-memory — chưa cần Postgres thật để xác nhận code chạy được).

## 1. Cài đặt

```bash
python -m venv venv && source venv/bin/activate     # hoặc venv\Scripts\activate trên Windows
pip install -r requirements.txt
```

`paddlepaddle` + `paddleocr` khá nặng (vài trăm MB) và cài lần đầu mất thời
gian — cứ để chạy nền trong lúc làm việc khác.

## 2. Tạo file cấu hình `.env`

```bash
cp .env.example .env
```

Mở file `.env` vừa tạo, sửa đúng mật khẩu PostgreSQL thật của bạn:
```
DATABASE_URL=postgresql+psycopg2://postgres:MATKHAU_CUA_BAN@localhost:5432/warehouse_db
```

## 3. Tạo database PostgreSQL

```bash
createdb warehouse_db
psql -d warehouse_db -f db/schema.sql
```

Hoặc để FastAPI tự tạo bảng lúc khởi động (dev only, xem `app/main.py`
`lifespan`) — không cần chạy `schema.sql` thủ công, nhưng nên có file này
sẵn để đối chiếu / khi cần migrate tay.

### Cách nhanh nhất để test ngay — không cần cài Postgres

Có sẵn file **`warehouse_demo.db`** (SQLite) đã nạp sẵn dữ liệu mẫu: 6 sản
phẩm, tồn kho có tình huống sắp hết hàng + sắp hết hạn, 2 phiếu nhập mẫu
(1 khớp, 1 lệch), vài cảnh báo có sẵn — đủ để xem ngay giao diện demo có
dữ liệu, không cần tự tạo tay từng thứ qua Swagger nữa.

```bash
# Windows PowerShell
$env:DATABASE_URL="sqlite:///./warehouse_demo.db"
uvicorn app.main:app --reload
```

Muốn tạo lại dữ liệu mẫu cho DB Postgres thật (thay vì SQLite), chạy:
```bash
python -m db.seed
```
Script tự kiểm tra tránh tạo trùng nếu đã seed rồi (dựa vào SKU `DEMO-...`).

## 4. Chạy server

```bash
uvicorn app.main:app --reload
```

Mở `http://localhost:8000/docs` để xem + thử toàn bộ API (Swagger UI tự sinh).

## 5. Test OCR trên phiếu nhập hàng thật (việc ưu tiên tuần này)

Không cần chạy server, test module OCR độc lập trước:

```bash
python -m ocr.test_ocr duong/dan/anh_phieu_nhap.jpg
```

In ra text thô + từng dòng hàng đã trích xuất (tên, số lượng, mã lô, HSD).
Sửa `SAMPLE_KNOWN_PRODUCTS` trong `ocr/test_ocr.py` bằng vài tên sản phẩm
thật của cửa hàng đã khảo sát để thấy luôn kết quả fuzzy-match.

**Lưu ý quan trọng:** `ocr/ocr_engine.py` dùng PP-Structure để tách bảng
trước — nếu phiếu KHÔNG có khung kẻ bảng rõ (viết tay tự do), code sẽ tự
rơi vào nhánh dự phòng `_parse_plain_text` (đọc từng dòng, độ chính xác
thấp hơn). Nên test lần lượt vài loại phiếu (in máy có khung bảng / in máy
không khung / viết tay) để biết engine đang mạnh — yếu ở đâu, phục vụ mục
9.2 (đánh giá OCR) và rủi ro #2 ở mục 13.

**Sửa lỗi sai dấu tiếng Việt ở tên sản phẩm (mới):** PaddleOCR `lang="vi"`
thực chất dùng chung bộ ký tự "latin" (Pháp/Đức/Việt...), thiếu nhiều tổ
hợp dấu tiếng Việt -> tên sản phẩm hay bị mất/sai dấu (vd "Kẹo" đọc thành
"Keo") dù số/ngày/mã lô vẫn đúng. Từ giờ mặc định dùng kiến trúc lai:
PaddleOCR chỉ lo dò vị trí dòng chữ, VietOCR (model riêng cho tiếng Việt)
đảm nhiệm đọc chữ. Cần cài thêm:
```bash
pip install vietocr
```
Nếu máy yếu / muốn tắt VietOCR để test nhanh, tạo engine với
`ReceiptOCREngine(use_vietocr=False)` để quay lại PaddleOCR thuần (nhanh
hơn nhưng tên sản phẩm có dấu sẽ kém chính xác hơn).

## 6. Demo web (không cần code frontend riêng)

Đã có sẵn 1 trang demo tĩnh (`static/index.html`, thuần HTML/CSS/JS, không
cần build) — FastAPI tự phục vụ luôn, không cần chạy thêm server nào khác:

```bash
uvicorn app.main:app --reload
```

Mở **http://localhost:8000/app/** — trang tự nhận API cùng origin nên
không cần cấu hình gì thêm (có ô đổi API base URL ở góc trên nếu chạy
frontend/backend khác cổng nhau).

Gồm: upload ảnh phiếu → xem kết quả OCR ngay; tạo phiên đếm camera giả lập
+ chạy đối chiếu; xem tồn kho (tất cả / sắp hết hàng / sắp hết hạn); xem
cảnh báo đang mở; danh sách phiếu nhập gần đây. Đủ để demo nhanh cho GVHD
mà không cần gõ `curl`, và cũng là điểm khởi đầu tốt khi làm giao diện
web thật ở tuần sau (mục 14 — phần của Luân).

## 7. Test nhanh toàn luồng qua API (khi đã có server + DB)

```bash
# 1. Upload phiếu, chạy OCR tự động
curl -F "file=@sample_receipt.jpg" -F "store_location=Tạp hoá A" \
     http://localhost:8000/receipts/upload

# 2. Gửi kết quả đếm từ camera (giả lập, chờ notebook YOLOv8 nối vào sau)
curl -X POST http://localhost:8000/camera-sessions \
     -H "Content-Type: application/json" \
     -d '{"counted_quantity": 48, "model_version": "yolov8s_gd1gd2_v1"}'

# 3. Chạy đối chiếu
curl -X POST http://localhost:8000/reconciliation/run \
     -H "Content-Type: application/json" \
     -d '{"receipt_id": 1, "session_id": 1, "threshold_pct": 0.02}'

# 4. Xem tồn kho / cảnh báo
curl http://localhost:8000/inventory
curl http://localhost:8000/alerts
```

## Việc còn để TODO (chưa làm trong khung này, làm ở bước sau)

- `product_id` trong `receipt_line_items` hiện phải map thủ công qua danh
  mục `products` — cần thêm bước "tạo sản phẩm mới nếu OCR đọc ra tên chưa
  từng có trong danh mục" (hiện tại dòng chưa map sẽ bị bỏ qua khi cộng dồn
  tồn kho — xem `_apply_inventory_update`).
- Alembic chưa cấu hình (mới dùng `create_all` cho dev) — nên thêm khi
  schema bắt đầu ổn định, tránh mất dữ liệu lúc đổi cột.
- Chatbot (Claude API, function calling) sẽ gọi vào các endpoint
  `/inventory/low-stock`, `/inventory/expiring-soon`, `/alerts` — có thể
  bắt đầu viết luôn phần "tool definitions" cho Claude API dựa trên các
  endpoint này ở bước tiếp theo.
- Endpoint upload hiện chạy OCR đồng bộ (block request) — khi ảnh nhiều /
  OCR chậm nên chuyển sang background task hoặc queue (Celery/RQ).
