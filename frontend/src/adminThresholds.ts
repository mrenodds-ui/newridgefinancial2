import type { AdminSummaryResponse } from "./api/schemas";

export type ThresholdSeverity = "good" | "watch" | "critical";
export type OwnerSection = "ar" | "claims" | "payers" | "providers";

export type ThresholdCheck = {
  id: string;
  label: string;
  description: string;
  current: number;
  target: number;
  comparator: "lte" | "gte";
  severity: ThresholdSeverity;
  action: string;
  triggered: boolean;
  gapPercent: number;
};

export type ThresholdContract = {
  checks: ThresholdCheck[];
  prioritySummary: string;
  priorityActions: string[];
  alertLevel: "ok" | "warning" | "critical";
  section: OwnerSection;
};

const SECTION_THRESHOLDS: Record<
  OwnerSection,
  Array<{
    id: string;
    label: string;
    description: string;
    thresholdPercent: number;
    comparator: "lte" | "gte";
    criticalGapPercent: number;
    recommendedAction: string;
    metric: (summary: AdminSummaryResponse) => number;
  }>
> = {
  ar: [
    {
      id: "ar_over_90_share",
      label: "Over 90 days share",
      description: "Portion of AR in 90+ bucket should stay at or below 25%.",
      thresholdPercent: 25,
      comparator: "lte",
      criticalGapPercent: 10,
      recommendedAction: "Prioritize collection calls for 90+ day balances and verify aging workflow ownership.",
      metric: (summary) => {
        const claims = summary.claims_summary as { high_risk_count?: number; count?: number } | undefined;
        const highRisk = numericOrZero(claims?.high_risk_count);
        const count = Math.max(numericOrZero(claims?.count), 1);
        return (highRisk / count) * 100;
      },
    },
    {
      id: "ar_current_share",
      label: "Current AR share",
      description: "Portion of AR in current bucket should stay at or above 50%.",
      thresholdPercent: 50,
      comparator: "gte",
      criticalGapPercent: 10,
      recommendedAction: "Tighten front-desk balance capture and same-week claim submission.",
      metric: (summary) => {
        const claims = summary.claims_summary as { average_age_days?: number } | undefined;
        const avgAge = numericOrZero(claims?.average_age_days);
        return Math.max(0, 100 - Math.min(avgAge, 100));
      },
    },
  ],
  claims: [
    {
      id: "claims_denial_rate",
      label: "Denial rate",
      description: "Claim denial rate should stay at or below 10%.",
      thresholdPercent: 10,
      comparator: "lte",
      criticalGapPercent: 5,
      recommendedAction: "Audit top denial reasons, retrain coding and attachment workflow, and rework denied claims daily.",
      metric: (summary) => {
        const claims = summary.claims_summary as { high_risk_count?: number; count?: number } | undefined;
        const highRisk = numericOrZero(claims?.high_risk_count);
        const count = Math.max(numericOrZero(claims?.count), 1);
        return (highRisk / count) * 100;
      },
    },
  ],
  payers: [
    {
      id: "payer_top_concentration",
      label: "Top payer concentration",
      description: "Top payer concentration should stay at or below 45%.",
      thresholdPercent: 45,
      comparator: "lte",
      criticalGapPercent: 10,
      recommendedAction: "Diversify case mix and monitor top-payer dependency in scheduling and treatment acceptance reviews.",
      metric: (summary) => {
        const providers = (summary.softdent_insights as { providers?: Array<{ collections?: number }> } | undefined)?.providers ?? [];
        const totals = providers.map((item) => numericOrZero(item.collections));
        const total = totals.reduce((acc, item) => acc + item, 0);
        if (!total) return 0;
        const max = Math.max(...totals, 0);
        return (max / total) * 100;
      },
    },
  ],
  providers: [
    {
      id: "provider_collection_efficiency",
      label: "Collection efficiency",
      description: "Collection efficiency should stay at or above 85%.",
      thresholdPercent: 85,
      comparator: "gte",
      criticalGapPercent: 10,
      recommendedAction: "Review same-day collection scripting and tighten checkout handoff for unscheduled balances.",
      metric: (summary) => {
        const kpis = summary.kpis ?? [];
        const latest = kpis.length ? kpis[kpis.length - 1] : null;
        const production = Math.max(numericOrZero(latest?.production), 1);
        const collections = numericOrZero(latest?.collections);
        return (collections / production) * 100;
      },
    },
  ],
};

function resolveSeverity(current: number, target: number, comparator: "lte" | "gte"): ThresholdSeverity {
  if (comparator === "lte") {
    if (current <= target) return "good";
    if (current <= target * 1.1) return "watch";
    return "critical";
  }

  if (current >= target) return "good";
  if (current >= target * 0.9) return "watch";
  return "critical";
}

function thresholdTriggered(current: number, target: number, comparator: "lte" | "gte"): boolean {
  return comparator === "lte" ? current > target : current < target;
}

function thresholdGapPercent(current: number, target: number, comparator: "lte" | "gte"): number {
  if (!target) return 0;
  const rawGap = comparator === "lte" ? current - target : target - current;
  return Math.max(0, (rawGap / target) * 100);
}

function numericOrZero(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

export function buildThresholdContract(summary: AdminSummaryResponse, section: OwnerSection): ThresholdContract {
  const sectionThresholds = SECTION_THRESHOLDS[section] ?? [];
  const checks: ThresholdCheck[] = sectionThresholds.map((item) => {
    const current = item.metric(summary);
    const target = item.thresholdPercent;
    const gapPercent = thresholdGapPercent(current, target, item.comparator);
    return {
      id: item.id,
      label: item.label,
      description: item.description,
      current,
      target,
      comparator: item.comparator,
      severity: resolveSeverity(current, target, item.comparator),
      action: item.recommendedAction,
      triggered: thresholdTriggered(current, target, item.comparator),
      gapPercent,
    };
  });

  const criticalCount = checks.filter((item) => item.severity === "critical").length;
  const watchCount = checks.filter((item) => item.severity === "watch").length;
  const prioritySummary = criticalCount
    ? `${criticalCount} critical checks require immediate action.`
    : watchCount
      ? `${watchCount} checks need close monitoring this refresh window.`
      : "All threshold checks are currently within target.";

  const priorityActions = checks
    .filter((item) => item.triggered)
    .sort((a, b) => b.gapPercent - a.gapPercent)
    .map((item) => `${item.label}: ${item.action}`);

  const alertLevel: "ok" | "warning" | "critical" = criticalCount ? "critical" : watchCount ? "warning" : "ok";

  return {
    checks,
    prioritySummary,
    priorityActions,
    alertLevel,
    section,
  };
}
