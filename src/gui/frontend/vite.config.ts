import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';

// 产物输出到 ../dist-frontend（与 Tauri.toml 的 frontendDist 对应）
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: fileURLToPath(new URL('../dist-frontend', import.meta.url)),
    emptyOutDir: true,
  },
  // Tauri 用静态产物，base 设为相对路径
  base: './',
  server: {
    port: 5173,
    strictPort: true,
  },
});
