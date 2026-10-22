import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { allowedHosts: ['terminal.local'], proxy: { '/api': 'http://127.0.0.1:8000' } },
  preview: { allowedHosts: ['terminal.local'], proxy: { '/api': 'http://127.0.0.1:8000' } },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.js'],
    maxWorkers: 2,
    testTimeout: 10000,
  },
});
