import { HashRouter, Routes, Route, Outlet } from "react-router-dom";
import TopNav from "./components/TopNav";
import Overview from "./pages/Overview";
import Products from "./pages/Products";
import Alerts from "./pages/Alerts";
import ImportFlow from "./pages/ImportFlow";
import CreateReceiptManual from "./pages/CreateReceiptManual";
import ExportFlow from "./pages/ExportFlow";
import ExportHistory from "./pages/ExportHistory";
import Chatbot from "./pages/Chatbot";
import ScanReceipt from "./pages/ScanReceipt";
import "./styles/app.css";

// Dùng HashRouter (URL dạng /#/import) thay vì BrowserRouter — tránh cần
// cấu hình rewrite rule riêng trên Vercel cho SPA (Vercel serve file tĩnh,
// nếu dùng BrowserRouter mà không có vercel.json rewrite thì F5 ở /import
// sẽ ra lỗi 404). HashRouter luôn chạy đúng ngay cả khi chỉ serve tĩnh đơn giản.
function Layout() {
  return (
    <div className="page">
      <TopNav />
      <Outlet />
    </div>
  );
}

export default function App() {
  return (
    <HashRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Overview />} />
          <Route path="/products" element={<Products />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/import" element={<ImportFlow />} />
          <Route path="/import/create" element={<CreateReceiptManual />} />
          <Route path="/import/scan" element={<ScanReceipt />} />
          <Route path="/export" element={<ExportFlow />} />
          <Route path="/export/history" element={<ExportHistory />} />
          <Route path="/chatbot" element={<Chatbot />} />
        </Route>
      </Routes>
    </HashRouter>
  );
}
