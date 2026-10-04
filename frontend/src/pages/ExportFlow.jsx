import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useToast } from "../components/Toast";
import CountingScreen from "../components/CountingScreen";
import ProductSearchSelect from "../components/ProductSearchSelect";
import { formatDateTimeVN } from "../utils/search";
import "../styles/listing.css";

const REF_TYPE_LABEL = {
  manual: "Gõ tay",
  camera_session: "Qua camera",
};

export default function ExportFlow() {
  const [products, setProducts] = useState([]);
  const [inventory, setInventory] = useState([]);
  const [productId, setProductId] = useState("");
  const [qty, setQty] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [activeSession, setActiveSession] = useState(null); // { session, expected, label }
  const [recent, setRecent] = useState(null); // 5 lượt xuất gần nhất (null = đang tải)
  const showToast = useToast();

  useEffect(() => {
    Promise.all([api.listProducts(), api.listInventory()])
      .then(([p, inv]) => {
        setProducts(p);
        setInventory(inv);
      })
      .catch((err) => setErrorMsg(err.message || String(err)));
    loadRecent();
  }, []);

  async function loadRecent() {
    try {
      const hist = await api.listExportHistory();
      setRecent(hist.slice(0, 5)); // backend đã sắp mới -> cũ
    } catch {
      setRecent([]); // không tải được thì chỉ ẩn mục này, không ảnh hưởng form xuất kho
    }
  }

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
    const currentStock = stockOf(pid);
    if (q > currentStock) {
      // Chặn sớm ngay trên UI — backend cũng tự chặn ở bước /stop, nhưng để
      // tới lúc đó thì nhân viên đã mất công quay/đếm hết video rồi mới biết.
      setErrorMsg(`Chỉ còn ${currentStock.toLocaleString("vi-VN")} trong kho, không đủ để xuất ${q}`);
      return;
    }
    try {
      const session = await api.startExport(pid, q);
      setActiveSession({ session, expected: q, label: productName });
    } catch (err) {
      showToast(err.message || String(err), "error");
    }
  }

  async function backToForm() {
    setActiveSession(null);
    setQty("");
    // Tải lại để số "còn X" trong danh sách + mục "Vừa xuất gần đây" cập nhật
    // ngay sau khi xuất xong (trước đây phải tải lại trang mới thấy số mới).
    try {
      setInventory(await api.listInventory());
    } catch {
      // giữ nguyên số cũ nếu tải lỗi
    }
    loadRecent();
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
        <label htmlFor="export-product">Sản phẩm (gõ tên để tìm, không cần dấu)</label>
        <ProductSearchSelect
          id="export-product"
          products={products}
          value={productId}
          onChange={setProductId}
          stockOf={stockOf}
        />

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

      {recent && recent.length > 0 && (
        <div className="card">
          <div className="card-headRow">
            <h2>Vừa xuất gần đây</h2>
            <Link to="/export/history" className="rc-link">
              Xem tất cả →
            </Link>
          </div>
          {recent.map((h) => (
            <div className="recentItem" key={h.id}>
              <div>
                <div className="recentItem-name">{h.product_name}</div>
                <div className="recentItem-sub">
                  {formatDateTimeVN(h.created_at)} · lô {h.batch_code} ·{" "}
                  {REF_TYPE_LABEL[h.reference_type] || h.reference_type || "—"}
                </div>
              </div>
              <div className="recentItem-qty">
                −{h.quantity.toLocaleString("vi-VN")} {h.unit}
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
