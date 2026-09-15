from datetime import date, timedelta, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, case
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


@router.put("/{inventory_id}/location", response_model=schemas.InventoryOut)
def update_inventory_location(
    inventory_id: int, payload: schemas.InventoryLocationUpdate, db: Session = Depends(get_db)
):
    """Gán/sửa vị trí vật lý (kệ, dãy...) cho 1 lô tồn kho — hoàn toàn độc
    lập với luồng nhập/xuất/đối chiếu, không ảnh hưởng số lượng hay lịch sử
    giao dịch. Gửi location="" hoặc null để xoá vị trí đã gán."""
    inv = db.get(models.Inventory, inventory_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Không tìm thấy lô tồn kho này")
    inv.location = payload.location or None
    db.commit()
    db.refresh(inv)
    return inv


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


@router.get("/analytics", response_model=schemas.AnalyticsOut)
def analytics(days: int = 30, db: Session = Depends(get_db)):
    """Dashboard báo cáo/phân tích nhập-xuất-tồn — CHỈ đọc lại dữ liệu
    InventoryTransaction/Inventory/Alert đã có sẵn từ trước, KHÔNG thêm
    bảng mới, KHÔNG đụng gì tới luồng nhập/xuất/đếm camera đang chạy.
    Dùng cho trang Dashboard mới ở frontend (xem pages/Dashboard.jsx)."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    day_expr = func.date(models.InventoryTransaction.created_at)
    imported_expr = func.sum(
        case((models.InventoryTransaction.transaction_type == "import", models.InventoryTransaction.change_qty), else_=0)
    )
    # change_qty của export lưu ÂM trong DB (xem models.py) -> đảo dấu lại
    # cho dễ đọc, khớp đúng quy ước đã dùng ở ExportHistoryItem (schemas.py).
    exported_expr = func.sum(
        case((models.InventoryTransaction.transaction_type == "export", -models.InventoryTransaction.change_qty), else_=0)
    )

    # --- Nhập/xuất theo từng ngày, trong N ngày gần nhất ---
    daily_rows = (
        db.query(day_expr.label("day"), imported_expr.label("imported"), exported_expr.label("exported"))
        .filter(models.InventoryTransaction.created_at >= since)
        .group_by(day_expr)
        .order_by(day_expr)
        .all()
    )
    daily_flow = [
        schemas.DailyFlowPoint(date=str(r.day), imported=float(r.imported or 0), exported=float(r.exported or 0))
        for r in daily_rows
    ]

    # --- Top 10 sản phẩm quay vòng nhiều nhất (tổng nhập + xuất) ---
    top_rows = (
        db.query(
            models.Product.id,
            models.Product.name,
            models.Product.sku,
            models.Product.unit,
            imported_expr.label("imported_total"),
            exported_expr.label("exported_total"),
        )
        .join(models.Inventory, models.Inventory.product_id == models.Product.id)
        .join(models.InventoryTransaction, models.InventoryTransaction.inventory_id == models.Inventory.id)
        .filter(models.InventoryTransaction.created_at >= since)
        .group_by(models.Product.id, models.Product.name, models.Product.sku, models.Product.unit)
        .order_by((imported_expr + exported_expr).desc())
        .limit(10)
        .all()
    )
    top_products = [
        schemas.TopProductMovement(
            product_id=r.id,
            name=r.name,
            sku=r.sku,
            unit=r.unit,
            imported_total=float(r.imported_total or 0),
            exported_total=float(r.exported_total or 0),
            net_change=float((r.imported_total or 0) - (r.exported_total or 0)),
        )
        for r in top_rows
    ]

    # --- KPI nhanh cho đầu trang Dashboard ---
    open_alerts = db.query(models.Alert).filter(models.Alert.status == "open").count()
    low_stock_products = (
        db.query(models.Inventory)
        .join(models.Product)
        .filter(models.Inventory.quantity <= models.Product.low_stock_threshold)
        .count()
    )
    cutoff = date.today() + timedelta(days=30)
    expiring_soon_batches = (
        db.query(models.Inventory)
        .filter(models.Inventory.expiry_date.isnot(None))
        .filter(models.Inventory.expiry_date <= cutoff)
        .filter(models.Inventory.expiry_date >= date.today())
        .count()
    )
    total_transactions = (
        db.query(models.InventoryTransaction).filter(models.InventoryTransaction.created_at >= since).count()
    )

    return schemas.AnalyticsOut(
        days=days,
        daily_flow=daily_flow,
        top_products=top_products,
        kpis=schemas.AnalyticsKpis(
            open_alerts=open_alerts,
            low_stock_products=low_stock_products,
            expiring_soon_batches=expiring_soon_batches,
            total_transactions=total_transactions,
        ),
    )


@router.get("/export-history", response_model=list[schemas.ExportHistoryItem])
def export_history(
    limit: int = 100,
    reference_type: Optional[str] = None,
    reference_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Lịch sử xuất kho — KHÔNG cần bảng mới, đọc lại từ InventoryTransaction
    (mỗi lần xuất kho, dù qua form gõ tay /inventory/export hay qua đếm camera
    /camera-sessions/{id}/stop, đều đã tự ghi log ở đây từ trước qua
    perform_fefo_export() — endpoint này chỉ đơn giản là ĐỌC LẠI đúng dữ liệu
    đã có sẵn, join thêm tên sản phẩm/đơn vị/mã lô cho dễ đọc trên giao diện).

    reference_type/reference_id: lọc đúng 1 LƯỢT xuất cụ thể — dùng để in
    phiếu xuất kho ngay sau khi xuất xong qua đếm camera (reference_type=
    'camera_session', reference_id=<session.id>, xem app/routers/camera.py
    dòng gọi perform_fefo_export() — đã xác nhận 2 chỗ export qua camera
    đều truyền đúng 2 giá trị này). KHÔNG cần sửa camera.py để thêm tính
    năng in phiếu — chỉ cần đọc lại đúng dữ liệu đã ghi log sẵn từ trước.
    """
    query = (
        db.query(
            models.InventoryTransaction,
            models.Inventory.product_id,
            models.Inventory.batch_code,
            models.Product.name,
            models.Product.unit,
        )
        .join(models.Inventory, models.InventoryTransaction.inventory_id == models.Inventory.id)
        .join(models.Product, models.Inventory.product_id == models.Product.id)
        .filter(models.InventoryTransaction.transaction_type == "export")
    )
    if reference_type:
        query = query.filter(models.InventoryTransaction.reference_type == reference_type)
    if reference_id is not None:
        query = query.filter(models.InventoryTransaction.reference_id == reference_id)

    rows = query.order_by(models.InventoryTransaction.created_at.desc()).limit(limit).all()
    return [
        schemas.ExportHistoryItem(
            id=txn.id,
            product_id=product_id,
            product_name=product_name,
            unit=unit,
            batch_code=batch_code,
            quantity=abs(float(txn.change_qty)),  # DB lưu âm (trừ kho) -> đổi dương cho dễ đọc
            reference_type=txn.reference_type,
            reference_id=txn.reference_id,
            note=txn.note,
            created_at=txn.created_at,
        )
        for txn, product_id, batch_code, product_name, unit in rows
    ]


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