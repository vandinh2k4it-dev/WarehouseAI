import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

const REF_TYPE_LABEL = {
  manual: "Gõ tay",
  camera_session: "Qua camera",
};

export default function ExportHistory() {
  const [history, setHistory] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [search, setSearch] = useState("");

  useEffect(() => {
    api
      .listExportHistory()
      .then(setHistory)
      .catch((err) => setErrorMsg(err.message || String(err)));
  }, []);

  const filtered = history?.filter((h) => h.product_name.toLowerCase().includes(search.toLowerCase()));

  // Tổng số lượng đã xuất (theo đúng danh sách đang lọc) — hiện nhanh 1 con
  // số tổng hợp phía trên bảng, kiểu dashboard thật.
  const totalExported = filtered?.reduce((s, h) => s + h.quantity, 0) ?? 0;

  return (
    <main className="page-main">
      <div className="card-headRow" style={{ marginBottom: 0 }}>
        <h2 style={{ margin: 0, fontSize: 20, textTransform: "none", color: "var(--text)" }}>Lịch sử xuất kho</h2>
        <Link to="/export" className="tapbtn">
          + Xuất hàng mới
        </Link>
      </div>

      <div className="statGrid" style={{ gridTemplateColumns: "1fr 1fr", marginTop: 14 }}>
        <div className="statCard">
          <div className="statCard-value accent">{filtered?.length ?? "…"}</div>
          <div className="statCard-label">Lượt xuất</div>
        </div>
        <div className="statCard">
          <div className="statCard-value">{totalExported.toLocaleString("vi-VN")}</div>
          <div className="statCard-label">Tổng số lượng đã xuất</div>
        </div>
      </div>

      <div className="card">
        <input
          type="text"
          placeholder="Tìm theo tên sản phẩm…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />

        {errorMsg && <div className="empty" style={{ color: "var(--danger)" }}>{errorMsg}</div>}
        {!history && !errorMsg && <div className="empty">Đang tải…</div>}
        {filtered && filtered.length === 0 && <div className="empty">Chưa có lượt xuất kho nào</div>}

        {filtered && filtered.length > 0 && (
          <div className="tableScroll">
            <table className="dataTable adminTable">
              <thead>
                <tr>
                  <th>Thời gian</th>
                  <th>Sản phẩm</th>
                  <th>Lô</th>
                  <th>Số lượng</th>
                  <th>Nguồn</th>
                  <th>Ghi chú</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((h) => (
                  <tr key={h.id}>
                    <td className="text-muted" style={{ whiteSpace: "nowrap" }}>
                      {new Date(h.created_at).toLocaleString("vi-VN")}
                    </td>
                    <td className="adminTable-name">{h.product_name}</td>
                    <td className="mono text-muted">{h.batch_code}</td>
                    <td className="mono">
                      {h.quantity.toLocaleString("vi-VN")} {h.unit}
                    </td>
                    <td className="text-muted">{REF_TYPE_LABEL[h.reference_type] || h.reference_type || "—"}</td>
                    <td className="text-muted">{h.note || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}
