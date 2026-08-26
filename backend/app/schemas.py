from datetime import datetime, date
from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict


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
class ReceiptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    receipt_code: Optional[str]
    store_location: Optional[str]
    image_path: str
    ocr_confidence: Optional[float]
    status: str
    received_at: Optional[datetime]
    line_items: List[LineItemOut] = []


# ---------- Camera session (nhận từ pipeline YOLOv8 + ByteTrack) ----------
class CameraSessionCreate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    session_code: Optional[str] = None
    camera_id: Optional[str] = None
    linked_receipt_id: Optional[int] = None
    video_path: Optional[str] = None
    counted_quantity: int
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
    expected_quantity: float
    camera_id: Optional[str] = None
    note: Optional[str] = None


class CameraSegmentStopRequest(BaseModel):
    """Nhân viên bấm 'Xong loại này' — gửi kèm số camera đã đếm được."""
    counted_quantity: int
    avg_detection_confidence: Optional[float] = None
    model_version: Optional[str] = None
    video_path: Optional[str] = None
    threshold_pct: float = 0.02


class CameraSegmentStopResult(BaseModel):
    session: CameraSessionOut
    reconciliation: "ReconciliationOut"
    can_proceed_to_next: bool
    message: str
    annotated_video_url: Optional[str] = None  # URL video đã vẽ khung hộp nhận diện, chỉ có khi đếm qua /count-video


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
    counting_status: str  # not_started | counting | matched | blocked | resolved_override
    latest_session_id: Optional[int] = None
    counted_quantity: Optional[int] = None


# ---------- Reconciliation ----------
class ReconciliationRunRequest(BaseModel):
    receipt_id: int
    session_id: int
    threshold_pct: float = 0.02  # 2% sai số cho phép mặc định — chỉnh theo mục 9.3


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


# ---------- Xuất kho ----------
class ExportRequest(BaseModel):
    product_id: int
    quantity: float
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


# ---------- Alerts ----------
class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    alert_type: str
    severity: str
    message: str
    status: str
    created_at: datetime


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
