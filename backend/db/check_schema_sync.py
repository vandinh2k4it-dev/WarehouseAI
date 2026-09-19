"""So sánh CỘT giữa db/schema.sql và app/models.py — chạy tay lệnh này TRƯỚC
mỗi lần commit có đụng tới model hoặc schema.sql, để không lặp lại đúng lỗi
đã xảy ra trước đây (schema.sql lệch models.py qua nhiều đợt sửa, chỉ lộ ra
khi có ai tạo Postgres MỚI từ đầu bằng schema.sql, không lộ trên Railway vì
bảng cũ đã tồn tại sẵn — xem ghi chú đầu file db/schema.sql).

CÁCH DÙNG:
    python db/check_schema_sync.py

Không cần Postgres đang chạy, không cần biến môi trường DATABASE_URL đúng
thật — script chỉ ĐỌC định nghĩa cột (không kết nối DB), nên chạy được ở
bất kỳ máy nào đã cài xong requirements.txt.

GIỚI HẠN CỐ Ý: đây là script kiểm tra NHANH bằng cách so tên cột parse thô
từ schema.sql (regex, không phải SQL parser đầy đủ) với tên cột khai báo
trong models.py (qua SQLAlchemy metadata thật) — CHỈ báo được thiếu/thừa
CỘT NÀO so với CỘT NÀO, KHÔNG kiểm tra kiểu dữ liệu, NULL/NOT NULL, default,
hay CHECK constraint có khớp nội dung hay không. Có báo "OK — khớp cột" vẫn
nên tự đọc lại 2 file nếu vừa đổi kiểu dữ liệu hoặc constraint (không đổi
tên cột), vì loại thay đổi đó script này không phát hiện được. Nếu sau này
chuyển hẳn sang Alembic migration (đã có sẵn trong requirements.txt nhưng
chưa dùng thật — xem ghi chú trong models.py), script này sẽ không còn cần
thiết nữa vì Alembic tự đảm bảo đồng bộ.
"""
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SCHEMA_SQL_PATH = _ROOT / "db" / "schema.sql"

# Từ khoá mở đầu 1 "cột" trong CREATE TABLE mà KHÔNG PHẢI là tên cột thật —
# đây là các ràng buộc/chỉ mục cấp bảng, không phải cột dữ liệu.
_CONSTRAINT_KEYWORDS = {
    "check", "constraint", "primary", "foreign", "unique", "exclude",
}


def _split_top_level(body: str) -> list[str]:
    """Tách body bên trong CREATE TABLE (...) thành từng mục theo dấu phẩy
    Ở CẤP NGOÀI CÙNG — không tách nhầm dấu phẩy bên trong NUMERIC(12,2),
    CHECK(...), v.v. (đếm độ sâu ngoặc tròn thủ công)."""
    items, depth, current = [], 0, []
    for ch in body:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            items.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        items.append("".join(current))
    return items


def parse_schema_sql(sql_text: str) -> dict[str, set[str]]:
    """Trả về {tên_bảng: {tên_cột, ...}} parse từ toàn bộ file schema.sql."""
    # Bỏ comment dòng "--..." trước khi parse, tránh comment chứa dấu ) hay ,
    # làm lệch việc đếm độ sâu ngoặc ở _split_top_level.
    no_comments = re.sub(r"--[^\n]*", "", sql_text)

    tables: dict[str, set[str]] = {}
    for match in re.finditer(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s*\((.*?)\)\s*;",
        no_comments,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        table_name = match.group(1)
        body = match.group(2)
        columns = set()
        for item in _split_top_level(body):
            item = item.strip()
            if not item:
                continue
            first_word_match = re.match(r'"?(\w+)"?', item)
            first_word = first_word_match.group(1).lower() if first_word_match else ""
            if first_word in _CONSTRAINT_KEYWORDS:
                continue  # ràng buộc cấp bảng, không phải cột
            columns.add(first_word)
        tables[table_name] = columns
    return tables


def get_models_columns() -> dict[str, set[str]]:
    """Trả về {tên_bảng: {tên_cột, ...}} đọc thật từ SQLAlchemy metadata
    (app/models.py) — import models sẽ tự đăng ký hết các class vào
    Base.metadata, KHÔNG cần kết nối Postgres thật (create_engine không tự
    kết nối ngay lúc gọi, chỉ kết nối khi có query đầu tiên)."""
    sys.path.insert(0, str(_ROOT))
    from app import models  # noqa: F401  (import để đăng ký metadata)
    from app.database import Base

    return {
        table_name: {col.name for col in table.columns}
        for table_name, table in Base.metadata.tables.items()
    }


def main() -> int:
    if not _SCHEMA_SQL_PATH.exists():
        print(f"❌ Không tìm thấy {_SCHEMA_SQL_PATH}")
        return 1

    sql_tables = parse_schema_sql(_SCHEMA_SQL_PATH.read_text(encoding="utf-8"))
    model_tables = get_models_columns()

    all_table_names = sorted(set(sql_tables) | set(model_tables))
    has_mismatch = False

    for table_name in all_table_names:
        sql_cols = sql_tables.get(table_name)
        model_cols = model_tables.get(table_name)

        if sql_cols is None:
            print(f"❌ Bảng '{table_name}' có trong models.py nhưng KHÔNG có trong schema.sql")
            has_mismatch = True
            continue
        if model_cols is None:
            print(f"❌ Bảng '{table_name}' có trong schema.sql nhưng KHÔNG có trong models.py")
            has_mismatch = True
            continue

        missing_in_sql = model_cols - sql_cols
        missing_in_models = sql_cols - model_cols

        if missing_in_sql or missing_in_models:
            has_mismatch = True
            print(f"❌ Bảng '{table_name}' LỆCH:")
            if missing_in_sql:
                print(f"     Có trong models.py, THIẾU trong schema.sql: {sorted(missing_in_sql)}")
            if missing_in_models:
                print(f"     Có trong schema.sql, THIẾU trong models.py: {sorted(missing_in_models)}")
        else:
            print(f"✅ Bảng '{table_name}' khớp cột ({len(sql_cols)} cột)")

    print()
    if has_mismatch:
        print("❌ CÓ LỆCH — xem chi tiết ở trên. Sửa lại schema.sql hoặc models.py cho khớp trước khi commit.")
        return 1

    print("✅ Tất cả bảng khớp cột giữa schema.sql và models.py (chỉ kiểm tra TÊN CỘT — xem giới hạn ở đầu file).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
