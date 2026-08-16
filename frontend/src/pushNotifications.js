import { api } from "./api";

// Chuyển khoá công khai VAPID (dạng base64url từ backend) thành Uint8Array —
// định dạng bắt buộc theo chuẩn Push API (PushManager.subscribe cần
// applicationServerKey ở dạng này, không nhận thẳng string).
function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  return Uint8Array.from([...rawData].map((c) => c.charCodeAt(0)));
}

export function isPushSupported() {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

export function getPermissionState() {
  if (!("Notification" in window)) return "unsupported";
  return Notification.permission; // "granted" | "denied" | "default"
}

// Xin quyền + đăng ký nhận push — gọi khi người dùng chủ động bấm nút "Bật
// thông báo" (KHÔNG tự gọi lúc mở app, trình duyệt sẽ chặn/ẩn hộp thoại xin
// quyền nếu gọi không do người dùng chủ động thao tác).
export async function subscribeToPush(deviceLabel) {
  if (!isPushSupported()) {
    throw new Error("Trình duyệt này không hỗ trợ thông báo đẩy (Push API).");
  }

  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error("Bạn chưa cho phép nhận thông báo — vào cài đặt trình duyệt để bật lại nếu đổi ý.");
  }

  const { public_key } = await api.getVapidPublicKey();
  const registration = await navigator.serviceWorker.ready;

  let subscription = await registration.pushManager.getSubscription();
  if (!subscription) {
    subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(public_key),
    });
  }

  await api.subscribePush(subscription.toJSON(), deviceLabel);
  return subscription;
}

export async function unsubscribeFromPush() {
  if (!isPushSupported()) return;
  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.getSubscription();
  if (!subscription) return;

  await api.unsubscribePush(subscription.endpoint);
  await subscription.unsubscribe();
}

export async function getCurrentSubscription() {
  if (!isPushSupported()) return null;
  const registration = await navigator.serviceWorker.ready;
  return registration.pushManager.getSubscription();
}
