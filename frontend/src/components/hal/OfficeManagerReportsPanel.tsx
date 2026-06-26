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
      <p>Ask HAL for a report summary, then create a review draft or local packet for staff approval.</p>
    </section>
  );
}
