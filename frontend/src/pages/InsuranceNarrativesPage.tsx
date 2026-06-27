import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import {
  approveAndExportInsuranceNarrativeWorkflow,
  createInsuranceNarrativeDraftWorkflow,
  type InsuranceNarrativeWorkflowResult,
} from "../api/client";
import { PageSurfaceHeader, PageSurfaceShell } from "../components/PageSurfaceHeader";

const FIXTURE_SAMPLE = {
  patientRef: "CHART-A",
  claimId: "CLAIM-1001",
  procedureIds: "PROC-CROWN-BUILDUP-3",
  narrativeType: "denied_claim_resubmission",
} as const;

const SOFTDENT_EXPORT_SAMPLE = {
  patientRef: "CHART-EXPORT",
  claimId: "CLAIM-EXPORT-1",
  procedureIds: "PROC-CROWN-30",
  narrativeType: "appeal",
} as const;

type AdapterMode = "fixture" | "softdent_export_file";

function sampleValuesForAdapterMode(mode: AdapterMode) {
  return mode === "softdent_export_file" ? SOFTDENT_EXPORT_SAMPLE : FIXTURE_SAMPLE;
}

function formatMissingDataLabel(code: string): string {
  if (code === "missing_softdent_ar") {
    return `${code} (A/R unavailable — not $0)`;
  }
  return code;
}

function SourceFactList({ facts }: { facts: InsuranceNarrativeWorkflowResult["packet"]["source_facts"] }) {
  if (!facts.length) {
    return <p className="hal-answer-card__meta">No scoped source facts in packet.</p>;
  }

  return (
    <ul className="hal-answer-card__list">
      {facts.map((fact) => (
        <li key={fact.fact_id}>
          <strong>{fact.fact_id}</strong> ({fact.source_type}) — {fact.text}
        </li>
      ))}
    </ul>
  );
}

