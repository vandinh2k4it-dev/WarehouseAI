"""Test FEFO bỏ lô hết hạn trên PostgreSQL thật — tạo dữ liệu tạm rồi ROLLBACK,
không để lại gì trong DB. Chạy từ thư mục backend: python test\\check_fefo_expired.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import date, timedelta

from fastapi import HTTPException
from app.database import SessionLocal
from app import models
from app.routers.inventory import perform_fefo_export

db = SessionLocal()
db.commit = db.flush  # perform_fefo_export tự commit -> chặn lại để cuối cùng rollback sạch
try:
    p = models.Product(sku="TMP-FEFO-TEST", name="SP test FEFO", unit="thung", low_stock_threshold=1)
    db.add(p); db.flush()
    today = date.today()
    exp = models.Inventory(product_id=p.id, batch_code="EXPIRED", quantity=10, expiry_date=today - timedelta(days=5))
    ok1 = models.Inventory(product_id=p.id, batch_code="SOON", quantity=5, expiry_date=today + timedelta(days=10))
    ok2 = models.Inventory(product_id=p.id, batch_code="LATER", quantity=5, expiry_date=today + timedelta(days=90))
    db.add_all([exp, ok1, ok2]); db.flush()

    r = perform_fefo_export(db, p.id, 7)
    used = {d.batch_code: d.quantity_deducted for d in r.details} if hasattr(r, "details") else None
    print("xuat 7:", used)
    db.refresh(exp)
    assert float(exp.quantity) == 10, "lo het han khong duoc bi tru"

    try:
        perform_fefo_export(db, p.id, 4)  # con 3 lo con han -> phai bao thieu du con 10 het han
        raise SystemExit("LOI: phai bao khong du ton")
    except HTTPException as e:
        print("xuat 4 ->", e.status_code, e.detail)
        assert e.status_code == 400 and "hết hạn" in e.detail

    r = perform_fefo_export(db, p.id, 10, batch_code="EXPIRED")  # chi dinh ro lo het han van duoc
    print("chi dinh lo EXPIRED: OK")
    print("OK")
finally:
    db.rollback()
    db.close()
