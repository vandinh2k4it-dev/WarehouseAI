"""Vòng lặp gọi Claude API với tool-use (function-calling) để chatbot trả
lời câu hỏi của nhân viên kho dựa trên dữ liệu THẬT trong Postgres — mục 6.6
đề cương.

Dùng model Haiku (rẻ nhất dòng Claude hiện tại) vì đây là tác vụ tra cứu đơn
giản (đọc DB, trả lời ngắn), không cần model mạnh/tốn kém hơn.
"""
import json
import os

import anthropic
from anthropic import Anthropic
from sqlalchemy.orm import Session

from app.chatbot.tools import TOOLS, TOOL_FUNCTIONS
from app.chatbot.mock_service import mock_ask

MODEL_NAME = "claude-haiku-4-5-20251001"
MAX_TOOL_ROUNDS = 5  # chặn vòng lặp vô hạn nếu Claude cứ liên tục gọi tool

SYSTEM_PROMPT = """Bạn là trợ lý AI của hệ thống quản lý kho hàng thông minh.
Vai trò: trả lời nhân viên kho các câu hỏi về tồn kho, phiếu nhập hàng, cảnh
báo (hàng sắp hết, sắp hết hạn, lệch số liệu đối chiếu camera-phiếu nhập).

QUY TẮC QUAN TRỌNG:
- LUÔN dùng tool để lấy dữ liệu thật trước khi trả lời câu hỏi liên quan đến
  số liệu cụ thể (tồn kho, ngày hết hạn, trạng thái phiếu...). KHÔNG được tự
  bịa số liệu.
- Nếu tool trả về rỗng/không tìm thấy, nói rõ là không tìm thấy, không suy
  đoán.
- Trả lời ngắn gọn, đúng trọng tâm, bằng tiếng Việt, giọng điệu như nhân
  viên văn phòng nói chuyện với đồng nghiệp — không dùng tool nào để SỬA dữ
  liệu (không có tool nào làm việc đó, tất cả chỉ đọc).
- Nếu câu hỏi mơ hồ (vd tên sản phẩm gõ tắt/sai chính tả), dùng search_products
  trước để tìm tên đúng, rồi mới tra tồn kho.
"""


def _get_client() -> Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Chưa cấu hình ANTHROPIC_API_KEY. Thêm dòng ANTHROPIC_API_KEY=sk-ant-... "
            "vào file .env (xem .env.example)."
        )
    return Anthropic(api_key=api_key)


