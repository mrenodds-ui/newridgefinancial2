import { type Page, expect, test } from "@playwright/test";

function buildFinancialSummary() {
  const trailing12Months = Array.from({ length: 12 }, (_, index) => ({
    year_month: `2026-${String(index + 1).padStart(2, "0")}`,
    gross_production: 100,
    net_production: 90,
    collections: 50,
    collection_rate: 50,
  }));

  const quickBooksProfitLossSummary = [
    { year_month: "2025-05", income_total: 9999, expense_total: 8888, net_income: 9999 },
    ...Array.from({ length: 12 }, (_, index) => ({
      year_month: `2026-${String(index + 1).padStart(2, "0")}`,
      income_total: 200,
      expense_total: 40,
      net_income: 10,
    })),
    { year_month: "2026-12", income_total: 800, expense_total: 500, net_income: 300 },
  ];

  return {
    generatedAt: "2026-06-22T10:00:00Z",
    latestSoftDentRefreshAt: "2026-06-22T09:45:00Z",
    dataFreshnessStatus: "fresh",
    sourceReview: null,
    softDentCoverage: null,
    softDentCoverageMetrics: null,
    claimsSummary: null,
    lastRefreshed: "2026-06-22T09:50:00Z",
    latestDailyKpi: null,
    latestAr: {
      as_of_date: "2026-06-22",
      total_ar: 3000,
      insurance_ar: 1200,
      patient_ar: 1800,
      current_balance: 1500,
      balance_30: 800,
      balance_60: 500,
      balance_90: 200,
      credit_balance: 0,
    },
    monthlyKpis: [
      { year_month: "2026-05", gross_production: 100, net_production: 80, collections: 50, collection_rate: 50 },
      { year_month: "2026-06", gross_production: 900, net_production: 700, collections: 650, collection_rate: 72 },
    ],
    trailing12Months,
    calendarYearKpis: trailing12Months,
    fourYearMonthlyKpis: [
      { year_month: "2024-01", gross_production: 1000, net_production: 900, collections: 900, collection_rate: 90 },
      ...trailing12Months,
    ],
    providerProduction: [],
    topAdaCodes: [],
    quickBooksStatus: {
      status: "ok",
      message: "ready",
      lastCheckedAtUtc: "2026-06-22T09:45:00Z",
      lastImportedAtUtc: "2026-06-22T09:40:00Z",
      rowCounts: {},
    },
    quickBooksExpenseCategories: [
      { expense_category: "Supplies", total_amount: 200 },
      { expense_category: "Payroll", total_amount: 500 },
    ],
    quickBooksMonthlyExpenses: [],
    quickBooksProfitLossSummary,
    quickBooksEbitdaCandidates: quickBooksProfitLossSummary,
    dataFreshnessWarnings: [],
    currentMonthProduction: { year_month: "2026-06", gross_production: 900, net_production: 700, collections: 650, collection_rate: 72 },
    currentYearProduction: { year_month: "2026", gross_production: 1000, net_production: 780, collections: 700, collection_rate: 70 },
  };
}

async function mockFinancialSummary(page: Page): Promise<void> {
  await page.route("**/api/hal9000/page-summary", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(buildFinancialSummary()),
    });
  });
}

test("loads the repaired financial routes under /app", async ({ page }) => {
  await mockFinancialSummary(page);

  const routeChecks = [
    { path: "/app/softdent", heading: "SoftDent Financials", expectedTexts: ["$900", "72%"] },
    { path: "/app/ar", heading: "A/R & Collections", expectedTexts: ["72%", "$3,000"] },
    { path: "/app/trends", heading: "Trends", expectedTexts: ["$1,200", "$410"] },
    { path: "/app/hal-landing", heading: "New Ridge Family Financial", expectedTexts: ["$900", "$300"] },
  ] as const;

  for (const routeCheck of routeChecks) {
    await page.goto(routeCheck.path);
    await expect(page.getByRole("heading", { name: routeCheck.heading })).toBeVisible();
    for (const text of routeCheck.expectedTexts) {
      await expect(page.getByText(text, { exact: true }).first()).toBeVisible();
    }
  }
});

test("renders sidebar links for the mounted financial routes", async ({ page }) => {
  await mockFinancialSummary(page);
  await page.goto("/app/hal-landing");

  await expect(page.getByRole("link", { name: "SoftDent" })).toHaveAttribute("href", "/app/softdent");
  await expect(page.getByRole("link", { name: "A/R & Collections" })).toHaveAttribute("href", "/app/ar");
  await expect(page.getByRole("link", { name: "Trends" })).toHaveAttribute("href", "/app/trends");
  await expect(page.getByRole("link", { name: "Hal 9000 Landing" })).toHaveAttribute("href", "/app/hal-landing");
});
