import { MissingDataNotice } from "./MissingDataNotice";
import { SafetyLabelStrip } from "./SafetyLabelStrip";

export function TreatmentPlanFollowUpPanel() {
  return (
    <section className="hal-workstation-card" aria-labelledby="hal-treatment-plan-title">
      <div className="hal-workstation-card__header">
        <p className="eyebrow">Treatment plan follow-up</p>
        <h2 id="hal-treatment-plan-title">Unscheduled and accepted treatment review</h2>
      </div>
      <SafetyLabelStrip labels={["Local only", "Requires human review", "not_submitted"]} />
      <MissingDataNotice
        title="Treatment plan source is not available yet"
        detail="HAL will not fabricate unscheduled treatment, accepted-not-scheduled, or case-acceptance data until a real treatment-plan export is approved."
        codes={["missing_treatment_plan_export"]}
      />
    </section>
  );
}
