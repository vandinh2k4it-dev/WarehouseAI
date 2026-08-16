import { useState, useRef } from "react";
import { api } from "../api";

// Màn hình đếm dùng chung cho cả nhập và xuất — nhận session đã tạo sẵn
// (từ start-import hoặc start-export), cho nhân viên quay video, tự động
// upload + đếm + đối chiếu ngay khi chọn xong video.
//
// GHI CHÚ: dùng <input type="file" accept="video/*" capture="environment">
// thay vì getUserMedia + MediaRecorder tự ghép — cách này đơn giản hơn,
// đáng tin cậy hơn trên nhiều trình duyệt di động (đặc biệt Safari/Chrome
// iOS), và đã được test kỹ ở bản mobile.html trước khi chuyển sang PWA này.
export default function CountingScreen({ session, expectedQuantity, label, onDone, onCancel }) {
  const [status, setStatus] = useState("idle"); // idle | uploading | done | error
  const [result, setResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const inputRef = useRef(null);

  async function handleFileSelected(e) {
    const file = e.target.files?.[0];
    if (!file || !session) return;

    setStatus("uploading");
    setErrorMsg("");
    try {
      const res = await api.countVideo(session.id, file);
      setResult(res);
      setStatus("done");
    } catch (err) {
      setErrorMsg(err.message || String(err));
      setStatus("error");
    }
  }

  function retry() {
    setStatus("idle");
    setErrorMsg("");
    if (inputRef.current) inputRef.current.value = "";
  }

  const matched = result?.session?.status === "completed";

  return (
    <div className="countStage">
      <div className="countStage-target">
        Cần khớp <span className="mono">{expectedQuantity}</span>
      </div>
      <div className="countStage-name">{label}</div>

      {status === "idle" && (
        <>
          <label className="camBtn">
            🎥 Chạm để quay video đếm hàng
            <input
              ref={inputRef}
              type="file"
              accept="video/*"
              capture="environment"
              onChange={handleFileSelected}
              style={{ display: "none" }}
            />
          </label>
          <button className="ghost" onClick={onCancel}>
            Huỷ, quay lại danh sách
          </button>
        </>
      )}

      {status === "uploading" && (
        <>
          <div className="spinner" />
          <div className="empty">Đang tải video lên &amp; đếm — có thể mất chút thời gian…</div>
        </>
      )}

      {status === "error" && (
        <>
          <div className="empty" style={{ color: "var(--danger)" }}>
            Lỗi: {errorMsg}
          </div>
          <button className="ghost" onClick={retry}>
            Thử lại
          </button>
        </>
      )}

      {status === "done" && result && (
        <>
          <div className={`resultBox ${matched ? "ok" : "warn"}`}>
            <div className="resultBox-title">{matched ? "✅ Khớp" : "⚠️ Lệch — cần kiểm tra sau"}</div>
            <div className="resultBox-num mono">
              Camera đếm: {result.session.counted_quantity} / cần {expectedQuantity}
            </div>
            <div className="resultBox-msg">{result.message}</div>
          </div>
          <button className="primary" onClick={() => onDone(result)}>
            Xong — chọn loại tiếp theo
          </button>
        </>
      )}
    </div>
  );
}
