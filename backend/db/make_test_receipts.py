"""Tạo vài ẢNH PHIẾU NHẬP để thử chức năng "Quét phiếu mới" (OCR) của ứng dụng.

KHÔNG đụng vào cơ sở dữ liệu — chỉ vẽ ra file ảnh + file README ghi nội dung đúng của
từng phiếu để bạn đối chiếu với kết quả OCR đọc được.

    python -m db.make_test_receipts                    # tạo vào thư mục ./phieu_test
    python -m db.make_test_receipts --out D:\\test      # chọn thư mục khác
    python -m db.make_test_receipts --font C:\\Windows\\Fonts\\arial.ttf

Có 3 kiểu ảnh, từ dễ đến khó:
  - "sạch"    : nền trắng, thẳng, chữ đen — cùng bố cục phiếu mẫu đã đọc tốt (dễ nhất)
  - "ảnh chụp": tờ phiếu trên mặt bàn, hơi nghiêng, hơi nhiễu — giống chụp bằng điện thoại
  - "tối mờ"  : thiếu sáng, hơi nhoè, nghiêng nhiều — để thử trường hợp OCR đọc kém

Mã lô trên phiếu test dùng dạng L###X (vd L412A) nên KHÔNG trùng mã lô của bộ dữ liệu seed.
Ngày nhập = hôm nay; HSD luôn ở tương lai. Mọi dòng đều có đủ 4 ô (tên, số lượng, mã lô,
HSD) vì bộ đọc bảng gom theo nhóm 4 ô liên tiếp — dòng thiếu HSD sẽ làm lệch cả nhóm.
"""
from __future__ import annotations

import argparse
import random
import sys
from datetime import date, timedelta
from pathlib import Path

