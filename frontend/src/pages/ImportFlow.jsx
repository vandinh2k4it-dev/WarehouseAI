import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, API_BASE } from "../api";
import { useToast } from "../components/Toast";
import CountingScreen from "../components/CountingScreen";
import Highlight from "../components/Highlight";
import { matchesQuery, toLocalDateKey, dateGroupLabel, formatDateTimeVN } from "../utils/search";
import "../styles/listing.css";

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
  flagged: "lỗi OCR — cần xử lý",
};
const RECEIPT_STATUS_BADGE = {
  pending_ocr: "counting",
  ocr_done: "not_started",
  reconciled: "matched",
  flagged: "needs_review",
};
// Nhóm lọc theo trạng thái hiện trên UI. Phiếu pending_ocr/flagged (chưa có
// dòng hàng sẵn sàng đếm) chỉ hiện ở tab "Tất cả" — tab "Chưa đếm" đã gỡ
// theo yêu cầu trước đó.
const RECEIPT_FILTER_TABS = [
  { key: "all", label: "Tất cả" },
  { key: "ocr_done", label: "Chờ đếm hàng", statuses: ["ocr_done"] },
  { key: "reconciled", label: "Đã xong", statuses: ["reconciled"] },
];
// Phân loại theo NGUỒN phiếu: quét ảnh (OCR) hay nhập tay.
const RECEIPT_SOURCE_FILTERS = [
  { key: "all", label: "Mọi nguồn" },
  { key: "ocr", label: "📷 Quét ảnh" },
  { key: "manual", label: "✍️ Nhập tay" },
];

// Tìm phiếu theo: mã phiếu, nơi nhập, hoặc TÊN SẢN PHẨM / mã lô của bất kỳ
// dòng hàng nào trên phiếu. Không cần gõ dấu (xem utils/search.js).
function receiptMatchesQuery(r, query) {
  if (!query.trim()) return true;
  if (matchesQuery(`${r.receipt_code || ""} ${r.store_location || ""}`, query)) return true;
  return (r.line_items ?? []).some((l) =>
    matchesQuery(`${l.product_name_raw} ${l.batch_code || ""}`, query)
  );
}

