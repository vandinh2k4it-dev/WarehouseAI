import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, API_BASE } from "../api";
import { useToast } from "../components/Toast";
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
  const [editDraft, setEditDraft] = useState({ product_name_raw: "", product_id: "", quantity: "", batch_code: "" });
  const [addingLine, setAddingLine] = useState(false);
  const [newLineDraft, setNewLineDraft] = useState({ product_name_raw: "", quantity: "", batch_code: "" });
  const [products, setProducts] = useState([]);
  // Form "Xác nhận ghi đè" cho dòng đang lệch (needs_review) — mở theo từng
  // dòng 1 lúc (line_id đang mở), bắt buộc phải ghi lý do trước khi gửi,
  // khớp đúng validate bắt buộc override_note ở backend (xem camera.py).
  const [overridingLineId, setOverridingLineId] = useState(null);
  const [overrideNote, setOverrideNote] = useState("");
  const [overrideSubmitting, setOverrideSubmitting] = useState(false);
  const showToast = useToast();

  useEffect(() => {
    api.listProducts().then(setProducts).catch(() => {});
  }, []);

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
      showToast(err.message || String(err), "error");
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
      showToast("Đã xoá phiếu", "success");
      loadReceipts();
    } catch (err) {
      showToast(err.message || String(err), "error");
    }
  }

  function startEditLine(line) {
    setEditingLineId(line.line_id);
    setEditDraft({
      product_name_raw: line.product_name_raw,
      product_id: line.product_id != null ? String(line.product_id) : "",
      quantity: String(line.declared_quantity),
      batch_code: "",
    });
  }

  async function saveEditLine(lineId) {
    try {
      await api.updateReceiptLine(selectedReceipt.id, lineId, {
        product_name_raw: editDraft.product_name_raw,
        product_id: editDraft.product_id ? parseInt(editDraft.product_id, 10) : null,
        quantity: parseFloat(editDraft.quantity),
        batch_code: editDraft.batch_code || null,
      });
      setEditingLineId(null);
      showToast("Đã lưu dòng hàng", "success");
      const data = await api.getLinesProgress(selectedReceipt.id);
      setLines(data);
    } catch (err) {
      showToast(err.message || String(err), "error");
    }
  }

  async function handleDeleteLine(lineId) {
    if (!window.confirm("Xoá dòng hàng này khỏi phiếu?")) return;
    try {
      await api.deleteReceiptLine(selectedReceipt.id, lineId);
      showToast("Đã xoá dòng hàng", "success");
      const data = await api.getLinesProgress(selectedReceipt.id);
      setLines(data);
    } catch (err) {
      showToast(err.message || String(err), "error");
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
      showToast("Đã thêm dòng hàng", "success");
      const data = await api.getLinesProgress(selectedReceipt.id);
      setLines(data);
    } catch (err) {
      showToast(err.message || String(err), "error");
    }
  }

  // Xử lý dòng đang lệch (needs_review): xác nhận ghi đè theo số camera thực
  // tế đã đếm được — bắt buộc ghi rõ lý do, khớp validate bắt buộc của
  // backend (POST /camera-sessions/{id}/resolve, action=override).
  function startOverride(line) {
    setOverridingLineId(line.line_id);
    setOverrideNote("");
  }

  async function submitOverride(line) {
    if (!overrideNote.trim()) {
      showToast("Cần ghi rõ lý do trước khi xác nhận ghi đè", "error");
      return;
    }
    setOverrideSubmitting(true);
    try {
      await api.resolveSegment(line.latest_session_id, "override", overrideNote.trim());
      showToast(`Đã ghi đè — cập nhật kho theo số camera (${line.counted_quantity})`, "success");
      setOverridingLineId(null);
      setOverrideNote("");
      const data = await api.getLinesProgress(selectedReceipt.id);
      setLines(data);
    } catch (err) {
      showToast(err.message || String(err), "error");
    } finally {
      setOverrideSubmitting(false);
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

          {selectedReceipt.image_url && (
            <div className="receiptImage">
              <div className="receiptImage-label">📷 Ảnh phiếu gốc đã quét</div>
              <a href={`${API_BASE}${selectedReceipt.image_url}`} target="_blank" rel="noreferrer">
                <img src={`${API_BASE}${selectedReceipt.image_url}`} alt="Ảnh phiếu nhập gốc" className="receiptImage-img" />
              </a>
            </div>
          )}

          {!lines && !errorMsg && <div className="empty">Đang tải…</div>}
          {errorMsg && <div className="empty" style={{ color: "var(--danger)" }}>{errorMsg}</div>}

          {lines && lines.length > 0 && (() => {
            const doneCount = lines.filter(
              (l) => l.counting_status === "matched" || l.counting_status === "resolved_override"
            ).length;
            const unmappedCount = lines.filter((l) => l.product_id == null).length;
            return (
              <div className="progressSummary">
                <div className="progressSummary-bar">
                  <div
                    className="progressSummary-fill"
                    style={{ width: `${Math.round((doneCount / lines.length) * 100)}%` }}
                  />
                </div>
                <div className="progressSummary-text">
                  {doneCount}/{lines.length} dòng đã xong
                  {unmappedCount > 0 && (
                    <span className="stockHint-warn" style={{ marginLeft: 8 }}>
                      ⚠ {unmappedCount} dòng chưa gán sản phẩm
                    </span>
                  )}
                </div>
              </div>
            );
          })()}

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
                      <label className="text-muted" style={{ fontSize: 12 }}>
                        Sản phẩm trong danh mục
                      </label>
                      <select
                        value={editDraft.product_id}
                        onChange={(e) => {
                          const val = e.target.value;
                          const p = products.find((pp) => pp.id === parseInt(val, 10));
                          setEditDraft((d) => ({
                            ...d,
                            product_id: val,
                            product_name_raw: p ? p.name : d.product_name_raw,
                          }));
                        }}
                      >
                        <option value="">— Chưa có trong danh mục —</option>
                        {products.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.name}
                            {p.sku ? ` (${p.sku})` : ""}
                          </option>
                        ))}
                      </select>
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

                const isOverriding = overridingLineId === line.line_id;

                return (
                  <div className="lineCard" key={line.line_id} style={isOverriding ? { flexDirection: "column", alignItems: "stretch" } : undefined}>
                    <div>
                      <div className="lineCard-name">{line.product_name_raw}</div>
                      <div className="lineCard-sub">
                        Cần {line.declared_quantity}
                        {line.counted_quantity != null ? ` · camera đếm ${line.counted_quantity}` : ""}
                      </div>
                      {line.product_id == null && (
                        <div className="stockHint-warn" style={{ marginTop: 4, fontSize: 12 }}>
                          ⚠ Chưa gán sản phẩm — cần sửa dòng này và chọn sản phẩm trước khi đếm
                        </div>
                      )}
                    </div>

                    {/* Form ghi đè — chỉ mở khi bấm "Xác nhận ghi đè" ở dòng needs_review */}
                    {isOverriding ? (
                      <div className="lineCard-editing" style={{ marginTop: 8 }}>
                        <label className="text-muted" style={{ fontSize: 12 }}>
                          Lý do ghi đè (bắt buộc) — vd "đã kiểm lại bằng tay, số camera đúng"
                        </label>
                        <input
                          type="text"
                          value={overrideNote}
                          onChange={(e) => setOverrideNote(e.target.value)}
                          placeholder="Nhập lý do..."
                          autoFocus
                        />
                        <div className="lineCard-actions">
                          <button className="ghost" onClick={() => setOverridingLineId(null)} disabled={overrideSubmitting}>
                            Huỷ
                          </button>
                          <button className="tapbtn" onClick={() => submitOverride(line)} disabled={overrideSubmitting}>
                            {overrideSubmitting ? "Đang lưu…" : `Xác nhận ghi đè còn ${line.counted_quantity}`}
                          </button>
                        </div>
                      </div>
                    ) : (
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
                        {line.counting_status === "needs_review" && (
                          <button className="ghost lineCard-smallBtn" onClick={() => startOverride(line)}>
                            Xác nhận ghi đè
                          </button>
                        )}
                        {(line.counting_status === "not_started" ||
                          line.counting_status === "needs_review" ||
                          line.counting_status === "counting") && (
                          <button
                            className="tapbtn"
                            onClick={() => beginLine(line)}
                            disabled={line.product_id == null}
                            title={line.product_id == null ? "Cần gán sản phẩm trước khi đếm" : undefined}
                          >
                            {line.counting_status === "counting" ? "Đếm lại" : "Đếm"}
                          </button>
                        )}
                      </div>
                    )}
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
