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
  const [analytics, setAnalytics] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [ackBusy, setAckBusy] = useState(null);
  const [expandedAlertId, setExpandedAlertId] = useState(null);

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

    // Tách riêng khỏi khối try/catch chính ở trên — đây là khối thống kê
    // MỚI thêm, nếu lỗi (vd backend chưa deploy kịp endpoint mới) thì chỉ
    // ẩn 2 card thống kê, KHÔNG được làm hỏng luôn cả trang Tổng quan
    // (4 stat card + cảnh báo + phiếu gần đây) vốn đã chạy ổn định.
    try {
      const an = await api.getAnalytics(14);
      setAnalytics(an);
    } catch {
      setAnalytics(null);
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
        <Link to="/products" className="statCard-link">
          <StatCard value={totalProducts} label="Tổng sản phẩm" />
        </Link>
        <Link to="/products" className="statCard-link">
          <StatCard value={totalStock != null ? totalStock.toLocaleString("vi-VN") : null} label="Tổng tồn kho (đơn vị)" accent />
        </Link>
        <Link to="/alerts" className="statCard-link">
          <StatCard value={openAlertCount} label="Cảnh báo đang mở" danger={openAlertCount > 0} />
        </Link>
        <Link to="/import" className="statCard-link">
          <StatCard value={pendingOcrCount} label="Phiếu chờ xử lý OCR" />
        </Link>
      </div>

      <div className="dashGrid">
        {analytics && analytics.daily_flow.length > 0 && (() => {
          const maxVal = Math.max(1, ...analytics.daily_flow.flatMap((d) => [d.imported, d.exported]));
          return (
            <div className="card">
              <h2>Xu hướng nhập-xuất ({analytics.days} ngày)</h2>
              <p className="card-sub">
                <span className="flowLegend-dot imported" /> Nhập &nbsp;
                <span className="flowLegend-dot exported" /> Xuất
              </p>
              <div className="flowChart">
                {analytics.daily_flow.map((d) => (
                  <div className="flowChart-col" key={d.date} title={`${d.date}: nhập ${d.imported} / xuất ${d.exported}`}>
                    <div className="flowChart-bars">
                      <div className="flowChart-bar imported" style={{ height: `${(d.imported / maxVal) * 100}%` }} />
                      <div className="flowChart-bar exported" style={{ height: `${(d.exported / maxVal) * 100}%` }} />
                    </div>
                    <div className="flowChart-label">{d.date.slice(5)}</div>
                  </div>
                ))}
              </div>
            </div>
          );
        })()}

        {analytics && analytics.top_products.length > 0 && (() => {
          const maxMoved = Math.max(
            1,
            ...analytics.top_products.map((p) => p.imported_total + p.exported_total)
          );
          return (
            <div className="card">
              <h2>Top sản phẩm quay vòng nhanh ({analytics.days} ngày)</h2>
              <p className="card-sub">Xếp theo tổng nhập + xuất — sản phẩm luân chuyển nhiều nhất trong kho</p>
              <div className="topProductList">
                {analytics.top_products.map((p) => {
                  const moved = p.imported_total + p.exported_total;
                  return (
                    <div className="topProductRow" key={p.product_id}>
                      <div className="topProductRow-name">
                        {p.name}
                        {p.sku ? <span className="text-muted"> ({p.sku})</span> : null}
                      </div>
                      <div className="topProductRow-bar">
                        <div className="topProductRow-fill" style={{ width: `${(moved / maxMoved) * 100}%` }} />
                      </div>
                      <div className="topProductRow-nums mono">
                        +{p.imported_total.toLocaleString("vi-VN")} / -{p.exported_total.toLocaleString("vi-VN")} {p.unit}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })()}

        <div className="card">
          <h2>Cảnh báo gần đây</h2>
          <p className="card-sub">
            {recentAlerts ? `${recentAlerts.length} cảnh báo mới nhất` : "Đang tải…"} — xem đầy đủ ở tab{" "}
            <Link to="/alerts">Cảnh báo</Link>.
          </p>
          {recentAlerts && recentAlerts.length === 0 && <div className="empty">Không có cảnh báo nào đang mở 🎉</div>}
          <div className="alertList">
            {recentAlerts?.map((a) => {
              const isExpanded = expandedAlertId === a.id;
              // Rút gọn về đúng CÂU ĐẦU TIÊN (tới dấu chấm đầu tiên) cho cái
              // nhìn tổng quan gọn gàng — phần chi tiết kỹ thuật (ngưỡng %,
              // số phiên...) chỉ hiện khi bấm vào xem thêm, tránh mỗi dòng
              // cảnh báo dài 3-4 dòng làm rối cả trang Tổng quan.
              const firstSentenceEnd = a.message.indexOf(". ");
              const shortMsg =
                firstSentenceEnd > -1 ? a.message.slice(0, firstSentenceEnd + 1) : a.message;
              const hasMore = shortMsg.length < a.message.length;

              return (
                <div className="alertRow" key={a.id}>
                  <div
                    className={hasMore ? "alertRow-clickable" : ""}
                    onClick={hasMore ? () => setExpandedAlertId(isExpanded ? null : a.id) : undefined}
                  >
                    <span className={`badge alertType-${a.alert_type}`}>{ALERT_TYPE_LABEL[a.alert_type] || a.alert_type}</span>
                    <div className="alertRow-msg">{isExpanded ? a.message : shortMsg}</div>
                    {hasMore && (
                      <span className="alertRow-toggle">{isExpanded ? "Thu gọn" : "Xem thêm"}</span>
                    )}
                  </div>
                  <button className="tapbtn" disabled={ackBusy === a.id} onClick={() => handleAck(a.id)}>
                    {ackBusy === a.id ? "…" : "Đã xử lý"}
                  </button>
                </div>
              );
            })}
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
