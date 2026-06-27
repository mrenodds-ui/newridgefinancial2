export const MISSING_DATA_LABELS: Record<string, string> = {
  missing_softdent_ar: "DAYSHEET A/R not imported yet",
  missing_softdent_eod_report: "DAYSHEET report not imported yet",
  missing_softdent_claims_export: "Claims export not imported yet",
  missing_treatment_plan_export: "Treatment plan export not imported yet",
  missing_hygiene_recall_export: "Hygiene/recall export not imported yet",
  missing_vendor_tracker_source: "Vendor tracker source not imported yet",
  missing_softdent_patient_match: "No matching patient record found",
};

export function describeMissingDataCode(code: string): string {
  return MISSING_DATA_LABELS[code] ?? "Source not imported yet";
}

export function describeMissingDataCodes(codes: string[] | undefined | null): string {
  if (!codes || codes.length === 0) {
    return "";
  }
  const labels = Array.from(new Set(codes.map(describeMissingDataCode)));
  return labels.join("; ");
}
