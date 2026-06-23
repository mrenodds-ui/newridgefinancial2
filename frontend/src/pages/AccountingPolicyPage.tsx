import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { fetchAccountingPolicyAnswer } from "../api/client";

export default function AccountingPolicyPage() {
  const [question, setQuestion] = useState("");
  const [topic, setTopic] = useState("prepaids");
  const [accountingStandard, setAccountingStandard] = useState("GAAP");

  const policyMutation = useMutation({
    mutationFn: fetchAccountingPolicyAnswer,
  });

  const trimmedQuestion = question.trim();
  const trimmedTopic = topic.trim();
  const trimmedAccountingStandard = accountingStandard.trim();

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!trimmedQuestion || policyMutation.isPending) {
      return;
    }

    policyMutation.mutate({
      question: trimmedQuestion,
      topic: trimmedTopic || "prepaids",
      accounting_standard: trimmedAccountingStandard || "GAAP",
    });
  }

  const response = policyMutation.data;
  const lastSubmittedRequest = policyMutation.variables;
  const responseMatchesCurrentInputs =
    Boolean(response) &&
    Boolean(lastSubmittedRequest) &&
    trimmedQuestion === lastSubmittedRequest?.question &&
    (trimmedTopic || "prepaids") === lastSubmittedRequest?.topic &&
    (trimmedAccountingStandard || "GAAP") === lastSubmittedRequest?.accounting_standard;
  const renderedResponse = responseMatchesCurrentInputs ? response : null;

  return (
    <div className="dashboard-page">
      <div className="page-content">
        <header className="page-header">
          <p className="eyebrow">Accounting Copilot</p>
          <h1>Accounting Policy Guidance</h1>
          <p>Ask for draft accounting guidance grounded in approved local policy and financial documentation.</p>
        </header>
        <form className="hal-form hal-form--narrative" onSubmit={handleSubmit}>
          <label htmlFor="policy-question">Policy Question</label>
          <textarea
            id="policy-question"
            className="hal-form__textarea"
            rows={4}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="e.g. How should prepaid insurance be treated at period end?"
            required
          />
          <div className="journal-draft-grid">
            <label>
              Topic
              <input type="text" value={topic} onChange={(event) => setTopic(event.target.value)} />
            </label>
            <label>
              Accounting Standard
              <input type="text" value={accountingStandard} onChange={(event) => setAccountingStandard(event.target.value)} />
            </label>
          </div>
          <button type="submit" className="refresh-button" disabled={!trimmedQuestion || policyMutation.isPending}>
            {policyMutation.isPending ? "Fetching guidance..." : "Get policy guidance"}
          </button>
        </form>

        {policyMutation.isError ? (
          <div className="hal-answer-card">
            <h2>Request failed</h2>
            <div>{policyMutation.error instanceof Error ? policyMutation.error.message : "Unable to fetch policy guidance."}</div>
          </div>
        ) : null}

        {renderedResponse ? (
          <div className="hal-answer-card">
            <h2>Draft Policy Guidance</h2>
            <div className="hal-answer-card__section hal-answer-card__section--lead">{renderedResponse.answer}</div>
            <div className="journal-draft-banner">Policy guidance is draft-only and requires accounting review before operational use.</div>
            <div className="hal-answer-card__section">
              <strong>Accounting standard:</strong> {renderedResponse.accounting_standard || "Internal reviewed guidance"}
            </div>
            <div className="hal-answer-card__section">
              <strong>Confidence:</strong> {renderedResponse.confidence}
            </div>
            <div className="hal-answer-card__section">
              <strong>Audit ID:</strong> {renderedResponse.audit_id}
            </div>
            <h3>Citations</h3>
            {renderedResponse.citations.length === 0 ? <div>No citations returned.</div> : null}
            {renderedResponse.citations.map((citation) => (
              <div key={citation.source_id} className="hal-supporting-context-item">
                <strong>{citation.title}</strong>
                <div>{citation.excerpt}</div>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}
