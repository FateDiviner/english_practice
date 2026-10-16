import { fileURLToPath, URL } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// 管理端独立部署：后端地址由 VITE_API_BASE 决定，开发期走代理
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5174,
    strictPort: true,
    proxy: {
      "/api": {
        target: process.env.VITE_PROXY_TARGET ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
