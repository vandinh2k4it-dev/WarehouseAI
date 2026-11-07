import { useState } from "react";

// Key và 2 mã màu dưới đây phải khớp với đoạn script trong index.html.
const STORAGE_KEY = "theme";
const THEME_COLORS = { light: "#FFFFFF", dark: "#12161B" };

export default function ThemeToggle() {
  const [theme, setTheme] = useState(() =>
    document.documentElement.dataset.theme === "dark" ? "dark" : "light"
  );
  const next = theme === "dark" ? "light" : "dark";
  const label = next === "dark" ? "Chuyển sang chế độ tối" : "Chuyển sang chế độ sáng";

  function toggle() {
    document.documentElement.dataset.theme = next;
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", THEME_COLORS[next]);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Trình duyệt chặn lưu trữ: vẫn đổi được giao diện, chỉ không nhớ cho lần sau.
    }
    setTheme(next);
  }

  return (
    <button type="button" className="themeToggle" onClick={toggle} aria-label={label} title={label}>
      {next === "dark" ? "🌙" : "☀️"}
    </button>
  );
}
