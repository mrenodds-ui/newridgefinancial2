import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import type { Layout } from "react-grid-layout/legacy";
import { Responsive, WidthProvider } from "react-grid-layout/legacy";
import { Link } from "react-router-dom";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";
import "./financial-dashboard.css";

import { fetchFinancialSummary, type FinancialSummaryResponse } from "../../api/client";
import { useAuthSession } from "../../hooks/useAuthSession";
import { LoadingSpinner } from "../LoadingSpinner";
import {
  DASHBOARD_TREND_MONTH_WINDOW,
  buildArOver90AlertMessage,
  buildDashboardTrendData,
  buildDashboardSummaryFromFinancialSummary,
  buildFinancialSummaryInsurancePatientTotals,
  buildProfitLossTrendData,
  buildQuickBooksExpenseCategoryData,
  buildQuickBooksMonthlyExpenseTrendData,
} from "./financialDashboardSummary";
import { ARAgingBarChart } from "./ARAgingBarChart";
import { CurrencyBarChart } from "./CurrencyBarChart";
import { CurrencyLineChart } from "./CurrencyLineChart";
import { CustomAlert } from "./CustomAlert";
import {
  FINANCIAL_DASHBOARD_BREAKPOINTS,
  FINANCIAL_DASHBOARD_COLS,
  loadFinancialDashboardLayouts,
  mergeFinancialDashboardLayouts,
  resetFinancialDashboardLayouts,
  saveFinancialDashboardLayouts,
  type FinancialDashboardLayouts,
  type FinancialDashboardTileId,
} from "./financialDashboardLayout";
import { HorizontalExpenseBarChart } from "./HorizontalExpenseBarChart";

const PRODUCTION_COLOR = "#4c84ff";
const COLLECTIONS_COLOR = "#e4ecff";
const EXPENSES_COLOR = "#3f6bff";
const NET_INCOME_COLOR = "#69e6ff";
const ResponsiveGridLayout = WidthProvider(Responsive);
const DASHBOARD_TREND_WINDOW_LABEL = "24 months";

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
function formatCountValue(value: number | null | undefined, noun?: string) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "Unavailable";
  }

  const formatted = Math.round(value).toLocaleString("en-US");
  return noun ? `${formatted} ${noun}` : formatted;
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

function ChartUnavailableCard({ title, message, className = "" }: { title: string; message: string; className?: string }) {
  return (
    <div className={["chart-card", "halfsize", className].filter(Boolean).join(" ")}>
      <div className="chart-title">{title}</div>
      <div className="page-state-card page-state-card--info">{message}</div>
    </div>
  );
}

function SummaryMetricCard({
  title,
  value,
  label,
  detail,
  badge,
  badgeTone = "neutral",
}: {
  title: string;
  value: string;
  label: string;
  detail: string;
  badge: string;
  badgeTone?: "neutral" | "positive" | "warning";
}) {
  return (
    <div className="dashboard-summary-card dashboard-summary-card--metric">
      <div className="dashboard-summary-card__topline">
        <div className="dashboard-summary-card__title">{title}</div>
        <span className={["dashboard-summary-chip", `dashboard-summary-chip--${badgeTone}`].join(" ")}>{badge}</span>
      </div>
      <div className="dashboard-kpi-main">{value}</div>
      <div className="dashboard-kpi-label">{label}</div>
      <div className="dashboard-summary-card__detail">{detail}</div>
    </div>
  );
}

function FeaturedChartHeader() {
  return (
    <div className="chart-card__header">
      <div>
        <div className="chart-kicker">Annual performance</div>
        <div className="chart-title">Production vs Collections</div>
      </div>
      <div className="chart-card__controls" aria-label="Chart view metadata">
        <span className="chart-pill chart-pill--active">Live</span>
        <span className="chart-pill">{DASHBOARD_TREND_WINDOW_LABEL}</span>
      </div>
    </div>
  );
}

function clampPercent(value: number) {
  return Math.max(0, Math.min(100, value));
}

type WidgetTone = "neutral" | "positive" | "warning";

type FinancialWidget = {
  id: string;
  kicker: string;
  title: string;
  statusLabel: string;
  statusTone: WidgetTone;
  headline: string;
  summary: string;
  metrics: Array<{ label: string; value: string }>;
  nextAction: string;
  actionLabel: string;
  actionPath: string;
  secondaryActionLabel: string;
  secondaryActionPath: string;
};

type WidgetAction = {
  label: string;
  path: string;
};

type FinancialSummaryWidgetFeedSnapshot = NonNullable<FinancialSummaryResponse["widgetFeed"]>;

type PublishedHalWidget = {
  title?: unknown;
  status?: unknown;
  metrics?: Record<string, unknown> | null;
};

function sumRowCounts(rowCounts: Record<string, number> | null | undefined) {
  return Object.values(rowCounts ?? {}).reduce((total, value) => total + (Number.isFinite(value) ? value : 0), 0);
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function toOptionalNumber(value: unknown) {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }

  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  return null;
}

function getWidgetFeedSnapshot(financialSummary: FinancialSummaryResponse | undefined): FinancialSummaryWidgetFeedSnapshot | null {
  const widgetFeed = (financialSummary?.widgetFeed ?? null) as FinancialSummaryWidgetFeedSnapshot | null;
  return asRecord(widgetFeed) ? widgetFeed : null;
}

function getPublishedHalWidget(widgetFeed: FinancialSummaryWidgetFeedSnapshot | null, widgetKey: string): PublishedHalWidget | null {
  const widgets = asRecord(widgetFeed?.widgets);
  const widget = asRecord(widgets?.[widgetKey]);
  if (!widget) {
    return null;
  }

  return {
    title: widget.title,
    status: widget.status,
    metrics: asRecord(widget.metrics),
  };
}

function isSuccessfulHalWidget(widget: PublishedHalWidget | null): widget is PublishedHalWidget {
  return widget !== null && String(widget.status ?? "").trim().toUpperCase() === "SUCCESS";
}

function getWidgetFeedSourceLabel(widgetFeed: FinancialSummaryWidgetFeedSnapshot | null): string {
  const manager = String(widgetFeed?.manager ?? "")
    .trim()
    .toLowerCase();
  if (manager === "import cache") {
    return "Import cache";
  }
  if (manager) {
    return "HAL feed";
  }
  return "Local KPI";
}

