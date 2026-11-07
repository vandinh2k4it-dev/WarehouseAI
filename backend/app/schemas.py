from datetime import datetime, date
from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict, Field, computed_field


# ---------- Product ----------
class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sku: Optional[str]
    name: str
    category: Optional[str]
    unit: str
    low_stock_threshold: float


# ---------- Receipt line item ----------
class LineItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    line_no: int
    product_name_raw: str
    product_id: Optional[int]
    quantity: float
    batch_code: Optional[str]
    expiry_date: Optional[date]
    match_score: Optional[float]


# ---------- Receipt ----------
class ReceiptDateCheck(BaseModel):
    import_date: Optional[date]  # ngày nhập đem ra so
    today: date  # ngày hôm nay theo giờ Việt Nam
    source: str  # "phiếu" (đọc/gõ từ phiếu) | "hệ thống" (lùi về received_at) | "không có"
    days_diff: Optional[int]  # hôm nay - ngày nhập; 0 là khớp
    matches: bool
    message: str


class ReceiptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    receipt_code: Optional[str]
    store_location: Optional[str]
    image_path: Optional[str] = None
    ocr_confidence: Optional[float]
    status: str
    source_type: str = "ocr"
    received_at: Optional[datetime]
    receipt_date: Optional[date] = None  # ngày nhập ghi trên phiếu
    line_items: List[LineItemOut] = []

    @computed_field
    @property
    def date_check(self) -> "ReceiptDateCheck":
        """So ngày nhập trên phiếu với hôm nay — tính lại MỖI LẦN trả về,
        nên mở lại phiếu hôm sau sẽ thấy cảnh báo phiếu đã cũ."""
        from app.receipt_dates import check_receipt_date
        return ReceiptDateCheck(**check_receipt_date(self))

    @computed_field
    @property
    def image_url(self) -> Optional[str]:
        """URL công khai để xem lại ảnh gốc phiếu nhập đã quét — tính từ
        image_path (đường dẫn file thật trên server, không public được trực
        tiếp) sang URL qua /media/receipts/ đã mount ở app/main.py. Chỉ lấy
        đúng TÊN FILE (bỏ hết phần thư mục), dùng cả 2 kiểu dấu / và \\ để
        an toàn nếu path được lưu trên Windows lúc chạy local. Trả None nếu
        phiếu không có ảnh (tạo bằng tay, không quét OCR)."""
        if not self.image_path:
            return None
        filename = self.image_path.replace("\\", "/").rsplit("/", 1)[-1]
        return f"/media/receipts/{filename}"


# ---------- Tạo / sửa phiếu nhập BẰNG TAY (không qua OCR) ----------
class ReceiptLineItemManualCreate(BaseModel):
    product_name_raw: str
    product_id: Optional[int] = None  # để trống nếu chưa có trong danh mục — vẫn tạo được dòng, gán sau ở /products/unmapped-lines
    quantity: float = Field(gt=0)  # số lượng phải dương
    batch_code: Optional[str] = None
    expiry_date: Optional[date] = None


class ReceiptManualCreate(BaseModel):
    receipt_code: Optional[str] = None
    store_location: Optional[str] = None
    received_at: Optional[datetime] = None
    receipt_date: Optional[date] = None  # ngày nhập ghi trên phiếu giấy
    line_items: List[ReceiptLineItemManualCreate]


class ReceiptUpdateRequest(BaseModel):
    """Sửa thông tin CHUNG của phiếu — KHÔNG sửa dòng hàng ở đây (xem riêng
    ReceiptLineItemUpdateRequest), vì sửa dòng hàng cần kiểm tra an toàn
    theo từng dòng (dòng đã đếm rồi thì không cho sửa số lượng nữa)."""
    receipt_code: Optional[str] = None
    store_location: Optional[str] = None
    received_at: Optional[datetime] = None
    receipt_date: Optional[date] = None  # sửa lại nếu OCR đọc sai ngày trên phiếu


