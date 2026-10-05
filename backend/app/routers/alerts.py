from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[schemas.AlertOut])
def list_alerts(status: Optional[str] = "open", db: Session = Depends(get_db)):
    query = db.query(models.Alert)
    if status:
        query = query.filter(models.Alert.status == status)
    return query.order_by(models.Alert.created_at.desc()).all()


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
