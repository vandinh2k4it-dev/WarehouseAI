// Hiển thị markdown (kiểu Gemini hay trả về) thành giao diện đẹp: tiêu đề, **đậm**, *nghiêng*,
// `mã`, danh sách (kể cả LỒNG nhau), bảng, trích dẫn, khối mã, đường kẻ, liên kết.
//
// AN TOÀN: KHÔNG dùng dangerouslySetInnerHTML — mọi chữ đều đi qua React (tự escape), nên chuỗi
// như "<script>…" hay "<img onerror=…>" trong câu trả lời chỉ hiện ra như chữ thường, không chạy.
// Liên kết chỉ nhận http/https. Cố ý KHÔNG hiểu _gạch_dưới_ là nghiêng để không làm hỏng mã/tên có dấu "_".

const INLINE_RE = /(`[^`\n]+`)|(\*\*[^*\n]+?\*\*)|(__[^_\n]+?__)|(\*[^*\s][^*\n]*?\*)|(\[[^\]\n]+\]\((https?:\/\/[^\s)]+)\))/;

function renderInline(text, key = "i") {
  const out = [];
  let rest = text;
  let n = 0;
  while (rest) {
    const m = INLINE_RE.exec(rest);
    if (!m) {
      out.push(rest);
      break;
    }
    if (m.index > 0) out.push(rest.slice(0, m.index));
    const tok = m[0];
    const k = `${key}-${n++}`;
    if (m[1]) out.push(<code key={k}>{tok.slice(1, -1)}</code>);
    else if (m[2] || m[3]) out.push(<strong key={k}>{renderInline(tok.slice(2, -2), k)}</strong>);
    else if (m[4]) out.push(<em key={k}>{renderInline(tok.slice(1, -1), k)}</em>);
    else
      out.push(
        <a key={k} href={m[6]} target="_blank" rel="noopener noreferrer">
          {tok.slice(1, tok.indexOf("]"))}
        </a>
      );
    rest = rest.slice(m.index + tok.length);
  }
  return out;
}

const LIST_RE = /^(\s*)([*+-]|\d+[.)])\s+(.*)$/;
const HR_RE = /^\s*([-*_])(\s*\1){2,}\s*$/;
const HEADING_RE = /^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$/;
const FENCE_RE = /^\s*```/;
const TABLE_SEP_RE = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$/;

const splitRow = (line) =>
  line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((c) => c.trim());

// Dựng cây danh sách lồng nhau từ các dòng "* …" / "1. …" theo độ thụt lề.
function buildList(items) {
  const root = { ordered: /\d/.test(items[0].marker), start: parseInt(items[0].marker, 10) || 1, items: [] };
  const stack = [{ indent: items[0].indent, list: root }];
  for (const it of items) {
    while (stack.length > 1 && it.indent < stack[stack.length - 1].indent) stack.pop();
    const top = stack[stack.length - 1];
    if (it.indent > top.indent && top.list.items.length > 0) {
      const parent = top.list.items[top.list.items.length - 1];
      const child = { ordered: /\d/.test(it.marker), start: parseInt(it.marker, 10) || 1, items: [] };
      parent.children = child;
      stack.push({ indent: it.indent, list: child });
      child.items.push({ text: it.text });
    } else {
      top.list.items.push({ text: it.text });
    }
  }
  return root;
}

