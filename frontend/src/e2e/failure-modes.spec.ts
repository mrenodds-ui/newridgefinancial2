import { expect, test } from "@playwright/test";

test.describe("Failure modes", () => {
  test("offline startup shows offline message", async ({ page, context }) => {
    await context.setOffline(true);
    await page.goto("/app/");
    await expect(page.getByText(/offline/i)).toBeVisible();
    await context.setOffline(false);
  });

  test("failed save shows error", async ({ page }) => {
    await page.goto("/app/");
    // Simulate failure by blocking IndexedDB
    await page.addInitScript(() => {
      window.indexedDB.deleteDatabase = () => {
        throw new Error("fail");
      };
    });
    await page.getByLabel("Period").fill("2026-07");
    await page.getByLabel("Production").fill("100000");
    await page.getByLabel("Collections").fill("95000");
    await page.getByLabel("Overhead %").fill("25");
    await page.getByRole("button", { name: /save/i }).click();
    await expect(page.getByText(/failed|error|retry/i)).toBeVisible();
  });
});
