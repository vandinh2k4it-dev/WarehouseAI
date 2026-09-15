# ============================================================
# Dockerfile triển khai backend lên Google Cloud Run.
# (ĐÃ ĐỔI TỪ Hugging Face Spaces — tháng 7/2026 HF chuyển Docker SDK sang
# yêu cầu gói PRO trả phí, không còn free cho việc chạy container nữa.
# Cloud Run vẫn có gói Always Free thật cho container Docker.)
#
# Khác biệt quan trọng so với bản Dockerfile cũ (viết cho HF Spaces):
#   - Cloud Run tự tiêm biến môi trường PORT (mặc định 8080) vào container
#     lúc chạy — server BẮT BUỘC phải lắng nghe đúng cổng này, không phải
#     cổng cố định như 7860 (HF) hay $PORT riêng của Railway.
#   - Không bắt buộc user non-root như HF, nhưng vẫn giữ lại theo thông lệ
#     bảo mật tốt — không ảnh hưởng gì tới việc chạy trên Cloud Run.
# ============================================================
FROM python:3.11-slim

# Thư viện hệ thống cần cho:
# - opencv-python-headless chạy được (không cần libGL vì dùng bản headless,
#   nhưng vẫn cần vài thư viện dùng chung bên dưới của X11/glib)
# - paddlepaddle lúc suy luận (libgomp1 = OpenMP runtime, paddlepaddle cần
#   để chạy đa luồng CPU — thiếu sẽ lỗi "libgomp.so.1: cannot open...")
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 libsm6 libxext6 libxrender1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Tạo user thường (không phải root) theo thông lệ bảo mật container tốt —
# Cloud Run không bắt buộc điều này (khác HF Spaces), nhưng giữ lại vô hại.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

WORKDIR $HOME/app

# Cài dependencies TRƯỚC khi copy code (tận dụng Docker layer cache) — nếu
# lần build sau chỉ sửa code Python (không đụng requirements.txt), Docker
# sẽ BỎ QUA bước cài lại paddlepaddle/torch (rất nặng, có thể mất 5-10 phút
# mỗi lần), giúp các lần deploy sau nhanh hơn nhiều.
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    # Y HỆT bước trong nixpacks.toml (dùng cho Railway trước đây): gỡ bản
    # opencv-python GUI (ultralytics tự kéo về làm dependency ngầm) rồi cài
    # lại bản headless — container Cloud Run cũng không có thư viện đồ họa
    # (libGL đầy đủ) nên cần bước này y hệt, nếu không sẽ lỗi
    # "ImportError: libGL.so.1: cannot open shared object file".
    && pip uninstall -y opencv-python opencv-contrib-python opencv-python-headless \
    && pip install --no-cache-dir opencv-python-headless==4.10.0.84

# Copy toàn bộ code sau cùng (đổi hay nhiều nhất, nên đặt cuối để không phá
# cache của bước cài đặt dependencies ở trên).
COPY --chown=user . .

# Cloud Run tiêm biến PORT lúc chạy — EXPOSE ở đây chỉ mang tính tài liệu
# (Cloud Run không đọc dòng EXPOSE để quyết định cổng thật).
EXPOSE 8080

# Dùng CMD dạng shell (không phải dạng mảng JSON) để ${PORT} được biến đổi
# môi trường thay thế lúc container khởi động. Có fallback về 8080 khi
# chạy thử local bằng `docker run` (không có biến PORT như trên Cloud Run).
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
