import { useEffect, useRef, useState } from "react";
import { api } from "../api";

// Chatbot AI — nối vào API /chatbot/ask ĐÃ CÓ SẴN trên backend (mục 6.6 đề
// cương, dùng Gemini function-calling truy vấn DB thật).
//
// LƯU LỊCH SỬ QUA localStorage: cả "messages" (hiển thị trên màn hình) lẫn
// "history" (trạng thái nội bộ backend cần gửi lại nguyên vẹn mỗi lượt hỏi
// tiếp theo) đều được lưu lại — tải lại trang / thoát vào lại KHÔNG mất
// cuộc hội thoại đang dở, khác với trước đây (chỉ tồn tại trong state React,
// mất ngay khi rời trang). Đây là localStorage của TRÌNH DUYỆT THẬT (ứng
// dụng web PWA đang chạy thật cho người dùng), khác với artifact demo trong
// khung chat — hoàn toàn hợp lệ để dùng ở đây.
const STORAGE_KEY_MESSAGES = "warehouse_chatbot_messages";
const STORAGE_KEY_HISTORY = "warehouse_chatbot_history";

const SUGGESTED_QUESTIONS = [
  "Sản phẩm nào sắp hết hàng?",
  "Lô hàng nào sắp hết hạn trong 30 ngày tới?",
  "Có bao nhiêu cảnh báo đang mở?",
];

function loadSavedMessages() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_MESSAGES);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return []; // dữ liệu cũ hỏng/không đọc được -> coi như chưa có gì, không crash cả trang
  }
}

function loadSavedHistory() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_HISTORY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export default function Chatbot() {
  const [messages, setMessages] = useState(loadSavedMessages); // [{role: 'user'|'assistant', text}]
  const [history, setHistory] = useState(loadSavedHistory); // trạng thái nội bộ backend, gửi lại nguyên vẹn
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const scrollRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  // Lưu lại MỖI KHI messages/history đổi — không cần nút "Lưu" riêng, tự
  // động lưu ngay sau mỗi câu hỏi/trả lời.
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY_MESSAGES, JSON.stringify(messages));
  }, [messages]);

  useEffect(() => {
    if (history != null) {
      localStorage.setItem(STORAGE_KEY_HISTORY, JSON.stringify(history));
    }
  }, [history]);

  function clearHistory() {
    if (!window.confirm("Xoá toàn bộ lịch sử trò chuyện? Không thể hoàn tác.")) return;
    setMessages([]);
    setHistory(null);
    localStorage.removeItem(STORAGE_KEY_MESSAGES);
    localStorage.removeItem(STORAGE_KEY_HISTORY);
  }

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
        <div className="card-headRow" style={{ marginBottom: 0 }}>
          <h2 style={{ margin: 0 }}>🤖 Trợ lý AI — tra cứu kho hàng</h2>
          {messages.length > 0 && (
            <button className="ghost lineCard-smallBtn" onClick={clearHistory}>
              Xoá lịch sử
            </button>
          )}
        </div>

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
