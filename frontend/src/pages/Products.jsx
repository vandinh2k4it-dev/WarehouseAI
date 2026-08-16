import { useEffect, useState } from "react";
import { api } from "../api";

export default function Products() {
  const [products, setProducts] = useState(null);
  const [inventory, setInventory] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [search, setSearch] = useState("");

  useEffect(() => {
    Promise.all([api.listProducts(), api.listInventory()])
      .then(([p, inv]) => {
        setProducts(p);
        setInventory(inv);
      })
      .catch((err) => setErrorMsg(err.message || String(err)));
  }, []);

  const filtered = products?.filter((p) =>
    (p.name + " " + (p.sku || "")).toLowerCase().includes(search.toLowerCase())
  );

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

        {errorMsg && <div className="empty" style={{ color: "var(--danger)" }}>{errorMsg}</div>}
        {!products && !errorMsg && <div className="empty">Đang tải…</div>}
        {filtered && filtered.length === 0 && <div className="empty">Không tìm thấy sản phẩm nào</div>}

        {filtered && filtered.length > 0 && (
          <div className="productGrid">
            {filtered.map((p) => {
              const batches = inventory?.filter((i) => i.product_id === p.id && parseFloat(i.quantity) > 0) || [];
              const total = batches.reduce((s, b) => s + parseFloat(b.quantity), 0);
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
