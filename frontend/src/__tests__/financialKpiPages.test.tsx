import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { FinancialSummaryResponse } from "../api/client";
import { fetchFinancialSummary } from "../api/client";
import ARCollectionsPage from "../pages/ARCollectionsPage";
import HalLandingPage from "../pages/HalLandingPage";
import SoftDentPage from "../pages/SoftDentPage";
import TrendsPage from "../pages/TrendsPage";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    fetchFinancialSummary: vi.fn(),
  };
});

vi.mock("../components/dashboard/CurrencyLineChart", () => ({
  CurrencyLineChart: () => <div data-testid="currency-line-chart" />,
}));

vi.mock("../components/dashboard/ARAgingBarChart", () => ({
  ARAgingBarChart: () => <div data-testid="ar-aging-chart" />,
}));

vi.mock("../components/dashboard/SoftDentCoveragePanel", () => ({
  SoftDentCoveragePanel: () => <div data-testid="softdent-coverage-panel" />,
}));

vi.mock("../components/dashboard/SourceReviewContent", () => ({
  SourceReviewContent: () => <div data-testid="source-review-content" />,
}));

vi.mock("../components/dashboard/TransactionFeedStatusNotice", () => ({
  TransactionFeedStatusNotice: () => <div data-testid="transaction-feed-status" />,
}));

function buildFinancialSummary(): FinancialSummaryResponse {
  const trailing12Months = Array.from({ length: 12 }, (_, index) => ({
    year_month: `2026-${String(index + 1).padStart(2, "0")}`,
    gross_production: 100,
    net_production: 90,
    collections: 50,
    collection_rate: 50,
  }));

  const fourYearMonthlyKpis = [
    { year_month: "2024-01", gross_production: 1000, net_production: 900, collections: 900, collection_rate: 90 },
    ...trailing12Months,
  ];

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
    fourYearMonthlyKpis,
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

function renderWithQuery(ui: React.ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.restoreAllMocks();
});

describe("financial KPI pages", () => {
  it("renders SoftDent current-month cards from the latest monthly KPI row", async () => {
    vi.mocked(fetchFinancialSummary).mockResolvedValue(buildFinancialSummary());

    renderWithQuery(<SoftDentPage />);

    await screen.findByText("SoftDent Financials");

    expect(screen.getByText("$900")).toBeInTheDocument();
    expect(screen.getByText("$700")).toBeInTheDocument();
    expect(screen.getByText("$650")).toBeInTheDocument();
    expect(screen.getByText("72%")).toBeInTheDocument();
    expect(screen.queryByText(/^\$100$/)).not.toBeInTheDocument();
  });

  it("renders HAL landing KPIs from the latest monthly and profit-loss rows", async () => {
    vi.mocked(fetchFinancialSummary).mockResolvedValue(buildFinancialSummary());

    renderWithQuery(<HalLandingPage />);

    await screen.findByText("New Ridge Family Financial");

    expect(screen.getAllByText("$900").length).toBeGreaterThan(0);
    expect(screen.getByText("$650")).toBeInTheDocument();
    expect(screen.getByText("$300")).toBeInTheDocument();
    expect(screen.queryByText(/^\$100$/)).not.toBeInTheDocument();
  });

  it("renders Trends 12-month totals from trailing-12 data and QuickBooks net income", async () => {
    vi.mocked(fetchFinancialSummary).mockResolvedValue(buildFinancialSummary());

    renderWithQuery(<TrendsPage />);

    await screen.findByText("Trends");

    expect(screen.getByText("$1,200")).toBeInTheDocument();
    expect(screen.getByText("$600")).toBeInTheDocument();
    expect(screen.getByText("$410")).toBeInTheDocument();
    expect(screen.queryByText("$2,200")).not.toBeInTheDocument();
    expect(screen.queryByText("$10,119")).not.toBeInTheDocument();
  });

  it("renders A/R collection percentage from the latest monthly KPI row", async () => {
    vi.mocked(fetchFinancialSummary).mockResolvedValue(buildFinancialSummary());

    renderWithQuery(<ARCollectionsPage />);

    await screen.findByText("A/R & Collections");

    expect(screen.getByText("72%")).toBeInTheDocument();
    expect(screen.queryByText(/^50%$/)).not.toBeInTheDocument();
  });
});