class ReceiptLineItemCreateRequest(BaseModel):
    """Thêm 1 dòng hàng MỚI vào phiếu đã có sẵn — luôn an toàn vì là dòng
    hoàn toàn mới, không đụng tới dữ liệu tồn kho/đếm nào đã có."""
    product_name_raw: str
    product_id: Optional[int] = None
    quantity: float = Field(gt=0)
    batch_code: Optional[str] = None
    expiry_date: Optional[date] = None


class ReceiptLineItemUpdateRequest(BaseModel):
    """Sửa 1 dòng hàng đã có — CHỈ cho phép nếu dòng đó CHƯA từng được đếm
    (chưa có CameraCountSession nào) — xem kiểm tra an toàn trong
    app/routers/receipts.py, tránh sửa số lượng sau khi tồn kho đã được
    cộng dựa trên số cũ, gây sai lệch dữ liệu âm thầm."""
    product_name_raw: Optional[str] = None
    product_id: Optional[int] = None
    quantity: Optional[float] = Field(None, gt=0)
    batch_code: Optional[str] = None
    expiry_date: Optional[date] = None


# ---------- Camera session (nhận từ pipeline YOLOv8 + ByteTrack) ----------
class CameraSessionCreate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    session_code: Optional[str] = None
    camera_id: Optional[str] = None
    linked_receipt_id: Optional[int] = None
    video_path: Optional[str] = None
    counted_quantity: int = Field(ge=0)
    avg_detection_confidence: Optional[float] = None
    model_version: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


class CameraSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())
    id: int
    session_code: Optional[str] = None
    camera_id: Optional[str] = None
    linked_receipt_id: Optional[int] = None
    video_path: Optional[str] = None
    counted_quantity: Optional[int] = None
    avg_detection_confidence: Optional[float] = None
    model_version: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    direction: str
    receipt_line_item_id: Optional[int] = None
    product_id: Optional[int] = None
    expected_quantity: Optional[float] = None
    status: str


# ---------- Đếm theo từng loại hàng (quy trình mới) ----------
class CameraSegmentStartImport(BaseModel):
    """Bắt đầu đếm cho 1 DÒNG HÀNG cụ thể trên phiếu nhập — nhân viên chọn
    đúng loại hàng đang đi qua băng chuyền trước khi bấm bắt đầu."""
    receipt_line_item_id: int
    camera_id: Optional[str] = None


class CameraSegmentStartExport(BaseModel):
    """Bắt đầu đếm khi xuất hàng — chưa có phiếu xuất trước, nhân viên gõ
    tay số lượng dự kiến xuất ngay lúc này để camera đối chiếu."""
    product_id: int
    expected_quantity: float = Field(gt=0)
    camera_id: Optional[str] = None
    note: Optional[str] = None


class CameraSegmentStopRequest(BaseModel):
    """Nhân viên bấm 'Xong loại này' — gửi kèm số camera đã đếm được."""
    counted_quantity: int = Field(ge=0)
    avg_detection_confidence: Optional[float] = None
    model_version: Optional[str] = None
    video_path: Optional[str] = None
    threshold_pct: float = 0.0  # theo yêu cầu: KHÔNG cho phép sai số nào, dù nhỏ nhất


class CameraSegmentStopResult(BaseModel):
    session: CameraSessionOut
    reconciliation: "ReconciliationOut"
    can_proceed_to_next: bool
    message: str
    annotated_video_url: Optional[str] = None  # URL video đã vẽ khung hộp nhận diện, chỉ có khi đếm qua /count-video
    # Thời gian chạy — chỉ có khi đếm qua /count-video
    inference_seconds: Optional[float] = None  # riêng mô hình YOLOv8+ByteTrack đếm
    processing_seconds: Optional[float] = None  # toàn bộ xử lý trên server (đếm + chuyển đổi video + đối chiếu)
    total_frames: Optional[int] = None  # số khung hình mô hình đã xử lý
    date_check: Optional["ReceiptDateCheck"] = None  # so ngày nhập trên phiếu với hôm nay, chỉ có ở phiên nhập


class CameraSegmentResolveRequest(BaseModel):
    """Nhân viên quay lại xử lý 1 dòng đang 'needs_review' (lệch số, đã skip qua trước đó)."""
    action: str  # 'recount' | 'override'
    resolved_by: Optional[str] = None
    override_note: Optional[str] = None  # BẮT BUỘC nếu action='override'


