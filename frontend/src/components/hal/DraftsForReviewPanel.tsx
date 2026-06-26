import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { createSoftDentDraft, type SoftDentDraftArtifact, type SoftDentDraftRequest } from "../../api/client";
import type { SoftDentDraftType } from "../../api/schemas";

const DRAFT_TYPES: { value: SoftDentDraftType; label: string }[] = [
  { value: "clinical_note_proposal", label: "Clinical note proposal" },
  { value: "insurance_narrative_proposal", label: "Insurance narrative proposal" },
  { value: "claim_follow_up_checklist", label: "Claim follow-up checklist" },
  { value: "missing_document_checklist", label: "Missing-document checklist" },
  { value: "payer_appeal_prep_summary", label: "Payer appeal prep summary" },
  { value: "staff_task_recommendation", label: "Staff task recommendation" },
  { value: "internal_patient_summary", label: "Internal patient summary" },
];

export function DraftsForReviewPanel({
  selectedDraft,
  onDraftCreated,
}: {
  selectedDraft: SoftDentDraftArtifact | null;
  onDraftCreated: (draft: SoftDentDraftArtifact) => void;
}) {
  const [patientQuery, setPatientQuery] = useState("");
  const [claimId, setClaimId] = useState("");
  const [draftType, setDraftType] = useState<SoftDentDraftType>("insurance_narrative_proposal");
  const [includeClinicalContext, setIncludeClinicalContext] = useState(true);
  const [includeLedgerContext, setIncludeLedgerContext] = useState(false);

  const mutation = useMutation({
    mutationFn: createSoftDentDraft,
    onSuccess: onDraftCreated,
  });

  const canCreateDraft = patientQuery.trim().length >= 3 && !mutation.isPending;

  function submitDraft() {
    if (!canCreateDraft) return;
    const payload: SoftDentDraftRequest = {
      patient_query: patientQuery.trim(),
      claim_id: claimId.trim() || null,
      draft_type: draftType,
      workflow_reason: "hal_workstation_review",
      include_clinical_context: includeClinicalContext,
      include_ledger_context: includeLedgerContext,
    };
    mutation.mutate(payload);
  }

  const visibleDraft = mutation.data ?? selectedDraft;

  return (
    <section className="hal-workstation-card" aria-labelledby="hal-drafts-title">
      <div className="hal-workstation-card__header">
        <p className="eyebrow">Drafts for review</p>
        <h2 id="hal-drafts-title">Create Phase 2 draft artifacts</h2>
        <p>Drafts are review-required, local-only working text. They are not submitted or written to SoftDent.</p>
      </div>
      <div className="hal-draft-form">
        <label>
          Patient / claim question
          <input
            value={patientQuery}
            onChange={(event) => setPatientQuery(event.target.value)}
            placeholder="Patient name, claim id, payer, or procedure"
          />
        </label>
        <label>
          Claim ID (optional)
          <input value={claimId} onChange={(event) => setClaimId(event.target.value)} placeholder="CLM-1001" />
        </label>
        <label>
          Draft type
          <select value={draftType} onChange={(event) => setDraftType(event.target.value as SoftDentDraftType)}>
            {DRAFT_TYPES.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <label className="hal-command-center__checkbox">
          <input
            type="checkbox"
            checked={includeClinicalContext}
            onChange={(event) => setIncludeClinicalContext(event.target.checked)}
          />
          Include clinical-note summaries when authorized
        </label>
        <label className="hal-command-center__checkbox">
          <input
            type="checkbox"
            checked={includeLedgerContext}
            onChange={(event) => setIncludeLedgerContext(event.target.checked)}
          />
          Include ledger/A/R context only when a real source exists
        </label>
        <button type="button" className="refresh-button" onClick={submitDraft} disabled={!canCreateDraft}>
          {mutation.isPending ? "Creating draft..." : "Create review draft"}
        </button>
      </div>
      {mutation.isError ? (
        <p className="hal-inline-error" role="alert">
          {mutation.error instanceof Error ? mutation.error.message : "Draft could not be created. Check SoftDent roles."}
        </p>
      ) : null}
      {visibleDraft ? (
        <article className="hal-artifact-card">
          <h3>{visibleDraft.title}</h3>
          <dl className="hal-artifact-meta">
            <div>
              <dt>Draft type</dt>
              <dd>{visibleDraft.draft_type}</dd>
            </div>
            <div>
              <dt>Patient / claim</dt>
              <dd>{visibleDraft.patient_label}</dd>
            </div>
            <div>
              <dt>Review required</dt>
              <dd>{String(visibleDraft.review_required)}</dd>
            </div>
            <div>
              <dt>External action</dt>
              <dd>{String(visibleDraft.external_action_performed)}</dd>
            </div>
          </dl>
          <div className="hal-safety-strip">
            <span>Draft only</span>
            <span>Requires human review</span>
            <span>not_submitted</span>
            <span>Not written to SoftDent</span>
            <span>No email/fax/upload/Gateway</span>
          </div>
          <p>{visibleDraft.body}</p>
          <h4>Source facts</h4>
          <p>{visibleDraft.source_fact_refs.length ? visibleDraft.source_fact_refs.join(", ") : "No source refs returned."}</p>
          <h4>Missing data</h4>
          <p>{visibleDraft.missing_data_codes.length ? visibleDraft.missing_data_codes.join(", ") : "No missing data returned."}</p>
          <h4>Limitations</h4>
          <ul>
            {visibleDraft.limitations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>
      ) : null}
    </section>
  );
}
