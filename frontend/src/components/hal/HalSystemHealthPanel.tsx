import type { FinancialSummaryResponse } from "../../api/client";
import type { HalStatusResponse } from "../../api/schemas";

function statusText(value: unknown, fallback = "unknown") {
  if (typeof value === "string" && value.trim()) return value;
  if (typeof value === "boolean") return value ? "ready" : "unavailable";
  return fallback;
}

export function HalSystemHealthPanel({
  halStatus,
  financialSummary,
  isLoading,
}: {
  halStatus?: HalStatusResponse;
  financialSummary?: FinancialSummaryResponse;
  isLoading?: boolean;
}) {
  const softDent = halStatus?.financial_sources?.softdent;
  const quickBooks = halStatus?.financial_sources?.quickbooks;
  const softDentClaims = softDent?.live_claims;
  const softDentNotes = softDent?.live_clinical_notes;
  const quickBooksRevenue = quickBooks?.live_revenue;
  const latestRefresh = financialSummary?.latestSoftDentRefreshAt ?? financialSummary?.generatedAt ?? "";

  return (
    <section className="hal-workstation-card hal-system-health" aria-labelledby="hal-system-health-title">
      <div className="hal-workstation-card__header">
        <p className="eyebrow">System health</p>
        <h2 id="hal-system-health-title">Local readiness</h2>
      </div>
      {isLoading ? <p>Checking local sources...</p> : null}
      <dl className="hal-artifact-meta">
        <div>
          <dt>Backend</dt>
          <dd>{halStatus?.backend || "unknown"}</dd>
        </div>
        <div>
          <dt>24B lane</dt>
          <dd>{halStatus?.mode || "available through HAL"}</dd>
        </div>
        <div>
          <dt>30B lane</dt>
          <dd>optional second opinion</dd>
        </div>
        <div>
          <dt>SoftDent claims</dt>
          <dd>{statusText(softDentClaims?.available)}</dd>
        </div>
        <div>
          <dt>Clinical notes</dt>
          <dd>{statusText(softDentNotes?.available)}</dd>
        </div>
        <div>
          <dt>QuickBooks</dt>
          <dd>{statusText(quickBooksRevenue?.available)}</dd>
        </div>
        <div>
          <dt>Last index / source refresh</dt>
          <dd>{latestRefresh || "unknown"}</dd>
        </div>
      </dl>
    </section>
  );
}
