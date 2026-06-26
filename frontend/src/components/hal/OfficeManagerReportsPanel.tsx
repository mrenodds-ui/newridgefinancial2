import { useQuery } from "@tanstack/react-query";

import { fetchSoftDentEndOfDayAr } from "../../api/client";
import { MissingDataNotice } from "./MissingDataNotice";
import { SafetyLabelStrip } from "./SafetyLabelStrip";

const REPORT_TYPES = [
  "Morning huddle summary",
  "End-of-day summary",
  "Claims aging summary",
  "Missing documentation report",
  "Office-manager weekly summary",
  "Month-end checklist",
];

export function OfficeManagerReportsPanel() {
  const endOfDayArQuery = useQuery({
    queryKey: ["softdent-end-of-day-ar"],
    queryFn: fetchSoftDentEndOfDayAr,
  });
  const endOfDayAr = endOfDayArQuery.data;

  return (
    <section className="hal-workstation-card" aria-labelledby="hal-reports-title">
      <div className="hal-workstation-card__header">
        <p className="eyebrow">Reports</p>
        <h2 id="hal-reports-title">Local office-manager summaries</h2>
        <p>
          Report types are generated as local review drafts/checklists from authorized read-only data. They remain not
          submitted with no external delivery.
        </p>
      </div>
      <SafetyLabelStrip labels={["Draft only", "Local only", "not_submitted", "Not written to SoftDent"]} />
      <ul className="hal-attention-list">
        {REPORT_TYPES.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      {endOfDayArQuery.isError ? (
        <MissingDataNotice
          title="Daily End-of-Day report A/R unavailable"
          detail="Report-derived A/R requires authorized SoftDent ledger-read access and a verified report source."
          codes={["missing_softdent_ar"]}
        />
      ) : null}
      {endOfDayAr ? (
        endOfDayAr.available ? (
          <div className="hal-source-summary" role="status">
            <strong>{endOfDayAr.source_label}</strong>
            <p>
              Freshness: {endOfDayAr.freshness_status}. Report date: {endOfDayAr.report_date ?? "unknown"}.
            </p>
            <p>Total A/R: {endOfDayAr.total_ar == null ? "not provided" : `$${endOfDayAr.total_ar.toLocaleString()}`}</p>
            <p className="hal-attention-item__hint">
              Values are bounded report-derived A/R from the final page only, not patient-level ledger access.
            </p>
          </div>
        ) : (
          <MissingDataNotice
            title={
              endOfDayAr.freshness_status === "stale"
                ? "Daily End-of-Day report A/R is stale"
                : "Daily End-of-Day report A/R unavailable"
            }
            detail={
              endOfDayAr.stale_reason ||
              "HAL will not state an A/R balance or $0 until a current Daily End-of-Day report parses successfully."
            }
            codes={endOfDayAr.missing_data_codes}
          />
        )
      ) : null}
      <p>Ask HAL for a report summary, then create a review draft or local packet for staff approval.</p>
    </section>
  );
}
