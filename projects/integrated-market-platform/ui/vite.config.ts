import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const apiPort = process.env.IMP_E2E_API_PORT ?? "8766";
const apiTarget = `http://127.0.0.1:${apiPort}`;
const uiPort = Number(process.env.IMP_E2E_UI_PORT ?? "5173");

export default defineConfig({
  plugins: [react()],
  build: {
    manifest: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("/node_modules/victory-vendor/")) return "chart-primitives";
          if (id.includes("/node_modules/recharts/")) return "recharts";
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: true,
  },
  server: {
    port: uiPort,
    proxy: {
      "/context": apiTarget,
      "/auth": apiTarget,
      "/capabilities": apiTarget,
      "/attention": apiTarget,
      "/discover": apiTarget,
      "/instruments": apiTarget,
      "/explain": apiTarget,
      "/inspect": apiTarget,
      "/replay": apiTarget,
      "/explore/futures": apiTarget,
      "/explore/squeeze": apiTarget,
      "/explore/catalyst": apiTarget,
      "/workspace": {
        target: apiTarget,
        bypass(req) {
          const accept = req.headers.accept ?? "";
          if (req.method === "GET" && accept.includes("text/html")) {
            return "/index.html";
          }
        },
      },
      "/assistant": apiTarget,
      "/research": apiTarget,
      "/paper": apiTarget,
      "/provider": apiTarget,
      "/symbols": apiTarget,
      "/market-state": apiTarget,
      "/subscriptions": apiTarget,
      "/operator": apiTarget,
      "/control": "http://127.0.0.1:8767",
      "/state": apiTarget,
      "/captures": apiTarget,
    },
  },
});
