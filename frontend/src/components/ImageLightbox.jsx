import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import "../styles/listing.css";

// Khung xem ảnh phóng to NGAY TRONG TRANG (thay cho việc mở ảnh ở tab mới).
// - Bấm ✕, bấm vùng nền tối bên ngoài, hoặc nhấn Esc để thoát.
// - Bấm vào ảnh (hoặc nút "Phóng to") để phóng to xem chữ nhỏ, bấm lần nữa để thu lại.
// - Khoá cuộn trang nền khi đang mở, trả lại vị trí focus cũ khi đóng, Tab chỉ
//   xoay vòng trong khung (dùng được bằng bàn phím).
export default function ImageLightbox({ src, title, subtitle, onClose }) {
  const [zoomed, setZoomed] = useState(false);
  const [status, setStatus] = useState("loading"); // loading | ok | error
  const dialogRef = useRef(null);
  const closeRef = useRef(null);
  const onCloseRef = useRef(onClose);

  // Luôn gọi bản onClose mới nhất mà không phải đăng ký lại sự kiện bàn phím mỗi lần render.
  useEffect(() => {
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    const prevFocus = document.activeElement;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();

    function onKey(e) {
      if (e.key === "Escape") {
        e.stopPropagation();
        onCloseRef.current();
      } else if (e.key === "Tab" && dialogRef.current) {
        const items = dialogRef.current.querySelectorAll("button");
        if (items.length === 0) return;
        const first = items[0];
        const last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
      if (prevFocus && prevFocus.focus) prevFocus.focus();
    };
  }, []);

  return createPortal(
    <div
      className="lightbox"
      role="dialog"
      aria-modal="true"
      aria-label={title || "Xem ảnh"}
      ref={dialogRef}
      onClick={() => onClose()}
    >
      <div className="lightbox-bar" onClick={(e) => e.stopPropagation()}>
        <div className="lightbox-title">
          {title}
          {subtitle && <small>{subtitle}</small>}
        </div>
        <div className="lightbox-actions">
          <button type="button" className="lightbox-btn" onClick={() => setZoomed((z) => !z)}>
            {zoomed ? "🔍 Thu nhỏ" : "🔍 Phóng to"}
          </button>
          <button type="button" className="lightbox-close" aria-label="Đóng" ref={closeRef} onClick={() => onClose()}>
            ✕
          </button>
        </div>
      </div>

      <div className="lightbox-stage">
        {status === "loading" && <div className="lightbox-msg">Đang tải ảnh…</div>}
        {status === "error" && <div className="lightbox-msg">Không tải được ảnh phiếu.</div>}
        <img
          src={src}
          alt={title || "Ảnh phiếu"}
          className={`lightbox-img${zoomed ? " zoomed" : ""}`}
          style={{ display: status === "error" ? "none" : undefined, opacity: status === "ok" ? 1 : 0 }}
          onLoad={() => setStatus("ok")}
          onError={() => setStatus("error")}
          onClick={(e) => {
            e.stopPropagation();
            setZoomed((z) => !z);
          }}
        />
      </div>
    </div>,
    document.body
  );
}
