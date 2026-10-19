"""Kiểm tra 7 bản sửa "Nhóm A" trên PostgreSQL thật. Phần ghi DB dùng dữ liệu tạm rồi ROLLBACK
(chặn commit); phần gọi API chỉ dùng request bị từ chối (không tạo gì).
Chạy từ thư mục backend:  python test\\check_group_a.py"""
import importlib
import inspect
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone

from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient
from PIL import Image

from app import models, push_service, schemas
from app.database import SessionLocal
from app.main import app
from app.routers import camera, receipts

client = TestClient(app)
db = SessionLocal()
n_receipts_before = db.query(models.ImportReceipt).count()
files_before = set(os.listdir(receipts.UPLOAD_DIR))


def ok(msg):
    print("OK  ", msg)


# 1) Validate ảnh phiếu ------------------------------------------------------
r = client.post("/receipts/upload", files={"file": ("evil.exe", b"MZ\x90", "application/octet-stream")})
assert r.status_code == 400 and "Chỉ nhận file ảnh" in r.json()["detail"], r.text
r = client.post("/receipts/upload", files={"file": ("fake.jpg", b"day khong phai anh", "image/jpeg")})
assert r.status_code == 400 and "không phải ảnh hợp lệ" in r.json()["detail"], r.text
r = client.post("/receipts/upload", files={"file": ("a.png", b"x", "text/html")})
assert r.status_code == 400 and "không phải ảnh" in r.json()["detail"], r.text
assert db.query(models.ImportReceipt).count() == n_receipts_before, "không được tạo phiếu rác"
assert set(os.listdir(receipts.UPLOAD_DIR)) == files_before, "không được để lại file rác"
buf = io.BytesIO()
Image.new("RGB", (8, 8), "white").save(buf, "PNG")
buf.seek(0)
p = receipts._save_validated_image(UploadFile(file=buf, filename="ok.PNG", headers=None))
assert os.path.exists(p)
os.remove(p)
old = receipts.MAX_RECEIPT_IMAGE_MB
receipts.MAX_RECEIPT_IMAGE_MB = 0.00001
buf.seek(0)
try:
    receipts._save_validated_image(UploadFile(file=buf, filename="big.png", headers=None))
    raise SystemExit("LỖI: phải chặn ảnh quá lớn")
except HTTPException as e:
    assert e.status_code == 413
finally:
    receipts.MAX_RECEIPT_IMAGE_MB = old
assert set(os.listdir(receipts.UPLOAD_DIR)) == files_before
ok("validate ảnh: .exe / ảnh giả / sai content-type / quá lớn bị chặn; PNG thật lưu được; không để rác")

# 2) Số lượng dương -----------------------------------------------------------
prod = db.query(models.Product).first()
for path, body in [
    ("/inventory/export", {"product_id": prod.id, "quantity": 0}),
    ("/inventory/export", {"product_id": prod.id, "quantity": -3}),
    ("/receipts/manual", {"line_items": [{"product_name_raw": "x", "quantity": -1}]}),
    ("/camera-sessions/start-export", {"product_id": prod.id, "expected_quantity": 0}),
]:
    r = client.post(path, json=body)
    assert r.status_code == 422 and isinstance(r.json()["detail"], str) and "lớn hơn 0" in r.json()["detail"], (path, r.text)
r = client.post("/camera-sessions/1/stop", json={"counted_quantity": -1})
assert r.status_code == 422 and "từ 0 trở lên" in r.json()["detail"], r.text
assert db.query(models.ImportReceipt).count() == n_receipts_before
ok("số lượng <= 0 bị từ chối (422, thông báo tiếng Việt, không tạo gì)")

# 3) VAPID mailto -------------------------------------------------------------
for raw in ["mailto:a@b.com", "MAILTO:a@b.com", " a@b.com "]:
    os.environ["VAPID_CLAIM_EMAIL"] = raw
    importlib.reload(push_service)
    assert push_service.VAPID_CLAIM_EMAIL == "a@b.com", (raw, push_service.VAPID_CLAIM_EMAIL)
os.environ.pop("VAPID_CLAIM_EMAIL")
importlib.reload(push_service)
ok("VAPID_CLAIM_EMAIL: bỏ 'mailto:' thừa và khoảng trắng")

