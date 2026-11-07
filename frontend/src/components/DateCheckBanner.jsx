// Kết quả so ngày nhập trên phiếu với NGÀY HÔM NAY (backend tính, xem
// app/receipt_dates.py) — chỉ cảnh báo, không chặn đếm.
export default function DateCheckBanner({ check }) {
  if (!check) return null;
  return (
    <div className={`dateCheck ${check.matches ? "ok" : "warn"}`}>
      {check.matches ? "📅 " : "⚠️ "}
      {check.message}
    </div>
  );
}
