"""XOÁ SẠCH dữ liệu kho hiện có và tạo BỘ DỮ LIỆU THỰC TẾ của 1 kho hàng
(nhà phân phối hàng tiêu dùng nhanh: nước, sữa, bánh kẹo, mì, gia vị, hoá phẩm).

KHÁC seed_main.py (bộ demo dàn dựng) ở chỗ: dữ liệu ở đây được MÔ PHỎNG THEO
THỜI GIAN, đúng cách ứng dụng thật vận hành, nên mọi con số đều khớp nhau:
  - Tồn kho của MỖI LÔ = đúng tổng mọi giao dịch (nhập/xuất/điều chỉnh) của lô đó
    (seed_main gán số ngẫu nhiên nên tồn kho không truy vết được).
  - Phiếu nhập -> đếm camera từng dòng -> khớp thì cộng kho; lệch thì cảnh báo,
    rồi đếm lại hoặc xác nhận ghi đè (đúng luồng camera.py / reconciliation.py).
  - Khách đặt hàng -> xuất kho theo FEFO (lô hết hạn sớm xuất trước), cảnh báo
    sắp hết hàng sinh ra đúng lúc lô chạm ngưỡng (đúng _check_low_stock_alert).
  - Đặt hàng bổ sung theo mức tồn + chu kỳ giao hàng của từng nhà cung cấp.
  - Ảnh phiếu nhập được VẼ RA FILE THẬT (seed_main trỏ tới file không tồn tại).

CÁCH DÙNG (chạy trong thư mục backend/, đã kích hoạt venv):
    python -m db.seed_realistic                      # hỏi xác nhận (gõ XOA)
    python -m db.seed_realistic --yes                # không hỏi
    python -m db.seed_realistic --yes --clear-uploads  # xoá luôn ảnh/video cũ đã upload
    python -m db.seed_realistic --days 120 --seed 7 --yes
    python -m db.seed_realistic --no-images --yes    # không vẽ ảnh phiếu

⚠️ SẼ XOÁ: products, inventory, inventory_transactions, import_receipts,
receipt_line_items, camera_count_sessions, reconciliations, alerts.
KHÔNG xoá push_subscriptions (đăng ký nhận thông báo của điện thoại).
NÊN SAO LƯU TRƯỚC:  pg_dump -U postgres warehouse_db > backup.sql

AN TOÀN: toàn bộ (xoá + tạo mới) chạy trong 1 GIAO DỊCH — lỗi giữa chừng thì dữ
liệu cũ còn NGUYÊN. Từ chối chạy trên DB không phải localhost trừ khi có
--allow-remote.
"""
from __future__ import annotations

import argparse
import difflib
import heapq
import math
import random
import sys
import unicodedata
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, text
from sqlalchemy.engine import make_url

from app import models
from app.database import DATABASE_URL, Base, SessionLocal, engine

VN_TZ = timezone(timedelta(hours=7))  # Việt Nam không có giờ mùa hè -> dùng múi giờ cố định, khỏi cần tzdata
BACKEND_DIR = Path(__file__).resolve().parent.parent
UPLOADS_DIR = BACKEND_DIR / "uploads"
RECEIPT_DIR = UPLOADS_DIR / "receipts"

DEMAND_SCALE = 0.45  # co nhỏ nhu cầu về quy mô 1 kho vừa (~35 dòng xuất/ngày)
REORDER_DAYS = 7  # tồn (+ hàng đang chờ đếm) <= 7 ngày bán -> đặt thêm
TARGET_DAYS = 15  # đặt cho đủ ~15 ngày bán
LEAD_BUFFER = 1.3  # tồn tối thiểu = ngưỡng cảnh báo x hệ số này
MODEL_VERSION = "yolov8s-bytetrack-v1"