export default function ImportFlow() {
  const [receipts, setReceipts] = useState(null);
  const [loadingReceipts, setLoadingReceipts] = useState(true);
  const [selectedReceipt, setSelectedReceipt] = useState(null); // receipt object
  const [lines, setLines] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [activeSession, setActiveSession] = useState(null); // { session, expected, label }
  const [editingLineId, setEditingLineId] = useState(null);
  const [editDraft, setEditDraft] = useState({ product_name_raw: "", product_id: "", quantity: "", batch_code: "", expiry_date: "" });
  const [addingLine, setAddingLine] = useState(false);
  const [newLineDraft, setNewLineDraft] = useState({ product_name_raw: "", quantity: "", batch_code: "", expiry_date: "" });
  const [products, setProducts] = useState([]);
  // Bộ lọc danh sách phiếu nhập — lọc thuần phía client trên danh sách đã
  // tải sẵn (số lượng phiếu của 1 kho nhỏ không cần lọc phía server).
  const [receiptFilterTab, setReceiptFilterTab] = useState("all");
  const [receiptDateFilter, setReceiptDateFilter] = useState(""); // "YYYY-MM-DD"
  const [receiptSearch, setReceiptSearch] = useState(""); // tìm theo tên sản phẩm / mã phiếu / nơi nhập
  const [receiptSourceFilter, setReceiptSourceFilter] = useState("all"); // all | ocr | manual
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
      expiry_date: "",
    });
  }

  // Tạo nhanh sản phẩm mới lấy đúng tên OCR đọc được (line.product_name_raw
  // đã LƯU trong DB, không phải tên đang gõ dở trong ô sửa) rồi gán luôn
  // cho dòng này — dùng endpoint có sẵn POST /products/lines/{id}/create-and-map.
  async function createAndMapProduct(line) {
    if (
      !window.confirm(
        `Tạo sản phẩm mới tên "${line.product_name_raw}" và gán cho dòng này?`
      )
    )
      return;
    try {
      const product = await api.createProductAndMap(line.line_id);
      showToast(`Đã tạo sản phẩm "${product.name}" và gán cho dòng hàng`, "success");
      setEditingLineId(null);
      const [freshLines, freshProducts] = await Promise.all([
        api.getLinesProgress(selectedReceipt.id),
        api.listProducts(),
      ]);
      setLines(freshLines);
      setProducts(freshProducts);
    } catch (err) {
      showToast(err.message || String(err), "error");
    }
  }

  async function saveEditLine(lineId) {
    try {
      await api.updateReceiptLine(selectedReceipt.id, lineId, {
        product_name_raw: editDraft.product_name_raw,
        product_id: editDraft.product_id ? parseInt(editDraft.product_id, 10) : null,
        quantity: parseFloat(editDraft.quantity),
        batch_code: editDraft.batch_code || null,
        expiry_date: editDraft.expiry_date || null,
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
        expiry_date: newLineDraft.expiry_date || null,
      });
      setNewLineDraft({ product_name_raw: "", quantity: "", batch_code: "", expiry_date: "" });
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
          <div className="rcDetailMeta">
            📅 Nhập kho: <b>{formatDateTimeVN(selectedReceipt.received_at) || "chưa có ngày"}</b>
            {" · "}
            {selectedReceipt.source_type === "manual" ? "✍️ Nhập tay" : "📷 Quét ảnh"}
          </div>

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
                      {!editDraft.product_id && (
                        <button
                          type="button"
                          className="ghost"
                          style={{ marginTop: 6, width: "100%" }}
                          onClick={() => createAndMapProduct(line)}
                        >
                          + Tạo sản phẩm mới từ tên "{line.product_name_raw}"
                        </button>
                      )}
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
                      <label className="text-muted" style={{ fontSize: 12 }}>
                        Hạn sử dụng (để trống nếu không đổi)
                      </label>
                      <input
                        type="date"
                        value={editDraft.expiry_date}
                        onChange={(e) => setEditDraft((d) => ({ ...d, expiry_date: e.target.value }))}
                      />
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
              <label className="text-muted" style={{ fontSize: 12 }}>
                Hạn sử dụng (tuỳ chọn)
              </label>
              <input
                type="date"
                value={newLineDraft.expiry_date}
                onChange={(e) => setNewLineDraft((d) => ({ ...d, expiry_date: e.target.value }))}
              />
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
  const query = receiptSearch;
  const hasQuery = query.trim() !== "";
  const unitById = {};
  products.forEach((p) => {
    unitById[p.id] = p.unit;
  });

  // 1 phiếu có "qua" được các bộ lọc không. `skip` cho phép bỏ qua 1 nhóm bộ
  // lọc để đếm số lượng cho CHÍNH nhóm đó (vd số phiếu mỗi tab trạng thái
  // phải tính theo bộ lọc nguồn/ngày/từ khoá đang chọn, nhưng không theo tab).
  const passes = (r, skip = {}) => {
    if (!skip.tab) {
      const tab = RECEIPT_FILTER_TABS.find((t) => t.key === receiptFilterTab);
      if (tab?.statuses && !tab.statuses.includes(r.status)) return false;
    }
    if (!skip.source && receiptSourceFilter !== "all" && (r.source_type || "ocr") !== receiptSourceFilter) {
      return false;
    }
    // Đang lọc theo ngày mà phiếu chưa có ngày nhận -> toLocalDateKey trả "" -> bị loại (như trước)
    if (receiptDateFilter && toLocalDateKey(r.received_at) !== receiptDateFilter) return false;
    if (!receiptMatchesQuery(r, query)) return false;
    return true;
  };

  const allReceipts = receipts ?? [];
  const filteredReceipts = allReceipts.filter((r) => passes(r));
  const tabCount = (tab) =>
    allReceipts.filter((r) => passes(r, { tab: true }) && (!tab.statuses || tab.statuses.includes(r.status))).length;
  const sourceCount = (key) =>
    allReceipts.filter((r) => passes(r, { source: true }) && (key === "all" || (r.source_type || "ocr") === key)).length;

  const anyFilterActive =
    hasQuery || receiptDateFilter || receiptSourceFilter !== "all" || receiptFilterTab !== "all";
  function clearAllFilters() {
    setReceiptSearch("");
    setReceiptDateFilter("");
    setReceiptSourceFilter("all");
    setReceiptFilterTab("all");
  }

  // Gom phiếu theo NGÀY NHẬP KHO (giữ nguyên thứ tự mới -> cũ backend trả về
  // trong từng ngày); phiếu chưa có ngày nhập xuống cuối.
  const groups = [];
  const groupIndex = new Map();
  filteredReceipts.forEach((r) => {
    const key = toLocalDateKey(r.received_at);
    if (!groupIndex.has(key)) {
      const g = { key, items: [] };
      groupIndex.set(key, g);
      groups.push(g);
    }
    groupIndex.get(key).items.push(r);
  });
  groups.sort((a, b) => {
    if (!a.key) return 1;
    if (!b.key) return -1;
    return b.key.localeCompare(a.key);
  });

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

        <div className="searchBox">
          <span className="searchBox-icon" aria-hidden="true">
            🔍
          </span>
          <input
            type="text"
            value={receiptSearch}
            onChange={(e) => setReceiptSearch(e.target.value)}
            placeholder="Tìm sản phẩm, mã phiếu…"
            title="Tìm theo tên sản phẩm, mã phiếu, mã lô hoặc nơi nhập — không cần gõ dấu"
            aria-label="Tìm phiếu nhập"
          />
          {receiptSearch && (
            <button
              type="button"
              className="searchBox-clear"
              aria-label="Xoá từ khoá tìm kiếm"
              onClick={() => setReceiptSearch("")}
            >
              ✕
            </button>
          )}
        </div>

        <div className="filterTabs" style={{ marginTop: 0 }}>
          {RECEIPT_FILTER_TABS.map((tab) => (
            <button
              key={tab.key}
              className={`filterTab${receiptFilterTab === tab.key ? " active" : ""}`}
              onClick={() => setReceiptFilterTab(tab.key)}
            >
              {tab.label}
              <span className="filterTab-count">{tabCount(tab)}</span>
            </button>
          ))}
        </div>

        <div className="listFilters">
          <div className="filterTabs noMargin">
            {RECEIPT_SOURCE_FILTERS.map((s) => (
              <button
                key={s.key}
                className={`filterTab${receiptSourceFilter === s.key ? " active" : ""}`}
                onClick={() => setReceiptSourceFilter(s.key)}
              >
                {s.label}
                <span className="filterTab-count">{sourceCount(s.key)}</span>
              </button>
            ))}
          </div>
          <input
            type="date"
            value={receiptDateFilter}
            onChange={(e) => setReceiptDateFilter(e.target.value)}
            title="Lọc theo ngày nhập kho"
            aria-label="Lọc theo ngày nhập kho"
          />
          {receiptDateFilter && (
            <button className="ghost lineCard-smallBtn" onClick={() => setReceiptDateFilter("")}>
              Bỏ lọc ngày
            </button>
          )}
        </div>

        {loadingReceipts && <div className="empty">Đang tải danh sách phiếu…</div>}
        {errorMsg && <div className="empty" style={{ color: "var(--danger)" }}>{errorMsg}</div>}

        {!loadingReceipts && receipts && receipts.length === 0 && (
          <div className="empty">Chưa có phiếu nhập nào — quét phiếu hoặc tạo phiếu tay.</div>
        )}

        {!loadingReceipts && receipts && receipts.length > 0 && (
          <div className="listSummary">
            <span>
              Hiển thị <b>{filteredReceipts.length}</b>/{receipts.length} phiếu
            </span>
            {anyFilterActive && (
              <button className="linkBtn" onClick={clearAllFilters}>
                Xoá tất cả bộ lọc
              </button>
            )}
          </div>
        )}
        {!loadingReceipts && receipts && receipts.length > 0 && filteredReceipts.length === 0 && (
          <div className="empty">Không có phiếu nào khớp bộ lọc/từ khoá đang chọn.</div>
        )}

        {groups.map((g) => (
          <section key={g.key || "no-date"}>
            <div className="dayHeader">
              <span>📅 {dateGroupLabel(g.key)}</span>
              <span className="dayHeader-count">{g.items.length} phiếu</span>
            </div>

            {g.items.map((r) => {
              const lines = [...(r.line_items ?? [])].sort((a, b) => a.line_no - b.line_no);
              // Khi đang tìm: đưa các dòng khớp từ khoá lên trước để luôn thấy được
              // dòng hàng người dùng đang tìm, dù nó nằm ở cuối phiếu dài.
              const isMatch = (l) => hasQuery && matchesQuery(`${l.product_name_raw} ${l.batch_code || ""}`, query);
              const ordered = hasQuery ? [...lines.filter(isMatch), ...lines.filter((l) => !isMatch(l))] : lines;
              const shownLines = ordered.slice(0, 3);
              const hiddenCount = ordered.length - shownLines.length;
              const isManual = r.source_type === "manual";

              return (
                <div className="rcCard" key={r.id} onClick={() => pickReceipt(r)}>
                  <div className="rcThumb">
                    {r.image_url ? (
                      <a
                        href={`${API_BASE}${r.image_url}`}
                        target="_blank"
                        rel="noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        title="Bấm để xem ảnh phiếu gốc"
                      >
                        <img
                          src={`${API_BASE}${r.image_url}`}
                          alt={`Ảnh phiếu ${r.receipt_code || `#${r.id}`}`}
                          loading="lazy"
                        />
                      </a>
                    ) : (
                      <div className="rcThumb-empty">
                        <span>✍️</span>
                        <small>Nhập tay</small>
                      </div>
                    )}
                  </div>

                  <div className="rcBody">
                    <div className="rcHead">
                      <button type="button" className="rcTitleBtn">
                        <Highlight text={r.receipt_code || `Phiếu #${r.id}`} query={query} />
                      </button>
                      <span className={`badge ${RECEIPT_STATUS_BADGE[r.status] || "not_started"}`}>
                        {RECEIPT_STATUS_LABEL[r.status] || r.status}
                      </span>
                    </div>

                    <div className="rcMeta">
                      <span>
                        📅 Nhập kho: <b>{formatDateTimeVN(r.received_at) || "chưa có ngày"}</b>
                      </span>
                      {r.store_location && (
                        <span>
                          📍 <Highlight text={r.store_location} query={query} />
                        </span>
                      )}
                      <span>{isManual ? "✍️ Nhập tay" : "📷 Quét ảnh"}</span>
                    </div>

                    {lines.length > 0 && (
                      <ul className="rcLines">
                        {shownLines.map((l) => (
                          <li key={l.id}>
                            <span className="rcLine-name">
                              <Highlight text={l.product_name_raw} query={query} />
                              {l.product_id == null && <span className="rc-tag warn">chưa gán SP</span>}
                            </span>
                            <span className="rcLine-qty">
                              ×{Number(l.quantity).toLocaleString("vi-VN")}
                              {l.product_id != null && unitById[l.product_id] ? ` ${unitById[l.product_id]}` : ""}
                            </span>
                          </li>
                        ))}
                        {hiddenCount > 0 && <li className="rcLines-more">+{hiddenCount} sản phẩm khác…</li>}
                      </ul>
                    )}

                    <div className="rcFoot">
                      <span>{lines.length} dòng hàng</span>
                      <button className="ghost lineCard-smallBtn" onClick={(e) => handleDeleteReceipt(r, e)}>
                        Xoá
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </section>
        ))}
      </div>
    </main>
  );
}
