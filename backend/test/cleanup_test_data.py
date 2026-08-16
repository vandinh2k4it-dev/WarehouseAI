"""Dọn dữ liệu rác sinh ra trong lúc test/debug môi trường (trước khi sửa
xong chuỗi lỗi shm.dll -> pkg_resources -> ANTIALIAS).

Nhận diện phiếu rác bằng dấu hiệu rất đặc trưng: OCR engine cũ (trước khi
đổi sang VietOCR) hay sinh ra ký tự ä/ö/ü kiểu Đức — tiếng Việt THẬT KHÔNG
BAO GIỜ có các ký tự này (chỉ dùng ă/â/ê/ô/ơ/ư + dấu thanh), nên đây là tín
hiệu đáng tin cậy để lọc.

An toàn: MẶC ĐỊNH CHỈ IN RA (dry-run), không xoá gì cả. Phải thêm --confirm
mới thực sự xoá.

Chạy xem trước (an toàn, không đổi gì):
    python test\\cleanup_test_data.py

Chạy xoá thật sau khi đã xem kỹ danh sách và đồng ý:
    python test\\cleanup_test_data.py --confirm

Có thể loại trừ thêm 1 số receipt_id cụ thể không muốn đụng tới (vd phiếu
bạn biết chắc là tốt nhưng lỡ dính ký tự lạ vì lý do khác):
    python test\\cleanup_test_data.py --confirm --keep 47 48
"""
import argparse
import sys

sys.path.insert(0, ".")  # để import được app.* khi chạy từ thư mục gốc repo

from app.database import SessionLocal
from app import models

BAD_CHARS = set("äöüÄÖÜ")


def is_garbled(text: str | None) -> bool:
    if not text:
        return False
    return any(ch in BAD_CHARS for ch in text)


def find_junk_receipts(db, keep_ids: set[int]) -> list[models.ImportReceipt]:
    receipts = db.query(models.ImportReceipt).all()
    junk = []
    for r in receipts:
        if r.id in keep_ids:
            continue
        raw_bad = is_garbled(r.ocr_raw_text)
        line_bad = any(is_garbled(li.product_name_raw) for li in r.line_items)
        if raw_bad or line_bad:
            junk.append(r)
    return junk


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", action="store_true", help="Thực sự xoá (mặc định chỉ xem trước)")
    parser.add_argument("--keep", type=int, nargs="*", default=[], help="Các receipt_id KHÔNG được đụng tới dù có ký tự lạ")
    args = parser.parse_args()
    keep_ids = set(args.keep)

    db = SessionLocal()
    try:
        junk = find_junk_receipts(db, keep_ids)

        if not junk:
            print("✅ Không tìm thấy phiếu nào có dấu hiệu OCR lỗi cũ (ä/ö/ü). Không cần dọn gì.")
            return

        print(f"Tìm thấy {len(junk)} phiếu nghi là rác (OCR lỗi cũ):\n")
        for r in junk:
            sample_names = ", ".join(li.product_name_raw for li in r.line_items[:3])
            print(f"  #{r.id:>4}  status={r.status:<10}  {sample_names}")

        if not args.confirm:
            print(f"\n(Chế độ XEM TRƯỚC — chưa xoá gì. Xem kỹ danh sách trên, nếu đúng là rác thật, "
                  f"chạy lại với --confirm để xoá thật. Dùng --keep <id> <id> nếu muốn giữ lại phiếu nào đó.)")
            return

        junk_ids = [r.id for r in junk]

        # Xoá cảnh báo + đối chiếu liên quan trước (tránh lỗi khoá ngoại)
        recon_ids = [
            row.id for row in db.query(models.Reconciliation.id)
            .filter(models.Reconciliation.receipt_id.in_(junk_ids)).all()
        ]
        if recon_ids:
            n = db.query(models.Alert).filter(models.Alert.reconciliation_id.in_(recon_ids)).delete(synchronize_session=False)
            print(f"  Đã xoá {n} cảnh báo liên quan tới các phiếu rác.")
        n = db.query(models.Reconciliation).filter(models.Reconciliation.receipt_id.in_(junk_ids)).delete(synchronize_session=False)
        print(f"  Đã xoá {n} bản ghi đối chiếu liên quan.")

        # line_items tự xoá theo do cascade="all, delete-orphan" trên relationship,
        # nhưng xoá thẳng qua ORM object để chắc chắn kích hoạt cascade đúng.
        for r in junk:
            db.delete(r)
        db.commit()
        print(f"\n✅ Đã xoá {len(junk)} phiếu rác (và toàn bộ dòng hàng con của chúng).")

    finally:
        db.close()


if __name__ == "__main__":
    main()
