"""Vòng lặp gọi AI với tool-use (function-calling) để chatbot trả lời câu
hỏi của nhân viên kho dựa trên dữ liệu THẬT trong Postgres — mục 6.6 đề
cương.

ĐÃ CHUYỂN từ Claude (Anthropic) sang Gemini (Google) — lý do: Gemini có
free tier THẬT (không cần thẻ tín dụng/nạp tiền) đủ dùng cho khối lượng
dùng ở quy mô demo khóa luận, xem chi tiết bên dưới. Model dùng:
gemini-3.6-flash — ĐÃ ĐỔI 1 LẦN từ gemini-2.5-flash vì Google ngừng hỗ trợ
model đó cho user mới (lỗi 404 thật gặp phải: "This model
models/gemini-2.5-flash is no longer available to new users. Please
update your code to use models/gemini-3.6-flash") — XÁC NHẬN THỰC TẾ tên
model AI của Google đổi RẤT NHANH, có thể lại đổi tiếp trong tương lai. Nếu
gặp lỗi "404 NOT_FOUND" tương tự, đọc kỹ nội dung lỗi — Google THƯỜNG TỰ
NÓI LUÔN tên model mới cần đổi sang ngay trong thông báo lỗi (như lần này),
chỉ cần đổi đúng hằng số MODEL_NAME bên dưới, không cần sửa gì khác.

SDK dùng: google-genai (SDK thống nhất mới của Google, KHÔNG PHẢI SDK cũ
"google-generativeai" đã ngừng phát triển) — cài qua `pip install
google-genai`, đã thêm vào requirements.txt.
"""
import json
import os

from google import genai
from google.genai import types
from google.genai import errors as genai_errors
from sqlalchemy.orm import Session

from app.chatbot.tools import TOOLS, TOOL_FUNCTIONS
from app.chatbot.mock_service import mock_ask

MODEL_NAME = "gemini-3.6-flash"
MAX_TOOL_ROUNDS = 5  # chặn vòng lặp vô hạn nếu model cứ liên tục gọi tool

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

_FUNCTION_DECLARATIONS = [types.FunctionDeclaration(**t) for t in TOOLS]
_TOOL = types.Tool(function_declarations=_FUNCTION_DECLARATIONS)


def _get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Chưa cấu hình GEMINI_API_KEY. Lấy key miễn phí tại "
            "https://aistudio.google.com/apikey rồi thêm dòng "
            "GEMINI_API_KEY=... vào file .env (xem .env.example)."
        )
    return genai.Client(api_key=api_key)


def ask_chatbot(db: Session, user_message: str, history: list[dict] | None = None) -> dict:
    """Gửi câu hỏi cho Gemini, để model tự gọi tool tra DB nếu cần, trả về
    câu trả lời cuối cùng + log các tool đã gọi (để debug/hiển thị minh bạch
    cho người dùng thấy chatbot lấy dữ liệu từ đâu ra).

    Tự động chuyển sang MOCK MODE (app/chatbot/mock_service.py — không gọi
    AI thật) trong 3 trường hợp — MỖI TRƯỜNG HỢP GẮN ĐÚNG 1 TIỀN TỐ RIÊNG
    BIỆT vào câu trả lời để người dùng tự chẩn đoán được ngay trong khung
    chat, không cần mò log Railway:
    1. Biến CHATBOT_MOCK đang bật (ép mock dù có key thật).
    2. Chưa cấu hình GEMINI_API_KEY (biến trống/chưa deploy lại).
    3. Có key nhưng gọi Gemini thật bị lỗi — bắt RỘNG theo
       google.genai.errors.APIError (lớp cha chung của ClientError [401
       sai key, 429 rate limit...] và ServerError [lỗi phía Google]) CỘNG
       THÊM 1 lớp Exception chung làm lưới an toàn cuối cùng cho lỗi mạng/
       lỗi không lường trước — không để bất kỳ lỗi nào làm crash 500 thẳng
       cho người dùng.
    """
    force_mock = os.getenv("CHATBOT_MOCK", "").lower() in ("1", "true", "yes")
    has_key = bool(os.getenv("GEMINI_API_KEY"))

    if force_mock:
        fallback = mock_ask(db, user_message, history)
        fallback["reply"] = (
            "[MOCK — biến CHATBOT_MOCK đang BẬT trên server, ép dùng mô phỏng dù "
            "có thể đã có GEMINI_API_KEY thật. Xoá biến CHATBOT_MOCK trên Railway "
            "nếu muốn dùng AI thật.]\n" + fallback["reply"]
        )
        return fallback

    if not has_key:
        fallback = mock_ask(db, user_message, history)
        fallback["reply"] = (
            "[MOCK — CHƯA CÓ biến GEMINI_API_KEY trên server (đọc ra rỗng). "
            "Kiểm tra lại: (1) đã thêm đúng tên biến GEMINI_API_KEY trên Railway "
            "chưa (phân biệt hoa/thường, không thừa khoảng trắng), (2) đã LƯU biến "
            "chưa, (3) Railway đã BUILD LẠI xong chưa (đổi biến môi trường luôn cần "
            "build lại mới có hiệu lực).]\n" + fallback["reply"]
        )
        return fallback

    try:
        return _ask_gemini_real(db, user_message, history)
    except genai_errors.APIError as e:
        code = getattr(e, "code", None)
        error_detail = f"{type(e).__name__}" + (f" (HTTP {code})" if code else "") + f": {e}"
        fallback = mock_ask(db, user_message, history)
        fallback["reply"] = f"[MOCK — gọi Gemini API thật thất bại: {error_detail}]\n" + fallback["reply"]
        return fallback
    except Exception as e:  # noqa: BLE001 — lưới an toàn cuối cùng: lỗi mạng/DNS/timeout
        # không được wrap thành genai_errors.APIError (vd httpx.ConnectError)
        # vẫn phải rớt êm về mock, KHÔNG được crash 500 cho người dùng.
        error_detail = f"{type(e).__name__}: {e}"
        fallback = mock_ask(db, user_message, history)
        fallback["reply"] = f"[MOCK — lỗi không lường trước khi gọi Gemini: {error_detail}]\n" + fallback["reply"]
        return fallback


