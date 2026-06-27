import type { FinancialSummaryResponse } from "../../api/client";
import { MissingDataNotice } from "./MissingDataNotice";
import { OFFICE_MANAGER_SAFETY_LABELS, SafetyLabelStrip } from "./SafetyLabelStrip";

function formatCurrency(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return "Unavailable";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value);
}

export function ClaimsFollowUpPanel({
  financialSummary,
  onPrefillDraftQuery,
}: {
  financialSummary?: FinancialSummaryResponse | null;
  onPrefillDraftQuery?: (query: string) => void;
}) {
  const claims = financialSummary?.claimsSummary;
  const available = Boolean(claims?.available);
  const unsubmittedAvailable = claims?.unsubmitted_claims_amount != null;
  const outstandingAvailable = claims?.true_outstanding_claims_amount != null;
  const unsubmittedCount = claims?.unsubmitted_claims_count ?? 0;
  const outstandingCount = claims?.true_outstanding_claims_count ?? 0;

  return (
    <section className="hal-workstation-card" aria-labelledby="hal-claims-followup-title">
      <div className="hal-workstation-card__header">
        <p className="eyebrow">Claims follow-up</p>
        <h2 id="hal-claims-followup-title">Unpaid, aging, and denied claim review</h2>
        <p>
          Use claims summaries and local drafts for staff review. HAL does not submit claims, contact payers, or perform
          external delivery.
        </p>
      </div>
      <SafetyLabelStrip labels={[...OFFICE_MANAGER_SAFETY_LABELS]} />
      {available ? (
        <dl className="hal-artifact-meta">
          <div>
            <dt>Unsubmitted claims</dt>
            <dd>
              {unsubmittedAvailable
                ? `${unsubmittedCount} claim(s) · ${formatCurrency(claims?.unsubmitted_claims_amount)}`
                : "Unavailable"}
            </dd>
          </div>
          <div>
            <dt>Outstanding claims</dt>
            <dd>
              {outstandingAvailable
                ? `${outstandingCount} claim(s) · ${formatCurrency(claims?.true_outstanding_claims_amount)}`
                : "Unavailable"}
            </dd>
          </div>
        </dl>
      ) : (
        <MissingDataNotice
          title="Claims follow-up data is unavailable"
          detail="Approved aggregate claims exports are required before HAL can expose real outstanding and unsubmitted balances."
          codes={["missing_softdent_claims_export"]}
        />
      )}
      <div className="hal-template-buttons">
        <button
          type="button"
          className="refresh-button"
          disabled={!onPrefillDraftQuery}
          onClick={() => onPrefillDraftQuery?.("denied claim follow-up checklist")}
        >
          Prepare claim follow-up draft
        </button>
        <button
          type="button"
          className="refresh-button"
          disabled={!onPrefillDraftQuery}
          onClick={() => onPrefillDraftQuery?.("missing documentation checklist")}
        >
          Prepare missing-document draft
        </button>
        <button
          type="button"
          className="refresh-button"
          disabled={!onPrefillDraftQuery}
          onClick={() => onPrefillDraftQuery?.("payer appeal prep summary")}
        >
          Prepare appeal prep draft
        </button>
      </div>
    </section>
  );
}
