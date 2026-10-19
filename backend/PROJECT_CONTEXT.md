# Bối cảnh dự án — ĐỌC FILE NÀY TRƯỚC KHI LÀM BẤT KỲ VIỆC GÌ

Khóa luận tốt nghiệp: **"Hệ thống Quản lý Kho hàng Thông minh dựa trên Thị giác
Máy tính và Chatbot AI"** — Cao Văn Định (CSDL/API, OCR, chatbot, giao diện) +
Nguyễn Thành Luân (thu thập dữ liệu/huấn luyện model YOLOv8), ĐH Công nghiệp
TP.HCM K18, lớp DHKHMT18CTT, GVHD TS. Lê Thị Vĩnh Thanh.

Nếu bạn là Claude (Code hoặc chat) đang hỗ trợ 1 trong 2 thành viên, đọc hết
file này trước — nó tóm tắt mọi quyết định, mọi lỗi đã gặp và cách đã sửa,
để không lặp lại công sức debug hoặc đi ngược lại quyết định đã chốt.

---

## 1. KIẾN TRÚC TỔNG QUAN

FastAPI + PostgreSQL (8 bảng, `db/schema.sql`) làm backend. OCR đọc phiếu
nhập hàng tiếng Việt (VietOCR + PaddleOCR lai). YOLOv8 + ByteTrack đếm số
lượng thùng carton qua camera (KHÔNG phân loại loại hàng bằng thị giác máy
tính — con người chọn loại hàng, camera chỉ đếm số lượng, đây là quyết định
lõi đã duyệt trong đề cương, không được thay đổi). Đối chiếu số đếm với
phiếu nhập để tự động cập nhật tồn kho theo FEFO. Chatbot **Gemini**
(google-genai, function calling, tra DB thật) để nhân viên hỏi đáp tồn
kho/cảnh báo. Giao diện chính là **React PWA** ở thư mục `frontend/` (xem
`CLAUDE.md` ở gốc repo để biết công nghệ, quy tắc nghiệp vụ đã chốt và các
"bẫy" kỹ thuật); hệ thống chạy hoàn toàn trên máy local (đã gỡ Railway).

## 2. TRẠNG THÁI HIỆN TẠI (theo từng phần)

### 2.1 Backend + Database — ĐÃ HOÀN THIỆN, đã test kỹ
- FastAPI + PostgreSQL, 8 bảng, chạy ổn định.
- Đã test 6/6 bước luồng nghiệp vụ qua `test/verify_full_flow.py`; các bản
  sửa gần đây có bài test riêng `test/check_*.py` (chạy trên PostgreSQL thật,
  dùng dữ liệu tạm rồi rollback).
- Data mẫu: **`python -m db.seed_realistic`** (mô phỏng 12 tuần nhập/xuất thực
  tế; hỏi xác nhận gõ `XOA`; tuỳ chọn `--yes --clear-uploads --days N --seed N`).
  `db/seed_main.py` chỉ là bộ demo dàn dựng cũ (30 sản phẩm + tình huống
  dựng sẵn). **CẢNH BÁO: cả hai đều XOÁ SẠCH data cũ** (seed_main có
  `--no-wipe`) — sao lưu trước bằng `pg_dump`.

### 2.2 OCR — ĐÃ HOÀN THIỆN
File: `ocr/ocr_engine.py`. Kiến trúc lai: **PaddleOCR chỉ dò vị trí dòng chữ
(detection)**, **VietOCR đọc chữ (recognition)**. Lý do: PaddleOCR
`lang='vi'` thực chất dùng chung bộ ký tự "latin" với Pháp/Đức, đọc sai/mất
dấu tiếng Việt. Đã test: đọc đúng dấu 100%, đủ 5/5 dòng hàng trên phiếu
thật.

### 2.3 Chatbot — ĐÃ HOÀN THIỆN
Thư mục `app/chatbot/`:
- `service.py` — gọi **Gemini** qua `google-genai` (function calling; hằng
  `MODEL_NAME`, hiện `gemini-3.5-flash-lite` — free tier 500 lượt/ngày), 8
  tool CHỈ ĐỌC truy vấn DB thật (tồn kho, sản phẩm, cảnh báo, phiếu nhập,
  đối chiếu lệch...). Biến môi trường: `GEMINI_API_KEY`, `CHATBOT_MOCK`.
- `mock_service.py` — chế độ mô phỏng, không cần key, tự chọn tool theo từ
  khoá, vẫn tra DB thật (không bịa số). Tự động fallback khi thiếu
  `GEMINI_API_KEY` hoặc Gemini lỗi (vd hết hạn mức 429). Khi chạy thực
  nghiệm chatbot phải dùng Gemini thật — mock định tuyến theo từ khoá nên
  không phản ánh đúng.
