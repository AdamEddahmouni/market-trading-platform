import { expect, test } from "@playwright/test";
import { FUTURES_CONTRACT, OPTION_CONTRACT, openFuturesWorkspace, openOptionsWorkspace } from "./helpers";

test.describe("G15 derivative Paper acceptance", () => {
  test("options product surface shows canonical contract identity", async ({ page }) => {
    await openOptionsWorkspace(page);
    const surface = page.getByLabel("Options product surface");
    await expect(surface.getByRole("heading", { name: `Options · ${OPTION_CONTRACT}` })).toBeVisible();
    await expect(surface.getByText("Multiplier")).toBeVisible();
    await expect(surface.getByText("100", { exact: true })).toBeVisible();
    await expect(surface.getByText("call", { exact: true })).toBeVisible();
  });

  test("futures contract surface is margin-aware and non-family actionable", async ({ page }) => {
    await openFuturesWorkspace(page);
    await expect(page.getByRole("heading", { name: `Futures · ${FUTURES_CONTRACT}` })).toBeVisible();
    await expect(page.getByLabel(/Futures product surface/i).getByText(/margin/i).first()).toBeVisible();
  });
});
