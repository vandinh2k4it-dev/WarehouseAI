import { NavLink, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { api } from "../api";

const TABS = [
  { to: "/", label: "Tổng quan", match: (p) => p === "/" },
  { to: "/products", label: "Sản phẩm", match: (p) => p.startsWith("/products") },
  { to: "/inout", label: "Nhập / Xuất kho", match: (p) => ["/inout", "/import", "/export"].some((x) => p.startsWith(x)) },
  { to: "/alerts", label: "Cảnh báo", match: (p) => p.startsWith("/alerts") },
];

export default function TopNav() {
  const location = useLocation();
  const [connStatus, setConnStatus] = useState("checking");
  const [openAlertCount, setOpenAlertCount] = useState(null);

  useEffect(() => {
    api
      .health()
      .then(() => setConnStatus("ok"))
      .catch(() => setConnStatus("bad"));
    loadAlertCount();

    // Cập nhật lại số đếm ngay khi có nơi khác vừa xử lý xong 1 cảnh báo
    // (xem ghi chú trong api.js — acknowledgeAlert phát sự kiện này).
    window.addEventListener("alerts-changed", loadAlertCount);
    return () => window.removeEventListener("alerts-changed", loadAlertCount);
  }, []);

  function loadAlertCount() {
    api
      .listAlerts("open")
      .then((data) => setOpenAlertCount(data.length))
      .catch(() => {});
  }

  return (
    <header className="topnav">
      <div className="topnav-top">
        <div className="topnav-title">
          <span className="topnav-logo">📦</span>
          <div>
            <div className="topnav-h1">Kho thông minh</div>
            <div className="conn">
              <span className={`dot ${connStatus === "ok" ? "ok" : connStatus === "bad" ? "bad" : ""}`} />
              <span>
                {connStatus === "checking" && "Đang kết nối…"}
                {connStatus === "ok" && "Đã kết nối tới backend"}
                {connStatus === "bad" && "Không kết nối được API"}
              </span>
            </div>
          </div>
        </div>
      </div>

      <nav className="topnav-tabs">
        {TABS.map((tab) => (
          <NavLink key={tab.to} to={tab.to} className={`topnav-tab${tab.match(location.pathname) ? " active" : ""}`}>
            {tab.label}
            {tab.to === "/alerts" && openAlertCount != null && openAlertCount > 0 && (
              <span className="topnav-badge">{openAlertCount}</span>
            )}
          </NavLink>
        ))}
      </nav>
    </header>
  );
}
