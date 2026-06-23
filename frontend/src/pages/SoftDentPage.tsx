import { useQuery } from "@tanstack/react-query";

import { formatCurrency } from "../../utils/formatting";
import { fetchFinancialSummary } from "../api/client";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { ARAgingBarChart } from "../components/dashboard/ARAgingBarChart";
import { ChartCard } from "../components/dashboard/ChartCard";
import { CurrencyLineChart } from "../components/dashboard/CurrencyLineChart";
import { buildProductionCollectionsSeries, selectLatestMonthlyKpi } from "../components/dashboard/financialDashboardSummary";
import { SoftDentCoveragePanel } from "../components/dashboard/SoftDentCoveragePanel";
import { SourceReviewContent } from "../components/dashboard/SourceReviewContent";
import { SummaryCard } from "../components/dashboard/SummaryCard";

function formatCurrencyValue(value: number | null | undefined) {
  return value === null || value === undefined ? "Unavailable" : formatCurrency(value);
}

export default function SoftDentPage() {
  const financialSummaryQuery = useQuery({
    queryKey: ["financial-summary"],
    queryFn: fetchFinancialSummary,
  });

  if (financialSummaryQuery.isPending) {
    return (
      <div className="dashboard-page">
        <LoadingSpinner label="Loading SoftDent financials..." />
      </div>
    );
  }

  if (financialSummaryQuery.isError || !financialSummaryQuery.data) {
    return (
      <div className="dashboard-page">
        <div className="page-state-card page-state-card--error">Unable to load live SoftDent financial data.</div>
      </div>
    );
  }

  const financialSummary = financialSummaryQuery.data;

  const latestAr = financialSummary.latestAr;
  const softDentCoverage = financialSummary.softDentCoverage ?? null;
  const softDentReview = financialSummary.sourceReview?.softDent ?? null;
  const monthlyKpi = selectLatestMonthlyKpi(financialSummary.monthlyKpis);
  const trailing12Months = buildProductionCollectionsSeries(financialSummary.trailing12Months);
  const arAging = latestAr
    ? [
        { name: "Current", value: latestAr.current_balance ?? 0 },
        { name: "31-60", value: latestAr.balance_30 ?? 0 },
        { name: "61-90", value: latestAr.balance_60 ?? 0 },
        { name: "90+", value: latestAr.balance_90 ?? 0 },
      ]
    : [];

  return (
    <div className="dashboard-page">
      <h1>SoftDent Financials</h1>
      <div className="dashboard-description">Practice-management financial performance from SoftDent.</div>
      <section className="dashboard-import-history">
        <h2>SoftDent Source Review</h2>
        <SourceReviewContent review={softDentReview} emptyMessage="SoftDent source review metadata is unavailable." />
      </section>
      <section className="dashboard-import-history">
        <h2>Data Coverage / Missing Reports</h2>
        <SoftDentCoveragePanel coverage={softDentCoverage} emptyMessage="SoftDent data coverage details are unavailable." />
      </section>
      <div className="kpi-grid">
        <SummaryCard title="Production">
          <div>
            Current month gross: <strong>{formatCurrencyValue(monthlyKpi?.gross_production)}</strong>
          </div>
          <div>
            Current month net: <strong>{formatCurrencyValue(monthlyKpi?.net_production)}</strong>
          </div>
        </SummaryCard>
        <SummaryCard title="Collections">
          <div>
            Current month: <strong>{formatCurrencyValue(monthlyKpi?.collections)}</strong>
          </div>
          <div>
            Collection %:{" "}
            <strong>{monthlyKpi?.collection_rate != null ? `${Math.round(monthlyKpi.collection_rate)}%` : "N/A"}</strong>
          </div>
        </SummaryCard>
        <SummaryCard title="A/R Aging">
          <div>
            Total: <strong>{formatCurrencyValue(latestAr?.total_ar)}</strong>
          </div>
          <div>
            90+: <strong>{formatCurrencyValue(latestAr?.balance_90)}</strong>
          </div>
        </SummaryCard>
      </div>
      <div className="dashboard-charts">
        <ChartCard title="Production Trend">
          <CurrencyLineChart data={trailing12Months} lines={[{ dataKey: "production", name: "Production", color: "#D6B15E" }]} />
        </ChartCard>
        <ChartCard title="Collections Trend">
          <CurrencyLineChart data={trailing12Months} lines={[{ dataKey: "collections", name: "Collections", color: "#78A86B" }]} />
        </ChartCard>
        <ChartCard title="A/R Aging">
          <ARAgingBarChart data={arAging} />
        </ChartCard>
      </div>
      <div className="dashboard-import-history">
        <h2>Current Source Snapshot</h2>
        <table className="import-history-table">
          <thead>
            <tr>
              <th>Measure</th>
              <th>Value</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Latest A/R snapshot</td>
              <td>{latestAr?.as_of_date ?? "Unavailable"}</td>
            </tr>
            <tr>
              <td>Monthly KPI rows</td>
              <td>{financialSummary.monthlyKpis?.length ?? 0}</td>
            </tr>
            <tr>
              <td>Trailing trend rows</td>
              <td>{financialSummary.trailing12Months?.length ?? 0}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
