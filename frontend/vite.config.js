import process from 'node:process'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => {
  // Extra hostnames the dev server answers to (e.g. your Mac's .local name), comma-separated.
  // Set VITE_ALLOWED_HOSTS in frontend/.env.local, which is git-ignored.
  const env = loadEnv(mode, process.cwd(), '')
  const allowedHosts = (env.VITE_ALLOWED_HOSTS ?? '').split(',').map((h) => h.trim()).filter(Boolean)
  return {
    plugins: [react(), tailwindcss()],
    server: {
      allowedHosts,
      proxy: {
        '/api': 'http://localhost:8000',
      },
    },
  }
})
