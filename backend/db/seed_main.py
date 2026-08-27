"""Tạo bộ DATA CHÍNH đầy đủ, phong phú — phủ hết mọi tính năng để DEMO NGAY
không cần tự dàn dựng tình huống bằng tay. Xem HUONG_DAN_DEMO.md đi kèm để
biết đúng thứ tự demo từng tính năng khớp với data này.

Cách dùng:
    python -m db.seed_main

MẶC ĐỊNH SẼ XOÁ SẠCH TOÀN BỘ DATA CŨ trước khi tạo mới. Nếu KHÔNG muốn xoá:
    python -m db.seed_main --no-wipe
(khi đó CỘNG THÊM vào data hiện có, có thể trùng SKU nếu chạy 2 lần.)

TÓM TẮT DATA TẠO RA (xem đủ chi tiết ở cuối file lúc chạy):
  - 30 sản phẩm, 6 ngành hàng
  - ~45 lô tồn kho — có sẵn tình huống sắp hết hàng / sắp hết hạn / hết hạn hẳn
  - 7 phiếu nhập — đủ mọi trạng thái + cả 2 nguồn gốc (quét OCR / tạo tay):
      PN-2026-001  quét OCR, đã đối chiếu xong toàn bộ (reconciled)
      PN-2026-002  quét OCR, đã đối chiếu xong toàn bộ (reconciled)
      PN-2026-003  quét OCR, có 1 dòng LỆCH cần xử lý (ocr_done, flagged)
      PN-2026-004  TẠO TAY, đã đối chiếu xong toàn bộ (reconciled)
      PN-2026-005  TẠO TAY, CHƯA đếm dòng nào (ocr_done, not_started hết)
      PN-2026-006  quét OCR, đang chờ xử lý OCR (pending_ocr — demo trạng thái lỗi/đang xử lý)
      PN-2026-007  quét OCR, đã đối chiếu xong toàn bộ (reconciled)
  - 5 lượt xuất kho đã có sẵn trong Lịch sử xuất kho (3 qua camera, 2 gõ tay)
  - Cảnh báo tự sinh: low_stock + expiring_soon theo đúng data tồn kho, cộng
    1 cảnh báo discrepancy từ phiếu PN-2026-003
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

SUPPLIERS = [
    "Công ty TNHH An Bình",
    "Đại lý Minh Phát",
    "Công ty CP Thương mại Hưng Thịnh",
    "Nhà phân phối Sài Gòn Food",
    "Chành xe Miền Tây (giao tận kho)",
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


def _new_batch_code(existing: set) -> str:
    """Sinh mã lô ngẫu nhiên nhưng ĐẢM BẢO không trùng — bản gốc trước đây
    có thể trùng ngẫu nhiên hiếm khi vì chỉ random 3 số + 1 chữ, gây lỗi
    UniqueConstraint('product_id','batch_code') nếu trùng đúng lúc cùng 1
    sản phẩm. Bộ data lớn hơn lần này (nhiều lô hơn) nên cần chắc chắn
    tránh trùng thay vì chỉ dựa vào xác suất thấp như bản cũ."""
    while True:
        code = f"L{random.randint(100,999)}{random.choice('ABCDEFGHKLMNPQRSTUVXYZ')}"
        if code not in existing:
            existing.add(code)
            return code


def seed_main(wipe: bool = True):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    used_batch_codes: set[str] = set()
    try:
        if wipe:
            wipe_all(db)

        today = date.today()

        # ================== 1. DANH MỤC SẢN PHẨM ==================
        products = {}
        for sku, name, category, unit, threshold in PRODUCTS:
            p = models.Product(sku=sku, name=name, category=category, unit=unit, low_stock_threshold=threshold)
            db.add(p)
            products[sku] = p
        db.flush()
        print(f"✅ Đã tạo {len(products)} sản phẩm.")

        # ================== 2. TỒN KHO — nhiều lô, đa dạng tình huống ==================
        # Chủ đích tạo sẵn ĐỦ 4 tình huống để demo ngay không cần dàn dựng:
        #   - ~15% dưới ngưỡng cảnh báo (low_stock)
        #   - ~15% sắp hết hạn trong 20 ngày (expiring_soon, còn dùng được)
        #   - ~7% ĐÃ hết hạn nhưng vẫn còn tồn kho (tình huống thực tế cần xử
        #     lý/huỷ — khác "sắp hết hạn", xem lưu ý đã sửa lỗi lọc ngày ở
        #     app/chatbot/tools.py trước đó)
        #   - còn lại tồn kho khoẻ mạnh bình thường
        inventory_rows = []
        for i, (sku, name, category, unit, threshold) in enumerate(PRODUCTS):
            n_batches = 2 if i % 4 == 0 else 1
            for b in range(n_batches):
                batch_code = _new_batch_code(used_batch_codes)

                if i % 9 == 0:  # ~11% ĐÃ hết hạn nhưng còn tồn kho — tình huống cần xử lý
                    qty = max(1, int(threshold * random.uniform(0.3, 1.2)))
                    exp = today - timedelta(days=random.randint(1, 15))
                elif i % 7 == 0:  # ~15% dưới ngưỡng thấp
                    qty = max(1, int(threshold * random.uniform(0.2, 0.8)))
                    exp = today + timedelta(days=random.randint(60, 400))
                elif i % 6 == 0:  # ~17% dư dả nhiều
                    qty = int(threshold * random.uniform(4, 8))
                    exp = today + timedelta(days=random.randint(60, 400))
                elif i % 5 == 0:  # ~20% sắp hết hạn trong 5-20 ngày (còn dùng được)
                    qty = int(threshold * random.uniform(1.5, 3.5))
                    exp = today + timedelta(days=random.randint(5, 20))
                else:  # còn lại — bình thường
                    qty = int(threshold * random.uniform(1.5, 3.5))
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
        print(f"✅ Đã tạo {len(inventory_rows)} lô tồn kho.")

        # ================== 3. PHIẾU NHẬP — đủ 7 tình huống khác nhau ==================
        def make_reconciled_receipt(code, supplier, skus, source_type="ocr"):
            """Phiếu ĐÃ đối chiếu xong TOÀN BỘ — mọi dòng khớp đúng số."""
            receipt = models.ImportReceipt(
                receipt_code=code, store_location=supplier,
                image_path=None if source_type == "manual" else f"./uploads/receipts/seed_{code}.jpg",
                ocr_raw_text=None if source_type == "manual" else f"Phiếu nhập {code} — dữ liệu seed, không qua OCR thật.",
                ocr_confidence=None if source_type == "manual" else 0.97,
                status="ocr_done", source_type=source_type,
                received_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1, 25)),
            )
            db.add(receipt)
            db.flush()

            for i, sku in enumerate(skus, start=1):
                qty = random.randint(50, 300)
                batch_code = _new_batch_code(used_batch_codes)
                exp = today + timedelta(days=random.randint(60, 300))
                li = models.ReceiptLineItem(
                    receipt_id=receipt.id, line_no=i,
                    product_name_raw=products[sku].name, product_id=products[sku].id,
                    quantity=qty, batch_code=batch_code, expiry_date=exp,
                    match_score=1.0, field_confidence={"quantity": 1.0, "batch": 1.0, "expiry": 1.0},
                )
                db.add(li)
                db.flush()

                started = receipt.received_at
                session = models.CameraCountSession(
                    session_code=f"cam-{code}-L{i}", camera_id="cam-01",
                    direction="import", linked_receipt_id=receipt.id,
                    receipt_line_item_id=li.id, product_id=li.product_id,
                    expected_quantity=li.quantity, counted_quantity=int(li.quantity),
                    avg_detection_confidence=round(random.uniform(0.85, 0.97), 2),
                    model_version="seed-manual", status="completed",
                    started_at=started, ended_at=started + timedelta(minutes=2 + i),
                )
                db.add(session)
                db.flush()

                db.add(models.Reconciliation(
                    receipt_id=receipt.id, receipt_line_item_id=li.id, product_id=li.product_id,
                    session_id=session.id, receipt_total=li.quantity, camera_total=int(li.quantity),
                    difference=0, threshold_used=0.02, status="matched",
                ))

                inv = models.Inventory(
                    product_id=li.product_id, batch_code=li.batch_code,
                    quantity=float(li.quantity), expiry_date=li.expiry_date,
                    last_updated=datetime.now(timezone.utc),
                )
                db.add(inv)
                db.flush()
                db.add(models.InventoryTransaction(
                    inventory_id=inv.id, change_qty=float(li.quantity),
                    transaction_type="import", reference_type="receipt_line", reference_id=li.id,
                ))
                inventory_rows.append((inv, sku, int(li.quantity)))

            receipt.status = "reconciled"
            return receipt

        def make_flagged_receipt(code, supplier, skus):
            """Phiếu quét OCR, DÒNG CUỐI CÙNG cố tình lệch — demo cảnh báo +
            quy trình xử lý sau (đa số OK, có 1 loại cần kiểm tra lại)."""
            receipt = models.ImportReceipt(
                receipt_code=code, store_location=supplier,
                image_path=f"./uploads/receipts/seed_{code}.jpg",
                ocr_raw_text=f"Phiếu nhập {code} — dữ liệu seed, không qua OCR thật.",
                ocr_confidence=0.94, status="ocr_done", source_type="ocr",
                received_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1, 10)),
            )
            db.add(receipt)
            db.flush()

            lines = []
            for i, sku in enumerate(skus, start=1):
                qty = random.randint(50, 300)
                batch_code = _new_batch_code(used_batch_codes)
                exp = today + timedelta(days=random.randint(60, 300))
                li = models.ReceiptLineItem(
                    receipt_id=receipt.id, line_no=i,
                    product_name_raw=products[sku].name, product_id=products[sku].id,
                    quantity=qty, batch_code=batch_code, expiry_date=exp, match_score=1.0,
                )
                db.add(li)
                lines.append(li)
            db.flush()

            flagged_idx = len(lines) - 1
            for idx, li in enumerate(lines):
                is_flagged = idx == flagged_idx
                counted_qty = li.quantity - random.randint(15, 40) if is_flagged else li.quantity
                started = receipt.received_at
                session = models.CameraCountSession(
                    session_code=f"cam-{code}-L{idx+1}", camera_id="cam-01",
                    direction="import", linked_receipt_id=receipt.id,
                    receipt_line_item_id=li.id, product_id=li.product_id,
                    expected_quantity=li.quantity, counted_quantity=counted_qty,
                    avg_detection_confidence=0.9, model_version="seed-manual",
                    status="needs_review" if is_flagged else "completed",
                    started_at=started, ended_at=started + timedelta(minutes=2 + idx),
                )
                db.add(session)
                db.flush()

                difference = counted_qty - float(li.quantity)
                recon = models.Reconciliation(
                    receipt_id=receipt.id, receipt_line_item_id=li.id, product_id=li.product_id,
                    session_id=session.id, receipt_total=li.quantity, camera_total=counted_qty,
                    difference=difference, threshold_used=0.02,
                    status="flagged" if is_flagged else "matched",
                )
                db.add(recon)
                db.flush()

                if is_flagged:
                    db.add(models.Alert(
                        alert_type="discrepancy", severity="high", reconciliation_id=recon.id,
                        message=(
                            f"[NHẬP] Lệch {difference:+.0f} khi đếm '{li.product_name_raw}' — "
                            f"camera đếm {counted_qty}, cần {li.quantity} (vượt ngưỡng 2.0%). "
                            f"Chưa cập nhật tồn kho cho dòng này — cần kiểm tra lại (phiên #{session.id})."
                        ),
                    ))
                else:
                    inv = models.Inventory(
                        product_id=li.product_id, batch_code=li.batch_code,
                        quantity=float(li.quantity), expiry_date=li.expiry_date,
                        last_updated=datetime.now(timezone.utc),
                    )
                    db.add(inv)
                    db.flush()
                    db.add(models.InventoryTransaction(
                        inventory_id=inv.id, change_qty=float(li.quantity),
                        transaction_type="import", reference_type="receipt_line", reference_id=li.id,
                    ))
                    inventory_rows.append((inv, skus[idx], int(li.quantity)))

            receipt.status = "ocr_done"  # còn dòng flagged -> chưa "reconciled" hoàn toàn
            return receipt

        def make_not_started_receipt(code, supplier, skus, source_type="ocr"):
            """Phiếu đã có đủ dòng hàng nhưng CHƯA đếm dòng nào cả — demo
            trạng thái phiếu mới tinh, để nhân viên bắt đầu đếm từ đầu."""
            receipt = models.ImportReceipt(
                receipt_code=code, store_location=supplier,
                image_path=None if source_type == "manual" else f"./uploads/receipts/seed_{code}.jpg",
                ocr_confidence=None if source_type == "manual" else 0.95,
                status="ocr_done", source_type=source_type,
                received_at=datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 12)),
            )
            db.add(receipt)
            db.flush()
            for i, sku in enumerate(skus, start=1):
                db.add(models.ReceiptLineItem(
                    receipt_id=receipt.id, line_no=i,
                    product_name_raw=products[sku].name, product_id=products[sku].id,
                    quantity=random.randint(30, 150), batch_code=_new_batch_code(used_batch_codes),
                    expiry_date=today + timedelta(days=random.randint(60, 300)),
                    match_score=1.0 if source_type == "manual" else 0.92,
                ))
            return receipt

        receipts_created = []
        receipts_created.append(make_reconciled_receipt("PN-2026-001", SUPPLIERS[0], ["SP-001", "SP-004", "SP-017", "SP-026"]))
        receipts_created.append(make_reconciled_receipt("PN-2026-002", SUPPLIERS[1], ["SP-011", "SP-013", "SP-014", "SP-016"]))
        receipts_created.append(make_flagged_receipt("PN-2026-003", SUPPLIERS[2], ["SP-021", "SP-023", "SP-025"]))
        receipts_created.append(make_reconciled_receipt("PN-2026-004", SUPPLIERS[3], ["SP-002", "SP-006", "SP-009"], source_type="manual"))
        receipts_created.append(make_not_started_receipt("PN-2026-005", SUPPLIERS[4], ["SP-018", "SP-019", "SP-027"], source_type="manual"))
        receipts_created.append(make_reconciled_receipt("PN-2026-007", SUPPLIERS[0], ["SP-003", "SP-010", "SP-030"]))

        # Phiếu "pending_ocr" — demo trạng thái đang chờ xử lý (chưa có dòng
        # hàng nào vì thực tế OCR chưa chạy xong/chưa được duyệt).
        receipt_pending = models.ImportReceipt(
            receipt_code="PN-2026-006", store_location=SUPPLIERS[2],
            image_path="./uploads/receipts/seed_PN-2026-006.jpg",
            status="pending_ocr", source_type="ocr",
            received_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        db.add(receipt_pending)
        receipts_created.append(receipt_pending)

        db.commit()
        print(f"✅ Đã tạo {len(receipts_created)} phiếu nhập (đủ các trạng thái: reconciled/flagged/not_started/pending_ocr, cả OCR lẫn tạo tay).")

        # ================== 4. LỊCH SỬ XUẤT KHO — có sẵn vài lượt để demo ngay ==================
        export_specs = [
            ("SP-004", 15, "camera_session", "Xuất theo đơn khách lẻ"),
            ("SP-017", 40, "camera_session", "Xuất cho đại lý con"),
            ("SP-026", 6, "manual", "Xuất huỷ (bao bì hư)"),
            ("SP-011", 20, "camera_session", None),
            ("SP-006", 10, "manual", None),
        ]
        n_exports = 0
        for sku, qty, ref_type, note in export_specs:
            product = products[sku]
            batches = (
                db.query(models.Inventory)
                .filter(models.Inventory.product_id == product.id, models.Inventory.quantity >= qty)
                .order_by(models.Inventory.expiry_date.asc().nullslast())
                .first()
            )
            if not batches:
                continue  # bỏ qua nếu không đủ tồn kho ở đúng 1 lô (bộ data nhỏ, chấp nhận bỏ sót vài trường hợp hiếm)

            batches.quantity = float(batches.quantity) - qty
            batches.last_updated = datetime.now(timezone.utc) - timedelta(days=random.randint(0, 5))

            fake_session_id = None
            if ref_type == "camera_session":
                sess = models.CameraCountSession(
                    direction="export", product_id=product.id, expected_quantity=qty,
                    counted_quantity=qty, status="completed",
                    started_at=batches.last_updated, ended_at=batches.last_updated,
                )
                db.add(sess)
                db.flush()
                fake_session_id = sess.id

            db.add(models.InventoryTransaction(
                inventory_id=batches.id, change_qty=-qty, transaction_type="export",
                reference_type=ref_type, reference_id=fake_session_id, note=note,
                created_at=batches.last_updated,
            ))
            n_exports += 1
        db.commit()
        print(f"✅ Đã tạo {n_exports} lượt xuất kho có sẵn trong Lịch sử xuất kho.")

        # ================== 5. CẢNH BÁO low_stock / expiring_soon tự sinh ==================
        n_alerts = 0
        seen_inv_ids = set()
        for inv, sku, qty in inventory_rows:
            if inv.id in seen_inv_ids:
                continue
            seen_inv_ids.add(inv.id)
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
            # CHỈ tính "sắp hết hạn" cho lô CHƯA hết hạn (>= hôm nay) — đúng
            # bản sửa lỗi trước đó (tools.py get_expiring_soon), tránh lặp
            # lại lỗi liệt kê nhầm lô ĐÃ hết hạn vào "sắp hết hạn".
            if inv.expiry_date and today <= inv.expiry_date <= today + timedelta(days=20):
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
        print(f"✅ Đã tạo {n_alerts} cảnh báo (low_stock + expiring_soon).")

        total_batches = db.query(models.Inventory).count()
        print("\n" + "=" * 60)
        print("✅ HOÀN TẤT SEED DATA")
        print("=" * 60)
        print(f"   - {len(PRODUCTS)} sản phẩm, {total_batches} lô tồn kho")
        print(f"   - {len(receipts_created)} phiếu nhập (đủ trạng thái + cả 2 nguồn tạo)")
        print(f"   - {n_exports} lượt xuất kho có sẵn")
        print(f"   - {n_alerts} cảnh báo tự sinh + 1 cảnh báo discrepancy")
        print("\n   Xem HUONG_DAN_DEMO.md để biết thứ tự demo từng tính năng.")

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-wipe", action="store_true", help="Không xoá data cũ, chỉ cộng thêm")
    args = parser.parse_args()
    seed_main(wipe=not args.no_wipe)
