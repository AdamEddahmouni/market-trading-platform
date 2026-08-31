import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

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
    port: 5173,
    proxy: {
      "/context": "http://127.0.0.1:8766",
      "/capabilities": "http://127.0.0.1:8766",
      "/attention": "http://127.0.0.1:8766",
      "/discover": "http://127.0.0.1:8766",
      "/instruments": "http://127.0.0.1:8766",
      "/explain": "http://127.0.0.1:8766",
      "/inspect": "http://127.0.0.1:8766",
      "/replay": "http://127.0.0.1:8766",
      "/explore/futures": "http://127.0.0.1:8766",
      "/explore/squeeze": "http://127.0.0.1:8766",
      "/explore/catalyst": "http://127.0.0.1:8766",
      "/workspace": {
        target: "http://127.0.0.1:8766",
        bypass(req) {
          const accept = req.headers.accept ?? "";
          if (req.method === "GET" && accept.includes("text/html")) {
            return "/index.html";
          }
        },
      },
      "/assistant": "http://127.0.0.1:8766",
      "/research": "http://127.0.0.1:8766",
      "/paper": "http://127.0.0.1:8766",
      "/provider": "http://127.0.0.1:8766",
      "/symbols": "http://127.0.0.1:8766",
      "/market-state": "http://127.0.0.1:8766",
      "/subscriptions": "http://127.0.0.1:8766",
      "/operator": "http://127.0.0.1:8766",
      "/state": "http://127.0.0.1:8766",
      "/captures": "http://127.0.0.1:8766",
    },
  },
});
