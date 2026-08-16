"""Hậu xử lý dựa trên quy tắc, theo mục 6.4 đề cương:
- chuẩn hoá văn bản
- nhận dạng ngày tháng / mã lô bằng regex
- đối chiếu tên sản phẩm với danh mục đã biết bằng khoảng cách chỉnh sửa (fuzzy match)
"""
import re
from datetime import date, datetime
from typing import Optional

try:
    from rapidfuzz import fuzz, process
except ImportError:  # pragma: no cover
    fuzz = None
    process = None


DATE_PATTERNS = [
    r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})",   # dd/mm/yyyy, dd-mm-yyyy, dd.mm.yyyy
    r"(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})",   # yyyy-mm-dd
]

# Mã lô thường gặp trên phiếu VN: chữ+số, vd LOT2026A07, L-0719, B240719, L23A
BATCH_CODE_PATTERN = re.compile(r"\b([A-Za-z]{0,4}[-]?\d{1,8}[A-Za-z0-9]{0,4})\b")


def normalize_text(raw: str) -> str:
    """Chuẩn hoá khoảng trắng, loại ký tự lạ OCR hay đọc nhầm."""
    text = raw.strip()
    text = re.sub(r"\s+", " ", text)
    # OCR hay nhầm O<->0, l<->1 trong số lượng/mã lô — không sửa mù quáng ở tên sản phẩm,
    # chỉ áp dụng khi parse các trường số cụ thể (xem parse_batch_code, parse_quantity)
    return text


def parse_date(raw: str) -> Optional[date]:
    text = normalize_text(raw)
    for pattern in DATE_PATTERNS:
        m = re.search(pattern, text)
        if not m:
            continue
        groups = [int(g) for g in m.groups()]
        try:
            if pattern == DATE_PATTERNS[0]:
                d, mo, y = groups
            else:
                y, mo, d = groups
            return date(y, mo, d)
        except ValueError:
            continue
    return None


def parse_batch_code(raw: str) -> Optional[str]:
    text = normalize_text(raw)
    m = BATCH_CODE_PATTERN.search(text)
    return m.group(1) if m else None


def parse_quantity(raw: str) -> Optional[float]:
    text = normalize_text(raw).replace(",", ".")
    # sửa nhầm lẫn OCR phổ biến với số: O->0, o->0, l->1
    text = text.replace("O", "0").replace("o", "0").replace("l", "1")
    m = re.search(r"\d+(\.\d+)?", text)
    return float(m.group(0)) if m else None


def match_product_name(raw_name: str, known_products: list[str], threshold: float = 0.75):
    """So khớp gần đúng tên sản phẩm đọc từ OCR với danh mục đã biết.
    Trả về (tên_khớp_nhất, điểm_khớp 0-1) hoặc (None, 0.0) nếu không đủ ngưỡng
    hoặc rapidfuzz chưa được cài.
    """
    if not known_products or process is None:
        return None, 0.0
    best = process.extractOne(raw_name, known_products, scorer=fuzz.token_sort_ratio)
    if best is None:
        return None, 0.0
    name, score, _ = best
    score_normalized = score / 100.0
    if score_normalized < threshold:
        return None, score_normalized
    return name, score_normalized