def _ask_gemini_real(db: Session, user_message: str, history: list[dict] | None = None) -> dict:
    """Luồng gọi Gemini API thật + vòng lặp tool-use — tách riêng khỏi
    ask_chatbot() để hàm đó có thể bắt lỗi và fallback sang mock gọn hơn.

    "history"/"contents" dùng dict thuần dạng {"role": ..., "parts": [...]}
    (đúng ContentDict/PartDict mà SDK google-genai chấp nhận trực tiếp,
    KHÔNG cần dựng object types.Content — đã xác nhận qua test thật, không
    đoán) — để JSON-serialize được dễ dàng khi trả về/nhận lại từ client,
    giống hệt cách "history" hoạt động ở bản Claude cũ."""
    client = _get_client()
    contents: list[dict] = list(history or [])
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    tool_call_log: list[dict] = []
    config = types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, tools=[_TOOL])

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.models.generate_content(model=MODEL_NAME, contents=contents, config=config)

        function_calls = response.function_calls  # property tiện ích của SDK, rỗng nếu model trả lời thẳng
        if not function_calls:
            final_text = response.text or ""
            model_content = {"role": "model", "parts": [{"text": final_text}]}
            return {
                "reply": final_text,
                "tool_calls": tool_call_log,
                "messages": contents + [model_content],
            }

        # Model yêu cầu gọi 1 hoặc nhiều tool -> lưu đúng nguyên các
        # function_call model vừa trả về vào lịch sử, rồi chạy thật, gửi
        # kết quả lại dưới dạng function_response.
        model_call_parts = [{"function_call": {"name": fc.name, "args": dict(fc.args or {})}} for fc in function_calls]
        contents.append({"role": "model", "parts": model_call_parts})

        response_parts = []
        for fc in function_calls:
            func = TOOL_FUNCTIONS.get(fc.name)
            args = dict(fc.args or {})
            if func is None:
                result_content = {"error": f"Không có tool tên '{fc.name}'"}
            else:
                try:
                    result_content = func(db, **args)
                except Exception as e:  # noqa: BLE001 — muốn bắt mọi lỗi để trả về model, không crash request
                    result_content = {"error": str(e)}

            tool_call_log.append({"tool": fc.name, "input": args, "output": result_content})
            # function_response.response PHẢI là dict — bọc kết quả (có thể
            # là list, vd get_low_stock_products trả về list[dict]) vào 1
            # key "result" để luôn hợp lệ bất kể tool trả về kiểu dữ liệu gì.
            wrapped = result_content if isinstance(result_content, dict) else {"result": result_content}
            response_parts.append({"function_response": {"name": fc.name, "response": wrapped}})

        contents.append({"role": "user", "parts": response_parts})

    # Vượt quá số vòng cho phép — trả lời an toàn thay vì treo request
    return {
        "reply": "Xin lỗi, câu hỏi này cần tra cứu nhiều bước quá mức cho phép. Bạn thử hỏi cụ thể/ngắn gọn hơn nhé.",
        "tool_calls": tool_call_log,
        "messages": contents,
    }
