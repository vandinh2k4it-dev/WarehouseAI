"""Script kiểm tra toàn bộ luồng backend end-to-end trong 1 lần chạy — dùng
sau khi OCR đã chạy được qua API thật (như phiếu #47 vừa test).

Chạy: python test\verify_full_flow.py [receipt_id]
(mặc định receipt_id=47 nếu không truyền, đổi số cho khớp phiếu mới nhất
của bạn — xem cột ID trong bảng "PHIẾU NHẬP GẦN ĐÂY" trên web UI)

Làm những việc sau, IN RA từng bước để bạn thấy rõ đúng/sai ở đâu:
1. Map tất cả dòng hàng "chưa khớp" của phiếu này thành sản phẩm mới.
2. Hỏi thử chatbot (mock mode) về 1 sản phẩm vừa map — xác nhận nó tra
   đúng DB thật.
3. Tạo 1 phiên đếm camera GIẢ LẬP (nhập tay, không cần model YOLOv8 thật)
   khớp đúng tổng số lượng của phiếu -> chạy đối chiếu -> phải ra "matched"
   và tự cộng vào tồn kho.
4. Xuất kho thử 1 ít theo FEFO -> xác nhận trừ đúng lô hết hạn sớm nhất.
5. Kiểm tra danh sách cảnh báo hiện có.

Không cần cài gì thêm ngoài `requests` (đã có sẵn trong requirements.txt).
"""
import sys

import requests

BASE = "http://localhost:8000"
RECEIPT_ID = int(sys.argv[1]) if len(sys.argv) > 1 else 47


def step(title):
    print(f"\n{'='*60}\n{title}\n{'='*60}")


def check(resp: requests.Response, label: str):
    ok = resp.status_code < 400
    mark = "✅" if ok else "❌"
    print(f"{mark} {label} -> {resp.status_code}")
    if not ok:
        print(f"   Chi tiết lỗi: {resp.text}")
    return ok


# ---------------------------------------------------------------------
step(f"1. Map các dòng hàng chưa khớp của phiếu #{RECEIPT_ID} thành sản phẩm")
r = requests.get(f"{BASE}/products/unmapped-lines")
check(r, "GET /products/unmapped-lines")
lines = [l for l in r.json() if l["receipt_id"] == RECEIPT_ID]

if not lines:
    print(f"⚠️  Không còn dòng nào của phiếu #{RECEIPT_ID} đang 'chưa khớp' "
          f"— có thể đã map hết từ trước, hoặc receipt_id sai. Bỏ qua bước map.")
else:
    for line in lines:
        r = requests.post(f"{BASE}/products/lines/{line['line_id']}/create-and-map")
        ok = check(r, f"Map '{line['product_name_raw']}' (line #{line['line_id']})")
        if ok:
            print(f"   -> Tạo sản phẩm mới: {r.json()}")

# ---------------------------------------------------------------------
step("2. Hỏi thử chatbot về 1 sản phẩm vừa map")
first_product_name = lines[0]["product_name_raw"] if lines else "Bánh Oreo"
r = requests.post(f"{BASE}/chatbot/ask", json={"message": f"Còn bao nhiêu {first_product_name} trong kho?"})
check(r, "POST /chatbot/ask")
if r.ok:
    data = r.json()
    print(f"   Trả lời: {data['reply']}")
    print(f"   Tool đã gọi: {[tc['tool'] for tc in data['tool_calls']]}")

# ---------------------------------------------------------------------
step(f"3. Tạo phiên đếm camera giả lập + đối chiếu với phiếu #{RECEIPT_ID}")
r = requests.get(f"{BASE}/receipts/{RECEIPT_ID}")
if not check(r, f"GET /receipts/{RECEIPT_ID}"):
    print("Dừng lại — không lấy được phiếu, kiểm tra receipt_id truyền vào đúng chưa.")
    sys.exit(1)

receipt = r.json()
total_qty = sum(float(li["quantity"]) for li in receipt["line_items"])
print(f"   Tổng SL trên phiếu: {total_qty}")

r = requests.post(f"{BASE}/camera-sessions", json={
    "session_code": f"test-verify-{RECEIPT_ID}",
    "camera_id": "cam-test",
    "linked_receipt_id": RECEIPT_ID,
    "counted_quantity": int(total_qty),  # khớp chính xác để test luồng "matched"
    "avg_detection_confidence": 0.95,
    "model_version": "manual-test",
})
check(r, "POST /camera-sessions (giả lập, khớp đúng số)")
session_id = r.json()["id"] if r.ok else None

if session_id:
    r = requests.post(f"{BASE}/reconciliation/run", json={
        "receipt_id": RECEIPT_ID,
        "session_id": session_id,
        "threshold_pct": 0.02,
    })
    ok = check(r, "POST /reconciliation/run")
    if ok:
        recon = r.json()
        print(f"   Trạng thái: {recon['status']} (kỳ vọng 'matched' vì số khớp đúng)")
        if recon["status"] != "matched":
            print("   ⚠️  Không khớp — kiểm tra lại logic threshold hoặc số liệu.")

# ---------------------------------------------------------------------
step("4. Xem tồn kho sau khi đối chiếu (phải đã cộng dồn)")
r = requests.get(f"{BASE}/inventory")
check(r, "GET /inventory")
if r.ok:
    for row in r.json()[:10]:
        print(f"   product_id={row['product_id']} lô={row['batch_code']} SL={row['quantity']}")

# ---------------------------------------------------------------------
step("5. Xuất kho thử theo FEFO (nếu có sản phẩm nào vừa nhập)")
inv = requests.get(f"{BASE}/inventory").json()
if inv:
    pid = inv[0]["product_id"]
    export_qty = min(5, float(inv[0]["quantity"]))
    r = requests.post(f"{BASE}/inventory/export", json={
        "product_id": pid,
        "quantity": export_qty,
        "note": "Test xuất kho FEFO tự động (verify_full_flow.py)",
    })
    check(r, f"POST /inventory/export (product_id={pid}, SL={export_qty})")
    if r.ok:
        print(f"   Chi tiết: {r.json()}")
else:
    print("⚠️  Chưa có tồn kho nào để test xuất — chạy lại sau khi bước 3 thành công.")

# ---------------------------------------------------------------------
step("6. Danh sách cảnh báo hiện có")
r = requests.get(f"{BASE}/alerts")
check(r, "GET /alerts")
if r.ok:
    for a in r.json()[:10]:
        print(f"   [{a['alert_type']}/{a['severity']}] {a['message']}")

print("\n" + "=" * 60)
print("XONG. Đọc lại từng bước ✅/❌ ở trên để biết chỗ nào cần sửa tiếp.")
print("=" * 60)
