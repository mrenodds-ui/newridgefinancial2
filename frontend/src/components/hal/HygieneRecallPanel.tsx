import { MissingDataNotice } from "./MissingDataNotice";
import { SafetyLabelStrip } from "./SafetyLabelStrip";

export function HygieneRecallPanel() {
  return (
    <section className="hal-workstation-card" aria-labelledby="hal-hygiene-recall-title">
      <div className="hal-workstation-card__header">
        <p className="eyebrow">Hygiene / recall</p>
        <h2 id="hal-hygiene-recall-title">Overdue recall and hygiene follow-up</h2>
      </div>
      <SafetyLabelStrip labels={["Local only", "Requires human review", "not_submitted"]} />
      <MissingDataNotice
        title="Hygiene and recall source is not available yet"
        detail="HAL will not fabricate overdue recall, unscheduled hygiene, or forms-update lists until a real recall/hygiene export is approved."
        codes={["missing_hygiene_recall_export"]}
      />
    </section>
  );
}
