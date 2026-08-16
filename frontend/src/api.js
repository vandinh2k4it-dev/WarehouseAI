// API client — gọi thẳng các endpoint ĐÃ CÓ SẴN trên backend FastAPI
// (app/routers/camera.py, receipts.py, products.py) — không tạo endpoint
// mới, PWA này chỉ là giao diện thay thế cho static/mobile.html.

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // ignore — không phải JSON
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json();
}

export const api = {
  health: () => request("/health"),

  listProducts: () => request("/products"),
  listInventory: () => request("/inventory"),
  listAlerts: (status) => request(`/alerts?status=${status ?? "open"}`),
  acknowledgeAlert: async (alertId) => {
    const result = await request(`/alerts/${alertId}/acknowledge`, { method: "POST" });
    // Báo cho TopNav (và bất kỳ ai đang lắng nghe) biết số cảnh báo vừa đổi,
    // để cập nhật lại số đếm trên tab "Cảnh báo" ngay lập tức — 2 component
    // này không có state dùng chung nên dùng sự kiện toàn cục cho đơn giản,
    // không cần thêm thư viện quản lý state chỉ vì 1 con số nhỏ này.
    window.dispatchEvent(new CustomEvent("alerts-changed"));
    return result;
  },

  // Nhập hàng — theo từng dòng trên phiếu
  listReceipts: (status) => request(`/receipts${status ? `?status=${status}` : ""}`),
  getLinesProgress: (receiptId) => request(`/receipts/${receiptId}/lines-progress`),

  // Quét phiếu nhập bằng ảnh chụp từ camera — backend chạy OCR (PaddleOCR +
  // VietOCR) ngay khi nhận ảnh, trả về phiếu đã tạo kèm các dòng hàng đã
  // trích xuất (tự động so khớp với danh mục sản phẩm nếu tên khớp đủ gần).
  uploadReceipt: async (imageFile, storeLocation) => {
    const form = new FormData();
    form.append("file", imageFile);
    const qs = storeLocation ? `?store_location=${encodeURIComponent(storeLocation)}` : "";
    const res = await fetch(`${API_BASE}/receipts/upload${qs}`, { method: "POST", body: form });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        detail = (await res.json()).detail || detail;
      } catch {
        // ignore
      }
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return res.json();
  },

  startImport: (receiptLineItemId) =>
    request("/camera-sessions/start-import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ receipt_line_item_id: receiptLineItemId }),
    }),

  // Xuất hàng — gõ tay số lượng dự kiến, chưa có phiếu xuất trước
  startExport: (productId, expectedQuantity) =>
    request("/camera-sessions/start-export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product_id: productId, expected_quantity: expectedQuantity }),
    }),

  // Quay video xong -> upload thẳng, backend tự đếm (YOLOv8+ByteTrack) rồi
  // tự đối chiếu luôn — chỉ 1 lần gọi, không cần round-trip riêng.
  countVideo: async (sessionId, videoFile, thresholdPct = 0.02) => {
    const form = new FormData();
    form.append("file", videoFile);
    form.append("threshold_pct", String(thresholdPct));
    const res = await fetch(`${API_BASE}/camera-sessions/${sessionId}/count-video`, {
      method: "POST",
      body: form,
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        detail = (await res.json()).detail || detail;
      } catch {
        // ignore
      }
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return res.json();
  },

  // Nhập tay số lượng đã đếm — dùng khi số lượng ít, không cần quay video.
  // Gọi thẳng /stop với số đã đếm, cùng logic đối chiếu như count-video.
  stopManualCount: (sessionId, countedQuantity, thresholdPct = 0.02) =>
    request(`/camera-sessions/${sessionId}/stop`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ counted_quantity: countedQuantity, threshold_pct: thresholdPct }),
    }),

  // Xử lý dòng đang lệch (needs_review) khi quay lại sau
  resolveSegment: (sessionId, action, overrideNote) =>
    request(`/camera-sessions/${sessionId}/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, override_note: overrideNote }),
    }),
};

export { API_BASE };
