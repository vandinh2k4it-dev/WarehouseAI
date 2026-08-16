"""Tạo bộ DATA CHÍNH thực tế kiểu tạp hoá/siêu thị mini Việt Nam — thay cho
data demo nghèo nàn cũ (chỉ 6 sản phẩm). Dùng để test hệ thống với khối
lượng và tình huống gần với thực tế: nhiều ngành hàng, nhiều lô hàng, có sẵn
tình huống sắp hết hàng / sắp hết hạn / lệch đối chiếu để demo đủ tính năng
ngay mà không cần tự tạo tình huống bằng tay.

Cách dùng:
    python -m db.seed_main

MẶC ĐỊNH SẼ XOÁ SẠCH TOÀN BỘ DATA CŨ trước khi tạo mới (products, receipts,
inventory, alerts...) — dùng khi muốn có bộ data chính sạch sẽ, không lẫn
data test/demo cũ. Nếu KHÔNG muốn xoá, chạy với --no-wipe:
    python -m db.seed_main --no-wipe
(khi đó sẽ CỘNG THÊM vào data hiện có, có thể tạo trùng sản phẩm nếu SKU
trùng nhau.)
"""
import argparse
import random
from datetime import date, datetime, timedelta, timezone

from app.database import Base, engine, SessionLocal
from app import models

random.seed(42)  # để chạy lại nhiều lần ra cùng 1 bộ data, dễ so sánh khi debug

# (sku, tên, ngành hàng, đơn vị, ngưỡng cảnh báo tồn kho thấp)
PRODUCTS = [
    ("SP-001", "Sữa tươi Vinamilk 1L", "Sữa & đồ uống", "thùng", 15),
    ("SP-002", "Sữa tươi TH True Milk 1L", "Sữa & đồ uống", "thùng", 15),
    ("SP-003", "Sữa đặc Ông Thọ", "Sữa & đồ uống", "thùng", 10),
    ("SP-004", "Nước suối Lavie 500ml", "Sữa & đồ uống", "thùng", 20),
    ("SP-005", "Nước suối Aquafina 500ml", "Sữa & đồ uống", "thùng", 20),
    ("SP-006", "Coca-Cola lon 330ml", "Sữa & đồ uống", "thùng", 25),
    ("SP-007", "Pepsi lon 330ml", "Sữa & đồ uống", "thùng", 25),
    ("SP-008", "Nước tăng lực Sting dâu 330ml", "Sữa & đồ uống", "thùng", 15),
    ("SP-009", "Trà xanh không độ", "Sữa & đồ uống", "thùng", 15),
    ("SP-010", "Cà phê hòa tan G7 3in1", "Sữa & đồ uống", "thùng", 10),
    ("SP-011", "Bánh Oreo hộp 133g", "Bánh kẹo", "thùng", 10),
    ("SP-012", "Bánh Cosy quy bơ", "Bánh kẹo", "thùng", 10),
    ("SP-013", "Bánh Solite hộp", "Bánh kẹo", "thùng", 10),
    ("SP-014", "Kẹo Mentos bạc hà", "Bánh kẹo", "thùng", 12),
    ("SP-015", "Kẹo Alpenliebe", "Bánh kẹo", "thùng", 12),
    ("SP-016", "Snack Oishi khoai tây", "Bánh kẹo", "thùng", 15),
    ("SP-017", "Mì Hảo Hảo tôm chua cay", "Thực phẩm khô", "thùng", 30),
    ("SP-018", "Mì Omachi sốt bò hầm", "Thực phẩm khô", "thùng", 25),
    ("SP-019", "Cháo gói Kinh Đô", "Thực phẩm khô", "thùng", 15),
    ("SP-020", "Gạo ST25 túi 5kg", "Thực phẩm khô", "bao", 10),
    ("SP-021", "Dầu ăn Simply 1L", "Gia vị", "thùng", 8),
    ("SP-022", "Dầu ăn Neptune 1L", "Gia vị", "thùng", 8),
    ("SP-023", "Nước mắm Nam Ngư 500ml", "Gia vị", "thùng", 8),
    ("SP-024", "Nước mắm Chinsu 500ml", "Gia vị", "thùng", 8),
    ("SP-025", "Hạt nêm Knorr", "Gia vị", "thùng", 10),
    ("SP-026", "Bột giặt Omo 3kg", "Hoá phẩm", "thùng", 6),
    ("SP-027", "Bột giặt Ariel 3kg", "Hoá phẩm", "thùng", 6),
    ("SP-028", "Nước xả Comfort 1.5L", "Hoá phẩm", "thùng", 8),
    ("SP-029", "Nước rửa chén Sunlight", "Hoá phẩm", "thùng", 8),
    ("SP-030", "Giấy vệ sinh Pulppy 10 cuộn", "Hoá phẩm", "lốc", 10),
]

