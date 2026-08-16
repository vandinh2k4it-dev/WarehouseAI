import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'Đếm hàng — Kho thông minh',
        short_name: 'Đếm hàng',
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
      // Không cache API call (dữ liệu tồn kho/phiên đếm phải luôn mới) —
      // chỉ cache asset tĩnh (JS/CSS/font) để mở app nhanh hơn lần sau.
      workbox: {
        navigateFallbackDenylist: [/^\/camera-sessions/, /^\/receipts/, /^\/products/],
      },
    }),
  ],
})