function toHalWidgetStatusTone(status: unknown): WidgetTone {
  const normalized = String(status ?? "").trim().toUpperCase();
  if (normalized === "SUCCESS") {
    return "positive";
  }
  if (normalized === "DEGRADED" || normalized === "FAILED") {
    return "warning";
  }
  return "neutral";
}

function toHalWidgetStatusLabel(status: unknown, fallback: string, sourceLabel = "HAL feed") {
  const normalized = String(status ?? "").trim().toUpperCase();
  if (normalized === "SUCCESS") {
    return sourceLabel;
  }
  if (normalized === "DEGRADED") {
    return "HAL degraded";
  }
  if (normalized === "FAILED") {
    return "HAL failed";
  }
  return fallback;
}

function buildHighTechFinanceWidgets({
  financialSummary,
  summary,
}: {
  financialSummary: FinancialSummaryResponse | undefined;
  summary: ReturnType<typeof buildDashboardSummaryFromFinancialSummary>;
}): FinancialWidget[] {
  const latestAr = financialSummary?.latestAr ?? null;
  const quickBooksStatus = financialSummary?.quickBooksStatus ?? null;
  const claimsSummary = financialSummary?.claimsSummary ?? null;
  const softDentCoverageMetrics = financialSummary?.softDentCoverageMetrics ?? null;
  const sourceReview = financialSummary?.sourceReview ?? null;
  const treatmentPlans = softDentCoverageMetrics?.treatmentPlans ?? null;
  const paymentPlans = softDentCoverageMetrics?.paymentPlans ?? null;
  const claimsSource = sourceReview?.softDentClaims ?? null;
  const topOutstandingPayer = claimsSummary?.top_outstanding_payers?.[0] ?? null;
  const patientAr = latestAr?.patient_ar ?? null;
  const importedRowCount = sumRowCounts(quickBooksStatus?.rowCounts ?? undefined);
  const hasTreatmentPlans = Boolean(treatmentPlans?.available);
  const hasPaymentPlans = Boolean(paymentPlans?.available);
  const quickBooksReady = quickBooksStatus?.status === "ok";
  const claimsAvailable = Boolean(claimsSummary?.available);
  const hasCollectionPressure = (summary?.arOver90 ?? 0) > 0 || (claimsSummary?.unsubmitted_claims_count ?? 0) > 0;
  const caseAcceptanceCoverageMissing = !hasTreatmentPlans || !hasPaymentPlans;
  const claimsNeedReview = !claimsAvailable || Boolean(claimsSource?.reviewRequired) || claimsSource?.confidenceLabel === "manual review";
  const revenueNeedsRefresh = Boolean(summary?.isStale) || !quickBooksReady;
  const widgetFeed = getWidgetFeedSnapshot(financialSummary);
  const widgetFeedSourceLabel = getWidgetFeedSourceLabel(widgetFeed);
  const practiceFinancialOverview = getPublishedHalWidget(widgetFeed, "practice_financial_overview");
  const accountsPayableAutomation = getPublishedHalWidget(widgetFeed, "accounts_payable_automation");
  const smartClaimsAndReceivables = getPublishedHalWidget(widgetFeed, "smart_claims_and_receivables");
  const careDeliveryPerformance = getPublishedHalWidget(widgetFeed, "care_delivery_performance");

  const caseAcceptancePrimaryAction: WidgetAction = caseAcceptanceCoverageMissing
    ? { label: "Open import settings", path: "/settings" }
    : { label: "Open SoftDent plans", path: "/softdent" };
  const caseAcceptanceSecondaryAction: WidgetAction = caseAcceptanceCoverageMissing
    ? { label: "Open SoftDent plans", path: "/softdent" }
    : { label: "Review A/R follow-up", path: "/ar" };
  const apAutomationPrimaryAction: WidgetAction = quickBooksReady
    ? { label: "Review QuickBooks feed", path: "/quickbooks" }
    : { label: "Fix QuickBooks import", path: "/settings" };
  const apAutomationSecondaryAction: WidgetAction = quickBooksReady
    ? { label: "Open expense analysis", path: "/expenses" }
    : { label: "Open QuickBooks summary", path: "/quickbooks" };
  const smartClaimsPrimaryAction: WidgetAction = claimsNeedReview
    ? { label: "View claims source status", path: "/softdent" }
    : { label: "Open Claims Workbench", path: "/claims-workbench" };
  const smartClaimsSecondaryAction: WidgetAction = claimsNeedReview
    ? { label: "Open Claims Workbench", path: "/claims-workbench" }
    : { label: "Review A/R aging", path: "/ar" };
  const revenueAnalyticsPrimaryAction: WidgetAction = revenueNeedsRefresh
    ? { label: "Refresh data settings", path: "/settings" }
    : { label: "View revenue trends", path: "/trends" };
  const revenueAnalyticsSecondaryAction: WidgetAction = revenueNeedsRefresh
    ? { label: "Inspect QuickBooks feed", path: "/quickbooks" }
    : { label: "Open QuickBooks summary", path: "/quickbooks" };
  const aiFollowUpPrimaryAction: WidgetAction = claimsNeedReview
    ? { label: "Review claims readiness", path: "/claims-workbench" }
    : { label: "Launch HAL follow-up", path: "/dashboard/hal" };
  const aiFollowUpSecondaryAction: WidgetAction = claimsNeedReview
    ? { label: "Open collections page", path: "/ar" }
    : hasCollectionPressure
      ? { label: "Open collections page", path: "/ar" }
      : { label: "Open Claims Workbench", path: "/claims-workbench" };

  const widgets: FinancialWidget[] = [
    {
      id: "case-acceptance",
      kicker: "Case acceptance",
      title: "Case Acceptance & Financing",
      statusLabel: hasTreatmentPlans ? "Live opportunity" : hasPaymentPlans ? "Partial coverage" : "Export required",
      statusTone: hasTreatmentPlans ? "positive" : hasPaymentPlans ? "neutral" : "warning",
      headline: hasTreatmentPlans
        ? `${formatCurrency(treatmentPlans?.totalAmount ?? 0)} pending plan value`
        : patientAr !== null
          ? `${formatCurrency(patientAr)} patient balance needs financing support`
          : "Financing opportunity is not quantified yet",
      summary: hasTreatmentPlans
        ? `${formatCountValue(treatmentPlans?.itemCount, "plans")} and ${formatCountValue(paymentPlans?.itemCount ?? 0, "payment plans")} are available for front-desk financing conversations.`
        : "Approved treatment-plan and payment-plan exports unlock real case value tracking and financing follow-up from the same dashboard.",
      metrics: [
        { label: "Treatment plans", value: hasTreatmentPlans ? formatCountValue(treatmentPlans?.itemCount) : "Pending export" },
        { label: "Payment plans", value: hasPaymentPlans ? formatCountValue(paymentPlans?.itemCount) : "Pending export" },
        { label: "Patient A/R", value: formatCurrencyValue(patientAr) },
      ],
      nextAction: hasTreatmentPlans
        ? "Prioritize patients with unfinished treatment and high balances for financing outreach."
        : "Import treatment-plan and payment-plan summaries to quantify case acceptance risk.",
      actionLabel: caseAcceptancePrimaryAction.label,
      actionPath: caseAcceptancePrimaryAction.path,
      secondaryActionLabel: caseAcceptanceSecondaryAction.label,
      secondaryActionPath: caseAcceptanceSecondaryAction.path,
    },
    {
      id: "ap-automation",
      kicker: "Accounts payable",
      title: "AP Automation",
      statusLabel: quickBooksReady ? "Connected" : "Needs review",
      statusTone: quickBooksReady ? "positive" : "warning",
      headline:
        summary?.monthExpenses !== null
          ? `${formatCurrency(summary?.monthExpenses ?? 0)} current spend in review`
          : "Expense automation lane is not quantified yet",
      summary: quickBooksReady
        ? "QuickBooks imports are fresh enough to monitor vendor spend, batch review, and payable exceptions from one view."
        : quickBooksStatus?.message?.trim() || "QuickBooks imports need attention before AP automation can be trusted.",
      metrics: [
        { label: "Feed", value: quickBooksReady ? "Ready" : quickBooksStatus?.status || "Unavailable" },
        { label: "Imported rows", value: importedRowCount > 0 ? formatCountValue(importedRowCount) : "0" },
        { label: "Top expense", value: summary?.topExpenseCategory ?? "Unavailable" },
      ],
      nextAction: quickBooksReady
        ? "Review large expense categories before approving the next vendor payment batch."
        : "Repair the QuickBooks import lane before using AP automation for payment review.",
      actionLabel: apAutomationPrimaryAction.label,
      actionPath: apAutomationPrimaryAction.path,
      secondaryActionLabel: apAutomationSecondaryAction.label,
      secondaryActionPath: apAutomationSecondaryAction.path,
    },
    {
      id: "smart-claims",
      kicker: "Billing transparency",
      title: "Smart Claims & Invoicing",
      statusLabel: claimsAvailable ? "Billing live" : "Awaiting exports",
      statusTone: claimsAvailable ? "positive" : "warning",
      headline: claimsAvailable
        ? `${formatCurrency(claimsSummary?.true_outstanding_claims_amount ?? 0)} insurance receivables`
        : "Outstanding claims are not quantified yet",
      summary: claimsAvailable
        ? `${formatCountValue(claimsSummary?.true_outstanding_claims_count, "outstanding claims")} and ${formatCountValue(claimsSummary?.unsubmitted_claims_count, "unsubmitted claims")} are visible for payer follow-up.`
        : "Approved aggregate claims exports are still required before the dashboard can expose real outstanding and unsubmitted balances.",
      metrics: [
        { label: "Outstanding", value: formatCountValue(claimsSummary?.true_outstanding_claims_count ?? null) },
        { label: "Unsubmitted", value: formatCurrencyValue(claimsSummary?.unsubmitted_claims_amount ?? null) },
        { label: "Top payer", value: topOutstandingPayer?.label ?? "Unavailable" },
      ],
      nextAction: claimsAvailable
        ? `Escalate ${topOutstandingPayer?.label ?? "top payers"} and clear unsubmitted claims before month-end close.`
        : "Stage approved outstanding-claims and unsubmitted-claims exports into the SoftDent import lane.",
      actionLabel: smartClaimsPrimaryAction.label,
      actionPath: smartClaimsPrimaryAction.path,
      secondaryActionLabel: smartClaimsSecondaryAction.label,
      secondaryActionPath: smartClaimsSecondaryAction.path,
    },
    {
      id: "revenue-analytics",
      kicker: "Practice performance",
      title: "Real-Time Revenue Analytics",
      statusLabel: summary?.isStale ? "Stale feed" : "Live performance",
      statusTone: summary?.isStale ? "warning" : "positive",
      headline:
        summary?.monthProduction !== null
          ? `${formatCurrency(summary?.monthProduction ?? 0)} produced this month`
          : "Revenue run-rate is not available",
      summary: `Practice-wide collections pace is ${formatPercentValue(summary?.collectionPercent ?? null)} with production and QuickBooks metrics aligned in one view.`,
      metrics: [
        { label: "Collections", value: formatCurrencyValue(summary?.monthCollections ?? null) },
        { label: "Collection rate", value: formatPercentValue(summary?.collectionPercent ?? null) },
        { label: "Practice production", value: formatCurrencyValue(summary?.monthProduction ?? null) },
      ],
      nextAction: "Use the verified monthly production and collections trend to spot pacing risk early.",
      actionLabel: revenueAnalyticsPrimaryAction.label,
      actionPath: revenueAnalyticsPrimaryAction.path,
      secondaryActionLabel: revenueAnalyticsSecondaryAction.label,
      secondaryActionPath: revenueAnalyticsSecondaryAction.path,
    },
    {
      id: "ai-follow-up",
      kicker: "Collections outreach",
      title: "AI Follow-up & Collections",
      statusLabel: hasCollectionPressure ? "Priority queue" : claimsAvailable ? "AI-ready queue" : "Coverage pending",
      statusTone: hasCollectionPressure ? "warning" : claimsAvailable ? "positive" : "neutral",
      headline:
        (summary?.arOver90 ?? 0) > 0
          ? `${formatCurrency(summary?.arOver90 ?? 0)} aged 90+ still needs follow-up`
          : claimsAvailable
            ? "No 90+ A/R is currently flagged"
            : "Follow-up queue is not verified yet",
      summary: claimsAvailable
        ? `${formatCountValue(claimsSummary?.unsubmitted_claims_count, "unsubmitted claims")} and aged receivables can feed AI-assisted payment, recall, and reschedule outreach.`
        : "Claims export confidence and aged receivable detail must be verified before an AI follow-up queue can be trusted.",
      metrics: [
        { label: "90+ A/R", value: formatCurrencyValue(summary?.arOver90 ?? null) },
        { label: "Unsubmitted claims", value: formatCountValue(claimsSummary?.unsubmitted_claims_count ?? null) },
        { label: "Claims source", value: claimsSource?.confidenceLabel ?? "Manual review" },
      ],
      nextAction: hasCollectionPressure
        ? "Start with 90+ patient balances and unsubmitted claims before lower-risk reminders."
        : "Verify claims exports and collection rules before enabling automated outreach.",
      actionLabel: aiFollowUpPrimaryAction.label,
      actionPath: aiFollowUpPrimaryAction.path,
      secondaryActionLabel: aiFollowUpSecondaryAction.label,
      secondaryActionPath: aiFollowUpSecondaryAction.path,
    },
  ];

  if (!widgetFeed) {
    return widgets;
  }

  const practiceMetrics = asRecord(practiceFinancialOverview?.metrics);
  const apMetrics = asRecord(accountsPayableAutomation?.metrics);
  const claimsMetrics = asRecord(smartClaimsAndReceivables?.metrics);
  const careMetrics = asRecord(careDeliveryPerformance?.metrics);
  const monthlyRevenue = toOptionalNumber(practiceMetrics?.monthly_revenue);
  const monthlyNetIncome = toOptionalNumber(practiceMetrics?.monthly_net_income);
  const collectionRate = toOptionalNumber(practiceMetrics?.collection_rate);
  const openBillsTotal = toOptionalNumber(apMetrics?.open_bills_total);
  const expenseTotal = toOptionalNumber(apMetrics?.expense_total);
  const outstandingClaimAmount = toOptionalNumber(claimsMetrics?.outstanding_claim_amount);
  const outstandingClaimCount = toOptionalNumber(claimsMetrics?.outstanding_claim_count);
  const unsubmittedClaimCount = toOptionalNumber(claimsMetrics?.unsubmitted_claim_count);
  const accountsReceivableTotal = toOptionalNumber(claimsMetrics?.accounts_receivable_total);
  const patientCount = toOptionalNumber(careMetrics?.patient_count);
  const patientBalanceTotal = toOptionalNumber(careMetrics?.patient_balance_total);

  return widgets.map((widget) => {
    if (widget.id === "case-acceptance" && isSuccessfulHalWidget(careDeliveryPerformance)) {
      return {
        ...widget,
        statusLabel: toHalWidgetStatusLabel(careDeliveryPerformance.status, widget.statusLabel, widgetFeedSourceLabel),
        statusTone: toHalWidgetStatusTone(careDeliveryPerformance.status),
        headline: patientBalanceTotal !== null ? `${formatCurrency(patientBalanceTotal)} patient balance in active care` : widget.headline,
        summary: `${widgetFeedSourceLabel} published a current care-delivery balance snapshot from the latest import cache.`,
        metrics: [
          { label: "Patients", value: formatCountValue(patientCount) },
          { label: "Patient balance", value: formatCurrencyValue(patientBalanceTotal) },
          { label: "Feed status", value: toHalWidgetStatusLabel(careDeliveryPerformance.status, widget.statusLabel, widgetFeedSourceLabel) },
        ],
        nextAction: "Use the published care-delivery snapshot to prioritize financing and case presentation follow-up.",
      };
    }

    if (widget.id === "ap-automation" && isSuccessfulHalWidget(accountsPayableAutomation)) {
      return {
        ...widget,
        statusLabel: toHalWidgetStatusLabel(accountsPayableAutomation.status, widget.statusLabel, "QuickBooks"),
        statusTone: toHalWidgetStatusTone(accountsPayableAutomation.status),
        headline: openBillsTotal !== null ? `${formatCurrency(openBillsTotal)} open bills staged` : widget.headline,
        summary: "QuickBooks import cache published current payable exposure and expense totals for this dashboard slice.",
        metrics: [
          { label: "Open bills", value: formatCurrencyValue(openBillsTotal) },
          { label: "Expense total", value: formatCurrencyValue(expenseTotal) },
          { label: "Feed status", value: toHalWidgetStatusLabel(accountsPayableAutomation.status, widget.statusLabel, "QuickBooks") },
        ],
        nextAction: "Review QuickBooks payable exposure before approving the next vendor payment batch.",
      };
    }

    if (widget.id === "smart-claims" && isSuccessfulHalWidget(smartClaimsAndReceivables)) {
      return {
        ...widget,
        statusLabel: toHalWidgetStatusLabel(smartClaimsAndReceivables.status, widget.statusLabel, "SoftDent"),
        statusTone: toHalWidgetStatusTone(smartClaimsAndReceivables.status),
        headline: outstandingClaimAmount !== null ? `${formatCurrency(outstandingClaimAmount)} insurance receivables` : widget.headline,
        summary: "SoftDent import cache published current claim exposure and receivables totals for this dashboard slice.",
        metrics: [
          { label: "Outstanding", value: formatCountValue(outstandingClaimCount) },
          { label: "Receivables", value: formatCurrencyValue(accountsReceivableTotal) },
          { label: "Unsubmitted", value: formatCountValue(unsubmittedClaimCount) },
        ],
        nextAction: "Work the published outstanding claims queue before month-end close.",
      };
    }

    if (widget.id === "revenue-analytics" && isSuccessfulHalWidget(practiceFinancialOverview)) {
      return {
        ...widget,
        statusLabel: toHalWidgetStatusLabel(practiceFinancialOverview.status, widget.statusLabel, widgetFeedSourceLabel),
        statusTone: toHalWidgetStatusTone(practiceFinancialOverview.status),
        headline: monthlyRevenue !== null ? `${formatCurrency(monthlyRevenue)} revenue snapshot` : widget.headline,
        summary: `${widgetFeedSourceLabel} published synchronized revenue, net income, production, and collections totals for this dashboard slice.`,
        metrics: [
          { label: "Revenue", value: formatCurrencyValue(monthlyRevenue) },
          { label: "Net income", value: formatCurrencyValue(monthlyNetIncome) },
          { label: "Collection rate", value: formatPercentValue(collectionRate) },
        ],
        nextAction: "Use the published revenue snapshot to compare production, collections, and margin pacing before shifting resources.",
      };
    }

    if (widget.id === "ai-follow-up" && isSuccessfulHalWidget(smartClaimsAndReceivables)) {
      return {
        ...widget,
        statusLabel: toHalWidgetStatusLabel(smartClaimsAndReceivables.status, widget.statusLabel, "SoftDent"),
        statusTone: toHalWidgetStatusTone(smartClaimsAndReceivables.status),
        headline: accountsReceivableTotal !== null ? `${formatCurrency(accountsReceivableTotal)} receivables queue` : widget.headline,
        summary: "SoftDent import cache published a live follow-up queue for receivables and unsubmitted claims.",
        metrics: [
          { label: "Receivables", value: formatCurrencyValue(accountsReceivableTotal) },
          { label: "Outstanding claims", value: formatCountValue(outstandingClaimCount) },
          { label: "Unsubmitted claims", value: formatCountValue(unsubmittedClaimCount) },
        ],
        nextAction: "Start with the published receivables queue before lower-risk reminder workflows.",
      };
    }

    return widget;
  });
}

