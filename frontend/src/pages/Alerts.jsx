import { useEffect, useState } from "react";
import { api } from "../api";
import {
  isPushSupported,
  getPermissionState,
  getCurrentSubscription,
  subscribeToPush,
  unsubscribeFromPush,
} from "../pushNotifications";

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
      <PushNotificationBanner />

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

// Banner bật/tắt thông báo đẩy — tách riêng để Alerts.jsx không phình to,
// tự kiểm tra trạng thái đăng ký hiện tại lúc mount (đã bật từ trước, hay
// trình duyệt không hỗ trợ, hay người dùng đã từ chối quyền trước đó).
function PushNotificationBanner() {
  const [state, setState] = useState("checking"); // checking | unsupported | denied | off | on
  const [busy, setBusy] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [testMsg, setTestMsg] = useState("");

  useEffect(() => {
    checkState();
  }, []);

  async function checkState() {
    if (!isPushSupported()) {
      setState("unsupported");
      return;
    }
    const perm = getPermissionState();
    if (perm === "denied") {
      setState("denied");
      return;
    }
    const sub = await getCurrentSubscription();
    setState(sub ? "on" : "off");
  }

  async function handleEnable() {
    setBusy(true);
    setErrorMsg("");
    try {
      await subscribeToPush(navigator.userAgent.slice(0, 60));
      setState("on");
    } catch (err) {
      setErrorMsg(err.message || String(err));
      await checkState();
    } finally {
      setBusy(false);
    }
  }

  async function handleDisable() {
    setBusy(true);
    setErrorMsg("");
    try {
      await unsubscribeFromPush();
      setState("off");
    } catch (err) {
      setErrorMsg(err.message || String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleTest() {
    setTestMsg("Đang gửi…");
    try {
      const result = await api.testPush();
      setTestMsg(`Đã gửi tới ${result.sent} thiết bị (${result.failed} lỗi, ${result.removed} hết hạn đã dọn).`);
    } catch (err) {
      setTestMsg("Lỗi: " + (err.message || String(err)));
    }
  }

  if (state === "checking") return null;

  if (state === "unsupported") {
    return (
      <div className="pushBanner">
        <span>🔕 Trình duyệt này không hỗ trợ thông báo đẩy.</span>
      </div>
    );
  }

  if (state === "denied") {
    return (
      <div className="pushBanner warn">
        <span>🔕 Bạn đã chặn thông báo trước đó — vào cài đặt trình duyệt (biểu tượng ổ khoá cạnh URL) để bật lại.</span>
      </div>
    );
  }

  if (state === "on") {
    return (
      <div className="pushBanner ok">
        <span>🔔 Đã bật thông báo đẩy cho thiết bị này.</span>
        <div className="pushBanner-actions">
          <button className="ghost" onClick={handleTest} style={{ marginTop: 0 }}>
            Gửi thử
          </button>
          <button className="ghost" disabled={busy} onClick={handleDisable} style={{ marginTop: 0 }}>
            Tắt
          </button>
        </div>
        {testMsg && <div className="pushBanner-msg">{testMsg}</div>}
      </div>
    );
  }

  return (
    <div className="pushBanner">
      <span>🔔 Bật thông báo để nhận cảnh báo ngay trên điện thoại, kể cả khi không mở sẵn app.</span>
      <button className="primary" disabled={busy} onClick={handleEnable} style={{ marginTop: 10 }}>
        {busy ? "Đang bật…" : "Bật thông báo"}
      </button>
      {errorMsg && <div className="pushBanner-msg" style={{ color: "var(--danger)" }}>{errorMsg}</div>}
    </div>
  );
}
