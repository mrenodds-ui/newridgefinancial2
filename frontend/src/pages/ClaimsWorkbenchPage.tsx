import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { formatCurrency } from "../../utils/formatting";
import { fetchFinancialSummary, fetchHalPatientDossier, fetchHalStatus, generateHalInsuranceNarrative } from "../api/client";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { TransactionFeedStatusNotice } from "../components/dashboard/TransactionFeedStatusNotice";
import { queryKeys } from "../queryClient";

function confidenceBadgeClass(label: string, reviewRequired: boolean) {
  if (label === "manual review") {
    return "dashboard-import-status-badge dashboard-import-status-badge--error";
  }
  if (reviewRequired || label === "review suggested") {
    return "dashboard-import-status-badge dashboard-import-status-badge--pending";
  }
  return "dashboard-import-status-badge";
}

export default function ClaimsWorkbenchPage() {
  const [lookupQuestion, setLookupQuestion] = useState("");
  const [narrativeQuestion, setNarrativeQuestion] = useState("");

  const halStatusQuery = useQuery({
    queryKey: queryKeys.halStatus,
    queryFn: fetchHalStatus,
  });
  const financialSummaryQuery = useQuery({
    queryKey: ["financial-summary"],
    queryFn: fetchFinancialSummary,
  });
  const dossierMutation = useMutation({ mutationFn: fetchHalPatientDossier });
  const narrativeMutation = useMutation({
    mutationFn: generateHalInsuranceNarrative,
  });

  if (halStatusQuery.isPending || financialSummaryQuery.isPending) {
    return (
      <div className="dashboard-page claims-workbench-page">
        <LoadingSpinner label="Loading claims workbench..." />
      </div>
    );
  }

  if (halStatusQuery.isError || financialSummaryQuery.isError || !halStatusQuery.data || !financialSummaryQuery.data) {
    return (
      <div className="dashboard-page claims-workbench-page">
        <div className="page-state-card page-state-card--error">The claims workbench data could not be loaded right now.</div>
      </div>
    );
  }

  const softDentSources = halStatusQuery.data.financial_sources?.softdent;
  const claimsSource = softDentSources?.live_claims;
  const notesSource = softDentSources?.live_clinical_notes;
  const transactionFeedSource = softDentSources?.live_transaction_feed;
  const healthFlags = financialSummaryQuery.data.healthFlags ?? [];
  const claimsSummary = financialSummaryQuery.data.claimsSummary ?? null;
  const softDentCoverage = financialSummaryQuery.data.softDentCoverage ?? null;
  const coverageGaps = (softDentCoverage?.rows ?? []).filter((row) => row.status !== "available").slice(0, 3);

  return (
    <div className="dashboard-page claims-workbench-page">
      <header className="page-header">
        <p className="eyebrow">Claims Workbench</p>
        <h1>Patient Claims Workbench</h1>
        <p>
          Search patient claim context, review source readiness, and generate one-click insurance narratives from approved local SoftDent
          exports.
        </p>
      </header>

      <section className="claims-workbench-grid">
        <article className="admin-card">
          <h2>Transaction Feed Status</h2>
          <TransactionFeedStatusNotice healthFlags={healthFlags} />
        </article>

        <article className="admin-card">
          <h2>Source Readiness</h2>
          <div className="admin-audit-list">
            {[
              { label: "Transaction feed", item: transactionFeedSource },
              { label: "Claims export", item: claimsSource },
              { label: "Clinical notes export", item: notesSource },
            ].map(({ label, item }) => (
              <div key={label} className="admin-audit-item">
                <div className="admin-audit-item__header">
                  <strong>{label}</strong>
                  <span>
                    {item?.health?.toUpperCase() || "MISSING"} · {item?.source_backend || "missing"} ·{" "}
                    <span className={confidenceBadgeClass(item?.confidence_label || "manual review", item?.review_required ?? true)}>
                      {item?.confidence_label || "manual review"}
                    </span>
                  </span>
                </div>
                <div className="admin-audit-item__summary">{item?.excerpt || "No approved export file is available yet."}</div>
                <div className="admin-audit-item__summary">Source file: {item?.source_file || "missing"}</div>
                <div className="admin-audit-item__summary">
                  {(item?.review_flags?.length ?? 0) > 0 ? (
                    item?.review_flags?.map((flag) => (
                      <span
                        key={`${label}-${flag}`}
                        className="dashboard-import-status-badge dashboard-import-status-badge--pending dashboard-import-status-badge--spaced"
                      >
                        {flag}
                      </span>
                    ))
                  ) : (
                    <span className="dashboard-import-status-badge">no review flags</span>
                  )}
                </div>
              </div>
            ))}
          </div>
          {!claimsSource?.available || !notesSource?.available ? (
            <p className="claims-workbench-warning">
              Live patient work is ready in HAL, but real SoftDent claim and note export files are not present on this machine yet.
            </p>
          ) : null}
        </article>

        <article className="admin-card">
          <h2>Claims Aggregate Snapshot</h2>
          <p className="admin-card__summary">
            {claimsSummary?.available
              ? "Approved SoftDent aggregate claim exports are now feeding true outstanding and unsubmitted claim exposure into this page."
              : "Approved SoftDent aggregate claim exports are still required before this page can quantify true outstanding and unsubmitted claim exposure."}
          </p>
          <dl className="admin-kv">
            <div>
              <dt>True outstanding</dt>
              <dd>{formatCurrency(claimsSummary?.true_outstanding_claims_amount ?? 0)}</dd>
            </div>
            <div>
              <dt>Outstanding claims</dt>
              <dd>{claimsSummary?.true_outstanding_claims_count ?? 0}</dd>
            </div>
            <div>
              <dt>Unsubmitted</dt>
              <dd>{formatCurrency(claimsSummary?.unsubmitted_claims_amount ?? 0)}</dd>
            </div>
            <div>
              <dt>Unsubmitted claims</dt>
              <dd>{claimsSummary?.unsubmitted_claims_count ?? 0}</dd>
            </div>
          </dl>
          <div className="admin-audit-item__summary">
            Top outstanding payers:{" "}
            {claimsSummary?.top_outstanding_payers?.length
              ? claimsSummary.top_outstanding_payers.map((item) => `${item.label} ${formatCurrency(item.amount)}`).join(" · ")
              : "not available yet"}
          </div>
          <div className="admin-audit-item__summary">
            Top unsubmitted payers:{" "}
            {claimsSummary?.top_unsubmitted_payers?.length
              ? claimsSummary.top_unsubmitted_payers.map((item) => `${item.label} ${formatCurrency(item.amount)}`).join(" · ")
              : "not available yet"}
          </div>
          {coverageGaps.length ? (
            <p className="claims-workbench-warning">
              Coverage gaps still limit parts of this page: {coverageGaps.map((row) => row.label).join(", ")}.
            </p>
          ) : null}
        </article>

        <article className="admin-card">
          <h2>Patient Lookup</h2>
          <form
            className="hal-form hal-form--narrative"
            onSubmit={(event) => {
              event.preventDefault();
              dossierMutation.mutate(lookupQuestion.trim());
            }}
          >
            <label htmlFor="claims-lookup-question">Lookup question</label>
            <textarea
              id="claims-lookup-question"
              className="hal-form__textarea"
              rows={4}
              value={lookupQuestion}
              onChange={(event) => setLookupQuestion(event.target.value)}
              placeholder="e.g. Patient John Doe MRN 778899 claim lookup."
            />
            <button type="submit" className="refresh-button" disabled={!lookupQuestion.trim() || dossierMutation.isPending}>
              {dossierMutation.isPending ? "Searching..." : "Lookup patient dossier"}
            </button>
          </form>
          {dossierMutation.data ? (
            <div className="hal-answer-card">
              <h3>Lookup Result</h3>
              <div className="hal-answer-card__section">{dossierMutation.data.summary}</div>
              <div className="hal-answer-card__section">
                <strong>Sanitized audit question:</strong> {dossierMutation.data.sanitized_question}
              </div>
              {(dossierMutation.data.supporting_context ?? []).length ? (
                (dossierMutation.data.supporting_context ?? []).map((item) => (
                  <div key={item.source_id} className="hal-supporting-context-item">
                    <strong>{item.title}</strong>
                    <div>{item.excerpt}</div>
                  </div>
                ))
              ) : (
                <div className="hal-answer-card__section">No supporting context snippets were returned for this lookup.</div>
              )}
            </div>
          ) : null}
        </article>

        <article className="admin-card admin-card--wide">
          <h2>Insurance Narrative</h2>
          <form
            className="hal-form hal-form--narrative"
            onSubmit={(event) => {
              event.preventDefault();
              narrativeMutation.mutate(narrativeQuestion.trim());
            }}
          >
            <label htmlFor="claims-narrative-question">Narrative request</label>
            <textarea
              id="claims-narrative-question"
              className="hal-form__textarea"
              rows={4}
              value={narrativeQuestion}
              onChange={(event) => setNarrativeQuestion(event.target.value)}
              placeholder="e.g. Patient John Doe MRN 778899 needs an insurance narrative for the denied crown buildup claim."
            />
            <button type="submit" className="refresh-button" disabled={!narrativeQuestion.trim() || narrativeMutation.isPending}>
              {narrativeMutation.isPending ? "Generating..." : "Generate narrative"}
            </button>
          </form>
          {narrativeMutation.data ? (
            <div className="hal-answer-card">
              <h3>Narrative Output</h3>
              <div className="hal-answer-card__section hal-answer-card__section--lead">{narrativeMutation.data.narrative}</div>
              <div className="hal-answer-card__section">
                <strong>Audit ID:</strong> {narrativeMutation.data.audit_id}
              </div>
              <div className="hal-answer-card__section">
                <strong>Sanitized audit question:</strong> {narrativeMutation.data.sanitized_question}
              </div>
              <div className="hal-answer-card__section">
                <strong>Guardrails:</strong>{" "}
                {(narrativeMutation.data.guardrails ?? []).length ? narrativeMutation.data.guardrails.join(", ") : "None"}
              </div>
            </div>
          ) : null}
        </article>
      </section>
    </div>
  );
}
