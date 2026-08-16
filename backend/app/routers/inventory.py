from datetime import date, timedelta, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app import push_service

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("", response_model=list[schemas.InventoryOut])
def list_inventory(product_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(models.Inventory)
    if product_id:
        query = query.filter(models.Inventory.product_id == product_id)
    return query.all()


@router.get("/low-stock", response_model=list[schemas.InventoryOut])
def low_stock(db: Session = Depends(get_db)):
    """Dùng cho chatbot: 'kho nào sắp hết hàng?' — join với ngưỡng riêng của từng sản phẩm."""
    return (
        db.query(models.Inventory)
        .join(models.Product)
        .filter(models.Inventory.quantity <= models.Product.low_stock_threshold)
        .all()
    )


@router.get("/expiring-soon", response_model=list[schemas.InventoryOut])
def expiring_soon(days: int = 30, db: Session = Depends(get_db)):
    """Dùng cho chatbot: 'lô hàng nào sắp hết hạn?' — mặc định trong 30 ngày tới."""
    cutoff = date.today() + timedelta(days=days)
    return (
        db.query(models.Inventory)
        .filter(models.Inventory.expiry_date.isnot(None))
        .filter(models.Inventory.expiry_date <= cutoff)
        .filter(models.Inventory.expiry_date >= date.today())
        .all()
    )


@router.post("/export", response_model=schemas.ExportResult)
def export_inventory(payload: schemas.ExportRequest, db: Session = Depends(get_db)):
    """Xuất kho (bán hàng / xuất huỷ...). Nếu chỉ định `batch_code`, trừ đúng lô
    đó. Nếu KHÔNG chỉ định, tự động trừ theo nguyên tắc FEFO (First-Expired-
    First-Out — lô hết hạn sớm nhất trừ trước, giảm rủi ro tồn hàng hết hạn),
    có thể trừ qua nhiều lô nếu 1 lô không đủ số lượng yêu cầu.
    """
    return perform_fefo_export(
        db, payload.product_id, payload.quantity, batch_code=payload.batch_code, note=payload.note,
    )


def perform_fefo_export(
    db: Session, product_id: int, quantity: float, batch_code: str | None = None,
    note: str | None = None, reference_type: str = "manual", reference_id: int | None = None,
) -> "schemas.ExportResult":
    """Logic xuất kho dùng chung — được gọi từ endpoint /inventory/export (xuất
    tay bình thường) VÀ từ /camera-sessions/{id}/stop khi xuất hàng qua băng
    chuyền (mục quy trình đếm theo từng loại hàng) đã khớp số camera.

    Kiểm tra đủ hàng TRƯỚC khi trừ bất kỳ lô nào — tránh tình trạng trừ dở
    dang rồi mới phát hiện thiếu hàng ở lô sau.
    """
    from app import schemas  # import trễ để tránh vòng lặp import

    product = db.get(models.Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Số lượng xuất phải lớn hơn 0")

    query = db.query(models.Inventory).filter(models.Inventory.product_id == product_id)
    if batch_code:
        query = query.filter(models.Inventory.batch_code == batch_code)
        batches = query.all()
        if not batches:
            raise HTTPException(
                status_code=404,
                detail=f"Không tìm thấy lô '{batch_code}' của sản phẩm #{product_id} trong tồn kho",
            )
    else:
        batches = query.order_by(models.Inventory.expiry_date.asc().nullslast()).all()

    available_total = sum(float(b.quantity) for b in batches)
    if available_total < quantity:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Không đủ tồn kho: yêu cầu xuất {quantity}, "
                f"hiện chỉ còn {available_total} (sản phẩm '{product.name}')"
            ),
        )

    remaining_to_deduct = quantity
    details: list[schemas.ExportBatchDetail] = []
    triggered_alert_messages: list[str] = []

    for batch in batches:
        if remaining_to_deduct <= 0:
            break
        deduct = min(float(batch.quantity), remaining_to_deduct)
        batch.quantity = float(batch.quantity) - deduct
        batch.last_updated = datetime.now(timezone.utc)
        remaining_to_deduct -= deduct

        db.add(
            models.InventoryTransaction(
                inventory_id=batch.id,
                change_qty=-deduct,
                transaction_type="export",
                reference_type=reference_type,
                reference_id=reference_id,
                note=note,
            )
        )
        details.append(
            schemas.ExportBatchDetail(
                batch_code=batch.batch_code,
                quantity_deducted=deduct,
                remaining_in_batch=float(batch.quantity),
            )
        )

        alert_msg = _check_low_stock_alert(db, batch, product)
        if alert_msg:
            triggered_alert_messages.append(alert_msg)

    db.commit()

    # Gửi push SAU KHI commit thành công toàn bộ giao dịch — tách khỏi vòng
    # lặp phía trên để không commit dở dang giữa chừng nếu 1 lô sau đó lỗi.
    for msg in triggered_alert_messages:
        push_service.send_push_to_all(db, title="📦 Sắp hết hàng", body=msg[:180], url="/alerts")

    return schemas.ExportResult(product_id=product.id, total_exported=quantity, details=details)


def _check_low_stock_alert(db: Session, inventory_row: models.Inventory, product: models.Product) -> str | None:
    """Sau khi trừ kho, nếu số lượng còn lại <= ngưỡng cảnh báo của sản phẩm,
    tạo cảnh báo mới — trừ khi đã có cảnh báo 'low_stock' đang mở cho đúng
    lô này rồi (tránh tạo trùng lặp mỗi lần xuất thêm 1 chút).

    Trả về nội dung cảnh báo (str) nếu vừa tạo mới, hoặc None nếu không tạo
    gì — hàm gọi (perform_fefo_export) tự quyết định lúc nào gửi push, KHÔNG
    commit/gửi push ngay tại đây vì hàm này chạy giữa 1 vòng lặp, commit sớm
    sẽ phá vỡ tính toàn vẹn giao dịch của cả lượt xuất kho."""
    if float(inventory_row.quantity) > float(product.low_stock_threshold):
        return None

    existing_open_alert = (
        db.query(models.Alert)
        .filter(
            models.Alert.inventory_id == inventory_row.id,
            models.Alert.alert_type == "low_stock",
            models.Alert.status == "open",
        )
        .first()
    )
    if existing_open_alert:
        return None

    alert_message = (
        f"Sản phẩm '{product.name}' (lô {inventory_row.batch_code}) chỉ còn "
        f"{inventory_row.quantity} {product.unit} — dưới ngưỡng {product.low_stock_threshold}."
    )
    db.add(
        models.Alert(
            alert_type="low_stock",
            severity="medium" if inventory_row.quantity > 0 else "high",
            inventory_id=inventory_row.id,
            message=alert_message,
        )
    )
    return alert_message
