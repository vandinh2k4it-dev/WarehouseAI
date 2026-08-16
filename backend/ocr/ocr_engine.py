"""OCR engine cho Phiếu nhập hàng — mục 6.4 đề cương.

LỊCH SỬ ĐỔI HƯỚNG (quan trọng, nên ghi vào mục 6.1/13 báo cáo):
1. Bản đầu dùng PP-Structure để dò bảng có khung kẻ -> lỗi thư viện với
   lang="vi" (được ánh xạ nội bộ thành "latin", không được module layout
   hỗ trợ) + ảnh phiếu nhập hàng VN thực tế thường KHÔNG có khung kẻ ô,
   mà là dạng liệt kê tuần tự.
2. Bản 2 thử nhận diện dòng tiêu đề cột bằng cách so khớp chữ tiếng Việt
   ("tên sản phẩm", "số lượng"...) -> vẫn không ổn định vì OCR không chỉ
   sai DẤU mà đôi khi sai luôn CẢ KÝ TỰ (vd "lượng" bị đọc thành "lugng",
   chữ o thành g) — so khớp dù đã bỏ dấu hay dùng fuzzy-match vẫn có lúc
   trượt hoặc khớp nhầm vì nhiều cụm tiếng Việt có nét giống nhau.
3. Bản này (hiện tại): KHÔNG dựa vào việc đọc đúng tiêu đề cột tiếng Việt
   nữa. Thay vào đó, quét toàn bộ danh sách dòng OCR và tìm các nhóm 4
   dòng liên tiếp khớp ĐÚNG KHUÔN DẠNG dữ liệu của 1 sản phẩm:
       [tên sản phẩm] [số lượng: số thuần] [mã lô: chữ+số] [HSD: ngày/tháng/năm]
   Số, mã lô, ngày tháng gần như không có dấu tiếng Việt nên OCR đọc các
   trường này chính xác hơn nhiều so với tên sản phẩm -> dùng chúng làm
   "mỏ neo" đáng tin cậy để xác định ranh giới từng dòng hàng, thay vì
   phụ thuộc vào việc đọc đúng chữ có dấu.

Hạn chế đã biết: cách này giả định đúng thứ tự cột
[tên, số lượng, mã lô, HSD] và đúng 4 trường — nếu phiếu có thêm/bớt cột,
hoặc đổi thứ tự, cần điều chỉnh lại logic quét. Đây là điểm nên thử
nghiệm thêm trên nhiều mẫu phiếu thật (mục 9.2) trước khi coi là ổn định.

Cài đặt:
    pip install paddlepaddle paddleocr rapidfuzz
"""
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from ocr.postprocess import parse_date, parse_batch_code, parse_quantity, match_product_name

# --- Vá tương thích Pillow >=10.0 ---
# Image.ANTIALIAS bị XOÁ HẲN khỏi Pillow từ bản 10.0 (đổi tên thành
# Image.Resampling.LANCZOS), nhưng một số thư viện phụ thuộc của
# paddleocr/vietocr (vd 1 lớp resize ảnh nội bộ) vẫn gọi theo tên cũ ->
# AttributeError: module 'PIL.Image' has no attribute 'ANTIALIAS'.
# Đây là lỗi tương thích rất phổ biến trong hệ sinh thái thư viện OCR/CV,
# không phải lỗi logic code — vá ở đây (chạy 1 lần khi import module này,
# TRƯỚC khi paddleocr/vietocr được import) để không phải hạ cấp Pillow.
from PIL import Image as _PILImage
if not hasattr(_PILImage, "ANTIALIAS"):
    _PILImage.ANTIALIAS = _PILImage.Resampling.LANCZOS


