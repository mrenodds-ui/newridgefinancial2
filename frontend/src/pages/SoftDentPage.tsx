import { useQuery } from "@tanstack/react-query";

import { formatCurrency } from "../../utils/formatting";
import { fetchFinancialSummary } from "../api/client";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { PageSurfaceHeader, PageSurfaceShell } from "../components/PageSurfaceHeader";
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

function formatCurrencyValue(value: number | null | undefined) {
  return value === null || value === undefined ? "Unavailable" : formatCurrency(value);
}

function formatArCurrency(value: number | null) {
  if (value === null) {
    return "Unavailable";
  }
  return formatCurrency(value);
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

export default function SoftDentPage() {
  const financialSummaryQuery = useQuery({
    queryKey: ["financial-summary"],
    queryFn: fetchFinancialSummary,
  });

  if (financialSummaryQuery.isPending) {
    return (
      <PageSurfaceShell className="softdent-page">
        <LoadingSpinner label="Loading SoftDent financials..." />
      </PageSurfaceShell>
    );
  }

  if (financialSummaryQuery.isError || !financialSummaryQuery.data) {
    return (
      <PageSurfaceShell className="softdent-page">
        <div className="page-state-card page-state-card--error">Unable to load live SoftDent financial data.</div>
      </PageSurfaceShell>
    );
  }

  const financialSummary = financialSummaryQuery.data;

  const latestAr = financialSummary.latestAr;
  const arAvailable = isSoftdentArAvailable(latestAr);
  const totalAr = arAvailable ? toArField(latestAr.total_ar) : null;
  const arOver90 = arAvailable ? toArField(latestAr.balance_90) : null;
  const currentBalance = arAvailable ? toArField(latestAr.current_balance) : null;
  const balance60 = arAvailable ? toArField(latestAr.balance_60) : null;
  const balance90 = arAvailable ? toArField(latestAr.balance_90) : null;
  const olderArBalance =
    arAvailable && balance60 !== null && balance90 !== null ? balance60 + balance90 : null;
  const monthlyKpi = selectLatestMonthlyKpi(financialSummary.monthlyKpis);
  const trailing12Months = buildProductionCollectionsSeries(financialSummary.trailing12Months);
  const collectionPercent = monthlyKpi?.collection_rate != null ? Math.round(monthlyKpi.collection_rate) : null;
  const arAging = arAvailable
    ? [
        { name: "Current", value: toArField(latestAr.current_balance) },
        { name: "31-60", value: toArField(latestAr.balance_30) },
        { name: "61-90", value: balance60 },
        { name: "90+", value: balance90 },
      ].filter((bucket): bucket is { name: string; value: number } => bucket.value !== null)
    : [];

  return (
    <PageSurfaceShell className="softdent-page">
      <PageSurfaceHeader
        breadcrumbs="Data sources / SoftDent"
        eyebrow="Practice management feed"
        title="Practice performance"
        titleId="softdent-page-title"
        description="Production, collections, and receivables from approved SoftDent import exports. Dental A/R stays unavailable until the DAYSHEET export is present."
        badges={[
          { label: "SoftDent Read-Only" },
          { label: "Missing A/R ≠ $0", tone: "warning" },
          { label: "No Writeback" },
        ]}
        statusItems={[
          { label: "A/R source", value: arAvailable ? "DAYSHEET imported" : "Awaiting DAYSHEET export" },
          { label: "Last refresh", value: formatDateTime(financialSummary.latestSoftDentRefreshAt) },
          { label: "Collection pace", value: collectionPercent === null ? "Unavailable" : `${collectionPercent}%` },
        ]}
        badgesAriaLabel="SoftDent data safety posture"
        statusAriaLabel="SoftDent import status"
      />
      <section className="dashboard-toolbar" aria-label="SoftDent summary">
        <div>
          <div className="dashboard-toolbar__label">Collections pace</div>
          <div className="dashboard-toolbar__value">{collectionPercent === null ? "Unavailable" : `${collectionPercent}%`}</div>
        </div>
        <div>
          <div className="dashboard-toolbar__label">Total practice A/R</div>
          <div className="dashboard-toolbar__value">{formatArCurrency(totalAr)}</div>
        </div>
        <div>
          <div className="dashboard-toolbar__label">A/R older than 90 days</div>
          <div className="dashboard-toolbar__value">{formatArCurrency(arOver90)}</div>
        </div>
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
            Collection rate: <strong>{collectionPercent === null ? "Unavailable" : `${collectionPercent}%`}</strong>
          </div>
        </SummaryCard>
        <SummaryCard title="A/R aging">
          <div>
            Total: <strong>{formatArCurrency(totalAr)}</strong>
          </div>
          <div>
            90+: <strong>{formatArCurrency(arOver90)}</strong>
          </div>
        </SummaryCard>
        <SummaryCard title="Receivables focus">
          <div>
            Current A/R: <strong>{formatArCurrency(currentBalance)}</strong>
          </div>
          <div>
            60+ aging: <strong>{formatArCurrency(olderArBalance)}</strong>
          </div>
        </SummaryCard>
      </div>
      <div className="dashboard-charts">
        <ChartCard title="Production trend">
          <CurrencyLineChart data={trailing12Months} lines={[{ dataKey: "production", name: "Production", color: "#4c84ff" }]} />
        </ChartCard>
        <ChartCard title="Collections trend">
          <CurrencyLineChart data={trailing12Months} lines={[{ dataKey: "collections", name: "Collections", color: "#69e6ff" }]} />
        </ChartCard>
        <ChartCard title="A/R aging buckets">
          {arAvailable ? (
            <ARAgingBarChart data={arAging} />
          ) : (
            <div className="page-state-card page-state-card--info">No SoftDent A/R export available.</div>
          )}
        </ChartCard>
      </div>
      <section className="page-surface__focus-card" aria-label="Collections focus">
        <div className="page-surface__focus-title">Current month collections</div>
        <div className="page-surface__focus-metric">{formatCurrencyValue(monthlyKpi?.collections)}</div>
        <div className="page-surface__focus-detail">Verified SoftDent production and collections snapshot</div>
        <div className="page-surface__focus-support">
          <span>
            Gross production: <strong>{formatCurrencyValue(monthlyKpi?.gross_production)}</strong>
          </span>
          <span>
            Net production: <strong>{formatCurrencyValue(monthlyKpi?.net_production)}</strong>
          </span>
          <span>
            Older A/R: <strong>{formatArCurrency(olderArBalance)}</strong>
          </span>
        </div>
      </section>
    </PageSurfaceShell>
  );
}
