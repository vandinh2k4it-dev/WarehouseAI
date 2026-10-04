import { highlightRanges } from "../utils/search";

// Hiển thị `text` và tô sáng các từ khớp với `query` (khớp không phân biệt
// hoa/thường, không cần dấu — xem utils/search.js). Không có query/không có
// chỗ khớp thì trả nguyên văn bản, không thêm thẻ thừa.
export default function Highlight({ text, query }) {
  const src = String(text ?? "");
  const ranges = highlightRanges(src, query);
  if (ranges.length === 0) return <>{src}</>;

  const parts = [];
  let cursor = 0;
  ranges.forEach(([start, end], i) => {
    if (start > cursor) parts.push(src.slice(cursor, start));
    parts.push(
      <mark className="hl" key={i}>
        {src.slice(start, end)}
      </mark>
    );
    cursor = end;
  });
  if (cursor < src.length) parts.push(src.slice(cursor));
  return <>{parts}</>;
}
