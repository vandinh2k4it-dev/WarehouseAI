import { useEffect, useMemo, useState } from "react";
import { api } from "../api";

const SORT_OPTIONS = [
  { value: "default", label: "Mặc định (theo tên)" },
  { value: "expiry_asc", label: "HSD sắp hết trước" },
  { value: "expiry_desc", label: "HSD còn xa trước" },
  { value: "received_desc", label: "Nhập gần đây trước" },
  { value: "received_asc", label: "Nhập lâu rồi trước" },
];

export default function Products() {
  const [products, setProducts] = useState(null);
  const [inventory, setInventory] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("default");

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

  const filtered = enriched?.filter((e) =>
    (e.product.name + " " + (e.product.sku || "")).toLowerCase().includes(search.toLowerCase())
  );

  const sorted = useMemo(() => {
    if (!filtered) return null;
    const arr = [...filtered];
    switch (sortBy) {
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
      <div className="card">
        <h2>Sản phẩm ({products?.length ?? "…"})</h2>
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
          <div className="productGrid">
            {sorted.map(({ product: p, batches, total }) => {
              const isLow = total <= p.low_stock_threshold;
              return (
                <div className="productCard" key={p.id}>
                  <div className="productCard-head">
                    <div className="productCard-name">{p.name}</div>
                    {p.sku && <div className="productCard-sku mono">{p.sku}</div>}
                  </div>
                  <div className={`productCard-total${isLow ? " low" : ""}`}>
                    {total.toLocaleString("vi-VN")} {p.unit}
                    {isLow && <span className="badge needs_review" style={{ marginLeft: 8 }}>sắp hết</span>}
                  </div>
                  {batches.length > 0 ? (
                    <div className="productCard-batches">
                      {batches
                        .slice()
                        .sort((a, b) => (a.expiry_date || "9999").localeCompare(b.expiry_date || "9999"))
                        .map((b) => (
                          <div key={b.id} className="productCard-batchRow">
                            <span className="mono">{b.batch_code}</span>
                            <span>{b.quantity} {p.unit}</span>
                            <span className="text-muted">{b.expiry_date || "—"}</span>
                          </div>
                        ))}
                    </div>
                  ) : (
                    <div className="empty" style={{ padding: "8px 0" }}>Hết tồn kho</div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </main>
  );
}
