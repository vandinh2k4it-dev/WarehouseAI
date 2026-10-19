"""Dọn cảnh báo 'low_stock' cũ (tạo theo từng lô, rất nhiễu) về dạng gộp theo sản phẩm:
mỗi sản phẩm tồn thấp chỉ giữ 1 cảnh báo mở, sản phẩm đã đủ hàng thì đóng hết.
Chỉ đổi status/resolved_at/message của cảnh báo, KHÔNG đụng tồn kho hay giao dịch.

Mặc định chỉ XEM TRƯỚC. Thêm --confirm mới ghi thật. Nên pg_dump trước.
Chạy từ thư mục backend:  python -m db.migrate_merge_low_stock_alerts [--confirm]"""
import sys

from app.database import SessionLocal
from app import models
from app.routers.inventory import sync_low_stock_alert


def main(confirm: bool):
    db = SessionLocal()
    try:
        product_ids = [
            r[0]
            for r in db.query(models.Inventory.product_id)
            .join(models.Alert, models.Alert.inventory_id == models.Inventory.id)
            .filter(models.Alert.alert_type == "low_stock", models.Alert.status == "open")
            .distinct()
            .all()
        ]
        open_before = db.query(models.Alert).filter_by(alert_type="low_stock", status="open").count()
        for pid in product_ids:
            sync_low_stock_alert(db, pid)
        db.flush()
        open_after = db.query(models.Alert).filter_by(alert_type="low_stock", status="open").count()
        print(f"low_stock đang mở: {open_before} -> {open_after} ({len(product_ids)} sản phẩm có cảnh báo)")
        if confirm:
            db.commit()
            print("Đã ghi.")
        else:
            db.rollback()
            print("Chỉ xem trước, chưa ghi gì. Thêm --confirm để áp dụng.")
    finally:
        db.close()


if __name__ == "__main__":
    main("--confirm" in sys.argv)
