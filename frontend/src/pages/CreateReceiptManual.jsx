import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

const EMPTY_LINE = { product_name_raw: "", quantity: "", batch_code: "", expiry_date: "" };

export default function CreateReceiptManual() {
  const navigate = useNavigate();
  const [receiptCode, setReceiptCode] = useState("");
  const [storeLocation, setStoreLocation] = useState("");
  const [lines, setLines] = useState([{ ...EMPTY_LINE }]);
  const [errorMsg, setErrorMsg] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function updateLine(idx, field, value) {
    setLines((prev) => prev.map((l, i) => (i === idx ? { ...l, [field]: value } : l)));
  }

  function addLine() {
    setLines((prev) => [...prev, { ...EMPTY_LINE }]);
  }

  function removeLine(idx) {
    setLines((prev) => prev.filter((_, i) => i !== idx));
  }

  async function submit() {
    setErrorMsg("");

    const validLines = lines.filter((l) => l.product_name_raw.trim() && l.quantity);
    if (validLines.length === 0) {
      setErrorMsg("Cần ít nhất 1 dòng hàng có đủ tên sản phẩm và số lượng");
      return;
    }

    const payload = {
      receipt_code: receiptCode.trim() || null,
      store_location: storeLocation.trim() || null,
      line_items: validLines.map((l) => ({
        product_name_raw: l.product_name_raw.trim(),
        quantity: parseFloat(l.quantity),
        batch_code: l.batch_code.trim() || null,
        expiry_date: l.expiry_date || null,
      })),
    };

    setSubmitting(true);
    try {
      const receipt = await api.createReceiptManual(payload);
      navigate(`/import`, { state: { justCreatedReceiptId: receipt.id } });
    } catch (err) {
      setErrorMsg(err.message || String(err));
      setSubmitting(false);
    }
  }

  return (
    <main className="page-main">
      <div className="card">
        <h2>Tạo phiếu nhập bằng tay</h2>
        <p className="card-sub">
          Dùng khi không có ảnh phiếu giấy để quét — tự gõ lại thông tin trực tiếp.
        </p>

        <label>Mã phiếu (tuỳ chọn)</label>
        <input
          type="text"
          placeholder="VD: PN-2026-010"
          value={receiptCode}
          onChange={(e) => setReceiptCode(e.target.value)}
        />

        <label style={{ marginTop: 12 }}>Nhà cung cấp / địa điểm (tuỳ chọn)</label>
        <input
          type="text"
          placeholder="VD: Công ty TNHH An Bình"
          value={storeLocation}
          onChange={(e) => setStoreLocation(e.target.value)}
        />

        <div className="card-headRow" style={{ marginTop: 20 }}>
          <h2 style={{ margin: 0 }}>Dòng hàng</h2>
        </div>

        {lines.map((line, idx) => (
          <div className="manualLineRow" key={idx}>
            <div className="manualLineRow-head">
              <span className="text-muted mono">Dòng {idx + 1}</span>
              {lines.length > 1 && (
                <button className="ghost manualLineRow-remove" onClick={() => removeLine(idx)}>
                  Xoá dòng
                </button>
              )}
            </div>
            <input
              type="text"
              placeholder="Tên sản phẩm *"
              value={line.product_name_raw}
              onChange={(e) => updateLine(idx, "product_name_raw", e.target.value)}
            />
            <div className="manualLineRow-grid">
              <input
                type="number"
                inputMode="numeric"
                placeholder="Số lượng *"
                value={line.quantity}
                onChange={(e) => updateLine(idx, "quantity", e.target.value)}
              />
              <input
                type="text"
                placeholder="Mã lô (tuỳ chọn)"
                value={line.batch_code}
                onChange={(e) => updateLine(idx, "batch_code", e.target.value)}
              />
            </div>
            <label className="text-muted" style={{ fontSize: 12 }}>
              Hạn sử dụng (tuỳ chọn)
            </label>
            <input
              type="date"
              value={line.expiry_date}
              onChange={(e) => updateLine(idx, "expiry_date", e.target.value)}
            />
          </div>
        ))}

        <button className="ghost" onClick={addLine} style={{ marginTop: 4 }}>
          + Thêm dòng hàng
        </button>

        {errorMsg && (
          <div className="empty" style={{ color: "var(--danger)", marginTop: 12 }}>
            {errorMsg}
          </div>
        )}

        <button className="primary" onClick={submit} disabled={submitting} style={{ marginTop: 16 }}>
          {submitting ? "Đang tạo…" : "Tạo phiếu nhập"}
        </button>
      </div>
    </main>
  );
}
