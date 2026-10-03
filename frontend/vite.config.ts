import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Docker supplies all of these values. Defaults support host development.
  server: {
    host: process.env.VITE_DEV_HOST || '127.0.0.1',
    port: Number(process.env.VITE_DEV_PORT || '5173'),
    strictPort: true,
    watch: { usePolling: process.env.VITE_USE_POLLING === 'true' },
    proxy: { '/api': process.env.VITE_API_PROXY || 'http://127.0.0.1:8000' },
  },
  test: { globals: true, environment: 'jsdom', setupFiles: ['./src/test-setup.ts'], css: false },
});

