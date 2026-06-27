import { useQuery } from "@tanstack/react-query";

import { fetchClaimPacketReadiness } from "../../api/client";
import { OFFICE_MANAGER_SAFETY_LABELS, SafetyLabelStrip } from "./SafetyLabelStrip";

const SAFE_ACTIONS = ["Review packet", "View missing items", "Prepare local draft"] as const;

export function ClaimPacketReadinessPanel({
  onAskPrefill,
}: {
  onAskPrefill?: (question: string) => void;
}) {
  const readinessQuery = useQuery({
    queryKey: ["claim-packet-readiness"],
    queryFn: fetchClaimPacketReadiness,
  });
  const payload = readinessQuery.data;
  const summary = payload?.summary;

  return (
    <section className="hal-workstation-card" aria-labelledby="hal-claim-packet-readiness-title">
      <div className="hal-workstation-card__header">
        <p className="eyebrow">Claim packet readiness</p>
        <h2 id="hal-claim-packet-readiness-title">Local claim packet review</h2>
        <p>
          HAL can prepare a local packet and draft. Staff must review before use. Nothing has been submitted or sent.
        </p>
      </div>
      <SafetyLabelStrip labels={[...OFFICE_MANAGER_SAFETY_LABELS]} />
      {readinessQuery.isPending ? <p>Loading claim packet readiness...</p> : null}
      {readinessQuery.isError ? (
        <p className="hal-inline-error" role="alert">
          {readinessQuery.error instanceof Error
            ? readinessQuery.error.message
            : "Claim packet readiness could not be loaded."}
        </p>
      ) : null}
      {summary ? (
        <div className="hal-snapshot-grid" aria-label="Claim packet readiness counts">
          <div className="hal-snapshot-card hal-snapshot-card--ok">
            <span>Ready</span>
            <strong>{summary.ready_count}</strong>
          </div>
          <div className="hal-snapshot-card hal-snapshot-card--pending">
            <span>Needs Review</span>
            <strong>{summary.needs_review_count}</strong>
          </div>
          <div className="hal-snapshot-card hal-snapshot-card--alert">
            <span>Blocked</span>
            <strong>{summary.blocked_count}</strong>
          </div>
        </div>
      ) : null}
      {payload?.items.length ? (
        <ul className="hal-attention-list">
          {payload.items.slice(0, 6).map((item) => (
            <li key={item.packet_id} className={`hal-attention-item hal-attention-item--${item.status === "blocked" ? "critical" : item.status === "needs_review" ? "warning" : "info"}`}>
              <strong>{item.claim_ref ? `${item.claim_ref}` : "Claim packet"}</strong>
              <p>{item.staff_summary}</p>
              {item.missing_items.length ? (
                <p className="hal-missing-data-notice__codes">Missing: {item.missing_items.join("; ")}</p>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
      <div className="hal-automation-grid">
        {SAFE_ACTIONS.map((label) => (
          <button
            key={label}
            type="button"
            className="hal-automation-tile__action"
            disabled={label === "Prepare local draft"}
            title={
              label === "Prepare local draft"
                ? "Local draft preparation remains review-only in this version."
                : undefined
            }
            onClick={() => {
              if (!onAskPrefill) {
                return;
              }
              if (label === "Review packet") {
                onAskPrefill("claim packet readiness");
              } else if (label === "View missing items") {
                onAskPrefill("which claim packets are blocked");
              } else {
                onAskPrefill("what can HAL draft locally for claim packets");
              }
            }}
          >
            {label}
          </button>
        ))}
      </div>
    </section>
  );
}
