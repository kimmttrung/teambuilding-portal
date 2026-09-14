import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Chạy thẳng trên máy: uvicorn ở 127.0.0.1:8000. Chạy trong docker-compose.dev.yml: http://backend:8000.
const proxyTarget = process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // Bind mount từ Windows vào container không phát sự kiện đổi file — phải hỏi định kỳ.
    watch: process.env.VITE_USE_POLLING === 'true' ? { usePolling: true, interval: 300 } : undefined,
    proxy: {
      // Gọi API bằng đường dẫn tương đối /api/... trong mọi môi trường:
      // dev thì Vite proxy sang uvicorn, production thì nginx proxy sang backend.
      // Nhờ vậy không cần cấu hình CORS và không có URL backend nào nằm trong code.
      '/api': { target: proxyTarget, changeOrigin: true },
      '/uploads': { target: proxyTarget, changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
