import { HashRouter, Routes, Route } from "react-router-dom";
import Home from "./pages/Home";
import ImportFlow from "./pages/ImportFlow";
import ExportFlow from "./pages/ExportFlow";
import "./styles/app.css";

// Dùng HashRouter (URL dạng /#/import) thay vì BrowserRouter — tránh cần
// cấu hình rewrite rule riêng trên Vercel cho SPA (Vercel serve file tĩnh,
// nếu dùng BrowserRouter mà không có vercel.json rewrite thì F5 ở /import
// sẽ ra lỗi 404). HashRouter luôn chạy đúng ngay cả khi chỉ serve tĩnh đơn giản.
export default function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/import" element={<ImportFlow />} />
        <Route path="/export" element={<ExportFlow />} />
      </Routes>
    </HashRouter>
  );
}
