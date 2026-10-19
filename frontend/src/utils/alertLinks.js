// Đích "chính" khi bấm thẳng vào dòng chữ của 1 cảnh báo (dữ liệu liên kết do GET /alerts trả về):
// - cảnh báo chênh lệch nhập kho  -> mở phiếu nhập, tô sáng đúng dòng hàng bị lệch
// - cảnh báo theo lô (sắp hết/hết hạn) -> mở sản phẩm, tô sáng lô
// - còn lại có sản phẩm            -> mở sản phẩm
// Không có liên kết nào (dữ liệu gốc đã bị xoá) -> trả null, dòng chữ chỉ là chữ thường.
export function alertTarget(a) {
  if (a.receipt_id) {
    return `/import?receipt=${a.receipt_id}${a.receipt_line_id ? `&line=${a.receipt_line_id}` : ""}`;
  }
  if (a.product_id) {
    return `/products?product=${a.product_id}${a.batch_code ? `&batch=${encodeURIComponent(a.batch_code)}` : ""}`;
  }
  return null;
}
