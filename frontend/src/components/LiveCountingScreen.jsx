import { useEffect, useRef, useState } from "react";
import { API_BASE, api } from "../api";

// Đếm TRỰC TIẾP — khác hẳn "Quay video" (quay xong mới gửi 1 lần): ở đây
// liên tục chụp từng khung hình từ camera (mỗi ~700ms), gửi lên backend,
// nhận về toạ độ khung hộp + số đếm luỹ kế, VẼ ĐÈ khung hộp lên video ngay
// lập tức — giống hệt hiệu ứng "camera detection" thường thấy.
//
// GHI CHÚ QUAN TRỌNG: mỗi khung hình là 1 lần gọi API riêng (không phải
// streaming 2 chiều liên tục qua WebSocket) — đơn giản hơn nhiều để làm
// đúng và dễ debug, đánh đổi lại là có độ trễ ~0.5-1s giữa lúc thùng đi
// qua và lúc khung hộp hiện lên, không phải tức thời 100%. Với tốc độ băng
// chuyền thông thường, độ trễ này chấp nhận được.
export default function LiveCountingScreen({ session, expectedQuantity, label, onDone, onCancel }) {
  const videoRef = useRef(null);
  const overlayRef = useRef(null);
  const captureCanvasRef = useRef(null);
  const streamRef = useRef(null);
  const intervalRef = useRef(null);
  const sendingRef = useRef(false); // tránh gửi chồng khung khi khung trước chưa xử lý xong

  const [count, setCount] = useState(0);
  const [status, setStatus] = useState("starting"); // starting | live | error | finishing
  const [errorMsg, setErrorMsg] = useState("");
  const [boxCount, setBoxCount] = useState(0); // số khung hộp đang thấy ở khung hình hiện tại
  const [frameErrorMsg, setFrameErrorMsg] = useState(""); // lỗi từ /live-frame (khác lỗi mở camera)
  const consecutiveFailsRef = useRef(0);
  const [conf, setConf] = useState(0.35); // độ nhạy phát hiện — thấp hơn = bắt được nhiều thùng hơn nhưng dễ nhận nhầm vật khác
  const confRef = useRef(conf); // setInterval đóng gói giá trị lúc khởi tạo — dùng ref để luôn đọc đúng giá trị MỚI NHẤT của thanh trượt, không bị "đông cứng" giá trị cũ
  confRef.current = conf;

  useEffect(() => {
    startCamera();
    return () => stopCamera();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function startCamera() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment", width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setStatus("live");
      intervalRef.current = setInterval(captureAndSend, 700);
    } catch (err) {
      setErrorMsg(
        err.name === "NotAllowedError" || err.name === "PermissionDeniedError"
          ? "Bạn chưa cho phép truy cập camera — vào cài đặt trình duyệt để bật lại quyền camera cho trang này."
          : err.message || String(err)
      );
      setStatus("error");
    }
  }

  function stopCamera() {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
  }

  function captureAndSend() {
    if (sendingRef.current) return; // khung trước chưa xong -> bỏ qua khung này, đợi khung kế tiếp
    const video = videoRef.current;
    const capture = captureCanvasRef.current;
    if (!video || !capture || !video.videoWidth) return;

    if (capture.width !== video.videoWidth) {
      capture.width = video.videoWidth;
      capture.height = video.videoHeight;
    }
    capture.getContext("2d").drawImage(video, 0, 0, capture.width, capture.height);

    sendingRef.current = true;
    capture.toBlob(
      async (blob) => {
        if (!blob) {
          sendingRef.current = false;
          return;
        }
        try {
          const form = new FormData();
          form.append("file", blob, "frame.jpg");
          const res = await fetch(`${API_BASE}/camera-sessions/${session.id}/live-frame?conf=${confRef.current}`, {
            method: "POST",
            body: form,
          });
          if (res.ok) {
            const data = await res.json();
            consecutiveFailsRef.current = 0;
            setFrameErrorMsg("");
            setCount(data.count);
            setBoxCount(data.boxes.length);
            drawBoxes(data);
          } else {
            // QUAN TRỌNG: trước đây lỗi từng khung bị bỏ qua ÂM THẦM hoàn
            // toàn — hậu quả là nếu MỌI khung đều lỗi (vd sai đường dẫn
            // model, model chưa load được), người dùng chỉ thấy số đếm
            // đứng yên ở 0 mãi mà KHÔNG BIẾT vì sao, tưởng nhầm là model
            // không nhận diện được gì trong khi thật ra server đang lỗi.
            // Giờ: sau 3 lần lỗi liên tiếp mới hiện cảnh báo (bỏ qua lỗi
            // đơn lẻ thoáng qua do mạng chập chờn), kèm ĐÚNG nội dung lỗi
            // thật từ backend để biết chính xác nguyên nhân.
            consecutiveFailsRef.current += 1;
            if (consecutiveFailsRef.current >= 3) {
              let detail = `Lỗi ${res.status}`;
              try {
                detail = (await res.json()).detail || detail;
              } catch {
                // ignore
              }
              setFrameErrorMsg(detail);
            }
          }
        } catch (err) {
          consecutiveFailsRef.current += 1;
          if (consecutiveFailsRef.current >= 3) {
            setFrameErrorMsg("Mất kết nối tới server: " + (err.message || String(err)));
          }
        } finally {
          sendingRef.current = false;
        }
      },
      "image/jpeg",
      0.7
    );
  }

  function drawBoxes(data) {
    const overlay = overlayRef.current;
    if (!overlay) return;
    if (overlay.width !== data.frame_width || overlay.height !== data.frame_height) {
      overlay.width = data.frame_width;
      overlay.height = data.frame_height;
    }
    const ctx = overlay.getContext("2d");
    ctx.clearRect(0, 0, overlay.width, overlay.height);
    ctx.strokeStyle = "#F5A524";
    ctx.lineWidth = Math.max(3, overlay.width / 260);
    ctx.font = `${Math.max(18, Math.round(overlay.width / 35))}px sans-serif`;
    ctx.fillStyle = "#F5A524";
    for (const box of data.boxes) {
      ctx.strokeRect(box.x1, box.y1, box.x2 - box.x1, box.y2 - box.y1);
      const labelY = box.y1 > 24 ? box.y1 - 8 : box.y1 + 20;
      ctx.fillText(`#${box.track_id}`, box.x1 + 4, labelY);
    }
  }

  async function finish() {
    setStatus("finishing");
    stopCamera();
    try {
      const result = await api.stopManualCount(session.id, count);
      onDone(result);
    } catch (err) {
      setErrorMsg(err.message || String(err));
      setStatus("error");
    }
  }

  function cancel() {
    stopCamera();
    onCancel();
  }

  return (
    <div className="liveStage">
      <div className="countStage-target">
        Cần khớp <span className="mono">{expectedQuantity}</span>
      </div>
      <div className="countStage-name">{label}</div>

      {status === "error" && (
        <div className="empty" style={{ color: "var(--danger)", marginBottom: 10 }}>
          {errorMsg}
        </div>
      )}

      <div className="liveVideo-wrap" style={{ display: status === "error" ? "none" : "block" }}>
        <video ref={videoRef} className="liveVideo" muted playsInline autoPlay />
        <canvas ref={overlayRef} className="liveOverlay" />
        <div className="liveCount-badge">
          <span className="mono">{count}</span>
          {boxCount > 0 && <span className="liveCount-sub">{boxCount} đang thấy</span>}
        </div>
        {frameErrorMsg && (
          <div className="liveFrame-error">
            ⚠ Server lỗi khi xử lý khung hình: {frameErrorMsg}
          </div>
        )}
        {status === "starting" && (
          <div className="liveVideo-loading">
            <div className="spinner" />
            <div>Đang mở camera…</div>
          </div>
        )}
      </div>
      <canvas ref={captureCanvasRef} style={{ display: "none" }} />

      {(status === "live" || status === "finishing") && (
        <div className="confSlider">
          <div className="confSlider-row">
            <span>Độ nhạy phát hiện</span>
            <span className="mono">{conf.toFixed(2)}</span>
          </div>
          <input
            type="range"
            min="0.15"
            max="0.7"
            step="0.05"
            value={conf}
            onChange={(e) => setConf(parseFloat(e.target.value))}
          />
          <div className="confSlider-hint">
            Kéo trái nếu model đang BỎ SÓT nhiều thùng (nhận diện được ít hơn thực tế) — kéo phải nếu
            đang NHẬN NHẦM vật khác thành thùng.
          </div>
        </div>
      )}

      {(status === "live" || status === "finishing") && (
        <>
          <button className="primary" disabled={status === "finishing"} onClick={finish}>
            {status === "finishing" ? "Đang gửi kết quả…" : `Xong — đã đếm ${count}`}
          </button>
          <button className="ghost" disabled={status === "finishing"} onClick={cancel}>
            Huỷ, quay lại danh sách
          </button>
        </>
      )}
      {status === "error" && (
        <button className="ghost" onClick={cancel}>
          Quay lại danh sách
        </button>
      )}
    </div>
  );
}