class ReceiptLineProgressOut(BaseModel):
    """Tiến độ đếm của 1 dòng hàng trên phiếu — phục vụ UI hiển thị checklist
    'đã xong / đang đếm / bị chặn / chưa bắt đầu' theo từng loại hàng."""
    line_id: int
    product_name_raw: str
    product_id: Optional[int]
    declared_quantity: float
    batch_code: Optional[str] = None
    expiry_date: Optional[date] = None
    counting_status: str  # not_started | counting | matched | blocked | resolved_override
    latest_session_id: Optional[int] = None
    counted_quantity: Optional[int] = None


# ---------- Reconciliation ----------
class ReconciliationRunRequest(BaseModel):
    receipt_id: int
    session_id: int
    threshold_pct: float = 0.0  # theo yêu cầu: KHÔNG cho phép sai số nào, dù nhỏ nhất


class ReconciliationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    receipt_id: Optional[int] = None
    receipt_line_item_id: Optional[int] = None
    product_id: Optional[int] = None
    session_id: int
    receipt_total: float
    camera_total: int
    difference: float
    threshold_used: float
    status: str
    resolved_by: Optional[str]
    resolved_note: Optional[str]


class ReconciliationResolveRequest(BaseModel):
    resolved_by: str
    resolved_note: Optional[str] = None
    accept_camera_total: bool = True  # True: lấy camera_total làm số liệu chính thức


# ---------- Inventory ----------
class InventoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    batch_code: str
    quantity: float
    expiry_date: Optional[date]
    last_updated: datetime
    location: Optional[str] = None


class InventoryLocationUpdate(BaseModel):
    location: Optional[str] = None  # để trống ("" hoặc null) = xoá vị trí đã gán


# ---------- Xuất kho ----------
class ExportRequest(BaseModel):
    product_id: int
    quantity: float = Field(gt=0)
    batch_code: Optional[str] = None  # chỉ định đúng lô; bỏ trống -> tự động FEFO (hết hạn sớm nhất trước)
    note: Optional[str] = None


class ExportBatchDetail(BaseModel):
    batch_code: str
    quantity_deducted: float
    remaining_in_batch: float


class ExportResult(BaseModel):
    product_id: int
    total_exported: float
    details: list[ExportBatchDetail]


# ---------- Lịch sử xuất kho (đọc lại từ InventoryTransaction đã có sẵn —
# không cần bảng mới, mỗi lần xuất kho đã tự ghi log qua perform_fefo_export) ----------
class ExportHistoryItem(BaseModel):
    id: int  # id của InventoryTransaction
    product_id: int
    product_name: str
    unit: str
    batch_code: str
    quantity: float  # số dương (đã đổi dấu từ change_qty âm lưu trong DB cho dễ đọc)
    reference_type: Optional[str] = None  # 'manual' (gõ tay qua form) | 'camera_session' (qua đếm camera)
    reference_id: Optional[int] = None
    note: Optional[str] = None
    created_at: datetime


# ---------- Dashboard báo cáo/phân tích (đọc lại InventoryTransaction có
# sẵn, KHÔNG thêm bảng mới) ----------
class DailyFlowPoint(BaseModel):
    date: str  # "YYYY-MM-DD"
    imported: float
    exported: float


class TopProductMovement(BaseModel):
    product_id: int
    name: str
    sku: Optional[str] = None
    unit: str
    imported_total: float
    exported_total: float
    net_change: float  # imported_total - exported_total, có thể âm


class AnalyticsKpis(BaseModel):
    open_alerts: int
    low_stock_products: int
    expiring_soon_batches: int
    total_transactions: int  # tổng số phiếu giao dịch trong khoảng ngày đang xem


class AnalyticsOut(BaseModel):
    days: int
    daily_flow: List[DailyFlowPoint]
    top_products: List[TopProductMovement]
    kpis: AnalyticsKpis


