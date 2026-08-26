import { NavLink, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { api } from "../api";

const TABS = [
  { to: "/", label: "Tổng quan", icon: "📊", match: (p) => p === "/" },
  { to: "/products", label: "Sản phẩm", icon: "📦", match: (p) => p.startsWith("/products") },
  { to: "/import", label: "Nhập kho", icon: "⬇️", match: (p) => p.startsWith("/import") },
  { to: "/export", label: "Xuất kho", icon: "⬆️", match: (p) => p.startsWith("/export") },
  { to: "/chatbot", label: "Trợ lý AI", icon: "🤖", match: (p) => p.startsWith("/chatbot") },
  { to: "/alerts", label: "Cảnh báo", icon: "⚠️", match: (p) => p.startsWith("/alerts") },
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
          <img src="/icon-192.png" alt="Warehouse" className="topnav-logo" />
          <div>
            <div className="topnav-h1">Warehouse</div>
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
            <span className="topnav-tab-icon">{tab.icon}</span>
            <span className="topnav-tab-label">{tab.label}</span>
            {tab.to === "/alerts" && openAlertCount != null && openAlertCount > 0 && (
              <span className="topnav-badge">{openAlertCount}</span>
            )}
          </NavLink>
        ))}
      </nav>
    </header>
  );
}
