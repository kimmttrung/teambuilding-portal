import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { STUB } from './stub-auth.js'

/**
 * Cấu hình tạm để render các trang bằng react-dom/server trong node.
 * Chỉ dùng để bắt lỗi render (trang trắng), không phải build production.
 */
export default defineConfig({
  root: path.resolve(import.meta.dirname, '..'),
  plugins: [
    react(),
    {
      name: 'stub-auth-context',
      enforce: 'pre',
      transform(code, id) {
        if (id.replace(/\\/g, '/').endsWith('/src/context/AuthContext.jsx')) return STUB
        return null
      },
    },
  ],
  build: {
    ssr: path.resolve(import.meta.dirname, 'entry.jsx'),
    outDir: path.resolve(import.meta.dirname, 'dist'),
    emptyOutDir: true,
    write: true,
  },
})