function OperationsWidgetCard({ widget }: { widget: FinancialWidget }) {
  return (
    <article className={["financial-widget-card", `financial-widget-card--${widget.id}`].join(" ")}>
      <div className="financial-widget-card__topline">
        <div>
          <div className="financial-widget-card__kicker">{widget.kicker}</div>
          <h3 className="financial-widget-card__title">{widget.title}</h3>
        </div>
        <span className={["financial-widget-chip", `financial-widget-chip--${widget.statusTone}`].join(" ")}>{widget.statusLabel}</span>
      </div>
      <div className="financial-widget-card__headline">{widget.headline}</div>
      <p className="financial-widget-card__summary">{widget.summary}</p>
      <div className="financial-widget-card__metrics">
        {widget.metrics.map((metric) => (
          <div key={`${widget.id}-${metric.label}`} className="financial-widget-card__metric">
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
          </div>
        ))}
      </div>
      <div className="financial-widget-card__footer">
        <span className="financial-widget-card__footer-label">Next action</span>
        <p>{widget.nextAction}</p>
        <div className="financial-widget-card__actions">
          <Link className="financial-widget-card__action" to={widget.actionPath}>
            {widget.actionLabel}
          </Link>
          <Link className="financial-widget-card__action financial-widget-card__action--secondary" to={widget.secondaryActionPath}>
            {widget.secondaryActionLabel}
          </Link>
        </div>
      </div>
    </article>
  );
}

