"""Chế độ MÔ PHỎNG (mock) — dùng khi CHƯA có credit Claude API hoặc muốn
test nhanh không tốn tiền. KHÔNG gọi Claude thật — thay vào đó tự chọn tool
theo từ khóa đơn giản trong câu hỏi, chạy tool đó lấy dữ liệu THẬT từ
Postgres, rồi ghép thành câu trả lời bằng template có sẵn.

Mục đích: cho phép test toàn bộ phần khó (DB query, API wiring, tool logic)
hoàn toàn miễn phí. Phần CHƯA test được ở chế độ này: khả năng hiểu ngôn ngữ
tự nhiên linh hoạt của Claude thật (câu hỏi diễn đạt khác thường, câu hỏi
nhiều bước, ngữ cảnh hội thoại phức tạp) — cái đó bắt buộc phải test bằng
API thật (dù chỉ vài nghìn đồng credit) trước khi coi khóa luận hoàn thành
phần chatbot.

Bật chế độ này bằng cách KHÔNG cấu hình ANTHROPIC_API_KEY, hoặc set biến môi
trường CHATBOT_MOCK=true (ưu tiên hơn, dùng khi muốn ép mock dù đã có key,
vd để giữ credit)."""
import re
import unicodedata

from sqlalchemy.orm import Session

from app import models
from app.chatbot import tools as T


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip()


def _has_word(norm_msg: str, word: str) -> bool:
    """So khớp THEO TỪ TRỌN VẸN (word boundary), không phải chuỗi con.
    Lý do bắt buộc phải làm vậy: sau khi bỏ dấu, 'hạn' -> 'han' lại là 3 ký
    tự ĐẦU của 'hàng' -> 'hang' — so khớp chuỗi con kiểu `'han' in text` sẽ
    khiến câu hỏi về HÀNG (low stock) bị nhận nhầm thành câu hỏi về HẠN
    (expiring soon). Ví dụ lỗi thật đã gặp: 'sắp hết hàng' bị nhận nhầm
    thành 'sắp hết hạn' vì chuỗi 'het han' nằm trọn trong 'het hang'."""
    return re.search(rf"\b{re.escape(word)}\b", norm_msg) is not None


def _extract_product_name(db: Session, message: str) -> str | None:
    """Tìm xem câu hỏi có nhắc tên sản phẩm nào đã có trong danh mục không
    (so khớp không dấu, không phân biệt hoa/thường). Trả về tên KHỚP DÀI
    NHẤT nếu có nhiều khớp (vd tránh 'Bánh' khớp nhầm cả 'Bánh Oreo' lẫn
    'Bánh Solite' khi câu hỏi thật sự nhắc rõ 1 trong 2)."""
    norm_msg = _norm(message)
    products = db.query(models.Product.name).all()
    best_match = None
    for (name,) in products:
        if _norm(name) in norm_msg:
            if best_match is None or len(name) > len(best_match):
                best_match = name
    return best_match