def _strip_diacritics(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


_QUANTITY_RE = re.compile(r"\d+(\.\d+)?")
_DATE_RE = re.compile(r"^\s*(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{4}|\d{4}[/\-.]\d{1,2}[/\-.]\d{1,2})\s*$")
_BATCH_RE = re.compile(r"^[A-Za-z0-9]{2,12}$")
_BATCH_TRAILING_NOISE = "]})>.,:;'\""  # ký tự nhiễu OCR hay thêm nhầm ở cuối mã lô (vd J đọc thành ])

FOOTER_MARKERS = ["ghi chu", "nguoi giao", "nguoi nhan", "ky ten", "xac nhan"]


def _looks_like_quantity(text: str) -> bool:
    """Dòng gần như CHỈ chứa 1 con số — đặc trưng của cột số lượng.
    Sửa trước các lỗi OCR số phổ biến: O/o -> 0."""
    cleaned = text.strip().replace(",", ".").replace("O", "0").replace("o", "0")
    return bool(re.fullmatch(r"\d+(\.\d+)?", cleaned))


def _looks_like_date(text: str) -> bool:
    return bool(_DATE_RE.match(text.strip()))


def _looks_like_batch(text: str) -> bool:
    """Mã lô: chuỗi chữ+số liền nhau, không khoảng trắng, có ít nhất 1 chữ số
    (để không nhầm với 1 từ tiếng Anh ngẫu nhiên). Bỏ qua ký tự nhiễu OCR ở
    cuối chuỗi (vd 'L639]' — VietOCR đọc nhầm J thành ] — vẫn nhận là mã lô
    hợp lệ 'L639', khớp với cách postprocess.parse_batch_code() đã xử lý)."""
    t = text.strip().rstrip(_BATCH_TRAILING_NOISE)
    return bool(_BATCH_RE.match(t)) and any(ch.isdigit() for ch in t)


def _looks_like_footer(text: str) -> bool:
    norm = _strip_diacritics(text)
    return any(marker in norm for marker in FOOTER_MARKERS)


@dataclass
class ReceiptLineResult:
    product_name_raw: str
    quantity: Optional[float]
    batch_code: Optional[str]
    expiry_date: Optional[date]
    match_score: Optional[float] = None
    field_confidence: dict = field(default_factory=dict)


@dataclass
class ReceiptOCRResult:
    raw_text: str
    avg_confidence: float
    lines: list[ReceiptLineResult]


class ReceiptOCREngine:
    def __init__(
        self,
        lang: str = "vi",
        known_products: Optional[list[str]] = None,
        use_vietocr: bool = True,
    ):
        """PaddleOCR lang='vi' KHÔNG có model tiếng Việt riêng — nó ánh xạ nội
        bộ sang bộ ký tự dùng chung 'latin' (Pháp/Đức/Việt...), thiếu nhiều tổ
        hợp dấu tiếng Việt (ẹ, ặ, ê, ơ, ư...) -> tên sản phẩm hay bị sai dấu,
        trong khi số/ngày/mã lô (không dấu) vẫn đọc đúng bình thường.

        use_vietocr=True (mặc định): dùng kiến trúc lai — PaddleOCR chỉ lo
        DÒ VỊ TRÍ dòng chữ (detection, không phụ thuộc ngôn ngữ), còn ĐỌC CHỮ
        (recognition) chuyển sang VietOCR — model huấn luyện riêng cho tiếng
        Việt, đọc dấu chính xác hơn hẳn. Toàn bộ logic quét theo khuôn dạng ở
        _scan_product_groups giữ nguyên, không phụ thuộc việc text đến từ
        engine nào.

        use_vietocr=False: dùng lại PaddleOCR thuần (đọc cả detect+recognize),
        nhanh hơn / nhẹ hơn nhưng tên sản phẩm có dấu sẽ kém chính xác — chỉ
        nên dùng khi test nhanh hoặc máy yếu không cài được thêm VietOCR.

        known_products: danh mục tên sản phẩm chuẩn để fuzzy-match (mục 6.4);
        truyền vào từ DB (bảng products) khi tích hợp thật.
        """
        # Thứ tự import ở đây QUAN TRỌNG trên Windows: paddlepaddle và torch
        # đều mang theo DLL runtime riêng (MKL/OpenMP). Nếu paddlepaddle nạp
        # trước, nó có thể che mất DLL torch cần (gây lỗi kiểu
        # "WinError 127 ... torch\lib\shm.dll") khi torch nạp sau. Nên LUÔN
        # import torch (qua vietocr) trước khi khởi tạo PaddleOCR.
        self.use_vietocr = use_vietocr
        self.known_products = known_products or []

        if use_vietocr:
            self._init_vietocr()  # import torch trước

        from paddleocr import PaddleOCR  # import trễ, sau torch — xem lý do ở trên

        if use_vietocr:
            # det=True, rec=False -> PaddleOCR chỉ trả toạ độ box, không đọc chữ
            self.det_engine = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)
        else:
            self.text_ocr = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)

    def _init_vietocr(self):
        try:
            from vietocr.tool.predictor import Predictor
            from vietocr.tool.config import Cfg
        except ImportError as e:  # pragma: no cover
            raise ImportError(
                f"Import vietocr thất bại — LÝ DO THẬT: {e!r}\n"
                "Nếu lý do trên là 'No module named vietocr' -> pip install vietocr.\n"
                "Nếu là lỗi khác (thiếu package con, xung đột bản, ANTIALIAS, "
                "pkg_resources...) -> sửa đúng theo lý do thật ở trên, KHÔNG chỉ cài "
                "lại vietocr suông sẽ không hết.\n"
                "Dự phòng tạm: ReceiptOCREngine(use_vietocr=False) dùng PaddleOCR thuần."
            ) from e

        cfg = Cfg.load_config_from_name("vgg_transformer")
        cfg["device"] = "cpu"  # đổi 'cuda:0' nếu máy có GPU rảnh lúc chạy OCR
        cfg["predictor"]["beamsearch"] = False  # tắt beamsearch cho nhanh, bật lại nếu cần độ chính xác cao hơn
        self.rec_engine = Predictor(cfg)

    # ------------------------------------------------------------------
    def process_receipt(self, image_path: str) -> ReceiptOCRResult:
        raw_lines = self._run_ocr(image_path)  # list[(text, conf)], theo thứ tự đọc trên->dưới
        raw_text = "\n".join(t for t, _ in raw_lines)
        avg_conf = sum(c for _, c in raw_lines) / len(raw_lines) if raw_lines else 0.0

        lines = self._scan_product_groups(raw_lines)
        return ReceiptOCRResult(raw_text=raw_text, avg_confidence=avg_conf, lines=lines)

    # ------------------------------------------------------------------
    def _run_ocr(self, image_path: str) -> list[tuple[str, float]]:
        if self.use_vietocr:
            return self._run_ocr_hybrid(image_path)
        result = self.text_ocr.ocr(image_path, cls=True)
        out = []
        for block in result or []:
            for _, (text, conf) in block:
                text = text.strip()
                if text:
                    out.append((text, conf))
        return out

    def _run_ocr_hybrid(self, image_path: str) -> list[tuple[str, float]]:
        """PaddleOCR dò box (det) -> cắt từng dòng -> VietOCR đọc chữ (rec).
        Sắp xếp lại theo thứ tự trên->dưới, trái->phải để không phá vỡ giả
        định thứ tự dòng trong _scan_product_groups."""
        import cv2
        from PIL import Image

        det_result = self.det_engine.ocr(image_path, cls=True, rec=False)
        boxes = det_result[0] if det_result else []
        if not boxes:
            return []

        boxes = self._sort_boxes_into_rows(boxes)

        img = cv2.imread(image_path)
        out = []
        for box in boxes:
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            x1, y1, x2, y2 = int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))
            crop = img[max(0, y1):y2, max(0, x1):x2]
            if crop.size == 0:
                continue
            pil_crop = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
            text = self.rec_engine.predict(pil_crop).strip()
            if text:
                out.append((text, 1.0))  # VietOCR bản base không trả confidence per-char; coi như 1.0
        return out

    @staticmethod
    def _sort_boxes_into_rows(boxes: list) -> list:
        """Gộp các box về cùng 'hàng' bảng rồi sắp trái->phải trong hàng.

        Bản trước dùng ngưỡng cố định round(y/10)*10 -> khi 2 ô cùng hàng
        lệch y hơi quá 10px (rất hay gặp vì bảng thật không thẳng tuyệt đối)
        thì bị tính nhầm thành 2 hàng khác nhau, xáo trộn thứ tự đọc và phá
        vỡ khuôn dạng [tên, SL, mã lô, HSD] mà _scan_product_groups cần.

        Cách mới: ngưỡng gộp hàng tính theo chiều cao chữ THỰC TẾ của ảnh
        (trung vị chiều cao box) thay vì số cố định -> tự thích ứng với
        ảnh chụp to/nhỏ, font to/nhỏ khác nhau.
        """
        if not boxes:
            return []

        def y_center(box):
            ys = [p[1] for p in box]
            return (min(ys) + max(ys)) / 2

        def box_height(box):
            ys = [p[1] for p in box]
            return max(ys) - min(ys)

        heights = sorted(box_height(b) for b in boxes)
        median_h = heights[len(heights) // 2] or 20
        row_threshold = median_h * 0.6  # 2 box cách nhau dưới ngưỡng này -> coi là cùng hàng

        boxes_sorted_by_y = sorted(boxes, key=y_center)

        rows: list[list] = []
        for box in boxes_sorted_by_y:
            yc = y_center(box)
            if rows and abs(yc - rows[-1]["y"]) <= row_threshold:
                rows[-1]["boxes"].append(box)
                # cập nhật y đại diện của hàng = trung bình các box đã gộp
                rows[-1]["y"] = sum(y_center(b) for b in rows[-1]["boxes"]) / len(rows[-1]["boxes"])
            else:
                rows.append({"y": yc, "boxes": [box]})

        ordered: list = []
        for row in rows:
            row_boxes = sorted(row["boxes"], key=lambda b: min(p[0] for p in b))  # trái -> phải
            ordered.extend(row_boxes)
        return ordered

    def _scan_product_groups(self, raw_lines: list[tuple[str, float]]) -> list[ReceiptLineResult]:
        """Quét toàn bộ danh sách dòng, tìm các nhóm 4 dòng liên tiếp khớp khuôn
        dạng [tên] [số lượng] [mã lô] [HSD]. Xem docstring đầu file để biết vì
        sao chọn cách này thay vì đọc tiêu đề cột."""
        n = len(raw_lines)
        results: list[ReceiptLineResult] = []
        i = 0
        while i <= n - 4:
            name_txt, _ = raw_lines[i]

            if _looks_like_footer(name_txt):
                break  # đã sang phần chân trang -> dừng quét hẳn

            qty_txt, qty_conf = raw_lines[i + 1]
            batch_txt, batch_conf = raw_lines[i + 2]
            exp_txt, exp_conf = raw_lines[i + 3]

            name_is_data_field = (
                _looks_like_quantity(name_txt) or _looks_like_date(name_txt) or _looks_like_batch(name_txt)
            )
            valid_group = (
                not name_is_data_field
                and len(name_txt.strip()) >= 3  # tên sản phẩm quá ngắn -> khả năng cao là dòng rác
                and _looks_like_quantity(qty_txt)
                and _looks_like_batch(batch_txt)
                and _looks_like_date(exp_txt)
            )

            if valid_group:
                matched_name, score = match_product_name(name_txt.strip(), self.known_products)
                results.append(
                    ReceiptLineResult(
                        product_name_raw=name_txt.strip(),
                        quantity=parse_quantity(qty_txt),
                        batch_code=parse_batch_code(batch_txt),
                        expiry_date=parse_date(exp_txt),
                        match_score=score,
                        field_confidence={
                            "quantity": round(qty_conf, 4),
                            "batch": round(batch_conf, 4),
                            "expiry": round(exp_conf, 4),
                        },
                    )
                )
                i += 4  # nhảy qua hết nhóm vừa nhận diện được
            else:
                i += 1  # trượt 1 dòng, thử lại vị trí kế tiếp

        return results
