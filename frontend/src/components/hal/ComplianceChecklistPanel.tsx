import { SafetyLabelStrip } from "./SafetyLabelStrip";

const CHECKLIST_ITEMS = [
  "Missing consent/forms review",
  "HIPAA/OSHA checklist ideas for staff review",
  "Scan documentation reminders",
  "Clinical documentation completeness checks",
  "Staff training checklist support",
];

export function ComplianceChecklistPanel() {
  return (
    <section className="hal-workstation-card" aria-labelledby="hal-compliance-title">
      <div className="hal-workstation-card__header">
        <p className="eyebrow">Compliance</p>
        <h2 id="hal-compliance-title">Local compliance checklist support</h2>
        <p>Checklist ideas for human review only. No external submission or delivery.</p>
      </div>
      <SafetyLabelStrip labels={["Draft only", "Requires human review", "Local only", "not_submitted"]} />
      <ul className="hal-attention-list">
        {CHECKLIST_ITEMS.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  );
}
