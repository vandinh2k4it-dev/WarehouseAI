"""Định nghĩa các "công cụ" (tools) mà Claude được phép gọi để trả lời câu
hỏi của nhân viên kho — mục 6.6 đề cương (chatbot tra cứu tồn kho/phiếu
nhập/cảnh báo). Mỗi tool là 1 hàm Python thuần, chỉ ĐỌC dữ liệu (không có
tool nào sửa/xoá DB) — Claude không có quyền tự ý thay đổi tồn kho, chỉ trả
lời dựa trên dữ liệu thật lấy từ Postgres.

Cách hoạt động (tool-use / function-calling của Claude API):
1. Gửi câu hỏi của người dùng + danh sách TOOLS (khai báo ở cuối file) cho
   Claude.
2. Nếu Claude thấy cần dữ liệu thật để trả lời, nó trả về 1 tool_use block
   (tên hàm + tham số) thay vì trả lời ngay.
3. Backend chạy đúng hàm Python tương ứng trong TOOL_FUNCTIONS, lấy kết quả
   thật từ DB, gửi lại cho Claude dưới dạng tool_result.
4. Claude đọc kết quả đó và viết câu trả lời cuối bằng ngôn ngữ tự nhiên.
Toàn bộ vòng lặp này nằm trong app/chatbot/service.py.
"""
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models


def search_products(db: Session, keyword: str = "", limit: int = 10) -> list[dict]:
    """Tìm sản phẩm theo tên (gần đúng, không phân biệt hoa/thường/dấu đơn giản)."""
    q = db.query(models.Product)
    if keyword:
        q = q.filter(models.Product.name.ilike(f"%{keyword}%"))
    products = q.limit(limit).all()
    return [
        {
            "id": p.id,
            "sku": p.sku,
            "name": p.name,
            "category": p.category,
            "unit": p.unit,
            "low_stock_threshold": float(p.low_stock_threshold or 0),
        }
        for p in products
    ]


def get_inventory_by_product(db: Session, product_name: str) -> list[dict]:
    """Xem tồn kho hiện tại (theo từng lô/HSD) của 1 sản phẩm, tìm theo tên gần đúng."""
    rows = (
        db.query(models.Inventory, models.Product)
        .join(models.Product, models.Inventory.product_id == models.Product.id)
        .filter(models.Product.name.ilike(f"%{product_name}%"))
        .order_by(models.Inventory.expiry_date.asc().nulls_last())
        .all()
    )
    return [
        {
            "product_name": prod.name,
            "batch_code": inv.batch_code,
            "quantity": float(inv.quantity),
            "unit": prod.unit,
            "expiry_date": inv.expiry_date.isoformat() if inv.expiry_date else None,
            "last_updated": inv.last_updated.isoformat() if inv.last_updated else None,
        }
        for inv, prod in rows
    ]


def get_total_stock(db: Session, product_name: str) -> dict:
    """Tổng tồn kho (cộng dồn mọi lô) của 1 sản phẩm — trả lời nhanh câu
    kiểu 'còn bao nhiêu thùng X trong kho'."""
    rows = (
        db.query(models.Product.name, models.Product.unit, func.sum(models.Inventory.quantity))
        .join(models.Inventory, models.Inventory.product_id == models.Product.id)
        .filter(models.Product.name.ilike(f"%{product_name}%"))
        .group_by(models.Product.id, models.Product.name, models.Product.unit)
        .all()
    )
    if not rows:
        return {"found": False, "message": f"Không tìm thấy sản phẩm khớp '{product_name}' trong kho."}
    name, unit, total = rows[0]
    return {"found": True, "product_name": name, "total_quantity": float(total or 0), "unit": unit}


def get_low_stock_products(db: Session) -> list[dict]:
    """Danh sách sản phẩm có tổng tồn kho dưới ngưỡng cảnh báo (low_stock_threshold)."""
    rows = (
        db.query(models.Product.name, models.Product.unit, models.Product.low_stock_threshold, func.coalesce(func.sum(models.Inventory.quantity), 0))
        .outerjoin(models.Inventory, models.Inventory.product_id == models.Product.id)
        .group_by(models.Product.id, models.Product.name, models.Product.unit, models.Product.low_stock_threshold)
        .having(func.coalesce(func.sum(models.Inventory.quantity), 0) < models.Product.low_stock_threshold)
        .all()
    )
    return [
        {"product_name": name, "total_quantity": float(total), "threshold": float(threshold or 0), "unit": unit}
        for name, unit, threshold, total in rows
    ]


def get_expiring_soon(db: Session, days: int = 30) -> list[dict]:
    """Các lô hàng sắp hết hạn trong N ngày tới (mặc định 30 ngày) — phục vụ
    FEFO, cảnh báo hàng cận date."""
    cutoff = date.today() + timedelta(days=days)
    rows = (
        db.query(models.Inventory, models.Product)
        .join(models.Product, models.Inventory.product_id == models.Product.id)
        .filter(models.Inventory.expiry_date.isnot(None))
        .filter(models.Inventory.expiry_date <= cutoff)
        .filter(models.Inventory.quantity > 0)
        .order_by(models.Inventory.expiry_date.asc())
        .all()
    )
    return [
        {
            "product_name": prod.name,
            "batch_code": inv.batch_code,
            "quantity": float(inv.quantity),
            "unit": prod.unit,
            "expiry_date": inv.expiry_date.isoformat(),
            "days_left": (inv.expiry_date - date.today()).days,
        }
        for inv, prod in rows
    ]


