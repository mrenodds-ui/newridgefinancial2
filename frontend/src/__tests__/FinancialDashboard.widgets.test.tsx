import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { FinancialSummaryResponse } from "../api/client";
import { fetchFinancialSummary } from "../api/client";
import FinancialDashboard from "../components/dashboard/FinancialDashboard";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    fetchFinancialSummary: vi.fn(),
  };
});

vi.mock("../hooks/useAuthSession", () => ({
  useAuthSession: () => ({
    error: null,
    isAuthenticated: true,
    isLoading: false,
    isSessionVerified: true,
    sessionStatusCode: 200,
  }),
}));

vi.mock("../components/dashboard/CurrencyLineChart", () => ({
  CurrencyLineChart: () => <div data-testid="currency-line-chart" />,
}));

vi.mock("../components/dashboard/CurrencyBarChart", () => ({
  CurrencyBarChart: () => <div data-testid="currency-bar-chart" />,
}));

vi.mock("../components/dashboard/ARAgingBarChart", () => ({
  ARAgingBarChart: () => <div data-testid="ar-aging-chart" />,
}));

vi.mock("../components/dashboard/HorizontalExpenseBarChart", () => ({
  HorizontalExpenseBarChart: () => <div data-testid="expense-bar-chart" />,
}));

function buildFinancialSummary(): FinancialSummaryResponse {
  const trailing12Months = Array.from({ length: 12 }, (_, index) => ({
    year_month: `2026-${String(index + 1).padStart(2, "0")}`,
    gross_production: 100,
    net_production: 90,
    collections: 50,
    collection_rate: 50,
  }));

  const quickBooksProfitLossSummary = [
    { year_month: "2026-05", income_total: 4000, expense_total: 2600, net_income: 1400 },
    { year_month: "2026-06", income_total: 5100, expense_total: 3200, net_income: 1900 },
  ];

  return {
    generatedAt: "2026-06-22T10:00:00Z",
    latestSoftDentRefreshAt: "2026-06-22T09:45:00Z",
    dataFreshnessStatus: "fresh",
    sourceReview: {
      quickBooks: {
        sourceSystem: "quickbooks",
        status: "available",
        summary: "QuickBooks import is current.",
        confidenceLabel: "verified",
        reviewRequired: false,
        reviewFlags: [],
        lastVerifiedAt: "2026-06-22T09:45:00Z",
      },
      softDent: {
        sourceSystem: "softdent",
        status: "available",
        summary: "SoftDent dashboard export is current.",
        confidenceLabel: "verified",
        reviewRequired: false,
        reviewFlags: [],
        lastVerifiedAt: "2026-06-22T09:45:00Z",
      },
      softDentClaims: {
        sourceSystem: "softdent_claims",
        status: "available",
        summary: "Claims exports are current.",
        confidenceLabel: "verified",
        reviewRequired: false,
        reviewFlags: [],
        lastVerifiedAt: "2026-06-22T09:45:00Z",
      },
    },
    softDentCoverage: null,
    softDentCoverageMetrics: {
      trueOutstandingClaims: null,
      unsubmittedClaims: null,
      insuranceIncome: null,
      insurancePaymentDistribution: null,
      insuranceCheckDistribution: null,
      treatmentPlans: {
        label: "Treatment Plans",
        available: true,
        sourceFile: "treatment_plan_summary.csv",
        sourceBackend: "csv",
        modifiedAtUtc: "2026-06-22T09:40:00Z",
        rowCount: 18,
        itemCount: 18,
        totalAmount: 48200,
        lastPeriod: "2026-06",
        summary: "Pending treatment plans are available.",
        breakdown: [],
      },
      paymentPlans: {
        label: "Payment Plans",
        available: true,
        sourceFile: "payment_plans.csv",
        sourceBackend: "csv",
        modifiedAtUtc: "2026-06-22T09:40:00Z",
        rowCount: 6,
        itemCount: 6,
        totalAmount: 9500,
        lastPeriod: "2026-06",
        summary: "Payment plans are available.",
        breakdown: [],
      },
    },
    claimsSummary: {
      available: true,
      true_outstanding_claims_amount: 12401,
      true_outstanding_claims_count: 9,
      unsubmitted_claims_amount: 3840,
      unsubmitted_claims_count: 4,
      top_outstanding_payers: [{ label: "Delta Dental", amount: 7100, count: 4 }],
      top_unsubmitted_payers: [{ label: "Cigna", amount: 1640, count: 2 }],
    },
    lastRefreshed: "2026-06-22T09:50:00Z",
    latestDailyKpi: null,
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
      { year_month: "2026-05", gross_production: 100, net_production: 80, collections: 50, collection_rate: 50 },
      { year_month: "2026-06", gross_production: 2500, net_production: 700, collections: 2100, collection_rate: 84 },
    ],
    trailing12Months,
    calendarYearKpis: trailing12Months,
    fourYearMonthlyKpis: trailing12Months,
    providerProduction: [
      {
        provider: "Entire Practice",
        production: 7300,
        collections: 6400,
        insurance: 4600,
        patient: 1800,
      },
    ],
    topAdaCodes: [],
    quickBooksStatus: {
      status: "ok",
      message: "ready",
      lastCheckedAtUtc: "2026-06-22T09:45:00Z",
      lastImportedAtUtc: "2026-06-22T09:40:00Z",
      rowCounts: { bills: 14, expenses: 28 },
    },
    quickBooksExpenseCategories: [
      { expense_category: "Supplies", total_amount: 300 },
      { account_name: "Payroll", total_amount: 1800 },
    ],
    quickBooksMonthlyExpenses: [
      { year_month: "2026-05", expense_total: 2600 },
      { year_month: "2026-06", expense_total: 3200 },
    ],
    quickBooksProfitLossSummary,
    quickBooksEbitdaCandidates: quickBooksProfitLossSummary,
    dataFreshnessWarnings: [],
    currentMonthProduction: { year_month: "2026-06", gross_production: 2500, collections: 2100, collection_rate: 84 },
    currentYearProduction: { year_month: "2026", gross_production: 1000, net_production: 780, collections: 700, collection_rate: 70 },
  };
}

