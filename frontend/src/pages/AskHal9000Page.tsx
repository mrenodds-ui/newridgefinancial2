import { useMutation, useQuery } from "@tanstack/react-query";
import { type FormEvent, useEffect, useRef, useState } from "react";

import {
  approveHalChartPlan,
  askHalQuestion,
  buildHalChartFileUrl,
  createHalConversationId,
  executeMonitorReviewAction,
  fetchFinancialSummary,
  fetchHalChartPlans,
  fetchLocalAccountingDocuments,
  generateHalChartPlan,
} from "../api/client";
import { HalChartPreview } from "../components/HalChartPreview";
import { queryClient } from "../queryClient";

const HAL_SPEECH_VOICE_KEY = "halSpeechVoice";
const HAL_SPEECH_RATE_KEY = "halSpeechRate";

function humanizeCorrectionFlag(flag: string) {
  return flag.replaceAll("_", " ");
}

function confidenceBadgeClass(label: string, reviewRequired: boolean) {
  if (label === "manual review") {
    return "dashboard-import-status-badge dashboard-import-status-badge--error";
  }
  if (reviewRequired || label === "review suggested") {
    return "dashboard-import-status-badge dashboard-import-status-badge--pending";
  }
  return "dashboard-import-status-badge";
}

function buildCorrectionFlags(item: { correction_flags?: string[] }) {
  return (item.correction_flags || []).map(humanizeCorrectionFlag);
}

function humanizeGuardrail(flag: string) {
  switch (flag) {
    case "approved local read-only scope":
      return "Uses only approved local read-only data";
    case "deterministic server facts first":
      return "Starts with verified system facts";
    case "sanitized retrieval only":
      return "Uses sanitized retrieval only";
    case "read-only data boundary":
      return "Stays inside a read-only data boundary";
    case "approved summary queries only":
      return "Uses approved summary queries only";
    case "truthful runtime claims only":
      return "Describes runtime status only when the backend verified it";
    case "audit log recorded":
      return "Records an audit trail";
    case "hardware mutations require human confirmation":
      return "Any hardware change still needs your approval";
    case "tier-1 critical actions require explicit confirmation":
      return "Critical actions stay proposal-only until you confirm them";
    case "tier-2 mismatches raise [ALERT]":
      return "Raises an alert when reviewed facts do not line up";
    case "tier-3 assistance stays concise":
      return "Keeps routine help brief";
    case "raw identifiers processed only in local patient tool":
      return "Raw patient identifiers stay inside the local patient tool";
    default:
      return flag;
  }
}

function getSpeechSynthesis(): SpeechSynthesis | null {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) {
    return null;
  }
  return window.speechSynthesis;
}

function isAutomatedBrowserSession(): boolean {
  return typeof navigator !== "undefined" && navigator.webdriver;
}

