import { useQuery } from "@tanstack/react-query";
import React from "react";

import { formatCurrency as formatUsd } from "../../utils/formatting";
import { fetchFinancialSummary } from "../api/client";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { CurrencyLineChart } from "../components/dashboard/CurrencyLineChart";
import {
  buildProductionCollectionsSeries,
  selectLatestMonthlyKpi,
  selectLatestProfitLoss,
} from "../components/dashboard/financialDashboardSummary";
import { SourceReviewContent } from "../components/dashboard/SourceReviewContent";
import { SummaryCard } from "../components/dashboard/SummaryCard";
import "./HalLandingPage.css";

function parseNumber(value: number | string | null | undefined) {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function formatCurrencyValue(value: number | string | null | undefined) {
  const parsed = parseNumber(value);
  return parsed === null ? "Unavailable" : formatUsd(parsed);
}

function formatDateLabel(value: string | null | undefined, fallback: string) {
  if (!value) {
    return fallback;
  }

  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? fallback : new Date(timestamp).toLocaleDateString("en-US");
}

export default function HalLandingPage() {
  const financialSummaryQuery = useQuery({
    queryKey: ["financial-summary"],
    queryFn: fetchFinancialSummary,
  });
  const trendData = React.useMemo(
    () => buildProductionCollectionsSeries(financialSummaryQuery.data?.trailing12Months),
    [financialSummaryQuery.data?.trailing12Months],
  );

  if (financialSummaryQuery.isPending) {
    return (
      <div className="dashboard-page">
        <LoadingSpinner label="Loading financial summary..." />
      </div>
    );
  }

  if (financialSummaryQuery.isError || !financialSummaryQuery.data) {
    return (
      <div className="dashboard-page">
        <div className="page-state-card page-state-card--error">The live financial summary could not be loaded right now.</div>
      </div>
    );
  }

  const financialSummary = financialSummaryQuery.data;
  const monthlyKpi = selectLatestMonthlyKpi(financialSummary.monthlyKpis);
  const latestProfitLoss = selectLatestProfitLoss(financialSummary.quickBooksProfitLossSummary);
  const quickBooksReview = financialSummary.sourceReview?.quickBooks ?? null;
  const softDentReview = financialSummary.sourceReview?.softDent ?? null;
  const latestRefresh = financialSummary.latestSoftDentRefreshAt ?? financialSummary.generatedAt ?? null;
  const monitorStatus = "Read-only telemetry live";
  const latestRefreshLabel = formatDateLabel(latestRefresh, "Waiting for sync");

  return (
    <div className="dashboard-page">
      <div className="page-content">
        <header className="page-header hal-landing-header">
          <h1 className="hal-landing-title">New Ridge Family Financial</h1>
          <p className="eyebrow">A clearer daily financial view for the practice</p>
        </header>

        <section className="hal-monitor" aria-label="HAL monitor">
          <div className="hal-monitor__frame">
            <div className="hal-monitor__screen">
              <div className="hal-monitor__grid" aria-hidden="true" />
              <div className="hal-monitor__hud">
                <div>
                  <p className="hal-monitor__eyebrow">HAL Monitor</p>
                  <h2 className="hal-monitor__headline">Practice telemetry is live on screen.</h2>
                </div>
                <div className="hal-monitor__status">{monitorStatus}</div>
              </div>
              <div className="hal-monitor__stats">
                <div className="hal-monitor__stat">
                  <span className="hal-monitor__stat-label">Production</span>
                  <strong className="hal-monitor__stat-value">{formatCurrencyValue(monthlyKpi?.gross_production)}</strong>
                  <span className="hal-monitor__stat-note">Current month gross</span>
                </div>
                <div className="hal-monitor__stat">
                  <span className="hal-monitor__stat-label">Latest sync</span>
                  <strong className="hal-monitor__stat-value">{latestRefreshLabel}</strong>
                  <span className="hal-monitor__stat-note">SoftDent or summary refresh</span>
                </div>
                <div className="hal-monitor__stat">
                  <span className="hal-monitor__stat-label">A/R over 90</span>
                  <strong className="hal-monitor__stat-value">{formatCurrencyValue(financialSummary.latestAr?.balance_90)}</strong>
                  <span className="hal-monitor__stat-note">Needs operator attention</span>
                </div>
              </div>
              <div className="hal-monitor__wave-band" aria-hidden="true">
                <svg className="hal-monitor__wave hal-monitor__wave--back" viewBox="0 0 1600 120" preserveAspectRatio="none">
                  <title>HAL monitor decorative back wave</title>
                  <path d="M0 74 C40 74 40 74 80 74 C120 74 128 32 164 32 C200 32 208 94 244 94 C280 94 288 50 324 50 C360 50 368 74 404 74 C440 74 448 74 484 74 C520 74 528 20 564 20 C600 20 608 108 644 108 C680 108 688 58 724 58 C760 58 768 74 804 74 C840 74 848 74 884 74 C920 74 928 36 964 36 C1000 36 1008 100 1044 100 C1080 100 1088 44 1124 44 C1160 44 1168 74 1204 74 C1240 74 1248 74 1284 74 C1320 74 1328 28 1364 28 C1400 28 1408 90 1444 90 C1480 90 1488 52 1524 52 C1560 52 1568 74 1600 74" />
                </svg>
                <svg className="hal-monitor__wave hal-monitor__wave--front" viewBox="0 0 1600 120" preserveAspectRatio="none">
                  <title>HAL monitor decorative front wave</title>
                  <path d="M0 72 C48 72 52 72 96 72 C138 72 144 26 182 26 C220 26 226 100 264 100 C302 100 308 46 346 46 C384 46 392 72 430 72 C468 72 474 72 512 72 C552 72 560 16 598 16 C636 16 644 112 682 112 C720 112 726 56 764 56 C802 56 810 72 848 72 C888 72 894 72 932 72 C972 72 978 34 1016 34 C1054 34 1062 96 1100 96 C1138 96 1144 42 1182 42 C1220 42 1228 72 1266 72 C1304 72 1310 72 1348 72 C1388 72 1394 24 1432 24 C1470 24 1478 88 1516 88 C1554 88 1562 52 1600 52" />
                </svg>
              </div>
            </div>
            <div className="hal-monitor__stand" aria-hidden="true">
              <span className="hal-monitor__neck" />
              <span className="hal-monitor__base" />
            </div>
          </div>
        </section>

        <section className="dashboard-summary-row hal-landing-summary">
          <SummaryCard title="Production">
            <div className="hal-landing-kpi">{formatCurrencyValue(monthlyKpi?.gross_production)}</div>
            <div>Gross production this month</div>
          </SummaryCard>
          <SummaryCard title="Collections">
            <div className="hal-landing-kpi">{formatCurrencyValue(monthlyKpi?.collections)}</div>
            <div>Collected month to date</div>
          </SummaryCard>
          <SummaryCard title="Net Income">
            <div className="hal-landing-kpi">{formatCurrencyValue(latestProfitLoss?.net_income)}</div>
            <div>Net income month to date</div>
          </SummaryCard>
        </section>

        <section className="hal-landing-trend-section">
          <div className="hal-landing-trend-card">
            <h2 className="hal-landing-trend-title">12-Month Production Trend</h2>
            <CurrencyLineChart data={trendData} lines={[{ dataKey: "production", name: "Production", color: "#D6B15E" }]} height={180} />
          </div>
          <div className="hal-landing-trend-card">
            <h2 className="hal-landing-trend-title">12-Month Collections Trend</h2>
            <CurrencyLineChart
              data={trendData}
              lines={[
                {
                  dataKey: "collections",
                  name: "Collections",
                  color: "#78A86B",
                },
              ]}
              height={180}
            />
          </div>
        </section>

        <section className="dashboard-import-history">
          <h2>Source Notes</h2>
          <div className="admin-audit-list">
            <SourceReviewContent review={softDentReview} emptyMessage="SoftDent source review metadata is unavailable." />
            <SourceReviewContent review={quickBooksReview} emptyMessage="QuickBooks source review metadata is unavailable." />
          </div>
        </section>

        <section className="hal-landing-actions">
          <div className="hal-landing-actions-card">
            <h2 className="hal-landing-actions-title">Where To Look First</h2>
            <ul>
              <li>Refresh SoftDent if the latest import looks stale. Last import: {formatDateLabel(latestRefresh, "Unavailable")}</li>
              <li>Look at A/R over 90 days: {formatCurrencyValue(financialSummary.latestAr?.balance_90)}</li>
              <li>Ask HAL for a plain-English summary of what matters today.</li>
            </ul>
          </div>
        </section>

        <section className="hal-landing-form-section">
          <div className="page-state-card page-state-card--info">
            <h2>Ask HAL</h2>
            <p>Interactive HAL chat lives on the dedicated HAL page.</p>
            <p>Open the HAL route when you want a plain-English summary or a guided follow-up.</p>
          </div>
        </section>
      </div>
    </div>
  );
}
