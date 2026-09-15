# Hướng dẫn chuyển deploy backend từ Railway sang Google Cloud Run

> **Bản cập nhật:** Kế hoạch ban đầu dùng Hugging Face Spaces, nhưng đầu
> tháng 7/2026 HF đã đổi chính sách — Docker SDK (và Gradio) giờ **bắt
> buộc phải có gói PRO trả phí** mới tạo Space được, chỉ còn "Static"
> (web tĩnh, không chạy được FastAPI) là free thật. File này thay thế
> hoàn toàn hướng dẫn HF Spaces trước đó.

## 1. Vì sao chọn Cloud Run

- **Free tier Cloud Run là "Always Free" thật** (không phải trial có hạn
  ngày), gồm: 2 triệu request/tháng, 360.000 GiB-giây bộ nhớ, 180.000
  vCPU-giây mỗi tháng — dùng chung cho toàn bộ Cloud Run trong 1 tài
  khoản billing. Với traffic thấp của 1 backend khóa luận (chủ yếu Em
  và hội đồng test), gần như chắc chắn không vượt quota này.
- Cloud Run tự **"ngủ" về 0 instance** khi không có traffic (giống ý
  tưởng Sleep của HF/Render) — nghĩa là không tốn phí lúc rảnh, nhưng
  cũng có cold start giống các bản trước.
- Chạy Docker container x86_64 bình thường — **tái sử dụng gần như toàn
  bộ Dockerfile đã viết**, chỉ cần đổi 1 chỗ (cổng lắng nghe).
- **Lưu ý quan trọng:** cần thẻ Visa/Mastercard để tạo tài khoản Google
  Cloud (bắt buộc, dù không bị trừ tiền nếu ở trong free tier) — nếu
  vượt quota free mới bị tính phí. Để an toàn, đặt **Budget Alert** ở
  bước 3 bên dưới.

## 2. File thay đổi trong backend

So với bản gửi trước (viết cho HF Spaces), chỉ **Dockerfile** đổi:

| File | Thay đổi |
|---|---|
| `Dockerfile` | Đổi cổng lắng nghe từ cố định `7860` (HF) sang biến môi trường `$PORT` mà Cloud Run tự tiêm vào lúc chạy (mặc định `8080`). Bỏ yêu cầu bắt buộc user non-root của HF (Cloud Run không đòi hỏi, nhưng vẫn giữ lại theo thông lệ tốt). |
| `.dockerignore` | Giữ nguyên, không đổi. |
| `README.md` | Gỡ khối YAML frontmatter dành riêng cho HF Spaces (Cloud Run không đọc file này để cấu hình). |

Đặt cả 3 file vào đúng thư mục gốc backend, đè lên bản cũ đã gửi trước
đó (ngang hàng `Procfile`, `requirements.txt`).

## 3. Cài đặt Google Cloud CLI & tạo project

