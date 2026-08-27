import os
import shutil
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.code_generator import generate_next_code
from ocr.ocr_engine import ReceiptOCREngine
from ocr.postprocess import match_product_name

router = APIRouter(prefix="/receipts", tags=["receipts"])

UPLOAD_DIR = os.getenv("RECEIPT_UPLOAD_DIR", "./uploads/receipts")
os.makedirs(UPLOAD_DIR, exist_ok=True)

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
    """Nhận ảnh Phiếu nhập hàng, chạy OCR ngay, lưu kết quả từng dòng hàng.
    Test nhanh bằng: curl -F "file=@sample_receipt.jpg" http://localhost:8000/receipts/upload
    """
    ext = os.path.splitext(file.filename)[1] or ".jpg"
    saved_name = f"{uuid.uuid4().hex}{ext}"
    saved_path = os.path.join(UPLOAD_DIR, saved_name)
    with open(saved_path, "wb") as out:
        shutil.copyfileobj(file.file, out)

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
    try:
        engine = get_ocr_engine()
        ocr_result = engine.process_receipt(saved_path)
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

    receipt.ocr_raw_text = ocr_result.raw_text
    receipt.ocr_confidence = ocr_result.avg_confidence
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

    db.delete(receipt)  # cascade="all, delete-orphan" trên line_items tự xoá kèm theo
    db.commit()
    return {"deleted": True, "receipt_id": receipt_id}


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
def list_receipts(status: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.ImportReceipt)
    if status:
        query = query.filter(models.ImportReceipt.status == status)
    return query.order_by(models.ImportReceipt.created_at.desc()).limit(100).all()


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
            counting_status=counting_status,
            latest_session_id=latest.id if latest else None,
            counted_quantity=latest.counted_quantity if latest else None,
        ))
    return result
