"""Tạo dữ liệu mẫu để test nhanh, không cần tự gọi tay từng API như lúc debug.

Cách dùng:
    python -m db.seed

Sẽ tạo vào DB đang trỏ tới (theo DATABASE_URL trong .env):
- 6 sản phẩm đa dạng (đủ để demo low-stock, expiring-soon)
- Tồn kho tương ứng — có cả lô sắp hết hàng, sắp hết hạn để test cảnh báo
- 2 phiếu nhập đã OCR + map sản phẩm + đối chiếu xong (1 matched, 1 flagged)
- Vài giao dịch xuất kho mẫu
- Vài cảnh báo có sẵn để test ngay /alerts mà không cần tự tạo tình huống

An toàn khi chạy nhiều lần: kiểm tra nếu đã có dữ liệu mẫu (theo SKU đặc biệt
'DEMO-') thì bỏ qua, không tạo trùng.
"""
from datetime import date, datetime, timedelta, timezone

from app.database import Base, engine, SessionLocal
from app import models


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    existing = db.query(models.Product).filter(models.Product.sku.like("DEMO-%")).first()
    if existing:
        print("Dữ liệu mẫu đã tồn tại (tìm thấy SKU 'DEMO-...') — bỏ qua, không tạo trùng.")
        print("Muốn tạo lại từ đầu: xoá các sản phẩm có SKU bắt đầu 'DEMO-' trong pgAdmin rồi chạy lại.")
        db.close()
        return

    today = date.today()

    products_data = [
        # (sku, name, category, unit, low_stock_threshold)
        ("DEMO-001", "Sữa tươi Vinamilk 1L", "Đồ uống", "thùng", 15),
        ("DEMO-002", "Nước suối Lavie 500ml", "Đồ uống", "thùng", 20),
        ("DEMO-003", "Bánh Oreo hộp 133g", "Bánh kẹo", "thùng", 10),
        ("DEMO-004", "Mì Hảo Hảo tôm chua cay", "Thực phẩm khô", "thùng", 30),
        ("DEMO-005", "Dầu ăn Neptune 1L", "Gia vị", "thùng", 8),
        ("DEMO-006", "Nước mắm Nam Ngư 500ml", "Gia vị", "thùng", 5),
    ]
    products = {}
    for sku, name, category, unit, threshold in products_data:
        p = models.Product(sku=sku, name=name, category=category, unit=unit, low_stock_threshold=threshold)
        db.add(p)
        products[sku] = p
    db.flush()  # cần .id trước khi dùng cho inventory

    # ---- Tồn kho: cố tình để vài mức khác nhau để test đủ 3 tab (tất cả / sắp hết hàng / sắp hết hạn) ----
    inventory_data = [
        # (sku, batch_code, quantity, expiry_date)
        ("DEMO-001", "LOT2601", 42, today + timedelta(days=120)),
        ("DEMO-002", "L23A", 88, today + timedelta(days=200)),
        ("DEMO-003", "B045", 6, today + timedelta(days=10)),      # sắp hết hàng (<10) VÀ sắp hết hạn (<30 ngày)
        ("DEMO-004", "M12X", 55, today + timedelta(days=180)),
        ("DEMO-005", "N0725", 3, today + timedelta(days=300)),    # sắp hết hàng (<8)
        ("DEMO-006", "NM0819", 40, today + timedelta(days=15)),   # sắp hết hạn (<30 ngày)
    ]
    inventories = {}
    for sku, batch, qty, expiry in inventory_data:
        inv = models.Inventory(
            product_id=products[sku].id, batch_code=batch, quantity=qty, expiry_date=expiry
        )
        db.add(inv)
        inventories[sku] = inv
    db.flush()

    # ---- Cảnh báo có sẵn — khớp đúng với tình huống tồn kho ở trên ----
    db.add(
        models.Alert(
            alert_type="low_stock",
            severity="high",
            inventory_id=inventories["DEMO-003"].id,
            message="Sản phẩm 'Bánh Oreo hộp 133g' (lô B045) chỉ còn 6 thùng — dưới ngưỡng 10.",
        )
    )
    db.add(
        models.Alert(
            alert_type="low_stock",
            severity="medium",
            inventory_id=inventories["DEMO-005"].id,
            message="Sản phẩm 'Dầu ăn Neptune 1L' (lô N0725) chỉ còn 3 thùng — dưới ngưỡng 8.",
        )
    )
    db.add(
        models.Alert(
            alert_type="expiring_soon",
            severity="medium",
            inventory_id=inventories["DEMO-006"].id,
            message="Lô NM0819 (Nước mắm Nam Ngư 500ml) sắp hết hạn trong 15 ngày.",
        )
    )

    # ---- 1 phiếu nhập đã OCR + map + đối chiếu 'matched' (mẫu luồng chạy đúng) ----
    receipt_ok = models.ImportReceipt(
        receipt_code="DEMO-PN-001",
        store_location="Tạp hoá Cô Ba, Q.Tân Bình (dữ liệu mẫu)",
        image_path="uploads/receipts/demo_sample.png",
        ocr_raw_text="(dữ liệu mẫu, không phải OCR thật)",
        ocr_confidence=0.959,
        status="reconciled",
        received_at=datetime.now(timezone.utc) - timedelta(days=2),
    )
    db.add(receipt_ok)
    db.flush()

    line1 = models.ReceiptLineItem(
        receipt_id=receipt_ok.id, line_no=1, product_name_raw="Sữa tươi Vinamilk 1L",
        product_id=products["DEMO-001"].id, quantity=42, batch_code="LOT2601",
        expiry_date=today + timedelta(days=120), match_score=1.0,
    )
    db.add(line1)
    db.flush()

    session_ok = models.CameraCountSession(
        session_code="DEMO-CAM-001", camera_id="CAM01",
        linked_receipt_id=receipt_ok.id, counted_quantity=42,
        model_version="demo_seed", avg_detection_confidence=0.97,
    )
    db.add(session_ok)
    db.flush()

    db.add(
        models.Reconciliation(
            receipt_id=receipt_ok.id, session_id=session_ok.id,
            receipt_total=42, camera_total=42, difference=0,
            threshold_used=0.02, status="matched",
        )
    )

    # ---- 1 phiếu nhập bị lệch (mẫu luồng flagged, để test /alerts kiểu discrepancy) ----
    receipt_bad = models.ImportReceipt(
        receipt_code="DEMO-PN-002",
        store_location="Nhà thuốc Minh Phát (dữ liệu mẫu)",
        image_path="uploads/receipts/demo_sample2.png",
        ocr_raw_text="(dữ liệu mẫu, không phải OCR thật)",
        ocr_confidence=0.941,
        status="flagged",
        received_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db.add(receipt_bad)
    db.flush()

    line2 = models.ReceiptLineItem(
        receipt_id=receipt_bad.id, line_no=1, product_name_raw="Nước suối Lavie 500ml",
        product_id=products["DEMO-002"].id, quantity=100, batch_code="L23A",
        expiry_date=today + timedelta(days=200), match_score=1.0,
    )
    db.add(line2)
    db.flush()

    session_bad = models.CameraCountSession(
        session_code="DEMO-CAM-002", camera_id="CAM01",
        linked_receipt_id=receipt_bad.id, counted_quantity=88,
        model_version="demo_seed", avg_detection_confidence=0.93,
    )
    db.add(session_bad)
    db.flush()

    recon_bad = models.Reconciliation(
        receipt_id=receipt_bad.id, session_id=session_bad.id,
        receipt_total=100, camera_total=88, difference=-12,
        threshold_used=0.02, status="flagged",
    )
    db.add(recon_bad)
    db.flush()

    db.add(
        models.Alert(
            alert_type="discrepancy",
            severity="high",
            reconciliation_id=recon_bad.id,
            message="Chênh lệch -12 thùng giữa camera (88) và phiếu nhập DEMO-PN-002 (100) — vượt ngưỡng 2.0%. Cần kiểm tra thủ công.",
        )
    )

    # ---- Giao dịch xuất kho mẫu (test lịch sử inventory_transactions) ----
    db.add(
        models.InventoryTransaction(
            inventory_id=inventories["DEMO-001"].id, change_qty=-8,
            transaction_type="export", reference_type="manual",
            note="Bán lẻ (dữ liệu mẫu)",
        )
    )

    db.commit()
    db.close()
    print("✅ Đã tạo dữ liệu mẫu:")
    print("   - 6 sản phẩm (SKU DEMO-001 .. DEMO-006)")
    print("   - 6 dòng tồn kho (có sẵn tình huống sắp hết hàng + sắp hết hạn)")
    print("   - 4 cảnh báo đang mở (2 low_stock, 1 expiring_soon, 1 discrepancy)")
    print("   - 2 phiếu nhập mẫu (1 matched, 1 flagged) kèm đối chiếu")
    print("   - 1 giao dịch xuất kho mẫu")
    print("Mở http://localhost:8000/app/ để xem ngay, không cần tự tạo gì thêm.")


if __name__ == "__main__":
    seed()
