import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import {
  createSoftDentLocalPacket,
  type SoftDentDraftArtifact,
  type SoftDentLocalPacketArtifact,
  type SoftDentLocalPacketRequest,
} from "../../api/client";
import type { SoftDentPacketApprovalAttestation, SoftDentPacketType } from "../../api/schemas";

const PACKET_TYPES: { value: SoftDentPacketType; label: string }[] = [
  { value: "approved_narrative_packet", label: "Approved local narrative packet" },
  { value: "appeal_prep_packet", label: "Local appeal-prep packet" },
  { value: "missing_document_checklist_packet", label: "Local missing-document checklist packet" },
  { value: "staff_task_packet", label: "Local staff task packet" },
  { value: "patient_claim_review_packet", label: "Local patient/claim review packet" },
  { value: "printable_internal_review_artifact", label: "Printable internal review artifact" },
  { value: "copied_draft_text_packet", label: "Copied draft text for human use" },
];

type AttestationState = {
  approved_by: string;
  approval_note: string;
  attestation_checked: boolean;
  acknowledged_local_only: boolean;
  acknowledged_not_submitted: boolean;
  acknowledged_no_softdent_writeback: boolean;
  acknowledged_no_external_delivery: boolean;
};

const initialAttestation: AttestationState = {
  approved_by: "",
  approval_note: "",
  attestation_checked: false,
  acknowledged_local_only: false,
  acknowledged_not_submitted: false,
  acknowledged_no_softdent_writeback: false,
  acknowledged_no_external_delivery: false,
};

export function ApprovedLocalPacketsPanel({
  selectedDraft,
  selectedPacket,
  onPacketCreated,
}: {
  selectedDraft: SoftDentDraftArtifact | null;
  selectedPacket: SoftDentLocalPacketArtifact | null;
  onPacketCreated: (packet: SoftDentLocalPacketArtifact) => void;
}) {
  const [packetType, setPacketType] = useState<SoftDentPacketType>("approved_narrative_packet");
  const [attestation, setAttestation] = useState<AttestationState>(initialAttestation);
  const mutation = useMutation({
    mutationFn: createSoftDentLocalPacket,
    onSuccess: onPacketCreated,
  });

  const allAttested =
    attestation.approved_by.trim().length > 0 &&
    attestation.approval_note.trim().length > 0 &&
    attestation.attestation_checked &&
    attestation.acknowledged_local_only &&
    attestation.acknowledged_not_submitted &&
    attestation.acknowledged_no_softdent_writeback &&
    attestation.acknowledged_no_external_delivery;
  const canCreatePacket = Boolean(selectedDraft) && allAttested && !mutation.isPending;

  function updateAttestation<K extends keyof AttestationState>(key: K, value: AttestationState[K]) {
    setAttestation((current) => ({ ...current, [key]: value }));
  }

  function submitPacket() {
    if (!selectedDraft || !canCreatePacket) return;
    const payload: SoftDentLocalPacketRequest = {
      draft_artifact: selectedDraft,
      packet_type: packetType,
      approval_attestation: {
        ...attestation,
        reviewed_at_utc: new Date().toISOString(),
      } satisfies SoftDentPacketApprovalAttestation,
    };
    mutation.mutate(payload);
  }

  const visiblePacket = mutation.data ?? selectedPacket;

  return (
    <section className="hal-workstation-card" aria-labelledby="hal-packets-title">
      <div className="hal-workstation-card__header">
        <p className="eyebrow">Approved local packets</p>
        <h2 id="hal-packets-title">Approve local-only internal artifacts</h2>
        <p>
          Local packets start from a reviewed Phase 2 draft. They are approved for internal use only and remain
          not_submitted with no external delivery.
        </p>
      </div>
      {!selectedDraft ? <p>Select or create a review draft before creating a local packet.</p> : null}
      <div className="hal-draft-form">
        <label>
          Packet type
          <select value={packetType} onChange={(event) => setPacketType(event.target.value as SoftDentPacketType)}>
            {PACKET_TYPES.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Approved by
          <input
            value={attestation.approved_by}
            onChange={(event) => updateAttestation("approved_by", event.target.value)}
            placeholder="Billing lead or reviewer"
          />
        </label>
        <label>
          Approval note
          <textarea
            value={attestation.approval_note}
            onChange={(event) => updateAttestation("approval_note", event.target.value)}
            rows={3}
            placeholder="Reviewed and approved for internal office use only."
          />
        </label>
        {[
          ["attestation_checked", "I reviewed the draft and attest it is ready for local internal use."],
          ["acknowledged_local_only", "Local only."],
          ["acknowledged_not_submitted", "not_submitted."],
          ["acknowledged_no_softdent_writeback", "Not written to SoftDent."],
          ["acknowledged_no_external_delivery", "No external delivery."],
        ].map(([key, label]) => (
          <label key={key} className="hal-command-center__checkbox">
            <input
              type="checkbox"
              checked={Boolean(attestation[key as keyof AttestationState])}
              onChange={(event) => updateAttestation(key as keyof AttestationState, event.target.checked)}
            />
            {label}
          </label>
        ))}
        <button type="button" className="refresh-button" onClick={submitPacket} disabled={!canCreatePacket}>
          {mutation.isPending ? "Creating local packet..." : "Create local packet"}
        </button>
      </div>
      {mutation.isError ? (
        <p className="hal-inline-error" role="alert">
          {mutation.error instanceof Error
            ? mutation.error.message
            : "Local packet could not be created. Check approval fields and roles."}
        </p>
      ) : null}
      {visiblePacket ? (
        <article className="hal-artifact-card">
          <h3>{visiblePacket.title}</h3>
          <dl className="hal-artifact-meta">
            <div>
              <dt>Packet type</dt>
              <dd>{visiblePacket.packet_type}</dd>
            </div>
            <div>
              <dt>Source draft</dt>
              <dd>{visiblePacket.source_draft_id}</dd>
            </div>
            <div>
              <dt>Submission status</dt>
              <dd>{visiblePacket.submission_status}</dd>
            </div>
            <div>
              <dt>External action</dt>
              <dd>{String(visiblePacket.external_action_performed)}</dd>
            </div>
            <div>
              <dt>SoftDent writeback</dt>
              <dd>{String(visiblePacket.softdent_writeback_performed)}</dd>
            </div>
            <div>
              <dt>Local only</dt>
              <dd>{String(visiblePacket.local_only)}</dd>
            </div>
          </dl>
          <div className="hal-safety-strip">
            <span>Local only</span>
            <span>Approved for internal use</span>
            <span>not_submitted</span>
            <span>Not written to SoftDent</span>
            <span>No email/fax/upload/Gateway</span>
          </div>
          <p>{visiblePacket.body}</p>
          <h4>Source facts preserved</h4>
          <p>{visiblePacket.source_fact_refs.join(", ") || "No source refs returned."}</p>
          <h4>Missing data preserved</h4>
          <p>{visiblePacket.missing_data_codes.join(", ") || "No missing data returned."}</p>
        </article>
      ) : null}
    </section>
  );
}
