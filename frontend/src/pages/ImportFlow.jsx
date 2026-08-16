import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import CountingScreen from "../components/CountingScreen";

const STATUS_LABEL = {
  not_started: "chưa đếm",
  counting: "đang đếm",
  matched: "đã khớp",
  needs_review: "lệch — kiểm tra sau",
  resolved_override: "đã xử lý",
};

export default function ImportFlow() {
  const [receiptId, setReceiptId] = useState("");
  const [lines, setLines] = useState(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [activeSession, setActiveSession] = useState(null); // { session, expected, label }

  async function loadLines() {
    if (!receiptId) {
      setErrorMsg("Nhập Receipt ID trước");
      return;
    }
    setLoading(true);
    setErrorMsg("");
    try {
      const data = await api.getLinesProgress(receiptId);
      setLines(data);
    } catch (err) {
      setErrorMsg(err.message || String(err));
      setLines(null);
    } finally {
      setLoading(false);
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

  function backToList() {
    setActiveSession(null);
    loadLines();
  }

  if (activeSession) {
    return (
      <div className="page">
        <main className="page-main">
          <CountingScreen
            session={activeSession.session}
            expectedQuantity={activeSession.expected}
            label={activeSession.label}
            onCancel={() => setActiveSession(null)}
            onDone={backToList}
          />
        </main>
      </div>
    );
  }

  return (
    <div className="page">
      <header className="page-header">
        <Link to="/" className="backlink">
          ← Về trang chủ
        </Link>
        <h1>⬇ Nhập hàng</h1>
      </header>

      <main className="page-main">
        <div className="card">
          <h2>Chọn phiếu nhập</h2>
          <label>Receipt ID</label>
          <input
            type="number"
            inputMode="numeric"
            placeholder="VD: 47"
            value={receiptId}
            onChange={(e) => setReceiptId(e.target.value)}
          />
          <button className="primary" onClick={loadLines} disabled={loading}>
            {loading ? "Đang tải…" : "Tải danh sách dòng hàng"}
          </button>

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
                      {STATUS_LABEL[line.counting_status] || line.counting_status}
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
    </div>
  );
}
