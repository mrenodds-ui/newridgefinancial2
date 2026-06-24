import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { FinancialSummaryResponse } from "../api/client";
import { fetchFinancialSummary } from "../api/client";
import ARCollectionsPage from "../pages/ARCollectionsPage";

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

function buildBaseFinancialSummary(overrides: Partial<FinancialSummaryResponse> = {}): FinancialSummaryResponse {
  const trailing12Months = Array.from({ length: 12 }, (_, index) => ({
    year_month: `2026-${String(index + 1).padStart(2, "0")}`,
    gross_production: 100,
    net_production: 90,
    collections: 50,
    collection_rate: 50,
  }));

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
    latestAr: null,
    monthlyKpis: [
      { year_month: "2026-06", gross_production: 900, net_production: 700, collections: 650, collection_rate: 72 },
    ],
    trailing12Months,
    calendarYearKpis: trailing12Months,
    fourYearMonthlyKpis: trailing12Months,
    providerProduction: [],
    topAdaCodes: [],
    quickBooksStatus: null,
    quickBooksExpenseCategories: [],
    quickBooksMonthlyExpenses: [],
    quickBooksProfitLossSummary: [],
    quickBooksEbitdaCandidates: [],
    dataFreshnessWarnings: [],
    currentMonthProduction: null,
    currentYearProduction: null,
    ...overrides,
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

describe("ARCollectionsPage", () => {
  it("shows unavailable A/R copy when latestAr is missing", async () => {
    vi.mocked(fetchFinancialSummary).mockResolvedValue(buildBaseFinancialSummary({ latestAr: null }));

    renderWithQuery(<ARCollectionsPage />);

    await screen.findByText("A/R & Collections");

    expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0);
    expect(screen.getByText("No SoftDent A/R export available.")).toBeInTheDocument();
    expect(screen.queryByText("$0")).not.toBeInTheDocument();
  });

  it("shows unavailable A/R copy when latestAr is marked unavailable", async () => {
    vi.mocked(fetchFinancialSummary).mockResolvedValue(
      buildBaseFinancialSummary({
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
          available: false,
        } as FinancialSummaryResponse["latestAr"],
      }),
    );

    renderWithQuery(<ARCollectionsPage />);

    await screen.findByText("A/R & Collections");

    expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0);
    expect(screen.getByText("No SoftDent A/R export available.")).toBeInTheDocument();
    expect(screen.queryByText("$3,000")).not.toBeInTheDocument();
    expect(screen.queryByText("$0")).not.toBeInTheDocument();
  });

  it("renders explicit SoftDent A/R values when available", async () => {
    vi.mocked(fetchFinancialSummary).mockResolvedValue(
      buildBaseFinancialSummary({
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
          available: true,
        } as FinancialSummaryResponse["latestAr"],
      }),
    );

    renderWithQuery(<ARCollectionsPage />);

    await screen.findByText("A/R & Collections");

    expect(screen.getAllByText("$3,000").length).toBeGreaterThan(0);
    expect(screen.getAllByText("$700").length).toBeGreaterThan(0);
    expect(screen.getAllByText("$200").length).toBeGreaterThan(0);
    expect(screen.getByTestId("ar-aging-chart")).toBeInTheDocument();
    expect(screen.queryByText("Unavailable")).not.toBeInTheDocument();
  });

  it("renders $0 only when explicit available SoftDent A/R is truly zero", async () => {
    vi.mocked(fetchFinancialSummary).mockResolvedValue(
      buildBaseFinancialSummary({
        latestAr: {
          as_of_date: "2026-06-22",
          total_ar: 0,
          insurance_ar: 0,
          patient_ar: 0,
          current_balance: 0,
          balance_30: 0,
          balance_60: 0,
          balance_90: 0,
          credit_balance: 0,
          available: true,
        } as FinancialSummaryResponse["latestAr"],
      }),
    );

    renderWithQuery(<ARCollectionsPage />);

    await screen.findByText("A/R & Collections");

    expect(screen.getAllByText("$0").length).toBeGreaterThan(0);
    expect(screen.queryByText("Unavailable")).not.toBeInTheDocument();
    expect(screen.getByTestId("ar-aging-chart")).toBeInTheDocument();
  });
});
