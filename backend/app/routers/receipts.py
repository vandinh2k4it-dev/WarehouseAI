import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.code_generator import generate_next_code, is_auto_code, renumber_codes
from ocr.ocr_engine import ReceiptOCREngine
from ocr.pdf_utils import render_pdf_pages, stack_pages
from ocr.postprocess import match_product_name

router = APIRouter(prefix="/receipts", tags=["receipts"])

UPLOAD_DIR = os.getenv("RECEIPT_UPLOAD_DIR", "./uploads/receipts")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Chỉ nhận ảnh: kiểm tra đuôi file + loại nội dung khai báo + giới hạn dung lượng,
# rồi mở thử bằng Pillow — chặn file rác/độc hại (vd .exe đổi tên) TRƯỚC khi lưu
# vào uploads/ và trước khi tạo phiếu (không tốn mã PN, không để lại phiếu rác).
ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
MAX_RECEIPT_IMAGE_MB = float(os.getenv("MAX_RECEIPT_IMAGE_MB", "15"))


def _save_validated_image(file: UploadFile) -> str:
    """Lưu ảnh phiếu lên đĩa nếu hợp lệ, trả về đường dẫn; sai thì xoá file và raise 400/413."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_IMAGE_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"Chỉ nhận file ảnh ({', '.join(sorted(ALLOWED_IMAGE_EXT))}); file gửi lên có đuôi '{ext or 'không có'}'.",
        )
    ctype = (file.content_type or "").lower()
    if ctype and not ctype.startswith("image/") and ctype != "application/octet-stream":
        raise HTTPException(status_code=400, detail=f"Loại nội dung '{ctype}' không phải ảnh.")

    saved_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}{ext}")
    max_bytes = int(MAX_RECEIPT_IMAGE_MB * 1024 * 1024)
    size = 0
    try:
        with open(saved_path, "wb") as out:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(status_code=413, detail=f"Ảnh quá lớn (tối đa {MAX_RECEIPT_IMAGE_MB:g} MB).")
                out.write(chunk)
        if size == 0:
            raise HTTPException(status_code=400, detail="File ảnh rỗng.")
        try:
            from PIL import Image
            with Image.open(saved_path) as img:
                img.verify()
        except Exception:
            raise HTTPException(status_code=400, detail="File không phải ảnh hợp lệ (không đọc được nội dung).")
    except HTTPException:
        if os.path.exists(saved_path):
            os.remove(saved_path)
        raise
    return saved_path

# Khởi tạo 1 lần — PaddleOCR load model khá lâu (vài giây), không nên khởi tạo lại mỗi request
_ocr_engine: Optional[ReceiptOCREngine] = None


def get_ocr_engine() -> ReceiptOCREngine:
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = ReceiptOCREngine()
    return _ocr_engine


@router.post("/upload", response_model=schemas.ReceiptOut)
def upload_receipt(
    file: UploadFile = File(...),
    store_location: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Nhận ảnh hoặc PDF Phiếu nhập hàng, chạy OCR ngay, lưu kết quả từng dòng hàng.
    PDF nhiều trang được tính là 1 phiếu; chỉ lưu ảnh ghép các trang, không lưu file PDF gốc.
    Test nhanh bằng: curl -F "file=@sample_receipt.jpg" http://localhost:8000/receipts/upload
    """
    fname = file.filename or ""
    is_pdf = os.path.splitext(fname)[1].lower() == ".pdf" or file.file.read(5) == b"%PDF-"
    file.file.seek(0)

    if is_pdf:
        # Kiểm tra PDF TRƯỚC khi tạo phiếu — file hỏng thì báo lỗi luôn, không để lại phiếu rác.
        data = file.file.read(int(MAX_RECEIPT_IMAGE_MB * 1024 * 1024) + 1)
        if len(data) > MAX_RECEIPT_IMAGE_MB * 1024 * 1024:
            raise HTTPException(status_code=413, detail=f"File quá lớn (tối đa {MAX_RECEIPT_IMAGE_MB:g} MB).")
        try:
            pdf_pages = render_pdf_pages(data)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        saved_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}.png")
        stack_pages(pdf_pages).save(saved_path)
    else:
        saved_path = _save_validated_image(file)

    receipt = models.ImportReceipt(
        receipt_code=generate_next_code(db, models.ImportReceipt, "receipt_code", "PN"),
        store_location=store_location,
        image_path=saved_path,
        status="pending_ocr",
        received_at=datetime.now(timezone.utc),
    )
    db.add(receipt)
    db.commit()
    db.refresh(receipt)

    # Chạy OCR ngay (đồng bộ để test nhanh trong tuần này;
    # khi tích hợp thật nên chuyển sang background task / queue để không block request)
    page_dir = None
    try:
        engine = get_ocr_engine()
        ocr_input = saved_path
        if pdf_pages:
            page_dir = tempfile.mkdtemp()
            ocr_input = []
            for i, page in enumerate(pdf_pages):
                page_path = os.path.join(page_dir, f"page_{i}.png")
                page.save(page_path)
                ocr_input.append(page_path)
        ocr_result = engine.process_receipt(ocr_input)
    except Exception as exc:
        receipt.status = "flagged"
        db.commit()
        # In toàn bộ chuỗi lỗi (kể cả lỗi gốc bị "chain" qua `raise ... from e`)
        # để hiện thẳng lên UI — tránh phải mở terminal chụp traceback mỗi lần.
        chain = []
        cur = exc
        seen = set()
        while cur is not None and id(cur) not in seen:
            seen.add(id(cur))
            chain.append(f"{type(cur).__name__}: {cur}")
            cur = cur.__cause__ or cur.__context__
        detail = "OCR thất bại:\n" + "\n  -> gây ra bởi: ".join(chain)
        raise HTTPException(status_code=500, detail=detail)
    finally:
        if page_dir:
            shutil.rmtree(page_dir, ignore_errors=True)

    receipt.ocr_raw_text = ocr_result.raw_text
    receipt.ocr_confidence = ocr_result.avg_confidence
    receipt.receipt_date = ocr_result.receipt_date
    receipt.status = "ocr_done"

    # Tự động so khớp từng dòng OCR với danh mục sản phẩm ĐÃ CÓ SẴN trong DB
    # (không tự tạo sản phẩm mới ở đây — tránh tạo trùng/rác nếu OCR đọc sai
    # tên; sản phẩm hoàn toàn mới vẫn cần duyệt tay 1 lần qua
    # /products/unmapped-lines, các lần nhập sau của đúng sản phẩm đó sẽ tự
    # động map nhờ có tên trong danh mục rồi).
    existing_products = db.query(models.Product).all()
    product_lookup = {p.name: p.id for p in existing_products}
    known_names = list(product_lookup.keys())

    auto_mapped = 0
    for i, line in enumerate(ocr_result.lines, start=1):
        matched_name, score = match_product_name(line.product_name_raw, known_names)
        product_id = product_lookup.get(matched_name) if matched_name else None
        if product_id is not None:
            auto_mapped += 1

        db.add(
            models.ReceiptLineItem(
                receipt_id=receipt.id,
                line_no=i,
                product_name_raw=line.product_name_raw,
                product_id=product_id,
                quantity=line.quantity,
                batch_code=line.batch_code,
                expiry_date=line.expiry_date,
                match_score=score,
                field_confidence=line.field_confidence,
            )
        )
    db.commit()
    db.refresh(receipt)
    return receipt


