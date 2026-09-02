import react from "@vitejs/plugin-react";
import { parseCLI, startVitest } from "vitest/node";

const { filter, options } = parseCLI(["vitest", ...process.argv.slice(2)]);

const vitest = await startVitest("test", filter, {
  ...options,
  config: false,
  root: process.cwd(),
  run: true,
  globals: true,
  environment: "jsdom",
  setupFiles: ["./src/test/setup.ts"],
  css: true,
  plugins: [react()],
});

await vitest?.exit();
