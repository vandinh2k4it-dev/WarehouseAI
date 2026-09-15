-- ============================================================
-- SCHEMA CSDL — Hệ thống Quản lý Kho hàng Thông minh
-- Khớp với mục 6.5 (đối chiếu), 6.6 (chatbot), 7 (kiến trúc) của đề cương
-- Chạy: psql -U <user> -d <dbname> -f schema.sql
--
-- LƯU Ý QUAN TRỌNG (14/9/2026): file này trước đó bị LỆCH so với
-- app/models.py qua nhiều vòng chỉnh sửa (thiếu cột source_type, thiếu
-- toàn bộ cột đếm-theo-dòng của camera_count_sessions/reconciliations,
-- thiếu hẳn bảng push_subscriptions) — nguyên nhân vì các cột này được
-- thêm thẳng vào models.py + chạy Base.metadata.create_all() lúc dev,
-- không có ai cập nhật lại file .sql này cho khớp. Đã rà soát và đồng bộ
-- lại 100% với models.py tại thời điểm trên. Nếu sau này còn sửa
-- models.py, NHỚ cập nhật lại file này (hoặc chuyển hẳn sang Alembic để
-- tránh lệch tiếp — xem ghi chú trong models.py).
-- ============================================================

-- ---------- 1. DANH MỤC SẢN PHẨM ----------
CREATE TABLE products (
    id              SERIAL PRIMARY KEY,
    sku             VARCHAR(64) UNIQUE,             -- mã hàng nội bộ (có thể null nếu chưa gán)
    name            VARCHAR(255) NOT NULL,          -- tên chuẩn hoá, dùng để fuzzy-match với OCR
    category        VARCHAR(100),                   -- thực phẩm / đồ uống / hoá mỹ phẩm / dược phẩm...
    unit            VARCHAR(32) NOT NULL DEFAULT 'thùng',
    low_stock_threshold NUMERIC(12,2) DEFAULT 10,   -- ngưỡng cảnh báo sắp hết hàng
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- 2. PHIẾU NHẬP HÀNG (nguồn OCR hoặc nhập tay) ----------
CREATE TABLE import_receipts (
    id              SERIAL PRIMARY KEY,
    receipt_code    VARCHAR(64) UNIQUE,             -- mã phiếu (OCR đọc được hoặc hệ thống tự sinh)
    store_location  VARCHAR(255),
    -- Cho phép NULL: phiếu tạo bằng tay (endpoint /receipts/manual) không
    -- có ảnh gốc để lưu (trước đây NOT NULL, gây lỗi khi tạo phiếu tay).
    image_path      VARCHAR(512),
    ocr_raw_text    TEXT,                           -- toàn bộ text thô từ OCR (để truy vết)
    ocr_confidence  NUMERIC(5,4),                   -- độ tin cậy trung bình
    status          VARCHAR(20) NOT NULL DEFAULT 'pending_ocr'
                    CHECK (status IN ('pending_ocr','ocr_done','reconciled','flagged')),
    received_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- 'ocr' (quét ảnh, mặc định) hoặc 'manual' (nhập tay toàn bộ) — dùng
    -- để UI hiện đúng ngữ cảnh và chặn sửa/xoá an toàn hơn.
    source_type     VARCHAR(20) NOT NULL DEFAULT 'ocr'
                    CHECK (source_type IN ('ocr','manual'))
);
CREATE INDEX idx_receipts_status ON import_receipts(status);

-- ---------- 3. DÒNG HÀNG TRONG PHIẾU (mỗi dòng = 1 sản phẩm) ----------
CREATE TABLE receipt_line_items (
    id                  SERIAL PRIMARY KEY,
    receipt_id          INTEGER NOT NULL REFERENCES import_receipts(id) ON DELETE CASCADE,
    line_no             INTEGER NOT NULL,
    product_name_raw    VARCHAR(255) NOT NULL,      -- tên đọc trực tiếp từ OCR, trước khi map
    product_id          INTEGER REFERENCES products(id),  -- gán sau khi fuzzy-match, có thể NULL
    quantity            NUMERIC(12,2) NOT NULL,
    batch_code          VARCHAR(64),
    expiry_date         DATE,
    match_score         NUMERIC(5,4),               -- độ khớp fuzzy-match tên sản phẩm (0-1)
    field_confidence    JSONB,                      -- {"name":0.9,"qty":0.95,"batch":0.8,"expiry":0.7}
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_line_items_receipt ON receipt_line_items(receipt_id);

-- ---------- 4. PHIÊN ĐẾM QUA CAMERA (kết quả YOLOv8 + ByteTrack) ----------
CREATE TABLE camera_count_sessions (
    id                      SERIAL PRIMARY KEY,
    session_code            VARCHAR(64) UNIQUE,
    camera_id               VARCHAR(64),
    linked_receipt_id       INTEGER REFERENCES import_receipts(id),  -- gán khi biết phiếu tương ứng
    video_path              VARCHAR(512),
    -- Cho phép NULL: chưa có kết quả cho tới khi endpoint /stop được gọi
    -- (trước đây NOT NULL, không tạo được session lúc mới /start).
    counted_quantity        INTEGER,
    avg_detection_confidence NUMERIC(5,4),
    model_version           VARCHAR(64),              -- vd: "yolov8s_gd1gd2_v1"
    started_at              TIMESTAMPTZ,
    ended_at                TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- --- Đếm theo TỪNG LOẠI HÀNG (đối chiếu theo dòng, không theo cả phiếu) ---
    -- direction: 'import' (nhập, đối chiếu với 1 dòng hàng cụ thể trên
    --            phiếu) hoặc 'export' (xuất, đối chiếu với số nhân viên
    --            gõ tay lúc bắt đầu đếm).
    direction               VARCHAR(10) NOT NULL DEFAULT 'import'
                            CHECK (direction IN ('import','export')),
    receipt_line_item_id    INTEGER REFERENCES receipt_line_items(id),
    product_id              INTEGER REFERENCES products(id),
    expected_quantity       NUMERIC(12,2),           -- số "chuẩn" để đối chiếu khi /stop
    -- status: counting -> đang đếm | completed -> đã khớp & cập nhật kho
    --         xong | needs_review -> lệch, CẢNH BÁO nhưng KHÔNG chặn |
    --         resolved_override -> nhân viên xác nhận ghi đè sau khi lệch |
    --         superseded -> bị thay bởi 1 lượt đếm lại (recount) mới hơn
    status                  VARCHAR(20) NOT NULL DEFAULT 'counting'
                            CHECK (status IN ('counting','completed','needs_review','resolved_override','superseded'))
);
CREATE INDEX idx_camera_sessions_receipt ON camera_count_sessions(linked_receipt_id);

-- ---------- 5. ĐỐI CHIẾU (mục 6.5 — trung tâm hệ thống) ----------
CREATE TABLE reconciliations (
    id                      SERIAL PRIMARY KEY,
    -- Cho phép NULL + BỎ UNIQUE: 1 phiếu giờ có thể có NHIỀU bản ghi đối
    -- chiếu (mỗi dòng hàng đối chiếu riêng), thay vì 1-phiếu-1-lần như
    -- thiết kế cũ (trước đây NOT NULL UNIQUE, chặn mất tính năng đối
    -- chiếu theo dòng).
    receipt_id              INTEGER REFERENCES import_receipts(id),
    receipt_line_item_id    INTEGER REFERENCES receipt_line_items(id),
    product_id              INTEGER REFERENCES products(id),  -- dùng khi xuất hàng (không gắn phiếu)
    session_id              INTEGER NOT NULL REFERENCES camera_count_sessions(id),
    receipt_total           NUMERIC(12,2) NOT NULL,  -- đối chiếu theo dòng: chính là expected_quantity
    camera_total            INTEGER NOT NULL,        -- SL đếm từ camera
    difference              NUMERIC(12,2) NOT NULL,  -- camera_total - receipt_total
    threshold_used          NUMERIC(5,4) NOT NULL,   -- ngưỡng sai số % cho phép tại thời điểm chạy
    -- 'resolved_override' được code dùng thật (xem app/routers/camera.py)
    -- nhưng bản CHECK cũ của file này thiếu giá trị này — đã bổ sung.
    status                  VARCHAR(20) NOT NULL DEFAULT 'matched'
                            CHECK (status IN ('matched','flagged','resolved_manual','resolved_override')),
    resolved_by             VARCHAR(100),
    resolved_note           TEXT,
    resolved_at             TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- 6. TỒN KHO HIỆN TẠI (theo sản phẩm + lô) ----------
CREATE TABLE inventory (
    id              SERIAL PRIMARY KEY,
    product_id      INTEGER NOT NULL REFERENCES products(id),
    batch_code      VARCHAR(64) NOT NULL,
    quantity        NUMERIC(12,2) NOT NULL DEFAULT 0,
    expiry_date     DATE,
    last_updated    TIMESTAMPTZ NOT NULL DEFAULT now(),
    location        VARCHAR(50),
    UNIQUE(product_id, batch_code)
);
CREATE INDEX idx_inventory_expiry ON inventory(expiry_date);

-- ---------- 7. LỊCH SỬ BIẾN ĐỘNG TỒN KHO (truy vết) ----------
CREATE TABLE inventory_transactions (
    id              SERIAL PRIMARY KEY,
    inventory_id    INTEGER NOT NULL REFERENCES inventory(id),
    change_qty      NUMERIC(12,2) NOT NULL,          -- + nhập / - xuất / +- điều chỉnh
    transaction_type VARCHAR(20) NOT NULL
                    CHECK (transaction_type IN ('import','export','adjustment')),
    reference_type  VARCHAR(20),                     -- 'receipt' | 'manual' | 'camera_session'
    reference_id    INTEGER,
    note            TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_inv_txn_inventory ON inventory_transactions(inventory_id);

-- ---------- 8. CẢNH BÁO (dùng cho chatbot mục 6.6) ----------
CREATE TABLE alerts (
    id                  SERIAL PRIMARY KEY,
    alert_type          VARCHAR(30) NOT NULL
                        CHECK (alert_type IN ('low_stock','expiring_soon','discrepancy')),
    severity            VARCHAR(10) NOT NULL DEFAULT 'medium'
                        CHECK (severity IN ('low','medium','high')),
    inventory_id        INTEGER REFERENCES inventory(id),
    reconciliation_id   INTEGER REFERENCES reconciliations(id),
    message             TEXT NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open','acknowledged','resolved')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at         TIMESTAMPTZ
);
CREATE INDEX idx_alerts_status ON alerts(status);

-- ---------- 9. ĐĂNG KÝ NHẬN THÔNG BÁO ĐẨY (Web Push) ----------
-- Bảng này THIẾU HOÀN TOÀN trong bản schema.sql cũ (tính năng push được
-- thêm sau, chỉ có trong models.py) — đã bổ sung đầy đủ.
CREATE TABLE push_subscriptions (
    id              SERIAL PRIMARY KEY,
    endpoint        TEXT NOT NULL UNIQUE,
    p256dh          TEXT NOT NULL,
    auth            TEXT NOT NULL,
    label           VARCHAR(100),        -- tuỳ chọn: tên thiết bị để dễ quản lý nhiều máy
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);