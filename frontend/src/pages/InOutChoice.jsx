import { Link } from "react-router-dom";

export default function InOutChoice() {
  return (
    <main className="page-main">
      <div className="card">
        <h2>Nhập / Xuất kho</h2>
        <div className="bigtoggle">
          <Link to="/import" className="bigtoggle-btn">
            ↓ Nhập hàng
          </Link>
          <Link to="/export" className="bigtoggle-btn">
            ↑ Xuất hàng
          </Link>
        </div>
        <p className="hint">
          Chọn <b>Nhập hàng</b> để đếm theo phiếu đã có, hoặc <b>Xuất hàng</b> để đếm hàng
          xuất kho — cả hai đều dùng camera điện thoại quay video, tự động đếm bằng model
          YOLOv8 đã huấn luyện.
        </p>
      </div>
    </main>
  );
}
