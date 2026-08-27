import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import CountingScreen from "../components/CountingScreen";

const LINE_STATUS_LABEL = {
  not_started: "chưa đếm",
  counting: "đang đếm dở",
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
  const [editingLineId, setEditingLineId] = useState(null);
  const [editDraft, setEditDraft] = useState({ product_name_raw: "", quantity: "", batch_code: "" });
  const [addingLine, setAddingLine] = useState(false);
  const [newLineDraft, setNewLineDraft] = useState({ product_name_raw: "", quantity: "", batch_code: "" });

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

  async function handleDeleteReceipt(receipt, e) {
    e.stopPropagation(); // không cho nổi bọt lên onClick của cả dòng (mở phiếu)
    if (!window.confirm(`Xoá hẳn phiếu "${receipt.receipt_code || `#${receipt.id}`}"? Không thể hoàn tác.`)) return;
    try {
      await api.deleteReceipt(receipt.id);
      loadReceipts();
    } catch (err) {
      setErrorMsg(err.message || String(err));
    }
  }

  function startEditLine(line) {
    setEditingLineId(line.line_id);
    setEditDraft({
      product_name_raw: line.product_name_raw,
      quantity: String(line.declared_quantity),
      batch_code: "",
    });
  }

  async function saveEditLine(lineId) {
    try {
      await api.updateReceiptLine(selectedReceipt.id, lineId, {
        product_name_raw: editDraft.product_name_raw,
        quantity: parseFloat(editDraft.quantity),
        batch_code: editDraft.batch_code || null,
      });
      setEditingLineId(null);
      const data = await api.getLinesProgress(selectedReceipt.id);
      setLines(data);
    } catch (err) {
      setErrorMsg(err.message || String(err));
    }
  }

  async function handleDeleteLine(lineId) {
    if (!window.confirm("Xoá dòng hàng này khỏi phiếu?")) return;
    try {
      await api.deleteReceiptLine(selectedReceipt.id, lineId);
      const data = await api.getLinesProgress(selectedReceipt.id);
      setLines(data);
    } catch (err) {
      setErrorMsg(err.message || String(err));
    }
  }

  async function saveNewLine() {
    if (!newLineDraft.product_name_raw.trim() || !newLineDraft.quantity) {
      setErrorMsg("Cần nhập đủ tên sản phẩm và số lượng");
      return;
    }
    try {
      await api.addReceiptLine(selectedReceipt.id, {
        product_name_raw: newLineDraft.product_name_raw.trim(),
        quantity: parseFloat(newLineDraft.quantity),
        batch_code: newLineDraft.batch_code || null,
      });
      setNewLineDraft({ product_name_raw: "", quantity: "", batch_code: "" });
      setAddingLine(false);
      const data = await api.getLinesProgress(selectedReceipt.id);
      setLines(data);
    } catch (err) {
      setErrorMsg(err.message || String(err));
    }
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
              {lines.map((line) => {
                const isEditing = editingLineId === line.line_id;
                const canEdit = line.counting_status === "not_started"; // khớp đúng điều kiện an toàn phía backend

                if (isEditing) {
                  return (
                    <div className="lineCard lineCard-editing" key={line.line_id}>
                      <input
                        type="text"
                        value={editDraft.product_name_raw}
                        onChange={(e) => setEditDraft((d) => ({ ...d, product_name_raw: e.target.value }))}
                        placeholder="Tên sản phẩm"
                      />
                      <div className="manualLineRow-grid">
                        <input
                          type="number"
                          value={editDraft.quantity}
                          onChange={(e) => setEditDraft((d) => ({ ...d, quantity: e.target.value }))}
                          placeholder="Số lượng"
                        />
                        <input
                          type="text"
                          value={editDraft.batch_code}
                          onChange={(e) => setEditDraft((d) => ({ ...d, batch_code: e.target.value }))}
                          placeholder="Mã lô"
                        />
                      </div>
                      <div className="lineCard-actions">
                        <button className="ghost" onClick={() => setEditingLineId(null)}>
                          Huỷ
                        </button>
                        <button className="tapbtn" onClick={() => saveEditLine(line.line_id)}>
                          Lưu
                        </button>
                      </div>
                    </div>
                  );
                }

                return (
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
                      {canEdit && (
                        <>
                          <button className="ghost lineCard-smallBtn" onClick={() => startEditLine(line)}>
                            Sửa
                          </button>
                          <button className="ghost lineCard-smallBtn" onClick={() => handleDeleteLine(line.line_id)}>
                            Xoá
                          </button>
                        </>
                      )}
                      {(line.counting_status === "not_started" ||
                        line.counting_status === "needs_review" ||
                        line.counting_status === "counting") && (
                        <button className="tapbtn" onClick={() => beginLine(line)}>
                          {line.counting_status === "counting" ? "Đếm lại" : "Đếm"}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {selectedReceipt && !addingLine && (
            <button className="ghost" onClick={() => setAddingLine(true)} style={{ marginTop: 10 }}>
              + Thêm dòng hàng
            </button>
          )}

          {addingLine && (
            <div className="lineCard lineCard-editing" style={{ marginTop: 10 }}>
              <input
                type="text"
                placeholder="Tên sản phẩm"
                value={newLineDraft.product_name_raw}
                onChange={(e) => setNewLineDraft((d) => ({ ...d, product_name_raw: e.target.value }))}
              />
              <div className="manualLineRow-grid">
                <input
                  type="number"
                  placeholder="Số lượng"
                  value={newLineDraft.quantity}
                  onChange={(e) => setNewLineDraft((d) => ({ ...d, quantity: e.target.value }))}
                />
                <input
                  type="text"
                  placeholder="Mã lô (tuỳ chọn)"
                  value={newLineDraft.batch_code}
                  onChange={(e) => setNewLineDraft((d) => ({ ...d, batch_code: e.target.value }))}
                />
              </div>
              <div className="lineCard-actions">
                <button className="ghost" onClick={() => setAddingLine(false)}>
                  Huỷ
                </button>
                <button className="tapbtn" onClick={saveNewLine}>
                  Thêm dòng
                </button>
              </div>
            </div>
          )}
        </div>
      </main>
    );
  }

  // ---------- Danh sách phiếu nhập ----------
  return (
    <main className="page-main">
      <div className="card">
        <div className="card-headRow">
          <h2>Chọn phiếu nhập</h2>
          <div style={{ display: "flex", gap: 8 }}>
            <Link to="/import/create" className="tapbtn">
              ✍️ Tạo phiếu tay
            </Link>
            <Link to="/import/scan" className="tapbtn">
              + Quét phiếu mới
            </Link>
          </div>
        </div>

        {loadingReceipts && <div className="empty">Đang tải danh sách phiếu…</div>}
        {errorMsg && <div className="empty" style={{ color: "var(--danger)" }}>{errorMsg}</div>}

        {!loadingReceipts && receipts && receipts.length === 0 && (
          <div className="empty">Chưa có phiếu nhập nào — quét phiếu hoặc tạo phiếu tay.</div>
        )}

        {receipts && receipts.length > 0 && (
          <div className="lineList">
            {receipts.map((r) => (
              <div className="lineCard clickable" key={r.id} onClick={() => pickReceipt(r)}>
                <div>
                  <div className="lineCard-name">
                    {r.receipt_code || `Phiếu #${r.id}`}
                    {r.source_type === "manual" && <span className="badge not_started" style={{ marginLeft: 6 }}>tay</span>}
                  </div>
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
                  <button className="ghost lineCard-smallBtn" onClick={(e) => handleDeleteReceipt(r, e)}>
                    Xoá
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
