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
import "../styles/page-surface.css";

const AR_SAFETY_BADGES = [
  { label: "SoftDent Read-Only", tone: "neutral" as const },
  { label: "Missing A/R ≠ $0", tone: "warning" as const },
  { label: "No Payer Contact", tone: "neutral" as const },
  { label: "Not Submitted", tone: "neutral" as const },
];

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

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "Unavailable";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "Unavailable";
  }
  return parsed.toLocaleString();
}

export default function ARCollectionsPage() {
  const financialSummaryQuery = useQuery({
    queryKey: ["financial-summary"],
    queryFn: fetchFinancialSummary,
  });

  if (financialSummaryQuery.isPending) {
    return (
      <div className="dashboard-page ar-collections-page page-surface">
        <LoadingSpinner label="Loading A/R and collections..." />
      </div>
    );
  }

  if (financialSummaryQuery.isError || !financialSummaryQuery.data) {
    return (
      <div className="dashboard-page ar-collections-page page-surface">
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
  const arSourceLabel = arAvailable ? "SoftDent DAYSHEET imported" : "Awaiting SoftDent A/R export";

  return (
    <div className="dashboard-page ar-collections-page page-surface">
      <header className="page-surface__hero" aria-labelledby="ar-collections-title">
        <div className="page-surface__hero-top">
          <div className="page-surface__hero-copy">
            <div className="page-surface__breadcrumbs">Collections / Practice receivables</div>
            <p className="eyebrow">Collections workspace</p>
            <h1 id="ar-collections-title">A/R & Collections</h1>
            <p className="dashboard-description">
              Read-only view of dental practice receivables from approved SoftDent DAYSHEET exports. Unavailable balances stay
              labeled unavailable — never shown as zero.
            </p>
          </div>
          <div className="page-surface__badges" aria-label="Collections safety posture">
            {AR_SAFETY_BADGES.map((badge) => (
              <span
                key={badge.label}
                className={["page-surface__badge", badge.tone === "warning" ? "page-surface__badge--warning" : "page-surface__badge--neutral"].join(
                  " ",
                )}
              >
                {badge.label}
              </span>
            ))}
          </div>
        </div>
        <div className="page-surface__status-strip" aria-label="Collections source status">
          <div className="page-surface__status-item">
            <span className="page-surface__status-label">A/R source</span>
            <span className="page-surface__status-value">{arSourceLabel}</span>
          </div>
          <div className="page-surface__status-item">
            <span className="page-surface__status-label">Last refresh</span>
            <span className="page-surface__status-value">{formatDateTime(financialSummary.latestSoftDentRefreshAt)}</span>
          </div>
          <div className="page-surface__status-item">
            <span className="page-surface__status-label">Collection pace</span>
            <span className="page-surface__status-value">
              {collectionPercent !== null ? `${Math.round(collectionPercent)}%` : "Unavailable"}
            </span>
          </div>
        </div>
      </header>

      <section className="dashboard-toolbar" aria-label="Collections summary">
        <div>
          <div className="dashboard-toolbar__label">Total practice A/R</div>
          <div className="dashboard-toolbar__value">{formatArCurrency(totalAr)}</div>
        </div>
        <div>
          <div className="dashboard-toolbar__label">A/R aged 60+ days</div>
          <div className="dashboard-toolbar__value">{formatArCurrency(olderArTotal)}</div>
        </div>
        <div>
          <div className="dashboard-toolbar__label">Collection pace</div>
          <div className="dashboard-toolbar__value">{collectionPercent !== null ? `${Math.round(collectionPercent)}%` : "Unavailable"}</div>
        </div>
      </section>

      <div className="kpi-grid">
        <SummaryCard title="Total practice A/R">
          <div>
            <strong>{formatArCurrency(totalAr)}</strong>
          </div>
        </SummaryCard>
        <SummaryCard title="A/R older than 90 days">
          <div>
            <strong>{formatArCurrency(arOver90)}</strong>
          </div>
        </SummaryCard>
        <SummaryCard title="Collection rate">
          <div>
            <strong>{collectionPercent !== null ? `${Math.round(collectionPercent)}%` : "Unavailable"}</strong>
          </div>
        </SummaryCard>
        <SummaryCard title="A/R aged 60+ days">
          <div>
            <strong>{formatArCurrency(olderArTotal)}</strong>
          </div>
        </SummaryCard>
      </div>

      <div className="dashboard-charts">
        <ChartCard title="A/R aging buckets">
          {arAvailable ? (
            <ARAgingBarChart data={arAging} />
          ) : (
            <div className="page-state-card page-state-card--info">No SoftDent A/R export available.</div>
          )}
        </ChartCard>
        <ChartCard title="Trailing collections trend">
          <CurrencyLineChart data={trailing12Months} lines={[{ dataKey: "collections", name: "Collections", color: "#4c84ff" }]} />
        </ChartCard>
      </div>

      <section className="page-surface__focus-card" aria-label="Collections focus">
        <div className="page-surface__focus-title">Priority follow-up</div>
        <div className="page-surface__focus-metric">{formatArCurrency(arOver90)}</div>
        <div className="page-surface__focus-detail">Practice A/R older than 90 days</div>
        <div className="page-surface__focus-support">
          <span>
            Total practice A/R: <strong>{formatArCurrency(totalAr)}</strong>
          </span>
          <span>
            A/R aged 60+ days: <strong>{formatArCurrency(olderArTotal)}</strong>
          </span>
          <span>
            Collection pace: <strong>{collectionPercent !== null ? `${Math.round(collectionPercent)}%` : "Unavailable"}</strong>
          </span>
        </div>
      </section>
    </div>
  );
}
