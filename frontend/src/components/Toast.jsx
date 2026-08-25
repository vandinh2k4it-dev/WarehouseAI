import { createContext, useCallback, useContext, useRef, useState } from "react";

// Hệ thống Toast dùng chung toàn app — thay cho việc mỗi trang tự hiện
// thông báo kết quả theo 1 kiểu riêng (rải rác, không nhất quán). Bọc
// <ToastProvider> ở gốc app (trong App.jsx, bên ngoài <HashRouter> hoặc
// bên trong đều được, miễn bọc toàn bộ các trang cần dùng), rồi bất kỳ
// component con nào cũng gọi được useToast() để hiện thông báo.
//
// CÁCH DÙNG (thêm vào App.jsx của bạn):
//   import { ToastProvider } from "./components/Toast";
//   export default function App() {
//     return (
//       <ToastProvider>
//         <HashRouter>...</HashRouter>
//       </ToastProvider>
//     );
//   }
//
// CÁCH DÙNG trong bất kỳ trang/component nào:
//   import { useToast } from "../components/Toast";
//   const showToast = useToast();
//   showToast("Đã lưu thành công!", "success");
//   showToast("Có lỗi xảy ra: " + err.message, "error");
//   showToast("Đang xử lý...", "info");

const ToastContext = createContext(null);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const idRef = useRef(0);

  const showToast = useCallback((message, type = "info", duration = 3000) => {
    const id = ++idRef.current;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, duration);
  }, []);

  function dismiss(id) {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }

  return (
    <ToastContext.Provider value={showToast}>
      {children}
      <div className="toastStack">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.type}`} onClick={() => dismiss(t.id)}>
            {t.type === "success" && "✅ "}
            {t.type === "error" && "⚠️ "}
            {t.type === "info" && "ℹ️ "}
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast() phải được gọi bên trong <ToastProvider> — bọc App.jsx trước khi dùng.");
  }
  return ctx;
}
