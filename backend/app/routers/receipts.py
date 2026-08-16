import os
import shutil
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
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