function parseBlocks(src) {
  const lines = src.replace(/\r\n?/g, "\n").split("\n");
  const blocks = [];
  let i = 0;
  const startsBlock = (l, next) =>
    HEADING_RE.test(l) || LIST_RE.test(l) || FENCE_RE.test(l) || /^\s*>/.test(l) || HR_RE.test(l) || (l.includes("|") && next !== undefined && TABLE_SEP_RE.test(next));

  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i++;
      continue;
    }
    if (FENCE_RE.test(line)) {
      const buf = [];
      i++;
      while (i < lines.length && !FENCE_RE.test(lines[i])) buf.push(lines[i++]);
      i++;
      blocks.push({ type: "code", text: buf.join("\n") });
      continue;
    }
    const h = line.match(HEADING_RE);
    if (h) {
      blocks.push({ type: "heading", level: h[1].length, text: h[2] });
      i++;
      continue;
    }
    if (HR_RE.test(line) && !LIST_RE.test(line.replace(/^\s*/, "") + " x")) {
      blocks.push({ type: "hr" });
      i++;
      continue;
    }
    if (line.includes("|") && i + 1 < lines.length && TABLE_SEP_RE.test(lines[i + 1])) {
      const head = splitRow(line);
      i += 2;
      const rows = [];
      while (i < lines.length && lines[i].trim() && lines[i].includes("|")) rows.push(splitRow(lines[i++]));
      blocks.push({ type: "table", head, rows });
      continue;
    }
    if (/^\s*>/.test(line)) {
      const buf = [];
      while (i < lines.length && /^\s*>/.test(lines[i])) buf.push(lines[i++].replace(/^\s*>\s?/, ""));
      blocks.push({ type: "quote", text: buf.join("\n") });
      continue;
    }
    if (LIST_RE.test(line)) {
      const items = [];
      while (i < lines.length) {
        const m = lines[i].match(LIST_RE);
        if (m) {
          items.push({ indent: m[1].replace(/\t/g, "    ").length, marker: m[2], text: m[3] });
          i++;
        } else if (!lines[i].trim()) {
          // dòng trống giữa các mục danh sách (kiểu "danh sách thưa") vẫn thuộc cùng 1 danh sách
          let j = i;
          while (j < lines.length && !lines[j].trim()) j++;
          if (j < lines.length && LIST_RE.test(lines[j])) i = j;
          else break;
        } else if (/^\s{2,}\S/.test(lines[i]) && items.length) {
          items[items.length - 1].text += " " + lines[i].trim(); // dòng tiếp nối của mục trước
          i++;
        } else break;
      }
      blocks.push({ type: "list", list: buildList(items) });
      continue;
    }
    const buf = [];
    while (i < lines.length && lines[i].trim() && !(buf.length && startsBlock(lines[i], lines[i + 1]))) buf.push(lines[i++]);
    blocks.push({ type: "para", text: buf.join("\n") });
  }
  return blocks;
}

function renderList(list, key) {
  const Tag = list.ordered ? "ol" : "ul";
  return (
    <Tag key={key} start={list.ordered && list.start !== 1 ? list.start : undefined}>
      {list.items.map((it, idx) => (
        <li key={idx}>
          {renderInline(it.text, `${key}-${idx}`)}
          {it.children && renderList(it.children, `${key}-${idx}c`)}
        </li>
      ))}
    </Tag>
  );
}

function renderBlock(b, idx) {
  const key = `b${idx}`;
  switch (b.type) {
    case "heading": {
      const cls = b.level <= 1 ? "md-h1" : b.level === 2 ? "md-h2" : "md-h3";
      return (
        <div key={key} className={cls} role="heading" aria-level={Math.min(b.level + 2, 6)}>
          {renderInline(b.text, key)}
        </div>
      );
    }
    case "hr":
      return <hr key={key} />;
    case "code":
      return (
        <pre key={key}>
          <code>{b.text}</code>
        </pre>
      );
    case "quote":
      return <blockquote key={key}>{renderInline(b.text, key)}</blockquote>;
    case "list":
      return renderList(b.list, key);
    case "table":
      return (
        <div key={key} className="md-tableWrap">
          <table>
            <thead>
              <tr>
                {b.head.map((c, i) => (
                  <th key={i}>{renderInline(c, `${key}h${i}`)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {b.rows.map((r, ri) => (
                <tr key={ri}>
                  {r.map((c, ci) => (
                    <td key={ci}>{renderInline(c, `${key}r${ri}c${ci}`)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    default:
      return (
        <p key={key}>
          {b.text.split("\n").map((ln, i, arr) => (
            <span key={i}>
              {renderInline(ln, `${key}l${i}`)}
              {i < arr.length - 1 && <br />}
            </span>
          ))}
        </p>
      );
  }
}

export default function Markdown({ text }) {
  return <div className="md">{parseBlocks(String(text ?? "")).map(renderBlock)}</div>;
}