export default function AskHal9000Page() {
  const [question, setQuestion] = useState("");
  const [lastRequestLane, setLastRequestLane] = useState<"primary" | "second_opinion">("primary");
  const [chartQuestion, setChartQuestion] = useState("");
  const [chartPlanStatusFilter, setChartPlanStatusFilter] = useState<"all" | "pending_human_approval" | "approved_and_rendered">("all");
  const [documentSearch, setDocumentSearch] = useState("");
  const [documentType, setDocumentType] = useState("");
  const [reviewOnly, setReviewOnly] = useState(false);
  const [speechError, setSpeechError] = useState<string | null>(null);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [speechRate, setSpeechRate] = useState(() => {
    if (typeof window === "undefined") {
      return 1;
    }
    const savedRate = Number(window.localStorage.getItem(HAL_SPEECH_RATE_KEY));
    return Number.isFinite(savedRate) && savedRate >= 0.7 && savedRate <= 1.4 ? savedRate : 1;
  });
  const [availableVoices, setAvailableVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [selectedVoiceName, setSelectedVoiceName] = useState(() => {
    if (typeof window === "undefined") {
      return "";
    }
    return window.localStorage.getItem(HAL_SPEECH_VOICE_KEY) || "";
  });
  const askInFlightRef = useRef(false);
  const conversationIdRef = useRef(createHalConversationId());
  const financialSummaryQuery = useQuery({
    queryKey: ["financial-summary"],
    queryFn: fetchFinancialSummary,
  });
  const halMutation = useMutation({
    mutationFn: ({ nextQuestion, lane }: { nextQuestion: string; lane: "primary" | "second_opinion" }) =>
      askHalQuestion(nextQuestion, {
        summary: financialSummaryQuery.data ?? null,
        lane,
        conversationId: conversationIdRef.current,
      }),
    onSettled: () => {
      askInFlightRef.current = false;
    },
  });
  const actionMutation = useMutation({
    mutationFn: executeMonitorReviewAction,
  });
  const chartPlanMutation = useMutation({
    mutationFn: generateHalChartPlan,
  });
  const chartApprovalMutation = useMutation({
    mutationFn: approveHalChartPlan,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["hal-chart-plans"] });
    },
  });
  const chartPlansQuery = useQuery({
    queryKey: ["hal-chart-plans", chartPlanStatusFilter],
    queryFn: () => fetchHalChartPlans(8, chartPlanStatusFilter === "all" ? undefined : chartPlanStatusFilter),
  });
  const accountingDocumentsQuery = useQuery({
    queryKey: ["hal-accounting-documents", documentSearch, documentType, reviewOnly],
    queryFn: () =>
      fetchLocalAccountingDocuments({
        limit: 8,
        search: documentSearch.trim() || undefined,
        documentType: documentType || undefined,
        reviewOnly,
      }),
  });

  function submitHalQuestion(lane: "primary" | "second_opinion") {
    if (!question.trim() || halMutation.isPending || askInFlightRef.current) {
      return;
    }
    askInFlightRef.current = true;
    setLastRequestLane(lane);
    actionMutation.reset();
    setSpeechError(null);
    setIsSpeaking(false);
    halMutation.mutate({ nextQuestion: question.trim(), lane });
  }

  function handleAsk(e: FormEvent) {
    e.preventDefault();
    submitHalQuestion("primary");
  }

  function handleSecondOpinionAsk() {
    submitHalQuestion("second_opinion");
  }

  function handleRetryAsk() {
    submitHalQuestion(lastRequestLane);
  }

  function handleGenerateChartPlan(e: FormEvent) {
    e.preventDefault();
    chartPlanMutation.mutate(chartQuestion.trim());
  }

  function handleApproveChartPlan() {
    const reviewPlanPath = chartPlanMutation.data?.review_plan_path;
    if (!reviewPlanPath) {
      return;
    }
    chartApprovalMutation.mutate(reviewPlanPath);
  }

  const response = halMutation.data;
  const reviewAction = response?.review_actions.find((item) => item.action_type === "SET_LUMINANCE");

  useEffect(() => {
    if (isAutomatedBrowserSession()) {
      return;
    }

    const synthesis = getSpeechSynthesis();
    if (!synthesis) {
      return;
    }

    const syncVoices = () => {
      const voices = synthesis.getVoices();
      setAvailableVoices(voices);
      setSelectedVoiceName((currentName) => {
        if (currentName && voices.some((voice) => voice.name === currentName)) {
          return currentName;
        }
        if (typeof window !== "undefined") {
          const savedVoice = window.localStorage.getItem(HAL_SPEECH_VOICE_KEY);
          if (savedVoice && voices.some((voice) => voice.name === savedVoice)) {
            return savedVoice;
          }
        }
        const chromeVoice = voices.find((voice) => /google|chrome/i.test(`${voice.name} ${voice.voiceURI}`));
        return chromeVoice?.name || voices[0]?.name || "";
      });
    };

    syncVoices();
    synthesis.onvoiceschanged = syncVoices;

    return () => {
      synthesis.onvoiceschanged = null;
      synthesis.cancel();
    };
  }, []);

  useEffect(() => {
    if (isAutomatedBrowserSession()) {
      return;
    }

    return () => {
      const synthesis = getSpeechSynthesis();
      if (synthesis) {
        synthesis.cancel();
      }
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    if (!selectedVoiceName) {
      window.localStorage.removeItem(HAL_SPEECH_VOICE_KEY);
      return;
    }
    window.localStorage.setItem(HAL_SPEECH_VOICE_KEY, selectedVoiceName);
  }, [selectedVoiceName]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    window.localStorage.setItem(HAL_SPEECH_RATE_KEY, speechRate.toString());
  }, [speechRate]);

  useEffect(() => {
    if (isAutomatedBrowserSession() || !response?.answer) {
      return;
    }
    handleSpeakResponse();
  }, [response?.answer]);

  function handleSpeakResponse() {
    if (!response?.answer) {
      return;
    }
    const synthesis = getSpeechSynthesis();
    if (!synthesis || typeof SpeechSynthesisUtterance === "undefined") {
      setSpeechError("Chrome speech is unavailable in this browser session.");
      return;
    }

    synthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(response.answer);
    utterance.rate = speechRate;
    const selectedVoice = availableVoices.find((voice) => voice.name === selectedVoiceName);
    if (selectedVoice) {
      utterance.voice = selectedVoice;
    }
    utterance.onstart = () => {
      setSpeechError(null);
      setIsSpeaking(true);
    };
    utterance.onend = () => {
      setIsSpeaking(false);
    };
    utterance.onerror = () => {
      setIsSpeaking(false);
      setSpeechError("Chrome could not speak the HAL response.");
    };
    synthesis.speak(utterance);
  }

  function handleStopSpeaking() {
    const synthesis = getSpeechSynthesis();
    if (!synthesis) {
      return;
    }
    synthesis.cancel();
    setIsSpeaking(false);
  }

  function handleApproveDisplayAdjustment() {
    if (!reviewAction) {
      return;
    }

    actionMutation.mutate({
      action_type: reviewAction.action_type,
      target_value: reviewAction.target_value,
      human_review_required: reviewAction.human_review_required,
      status: reviewAction.status,
      user_confirmed: true,
    });
  }

  return (
    <div className="dashboard-page dashboard-page--hal">
      <div className="page-content">
        <header className="page-header">
          <p className="eyebrow">AI Assistant</p>
          <h1>Ask Hal 9000</h1>
          <p>
            Ask HAL a question in plain language. He answers from the verified data on this system, and anything that would change hardware
            still waits for your approval first.
          </p>
        </header>
        <form className="hal-form hal-form--narrative" onSubmit={handleAsk}>
          <label htmlFor="hal-question">Your Question</label>
          <textarea
            className="hal-form__textarea"
            id="hal-question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={4}
            placeholder="e.g. Change brightness to 30% on the primary monitor."
            required
          />
          <br />
          <div className="hal-form__actions">
            <button type="submit" className="refresh-button" disabled={!question.trim() || halMutation.isPending}>
              {halMutation.isPending && lastRequestLane === "primary" ? "Asking HAL..." : "Ask HAL"}
            </button>
            <button
              type="button"
              className="refresh-button"
              onClick={handleSecondOpinionAsk}
              disabled={!question.trim() || halMutation.isPending}
            >
              {halMutation.isPending && lastRequestLane === "second_opinion" ? "Asking second opinion..." : "Ask HAL Second Opinion"}
            </button>
          </div>
        </form>

        {halMutation.isError && (
          <div className="hal-answer-card">
            <h2>Request failed</h2>
            <div>{halMutation.error instanceof Error ? halMutation.error.message : "HAL could not finish that request."}</div>
            <button type="button" className="refresh-button" onClick={handleRetryAsk} disabled={!question.trim() || halMutation.isPending}>
              {halMutation.isPending ? "Retrying..." : "Try Again"}
            </button>
          </div>
        )}

        {response && (
          <div className="hal-answer-card">
            <h2>HAL's Answer</h2>
            <div className="hal-answer-card__section">
              <strong>Response lane:</strong> {lastRequestLane === "second_opinion" ? "Deeper second opinion (Qwen3 30B)" : "Primary HAL"}
            </div>
            <div className="hal-answer-card__section hal-answer-card__section--lead">{response.answer}</div>
            <div className="hal-answer-card__section">
              <label htmlFor="hal-response-voice">Voice</label>
              <select
                id="hal-response-voice"
                className="hal-form__textarea"
                value={selectedVoiceName}
                onChange={(event) => setSelectedVoiceName(event.target.value)}
              >
                {availableVoices.length === 0 ? <option value="">Browser default</option> : null}
                {availableVoices.map((voice) => (
                  <option key={`${voice.name}-${voice.lang}`} value={voice.name}>
                    {voice.name} ({voice.lang})
                  </option>
                ))}
              </select>
              <label htmlFor="hal-response-rate">Speech rate</label>
              <input
                id="hal-response-rate"
                type="range"
                min="0.7"
                max="1.4"
                step="0.1"
                value={speechRate}
                onChange={(event) => setSpeechRate(Number(event.target.value))}
              />
              <div>{speechRate.toFixed(1)}x</div>
              <button type="button" className="refresh-button" onClick={handleSpeakResponse}>
                Read It Aloud
              </button>
              {isSpeaking ? (
                <button type="button" className="refresh-button" onClick={handleStopSpeaking}>
                  Stop Reading
                </button>
              ) : null}
            </div>
            {speechError ? <div className="hal-answer-card__section">{speechError}</div> : null}
            <div className="hal-answer-card__section">
              <strong>Audit-trail question:</strong> {response.sanitized_question}
            </div>
            <div className="hal-answer-card__section">
              <strong>Audit ID:</strong> {response.audit_id}
            </div>
            <div className="hal-answer-card__section">
              <strong>Safety checks:</strong> {response.guardrails.map(humanizeGuardrail).join(", ")}
            </div>
            {reviewAction ? (
              <section className="hal-review-actions">
                <h3>Before Anything Changes</h3>
                <div className="hal-review-actions__card">
                  <div className="hal-answer-card__section hal-answer-card__section--lead">{reviewAction.title}</div>
                  <div className="hal-answer-card__section">{reviewAction.confirmation_message}</div>
                  <div className="hal-answer-card__section">
                    <strong>Status:</strong> {reviewAction.status.replaceAll("_", " ")}
                  </div>
                  <button
                    type="button"
                    className="refresh-button"
                    onClick={handleApproveDisplayAdjustment}
                    disabled={actionMutation.isPending}
                  >
                    {actionMutation.isPending ? "Approving..." : `Approve display adjustment to ${reviewAction.target_value}%`}
                  </button>
                  {actionMutation.data ? (
                    <div className="hal-review-actions__result">
                      <strong>Executor status:</strong> {actionMutation.data.status}
                      {actionMutation.data.applied_value !== null ? ` (${actionMutation.data.applied_value}%)` : ""}
                      {actionMutation.data.error ? ` - ${actionMutation.data.error}` : ""}
                    </div>
                  ) : null}
                  {actionMutation.isError ? (
                    <div className="hal-review-actions__result hal-review-actions__result--error">
                      {actionMutation.error instanceof Error ? actionMutation.error.message : "Unable to execute the reviewed action."}
                    </div>
                  ) : null}
                </div>
              </section>
            ) : null}
            <h3>What HAL Used</h3>
            {response.retrieved_context.length === 0 ? <div>No supporting records were needed for this answer.</div> : null}
            {response.retrieved_context.map((item) => (
              <div key={item.source_id} className="hal-supporting-context-item">
                <strong>{item.title}</strong>
                <div>{item.excerpt}</div>
              </div>
            ))}
          </div>
        )}

        <section className="hal-answer-card">
          <h2>Chart Drafting</h2>
          <div className="hal-answer-card__section hal-answer-card__section--lead">
            Draft a chart request, save the review files in AI_Workspace, and hold the render until you approve it.
          </div>
          <form className="hal-form hal-form--narrative" onSubmit={handleGenerateChartPlan}>
            <label htmlFor="hal-chart-question">Chart request</label>
            <textarea
              className="hal-form__textarea"
              id="hal-chart-question"
              value={chartQuestion}
              onChange={(event) => setChartQuestion(event.target.value)}
              rows={4}
              placeholder="e.g. Create a bar chart showing June overhead variance by category."
              required
            />
            <br />
            <button type="submit" className="refresh-button" disabled={!chartQuestion.trim() || chartPlanMutation.isPending}>
              {chartPlanMutation.isPending ? "Generating chart plan..." : "Generate chart plan"}
            </button>
          </form>
          {chartPlanMutation.isError ? (
            <div className="hal-answer-card__section">
              {chartPlanMutation.error instanceof Error ? chartPlanMutation.error.message : "Unable to generate the HAL chart plan."}
            </div>
          ) : null}
          {chartApprovalMutation.isError ? (
            <div className="hal-answer-card__section">
              {chartApprovalMutation.error instanceof Error ? chartApprovalMutation.error.message : "Unable to approve the HAL chart plan."}
            </div>
          ) : null}
          {chartPlanMutation.data ? (
            <div className="hal-answer-card__section">
              <div>
                <strong>Status:</strong> {chartPlanMutation.data.status.replaceAll("_", " ")}
              </div>
              <div>
                <strong>Audit ID:</strong> {chartPlanMutation.data.audit_id}
              </div>
              <div>Review and render artifacts were staged locally for approval.</div>
              <button type="button" className="refresh-button" onClick={handleApproveChartPlan} disabled={chartApprovalMutation.isPending}>
                {chartApprovalMutation.isPending ? "Approving chart plan..." : "Approve and render chart"}
              </button>
              {chartPlanMutation.data.flag_for_review ? (
                <div>
                  <strong>Review required:</strong> {chartPlanMutation.data.review_reason || "yes"}
                </div>
              ) : null}
              {chartPlanMutation.data.alert_reason ? (
                <div>
                  <strong>[ALERT]</strong> {chartPlanMutation.data.alert_reason}
                </div>
              ) : null}
              <pre className="hal-answer-card__section">{chartPlanMutation.data.preview_summary}</pre>
              <pre className="hal-answer-card__section">{JSON.stringify(chartPlanMutation.data.request_json, null, 2)}</pre>
              {chartApprovalMutation.data ? (
                <div className="hal-answer-card__section">
                  <div>
                    <strong>Render status:</strong> {chartApprovalMutation.data.status.replaceAll("_", " ")}
                  </div>
                  <div>Rendered chart is available below.</div>
                  <div>
                    <HalChartPreview
                      path={chartApprovalMutation.data.rendered_output_path}
                      alt="Rendered HAL chart preview"
                      className="hal-chart-preview"
                    />
                  </div>
                  <div>
                    <a href={buildHalChartFileUrl(chartApprovalMutation.data.rendered_output_path)} target="_blank" rel="noreferrer">
                      Open rendered chart
                    </a>
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}
        </section>

        <section className="hal-answer-card">
          <h2>Recent Chart Drafts</h2>
          <div className="hal-answer-card__section">
            <label htmlFor="hal-chart-plan-status-filter">Status filter</label>
            <select
              id="hal-chart-plan-status-filter"
              className="hal-form__textarea"
              value={chartPlanStatusFilter}
              onChange={(event) =>
                setChartPlanStatusFilter(event.target.value as "all" | "pending_human_approval" | "approved_and_rendered")
              }
            >
              <option value="all">All chart plans</option>
              <option value="pending_human_approval">Pending human approval</option>
              <option value="approved_and_rendered">Approved and rendered</option>
            </select>
          </div>
          {chartPlansQuery.isPending ? <div className="hal-answer-card__section">Loading chart plan history...</div> : null}
          {chartPlansQuery.isError ? (
            <div className="hal-answer-card__section">
              {chartPlansQuery.error instanceof Error ? chartPlansQuery.error.message : "Unable to load HAL chart plan history."}
            </div>
          ) : null}
          {chartPlansQuery.data ? (
            <>
              <div className="hal-answer-card__section">
                <strong>Plans:</strong> {chartPlansQuery.data.count}
              </div>
              {chartPlansQuery.data.items.map((item) => (
                <div key={item.review_plan_path} className="hal-supporting-context-item">
                  <strong>{item.title}</strong>
                  <div>
                    {item.chart_type} · {item.status.replaceAll("_", " ")}
                  </div>
                  <div>{item.question}</div>
                  <div>Review artifacts are stored in the local AI workspace.</div>
                  {item.rendered_output_path ? (
                    <div>
                      Rendered chart available. {" "}
                      <a href={buildHalChartFileUrl(item.rendered_output_path)} target="_blank" rel="noreferrer">
                        Open chart
                      </a>
                      <div>
                        <HalChartPreview path={item.rendered_output_path} alt={`${item.title} preview`} className="hal-chart-preview" />
                      </div>
                    </div>
                  ) : null}
                </div>
              ))}
            </>
          ) : null}
        </section>

        <section className="hal-answer-card">
          <h2>Accounting Documents</h2>
          <div className="hal-answer-card__section hal-answer-card__section--lead">
            OCR-processed invoices, receipts, and statements from the local ledger.
          </div>
          <form className="hal-form hal-form--narrative" onSubmit={(event) => event.preventDefault()}>
            <label htmlFor="hal-accounting-doc-search">Search OCR ledger</label>
            <input
              id="hal-accounting-doc-search"
              className="hal-form__textarea"
              value={documentSearch}
              onChange={(event) => setDocumentSearch(event.target.value)}
              placeholder="Search by vendor, invoice number, filename, or extracted text"
            />
            <label htmlFor="hal-accounting-doc-type">Document type</label>
            <select
              id="hal-accounting-doc-type"
              className="hal-form__textarea"
              value={documentType}
              onChange={(event) => setDocumentType(event.target.value)}
            >
              <option value="">All types</option>
              <option value="invoice">Invoice</option>
              <option value="receipt">Receipt</option>
              <option value="bank_statement">Bank statement</option>
              <option value="financial_document">Financial document</option>
            </select>
            <label htmlFor="hal-accounting-doc-review-only">Needs review only</label>
            <input
              id="hal-accounting-doc-review-only"
              type="checkbox"
              checked={reviewOnly}
              onChange={(event) => setReviewOnly(event.target.checked)}
            />
          </form>
          {accountingDocumentsQuery.isPending ? <div className="hal-answer-card__section">Loading OCR ledger...</div> : null}
          {accountingDocumentsQuery.isError ? (
            <div className="hal-answer-card__section">
              {accountingDocumentsQuery.error instanceof Error
                ? accountingDocumentsQuery.error.message
                : "Unable to load local accounting documents."}
            </div>
          ) : null}
          {accountingDocumentsQuery.data ? (
            <>
              <div className="hal-answer-card__section">
                <strong>Documents:</strong> {accountingDocumentsQuery.data.count}
              </div>
              {accountingDocumentsQuery.data.items.length === 0 ? (
                <div className="hal-answer-card__section">No OCR documents matched this search.</div>
              ) : null}
              {accountingDocumentsQuery.data.items.map((item) => (
                <div key={item.id} className="hal-supporting-context-item">
                  <strong>{item.vendor_name || item.source_name}</strong>
                  <div>
                    <span className={confidenceBadgeClass(item.confidence_label, item.review_required)}>{item.confidence_label}</span>
                  </div>
                  <div>
                    {buildCorrectionFlags(item).map((flag) => (
                      <span
                        key={`${item.id}-${flag}`}
                        className="dashboard-import-status-badge dashboard-import-status-badge--pending dashboard-import-status-badge--spaced"
                      >
                        {flag}
                      </span>
                    ))}
                    {buildCorrectionFlags(item).length === 0 ? <span className="dashboard-import-status-badge">no corrections</span> : null}
                  </div>
                  <div>{item.invoice_number || item.source_name}</div>
                  <div>
                    {item.document_type} · {item.document_date || "date unavailable"} ·{" "}
                    {item.total_amount !== null ? `${item.currency} ${item.total_amount.toFixed(2)}` : "total unavailable"}
                  </div>
                  <div>{item.text_preview}</div>
                </div>
              ))}
            </>
          ) : null}
        </section>
      </div>
    </div>
  );
}