- Endpoint: `POST /chatbot/ask`.

### 2.4 Camera + Model YOLOv8 — VỪA HOÀN THÀNH TRAIN, ĐANG TÍCH HỢP
**Luân đã train xong model**, kết quả THẬT trên tập test VN (31 ảnh, 988 vật thể):

| Cấu hình | Precision | Recall | mAP50 | mAP50-95 |
|---|---|---|---|---|
| Chỉ GĐ1 (dữ liệu ngoài) | 0.838 | 0.770 | 0.855 | 0.695 |
| Chỉ VN (baseline) | 0.857 | 0.783 | 0.867 | 0.700 |
| **GĐ1+GĐ2 (đề xuất, dùng chính thức)** | **0.895** | 0.782 | **0.888** | **0.733** |

→ Kết quả xác nhận đúng lý do thiết kế 2 giai đoạn (domain adaptation) —
GĐ1+GĐ2 thắng gần tuyệt đối, số liệu này dùng cho RQ2 và Chương 5 khóa
luận. Biểu đồ so sánh đã có sẵn (`so_sanh_3_cau_hinh.png`, tự sinh trong
notebook Kaggle).

File model cuối: `carton_counter_best.pt` — **phải tải THỦ CÔNG từ tab
Output trên Kaggle** (không nằm trong file `.ipynb`, notebook chỉ chứa
code+log+ảnh). Đặt vào `warehouse-backend/models/carton_counter_best.pt`,
rồi thêm vào `.env`:
```
CARTON_MODEL_PATH=models/carton_counter_best.pt
```

**Quy trình vận hành camera đã CHỐT (đổi 2 lần trong quá trình làm, đây là
bản CUỐI CÙNG):**
1. Nhân viên mở app (web hoặc điện thoại), scan/chọn phiếu nhập.
2. Chọn ĐÚNG 1 loại hàng trên phiếu (vd "Sữa Vinamilk") trước khi loại đó
   đi qua băng chuyền — camera KHÔNG tự phân loại, con người chọn.
3. Bấm bắt đầu đếm → camera đếm số thùng đi qua (chỉ đếm số lượng, 1 class
   duy nhất `carton_box`).
4. Bấm "Xong loại này" → so khớp với số khai báo trên phiếu:
   - Khớp → tự cộng tồn kho ngay, cho qua loại tiếp theo.
   - **Lệch → CHỈ CẢNH BÁO, KHÔNG CHẶN** (đây là quyết định đã đổi — lúc đầu
     thiết kế "chặn cứng", sau đổi thành "skip tự do", nhân viên có toàn
     quyền bỏ qua loại đang lệch, chọn loại khác, quay lại xử lý sau).
5. Quay lại dòng bị lệch bất cứ lúc nào → chọn lại đúng dòng đó = tự động
   hiểu là "đếm lại" (không cần gọi API resolve riêng cho trường hợp này).
6. Xuất hàng: TƯƠNG TỰ nhập, nhưng KHÔNG có phiếu xuất trước — nhân viên gõ
   tay số lượng dự kiến xuất ngay lúc đó để camera đối chiếu.

**API đã code xong, đã tự test kỹ (TestClient, không cần chờ người dùng
debug):**
- `POST /camera-sessions/start-import` — chọn dòng hàng, bắt đầu đếm.
- `POST /camera-sessions/start-export` — chọn sản phẩm + gõ SL dự kiến.
- `POST /camera-sessions/{id}/stop` — "Xong loại này", so khớp, cập nhật
  kho nếu khớp, tạo cảnh báo nếu lệch (KHÔNG chặn).
- `POST /camera-sessions/{id}/count-video` — **MỚI**, nhận video upload
  (từ điện thoại), TỰ đếm bằng YOLOv8 (dùng `CARTON_MODEL_PATH`), rồi gọi
  thẳng logic `/stop` — chỉ 1 lần gọi API duy nhất.
- `POST /camera-sessions/{id}/resolve` — xử lý dòng lệch: `action=recount`
  hoặc `action=override` (bắt buộc `override_note`).
- `GET /receipts/{id}/lines-progress` — tiến độ từng dòng (not_started /
  counting / matched / needs_review / resolved_override).

**UI đã có 2 nơi:**
- `static/index.html` (desktop/admin) — card "2 · Nhập hàng qua camera —
  theo từng loại" + toggle "Xuất qua camera / Xuất tay" trong card xuất kho.
  Widget đếm có nút "+1 mô phỏng" và "▶ Tự động đếm" (giả lập vì chưa nối
  camera thật trên desktop UI này).
