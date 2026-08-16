from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app import push_service

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])


@router.post("/run", response_model=schemas.ReconciliationOut)
def run_reconciliation(payload: schemas.ReconciliationRunRequest, db: Session = Depends(get_db)):
    """Đối chiếu tổng SL trên phiếu nhập với tổng SL đếm từ camera (mục 6.5).
    - Nếu chênh lệch trong ngưỡng cho phép -> tự động cập nhật tồn kho.
    - Nếu vượt ngưỡng -> đánh dấu 'flagged' + tạo cảnh báo, chờ xác nhận thủ công.
    """
    receipt = db.get(models.ImportReceipt, payload.receipt_id)
    session = db.get(models.CameraCountSession, payload.session_id)
    if not receipt or not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiếu nhập hoặc phiên đếm camera")

    existing = db.query(models.Reconciliation).filter(models.Reconciliation.receipt_id == receipt.id).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Phiếu #{receipt.id} đã được đối chiếu trước đó (id={existing.id}, "
                f"trạng thái hiện tại: {existing.status}). Mỗi phiếu chỉ đối chiếu 1 lần — "
                f"dùng /reconciliation/{existing.id}/resolve nếu cần xác nhận lại thủ công."
            ),
        )

    receipt_total = (
        db.query(func.coalesce(func.sum(models.ReceiptLineItem.quantity), 0))
        .filter(models.ReceiptLineItem.receipt_id == receipt.id)
        .scalar()
    )
    camera_total = session.counted_quantity
    difference = float(camera_total) - float(receipt_total)
    diff_pct = abs(difference) / float(receipt_total) if receipt_total else 1.0

    status = "matched" if diff_pct <= payload.threshold_pct else "flagged"

    recon = models.Reconciliation(
        receipt_id=receipt.id,
        session_id=session.id,
        receipt_total=receipt_total,
        camera_total=camera_total,
        difference=difference,
        threshold_used=payload.threshold_pct,
        status=status,
    )
    db.add(recon)
    receipt.status = "reconciled" if status == "matched" else "flagged"

    if status == "matched":
        _apply_inventory_update(db, receipt)
        db.commit()
    else:
        db.flush()  # cần recon.id cho alert
        alert_message = (
            f"Chênh lệch {difference:+.0f} thùng giữa camera ({camera_total}) "
            f"và phiếu nhập #{receipt.id} ({receipt_total}) — vượt ngưỡng "
            f"{payload.threshold_pct:.1%}. Cần kiểm tra thủ công."
        )
        db.add(
            models.Alert(
                alert_type="discrepancy",
                severity="high",
                reconciliation_id=recon.id,
                message=alert_message,
            )
        )
        db.commit()
        push_service.send_push_to_all(db, title="⚠️ Phát hiện lệch số", body=alert_message[:180], url="/alerts")
    db.refresh(recon)
    return recon


@router.post("/{reconciliation_id}/resolve", response_model=schemas.ReconciliationOut)
def resolve_reconciliation(
    reconciliation_id: int,
    payload: schemas.ReconciliationResolveRequest,
    db: Session = Depends(get_db),
):
    """Nhân viên xác nhận thủ công sau khi kiểm tra chênh lệch."""
    recon = db.get(models.Reconciliation, reconciliation_id)
    if not recon:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi đối chiếu")

    recon.status = "resolved_manual"
    recon.resolved_by = payload.resolved_by
    recon.resolved_note = payload.resolved_note
    recon.resolved_at = datetime.now(timezone.utc)

    receipt = db.get(models.ImportReceipt, recon.receipt_id)
    receipt.status = "reconciled"
    if payload.accept_camera_total:
        _apply_inventory_update(db, receipt, override_total=recon.camera_total)
    else:
        _apply_inventory_update(db, receipt)

    db.commit()
    db.refresh(recon)
    return recon


def _apply_inventory_update(db: Session, receipt: models.ImportReceipt, override_total: float = None):
    """Cộng dồn từng dòng hàng của phiếu vào bảng inventory + ghi transaction.
    override_total: nếu nhân viên chọn tin theo số đếm camera thay vì số trên phiếu,
    ta scale tỉ lệ từng dòng theo tổng camera (đơn giản hoá cho khung ban đầu —
    có thể tinh chỉnh logic phân bổ chi tiết hơn sau khi có dữ liệu thực tế).
    """
    for line in receipt.line_items:
        if line.product_id is None:
            continue  # dòng chưa map được sản phẩm -> bỏ qua, cần xử lý thủ công riêng
        apply_line_import(db, line, qty_override=None)


def apply_line_import(db: Session, line: models.ReceiptLineItem, qty_override: float = None):
    """Cộng tồn kho cho ĐÚNG 1 DÒNG HÀNG — dùng trong quy trình đếm theo từng
    loại hàng mới (mỗi lần 1 dòng khớp xong thì cộng kho ngay, không đợi cả
    phiếu xong hết). qty_override: dùng khi nhân viên xác nhận ghi đè theo số
    camera thay vì số trên phiếu (action='override' ở /camera-sessions/resolve).
    """
    if line.product_id is None:
        raise ValueError(f"Dòng #{line.id} chưa map sản phẩm, không thể cập nhật tồn kho")

    qty = float(qty_override) if qty_override is not None else float(line.quantity)

    inv = (
        db.query(models.Inventory)
        .filter(
            models.Inventory.product_id == line.product_id,
            models.Inventory.batch_code == (line.batch_code or "N/A"),
        )
        .first()
    )
    if inv is None:
        inv = models.Inventory(
            product_id=line.product_id,
            batch_code=line.batch_code or "N/A",
            quantity=0,
            expiry_date=line.expiry_date,
        )
        db.add(inv)
        db.flush()

    inv.quantity = float(inv.quantity) + qty
    inv.last_updated = datetime.now(timezone.utc)

    db.add(
        models.InventoryTransaction(
            inventory_id=inv.id,
            change_qty=qty,
            transaction_type="import",
            reference_type="receipt_line",
            reference_id=line.id,
        )
    )
    return inv