1. Cài `gcloud` CLI theo hướng dẫn tại
   [cloud.google.com/sdk/docs/install](https://cloud.google.com/sdk/docs/install).
2. Đăng nhập: `gcloud auth login`
3. Tạo project mới (hoặc dùng project có sẵn):
   ```bash
   gcloud projects create warehouse-ai-thesis --name="Warehouse AI"
   gcloud config set project warehouse-ai-thesis
   ```
4. Liên kết billing account (bắt buộc phải có thẻ, xem lưu ý ở mục 1):
   vào [console.cloud.google.com/billing](https://console.cloud.google.com/billing)
   → tạo billing account → link vào project vừa tạo.
5. **Đặt Budget Alert để an toàn:** vào **Billing → Budgets & alerts →
   Create budget**, đặt ngưỡng nhỏ (vd 50.000đ / ~2 USD) để nếu lỡ vượt
   free tier, Em nhận email cảnh báo ngay thay vì bị bất ngờ cuối tháng.
6. Bật các API cần thiết:
   ```bash
   gcloud services enable run.googleapis.com \
       artifactregistry.googleapis.com \
       cloudbuild.googleapis.com
   ```

## 4. Deploy backend lên Cloud Run

Trong thư mục gốc backend (đã có Dockerfile mới ở bước 2), chạy:

```bash
gcloud run deploy warehouse-ai-backend \
    --source . \
    --region asia-southeast1 \
    --allow-unauthenticated \
    --memory 4Gi \
    --cpu 2 \
    --timeout 300 \
    --set-env-vars DATABASE_URL="postgresql+psycopg2://...(chuỗi Neon)...",GEMINI_API_KEY="...",VAPID_PRIVATE_KEY="...",VAPID_PUBLIC_KEY="...",VAPID_CLAIM_EMAIL="...",CORS_ORIGINS="https://<domain-vercel-thật>"
```

Giải thích các cờ quan trọng:
- `--region asia-southeast1`: Singapore, gần Việt Nam nhất, giảm độ trễ.
- `--memory 4Gi`: đủ rộng rãi cho torch + paddlepaddle + vietocr chạy
  cùng lúc (có thể tăng lên `8Gi` nếu log báo lỗi hết bộ nhớ lúc test).
- `--cpu 2`: 2 vCPU, giúp OCR chạy nhanh hơn 1 vCPU mặc định.
- `--timeout 300`: cho phép 1 request chạy tối đa 5 phút (OCR/xử lý
  video có thể lâu hơn mức mặc định 60 giây của Cloud Run).
- `--allow-unauthenticated`: cho phép frontend gọi API công khai (không
  cần xác thực IAM) — đúng với thiết kế hiện tại không có user login.
- `--set-env-vars`: khai báo trực tiếp biến môi trường. **Cách này đơn
  giản nhất cho deadline gấp**, nhưng giá trị sẽ hiện trong Cloud Console
  (không hiện trong code/git). Nếu muốn bảo mật hơn, có thể dùng Secret
  Manager (`--set-secrets` thay vì `--set-env-vars`) — có thể làm sau
  khi bảo vệ xong, không cấp thiết ngay bây giờ.

Lần đầu chạy lệnh này, `gcloud` sẽ tự động dùng Cloud Build để build
Dockerfile thành image rồi đẩy lên Artifact Registry — Em không cần tự
build tay. Quá trình này có thể mất 5-10 phút do cài `torch` +
`paddlepaddle`.

## 5. Kiểm tra sau khi deploy

Lệnh deploy xong sẽ in ra 1 **Service URL** dạng:
```
https://warehouse-ai-backend-xxxxxxxxxx.asia-southeast1.run.app
```

1. Xem log để xác nhận lifespan chạy đúng (giống HF trước đó): vào
   [console.cloud.google.com/run](https://console.cloud.google.com/run)
   → chọn service → tab **Logs**. Xác nhận thấy dòng khởi động server
   ngay lập tức, sau đó vài chục giây tới 1-2 phút mới thấy dòng
   `✅ [nền] Đã tải xong model OCR`.
2. Test thử endpoint sức khỏe hoặc Swagger UI:
   `https://<service-url>/docs`

## 6. Cập nhật frontend trên Vercel

1. Vào Vercel project frontend → **Settings** → **Environment
   Variables**.
2. Sửa `VITE_API_URL` sang Service URL Cloud Run ở bước 5.
3. Redeploy frontend, test lại luồng quét phiếu nhập **mới** để chắc
   chắn OCR + DB hoạt động đúng qua backend mới.

## 7. Lưu ý quan trọng trước khi bảo vệ khóa luận

- **Ổ đĩa Cloud Run tạm thời và dễ mất hơn cả HF Space**: không chỉ mất
  khi deploy lại, mà bất kỳ lúc nào Cloud Run "dọn dẹp" instance rảnh
  (idle) cũng có thể tạo instance mới sạch trơn. **Không lưu file quan
  trọng vào ổ đĩa container** (Postgres trên Neon vẫn an toàn vì tách
  riêng, chỉ ảnh của `uploads/receipts` lưu local là dễ mất bất cứ lúc
  nào — nếu cần giữ ảnh phiếu nhập demo, cân nhắc thêm bước upload ảnh
  đó lên Cloud Storage hoặc Neon dạng base64/blob nếu còn thời gian).
- **Cold start:** request đầu tiên sau khi Cloud Run "ngủ" sẽ chậm (vài
  chục giây tới hơn 1 phút, vì phải khởi động container + tải model OCR
  ở nền). **Trước buổi bảo vệ, mở thử trang web ít nhất 5-10 phút trước**
  để "đánh thức" service, y hệt lưu ý đã đưa ra với HF Space trước đó.
- Theo dõi **Billing → Reports** vài ngày sau khi deploy để chắc chắn
  usage vẫn nằm trong free tier, đặc biệt nếu hội đồng/nhiều người cùng
  test song song trong buổi bảo vệ.
