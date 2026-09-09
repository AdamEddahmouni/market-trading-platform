import { expect, type Page } from "@playwright/test";

export const EQUITY_INSTRUMENT = "BIYA";
export const OPTION_CONTRACT = "NVDA20260815C00130000";
export const FUTURES_CONTRACT = "ES202512";

/** Client-side navigation that preserves ApplicationBootstrap mode state. */
export async function navigateClient(page: Page, path: string) {
  await page.evaluate((target) => {
    window.history.pushState({}, "", target);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, path);
}

export async function waitForPlatformReady(page: Page) {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Choose how you enter the market/i })).toBeVisible();
}

export async function enterPaperMode(page: Page) {
  const bar = page.locator("section.mode-environment-bar[data-mode='PAPER']");
  if (await bar.isVisible().catch(() => false)) return;
  await waitForPlatformReady(page);
  await page.getByRole("button", { name: /Paper/i }).click();
  await expect(page.locator("section.mode-environment-bar[data-mode='PAPER']")).toBeVisible();
}

export async function enterDemoMode(page: Page) {
  const bar = page.locator("section.mode-environment-bar[data-mode='DEMO']");
  if (await bar.isVisible().catch(() => false)) return;
  await waitForPlatformReady(page);
  await page.getByRole("button", { name: /Demo/i }).click();
  await expect(page.locator("section.mode-environment-bar[data-mode='DEMO']")).toBeVisible();
}

export async function switchMode(page: Page, mode: "DEMO" | "PAPER" | "LIVE") {
  await page.getByRole("button", { name: "Switch mode" }).click();
  if (mode === "LIVE") {
    await page.getByRole("button", { name: /Live/i }).click();
    await page.getByRole("button", { name: /Enter live data/i }).click();
  } else {
    await page.getByRole("button", { name: new RegExp(mode, "i") }).click();
  }
  await expect(page.locator(`section.mode-environment-bar[data-mode='${mode}']`)).toBeVisible();
}

export async function openEquityWorkspace(page: Page, symbol = EQUITY_INSTRUMENT) {
  await enterPaperMode(page);
  await navigateClient(page, `/workspace/${symbol}`);
  await expect(page.getByRole("heading", { name: /Order ticket/i })).toBeVisible();
}

export async function ensurePaperSession(page: Page) {
  const openSession = page.getByRole("button", { name: /Open simulation session/i });
  if (await openSession.isVisible().catch(() => false)) {
    await openSession.click();
  }
}

export async function previewAndSubmitEquityOrder(page: Page, quantity = 1) {
  await ensurePaperSession(page);
  const quantityInput = page.getByRole("spinbutton", { name: "Quantity" });
  await quantityInput.fill(String(quantity));
  await page.getByRole("button", { name: "Preview" }).click();
  await expect(page.getByText(/Risk:/i).first()).toBeVisible();
  await expect(page.getByText(/PASS/i).first()).toBeVisible();
  const submit = page.getByRole("button", { name: "Submit" });
  await expect(submit).toBeEnabled();
  await submit.click();
}

export async function openOptionsWorkspace(page: Page) {
  await enterPaperMode(page);
  await navigateClient(page, `/workspace/${OPTION_CONTRACT}/options`);
  await expect(page.getByLabel("Options product surface")).toBeVisible();
}

export async function openFuturesWorkspace(page: Page) {
  await enterPaperMode(page);
  await navigateClient(page, `/workspace/${FUTURES_CONTRACT}/futures`);
  await expect(page.getByLabel(/Futures product surface/i)).toBeVisible();
}

export async function expectPortfolioShowsSymbol(page: Page, symbol: string) {
  await expect(page.getByRole("heading", { name: /Paper Portfolio/i })).toBeVisible();
  const positions = page.getByRole("heading", { name: "Positions" }).locator("xpath=following-sibling::table[1]");
  await expect(positions.getByRole("cell", { name: symbol, exact: true })).toBeVisible();
}
