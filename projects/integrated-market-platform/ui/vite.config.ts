import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const apiPort = process.env.IMP_E2E_API_PORT ?? "8766";
const apiTarget = `http://127.0.0.1:${apiPort}`;
const uiPort = Number(process.env.IMP_E2E_UI_PORT ?? "5173");

function spaHtmlBypass(req: { method?: string; headers: { accept?: string } }) {
  const accept = req.headers.accept ?? "";
  if (req.method === "GET" && accept.includes("text/html")) {
    return "/index.html";
  }
  return undefined;
}

export default defineConfig({
  plugins: [react()],
  build: {
    manifest: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("/node_modules/victory-vendor/")) return "chart-primitives";
          if (id.includes("/node_modules/recharts/")) return "recharts";
          if (id.includes("/node_modules/@luxalgo/vela")) return "vela";
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
      "/opportunities": apiTarget,
      "/intelligence": apiTarget,
      "/canary": apiTarget,
      "/accounts": apiTarget,
      "/security": apiTarget,
      "/discover": {
        target: apiTarget,
        bypass: spaHtmlBypass,
      },
      "/instruments": apiTarget,
      "/explain": apiTarget,
      "/inspect": apiTarget,
      "/replay": apiTarget,
      "/explore/futures": apiTarget,
      "/explore/squeeze": apiTarget,
      "/explore/catalyst": apiTarget,
      "/workspace": {
        target: apiTarget,
        bypass: spaHtmlBypass,
      },
      "/assistant": {
        target: apiTarget,
        bypass: spaHtmlBypass,
      },
      "/research": {
        target: apiTarget,
        bypass: spaHtmlBypass,
      },
      "/paper": apiTarget,
      "/provider": apiTarget,
      "/symbols": apiTarget,
      "/market-state": apiTarget,
      "/subscriptions": apiTarget,
      "/operator": apiTarget,
      "/control": {
        target: "http://127.0.0.1:8767",
        bypass: spaHtmlBypass,
      },
      "/state": apiTarget,
      "/captures": apiTarget,
    },
  },
});
