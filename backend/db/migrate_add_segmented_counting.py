"""Migration: thêm cột mới cho quy trình đếm THEO TỪNG LOẠI HÀNG (mỗi lần
1 loại đi qua băng chuyền) — KHÔNG xoá data cũ, chỉ ALTER TABLE thêm cột.

Chạy 1 lần sau khi đã pull code mới về, TRƯỚC khi chạy lại server:
    python -m db.migrate_add_segmented_counting

An toàn để chạy lại nhiều lần — mỗi lệnh đều có "IF NOT EXISTS".
"""
from sqlalchemy import text
from app.database import engine

STATEMENTS = [
    # camera_count_sessions
    "ALTER TABLE camera_count_sessions ALTER COLUMN counted_quantity DROP NOT NULL",
    "ALTER TABLE camera_count_sessions ADD COLUMN IF NOT EXISTS direction VARCHAR(10) NOT NULL DEFAULT 'import'",
    "ALTER TABLE camera_count_sessions ADD COLUMN IF NOT EXISTS receipt_line_item_id INTEGER REFERENCES receipt_line_items(id)",
    "ALTER TABLE camera_count_sessions ADD COLUMN IF NOT EXISTS product_id INTEGER REFERENCES products(id)",
    "ALTER TABLE camera_count_sessions ADD COLUMN IF NOT EXISTS expected_quantity NUMERIC(12,2)",
    "ALTER TABLE camera_count_sessions ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'counting'",
    # Dữ liệu cũ (tạo qua endpoint POST /camera-sessions kiểu cũ) coi như đã hoàn tất
    "UPDATE camera_count_sessions SET status = 'completed' WHERE counted_quantity IS NOT NULL AND status = 'counting'",

    # reconciliations
    "ALTER TABLE reconciliations DROP CONSTRAINT IF EXISTS reconciliations_receipt_id_key",
    "ALTER TABLE reconciliations ALTER COLUMN receipt_id DROP NOT NULL",
    "ALTER TABLE reconciliations ADD COLUMN IF NOT EXISTS receipt_line_item_id INTEGER REFERENCES receipt_line_items(id)",
    "ALTER TABLE reconciliations ADD COLUMN IF NOT EXISTS product_id INTEGER REFERENCES products(id)",
]


def main():
    with engine.begin() as conn:
        for i, stmt in enumerate(STATEMENTS, start=1):
            print(f"[{i}/{len(STATEMENTS)}] {stmt}")
            try:
                conn.execute(text(stmt))
            except Exception as e:
                print(f"   ⚠️  Bỏ qua (có thể đã áp dụng từ trước): {e}")
    print("\n✅ Migration xong. Có thể `uvicorn app.main:app --reload` lại bình thường.")


if __name__ == "__main__":
    main()
