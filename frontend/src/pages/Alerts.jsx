import { useEffect, useState } from "react";
import { api } from "../api";
import {
  isPushSupported,
  getPermissionState,
  getCurrentSubscription,
  subscribeToPush,
  unsubscribeFromPush,
} from "../pushNotifications";
import SmartSearchBox from "../components/SmartSearchBox";
import Highlight from "../components/Highlight";
import { useToast } from "../components/Toast";
import { matchesQuery, toLocalDateKey, dateGroupLabel, formatDateTimeVN } from "../utils/search";
import "../styles/listing.css";
import "../styles/alerts.css";

const ALERT_TYPES = [
  { key: "discrepancy", label: "Chênh lệch", icon: "⚖️", hint: "Camera đếm khác phiếu — cần kiểm tra" },
  { key: "low_stock", label: "Sắp hết hàng", icon: "📉", hint: "Lô có tồn dưới ngưỡng cảnh báo" },
  { key: "expiring_soon", label: "Sắp hết hạn", icon: "⏰", hint: "Lô gần đến hạn sử dụng" },
];
const ALERT_TYPE_LABEL = Object.fromEntries(ALERT_TYPES.map((t) => [t.key, t.label]));
const SEVERITIES = [
  { key: "high", label: "Cao", icon: "🔴", group: "Cần xử lý ngay" },
  { key: "medium", label: "Trung bình", icon: "🟠", group: "Cần theo dõi" },
  { key: "low", label: "Thấp", icon: "🟡", group: "Mức thấp" },
];
const SEV_RANK = { high: 0, medium: 1, low: 2 };
const PAGE_SIZE = 40; // danh sách "Đã xử lý" có thể rất dài -> chỉ vẽ dần từng đợt cho nhẹ

// Cảnh báo chỉ có 1 chuỗi message — tách tên sản phẩm (nằm trong dấu nháy đơn) và hướng (nhập/xuất) ra để phân loại/tìm kiếm.
const productOf = (a) => (a.message.match(/'([^']+)'/) || [])[1] || null;
const directionOf = (a) => {
  const m = a.message.match(/^\[(IMPORT|EXPORT)\]/);
  return m ? (m[1] === "IMPORT" ? "Nhập kho" : "Xuất kho") : null;
};
const byTimeDesc = (a, b) => new Date(b.created_at) - new Date(a.created_at);

