import { expect, test } from "@playwright/test";

type Vitals = {
  lcp: number;
  cls: number;
  inp: number;
};

test.describe("Performance budgets", () => {
  test("main app shell meets web vitals budgets", async ({ page }) => {
    await page.goto("/app/");
    // Collect Web Vitals via injected script
    const vitals = await page.evaluate(async (): Promise<Partial<Vitals> | null> => {
      // @ts-ignore
      const { getLCP, getCLS, getINP } = window.webVitals || {};
      if (!getLCP || !getCLS || !getINP) return null;
      const results: Partial<Vitals> = {};
      await Promise.all([
        getLCP((v: { value: number }) => {
          results.lcp = v.value;
        }),
        getCLS((v: { value: number }) => {
          results.cls = v.value;
        }),
        getINP((v: { value: number }) => {
          results.inp = v.value;
        }),
      ]);
      return results;
    });
    expect(vitals).not.toBeNull();
    expect(vitals?.lcp ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(2500); // ms
    expect(vitals?.cls ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(0.1);
    expect(vitals?.inp ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(200); // ms
  });
});
