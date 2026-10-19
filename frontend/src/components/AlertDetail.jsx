import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, API_BASE } from "../api";
import ImageLightbox from "./ImageLightbox";
import { formatDateTimeVN } from "../utils/search";
import "../styles/alerts.css";

const num = (n) => Number(n).toLocaleString("vi-VN");

const RECEIPT_STATUS = {
  pending_ocr: "đang xử lý OCR",
  ocr_done: "chờ đếm hàng",
  reconciled: "đã xong hết",
  flagged: "lỗi OCR — cần xử lý",
};
const SESSION_STATUS = {
  counting: "đang đếm",
  completed: "đã khớp",
  needs_review: "lệch — chờ xử lý",
  resolved_override: "đã ghi đè",
  superseded: "đã được đếm lại",
};
const RECON_STATUS = {
  matched: "khớp",
  flagged: "lệch — chờ xử lý",
  resolved_override: "đã ghi đè theo số camera",
  resolved_manual: "đã xác nhận thủ công",
};

function expiryText(b) {
  if (b.days_to_expiry == null) return "không có HSD";
  if (b.days_to_expiry < 0) return `HSD ${b.expiry_date} — ĐÃ HẾT HẠN ${-b.days_to_expiry} ngày`;
  return `HSD ${b.expiry_date} — còn ${b.days_to_expiry} ngày`;
}

function Row({ label, children }) {
  return (
    <div className="adRow">
      <span className="adRow-label">{label}</span>
      <span className="adRow-value">{children}</span>
    </div>
  );
}

