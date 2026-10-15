import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 开发期将 /api 代理到 FastAPI，避免跨域并保持前端代码零硬编码地址
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // 与 tsconfig.app.json 的 paths 对齐，构建期同样可解析 @/*
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        // SSE 流式接口必须关闭代理缓冲，否则逐字输出会被攒包
        configure: (proxy) => {
          proxy.on("proxyRes", (proxyRes) => {
            if (proxyRes.headers["content-type"]?.includes("text/event-stream")) {
              proxyRes.headers["cache-control"] = "no-cache";
            }
          });
        },
      },
    },
  },
  build: {
    sourcemap: false,
    chunkSizeWarningLimit: 1200,
  },
});
