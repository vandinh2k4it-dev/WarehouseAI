"""
count_pipeline.py — Đếm thùng carton bằng YOLOv8 + ByteTrack và đẩy kết quả
lên backend FastAPI (thay thế phần giả lập trước đây).

Trước đây: endpoint POST /camera-sessions chỉ NHẬN payload counted_quantity
đã tính sẵn (do đâu đó tính hộ) — nghĩa là chưa có mô hình thật nào chạy.

File này CHÍNH LÀ nơi tính counted_quantity thật, bằng cách:
  1. Load model YOLOv8 (.pt) — có thể là yolov8s.pt gốc (COCO, để test luồng
     end-to-end ngay hôm nay) hoặc carton_counter_best.pt sau khi huấn luyện
     xong ở notebook carton-training-yolov8.ipynb (mục 10 — model cuối cùng).
  2. Chạy model.track(..., tracker="bytetrack.yaml") trên video/luồng camera.
  3. Đếm số track ID DUY NHẤT xuất hiện (mỗi thùng chỉ tính 1 lần dù xuất
     hiện ở nhiều khung hình liên tiếp) — logic giống hệt mục 9 trong notebook.
  4. Gọi POST /camera-sessions của backend với đúng schema CameraSessionCreate
     (app/schemas.py) để lưu kết quả vào DB thật.

Cách dùng nhanh (test luồng end-to-end ngay cả khi CHƯA có model VN huấn
luyện xong — dùng tạm yolov8s.pt gốc, class 0 của COCO không phải carton
nên số đếm sẽ không đúng nghĩa, nhưng luồng API/DB sẽ chạy thật, không còn
giả lập):

    python camera/count_pipeline.py \
        --video test/video_demo.mp4 \
        --model yolov8s.pt \
        --receipt-id 12 \
        --backend-url http://localhost:8000

Khi có model.pt thật (carton_counter_best.pt từ notebook, class "carton_box"):

    python camera/count_pipeline.py \
        --video test/video_demo.mp4 \
        --model models/carton_counter_best.pt \
        --receipt-id 12
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# Import torch TRƯỚC ultralytics — trên Windows, để ultralytics tự kéo theo
# torch (import gián tiếp) đôi khi gây treo vô thời hạn lúc torch nạp DLL nội
# bộ (kẹt ở kernel32.LoadLibraryExW), có thể do xung đột thứ tự nạp DLL với
# thư viện khác đã cài trong cùng venv (paddlepaddle, numpy...). Ép torch tự
# khởi tạo xong hoàn toàn trước, độc lập, tránh được tình trạng treo này —
# cùng nguyên nhân/cách sửa như lỗi WinError 127 shm.dll gặp với PaddleOCR.
import torch  # noqa: F401

import requests

try:
    from ultralytics import YOLO
except ImportError:  # pragma: no cover
    print(
        "❌ Chưa cài ultralytics. Chạy: pip install ultralytics\n"
        "   (đã thêm vào requirements.txt — pip install -r requirements.txt)",
        file=sys.stderr,
    )
    raise


DEFAULT_BACKEND_URL = "http://localhost:8000"
CARTON_CLASS_NAME = "carton_box"  # đúng tên lớp đã định nghĩa trong notebook (CFG.CLASS_NAMES)


@dataclass
class CountResult:
    counted_quantity: int
    avg_detection_confidence: float
    total_frames: int
    track_ids: list[int] = field(default_factory=list)
    started_at: datetime = None
    ended_at: datetime = None
    model_warning: str | None = None  # cảnh báo nếu nghi ngờ đang dùng SAI model (xem bên dưới)


def count_boxes_in_video(
    model_path: str,
    video_path: str,
    conf: float = 0.5,
    iou: float = 0.45,
    target_class_name: str | None = CARTON_CLASS_NAME,
    save_annotated: bool = False,
    output_dir: str | None = None,
) -> CountResult:
    """Chạy YOLOv8 + ByteTrack trên video, trả về số thùng đếm được DUY NHẤT.

    target_class_name: nếu model có nhiều lớp (vd. đang test tạm bằng
    yolov8s.pt gốc/COCO), chỉ đếm các track thuộc lớp này. Đặt None để đếm
    mọi lớp (dùng khi model chỉ có 1 lớp carton_box, đúng thiết kế cuối cùng).
    """
    model = YOLO(model_path)
    class_names = model.names  # {id: name}

    # Nếu model chỉ train 1 lớp carton_box (đúng thiết kế), target_class_name
    # có thể không khớp tên — tự động bỏ lọc lớp trong trường hợp model chỉ
    # có đúng 1 class để tránh đếm hụt do sai tên.
    filter_by_class = target_class_name is not None and len(class_names) > 1

    # CẢNH BÁO SỚM — nếu model có nhiều lớp (nghi ngờ đang dùng nhầm model
    # COCO gốc thay vì model carton_box đã train) VÀ tên lớp cần lọc không
    # hề tồn tại trong danh sách lớp của model -> MỌI kết quả phát hiện sẽ
    # bị lọc bỏ hết, luôn ra đúng 0, dù model chạy "thành công" không báo
    # lỗi gì. Phát hiện sớm trường hợp này để báo rõ ra UI thay vì để người
    # dùng phải tự đoán vì sao đếm ra 0 (đã từng xảy ra thật — xem lịch sử
    # debug trong PROJECT_CONTEXT.md).
    model_warning = None
    if filter_by_class and target_class_name not in class_names.values():
        model_warning = (
            f"⚠️ Model '{model_path}' có {len(class_names)} lớp "
            f"({', '.join(list(class_names.values())[:5])}...) nhưng KHÔNG có lớp "
            f"'{target_class_name}' — nhiều khả năng đang dùng NHẦM model gốc (COCO) "
            f"thay vì model carton_box đã train. Mọi kết quả sẽ bị lọc về 0. "
            f"Kiểm tra lại biến môi trường CARTON_MODEL_PATH."
        )

    seen_track_ids: set[int] = set()
    confidences: list[float] = []
    frame_count = 0
    started_at = datetime.now(timezone.utc)

    track_kwargs = dict(
        source=video_path,
        conf=conf,
        iou=iou,
        tracker="bytetrack.yaml",
        persist=True,
        stream=True,
        verbose=False,
    )
    if save_annotated:
        out_dir = output_dir or "runs/count_pipeline"
        track_kwargs.update(save=True, project=out_dir, name="session", exist_ok=True)

    results_generator = model.track(**track_kwargs)

    for result in results_generator:
        frame_count += 1
        boxes = result.boxes
        if boxes is None or boxes.id is None:
            continue

        track_ids = boxes.id.int().tolist()
        cls_ids = boxes.cls.int().tolist()
        confs = boxes.conf.tolist()

        for tid, cid, c in zip(track_ids, cls_ids, confs):
            if filter_by_class and class_names.get(cid) != target_class_name:
                continue
            seen_track_ids.add(tid)
            confidences.append(c)

    ended_at = datetime.now(timezone.utc)
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

    return CountResult(
        counted_quantity=len(seen_track_ids),
        avg_detection_confidence=round(avg_conf, 4),
        total_frames=frame_count,
        track_ids=sorted(seen_track_ids),
        started_at=started_at,
        ended_at=ended_at,
        model_warning=model_warning,
    )


def push_to_backend(
    result: CountResult,
    backend_url: str,
    camera_id: str | None = None,
    linked_receipt_id: int | None = None,
    video_path: str | None = None,
    model_version: str | None = None,
    session_code: str | None = None,
) -> dict:
    """POST kết quả lên /camera-sessions — đúng schema CameraSessionCreate
    (app/schemas.py). Đây là bước thay thế cho việc trước đây phải tự tạo
    payload counted_quantity 'từ đâu đó' — giờ số liệu đến từ model thật."""
    payload = {
        "session_code": session_code,
        "camera_id": camera_id,
        "linked_receipt_id": linked_receipt_id,
        "video_path": video_path,
        "counted_quantity": result.counted_quantity,
        "avg_detection_confidence": result.avg_detection_confidence,
        "model_version": model_version,
        "started_at": result.started_at.isoformat() if result.started_at else None,
        "ended_at": result.ended_at.isoformat() if result.ended_at else None,
    }
    resp = requests.post(f"{backend_url.rstrip('/')}/camera-sessions", json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def main():
    parser = argparse.ArgumentParser(description="Đếm thùng carton bằng YOLOv8+ByteTrack và đẩy kết quả lên backend")
    parser.add_argument("--video", required=True, help="Đường dẫn video hoặc URL luồng camera (RTSP/webcam index)")
    parser.add_argument("--model", required=True, help="Đường dẫn file .pt (yolov8s.pt để test tạm, hoặc model đã huấn luyện)")
    parser.add_argument("--conf", type=float, default=0.5, help="Ngưỡng confidence (mặc định 0.5, khớp CFG.INFER_CONF trong notebook)")
    parser.add_argument("--iou", type=float, default=0.45, help="Ngưỡng IoU cho NMS (mặc định 0.45, khớp CFG.INFER_IOU)")
    parser.add_argument("--camera-id", default="cam-01")
    parser.add_argument("--receipt-id", type=int, default=None, help="ID phiếu nhập tương ứng (nếu đã có, dùng để đối chiếu ngay sau đó qua /reconciliation/run)")
    parser.add_argument("--backend-url", default=DEFAULT_BACKEND_URL)
    parser.add_argument("--session-code", default=None)
    parser.add_argument("--model-version", default=None, help="Vd. 'carton_counter_v1_gd1gd2'. Mặc định lấy tên file model.")
    parser.add_argument("--save-annotated", action="store_true", help="Lưu video đã vẽ box+track ID để kiểm tra trực quan")
    parser.add_argument("--no-push", action="store_true", help="Chỉ đếm, không gọi API (để test/debug pipeline riêng)")
    parser.add_argument("--target-class", default=CARTON_CLASS_NAME, help=f"Tên lớp cần đếm (mặc định '{CARTON_CLASS_NAME}'). Bỏ trống để đếm mọi lớp.")
    args = parser.parse_args()

    if not Path(args.video).exists() and not args.video.startswith(("rtsp://", "http://", "https://")):
        print(f"⚠️  Không tìm thấy file video: {args.video} (bỏ qua kiểm tra nếu đây là RTSP/webcam index)")

    t0 = time.time()
    result = count_boxes_in_video(
        model_path=args.model,
        video_path=args.video,
        conf=args.conf,
        iou=args.iou,
        target_class_name=args.target_class or None,
        save_annotated=args.save_annotated,
    )
    elapsed = time.time() - t0

    print(f"✅ Đếm xong: {result.counted_quantity} thùng duy nhất "
          f"({result.total_frames} khung hình, {elapsed:.1f}s, "
          f"conf trung bình {result.avg_detection_confidence:.3f})")

    if args.no_push:
        print("⏭️  --no-push: bỏ qua bước gửi lên backend.")
        return

    model_version = args.model_version or Path(args.model).stem
    try:
        saved = push_to_backend(
            result,
            backend_url=args.backend_url,
            camera_id=args.camera_id,
            linked_receipt_id=args.receipt_id,
            video_path=args.video,
            model_version=model_version,
            session_code=args.session_code,
        )
    except requests.RequestException as e:
        print(f"❌ Gửi lên backend thất bại: {e}", file=sys.stderr)
        print("   Kiểm tra backend đã chạy chưa: uvicorn app.main:app --reload", file=sys.stderr)
        sys.exit(1)

    print(f"📤 Đã lưu vào DB — camera_session id={saved['id']}")
    if args.receipt_id:
        print(
            f"➡️  Tiếp theo, gọi POST {args.backend_url}/reconciliation/run "
            f'với {{"receipt_id": {args.receipt_id}, "session_id": {saved["id"]}}} '
            "để đối chiếu với phiếu nhập."
        )


if __name__ == "__main__":
    main()
