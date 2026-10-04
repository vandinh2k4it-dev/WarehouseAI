import { normalizeVN, queryTokens } from "../utils/search";
import "../styles/listing.css";

// Gợi ý nhanh "có phải sản phẩm này trong danh mục không?" cho 1 dòng hàng
// CHƯA gán sản phẩm — dựa trên tên đang có (vd OCR đọc "Mì Omachi", "Nước
// Aquafina"). Chọn 1 nút là gán luôn, không phải mở danh sách ra tìm. Xếp theo
// số từ trong tên khớp được với sản phẩm trong danh mục; tối đa `max` gợi ý.
export default function ProductSuggestChips({ products, text, onPick, max = 3 }) {
  const tokens = queryTokens(text).filter((t) => t.length >= 2);
  if (tokens.length === 0) return null;

  const scored = products
    .map((p) => {
      const n = normalizeVN(`${p.name} ${p.sku || ""}`);
      return { p, score: tokens.filter((t) => n.includes(t)).length };
    })
    // Chỉ gợi ý khi khớp ÍT NHẤT ~60% số từ trong tên (tên 1 từ: khớp 1; 2-3 từ:
    // khớp 2; 4 từ: khớp 3...) — tránh gợi ý nhiễu kiểu "Bánh quy bơ" cho dòng
    // "Banh keo dua" chỉ vì trùng đúng chữ "bánh".
    .filter((x) => x.score >= Math.max(1, Math.ceil(tokens.length * 0.6)))
    .sort((a, b) => b.score - a.score || a.p.name.localeCompare(b.p.name, "vi"))
    .slice(0, max);
  if (scored.length === 0) return null;

  return (
    <div className="suggestChips">
      <span className="chipsLabel">💡 Gợi ý từ danh mục:</span>
      <div className="productChips" style={{ margin: "4px 0 6px" }}>
        {scored.map(({ p }) => (
          <button type="button" key={p.id} className="filterTab" onClick={() => onPick(String(p.id))}>
            {p.name}
          </button>
        ))}
      </div>
    </div>
  );
}
