import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { fetchFinancialSummary } from "../../api/client";
import { useDashboardData } from "../../context/DashboardDataContext";
import { useAuthSession } from "../../hooks/useAuthSession";
import {
  mockCaseAcceptance,
  mockExpenseCategories,
  mockInsurancePatientBreakdown,
  mockNoShowRate,
  mockPatientFlow,
  mockProviderProduction,
  mockTrendData,
} from "../../data/mockDashboardData";
import { LoadingSpinner } from "../LoadingSpinner";
import {
  buildArOver90AlertMessage,
  buildDashboardTrendData,
  buildDashboardSummaryFromFinancialSummary,
  buildFinancialSummaryInsurancePatientTotals,
  buildFinancialSummaryProviderProduction,
  buildProfitLossTrendData,
  buildQuickBooksExpenseCategoryData,
  buildQuickBooksMonthlyExpenseTrendData,
} from "./financialDashboardSummary";
import { ARAgingBarChart } from "./ARAgingBarChart";
import { CaseAcceptanceFunnel } from "./CaseAcceptanceFunnel";
import { CurrencyBarChart } from "./CurrencyBarChart";
import { CurrencyLineChart } from "./CurrencyLineChart";
import { CustomAlert } from "./CustomAlert";
import { HorizontalExpenseBarChart } from "./HorizontalExpenseBarChart";
import { InsurancePatientBreakdown } from "./InsurancePatientBreakdown";
import { NoShowRateChart } from "./NoShowRateChart";
import { PatientFlowChart } from "./PatientFlowChart";
import { ProductionCollectionsChart } from "./ProductionCollectionsChart";
import { ProviderPerformanceTable } from "./ProviderPerformanceTable";

const isDev = process.env.NODE_ENV === "development";

// Formatting utilities
function formatCurrency(value: number) {
  return value.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}
function formatCurrencyValue(value: number | null) {
  return value === null ? "Unavailable" : formatCurrency(value);
}
function formatPercent(value: number) {
  return `${Math.round(value)}%`;
}
function formatPercentValue(value: number | null) {
  return value === null ? "N/A" : formatPercent(value);
}
function formatDateTime(value: string | Date | null | undefined) {
  if (!value) {
    return "Unavailable";
  }

  const d = typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(d.getTime())) {
    return "Unavailable";
  }

  return d.toLocaleString();
}

function ChartUnavailableCard({ title, message }: { title: string; message: string }) {
  return (
    <div className="chart-card halfsize">
      <div className="chart-title">{title}</div>
      <div className="page-state-card page-state-card--info">{message}</div>
    </div>
  );
}

