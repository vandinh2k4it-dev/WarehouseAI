import { Fragment, useEffect, useMemo, useState } from "react";
import { api } from "../api";

const SORT_OPTIONS = [
  { value: "default", label: "Mặc định (theo tên)" },
  { value: "stock_desc", label: "Tồn kho cao nhất trước" },
  { value: "stock_asc", label: "Tồn kho thấp nhất trước" },
  { value: "expiry_asc", label: "HSD sắp hết trước" },
  { value: "expiry_desc", label: "HSD còn xa trước" },
  { value: "received_desc", label: "Nhập gần đây trước" },
  { value: "received_asc", label: "Nhập lâu rồi trước" },
];

function stockStatusOf(total, threshold) {
  if (total <= 0) return { label: "Hết hàng", cls: "danger" };
  if (total <= threshold) return { label: "Sắp hết", cls: "warn" };
  return { label: "Đủ hàng", cls: "ok" };
}

export default function Products() {
  const [products, setProducts] = useState(null);
  const [inventory, setInventory] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("stock_desc");
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    Promise.all([api.listProducts(), api.listInventory()])
      .then(([p, inv]) => {
        setProducts(p);
        setInventory(inv);
      })
      .catch((err) => setErrorMsg(err.message || String(err)));
  }, []);

  // Với mỗi sản phẩm, tính sẵn: tổng tồn kho, HSD gần nhất (để ưu tiên FEFO),
  // và ngày nhập gần nhất (dựa trên last_updated của lô mới nhất) — dùng
  // chung cho cả hiển thị lẫn sắp xếp, tính 1 lần duy nhất bằng useMemo.
  const enriched = useMemo(() => {
    if (!products || !inventory) return null;
    return products.map((p) => {
      const batches = inventory.filter((i) => i.product_id === p.id && parseFloat(i.quantity) > 0);
      const total = batches.reduce((s, b) => s + parseFloat(b.quantity), 0);
      const nearestExpiry = batches.length
        ? batches.reduce((min, b) => (!min || (b.expiry_date && b.expiry_date < min) ? b.expiry_date : min), null)
        : null;
      const latestReceived = batches.length
        ? batches.reduce((max, b) => (!max || (b.last_updated && b.last_updated > max) ? b.last_updated : max), null)
        : null;
      return { product: p, batches, total, nearestExpiry, latestReceived };
    });
  }, [products, inventory]);

  // Tổng tồn kho CẢ KHO (mọi sản phẩm cộng lại) — dùng làm mẫu số tính %
  // đóng góp của từng sản phẩm trong tổng thể, hiển thị ở cột "% Tổng kho".
  const totalStockAll = useMemo(() => {
    if (!enriched) return 0;
    return enriched.reduce((s, e) => s + e.total, 0);
  }, [enriched]);

  // Top 8 sản phẩm theo tồn kho — dữ liệu cho biểu đồ cột phía trên bảng.
  const topForChart = useMemo(() => {
    if (!enriched) return [];
    return [...enriched].sort((a, b) => b.total - a.total).slice(0, 8);
  }, [enriched]);
  const chartMax = topForChart[0]?.total || 1;

  const filtered = enriched?.filter((e) =>
    (e.product.name + " " + (e.product.sku || "")).toLowerCase().includes(search.toLowerCase())
  );

  const sorted = useMemo(() => {
    if (!filtered) return null;
    const arr = [...filtered];
    switch (sortBy) {
      case "stock_desc":
        return arr.sort((a, b) => b.total - a.total);
      case "stock_asc":
        return arr.sort((a, b) => a.total - b.total);
      case "expiry_asc":
        // Sản phẩm không có HSD (hết hàng) đẩy xuống cuối
        return arr.sort((a, b) => (a.nearestExpiry || "9999") < (b.nearestExpiry || "9999") ? -1 : 1);
      case "expiry_desc":
        return arr.sort((a, b) => (a.nearestExpiry || "0000") > (b.nearestExpiry || "0000") ? -1 : 1);
      case "received_desc":
        return arr.sort((a, b) => (a.latestReceived || "0000") > (b.latestReceived || "0000") ? -1 : 1);
      case "received_asc":
        return arr.sort((a, b) => (a.latestReceived || "9999") < (b.latestReceived || "9999") ? -1 : 1);
      default:
        return arr.sort((a, b) => a.product.name.localeCompare(b.product.name, "vi"));
    }
  }, [filtered, sortBy]);

  return (
    <main className="page-main">
      {/* Biểu đồ cột — top sản phẩm theo tồn kho, giúp nhìn nhanh mặt hàng
          nào đang chiếm nhiều kho nhất mà không cần đọc hết cả bảng. */}
      <div className="card">
        <h2>Top tồn kho</h2>
        {!enriched && <div className="empty">Đang tải…</div>}
        {topForChart.length > 0 && (
          <div className="barChart">
            {topForChart.map(({ product: p, total }) => (
              <div className="barChart-col" key={p.id}>
                <div className="barChart-value mono">{total.toLocaleString("vi-VN")}</div>
                <div className="barChart-bar" style={{ height: `${Math.max((total / chartMax) * 100, 3)}%` }} />
                <div className="barChart-label" title={p.name}>
                  {p.name}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Bảng dữ liệu chi tiết — kiểu dashboard quản trị: đầy đủ cột số
          liệu (tồn kho, % tổng kho, trạng thái, số lô, HSD), bấm vào 1
          dòng để mở rộng xem chi tiết từng lô hàng của đúng sản phẩm đó. */}
      <div className="card">
        <div className="card-headRow">
          <h2>Sản phẩm ({products?.length ?? "…"})</h2>
        </div>
        <input
          type="text"
          placeholder="Tìm theo tên hoặc SKU…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />

        <label style={{ marginTop: 2 }}>Sắp xếp theo</label>
        <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
          {SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>

        {errorMsg && <div className="empty" style={{ color: "var(--danger)" }}>{errorMsg}</div>}
        {!sorted && !errorMsg && <div className="empty">Đang tải…</div>}
        {sorted && sorted.length === 0 && <div className="empty">Không tìm thấy sản phẩm nào</div>}

        {sorted && sorted.length > 0 && (
          <div className="tableScroll">
            <table className="dataTable adminTable">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Sản phẩm</th>
                  <th>Tồn kho</th>
                  <th>% Tổng kho</th>
                  <th>Trạng thái</th>
                  <th>Số lô</th>
                  <th>HSD gần nhất</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map(({ product: p, batches, total, nearestExpiry }, idx) => {
                  const pct = totalStockAll > 0 ? (total / totalStockAll) * 100 : 0;
                  const status = stockStatusOf(total, p.low_stock_threshold);
                  const isExpanded = expandedId === p.id;
                  return (
                    <Fragment key={p.id}>
                      <tr className="adminTable-row" onClick={() => setExpandedId(isExpanded ? null : p.id)}>
                        <td className="text-muted">{idx + 1}</td>
                        <td>
                          <div className="adminTable-name">{p.name}</div>
                          {p.sku && <div className="adminTable-sku mono">{p.sku}</div>}
                        </td>
                        <td className="mono">
                          {total.toLocaleString("vi-VN")} {p.unit}
                        </td>
                        <td>
                          <div className="pctCell">
                            <div className="pctCell-bar">
                              <div className="pctCell-fill" style={{ width: `${Math.min(pct, 100)}%` }} />
                            </div>
                            <span className="mono pctCell-num">{pct.toFixed(1)}%</span>
                          </div>
                        </td>
                        <td>
                          <span className={`stockStatus ${status.cls}`}>{status.label}</span>
                        </td>
                        <td className="text-muted">{batches.length}</td>
                        <td className="text-muted">{nearestExpiry || "—"}</td>
                      </tr>
                      {isExpanded && (
                        <tr className="adminTable-expandRow">
                          <td colSpan={7}>
                            {batches.length > 0 ? (
                              <div className="productCard-batches">
                                {batches
                                  .slice()
                                  .sort((a, b) => (a.expiry_date || "9999").localeCompare(b.expiry_date || "9999"))
                                  .map((b) => (
                                    <div key={b.id} className="productCard-batchRow">
                                      <span className="mono">{b.batch_code}</span>
                                      <span>
                                        {b.quantity} {p.unit}
                                      </span>
                                      <span className="text-muted">{b.expiry_date || "—"}</span>
                                    </div>
                                  ))}
                              </div>
                            ) : (
                              <div className="empty" style={{ padding: "4px 0" }}>
                                Hết tồn kho — không còn lô nào
                              </div>
                            )}
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}
