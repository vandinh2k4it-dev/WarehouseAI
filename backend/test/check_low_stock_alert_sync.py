"""Test cảnh báo low_stock gộp theo sản phẩm + tự đóng khi nhập thêm, trên PostgreSQL thật.
Tạo dữ liệu tạm rồi ROLLBACK (chặn commit). Chạy từ backend: python test\\check_low_stock_alert_sync.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import date, timedelta

from app.database import SessionLocal
from app import models
from app.routers.inventory import perform_fefo_export, sync_low_stock_alert
from app.routers.reconciliation import apply_line_import

db = SessionLocal()
db.commit = db.flush  # perform_fefo_export tự commit -> chặn để rollback sạch cuối cùng
from app import push_service
pushed = []
push_service.send_push_to_all = lambda *a, **k: pushed.append(k.get("body"))  # KHÔNG gửi push thật


def open_alerts(pid):
    db.flush()  # SessionLocal tắt autoflush -> phải flush tay để truy vấn thấy thay đổi chưa commit
    return (
        db.query(models.Alert).join(models.Inventory, models.Alert.inventory_id == models.Inventory.id)
        .filter(models.Inventory.product_id == pid, models.Alert.alert_type == "low_stock", models.Alert.status == "open")
        .all()
    )


try:
    exp = date.today() + timedelta(days=60)
    p = models.Product(sku="TMP-LOW-TEST", name="SP test low", unit="thung", low_stock_threshold=10)
    db.add(p); db.flush()
    a = models.Inventory(product_id=p.id, batch_code="A", quantity=8, expiry_date=exp)
    b = models.Inventory(product_id=p.id, batch_code="B", quantity=8, expiry_date=exp + timedelta(days=30))
    db.add_all([a, b]); db.flush()

    # tổng 16 >= 10: xuất 5 lô A -> A còn 3 (cũ sẽ báo vì 3 <= 10) nhưng tổng 11 -> KHÔNG báo
    perform_fefo_export(db, p.id, 5)
    assert len(open_alerts(p.id)) == 0, "tổng còn 11 >= ngưỡng, không được báo"

    # xuất tiếp 3 -> tổng 8 < 10 -> đúng 1 cảnh báo (dù nhiều lô)
    perform_fefo_export(db, p.id, 3)
    al = open_alerts(p.id)
    assert len(al) == 1, f"phải đúng 1 cảnh báo, có {len(al)}"
    print("tạo:", al[0].message)

    # xuất thêm -> vẫn 1 cảnh báo, số còn lại được cập nhật
    perform_fefo_export(db, p.id, 2)
    al = open_alerts(p.id)
    assert len(al) == 1 and "6" in al[0].message, al[0].message
    print("cập nhật:", al[0].message)

    # dữ liệu cũ: thêm cảnh báo trùng theo lô -> sync gộp còn 1
    db.add(models.Alert(alert_type="low_stock", severity="medium", inventory_id=b.id, message="cũ"))
    db.flush()
    assert len(open_alerts(p.id)) == 2
    sync_low_stock_alert(db, p.id)
    assert len(open_alerts(p.id)) == 1, "phải gộp cảnh báo trùng"

    # nhập thêm 20 -> tổng 26 >= 10 -> tự đóng
    from types import SimpleNamespace  # apply_line_import chỉ đọc thuộc tính của dòng phiếu
    line = SimpleNamespace(id=0, product_id=p.id, quantity=20, batch_code="C", expiry_date=exp)
    apply_line_import(db, line)
    assert len(open_alerts(p.id)) == 0, "nhập thêm đủ ngưỡng phải tự đóng"
    closed = db.query(models.Alert).join(models.Inventory, models.Alert.inventory_id == models.Inventory.id) \
        .filter(models.Inventory.product_id == p.id, models.Alert.status == "acknowledged").all()
    assert closed and all(x.resolved_at is not None for x in closed)
    print("nhập thêm -> tự đóng", len(closed), "cảnh báo")
    print("OK")
finally:
    db.rollback()
    db.close()
