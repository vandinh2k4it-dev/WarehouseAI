"""Migration: thêm cột receipt_date (ngày nhập GHI TRÊN PHIẾU) vào
import_receipts — dùng để đối chiếu với ngày hôm nay khi đếm hàng.
KHÔNG xoá data cũ; phiếu cũ để NULL, khi so sẽ tự lùi về ngày received_at.

Chạy 1 lần sau khi pull code mới về, TRƯỚC khi chạy lại server:
    python -m db.migrate_add_receipt_date

An toàn để chạy lại nhiều lần — có "IF NOT EXISTS".
"""
from sqlalchemy import text
from app.database import engine

STATEMENTS = [
    "ALTER TABLE import_receipts ADD COLUMN IF NOT EXISTS receipt_date DATE",
]


def main():
    with engine.begin() as conn:
        for i, stmt in enumerate(STATEMENTS, start=1):
            print(f"[{i}/{len(STATEMENTS)}] {stmt}")
            conn.execute(text(stmt))
    print("\n✅ Migration xong. Có thể `uvicorn app.main:app --reload` lại bình thường.")


if __name__ == "__main__":
    main()
