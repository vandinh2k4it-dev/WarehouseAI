import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import Highlight from "../components/Highlight";
import { matchesQuery, toLocalDateKey } from "../utils/search";
import "../styles/listing.css";

const REF_TYPE_LABEL = {
  manual: "Gõ tay",
  camera_session: "Qua camera",
};

export default function ExportHistory() {
  const [history, setHistory] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [search, setSearch] = useState("");
  const [dateFilter, setDateFilter] = useState(""); // "YYYY-MM-DD"
  const [productFilter, setProductFilter] = useState(null); // product_id đang lọc nhanh bằng chip (null = không lọc)

  useEffect(() => {
    api
      .listExportHistory()
      .then(setHistory)
      .catch((err) => setErrorMsg(err.message || String(err)));
  }, []);

  // Tìm không phân biệt hoa/thường, KHÔNG cần gõ dấu, nhiều từ thì khớp đủ
  // các từ (xem utils/search.js); tìm cả theo mã lô và ghi chú.
  const filtered = history?.filter((h) => {
    if (productFilter !== null && h.product_id !== productFilter) return false;
    if (!matchesQuery(`${h.product_name} ${h.batch_code || ""} ${h.note || ""}`, search)) return false;
    if (dateFilter && toLocalDateKey(h.created_at) !== dateFilter) return false;
    return true;
  });

  // Tổng hợp "đã xuất những sản phẩm nào, bao nhiêu" để nhìn qua là biết —
  // tính theo bộ lọc NGÀY (không theo ô tìm/chip, để bấm chip này sang chip
  // khác được). Bấm vào chip = lọc nhanh đúng sản phẩm đó.
  const productSummary = (() => {
    const map = new Map();
    (history ?? []).forEach((h) => {
      if (dateFilter && toLocalDateKey(h.created_at) !== dateFilter) return;
      const cur = map.get(h.product_id) || { id: h.product_id, name: h.product_name, unit: h.unit, total: 0 };
      cur.total += h.quantity;
      map.set(h.product_id, cur);
    });
    return [...map.values()].sort((a, b) => b.total - a.total);
  })();
  const MAX_CHIPS = 10;
  const anyFilter = search.trim() !== "" || dateFilter !== "" || productFilter !== null;
  function clearAllFilters() {
    setSearch("");
    setDateFilter("");
    setProductFilter(null);
  }

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
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <div className="searchBox" style={{ flex: 1, minWidth: 180, marginBottom: 0 }}>
            <span className="searchBox-icon" aria-hidden="true">
              🔍
            </span>
            <input
              type="text"
              placeholder="Tìm sản phẩm, mã lô…"
              title="Tìm theo tên sản phẩm, mã lô hoặc ghi chú — không cần gõ dấu"
              aria-label="Tìm trong lịch sử xuất kho"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            {search && (
              <button
                type="button"
                className="searchBox-clear"
                aria-label="Xoá từ khoá tìm kiếm"
                onClick={() => setSearch("")}
              >
                ✕
              </button>
            )}
          </div>
          <input
            type="date"
            value={dateFilter}
            onChange={(e) => setDateFilter(e.target.value)}
            title="Lọc theo ngày xuất"
            style={{ width: "auto", marginBottom: 0 }}
          />
          {dateFilter && (
            <button className="ghost lineCard-smallBtn" onClick={() => setDateFilter("")}>
              Bỏ lọc ngày
            </button>
          )}
        </div>

        {productSummary.length > 0 && (
          <>
            <div className="chipsLabel">Đã xuất theo sản phẩm (bấm để lọc nhanh):</div>
            <div className="productChips">
              {productSummary.slice(0, MAX_CHIPS).map((p) => (
                <button
                  key={p.id}
                  className={`filterTab${productFilter === p.id ? " active" : ""}`}
                  onClick={() => setProductFilter(productFilter === p.id ? null : p.id)}
                >
                  {p.name}
                  <span className="filterTab-count">
                    −{p.total.toLocaleString("vi-VN")} {p.unit}
                  </span>
                </button>
              ))}
            </div>
            {productSummary.length > MAX_CHIPS && (
              <div className="chipsLabel" style={{ marginTop: -6, marginBottom: 10 }}>
                …và {productSummary.length - MAX_CHIPS} sản phẩm khác — gõ tên vào ô tìm kiếm để lọc.
              </div>
            )}
          </>
        )}
        {anyFilter && history && history.length > 0 && (
          <div className="listSummary">
            <span>
              Hiển thị <b>{filtered?.length ?? 0}</b>/{history.length} lượt xuất
            </span>
            <button className="linkBtn" onClick={clearAllFilters}>
              Xoá tất cả bộ lọc
            </button>
          </div>
        )}

        {errorMsg && <div className="empty" style={{ color: "var(--danger)" }}>{errorMsg}</div>}
        {!history && !errorMsg && <div className="empty">Đang tải…</div>}
        {history && history.length === 0 && <div className="empty">Chưa có lượt xuất kho nào</div>}
        {history && history.length > 0 && filtered && filtered.length === 0 && (
          <div className="empty">Không có lượt xuất nào khớp bộ lọc đang chọn.</div>
        )}

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
                    <td className="adminTable-name">
                      <Highlight text={h.product_name} query={search} />
                    </td>
                    <td className="mono text-muted">
                      <Highlight text={h.batch_code} query={search} />
                    </td>
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