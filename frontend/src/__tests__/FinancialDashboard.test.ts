import { describe, expect, it } from "vitest";

import {
  buildArOver90AlertMessage,
  buildDashboardTrendData,
  buildProductionCollectionsSeries,
  buildProfitLossTrendData,
  buildDashboardSummaryFromFinancialSummary,
  buildFinancialSummaryInsurancePatientTotals,
  buildFinancialSummaryProviderProduction,
  buildLiveDashboardTrendData,
  buildLiveInsurancePatientTotals,
  buildLiveProviderProduction,
  buildQuickBooksExpenseCategoryData,
  buildQuickBooksMonthlyExpenseTrendData,
  selectLatestProfitLoss,
  selectLatestMonthlyKpi,
  sumTrailing12NetIncome,
  sumTrailing12ProductionCollections,
} from "../components/dashboard/financialDashboardSummary";

describe("selectLatestMonthlyKpi", () => {
  it("returns the newest monthly KPI entry", () => {
    const latest = selectLatestMonthlyKpi([
      { year_month: "2026-05", gross_production: 1000, collections: 800 },
      { year_month: "2026-06", gross_production: 2000, collections: 1500 },
    ]);

    expect(latest).toEqual({
      year_month: "2026-06",
      gross_production: 2000,
      collections: 1500,
    });
  });

  it("returns null when there are no monthly KPIs", () => {
    expect(selectLatestMonthlyKpi([])).toBeNull();
    expect(selectLatestMonthlyKpi(undefined)).toBeNull();
  });
});

describe("selectLatestProfitLoss", () => {
  it("returns the newest quickbooks profit and loss entry", () => {
    const latest = selectLatestProfitLoss([
      { year_month: "2026-05", income_total: 1000, net_income: 300 },
      { year_month: "2026-06", income_total: 1200, net_income: 450 },
    ]);

    expect(latest).toEqual({ year_month: "2026-06", income_total: 1200, net_income: 450 });
  });

  it("returns null when there are no quickbooks profit and loss rows", () => {
    expect(selectLatestProfitLoss([])).toBeNull();
  });
});

describe("buildProductionCollectionsSeries", () => {
  it("maps monthly KPI rows into chart-friendly production and collections points", () => {
    expect(
      buildProductionCollectionsSeries([
        { year_month: "2026-05", gross_production: 1000, collections: 700 },
        { year_month: "2026-06", gross_production: 1500, collections: 900 },
      ]),
    ).toEqual([
      { date: "2026-05", production: 1000, collections: 700 },
      { date: "2026-06", production: 1500, collections: 900 },
    ]);
  });
});

describe("buildDashboardTrendData", () => {
  it("prefers the verified trailing 12-month summary rows for the root dashboard charts", () => {
    expect(
      buildDashboardTrendData({
        monthlyKpis: [{ year_month: "2026-04", gross_production: 999, collections: 888 }],
        trailing12Months: [{ year_month: "2026-06", gross_production: 1500, collections: 1200 }],
        calendarYearKpis: [],
        fourYearMonthlyKpis: [{ year_month: "2026-01", gross_production: 1000, collections: 700 }],
        providerProduction: [],
        topAdaCodes: [],
        latestAr: null,
      } as const),
    ).toEqual([{ date: "2026-06", production: 1500, collections: 1200 }]);
  });
});

describe("trailing 12 shared selectors", () => {
  it("sums only the latest 12 production and collection rows", () => {
    const monthlyRows = Array.from({ length: 13 }, (_, index) => ({
      year_month: `2026-${String(index + 1).padStart(2, "0")}`,
      gross_production: 100,
      collections: 50,
    }));

    expect(sumTrailing12ProductionCollections(monthlyRows)).toEqual({
      production: 1200,
      collections: 600,
    });
  });

  it("builds expense/net-income trend rows and sums only the latest 12 net-income values", () => {
    const profitLossRows = [
      { year_month: "2025-05", expense_total: 900, net_income: 9999 },
      ...Array.from({ length: 12 }, (_, index) => ({
        year_month: `2026-${String(index + 1).padStart(2, "0")}`,
        expense_total: 40,
        net_income: 10,
      })),
      { year_month: "2026-12", expense_total: 500, net_income: 300 },
    ];

    expect(buildProfitLossTrendData(profitLossRows)[0]).toEqual({
      date: "2025-05",
      expenses: 900,
      netIncome: 9999,
    });
    expect(sumTrailing12NetIncome(profitLossRows)).toBe(410);
  });
});