function RingInsightsCard({
  centerValue,
  centerLabel,
  items,
}: {
  centerValue: string;
  centerLabel: string;
  items: Array<{ label: string; value: string; ratio: number; color: string }>;
}) {
  return (
    <div className="chart-card chart-card--analytics-ring">
      <div className="chart-card__header">
        <div>
          <div className="chart-kicker">Collection makeup</div>
          <div className="chart-title">Payment Channels</div>
        </div>
        <div className="chart-card__controls" aria-label="Payment mix metadata">
          <span className="chart-pill chart-pill--active">Live</span>
          <span className="chart-pill">Mix</span>
        </div>
      </div>
      <div className="analytics-ring-card">
        <div className="analytics-ring-card__visual">
          <svg className="analytics-ring-card__svg" viewBox="0 0 200 200" role="img" aria-label="Concentric payment and collection performance rings">
            {items.map((item, index) => {
              const radius = 74 - index * 18;
              const circumference = 2 * Math.PI * radius;
              const progress = circumference * (clampPercent(item.ratio) / 100);

              return (
                <g key={item.label} transform="rotate(-214 100 100)">
                  <circle className="analytics-ring-card__track" cx="100" cy="100" r={radius} />
                  <circle
                    className="analytics-ring-card__progress"
                    cx="100"
                    cy="100"
                    r={radius}
                    stroke={item.color}
                    strokeDasharray={`${progress} ${circumference - progress}`}
                  />
                </g>
              );
            })}
          </svg>
          <div className="analytics-ring-card__center">
            <strong>{centerValue}</strong>
            <span>{centerLabel}</span>
          </div>
        </div>
        <div className="analytics-ring-card__legend">
          {items.map((item) => (
            <div key={item.label} className="analytics-ring-card__legend-item">
              <span
                className={["analytics-ring-card__legend-dot", `analytics-ring-card__legend-dot--${item.label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`].join(" ")}
                aria-hidden="true"
              />
              <span className="analytics-ring-card__legend-label">{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function DashboardGridTile({
  title,
  customizeMode,
  children,
}: {
  title: string;
  customizeMode: boolean;
  children: ReactNode;
}) {
  return (
    <div className="financial-dashboard__grid-item">
      {customizeMode ? (
        <button type="button" className="financial-dashboard__grid-item-handle" aria-label={`Move ${title}`}>
          Move
        </button>
      ) : null}
      {children}
    </div>
  );
}

function FinancialDashboard() {
  const [customizeMode, setCustomizeMode] = useState(false);
  const [dashboardLayouts, setDashboardLayouts] = useState<FinancialDashboardLayouts>(() => loadFinancialDashboardLayouts());
  const { error: authSessionError, isAuthenticated, isLoading: isAuthSessionLoading, isSessionVerified, sessionStatusCode } = useAuthSession();
  const financialSummaryQuery = useQuery({
    queryKey: ["financial-summary"],
    queryFn: fetchFinancialSummary,
    enabled: isSessionVerified,
  });
  const verifiedFinancialSummary = isSessionVerified ? financialSummaryQuery.data : undefined;
  const summary = useMemo(() => buildDashboardSummaryFromFinancialSummary(verifiedFinancialSummary), [verifiedFinancialSummary]);
  const trendData = useMemo(() => buildDashboardTrendData(verifiedFinancialSummary), [verifiedFinancialSummary]);
  const insurancePatientTotals = useMemo(() => buildFinancialSummaryInsurancePatientTotals(verifiedFinancialSummary), [verifiedFinancialSummary]);
  const expenseCategoryData = useMemo(() => buildQuickBooksExpenseCategoryData(verifiedFinancialSummary), [verifiedFinancialSummary]);
  const monthlyExpenseTrend = useMemo(
    () => buildQuickBooksMonthlyExpenseTrendData(verifiedFinancialSummary?.quickBooksMonthlyExpenses, DASHBOARD_TREND_MONTH_WINDOW),
    [verifiedFinancialSummary?.quickBooksMonthlyExpenses],
  );
  const netIncomeTrendData = useMemo(
    () => buildProfitLossTrendData(verifiedFinancialSummary?.quickBooksProfitLossSummary, DASHBOARD_TREND_MONTH_WINDOW),
    [verifiedFinancialSummary?.quickBooksProfitLossSummary],
  );
  const hasTrendData = trendData.length > 0;
  const hasInsurancePatientTotals = insurancePatientTotals.insurance > 0 || insurancePatientTotals.patient > 0;
  const hasExpenseCategoryData = expenseCategoryData.length > 0;
  const hasMonthlyExpenseTrend = monthlyExpenseTrend.length > 0;
  const hasNetIncomeTrendData = netIncomeTrendData.length > 0;
  const arOver90AlertMessage = useMemo(() => buildArOver90AlertMessage(summary), [summary]);
  const hasSessionVerificationError = isAuthenticated && !isSessionVerified && Boolean(authSessionError) && sessionStatusCode !== 401;
  const trendDataUnavailableMessage = hasSessionVerificationError
    ? "Financial trend activity is unavailable right now."
    : "Financial trend activity will appear after access is confirmed.";
  const expenseDataUnavailableMessage = hasSessionVerificationError
    ? "Expense and profit activity is unavailable right now."
    : "Expense and profit activity will appear after access is confirmed.";
  const summaryUnavailableMessage = hasSessionVerificationError
    ? "Financial information is unavailable right now."
    : "Financial information will appear after access is confirmed.";
  const summaryBadgeLabel = "Practice overview";
  const heroLastImportValue = formatDateTime(summary?.lastImportAt);
  const paymentMixInsurance = insurancePatientTotals.insurance;
  const paymentMixPatient = insurancePatientTotals.patient;
  const paymentMixTotal = paymentMixInsurance + paymentMixPatient;
  const paymentMixCollectionRate = summary?.collectionPercent ?? 0;
  const paymentMixItems = [
    {
      label: "Insurance",
      value: formatCurrency(paymentMixInsurance),
      ratio: paymentMixTotal > 0 ? (paymentMixInsurance / paymentMixTotal) * 100 : 0,
      color: PRODUCTION_COLOR,
    },
    {
      label: "Patient",
      value: formatCurrency(paymentMixPatient),
      ratio: paymentMixTotal > 0 ? (paymentMixPatient / paymentMixTotal) * 100 : 0,
      color: COLLECTIONS_COLOR,
    },
    {
      label: "Collection rate",
      value: formatPercent(paymentMixCollectionRate),
      ratio: paymentMixCollectionRate,
      color: NET_INCOME_COLOR,
    },
  ];
  const cashflowActivityData = useMemo(() => {
    const byDate = new Map<string, { date: string; collections: number; expenses: number }>();

    for (const row of trendData) {
      const current = byDate.get(row.date) ?? { date: row.date, collections: 0, expenses: 0 };
      current.collections = Number(row.collections) || 0;
      byDate.set(row.date, current);
    }

    for (const row of monthlyExpenseTrend) {
      const current = byDate.get(row.date) ?? { date: row.date, collections: 0, expenses: 0 };
      current.expenses = Number(row.expenses) || 0;
      byDate.set(row.date, current);
    }

    return [...byDate.values()].sort((left, right) => left.date.localeCompare(right.date)).slice(-DASHBOARD_TREND_MONTH_WINDOW);
  }, [monthlyExpenseTrend, trendData]);
  const hasCashflowActivityData = cashflowActivityData.length > 0 && cashflowActivityData.some((row) => row.collections > 0 || row.expenses > 0);
  const highTechWidgets = useMemo(
    () =>
      buildHighTechFinanceWidgets({
        financialSummary: verifiedFinancialSummary,
        summary,
      }),
    [summary, verifiedFinancialSummary],
  );

  useEffect(() => {
    saveFinancialDashboardLayouts(dashboardLayouts);
  }, [dashboardLayouts]);

  const paymentMixCard = hasInsurancePatientTotals ? (
    <RingInsightsCard centerValue={formatCurrency(paymentMixTotal)} centerLabel="Captured this period" items={paymentMixItems} />
  ) : (
    <ChartUnavailableCard title="Payment Channels" message="Verified insurance, patient, and collection mix data is not available from the current backend summary yet." />
  );
  const cashflowActivityCard = hasCashflowActivityData ? (
    <div className="chart-card chart-card--activity">
      <div className="chart-card__header">
        <div>
          <div className="chart-kicker">Cashflow activity</div>
          <div className="chart-title">Collections vs Expenses</div>
        </div>
        <div className="chart-card__controls" aria-label="Cashflow activity metadata">
          <span className="chart-pill chart-pill--active">{DASHBOARD_TREND_WINDOW_LABEL}</span>
          <span className="chart-pill">Monthly</span>
        </div>
      </div>
      <div className="chart-body">
        <CurrencyBarChart
          data={cashflowActivityData}
          bars={[
            { dataKey: "collections", name: "Collections", color: PRODUCTION_COLOR },
            { dataKey: "expenses", name: "Expenses", color: COLLECTIONS_COLOR },
          ]}
          height={250}
        />
      </div>
    </div>
  ) : (
    <ChartUnavailableCard title="Collections vs Expenses" message={expenseDataUnavailableMessage} className="chart-card--activity" />
  );

  const productionTrendCard = hasTrendData ? (
    <div className="chart-card halfsize">
      <div className="chart-title">Production Trend</div>
      <div className="chart-body">
        <CurrencyLineChart data={trendData} lines={[{ dataKey: "production", name: "Production", color: PRODUCTION_COLOR }]} height={160} legend={false} />
      </div>
    </div>
  ) : (
    <ChartUnavailableCard title="Production Trend" message={trendDataUnavailableMessage} />
  );

  const collectionsTrendCard = hasTrendData ? (
    <div className="chart-card halfsize">
      <div className="chart-title">Collections Trend</div>
      <div className="chart-body">
        <CurrencyLineChart data={trendData} lines={[{ dataKey: "collections", name: "Collections", color: COLLECTIONS_COLOR }]} height={160} legend={false} />
      </div>
    </div>
  ) : (
    <ChartUnavailableCard title="Collections Trend" message={trendDataUnavailableMessage} />
  );

  const productionCollectionsCard = hasTrendData ? (
    <div className="chart-card chart-card--featured">
      <FeaturedChartHeader />
      <div className="chart-body">
        <CurrencyLineChart
          data={trendData}
          lines={[
            { dataKey: "production", name: "Production", color: PRODUCTION_COLOR },
            { dataKey: "collections", name: "Collections", color: COLLECTIONS_COLOR },
          ]}
          height={280}
        />
      </div>
    </div>
  ) : (
    <div className="chart-card chart-card--featured">
      <FeaturedChartHeader />
      <div className="page-state-card page-state-card--info">{trendDataUnavailableMessage}</div>
    </div>
  );

  const expenseCategoryCard = hasExpenseCategoryData ? (
    <div className="chart-card halfsize">
      <div className="chart-title">Expense Categories</div>
      <div className="chart-body">
        <HorizontalExpenseBarChart data={expenseCategoryData} height={160} />
      </div>
    </div>
  ) : (
    <ChartUnavailableCard title="Expense Categories" message={expenseDataUnavailableMessage} />
  );

  const monthlyExpenseTrendCard = hasMonthlyExpenseTrend ? (
    <div className="chart-card halfsize">
      <div className="chart-title">Monthly Expense Trend</div>
      <div className="chart-body">
        <CurrencyBarChart data={monthlyExpenseTrend} bars={[{ dataKey: "expenses", name: "Expenses", color: EXPENSES_COLOR }]} height={160} legend={false} />
      </div>
    </div>
  ) : (
    <ChartUnavailableCard title="Monthly Expense Trend" message={expenseDataUnavailableMessage} />
  );

  const netIncomeTrendCard = hasNetIncomeTrendData ? (
    <div className="chart-card halfsize">
      <div className="chart-title">Net Income Trend</div>
      <div className="chart-body">
        <CurrencyLineChart data={netIncomeTrendData} lines={[{ dataKey: "netIncome", name: "Net Income", color: NET_INCOME_COLOR }]} height={160} legend={false} />
      </div>
    </div>
  ) : (
    <ChartUnavailableCard title="Net Income Trend" message={expenseDataUnavailableMessage} />
  );

  const arAgingCard = summary && summary.totalAR !== null ? (
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
  );

  const trailingCollectionsCard = hasTrendData ? (
    <div className="chart-card halfsize">
      <div className="chart-title">Trailing 24-Month Collections</div>
      <div className="chart-body">
        <CurrencyLineChart data={trendData} lines={[{ dataKey: "collections", name: "Collections", color: COLLECTIONS_COLOR }]} height={160} legend={false} />
      </div>
    </div>
  ) : (
    <ChartUnavailableCard title="Trailing 24-Month Collections" message={trendDataUnavailableMessage} />
  );

  const dashboardGridTiles = useMemo(
    () => [
      ...highTechWidgets.map((widget) => ({
        id: widget.id as FinancialDashboardTileId,
        title: widget.title,
        content: <OperationsWidgetCard widget={widget} />,
      })),
      {
        id: "featured" as const,
        title: "Production vs Collections",
        content: productionCollectionsCard,
      },
      {
        id: "payment-mix" as const,
        title: "Payment Channels",
        content: paymentMixCard,
      },
      {
        id: "cashflow" as const,
        title: "Collections vs Expenses",
        content: cashflowActivityCard,
      },
      {
        id: "production-trend" as const,
        title: "Production Trend",
        content: productionTrendCard,
      },
      {
        id: "collections-trend" as const,
        title: "Collections Trend",
        content: collectionsTrendCard,
      },
      {
        id: "expense-category" as const,
        title: "Expense Categories",
        content: expenseCategoryCard,
      },
      {
        id: "monthly-expense-trend" as const,
        title: "Monthly Expense Trend",
        content: monthlyExpenseTrendCard,
      },
      {
        id: "net-income-trend" as const,
        title: "Net Income Trend",
        content: netIncomeTrendCard,
      },
      {
        id: "ar-aging" as const,
        title: "A/R Aging",
        content: arAgingCard,
      },
      {
        id: "trailing-collections" as const,
        title: "Trailing 24-Month Collections",
        content: trailingCollectionsCard,
      },
    ],
    [
      arAgingCard,
      cashflowActivityCard,
      collectionsTrendCard,
      expenseCategoryCard,
      highTechWidgets,
      monthlyExpenseTrendCard,
      netIncomeTrendCard,
      paymentMixCard,
      productionCollectionsCard,
      productionTrendCard,
      trailingCollectionsCard,
    ],
  );

  function handleDashboardLayoutChange(_layout: Layout, layouts: FinancialDashboardLayouts) {
    setDashboardLayouts(mergeFinancialDashboardLayouts(layouts));
  }

  function handleResetDashboardLayout() {
    setCustomizeMode(false);
    setDashboardLayouts(resetFinancialDashboardLayouts());
  }

  if (isAuthSessionLoading) {
    return (
      <main className="dashboard-page financial-dashboard">
        <div className="dashboard-container">
          <LoadingSpinner label="Loading verified financial summary..." />
        </div>
      </main>
    );
  }

  if (isSessionVerified && financialSummaryQuery.isPending) {
    return (
      <main className="dashboard-page financial-dashboard">
        <div className="dashboard-container">
          <LoadingSpinner label="Loading verified financial summary..." />
        </div>
      </main>
    );
  }

  if (!summary) {
    return (
      <main className="dashboard-page financial-dashboard">
        <div className="dashboard-container">
          <header className="dashboard-header financial-dashboard__hero">
            <div className="dashboard-header__titles">
              <div className="financial-dashboard__breadcrumbs">Dashboard / Analytics report</div>
              <p className="eyebrow">Financial analytics</p>
              <h1 className="dashboard-title">New Ridge Family Financial</h1>
              <div className="dashboard-subtitle">A unified operating view for production, collections, expenses, and receivables across SoftDent and QuickBooks.</div>
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
    <main className="dashboard-page financial-dashboard">
      <div className="dashboard-container">
        <header className="dashboard-header financial-dashboard__hero">
          <div className="dashboard-header__titles">
            <div className="financial-dashboard__breadcrumbs">Dashboard / Analytics report</div>
            <p className="eyebrow">Financial analytics</p>
            <h1 className="dashboard-title">New Ridge Family Financial</h1>
            <div className="dashboard-subtitle">A unified operating view for production, collections, expenses, and receivables across SoftDent and QuickBooks.</div>
          </div>
          <div className="dashboard-header__right">
            <div className="header-actions financial-dashboard__hero-actions">
              <span className="badge badge-success">{summaryBadgeLabel}</span>
              <span className="badge">Cashflow view</span>
            </div>
            <div className="financial-dashboard__hero-meta">
              <div className="financial-dashboard__hero-stat">
                <span className="financial-dashboard__hero-stat-label">Updated</span>
                <span className="financial-dashboard__hero-stat-value">{heroLastImportValue}</span>
              </div>
              <div className="financial-dashboard__hero-stat">
                <span className="financial-dashboard__hero-stat-label">Net income</span>
                <span className="financial-dashboard__hero-stat-value">{formatCurrencyValue(summary?.estimatedNetIncome ?? null)}</span>
              </div>
            </div>
          </div>
        </header>

        <section className="status-toolbar" aria-label="Refresh and status toolbar">
          <div className="status-item">
            <span className="status-label">Collections pace</span>
            <span className="status-value">{formatPercentValue(summary?.collectionPercent ?? null)}</span>
          </div>
          <div className="status-item">
            <span className="status-label">Top expense</span>
            <span className="status-value">{summary?.topExpenseCategory ?? "Unavailable"}</span>
          </div>
          <div className="status-item">
            <span className="status-label">90+ A/R</span>
            <span className="status-value">{formatCurrencyValue(summary?.arOver90 ?? null)}</span>
          </div>
        </section>

        <section className="dashboard-summary-row" aria-label="Key financial metrics">
          {summary ? (
            <>
              <SummaryMetricCard
                title="Production"
                value={formatCurrencyValue(summary.monthProduction)}
                label="Month-to-date production"
                detail={`Last import ${formatDateTime(summary.lastImportAt)}`}
                badge={summary.isStale ? "Stale" : "Live"}
                badgeTone={summary.isStale ? "warning" : "positive"}
              />
              <SummaryMetricCard
                title="Collections"
                value={formatCurrencyValue(summary.monthCollections)}
                label="Month-to-date collections"
                detail={`Collection rate ${formatPercentValue(summary.collectionPercent)}`}
                badge={formatPercentValue(summary.collectionPercent)}
                badgeTone="positive"
              />
              <SummaryMetricCard
                title="Net income"
                value={formatCurrencyValue(summary.estimatedNetIncome)}
                label="Estimated month-to-date net"
                detail={`Top expense ${summary.topExpenseCategory ?? "Unavailable"}`}
                badge="Estimate"
                badgeTone="neutral"
              />
              <SummaryMetricCard
                title="A/R balance"
                value={formatCurrencyValue(summary.totalAR)}
                label="Current receivables"
                detail={`90+ aging ${formatCurrencyValue(summary.arOver90)}`}
                badge="Receivables"
                badgeTone="warning"
              />
            </>
          ) : (
            <section className="page-state-card page-state-card--info" aria-live="polite">
              Financial highlights are unavailable right now.
            </section>
          )}
        </section>

        <section className="financial-dashboard__widget-deck-section" aria-labelledby="finance-widget-deck-title">
          <div className="financial-dashboard__widget-deck-header">
            <div>
              <p className="eyebrow">Custom workspace</p>
              <h2 id="finance-widget-deck-title" className="financial-dashboard__widget-deck-title">
                Arrange your home dashboard around the widgets you actually use
              </h2>
            </div>
            <div className="financial-dashboard__layout-toolbar-copy">
              <p className="financial-dashboard__widget-deck-copy">
                Drag cards in customize mode to build a local focus view for billing, finance, and front-desk follow-up. Other dashboard pages stay fixed.
              </p>
              <div className="financial-dashboard__layout-actions">
                <button type="button" className="financial-dashboard__layout-action" onClick={() => setCustomizeMode((current) => !current)}>
                  {customizeMode ? "Done arranging" : "Customize layout"}
                </button>
                <button
                  type="button"
                  className="financial-dashboard__layout-action financial-dashboard__layout-action--secondary"
                  onClick={handleResetDashboardLayout}
                >
                  Reset layout
                </button>
              </div>
            </div>
          </div>
          <ResponsiveGridLayout
            className={customizeMode ? "financial-dashboard__custom-grid financial-dashboard__custom-grid--editing" : "financial-dashboard__custom-grid"}
            layouts={dashboardLayouts}
            breakpoints={FINANCIAL_DASHBOARD_BREAKPOINTS}
            cols={FINANCIAL_DASHBOARD_COLS}
            rowHeight={84}
            margin={[16, 16]}
            containerPadding={[0, 0]}
            isDraggable={customizeMode}
            isResizable={false}
            draggableHandle=".financial-dashboard__grid-item-handle"
            measureBeforeMount={false}
            onLayoutChange={handleDashboardLayoutChange}
          >
            {dashboardGridTiles.map((tile) => (
              <div key={tile.id}>
                <DashboardGridTile title={tile.title} customizeMode={customizeMode}>
                  {tile.content}
                </DashboardGridTile>
              </div>
            ))}
          </ResponsiveGridLayout>
        </section>

        {arOver90AlertMessage ? (
          <div className="dashboard-section-spacer">
            <CustomAlert message={arOver90AlertMessage} type="warning" />
          </div>
        ) : null}
      </div>
    </main>
  );
}

export default FinancialDashboard;
