import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";

// GHI CHÚ: OCR (PaddleOCR + VietOCR) chạy trên backend, có thể mất VÀI CHỤC
// GIÂY cho lần đầu tiên (model load lazy lúc nhận request đầu tiên, các lần
// sau nhanh hơn nhiều) — luôn hiện rõ cảnh báo thời gian chờ, tránh nhân
// viên tưởng bị treo mà bấm lại nhiều lần gây trùng phiếu.
export default function ScanReceipt() {
  const [status, setStatus] = useState("idle"); // idle | uploading | done | error
  const [storeLocation, setStoreLocation] = useState("");
  const [result, setResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const inputRef = useRef(null);
  const navigate = useNavigate();

  async function handleFileSelected(e) {
    const file = e.target.files?.[0];
    if (!file) return;

    setStatus("uploading");
    setErrorMsg("");
    try {
      const receipt = await api.uploadReceipt(file, storeLocation || undefined);
      setResult(receipt);
      setStatus("done");
    } catch (err) {
      setErrorMsg(err.message || String(err));
      setStatus("error");
    }
  }

  function retry() {
    setStatus("idle");
    setErrorMsg("");
    if (inputRef.current) inputRef.current.value = "";
  }

  const mappedCount = result?.line_items?.filter((l) => l.product_id != null).length ?? 0;
  const totalLines = result?.line_items?.length ?? 0;

  return (
    <main className="page-main">
      <Link to="/import" className="backlink">
        ← Chọn phiếu khác
      </Link>

      <div className="card">
        <h2>Quét phiếu nhập mới</h2>

        {status === "idle" && (
          <>
            <label>Kho / địa điểm (tuỳ chọn)</label>
            <input
              type="text"
              placeholder="VD: Kho A"
              value={storeLocation}
              onChange={(e) => setStoreLocation(e.target.value)}
            />

            <div className="scanBtnRow">
              <label className="camBtn">
                📷 Chụp ảnh
                <input
                  type="file"
                  accept="image/*"
                  capture="environment"
                  onChange={handleFileSelected}
                  style={{ display: "none" }}
                />
              </label>
              <label className="camBtn secondary">
                🖼 Chọn ảnh có sẵn
                <input
                  ref={inputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleFileSelected}
                  style={{ display: "none" }}
                />
              </label>
            </div>
            <p className="card-sub" style={{ marginTop: 4 }}>
              Chụp thẳng, đủ sáng, rõ nét cả bảng — OCR đọc chính xác hơn nhiều nếu ảnh không bị
              nghiêng/mờ/thiếu sáng.
            </p>
          </>
        )}

        {status === "uploading" && (
          <>
            <div className="spinner" />
            <div className="empty">
              Đang tải ảnh lên &amp; chạy OCR — có thể mất khoảng 10–30 giây (lâu hơn ở lần quét đầu
              tiên do model cần tải), xin đừng bấm lại hoặc rời trang.
            </div>
          </>
        )}

        {status === "error" && (
          <>
            <div className="empty" style={{ color: "var(--danger)", whiteSpace: "pre-wrap" }}>
              {errorMsg}
            </div>
            <button className="ghost" onClick={retry}>
              Thử lại
            </button>
          </>
        )}

        {status === "done" && result && (
          <>
            <div className="resultBox ok">
              <div className="resultBox-title">✅ Đã quét xong — {result.receipt_code || `Phiếu #${result.id}`}</div>
              <div className="resultBox-num">
                Trích xuất được {totalLines} dòng hàng, tự khớp đúng {mappedCount}/{totalLines} với
                danh mục sản phẩm sẵn có.
              </div>
            </div>

            {totalLines > 0 && (
              <div className="lineList" style={{ marginTop: 14 }}>
                {result.line_items.map((line) => (
                  <div className="lineCard" key={line.id}>
                    <div>
                      <div className="lineCard-name">{line.product_name_raw}</div>
                      <div className="lineCard-sub">
                        SL: {line.quantity}
                        {line.batch_code ? ` · Lô ${line.batch_code}` : ""}
                        {line.expiry_date ? ` · HSD ${line.expiry_date}` : ""}
                      </div>
                    </div>
                    <span className={`badge ${line.product_id != null ? "matched" : "needs_review"}`}>
                      {line.product_id != null ? "đã khớp" : "chưa rõ sản phẩm"}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {mappedCount < totalLines && (
              <p className="card-sub" style={{ marginTop: 10 }}>
                ⚠ Có {totalLines - mappedCount} dòng chưa tự khớp được với sản phẩm nào trong danh
                mục — kiểm tra lại trên máy tính (mục "Sản phẩm chưa gán") trước khi đếm dòng đó.
              </p>
            )}

            <button className="primary" style={{ marginTop: 14 }} onClick={() => navigate("/import")}>
              Xong — về danh sách phiếu
            </button>
          </>
        )}
      </div>
    </main>
  );
}