function FinancialDashboard() {
  const { dashboardData } = useDashboardData();
  const { error: authSessionError, isAuthenticated, isLoading: isAuthSessionLoading, isSessionVerified, sessionStatusCode } = useAuthSession();
  const financialSummaryQuery = useQuery({
    queryKey: ["financial-summary"],
    queryFn: fetchFinancialSummary,
    enabled: isSessionVerified,
  });
  const verifiedFinancialSummary = isSessionVerified ? financialSummaryQuery.data : undefined;
  const summary = useMemo(() => buildDashboardSummaryFromFinancialSummary(verifiedFinancialSummary), [verifiedFinancialSummary]);
  const hasImportPreviewData = dashboardData.length > 0;
  const showMockCharts = isDev && isSessionVerified && !hasImportPreviewData && !summary && !financialSummaryQuery.isPending;
  const trendData = useMemo(() => buildDashboardTrendData(verifiedFinancialSummary), [verifiedFinancialSummary]);
  const providerProduction = useMemo(() => buildFinancialSummaryProviderProduction(verifiedFinancialSummary), [verifiedFinancialSummary]);
  const insurancePatientTotals = useMemo(() => buildFinancialSummaryInsurancePatientTotals(verifiedFinancialSummary), [verifiedFinancialSummary]);
  const expenseCategoryData = useMemo(() => buildQuickBooksExpenseCategoryData(verifiedFinancialSummary), [verifiedFinancialSummary]);
  const monthlyExpenseTrend = useMemo(
    () => buildQuickBooksMonthlyExpenseTrendData(verifiedFinancialSummary?.quickBooksMonthlyExpenses),
    [verifiedFinancialSummary?.quickBooksMonthlyExpenses],
  );
  const netIncomeTrendData = useMemo(
    () => buildProfitLossTrendData(verifiedFinancialSummary?.quickBooksProfitLossSummary),
    [verifiedFinancialSummary?.quickBooksProfitLossSummary],
  );
  const hasTrendData = trendData.length > 0;
  const hasProviderProduction = providerProduction.length > 0;
  const hasInsurancePatientTotals = insurancePatientTotals.insurance > 0 || insurancePatientTotals.patient > 0;
  const hasExpenseCategoryData = expenseCategoryData.length > 0;
  const hasMonthlyExpenseTrend = monthlyExpenseTrend.length > 0;
  const hasNetIncomeTrendData = netIncomeTrendData.length > 0;
  const arOver90AlertMessage = useMemo(() => buildArOver90AlertMessage(summary), [summary]);
  const hasSessionVerificationError = isAuthenticated && !isSessionVerified && Boolean(authSessionError) && sessionStatusCode !== 401;
  const trendDataUnavailableMessage = isSessionVerified
    ? "Verified SoftDent production and collections trends are not available from the current backend summary yet."
    : hasSessionVerificationError
      ? "The dashboard session could not be verified right now."
      : "Sign in from the dashboard banner to load verified SoftDent trend data.";
  const expenseDataUnavailableMessage = isSessionVerified
    ? "Verified QuickBooks expense data is not available from the current backend summary yet."
    : hasSessionVerificationError
      ? "The dashboard session could not be verified right now."
      : "Sign in from the dashboard banner to load verified QuickBooks expense and net-income charts.";
  const summaryUnavailableMessage = isSessionVerified
    ? "Verified financial summary data is unavailable right now. Load the backend summary first, then return to the dashboard for live KPI cards and charts."
    : hasSessionVerificationError
      ? "The dashboard session could not be verified right now."
      : "Sign in from the dashboard banner to load the verified financial summary. Import-preview charts and CSV inspection remain available below.";

  if (isAuthSessionLoading && !hasImportPreviewData && !showMockCharts) {
    return (
      <main className="dashboard-page">
        <div className="dashboard-container">
          <LoadingSpinner label="Loading verified financial summary..." />
        </div>
      </main>
    );
  }

  if (isSessionVerified && financialSummaryQuery.isPending && !hasImportPreviewData && !showMockCharts) {
    return (
      <main className="dashboard-page">
        <div className="dashboard-container">
          <LoadingSpinner label="Loading verified financial summary..." />
        </div>
      </main>
    );
  }

  if (!summary && !hasImportPreviewData && !showMockCharts) {
    return (
      <main className="dashboard-page">
        <div className="dashboard-container">
          <header className="dashboard-header">
            <div>
              <h1 className="dashboard-title">New Ridge Family Financial</h1>
              <div className="dashboard-subtitle">SoftDent + QuickBooks financial overview</div>
            </div>
          </header>

          <section className="page-state-card page-state-card--info" aria-live="polite">
            {summaryUnavailableMessage}
          </section>
        </div>
      </main>
    );
  }

  return (
    <main className="dashboard-page">
      <div className="dashboard-container">
        <header className="dashboard-header">
          <div>
            <h1 className="dashboard-title">New Ridge Family Financial</h1>
            <div className="dashboard-subtitle">SoftDent + QuickBooks financial overview</div>
          </div>
          <div className="header-actions">
            <span className="badge badge-success">{summary?.isStale ? "Stale Summary" : summary ? "Verified Summary" : "Import Preview"}</span>
          </div>
        </header>

        <section className="status-toolbar" aria-label="Refresh and status toolbar">
          <div className="status-item">
            <span className="status-label">Last refreshed</span>
            <span className="status-value">{formatDateTime(summary?.lastRefreshedAt)}</span>
          </div>
          <div className="status-item">
            <span className="status-label">Preview CSV Rows</span>
            <span className="status-value">{dashboardData.length}</span>
          </div>
        </section>

        <section className="dashboard-summary-row" aria-label="Key financial metrics">
          {summary ? (
            <>
              <div className="dashboard-summary-card">
                <div className="dashboard-summary-card__title">Production / Collections</div>
                <div className="dashboard-kpi-main">{formatCurrencyValue(summary.monthProduction)}</div>
                <div className="dashboard-kpi-label">Month-to-date production</div>
                <div className="dashboard-kpi-support">
                  <span>
                    MTD Collections: <strong>{formatCurrencyValue(summary.monthCollections)}</strong>
                  </span>
                  <span>
                    Collection %: <strong>{formatPercentValue(summary.collectionPercent)}</strong>
                  </span>
                  <span>
                    Last import: <strong>{formatDateTime(summary.lastImportAt)}</strong>
                  </span>
                </div>
              </div>
              <div className="dashboard-summary-card">
                <div className="dashboard-summary-card__title">Expenses / Net Income</div>
                <div className="dashboard-kpi-main">{formatCurrencyValue(summary.monthExpenses)}</div>
                <div className="dashboard-kpi-label">Month-to-date expenses</div>
                <div className="dashboard-kpi-support">
                  <span>
                    MTD Income: <strong>{formatCurrencyValue(summary.monthIncome)}</strong>
                  </span>
                  <span>
                    Net Income: <strong>{formatCurrencyValue(summary.estimatedNetIncome)}</strong>
                  </span>
                  <span>
                    Top Expense: <strong>{summary.topExpenseCategory ?? "Unavailable"}</strong>
                  </span>
                </div>
              </div>
              <div className="dashboard-summary-card">
                <div className="dashboard-summary-card__title">A/R / Cash Health</div>
                <div className="dashboard-kpi-main">{formatCurrencyValue(summary.totalAR)}</div>
                <div className="dashboard-kpi-label">Total A/R</div>
                <div className="dashboard-kpi-support">
                  <span>
                    0–30: <strong>{formatCurrencyValue(summary.ar0to30)}</strong>
                  </span>
                  <span>
                    31–60: <strong>{formatCurrencyValue(summary.ar31to60)}</strong>
                  </span>
                  <span>
                    61–90: <strong>{formatCurrencyValue(summary.ar61to90)}</strong>
                  </span>
                  <span>
                    90+: <strong>{formatCurrencyValue(summary.arOver90)}</strong>
                  </span>
                </div>
              </div>
            </>
          ) : (
            <section className="page-state-card page-state-card--info" aria-live="polite">
              Verified KPI cards are unavailable right now. Import-preview charts and CSV inspection can still be used below.
            </section>
          )}
        </section>

        <section className="chart-grid chart-grid-halfsize">
          {showMockCharts ? (
            <>
              <div className="chart-card halfsize">
                <div className="chart-title">Production Trend</div>
                <div className="chart-body">
                  <CurrencyLineChart data={mockTrendData} lines={[{ dataKey: "production", name: "Production", color: "#D6B15E" }]} height={160} />
                </div>
              </div>
              <div className="chart-card halfsize">
                <div className="chart-title">Collections Trend</div>
                <div className="chart-body">
                  <CurrencyLineChart data={mockTrendData} lines={[{ dataKey: "collections", name: "Collections", color: "#78A86B" }]} height={160} />
                </div>
              </div>
              <div className="chart-card halfsize">
                <div className="chart-title">Production vs Collections</div>
                <div className="chart-body">
                  <ProductionCollectionsChart data={mockTrendData} />
                </div>
              </div>
              <div className="chart-card halfsize">
                <div className="chart-title">Expense Categories</div>
                <div className="chart-body">
                  <HorizontalExpenseBarChart data={mockExpenseCategories} height={160} />
                </div>
              </div>
              <div className="chart-card halfsize">
                <div className="chart-title">Monthly Expense Trend</div>
                <div className="chart-body">
                  <CurrencyBarChart data={mockTrendData} bars={[{ dataKey: "expenses", name: "Expenses", color: "#D89A2B" }]} height={160} />
                </div>
              </div>
              <div className="chart-card halfsize">
                <div className="chart-title">Net Income Trend</div>
                <div className="chart-body">
                  <CurrencyLineChart data={mockTrendData} lines={[{ dataKey: "netIncome", name: "Net Income", color: "#C7A24D" }]} height={160} />
                </div>
              </div>
            </>
          ) : (
            <>
              {hasTrendData ? (
                <>
                  <div className="chart-card halfsize">
                    <div className="chart-title">Production Trend</div>
                    <div className="chart-body">
                      <CurrencyLineChart data={trendData} lines={[{ dataKey: "production", name: "Production", color: "#D6B15E" }]} height={160} />
                    </div>
                  </div>
                  <div className="chart-card halfsize">
                    <div className="chart-title">Collections Trend</div>
                    <div className="chart-body">
                      <CurrencyLineChart data={trendData} lines={[{ dataKey: "collections", name: "Collections", color: "#78A86B" }]} height={160} />
                    </div>
                  </div>
                  <div className="chart-card halfsize">
                    <div className="chart-title">Production vs Collections</div>
                    <div className="chart-body">
                      <ProductionCollectionsChart data={trendData} />
                    </div>
                  </div>
                </>
              ) : (
                <>
                  <ChartUnavailableCard title="Production Trend" message={trendDataUnavailableMessage} />
                  <ChartUnavailableCard title="Collections Trend" message={trendDataUnavailableMessage} />
                  <ChartUnavailableCard title="Production vs Collections" message={trendDataUnavailableMessage} />
                </>
              )}
              {hasExpenseCategoryData ? (
                <div className="chart-card halfsize">
                  <div className="chart-title">Expense Categories</div>
                  <div className="chart-body">
                    <HorizontalExpenseBarChart data={expenseCategoryData} height={160} />
                  </div>
                </div>
              ) : (
                <ChartUnavailableCard title="Expense Categories" message={expenseDataUnavailableMessage} />
              )}
              {hasMonthlyExpenseTrend ? (
                <div className="chart-card halfsize">
                  <div className="chart-title">Monthly Expense Trend</div>
                  <div className="chart-body">
                    <CurrencyBarChart data={monthlyExpenseTrend} bars={[{ dataKey: "expenses", name: "Expenses", color: "#D89A2B" }]} height={160} />
                  </div>
                </div>
              ) : (
                <ChartUnavailableCard title="Monthly Expense Trend" message={expenseDataUnavailableMessage} />
              )}
              {hasNetIncomeTrendData ? (
                <div className="chart-card halfsize">
                  <div className="chart-title">Net Income Trend</div>
                  <div className="chart-body">
                    <CurrencyLineChart data={netIncomeTrendData} lines={[{ dataKey: "netIncome", name: "Net Income", color: "#C7A24D" }]} height={160} />
                  </div>
                </div>
              ) : (
                <ChartUnavailableCard title="Net Income Trend" message={expenseDataUnavailableMessage} />
              )}
            </>
          )}
          {summary && summary.totalAR !== null ? (
            <div className="chart-card halfsize">
              <div className="chart-title">A/R Aging</div>
              <div className="chart-body">
                <ARAgingBarChart
                  data={[
                    { name: "0–30", value: summary.ar0to30 ?? 0 },
                    { name: "31–60", value: summary.ar31to60 ?? 0 },
                    { name: "61–90", value: summary.ar61to90 ?? 0 },
                    { name: "90+", value: summary.arOver90 ?? 0 },
                  ]}
                  height={160}
                />
              </div>
            </div>
          ) : (
            <ChartUnavailableCard title="A/R Aging" message="Verified A/R aging data is not available from the current backend summary yet." />
          )}
          {showMockCharts ? (
            <div className="chart-card halfsize">
              <div className="chart-title">Trailing 12-Month Collections</div>
              <div className="chart-body">
                <CurrencyLineChart data={mockTrendData} lines={[{ dataKey: "collections", name: "Collections", color: "#78A86B" }]} height={160} />
              </div>
            </div>
          ) : hasTrendData ? (
            <div className="chart-card halfsize">
              <div className="chart-title">Trailing 12-Month Collections</div>
              <div className="chart-body">
                <CurrencyLineChart data={trendData} lines={[{ dataKey: "collections", name: "Collections", color: "#78A86B" }]} height={160} />
              </div>
            </div>
          ) : (
            <ChartUnavailableCard title="Trailing 12-Month Collections" message={trendDataUnavailableMessage} />
          )}
        </section>

        {(showMockCharts || hasProviderProduction) && (
          <div className="dashboard-section-spacer">
            <ProviderPerformanceTable data={showMockCharts ? mockProviderProduction : providerProduction} />
          </div>
        )}
        {isDev && (
          <div className="dashboard-section-spacer">
            <CaseAcceptanceFunnel presented={mockCaseAcceptance.presented} accepted={mockCaseAcceptance.accepted} />
          </div>
        )}
        {isDev && (
          <div className="dashboard-section-spacer">
            <NoShowRateChart data={mockNoShowRate} />
          </div>
        )}
        {isDev && (
          <div className="dashboard-section-spacer">
            <PatientFlowChart data={mockPatientFlow} />
          </div>
        )}
        {(showMockCharts || hasInsurancePatientTotals) && (
          <div className="dashboard-section-spacer">
            <InsurancePatientBreakdown
              insurance={showMockCharts ? mockInsurancePatientBreakdown.insurance : insurancePatientTotals.insurance}
              patient={showMockCharts ? mockInsurancePatientBreakdown.patient : insurancePatientTotals.patient}
            />
          </div>
        )}
        {arOver90AlertMessage ? (
          <div className="dashboard-section-spacer">
            <CustomAlert message={arOver90AlertMessage} type="warning" />
          </div>
        ) : null}
        {dashboardData.length > 0 && (
          <section className="dashboard-import-card dashboard-section-spacer" aria-label="CSV data preview">
            <h3 className="dashboard-import-history-title">CSV Data Preview</h3>
            <div className="dashboard-import-table-scroll">
              <table className="dashboard-import-table">
                <thead>
                  <tr>
                    {Object.keys(dashboardData[0]).map((k) => (
                      <th key={k}>{k}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {dashboardData.slice(0, 10).map((row) => {
                    const rowEntries = Object.entries(row as Record<string, unknown>);
                    const rowKey = rowEntries.map(([columnKey, value]) => `${columnKey}:${String(value)}`).join("|");
                    return (
                      <tr key={rowKey}>
                        {rowEntries.map(([columnKey, value]) => (
                          <td key={columnKey}>{String(value)}</td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="dashboard-import-preview-note">Showing first 10 rows. Upload more files to update.</div>
          </section>
        )}
      </div>
    </main>
  );
}

export default FinancialDashboard;
