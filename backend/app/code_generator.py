"""Sinh mã tự động dạng "TIỀN TỐ + số tăng dần, đệm 0" (vd PN0001, PN0002...)
dùng chung cho phiếu nhập, phiếu xuất, phiên đếm — thay cho việc phải tự gõ
tay hoặc để trống mã, đảm bảo mọi phiếu/phiên đều có mã dễ đọc, dễ tra cứu,
tăng dần đúng thứ tự tạo ra (không phải ID tự tăng thô của database).

CÁCH HOẠT ĐỘNG: tìm mã LỚN NHẤT hiện có cùng tiền tố, tách lấy phần số, +1,
đệm lại đủ số chữ số. KHÔNG dùng bảng đếm (sequence) riêng — đơn giản, đủ
dùng cho quy mô demo khóa luận (không có nhiều người dùng đồng thời tạo
phiếu cùng lúc, rủi ro trùng mã gần như không xảy ra trong thực tế demo).
"""
import re

from sqlalchemy import func, update
from sqlalchemy.orm import Session


def generate_next_code(db: Session, model, code_column_name: str, prefix: str, pad_width: int = 4) -> str:
    """Sinh mã tiếp theo cho model/cột chỉ định.

    Ví dụ: generate_next_code(db, models.ImportReceipt, "receipt_code", "PN")
    -> nếu đã có PN0001, PN0002 -> trả về "PN0003". Nếu chưa có mã nào cùng
    tiền tố "PN" -> trả về "PN0001" (bắt đầu từ đầu).
    """
    column = getattr(model, code_column_name)
    # Lấy TẤT CẢ mã cùng tiền tố (không dùng MAX() trực tiếp trên chuỗi vì
    # sắp xếp chuỗi không đúng thứ tự số học khi số chữ số khác nhau về sau
    # này, dù hiện tại luôn đệm cùng độ dài — làm chắc chắn bằng cách tự
    # parse số lớn nhất trong Python thay vì tin vào ORDER BY chuỗi của SQL).
    existing_codes = (
        db.query(column)
        .filter(column.isnot(None))
        .filter(column.like(f"{prefix}%"))
        .all()
    )
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    max_num = 0
    for (code,) in existing_codes:
        if not code:
            continue
        m = pattern.match(code)
        if m:
            max_num = max(max_num, int(m.group(1)))

    next_num = max_num + 1
    return f"{prefix}{str(next_num).zfill(pad_width)}"


def is_auto_code(code: str | None, prefix: str) -> bool:
    """True nếu `code` đúng dạng mã tự sinh của hệ thống (vd PN0007) — mã người dùng
    tự đặt theo kiểu khác (vd HD-2026-01) thì không thuộc diện đánh số lại."""
    return bool(code) and re.fullmatch(rf"{re.escape(prefix)}\d+", code) is not None


def renumber_codes(db: Session, model, code_column_name: str, prefix: str, pad_width: int = 4) -> int:
    """Dồn lại các mã tự sinh cùng tiền tố thành dãy LIÊN TỤC 1, 2, 3... theo đúng thứ tự
    hiện có (số nhỏ trước) — dùng sau khi xoá 1 bản ghi để không còn "lỗ hổng" mã.
    Vd có PN0001, PN0002, PN0004, PN0005 -> PN0001, PN0002, PN0003, PN0004.

    CHỈ đổi cột mã hiển thị, KHÔNG đổi khoá chính `id` (id được các bảng khác tham chiếu
    qua khoá ngoại). Mã không đúng dạng tiền tố + số (vd mã người dùng tự đặt) được bỏ qua.
    Trả về số bản ghi đã đổi mã. KHÔNG commit — để hàm gọi gộp chung 1 giao dịch với thao tác
    xoá, lỗi thì hoàn tác cả hai.

    Vì sao đổi TỪNG bản ghi theo thứ tự tăng dần: cột mã có ràng buộc UNIQUE kiểm tra ngay
    từng dòng, nên 1 câu UPDATE dồn cả loạt có thể đụng mã đích chưa kịp được giải phóng.
    Đi từ số nhỏ đến lớn thì mã đích (<= mã hiện tại) luôn đã trống lúc cần dùng."""
    column = getattr(model, code_column_name)
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    rows = db.query(model.id, column).filter(column.isnot(None)).filter(column.like(f"{prefix}%")).all()

    numbered = []
    for row_id, code in rows:
        m = pattern.match(code or "")
        if m:
            numbered.append((int(m.group(1)), row_id))
    numbered.sort()  # theo số, cùng số (không thể xảy ra vì UNIQUE) thì theo id

    changed = 0
    for new_num, (old_num, row_id) in enumerate(numbered, start=1):
        if old_num == new_num:
            continue
        db.execute(update(model).where(model.id == row_id).values({code_column_name: f"{prefix}{new_num:0{pad_width}d}"}))
        changed += 1
    return changed
