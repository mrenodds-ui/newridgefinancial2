import { MissingDataNotice } from "./MissingDataNotice";
import { SafetyLabelStrip } from "./SafetyLabelStrip";

export function VendorIssueTrackerPanel() {
  return (
    <section className="hal-workstation-card" aria-labelledby="hal-vendor-title">
      <div className="hal-workstation-card__header">
        <p className="eyebrow">Vendor / software issues</p>
        <h2 id="hal-vendor-title">Local issue history and impact notes</h2>
        <p>Track SoftDent, Carestream, and vendor issues as local records only. No external ticket submission.</p>
      </div>
      <SafetyLabelStrip labels={["Local only", "not_submitted", "No external delivery"]} />
      <MissingDataNotice
        title="Vendor tracker uses local office tasks and reports"
        detail="Create local vendor follow-up tasks and local review artifacts. HAL does not open external support tickets or send communications."
        codes={["missing_vendor_tracker_source"]}
      />
    </section>
  );
}
