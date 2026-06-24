import { useQuery } from "@tanstack/react-query";

import { fetchFinancialSummary } from "../api/client";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { ARAgingBarChart } from "../components/dashboard/ARAgingBarChart";
import { ChartCard } from "../components/dashboard/ChartCard";
import { CurrencyLineChart } from "../components/dashboard/CurrencyLineChart";
import {
  buildProductionCollectionsSeries,
  isSoftdentArAvailable,
  selectLatestMonthlyKpi,
} from "../components/dashboard/financialDashboardSummary";
import { SummaryCard } from "../components/dashboard/SummaryCard";

function toArField(value: unknown): number | null {
  if (value === null || value === undefined) {
    return null;
  }
  const numeric = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function formatArCurrency(value: number | null): string {
  if (value === null) {
    return "Unavailable";
  }
  return value.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

export default function ARCollectionsPage() {
  const financialSummaryQuery = useQuery({
    queryKey: ["financial-summary"],
    queryFn: fetchFinancialSummary,
  });

  if (financialSummaryQuery.isPending) {
    return (
      <div className="dashboard-page">
        <LoadingSpinner label="Loading A/R and collections..." />
      </div>
    );
  }

  if (financialSummaryQuery.isError || !financialSummaryQuery.data) {
    return (
      <div className="dashboard-page">
        <div className="page-state-card page-state-card--error">Unable to load live A/R data.</div>
      </div>
    );
  }

  const financialSummary = financialSummaryQuery.data;
  const latestAr = financialSummary.latestAr;
  const arAvailable = isSoftdentArAvailable(latestAr);
  const totalAr = arAvailable ? toArField(latestAr.total_ar) : null;
  const arOver90 = arAvailable ? toArField(latestAr.balance_90) : null;
  const balance60 = arAvailable ? toArField(latestAr.balance_60) : null;
  const balance90 = arAvailable ? toArField(latestAr.balance_90) : null;
  const olderArTotal =
    arAvailable && balance60 !== null && balance90 !== null ? balance60 + balance90 : null;
  const trailing12Months = buildProductionCollectionsSeries(financialSummary.trailing12Months);
  const arAging =
    arAvailable
      ? [
          { name: "Current", value: toArField(latestAr.current_balance) },
          { name: "31-60", value: toArField(latestAr.balance_30) },
          { name: "61-90", value: balance60 },
          { name: "90+", value: balance90 },
        ].filter((bucket): bucket is { name: string; value: number } => bucket.value !== null)
      : [];
  const collectionPercent = selectLatestMonthlyKpi(financialSummary.monthlyKpis)?.collection_rate ?? null;

  return (
    <div className="dashboard-page">
      <header className="page-header">
        <p className="eyebrow">Collections</p>
        <h1>A/R & Collections</h1>
        <div className="dashboard-description">Cash collection health and A/R aging.</div>
      </header>
      <section className="dashboard-toolbar" aria-label="Collections summary">
        <div>
          <div className="dashboard-toolbar__label">Total A/R</div>
          <div className="dashboard-toolbar__value">{formatArCurrency(totalAr)}</div>
        </div>
        <div>
          <div className="dashboard-toolbar__label">60+ A/R</div>
          <div className="dashboard-toolbar__value">{formatArCurrency(olderArTotal)}</div>
        </div>
        <div>
          <div className="dashboard-toolbar__label">Collection pace</div>
          <div className="dashboard-toolbar__value">{collectionPercent !== null ? `${Math.round(collectionPercent)}%` : "N/A"}</div>
        </div>
      </section>
      <div className="kpi-grid">
        <SummaryCard title="Total A/R">
          <div>
            <strong>{formatArCurrency(totalAr)}</strong>
          </div>
        </SummaryCard>
        <SummaryCard title="90+ A/R">
          <div>
            <strong>{formatArCurrency(arOver90)}</strong>
          </div>
        </SummaryCard>
        <SummaryCard title="Collection %">
          <div>
            <strong>{collectionPercent !== null ? `${Math.round(collectionPercent)}%` : "N/A"}</strong>
          </div>
        </SummaryCard>
        <SummaryCard title="60+ A/R">
          <div>
            <strong>{formatArCurrency(olderArTotal)}</strong>
          </div>
        </SummaryCard>
      </div>
      <div className="dashboard-charts">
        <ChartCard title="A/R Aging">
          {arAvailable ? (
            <ARAgingBarChart data={arAging} />
          ) : (
            <div className="page-state-card page-state-card--info">No SoftDent A/R export available.</div>
          )}
        </ChartCard>
        <ChartCard title="Collections Trend">
          <CurrencyLineChart data={trailing12Months} lines={[{ dataKey: "collections", name: "Collections", color: "#78A86B" }]} />
        </ChartCard>
      </div>
      <section className="dashboard-card">
        <div className="dashboard-card__title">Collections Focus</div>
        <div className="dashboard-kpi-main">{formatArCurrency(arOver90)}</div>
        <div className="dashboard-kpi-label">A/R older than 90 days</div>
        <div className="dashboard-kpi-support">
          <span>
            Total A/R: <strong>{formatArCurrency(totalAr)}</strong>
          </span>
          <span>
            60+ aging: <strong>{formatArCurrency(olderArTotal)}</strong>
          </span>
          <span>
            Collection pace: <strong>{collectionPercent !== null ? `${Math.round(collectionPercent)}%` : "N/A"}</strong>
          </span>
        </div>
      </section>
    </div>
  );
}
