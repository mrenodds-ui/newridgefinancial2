import { describe, expect, it } from "vitest";

import { describeMissingDataCode, describeMissingDataCodes } from "../components/hal/missingDataLabels";

describe("missing-data plain-English labels", () => {
  it("maps known SoftDent codes to staff language", () => {
    expect(describeMissingDataCode("missing_softdent_ar")).toBe("DAYSHEET A/R not imported yet");
    expect(describeMissingDataCode("missing_softdent_eod_report")).toBe("DAYSHEET report not imported yet");
    expect(describeMissingDataCode("missing_softdent_claims_export")).toBe("Claims export not imported yet");
    expect(describeMissingDataCode("missing_treatment_plan_export")).toBe("Treatment plan export not imported yet");
    expect(describeMissingDataCode("missing_hygiene_recall_export")).toBe("Hygiene/recall export not imported yet");
    expect(describeMissingDataCode("missing_vendor_tracker_source")).toBe("Vendor tracker source not imported yet");
  });

  it("falls back to a generic, non-technical label for unknown codes", () => {
    expect(describeMissingDataCode("missing_unknown_thing")).toBe("Source not imported yet");
    expect(describeMissingDataCode("missing_unknown_thing")).not.toContain("missing_");
  });

  it("joins and de-duplicates multiple codes", () => {
    expect(describeMissingDataCodes(["missing_softdent_ar", "missing_softdent_ar"])).toBe("DAYSHEET A/R not imported yet");
    expect(describeMissingDataCodes([])).toBe("");
    expect(describeMissingDataCodes(null)).toBe("");
  });
});
