import { expect, test } from "@playwright/test";

test.use({ viewport: { width: 390, height: 844 } }); // iPhone 12 Pro

test("main screen fits and is usable on mobile", async ({ page }) => {
  await page.goto("/app/");
  // Main heading visible
  await expect(page.getByRole("heading", { name: /browser app/i })).toBeVisible();
  // Form fields visible and usable
  await expect(page.getByLabel("Period")).toBeVisible();
  await expect(page.getByLabel("Production")).toBeVisible();
  await expect(page.getByLabel("Collections")).toBeVisible();
  await expect(page.getByLabel("Overhead %")).toBeVisible();
  // Save button visible
  await expect(page.getByRole("button", { name: /save/i })).toBeVisible();
  // No horizontal scroll
  const bodyOverflow = await page.evaluate(() => document.body.scrollWidth > document.body.clientWidth);
  expect(bodyOverflow).toBeFalsy();
});