# ---------- Alerts ----------
class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    alert_type: str
    severity: str
    message: str
    status: str
    created_at: datetime
    # Liên kết tới dữ liệu gốc (để giao diện bấm vào là mở đúng sản phẩm/phiếu/lô).
    # Chỉ GET /alerts điền các trường này; mặc định None nên không ảnh hưởng nơi khác.
    inventory_id: Optional[int] = None
    reconciliation_id: Optional[int] = None
    product_id: Optional[int] = None
    product_name: Optional[str] = None
    batch_code: Optional[str] = None
    receipt_id: Optional[int] = None
    receipt_code: Optional[str] = None
    receipt_line_id: Optional[int] = None
    session_id: Optional[int] = None


class AlertProductInfo(BaseModel):
    id: int
    name: str
    sku: Optional[str] = None
    category: Optional[str] = None
    unit: str
    low_stock_threshold: float
    total_stock: float


class AlertBatchInfo(BaseModel):
    id: int
    batch_code: str
    quantity: float
    expiry_date: Optional[date] = None
    days_to_expiry: Optional[int] = None  # âm = đã hết hạn
    location: Optional[str] = None


class AlertReconciliationInfo(BaseModel):
    id: int
    status: str
    receipt_total: float
    camera_total: int
    difference: float
    threshold_used: float
    resolved_by: Optional[str] = None
    resolved_note: Optional[str] = None
    resolved_at: Optional[datetime] = None


class AlertSessionInfo(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    id: int
    session_code: Optional[str] = None
    direction: str
    status: str
    expected_quantity: Optional[float] = None
    counted_quantity: Optional[int] = None
    avg_detection_confidence: Optional[float] = None
    model_version: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    annotated_video_url: Optional[str] = None  # chỉ có nếu file video đã vẽ khung còn trên đĩa


class AlertReceiptInfo(BaseModel):
    id: int
    receipt_code: Optional[str] = None
    store_location: Optional[str] = None
    status: str
    source_type: str
    received_at: Optional[datetime] = None
    image_url: Optional[str] = None


class AlertLineInfo(BaseModel):
    id: int
    line_no: int
    product_name_raw: str
    quantity: float
    batch_code: Optional[str] = None
    expiry_date: Optional[date] = None
    product_id: Optional[int] = None


class AlertDetailOut(BaseModel):
    """Toàn bộ ngữ cảnh của 1 cảnh báo: sản phẩm, lô, phiếu nhập, dòng phiếu, đối chiếu,
    phiên đếm — thứ nào không liên quan tới loại cảnh báo này thì là None."""
    alert: AlertOut
    product: Optional[AlertProductInfo] = None
    batch: Optional[AlertBatchInfo] = None
    stocked_batches: List[AlertBatchInfo] = []  # các lô còn hàng của sản phẩm (nhiều nhất 8)
    reconciliation: Optional[AlertReconciliationInfo] = None
    session: Optional[AlertSessionInfo] = None
    receipt: Optional[AlertReceiptInfo] = None
    line: Optional[AlertLineInfo] = None
    # Trạng thái phiên đếm MỚI NHẤT của dòng phiếu (chỉ cảnh báo chênh lệch nhập): nếu dòng đã đếm lại
    # và khớp thì cảnh báo cũ này thực chất đã được xử lý.
    line_latest_session_status: Optional[str] = None


# ---------- Chatbot (mục 6.6) ----------
class ChatbotAsk(BaseModel):
    message: str
    # Lịch sử hội thoại trước đó (client tự giữ và gửi lại) — để chatbot nhớ
    # ngữ cảnh câu hỏi trước trong cùng phiên chat, không cần lưu session
    # phía server cho bản demo khóa luận.
    history: Optional[List[dict]] = None


class ChatbotToolCall(BaseModel):
    tool: str
    input: dict
    output: Any


class ChatbotAnswer(BaseModel):
    reply: str
    tool_calls: List[ChatbotToolCall]
    # Trả nguyên lịch sử (đã gồm câu hỏi + câu trả lời vừa rồi) để client lưu
    # lại, gửi kèm ở lượt hỏi tiếp theo -> chatbot có trí nhớ hội thoại.
    history: List[dict]