@router.post("/manual", response_model=schemas.ReceiptOut)
def create_receipt_manual(payload: schemas.ReceiptManualCreate, db: Session = Depends(get_db)):
    """Tạo phiếu nhập BẰNG TAY — dùng khi không có ảnh phiếu giấy để quét
    (vd nhân viên tự gõ lại theo phiếu giấy, hoặc nhập bổ sung/điều chỉnh).
    KHÔNG qua OCR, không tự động so khớp sản phẩm bằng tên gần đúng (khác
    /upload) — người dùng tự chọn đúng product_id ngay lúc nhập nếu sản
    phẩm đã có trong danh mục, để trống nếu chưa có (xử lý sau ở
    /products/unmapped-lines, giống hệt luồng OCR khi không khớp được)."""
    if not payload.line_items:
        raise HTTPException(status_code=400, detail="Phiếu phải có ít nhất 1 dòng hàng")

    receipt = models.ImportReceipt(
        receipt_code=payload.receipt_code or generate_next_code(db, models.ImportReceipt, "receipt_code", "PN"),
        store_location=payload.store_location,
        image_path=None,
        status="ocr_done",  # bỏ qua bước "pending_ocr" vì không có OCR nào để chạy
        source_type="manual",
        received_at=payload.received_at or datetime.now(timezone.utc),
        receipt_date=payload.receipt_date,
    )
    db.add(receipt)
    db.flush()

    for i, line in enumerate(payload.line_items, start=1):
        db.add(models.ReceiptLineItem(
            receipt_id=receipt.id,
            line_no=i,
            product_name_raw=line.product_name_raw,
            product_id=line.product_id,
            quantity=line.quantity,
            batch_code=line.batch_code,
            expiry_date=line.expiry_date,
            match_score=1.0 if line.product_id else None,  # đã tự chọn đúng sản phẩm -> coi như khớp tuyệt đối
        ))

    db.commit()
    db.refresh(receipt)
    return receipt