function buildFinancialSummaryWithIssues(): FinancialSummaryResponse {
  const summary = buildFinancialSummary();
  const sourceReview = summary.sourceReview!;
  const softDentCoverageMetrics = summary.softDentCoverageMetrics!;
  const claimsSummary = summary.claimsSummary!;
  const quickBooksStatus = summary.quickBooksStatus!;

  return {
    ...summary,
    dataFreshnessStatus: "stale",
    sourceReview: {
      ...sourceReview,
      quickBooks: {
        ...sourceReview.quickBooks!,
        status: "limited",
        summary: "QuickBooks import needs review.",
        confidenceLabel: "review suggested",
        reviewRequired: true,
        reviewFlags: ["stale import"],
      },
      softDentClaims: {
        ...sourceReview.softDentClaims!,
        status: "limited",
        summary: "Claims exports need review.",
        confidenceLabel: "manual review",
        reviewRequired: true,
        reviewFlags: ["stale export"],
      },
    },
    softDentCoverageMetrics: {
      ...softDentCoverageMetrics,
      treatmentPlans: {
        ...softDentCoverageMetrics.treatmentPlans!,
        available: false,
        itemCount: 0,
        totalAmount: 0,
        summary: "Treatment plan exports are missing.",
      },
      paymentPlans: {
        ...softDentCoverageMetrics.paymentPlans!,
        available: false,
        itemCount: 0,
        totalAmount: 0,
        summary: "Payment plan exports are missing.",
      },
    },
    claimsSummary: {
      ...claimsSummary,
      available: false,
      true_outstanding_claims_amount: 0,
      true_outstanding_claims_count: 0,
      unsubmitted_claims_amount: 0,
      unsubmitted_claims_count: 0,
      top_outstanding_payers: [],
      top_unsubmitted_payers: [],
    },
    quickBooksStatus: {
      ...quickBooksStatus,
      status: "error",
      message: "QuickBooks import needs attention.",
      rowCounts: {},
    },
  };
}

function buildFinancialSummaryWithImportWidgetFeed(): FinancialSummaryResponse {
  return {
    ...buildFinancialSummary(),
    widgetFeed: {
      manager: "Import cache",
      run_id: "import-run-1",
      generated_at: "2026-06-24T12:00:00Z",
      received_at: "2026-06-24T12:00:05Z",
      widgets: {
        practice_financial_overview: {
          title: "Practice Financial Overview",
          status: "SUCCESS",
          metrics: {
            monthly_revenue: 5100,
            monthly_net_income: 1900,
            collection_rate: 84,
          },
        },
        accounts_payable_automation: {
          title: "Accounts Payable Automation",
          status: "SUCCESS",
          metrics: {
            expense_total: 3200,
          },
        },
        smart_claims_and_receivables: {
          title: "Smart Claims & Receivables",
          status: "SUCCESS",
          metrics: {
            outstanding_claim_count: 9,
            outstanding_claim_amount: 12401,
            unsubmitted_claim_count: 4,
            accounts_receivable_total: 12000,
          },
        },
        care_delivery_performance: {
          title: "Care Delivery Performance",
          status: "SUCCESS",
          metrics: {
            provider_count: 1,
            patient_balance_total: 7000,
          },
        },
      },
      sources: {
        quickbooks: { last_status: "SUCCESS", origin: "imports" },
        softdent: { last_status: "SUCCESS", origin: "imports" },
      },
      jobs: {
        import_cache_refresh: { status: "SUCCESS" },
        widget_publish: { status: "SUCCESS" },
      },
    },
  };
}