FONT_PAIRS = [  # (thường, đậm) — font có đủ dấu tiếng Việt, tuỳ hệ điều hành
    (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
    (r"C:\Windows\Fonts\tahoma.ttf", r"C:\Windows\Fonts\tahomabd.ttf"),
    (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\segoeuib.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
]

# (tên in trên phiếu, số lượng, mã lô, HSD còn bao nhiêu ngày kể từ hôm nay)
RECEIPTS = [
    dict(
        file="phieu_test_01_de_doc.png", style="clean", number=901,
        supplier="Nhà phân phối Sài Gòn Food",
        purpose="Phiếu DỄ NHẤT: ảnh sạch, tên sản phẩm đúng 100% như danh mục. Dùng để thử luồng cơ bản: "
                "quét -> kiểm tra dòng -> đếm camera -> cộng kho.",
        expect="Cả 4 dòng đọc đúng và tự gán đúng sản phẩm; phiếu ở trạng thái 'Chờ đếm hàng'.",
        lines=[
            ("Mì Hảo Hảo tôm chua cay", 40, "L412A", 150),
            ("Mì Omachi sốt bò hầm", 24, "L413B", 140),
            ("Mì Kokomi tôm chua cay", 20, "L414C", 145),
            ("Phở bò ăn liền Vifon", 12, "L415D", 120),
        ],
    ),
    dict(
        file="phieu_test_02_anh_chup.jpg", style="photo", number=902,
        supplier="Đại lý Nước giải khát Minh Phát",
        purpose="Giống ảnh chụp điện thoại: tờ phiếu nằm trên bàn, hơi nghiêng, hơi nhiễu. Tên sản phẩm đúng.",
        expect="Đọc được cả 5 dòng; có thể có 1-2 ô số/mã lô đọc nhầm — hãy sửa tay ở bước kiểm tra dòng.",
        lines=[
            ("Nước suối Lavie 500ml", 30, "L521M", 600),
            ("Nước suối Aquafina 500ml", 30, "L522N", 590),
            ("Coca-Cola lon 330ml", 24, "L523P", 300),
            ("Pepsi lon 330ml", 24, "L524Q", 310),
            ("Trà xanh không độ 455ml", 12, "L525R", 280),
        ],
    ),
    dict(
        file="phieu_test_03_ten_khong_dau.png", style="clean", number=903,
        supplier="Công ty TNHH Gia vị Việt Tín",
        purpose="Tên sản phẩm VIẾT KHÔNG DẤU / IN HOA / RÚT GỌN — để thử so khớp gần đúng với danh mục "
                "(ngưỡng khớp 0,75) và các nút 'Gợi ý từ danh mục'.",
        expect="Dự đoán (tính bằng đúng hàm so khớp của dự án trên danh mục seed): chỉ 'Nuoc mam Chinsu 500ml' tự gán; "
               "3 dòng còn lại 'chưa gán SP' (điểm khớp 0,36-0,64 < 0,75) — gán bằng ô chọn sản phẩm hoặc nút '💡 Gợi ý từ danh mục'.",
        lines=[
            ("DAU AN SIMPLY 1L", 12, "L631E", 480),
            ("Nuoc mam Chinsu 500ml", 10, "L632F", 650),
            ("HAT NEM KNORR THIT THAN 900G", 8, "L633G", 640),
            ("Duong cat trang Bien Hoa 1kg", 20, "L634H", 600),
        ],
    ),
    dict(
        file="phieu_test_04_co_san_pham_moi.png", style="clean", number=904,
        supplier="Công ty CP Thương mại Hưng Thịnh",
        purpose="Có 2 sản phẩm CHƯA CÓ trong danh mục (7Up, Hura Swiss Roll) — để thử nút "
                "'+ Tạo sản phẩm mới từ tên …' và luồng gán sản phẩm trước khi đếm.",
        expect="Dự đoán: 7Up và Hura 'chưa gán SP' (điểm khớp 0,58 và 0,62); Alpenliebe và Oreo tự gán (1,00). "
               "Phải gán hoặc tạo sản phẩm cho 2 dòng đầu rồi mới đếm được.",
        lines=[
            ("Nước ngọt 7Up lon 330ml", 24, "L741J", 320),
            ("Bánh Hura Swiss Roll hộp", 10, "L742K", 160),
            ("Kẹo Alpenliebe", 15, "L743L", 500),
            ("Bánh Oreo hộp 133g", 12, "L744M", 250),
        ],
    ),
    dict(
        file="phieu_test_05_dai_8_dong.jpg", style="photo", number=905,
        supplier="Chành hoá phẩm Phú Lộc",
        purpose="Phiếu DÀI 8 dòng, ảnh chụp: thử danh sách phiếu ('+N sản phẩm khác'), đếm lần lượt nhiều loại hàng.",
        expect="Đọc được 8 dòng (có thể sai vài ô); thẻ phiếu trong danh sách hiện 3 dòng đầu + '+5 sản phẩm khác'.",
        lines=[
            ("Bột giặt Omo 3kg", 12, "L851A", 1000),
            ("Bột giặt Ariel 3kg", 10, "L852B", 1000),
            ("Nước xả Comfort 1.5L", 8, "L853C", 980),
            ("Nước rửa chén Sunlight 750g", 12, "L854D", 990),
            ("Nước lau sàn Sunlight 1L", 6, "L855E", 970),
            ("Dầu gội Clear men 630g", 6, "L856F", 1000),
            ("Sữa tắm Lifebuoy 850g", 6, "L857G", 995),
            ("Kem đánh răng P/S 230g", 20, "L858H", 1050),
        ],
    ),
    dict(
        file="phieu_test_06_mo_toi.jpg", style="dark", number=906,
        supplier="Công ty TNHH Phân phối An Bình",
        purpose="Ảnh THIẾU SÁNG, hơi nhoè, nghiêng nhiều — trường hợp xấu. Thử cách ứng dụng xử lý khi OCR "
                "đọc kém (điểm tin cậy thấp, thiếu dòng, đọc sai).",
        expect="Rất có thể đọc sai/thiếu vài ô hoặc cả phiếu bị đánh dấu lỗi OCR — đó là kết quả bình thường của ca khó này.",
        lines=[
            ("Sữa tươi Vinamilk 100% có đường 1L", 24, "L961S", 120),
            ("Sữa tươi TH True Milk ít đường 1L", 18, "L962T", 150),
            ("Sữa đặc Ông Thọ lon 380g", 10, "L963U", 500),
        ],
    ),
]


class Painter:
    def __init__(self, font_path: str | None):
        from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont  # noqa: F401

        self.Image, self.ImageDraw, self.ImageEnhance = Image, ImageDraw, ImageEnhance
        self.ImageFilter, self.ImageFont = ImageFilter, ImageFont
        self.regular = self.bold = None
        for reg, bld in ([(font_path, font_path)] if font_path else []) + FONT_PAIRS:
            if Path(reg).exists():
                self.regular, self.bold = reg, (bld if Path(bld).exists() else reg)
                break
        if not self.regular:
            sys.exit("❌ Không tìm thấy font có dấu tiếng Việt — dùng --font <đường dẫn file .ttf>")

    def font(self, bold: bool, size: int):
        return self.ImageFont.truetype(self.bold if bold else self.regular, size)

    def paper(self, spec: dict, today: date, clean: bool):
        W, M, ROW, HEAD = 1000, 50, 44, 50
        rows = spec["lines"]
        H = M + 70 + 2 * 32 + 20 + HEAD + len(rows) * ROW + 40 + 90
        bg = (255, 255, 255) if clean else (252, 252, 250)
        img = self.Image.new("RGB", (W, H), bg)
        d = self.ImageDraw.Draw(img)
        if not clean:
            d.rectangle([0, 0, W - 1, H - 1], outline=(200, 200, 196), width=2)
        d.text((W // 2, M + 18), f"PHIẾU NHẬP HÀNG #{spec['number']}", font=self.font(True, 34), fill=(20, 20, 20), anchor="mm")
        y = M + 70
        for line in (f"Ngày nhập: {today:%d/%m/%Y}", f"Đại lý: {spec['supplier']}"):
            d.text((M + 20, y), line, font=self.font(False, 22), fill=(25, 25, 25))
            y += 32
        y += 20
        cols = [("Tên sản phẩm", 500), ("Số lượng", 120), ("Mã lô", 150), ("HSD", 130)]
        d.rectangle([M, y, M + sum(w for _, w in cols), y + HEAD], fill=(210, 210, 210), outline=(30, 30, 30), width=2)
        cx = M
        for title, w in cols:
            d.text((cx + 12, y + HEAD // 2), title, font=self.font(False, 22), fill=(15, 15, 15), anchor="lm")
            cx += w
        y += HEAD
        for name, qty, batch, days_left in rows:
            cells = [name, str(qty), batch, f"{today + timedelta(days=days_left):%d/%m/%Y}"]
            cx = M
            for i, ((_, w), cell) in enumerate(zip(cols, cells)):
                size = 22
                while size > 15 and self.font(False, size).getlength(cell) > w - 20:
                    size -= 1  # tên dài thì thu nhỏ chữ cho vừa ô, không cắt bớt
                d.rectangle([cx, y, cx + w, y + ROW], outline=(30, 30, 30), width=2)
                anchor, tx = ("lm", cx + 12) if i == 0 else ("mm", cx + w // 2)
                d.text((tx, y + ROW // 2), cell, font=self.font(False, size), fill=(10, 10, 10), anchor=anchor)
                cx += w
            y += ROW
        d.text((M + 20, y + 45), "Người giao hàng: ____________   Người nhận hàng: ____________",
               font=self.font(False, 22), fill=(25, 25, 25))
        return img

    def render(self, spec: dict, today: date, path: Path, rng: random.Random):
        style = spec["style"]
        img = self.paper(spec, today, clean=(style == "clean"))
        if style == "clean":
            img.save(path, "PNG")
            return
        W, H = img.size
        col = (rng.randint(80, 120), rng.randint(70, 105), rng.randint(60, 95))
        desk = self.Image.new("RGB", (W + 120, H + 120), col)
        desk.paste(img, (60, 60))
        dark = style == "dark"
        angle = rng.choice([-1, 1]) * (rng.uniform(2.5, 3.5) if dark else rng.uniform(0.8, 1.6))
        desk = desk.rotate(angle, resample=self.Image.BICUBIC, expand=True, fillcolor=col)
        desk = self.ImageEnhance.Brightness(desk).enhance(rng.uniform(0.5, 0.62) if dark else rng.uniform(0.92, 1.04))
        desk = desk.filter(self.ImageFilter.GaussianBlur(1.4 if dark else rng.uniform(0.3, 0.7)))
        noise = self.Image.effect_noise(desk.size, 14 if dark else rng.uniform(4, 8)).convert("RGB")
        desk = self.Image.blend(desk, noise, 0.10 if dark else 0.04)
        desk.thumbnail((1000, 1400))
        desk.save(path, "JPEG", quality=58 if dark else 84)


def write_readme(out: Path, today: date):
    parts = [
        "PHIẾU NHẬP DÙNG ĐỂ TEST — nội dung ĐÚNG của từng ảnh (để đối chiếu với kết quả OCR)",
        f"Ngày nhập trên phiếu: {today:%d/%m/%Y}.  Cột: Tên sản phẩm | Số lượng | Mã lô | HSD",
        "Cách thử: Nhập kho -> '+ Quét phiếu mới' -> chọn ảnh -> xem kết quả OCR -> sửa dòng sai -> đếm.",
        "",
    ]
    for r in RECEIPTS:
        parts += [f"=== {r['file']}  (kiểu: {r['style']}, {r['supplier']})", f"Mục đích : {r['purpose']}",
                  f"Mong đợi : {r['expect']}", "Nội dung đúng:"]
        for name, qty, batch, days_left in r["lines"]:
            parts.append(f"    {name:<40} {qty:>4}   {batch:<7} {today + timedelta(days=days_left):%d/%m/%Y}")
        parts.append("")
    (out / "README_phieu_test.txt").write_text("\n".join(parts), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Tạo ảnh phiếu nhập để test chức năng quét OCR (không đụng DB).")
    ap.add_argument("--out", default="phieu_test", help="Thư mục xuất ảnh (mặc định ./phieu_test)")
    ap.add_argument("--font", help="Đường dẫn font .ttf có dấu tiếng Việt")
    ap.add_argument("--seed", type=int, default=1, help="Hạt giống ngẫu nhiên cho độ nghiêng/nhiễu")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    painter, rng, today = Painter(args.font), random.Random(args.seed), date.today()
    for spec in RECEIPTS:
        painter.render(spec, today, out / spec["file"], rng)
        print(f"  ✅ {spec['file']:<38} {spec['style']:<6} {len(spec['lines'])} dòng")
    write_readme(out, today)
    print(f"\nĐã tạo {len(RECEIPTS)} ảnh + README_phieu_test.txt trong: {out.resolve()}")


if __name__ == "__main__":
    main()