// Phần chi tiết hiện ra khi bấm vào 1 cảnh báo: gom thông tin sản phẩm / lô / phiếu nhập / dòng phiếu /
// đối chiếu / phiên đếm liên quan, mỗi mục có liên kết nhảy sang đúng trang chứa dữ liệu đó.
export default function AlertDetail({ alertId }) {
  const [data, setData] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [showVideo, setShowVideo] = useState(false);
  const [lightbox, setLightbox] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .getAlertDetail(alertId)
      .then((d) => !cancelled && setData(d))
      .catch((err) => !cancelled && setErrorMsg(err.message || String(err)));
    return () => {
      cancelled = true;
    };
  }, [alertId]);

  if (errorMsg) return <div className="adPanel adPanel-error">{errorMsg}</div>;
  if (!data) return <div className="adPanel adPanel-loading">Đang tải chi tiết…</div>;

  const { alert, product, batch, stocked_batches: stocked, reconciliation: recon, session, receipt, line } = data;
  // Cảnh báo chênh lệch còn mở nhưng dòng phiếu đó sau này đã đếm lại và khớp (hoặc đã ghi đè) -> báo cho người dùng biết.
  const alreadyFixed =
    alert.status === "open" &&
    alert.alert_type === "discrepancy" &&
    (data.line_latest_session_status === "completed" || data.line_latest_session_status === "resolved_override");
  const isImport = session?.direction === "import" || (!!receipt && !!line);
  const productLink = product ? `/products?product=${product.id}${batch ? `&batch=${encodeURIComponent(batch.batch_code)}` : ""}` : null;
  const lowOnly = alert.alert_type === "low_stock";
  const hasAnything = product || batch || recon || session || receipt || line;

  return (
    <div className="adPanel" onClick={(e) => e.stopPropagation()}>
      {!hasAnything && (
        <div className="adEmpty">Cảnh báo này không còn liên kết tới dữ liệu gốc (sản phẩm/phiếu đã bị xoá hoặc cảnh báo tạo từ bản cũ).</div>
      )}

      {alreadyFixed && (
        <div className="adNotice">
          ✅ Dòng hàng này sau đó đã được đếm lại và {data.line_latest_session_status === "completed" ? "khớp số" : "xác nhận ghi đè"} — bạn có thể bấm "Đã xử lý" cho cảnh báo này.
        </div>
      )}

      <div className="adGrid">
        {recon && (
          <section className="adCard adCard-recon">
            <h4>⚖️ Đối chiếu số lượng</h4>
            <Row label="Phiếu/khai báo">{num(recon.receipt_total)}</Row>
            <Row label="Camera đếm">{num(recon.camera_total)}</Row>
            <Row label="Chênh lệch">
              <b className={recon.difference === 0 ? "" : "adDanger"}>{recon.difference > 0 ? "+" : ""}{num(recon.difference)}</b>
              {` (ngưỡng cho phép ${(recon.threshold_used * 100).toFixed(1)}%)`}
            </Row>
            <Row label="Trạng thái">{RECON_STATUS[recon.status] || recon.status}</Row>
            {recon.resolved_note && <Row label="Ghi chú xử lý">{recon.resolved_note}</Row>}
            {recon.resolved_at && <Row label="Xử lý lúc">{formatDateTimeVN(recon.resolved_at)}</Row>}
          </section>
        )}

        {product && (
          <section className="adCard">
            <h4>📦 Sản phẩm</h4>
            <Row label="Tên">{product.name}</Row>
            {(product.sku || product.category) && (
              <Row label="Mã / nhóm">{[product.sku, product.category].filter(Boolean).join(" · ")}</Row>
            )}
            <Row label="Tồn kho hiện tại">
              <b className={product.total_stock < product.low_stock_threshold ? "adDanger" : ""}>
                {num(product.total_stock)} {product.unit}
              </b>
              {` (ngưỡng cảnh báo ${num(product.low_stock_threshold)})`}
            </Row>
            <div className="adLinks">
              <Link className="adLink" to={`/products?product=${product.id}`}>
                Xem sản phẩm &amp; các lô →
              </Link>
              {!isImport && (
                <Link className="adLink" to={`/export/history?product=${product.id}`}>
                  Lịch sử xuất của sản phẩm →
                </Link>
              )}
            </div>
          </section>
        )}

        {batch && (
          <section className="adCard">
            <h4>🏷️ Lô hàng</h4>
            <Row label="Mã lô">
              <span className="mono">{batch.batch_code}</span>
            </Row>
            <Row label="Còn trong kho">
              {num(batch.quantity)} {product?.unit || ""}
            </Row>
            <Row label="Hạn sử dụng">{expiryText(batch)}</Row>
            <Row label="Vị trí">{batch.location ? `📍 ${batch.location}` : "chưa gán vị trí"}</Row>
            {productLink && (
              <div className="adLinks">
                <Link className="adLink" to={productLink}>
                  Xem lô này trong kho →
                </Link>
              </div>
            )}
          </section>
        )}

        {receipt && (
          <section className="adCard">
            <h4>🧾 Phiếu nhập</h4>
            <Row label="Mã phiếu">
              <b>{receipt.receipt_code || `#${receipt.id}`}</b>
            </Row>
            {receipt.store_location && <Row label="Nơi nhập">{receipt.store_location}</Row>}
            <Row label="Ngày nhận">{formatDateTimeVN(receipt.received_at) || "chưa có"}</Row>
            <Row label="Trạng thái">{RECEIPT_STATUS[receipt.status] || receipt.status}</Row>
            <Row label="Nguồn">{receipt.source_type === "manual" ? "✍️ Nhập tay" : "📷 Quét ảnh"}</Row>
            <div className="adLinks">
              <Link className="adLink adLink-primary" to={`/import?receipt=${receipt.id}${line ? `&line=${line.id}` : ""}`}>
                {alert.status === "open" && recon?.status === "flagged" ? "Mở phiếu & xử lý dòng lệch →" : "Mở phiếu nhập →"}
              </Link>
              {receipt.image_url && (
                <button type="button" className="adLink" onClick={() => setLightbox(true)}>
                  🖼️ Xem ảnh phiếu
                </button>
              )}
            </div>
            {lightbox && (
              <ImageLightbox
                src={`${API_BASE}${receipt.image_url}`}
                title={receipt.receipt_code || `Phiếu #${receipt.id}`}
                subtitle={formatDateTimeVN(receipt.received_at)}
                onClose={() => setLightbox(false)}
              />
            )}
          </section>
        )}

        {line && (
          <section className="adCard">
            <h4>📋 Dòng hàng trên phiếu</h4>
            <Row label="Dòng số">#{line.line_no}</Row>
            <Row label="Tên trên phiếu">{line.product_name_raw}</Row>
            <Row label="Số lượng khai">{num(line.quantity)}</Row>
            {line.batch_code && (
              <Row label="Mã lô">
                <span className="mono">{line.batch_code}</span>
              </Row>
            )}
            {line.expiry_date && <Row label="HSD ghi trên phiếu">{line.expiry_date}</Row>}
            {line.product_id == null && <Row label="Lưu ý">⚠ Dòng này chưa gán sản phẩm trong danh mục</Row>}
          </section>
        )}

        {session && (
          <section className="adCard">
            <h4>🎥 Phiên đếm camera</h4>
            <Row label="Mã phiên">
              <span className="mono">{session.session_code || `#${session.id}`}</span> · {session.direction === "export" ? "xuất kho" : "nhập kho"}
            </Row>
            <Row label="Trạng thái">{SESSION_STATUS[session.status] || session.status}</Row>
            <Row label="Số đếm / dự kiến">
              {session.counted_quantity ?? "—"} / {session.expected_quantity != null ? num(session.expected_quantity) : "—"}
            </Row>
            {session.avg_detection_confidence != null && (
              <Row label="Độ tin cậy trung bình">{(session.avg_detection_confidence * 100).toFixed(0)}%</Row>
            )}
            {session.ended_at && <Row label="Kết thúc lúc">{formatDateTimeVN(session.ended_at)}</Row>}
            {session.annotated_video_url ? (
              <div className="adLinks">
                <button type="button" className="adLink" onClick={() => setShowVideo((v) => !v)}>
                  {showVideo ? "Ẩn video" : "▶ Xem video đã đếm"}
                </button>
              </div>
            ) : (
              <div className="adHint">Không còn video đã vẽ khung cho phiên này.</div>
            )}
            {showVideo && session.annotated_video_url && (
              <video className="adVideo" src={`${API_BASE}${session.annotated_video_url}`} controls playsInline preload="metadata" />
            )}
          </section>
        )}

        {lowOnly && stocked.length > 0 && (
          <section className="adCard">
            <h4>📚 Các lô còn hàng</h4>
            {stocked.map((b) => (
              <Row key={b.id} label={<span className="mono">{b.batch_code}</span>}>
                {num(b.quantity)} {product?.unit || ""} · {expiryText(b)}
              </Row>
            ))}
          </section>
        )}
        {lowOnly && stocked.length === 0 && product && (
          <section className="adCard">
            <h4>📚 Các lô còn hàng</h4>
            <div className="adHint">Sản phẩm đã hết sạch, không còn lô nào có hàng. Cần nhập thêm.</div>
            <div className="adLinks">
              <Link className="adLink adLink-primary" to="/import">
                Đi tới Nhập kho →
              </Link>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
