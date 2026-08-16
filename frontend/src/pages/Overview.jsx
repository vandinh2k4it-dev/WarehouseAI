import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

const ALERT_TYPE_LABEL = {
  discrepancy: "Chênh lệch",
  low_stock: "Sắp hết hàng",
  expiring_soon: "Sắp hết hạn",
};

const RECEIPT_STATUS_LABEL = {
  pending_ocr: "đang xử lý OCR",
  ocr_done: "chờ đếm hàng",
  reconciled: "đã xong hết",
};
const RECEIPT_STATUS_BADGE = {
  pending_ocr: "counting",
  ocr_done: "not_started",
  reconciled: "matched",
};

export default function Overview() {
  const [products, setProducts] = useState(null);
  const [inventory, setInventory] = useState(null);
  const [alerts, setAlerts] = useState(null);
  const [receipts, setReceipts] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [ackBusy, setAckBusy] = useState(null);

  useEffect(() => {
    loadAll();
  }, []);

  async function loadAll() {
    setErrorMsg("");
    try {
      const [p, inv, al, rc] = await Promise.all([
        api.listProducts(),
        api.listInventory(),
        api.listAlerts("open"),
        api.listReceipts(),
      ]);
      setProducts(p);
      setInventory(inv);
      setAlerts(al);
      setReceipts(rc);
    } catch (err) {
      setErrorMsg(err.message || String(err));
    }
  }

  async function handleAck(alertId) {
    setAckBusy(alertId);
    try {
      await api.acknowledgeAlert(alertId);
      setAlerts((prev) => prev.filter((a) => a.id !== alertId));
    } catch (err) {
      setErrorMsg(err.message || String(err));
    } finally {
      setAckBusy(null);
    }
  }

  const totalProducts = products?.length ?? null;
  const totalStock = inventory
    ? inventory.reduce((sum, i) => sum + parseFloat(i.quantity), 0)
    : null;
  const openAlertCount = alerts?.length ?? null;
  const pendingOcrCount = receipts
    ? receipts.filter((r) => r.status === "pending_ocr").length
    : null;

  const recentAlerts = alerts ? alerts.slice(0, 5) : null;
  const recentReceipts = receipts ? receipts.slice(0, 5) : null;

  return (
    <main className="page-main">
      {errorMsg && <div className="empty" style={{ color: "var(--danger)" }}>{errorMsg}</div>}

      <div className="statGrid">
        <StatCard value={totalProducts} label="Tổng sản phẩm" />
        <StatCard value={totalStock != null ? totalStock.toLocaleString("vi-VN") : null} label="Tổng tồn kho (đơn vị)" accent />
        <StatCard value={openAlertCount} label="Cảnh báo đang mở" danger={openAlertCount > 0} />
        <StatCard value={pendingOcrCount} label="Phiếu chờ xử lý OCR" />
      </div>

      <div className="dashGrid">
        <div className="card">
          <h2>Cảnh báo gần đây</h2>
          <p className="card-sub">
            {recentAlerts ? `${recentAlerts.length} cảnh báo mới nhất` : "Đang tải…"} — xem đầy đủ ở tab{" "}
            <Link to="/alerts">Cảnh báo</Link>.
          </p>
          {recentAlerts && recentAlerts.length === 0 && <div className="empty">Không có cảnh báo nào đang mở 🎉</div>}
          <div className="alertList">
            {recentAlerts?.map((a) => (
              <div className="alertRow" key={a.id}>
                <div>
                  <span className={`badge alertType-${a.alert_type}`}>{ALERT_TYPE_LABEL[a.alert_type] || a.alert_type}</span>
                  <div className="alertRow-msg">{a.message}</div>
                </div>
                <button className="tapbtn" disabled={ackBusy === a.id} onClick={() => handleAck(a.id)}>
                  {ackBusy === a.id ? "…" : "Đã xử lý"}
                </button>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <h2>Phiếu nhập gần đây</h2>
          <p className="card-sub">{recentReceipts ? `${recentReceipts.length} phiếu mới nhất` : "Đang tải…"}</p>
          {recentReceipts && recentReceipts.length === 0 && <div className="empty">Chưa có phiếu nhập nào</div>}
          {recentReceipts && recentReceipts.length > 0 && (
            <table className="dataTable">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Kho</th>
                  <th>Trạng thái</th>
                </tr>
              </thead>
              <tbody>
                {recentReceipts.map((r) => (
                  <tr key={r.id}>
                    <td>#{r.id}</td>
                    <td>{r.store_location || "—"}</td>
                    <td>
                      <span className={`badge ${RECEIPT_STATUS_BADGE[r.status] || "not_started"}`}>
                        {RECEIPT_STATUS_LABEL[r.status] || r.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </main>
  );
}

function StatCard({ value, label, accent, danger }) {
  return (
    <div className="statCard">
      <div className={`statCard-value${accent ? " accent" : ""}${danger ? " danger" : ""}`}>
        {value != null ? value : "—"}
      </div>
      <div className="statCard-label">{label}</div>
    </div>
  );
}