# 4) Phiếu chỉ reconciled khi mọi dòng đã gán SP và đếm xong ---------------------
db.commit = db.flush  # chặn commit trong các hàm được gọi -> cuối cùng rollback sạch
try:
    p1 = models.Product(sku="TMP-A-1", name="SP A1", unit="thung")
    p2 = models.Product(sku="TMP-A-2", name="SP A2", unit="thung")
    db.add_all([p1, p2])
    db.flush()
    rc = models.ImportReceipt(receipt_code="TMP-A-RC", status="ocr_done", source_type="manual", received_at=datetime.now(timezone.utc))
    db.add(rc)
    db.flush()
    l1 = models.ReceiptLineItem(receipt_id=rc.id, line_no=1, product_name_raw="a", product_id=p1.id, quantity=5)
    l2 = models.ReceiptLineItem(receipt_id=rc.id, line_no=2, product_name_raw="b", product_id=None, quantity=5)
    db.add_all([l1, l2])
    db.flush()
    db.add(models.CameraCountSession(receipt_line_item_id=l1.id, linked_receipt_id=rc.id, product_id=p1.id, status="completed", direction="import", expected_quantity=5))
    db.flush()
    db.refresh(rc)
    camera._maybe_complete_receipt(db, rc.id)
    assert rc.status != "reconciled", "còn dòng chưa gán SP -> không được 'reconciled'"
    l2.product_id = p2.id
    db.add(models.CameraCountSession(receipt_line_item_id=l2.id, linked_receipt_id=rc.id, product_id=p2.id, status="completed", direction="import", expected_quantity=5))
    db.flush()
    db.refresh(rc)
    camera._maybe_complete_receipt(db, rc.id)
    assert rc.status == "reconciled", "gán đủ SP và đếm xong -> phải 'reconciled'"
    ok("phiếu 'reconciled' chỉ khi mọi dòng đã gán SP và đếm xong")

    # 5) Đếm lại có session_code riêng (PX cho xuất, DEM cho nhập) -----------------
    for direction, prefix in [("export", "PX"), ("import", "DEM")]:
        s = models.CameraCountSession(
            session_code=f"{prefix}9999", direction=direction, product_id=p1.id, expected_quantity=5,
            status="needs_review", counted_quantity=3,
            receipt_line_item_id=l1.id if direction == "import" else None,
            linked_receipt_id=rc.id if direction == "import" else None,
        )
        db.add(s)
        db.flush()
        new = camera.resolve_segment(s.id, schemas.CameraSegmentResolveRequest(action="recount"), db)
        assert new.session_code and new.session_code.startswith(prefix) and new.session_code != s.session_code, new.session_code
    ok("recount: phiên mới có mã PX…/DEM… mới")
finally:
    db.rollback()
    db.close()

# 6) Giới hạn danh sách -------------------------------------------------------
db2 = SessionLocal()
total_receipts = db2.query(models.ImportReceipt).count()
total_exports = db2.query(models.InventoryTransaction).filter_by(transaction_type="export").count()
db2.close()
got_r = len(client.get("/receipts").json())
got_e = len(client.get("/inventory/export-history").json())
assert got_r == min(total_receipts, 1000), (got_r, total_receipts)
assert got_e == min(total_exports, 1000), (got_e, total_exports)
assert len(client.get("/receipts?limit=5").json()) == min(5, total_receipts)
assert client.get("/receipts?limit=0").status_code == 422
ok(f"danh sách không còn cắt ở 100: receipts {got_r}/{total_receipts}, lượt xuất {got_e}/{total_exports}")

# 7) Endpoint nặng không còn async -------------------------------------------------
assert not inspect.iscoroutinefunction(camera.count_video_segment)
assert not inspect.iscoroutinefunction(camera.live_frame)
ok("count-video và live-frame chạy trong threadpool (không chặn event loop)")

db3 = SessionLocal()
assert db3.query(models.Product).filter(models.Product.sku.like("TMP-%")).count() == 0
assert db3.query(models.ImportReceipt).count() == n_receipts_before
db3.close()
print("TẤT CẢ OK — DB không còn dữ liệu tạm")
