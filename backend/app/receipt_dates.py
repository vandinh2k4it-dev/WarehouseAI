"""So ngày nhập ghi trên phiếu với NGÀY HÔM NAY (giờ Việt Nam) — dùng khi
mở phiếu để đếm và khi đối chiếu xong từng loại hàng (app/routers/camera.py).

Lệch ngày CHỈ CẢNH BÁO, không chặn đếm — giống cách xử lý lệch số lượng
(nhân viên vẫn được làm tiếp, kiểm tra lại sau)."""
from datetime import date, datetime, timedelta, timezone

# Cố định UTC+7 thay vì zoneinfo("Asia/Ho_Chi_Minh") — Windows không có sẵn
# dữ liệu múi giờ (cần cài thêm gói tzdata), mà Việt Nam không đổi giờ mùa hè.
VN_TZ = timezone(timedelta(hours=7))


def today_vn() -> date:
    return datetime.now(VN_TZ).date()


def receipt_import_date(receipt) -> tuple[date | None, str]:
    """Ngày nhập dùng để so + nguồn lấy ngày đó: ưu tiên ngày ghi trên phiếu
    (receipt_date), phiếu cũ chưa có cột này thì lùi về ngày received_at."""
    if receipt.receipt_date:
        return receipt.receipt_date, "phiếu"
    if receipt.received_at:
        received = receipt.received_at
        if received.tzinfo is None:
            received = received.replace(tzinfo=timezone.utc)
        return received.astimezone(VN_TZ).date(), "hệ thống"
    return None, "không có"


def check_receipt_date(receipt) -> dict:
    today = today_vn()
    import_date, source = receipt_import_date(receipt)
    if import_date is None:
        return {
            "import_date": None, "today": today, "source": source, "days_diff": None,
            "matches": False, "message": "Phiếu chưa có ngày nhập — không đối chiếu được với hôm nay.",
        }
    label = "Ngày nhập trên phiếu" if source == "phiếu" else "Ngày nhập kho (phiếu không ghi ngày)"
    days_diff = (today - import_date).days  # >0: phiếu của ngày trước, <0: phiếu ghi ngày tương lai
    if days_diff == 0:
        message = f"Ngày nhập {import_date:%d/%m/%Y} khớp hôm nay."
    elif days_diff > 0:
        message = (
            f"{label} là {import_date:%d/%m/%Y}, hôm nay {today:%d/%m/%Y} — "
            f"phiếu đã cũ {days_diff} ngày, kiểm tra lại có đúng phiếu của lô hàng đang nhận không."
        )
    else:
        message = (
            f"{label} là {import_date:%d/%m/%Y}, SAU hôm nay {today:%d/%m/%Y} "
            f"{-days_diff} ngày — có thể phiếu ghi sai ngày hoặc OCR đọc nhầm."
        )
    return {
        "import_date": import_date, "today": today, "source": source, "days_diff": days_diff,
        "matches": days_diff == 0, "message": message,
    }
