import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  plugins: [vue()],
  build: { target: 'es2022' },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:9001', changeOrigin: true },
      '/audio': { target: 'http://localhost:9001', changeOrigin: true }
    }
  }
});
