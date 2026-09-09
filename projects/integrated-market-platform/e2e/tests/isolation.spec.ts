import { expect, test } from "@playwright/test";
import {
  enterDemoMode,
  enterPaperMode,
  EQUITY_INSTRUMENT,
  expectPortfolioShowsSymbol,
  navigateClient,
  openEquityWorkspace,
  previewAndSubmitEquityOrder,
  switchMode,
} from "./helpers";

test.describe("G15 mode isolation", () => {
  test("Demo portfolio does not show Paper execution state as current truth", async ({ page }) => {
    await enterPaperMode(page);
    await openEquityWorkspace(page);
    await previewAndSubmitEquityOrder(page, 1);
    await navigateClient(page, "/portfolio");
    await expectPortfolioShowsSymbol(page, EQUITY_INSTRUMENT);

    await switchMode(page, "DEMO");
    await navigateClient(page, "/portfolio");
    await expect(page.locator("section.mode-environment-bar[data-mode='DEMO']")).toBeVisible();
    const submitControls = page.getByRole("button", { name: "Submit" });
    await expect(submitControls).toHaveCount(0);
    const positions = page.getByRole("heading", { name: "Positions" }).locator("xpath=following-sibling::table[1]");
    await expect(positions.getByRole("cell", { name: EQUITY_INSTRUMENT, exact: true })).toHaveCount(0);
  });

  test("switching Paper back does not surface Demo read-only banner as execution authority", async ({ page }) => {
    await enterDemoMode(page);
    await navigateClient(page, "/portfolio");
    await expect(page.locator("section.mode-environment-bar[data-mode='DEMO']")).toBeVisible();

    await switchMode(page, "PAPER");
    await openEquityWorkspace(page);
    await expect(page.getByRole("heading", { name: /Order ticket/i })).toBeVisible();
    await expect(page.getByText(/PAPER ONLY/i).first()).toBeVisible();
  });
});
