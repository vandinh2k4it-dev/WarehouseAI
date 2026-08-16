# Đếm hàng — PWA (thay thế static/mobile.html)

Giao diện React PWA cho nhân viên đếm thùng carton bằng camera điện
thoại — quay video, tự động upload, backend chạy YOLOv8s+ByteTrack đếm
và đối chiếu với phiếu nhập/số lượng dự kiến xuất. Gọi thẳng các API có
sẵn trên backend `warehouse-backend`, không có logic nghiệp vụ riêng ở
tầng frontend.

## Chạy thử ở máy (dev)

```powershell
npm install
copy .env.example .env
# sửa .env: VITE_API_BASE_URL=http://localhost:8000 (hoặc IP máy chạy backend)
npm run dev
```

Backend (`warehouse-backend`) phải đang chạy song song
(`uvicorn app.main:app --reload`).

## Deploy thật — Vercel (frontend) + Railway (backend)

### A. Deploy backend lên Railway trước

1. Vào [railway.app](https://railway.app), đăng nhập bằng GitHub.
2. **New Project → Deploy from GitHub repo** → chọn repo
   `warehouse-backend`.
3. Railway tự nhận diện Python qua Nixpacks, đọc đúng `nixpacks.toml`
   và `Procfile` đã có sẵn trong repo — không cần cấu hình thêm.
4. **Add a database** → chọn **PostgreSQL** — Railway tự tạo và tự gán
   biến `DATABASE_URL` cho service backend (khớp đúng tên biến app đã
   dùng sẵn, không cần đổi code).
5. Vào tab **Variables** của service backend, thêm:
   - `ANTHROPIC_API_KEY` = key thật của nhóm
   - `CARTON_MODEL_PATH` = `models/carton_counter_best.pt` (nhớ commit
     file model này vào repo trước, xem mục "Model" bên dưới)
   - `CORS_ORIGINS` = để tạm `*`, quay lại điền domain Vercel thật sau
     khi deploy xong bước B.
6. Deploy xong, Railway cấp 1 domain dạng
   `https://ten-du-an.up.railway.app` — copy lại, dùng ở bước B.

### B. Deploy frontend lên Vercel

1. Vào [vercel.com](https://vercel.com), đăng nhập bằng GitHub.
2. **Add New → Project** → chọn repo chứa thư mục `warehouse-pwa` này.
3. Vercel tự nhận diện Vite, không cần đổi Build/Output settings mặc
   định (`npm run build`, output `dist`).
4. Vào **Settings → Environment Variables**, thêm:
   - `VITE_API_BASE_URL` = đúng domain Railway lấy được ở bước A.6.
5. Deploy — Vercel cấp domain dạng `https://ten-du-an.vercel.app`.

### C. Quay lại Railway, khoá CORS đúng domain thật

Vào lại **Variables** của backend trên Railway, sửa `CORS_ORIGINS`
thành đúng domain Vercel vừa có (bước B.5), có thể liệt kê nhiều domain
cách nhau dấu phẩy nếu Vercel tạo thêm domain preview:

```
CORS_ORIGINS=https://ten-du-an.vercel.app,https://ten-du-an-git-main-xxxx.vercel.app
```

Railway tự động redeploy lại khi đổi biến môi trường.

## Model YOLOv8

File `carton_counter_best.pt` (~21.5MB) cần nằm trong
`warehouse-backend/models/` VÀ được commit vào git bình thường (không
cần Git LFS, dung lượng nhỏ) để Railway build có sẵn model khi deploy —
Railway không đọc được ổ cứng máy bạn, chỉ đọc đúng những gì có trong
repo.

## Cấu trúc

```
src/
  api.js                 API client gọi backend FastAPI
  App.jsx                Router (HashRouter — 3 route: /, /import, /export)
  components/
    CountingScreen.jsx    Màn hình đếm dùng chung (quay video -> upload -> kết quả)
  pages/
    Home.jsx              Trang chủ, chọn Nhập/Xuất
    ImportFlow.jsx         Chọn phiếu -> xem tiến độ từng dòng -> đếm
    ExportFlow.jsx          Chọn sản phẩm + gõ số dự kiến -> đếm
  styles/app.css          Theme tối, đồng bộ giao diện admin desktop
```

## Việc còn thiếu (xem COMMIT_MSG_02_react_pwa.txt mục cuối)

- Chưa test quay video thật (môi trường build không có camera/model).
- Chưa deploy thật (cần tài khoản Vercel/Railway thật của nhóm).
- Chưa có nút "Ghi đè" tường minh khi dòng hàng bị lệch (`needs_review`)
  — hiện tại quay lại đúng dòng đó và bấm "Đếm" lại là được hiểu là đếm
  lại (backend đã hỗ trợ sẵn), nhưng chưa có nút riêng gọi
  `api.resolveSegment(...)` để chọn "Ghi đè, tin theo số camera".
