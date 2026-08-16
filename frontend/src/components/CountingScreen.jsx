import { useState, useRef } from "react";
import { api } from "../api";

// Màn hình đếm dùng chung cho cả nhập và xuất — nhận session đã tạo sẵn
// (từ start-import hoặc start-export). Có 2 cách đối chiếu:
// (1) Quay video — backend tự đếm bằng YOLOv8+ByteTrack (chính xác hơn,
//     phù hợp số lượng nhiều/khó đếm tay).
// (2) Nhập tay — gõ thẳng số đã đếm được, dùng khi số lượng ít, không
//     đáng để quay video (nhanh hơn nhiều cho vài thùng lẻ).
//
// GHI CHÚ quay video: dùng <input type="file" accept="video/*"
// capture="environment"> thay vì getUserMedia + MediaRecorder tự ghép —
// cách này đơn giản hơn, đáng tin cậy hơn trên nhiều trình duyệt di động
// (đặc biệt Safari/Chrome iOS), đã test kỹ ở bản mobile.html trước đó.
export default function CountingScreen({ session, expectedQuantity, label, onDone, onCancel }) {
  const [mode, setMode] = useState("video"); // video | manual
  const [status, setStatus] = useState("idle"); // idle | uploading | done | error
  const [manualQty, setManualQty] = useState("");
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

  async function submitManual() {
    const qty = parseInt(manualQty, 10);
    if (Number.isNaN(qty) || qty < 0) {
      setErrorMsg("Nhập đúng số lượng đã đếm được (số nguyên, từ 0 trở lên)");
      setStatus("error");
      return;
    }
    setStatus("uploading");
    setErrorMsg("");
    try {
      const res = await api.stopManualCount(session.id, qty);
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
          <div className="chips" style={{ justifyContent: "center" }}>
            <button className={`chip${mode === "video" ? " active" : ""}`} onClick={() => setMode("video")}>
              🎥 Quay video
            </button>
            <button className={`chip${mode === "manual" ? " active" : ""}`} onClick={() => setMode("manual")}>
              ✍️ Nhập tay
            </button>
          </div>

          {mode === "video" ? (
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
          ) : (
            <>
              <input
                type="number"
                inputMode="numeric"
                placeholder="Số lượng đã đếm được"
                value={manualQty}
                onChange={(e) => setManualQty(e.target.value)}
                autoFocus
              />
              <button className="primary" onClick={submitManual}>
                Xác nhận số đã đếm
              </button>
            </>
          )}

          <button className="ghost" onClick={onCancel}>
            Huỷ, quay lại danh sách
          </button>
        </>
      )}

      {status === "uploading" && (
        <>
          <div className="spinner" />
          <div className="empty">
            {mode === "video"
              ? "Đang tải video lên & đếm — có thể mất chút thời gian…"
              : "Đang gửi & đối chiếu…"}
          </div>
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
              Đã đếm: {result.session.counted_quantity} / cần {expectedQuantity}
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
