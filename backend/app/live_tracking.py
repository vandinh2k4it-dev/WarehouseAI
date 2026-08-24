"""Đếm trực tiếp (real-time) — nhận từng khung hình rời rạc gửi liên tục từ
điện thoại (khác với camera/count_pipeline.py xử lý nguyên 1 file video 1
lần). Mỗi phiên đếm (session_id) giữ 1 model YOLO RIÊNG trong bộ nhớ suốt
quá trình quay, để ByteTrack duy trì đúng track ID xuyên suốt nhiều khung
hình liên tiếp (persist=True) — không dùng chung 1 model cho nhiều phiên
cùng lúc vì sẽ làm lẫn track ID giữa các phiên khác nhau.

Đánh đổi: tải model riêng cho mỗi phiên tốn thêm bộ nhớ/thời gian so với
dùng chung 1 model toàn cục — chấp nhận được ở quy mô demo khóa luận (vài
người dùng, không phải hệ thống nhiều người dùng đồng thời quy mô lớn).
Có dọn phiên cũ không hoạt động quá lâu (cleanup_stale) để tránh rò rỉ
bộ nhớ nếu nhân viên bỏ dở không bấm "Xong".
"""
import time
import logging
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)

_sessions: dict[int, dict] = {}
_lock = Lock()

DEFAULT_CONF = 0.35  # hạ từ 0.5 -> 0.35: model dễ bỏ sót thùng bị che khuất/
# xếp chồng/góc chụp khó nếu ngưỡng quá cao — đổi thấp hơn để bắt được nhiều
# hơn, đánh đổi lại có thể tăng nhận nhầm vật khác thành thùng. Có thể chỉnh
# qua tham số ?conf=... trên endpoint /live-frame nếu 0.35 vẫn chưa phù hợp
# với điều kiện ánh sáng/góc camera thực tế — không cần sửa code, đổi số
# ngay trên URL để thử nghiệm nhanh.
DEFAULT_IOU = 0.45
STALE_SECONDS = 600  # phiên không hoạt động quá 10 phút -> tự dọn

# Khung hộp chiếm > 65% diện tích khung hình -> loại bỏ, nghi ngờ là
# tường/tủ máy/hàng rào sắt hoặc vật thể lớn tĩnh khác bị nhận NHẦM thành
# thùng carton (đã gặp thật khi test video ở môi trường khác điều kiện
# train — xem ảnh chụp: model nhận nhầm tường/tủ điện thành "carton_box").
# Thùng carton thật đi qua camera ở khoảng cách quay bình thường (kịch bản
# băng chuyền) hiếm khi chiếm gần hết khung hình như vậy.
#
# ĐÁNH ĐỔI: nếu quay CẬN CẢNH 1 thùng lớn (thùng chiếm gần hết khung hình
# do đặt camera sát), bộ lọc này CÓ THỂ loại nhầm thùng thật — nếu gặp
# trường hợp đó, tăng MAX_BOX_AREA_RATIO lên 0.75-0.8, hoặc giãn camera ra
# xa hơn khi quay thay vì đổi số này.
MAX_BOX_AREA_RATIO = 0.65


def _is_plausible_box_size(x1: float, y1: float, x2: float, y2: float, frame_w: int, frame_h: int) -> bool:
    """True nếu khung hộp có kích thước hợp lý so với cả khung hình (không
    quá to, nghi ngờ là tường/vật thể lớn tĩnh bị nhận nhầm)."""
    box_area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    frame_area = frame_w * frame_h
    if frame_area <= 0:
        return True
    return (box_area / frame_area) <= MAX_BOX_AREA_RATIO

# Dùng chung đúng 1 cấu hình ByteTrack với camera/count_pipeline.py (track_buffer
# tăng lên 90 để giảm đếm trùng khi thùng bị che khuất tạm thời) — tránh 2 nơi
# xử lý đếm (video-1-lần vs từng-khung-rời-rạc) dùng 2 tham số khác nhau, dễ
# gây kết quả lệch nhau khó giải thích.
_TRACKER_CONFIG = str(Path(__file__).resolve().parent.parent / "camera" / "carton_bytetrack.yaml")


def _get_or_create(session_id: int, model_path: str):
    with _lock:
        state = _sessions.get(session_id)
        if state is None:
            from ultralytics import YOLO  # import trễ — nặng, chỉ tải khi thật sự cần

            state = {"model": YOLO(model_path), "seen_ids": set(), "last_used": time.time()}
            _sessions[session_id] = state
        state["last_used"] = time.time()
        return state


def process_frame(session_id: int, model_path: str, frame_bytes: bytes,
                   conf: float = DEFAULT_CONF, iou: float = DEFAULT_IOU) -> dict:
    """Chạy YOLOv8 + ByteTrack (persist=True) trên ĐÚNG 1 khung hình, cộng
    dồn track ID mới thấy vào tập hợp đã đếm của phiên này. Trả về danh sách
    khung hộp (để frontend vẽ đè lên video) + tổng số đã đếm tới thời điểm
    hiện tại."""
    import cv2
    import numpy as np

    state = _get_or_create(session_id, model_path)
    model = state["model"]

    arr = np.frombuffer(frame_bytes, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Không đọc được ảnh gửi lên (file hỏng hoặc sai định dạng)")

    results = model.track(
        frame, persist=True, tracker=_TRACKER_CONFIG,
        conf=conf, iou=iou, verbose=False,
    )

    boxes_out = []
    r = results[0] if results else None
    h, w = frame.shape[:2]  # cần lấy TRƯỚC vòng lặp để dùng cho bộ lọc kích thước
    if r is not None and r.boxes is not None and r.boxes.id is not None:
        xyxy = r.boxes.xyxy.tolist()
        ids = r.boxes.id.tolist()
        confs = r.boxes.conf.tolist()
        for box, track_id, confidence in zip(xyxy, ids, confs):
            x1, y1, x2, y2 = box
            if not _is_plausible_box_size(x1, y1, x2, y2, w, h):
                continue  # nghi ngờ tường/tủ máy/vật thể lớn tĩnh -> bỏ qua, không đếm
            tid = int(track_id)
            state["seen_ids"].add(tid)
            boxes_out.append({
                "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                "track_id": tid, "conf": round(float(confidence), 3),
            })

    return {
        "boxes": boxes_out,
        "count": len(state["seen_ids"]),
        "frame_width": w,
        "frame_height": h,
    }


def close_session(session_id: int):
    """Giải phóng model + trạng thái của 1 phiên — gọi khi phiên kết thúc
    (bấm Xong/Huỷ) để không giữ model trong bộ nhớ mãi."""
    with _lock:
        _sessions.pop(session_id, None)


def cleanup_stale():
    """Dọn các phiên bỏ dở quá lâu không hoạt động (nhân viên thoát app giữa
    chừng, không bấm Xong/Huỷ) — nên gọi định kỳ, ví dụ mỗi lần có phiên mới
    bắt đầu, để tránh rò rỉ bộ nhớ dần theo thời gian."""
    with _lock:
        now = time.time()
        stale = [sid for sid, s in _sessions.items() if now - s["last_used"] > STALE_SECONDS]
        for sid in stale:
            _sessions.pop(sid, None)
        if stale:
            logger.info(f"Đã dọn {len(stale)} phiên đếm trực tiếp bỏ dở quá lâu.")
