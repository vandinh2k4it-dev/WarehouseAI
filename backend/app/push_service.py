"""Gửi Web Push notification tới toàn bộ thiết bị đã đăng ký nhận thông báo
(bảng push_subscriptions) — gọi từ bất kỳ đâu tạo ra Alert mới (camera.py,
inventory.py, reconciliation.py) để nhân viên nhận được cảnh báo ngay trên
điện thoại, kể cả khi không mở sẵn trình duyệt/app.

Cần 3 biến môi trường (xem .env.example):
  VAPID_PRIVATE_KEY  — khoá riêng, TUYỆT ĐỐI không lộ ra frontend/git công khai
  VAPID_PUBLIC_KEY   — khoá công khai, frontend dùng để đăng ký PushManager
  VAPID_CLAIM_EMAIL  — email liên hệ bắt buộc theo chuẩn VAPID (mailto:...)

Nếu chưa cấu hình đủ 3 biến, module tự tắt (không gửi, không lỗi) — để
không phá vỡ luồng tạo Alert bình thường khi push notification chưa setup.
"""
import os
import logging

logger = logging.getLogger(__name__)

VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_CLAIM_EMAIL = os.getenv("VAPID_CLAIM_EMAIL", "")

_ENABLED = bool(VAPID_PRIVATE_KEY and VAPID_PUBLIC_KEY and VAPID_CLAIM_EMAIL)


def send_push_to_all(db, title: str, body: str, url: str = "/") -> dict:
    """Gửi push tới TẤT CẢ thiết bị đã đăng ký. Trả về thống kê
    {sent, failed, removed} — không raise exception ra ngoài (gọi từ giữa
    luồng tạo Alert, lỗi gửi push không được phép làm hỏng việc tạo cảnh báo
    chính, chỉ log lại và tiếp tục)."""
    if not _ENABLED:
        logger.info("Push notification chưa cấu hình đủ VAPID_* — bỏ qua gửi.")
        return {"sent": 0, "failed": 0, "removed": 0, "enabled": False}

    # Import trễ — pywebpush kéo theo cryptography khá nặng, không cần load
    # nếu tính năng push chưa bật (đúng pattern lazy-import đã dùng cho
    # paddleocr/ultralytics trong dự án này).
    from pywebpush import webpush, WebPushException
    from app import models
    import json

    subs = db.query(models.PushSubscription).all()
    sent, failed, removed = 0, 0, 0
    payload = json.dumps({"title": title, "body": body, "url": url})

    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": f"mailto:{VAPID_CLAIM_EMAIL}"},
            )
            sent += 1
        except WebPushException as exc:
            # 404/410 = subscription hết hạn hoặc trình duyệt đã gỡ đăng ký
            # phía nó — dọn khỏi DB luôn, tránh cứ thử gửi lại mãi lần sau.
            status_code = getattr(exc.response, "status_code", None)
            if status_code in (404, 410):
                db.delete(sub)
                removed += 1
            else:
                logger.warning(f"Gửi push thất bại (endpoint {sub.endpoint[:50]}...): {exc}")
                failed += 1

    if removed:
        db.commit()

    return {"sent": sent, "failed": failed, "removed": removed, "enabled": True}
