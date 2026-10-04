// Hàm dùng chung cho các ô tìm kiếm "thông minh" (danh sách phiếu nhập,
// chọn sản phẩm xuất kho, lịch sử xuất kho).
//
// Thông minh ở chỗ nào:
//  - KHÔNG phân biệt hoa/thường.
//  - KHÔNG cần gõ dấu tiếng Việt: gõ "banh quy" vẫn ra "Bánh quy bơ".
//  - Gõ nhiều từ thì phải khớp ĐỦ các từ (thứ tự tuỳ ý): "quy banh" cũng ra
//    "Bánh quy bơ".

const COMBINING_MARKS = /[\u0300-\u036f]/g;

// Chuẩn hoá 1 chuỗi: thường hoá, bỏ dấu, đ -> d, gộp khoảng trắng thừa.
// ("đ" không tách được dấu bằng normalize("NFD") nên phải đổi riêng.)
export function normalizeVN(str) {
  return String(str ?? "")
    .toLowerCase()
    .normalize("NFD")
    .replace(COMBINING_MARKS, "")
    .replace(/đ/g, "d")
    .replace(/\s+/g, " ")
    .trim();
}

// Tách câu tìm kiếm thành các từ đã chuẩn hoá.
export function queryTokens(query) {
  const n = normalizeVN(query);
  return n ? n.split(" ") : [];
}

// true nếu `text` chứa đủ mọi từ trong `query`. Query rỗng -> luôn true.
export function matchesQuery(text, query) {
  const tokens = queryTokens(query);
  if (tokens.length === 0) return true;
  const hay = normalizeVN(text);
  return tokens.every((t) => hay.includes(t));
}

// Trả về các đoạn [start, end) TRONG CHUỖI GỐC cần tô sáng cho câu tìm kiếm.
// Vì việc khớp bỏ qua dấu nên phải dựng bảng ánh xạ vị trí từ chuỗi đã chuẩn
// hoá ngược về chuỗi gốc (để tô sáng đúng chữ có dấu người dùng đang thấy).
export function highlightRanges(text, query) {
  const tokens = queryTokens(query);
  const src = String(text ?? "");
  if (tokens.length === 0 || !src) return [];

  let norm = "";
  const map = []; // map[i] = vị trí ký tự gốc của ký tự thứ i trong `norm`
  for (let i = 0; i < src.length; i++) {
    const piece = src[i]
      .toLowerCase()
      .normalize("NFD")
      .replace(COMBINING_MARKS, "")
      .replace(/đ/g, "d");
    for (let k = 0; k < piece.length; k++) {
      norm += piece[k];
      map.push(i);
    }
  }

  const ranges = [];
  for (const token of tokens) {
    let from = 0;
    for (;;) {
      const idx = norm.indexOf(token, from);
      if (idx === -1) break;
      ranges.push([map[idx], map[idx + token.length - 1] + 1]);
      from = idx + token.length;
    }
  }

  // Gộp các đoạn chồng lấn/liền nhau — và cả các đoạn chỉ cách nhau bởi khoảng
  // trắng — thành 1, để cụm từ như "Mì Hảo Hảo" được tô sáng liền mạch thay
  // vì rời rạc từng chữ.
  ranges.sort((a, b) => a[0] - b[0]);
  const merged = [];
  for (const r of ranges) {
    const last = merged[merged.length - 1];
    if (last && (r[0] <= last[1] || src.slice(last[1], r[0]).trim() === "")) {
      last[1] = Math.max(last[1], r[1]);
    } else {
      merged.push([r[0], r[1]]);
    }
  }
  return merged;
}

// ---------- Ngày giờ ----------

// "YYYY-MM-DD" theo GIỜ ĐỊA PHƯƠNG (khớp giá trị của <input type="date">).
// Trả "" nếu không có/không hợp lệ.
export function toLocalDateKey(dateLike) {
  if (!dateLike) return "";
  const d = new Date(dateLike);
  if (Number.isNaN(d.getTime())) return "";
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate()
  ).padStart(2, "0")}`;
}

// Nhãn tiêu đề nhóm theo ngày: "Hôm nay · 04/10/2026", "Hôm qua · ...", hoặc ngày thường.
export function dateGroupLabel(key) {
  if (!key) return "Chưa có ngày nhập";
  const [yy, mm, dd] = key.split("-");
  const pretty = `${dd}/${mm}/${yy}`;
  const today = toLocalDateKey(new Date());
  const yesterdayDate = new Date();
  yesterdayDate.setDate(yesterdayDate.getDate() - 1);
  if (key === today) return `Hôm nay · ${pretty}`;
  if (key === toLocalDateKey(yesterdayDate)) return `Hôm qua · ${pretty}`;
  return pretty;
}

// "14:32 04/10/2026" — giờ + ngày đầy đủ. Trả "" nếu không có/không hợp lệ.
export function formatDateTimeVN(dateLike) {
  if (!dateLike) return "";
  const d = new Date(dateLike);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}