- `static/mobile.html` — **MỚI**, trang riêng tối giản cho điện thoại, nút
  to. Dùng `<input type="file" accept="video/*" capture="environment">` để
  mở thẳng camera điện thoại quay video, quay xong TỰ ĐỘNG upload lên
  `/count-video`, tự đếm bằng model thật, tự đối chiếu, hiện kết quả ngay.
  Truy cập: `http://<IP-máy-tính>:8000/app/mobile.html` (điện thoại và máy
  tính phải cùng mạng WiFi).

**`camera/count_pipeline.py`:**
- ĐÃ SỬA lỗi treo (xem mục 3.7 bên dưới). Nay tự đọc video bằng OpenCV, tự
  vẽ khung + số đếm ra `annotated.mp4`, theo dõi từng khung với
  `persist=True`, hỗ trợ giới hạn vùng nhận dạng `--roi` (`camera/pick_roi.py`
  để chọn vùng), cấu hình ByteTrack riêng `camera/carton_bytetrack.yaml`.
- Luồng chính trên giao diện là `/camera-sessions/{id}/count-video` (gọi
  trực tiếp `count_boxes_in_video`, đã chạy trong threadpool để không chặn
  server) rồi `/stop` nội bộ. Endpoint cũ `POST /camera-sessions` và
  `/reconciliation/run` (đối chiếu theo CẢ PHIẾU) chỉ còn để tương thích
  ngược/test, KHÔNG dùng trên giao diện.

**Ghi chú về `static/mobile.html` (trang demo cũ):** từng bị trắng trên
điện thoại, nghi do WiFi bật chế độ cô lập thiết bị (AP/Client Isolation) —
chưa có kết luận. Mục này nhiều khả năng ĐÃ LỖI THỜI: giao diện chính nay là
React PWA (`frontend/`), `static/*.html` chỉ còn là bản demo cũ. Nếu cần dùng
điện thoại truy cập máy tính: chạy `uvicorn ... --host 0.0.0.0`, cùng mạng
WiFi (hoặc bật hotspot) và mở đúng IP máy tính — chưa test bàn phím ảo/camera
trên điện thoại thật.

## 3. CHUỖI LỖI MÔI TRƯỜNG ĐÃ GẶP VÀ CÁCH SỬA (rất hữu ích nếu gặp lại)

1. **`WinError 127 ... torch\lib\shm.dll`** — do thứ tự import: paddlepaddle
   nạp DLL trước làm che DLL torch cần. Fix: import torch (qua vietocr)
   TRƯỚC khi khởi tạo PaddleOCR trong `ocr_engine.py`.
2. **`ModuleNotFoundError: pkg_resources`** — setuptools >=82 gỡ hẳn module
   này, nhưng `gdown` (dependency của vietocr) vẫn dùng kiểu cũ. Fix: ghim
   `setuptools<82` trong `requirements.txt`.
3. **`module 'PIL.Image' has no attribute 'ANTIALIAS'`** — Pillow >=10.0
   xoá hẳn hằng số này. Fix: monkey-patch ở đầu `ocr_engine.py`
   (`Image.ANTIALIAS = Image.Resampling.LANCZOS` nếu chưa có).
4. **Xung đột `albumentations`** giữa paddleocr (cần 1.4.10) và vietocr
   (ghim 1.4.2) — `pip install albumentations==1.4.10 --no-deps` sau khi
   cài `requirements.txt`.
5. **Row-grouping OCR bị xáo trộn thứ tự dòng** — do dùng ngưỡng gộp hàng
   cố định 10px. Fix: ngưỡng động theo chiều cao chữ thực tế
   (`_sort_boxes_into_rows` trong `ocr_engine.py`).
6. **Chatbot mock nhầm "hạn" (han) với "hàng" (hang)** sau khi bỏ dấu — vì
   "han" là chuỗi con của "hang". Fix: so khớp theo từ trọn vẹn (regex
   word-boundary, hàm `_has_word` trong `mock_service.py`), không so khớp
   chuỗi con.
7. **`ultralytics import YOLO` treo vô thời hạn** ở bước
   `kernel32.LoadLibraryExW` khi torch được import GIÁN TIẾP qua
   ultralytics (dù `import torch` ĐỘC LẬP chạy bình thường, không treo) —
   cùng bản chất xung đột thứ tự DLL như lỗi #1, khác thư viện. Fix: thêm
   `import torch` tường minh ở ĐẦU `camera/count_pipeline.py`, TRƯỚC khi
   import bất kỳ thứ gì từ `ultralytics`.
