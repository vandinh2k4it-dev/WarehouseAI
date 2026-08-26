import os
import time
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app import push_service
from app.routers.reconciliation import apply_line_import
from app.routers.inventory import perform_fefo_export

router = APIRouter(prefix="/camera-sessions", tags=["camera"])

DEFAULT_THRESHOLD_PCT = 0.02


@router.post("", response_model=schemas.CameraSessionOut)
def create_camera_session(payload: schemas.CameraSessionCreate, db: Session = Depends(get_db)):
    """[Cách cũ — đối chiếu theo CẢ PHIẾU] Nhận kết quả đếm 1 lần cho toàn bộ
    phiếu. Vẫn giữ lại để tương thích ngược (test/verify_full_flow.py). Quy
    trình MỚI (đếm theo từng loại hàng, không chặn khi lệch — chỉ cảnh báo,
    nhân viên tự do skip qua loại khác) dùng /start-import, /start-export,
    /{id}/stop, /{id}/resolve bên dưới."""
    session = models.CameraCountSession(**payload.model_dump(), direction="import", status="completed")
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/{session_id}", response_model=schemas.CameraSessionOut)
def get_camera_session(session_id: int, db: Session = Depends(get_db)):
    session = db.get(models.CameraCountSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên đếm camera")
    return session


# ======================================================================
# QUY TRÌNH ĐẾM THEO TỪNG LOẠI HÀNG (mỗi lần chỉ 1 loại đi qua băng chuyền)
# ======================================================================

@router.post("/start-import", response_model=schemas.CameraSessionOut)
def start_import_segment(payload: schemas.CameraSegmentStartImport, db: Session = Depends(get_db)):
    """Nhân viên chọn ĐÚNG 1 dòng hàng trên phiếu nhập (vd 'Sữa Vinamilk')
    trước khi hàng loại đó bắt đầu đi qua băng chuyền, rồi bấm bắt đầu đếm.

    KHÔNG có "chặn cứng" giữa các loại hàng — nhân viên có toàn quyền bỏ qua
    (skip) 1 loại đang bị lệch để đếm loại khác trước, quay lại xử lý sau.
    Nếu dòng ĐANG có 1 phiên bị lệch (needs_review) chưa xử lý, chọn lại
    đúng dòng đó được hiểu là "đếm lại" — tự động đóng phiên cũ, mở phiên mới.
    """
    line = db.get(models.ReceiptLineItem, payload.receipt_line_item_id)
    if not line:
        raise HTTPException(status_code=404, detail="Không tìm thấy dòng hàng trên phiếu")

    already_done = (
        db.query(models.CameraCountSession)
        .filter(
            models.CameraCountSession.receipt_line_item_id == line.id,
            models.CameraCountSession.status.in_(["completed", "resolved_override"]),
        )
        .first()
    )
    if already_done:
        raise HTTPException(
            status_code=409,
            detail=f"Dòng hàng '{line.product_name_raw}' đã đếm xong rồi (phiên #{already_done.id}).",
        )

    # Đang có phiên LỆCH chưa xử lý, HOẶC phiên "đang đếm" bị BỎ DỞ (nhân
    # viên thoát app/trình duyệt giữa chừng, chưa bao giờ bấm Xong/Huỷ) cho
    # ĐÚNG dòng này -> coi như đếm lại, tự động đóng phiên cũ. Không xử lý
    # trường hợp này thì dòng sẽ bị kẹt vĩnh viễn ở trạng thái "đang đếm",
    # không có cách nào bấm lại được từ giao diện (đã xảy ra thật khi test).
    pending = (
        db.query(models.CameraCountSession)
        .filter(
            models.CameraCountSession.receipt_line_item_id == line.id,
            models.CameraCountSession.status.in_(["needs_review", "counting"]),
        )
        .first()
    )
    if pending:
        pending.status = "superseded"
        try:
            from app import live_tracking
            live_tracking.close_session(pending.id)
        except ImportError:
            pass

    session = models.CameraCountSession(
        direction="import",
        linked_receipt_id=line.receipt_id,
        receipt_line_item_id=line.id,
        product_id=line.product_id,
        expected_quantity=line.quantity,
        camera_id=payload.camera_id,
        status="counting",
        started_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.post("/start-export", response_model=schemas.CameraSessionOut)
def start_export_segment(payload: schemas.CameraSegmentStartExport, db: Session = Depends(get_db)):
    """Xuất hàng: chưa có phiếu xuất trước — nhân viên chọn sản phẩm + gõ tay
    số lượng dự kiến xuất ngay lúc đó, rồi hàng loại đó đi qua băng chuyền.
    Không chặn — có thể xuất sản phẩm khác trước rồi quay lại xử lý phiên lệch sau."""
    product = db.get(models.Product, payload.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")
    if payload.expected_quantity <= 0:
        raise HTTPException(status_code=400, detail="Số lượng dự kiến xuất phải lớn hơn 0")

    session = models.CameraCountSession(
        direction="export",
        product_id=product.id,
        expected_quantity=payload.expected_quantity,
        camera_id=payload.camera_id,
        status="counting",
        started_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.post("/{session_id}/stop", response_model=schemas.CameraSegmentStopResult)
def stop_segment(session_id: int, payload: schemas.CameraSegmentStopRequest, db: Session = Depends(get_db)):
    """Nhân viên bấm 'Xong loại này'. So khớp counted_quantity vs expected_quantity:
    - Khớp (trong ngưỡng) -> cập nhật tồn kho NGAY cho đúng loại hàng này.
    - Lệch -> CHỈ CẢNH BÁO (status='needs_review'), KHÔNG chặn — nhân viên
      vẫn được phép chuyển sang loại hàng khác ngay (skip), quay lại xử lý
      dòng lệch này sau qua /{id}/resolve (đếm lại hoặc xác nhận ghi đè).
    """
    session = db.get(models.CameraCountSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên đếm")
    return _finalize_stop(
        db, session,
        counted_quantity=payload.counted_quantity,
        avg_detection_confidence=payload.avg_detection_confidence,
        model_version=payload.model_version,
        video_path=payload.video_path,
        threshold_pct=payload.threshold_pct,
    )


def _finalize_stop(
    db: Session, session: models.CameraCountSession, *, counted_quantity: int,
    avg_detection_confidence: float | None, model_version: str | None,
    video_path: str | None, threshold_pct: float, annotated_video_url: str | None = None,
) -> schemas.CameraSegmentStopResult:
    """Logic lõi của bước 'Xong loại này' — dùng chung cho cả 2 đường vào:
    (1) /stop — nhập tay số đếm (demo/mô phỏng trên web),
    (2) /count-video — upload video quay từ điện thoại, TỰ đếm rồi gọi thẳng
    hàm này, không cần round-trip riêng."""
    if session.status != "counting":
        raise HTTPException(
            status_code=409,
            detail=f"Phiên đếm #{session.id} đang ở trạng thái '{session.status}', không thể /stop lại.",
        )

    # Dọn trạng thái đếm trực tiếp (nếu phiên này có dùng /live-frame) — an
    # toàn để gọi kể cả khi phiên chưa từng dùng chế độ trực tiếp (no-op).
    try:
        from app import live_tracking
        live_tracking.close_session(session.id)
    except ImportError:
        pass

    session.counted_quantity = counted_quantity
    session.avg_detection_confidence = avg_detection_confidence
    session.model_version = model_version
    session.video_path = video_path
    session.ended_at = datetime.now(timezone.utc)

    expected = float(session.expected_quantity)
    difference = counted_quantity - expected
    diff_pct = abs(difference) / expected if expected else 1.0
    matched = diff_pct <= threshold_pct

    recon = models.Reconciliation(
        receipt_id=session.linked_receipt_id,
        receipt_line_item_id=session.receipt_line_item_id,
        product_id=session.product_id,
        session_id=session.id,
        receipt_total=expected,
        camera_total=counted_quantity,
        difference=difference,
        threshold_used=threshold_pct,
        status="matched" if matched else "flagged",
    )
    db.add(recon)
    db.flush()

    product = db.get(models.Product, session.product_id) if session.product_id else None

    # Xác định tên sản phẩm hiện trong thông báo — với phiên "export",
    # session.product_id có sẵn (product ở trên đã đúng). Với phiên
    # "import" thì session.product_id THƯỜNG LÀ NULL (sản phẩm chỉ được
    # xác định qua receipt_line_item_id, không gán trực tiếp vào session)
    # — nếu không xử lý riêng, rơi vào nhánh dự phòng cũ in thẳng
    # f"sản phẩm #{session.product_id}" ra ĐÚNG CHỮ "sản phẩm #None" (lỗi
    # thật đã xảy ra, thấy trong ảnh chụp cảnh báo trên Tổng quan). Sửa:
    # với phiên import, ưu tiên lấy product_name_raw từ ReceiptLineItem
    # (luôn có, kể cả khi OCR chưa khớp được sản phẩm nào trong danh mục).
    line_for_name = None
    if session.direction == "import" and session.receipt_line_item_id:
        line_for_name = db.get(models.ReceiptLineItem, session.receipt_line_item_id)

    if line_for_name:
        product_name = line_for_name.product_name_raw
    elif product:
        product_name = product.name
    else:
        product_name = "sản phẩm này"  # dự phòng an toàn — KHÔNG BAO GIỜ in ra dạng "#None"

    if matched:
        session.status = "completed"
        if session.direction == "import":
            line = line_for_name or db.get(models.ReceiptLineItem, session.receipt_line_item_id)
            apply_line_import(db, line)
            _maybe_complete_receipt(db, line.receipt_id)
        else:  # export
            perform_fefo_export(
                db, session.product_id, counted_quantity,
                note=f"Xuất qua camera, phiên #{session.id}",
                reference_type="camera_session", reference_id=session.id,
            )
        db.commit()
        db.refresh(session)
        db.refresh(recon)
        return schemas.CameraSegmentStopResult(
            session=session, reconciliation=recon, can_proceed_to_next=True,
            message=f"Khớp số — đã cập nhật kho cho '{product_name}'. Có thể chuyển sang loại hàng tiếp theo.",
            annotated_video_url=annotated_video_url,
        )
    else:
        session.status = "needs_review"
        alert_message = (
            f"[{session.direction.upper()}] Lệch {difference:+.0f} khi đếm '{product_name}' — "
            f"camera đếm {counted_quantity}, cần {expected:.0f} "
            f"(vượt ngưỡng {threshold_pct:.1%}). Chưa cập nhật tồn kho cho loại này — "
            f"cần kiểm tra lại (phiên #{session.id})."
        )
        db.add(models.Alert(
            alert_type="discrepancy", severity="high", reconciliation_id=recon.id,
            message=alert_message,
        ))
        db.commit()
        push_service.send_push_to_all(
            db, title="⚠️ Phát hiện lệch số", body=alert_message[:180], url="/alerts",
        )
        db.refresh(session)
        db.refresh(recon)
        return schemas.CameraSegmentStopResult(
            session=session, reconciliation=recon, can_proceed_to_next=True,
            message=(
                f"LỆCH SỐ — camera đếm {counted_quantity}, phiếu/khai báo là {expected:.0f}. "
                f"Đã ghi cảnh báo, CÓ THỂ chuyển sang loại hàng khác ngay. Quay lại xử lý dòng này "
                f"sau qua POST /camera-sessions/{session.id}/resolve (đếm lại hoặc xác nhận ghi đè)."
            ),
            annotated_video_url=annotated_video_url,
        )


@router.post("/{session_id}/live-frame")
async def live_frame(
    session_id: int, file: UploadFile = File(...),
    conf: float = 0.35,  # trùng DEFAULT_CONF trong live_tracking.py — không
    # tham chiếu trực tiếp live_tracking.DEFAULT_CONF ở đây được vì module
    # đó chỉ import TRỄ bên trong hàm (bên dưới), Python sẽ đánh giá giá trị
    # mặc định của tham số NGAY LÚC ĐỊNH NGHĨA HÀM (lúc app khởi động) —
    # trước khi phần import trễ kịp chạy, gây lỗi NameError khi khởi động.
    iou: float = 0.45,
    db: Session = Depends(get_db),
):
    """Đếm TRỰC TIẾP theo thời gian thực — điện thoại gửi liên tục từng
    khung hình rời rạc (không phải nguyên video như /count-video), backend
    chạy YOLOv8+ByteTrack ngay trên khung đó, trả về toạ độ khung hộp (để
    frontend tự vẽ đè lên video đang xem) + tổng số đã đếm luỹ kế tới thời
    điểm hiện tại trong phiên này.

    Tham số conf/iou cho phép CHỈNH NGƯỠNG THỬ NGHIỆM ngay trên URL, không
    cần sửa code/deploy lại — hữu ích khi cần tinh chỉnh theo điều kiện ánh
    sáng/góc camera thực tế. Ví dụ hạ ngưỡng xuống 0.25 nếu model đang bỏ
    sót nhiều thùng: /live-frame?conf=0.25

    KHÔNG cập nhật tồn kho ở đây — chỉ trả số để hiển thị trực tiếp. Khi
    nhân viên bấm "Xong", frontend gọi /stop (JSON, đúng endpoint có sẵn)
    với số đếm cuối cùng để thực sự đối chiếu + cập nhật kho."""
    session = db.get(models.CameraCountSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên đếm")
    if session.status != "counting":
        raise HTTPException(
            status_code=409,
            detail=f"Phiên đếm #{session_id} đang ở trạng thái '{session.status}', không thể đếm trực tiếp.",
        )

    try:
        from app import live_tracking
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Chưa cài đủ thư viện đếm trực tiếp trên server: {e!r}. Chạy: pip install ultralytics opencv-python-headless.",
        )

    model_path = os.getenv("CARTON_MODEL_PATH", "yolov8s.pt")
    frame_bytes = await file.read()
    try:
        result = live_tracking.process_frame(session_id, model_path, frame_bytes, conf=conf, iou=iou)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Xử lý khung hình thất bại: {e!r}")

    return result


def _reencode_to_h264(src_path: Path, dst_path: Path) -> bool:
    """Chuyển đổi video sang H.264/MP4 chuẩn — ultralytics thường xuất video
    bằng codec (mpeg4/mp4v qua container .avi) mà trình duyệt KHÔNG phát
    trực tiếp được qua thẻ <video> (hiện ra 0:00, bấm play không chạy —
    đúng hiện tượng gặp phải thật). Cần có ffmpeg cài sẵn trên server.
    Trả về True nếu chuyển đổi thành công, False nếu ffmpeg lỗi/không có
    (gọi nơi khác nên có phương án dự phòng, không được để crash cả request
    chỉ vì bước phụ này thất bại)."""
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(src_path),
                "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",  # cho phép phát ngay trong lúc tải, không cần tải hết file mới xem được
                str(dst_path),
            ],
            check=True, capture_output=True, timeout=180, text=True,
        )
        return dst_path.exists() and dst_path.stat().st_size > 0
    except FileNotFoundError:
        print("[annotated-video] ffmpeg KHÔNG có trên server — cần thêm 'ffmpeg' vào "
              "RAILPACK_BUILD_APT_PACKAGES/RAILPACK_DEPLOY_APT_PACKAGES trên Railway.")
        return False
    except subprocess.CalledProcessError as e:
        print(f"[annotated-video] ffmpeg chuyển đổi thất bại: {e.stderr[-500:] if e.stderr else e!r}")
        return False
    except subprocess.TimeoutExpired:
        print("[annotated-video] ffmpeg chuyển đổi quá thời gian cho phép (180s) — video có thể quá dài.")
        return False


@router.post("/{session_id}/count-video", response_model=schemas.CameraSegmentStopResult)
async def count_video_segment(
    session_id: int,
    file: UploadFile = File(...),
    threshold_pct: float = Form(DEFAULT_THRESHOLD_PCT),
    conf: float = Form(0.5),
    db: Session = Depends(get_db),
):
    """Nhận video quay TRỰC TIẾP từ điện thoại (qua trang mobile.html), tự
    chạy YOLOv8+ByteTrack đếm số thùng, rồi gọi thẳng luôn bước đối chiếu —
    chỉ cần 1 lần upload duy nhất, không cần vòng round-trip riêng như widget
    mô phỏng "+1" trên web desktop.

    Tham số conf (mặc định 0.5) cho phép CHỈNH NGƯỠNG confidence ngay từ
    frontend — hữu ích khi model nhận nhầm vật thể lớn tĩnh (tường, tủ máy,
    hàng rào sắt) thành thùng carton với độ tin cậy THẤP HƠN rõ rệt so với
    thùng thật (đã quan sát thực tế: khung sai ~0.5-0.6, khung đúng
    ~0.85-0.90) — tăng ngưỡng lên giúp lọc bớt các trường hợp nhận nhầm có
    độ tin cậy thấp, dù KHÔNG loại được hết mọi trường hợp (có case nhận
    nhầm từng lên tới 0.83, ngang khung đúng — xem PROJECT_CONTEXT.md).

    Cần biến môi trường CARTON_MODEL_PATH trỏ tới model .pt đã train (xem
    camera/count_pipeline.py). Nếu chưa có model thật, mặc định dùng tạm
    yolov8s.pt (COCO) — CHỈ để test luồng upload/API/DB chạy thông, số đếm
    lúc này KHÔNG mang ý nghĩa carton thật (xem README/PROJECT_CONTEXT.md)."""
    session = db.get(models.CameraCountSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên đếm")
    if session.status != "counting":
        raise HTTPException(
            status_code=409,
            detail=f"Phiên đếm #{session_id} đang ở trạng thái '{session.status}', không thể đếm video.",
        )

    try:
        from camera.count_pipeline import count_boxes_in_video, CARTON_CLASS_NAME
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Chưa cài đủ thư viện đếm video trên server: {e!r}. "
                "Chạy: pip install ultralytics (xem requirements.txt)."
            ),
        )

    model_path = os.getenv("CARTON_MODEL_PATH", "yolov8s.pt")
    upload_dir = Path("uploads/camera_videos")
    upload_dir.mkdir(parents=True, exist_ok=True)
    video_path = upload_dir / f"session_{session_id}_{datetime.now(timezone.utc).timestamp():.0f}_{file.filename}"

    with open(video_path, "wb") as f:
        f.write(await file.read())

    # Thư mục ultralytics tự ghi video đã vẽ khung hộp vào (save=True) —
    # dùng riêng cho từng phiên để tránh 2 phiên xử lý cùng lúc ghi đè nhau.
    annotated_raw_dir = Path("uploads/annotated_raw") / f"session_{session_id}"
    search_started_at = time.time()  # dùng để lọc đúng file MỚI tạo ra lần này

    try:
        result = count_boxes_in_video(
            model_path=model_path,
            video_path=str(video_path),
            conf=conf,
            target_class_name=CARTON_CLASS_NAME,
            save_annotated=True,
            output_dir=str(annotated_raw_dir),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Đếm video thất bại: {e!r}")

    # Phát hiện SỚM trường hợp đang dùng nhầm model (xem model_warning trong
    # count_boxes_in_video) — chặn lại NGAY, không cho đi tiếp vào luồng
    # "lệch số" bình thường, vì đây không phải lệch số thật mà là lỗi cấu
    # hình — để lẫn vào "LỆCH SỐ" thông thường sẽ khiến người dùng tưởng
    # nhầm là vấn đề đếm thiếu, mất công debug sai hướng (đã từng xảy ra
    # thật trước khi có cảnh báo này).
    if result.model_warning:
        raise HTTPException(status_code=500, detail=result.model_warning)

    # ultralytics KHÔNG dùng đúng nguyên đường dẫn project= truyền vào — nó
    # tự chèn thêm tiền tố "runs/<task>/" phía trước (xác nhận qua log thật:
    # truyền project="uploads/annotated_raw/session_56" nhưng file thật lại
    # nằm ở "runs/detect/uploads/annotated_raw/session_56/session/"). Thay vì
    # đoán cứng theo đúng 1 quy tắc (dễ vỡ lại nếu ultralytics đổi hành vi ở
    # bản khác), TÌM ĐỆ QUY toàn bộ file .mp4/.avi MỚI TẠO RA sau thời điểm
    # bắt đầu xử lý (search_started_at) — chắc chắn đúng bất kể ultralytics
    # đặt ở thư mục con nào.
    annotated_url = None
    try:
        search_roots = [Path("runs"), annotated_raw_dir, Path(".")]
        found_candidates = []
        for root in search_roots:
            if not root.exists():
                continue
            for ext in ("*.mp4", "*.avi"):
                for f in root.rglob(ext):
                    try:
                        if f.stat().st_mtime >= search_started_at - 2:  # trừ hao 2s cho sai lệch đồng hồ hệ thống
                            found_candidates.append(f)
                    except OSError:
                        continue

        # Loại trùng (3 thư mục tìm có thể trùng nhau) + sắp theo mới nhất trước
        seen_paths = set()
        candidates = []
        for f in sorted(found_candidates, key=lambda p: p.stat().st_mtime, reverse=True):
            resolved = f.resolve()
            if resolved not in seen_paths:
                seen_paths.add(resolved)
                candidates.append(f)

        print(f"[annotated-video] Tìm đệ quy từ thời điểm {search_started_at} -> thấy {len(candidates)} file mới")
        if candidates:
            print(f"[annotated-video] File mới nhất: {candidates[0].resolve()}")

        if candidates:
            served_dir = Path("uploads/annotated_videos")
            served_dir.mkdir(parents=True, exist_ok=True)
            final_name = f"session_{session_id}.mp4"
            final_path = served_dir / final_name

            # ultralytics xuất video bằng codec (thường mpeg4/mp4v qua .avi)
            # KHÔNG được trình duyệt hỗ trợ phát trực tiếp qua thẻ <video> —
            # phải chuyển đổi lại sang H.264/MP4 chuẩn mới phát được trên
            # mọi trình duyệt. Cần có ffmpeg cài sẵn trên server (xem
            # RAILPACK_BUILD_APT_PACKAGES/RAILPACK_DEPLOY_APT_PACKAGES).
            reencoded = _reencode_to_h264(candidates[0], final_path)
            if reencoded:
                annotated_url = f"/media/annotated/{final_name}"
                print(f"[annotated-video] Đã chuyển đổi sang H.264 + phục vụ -> {annotated_url}")
                candidates[0].unlink(missing_ok=True)  # dọn file gốc, không cần giữ 2 bản
            else:
                # ffmpeg lỗi/không có -> dùng tạm file gốc (có thể vẫn phát
                # được tuỳ trình duyệt, còn hơn không có gì để xem).
                fallback_name = f"session_{session_id}{candidates[0].suffix}"
                fallback_path = served_dir / fallback_name
                candidates[0].replace(fallback_path)
                annotated_url = f"/media/annotated/{fallback_name}"
                print(f"[annotated-video] ffmpeg lỗi/thiếu — dùng tạm file gốc chưa chuyển đổi -> {annotated_url}")
    except Exception as e:
        # Không tìm/chuyển được video đã vẽ khung hộp -> KHÔNG làm hỏng cả
        # kết quả đếm (số đếm vẫn đúng, giá trị chính) — chỉ đơn giản là
        # không có video xem lại, annotated_url ở lại None. NHƯNG vẫn in lỗi
        # thật ra log thay vì nuốt hoàn toàn như trước — cần biết lý do thật.
        print(f"[annotated-video] LỖI khi tìm/chuyển file: {e!r}")

    return _finalize_stop(
        db, session,
        counted_quantity=result.counted_quantity,
        avg_detection_confidence=result.avg_detection_confidence,
        model_version=model_path,
        video_path=str(video_path),
        threshold_pct=threshold_pct,
        annotated_video_url=annotated_url,
    )


@router.post("/{session_id}/resolve", response_model=schemas.CameraSessionOut)
def resolve_segment(session_id: int, payload: schemas.CameraSegmentResolveRequest, db: Session = Depends(get_db)):
    """Xử lý 1 dòng đang cần kiểm tra lại (needs_review) — nhân viên chủ động
    quay lại sau khi đã skip qua lúc trước:
    - action='recount': đóng phiên này (status=superseded), TẠO PHIÊN MỚI cùng
      dòng hàng/sản phẩm để đếm lại từ đầu.
    - action='override': xác nhận ghi đè, tin theo số camera thực tế, cập nhật
      kho theo số đó (không phải số phiếu) — bắt buộc phải có override_note.
    """
    session = db.get(models.CameraCountSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên đếm")
    if session.status != "needs_review":
        raise HTTPException(
            status_code=409,
            detail=f"Phiên #{session_id} không ở trạng thái cần xử lý (đang là '{session.status}'), không cần resolve.",
        )

    if payload.action == "recount":
        session.status = "superseded"
        new_session = models.CameraCountSession(
            direction=session.direction,
            linked_receipt_id=session.linked_receipt_id,
            receipt_line_item_id=session.receipt_line_item_id,
            product_id=session.product_id,
            expected_quantity=session.expected_quantity,
            camera_id=session.camera_id,
            status="counting",
            started_at=datetime.now(timezone.utc),
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        return new_session

    elif payload.action == "override":
        if not payload.override_note:
            raise HTTPException(
                status_code=400,
                detail="Cần ghi rõ lý do (override_note) khi xác nhận ghi đè số liệu lệch.",
            )
        session.status = "resolved_override"

        recon = (
            db.query(models.Reconciliation)
            .filter(models.Reconciliation.session_id == session.id)
            .order_by(models.Reconciliation.id.desc())
            .first()
        )
        if recon:
            recon.status = "resolved_override"
            recon.resolved_by = payload.resolved_by
            recon.resolved_note = payload.override_note
            recon.resolved_at = datetime.now(timezone.utc)

        if session.direction == "import":
            line = db.get(models.ReceiptLineItem, session.receipt_line_item_id)
            apply_line_import(db, line, qty_override=session.counted_quantity)
            _maybe_complete_receipt(db, line.receipt_id)
        else:
            perform_fefo_export(
                db, session.product_id, session.counted_quantity,
                note=f"Xuất qua camera (ghi đè lệch số): {payload.override_note}",
                reference_type="camera_session", reference_id=session.id,
            )

        db.commit()
        db.refresh(session)
        return session

    raise HTTPException(status_code=400, detail="action phải là 'recount' hoặc 'override'")


def _maybe_complete_receipt(db: Session, receipt_id: int):
    """Sau khi 1 dòng hàng khớp xong, kiểm tra nếu TẤT CẢ dòng của phiếu đã
    xong (completed/resolved_override) thì đánh dấu cả phiếu 'reconciled'."""
    receipt = db.get(models.ImportReceipt, receipt_id)
    if not receipt:
        return
    lines_with_product = [l for l in receipt.line_items if l.product_id is not None]
    if not lines_with_product:
        return

    for line in lines_with_product:
        done = (
            db.query(models.CameraCountSession)
            .filter(
                models.CameraCountSession.receipt_line_item_id == line.id,
                models.CameraCountSession.status.in_(["completed", "resolved_override"]),
            )
            .first()
        )
        if not done:
            return  # còn ít nhất 1 dòng chưa xong -> chưa hoàn tất cả phiếu

    receipt.status = "reconciled"
