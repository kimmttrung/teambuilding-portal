import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      // Gọi API bằng đường dẫn tương đối /api/... trong mọi môi trường:
      // dev thì Vite proxy sang uvicorn, production thì nginx proxy sang backend.
      // Nhờ vậy không cần cấu hình CORS và không có URL backend nào nằm trong code.
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/uploads': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
