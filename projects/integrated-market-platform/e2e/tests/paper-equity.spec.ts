import { expect, test } from "@playwright/test";
import {
  enterPaperMode,
  EQUITY_INSTRUMENT,
  navigateClient,
  expectPortfolioShowsSymbol,
  openEquityWorkspace,
  previewAndSubmitEquityOrder,
  waitForPlatformReady,
} from "./helpers";

test.describe("G15 equity Paper acceptance", () => {
  test("launches product and reaches Paper workspace", async ({ page }) => {
    await waitForPlatformReady(page);
    await enterPaperMode(page);
    await openEquityWorkspace(page);
    await expect(page.getByText(/PAPER ONLY/i).first()).toBeVisible();
    await expect(page.getByRole("heading", { name: EQUITY_INSTRUMENT, exact: true })).toBeVisible();
  });

  test("preview and submit update portfolio through real API boundary", async ({ page }) => {
    await enterPaperMode(page);
    await openEquityWorkspace(page);
    await previewAndSubmitEquityOrder(page, 1);
    await navigateClient(page, "/portfolio");
    await expect(page.locator("section.mode-environment-bar[data-mode='PAPER']")).toBeVisible();
    await expectPortfolioShowsSymbol(page, EQUITY_INSTRUMENT);
  });
});
