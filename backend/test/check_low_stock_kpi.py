"""So sánh KPI 'sắp hết hàng' cũ (đếm theo lô) và mới (đếm theo sản phẩm) trên DB thật.
Chỉ đọc, không ghi gì. Chạy: python test\\check_low_stock_kpi.py (từ thư mục backend)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app import models
from app.chatbot import tools

db = SessionLocal()
old_batches = (
    db.query(models.Inventory).join(models.Product)
    .filter(models.Inventory.quantity <= models.Product.low_stock_threshold).count()
)
chatbot_n = len(tools.get_low_stock_products(db))
db.close()

c = TestClient(app)
kpi = c.get("/inventory/analytics").json()["kpis"]["low_stock_products"]
rows = c.get("/inventory/low-stock").json()
print("cu (dem theo lo):", old_batches)
print("KPI moi:", kpi, "| chatbot:", chatbot_n)
print("so lo tra ve tu /low-stock:", len(rows), "| lo ton<=0:", sum(1 for r in rows if r["quantity"] <= 0))
assert kpi == chatbot_n, "KPI phai khop chatbot"
assert all(r["quantity"] > 0 for r in rows)
print("OK")
