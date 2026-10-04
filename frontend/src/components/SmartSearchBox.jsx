import { useEffect, useId, useMemo, useRef, useState } from "react";
import { matchesQuery, normalizeVN } from "../utils/search";
import Highlight from "./Highlight";
import "../styles/listing.css";

// Ô tìm kiếm có GỢI Ý (gõ tên -> hiện danh sách để chọn), cùng kiểu với ô chọn
// sản phẩm ở trang Xuất kho. Khác ProductSearchSelect ở chỗ: đây là ô LỌC chữ
// tự do — người dùng không chọn gợi ý nào mà cứ gõ thì danh sách bên dưới vẫn
// lọc theo chữ đang gõ; chọn 1 gợi ý chỉ là điền nhanh đúng tên đó vào ô.
//
// Props:
//  - value / onChange(text): chữ đang gõ (do trang cha giữ)
//  - items: [{ key, label, sub?, right?, icon? }] — toàn bộ gợi ý có thể có; component
//    tự lọc không dấu + xếp hạng (bắt đầu bằng từ gõ -> chứa từ gõ -> khớp phụ)
//  - onPick(item): tuỳ chọn; mặc định điền item.label vào ô
export default function SmartSearchBox({
  value,
  onChange,
  items = [],
  onPick,
  placeholder,
  title,
  ariaLabel,
  maxItems = 8,
  listLabel = "Gợi ý",
  style,
}) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1); // -1 = chưa dùng phím mũi tên chọn gợi ý nào
  const wrapRef = useRef(null);
  const inputRef = useRef(null);
  const listId = useId();

  const matches = useMemo(() => {
    const first = normalizeVN(value).split(" ")[0] || "";
    return items
      .map((it, i) => ({ it, i }))
      .filter(({ it }) => matchesQuery(`${it.label} ${it.sub || ""}`, value))
      .map(({ it, i }) => {
        const n = normalizeVN(it.label);
        return { it, i, rank: !first ? 0 : n.startsWith(first) ? 0 : n.includes(first) ? 1 : 2 };
      })
      .sort((a, b) => a.rank - b.rank || a.i - b.i)
      .slice(0, maxItems)
      .map((x) => x.it);
  }, [items, value, maxItems]);

  useEffect(() => {
    function onOutside(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onOutside);
    document.addEventListener("touchstart", onOutside);
    return () => {
      document.removeEventListener("mousedown", onOutside);
      document.removeEventListener("touchstart", onOutside);
    };
  }, []);

  useEffect(() => {
    if (!open || active < 0) return;
    const el = wrapRef.current?.querySelector('[data-active="true"]');
    if (el && el.scrollIntoView) el.scrollIntoView({ block: "nearest" });
  }, [active, open]);

  function pick(it) {
    if (onPick) onPick(it);
    else onChange(it.label);
    setOpen(false);
    setActive(-1);
  }

  function handleKeyDown(e) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!open) setOpen(true);
      else setActive((i) => Math.min(i + 1, matches.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, -1));
    } else if (e.key === "Enter") {
      if (open && active >= 0 && matches[active]) {
        e.preventDefault();
        pick(matches[active]);
      } else {
        setOpen(false); // Enter khi chưa chọn gợi ý nào: giữ nguyên chữ đã gõ, chỉ đóng danh sách
      }
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  const showList = open && matches.length > 0;

  return (
    <div className="smartSearch" ref={wrapRef} style={style}>
      <div className="searchBox" style={{ marginBottom: 0 }}>
        <span className="searchBox-icon" aria-hidden="true">
          🔍
        </span>
        <input
          ref={inputRef}
          type="text"
          role="combobox"
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-label={ariaLabel}
          aria-activedescendant={showList && active >= 0 ? `${listId}-opt-${active}` : undefined}
          autoComplete="off"
          value={value}
          placeholder={placeholder}
          title={title}
          onChange={(e) => {
            onChange(e.target.value);
            setOpen(true);
            setActive(-1);
          }}
          onFocus={() => setOpen(true)}
          onClick={() => setOpen(true)}
          onKeyDown={handleKeyDown}
        />
        {value && (
          <button
            type="button"
            className="searchBox-clear"
            aria-label="Xoá từ khoá tìm kiếm"
            onClick={() => {
              onChange("");
              setActive(-1);
              setOpen(true);
              inputRef.current?.focus();
            }}
          >
            ✕
          </button>
        )}
      </div>

      {showList && (
        <ul className="combo-list" role="listbox" id={listId}>
          <li className="combo-head" role="presentation">
            {value.trim() ? "Gợi ý khớp" : listLabel}
          </li>
          {matches.map((it, i) => (
            <li
              key={it.key}
              id={`${listId}-opt-${i}`}
              role="option"
              aria-selected={i === active}
              data-active={i === active}
              className={`combo-item${i === active ? " active" : ""}`}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => pick(it)}
              onMouseEnter={() => setActive(i)}
            >
              <span className="combo-name">
                {it.icon && <span className="combo-icon2">{it.icon}</span>}
                <Highlight text={it.label} query={value} />
                {it.sub && (
                  <span className="combo-sku">
                    <Highlight text={it.sub} query={value} />
                  </span>
                )}
              </span>
              {it.right && <span className="combo-stock neutral">{it.right}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
