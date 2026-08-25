// Hộp xác nhận dùng chung — hiện trước các hành động quan trọng/không
// thể hoàn tác (vd: ghi đè số liệu, xoá dữ liệu) thay vì làm ngay lập tức
// không hỏi lại.
//
// CÁCH DÙNG:
//   import { useState } from "react";
//   import ConfirmDialog from "../components/ConfirmDialog";
//
//   const [confirmOpen, setConfirmOpen] = useState(false);
//
//   <button onClick={() => setConfirmOpen(true)}>Xoá</button>
//   <ConfirmDialog
//     open={confirmOpen}
//     title="Xác nhận xoá"
//     message="Hành động này không thể hoàn tác. Bạn chắc chắn muốn xoá?"
//     danger
//     onConfirm={() => { doDelete(); setConfirmOpen(false); }}
//     onCancel={() => setConfirmOpen(false)}
//   />
export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Xác nhận",
  cancelLabel = "Huỷ",
  danger = false,
  onConfirm,
  onCancel,
}) {
  if (!open) return null;

  return (
    <div className="confirmOverlay" onClick={onCancel}>
      <div className="confirmBox" onClick={(e) => e.stopPropagation()}>
        {title && <div className="confirmBox-title">{title}</div>}
        <div className="confirmBox-msg">{message}</div>
        <div className="confirmBox-actions">
          <button className="ghost" onClick={onCancel} style={{ marginTop: 0 }}>
            {cancelLabel}
          </button>
          <button
            className={danger ? "dangerBtn" : "primary"}
            onClick={onConfirm}
            style={danger ? {} : { marginTop: 0 }}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
