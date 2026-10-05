import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import Markdown from "../components/Markdown";
import "../styles/chat.css";

// Chatbot AI — nối vào API /chatbot/ask ĐÃ CÓ SẴN trên backend (mục 6.6 đề
// cương, dùng Gemini function-calling truy vấn DB thật).
//
// LƯU LỊCH SỬ QUA localStorage: cả "messages" (hiển thị trên màn hình) lẫn
// "history" (trạng thái nội bộ backend cần gửi lại nguyên vẹn mỗi lượt hỏi
// tiếp theo) đều được lưu lại — tải lại trang / thoát vào lại KHÔNG mất
// cuộc hội thoại đang dở.
const STORAGE_KEY_MESSAGES = "warehouse_chatbot_messages";
const STORAGE_KEY_HISTORY = "warehouse_chatbot_history";

// Gợi ý theo nhóm — đều là câu chatbot THỰC SỰ trả lời được (đã có công cụ tương ứng ở backend).
const SUGGESTION_GROUPS = [
  { icon: "📦", title: "Tồn kho", questions: ["Sản phẩm nào sắp hết hàng?", "Cần nhập thêm mặt hàng nào?"] },
  { icon: "⏰", title: "Hạn sử dụng", questions: ["Lô nào sắp hết hạn trong 30 ngày tới?", "Hàng nào hết hạn trong 7 ngày tới?"] },
  { icon: "⚖️", title: "Chênh lệch", questions: ["Có phiếu nào bị lệch số lượng không?", "Cho tôi 5 lần đối chiếu lệch gần đây nhất"] },
  { icon: "🔔", title: "Cảnh báo", questions: ["Có bao nhiêu cảnh báo đang mở?", "Có bao nhiêu cảnh báo chia theo từng loại?"] },
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

// Trả lời bắt đầu bằng "MOCK" nghĩa là chatbot đang ở CHẾ ĐỘ MÔ PHỎNG (Gemini không dùng được: hết hạn
// mức, thiếu key…) — đánh dấu rõ cho người dùng khỏi nhầm đây là câu trả lời của AI thật.
const isMockReply = (text) => /^\s*\[?MOCK\b/i.test(text || "");

// Trên điện thoại/máy cảm ứng, phím Enter nên XUỐNG DÒNG (không có Shift để xuống dòng) và gửi bằng nút Gửi.
const isTouchDevice = () => typeof window !== "undefined" && window.matchMedia?.("(pointer: coarse)").matches;

export default function Chatbot() {
  const [messages, setMessages] = useState(loadSavedMessages); // [{role: 'user'|'assistant', text}]
  const [history, setHistory] = useState(loadSavedHistory); // trạng thái nội bộ backend, gửi lại nguyên vẹn
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const listRef = useRef(null);
  const inputRef = useRef(null);
  const lastQuestionRef = useRef("");

  // Trang chat chiếm TRỌN màn hình (không có đệm cuối trang) — chat.css dùng class này trên <body>.
  useEffect(() => {
    document.body.classList.add("is-chat-page");
    return () => document.body.classList.remove("is-chat-page");
  }, []);

  // Tự cuộn xuống cuối khi có tin mới — cuộn ngay trong khung tin nhắn (không cuộn cả trang).
  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages, sending, errorMsg]);

  // Ô nhập tự giãn theo số dòng (tối đa ~5 dòng rồi mới cuộn bên trong).
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`;
  }, [input]);

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
    setErrorMsg("");
    localStorage.removeItem(STORAGE_KEY_MESSAGES);
    localStorage.removeItem(STORAGE_KEY_HISTORY);
  }

  async function ask(question, { addUser = true } = {}) {
    if (addUser) setMessages((prev) => [...prev, { role: "user", text: question }]);
    lastQuestionRef.current = question;
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
      if (!isTouchDevice()) inputRef.current?.focus();
    }
  }

  function send(text) {
    const question = (text ?? input).trim();
    if (!question || sending) return;
    setInput("");
    ask(question);
  }

  // Thử lại câu vừa lỗi — KHÔNG thêm lại tin nhắn của người dùng (đã có trên màn hình).
  function retry() {
    if (lastQuestionRef.current && !sending) ask(lastQuestionRef.current, { addUser: false });
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey && !isTouchDevice()) {
      e.preventDefault();
      send();
    }
  }

  return (
    <main className="page-main chatPage">
      <div className="chatShell">
        <header className="chatHeader">
          <div className="chatHeader-avatar" aria-hidden="true">
            🤖
          </div>
          <div className="chatHeader-text">
            <h1 className="chatHeader-title">Trợ lý AI</h1>
            <div className="chatHeader-sub">Tra cứu kho hàng bằng tiếng Việt</div>
          </div>
          {messages.length > 0 && (
            <button className="ghost chatClearBtn" onClick={clearHistory}>
              🗑 Xoá lịch sử
            </button>
          )}
        </header>

        <div className="chatMessages" ref={listRef}>
          <div className="chatCol">
            {messages.length === 0 && (
              <div className="chatEmpty">
                <div className="chatEmpty-icon">👋</div>
                <div className="chatEmpty-title">Xin chào! Mình giúp gì cho bạn?</div>
                <div className="chatEmpty-sub">Hỏi về tồn kho, hạn sử dụng, chênh lệch, cảnh báo… Bấm một gợi ý bên dưới hoặc tự gõ câu hỏi.</div>
                <div className="chatSuggestGrid">
                  {SUGGESTION_GROUPS.map((g) => (
                    <div className="chatSuggestGroup" key={g.title}>
                      <div className="chatSuggestGroup-title">
                        {g.icon} {g.title}
                      </div>
                      {g.questions.map((q) => (
                        <button key={q} className="chatSuggestBtn" onClick={() => send(q)}>
                          {q}
                        </button>
                      ))}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m, i) =>
              m.role === "user" ? (
                <div key={i} className="chatRow user">
                  <div className="chatBubble user">{m.text}</div>
                </div>
              ) : (
                <div key={i} className="chatRow assistant">
                  <div className="chatAvatar" aria-hidden="true">
                    🤖
                  </div>
                  <div className={`chatBubble assistant${isMockReply(m.text) ? " mock" : ""}`}>
                    {isMockReply(m.text) && <div className="chatMockTag">⚠ Chế độ mô phỏng — Gemini đang không dùng được</div>}
                    <Markdown text={m.text} />
                  </div>
                </div>
              )
            )}

            {sending && (
              <div className="chatRow assistant">
                <div className="chatAvatar" aria-hidden="true">
                  🤖
                </div>
                <div className="chatBubble assistant chatThinking" role="status" aria-label="Trợ lý đang trả lời">
                  <span className="chatDot" />
                  <span className="chatDot" />
                  <span className="chatDot" />
                </div>
              </div>
            )}

            {errorMsg && (
              <div className="chatRow assistant">
                <div className="chatAvatar" aria-hidden="true">
                  ⚠️
                </div>
                <div className="chatBubble assistant chatError">
                  <div>{errorMsg}</div>
                  <button className="ghost chatRetryBtn" onClick={retry} disabled={sending}>
                    ↻ Thử lại
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="chatComposer">
          <div className="chatComposer-inner">
            <textarea
              ref={inputRef}
              className="chatInput"
              placeholder="Nhập câu hỏi cho trợ lý…"
              aria-label="Câu hỏi cho trợ lý"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
            />
            <button className="primary chatSendBtn" onClick={() => send()} disabled={sending || !input.trim()} aria-label="Gửi">
              Gửi ➤
            </button>
          </div>
          <div className="chatComposer-hint">Enter để gửi · Shift+Enter xuống dòng</div>
        </div>
      </div>
    </main>
  );
}
