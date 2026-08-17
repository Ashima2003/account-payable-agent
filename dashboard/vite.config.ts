import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Dev only -- in production the built dist/ is served by the same
      // FastAPI process as /api/*, so there's no cross-origin request and
      // no proxy involved (see api/app.py).
      '/api': 'http://localhost:8000',
    },
  },
})