function buildFinancialSummaryWithHalWidgetFeed(): FinancialSummaryResponse {
  return {
    ...buildFinancialSummary(),
    widgetFeed: {
      manager: "HAL 9000",
      run_id: "run-123",
      generated_at: "2026-06-23T12:10:00Z",
      received_at: "2026-06-23T12:10:05Z",
      widgets: {
        practice_financial_overview: {
          title: "Practice Financial Overview",
          status: "SUCCESS",
          metrics: {
            monthly_revenue: 155000,
            monthly_net_income: 62000,
            collection_rate: 87.03,
          },
        },
        accounts_payable_automation: {
          title: "Accounts Payable Automation",
          status: "SUCCESS",
          metrics: {
            open_bills_total: 12850,
            expense_total: 93000,
          },
        },
        smart_claims_and_receivables: {
          title: "Smart Claims & Receivables",
          status: "DEGRADED",
          metrics: {
            outstanding_claim_count: 34,
            outstanding_claim_amount: 22110,
            unsubmitted_claim_count: 9,
            accounts_receivable_total: 21700,
          },
        },
        care_delivery_performance: {
          title: "Care Delivery Performance",
          status: "SUCCESS",
          metrics: {
            provider_count: 1,
            patient_count: 642,
            patient_balance_total: 9100,
          },
        },
      },
      sources: {
        quickbooks_online: { last_status: "SUCCESS" },
        softdent: { last_status: "SUCCESS" },
      },
      jobs: {
        quickbooks_extract: { status: "SUCCESS" },
        softdent_extract: { status: "SUCCESS" },
        widget_publish: { status: "SUCCESS" },
      },
    },
  };
}

function renderDashboard() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <FinancialDashboard />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  vi.clearAllMocks();
  vi.restoreAllMocks();
});

