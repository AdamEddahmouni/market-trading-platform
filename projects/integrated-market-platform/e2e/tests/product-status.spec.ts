import { expect, test } from "@playwright/test";
import { openOptionsWorkspace } from "./helpers";

test.describe("G15 structured product status", () => {
  test("options surface renders explicit status rather than generic no-data", async ({ page }) => {
    await openOptionsWorkspace(page);
    const surface = page.getByLabel("Options product surface");
    await expect(surface).toBeVisible();
    await expect(surface.getByText(/Status/i)).toBeVisible();
    await expect(surface.getByText(/UNAVAILABLE|EMPTY|NOT_ENTITLED|STALE|AVAILABLE/i).first()).toBeVisible();
  });
});
