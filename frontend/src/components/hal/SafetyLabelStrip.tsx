export function SafetyLabelStrip({ labels }: { labels: string[] }) {
  return (
    <div className="hal-safety-strip" aria-label="Safety labels">
      {labels.map((label) => (
        <span key={label}>{label}</span>
      ))}
    </div>
  );
}

export const OFFICE_MANAGER_SAFETY_LABELS = [
  "Draft only",
  "Requires human review",
  "Local only",
  "not_submitted",
  "Not written to SoftDent",
  "No email/fax/upload/Gateway",
] as const;
