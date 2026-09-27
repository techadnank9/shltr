import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // ?source=ws talks to the control plane; point VITE_API at it when it exists.
    proxy: { '/ws': { target: process.env.VITE_API ?? 'http://localhost:8000', ws: true } },
  },
  build: { chunkSizeWarningLimit: 1600 },
})
