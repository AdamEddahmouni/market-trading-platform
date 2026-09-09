import { defineConfig, devices } from "@playwright/test";

const uiBase = process.env.IMP_E2E_UI_BASE ?? "http://127.0.0.1:5173";

export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [["list"], ["html", { open: "never", outputFolder: "../.local/e2e/playwright-report" }]],
  outputDir: "../.local/e2e/test-results",
  use: {
    baseURL: uiBase,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
