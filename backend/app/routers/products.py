from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/products", tags=["products"])


class ProductCreate(BaseModel):
    name: str
    sku: Optional[str] = None
    category: Optional[str] = None
    unit: str = "thùng"
    low_stock_threshold: float = 10


@router.post("", response_model=schemas.ProductOut)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    product = models.Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("", response_model=list[schemas.ProductOut])
def list_products(db: Session = Depends(get_db)):
    return db.query(models.Product).order_by(models.Product.name).all()


@router.get("/unmapped-lines")
def list_unmapped_lines(db: Session = Depends(get_db)):
    """Các dòng hàng OCR đọc được nhưng CHƯA khớp được với sản phẩm nào trong
    danh mục — cần xử lý thủ công (tạo sản phẩm mới, hoặc map tay vào sản
    phẩm có sẵn) trước khi đối chiếu có thể cập nhật đúng tồn kho."""
    lines = (
        db.query(models.ReceiptLineItem)
        .filter(models.ReceiptLineItem.product_id.is_(None))
        .order_by(models.ReceiptLineItem.id.desc())
        .limit(200)
        .all()
    )
    return [
        {
            "line_id": l.id,
            "receipt_id": l.receipt_id,
            "product_name_raw": l.product_name_raw,
            "quantity": float(l.quantity),
            "batch_code": l.batch_code,
            "expiry_date": l.expiry_date,
        }
        for l in lines
    ]


class MapLineRequest(BaseModel):
    product_id: int


@router.post("/lines/{line_id}/map")
def map_line_to_product(line_id: int, payload: MapLineRequest, db: Session = Depends(get_db)):
    """Gán 1 dòng hàng OCR vào đúng sản phẩm trong danh mục. Sau khi map,
    nếu phiếu chứa dòng này đã đối chiếu 'matched' rồi, cần chạy lại đối
    chiếu (hoặc resolve thủ công) để tồn kho được cộng đúng."""
    line = db.get(models.ReceiptLineItem, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Không tìm thấy dòng hàng")
    product = db.get(models.Product, payload.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")
    line.product_id = product.id
    db.commit()
    return {"line_id": line.id, "product_id": product.id, "message": "Đã gán sản phẩm cho dòng hàng"}


@router.post("/lines/{line_id}/create-and-map", response_model=schemas.ProductOut)
def create_product_and_map(line_id: int, db: Session = Depends(get_db)):
    """Tiện ích nhanh: tạo 1 sản phẩm mới lấy đúng tên OCR đọc được cho dòng
    hàng này, rồi gán luôn — dùng khi tên sản phẩm OCR đọc ra chưa từng có
    trong danh mục và bạn muốn thêm mới ngay thay vì gõ tay riêng."""
    line = db.get(models.ReceiptLineItem, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Không tìm thấy dòng hàng")

    product = models.Product(name=line.product_name_raw, unit="thùng")
    db.add(product)
    db.flush()  # cần product.id trước khi gán

    line.product_id = product.id
    db.commit()
    db.refresh(product)
    return product


@router.get("/{product_id}", response_model=schemas.ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    """Đặt cuối cùng trong file (dù thứ tự không bắt buộc vì product_id có
    kiểu int nên không khớp nhầm với các path chữ như /unmapped-lines) —
    quy ước cho dễ đọc: route cụ thể trước, route tổng quát sau."""
    product = db.get(models.Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")
    return product
