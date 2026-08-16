import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { api } from "../api";

export default function Home() {
  const [connStatus, setConnStatus] = useState("checking"); // checking | ok | bad

  useEffect(() => {
    api
      .health()
      .then(() => setConnStatus("ok"))
      .catch(() => setConnStatus("bad"));
  }, []);

  return (
    <div className="page">
      <header className="page-header">
        <h1>📦 Đếm hàng — Điện thoại</h1>
        <div className="conn">
          <span className={`dot ${connStatus === "ok" ? "ok" : connStatus === "bad" ? "bad" : ""}`} />
          <span>
            {connStatus === "checking" && "Đang kết nối…"}
            {connStatus === "ok" && "Đã kết nối tới backend"}
            {connStatus === "bad" && "Không kết nối được API"}
          </span>
        </div>
      </header>

      <main className="page-main">
        <div className="bigtoggle">
          <Link to="/import" className="bigtoggle-btn">
            ⬇ Nhập hàng
          </Link>
          <Link to="/export" className="bigtoggle-btn">
            ⬆ Xuất hàng
          </Link>
        </div>
        <p className="hint">
          Chọn <b>Nhập hàng</b> để đếm theo phiếu đã có, hoặc <b>Xuất hàng</b> để đếm
          hàng xuất kho — cả hai đều dùng camera điện thoại quay video, tự động đếm
          bằng model YOLOv8 đã huấn luyện.
        </p>
      </main>
    </div>
  );
}