@router.put("/{receipt_id}", response_model=schemas.ReceiptOut)
def update_receipt(receipt_id: int, payload: schemas.ReceiptUpdateRequest, db: Session = Depends(get_db)):
    """Sửa thông tin chung của phiếu (mã phiếu, nhà cung cấp, ngày nhận) —
    KHÔNG sửa dòng hàng ở đây, xem riêng /receipts/{id}/lines (POST) và
    /receipts/{id}/lines/{line_id} (PUT/DELETE)."""
    receipt = db.get(models.ImportReceipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiếu nhập")

    if payload.receipt_code is not None:
        receipt.receipt_code = payload.receipt_code
    if payload.store_location is not None:
        receipt.store_location = payload.store_location
    if payload.received_at is not None:
        receipt.received_at = payload.received_at
    if payload.receipt_date is not None:
        receipt.receipt_date = payload.receipt_date

    db.commit()
    db.refresh(receipt)
    return receipt


@router.delete("/{receipt_id}")
def delete_receipt(receipt_id: int, db: Session = Depends(get_db)):
    """Xoá hẳn 1 phiếu nhập — CHỈ CHO PHÉP nếu KHÔNG có dòng hàng nào đã bắt
    đầu đếm (chưa có CameraCountSession nào gắn với bất kỳ dòng nào của
    phiếu này). Chặn xoá nếu đã có đếm, dù mới đếm 1 dòng — vì việc đếm đã
    có thể làm thay đổi tồn kho thật (dòng đã khớp), xoá phiếu lúc này sẽ
    làm "mồ côi" dữ liệu tồn kho/giao dịch đã phát sinh, không phản ánh
    đúng lịch sử thật nữa."""
    receipt = db.get(models.ImportReceipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiếu nhập")

    line_ids = [li.id for li in receipt.line_items]
    if line_ids:
        has_sessions = (
            db.query(models.CameraCountSession)
            .filter(models.CameraCountSession.receipt_line_item_id.in_(line_ids))
            .first()
        )
        if has_sessions:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Không thể xoá — phiếu này đã có ít nhất 1 dòng hàng được đếm rồi "
                    "(có thể đã cập nhật tồn kho thật). Xoá lúc này sẽ làm mất dấu vết "
                    "giao dịch đã xảy ra. Nếu thực sự cần xoá, hãy liên hệ người quản trị "
                    "để xử lý thủ công trực tiếp trên cơ sở dữ liệu."
                ),
            )

    deleted_code = receipt.receipt_code
    db.delete(receipt)  # cascade="all, delete-orphan" trên line_items tự xoá kèm theo
    db.flush()  # giải phóng mã của phiếu vừa xoá TRƯỚC khi dồn mã các phiếu còn lại

    # Mã phiếu tự sinh (PN0001, PN0002...) luôn là dãy LIÊN TỤC: xoá 1 phiếu thì các phiếu
    # phía sau tự dồn lên lấp chỗ trống (vd xoá PN0003 -> PN0004 thành PN0003...), và phiếu
    # mới luôn nối tiếp ngay sau số cuối. Làm chung 1 giao dịch với việc xoá: lỗi thì hoàn tác
    # cả hai. Chỉ đổi MÃ HIỂN THỊ, khoá chính id (và mọi liên kết tới phiếu) giữ nguyên.
    renumbered = 0
    if is_auto_code(deleted_code, "PN"):
        renumbered = renumber_codes(db, models.ImportReceipt, "receipt_code", "PN")
    db.commit()
    return {"deleted": True, "receipt_id": receipt_id, "deleted_code": deleted_code, "renumbered": renumbered}


