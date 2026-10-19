from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/alerts", tags=["alerts"])

_ANNOTATED_DIR = Path(__file__).resolve().parent.parent.parent / "uploads" / "annotated_videos"


class _Ctx:
    """Các bản ghi gốc mà 1 cảnh báo trỏ tới (thứ nào không có thì None)."""

    __slots__ = ("inventory", "product", "recon", "session", "receipt", "line")

    def __init__(self):
        self.inventory = self.product = self.recon = self.session = self.receipt = self.line = None


def _load_contexts(db: Session, alerts: list[models.Alert]) -> dict[int, _Ctx]:
    """Gom ngữ cảnh cho nhiều cảnh báo bằng vài truy vấn IN (không truy vấn từng cảnh báo một).
    Đường đi: alert.inventory_id -> lô -> sản phẩm; alert.reconciliation_id -> đối chiếu ->
    (phiên đếm, dòng phiếu -> phiếu nhập, sản phẩm)."""
    inv_ids = {a.inventory_id for a in alerts if a.inventory_id}
    rec_ids = {a.reconciliation_id for a in alerts if a.reconciliation_id}
    invs = {i.id: i for i in db.query(models.Inventory).filter(models.Inventory.id.in_(inv_ids))} if inv_ids else {}
    recs = {r.id: r for r in db.query(models.Reconciliation).filter(models.Reconciliation.id.in_(rec_ids))} if rec_ids else {}

    sess_ids = {r.session_id for r in recs.values() if r.session_id}
    line_ids = {r.receipt_line_item_id for r in recs.values() if r.receipt_line_item_id}
    sessions = {s.id: s for s in db.query(models.CameraCountSession).filter(models.CameraCountSession.id.in_(sess_ids))} if sess_ids else {}
    lines = {l.id: l for l in db.query(models.ReceiptLineItem).filter(models.ReceiptLineItem.id.in_(line_ids))} if line_ids else {}

    receipt_ids = {r.receipt_id for r in recs.values() if r.receipt_id} | {l.receipt_id for l in lines.values()}
    receipts = {r.id: r for r in db.query(models.ImportReceipt).filter(models.ImportReceipt.id.in_(receipt_ids))} if receipt_ids else {}

    prod_ids = (
        {i.product_id for i in invs.values()}
        | {r.product_id for r in recs.values() if r.product_id}
        | {l.product_id for l in lines.values() if l.product_id}
        | {s.product_id for s in sessions.values() if s.product_id}
    )
    products = {p.id: p for p in db.query(models.Product).filter(models.Product.id.in_(prod_ids))} if prod_ids else {}

    out: dict[int, _Ctx] = {}
    for a in alerts:
        c = _Ctx()
        c.inventory = invs.get(a.inventory_id)
        c.recon = recs.get(a.reconciliation_id)
        if c.recon:
            c.session = sessions.get(c.recon.session_id)
            c.line = lines.get(c.recon.receipt_line_item_id)
            rid = c.recon.receipt_id or (c.line.receipt_id if c.line else None)
            c.receipt = receipts.get(rid)
        pid = (
            (c.inventory.product_id if c.inventory else None)
            or (c.recon.product_id if c.recon else None)
            or (c.line.product_id if c.line else None)
            or (c.session.product_id if c.session else None)
        )
        c.product = products.get(pid)
        out[a.id] = c
    return out


def _alert_out(a: models.Alert, c: _Ctx) -> schemas.AlertOut:
    out = schemas.AlertOut.model_validate(a)
    out.product_id = c.product.id if c.product else None
    out.product_name = c.product.name if c.product else (c.line.product_name_raw if c.line else None)
    out.batch_code = c.inventory.batch_code if c.inventory else (c.line.batch_code if c.line else None)
    out.receipt_id = c.receipt.id if c.receipt else None
    out.receipt_code = c.receipt.receipt_code if c.receipt else None
    out.receipt_line_id = c.line.id if c.line else None
    out.session_id = c.session.id if c.session else None
    return out


@router.get("", response_model=list[schemas.AlertOut])
def list_alerts(status: Optional[str] = "open", db: Session = Depends(get_db)):
    query = db.query(models.Alert)
    if status:
        query = query.filter(models.Alert.status == status)
    alerts = query.order_by(models.Alert.created_at.desc()).all()
    ctx = _load_contexts(db, alerts)
    return [_alert_out(a, ctx[a.id]) for a in alerts]


def _batch_info(b: models.Inventory) -> schemas.AlertBatchInfo:
    return schemas.AlertBatchInfo(
        id=b.id,
        batch_code=b.batch_code,
        quantity=float(b.quantity),
        expiry_date=b.expiry_date,
        days_to_expiry=(b.expiry_date - date.today()).days if b.expiry_date else None,
        location=b.location,
    )


