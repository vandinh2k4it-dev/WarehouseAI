"""Công cụ chọn vùng ROI (Region Of Interest) bằng tay, trực quan — mở khung
hình ĐẦU TIÊN của video lên, bạn kéo chuột chọn đúng vùng băng chuyền/nơi
thùng thật sự đi qua (bỏ ra ngoài phần có vật gây nhận nhầm), xong bấm ENTER
— script tự tính và in ra chuỗi toạ độ theo TỈ LỆ (0.0-1.0), dán thẳng được
vào --roi của camera/count_pipeline.py, không cần tự đoán/tính số bằng tay.

CÁCH DÙNG:
    python camera/pick_roi.py --video test/video_demo.mp4

TRONG CỬA SỔ HIỆN RA:
    - Kéo chuột từ góc trên-trái tới góc dưới-phải để vẽ khung chọn.
    - Bấm ENTER hoặc SPACE để xác nhận vùng đã chọn.
    - Bấm 'c' nếu muốn huỷ và chọn lại từ đầu.
    - Bấm ESC để thoát mà không lưu gì.
"""
import argparse
import sys

import cv2


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Chọn vùng ROI trực quan trên khung hình đầu của video (kéo chuột, không cần tính số)"
    )
    parser.add_argument("--video", required=True, help="Đường dẫn video cần chọn ROI")
    args = parser.parse_args()

    cap = cv2.VideoCapture(args.video)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        print(f"❌ Không đọc được khung hình đầu tiên từ: {args.video}", file=sys.stderr)
        return 1

    frame_h, frame_w = frame.shape[:2]

    print("Kéo chuột chọn đúng vùng băng chuyền/nơi thùng đi qua")
    print("(bỏ vật gây nhận nhầm — biển hiệu, cạnh kệ... — ra NGOÀI vùng chọn).")
    print("Xong bấm ENTER hoặc SPACE để xác nhận, ESC để huỷ.\n")

    x, y, box_w, box_h = cv2.selectROI(
        "Chon vung ROI - ENTER de xac nhan, ESC de huy", frame, showCrosshair=True
    )
    cv2.destroyAllWindows()

    if box_w == 0 or box_h == 0:
        print("⚠️  Không có vùng nào được chọn (đã bấm ESC hoặc chưa kéo chuột) — không có kết quả để in ra.")
        return 0

    x1_ratio = round(x / frame_w, 4)
    y1_ratio = round(y / frame_h, 4)
    x2_ratio = round((x + box_w) / frame_w, 4)
    y2_ratio = round((y + box_h) / frame_h, 4)

    roi_str = f"{x1_ratio},{y1_ratio},{x2_ratio},{y2_ratio}"
    print(f"✅ Vùng đã chọn (tính theo khung hình gốc {frame_w}x{frame_h}): {roi_str}")
    print("\nDùng lại bằng cách thêm vào lệnh count_pipeline.py, ví dụ:")
    print(
        f'    python camera/count_pipeline.py --video "{args.video}" --model models/carton_counter_best.pt '
        f'--roi "{roi_str}" --save-annotated --no-push'
    )
    print(
        "\nLưu ý: video khác có độ phân giải/khung hình khác (camera đặt lệch đi, "
        "phóng to/thu nhỏ) thì nên chọn lại ROI mới — tỉ lệ này gắn với đúng góc "
        "quay của video vừa chọn, không tự đúng cho video quay ở góc khác."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