def ask_chatbot(db: Session, user_message: str, history: list[dict] | None = None) -> dict:
    """Gửi câu hỏi cho Claude, để Claude tự gọi tool tra DB nếu cần, trả về
    câu trả lời cuối cùng + log các tool đã gọi (để debug/hiển thị minh bạch
    cho người dùng thấy chatbot lấy dữ liệu từ đâu ra).

    Tự động chuyển sang MOCK MODE (app/chatbot/mock_service.py — không gọi
    Claude thật, không tốn credit) trong 3 trường hợp — MỖI TRƯỜNG HỢP GẮN
    ĐÚNG 1 TIỀN TỐ RIÊNG BIỆT vào câu trả lời để người dùng tự chẩn đoán
    được ngay trong khung chat, không cần mò log Railway:
    1. Biến CHATBOT_MOCK đang bật (ép mock dù có key thật — thường do quên
       tắt sau lúc test).
    2. Chưa cấu hình ANTHROPIC_API_KEY (biến trống/chưa deploy lại).
    3. Có key nhưng gọi Claude thật bị lỗi — bắt RỘNG theo anthropic.APIError
       (lớp cha chung của CẢ APIStatusError [lỗi HTTP: sai định dạng key ->
       401 AuthenticationError, hết credit -> 400, rate limit -> 429] LẪN
       APIConnectionError [lỗi mạng/DNS/timeout] — bản trước chỉ bắt
       APIStatusError, bỏ sót lỗi mạng, khiến request bị crash 500 thay vì
       rớt êm về mock).
    """
    force_mock = os.getenv("CHATBOT_MOCK", "").lower() in ("1", "true", "yes")
    has_key = bool(os.getenv("ANTHROPIC_API_KEY"))

    if force_mock:
        fallback = mock_ask(db, user_message, history)
        fallback["reply"] = (
            "[MOCK — biến CHATBOT_MOCK đang BẬT trên server, ép dùng mô phỏng dù "
            "có thể đã có ANTHROPIC_API_KEY thật. Xoá biến CHATBOT_MOCK trên Railway "
            "nếu muốn dùng AI thật.]\n" + fallback["reply"]
        )
        return fallback

    if not has_key:
        fallback = mock_ask(db, user_message, history)
        fallback["reply"] = (
            "[MOCK — CHƯA CÓ biến ANTHROPIC_API_KEY trên server (đọc ra rỗng). "
            "Kiểm tra lại: (1) đã thêm đúng tên biến ANTHROPIC_API_KEY trên Railway "
            "chưa (phân biệt hoa/thường, không thừa khoảng trắng), (2) đã LƯU biến "
            "chưa, (3) Railway đã BUILD LẠI xong chưa (đổi biến môi trường luôn cần "
            "build lại mới có hiệu lực, không tự áp dụng ngay lập tức).]\n"
            + fallback["reply"]
        )
        return fallback

    try:
        return _ask_claude_real(db, user_message, history)
    except anthropic.APIError as e:
        status_code = getattr(e, "status_code", None)
        error_detail = type(e).__name__ + (f" (HTTP {status_code})" if status_code else "") + f": {e}"
        fallback = mock_ask(db, user_message, history)
        fallback["reply"] = f"[MOCK — gọi Claude API thật thất bại: {error_detail}]\n" + fallback["reply"]
        return fallback


def _ask_claude_real(db: Session, user_message: str, history: list[dict] | None = None) -> dict:
    """Luồng gọi Claude API thật + vòng lặp tool-use — tách riêng khỏi
    ask_chatbot() để hàm đó có thể bắt lỗi và fallback sang mock gọn hơn."""
    client = _get_client()
    messages: list[dict] = list(history or [])
    messages.append({"role": "user", "content": user_message})

    tool_call_log: list[dict] = []

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        # Convert luôn sang dict thuần (model_dump) — response.content là các
        # object SDK (TextBlock/ToolUseBlock), không JSON-serialize trực tiếp
        # được. Cần dict thuần để: (1) trả về client qua API, (2) client gửi
        # lại làm "history" ở câu hỏi tiếp theo mà không lỗi.
        assistant_content = [block.model_dump() for block in response.content]

        if response.stop_reason != "tool_use":
            final_text = "".join(b["text"] for b in assistant_content if b["type"] == "text")
            return {
                "reply": final_text,
                "tool_calls": tool_call_log,
                "messages": messages + [{"role": "assistant", "content": assistant_content}],
            }

        # Claude yêu cầu gọi 1 hoặc nhiều tool -> chạy thật, gửi kết quả lại
        messages.append({"role": "assistant", "content": assistant_content})

        tool_results = []
        for block in assistant_content:
            if block["type"] != "tool_use":
                continue

            func = TOOL_FUNCTIONS.get(block["name"])
            if func is None:
                result_content = {"error": f"Không có tool tên '{block['name']}'"}
            else:
                try:
                    result_content = func(db, **block["input"])
                except Exception as e:  # noqa: BLE001 — muốn bắt mọi lỗi để trả về Claude, không crash request
                    result_content = {"error": str(e)}

            tool_call_log.append({"tool": block["name"], "input": block["input"], "output": result_content})
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": json.dumps(result_content, ensure_ascii=False, default=str),
                }
            )

        messages.append({"role": "user", "content": tool_results})

    # Vượt quá số vòng cho phép — trả lời an toàn thay vì treo request
    return {
        "reply": "Xin lỗi, câu hỏi này cần tra cứu nhiều bước quá mức cho phép. Bạn thử hỏi cụ thể/ngắn gọn hơn nhé.",
        "tool_calls": tool_call_log,
        "messages": messages,
    }