def mock_ask(db: Session, user_message: str, history: list[dict] | None = None) -> dict:
    norm_msg = _norm(user_message)
    tool_call_log: list[dict] = []

    def run(tool_name: str, **kwargs) -> dict:
        result = T.TOOL_FUNCTIONS[tool_name](db, **kwargs)
        tool_call_log.append({"tool": tool_name, "input": kwargs, "output": result})
        return result

    # --- Định tuyến theo từ khóa, đơn giản hoá RẤT NHIỀU so với Claude thật ---
    if _has_word(norm_msg, "han") or "hsd" in norm_msg:
        days_match = re.search(r"(\d+)\s*ngay", norm_msg)
        days = int(days_match.group(1)) if days_match else 30
        result = run("get_expiring_soon", days=days)
        if not result:
            reply = f"[MOCK] Không có lô hàng nào sắp hết hạn trong {days} ngày tới."
        else:
            lines = [f"- {r['product_name']} (lô {r['batch_code']}): còn {r['days_left']} ngày, HSD {r['expiry_date']}" for r in result]
            reply = f"[MOCK — trả lời bằng template, không phải Claude thật] Có {len(result)} lô sắp hết hạn trong {days} ngày tới:\n" + "\n".join(lines)

    elif any(k in norm_msg for k in ["sap het", "ton kho thap", "can nhap them", "thieu hang"]):
        result = run("get_low_stock_products")
        if not result:
            reply = "[MOCK] Hiện không có sản phẩm nào dưới ngưỡng tồn kho thấp."
        else:
            lines = [f"- {r['product_name']}: còn {r['total_quantity']} {r['unit']} (ngưỡng cảnh báo {r['threshold']})" for r in result]
            reply = "[MOCK] Sản phẩm đang tồn kho thấp:\n" + "\n".join(lines)

    elif any(k in norm_msg for k in ["canh bao"]):
        result = run("get_open_alerts")
        if not result:
            reply = "[MOCK] Không có cảnh báo nào đang mở."
        else:
            lines = [f"- [{r['type']}/{r['severity']}] {r['message']}" for r in result]
            reply = "[MOCK] Cảnh báo đang mở:\n" + "\n".join(lines)

    elif any(k in norm_msg for k in ["lech", "doi chieu", "khong khop"]):
        result = run("get_recent_discrepancies")
        if not result:
            reply = "[MOCK] Không có lần đối chiếu nào bị lệch gần đây."
        else:
            lines = [f"- Phiếu #{r['receipt_id']}: phiếu ghi {r['receipt_total']}, camera đếm {r['camera_total']} (lệch {r['difference']})" for r in result]
            reply = "[MOCK] Các lần đối chiếu bị lệch gần đây:\n" + "\n".join(lines)

    elif "phieu" in norm_msg:
        id_match = re.search(r"#?(\d+)", norm_msg)
        if id_match:
            result = run("get_receipt_status", receipt_id=int(id_match.group(1)))
            if not result.get("found"):
                reply = f"[MOCK] {result.get('message')}"
            else:
                reply = f"[MOCK] Phiếu #{result['id']} — trạng thái: {result['status']}, {len(result['line_items'])} dòng hàng."
        else:
            reply = "[MOCK] Bạn muốn xem phiếu nhập số mấy? (vd 'phiếu #12')"

    else:
        product_name = _extract_product_name(db, user_message)
        if product_name:
            if any(k in norm_msg for k in ["lo", "ma lo", "chi tiet", "hsd"]):
                result = run("get_inventory_by_product", product_name=product_name)
                if not result:
                    reply = f"[MOCK] Không tìm thấy lô tồn kho nào của '{product_name}'."
                else:
                    lines = [f"- Lô {r['batch_code']}: {r['quantity']} {r['unit']}, HSD {r['expiry_date']}" for r in result]
                    reply = f"[MOCK] Tồn kho chi tiết '{product_name}':\n" + "\n".join(lines)
            else:
                result = run("get_total_stock", product_name=product_name)
                if not result.get("found"):
                    reply = f"[MOCK] {result.get('message')}"
                else:
                    reply = f"[MOCK] Kho hiện còn {result['total_quantity']} {result['unit']} {result['product_name']}."
        else:
            result = run("search_products", keyword=user_message.strip())
            if result:
                names = ", ".join(r["name"] for r in result)
                reply = f"[MOCK] Không hiểu rõ câu hỏi, nhưng tìm được các sản phẩm gần giống: {names}."
            else:
                reply = (
                    "[MOCK] Chế độ mô phỏng chỉ hiểu vài mẫu câu đơn giản (tồn kho, sắp hết, "
                    "sắp hết hạn, cảnh báo, phiếu nhập, đối chiếu lệch). Thử hỏi lại theo mẫu đó, "
                    "hoặc nạp credit Claude API thật để chatbot hiểu được câu hỏi tự do."
                )

    new_history = list(history or [])
    new_history.append({"role": "user", "content": user_message})
    new_history.append({"role": "assistant", "content": [{"type": "text", "text": reply}]})

    return {"reply": reply, "tool_calls": tool_call_log, "messages": new_history}
