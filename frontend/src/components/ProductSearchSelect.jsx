import { useEffect, useId, useMemo, useRef, useState } from "react";
import { matchesQuery, normalizeVN } from "../utils/search";
import Highlight from "./Highlight";
import "../styles/listing.css";

const MAX_RESULTS = 50; // danh sách dài hơn thì nhắc người dùng gõ thêm cho gọn

// Ô chọn sản phẩm kiểu "gõ tên -> chọn từ danh sách" (thay cho <select> cuộn
// dài). Gõ không dấu vẫn ra (xem utils/search.js), hiện luôn tồn kho cạnh
// từng sản phẩm, dùng được bằng bàn phím (↑ ↓ Enter Esc) lẫn chạm trên điện
// thoại.
//
// Props:
//  - products: danh sách sản phẩm [{id, name, sku, category, unit, low_stock_threshold}]
//  - value:    id sản phẩm đang chọn dạng chuỗi ("" = chưa chọn) — cùng kiểu
//              với <select value> cũ nên code gọi không phải đổi gì thêm.
//  - onChange: (idString) => void
//  - stockOf:  (productId) => number — để hiện "còn X" (tuỳ chọn)
export default function ProductSearchSelect({
  products,
  value,
  onChange,
  stockOf,
  id,
  placeholder = "Gõ tên hoặc mã sản phẩm…",
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const wrapRef = useRef(null);
  const listRef = useRef(null);
  const inputRef = useRef(null);
  const listId = useId();

  const selected = useMemo(
    () => products.find((p) => String(p.id) === String(value)) || null,
    [products, value]
  );

  // Khi có sản phẩm được chọn (kể cả do code ngoài đặt), hiện tên nó trong ô.
  useEffect(() => {
    if (selected) setQuery(selected.name);
  }, [selected]);

  // Đang "tìm" nghĩa là chữ trong ô khác với tên sản phẩm đã chọn. Vừa chọn
  // xong, mở lại danh sách thì phải hiện ĐỦ danh sách chứ không chỉ 1 món đã chọn.
  const searching = !selected || query !== selected.name;
  const filterText = searching ? query : "";

  const results = useMemo(() => {
    const q = normalizeVN(filterText);
    const first = q.split(" ")[0] || "";
    return products
      .filter((p) => matchesQuery(`${p.name} ${p.sku || ""} ${p.category || ""}`, filterText))
      .map((p) => {
        const n = normalizeVN(p.name);
        // Xếp hạng: tên bắt đầu bằng từ gõ -> 0, tên chứa từ gõ -> 1, còn lại (khớp theo mã/nhóm) -> 2
        const rank = !first ? 0 : n.startsWith(first) ? 0 : n.includes(first) ? 1 : 2;
        return { p, rank, n };
      })
      .sort((a, b) => a.rank - b.rank || a.n.localeCompare(b.n, "vi"))
      .map((x) => x.p);
  }, [products, filterText]);

  const shown = results.slice(0, MAX_RESULTS);

  // Bấm ra ngoài thì đóng danh sách; nếu đã chọn sản phẩm mà đang gõ dở thì trả lại tên đã chọn.
  useEffect(() => {
    function onOutside(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setOpen(false);
        if (selected) setQuery(selected.name);
      }
    }
    document.addEventListener("mousedown", onOutside);
    document.addEventListener("touchstart", onOutside);
    return () => {
      document.removeEventListener("mousedown", onOutside);
      document.removeEventListener("touchstart", onOutside);
    };
  }, [selected]);

  // Giữ dòng đang tô sáng (bằng phím mũi tên) luôn nằm trong vùng nhìn thấy.
  useEffect(() => {
    if (!open) return;
    const el = listRef.current?.querySelector('[data-active="true"]');
    if (el && el.scrollIntoView) el.scrollIntoView({ block: "nearest" });
  }, [active, open]);

  function pick(p) {
    onChange(String(p.id));
    setQuery(p.name);
    setOpen(false);
  }

  function handleType(e) {
    setQuery(e.target.value);
    setOpen(true);
    setActive(0);
    if (selected) onChange(""); // sửa chữ sau khi đã chọn = bỏ lựa chọn cũ
  }

  function clearAll() {
    setQuery("");
    onChange("");
    setOpen(true);
    setActive(0);
    inputRef.current?.focus();
  }

  function handleKeyDown(e) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!open) setOpen(true);
      else setActive((i) => Math.min(i + 1, Math.max(shown.length - 1, 0)));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      if (open && shown[active]) {
        e.preventDefault();
        pick(shown[active]);
      }
    } else if (e.key === "Escape") {
      setOpen(false);
      if (selected) setQuery(selected.name);
    }
  }

  return (
    <div className="combo" ref={wrapRef}>
      <div className="combo-inputWrap">
        <span className="combo-icon" aria-hidden="true">
          🔍
        </span>
        <input
          ref={inputRef}
          id={id}
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={open && shown[active] ? `${listId}-opt-${shown[active].id}` : undefined}
          autoComplete="off"
          value={query}
          placeholder={placeholder}
          onChange={handleType}
          onFocus={(e) => {
            setOpen(true);
            if (selected) e.target.select();
          }}
          // Sau khi chọn xong ô VẪN đang giữ focus, bấm lại vào ô sẽ không phát
          // sinh sự kiện focus nữa -> phải mở lại danh sách bằng onClick, nếu
          // không người dùng muốn đổi sản phẩm mà bấm vào ô thấy "không có gì xảy ra".
          onClick={(e) => {
            setOpen(true);
            if (selected) e.target.select();
          }}
          onKeyDown={handleKeyDown}
        />
        {query && (
          <button type="button" className="combo-clear" aria-label="Xoá lựa chọn" onClick={clearAll}>
            ✕
          </button>
        )}
      </div>

      {open && (
        <ul className="combo-list" role="listbox" id={listId} ref={listRef}>
          {shown.length === 0 && (
            <li className="combo-empty">Không tìm thấy sản phẩm nào khớp “{query}”</li>
          )}
          {shown.map((p, i) => {
            const stock = stockOf ? stockOf(p.id) : null;
            let stockClass = "";
            let stockText = "";
            if (stock !== null) {
              if (stock <= 0) {
                stockClass = "out";
                stockText = "Hết hàng";
              } else {
                stockClass = stock <= (p.low_stock_threshold ?? 0) ? "low" : "";
                stockText = `Còn ${stock.toLocaleString("vi-VN")} ${p.unit || ""}`.trim();
              }
            }
            const isActive = i === active;
            return (
              <li
                key={p.id}
                id={`${listId}-opt-${p.id}`}
                role="option"
                aria-selected={String(p.id) === String(value)}
                data-active={isActive}
                className={`combo-item${isActive ? " active" : ""}${
                  String(p.id) === String(value) ? " selected" : ""
                }`}
                onMouseDown={(e) => e.preventDefault()} // giữ focus ở ô nhập, tránh đóng danh sách trước khi kịp chọn
                onClick={() => pick(p)}
                onMouseEnter={() => setActive(i)}
              >
                <span className="combo-name">
                  <Highlight text={p.name} query={filterText} />
                  {p.sku && (
                    <span className="combo-sku">
                      Mã: <Highlight text={p.sku} query={filterText} />
                    </span>
                  )}
                </span>
                {stock !== null && <span className={`combo-stock ${stockClass}`}>{stockText}</span>}
              </li>
            );
          })}
          {results.length > MAX_RESULTS && (
            <li className="combo-more">
              …và {results.length - MAX_RESULTS} sản phẩm khác — gõ thêm để lọc gọn hơn
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
