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

from sqlalchemy import func
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
