import { precacheAndRoute } from "workbox-precaching";
import { clientsClaim } from "workbox-core";

self.skipWaiting();
clientsClaim();

// vite-plugin-pwa (chế độ injectManifest) tự tiêm danh sách file cần cache
// vào biến này lúc build — dòng dưới đây BẮT BUỘC phải có, không được xoá,
// nếu không bước build sẽ báo lỗi "manifest injection point not found".
precacheAndRoute(self.__WB_MANIFEST);

// ==========================================================
// PUSH NOTIFICATION — nhận thông báo đẩy từ backend (app/push_service.py)
// ==========================================================
self.addEventListener("push", (event) => {
  let data = { title: "Warehouse", body: "Có cảnh báo mới", url: "/" };
  try {
    if (event.data) data = { ...data, ...event.data.json() };
  } catch {
    // payload không phải JSON hợp lệ -> dùng giá trị mặc định ở trên
  }

  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: "/icon-192.png",
      badge: "/icon-192.png",
      data: { url: data.url || "/" },
      vibrate: [100, 50, 100],
    })
  );
});

// Bấm vào thông báo -> mở đúng trang liên quan (vd /#/alerts) — nếu app đã
// mở sẵn 1 tab thì focus vào tab đó thay vì mở tab mới, tránh mở trùng.
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetPath = event.notification.data?.url || "/";
  const targetUrl = new URL(`/#${targetPath}`, self.location.origin).href;

  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if (client.url.startsWith(self.location.origin) && "focus" in client) {
          client.navigate(targetUrl);
          return client.focus();
        }
      }
      return self.clients.openWindow(targetUrl);
    })
  );
});
