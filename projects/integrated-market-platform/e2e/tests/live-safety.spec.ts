import { expect, test } from "@playwright/test";
import { enterPaperMode, navigateClient, openEquityWorkspace, switchMode, waitForPlatformReady } from "./helpers";

test.describe("G15 live execution safety", () => {
  test("Live mode does not expose order submit controls", async ({ page }) => {
    await waitForPlatformReady(page);
    await page.getByRole("button", { name: /Live/i }).click();
    await page.getByRole("button", { name: /Enter live data/i }).click();
    await expect(page.locator("section.mode-environment-bar[data-mode='LIVE']")).toBeVisible();
    await navigateClient(page, "/workspace/BIYA");
    await expect(page.getByRole("button", { name: "Submit" })).toHaveCount(0);
    await expect(page.getByText(/Execution locked/i)).toBeVisible();
  });

  test("Paper submit remains available only in Paper mode", async ({ page }) => {
    await enterPaperMode(page);
    await openEquityWorkspace(page);
    await expect(page.getByRole("button", { name: "Preview" })).toBeVisible();
    await switchMode(page, "DEMO");
    await navigateClient(page, "/workspace/BIYA");
    await expect(page.getByRole("button", { name: "Submit" })).toHaveCount(0);
  });
});
