import { useEffect, useRef, useState } from "react";
import { api } from "../api";

// Chatbot AI — nối vào API /chatbot/ask ĐÃ CÓ SẴN trên backend từ trước (mục
// 6.6 đề cương, dùng Claude function-calling truy vấn DB thật). Trang này
// trước đây chỉ tồn tại ở bản demo desktop cũ (static/index.html), chưa
// từng được nối vào React PWA — đây là lần đầu có giao diện chat cho nó ở
// đây.
//
// LƯU Ý VỀ "history": backend tự quản lý định dạng lịch sử hội thoại nội bộ
// (khớp với Anthropic Messages API) — frontend chỉ cần GIỮ NGUYÊN state trả
// về từ mỗi lần gọi và gửi lại y hệt ở lần hỏi tiếp theo, KHÔNG cần hiểu/
// đụng vào cấu trúc bên trong. Danh sách hiển thị trên màn hình (messages)
// là state RIÊNG, tự xây dựng từ câu hỏi + câu trả lời mỗi lượt, độc lập
// với "history" gửi lên server.
const SUGGESTED_QUESTIONS = [
  "Sản phẩm nào sắp hết hàng?",
  "Lô hàng nào sắp hết hạn trong 30 ngày tới?",
  "Có bao nhiêu cảnh báo đang mở?",
];

export default function Chatbot() {
  const [messages, setMessages] = useState([]); // [{role: 'user'|'assistant', text}]
  const [history, setHistory] = useState(null); // trạng thái nội bộ backend, gửi lại nguyên vẹn
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const scrollRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  async function send(text) {
    const question = (text ?? input).trim();
    if (!question || sending) return;

    setMessages((prev) => [...prev, { role: "user", text: question }]);
    setInput("");
    setSending(true);
    setErrorMsg("");

    try {
      const res = await api.chatbotAsk(question, history);
      setMessages((prev) => [...prev, { role: "assistant", text: res.reply }]);
      setHistory(res.history);
    } catch (err) {
      setErrorMsg(err.message || String(err));
    } finally {
      setSending(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <main className="page-main chatbot-main">
      <div className="card chatbot-card">
        <h2>🤖 Trợ lý AI — tra cứu kho hàng</h2>

        <div className="chatbot-scroll">
          {messages.length === 0 && (
            <div className="chatbot-empty">
              <div style={{ fontSize: 32, marginBottom: 8 }}>👋</div>
              <div>Hỏi bất kỳ điều gì về tồn kho, cảnh báo, phiếu nhập…</div>
              <div className="chatbot-suggestions">
                {SUGGESTED_QUESTIONS.map((q) => (
                  <button key={q} className="chip" onClick={() => send(q)}>
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`chatbot-bubbleRow ${m.role}`}>
              <div className={`chatbot-bubble ${m.role}`}>{m.text}</div>
            </div>
          ))}

          {sending && (
            <div className="chatbot-bubbleRow assistant">
              <div className="chatbot-bubble assistant chatbot-thinking">
                <span className="chatbot-dot" />
                <span className="chatbot-dot" />
                <span className="chatbot-dot" />
              </div>
            </div>
          )}

          {errorMsg && (
            <div className="chatbot-bubbleRow assistant">
              <div className="chatbot-bubble assistant" style={{ color: "var(--danger)", borderColor: "var(--danger)" }}>
                ⚠ {errorMsg}
              </div>
            </div>
          )}

          <div ref={scrollRef} />
        </div>

        <div className="chatbot-inputRow">
          <textarea
            className="chatbot-input"
            placeholder="Nhập câu hỏi cho trợ lý"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
          />
          <button className="primary chatbot-sendBtn" onClick={() => send()} disabled={sending || !input.trim()}>
            Gửi
          </button>
        </div>
      </div>
    </main>
  );
}
