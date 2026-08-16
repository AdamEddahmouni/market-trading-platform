import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/context": "http://127.0.0.1:8766",
      "/capabilities": "http://127.0.0.1:8766",
      "/attention": "http://127.0.0.1:8766",
      "/instruments": "http://127.0.0.1:8766",
      "/explain": "http://127.0.0.1:8766",
      "/inspect": "http://127.0.0.1:8766",
      "/replay": "http://127.0.0.1:8766",
      "/explore": "http://127.0.0.1:8766",
      "/workspace": "http://127.0.0.1:8766",
      "/assistant": "http://127.0.0.1:8766",
      "/research": "http://127.0.0.1:8766",
    },
  },
});
