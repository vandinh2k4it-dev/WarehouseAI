import { useEffect, useState } from "react";
import { api } from "../api";

const ALERT_TYPE_LABEL = {
  discrepancy: "Chênh lệch",
  low_stock: "Sắp hết hàng",
  expiring_soon: "Sắp hết hạn",
};

export default function Alerts() {
  const [alerts, setAlerts] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [ackBusy, setAckBusy] = useState(null);
  const [showResolved, setShowResolved] = useState(false);

  useEffect(() => {
    load();
  }, [showResolved]);

  function load() {
    setErrorMsg("");
    api
      .listAlerts(showResolved ? "acknowledged" : "open")
      .then(setAlerts)
      .catch((err) => setErrorMsg(err.message || String(err)));
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

  return (
    <main className="page-main">
      <div className="card">
        <h2>Cảnh báo</h2>
        <div className="chips">
          <button className={`chip${!showResolved ? " active" : ""}`} onClick={() => setShowResolved(false)}>
            Đang mở
          </button>
          <button className={`chip${showResolved ? " active" : ""}`} onClick={() => setShowResolved(true)}>
            Đã xử lý
          </button>
        </div>

        {errorMsg && <div className="empty" style={{ color: "var(--danger)" }}>{errorMsg}</div>}
        {!alerts && !errorMsg && <div className="empty">Đang tải…</div>}
        {alerts && alerts.length === 0 && (
          <div className="empty">{showResolved ? "Chưa có cảnh báo nào đã xử lý" : "Không có cảnh báo nào đang mở 🎉"}</div>
        )}

        <div className="alertList">
          {alerts?.map((a) => (
            <div className="alertRow" key={a.id}>
              <div>
                <span className={`badge alertType-${a.alert_type}`}>{ALERT_TYPE_LABEL[a.alert_type] || a.alert_type}</span>
                <span className="alertRow-time text-muted">
                  {new Date(a.created_at).toLocaleString("vi-VN")}
                </span>
                <div className="alertRow-msg">{a.message}</div>
              </div>
              {!showResolved && (
                <button className="tapbtn" disabled={ackBusy === a.id} onClick={() => handleAck(a.id)}>
                  {ackBusy === a.id ? "…" : "Đã xử lý"}
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
