import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// In dev, requests to /api are proxied to the model backend (see .env.example).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  return {
    plugins: [react()],
    server: { proxy: { '/api': { target: env.VITE_API_URL || 'http://localhost:8000', changeOrigin: true, rewrite: p => p.replace(/^\/api/, '') } } },
  };
});