describe("FinancialDashboard widget deck", () => {
  it("renders the requested finance widgets from the verified summary payload", async () => {
    vi.mocked(fetchFinancialSummary).mockResolvedValue(buildFinancialSummary());

    renderDashboard();

    await screen.findByRole("heading", { name: "New Ridge Family Financial" });

    expect(screen.getByRole("heading", { name: "Arrange your home dashboard around the widgets you actually use" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Customize layout" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reset layout" })).toBeInTheDocument();
    expect(screen.getByText("Case Acceptance & Financing")).toBeInTheDocument();
    expect(screen.getByText("AP Automation")).toBeInTheDocument();
    expect(screen.getByText("Smart Claims & Invoicing")).toBeInTheDocument();
    expect(screen.getByText("Real-Time Revenue Analytics")).toBeInTheDocument();
    expect(screen.getByText("AI Follow-up & Collections")).toBeInTheDocument();
    expect(screen.getByText("$48,200 pending plan value")).toBeInTheDocument();
    expect(screen.getByText("$12,401 insurance receivables")).toBeInTheDocument();
    expect(screen.getByText("Delta Dental")).toBeInTheDocument();
    expect(screen.getByText("Practice production")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open SoftDent plans" })).toHaveAttribute("href", "/softdent");
    expect(screen.getByRole("link", { name: "Review A/R follow-up" })).toHaveAttribute("href", "/ar");
    expect(screen.getByRole("link", { name: "Review QuickBooks feed" })).toHaveAttribute("href", "/quickbooks");
    expect(screen.getByRole("link", { name: "Open expense analysis" })).toHaveAttribute("href", "/expenses");
    expect(screen.getByRole("link", { name: "Open Claims Workbench" })).toHaveAttribute("href", "/claims-workbench");
    expect(screen.getByRole("link", { name: "Review A/R aging" })).toHaveAttribute("href", "/ar");
    expect(screen.getByRole("link", { name: "View revenue trends" })).toHaveAttribute("href", "/trends");
    expect(screen.getByRole("link", { name: "Open QuickBooks summary" })).toHaveAttribute("href", "/quickbooks");
    expect(screen.getByRole("link", { name: "Launch HAL follow-up" })).toHaveAttribute("href", "/dashboard/hal");
    expect(screen.getByRole("link", { name: "Open collections page" })).toHaveAttribute("href", "/ar");
  });

  it("switches widget actions when source coverage is missing or stale", async () => {
    vi.mocked(fetchFinancialSummary).mockResolvedValue(buildFinancialSummaryWithIssues());

    renderDashboard();

    await screen.findByRole("heading", { name: "New Ridge Family Financial" });

    expect(screen.getByRole("link", { name: "Open import settings" })).toHaveAttribute("href", "/settings");
    expect(screen.getByRole("link", { name: "Open SoftDent plans" })).toHaveAttribute("href", "/softdent");
    expect(screen.getByRole("link", { name: "Fix QuickBooks import" })).toHaveAttribute("href", "/settings");
    expect(screen.getByRole("link", { name: "Open QuickBooks summary" })).toHaveAttribute("href", "/quickbooks");
    expect(screen.getByRole("link", { name: "View claims source status" })).toHaveAttribute("href", "/softdent");
    expect(screen.getByRole("link", { name: "Open Claims Workbench" })).toHaveAttribute("href", "/claims-workbench");
    expect(screen.getByRole("link", { name: "Refresh data settings" })).toHaveAttribute("href", "/settings");
    expect(screen.getByRole("link", { name: "Inspect QuickBooks feed" })).toHaveAttribute("href", "/quickbooks");
    expect(screen.getByRole("link", { name: "Review claims readiness" })).toHaveAttribute("href", "/claims-workbench");
    expect(screen.getByRole("link", { name: "Open collections page" })).toHaveAttribute("href", "/ar");
  });

  it("prefers SUCCESS HAL-published widget values when the backend exposes a widget feed", async () => {
    vi.mocked(fetchFinancialSummary).mockResolvedValue(buildFinancialSummaryWithHalWidgetFeed());

    renderDashboard();

    await screen.findByRole("heading", { name: "New Ridge Family Financial" });

    expect(screen.getByText("$9,100 patient balance in active care")).toBeInTheDocument();
    expect(screen.getByText("$12,850 open bills staged")).toBeInTheDocument();
    expect(screen.getByText("$155,000 revenue snapshot")).toBeInTheDocument();
    expect(screen.getAllByText("HAL feed").length).toBeGreaterThan(0);
    expect(screen.getByText("$12,401 insurance receivables")).toBeInTheDocument();
    expect(screen.queryByText("$22,110 insurance receivables")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Review QuickBooks feed" })).toHaveAttribute("href", "/quickbooks");
    expect(screen.getByRole("link", { name: "Open collections page" })).toHaveAttribute("href", "/ar");
  });

  it("renders import-cache SUCCESS widget values in finance and operations cards", async () => {
    vi.mocked(fetchFinancialSummary).mockResolvedValue(buildFinancialSummaryWithImportWidgetFeed());

    renderDashboard();

    await screen.findByRole("heading", { name: "New Ridge Family Financial" });

    expect(screen.getByText("$5,100 revenue snapshot")).toBeInTheDocument();
    expect(screen.getByText("$12,401 insurance receivables")).toBeInTheDocument();
    expect(screen.getByText("$7,000 patient balance in active care")).toBeInTheDocument();
    expect(screen.getAllByText("Import cache").length).toBeGreaterThan(0);
    expect(screen.getAllByText("QuickBooks").length).toBeGreaterThan(0);
    expect(screen.getAllByText("SoftDent").length).toBeGreaterThan(0);
  });

  it("does not override local KPI widgets when the widget feed is DEGRADED or FAILED", async () => {
    vi.mocked(fetchFinancialSummary).mockResolvedValue({
      ...buildFinancialSummaryWithHalWidgetFeed(),
      widgetFeed: {
        ...buildFinancialSummaryWithHalWidgetFeed().widgetFeed!,
        widgets: {
          ...buildFinancialSummaryWithHalWidgetFeed().widgetFeed!.widgets,
          practice_financial_overview: {
            title: "Practice Financial Overview",
            status: "FAILED",
            metrics: {
              monthly_revenue: 999999,
              monthly_net_income: 888888,
              collection_rate: 12,
            },
          },
          smart_claims_and_receivables: {
            title: "Smart Claims & Receivables",
            status: "DEGRADED",
            metrics: {
              outstanding_claim_count: 99,
              outstanding_claim_amount: 99999,
              unsubmitted_claim_count: 88,
              accounts_receivable_total: 77777,
            },
          },
        },
      },
    });

    renderDashboard();

    await screen.findByRole("heading", { name: "New Ridge Family Financial" });

    expect(screen.getByText("Practice production")).toBeInTheDocument();
    expect(screen.queryByText("$999,999 revenue snapshot")).not.toBeInTheDocument();
    expect(screen.getByText("$12,401 insurance receivables")).toBeInTheDocument();
    expect(screen.queryByText("$99,999 insurance receivables")).not.toBeInTheDocument();
  });

  it("does not show SUCCESS widget receivables when latestAr is missing", async () => {
    vi.mocked(fetchFinancialSummary).mockResolvedValue({
      ...buildFinancialSummaryWithImportWidgetFeed(),
      latestAr: null,
    });

    renderDashboard();

    await screen.findByRole("heading", { name: "New Ridge Family Financial" });

    expect(screen.getByText("$12,401 insurance receivables")).toBeInTheDocument();
    expect(screen.queryByText("$7,000 patient balance in active care")).not.toBeInTheDocument();
    expect(screen.queryByText("$12,000 receivables queue")).not.toBeInTheDocument();

    const smartClaimsCard = screen.getByRole("heading", { name: "Smart Claims & Invoicing" }).closest("article");
    expect(smartClaimsCard).not.toBeNull();
    expect(smartClaimsCard).toHaveTextContent("Outstanding");
    expect(smartClaimsCard).toHaveTextContent("9");
    expect(smartClaimsCard).toHaveTextContent("Receivables");
    expect(smartClaimsCard).toHaveTextContent("Unavailable");
    expect(smartClaimsCard).not.toHaveTextContent("$12,000");
  });

  it("does not show SUCCESS widget receivables when latestAr is marked unavailable", async () => {
    vi.mocked(fetchFinancialSummary).mockResolvedValue({
      ...buildFinancialSummaryWithImportWidgetFeed(),
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
        available: false,
      } as FinancialSummaryResponse["latestAr"],
    });

    renderDashboard();

    await screen.findByRole("heading", { name: "New Ridge Family Financial" });

    expect(screen.queryByText("$7,000 patient balance in active care")).not.toBeInTheDocument();
    expect(screen.queryByText("$12,000 receivables queue")).not.toBeInTheDocument();

    const smartClaimsCard = screen.getByRole("heading", { name: "Smart Claims & Invoicing" }).closest("article");
    expect(smartClaimsCard).toHaveTextContent("Unavailable");
    expect(smartClaimsCard).not.toHaveTextContent("$12,000");
    expect(smartClaimsCard).toHaveTextContent("9");
  });

  it("shows SUCCESS widget receivables when explicit SoftDent A/R is available", async () => {
    vi.mocked(fetchFinancialSummary).mockResolvedValue({
      ...buildFinancialSummaryWithImportWidgetFeed(),
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
        available: true,
      } as FinancialSummaryResponse["latestAr"],
    });

    renderDashboard();

    await screen.findByRole("heading", { name: "New Ridge Family Financial" });

    expect(screen.getByText("$7,000 patient balance in active care")).toBeInTheDocument();
    expect(screen.getByText("$12,000 receivables queue")).toBeInTheDocument();

    const smartClaimsCard = screen.getByRole("heading", { name: "Smart Claims & Invoicing" }).closest("article");
    expect(smartClaimsCard).toHaveTextContent("$12,000");
  });

  it("allows real zero receivables from SUCCESS widgets when latestAr is explicitly available", async () => {
    vi.mocked(fetchFinancialSummary).mockResolvedValue({
      ...buildFinancialSummaryWithImportWidgetFeed(),
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
      widgetFeed: {
        ...buildFinancialSummaryWithImportWidgetFeed().widgetFeed!,
        widgets: {
          ...buildFinancialSummaryWithImportWidgetFeed().widgetFeed!.widgets,
          smart_claims_and_receivables: {
            title: "Smart Claims & Receivables",
            status: "SUCCESS",
            metrics: {
              outstanding_claim_count: 9,
              outstanding_claim_amount: 12401,
              unsubmitted_claim_count: 4,
              accounts_receivable_total: 0,
            },
          },
          care_delivery_performance: {
            title: "Care Delivery Performance",
            status: "SUCCESS",
            metrics: {
              provider_count: 1,
              patient_balance_total: 0,
            },
          },
        },
      },
    });

    renderDashboard();

    await screen.findByRole("heading", { name: "New Ridge Family Financial" });

    expect(screen.getByText("$0 receivables queue")).toBeInTheDocument();
    expect(screen.getByText("$0 patient balance in active care")).toBeInTheDocument();

    const smartClaimsCard = screen.getByRole("heading", { name: "Smart Claims & Invoicing" }).closest("article");
    expect(smartClaimsCard).toHaveTextContent("$0");
    expect(smartClaimsCard).toHaveTextContent("9");
  });
});