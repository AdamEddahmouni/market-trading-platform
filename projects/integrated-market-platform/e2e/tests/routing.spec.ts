import { expect, test } from "@playwright/test";
import { enterPaperMode, FUTURES_CONTRACT, navigateClient, OPTION_CONTRACT } from "./helpers";

test.describe("G15 canonical route round-trip", () => {
  test("equity, option, and futures routes preserve instrument identity", async ({ page }) => {
    await enterPaperMode(page);

    await navigateClient(page, "/workspace/BIYA");
    await expect(page.getByRole("heading", { name: "BIYA", exact: true })).toBeVisible();

    await navigateClient(page, `/workspace/${OPTION_CONTRACT}/options`);
    await expect(page.getByRole("heading", { name: `${OPTION_CONTRACT} — Options Workspace` })).toBeVisible();

    await navigateClient(page, `/workspace/${FUTURES_CONTRACT}/futures`);
    await expect(page.getByRole("heading", { name: `${FUTURES_CONTRACT} — Futures Workspace` })).toBeVisible();
  });
});