def get_open_alerts(db: Session, alert_type: str | None = None) -> list[dict]:
    """Danh sách cảnh báo đang mở (chưa xử lý) — low_stock / expiring_soon / discrepancy.
    alert_type=None nghĩa là lấy tất cả loại."""
    q = db.query(models.Alert).filter(models.Alert.status == "open")
    if alert_type:
        q = q.filter(models.Alert.alert_type == alert_type)
    alerts = q.order_by(models.Alert.created_at.desc()).limit(20).all()
    return [
        {
            "id": a.id,
            "type": a.alert_type,
            "severity": a.severity,
            "message": a.message,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in alerts
    ]


def get_receipt_status(db: Session, receipt_id: int | None = None, receipt_code: str | None = None) -> dict:
    """Xem trạng thái + chi tiết 1 phiếu nhập hàng, theo id hoặc mã phiếu."""
    q = db.query(models.ImportReceipt)
    if receipt_id is not None:
        q = q.filter(models.ImportReceipt.id == receipt_id)
    elif receipt_code:
        q = q.filter(models.ImportReceipt.receipt_code == receipt_code)
    else:
        return {"found": False, "message": "Cần cung cấp receipt_id hoặc receipt_code."}

    receipt = q.first()
    if not receipt:
        return {"found": False, "message": "Không tìm thấy phiếu nhập này."}

    return {
        "found": True,
        "id": receipt.id,
        "receipt_code": receipt.receipt_code,
        "store_location": receipt.store_location,
        "status": receipt.status,
        "ocr_confidence": float(receipt.ocr_confidence) if receipt.ocr_confidence else None,
        "received_at": receipt.received_at.isoformat() if receipt.received_at else None,
        "line_items": [
            {
                "product_name_raw": li.product_name_raw,
                "quantity": float(li.quantity),
                "batch_code": li.batch_code,
                "expiry_date": li.expiry_date.isoformat() if li.expiry_date else None,
            }
            for li in receipt.line_items
        ],
    }


def get_recent_discrepancies(db: Session, limit: int = 10) -> list[dict]:
    """Các lần đối chiếu camera-phiếu nhập bị lệch (flagged), gần đây nhất."""
    rows = (
        db.query(models.Reconciliation)
        .filter(models.Reconciliation.status != "matched")
        .order_by(models.Reconciliation.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "receipt_id": r.receipt_id,
            "receipt_total": float(r.receipt_total),
            "camera_total": r.camera_total,
            "difference": float(r.difference),
            "status": r.status,
            "resolved_note": r.resolved_note,
        }
        for r in rows
    ]


# ----------------------------------------------------------------------
# Khai báo tool schema cho Claude API (định dạng chuẩn của Anthropic tool-use)
# Xem: https://docs.claude.com/en/docs/build-with-claude/tool-use
# ----------------------------------------------------------------------
TOOLS = [
    {
        "name": "search_products",
        "description": "Tìm sản phẩm trong danh mục theo tên gần đúng (không cần gõ chính xác dấu).",
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Từ khoá tên sản phẩm cần tìm"},
                "limit": {"type": "integer", "description": "Số kết quả tối đa, mặc định 10"},
            },
        },
    },
    {
        "name": "get_inventory_by_product",
        "description": "Xem tồn kho chi tiết theo từng lô (mã lô, số lượng, HSD) của 1 sản phẩm.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_name": {"type": "string", "description": "Tên sản phẩm cần tra (gần đúng)"},
            },
            "required": ["product_name"],
        },
    },
    {
        "name": "get_total_stock",
        "description": "Tổng số lượng tồn kho (cộng dồn mọi lô) của 1 sản phẩm — dùng khi người dùng hỏi 'còn bao nhiêu X'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_name": {"type": "string", "description": "Tên sản phẩm cần tra"},
            },
            "required": ["product_name"],
        },
    },
    {
        "name": "get_low_stock_products",
        "description": "Danh sách sản phẩm đang tồn kho thấp hơn ngưỡng cảnh báo, cần nhập thêm.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_expiring_soon",
        "description": "Danh sách lô hàng sắp hết hạn trong N ngày tới (mặc định 30 ngày).",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Số ngày tới cần kiểm tra, mặc định 30"},
            },
        },
    },
    {
        "name": "get_open_alerts",
        "description": "Danh sách cảnh báo đang mở, có thể lọc theo loại: low_stock, expiring_soon, discrepancy.",
        "input_schema": {
            "type": "object",
            "properties": {
                "alert_type": {"type": "string", "description": "Loại cảnh báo cần lọc, để trống nếu muốn xem tất cả"},
            },
        },
    },
    {
        "name": "get_receipt_status",
        "description": "Xem trạng thái và chi tiết dòng hàng của 1 phiếu nhập, theo ID hoặc mã phiếu.",
        "input_schema": {
            "type": "object",
            "properties": {
                "receipt_id": {"type": "integer", "description": "ID phiếu nhập"},
                "receipt_code": {"type": "string", "description": "Mã phiếu nhập (nếu không có ID)"},
            },
        },
    },
    {
        "name": "get_recent_discrepancies",
        "description": "Các lần đối chiếu camera-phiếu nhập bị lệch số lượng gần đây, chưa khớp.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Số kết quả tối đa, mặc định 10"},
            },
        },
    },
]

TOOL_FUNCTIONS: dict[str, Any] = {
    "search_products": search_products,
    "get_inventory_by_product": get_inventory_by_product,
    "get_total_stock": get_total_stock,
    "get_low_stock_products": get_low_stock_products,
    "get_expiring_soon": get_expiring_soon,
    "get_open_alerts": get_open_alerts,
    "get_receipt_status": get_receipt_status,
    "get_recent_discrepancies": get_recent_discrepancies,
}
