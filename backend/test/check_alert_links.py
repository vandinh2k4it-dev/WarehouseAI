"""Kiểm tra liên kết cảnh báo -> sản phẩm/lô/phiếu/phiên đếm trên DB thật (CHỈ ĐỌC).
Chạy từ thư mục backend:  python test\\check_alert_links.py"""
import os
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from app.main import app

c = TestClient(app)
t0 = time.time()
total = 0
missing = Counter()
for status in ("open", "acknowledged"):
    r = c.get(f"/alerts?status={status}")
    assert r.status_code == 200, r.text
    rows = r.json()
    total += len(rows)
    for a in rows:
        t = a["alert_type"]
        if t == "low_stock" and not (a["product_id"] and a["batch_code"]):
            missing["low_stock thiếu sản phẩm/lô"] += 1
        if t == "discrepancy" and not (a["product_name"] and a["session_id"]):
            missing["discrepancy thiếu tên SP/phiên"] += 1
        if t == "discrepancy" and a["message"].startswith("[IMPORT]") and not a["receipt_id"]:
            missing["discrepancy nhập thiếu phiếu"] += 1
print(f"{total} cảnh báo, list mất {time.time() - t0:.2f}s; thiếu liên kết: {dict(missing) or 'không'}")
assert not missing

# Chi tiết: kiểm tra TẤT CẢ cảnh báo đang mở + vài cảnh báo đã xử lý mỗi loại
openl = c.get("/alerts?status=open").json()
done = c.get("/alerts?status=acknowledged").json()
sample = openl + [a for t in ("low_stock", "discrepancy") for a in [x for x in done if x["alert_type"] == t][:15]]
shown = set()
for a in sample:
    r = c.get(f"/alerts/{a['id']}/detail")
    assert r.status_code == 200, (a["id"], r.text)
    d = r.json()
    assert d["alert"]["id"] == a["id"]
    if a["alert_type"] == "low_stock":
        assert d["product"] and d["batch"], a
        assert d["product"]["total_stock"] >= 0
    if a["alert_type"] == "discrepancy":
        assert d["reconciliation"] and d["session"], a
        assert d["reconciliation"]["camera_total"] == d["session"]["counted_quantity"], a
        if a["message"].startswith("[IMPORT]"):
            assert d["receipt"] and d["line"], a
            assert d["line"]["id"] == a["receipt_line_id"]
            assert d["line_latest_session_status"] in ("counting", "completed", "needs_review", "resolved_override", "superseded"), d["line_latest_session_status"]
    key = (a["alert_type"], a["message"][:8])
    if key not in shown:
        shown.add(key)
        print(f"  chi tiết #{a['id']} ({a['alert_type']}): SP={d['product'] and d['product']['name']!r}, lô={d['batch'] and d['batch']['batch_code']}, "
              f"phiếu={d['receipt'] and d['receipt']['receipt_code']}, phiên={d['session'] and d['session']['session_code']}, "
              f"video={'có' if d['session'] and d['session']['annotated_video_url'] else 'không'}")
assert c.get("/alerts/99999999/detail").status_code == 404
print(f"OK — đã kiểm tra chi tiết {len(sample)} cảnh báo")