@router.post("/{receipt_id}/lines", response_model=schemas.LineItemOut)
def add_receipt_line(receipt_id: int, payload: schemas.ReceiptLineItemCreateRequest, db: Session = Depends(get_db)):
    """Thêm 1 dòng hàng MỚI vào phiếu đã có — luôn an toàn (dòng hoàn toàn
    mới, không đụng dữ liệu đã có), dùng khi phát hiện thiếu dòng lúc nhập
    tay hoặc bổ sung sau khi quét OCR bị sót dòng."""
    receipt = db.get(models.ImportReceipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiếu nhập")

    max_line_no = max([li.line_no for li in receipt.line_items], default=0)
    line = models.ReceiptLineItem(
        receipt_id=receipt_id,
        line_no=max_line_no + 1,
        product_name_raw=payload.product_name_raw,
        product_id=payload.product_id,
        quantity=payload.quantity,
        batch_code=payload.batch_code,
        expiry_date=payload.expiry_date,
        match_score=1.0 if payload.product_id else None,
    )
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


def _get_line_counting_status(db: Session, line_id: int) -> str | None:
    """Trả về status của phiên đếm MỚI NHẤT gắn với dòng này, hoặc None nếu
    dòng chưa từng được đếm lần nào — dùng chung cho cả sửa lẫn xoá dòng để
    quyết định có an toàn để sửa/xoá không."""
    latest = (
        db.query(models.CameraCountSession)
        .filter(models.CameraCountSession.receipt_line_item_id == line_id)
        .order_by(models.CameraCountSession.id.desc())
        .first()
    )
    return latest.status if latest else None


@router.put("/{receipt_id}/lines/{line_id}", response_model=schemas.LineItemOut)
def update_receipt_line(
    receipt_id: int, line_id: int, payload: schemas.ReceiptLineItemUpdateRequest, db: Session = Depends(get_db),
):
    """Sửa 1 dòng hàng — CHỈ cho phép nếu dòng CHƯA từng được đếm (không có
    CameraCountSession nào, kể cả đã 'completed' hay đang 'counting') —
    tránh sửa số lượng SAU KHI tồn kho đã được cộng dựa trên số cũ, gây sai
    lệch âm thầm giữa "số ghi trên phiếu" và "số thực đã cộng vào kho"."""
    line = db.get(models.ReceiptLineItem, line_id)
    if not line or line.receipt_id != receipt_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy dòng hàng này trong phiếu")

    existing_status = _get_line_counting_status(db, line_id)
    if existing_status is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Không thể sửa — dòng hàng này đã có phiên đếm (trạng thái '{existing_status}'). "
                "Sửa lúc này có thể làm sai lệch tồn kho đã cập nhật. Nếu đếm bị sai, dùng chức năng "
                "'Đếm lại' thay vì sửa trực tiếp dòng hàng."
            ),
        )

    if payload.product_name_raw is not None:
        line.product_name_raw = payload.product_name_raw
    if payload.product_id is not None:
        line.product_id = payload.product_id
        line.match_score = 1.0
    if payload.quantity is not None:
        line.quantity = payload.quantity
    if payload.batch_code is not None:
        line.batch_code = payload.batch_code
    if payload.expiry_date is not None:
        line.expiry_date = payload.expiry_date

    db.commit()
    db.refresh(line)
    return line


