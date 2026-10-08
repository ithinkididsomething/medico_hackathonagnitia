import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Where the dev server proxies /api requests to the Python backend.
// Override with:  BACKEND_URL=http://127.0.0.1:8000 npm run dev
const backendUrl = process.env.BACKEND_URL || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: backendUrl,
        changeOrigin: true,
      },
    },
  },
})
