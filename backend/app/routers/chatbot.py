from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas
from app.chatbot.service import ask_chatbot

router = APIRouter(prefix="/chatbot", tags=["chatbot"])


@router.post("/ask", response_model=schemas.ChatbotAnswer)
def chatbot_ask(payload: schemas.ChatbotAsk, db: Session = Depends(get_db)):
    """Chatbot tra cứu kho hàng (mục 6.6) — Claude tự gọi tool để lấy dữ
    liệu THẬT từ Postgres (tồn kho, phiếu nhập, cảnh báo...) rồi trả lời.
    Gửi kèm `history` (lấy từ response trước) để chatbot nhớ ngữ cảnh hội
    thoại trong cùng phiên chat."""
    try:
        result = ask_chatbot(db, payload.message, payload.history)
    except RuntimeError as e:
        # Thiếu ANTHROPIC_API_KEY hoặc lỗi cấu hình — trả 400 rõ ràng thay vì 500 mù mờ
        raise HTTPException(status_code=400, detail=str(e))

    return schemas.ChatbotAnswer(
        reply=result["reply"],
        tool_calls=[schemas.ChatbotToolCall(**tc) for tc in result["tool_calls"]],
        history=result["messages"],
    )
