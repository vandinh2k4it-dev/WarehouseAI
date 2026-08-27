import { useEffect, useState } from "react";
import { api } from "../api";

// Phiếu xuất kho — hiện dạng modal, có nút "In phiếu" gọi window.print().
// CSS in (@media print, xem src/styles/app.css) tự ẩn toàn bộ giao diện
// app, chỉ in đúng nội dung phiếu — không cần thư viện tạo PDF riêng, dùng
// đúng tính năng in có sẵn của trình duyệt/điện thoại.
export default function PrintExportReceipt({ session, productLabel, expectedQuantity, onClose }) {
  const [details, setDetails] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    // Mọi lượt xuất qua màn hình đếm (dù đếm bằng video/trực tiếp/nhập tay)
    // đều đi qua luồng camera-session -> perform_fefo_export với
    // reference_type="camera_session", reference_id=session.id — xem
    // app/routers/camera.py. Lọc lại đúng dữ liệu này để biết CHÍNH XÁC
    // đã trừ những lô nào, bao nhiêu mỗi lô — không đoán/tính lại.
    api
      .getExportDetailsByReference("camera_session", session.id)
      .then(setDetails)
      .catch((err) => setErrorMsg(err.message || String(err)));
  }, [session.id]);

  const now = new Date();
  const totalQuantity = details?.reduce((s, d) => s + d.quantity, 0) ?? null;

  return (
    <div className="printReceipt-overlay" onClick={onClose}>
      <div className="printReceipt-box" onClick={(e) => e.stopPropagation()}>
        <div className="printReceipt-toolbar noPrint">
          <button className="ghost" onClick={onClose}>
            Đóng
          </button>
          <button className="primary" onClick={() => window.print()} disabled={!details}>
            🖨️ In phiếu
          </button>
        </div>

        <div className="printReceipt-content">
          <div className="printReceipt-header">
            <div>
              <div className="printReceipt-company">KHO HÀNG WAREHOUSE</div>
              <div className="printReceipt-sub">Địa chỉ: ................................................</div>
            </div>
            <div className="printReceipt-title">
              <div>PHIẾU XUẤT KHO</div>
              <div className="printReceipt-sub">
                Ngày {now.getDate()} tháng {now.getMonth() + 1} năm {now.getFullYear()}
              </div>
            </div>
          </div>

          <div className="printReceipt-meta">
            <div>
              Số phiên đếm: <b className="mono">#{session.id}</b>
            </div>
            <div>
              Người nhận hàng: <span className="printReceipt-blank">.............................</span>
            </div>
          </div>

          {errorMsg && <div className="empty" style={{ color: "var(--danger)" }}>{errorMsg}</div>}
          {!details && !errorMsg && <div className="empty noPrint">Đang tải chi tiết...</div>}

          {details && (
            <table className="printReceipt-table">
              <thead>
                <tr>
                  <th>STT</th>
                  <th>Tên sản phẩm</th>
                  <th>Mã lô</th>
                  <th>Số lượng</th>
                  <th>Đơn vị</th>
                </tr>
              </thead>
              <tbody>
                {details.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="text-muted">
                      {productLabel} — {expectedQuantity} (chưa có chi tiết theo lô)
                    </td>
                  </tr>
                ) : (
                  details.map((d, i) => (
                    <tr key={d.id}>
                      <td>{i + 1}</td>
                      <td>{d.product_name}</td>
                      <td className="mono">{d.batch_code}</td>
                      <td className="mono">{d.quantity.toLocaleString("vi-VN")}</td>
                      <td>{d.unit}</td>
                    </tr>
                  ))
                )}
              </tbody>
              {totalQuantity != null && (
                <tfoot>
                  <tr>
                    <td colSpan={3} style={{ textAlign: "right", fontWeight: 700 }}>
                      Tổng cộng
                    </td>
                    <td className="mono" style={{ fontWeight: 700 }}>
                      {totalQuantity.toLocaleString("vi-VN")}
                    </td>
                    <td></td>
                  </tr>
                </tfoot>
              )}
            </table>
          )}

          <div className="printReceipt-signatures">
            <div>
              <div className="printReceipt-sigTitle">Người lập phiếu</div>
              <div className="printReceipt-sigHint">(Ký, họ tên)</div>
            </div>
            <div>
              <div className="printReceipt-sigTitle">Thủ kho</div>
              <div className="printReceipt-sigHint">(Ký, họ tên)</div>
            </div>
            <div>
              <div className="printReceipt-sigTitle">Người nhận hàng</div>
              <div className="printReceipt-sigHint">(Ký, họ tên)</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
