"""
Test đúng logic MỚI (mà web/PWA đang gọi) — chạy thẳng bằng dòng lệnh,
KHÔNG cần server chạy, KHÔNG cần upload video qua đâu cả.

So sánh 2 cách đếm trên CÙNG 1 file video:
  1. count_boxes_in_video() — hàm dùng cho /count-video (chế độ "Quay
     video" trên web) — xử lý TRỌN video 1 lần, y hệt logic CLI cũ.
  2. process_frame() lặp lại theo từng khung — hàm dùng cho /live-frame
     (chế độ "Trực tiếp" trên web) — xử lý TỪNG khung hình rời rạc.

Nếu (1) ra số đúng nhưng (2) ra số sai/thấp hơn nhiều -> vấn đề nằm ở
logic xử lý-theo-từng-khung (live_tracking.py), không phải model/video.
Nếu CẢ HAI đều sai giống nhau -> vấn đề nằm ở model hoặc video, không
phải logic đếm.

Cách chạy (đứng đúng thư mục warehouse-backend, đã kích hoạt venv):
    python test_video_local.py --video test\\video_thu.mp4 --model models\\carton_counter_best.pt
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True, help="Đường dẫn file video cần test")
    parser.add_argument("--model", required=True, help="Đường dẫn file model .pt")
    parser.add_argument("--conf", type=float, default=0.35, help="Ngưỡng confidence (mặc định 0.35, khớp web)")
    parser.add_argument("--sample-every", type=int, default=10,
                         help="Test theo-từng-khung: lấy mẫu mỗi N khung hình thay vì tất cả (đỡ chậm), mặc định 10")
    args = parser.parse_args()

    video_path = Path(args.video)
    model_path = Path(args.model)
    if not video_path.exists():
        print(f"❌ Không tìm thấy file video: {video_path}")
        sys.exit(1)
    if not model_path.exists():
        print(f"❌ Không tìm thấy file model: {model_path}")
        sys.exit(1)

    print("=" * 70)
    print("BƯỚC 0 — Kiểm tra file video có đọc được bằng OpenCV không")
    print("=" * 70)
    import cv2
    cap = cv2.VideoCapture(str(video_path))
    opened = cap.isOpened()
    total_frames_meta = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"Mở file thành công: {opened}")
    print(f"Số khung hình (theo metadata): {total_frames_meta}")
    print(f"FPS: {fps}")
    if not opened:
        print("\n❌ DỪNG LẠI — OpenCV không mở được file video này trên MÁY BẠN.")
        print("   Nếu đây là kết quả THẬT trên máy bạn (không phải do tải lên đâu cả),")
        print("   thì đúng là file video có vấn đề thật — cần quay lại video khác để test.")
        sys.exit(1)

    real_frame_count = 0
    frames_sample = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        real_frame_count += 1
        if real_frame_count % args.sample_every == 0:
            frames_sample.append(frame)
    cap.release()
    print(f"Số khung hình ĐỌC ĐƯỢC THẬT SỰ: {real_frame_count}")
    print(f"Số khung hình lấy mẫu để test theo-từng-khung: {len(frames_sample)}")

    print()
    print("=" * 70)
    print("BƯỚC 1 — Test count_boxes_in_video() — dùng cho chế độ 'Quay video'")
    print("(Đúng y hệt hàm CLI cũ đã test thành công trước đây)")
    print("=" * 70)
    try:
        from camera.count_pipeline import count_boxes_in_video, CARTON_CLASS_NAME
        result = count_boxes_in_video(
            model_path=str(model_path),
            video_path=str(video_path),
            target_class_name=CARTON_CLASS_NAME,
        )
        print(f"✅ Đếm được: {result.counted_quantity} thùng duy nhất")
        print(f"   Độ tin cậy trung bình: {result.avg_detection_confidence}")
    except Exception as e:
        print(f"❌ LỖI: {e!r}")

    print()
    print("=" * 70)
    print("BƯỚC 2 — Test process_frame() lặp lại — dùng cho chế độ 'Trực tiếp'")
    print("(Xử lý từng khung hình rời rạc, y hệt cách /live-frame hoạt động)")
    print("=" * 70)
    try:
        from app import live_tracking
        import io

        fake_session_id = 999999  # id giả, không đụng tới DB thật
        for i, frame in enumerate(frames_sample):
            ok, buf = cv2.imencode(".jpg", frame)
            if not ok:
                continue
            frame_bytes = buf.tobytes()
            res = live_tracking.process_frame(fake_session_id, str(model_path), frame_bytes, conf=args.conf)
            print(f"  Khung mẫu #{i+1}: thấy {len(res['boxes'])} khung hộp -> luỹ kế {res['count']}")
        live_tracking.close_session(fake_session_id)
        print(f"\n✅ Tổng đếm được (theo-từng-khung, lấy mẫu 1/{args.sample_every} khung): xem số luỹ kế cuối cùng ở trên")
        print("   LƯU Ý: đây chỉ lấy MẪU (không phải mọi khung hình) nên số sẽ THẤP HƠN")
        print("   thực tế nếu chạy đủ mọi khung — không so trực tiếp 1-1 với Bước 1.")
    except Exception as e:
        print(f"❌ LỖI: {e!r}")

    print()
    print("=" * 70)
    print("KẾT LUẬN")
    print("=" * 70)
    print("- Nếu Bước 0 báo KHÔNG mở được file -> vấn đề ở chính file video,")
    print("  không liên quan gì tới code cũ/mới.")
    print("- Nếu Bước 1 ra số ĐÚNG (khớp lần test CLI cũ) -> model + code đếm")
    print("  theo-video vẫn hoạt động tốt, vấn đề nằm ở chỗ khác (vd đường dẫn")
    print("  model trên Railway, hoặc luồng upload qua web).")
    print("- Nếu Bước 1 CŨNG sai -> có gì đó thay đổi ở model/dữ liệu, cần xem")
    print("  lại đang dùng đúng file model carton_counter_best.pt chưa.")


if __name__ == "__main__":
    main()