export default function Alerts() {
  const [openAlerts, setOpenAlerts] = useState(null);
  const [doneAlerts, setDoneAlerts] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [ackBusy, setAckBusy] = useState(null);
  const [bulkBusy, setBulkBusy] = useState(false);
  const [statusTab, setStatusTab] = useState("open"); // open | acknowledged
  const [typeFilter, setTypeFilter] = useState("all");
  const [sevFilter, setSevFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [limit, setLimit] = useState(PAGE_SIZE);
  const showToast = useToast();

  useEffect(() => {
    load();
  }, []);

  function load() {
    setErrorMsg("");
    // Tải cả 2 danh sách một lượt để hiện được số lượng "Đang mở" lẫn "Đã xử lý" ngay trên nút chuyển.
    Promise.all([api.listAlerts("open"), api.listAlerts("acknowledged")])
      .then(([o, d]) => {
        setOpenAlerts(o);
        setDoneAlerts(d);
      })
      .catch((err) => setErrorMsg(err.message || String(err)));
  }

  // Đổi bộ lọc luôn quay lại đợt hiển thị đầu tiên.
  const pick = (setter) => (value) => {
    setter(value);
    setLimit(PAGE_SIZE);
  };
  const clearFilters = () => {
    setTypeFilter("all");
    setSevFilter("all");
    setSearch("");
    setLimit(PAGE_SIZE);
  };

  function moveToDone(ids) {
    const set = new Set(ids);
    const moved = (openAlerts ?? []).filter((a) => set.has(a.id)).map((a) => ({ ...a, status: "acknowledged" }));
    setOpenAlerts((prev) => prev.filter((a) => !set.has(a.id)));
    setDoneAlerts((prev) => [...moved, ...(prev ?? [])]);
  }

  async function handleAck(alertId) {
    setAckBusy(alertId);
    try {
      await api.acknowledgeAlert(alertId);
      moveToDone([alertId]);
    } catch (err) {
      setErrorMsg(err.message || String(err));
    } finally {
      setAckBusy(null);
    }
  }

  const isOpenTab = statusTab === "open";
  const base = (isOpenTab ? openAlerts : doneAlerts) ?? [];

  // 1 cảnh báo có "qua" các bộ lọc không; `skip` để đếm số lượng cho CHÍNH nhóm lọc đó (vd số trên mỗi
  // thẻ loại phải tính theo mức độ + từ khoá đang chọn, nhưng không theo loại).
  const passes = (a, skip = {}) => {
    if (!skip.type && typeFilter !== "all" && a.alert_type !== typeFilter) return false;
    if (!skip.sev && sevFilter !== "all" && a.severity !== sevFilter) return false;
    if (search.trim() && !matchesQuery(`${a.message} ${ALERT_TYPE_LABEL[a.alert_type] || ""}`, search)) return false;
    return true;
  };
  const filtered = base
    .filter((a) => passes(a))
    // Tab "Đang mở": mức độ cao lên trước rồi mới tới mới nhất (hàng đợi cần xử lý). Tab "Đã xử lý": mới nhất trước.
    .sort((a, b) => (isOpenTab ? (SEV_RANK[a.severity] ?? 9) - (SEV_RANK[b.severity] ?? 9) || byTimeDesc(a, b) : byTimeDesc(a, b)));
  const typeCount = (k) => base.filter((a) => passes(a, { type: true }) && a.alert_type === k).length;
  const sevCount = (k) => base.filter((a) => passes(a, { sev: true }) && a.severity === k).length;
  const highInType = (k) => base.filter((a) => passes(a, { type: true, sev: true }) && a.alert_type === k && a.severity === "high").length;
  const totalForTypes = base.filter((a) => passes(a, { type: true })).length;
  const totalForSev = base.filter((a) => passes(a, { sev: true })).length;
  const hasExpiring = [...(openAlerts ?? []), ...(doneAlerts ?? [])].some((a) => a.alert_type === "expiring_soon");
  const shownTypes = ALERT_TYPES.filter((t) => t.key !== "expiring_soon" || hasExpiring);
  const anyFilter = typeFilter !== "all" || sevFilter !== "all" || search.trim() !== "";

  // Gợi ý tìm kiếm: các sản phẩm đang có cảnh báo (kèm số cảnh báo), nhiều nhất trước.
  const productCounts = new Map();
  base.forEach((a) => {
    const name = productOf(a);
    if (name) productCounts.set(name, (productCounts.get(name) || 0) + 1);
  });
  const searchItems = [...productCounts.entries()]
    .sort((x, y) => y[1] - x[1] || x[0].localeCompare(y[0], "vi"))
    .map(([name, n]) => ({ key: name, icon: "📦", label: name, right: `${n} cảnh báo` }));

  // Chia nhóm: "Đang mở" theo MỨC ƯU TIÊN, "Đã xử lý" theo NGÀY. Chỉ vẽ `limit` cảnh báo đầu.
  const visible = filtered.slice(0, limit);
  const groups = [];
  if (isOpenTab) {
    [...SEVERITIES, { key: "_other", label: "Khác", icon: "⚪", group: "Chưa phân mức" }].forEach((sv) => {
      const inGroup = (a) => (sv.key === "_other" ? !SEV_RANK.hasOwnProperty(a.severity) : a.severity === sv.key);
      const items = visible.filter(inGroup);
      if (items.length) groups.push({ key: sv.key, label: `${sv.icon} ${sv.group}`, total: filtered.filter(inGroup).length, items });
    });
  } else {
    const idx = new Map();
    visible.forEach((a) => {
      const k = toLocalDateKey(a.created_at);
      if (!idx.has(k)) {
        const g = { key: k, label: `📅 ${dateGroupLabel(k)}`, total: filtered.filter((x) => toLocalDateKey(x.created_at) === k).length, items: [] };
        idx.set(k, g);
        groups.push(g);
      }
      idx.get(k).items.push(a);
    });
  }

  async function handleBulkAck() {
    const ids = filtered.map((a) => a.id);
    const nDisc = filtered.filter((a) => a.alert_type === "discrepancy").length;
    const warn = nDisc > 0 ? `\n\nTrong đó có ${nDisc} cảnh báo CHÊNH LỆCH — chỉ xác nhận khi đã xử lý xong ở phiếu nhập.` : "";
    if (!window.confirm(`Đánh dấu ${ids.length} cảnh báo đang hiển thị là ĐÃ XỬ LÝ?${warn}`)) return;
    setBulkBusy(true);
    try {
      const res = await api.acknowledgeAlertsBulk(ids);
      moveToDone(ids);
      showToast(`Đã xác nhận ${res.acknowledged} cảnh báo`, "success");
    } catch (err) {
      showToast(err.message || String(err), "error");
    } finally {
      setBulkBusy(false);
    }
  }

  const loading = !openAlerts && !doneAlerts && !errorMsg;

  return (
    <main className="page-main">
      <PushNotificationBanner />

      <div className="card">
        <h2>Cảnh báo</h2>
        <div className="chips">
          <button className={`chip${isOpenTab ? " active" : ""}`} onClick={() => pick(setStatusTab)("open")}>
            Đang mở ({openAlerts?.length ?? "…"})
          </button>
          <button className={`chip${!isOpenTab ? " active" : ""}`} onClick={() => pick(setStatusTab)("acknowledged")}>
            Đã xử lý ({doneAlerts?.length ?? "…"})
          </button>
        </div>

        {errorMsg && <div className="empty" style={{ color: "var(--danger)" }}>{errorMsg}</div>}
        {loading && <div className="empty">Đang tải…</div>}

        {!loading && (
          <>
            <div className="alertSummary">
              <button
                className={`alertCard${typeFilter === "all" ? " active" : ""}`}
                onClick={() => pick(setTypeFilter)("all")}
              >
                <span className="alertCard-count">{totalForTypes}</span>
                <span className="alertCard-label">🗂️ Tất cả loại</span>
                <span className="alertCard-hint">{isOpenTab ? "Mọi cảnh báo đang mở" : "Mọi cảnh báo đã xử lý"}</span>
              </button>
              {shownTypes.map((t) => (
                <button
                  key={t.key}
                  className={`alertCard type-${t.key}${typeFilter === t.key ? " active" : ""}`}
                  onClick={() => pick(setTypeFilter)(typeFilter === t.key ? "all" : t.key)}
                >
                  <span className="alertCard-count">{typeCount(t.key)}</span>
                  <span className="alertCard-label">
                    {t.icon} {t.label}
                  </span>
                  <span className="alertCard-hint">{t.hint}</span>
                  {isOpenTab && highInType(t.key) > 0 && <span className="alertCard-high">🔴 {highInType(t.key)} mức cao</span>}
                </button>
              ))}
            </div>

            <div className="filterTabs noMargin" style={{ marginBottom: 12 }}>
              <span className="filterLabel">Mức độ:</span>
              <button className={`filterTab${sevFilter === "all" ? " active" : ""}`} onClick={() => pick(setSevFilter)("all")}>
                Tất cả<span className="filterTab-count">{totalForSev}</span>
              </button>
              {SEVERITIES.map((sv) => (
                <button
                  key={sv.key}
                  className={`filterTab${sevFilter === sv.key ? " active" : ""}`}
                  onClick={() => pick(setSevFilter)(sevFilter === sv.key ? "all" : sv.key)}
                >
                  {sv.icon} {sv.label}
                  <span className="filterTab-count">{sevCount(sv.key)}</span>
                </button>
              ))}
            </div>

            <SmartSearchBox
              value={search}
              onChange={pick(setSearch)}
              items={searchItems}
              placeholder="Tìm sản phẩm, mã lô…"
              title="Gõ tên sản phẩm hoặc mã lô để tìm cảnh báo — không cần gõ dấu"
              ariaLabel="Tìm cảnh báo"
              listLabel="Sản phẩm đang có cảnh báo"
            />

            {base.length > 0 && (
              <div className="listSummary">
                <div className="listSummary-left">
                  <span>
                    Hiển thị <b>{filtered.length}</b>/{base.length} cảnh báo
                  </span>
                  {anyFilter && (
                    <button className="linkBtn" onClick={clearFilters}>
                      Xoá bộ lọc
                    </button>
                  )}
                </div>
                {isOpenTab && filtered.length > 0 && (
                  <button className="tapbtn bulkBtn" disabled={bulkBusy} onClick={handleBulkAck}>
                    {bulkBusy ? "Đang xử lý…" : `✓ Xác nhận tất cả ${filtered.length} cảnh báo này`}
                  </button>
                )}
              </div>
            )}

            {base.length === 0 && (
              <div className="empty">{isOpenTab ? "Không có cảnh báo nào đang mở 🎉" : "Chưa có cảnh báo nào đã xử lý"}</div>
            )}
            {base.length > 0 && filtered.length === 0 && <div className="empty">Không có cảnh báo nào khớp bộ lọc đang chọn.</div>}

            {groups.map((g) => (
              <section key={g.key || "none"}>
                <div className="dayHeader">
                  <span>{g.label}</span>
                  <span className="dayHeader-count">{g.total} cảnh báo</span>
                </div>
                <div className="alertList">
                  {g.items.map((a) => {
                    const sev = SEVERITIES.find((s) => s.key === a.severity);
                    const dir = directionOf(a);
                    return (
                      <div className={`alertRow sev-${a.severity}`} key={a.id}>
                        <div>
                          <div className="alertRow-badges">
                            <span className={`badge alertType-${a.alert_type}`}>{ALERT_TYPE_LABEL[a.alert_type] || a.alert_type}</span>
                            {dir && <span className="badge dirBadge">{dir}</span>}
                            {sev && (
                              <span className={`sevTag sev-${a.severity}`}>
                                {sev.icon} {sev.label}
                              </span>
                            )}
                            <span className="alertRow-time text-muted">{formatDateTimeVN(a.created_at)}</span>
                          </div>
                          <div className="alertRow-msg">
                            <Highlight text={a.message} query={search} />
                          </div>
                        </div>
                        {isOpenTab && (
                          <button className="tapbtn" disabled={ackBusy === a.id} onClick={() => handleAck(a.id)}>
                            {ackBusy === a.id ? "…" : "Đã xử lý"}
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>
              </section>
            ))}

            {filtered.length > limit && (
              <button className="ghost moreBtn" onClick={() => setLimit((n) => n + PAGE_SIZE)}>
                Xem thêm {Math.min(PAGE_SIZE, filtered.length - limit)} cảnh báo ({filtered.length - limit} còn lại)
              </button>
            )}
          </>
        )}
      </div>
    </main>
  );
}

// Banner bật/tắt thông báo đẩy — tách riêng để Alerts.jsx không phình to,
// tự kiểm tra trạng thái đăng ký hiện tại lúc mount (đã bật từ trước, hay
// trình duyệt không hỗ trợ, hay người dùng đã từ chối quyền trước đó).
function PushNotificationBanner() {
  const [state, setState] = useState("checking"); // checking | unsupported | denied | off | on
  const [busy, setBusy] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [testMsg, setTestMsg] = useState("");

  useEffect(() => {
    checkState();
  }, []);

  async function checkState() {
    if (!isPushSupported()) {
      setState("unsupported");
      return;
    }
    const perm = getPermissionState();
    if (perm === "denied") {
      setState("denied");
      return;
    }
    const sub = await getCurrentSubscription();
    setState(sub ? "on" : "off");
  }

  async function handleEnable() {
    setBusy(true);
    setErrorMsg("");
    try {
      await subscribeToPush(navigator.userAgent.slice(0, 60));
      setState("on");
    } catch (err) {
      setErrorMsg(err.message || String(err));
      await checkState();
    } finally {
      setBusy(false);
    }
  }

  async function handleDisable() {
    setBusy(true);
    setErrorMsg("");
    try {
      await unsubscribeFromPush();
      setState("off");
    } catch (err) {
      setErrorMsg(err.message || String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleTest() {
    setTestMsg("Đang gửi…");
    try {
      const result = await api.testPush();
      setTestMsg(`Đã gửi tới ${result.sent} thiết bị (${result.failed} lỗi, ${result.removed} hết hạn đã dọn).`);
    } catch (err) {
      setTestMsg("Lỗi: " + (err.message || String(err)));
    }
  }

  if (state === "checking") return null;

  if (state === "unsupported") {
    return (
      <div className="pushBanner">
        <span>🔕 Trình duyệt này không hỗ trợ thông báo đẩy.</span>
      </div>
    );
  }

  if (state === "denied") {
    return (
      <div className="pushBanner warn">
        <span>🔕 Bạn đã chặn thông báo trước đó — vào cài đặt trình duyệt (biểu tượng ổ khoá cạnh URL) để bật lại.</span>
      </div>
    );
  }

  if (state === "on") {
    return (
      <div className="pushBanner ok">
        <span>🔔 Đã bật thông báo đẩy cho thiết bị này.</span>
        <div className="pushBanner-actions">
          <button className="ghost" onClick={handleTest} style={{ marginTop: 0 }}>
            Gửi thử
          </button>
          <button className="ghost" disabled={busy} onClick={handleDisable} style={{ marginTop: 0 }}>
            Tắt
          </button>
        </div>
        {testMsg && <div className="pushBanner-msg">{testMsg}</div>}
      </div>
    );
  }

  return (
    <div className="pushBanner">
      <span>🔔 Bật thông báo để nhận cảnh báo ngay trên điện thoại, kể cả khi không mở sẵn app.</span>
      <button className="primary" disabled={busy} onClick={handleEnable} style={{ marginTop: 10 }}>
        {busy ? "Đang bật…" : "Bật thông báo"}
      </button>
      {errorMsg && <div className="pushBanner-msg" style={{ color: "var(--danger)" }}>{errorMsg}</div>}
    </div>
  );
}
