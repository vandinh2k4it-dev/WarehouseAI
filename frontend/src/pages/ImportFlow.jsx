import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import CountingScreen from "../components/CountingScreen";

const LINE_STATUS_LABEL = {
  not_started: "chưa đếm",
  counting: "đang đếm",
  matched: "đã khớp",
  needs_review: "lệch — kiểm tra sau",
  resolved_override: "đã xử lý",
};

const RECEIPT_STATUS_LABEL = {
  pending_ocr: "đang xử lý OCR",
  ocr_done: "chờ đếm hàng",
  reconciled: "đã xong hết",
};
const RECEIPT_STATUS_BADGE = {
  pending_ocr: "counting",
  ocr_done: "not_started",
  reconciled: "matched",
};

export default function ImportFlow() {
  const [receipts, setReceipts] = useState(null);
  const [loadingReceipts, setLoadingReceipts] = useState(true);
  const [selectedReceipt, setSelectedReceipt] = useState(null); // receipt object
  const [lines, setLines] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [activeSession, setActiveSession] = useState(null); // { session, expected, label }

  useEffect(() => {
    loadReceipts();
  }, []);

  async function loadReceipts() {
    setLoadingReceipts(true);
    setErrorMsg("");
    try {
      const data = await api.listReceipts();
      setReceipts(data);
    } catch (err) {
      setErrorMsg(err.message || String(err));
    } finally {
      setLoadingReceipts(false);
    }
  }

  async function pickReceipt(receipt) {
    setSelectedReceipt(receipt);
    setErrorMsg("");
    setLines(null);
    try {
      const data = await api.getLinesProgress(receipt.id);
      setLines(data);
    } catch (err) {
      setErrorMsg(err.message || String(err));
    }
  }

  async function beginLine(line) {
    setErrorMsg("");
    try {
      const session = await api.startImport(line.line_id);
      setActiveSession({
        session,
        expected: line.declared_quantity,
        label: line.product_name_raw,
      });
    } catch (err) {
      setErrorMsg(err.message || String(err));
    }
  }

  async function backToLines() {
    setActiveSession(null);
    const data = await api.getLinesProgress(selectedReceipt.id);
    setLines(data);
  }

  function backToReceiptList() {
    setSelectedReceipt(null);
    setLines(null);
    loadReceipts();
  }

  // ---------- Màn hình đếm ----------
  if (activeSession) {
    return (
      <main className="page-main">
        <CountingScreen
          session={activeSession.session}
          expectedQuantity={activeSession.expected}
          label={activeSession.label}
          onCancel={() => setActiveSession(null)}
          onDone={backToLines}
        />
      </main>
    );
  }

  // ---------- Danh sách dòng hàng của phiếu đã chọn ----------
  if (selectedReceipt) {
    return (
      <main className="page-main">
        <a className="backlink" onClick={backToReceiptList} style={{ cursor: "pointer" }}>
          ← Chọn phiếu khác
        </a>
        <div className="card">
          <h2>
            {selectedReceipt.receipt_code || `Phiếu #${selectedReceipt.id}`}
            {selectedReceipt.store_location ? ` — ${selectedReceipt.store_location}` : ""}
          </h2>

          {!lines && !errorMsg && <div className="empty">Đang tải…</div>}
          {errorMsg && <div className="empty" style={{ color: "var(--danger)" }}>{errorMsg}</div>}

          {lines && (
            <div className="lineList">
              {lines.length === 0 && <div className="empty">Phiếu không có dòng hàng nào</div>}
              {lines.map((line) => (
                <div className="lineCard" key={line.line_id}>
                  <div>
                    <div className="lineCard-name">{line.product_name_raw}</div>
                    <div className="lineCard-sub">
                      Cần {line.declared_quantity}
                      {line.counted_quantity != null ? ` · camera đếm ${line.counted_quantity}` : ""}
                    </div>
                  </div>
                  <div className="lineCard-actions">
                    <span className={`badge ${line.counting_status}`}>
                      {LINE_STATUS_LABEL[line.counting_status] || line.counting_status}
                    </span>
                    {(line.counting_status === "not_started" || line.counting_status === "needs_review") && (
                      <button className="tapbtn" onClick={() => beginLine(line)}>
                        Đếm
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    );
  }

  // ---------- Danh sách phiếu nhập ----------
  return (
    <main className="page-main">
      <Link to="/inout" className="backlink">
        ← Chọn Nhập / Xuất kho
      </Link>
      <div className="card">
        <div className="card-headRow">
          <h2>Chọn phiếu nhập</h2>
          <Link to="/import/scan" className="tapbtn">
            + Quét phiếu mới
          </Link>
        </div>

        {loadingReceipts && <div className="empty">Đang tải danh sách phiếu…</div>}
        {errorMsg && <div className="empty" style={{ color: "var(--danger)" }}>{errorMsg}</div>}

        {!loadingReceipts && receipts && receipts.length === 0 && (
          <div className="empty">Chưa có phiếu nhập nào — quét phiếu trên máy tính trước.</div>
        )}

        {receipts && receipts.length > 0 && (
          <div className="lineList">
            {receipts.map((r) => (
              <div className="lineCard clickable" key={r.id} onClick={() => pickReceipt(r)}>
                <div>
                  <div className="lineCard-name">{r.receipt_code || `Phiếu #${r.id}`}</div>
                  <div className="lineCard-sub">
                    {r.store_location ? `${r.store_location} · ` : ""}
                    {r.line_items?.length ?? 0} dòng hàng
                    {r.received_at ? ` · ${new Date(r.received_at).toLocaleDateString("vi-VN")}` : ""}
                  </div>
                </div>
                <div className="lineCard-actions">
                  <span className={`badge ${RECEIPT_STATUS_BADGE[r.status] || "not_started"}`}>
                    {RECEIPT_STATUS_LABEL[r.status] || r.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
