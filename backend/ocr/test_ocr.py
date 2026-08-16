"""Test nhanh OCR trên 1 ảnh phiếu nhập hàng — không cần chạy cả server FastAPI.

Cách dùng:
    python -m ocr.test_ocr duong/dan/anh_phieu_nhap.jpg

In ra: text thô, độ tin cậy trung bình, và từng dòng hàng đã trích xuất
(tên sản phẩm, số lượng, mã lô, hạn sử dụng, điểm fuzzy-match nếu có
danh mục sản phẩm).
"""
import sys
import json
from dataclasses import asdict

from ocr.ocr_engine import ReceiptOCREngine

# TODO (Luân): dán vào đây vài tên sản phẩm thật của cửa hàng đã khảo sát,
# để test luôn khả năng fuzzy-match (mục 6.4) — để trống vẫn chạy được OCR bình thường.
SAMPLE_KNOWN_PRODUCTS = [
    "Sữa tươi Vinamilk 1L",
    "Nước suối Aquafina 500ml",
    "Mì gói Hảo Hảo tôm chua cay",
    "Dầu ăn Neptune 1L",
]


def main():
    if len(sys.argv) < 2:
        print("Cách dùng: python -m ocr.test_ocr <đường_dẫn_ảnh_phiếu>")
        sys.exit(1)

    image_path = sys.argv[1]
    print(f"Đang xử lý: {image_path}")

    engine = ReceiptOCREngine(lang="vi", known_products=SAMPLE_KNOWN_PRODUCTS)
    result = engine.process_receipt(image_path)

    print("\n=== TEXT THÔ (toàn bộ) ===")
    print(result.raw_text)
    print(f"\nĐộ tin cậy trung bình: {result.avg_confidence:.2%}")

    print(f"\n=== {len(result.lines)} DÒNG HÀNG TRÍCH XUẤT ĐƯỢC ===")
    for i, line in enumerate(result.lines, start=1):
        print(f"\n-- Dòng {i} --")
        print(json.dumps(asdict(line), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