describe("buildLiveDashboardTrendData", () => {
  it("aggregates imported dashboard rows by period", () => {
    const trendData = buildLiveDashboardTrendData([
      { provider: "Dr. Adams", period: "2026-06", production: 1000, collections: 800 },
      { provider: "Dr. Lee", period: "2026-05", production: 900, collections: 700 },
      { provider: "Dr. Adams", period: "2026-06", production: 500, collections: 450 },
    ]);

    expect(trendData).toEqual([
      { date: "2026-05", production: 900, collections: 700 },
      { date: "2026-06", production: 1500, collections: 1250 },
    ]);
  });
});

describe("buildLiveProviderProduction", () => {
  it("aggregates provider totals and sorts by production descending", () => {
    const providerRows = buildLiveProviderProduction([
      { provider: "Dr. Lee", production: 500, collections: 450 },
      { provider: "Dr. Adams", production: 1200, collections: 1100 },
      { provider: "Dr. Lee", production: 600, collections: 550 },
    ]);

    expect(providerRows).toEqual([
      { provider: "Dr. Adams", production: 1200, collections: 1100 },
      { provider: "Dr. Lee", production: 1100, collections: 1000 },
    ]);
  });
});

describe("buildFinancialSummaryProviderProduction", () => {
  it("aggregates verified provider rows from the shared financial summary", () => {
    expect(
      buildFinancialSummaryProviderProduction({
        latestAr: null,
        monthlyKpis: [],
        trailing12Months: [],
        calendarYearKpis: [],
        fourYearMonthlyKpis: [],
        providerProduction: [
          { provider: "Dr. Lee", production: 500, collections: 450 },
          { provider_name: "Dr. Adams", production_amount: 1200, collection_amount: 1100 },
          { provider: "Dr. Lee", production: 600, collections: 550 },
        ],
        topAdaCodes: [],
      } as const),
    ).toEqual([
      { provider: "Dr. Adams", production: 1200, collections: 1100 },
      { provider: "Dr. Lee", production: 1100, collections: 1000 },
    ]);
  });
});

describe("buildLiveInsurancePatientTotals", () => {
  it("sums insurance and patient payments from imported rows", () => {
    expect(
      buildLiveInsurancePatientTotals([
        { insurance: 300, patient: 200 },
        { insurance: "150", patient: "50" },
      ]),
    ).toEqual({ insurance: 450, patient: 250 });
  });
});

describe("buildFinancialSummaryInsurancePatientTotals", () => {
  it("sums insurance and patient collections from verified provider rows", () => {
    expect(
      buildFinancialSummaryInsurancePatientTotals({
        latestAr: null,
        monthlyKpis: [],
        trailing12Months: [],
        calendarYearKpis: [],
        fourYearMonthlyKpis: [],
        providerProduction: [
          { provider: "Dr. Lee", insurance: 300, patient: 200 },
          { provider: "Dr. Adams", insurance: "150", patient: "50" },
        ],
        topAdaCodes: [],
      } as const),
    ).toEqual({ insurance: 450, patient: 250 });
  });
});

describe("verified QuickBooks dashboard helpers", () => {
  it("maps expense categories and monthly expense rows from the shared financial summary", () => {
    expect(
      buildQuickBooksExpenseCategoryData({
        latestAr: null,
        monthlyKpis: [],
        trailing12Months: [],
        calendarYearKpis: [],
        fourYearMonthlyKpis: [],
        providerProduction: [],
        topAdaCodes: [],
        quickBooksExpenseCategories: [
          { expense_category: "Supplies", total_amount: 300 },
          { account_name: "Payroll", total_amount: 1800 },
        ],
        quickBooksProfitLossSummary: [{ year_month: "2026-06", expense_total: 3000, net_income: 1200 }],
      } as const),
    ).toEqual([
      { category: "Payroll", amount: 1800, percent: 60 },
      { category: "Supplies", amount: 300, percent: 10 },
    ]);

    expect(
      buildQuickBooksMonthlyExpenseTrendData([
        { year_month: "2026-05", expense_total: 900 },
        { year_month: "2026-06", expense_total: "1200" },
      ]),
    ).toEqual([
      { date: "2026-05", expenses: 900 },
      { date: "2026-06", expenses: 1200 },
    ]);
  });
});

