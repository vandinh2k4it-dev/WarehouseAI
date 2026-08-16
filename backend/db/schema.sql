-- ============================================================
-- SCHEMA CSDL — Hệ thống Quản lý Kho hàng Thông minh
-- Khớp với mục 6.5 (đối chiếu), 6.6 (chatbot), 7 (kiến trúc) của đề cương
-- Chạy: psql -U <user> -d <dbname> -f schema.sql
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

-- ---------- 2. PHIẾU NHẬP HÀNG (nguồn OCR) ----------
CREATE TABLE import_receipts (
    id              SERIAL PRIMARY KEY,
    receipt_code    VARCHAR(64) UNIQUE,             -- mã phiếu (OCR đọc được hoặc hệ thống tự sinh)
    store_location  VARCHAR(255),
    image_path      VARCHAR(512) NOT NULL,          -- ảnh gốc phiếu đã chụp
    ocr_raw_text    TEXT,                           -- toàn bộ text thô từ OCR (để truy vết)
    ocr_confidence  NUMERIC(5,4),                   -- độ tin cậy trung bình
    status          VARCHAR(20) NOT NULL DEFAULT 'pending_ocr'
                    CHECK (status IN ('pending_ocr','ocr_done','reconciled','flagged')),
    received_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
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
    counted_quantity        INTEGER NOT NULL,        -- kết quả đếm cuối (unique track ID)
    avg_detection_confidence NUMERIC(5,4),
    model_version           VARCHAR(64),              -- vd: "yolov8s_gd1gd2_v1"
    started_at              TIMESTAMPTZ,
    ended_at                TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_camera_sessions_receipt ON camera_count_sessions(linked_receipt_id);

-- ---------- 5. ĐỐI CHIẾU (mục 6.5 — trung tâm hệ thống) ----------
CREATE TABLE reconciliations (
    id              SERIAL PRIMARY KEY,
    receipt_id      INTEGER NOT NULL UNIQUE REFERENCES import_receipts(id),
    session_id      INTEGER NOT NULL REFERENCES camera_count_sessions(id),
    receipt_total   NUMERIC(12,2) NOT NULL,          -- tổng SL trên phiếu (sum quantity)
    camera_total    INTEGER NOT NULL,                -- SL đếm từ camera
    difference      NUMERIC(12,2) NOT NULL,          -- camera_total - receipt_total
    threshold_used  NUMERIC(5,4) NOT NULL,           -- ngưỡng sai số % cho phép tại thời điểm chạy
    status          VARCHAR(20) NOT NULL DEFAULT 'matched'
                    CHECK (status IN ('matched','flagged','resolved_manual')),
    resolved_by     VARCHAR(100),
    resolved_note   TEXT,
    resolved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- 6. TỒN KHO HIỆN TẠI (theo sản phẩm + lô) ----------
CREATE TABLE inventory (
    id              SERIAL PRIMARY KEY,
    product_id      INTEGER NOT NULL REFERENCES products(id),
    batch_code      VARCHAR(64) NOT NULL,
    quantity        NUMERIC(12,2) NOT NULL DEFAULT 0,
    expiry_date     DATE,
    last_updated    TIMESTAMPTZ NOT NULL DEFAULT now(),
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
    reference_type  VARCHAR(20),                     -- 'receipt' | 'manual'
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
