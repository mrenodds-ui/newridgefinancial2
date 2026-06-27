import { useQuery } from "@tanstack/react-query";

import { fetchFinancialSummary } from "../api/client";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { PageSurfaceHeader, PageSurfaceShell } from "../components/PageSurfaceHeader";
import { ChartCard } from "../components/dashboard/ChartCard";
import { CurrencyLineChart } from "../components/dashboard/CurrencyLineChart";
import {
  buildProductionCollectionsSeries,
  buildProfitLossTrendData,
  sumTrailing12NetIncome,
  sumTrailing12ProductionCollections,
} from "../components/dashboard/financialDashboardSummary";
import { SummaryCard } from "../components/dashboard/SummaryCard";

function formatCurrency(value: number) {
  return value.toLocaleString();
}

function formatCurrencyValue(value: number | null) {
  return value === null ? "Unavailable" : `$${formatCurrency(value)}`;
}

export default function TrendsPage() {
  const financialSummaryQuery = useQuery({
    queryKey: ["financial-summary"],
    queryFn: fetchFinancialSummary,
  });

  if (financialSummaryQuery.isPending) {
    return (
      <PageSurfaceShell className="trends-page">
        <LoadingSpinner label="Loading financial trends..." />
      </PageSurfaceShell>
    );
  }

  if (financialSummaryQuery.isError || !financialSummaryQuery.data) {
    return (
      <PageSurfaceShell className="trends-page">
        <div className="page-state-card page-state-card--error">Unable to load live trend data.</div>
      </PageSurfaceShell>
    );
  }

  const financialSummary = financialSummaryQuery.data;
  const trendRows = buildProductionCollectionsSeries(
    financialSummary.fourYearMonthlyKpis?.length ? financialSummary.fourYearMonthlyKpis : financialSummary.trailing12Months,
  );
  const profitLossTrendRows = buildProfitLossTrendData(financialSummary.quickBooksProfitLossSummary);
  const { production: productionTotal, collections: collectionsTotal } = sumTrailing12ProductionCollections(financialSummary.trailing12Months);
  const netIncomeTotal = sumTrailing12NetIncome(financialSummary.quickBooksProfitLossSummary);

  return (
    <PageSurfaceShell className="trends-page">
      <PageSurfaceHeader
        breadcrumbs="Analytics / Performance trends"
        eyebrow="Performance trends"
        title="Trends"
        titleId="trends-page-title"
        description="Long-horizon production, collections, and QuickBooks profit trends from approved import caches."
        badges={[
          { label: "Import Read-Only" },
          { label: "Verified Feeds Only" },
        ]}
        statusItems={[
          { label: "SoftDent months", value: String(financialSummary.trailing12Months?.length ?? 0) },
          { label: "QuickBooks P&L months", value: String(financialSummary.quickBooksProfitLossSummary?.length ?? 0) },
          { label: "Data freshness", value: financialSummary.dataFreshnessStatus ?? "Unknown" },
        ]}
      />
      <div className="kpi-grid">
        <SummaryCard title="12-month production">
          <div>
            <strong>{formatCurrencyValue(productionTotal)}</strong>
          </div>
        </SummaryCard>
        <SummaryCard title="12-month collections">
          <div>
            <strong>{formatCurrencyValue(collectionsTotal)}</strong>
          </div>
        </SummaryCard>
        <SummaryCard title="12-month net income">
          <div>
            <strong>{formatCurrencyValue(netIncomeTotal)}</strong>
          </div>
        </SummaryCard>
      </div>
      <div className="dashboard-charts">
        <ChartCard title="Production trend">
          <CurrencyLineChart data={trendRows} lines={[{ dataKey: "production", name: "Production", color: "#4c84ff" }]} />
        </ChartCard>
        <ChartCard title="Collections trend">
          <CurrencyLineChart data={trendRows} lines={[{ dataKey: "collections", name: "Collections", color: "#69e6ff" }]} />
        </ChartCard>
        <ChartCard title="Expense trend">
          {profitLossTrendRows.length ? (
            <CurrencyLineChart data={profitLossTrendRows} lines={[{ dataKey: "expenses", name: "Expenses", color: "#e4ecff" }]} />
          ) : (
            <div className="page-state-card page-state-card--info">Verified QuickBooks expense history is not available yet.</div>
          )}
        </ChartCard>
        <ChartCard title="Net income trend">
          {profitLossTrendRows.length ? (
            <CurrencyLineChart data={profitLossTrendRows} lines={[{ dataKey: "netIncome", name: "Net Income", color: "#4c84ff" }]} />
          ) : (
            <div className="page-state-card page-state-card--info">Verified QuickBooks net-income history is not available yet.</div>
          )}
        </ChartCard>
      </div>
    </PageSurfaceShell>
  );
}