# ------------------------------------------------------------------ DANH MỤC
# (sku, tên, ngành hàng, đơn vị, nhu cầu TB/ngày (trước khi co), số lượng TB mỗi dòng đơn,
#  hạn dùng (ngày) hoặc None, nhà cung cấp, vị trí kệ gốc)
PRODUCTS = [
    ("SP-001", "Sữa tươi Vinamilk 100% có đường 1L", "Sữa & đồ uống", "thùng", 7, 3, 150, 0, "A1"),
    ("SP-002", "Sữa tươi TH True Milk ít đường 1L", "Sữa & đồ uống", "thùng", 5, 3, 180, 0, "A1"),
    ("SP-003", "Sữa đặc Ông Thọ lon 380g", "Sữa & đồ uống", "thùng", 3, 2, 540, 0, "A2"),
    ("SP-004", "Sữa đậu nành Fami 200ml", "Sữa & đồ uống", "thùng", 4, 3, 270, 0, "A2"),
    ("SP-005", "Nước suối Lavie 500ml", "Sữa & đồ uống", "thùng", 11, 5, 720, 1, "A3"),
    ("SP-006", "Nước suối Aquafina 500ml", "Sữa & đồ uống", "thùng", 9, 5, 720, 1, "A3"),
    ("SP-007", "Nước khoáng Vĩnh Hảo 500ml", "Sữa & đồ uống", "thùng", 4, 3, 720, 1, "A4"),
    ("SP-008", "Coca-Cola lon 330ml", "Sữa & đồ uống", "thùng", 12, 5, 365, 1, "A5"),
    ("SP-009", "Coca-Cola chai 390ml", "Sữa & đồ uống", "thùng", 6, 4, 270, 1, "A5"),
    ("SP-010", "Pepsi lon 330ml", "Sữa & đồ uống", "thùng", 9, 4, 365, 1, "A6"),
    ("SP-011", "Nước tăng lực Sting dâu 330ml", "Sữa & đồ uống", "thùng", 7, 4, 365, 1, "A6"),
    ("SP-012", "Trà xanh không độ 455ml", "Sữa & đồ uống", "thùng", 5, 3, 365, 1, "A4"),
    ("SP-013", "Cà phê hòa tan G7 3in1", "Sữa & đồ uống", "thùng", 3, 2, 540, 1, "A2"),
    ("SP-014", "Bánh Oreo hộp 133g", "Bánh kẹo", "thùng", 2.5, 2, 300, 2, "B1"),
    ("SP-015", "Bánh Cosy quy bơ", "Bánh kẹo", "thùng", 3, 2, 300, 2, "B1"),
    ("SP-016", "Bánh Solite hộp", "Bánh kẹo", "thùng", 2.5, 2, 270, 2, "B2"),
    ("SP-017", "Bánh AFC dinh dưỡng", "Bánh kẹo", "thùng", 2, 2, 300, 2, "B2"),
    ("SP-018", "Bánh gạo One One", "Bánh kẹo", "thùng", 3, 2, 240, 2, "B3"),
    ("SP-019", "Kẹo Mentos bạc hà", "Bánh kẹo", "thùng", 2, 2, 540, 2, "B3"),
    ("SP-020", "Kẹo Alpenliebe", "Bánh kẹo", "thùng", 2, 2, 540, 2, "B4"),
    ("SP-021", "Kẹo Cool Air bạc hà", "Bánh kẹo", "thùng", 1.5, 2, 540, 2, "B4"),
    ("SP-022", "Snack Oishi khoai tây", "Bánh kẹo", "thùng", 4, 3, 210, 2, "B5"),
    ("SP-023", "Snack Lay's vị tự nhiên", "Bánh kẹo", "thùng", 3, 3, 210, 2, "B5"),
    ("SP-024", "Sô-cô-la KitKat 4 finger", "Bánh kẹo", "thùng", 1.2, 2, 360, 2, "B6"),
    ("SP-025", "Bánh Chocopie hộp 12 cái", "Bánh kẹo", "thùng", 3, 2, 270, 2, "B6"),
    ("SP-026", "Mì Hảo Hảo tôm chua cay", "Thực phẩm khô", "thùng", 14, 6, 180, 3, "C1"),
    ("SP-027", "Mì Hảo Hảo sa tế hành", "Thực phẩm khô", "thùng", 4, 3, 180, 3, "C1"),
    ("SP-028", "Mì Omachi sốt bò hầm", "Thực phẩm khô", "thùng", 7, 4, 180, 3, "C2"),
    ("SP-029", "Mì Kokomi tôm chua cay", "Thực phẩm khô", "thùng", 5, 3, 180, 3, "C2"),
    ("SP-030", "Mì 3 Miền gà", "Thực phẩm khô", "thùng", 4, 3, 180, 3, "C3"),
    ("SP-031", "Mì ly Modern lẩu thái", "Thực phẩm khô", "thùng", 3, 2, 180, 3, "C3"),
    ("SP-032", "Phở bò ăn liền Vifon", "Thực phẩm khô", "thùng", 2.5, 2, 180, 3, "C4"),
    ("SP-033", "Hủ tiếu Nam Vang Vifon", "Thực phẩm khô", "thùng", 2.5, 2, 180, 3, "C4"),
    ("SP-034", "Cháo ăn liền Gấu Đỏ", "Thực phẩm khô", "thùng", 1.5, 2, 270, 3, "C5"),
    ("SP-035", "Gạo ST25 túi 5kg", "Thực phẩm khô", "bao", 6, 3, 365, 3, "C6"),
    ("SP-036", "Gạo thơm Jasmine bao 10kg", "Thực phẩm khô", "bao", 4, 2, 365, 3, "C6"),
    ("SP-037", "Miến dong Phú Hương", "Thực phẩm khô", "thùng", 1.5, 2, 540, 3, "C5"),
    ("SP-038", "Dầu ăn Simply 1L", "Gia vị", "thùng", 3.5, 2, 540, 4, "D1"),
    ("SP-039", "Dầu ăn Neptune 1L", "Gia vị", "thùng", 3.5, 2, 540, 4, "D1"),
    ("SP-040", "Dầu ăn Tường An Cooking 1L", "Gia vị", "thùng", 3, 2, 540, 4, "D2"),
    ("SP-041", "Nước mắm Nam Ngư 500ml", "Gia vị", "thùng", 4, 3, 720, 4, "D2"),
    ("SP-042", "Nước mắm Chinsu 500ml", "Gia vị", "thùng", 3.5, 2, 720, 4, "D3"),
    ("SP-043", "Nước tương Maggi 300ml", "Gia vị", "thùng", 2, 2, 540, 4, "D3"),
    ("SP-044", "Tương ớt Chinsu 250g", "Gia vị", "thùng", 2.5, 2, 540, 4, "D4"),
    ("SP-045", "Hạt nêm Knorr thịt thăn xương ống 900g", "Gia vị", "thùng", 3, 2, 720, 4, "D4"),
    ("SP-046", "Bột ngọt Ajinomoto 400g", "Gia vị", "thùng", 2.5, 2, 1080, 4, "D5"),
    ("SP-047", "Muối i-ốt Bạc Liêu 500g", "Gia vị", "thùng", 1.5, 2, 1080, 4, "D5"),
    ("SP-048", "Đường cát trắng Biên Hòa 1kg", "Gia vị", "thùng", 5, 3, 720, 4, "D6"),
    ("SP-049", "Bột giặt Omo 3kg", "Hoá phẩm", "thùng", 2.5, 2, 1095, 5, "E1"),
    ("SP-050", "Bột giặt Ariel 3kg", "Hoá phẩm", "thùng", 2, 2, 1095, 5, "E1"),
    ("SP-051", "Bột giặt Surf hương nước hoa 3kg", "Hoá phẩm", "thùng", 2, 2, 1095, 5, "E2"),
    ("SP-052", "Nước xả Comfort 1.5L", "Hoá phẩm", "thùng", 2, 2, 1095, 5, "E2"),
    ("SP-053", "Nước rửa chén Sunlight 750g", "Hoá phẩm", "thùng", 3, 2, 1095, 5, "E3"),
    ("SP-054", "Nước lau sàn Sunlight 1L", "Hoá phẩm", "thùng", 1.5, 2, 1095, 5, "E3"),
    ("SP-055", "Nước tẩy bồn cầu Vim 880ml", "Hoá phẩm", "thùng", 1.2, 2, 1095, 5, "E4"),
    ("SP-056", "Dầu gội Clear men 630g", "Hoá phẩm", "thùng", 1.2, 2, 1095, 5, "E4"),
    ("SP-057", "Dầu gội Sunsilk 650g", "Hoá phẩm", "thùng", 1.2, 2, 1095, 5, "E5"),
    ("SP-058", "Sữa tắm Lifebuoy 850g", "Hoá phẩm", "thùng", 1.2, 2, 1095, 5, "E5"),
    ("SP-059", "Kem đánh răng P/S 230g", "Hoá phẩm", "thùng", 2.5, 3, 1095, 5, "E6"),
    ("SP-060", "Giấy vệ sinh Pulppy 10 cuộn", "Hoá phẩm", "lốc", 5, 3, None, 5, "E6"),
    ("SP-061", "Khăn giấy rút Bless You", "Hoá phẩm", "thùng", 2.5, 2, None, 5, "E6"),
]

SUPPLIERS = [
    "Công ty TNHH Phân phối An Bình",
    "Đại lý Nước giải khát Minh Phát",
    "Công ty CP Thương mại Hưng Thịnh",
    "Nhà phân phối Sài Gòn Food",
    "Công ty TNHH Gia vị Việt Tín",
    "Chành hoá phẩm Phú Lộc",
]
# thứ trong tuần (Thứ 2 = 0) -> các nhà cung cấp giao hàng hôm đó
DELIVERY_SCHEDULE = {0: [0, 3], 1: [1, 4], 2: [2, 5], 3: [0, 3], 4: [1, 5], 5: [4]}

# Lô "cận date / để quên cuối kệ": cố ý tạo để có sẵn lô hết hạn chưa huỷ + sắp hết hạn
# (sku, hạn dùng cách HÔM NAY bao nhiêu ngày, số lượng, đến kho cách đây ~ bao nhiêu ngày)
ENGINEERED_BATCHES = [
    ("SP-024", -2, 6, 52),
    ("SP-021", -1, 8, 47),
    ("SP-034", 6, 10, 41),
    ("SP-037", 9, 6, 38),
    ("SP-031", 17, 12, 33),
    ("SP-017", 26, 9, 30),
]

STAFF = ["Nguyễn Văn Hùng", "Trần Thị Mai", "Lê Quốc Bảo", "Phạm Thị Hạnh"]
OVERRIDE_NOTES = [
    "Thùng móp rách, đã loại ra khỏi lô nhập — lập biên bản với nhà cung cấp",
    "Nhà cung cấp giao thiếu so với phiếu, đã xác nhận qua điện thoại",
    "Đếm lại bằng tay đúng số camera, phiếu ghi nhầm",
    "Có thùng bị che khuất lúc đếm, đã kiểm tra thực tế khớp số camera",
]
CUSTOMERS = [
    "Tạp hóa Bà Tư (Q.8)", "Tạp hóa Cô Lan (Q.7)", "Cửa hàng Minh Châu (Bình Tân)",
    "Siêu thị mini Gia Hân (Q.12)", "Đại lý Phát Lộc (Hóc Môn)", "Quán cơm Ba Miền (Gò Vấp)",
    "CH tiện lợi Sao Mai (Thủ Đức)", "Sạp Chú Hai (chợ Bình Điền)", "Tạp hóa Út Hiền (Bình Chánh)",
    "Nhà hàng Hương Quê (Q.10)", "Cửa hàng Thanh Tâm (Tân Phú)", "Đại lý Hoàng Gia (Củ Chi)",
    "Tạp hóa Chị Ngọc (Q.6)", "Căn tin trường THPT (Q.9)", "Cửa hàng 24h Bình An (Q.3)",
    "Tạp hóa Dì Sáu (Nhà Bè)", "Quán ăn Tư Béo (Q.4)", "Siêu thị mini Phúc Lộc (Q.11)",
    "Đại lý Tân Thành (Long An)", "Tạp hóa Anh Khoa (Bình Thạnh)", "Quán cà phê Góc Phố (Q.1)",
    "Cửa hàng Kim Ngân (Tân Bình)", "Bếp ăn công ty Việt Phát (KCN Tân Bình)",
]


def strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("đ", "d").replace("Đ", "D")


def poisson(rng: random.Random, lam: float) -> int:
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= limit:
            return k - 1


def ceil_to(x: float, step: int) -> int:
    return int(math.ceil(max(x, 0) / step) * step)


# ------------------------------------------------------------------ ẢNH PHIẾU
FONT_PAIRS = [  # (thường, đậm) — chọn font có đủ dấu tiếng Việt, tuỳ hệ điều hành
    (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
    (r"C:\Windows\Fonts\tahoma.ttf", r"C:\Windows\Fonts\tahomabd.ttf"),
    (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\segoeuib.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
]


class ReceiptRenderer:
    """Vẽ ảnh phiếu nhập giống ảnh chụp thật: tờ phiếu trên mặt bàn, hơi nghiêng,
    hơi nhiễu — cùng bố cục bảng 4 cột (Tên sản phẩm | Số lượng | Mã lô | HSD) mà
    mô-đun OCR đang đọc."""

    def __init__(self, font_path: str | None):
        from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont  # noqa: F401

        self.Image, self.ImageDraw, self.ImageEnhance = Image, ImageDraw, ImageEnhance
        self.ImageFilter, self.ImageFont = ImageFilter, ImageFont
        self.regular = self.bold = None
        pairs = ([(font_path, font_path)] if font_path else []) + FONT_PAIRS
        for reg, bld in pairs:
            if Path(reg).exists():
                self.regular = reg
                self.bold = bld if Path(bld).exists() else reg
                break
        if not self.regular:
            raise RuntimeError("không tìm thấy font có dấu tiếng Việt (dùng --font <đường dẫn .ttf>)")

    def _font(self, bold: bool, size: int):
        return self.ImageFont.truetype(self.bold if bold else self.regular, size)

    def render(self, path: Path, number: int, supplier: str, received: datetime, rows: list, rng: random.Random):
        """rows: [(tên, số lượng, mã lô, hsd (date|None))]"""
        W, M, ROW, HEAD = 1000, 50, 44, 50
        H = M + 70 + 3 * 32 + HEAD + len(rows) * ROW + 40 + 90
        paper = self.Image.new("RGB", (W, H), (252, 252, 250))
        d = self.ImageDraw.Draw(paper)
        d.rectangle([0, 0, W - 1, H - 1], outline=(200, 200, 196), width=2)

        d.text((W // 2, M + 18), f"PHIẾU NHẬP HÀNG #{number}", font=self._font(True, 34), fill=(20, 20, 20), anchor="mm")
        y = M + 70
        for line in (
            f"Ngày nhập: {received:%d/%m/%Y}",
            f"Đại lý: {supplier}",
            f"Số phiếu giao: GH{received:%y%m}-{rng.randint(1000, 9999)}",
        ):
            d.text((M + 20, y), line, font=self._font(False, 22), fill=(25, 25, 25))
            y += 32

        cols = [("Tên sản phẩm", 500), ("Số lượng", 120), ("Mã lô", 150), ("HSD", 130)]
        x0 = M
        d.rectangle([x0, y, x0 + sum(w for _, w in cols), y + HEAD], fill=(210, 210, 210), outline=(30, 30, 30), width=2)
        cx = x0
        for title, w in cols:
            d.text((cx + 12, y + HEAD // 2), title, font=self._font(False, 22), fill=(15, 15, 15), anchor="lm")
            cx += w
        y += HEAD
        for name, qty, batch, exp in rows:
            cx = x0
            cells = [name, str(qty), batch or "", f"{exp:%d/%m/%Y}" if exp else ""]
            for i, ((_, w), cell) in enumerate(zip(cols, cells)):
                size = 22
                while size > 15 and self._font(False, size).getlength(cell) > w - 20:
                    size -= 1  # tên dài thì thu nhỏ chữ cho vừa ô, KHÔNG cắt bớt
                d.rectangle([cx, y, cx + w, y + ROW], outline=(30, 30, 30), width=2)
                anchor, tx = ("lm", cx + 12) if i == 0 else ("mm", cx + w // 2)
                d.text((tx, y + ROW // 2), cell, font=self._font(False, size), fill=(10, 10, 10), anchor=anchor)
                cx += w
            y += ROW
        d.text((M + 20, y + 45), "Người giao hàng: ____________   Người nhận hàng: ____________",
               font=self._font(False, 22), fill=(25, 25, 25))

        # đặt tờ phiếu lên mặt bàn, nghiêng nhẹ, thêm nhiễu/mờ nhẹ cho giống ảnh chụp bằng điện thoại
        desk_col = (rng.randint(80, 120), rng.randint(70, 105), rng.randint(60, 95))
        desk = self.Image.new("RGB", (W + 120, H + 120), desk_col)
        desk.paste(paper, (60, 60))
        desk = desk.rotate(rng.uniform(-1.6, 1.6), resample=self.Image.BICUBIC, expand=True, fillcolor=desk_col)
        desk = self.ImageEnhance.Brightness(desk).enhance(rng.uniform(0.9, 1.05))
        desk = desk.filter(self.ImageFilter.GaussianBlur(rng.uniform(0.3, 0.8)))
        noise = self.Image.effect_noise(desk.size, rng.uniform(4, 9)).convert("RGB")
        desk = self.Image.blend(desk, noise, 0.04)
        desk.thumbnail((1000, 1400))
        desk.save(path, "JPEG", quality=82)


# ------------------------------------------------------------------ MÔ PHỎNG
@dataclass
class Batch:
    row: models.Inventory
    pid: int
    code: str
    exp: date | None
    qty: int = 0
    avail_from: datetime | None = None
    forgotten: bool = False  # lô để quên cuối kệ: nhân viên không lấy hàng từ lô này
    last_in: datetime | None = None
    open_alert: models.Alert | None = None


class Simulator:
    def __init__(self, db, rng, now, days, renderer):
        self.db, self.rng, self.now, self.renderer = db, rng, now, renderer
        self.today = now.date()
        self.start = self.today - timedelta(days=days)
        self.days = days
        self.new_files: list[Path] = []

        self.P: dict[int, dict] = {}
        self.batches: dict[int, list[Batch]] = defaultdict(list)
        self.batch_by_key: dict[tuple, Batch] = {}
        self.pending: dict[int, int] = defaultdict(int)
        self.rstate: dict[int, dict] = {}
        self.engineered = [dict(sku=s, exp_offset=e, qty=q, ago=a, placed=False) for s, e, q, a in ENGINEERED_BATCHES]
        self.counters = defaultdict(int)
        self.heap: list = []
        self.seq = 0
        self.stats = defaultdict(int)

        self.last_day = self._last_receipt_day()
        self.open_export_pending = True
        self.flag_day = self._nth_working_day_before(self.last_day, 3)
        self.flag_done = False

    # ---------------- tiện ích
    def at(self, day: date, hour: float) -> datetime:
        h = int(hour)
        m = int((hour - h) * 60)
        return datetime(day.year, day.month, day.day, h, m, self.rng.randint(0, 59), tzinfo=VN_TZ)

    def code(self, prefix: str, width: int = 4) -> str:
        self.counters[prefix] += 1
        return f"{prefix}{self.counters[prefix]:0{width}d}"

    def push(self, ts: datetime, kind: str, **payload):
        self.seq += 1
        heapq.heappush(self.heap, (ts, self.seq, kind, payload))

    def _last_receipt_day(self) -> date:
        d = self.today
        while True:
            if d.weekday() != 6:
                first = self.at(d, 9.0)
                if d < self.today or first <= self.now:
                    return d
            d -= timedelta(days=1)

    def _nth_working_day_before(self, day: date, n: int) -> date:
        d = day
        while n > 0:
            d -= timedelta(days=1)
            if d.weekday() != 6:
                n -= 1
        return d

    # ---------------- danh mục
    def create_products(self):
        ts = self.at(self.start, 7.0)
        for i, (sku, name, cat, unit, d, q, shelf, sup, rack) in enumerate(PRODUCTS, start=1):
            d_eff = d * DEMAND_SCALE
            thr = max(5, 5 * round(d_eff * 3 / 5))
            step = 10 if d_eff >= 4 else 5 if d_eff >= 1.5 else 2
            row = models.Product(sku=sku, name=name, category=cat, unit=unit, low_stock_threshold=thr, created_at=ts)
            self.db.add(row)
            self.db.flush()
            self.P[row.id] = dict(id=row.id, sku=sku, name=name, unit=unit, d=d_eff, q=q, shelf=shelf, sup=sup,
                                  rack=rack, step=step, thr=thr, f=d_eff / q)
        self.by_sku = {p["sku"]: p for p in self.P.values()}
        self.orders_per_day = sum(p["f"] for p in self.P.values()) / 3.65

    # ---------------- lô hàng / giao dịch kho
    def batch_code(self, pid: int, prod_date: date) -> str:
        for letter in "ABCDEFGHKLMNPQRSTUVXYZ":
            code = f"L{prod_date:%y%m%d}{letter}"
            if (pid, code) not in self.batch_by_key:
                return code
        raise RuntimeError("hết mã lô")

    def new_batch(self, pid: int, code: str, exp: date | None, ts: datetime, forgotten: bool = False) -> Batch:
        row = models.Inventory(product_id=pid, batch_code=code, quantity=0, expiry_date=exp, last_updated=ts)
        self.db.add(row)
        self.db.flush()
        b = Batch(row=row, pid=pid, code=code, exp=exp, forgotten=forgotten)
        self.batches[pid].append(b)
        self.batch_by_key[(pid, code)] = b
        return b

    def tx(self, b: Batch, qty: int, ts: datetime, ttype: str, rtype: str | None, rid: int | None, note: str | None):
        b.qty += qty
        assert b.qty >= 0, "tồn kho âm — lỗi mô phỏng"
        b.row.quantity = b.qty
        b.row.last_updated = ts
        self.db.add(models.InventoryTransaction(inventory_id=b.row.id, change_qty=qty, transaction_type=ttype,
                                                reference_type=rtype, reference_id=rid, note=note, created_at=ts))
        self.stats[f"tx_{ttype}"] += 1

    def pickable(self, pid: int, ts: datetime) -> list[Batch]:
        """Các lô được phép lấy hàng, theo FEFO: hết hạn sớm xuất trước, lô không HSD xuống cuối.
        Nhân viên bỏ qua lô đã hết hạn và lô để quên (khi xuất tay họ chọn đúng lô)."""
        out = [b for b in self.batches[pid]
               if b.qty > 0 and not b.forgotten and b.avail_from and b.avail_from <= ts
               and (b.exp is None or b.exp >= ts.date())]
        return sorted(out, key=lambda b: (b.exp is None, b.exp or date.max))

    def onhand(self, pid: int, ts: datetime) -> int:
        return sum(b.qty for b in self.pickable(pid, ts))

    def check_low_alert(self, b: Batch, ts: datetime):
        """Đúng logic _check_low_stock_alert: sau khi trừ kho, lô <= ngưỡng thì cảnh báo, trừ khi lô đó đã có cảnh báo đang mở."""
        p = self.P[b.pid]
        if b.qty > p["thr"] or (b.open_alert is not None and b.open_alert.status == "open"):
            return
        a = models.Alert(
            alert_type="low_stock", severity="medium" if b.qty > 0 else "high", inventory_id=b.row.id,
            message=f"Sản phẩm '{p['name']}' (lô {b.code}) chỉ còn {b.qty:.2f} {p['unit']} — dưới ngưỡng {p['thr']:.2f}.",
            status="open", created_at=ts)
        self.db.add(a)
        b.open_alert = a
        self.stats["alert_low"] += 1

    def export_fefo(self, pid: int, qty: int, ts: datetime, note, rtype, rid) -> int:
        rem = qty
        for b in self.pickable(pid, ts):
            if rem <= 0:
                break
            take = min(b.qty, rem)
            self.tx(b, -take, ts, "export", rtype, rid, note)
            rem -= take
            self.check_low_alert(b, ts)
        return qty - rem

    # ---------------- tồn đầu kỳ
    def opening_stock(self):
        ts = self.at(self.start, 7.5)
        for pid, p in self.P.items():
            total = max(p["step"], int(round(p["d"] * self.rng.uniform(9, 15))))
            parts = [total]
            if total >= 24:
                first = int(total * self.rng.uniform(0.35, 0.6))
                parts = [first, total - first]
            for k, q in enumerate(parts):
                exp = None
                if p["shelf"]:
                    exp = self.start + timedelta(days=int(p["shelf"] * self.rng.uniform(0.4, 0.85)) - 25 * k)
                prod_date = exp - timedelta(days=p["shelf"]) if exp else self.start - timedelta(days=self.rng.randint(20, 120))
                b = self.new_batch(pid, self.batch_code(pid, prod_date), exp, ts)
                self.tx(b, q, ts, "adjustment", "manual", None, "Tồn đầu kỳ — kiểm kê khi bắt đầu sử dụng hệ thống")
                b.avail_from = b.last_in = ts

    # ---------------- vòng lặp theo ngày
    def run(self):
        self.create_products()
        self.opening_stock()
        for i in range(self.days + 1):
            day = self.start + timedelta(days=i)
            if day.weekday() == 6:  # chủ nhật nghỉ
                continue
            self.plan_day(day, i)
            while self.heap:
                ts, _, kind, payload = heapq.heappop(self.heap)
                if ts > self.now:
                    continue
                getattr(self, f"ev_{kind}")(ts, **payload)
            self.end_of_day(day)
        for pid, bl in self.batches.items():
            for b in bl:
                b.row.quantity = b.qty

    def plan_day(self, day: date, idx: int):
        wd = day.weekday()
        sched = DELIVERY_SCHEDULE.get(wd, [])
        is_last = day == self.last_day
        for k, sup in enumerate(sched):
            if is_last:
                if len(sched) == 1:
                    mode = "partial"  # ngày chỉ có 1 nhà cung cấp: phiếu đang đếm dở
                elif k == len(sched) - 1:
                    mode = "none"  # phiếu vừa về, chưa đếm dòng nào
                elif k == len(sched) - 2:
                    mode = "partial"
                else:
                    mode = "full"
                base = self.now - timedelta(minutes=(len(sched) - k) * 60 + 25)
                ts = max(base, self.at(day, 7.6 + 0.3 * k))
            else:
                mode, ts = "full", self.at(day, self.rng.uniform(7.5, 10.2))
            self.push(ts, "receipt", sup=sup, mode=mode, force=is_last, flagged=False)
            if day == self.flag_day and not self.flag_done and k == 0:
                self.flag_done = True
                self.push(ts + timedelta(minutes=40), "receipt", sup=sup, mode="none", force=False, flagged=True)

        dow = 0.55 if wd == 5 else 1.0
        lam = self.orders_per_day * dow * (1 + 0.18 * idx / max(self.days, 1)) * self.rng.uniform(0.85, 1.15)
        for _ in range(poisson(self.rng, lam)):
            hour = self.rng.uniform(8.5, 11.6) if self.rng.random() < 0.6 else self.rng.uniform(13.4, 16.6)
            ts = self.at(day, hour)
            if ts <= self.now - timedelta(minutes=1):
                self.push(ts, "order")
        self.push(self.at(day, 16.75), "dispose")
        if wd == 5 and (day + timedelta(days=7)).month != day.month:
            self.push(self.at(day, 17.1), "stocktake")

    def end_of_day(self, day: date):
        """Cuối ngày: cảnh báo của lô đã hết sạch được nhân viên xác nhận (đa số) từ hôm sau."""
        for bl in self.batches.values():
            for b in bl:
                a = b.open_alert
                if a is not None and a.status == "open" and b.qty == 0 and a.created_at.date() < day \
                        and self.rng.random() < 0.85:
                    a.status = "acknowledged"

    # ---------------- phiếu nhập
    def raw_variant(self, name: str) -> tuple[str, float]:
        r = self.rng.random()
        if r < 0.55:
            return name, 1.0
        if r < 0.73:
            out = strip_accents(name)
        elif r < 0.83 and len(name) <= 30:
            out = name.upper()
        elif r < 0.93:
            confusable = {"o": "0", "l": "1", "i": "l", "a": "o", "e": "c", "n": "h", "m": "rn"}
            idxs = [i for i, c in enumerate(name) if c.lower() in confusable and i > 0]
            if not idxs:
                return name, 1.0
            i = self.rng.choice(idxs)
            out = name[:i] + confusable[name[i].lower()] + name[i + 1:]
        else:
            words = name.split()
            out = " ".join(words[:-1]) if len(words) > 3 else name
        score = difflib.SequenceMatcher(None, strip_accents(out).lower(), strip_accents(name).lower()).ratio()
        return out, round(min(score, 0.9999), 4) if out != name else 1.0

    def plan_lines(self, day: date, sup: int, ts: datetime, force: bool) -> list[dict]:
        specs = []
        mine = [p for p in self.P.values() if p["sup"] == sup]
        for e in self.engineered:
            p = self.by_sku[e["sku"]]
            if p["sup"] == sup and not e["placed"] and (self.today - day).days <= e["ago"]:
                e["placed"] = True
                exp = self.today + timedelta(days=e["exp_offset"])
                specs.append(dict(pid=p["id"], qty=e["qty"], exp=exp, forgotten=True, prod=exp - timedelta(days=int(p["shelf"] * 0.5))))
        taken = {s["pid"] for s in specs}
        need = []
        for p in mine:
            if p["id"] in taken:
                continue
            have = self.onhand(p["id"], ts) + self.pending[p["id"]]
            rop = max(p["d"] * REORDER_DAYS, p["thr"] * LEAD_BUFFER)
            target = max(p["d"] * TARGET_DAYS, p["thr"] * 2.5)
            cover = have / max(p["d"], 0.01)
            if have <= rop:
                need.append((cover, p, ceil_to(target - have, p["step"])))
        if force and len(need) + len(specs) < 3:
            # Ngày cuối: đảm bảo phiếu có >= 3 dòng (để còn có phiếu "đang đếm dở" thật) —
            # bổ sung những mặt hàng còn ít ngày bán nhất của nhà cung cấp này.
            skip = taken | {p["id"] for _, p, _ in need}
            ranked = sorted(((self.onhand(p["id"], ts) / max(p["d"], 0.01), p) for p in mine if p["id"] not in skip),
                            key=lambda x: x[0])[:3 - len(need) - len(specs) + self.rng.randint(0, 2)]
            need += [(c, p, p["step"] * self.rng.randint(2, 4)) for c, p in ranked]
        need.sort(key=lambda x: x[0])
        for _, p, qty in need[:9]:
            specs.append(dict(pid=p["id"], qty=max(qty, p["step"]), exp=None, forgotten=False, prod=None))
        if len(specs) > 10:
            specs = specs[:10]
        for s in specs:
            p = self.P[s["pid"]]
            if s["exp"] is None and p["shelf"]:
                prod = day - timedelta(days=self.rng.randint(5, 40))
                s["prod"] = prod
                s["exp"] = prod + timedelta(days=p["shelf"] + self.rng.randint(-10, 10))
            elif s["exp"] is None:
                s["prod"] = day - timedelta(days=self.rng.randint(10, 90))
        return specs

    def ev_receipt(self, ts, sup, mode, force, flagged):
        day = ts.date()
        if flagged:
            specs = []
        else:
            specs = self.plan_lines(day, sup, ts, force)
            if not specs:
                return
        manual = (not flagged) and mode == "full" and self.rng.random() < 0.22
        n = self.counters["PN"] + 1
        code = self.code("PN")
        rc = models.ImportReceipt(
            receipt_code=code, store_location=SUPPLIERS[sup], image_path=None, status="ocr_done",
            source_type="manual" if manual else "ocr", received_at=ts, created_at=ts)
        self.db.add(rc)
        self.db.flush()

        lines, plans = [], []
        if flagged:  # phiếu chụp mờ: OCR đọc lỗi, dòng chưa nhận ra sản phẩm -> chờ nhân viên xử lý
            rc.status, rc.ocr_confidence = "flagged", round(self.rng.uniform(0.55, 0.68), 4)
            garbled = [("Banh keo dua", 15), ("Nuoc mam Nam N9u", 8)]
            for i, (nm, q) in enumerate(garbled, start=1):
                li = models.ReceiptLineItem(
                    receipt_id=rc.id, line_no=i, product_name_raw=nm, product_id=None, quantity=q, batch_code=None,
                    expiry_date=None, match_score=round(self.rng.uniform(0.4, 0.62), 4),
                    field_confidence={"quantity": 0.71, "batch": 0.2, "expiry": 0.18}, created_at=ts)
                self.db.add(li)
                lines.append(li)
        else:
            for i, s in enumerate(specs, start=1):
                p = self.P[s["pid"]]
                raw, score = (p["name"], 1.0) if manual else self.raw_variant(p["name"])
                bcode = self.batch_code(p["id"], s["prod"])
                while any(pl["code"] == bcode and pl["pid"] == p["id"] for pl in plans):
                    bcode = self.batch_code(p["id"], s["prod"] - timedelta(days=1))
                li = models.ReceiptLineItem(
                    receipt_id=rc.id, line_no=i, product_name_raw=raw, product_id=p["id"], quantity=s["qty"],
                    batch_code=bcode, expiry_date=s["exp"], match_score=score,
                    field_confidence=None if manual else {
                        "quantity": round(self.rng.uniform(0.9, 0.995), 4),
                        "batch": round(self.rng.uniform(0.86, 0.99), 4),
                        "expiry": round(self.rng.uniform(0.88, 0.99), 4)},
                    created_at=ts)
                self.db.add(li)
                lines.append(li)
                plans.append(dict(pid=p["id"], code=bcode, forgotten=s["forgotten"]))
                self.pending[p["id"]] += s["qty"]
            if mode == "none" and not manual:  # hàng mới chưa có trong danh mục: dòng "chưa gán SP"
                extra = models.ReceiptLineItem(
                    receipt_id=rc.id, line_no=len(lines) + 1, product_name_raw="Sữa tươi Vinamilk Green Farm 1L",
                    product_id=None, quantity=6, batch_code=self.batch_code(self.by_sku["SP-001"]["id"], day - timedelta(days=12)),
                    expiry_date=day + timedelta(days=130), match_score=0.58,
                    field_confidence={"quantity": 0.93, "batch": 0.88, "expiry": 0.9}, created_at=ts)
                self.db.add(extra)
                lines.append(extra)
        self.db.flush()
        for pl, li in zip(plans, lines):
            pl["line"] = li

        if not manual:
            rows = [(l.product_name_raw, int(l.quantity), l.batch_code, l.expiry_date) for l in lines]
            raw_text = "\n".join(
                [f"PHIẾU NHẬP HÀNG #{n}", f"Ngày nhập: {day:%d/%m/%Y}", f"Đại lý: {SUPPLIERS[sup]}",
                 "Tên sản phẩm Số lượng Mã lô HSD"]
                + [f"{r[0]} {r[1]} {r[2] or ''} {r[3]:%d/%m/%Y}" if r[3] else f"{r[0]} {r[1]} {r[2] or ''}" for r in rows]
                + ["Người giao hàng: Người nhận hàng:"])
            rc.ocr_raw_text = raw_text
            if not flagged:
                confs = [min(l.field_confidence.values()) for l in lines if l.field_confidence]
                rc.ocr_confidence = round(min(0.985, max(0.88, sum(confs) / len(confs) + 0.06)), 4)
            if self.renderer:
                name = f"{uuid.uuid4().hex}.jpg"
                path = RECEIPT_DIR / name
                self.renderer.render(path, n, SUPPLIERS[sup], ts, rows, self.rng)
                self.new_files.append(path)
                rc.image_path = f"./uploads/receipts/{name}"
        self.stats["receipts"] += 1
        self.stats["receipt_lines"] += len(lines)
        self.rstate[rc.id] = dict(rc=rc, total=len(lines), done=0)
        if mode == "none" or flagged:
            return

        if mode == "partial" and len(plans) < 2:
            return  # phiếu 1 dòng không thể "đếm dở" — để nguyên chưa đếm
        k = len(plans) if mode == "full" else max(1, round(len(plans) * 0.6))
        t = ts + timedelta(minutes=self.rng.randint(12, 25))
        for i, pl in enumerate(plans[:k]):
            t_start = t
            t_end = t_start + timedelta(seconds=self.rng.randint(90, 240))
            if t_end > self.now - timedelta(minutes=1):
                break
            r = self.rng.random()
            outcome = "recount" if r < 0.062 else "override" if r < 0.092 else "match"
            if mode == "partial" and i == 1:
                outcome = "open"
            self.push(t_end, "line_done", rcid=rc.id, pl=pl, t_start=t_start, outcome=outcome)
            t = t_end + timedelta(minutes=self.rng.randint(2, 6))

    # ---------------- đếm camera cho từng dòng phiếu
    def session(self, direction, ts_start, ts_end, counted, expected, status, pid, rcid=None, lid=None, prefix="DEM"):
        s = models.CameraCountSession(
            session_code=self.code(prefix), camera_id="cam-01" if self.rng.random() < 0.85 else "cam-02",
            direction=direction, linked_receipt_id=rcid, receipt_line_item_id=lid, product_id=pid,
            expected_quantity=expected, counted_quantity=counted,
            avg_detection_confidence=round(self.rng.uniform(0.82, 0.95), 4), model_version=MODEL_VERSION,
            status=status, started_at=ts_start, ended_at=ts_end, created_at=ts_start)
        self.db.add(s)
        self.db.flush()
        self.stats[f"session_{direction}"] += 1
        return s

    def recon(self, s, expected, counted, status, ts, pid, rcid=None, lid=None):
        r = models.Reconciliation(
            receipt_id=rcid, receipt_line_item_id=lid, product_id=pid, session_id=s.id, receipt_total=expected,
            camera_total=counted, difference=counted - expected, threshold_used=0.0, status=status, created_at=ts)
        self.db.add(r)
        self.db.flush()
        return r

    def discrepancy_alert(self, direction, name, counted, expected, s, r, ts):
        a = models.Alert(
            alert_type="discrepancy", severity="high", reconciliation_id=r.id, status="open", created_at=ts,
            message=(f"[{direction.upper()}] Lệch {counted - expected:+.0f} khi đếm '{name}' — camera đếm {counted}, "
                     f"cần {expected:.0f} (vượt ngưỡng 0.0%). Chưa cập nhật tồn kho cho loại này — "
                     f"cần kiểm tra lại (phiên #{s.id})."))
        self.db.add(a)
        self.stats["alert_discrepancy"] += 1
        return a

    def apply_import(self, line, qty, ts, pl):
        b = self.batch_by_key.get((line.product_id, line.batch_code))
        if b is None:
            b = self.new_batch(line.product_id, line.batch_code, line.expiry_date, ts, forgotten=pl["forgotten"])
        self.tx(b, qty, ts, "import", "receipt_line", line.id, None)
        b.avail_from = b.last_in = ts
        self.pending[line.product_id] = max(0, self.pending[line.product_id] - int(line.quantity))
        for ob in self.batches[line.product_id]:  # hàng đã về -> nhân viên xác nhận cảnh báo sắp hết của sản phẩm này
            if ob.open_alert is not None and ob.open_alert.status == "open" and ob is not b:
                ob.open_alert.status = "acknowledged"

    def finish_line(self, rcid):
        st = self.rstate[rcid]
        st["done"] += 1
        if st["done"] == st["total"]:
            st["rc"].status = "reconciled"  # đúng _maybe_complete_receipt: xong mọi dòng thì phiếu xong

    def mismatch_count(self, expected: int) -> int:
        delta = self.rng.choice([-1, -2, -3, -1, -2, 1, 2]) * (2 if expected >= 40 else 1)
        c = max(0, expected + delta)
        return c if c != expected else expected + 1

    def ev_line_done(self, ts, rcid, pl, t_start, outcome):
        line, pid = pl["line"], pl["line"].product_id
        name, expected = line.product_name_raw, int(line.quantity)
        if outcome == "match":
            s = self.session("import", t_start, ts, expected, expected, "completed", pid, rcid, line.id)
            self.recon(s, expected, expected, "matched", ts, pid, rcid, line.id)
            self.apply_import(line, expected, ts, pl)
            self.finish_line(rcid)
            return
        c1 = self.mismatch_count(expected)
        s1 = self.session("import", t_start, ts, c1, expected, "needs_review", pid, rcid, line.id)
        r1 = self.recon(s1, expected, c1, "flagged", ts, pid, rcid, line.id)
        alert = self.discrepancy_alert("import", name, c1, expected, s1, r1, ts)
        if outcome == "open":
            return
        if outcome == "recount":
            t2 = ts + timedelta(minutes=self.rng.randint(4, 12))
            self.push(t2, "line_recount", rcid=rcid, pl=pl, s1=s1, alert=alert, t_start=ts + timedelta(minutes=2))
        else:
            self.push(ts + timedelta(minutes=self.rng.randint(15, 70)), "line_override", rcid=rcid, pl=pl, s1=s1,
                      r1=r1, alert=alert, c1=c1)

    def ev_line_recount(self, ts, rcid, pl, s1, alert, t_start):
        line, pid = pl["line"], pl["line"].product_id
        expected = int(line.quantity)
        s1.status = "superseded"
        s2 = self.session("import", t_start, ts, expected, expected, "completed", pid, rcid, line.id)
        self.recon(s2, expected, expected, "matched", ts, pid, rcid, line.id)
        self.apply_import(line, expected, ts, pl)
        alert.status = "acknowledged"
        self.finish_line(rcid)

    def ev_line_override(self, ts, rcid, pl, s1, r1, alert, c1):
        line = pl["line"]
        s1.status = "resolved_override"
        r1.status, r1.resolved_by = "resolved_override", self.rng.choice(STAFF)
        r1.resolved_note, r1.resolved_at = self.rng.choice(OVERRIDE_NOTES), ts
        self.apply_import(line, c1, ts, pl)  # ghi đè: cộng kho theo SỐ CAMERA, không phải số trên phiếu
        alert.status = "acknowledged"
        self.finish_line(rcid)

    # ---------------- đơn khách -> xuất kho
    def ev_order(self, ts):
        order = self.code("DH")
        customer = self.rng.choice(CUSTOMERS)
        n_lines = self.rng.choices([2, 3, 4, 5, 6], weights=[20, 30, 25, 15, 10])[0]
        pids = list(self.P)
        weights = [self.P[p]["f"] for p in pids]
        chosen: list[int] = []
        while len(chosen) < n_lines:
            pid = self.rng.choices(pids, weights=weights)[0]
            if pid not in chosen:
                chosen.append(pid)
        t = ts
        for pid in chosen:
            p = self.P[pid]
            qty = max(1, int(round(p["q"] * self.rng.lognormvariate(0, 0.45))))
            camera = qty >= 4 and self.rng.random() < 0.55
            if t <= self.now - timedelta(minutes=1):
                self.push(t, "export_line", pid=pid, qty=qty, order=order, customer=customer, camera=camera)
            t += timedelta(minutes=self.rng.randint(2, 6))

    def ev_export_line(self, ts, pid, qty, order, customer, camera):
        avail = self.onhand(pid, ts)
        if avail <= 0:
            self.stats["stockout_lines"] += 1  # hết hàng đúng lúc khách hỏi — thực tế vẫn xảy ra
            return
        qty = min(qty, avail)
        if not camera:
            self.export_fefo(pid, qty, ts, f"Đơn {order} — {customer}", "manual", None)
            return
        p = self.P[pid]
        t_start = ts - timedelta(minutes=self.rng.randint(2, 6))
        outcome = "match"
        if ts.date() == self.last_day and self.open_export_pending and qty >= 4:
            outcome, self.open_export_pending = "open", False
        elif qty >= 4 and self.rng.random() < 0.004:
            outcome = "override"
        if outcome == "match":
            s = self.session("export", t_start, ts, qty, qty, "completed", pid, prefix="PX")
            self.recon(s, qty, qty, "matched", ts, pid)
            self.export_fefo(pid, qty, ts, f"Xuất qua camera, phiên #{s.id}", "camera_session", s.id)
            return
        c1 = max(1, qty - self.rng.randint(1, 2))
        s = self.session("export", t_start, ts, c1, qty, "needs_review", pid, prefix="PX")
        r = self.recon(s, qty, c1, "flagged", ts, pid)
        alert = self.discrepancy_alert("export", p["name"], c1, qty, s, r, ts)
        if outcome == "override":
            self.push(ts + timedelta(minutes=self.rng.randint(8, 40)), "export_override", s=s, r=r, alert=alert, pid=pid, c1=c1)

    def ev_export_override(self, ts, s, r, alert, pid, c1):
        note = self.rng.choice(OVERRIDE_NOTES)
        s.status, r.status = "resolved_override", "resolved_override"
        r.resolved_by, r.resolved_note, r.resolved_at = self.rng.choice(STAFF), note, ts
        self.export_fefo(pid, min(c1, self.onhand(pid, ts)), ts, f"Xuất qua camera (ghi đè lệch số): {note}", "camera_session", s.id)
        alert.status = "acknowledged"

    # ---------------- huỷ hàng hết hạn + kiểm kê
    def ev_dispose(self, ts):
        day, code = ts.date(), None
        for bl in self.batches.values():
            for b in bl:
                if b.qty > 0 and b.exp is not None and b.exp <= day - timedelta(days=4):
                    code = code or self.code("HH", 3)
                    self.tx(b, -b.qty, ts, "export", "manual", None, f"Xuất huỷ hàng hết hạn — biên bản huỷ {code}")
                    self.check_low_alert(b, ts)
                    self.stats["disposed_batches"] += 1

    def ev_stocktake(self, ts):
        cands = [b for bl in self.batches.values() for b in bl if b.qty >= 6 and not b.forgotten]
        for b in self.rng.sample(cands, min(5, len(cands))):
            if self.rng.random() < 0.8:
                d = -self.rng.randint(1, 3)
                note = "Kiểm kê cuối tháng — hao hụt do vỡ/móp bao bì"
            else:
                d, note = 1, "Kiểm kê cuối tháng — tìm thấy thùng để nhầm kệ"
            self.tx(b, d, ts, "adjustment", "manual", None, note)

    # ---------------- hoàn tất
    def assign_locations(self):
        for pid, bl in self.batches.items():
            rack = self.P[pid]["rack"]
            for lvl, b in enumerate(sorted(bl, key=lambda b: b.exp or date.max), start=1):
                shelved = b.last_in is None or (self.now - b.last_in) > timedelta(hours=18)
                if shelved and (b.qty > 0 or self.rng.random() < 0.95):
                    b.row.location = f"Kệ {rack[0]}{rack[1:]}-{((lvl - 1) % 4) + 1:02d}"


# ------------------------------------------------------------------ KIỂM TRA + XOÁ
def verify(db) -> list[str]:
    """Kiểm tra tính nhất quán dữ liệu vừa tạo. Trả về danh sách lỗi (rỗng = ổn)."""
    errs = []
    tx_sum = dict(db.query(models.InventoryTransaction.inventory_id, func.sum(models.InventoryTransaction.change_qty))
                  .group_by(models.InventoryTransaction.inventory_id).all())
    for inv in db.query(models.Inventory).all():
        s = float(tx_sum.get(inv.id, 0) or 0)
        if abs(s - float(inv.quantity)) > 1e-6:
            errs.append(f"lô #{inv.id} {inv.batch_code}: tồn {inv.quantity} != tổng giao dịch {s}")
        if float(inv.quantity) < 0:
            errs.append(f"lô #{inv.id}: tồn kho âm")
    done_lines = {r[0] for r in db.query(models.InventoryTransaction.reference_id)
                  .filter(models.InventoryTransaction.reference_type == "receipt_line").all()}
    for rc in db.query(models.ImportReceipt).all():
        lines = db.query(models.ReceiptLineItem).filter_by(receipt_id=rc.id).all()
        all_done = bool(lines) and all(l.id in done_lines for l in lines)
        if rc.status == "reconciled" and not all_done:
            errs.append(f"phiếu {rc.receipt_code} 'reconciled' nhưng còn dòng chưa cộng kho")
        if rc.status == "ocr_done" and lines and all_done:
            errs.append(f"phiếu {rc.receipt_code} đã xong mọi dòng nhưng chưa 'reconciled'")
        if rc.status == "reconciled" and any(l.product_id is None for l in lines):
            errs.append(f"phiếu {rc.receipt_code} reconciled nhưng có dòng chưa gán SP")
    for s in db.query(models.CameraCountSession).filter(models.CameraCountSession.status == "completed",
                                                         models.CameraCountSession.direction == "import").all():
        if s.receipt_line_item_id not in done_lines:
            errs.append(f"phiên {s.session_code} completed nhưng dòng chưa cộng kho")
    return errs


def wipe(db):
    if engine.dialect.name == "postgresql":  # TRUNCATE ... RESTART IDENTITY để mã/ID bắt đầu lại từ 1
        db.execute(text("TRUNCATE TABLE alerts, reconciliations, camera_count_sessions, inventory_transactions, "
                        "receipt_line_items, import_receipts, inventory, products RESTART IDENTITY CASCADE"))
    else:
        for m in (models.Alert, models.Reconciliation, models.CameraCountSession, models.InventoryTransaction,
                  models.ReceiptLineItem, models.ImportReceipt, models.Inventory, models.Product):
            db.query(m).delete()


def guard_target(args) -> None:
    """Chặn CSDL từ xa NGAY ĐẦU (trước khi kết nối/tạo bảng), tránh lỡ tay xoá nhầm DB trên server."""
    host = make_url(DATABASE_URL).host or "(file cục bộ)"
    if host not in ("localhost", "127.0.0.1", "::1", "(file cục bộ)") and not args.allow_remote:
        sys.exit(f"❌ Từ chối: CSDL nằm ở máy từ xa ({host}) — {make_url(DATABASE_URL).render_as_string(hide_password=True)}\n"
                 "   Nếu CHẮC CHẮN muốn xoá, thêm --allow-remote.")


def confirm(args, db) -> None:
    url = make_url(DATABASE_URL)
    print("=" * 66)
    print(f"  CSDL ĐÍCH : {url.render_as_string(hide_password=True)}")
    print("  SẼ XOÁ SẠCH các bảng dữ liệu kho (push_subscriptions được giữ lại):")
    for label, m in (("sản phẩm", models.Product), ("lô tồn kho", models.Inventory),
                     ("giao dịch kho", models.InventoryTransaction), ("phiếu nhập", models.ImportReceipt),
                     ("dòng phiếu", models.ReceiptLineItem), ("phiên đếm", models.CameraCountSession),
                     ("đối chiếu", models.Reconciliation), ("cảnh báo", models.Alert)):
        print(f"    - {label:<14}: {db.query(m).count():>6} dòng")
    print("  Nên sao lưu trước:  pg_dump -U postgres warehouse_db > backup.sql")
    print("=" * 66)
    if args.yes:
        return
    if not sys.stdin.isatty():
        sys.exit("❌ Không có bàn phím để xác nhận — thêm --yes nếu muốn chạy không hỏi.")
    if input("Gõ XOA (viết hoa) để xác nhận xoá và tạo lại dữ liệu: ").strip() != "XOA":
        sys.exit("Đã huỷ — không có gì bị thay đổi.")


def clear_uploads(keep: set[Path]) -> int:
    n = 0
    for sub in ("receipts", "annotated_videos", "camera_videos"):
        folder = UPLOADS_DIR / sub
        if not folder.is_dir():
            continue
        for f in folder.iterdir():
            if f.is_file() and f.name != ".gitkeep" and f.resolve() not in keep:
                f.unlink()
                n += 1
    return n


def main():
    ap = argparse.ArgumentParser(description="Xoá dữ liệu kho và tạo bộ dữ liệu thực tế (mô phỏng theo thời gian).")
    ap.add_argument("--yes", action="store_true", help="Không hỏi xác nhận")
    ap.add_argument("--days", type=int, default=84, help="Số ngày lịch sử mô phỏng (mặc định 84 = 12 tuần)")
    ap.add_argument("--seed", type=int, default=2026, help="Hạt giống ngẫu nhiên (cùng seed + cùng ngày -> cùng dữ liệu)")
    ap.add_argument("--no-images", action="store_true", help="Không vẽ ảnh phiếu nhập")
    ap.add_argument("--font", help="Đường dẫn font .ttf có dấu tiếng Việt (nếu không tự tìm được)")
    ap.add_argument("--clear-uploads", action="store_true", help="Xoá luôn ảnh/video đã upload trước đó")
    ap.add_argument("--allow-remote", action="store_true", help="Cho phép chạy trên CSDL không phải localhost")
    args = ap.parse_args()

    guard_target(args)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        confirm(args, db)
        renderer = None
        if not args.no_images:
            try:
                RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
                renderer = ReceiptRenderer(args.font)
            except Exception as e:  # noqa: BLE001
                print(f"⚠️  Không vẽ được ảnh phiếu ({e}) — phiếu quét sẽ KHÔNG có ảnh. Cài Pillow hoặc dùng --font.")
        rng = random.Random(args.seed)
        now = datetime.now(VN_TZ)
        print("Đang xoá dữ liệu cũ và mô phỏng hoạt động kho… (có thể mất ~1 phút)")
        wipe(db)
        sim = Simulator(db, rng, now, args.days, renderer)
        sim.run()
        sim.assign_locations()
        db.flush()
        errs = verify(db)
        if errs:
            db.rollback()
            for f in sim.new_files:
                f.unlink(missing_ok=True)
            print("❌ Dữ liệu vừa tạo KHÔNG nhất quán — đã HOÀN TÁC, dữ liệu cũ còn nguyên:")
            for e in errs[:15]:
                print("   -", e)
            sys.exit(1)
        db.commit()
    except SystemExit:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    removed = clear_uploads({f.resolve() for f in sim.new_files}) if args.clear_uploads else 0
    db = SessionLocal()
    try:
        today = now.date()
        q = lambda m: db.query(m).count()  # noqa: E731
        inv = db.query(models.Inventory).all()
        in_stock = [i for i in inv if float(i.quantity) > 0]
        expired = [i for i in in_stock if i.expiry_date and i.expiry_date < today]
        soon = [i for i in in_stock if i.expiry_date and today <= i.expiry_date <= today + timedelta(days=30)]
        by_status = dict(db.query(models.ImportReceipt.status, func.count()).group_by(models.ImportReceipt.status).all())
        by_source = dict(db.query(models.ImportReceipt.source_type, func.count()).group_by(models.ImportReceipt.source_type).all())
        open_alerts = dict(db.query(models.Alert.alert_type, func.count()).filter(models.Alert.status == "open")
                           .group_by(models.Alert.alert_type).all())
        n_export = db.query(models.InventoryTransaction).filter_by(transaction_type="export").count()
        print("\n" + "=" * 66)
        print(f"✅ HOÀN TẤT — {sim.start:%d/%m/%Y} → {today:%d/%m/%Y} ({args.days} ngày, nghỉ chủ nhật)")
        print("=" * 66)
        print(f"  Sản phẩm            : {q(models.Product)}")
        print(f"  Lô tồn kho          : {len(inv)}  (còn hàng: {len(in_stock)})")
        print(f"  Giao dịch kho       : {q(models.InventoryTransaction)}  (xuất: {n_export})")
        print(f"  Phiếu nhập          : {q(models.ImportReceipt)}  trạng thái {by_status}  nguồn {by_source}")
        print(f"  Dòng phiếu          : {q(models.ReceiptLineItem)}")
        print(f"  Phiên đếm camera    : {q(models.CameraCountSession)}  (đối chiếu: {q(models.Reconciliation)})")
        print(f"  Cảnh báo            : {q(models.Alert)}  (đang mở: {open_alerts or 0})")
        print(f"  Lô hết hạn chưa huỷ : {len(expired)}   |   sắp hết hạn ≤30 ngày: {len(soon)}")
        print(f"  Ảnh phiếu đã vẽ     : {len(sim.new_files)}")
        if args.clear_uploads:
            print(f"  Đã xoá file upload cũ: {removed}")
        print("\n  Mở lại ứng dụng (F5) để thấy dữ liệu mới.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
