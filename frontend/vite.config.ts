import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // Any request to /api/... is forwarded to FastAPI, so the browser
    // only ever talks to one address.
    proxy: { '/api': 'http://localhost:8000' },
  },
})
