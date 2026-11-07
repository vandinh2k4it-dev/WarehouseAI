"""Chuyển phiếu nhập dạng PDF thành ảnh để chạy qua đúng pipeline OCR ảnh.

Render mọi PDF thành ảnh (kể cả PDF có sẵn lớp chữ) thay vì trích text: logic
quét ở ocr_engine dựa vào thứ tự dòng từ OCR, còn thứ tự text trong PDF tuỳ
phần mềm xuất file nên không đáng tin.
"""
import pypdfium2 as pdfium
from PIL import Image

MAX_PDF_PAGES = 10
RENDER_DPI = 200
MAX_PAGE_SIDE_PX = 4000  # chặn trang khổ lớn (A0, bản vẽ...) ngốn hết RAM


def render_pdf_pages(pdf_bytes: bytes) -> list[Image.Image]:
    """Trả về ảnh RGB của từng trang. Raise ValueError (kèm lý do hiện được lên
    UI) nếu file hỏng, có mật khẩu, không có trang nào hoặc quá nhiều trang."""
    try:
        doc = pdfium.PdfDocument(pdf_bytes)
    except pdfium.PdfiumError as exc:
        raise ValueError("Không đọc được file PDF — file bị hỏng hoặc có mật khẩu.") from exc

    try:
        page_count = len(doc)
        if page_count == 0:
            raise ValueError("File PDF không có trang nào.")
        if page_count > MAX_PDF_PAGES:
            raise ValueError(f"File PDF có {page_count} trang, tối đa {MAX_PDF_PAGES} trang cho 1 phiếu.")

        images = []
        for i in range(page_count):
            page = doc[i]
            try:
                width, height = page.get_size()
                scale = min(RENDER_DPI / 72, MAX_PAGE_SIDE_PX / max(width, height))
                images.append(page.render(scale=scale).to_pil().convert("RGB"))
            finally:
                page.close()
        return images
    finally:
        doc.close()


def stack_pages(pages: list[Image.Image]) -> Image.Image:
    """Ghép các trang thành 1 ảnh dọc — chỉ để lưu làm ảnh phiếu hiển thị trên UI.
    OCR vẫn chạy TỪNG TRANG riêng: PaddleOCR thu nhỏ ảnh theo cạnh dài nên chạy
    trên ảnh ghép rất dài sẽ làm chữ quá nhỏ, khó dò."""
    if len(pages) == 1:
        return pages[0]
    stacked = Image.new("RGB", (max(p.width for p in pages), sum(p.height for p in pages)), "white")
    y = 0
    for page in pages:
        stacked.paste(page, (0, y))
        y += page.height
    return stacked
