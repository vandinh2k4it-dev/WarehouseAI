"""SQLAlchemy models — phản ánh đúng db/schema.sql.
Dùng Base.metadata.create_all() lúc dev; khi lên production nên chuyển
sang Alembic migration để không mất dữ liệu khi đổi schema.
"""
from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Numeric, Text, Date, TIMESTAMP, ForeignKey,
    CheckConstraint, UniqueConstraint, JSON, func
)
from sqlalchemy.orm import relationship
from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    sku = Column(String(64), unique=True, nullable=True)
    name = Column(String(255), nullable=False)
    category = Column(String(100))
    unit = Column(String(32), nullable=False, default="thùng")
    low_stock_threshold = Column(Numeric(12, 2), default=10)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    inventory_entries = relationship("Inventory", back_populates="product")


class ImportReceipt(Base):
    __tablename__ = "import_receipts"

    id = Column(Integer, primary_key=True)
    receipt_code = Column(String(64), unique=True, nullable=True)
    store_location = Column(String(255))
    # Cho phép NULL — phiếu tạo bằng tay (không quét ảnh, xem
    # app/routers/receipts.py endpoint /manual) không có ảnh gốc để lưu.
    image_path = Column(String(512), nullable=True)
    ocr_raw_text = Column(Text)
    ocr_confidence = Column(Numeric(5, 4))
    status = Column(String(20), nullable=False, default="pending_ocr")
    received_at = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    # 'ocr' (quét ảnh, mặc định — khớp dữ liệu cũ) hoặc 'manual' (nhập tay
    # toàn bộ, không qua OCR) — dùng để UI hiện đúng ngữ cảnh (vd không hiện
    # link xem ảnh gốc cho phiếu manual) và để chặn sửa/xoá an toàn hơn.
    source_type = Column(String(20), nullable=False, default="ocr")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending_ocr','ocr_done','reconciled','flagged')",
            name="ck_receipt_status",
        ),
        CheckConstraint("source_type IN ('ocr','manual')", name="ck_receipt_source_type"),
    )

    line_items = relationship(
        "ReceiptLineItem", back_populates="receipt", cascade="all, delete-orphan"
    )


class ReceiptLineItem(Base):
    __tablename__ = "receipt_line_items"

    id = Column(Integer, primary_key=True)
    receipt_id = Column(Integer, ForeignKey("import_receipts.id", ondelete="CASCADE"), nullable=False)
    line_no = Column(Integer, nullable=False)
    product_name_raw = Column(String(255), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    quantity = Column(Numeric(12, 2), nullable=False)
    batch_code = Column(String(64))
    expiry_date = Column(Date)
    match_score = Column(Numeric(5, 4))
    field_confidence = Column(JSON)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    receipt = relationship("ImportReceipt", back_populates="line_items")


class CameraCountSession(Base):
    __tablename__ = "camera_count_sessions"

    id = Column(Integer, primary_key=True)
    session_code = Column(String(64), unique=True, nullable=True)
    camera_id = Column(String(64))
    linked_receipt_id = Column(Integer, ForeignKey("import_receipts.id"), nullable=True)
    video_path = Column(String(512))
    counted_quantity = Column(Integer, nullable=True)  # NULL cho tới khi /stop được gọi
    avg_detection_confidence = Column(Numeric(5, 4))
    model_version = Column(String(64))
    started_at = Column(TIMESTAMP(timezone=True))
    ended_at = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    # --- Đếm theo TỪNG LOẠI HÀNG (mục quy trình mới) ---
    # direction: 'import' (nhập, đối chiếu với 1 dòng hàng cụ thể trên phiếu)
    #            hoặc 'export' (xuất, đối chiếu với số nhân viên gõ tay lúc đó)
    direction = Column(String(10), nullable=False, default="import")
    receipt_line_item_id = Column(Integer, ForeignKey("receipt_line_items.id"), nullable=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    expected_quantity = Column(Numeric(12, 2), nullable=True)  # số "chuẩn" để đối chiếu khi /stop
    # status: counting -> đang đếm | completed -> đã khớp & cập nhật kho xong |
    #         needs_review -> lệch, CẢNH BÁO nhưng KHÔNG chặn (nhân viên có thể
    #         skip qua loại khác, quay lại xử lý sau) |
    #         resolved_override -> nhân viên xác nhận ghi đè sau khi lệch |
    #         superseded -> bị thay bởi 1 lượt đếm lại (recount) mới hơn
    status = Column(String(20), nullable=False, default="counting")

    __table_args__ = (
        CheckConstraint("direction IN ('import','export')", name="ck_camera_direction"),
        CheckConstraint(
            "status IN ('counting','completed','needs_review','resolved_override','superseded')",
            name="ck_camera_status",
        ),
    )


class Reconciliation(Base):
    __tablename__ = "reconciliations"

    id = Column(Integer, primary_key=True)
    # Cho phép NULL + bỏ unique: 1 phiếu giờ có thể có NHIỀU bản ghi đối chiếu
    # (mỗi dòng hàng đối chiếu riêng), thay vì 1-phiếu-1-lần như thiết kế cũ.
    receipt_id = Column(Integer, ForeignKey("import_receipts.id"), nullable=True)
    receipt_line_item_id = Column(Integer, ForeignKey("receipt_line_items.id"), nullable=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)  # dùng khi xuất hàng (không gắn phiếu)
    session_id = Column(Integer, ForeignKey("camera_count_sessions.id"), nullable=False)
    receipt_total = Column(Numeric(12, 2), nullable=False)  # với đối chiếu theo dòng: chính là expected_quantity
    camera_total = Column(Integer, nullable=False)
    difference = Column(Numeric(12, 2), nullable=False)
    threshold_used = Column(Numeric(5, 4), nullable=False)
    status = Column(String(20), nullable=False, default="matched")
    resolved_by = Column(String(100))
    resolved_note = Column(Text)
    resolved_at = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    batch_code = Column(String(64), nullable=False)
    quantity = Column(Numeric(12, 2), nullable=False, default=0)
    expiry_date = Column(Date)
    last_updated = Column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("product_id", "batch_code", name="uq_inventory_product_batch"),)

    product = relationship("Product", back_populates="inventory_entries")


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id = Column(Integer, primary_key=True)
    inventory_id = Column(Integer, ForeignKey("inventory.id"), nullable=False)
    change_qty = Column(Numeric(12, 2), nullable=False)
    transaction_type = Column(String(20), nullable=False)  # import / export / adjustment
    reference_type = Column(String(20))
    reference_id = Column(Integer)
    note = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True)
    alert_type = Column(String(30), nullable=False)  # low_stock / expiring_soon / discrepancy
    severity = Column(String(10), nullable=False, default="medium")
    inventory_id = Column(Integer, ForeignKey("inventory.id"), nullable=True)
    reconciliation_id = Column(Integer, ForeignKey("reconciliations.id"), nullable=True)
    message = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="open")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    resolved_at = Column(TIMESTAMP(timezone=True))


class PushSubscription(Base):
    """Đăng ký nhận thông báo đẩy (Web Push) của 1 trình duyệt/thiết bị cụ
    thể — lưu lại thông tin PushManager.subscribe() trả về từ frontend, dùng
    để gửi push mỗi khi có Alert mới (xem app/push_service.py)."""
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True)
    endpoint = Column(Text, nullable=False, unique=True)
    p256dh = Column(Text, nullable=False)
    auth = Column(Text, nullable=False)
    label = Column(String(100))  # tuỳ chọn: tên thiết bị để dễ quản lý nhiều máy
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