# Nhà cung cấp giả định (dùng cho store_location trên phiếu nhập cho có ngữ cảnh thật)
SUPPLIERS = [
    "Công ty TNHH An Bình",
    "Đại lý Minh Phát",
    "Công ty CP Thương mại Hưng Thịnh",
    "Nhà phân phối Sài Gòn Food",
]


def wipe_all(db):
    """Xoá sạch theo đúng thứ tự khoá ngoại (con trước, cha sau)."""
    print("Đang xoá sạch data cũ...")
    db.query(models.Alert).delete()
    db.query(models.Reconciliation).delete()
    db.query(models.CameraCountSession).delete()
    db.query(models.InventoryTransaction).delete()
    db.query(models.ReceiptLineItem).delete()
    db.query(models.ImportReceipt).delete()
    db.query(models.Inventory).delete()
    db.query(models.Product).delete()
    db.commit()
    print("Đã xoá xong.")


def seed_main(wipe: bool = True):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if wipe:
            wipe_all(db)

        today = date.today()

        # ---------------- 1. Danh mục sản phẩm ----------------
        products = {}
        for sku, name, category, unit, threshold in PRODUCTS:
            p = models.Product(sku=sku, name=name, category=category, unit=unit, low_stock_threshold=threshold)
            db.add(p)
            products[sku] = p
        db.flush()
        print(f"Đã tạo {len(products)} sản phẩm.")

        # ---------------- 2. Tồn kho — mỗi sản phẩm 1-2 lô, số lượng đa dạng ----------------
        # Cố tình để ~15% sản phẩm dưới ngưỡng cảnh báo, ~15% sắp hết hạn trong 20 ngày
        # để có sẵn tình huống demo, không cần tự dàn dựng thêm.
        inventory_rows = []
        for i, (sku, name, category, unit, threshold) in enumerate(PRODUCTS):
            n_batches = 2 if i % 4 == 0 else 1
            for b in range(n_batches):
                batch_code = f"L{random.randint(100,999)}{chr(65 + (i + b) % 26)}"
                if i % 7 == 0:  # ~15% dưới ngưỡng thấp
                    qty = max(1, int(threshold * random.uniform(0.2, 0.8)))
                elif i % 6 == 0:  # ~17% dư dả nhiều
                    qty = int(threshold * random.uniform(4, 8))
                else:
                    qty = int(threshold * random.uniform(1.5, 3.5))

                if i % 5 == 0:  # ~20% sắp hết hạn trong 5-20 ngày
                    exp = today + timedelta(days=random.randint(5, 20))
                else:
                    exp = today + timedelta(days=random.randint(60, 400))

                inv = models.Inventory(
                    product_id=products[sku].id,
                    batch_code=batch_code,
                    quantity=qty,
                    expiry_date=exp,
                    last_updated=datetime.now(timezone.utc) - timedelta(days=random.randint(0, 10)),
                )
                db.add(inv)
                inventory_rows.append((inv, sku, qty))
        db.flush()
        print(f"Đã tạo {len(inventory_rows)} lô tồn kho.")

        # ---------------- 3. Vài phiếu nhập ĐÃ đối chiếu xong (matched + 1 flagged) ----------------
        receipt_specs = [
            # (mã phiếu, địa điểm, các SKU trong phiếu, có khớp camera hay không)
            ("PN-2026-001", SUPPLIERS[0], ["SP-001", "SP-004", "SP-017", "SP-026"], True),
            ("PN-2026-002", SUPPLIERS[1], ["SP-011", "SP-013", "SP-014", "SP-016"], True),
            ("PN-2026-003", SUPPLIERS[2], ["SP-021", "SP-023", "SP-025"], False),  # cố tình lệch để demo cảnh báo
        ]

        for code, supplier, skus, matched in receipt_specs:
            receipt = models.ImportReceipt(
                receipt_code=code,
                store_location=supplier,
                image_path=f"./uploads/receipts/seed_{code}.jpg",
                ocr_raw_text=f"Phiếu nhập {code} — dữ liệu seed, không qua OCR thật.",
                ocr_confidence=0.97,
                status="pending_ocr",
                received_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1, 20)),
            )
            db.add(receipt)
            db.flush()

            lines = []
            for i, sku in enumerate(skus, start=1):
                qty = random.randint(50, 300)
                batch_code = f"L{random.randint(100,999)}{chr(64 + i)}"
                exp = today + timedelta(days=random.randint(60, 300))
                li = models.ReceiptLineItem(
                    receipt_id=receipt.id,
                    line_no=i,
                    product_name_raw=products[sku].name,
                    product_id=products[sku].id,
                    quantity=qty,
                    batch_code=batch_code,
                    expiry_date=exp,
                    match_score=1.0,
                    field_confidence={"quantity": 1.0, "batch": 1.0, "expiry": 1.0},
                )
                db.add(li)
                lines.append(li)
            receipt.status = "ocr_done"
            db.flush()

            # ---- Tạo phiên đếm THEO TỪNG DÒNG HÀNG (đúng kiến trúc đối chiếu
            # mới — start-import/stop — thay cho kiểu tính tổng cả phiếu cũ.
            # Nếu không làm vậy, phiếu sẽ hiện "đã xong hết" nhưng mở ra từng
            # dòng vẫn "chưa đếm", gây khó hiểu như đã gặp phải khi demo). ----
            # receipt "flagged": dòng CUỐI CÙNG cố tình lệch để demo cảnh báo,
            # các dòng còn lại khớp bình thường — mô phỏng đúng tình huống
            # thực tế "đa số OK, có 1 loại cần kiểm tra lại".
            flagged_line_idx = len(lines) - 1 if not matched else None

            for idx, li in enumerate(lines):
                is_flagged_line = idx == flagged_line_idx
                counted_qty = (
                    li.quantity - random.randint(15, 40) if is_flagged_line else li.quantity
                )
                started = receipt.received_at
                ended = started + timedelta(minutes=2 + idx)

                session = models.CameraCountSession(
                    session_code=f"cam-{code}-L{idx+1}",
                    camera_id="cam-01",
                    direction="import",
                    linked_receipt_id=receipt.id,
                    receipt_line_item_id=li.id,
                    product_id=li.product_id,
                    expected_quantity=li.quantity,
                    counted_quantity=counted_qty,
                    avg_detection_confidence=0.9,
                    model_version="seed-manual",
                    status="needs_review" if is_flagged_line else "completed",
                    started_at=started,
                    ended_at=ended,
                )
                db.add(session)
                db.flush()

                difference = counted_qty - float(li.quantity)
                diff_pct = abs(difference) / float(li.quantity) if li.quantity else 0
                recon = models.Reconciliation(
                    receipt_id=receipt.id,
                    receipt_line_item_id=li.id,
                    product_id=li.product_id,
                    session_id=session.id,
                    receipt_total=li.quantity,
                    camera_total=counted_qty,
                    difference=difference,
                    threshold_used=0.02,
                    status="flagged" if is_flagged_line else "matched",
                )
                db.add(recon)
                db.flush()

                if is_flagged_line:
                    db.add(models.Alert(
                        alert_type="discrepancy", severity="high", reconciliation_id=recon.id,
                        message=(
                            f"[NHẬP] Lệch {difference:+.0f} khi đếm '{products[skus[idx]].name}' — "
                            f"camera đếm {counted_qty}, cần {li.quantity} (vượt ngưỡng 2.0%). "
                            f"Chưa cập nhật tồn kho cho dòng này — cần kiểm tra lại (phiên #{session.id})."
                        ),
                    ))
                else:
                    # Khớp -> cộng tồn kho đúng như logic apply_line_import() thật
                    inv = (
                        db.query(models.Inventory)
                        .filter(models.Inventory.product_id == li.product_id, models.Inventory.batch_code == li.batch_code)
                        .first()
                    )
                    if inv is None:
                        inv = models.Inventory(
                            product_id=li.product_id, batch_code=li.batch_code,
                            quantity=0, expiry_date=li.expiry_date,
                        )
                        db.add(inv)
                        db.flush()
                    inv.quantity = float(inv.quantity) + float(li.quantity)
                    inv.last_updated = datetime.now(timezone.utc)
                    db.add(models.InventoryTransaction(
                        inventory_id=inv.id, change_qty=float(li.quantity),
                        transaction_type="import", reference_type="receipt_line", reference_id=li.id,
                    ))

            # Phiếu chỉ "reconciled" khi TẤT CẢ dòng đã xong (đúng logic
            # _maybe_complete_receipt thật) — phiếu có dòng needs_review vẫn
            # dừng ở "ocr_done", đúng để badge trên giao diện không nói dối.
            receipt.status = "reconciled" if matched else "ocr_done"
        db.commit()
        print(f"Đã tạo {len(receipt_specs)} phiếu nhập (đối chiếu theo từng dòng hàng).")

        # ---------------- 4. Cảnh báo low_stock / expiring_soon tự sinh theo data tồn kho vừa tạo ----------------
        n_alerts = 0
        for inv, sku, qty in inventory_rows:
            product = products[sku]
            if float(inv.quantity) <= float(product.low_stock_threshold):
                db.add(models.Alert(
                    alert_type="low_stock", severity="medium" if inv.quantity > 0 else "high",
                    inventory_id=inv.id,
                    message=(
                        f"Sản phẩm '{product.name}' (lô {inv.batch_code}) chỉ còn "
                        f"{inv.quantity} {product.unit} — dưới ngưỡng {product.low_stock_threshold}."
                    ),
                ))
                n_alerts += 1
            if inv.expiry_date and inv.expiry_date <= today + timedelta(days=20):
                days_left = (inv.expiry_date - today).days
                db.add(models.Alert(
                    alert_type="expiring_soon", severity="high" if days_left <= 10 else "medium",
                    inventory_id=inv.id,
                    message=(
                        f"Lô '{inv.batch_code}' của '{product.name}' sắp hết hạn trong {days_left} ngày "
                        f"(HSD {inv.expiry_date})."
                    ),
                ))
                n_alerts += 1
        db.commit()
        print(f"Đã tạo {n_alerts} cảnh báo (low_stock + expiring_soon).")

        print("\n✅ HOÀN TẤT. Tóm tắt:")
        print(f"   - {len(PRODUCTS)} sản phẩm, {len(inventory_rows)} lô tồn kho")
        print(f"   - {len(receipt_specs)} phiếu nhập đã đối chiếu (2 matched, 1 flagged)")
        print(f"   - {n_alerts} cảnh báo tự sinh + 1 cảnh báo discrepancy")

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-wipe", action="store_true", help="Không xoá data cũ, chỉ cộng thêm")
    args = parser.parse_args()
    seed_main(wipe=not args.no_wipe)