export default function InsuranceNarrativesPage() {
  const [adapterMode, setAdapterMode] = useState<AdapterMode>("fixture");
  const [patientRef, setPatientRef] = useState<string>(FIXTURE_SAMPLE.patientRef);
  const [claimId, setClaimId] = useState<string>(FIXTURE_SAMPLE.claimId);
  const [procedureIds, setProcedureIds] = useState<string>(FIXTURE_SAMPLE.procedureIds);
  const [narrativeType, setNarrativeType] = useState<string>(FIXTURE_SAMPLE.narrativeType);
  const [runChecker, setRunChecker] = useState(false);
  const [reviewer, setReviewer] = useState("local-reviewer");
  const [notes, setNotes] = useState("Reviewed packet-bounded draft for local export preview.");
  const [approvalAttestation, setApprovalAttestation] = useState(false);
  const [exportFormat, setExportFormat] = useState<"markdown" | "plain_text">("markdown");

  const draftMutation = useMutation({
    mutationFn: createInsuranceNarrativeDraftWorkflow,
  });

  const exportMutation = useMutation({
    mutationFn: approveAndExportInsuranceNarrativeWorkflow,
  });

  const draftResult = draftMutation.data;
  const exportResult = exportMutation.data;
  const activeResult = exportResult ?? draftResult;
  const draftBlocked = draftResult?.draft.status === "blocked_missing_data";
  const canApprove = Boolean(draftResult && !draftBlocked && !exportResult);

  function handleAdapterModeChange(nextMode: AdapterMode) {
    setAdapterMode(nextMode);
    const sample = sampleValuesForAdapterMode(nextMode);
    setPatientRef(sample.patientRef);
    setClaimId(sample.claimId);
    setProcedureIds(sample.procedureIds);
    setNarrativeType(sample.narrativeType);
  }

  function handleCreateDraft(event: React.FormEvent) {
    event.preventDefault();
    exportMutation.reset();
    const parsedProcedureIds = procedureIds
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);

    draftMutation.mutate({
      patient_ref: patientRef.trim().toUpperCase(),
      claim_id: claimId.trim().toUpperCase() || null,
      procedure_ids: parsedProcedureIds.length ? parsedProcedureIds : null,
      narrative_type: narrativeType.trim(),
      run_checker: runChecker,
      adapter_mode: adapterMode,
    });
  }

  function handleApproveExport(event: React.FormEvent) {
    event.preventDefault();
    if (!draftResult || !approvalAttestation) {
      return;
    }

    exportMutation.mutate({
      packet: draftResult.packet,
      draft: draftResult.draft,
      reviewer: reviewer.trim(),
      notes: notes.trim(),
      approval_attestation: true,
      export_format: exportFormat,
      checker_summary: draftResult.checker_summary,
    });
  }

  return (
    <PageSurfaceShell className="insurance-narratives-page">
      <div className="page-content">
        <PageSurfaceHeader
          breadcrumbs="Billing / Narrative workflow"
          eyebrow="Insurance narratives"
          title="Operator narrative workflow"
          titleId="insurance-narratives-title"
          description="Local packet → draft → optional checker → human review → export preview only. No payer submission, email, fax, or upload occurs from this page."
          badges={[
            { label: "Local-Only" },
            { label: "Human Review Required" },
            { label: "Not Submitted" },
            { label: "No Payer Contact" },
          ]}
          statusItems={[
            { label: "Workflow stage", value: exportResult?.export ? "Export preview" : draftResult ? "Draft review" : "Scope entry" },
            { label: "Submission status", value: exportResult?.export?.submission_status ?? "not_submitted" },
            { label: "Checker", value: runChecker ? "Opt-in enabled" : "Off by default" },
          ]}
          badgesAriaLabel="Narrative workflow safety posture"
          statusAriaLabel="Narrative workflow status"
        />

        <section className="hal-answer-card" aria-labelledby="narrative-scope-heading">
          <h2 id="narrative-scope-heading">1. Scope</h2>
          <p className="hal-answer-card__meta">
            Sample defaults are local references only. Choose the data source that matches your backend
            configuration, then adjust scope fields as needed.
          </p>
          <form className="hal-form hal-form--narrative" onSubmit={handleCreateDraft}>
            <label htmlFor="narrative-adapter-mode">Data source</label>
            <select
              id="narrative-adapter-mode"
              className="hal-form__input"
              value={adapterMode}
              onChange={(event) => handleAdapterModeChange(event.target.value as AdapterMode)}
            >
              <option value="fixture">Fixture demo data</option>
              <option value="softdent_export_file">SoftDent export files</option>
            </select>

            {adapterMode === "softdent_export_file" ? (
              <p className="hal-answer-card__meta" role="note">
                SoftDent export mode reads server-configured local export files only. No E-Services, Gateway,
                database scraping, payer submission, email, fax, or upload.
              </p>
            ) : null}

            <label htmlFor="narrative-patient-ref">Patient ref</label>
            <input
              id="narrative-patient-ref"
              className="hal-form__input"
              value={patientRef}
              onChange={(event) => setPatientRef(event.target.value)}
              required
            />

            <label htmlFor="narrative-claim-id">Claim id</label>
            <input
              id="narrative-claim-id"
              className="hal-form__input"
              value={claimId}
              onChange={(event) => setClaimId(event.target.value)}
            />

            <label htmlFor="narrative-procedure-ids">Procedure ids (comma-separated)</label>
            <input
              id="narrative-procedure-ids"
              className="hal-form__input"
              value={procedureIds}
              onChange={(event) => setProcedureIds(event.target.value)}
            />

            <label htmlFor="narrative-type">Narrative type</label>
            <input
              id="narrative-type"
              className="hal-form__input"
              value={narrativeType}
              onChange={(event) => setNarrativeType(event.target.value)}
              required
            />

            <label className="hal-form__checkbox">
              <input
                type="checkbox"
                checked={runChecker}
                onChange={(event) => setRunChecker(event.target.checked)}
              />
              Run fast_review checker (opt-in only; default off)
            </label>

            <div className="hal-form__actions">
              <button type="submit" disabled={draftMutation.isPending}>
                {draftMutation.isPending ? "Creating draft…" : "Create draft"}
              </button>
            </div>
          </form>
          {draftMutation.isError ? (
            <p className="hal-answer-card__error" role="alert">
              {draftMutation.error instanceof Error ? draftMutation.error.message : "Draft request failed."}
            </p>
          ) : null}
        </section>

        {draftResult ? (
          <section className="hal-answer-card" aria-labelledby="narrative-draft-heading">
            <h2 id="narrative-draft-heading">2. Draft result</h2>
            <dl className="hal-answer-card__details">
              <div>
                <dt>Workflow status</dt>
                <dd>{draftResult.status}</dd>
              </div>
              <div>
                <dt>Packet id</dt>
                <dd>{draftResult.packet.packet_id}</dd>
              </div>
              <div>
                <dt>Draft id</dt>
                <dd>{draftResult.draft.draft_id}</dd>
              </div>
              <div>
                <dt>Draft status</dt>
                <dd>{draftResult.draft.status}</dd>
              </div>
              <div>
                <dt>Source fact count</dt>
                <dd>{draftResult.packet.source_facts.length}</dd>
              </div>
            </dl>

            {draftBlocked ? (
              <p className="page-state-card page-state-card--error" role="alert">
                Draft is blocked due to missing required data. Review missing-data codes below. Local export is not
                available until a non-blocked draft is created.
              </p>
            ) : null}

            <h3>Missing data codes</h3>
            {draftResult.packet.missing_data.length ? (
              <ul className="hal-answer-card__list">
                {draftResult.packet.missing_data.map((item) => (
                  <li key={item.code}>
                    <strong>{formatMissingDataLabel(item.code)}</strong> — {item.label} ({item.severity}
                    {item.blocking ? ", blocking" : ", non-blocking"})
                  </li>
                ))}
              </ul>
            ) : (
              <p className="hal-answer-card__meta">No missing-data disclosures.</p>
            )}

            {draftResult.warnings.length ? (
              <>
                <h3>Warnings</h3>
                <ul className="hal-answer-card__list">
                  {draftResult.warnings.map((warning) => (
                    <li key={`${warning.code}-${warning.message}`}>
                      <strong>{warning.code}</strong> — {warning.message}
                    </li>
                  ))}
                </ul>
              </>
            ) : null}

            {draftResult.checker_summary ? (
              <>
                <h3>Checker summary (advisory)</h3>
                <p className="hal-answer-card__meta">
                  Status: {draftResult.checker_summary.checker_status ?? "unknown"}; ready for human review:{" "}
                  {String(draftResult.checker_summary.ready_for_human_review ?? "n/a")}
                </p>
              </>
            ) : null}

            <h3>Source facts (summaries only)</h3>
            <SourceFactList facts={draftResult.packet.source_facts} />
          </section>
        ) : null}

        {canApprove ? (
          <section className="hal-answer-card" aria-labelledby="narrative-approve-heading">
            <h2 id="narrative-approve-heading">3. Approve and create local export</h2>
            <form className="hal-form hal-form--narrative" onSubmit={handleApproveExport}>
              <label htmlFor="narrative-reviewer">Reviewer</label>
              <input
                id="narrative-reviewer"
                className="hal-form__input"
                value={reviewer}
                onChange={(event) => setReviewer(event.target.value)}
                required
              />

              <label htmlFor="narrative-notes">Review notes</label>
              <textarea
                id="narrative-notes"
                className="hal-form__textarea"
                rows={4}
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                required
              />

              <label htmlFor="narrative-export-format">Export format</label>
              <select
                id="narrative-export-format"
                className="hal-form__input"
                value={exportFormat}
                onChange={(event) => setExportFormat(event.target.value as "markdown" | "plain_text")}
              >
                <option value="markdown">markdown</option>
                <option value="plain_text">plain_text</option>
              </select>

              <label className="hal-form__checkbox">
                <input
                  type="checkbox"
                  checked={approvalAttestation}
                  onChange={(event) => setApprovalAttestation(event.target.checked)}
                  required
                />
                I attest this draft was human-reviewed and this export must not be auto-submitted to any payer.
              </label>

              <div className="hal-form__actions">
                <button type="submit" disabled={exportMutation.isPending || !approvalAttestation}>
                  {exportMutation.isPending ? "Creating local export…" : "Approve and create local export"}
                </button>
              </div>
            </form>
            {exportMutation.isError ? (
              <p className="hal-answer-card__error" role="alert">
                {exportMutation.error instanceof Error ? exportMutation.error.message : "Export request failed."}
              </p>
            ) : null}
          </section>
        ) : null}

        {exportResult?.export ? (
          <section className="hal-answer-card" aria-labelledby="narrative-export-heading">
            <h2 id="narrative-export-heading">4. Export preview</h2>
            <p className="page-state-card page-state-card--info" role="status">
              Not submitted — local export only. No payer submission, email, fax, or upload occurred.
            </p>
            <dl className="hal-answer-card__details">
              <div>
                <dt>Review id</dt>
                <dd>{exportResult.review?.review_id}</dd>
              </div>
              <div>
                <dt>Export id</dt>
                <dd>{exportResult.export.export_id}</dd>
              </div>
              <div>
                <dt>Submission status</dt>
                <dd>{exportResult.export.submission_status}</dd>
              </div>
              <div>
                <dt>Review status</dt>
                <dd>{exportResult.review?.status}</dd>
              </div>
            </dl>

            <h3>Export body</h3>
            <pre className="hal-answer-card__pre">{exportResult.export.body}</pre>
          </section>
        ) : null}

        {activeResult && !exportResult?.export ? (
          <p className="hal-answer-card__meta">
            Workflow ends at draft preview when blocked or before approval. Submission status remains not_submitted.
          </p>
        ) : null}
      </div>
    </PageSurfaceShell>
  );
}