8. **Test tiếng Việt qua `python -c "..."` trong PowerShell cho kết quả
   sai** — do console encoding không phải UTF-8, làm sai lệch ký tự trước
   khi gửi request. KHÔNG bao giờ test câu tiếng Việt có dấu qua `-c`, luôn
   viết ra file `.py` cố định rồi chạy `python file.py`.

## 4. QUYẾT ĐỊNH THIẾT KẾ QUAN TRỌNG — ĐỪNG THAY ĐỔI NGƯỢC LẠI

- **Không train model phân loại nhiều loại hàng** (chỉ 300 ảnh VN, không đủ)
  — camera chỉ đếm số lượng 1 class `carton_box`, con người chọn loại hàng.
  Đã cân nhắc kỹ và QUYẾT ĐỊNH GIỮ 2 giai đoạn train (GĐ1 data ngoài + GĐ2
  fine-tune VN) — không bỏ GĐ2, kết quả thực nghiệm đã chứng minh đúng
  (xem bảng mục 2.4).
- **Đối chiếu theo TỪNG DÒNG HÀNG**, không phải theo cả phiếu — đã báo
  GVHD, cập nhật đề cương mục 6.5.
- **Lệch số CHỈ CẢNH BÁO, KHÔNG CHẶN** — nhân viên tự do skip, quay lại xử
  lý sau (đổi từ thiết kế "chặn cứng" ban đầu).

## 5. QUY ƯỚC LÀM VIỆC / MÔI TRƯỜNG

- Windows, Python 3.11, venv tại `venv\`. Postgres local (`warehouse_db`,
  user `postgres`).
- Chạy server: `uvicorn app.main:app --reload` (thêm `--host 0.0.0.0` nếu
  cần truy cập từ điện thoại/thiết bị khác trong mạng). Frontend: `cd frontend
  ; npm run dev`.
- Data thực tế: `python -m db.seed_realistic` (hoặc `seed_main` bộ demo cũ);
  cả hai XOÁ SẠCH data cũ — `pg_dump` sao lưu trước (xem `CLAUDE.md` mục 4).
- Kiểm tra `schema.sql` khớp `models.py`: `python db/check_schema_sync.py`.
- Tạo ảnh phiếu test OCR: `python -m db.make_test_receipts`.
- Dọn cảnh báo `low_stock` cũ (theo lô) về dạng gộp theo sản phẩm:
  `python -m db.migrate_merge_low_stock_alerts [--confirm]` (mặc định chỉ xem trước).
- Thư mục `uploads/`, `phieu_test/`, `backup*.sql` KHÔNG nằm trong git
  (xem `.gitignore`); model `models/carton_counter_best.pt` (~22 MB) vẫn
  được commit để người khác clone về dùng ngay.
- Test toàn bộ luồng nghiệp vụ 1 lệnh: `python test\verify_full_flow.py <receipt_id>`.
- Test chatbot tiếng Việt AN TOÀN (không qua PowerShell `-c`):
  `python test\debug_chatbot_msg.py`.
- Dọn phiếu rác OCR lỗi cũ: `python test\cleanup_test_data.py` (mặc định
  chỉ xem trước, thêm `--confirm` mới xoá thật).
- Migrate DB Postgres hiện có sang schema mới (không mất data):
  `python -m db.migrate_add_segmented_counting`.
- Notebook train YOLOv8: `carton-training-yolov8.ipynb`, chạy trên Kaggle
  (GPU T4 free), cần API key Roboflow lưu qua Kaggle Secrets (KHÔNG hardcode).

## 6. VIỆC CÒN LẠI (theo thứ tự ưu tiên gợi ý)

(Danh sách cũ đã xong/lỗi thời — xem `CLAUDE.md` mục 8 để biết việc còn mở.)
1. Xác thực (auth): hiện mọi API mở — thêm 1 lớp bảo vệ đơn giản (API key/PIN
   chung) hoặc ghi rõ vào mục "Hạn chế" của báo cáo.
2. Chatbot: bổ sung công cụ (thống kê nhập–xuất, tra theo mã lô, lọc phiếu,
   lô đã hết hạn...), chạy thực nghiệm theo nhóm câu hỏi bằng Gemini thật.
3. Test OCR thật trên ảnh khó (tối/nghiêng) và test trên điện thoại thật.
4. Chưa có chức năng kiểm kê/điều chỉnh tồn (loại giao dịch `adjustment`
   chưa có endpoint) và chưa có Alembic migration (đang `create_all`).
