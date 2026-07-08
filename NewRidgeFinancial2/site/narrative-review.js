/* global globalThis, window */
/**
 * Human review and validation for insurance narrative drafts (Phase D / hal-10092).
 * Port of _legacy/app/insurance_narratives/review.py + draft boundary rules.
 */
(function initNarrativeReview(root) {
  "use strict";

  const MAX_DRAFT_LENGTH = 8000;
  const CLINICAL_NOTE_MAX = 1200;

  const FORBIDDEN_PHRASES = [
    "sent to payer",
    "faxed to",
    "uploaded to payer",
    "gateway submit",
    "writeback completed",
    "updated softdent",
    "auto-submitted",
    "has been submitted",
  ];

  const TOOTH_SURFACE_PROCEDURE_HINTS = /\b(crown|onlay|inlay|filling|composite|amalgam|extraction|implant|srp|scaling|root planing|perio|build.?up|core)\b/i;

  const TERMINAL_REVIEW_STATUSES = new Set(["approved", "rejected"]);
  const ACTIONABLE_REVIEW_STATUSES = new Set(["pending_review", "revision_requested"]);

  function utcNowIso() {
    return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
  }

  function deterministicReviewId(draftId) {
    let hash = 0;
    const s = String(draftId || "");
    for (let i = 0; i < s.length; i += 1) hash = (hash * 31 + s.charCodeAt(i)) >>> 0;
    return `narrative-review-${hash.toString(16).padStart(8, "0")}`;
  }

  function deterministicDraftId(packetId) {
    let hash = 0;
    const s = String(packetId || "");
    for (let i = 0; i < s.length; i += 1) hash = (hash * 31 + s.charCodeAt(i)) >>> 0;
    return `narrative-draft-${hash.toString(16).padStart(8, "0")}`;
  }

  function norm(value) {
    return String(value || "")
      .trim()
      .toLowerCase();
  }

  function claimField(claim, names) {
    for (let i = 0; i < names.length; i += 1) {
      const key = names[i];
      if (claim && claim[key] != null && claim[key] !== "") return String(claim[key]);
    }
    return "";
  }

  function normalizeClinicalNoteText(value) {
    const collapsed = String(value || "")
      .replace(/\s+/g, " ")
      .trim();
    if (collapsed.length <= CLINICAL_NOTE_MAX) return collapsed;
    return `${collapsed.slice(0, CLINICAL_NOTE_MAX - 3).trim()}...`;
  }

  function clinicalNoteRows(snapshot) {
    const bundle = (snapshot && snapshot.importBundle) || {};
    const rows = (bundle.softdent && bundle.softdent.clinicalNotes && bundle.softdent.clinicalNotes.rows) || [];
    return Array.isArray(rows) ? rows : [];
  }

  function notesForPatient(snapshot, patientLabel) {
    const target = norm(patientLabel);
    if (!target) return [];
    return clinicalNoteRows(snapshot).filter((row) => {
      const name = norm(row.PatientName || row.patientName || row.patient || "");
      return name && (name === target || name.includes(target) || target.includes(name));
    });
  }

  function buildCasePacket(claim, snapshot, options) {
    const opts = options || {};
    const patient = claimField(claim, ["patient", "PatientName", "patientName"]) || "Unknown patient";
    const claimId = claimField(claim, ["id", "ClaimId", "claimId"]) || "";
    const procedure = claimField(claim, ["procedure", "Procedure", "cdtCode"]);
    const serviceDate = claimField(claim, ["serviceDate", "ServiceDate", "date"]);
    const payer = claimField(claim, ["payer", "Payer"]);
    const denialReason = opts.denialReason || claimField(claim, ["denialReason", "DenialReason"]);
    const notes = notesForPatient(snapshot, patient);
    const sourceFacts = notes.slice(0, 6).map((row, idx) => {
      const text = normalizeClinicalNoteText(row.NoteText || row.ClinicalNote || row.noteText || row.text || "");
      const factId = `fact-${norm(patient).replace(/\s+/g, "-")}-note-${idx + 1}`;
      return { fact_id: factId, text: text || "Clinical note row present but text empty." };
    });
    const missingData = [];
    if (!serviceDate) {
      missingData.push({
        code: "missing_service_date",
        label: "Service date missing",
        blocking: true,
        why_it_matters: "Payer narratives require the billed service date.",
      });
    }
    if (!procedure) {
      missingData.push({
        code: "missing_procedure_code",
        label: "Procedure / CDT missing",
        blocking: true,
        why_it_matters: "Narrative must reference the billed procedure.",
      });
    }
    if (TOOTH_SURFACE_PROCEDURE_HINTS.test(procedure) && !claimField(claim, ["tooth", "Tooth", "surface", "Surface"])) {
      missingData.push({
        code: "missing_tooth_surface",
        label: "Tooth or surface not in claim export",
        blocking: false,
        why_it_matters: "Restorative narratives are stronger with tooth/surface when available.",
      });
    }
    if (!notes.length) {
      missingData.push({
        code: "missing_clinical_narrative",
        label: "Clinical note export missing for patient",
        blocking: true,
        why_it_matters: "HAL must not invent findings — import clinical notes before drafting.",
      });
    }
    const packetId = `packet-${claimId || norm(patient).replace(/\s+/g, "-") || "unknown"}`;
    return {
      packet_id: packetId,
      draft_id: deterministicDraftId(packetId),
      patient: { label: patient, patient_ref: norm(patient).replace(/\s+/g, "-") || "unknown" },
      claim: claimId ? { claim_id: claimId, payer, procedure, service_date: serviceDate, denial_reason: denialReason } : null,
      narrative_type: opts.focus || "Medical Necessity",
      source_facts: sourceFacts,
      missing_data: missingData,
      local_only: true,
      approval_required: true,
    };
  }

  function findForbiddenPhrases(text) {
    const lowered = norm(text);
    return FORBIDDEN_PHRASES.filter((phrase) => {
      if (!lowered.includes(phrase)) return false;
      const idx = lowered.indexOf(phrase);
      const before = lowered.slice(Math.max(0, idx - 8), idx);
      return !/\bnot\b|\bno\b|\bnever\b/.test(before);
    });
  }

  function validateDraftPayload(payload) {
    const text = String((payload && payload.text) || "").trim();
    const claim = (payload && payload.claim) || {};
    const packet = payload.packet || buildCasePacket(claim, payload.snapshot, payload);
    const issues = [];
    const missingFields = [];

    if (!text) issues.push("Draft body is empty.");
    if (text.length > MAX_DRAFT_LENGTH) issues.push(`Draft exceeds ${MAX_DRAFT_LENGTH} characters.`);

    (packet.missing_data || []).forEach((item) => {
      missingFields.push(item.code);
      if (item.blocking) issues.push(item.label);
    });

    findForbiddenPhrases(text).forEach((phrase) => issues.push(`Forbidden completion phrase: "${phrase}"`));

    const blocking = (packet.missing_data || []).some((item) => item.blocking) || issues.some((i) => /empty|exceeds|Forbidden/.test(i));
    const status = blocking ? "blocked_missing_data" : text ? "ready_for_human_review" : "draft";

    return {
      ok: !blocking && !!text,
      status,
      issues,
      missingFields,
      packet,
      draft_id: packet.draft_id,
      blocking,
      ready_for_human_review: status === "ready_for_human_review",
    };
  }

  function checkerSummaryFromValidation(result) {
    return {
      checker_status: result.status,
      missing_data_count: (result.missingFields || []).length,
      citation_issue_count: 0,
      possible_invented_fact_count: (result.missingFields || []).includes("missing_clinical_narrative") ? 1 : 0,
      contradiction_count: 0,
      ready_for_human_review: result.ready_for_human_review,
    };
  }

  function appendAuditEvent(review, event) {
    const events = (review.audit_events || []).slice();
    events.push(event);
    return events;
  }

  function createReviewRecord(draft, reviewer, checkerSummary) {
    const reviewerId = String(reviewer || "").trim();
    if (!reviewerId) throw new Error("reviewer is required");
    const timestamp = utcNowIso();
    const summary = checkerSummary || null;
    return {
      review_id: deterministicReviewId(draft.draft_id || draft.draftId),
      packet_id: draft.packet_id || draft.packetId,
      draft_id: draft.draft_id || draft.draftId,
      draft_status: draft.status || "ready_for_human_review",
      status: "pending_review",
      reviewer: reviewerId,
      checker_summary: summary,
      created_at: timestamp,
      audit_events: [
        {
          event_type: "review_created",
          at: timestamp,
          actor: reviewerId,
          previous_status: null,
          new_status: "pending_review",
          notes: "Review record created for human approval workflow.",
        },
      ],
    };
  }

  function assertActionable(review, action) {
    if (TERMINAL_REVIEW_STATUSES.has(review.status)) {
      throw new Error(`cannot ${action} a review already in status '${review.status}'`);
    }
    if (!ACTIONABLE_REVIEW_STATUSES.has(review.status)) {
      throw new Error(`cannot ${action} a review in status '${review.status}'`);
    }
  }

  function approveNarrativeDraft(review, opts) {
    const options = opts || {};
    const reviewerId = String(options.reviewer || "").trim();
    if (!reviewerId) throw new Error("reviewer is required");
    assertActionable(review, "approve");
    if (review.draft_status === "blocked_missing_data") {
      throw new Error("cannot approve a draft with status 'blocked_missing_data'");
    }
    if (!options.approval_attestation) {
      throw new Error("approval_attestation must be true to approve");
    }
    const timestamp = options.reviewed_at || utcNowIso();
    return Object.assign({}, review, {
      status: "approved",
      reviewer: reviewerId,
      reviewed_at: timestamp,
      notes: String(options.notes || "").trim() || null,
      approval_attestation: true,
      audit_events: appendAuditEvent(review, {
        event_type: "draft_approved",
        at: timestamp,
        actor: reviewerId,
        previous_status: review.status,
        new_status: "approved",
        notes: options.notes || "",
      }),
    });
  }

  function rejectNarrativeDraft(review, opts) {
    const options = opts || {};
    const reviewerId = String(options.reviewer || "").trim();
    if (!reviewerId) throw new Error("reviewer is required");
    assertActionable(review, "reject");
    const timestamp = options.reviewed_at || utcNowIso();
    return Object.assign({}, review, {
      status: "rejected",
      reviewer: reviewerId,
      reviewed_at: timestamp,
      notes: String(options.notes || "").trim() || null,
      approval_attestation: null,
      audit_events: appendAuditEvent(review, {
        event_type: "draft_rejected",
        at: timestamp,
        actor: reviewerId,
        previous_status: review.status,
        new_status: "rejected",
        notes: options.notes || "",
      }),
    });
  }

  function requestNarrativeRevision(review, opts) {
    const options = opts || {};
    const reviewerId = String(options.reviewer || "").trim();
    if (!reviewerId) throw new Error("reviewer is required");
    assertActionable(review, "request revision for");
    const normalized = (options.required_changes || []).map((c) => String(c).trim()).filter(Boolean);
    if (!normalized.length) throw new Error("required_changes must include at least one non-empty item");
    const timestamp = options.reviewed_at || utcNowIso();
    return Object.assign({}, review, {
      status: "revision_requested",
      reviewer: reviewerId,
      reviewed_at: timestamp,
      notes: String(options.notes || "").trim() || null,
      required_changes: normalized,
      approval_attestation: null,
      audit_events: appendAuditEvent(review, {
        event_type: "revision_requested",
        at: timestamp,
        actor: reviewerId,
        previous_status: review.status,
        new_status: "revision_requested",
        notes: options.notes || "",
      }),
    });
  }

  const api = {
    MAX_DRAFT_LENGTH,
    FORBIDDEN_PHRASES,
    buildCasePacket,
    validateDraftPayload,
    checkerSummaryFromValidation,
    createReviewRecord,
    approveNarrativeDraft,
    rejectNarrativeDraft,
    requestNarrativeRevision,
    notesForPatient,
    clinicalNoteRows,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  root.NarrativeReview = api;
})(typeof globalThis !== "undefined" ? globalThis : typeof window !== "undefined" ? window : {});
