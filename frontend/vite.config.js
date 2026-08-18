import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      // Đổi từ 'generateSW' (Workbox tự sinh service worker, không tuỳ biến
      // được) sang 'injectManifest' — dùng file src/sw.js TỰ VIẾT, cho phép
      // thêm code xử lý sự kiện 'push' (thông báo đẩy) mà generateSW không
      // hỗ trợ. vite-plugin-pwa vẫn tự lo phần cache asset tĩnh như trước
      // (tiêm sẵn danh sách file vào biến self.__WB_MANIFEST trong sw.js).
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.js',
      injectManifest: {
        // Không cache API call (dữ liệu tồn kho/phiên đếm phải luôn mới) —
        // chỉ cache asset tĩnh (JS/CSS/font).
        globPatterns: ['**/*.{js,css,html,png,svg,ico}'],
      },
      registerType: 'autoUpdate',
      manifest: {
        name: 'Warehouse — Đếm hàng thông minh',
        short_name: 'Warehouse',
        description: 'Đếm thùng carton qua camera điện thoại — Hệ thống quản lý kho thông minh',
        theme_color: '#12161B',
        background_color: '#12161B',
        display: 'standalone',
        orientation: 'portrait',
        start_url: '/',
        icons: [
          { src: 'icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
    }),
  ],
})
