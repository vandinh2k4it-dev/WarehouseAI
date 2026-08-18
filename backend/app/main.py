import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.routers import receipts, camera, reconciliation, inventory, alerts, products, chatbot, push


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dev only: tự tạo bảng nếu chưa có. Khi có Alembic thì bỏ dòng này,
    # dùng `alembic upgrade head` thay thế để không mất lịch sử migration.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Hệ thống Quản lý Kho hàng Thông minh — API",
    description="Backend cho khóa luận: đối chiếu số đếm camera (YOLOv8+ByteTrack) "
    "với OCR Phiếu nhập hàng, cập nhật tồn kho, phục vụ chatbot AI.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — đọc từ biến môi trường CORS_ORIGINS (phân cách bởi dấu phẩy), vd:
#   CORS_ORIGINS=https://ten-du-an.vercel.app,http://localhost:5173
# Không đặt biến này -> mặc định "*" (mở cho mọi nguồn) để tiện dev/demo.
# Khi deploy thật lên Railway, PHẢI đặt đúng domain Vercel thật vào biến này
# trên Railway Dashboard (Settings > Variables) để siết lại, tránh domain lạ
# gọi thẳng vào API.
_cors_origins_env = os.getenv("CORS_ORIGINS", "*")
_cors_origins = ["*"] if _cors_origins_env.strip() == "*" else [
    o.strip() for o in _cors_origins_env.split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(receipts.router)
app.include_router(camera.router)
app.include_router(reconciliation.router)
app.include_router(inventory.router)
app.include_router(alerts.router)
app.include_router(products.router)
app.include_router(chatbot.router)
app.include_router(push.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def root():
    """Mở thẳng http://localhost:8000/ cũng tự chuyển sang trang demo, đỡ
    phải nhớ gõ thêm /app/ mỗi lần."""
    return RedirectResponse(url="/app/")


# Demo web console — mở http://localhost:8000/app/ sau khi chạy `uvicorn app.main:app --reload`
# Dùng pathlib.resolve() thay vì os.path để luôn ra đường dẫn TUYỆT ĐỐI bất kể
# cách chạy (uvicorn từ thư mục nào, hay __file__ trả về đường dẫn tương đối
# trên 1 số cấu hình Windows) — bản os.path cũ từng bị mount thất bại âm thầm
# (không báo lỗi, chỉ đơn giản là route /app/ không tồn tại -> 404).
_static_dir = Path(__file__).resolve().parent.parent / "static"
if _static_dir.is_dir():
    app.mount("/app", StaticFiles(directory=str(_static_dir), html=True), name="demo-web")
else:
    print(f"⚠️  Không tìm thấy thư mục static tại: {_static_dir} — trang demo /app/ sẽ không khả dụng.")

# Phục vụ video đã vẽ khung hộp nhận diện (xem app/routers/camera.py,
# endpoint /count-video) qua URL /media/annotated/... — tự tạo thư mục nếu
# chưa có (chưa từng đếm video nào thì thư mục này chưa tồn tại).
_annotated_dir = Path(__file__).resolve().parent.parent / "uploads" / "annotated_videos"
_annotated_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media/annotated", StaticFiles(directory=str(_annotated_dir)), name="annotated-videos")
