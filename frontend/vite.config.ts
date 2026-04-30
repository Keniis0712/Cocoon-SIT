import { fileURLToPath, URL } from "node:url";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          const normalizedId = id.replace(/\\/g, "/");
          if (!normalizedId.includes("node_modules")) {
            return undefined;
          }
          if (normalizedId.includes("/echarts/")) {
            return "vendor-charts";
          }
          if (
            normalizedId.includes("/react/") ||
            normalizedId.includes("/react-dom/") ||
            normalizedId.includes("/react-router") ||
            normalizedId.includes("/@remix-run/") ||
            normalizedId.includes("/scheduler/") ||
            normalizedId.includes("/use-sync-external-store/")
          ) {
            return "vendor-framework";
          }
          if (
            normalizedId.includes("/i18next") ||
            normalizedId.includes("/react-i18next") ||
            normalizedId.includes("/i18next-browser-languagedetector/")
          ) {
            return "vendor-i18n";
          }
          if (normalizedId.includes("/axios/") || normalizedId.includes("/@cocoon-sit/ts-sdk/")) {
            return "vendor-api";
          }
          return undefined;
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    globals: true,
    css: false,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_BACKEND_TARGET || "http://127.0.0.1:8000",
        changeOrigin: true,
        ws: true,
      },
    },
  },
});
