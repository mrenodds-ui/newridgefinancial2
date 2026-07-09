/* global globalThis, window */
(function initHalNarrativeLibrary(root) {
  "use strict";

  const FOCUSES = [
    "Medical Necessity",
    "Denial Appeal",
    "Prior Authorization",
    "Fracture Documentation",
    "Recurrent Decay",
    "Periodontal Medical Necessity",
    "Post-Operative Complication",
    "Replacement Restoration",
    "Accident or Trauma",
    "Alternate Benefit Dispute",
  ];
  const TONES = ["Professional", "Clinical-Detailed", "Concise", "Payer-Focused", "ADA-Reference"];
  const LENGTHS = ["Standard", "Brief"];

  const PROCEDURE_TAGS = {
    "Medical Necessity": ["crown", "build-up", "core", "onlay", "inlay", "restoration"],
    "Denial Appeal": ["crown", "build-up", "denied", "appeal"],
    "Prior Authorization": ["srp", "scaling", "periodontal", "implant", "surgery"],
    "Fracture Documentation": ["crown", "fracture", "crack", "build-up", "core"],
    "Recurrent Decay": ["crown", "decay", "restoration", "filling"],
    "Periodontal Medical Necessity": ["srp", "scaling", "root planing", "periodontal", "quadrant"],
    "Post-Operative Complication": ["extraction", "infection", "complication", "post-op"],
    "Replacement Restoration": ["crown", "bridge", "replacement", "failed"],
    "Accident or Trauma": ["trauma", "accident", "fracture", "emergency"],
    "Alternate Benefit Dispute": ["alternate", "downgrade", "benefit", "allowance"],
  };

  const DENIAL_TAGS = {
    "Medical Necessity": ["medical necessity", "not necessary", "insufficient"],
    "Denial Appeal": ["denied", "denial", "appeal", "reconsideration"],
    "Prior Authorization": ["prior auth", "authorization", "pre-auth"],
    "Fracture Documentation": ["fracture", "documentation", "radiograph", "x-ray", "photo"],
    "Recurrent Decay": ["decay", "recurrent", "secondary"],
    "Periodontal Medical Necessity": ["periodontal", "srp", "gum", "bone loss"],
    "Post-Operative Complication": ["complication", "infection", "pain"],
    "Replacement Restoration": ["replacement", "failed", "defective"],
    "Accident or Trauma": ["trauma", "accident", "injury"],
    "Alternate Benefit Dispute": ["alternate", "downgrade", "amalgam", "composite"],
  };

  const MEMOAI_SOURCE_IDS = [
    "insurance-narrative-local-only",
    "crown-d2740-medical-necessity",
    "narrative-appeal-structure-sections",
    "srp-d4341-vs-prophy-d1110-bundling",
    "no-external-submit-actions",
  ];

  function leadFor(focus, tone, length) {
    if (length === "Brief") return `Clinical summary (${focus.toLowerCase()}, ${tone.toLowerCase()} tone):`;
    if (tone === "Payer-Focused") {
      return `This letter supports claim review for ${focus.toLowerCase()} using documented clinical findings only.`;
    }
    if (tone === "ADA-Reference") {
      return `Per accepted dental standards of care, the following supports ${focus.toLowerCase()} for the billed service date.`;
    }
    return `The following documents ${focus.toLowerCase()} for the proposed treatment based on examination and supporting records.`;
  }

  function bodyFor(focus, tone, length) {
    let detail =
      "Examination revealed findings consistent with the billed procedure, including structural compromise and functional impairment that cannot be managed with a more conservative restoration.";
    if (length === "Brief") detail = "Examination supports the billed procedure; conservative options were insufficient.";
    if (focus === "Denial Appeal") {
      detail =
        "The original determination did not account for fracture/recurrent decay documentation and functional risk if the tooth were left untreated.";
    }
    if (focus === "Fracture Documentation") {
      detail =
        "Clinical and radiographic evaluation demonstrates fracture or crack propagation with loss of tooth integrity.";
    }
    if (focus === "Periodontal Medical Necessity") {
      detail = "Periodontal charting and radiographs show localized disease activity with attachment loss.";
    }
    if (tone === "Clinical-Detailed") detail += " Findings were recorded in the clinical chart and correlate with the submitted claim line.";
    return detail;
  }

  function closingFor(length) {
    if (length === "Brief") return "Staff review required before any payer submission. Local draft only — not submitted.";
    return "Based on the above, the proposed procedure is appropriate and medically necessary. Human review required; not submitted.";
  }

  function buildGenericDraftLibrary() {
    const library = [];
    let idx = 0;
    FOCUSES.forEach((focus) => {
      TONES.forEach((tone) => {
        LENGTHS.forEach((length) => {
          idx += 1;
          library.push({
            id: `nar-${String(idx).padStart(3, "0")}`,
            focus,
            tone,
            length,
            procedureTags: PROCEDURE_TAGS[focus] || [],
            denialTags: DENIAL_TAGS[focus] || [],
            memoAiSources: MEMOAI_SOURCE_IDS.slice(),
            text: [leadFor(focus, tone, length), bodyFor(focus, tone, length), closingFor(length)].join(" "),
            localOnly: true,
            submissionStatus: "not_submitted",
          });
        });
      });
    });
    return library;
  }

  function norm(value) {
    return String(value || "")
      .trim()
      .toLowerCase()
      .replace(/\s+/g, " ");
  }

  function claimField(claim, names) {
    for (let i = 0; i < names.length; i += 1) {
      const key = names[i];
      if (claim[key] != null && claim[key] !== "") return String(claim[key]);
    }
    return "";
  }

  function scoreNarrativeForClaim(template, claim) {
    const procedure = norm(claimField(claim, ["procedure", "Procedure"]));
    const denial = norm(claimField(claim, ["denialReason", "DenialReason", "denialReason"]));
    const status = norm(claimField(claim, ["status", "ClaimStatus", "claimStatus"]));
    let score = 0;
    (template.procedureTags || []).forEach((tag) => {
      if (procedure.includes(tag)) score += 3;
    });
    (template.denialTags || []).forEach((tag) => {
      if (denial.includes(tag) || procedure.includes(tag)) score += 3;
    });
    const focus = template.focus || "";
    if (status.includes("denied") && ["Denial Appeal", "Fracture Documentation", "Medical Necessity"].includes(focus)) score += 2;
    if (status.includes("review") && ["Medical Necessity", "Prior Authorization"].includes(focus)) score += 2;
    if (procedure.includes("periodontal") && focus.includes("Periodontal")) score += 4;
    if (procedure.includes("crown") && ["Fracture Documentation", "Recurrent Decay", "Medical Necessity"].includes(focus)) score += 2;
    return score;
  }

  function selectBestNarrativeForClaim(claim, library) {
    const lib = library || buildGenericDraftLibrary();
    const ranked = lib
      .map((template) => ({ template, score: scoreNarrativeForClaim(template, claim) }))
      .sort((a, b) => b.score - a.score || a.template.id.localeCompare(b.template.id));
    const best = ranked[0] || null;
    return {
      claimRef: claimField(claim, ["id", "ClaimId", "claimId"]),
      patientLabel: claimField(claim, ["patient", "PatientName"]),
      librarySize: lib.length,
      selected: best ? best.template : null,
      score: best ? best.score : 0,
      alternates: ranked.slice(1, 4).map((row) => row.template.id),
      safety: { localOnly: true, humanReviewRequired: true, notSubmitted: true },
    };
  }

  function formatNarrativeSelectionAnswer(selection, claim) {
    if (!selection || !selection.selected) {
      return "No narrative template could be selected — claims export or claim facts are missing.";
    }
    const sel = selection.selected;
    const lines = [
      `Insurance narrative selection (MemoAI-guided · ${selection.librarySize} generic drafts · local only):`,
      "",
      `Claim: ${selection.claimRef || "—"} · Patient: ${selection.patientLabel || "—"}`,
      `Best match: ${sel.id} · focus ${sel.focus} · tone ${sel.tone} · score ${selection.score}`,
      `Alternates: ${(selection.alternates || []).join(", ") || "—"}`,
      "",
      "Selected draft (staff must review before use; not submitted):",
      sel.text,
    ];
    if (claim && claim.procedure) lines.splice(3, 0, `Procedure: ${claim.procedure}`);
    if (claim && claim.denialReason) lines.splice(4, 0, `Denial reason: ${claim.denialReason}`);
    lines.push("", "Nothing has been submitted or sent.");
    return lines.join("\n");
  }

  function resolveClaimFromQuery(query, snapshot) {
    const match = String(query || "").match(/\b(CLM[-\w]+|\d{4,})\b/i);
    const ref = match ? match[1] : "";
    const claimsBlock = (snapshot && snapshot.claims) || {};
    const claims = claimsBlock.claims || claimsBlock.top || [];
    if (!claims.length) return null;
    if (!ref) return claims[0];
    return claims.find((c) => String(c.id || "").toLowerCase() === ref.toLowerCase()) || claims[0];
  }

  const api = {
    FOCUSES,
    TONES,
    LENGTHS,
    buildGenericDraftLibrary,
    selectBestNarrativeForClaim,
    formatNarrativeSelectionAnswer,
    resolveClaimFromQuery,
    scoreNarrativeForClaim,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  root.HalNarrativeLibrary = api;
})(typeof globalThis !== "undefined" ? globalThis : typeof window !== "undefined" ? window : {});
