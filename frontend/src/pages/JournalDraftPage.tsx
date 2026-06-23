import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { draftJournalEntry, queueAccountingPostingDraft } from "../api/client";
import { DRAFT_STATUS_ENQUEUED } from "../utils/journalDraftStatus";

const ACCOUNTING_MONTH_OPTIONS = [
  { value: "01", label: "01 - January" },
  { value: "02", label: "02 - February" },
  { value: "03", label: "03 - March" },
  { value: "04", label: "04 - April" },
  { value: "05", label: "05 - May" },
  { value: "06", label: "06 - June" },
  { value: "07", label: "07 - July" },
  { value: "08", label: "08 - August" },
  { value: "09", label: "09 - September" },
  { value: "10", label: "10 - October" },
  { value: "11", label: "11 - November" },
  { value: "12", label: "12 - December" },
] as const;

const ACCOUNTING_YEAR_OPTIONS = ["2024", "2025", "2026", "2027", "2028"] as const;

export default function JournalDraftPage() {
  const [description, setDescription] = useState("");
  const [sourceText, setSourceText] = useState("");
  const [transactionDate, setTransactionDate] = useState("2026-06-15");
  const [accountingPeriod, setAccountingPeriod] = useState("2026-06");
  const [amount, setAmount] = useState("1200");
  const [transactionType, setTransactionType] = useState("auto");
  const [useLocalAiWorkflow, setUseLocalAiWorkflow] = useState(false);
  const [autoEnqueueValidatedDraft, setAutoEnqueueValidatedDraft] = useState(false);
  const [accountingYear, accountingMonth] = accountingPeriod.split("-");
  const parsedAmount = Number(amount);
  const amountIsValid = Number.isFinite(parsedAmount) && parsedAmount > 0;
  const amountValidationMessage = amount.trim() && !amountIsValid ? "Enter a positive amount before drafting or queueing a journal entry." : null;

  const draftMutation = useMutation({
    mutationFn: draftJournalEntry,
  });

  const queueMutation = useMutation({
    mutationFn: queueAccountingPostingDraft,
  });

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    queueMutation.reset();
    if (!amountIsValid) {
      return;
    }
    const context: Record<string, unknown> = transactionType === "auto" ? {} : { transaction_type: transactionType };
    if (useLocalAiWorkflow) {
      context.use_local_ai_workflow = true;
      context.source_text = sourceText.trim() || description.trim();
    }
    if (autoEnqueueValidatedDraft) {
      context.auto_enqueue_validated_draft = true;
    }

    draftMutation.mutate({
      description: description.trim(),
      transaction_date: transactionDate,
      accounting_period: accountingPeriod,
      amount: parsedAmount,
      context,
    });
  }

  const response = draftMutation.data;
  const queuedResponse = queueMutation.data;
  const queueEligible = Boolean(
    response?.validation.balanced && response.validation.open_period && response.validation.account_validation_passed,
  );
  const responseAlreadyEnqueued = response?.draft_status === DRAFT_STATUS_ENQUEUED;

  function handleQueueForReview() {
    if (!response || !queueEligible || !amountIsValid) {
      return;
    }
    queueMutation.mutate({
      description: description.trim(),
      transaction_date: transactionDate,
      accounting_period: accountingPeriod,
      amount: parsedAmount,
      transaction_type: transactionType === "auto" ? undefined : transactionType,
      source_audit_id: response.audit_id,
      lines: response.lines,
    });
  }

  return (
    <div className="dashboard-page">
      <div className="page-content">
        <header className="page-header">
          <p className="eyebrow">Accounting Copilot</p>
          <h1>Journal Draft Review</h1>
          <p>Create a structured draft journal entry from approved accounting input. All output is draft-only and requires human review.</p>
        </header>
        <form className="hal-form hal-form--narrative" onSubmit={handleSubmit}>
          <label htmlFor="journal-description">Transaction Description</label>
          <textarea
            id="journal-description"
            className="hal-form__textarea"
            rows={4}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="e.g. Record prepaid insurance for June coverage."
            required
          />
          <label htmlFor="journal-source-text">Raw Source Text</label>
          <textarea
            id="journal-source-text"
            className="hal-form__textarea"
            rows={6}
            value={sourceText}
            onChange={(event) => setSourceText(event.target.value)}
            placeholder="Paste invoice text, vendor bill details, or raw source notes for the local AI parser."
          />
          <div className="hal-answer-card__section">
            This field is optional for heuristic drafting. When local AI parsing is enabled, it becomes the preferred extraction source.
          </div>
          <div className="journal-draft-grid">
            <label>
              Transaction Date
              <input type="date" value={transactionDate} onChange={(event) => setTransactionDate(event.target.value)} required />
            </label>
            <label>
              Accounting Period
              <div className="journal-draft-grid">
                <select
                  aria-label="Accounting Period Year"
                  value={accountingYear}
                  onChange={(event) => setAccountingPeriod(`${event.target.value}-${accountingMonth}`)}
                  required
                >
                  {ACCOUNTING_YEAR_OPTIONS.map((year) => (
                    <option key={year} value={year}>
                      {year}
                    </option>
                  ))}
                </select>
                <select
                  aria-label="Accounting Period Month"
                  value={accountingMonth}
                  onChange={(event) => setAccountingPeriod(`${accountingYear}-${event.target.value}`)}
                  required
                >
                  {ACCOUNTING_MONTH_OPTIONS.map((monthOption) => (
                    <option key={monthOption.value} value={monthOption.value}>
                      {monthOption.label}
                    </option>
                  ))}
                </select>
              </div>
            </label>
            <label>
              Amount
              <input type="number" min="0.01" step="0.01" value={amount} onChange={(event) => setAmount(event.target.value)} required />
            </label>
            <label>
              Transaction Type
              <select value={transactionType} onChange={(event) => setTransactionType(event.target.value)}>
                <option value="auto">Auto-detect from description</option>
                <option value="prepaid_insurance">Prepaid Insurance</option>
                <option value="patient_service_revenue">Patient Service Revenue</option>
                <option value="patient_cash_receipt">Patient Cash Receipt</option>
                <option value="vendor_bill">Vendor Bill</option>
                <option value="supplies_accrual">Supplies Accrual</option>
                <option value="payroll_accrual">Payroll Accrual</option>
                <option value="equipment_purchase">Equipment Purchase</option>
                <option value="depreciation">Depreciation</option>
              </select>
            </label>
          </div>
          <div className="hal-answer-card__section">
            <label>
              <input
                type="checkbox"
                checked={useLocalAiWorkflow}
                onChange={(event) => {
                  const checked = event.target.checked;
                  setUseLocalAiWorkflow(checked);
                  if (!checked) {
                    setAutoEnqueueValidatedDraft(false);
                  }
                }}
              />
              Parse with local AI
            </label>
            <div>Use the local Qwen and Mistral workflow to parse the raw source text before deterministic accounting validation.</div>
          </div>
          <div className="hal-answer-card__section">
            <label>
              <input
                type="checkbox"
                checked={autoEnqueueValidatedDraft}
                disabled={!useLocalAiWorkflow}
                onChange={(event) => setAutoEnqueueValidatedDraft(event.target.checked)}
              />
              Auto-enqueue validated draft for human review
            </label>
            <div>Only available when local AI parsing is enabled. Validated drafts go directly into the posting queue for review.</div>
          </div>
          <button type="submit" className="refresh-button" disabled={!description.trim() || !amountIsValid || draftMutation.isPending}>
            {draftMutation.isPending ? "Drafting journal entry..." : "Draft journal entry"}
          </button>
        </form>

        {amountValidationMessage ? <div className="hal-answer-card__section">{amountValidationMessage}</div> : null}

        {draftMutation.isError ? (
          <div className="hal-answer-card">
            <h2>Draft failed</h2>
            <div>{draftMutation.error instanceof Error ? draftMutation.error.message : "Unable to draft journal entry."}</div>
          </div>
        ) : null}

        {queueMutation.isError ? (
          <div className="hal-answer-card">
            <h2>Queue request failed</h2>
            <div>{queueMutation.error instanceof Error ? queueMutation.error.message : "Unable to queue the draft for review."}</div>
          </div>
        ) : null}

        {response ? (
          <div className="hal-answer-card">
            <h2>Drafted Journal Entry</h2>
            <div className="hal-answer-card__section hal-answer-card__section--lead">{response.summary}</div>
            <div className="journal-draft-banner">Review required before posting to any accounting system.</div>
            <div className="hal-answer-card__section">
              <strong>Audit ID:</strong> {response.audit_id}
            </div>
            <div className="hal-answer-card__section">
              <strong>Draft status:</strong> {response.draft_status.replace("_", " ")}
            </div>
            {response.review_required ? (
              <div className="hal-answer-card__section">Draft review artifacts were saved locally for human review.</div>
            ) : null}
            <div className="hal-answer-card__section">
              <strong>Balanced:</strong> {response.validation.balanced ? "Yes" : "No"}
            </div>
            <div className="hal-answer-card__section">
              <strong>Open period:</strong> {response.validation.open_period ? "Yes" : "No"}
            </div>
            <div className="hal-answer-card__section">
              <strong>Debit total:</strong> {response.validation.debit_total.toFixed(2)}
            </div>
            <div className="hal-answer-card__section">
              <strong>Credit total:</strong> {response.validation.credit_total.toFixed(2)}
            </div>
            {response.queue_status ? (
              <div className="hal-answer-card__section">
                <strong>Queue status:</strong> {response.queue_status.replace("_", " ")}
              </div>
            ) : null}
            {response.queue_id ? (
              <div className="hal-answer-card__section">
                <strong>Queue ID:</strong> {response.queue_id}
              </div>
            ) : null}
            {response.enqueue_error ? (
              <div className="hal-answer-card__section">
                <strong>Auto-enqueue status:</strong> {response.enqueue_error}
              </div>
            ) : null}
            <div className="hal-answer-card__section">Activity logging and review-plan storage remain inside the local AI workspace.</div>
            <table className="dashboard-import-table">
              <thead>
                <tr>
                  <th>Account Code</th>
                  <th>Account Name</th>
                  <th>Debit</th>
                  <th>Credit</th>
                </tr>
              </thead>
              <tbody>
                {response.lines.map((line) => (
                  <tr key={`${line.account_code}-${line.account_name}`}>
                    <td>{line.account_code}</td>
                    <td>{line.account_name}</td>
                    <td>{line.debit.toFixed(2)}</td>
                    <td>{line.credit.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <h3>Validation Issues</h3>
            {response.validation.issues.length === 0 ? <div>No validation issues.</div> : null}
            <ul>
              {response.validation.issues.map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>

            <div className="posting-queue-action-row">
              <button
                type="button"
                className="refresh-button"
                disabled={!queueEligible || !amountIsValid || queueMutation.isPending || responseAlreadyEnqueued}
                onClick={handleQueueForReview}
              >
                {queueMutation.isPending ? "Queueing for review..." : "Queue for QuickBooks review"}
              </button>
            </div>
            {!queueEligible ? (
              <div className="hal-answer-card__section">
                Only balanced, valid, open-period drafts can be queued for QuickBooks Desktop review.
              </div>
            ) : null}
            {responseAlreadyEnqueued ? (
              <div className="hal-answer-card__section">This validated draft has already been auto-enqueued for human review.</div>
            ) : null}
            {queuedResponse ? (
              <div className="posting-queue-review-meta">
                <div>
                  <strong>Queue status:</strong> {queuedResponse.status.replace("_", " ")}
                </div>
                <div>
                  <strong>Queue ID:</strong> {queuedResponse.queue_id}
                </div>
                {queuedResponse ? (
                  <div>Queue review artifacts were saved locally for the approver.</div>
                ) : null}
                {queuedResponse.audit_id ? (
                  <div>
                    <strong>Queue audit ID:</strong> {queuedResponse.audit_id}
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}
