import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import CountingScreen from "../components/CountingScreen";

export default function ExportFlow() {
  const [products, setProducts] = useState([]);
  const [productId, setProductId] = useState("");
  const [qty, setQty] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [activeSession, setActiveSession] = useState(null); // { session, expected, label }

  useEffect(() => {
    api
      .listProducts()
      .then(setProducts)
      .catch((err) => setErrorMsg(err.message || String(err)));
  }, []);

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

  return (
    <main className="page-main">
      <Link to="/inout" className="backlink">
        ← Chọn Nhập / Xuất kho
      </Link>
      <div className="card">
        <h2>Chọn sản phẩm cần xuất</h2>
        <label>Sản phẩm</label>
        <select value={productId} onChange={(e) => setProductId(e.target.value)}>
          <option value="">— Chọn sản phẩm —</option>
          {products.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
              {p.sku ? ` (${p.sku})` : ""}
            </option>
          ))}
        </select>

        <label>Số lượng dự kiến xuất</label>
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
