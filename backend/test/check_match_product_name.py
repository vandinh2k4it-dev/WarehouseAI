"""Kiểm tra match_product_name khớp cả tên không dấu / sai hoa-thường.
Chạy từ thư mục backend: python test\\check_match_product_name.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ocr.postprocess import match_product_name

known = ["Dầu ăn Simply 1L", "Sữa tươi Vinamilk 1L", "Nước mắm Nam Ngư 500ml", "Đường tinh luyện Biên Hòa 1kg"]
cases = [
    ("DAU AN SIMPLY 1L", "Dầu ăn Simply 1L"),        # ca lỗi cũ: điểm 0,38
    ("Dầu ăn Simply 1L", "Dầu ăn Simply 1L"),        # có dấu như cũ
    ("sua tuoi vinamilk 1l", "Sữa tươi Vinamilk 1L"),
    ("DUONG TINH LUYEN BIEN HOA 1KG", "Đường tinh luyện Biên Hòa 1kg"),  # chữ đ
    ("Nuoc mam Nam Ngu 500ml", "Nước mắm Nam Ngư 500ml"),
]
for raw, want in cases:
    got, score = match_product_name(raw, known)
    print(f"{raw!r} -> {got!r} ({score:.2f})")
    assert got == want, f"sai: {raw!r} ra {got!r}"
got, score = match_product_name("Bột giặt Omo 3kg", known)
print("khong co trong danh muc ->", got, f"({score:.2f})")
assert got is None
print("OK")