@router.get("/{alert_id}/detail", response_model=schemas.AlertDetailOut)
def alert_detail(alert_id: int, db: Session = Depends(get_db)):
    """Chi tiết 1 cảnh báo kèm toàn bộ thông tin liên quan (sản phẩm, lô, phiếu nhập, dòng phiếu,
    đối chiếu, phiên đếm) — để giao diện mở rộng cảnh báo và cho bấm sang từng mục."""
    alert = db.get(models.Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Không tìm thấy cảnh báo")
    c = _load_contexts(db, [alert])[alert.id]

    product = None
    stocked: list[schemas.AlertBatchInfo] = []
    if c.product:
        total = db.query(func.coalesce(func.sum(models.Inventory.quantity), 0)).filter(
            models.Inventory.product_id == c.product.id
        ).scalar()
        product = schemas.AlertProductInfo(
            id=c.product.id, name=c.product.name, sku=c.product.sku, category=c.product.category,
            unit=c.product.unit, low_stock_threshold=float(c.product.low_stock_threshold or 0),
            total_stock=float(total),
        )
        rows = (
            db.query(models.Inventory)
            .filter(models.Inventory.product_id == c.product.id, models.Inventory.quantity > 0)
            .order_by(models.Inventory.expiry_date.asc().nullslast())
            .limit(8)
            .all()
        )
        stocked = [_batch_info(b) for b in rows]

    session = None
    if c.session:
        s = c.session
        video_url = None
        for ext in (".mp4", ".webm", ".avi"):
            if (_ANNOTATED_DIR / f"session_{s.id}{ext}").is_file():
                video_url = f"/media/annotated/session_{s.id}{ext}"
                break
        session = schemas.AlertSessionInfo(
            id=s.id, session_code=s.session_code, direction=s.direction, status=s.status,
            expected_quantity=float(s.expected_quantity) if s.expected_quantity is not None else None,
            counted_quantity=s.counted_quantity,
            avg_detection_confidence=float(s.avg_detection_confidence) if s.avg_detection_confidence is not None else None,
            model_version=s.model_version, started_at=s.started_at, ended_at=s.ended_at,
            annotated_video_url=video_url,
        )

    receipt = None
    if c.receipt:
        r = c.receipt
        image_url = None
        if r.image_path:
            image_url = "/media/receipts/" + r.image_path.replace(chr(92), "/").rsplit("/", 1)[-1]
        receipt = schemas.AlertReceiptInfo(
            id=r.id, receipt_code=r.receipt_code, store_location=r.store_location, status=r.status,
            source_type=r.source_type, received_at=r.received_at, image_url=image_url,
        )

    line = None
    if c.line:
        ln = c.line
        line = schemas.AlertLineInfo(
            id=ln.id, line_no=ln.line_no, product_name_raw=ln.product_name_raw, quantity=float(ln.quantity),
            batch_code=ln.batch_code, expiry_date=ln.expiry_date, product_id=ln.product_id,
        )

    recon = None
    if c.recon:
        r = c.recon
        recon = schemas.AlertReconciliationInfo(
            id=r.id, status=r.status, receipt_total=float(r.receipt_total), camera_total=r.camera_total,
            difference=float(r.difference), threshold_used=float(r.threshold_used),
            resolved_by=r.resolved_by, resolved_note=r.resolved_note, resolved_at=r.resolved_at,
        )

    latest_status = None
    if c.line:
        latest = (
            db.query(models.CameraCountSession.status)
            .filter(models.CameraCountSession.receipt_line_item_id == c.line.id)
            .order_by(models.CameraCountSession.id.desc())
            .first()
        )
        latest_status = latest[0] if latest else None

    return schemas.AlertDetailOut(
        alert=_alert_out(alert, c),
        product=product,
        batch=_batch_info(c.inventory) if c.inventory else None,
        stocked_batches=stocked,
        reconciliation=recon,
        session=session,
        receipt=receipt,
        line=line,
        line_latest_session_status=latest_status,
    )


@router.post("/{alert_id}/acknowledge", response_model=schemas.AlertOut)
def acknowledge_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.get(models.Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Không tìm thấy cảnh báo")
    alert.status = "acknowledged"
    db.commit()
    db.refresh(alert)
    return alert


class BulkAckRequest(BaseModel):
    alert_ids: list[int] = Field(max_length=2000)


@router.post("/acknowledge-bulk")
def acknowledge_alerts_bulk(payload: BulkAckRequest, db: Session = Depends(get_db)):
    """Đánh dấu NHIỀU cảnh báo là đã xử lý trong 1 lần gọi (1 giao dịch) — dùng cho nút
    "Xác nhận tất cả đang hiển thị" ở trang Cảnh báo, thay vì gọi /acknowledge hàng trăm lần.
    Chỉ đổi các cảnh báo đang 'open'; id không tồn tại hoặc đã xử lý rồi thì bỏ qua êm.
    Trả về số cảnh báo thực sự được đổi."""
    ids = list(set(payload.alert_ids))
    if not ids:
        return {"acknowledged": 0}
    n = (
        db.query(models.Alert)
        .filter(models.Alert.id.in_(ids), models.Alert.status == "open")
        .update({"status": "acknowledged"}, synchronize_session=False)
    )
    db.commit()
    return {"acknowledged": n}
