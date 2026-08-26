import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import CountingScreen from "../components/CountingScreen";

export default function ExportFlow() {
  const [products, setProducts] = useState([]);
  const [inventory, setInventory] = useState([]);
  const [productId, setProductId] = useState("");
  const [qty, setQty] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [activeSession, setActiveSession] = useState(null); // { session, expected, label }

  useEffect(() => {
    Promise.all([api.listProducts(), api.listInventory()])
      .then(([p, inv]) => {
        setProducts(p);
        setInventory(inv);
      })
      .catch((err) => setErrorMsg(err.message || String(err)));
  }, []);

  function stockOf(productId) {
    return inventory
      .filter((i) => i.product_id === productId)
      .reduce((sum, i) => sum + parseFloat(i.quantity), 0);
  }

  async function begin() {
    setErrorMsg("");
    const pid = parseInt(productId, 10);
    const q = parseFloat(qty);
    if (!pid || !q) {
      setErrorMsg("Chọn sản phẩm và nhập số lượng dự kiến xuất");
      return;
    }
    const productName = products.find((p) => p.id === pid)?.name || `#${pid}`;
    try {
      const session = await api.startExport(pid, q);
      setActiveSession({ session, expected: q, label: productName });
    } catch (err) {
      setErrorMsg(err.message || String(err));
    }
  }

  function backToForm() {
    setActiveSession(null);
    setQty("");
  }

  if (activeSession) {
    return (
      <main className="page-main">
        <CountingScreen
          session={activeSession.session}
          expectedQuantity={activeSession.expected}
          label={activeSession.label}
          onCancel={() => setActiveSession(null)}
          onDone={backToForm}
        />
      </main>
    );
  }

  const selectedProduct = products.find((p) => p.id === parseInt(productId, 10));
  const selectedBatches = selectedProduct
    ? inventory
        .filter((i) => i.product_id === selectedProduct.id && parseFloat(i.quantity) > 0)
        .slice()
        .sort((a, b) => (a.expiry_date || "9999").localeCompare(b.expiry_date || "9999"))
    : [];
  const selectedTotal = selectedProduct ? stockOf(selectedProduct.id) : null;

  return (
    <main className="page-main">
      <div className="card-headRow" style={{ marginBottom: 14 }}>
        <h2 style={{ margin: 0, fontSize: 20, textTransform: "none", color: "var(--text)" }}>Xuất kho</h2>
        <Link to="/export/history" className="tapbtn">
          🕘 Lịch sử xuất kho
        </Link>
      </div>
      <div className="card">
        <h2>Chọn sản phẩm cần xuất</h2>
        <label>Sản phẩm</label>
        <select value={productId} onChange={(e) => setProductId(e.target.value)}>
          <option value="">— Chọn sản phẩm —</option>
          {products.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
              {p.sku ? ` (${p.sku})` : ""} — còn {stockOf(p.id).toLocaleString("vi-VN")} {p.unit}
            </option>
          ))}
        </select>

        {selectedProduct && (
          <div className="stockHint">
            {selectedTotal <= selectedProduct.low_stock_threshold && (
              <div className="stockHint-warn">⚠ Sản phẩm này sắp hết hàng trong kho</div>
            )}
            {selectedBatches.length === 0 ? (
              <div className="stockHint-warn">⚠ Hiện KHÔNG còn tồn kho cho sản phẩm này</div>
            ) : (
              <>
                <div className="stockHint-total">
                  Tồn kho hiện có: <b>{selectedTotal.toLocaleString("vi-VN")} {selectedProduct.unit}</b>
                </div>
                <div className="stockHint-batches">
                  {selectedBatches.map((b) => (
                    <span key={b.id} className="mono">
                      {b.batch_code}: {b.quantity} {selectedProduct.unit}
                      {b.expiry_date ? ` (HSD ${b.expiry_date})` : ""}
                    </span>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        <label style={{ marginTop: 14 }}>Số lượng dự kiến xuất</label>
        <input
          type="number"
          inputMode="numeric"
          placeholder="20"
          value={qty}
          onChange={(e) => setQty(e.target.value)}
        />

        <button className="primary" onClick={begin}>
          Bắt đầu đếm
        </button>

        {errorMsg && <div className="empty" style={{ color: "var(--danger)" }}>{errorMsg}</div>}
      </div>
    </main>
  );
}