describe("buildDashboardSummaryFromFinancialSummary", () => {
  it("maps verified summary values from the latest month instead of heuristics", () => {
    const summary = buildDashboardSummaryFromFinancialSummary({
      generatedAt: "2026-06-22T10:00:00Z",
      latestSoftDentRefreshAt: "2026-06-22T09:30:00Z",
      dataFreshnessStatus: "fresh",
      latestAr: {
        as_of_date: "2026-06-22",
        total_ar: 12000,
        insurance_ar: 5000,
        patient_ar: 7000,
        current_balance: 6000,
        balance_30: 3000,
        balance_60: 2000,
        balance_90: 1000,
        credit_balance: 0,
      },
      monthlyKpis: [
        { year_month: "2026-05", gross_production: 1000, collections: 800, collection_rate: 80 },
        { year_month: "2026-06", gross_production: 2500, collections: 2100, collection_rate: 84 },
      ],
      trailing12Months: [],
      calendarYearKpis: [],
      fourYearMonthlyKpis: [],
      providerProduction: [],
      topAdaCodes: [],
      quickBooksExpenseCategories: [
        { expense_category: "Supplies", total_amount: 300 },
        { expense_category: "Payroll", total_amount: 1800 },
      ],
      quickBooksProfitLossSummary: [
        { year_month: "2026-05", income_total: 4000, expense_total: 2600, net_income: 1400 },
        { year_month: "2026-06", income_total: 5100, expense_total: 3200, net_income: 1900 },
      ],
    } as const);

    expect(summary).toEqual({
      monthProduction: 2500,
      monthCollections: 2100,
      collectionPercent: 84,
      monthIncome: 5100,
      monthExpenses: 3200,
      estimatedNetIncome: 1900,
      topExpenseCategory: "Payroll",
      totalAR: 12000,
      ar0to30: 6000,
      ar31to60: 3000,
      ar61to90: 2000,
      arOver90: 1000,
      lastImportAt: "2026-06-22T09:30:00Z",
      lastRefreshedAt: "2026-06-22T09:30:00Z",
      isStale: false,
    });
  });

  it("returns null when no verified metrics are available", () => {
    expect(
      buildDashboardSummaryFromFinancialSummary({
        latestAr: null,
        monthlyKpis: [],
        trailing12Months: [],
        calendarYearKpis: [],
        fourYearMonthlyKpis: [],
        providerProduction: [],
        topAdaCodes: [],
      } as const),
    ).toBeNull();
  });
});

describe("buildArOver90AlertMessage", () => {
  it("returns a verified warning only when the shared summary has aged receivables over 90 days", () => {
    expect(
      buildArOver90AlertMessage({
        monthProduction: 1,
        monthCollections: 1,
        collectionPercent: 1,
        monthIncome: 1,
        monthExpenses: 1,
        estimatedNetIncome: 1,
        topExpenseCategory: "Payroll",
        totalAR: 12000,
        ar0to30: 6000,
        ar31to60: 3000,
        ar61to90: 2000,
        arOver90: 1000,
        lastImportAt: "2026-06-22T09:30:00Z",
        lastRefreshedAt: "2026-06-22T09:30:00Z",
        isStale: false,
      }),
    ).toBe("Verified A/R over 90 days still needs follow-up: $1,000.");

    expect(buildArOver90AlertMessage(null)).toBeNull();
    expect(
      buildArOver90AlertMessage({
        monthProduction: 1,
        monthCollections: 1,
        collectionPercent: 1,
        monthIncome: 1,
        monthExpenses: 1,
        estimatedNetIncome: 1,
        topExpenseCategory: "Payroll",
        totalAR: 12000,
        ar0to30: 6000,
        ar31to60: 3000,
        ar61to90: 2000,
        arOver90: 0,
        lastImportAt: "2026-06-22T09:30:00Z",
        lastRefreshedAt: "2026-06-22T09:30:00Z",
        isStale: false,
      }),
    ).toBeNull();
  });
});