@router.delete("/{receipt_id}/lines/{line_id}")
def delete_receipt_line(receipt_id: int, line_id: int, db: Session = Depends(get_db)):
    """Xoá 1 dòng hàng — CHỈ cho phép nếu dòng CHƯA từng được đếm, cùng lý
    do an toàn như update_receipt_line ở trên."""
    line = db.get(models.ReceiptLineItem, line_id)
    if not line or line.receipt_id != receipt_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy dòng hàng này trong phiếu")

    existing_status = _get_line_counting_status(db, line_id)
    if existing_status is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Không thể xoá — dòng hàng này đã có phiên đếm (trạng thái '{existing_status}'). "
                "Xoá lúc này sẽ làm mất dấu vết giao dịch đã xảy ra."
            ),
        )

    db.delete(line)
    db.commit()
    return {"deleted": True, "line_id": line_id}


@router.get("/{receipt_id}", response_model=schemas.ReceiptOut)
def get_receipt(receipt_id: int, db: Session = Depends(get_db)):
    receipt = db.get(models.ImportReceipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiếu nhập")
    return receipt


@router.get("", response_model=list[schemas.ReceiptOut])
def list_receipts(
    status: Optional[str] = None,
    limit: int = Query(1000, ge=1, le=5000),  # trước đây cứng 100 -> phiếu cũ hơn biến mất khỏi giao diện
    db: Session = Depends(get_db),
):
    query = db.query(models.ImportReceipt)
    if status:
        query = query.filter(models.ImportReceipt.status == status)
    return query.order_by(models.ImportReceipt.created_at.desc(), models.ImportReceipt.id.desc()).limit(limit).all()


@router.get("/{receipt_id}/lines-progress", response_model=list[schemas.ReceiptLineProgressOut])
def get_lines_progress(receipt_id: int, db: Session = Depends(get_db)):
    """Tiến độ đếm camera của TỪNG DÒNG hàng trên phiếu — dùng cho UI hiển thị
    checklist 'loại nào đã xong / đang đếm / bị chặn / chưa bắt đầu', đúng quy
    trình: nhân viên chọn từng loại hàng lần lượt khi hàng đi qua băng chuyền."""
    receipt = db.get(models.ImportReceipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiếu nhập")

    result = []
    for line in receipt.line_items:
        sessions = (
            db.query(models.CameraCountSession)
            .filter(models.CameraCountSession.receipt_line_item_id == line.id)
            .order_by(models.CameraCountSession.id.desc())
            .all()
        )
        latest = sessions[0] if sessions else None

        if latest is None:
            counting_status = "not_started"
        elif latest.status == "counting":
            counting_status = "counting"
        elif latest.status == "needs_review":
            counting_status = "needs_review"
        elif latest.status == "resolved_override":
            counting_status = "resolved_override"
        elif latest.status == "completed":
            counting_status = "matched"
        else:  # superseded -> nhìn lại phiên trước đó (đang đếm lại)
            counting_status = "counting"

        result.append(schemas.ReceiptLineProgressOut(
            line_id=line.id,
            product_name_raw=line.product_name_raw,
            product_id=line.product_id,
            declared_quantity=float(line.quantity),
            batch_code=line.batch_code,
            expiry_date=line.expiry_date,
            counting_status=counting_status,
            latest_session_id=latest.id if latest else None,
            counted_quantity=latest.counted_quantity if latest else None,
        ))
    return result
