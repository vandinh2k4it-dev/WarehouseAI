import { useState, useRef } from "react";
import { api } from "../api";
import LiveCountingScreen from "./LiveCountingScreen";

// Màn hình đếm dùng chung cho cả nhập và xuất — nhận session đã tạo sẵn
// (từ start-import hoặc start-export). Có 3 cách đối chiếu:
// (1) Trực tiếp — mở thẳng camera, vẽ khung hộp nhận diện đè lên video theo
//     thời gian thực, số đếm tăng dần ngay khi thấy (LiveCountingScreen.jsx).
// (2) Quay video — quay xong mới gửi lên 1 lần, backend xử lý xong mới ra
//     số (không có phản hồi trực quan lúc quay, nhưng đáng tin cậy hơn nếu
//     mạng yếu vì chỉ cần gửi đúng 1 lần).
// (3) Nhập tay — gõ thẳng số đã đếm được, dùng khi số lượng ít.
export default function CountingScreen({ session, expectedQuantity, label, onDone, onCancel }) {
  const [mode, setMode] = useState("live"); // live | video | manual
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

  function handleLiveDone(liveResult) {
    setResult(liveResult);
    setStatus("done");
  }

  const matched = result?.session?.status === "completed";

  // Chế độ Trực tiếp có màn hình riêng hoàn toàn (video + overlay full màn
  // hình) — chỉ hiện khi đang ở bước chọn/đang đếm, chuyển sang khối kết
  // quả chung phía dưới khi xong (dùng chung UI kết quả với 2 chế độ kia).
  if (mode === "live" && status === "idle") {
    return (
      <div className="countStage">
        <div className="chips" style={{ justifyContent: "center" }}>
          <button className="chip active">🔴 Trực tiếp</button>
          <button className="chip" onClick={() => setMode("video")}>
            🎥 Quay video
          </button>
          <button className="chip" onClick={() => setMode("manual")}>
            ✍️ Nhập tay
          </button>
        </div>
        <LiveCountingScreen
          session={session}
          expectedQuantity={expectedQuantity}
          label={label}
          onCancel={onCancel}
          onDone={handleLiveDone}
        />
      </div>
    );
  }

  return (
    <div className="countStage">
      <div className="countStage-target">
        Cần khớp <span className="mono">{expectedQuantity}</span>
      </div>
      <div className="countStage-name">{label}</div>

      {status === "idle" && (
        <>
          <div className="chips" style={{ justifyContent: "center" }}>
            <button className={`chip${mode === "live" ? " active" : ""}`} onClick={() => setMode("live")}>
              🔴 Trực tiếp
            </button>
            <button className={`chip${mode === "video" ? " active" : ""}`} onClick={() => setMode("video")}>
              🎥 Quay video
            </button>
            <button className={`chip${mode === "manual" ? " active" : ""}`} onClick={() => setMode("manual")}>
              ✍️ Nhập tay
            </button>
          </div>

          {mode === "video" ? (
            <div className="scanBtnRow">
              <label className="camBtn">
                🎥 Quay video mới
                <input
                  type="file"
                  accept="video/*"
                  capture="environment"
                  onChange={handleFileSelected}
                  style={{ display: "none" }}
                />
              </label>
              <label className="camBtn secondary">
                📁 Chọn video có sẵn
                <input
                  ref={inputRef}
                  type="file"
                  accept="video/*"
                  onChange={handleFileSelected}
                  style={{ display: "none" }}
                />
              </label>
            </div>
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
