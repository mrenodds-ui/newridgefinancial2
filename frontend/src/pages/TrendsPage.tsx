import { useQuery } from "@tanstack/react-query";

import { fetchFinancialSummary } from "../api/client";
import { LoadingSpinner } from "../components/LoadingSpinner";
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
      <div className="dashboard-page">
        <LoadingSpinner label="Loading financial trends..." />
      </div>
    );
  }

  if (financialSummaryQuery.isError || !financialSummaryQuery.data) {
    return (
      <div className="dashboard-page">
        <div className="page-state-card page-state-card--error">Unable to load live trend data.</div>
      </div>
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
    <div className="dashboard-page">
      <h1>Trends</h1>
      <div className="dashboard-description">Key financial and operational trends over time.</div>
      <div className="kpi-grid">
        <SummaryCard title="12-Month Production">
          <div>
            <strong>{formatCurrencyValue(productionTotal)}</strong>
          </div>
        </SummaryCard>
        <SummaryCard title="12-Month Collections">
          <div>
            <strong>{formatCurrencyValue(collectionsTotal)}</strong>
          </div>
        </SummaryCard>
        <SummaryCard title="12-Month Net Income">
          <div>
            <strong>{formatCurrencyValue(netIncomeTotal)}</strong>
          </div>
        </SummaryCard>
      </div>
      <div className="dashboard-charts">
        <ChartCard title="Production Trend">
          <CurrencyLineChart data={trendRows} lines={[{ dataKey: "production", name: "Production", color: "#4B8BBE" }]} />
        </ChartCard>
        <ChartCard title="Collections Trend">
          <CurrencyLineChart data={trendRows} lines={[{ dataKey: "collections", name: "Collections", color: "#78A86B" }]} />
        </ChartCard>
        <ChartCard title="Expense Trend">
          {profitLossTrendRows.length ? (
            <CurrencyLineChart data={profitLossTrendRows} lines={[{ dataKey: "expenses", name: "Expenses", color: "#C96A5B" }]} />
          ) : (
            <div className="page-state-card page-state-card--info">Verified QuickBooks expense history is not available yet.</div>
          )}
        </ChartCard>
        <ChartCard title="Net Income Trend">
          {profitLossTrendRows.length ? (
            <CurrencyLineChart data={profitLossTrendRows} lines={[{ dataKey: "netIncome", name: "Net Income", color: "#F2B134" }]} />
          ) : (
            <div className="page-state-card page-state-card--info">Verified QuickBooks net-income history is not available yet.</div>
          )}
        </ChartCard>
      </div>
    </div>
  );
}
