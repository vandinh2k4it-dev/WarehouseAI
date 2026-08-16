from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, push_service

router = APIRouter(prefix="/push", tags=["push"])


@router.get("/vapid-public-key")
def get_vapid_public_key():
    """Frontend gọi endpoint này để lấy khoá công khai lúc đăng ký
    PushManager.subscribe() — không cần hardcode khoá trong code frontend,
    tránh lệch khoá nếu backend đổi khoá sau này."""
    if not push_service.VAPID_PUBLIC_KEY:
        raise HTTPException(
            status_code=503,
            detail="Push notification chưa được cấu hình trên server (thiếu biến VAPID_PUBLIC_KEY).",
        )
    return {"public_key": push_service.VAPID_PUBLIC_KEY}


class SubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class SubscribeRequest(BaseModel):
    endpoint: str
    keys: SubscriptionKeys
    label: str | None = None


@router.post("/subscribe")
def subscribe(payload: SubscribeRequest, db: Session = Depends(get_db)):
    existing = db.query(models.PushSubscription).filter(
        models.PushSubscription.endpoint == payload.endpoint
    ).first()
    if existing:
        existing.p256dh = payload.keys.p256dh
        existing.auth = payload.keys.auth
        existing.label = payload.label
        db.commit()
        return {"message": "Đã cập nhật đăng ký nhận thông báo cho thiết bị này."}

    sub = models.PushSubscription(
        endpoint=payload.endpoint,
        p256dh=payload.keys.p256dh,
        auth=payload.keys.auth,
        label=payload.label,
    )
    db.add(sub)
    db.commit()
    return {"message": "Đã đăng ký nhận thông báo cho thiết bị này."}


class UnsubscribeRequest(BaseModel):
    endpoint: str


@router.post("/unsubscribe")
def unsubscribe(payload: UnsubscribeRequest, db: Session = Depends(get_db)):
    db.query(models.PushSubscription).filter(
        models.PushSubscription.endpoint == payload.endpoint
    ).delete()
    db.commit()
    return {"message": "Đã huỷ đăng ký nhận thông báo cho thiết bị này."}


@router.post("/test")
def send_test_push(db: Session = Depends(get_db)):
    """Gửi thử 1 thông báo tới tất cả thiết bị đã đăng ký — dùng để xác nhận
    setup VAPID key + service worker hoạt động đúng trước khi tin vào cảnh
    báo thật."""
    result = push_service.send_push_to_all(
        db, title="🔔 Test thông báo", body="Nếu bạn thấy thông báo này, push notification đã hoạt động đúng!",
    )
    if not result["enabled"]:
        raise HTTPException(
            status_code=503,
            detail="Push notification chưa được cấu hình trên server (thiếu VAPID_PRIVATE_KEY/VAPID_PUBLIC_KEY/VAPID_CLAIM_EMAIL).",
        )
    return result
