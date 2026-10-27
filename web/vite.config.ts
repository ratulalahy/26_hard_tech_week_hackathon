import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// Relative base: the built dist/ works from any static path (spec §11 laptop delivery).
export default defineConfig({
  base: './',
  plugins: [react(), tailwindcss()],
  build: {
    target: 'es2022',
    chunkSizeWarningLimit: 1600,
    rollupOptions: {
      output: {
        manualChunks: { maplibre: ['maplibre-gl'], echarts: ['echarts/core', 'echarts/charts', 'echarts/components', 'echarts/renderers'] },
      },
    },
  },
  preview: { port: 4173, strictPort: true, host: '127.0.0.1' },
  server: { host: '127.0.0.1' },
});
