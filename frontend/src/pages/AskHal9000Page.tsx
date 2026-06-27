import { useMutation, useQuery } from "@tanstack/react-query";
import { type FormEvent, type ReactNode, useEffect, useRef, useState } from "react";

import {
  askHalQuestion,
  createHalConversationId,
  executeMonitorReviewAction,
  fetchFinancialSummary,
  fetchHalStatus,
  fetchOfficeManagerTaskMetrics,
  fetchSoftDentEndOfDayAr,
  type SoftDentDraftArtifact,
  type SoftDentLocalPacketArtifact,
} from "../api/client";
import { ApprovedLocalPacketsPanel } from "../components/hal/ApprovedLocalPacketsPanel";
import { ClaimPacketReadinessPanel } from "../components/hal/ClaimPacketReadinessPanel";
import { ClaimsFollowUpPanel } from "../components/hal/ClaimsFollowUpPanel";
import { ComplianceChecklistPanel } from "../components/hal/ComplianceChecklistPanel";
import { DraftsForReviewPanel } from "../components/hal/DraftsForReviewPanel";
import { HalCommandCenter } from "../components/hal/HalCommandCenter";
import { HalRecommendationBlock } from "../components/hal/HalRecommendationBlock";
import { HalSourcesPanel } from "../components/hal/HalSourcesPanel";
import { HalSystemHealthPanel } from "../components/hal/HalSystemHealthPanel";
import { HygieneRecallPanel } from "../components/hal/HygieneRecallPanel";
import { LocalOfficeTasksPanel } from "../components/hal/LocalOfficeTasksPanel";
import { OfficeManagerReportsPanel } from "../components/hal/OfficeManagerReportsPanel";
import { PatientPrepPanel } from "../components/hal/PatientPrepPanel";
import { TodaysAttentionPanel } from "../components/hal/TodaysAttentionPanel";
import { TreatmentPlanFollowUpPanel } from "../components/hal/TreatmentPlanFollowUpPanel";
import { VendorIssueTrackerPanel } from "../components/hal/VendorIssueTrackerPanel";
import "../components/hal/HalWorkstation.css";

const HAL_SPEECH_VOICE_KEY = "halSpeechVoice";
const HAL_SPEECH_RATE_KEY = "halSpeechRate";
const HAL_QUESTION_MIN_LENGTH = 3;
const HAL_PROMPT_SUGGESTIONS = [
  "What needs attention today?",
  "Prepare morning huddle",
  "Review claims needing follow-up",
  "Check today's A/R",
];

function isHalQuestionSubmittable(value: string): boolean {
  return value.trim().length >= HAL_QUESTION_MIN_LENGTH;
}

function humanizeLabel(value: string) {
  return value.replaceAll("_", " ");
}

function humanizeLaneLabel(value: string) {
  switch (value) {
    case "deterministic":
      return "Verified local status";
    case "fast_model":
      return "Routine office assistant";
    case "primary":
      return "Main reasoning";
    case "fallback":
      return "Deeper review";
    default:
      return value.replaceAll("_", " ");
  }
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

function formatCurrency(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "Not available";
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

type SnapshotCard = {
  label: string;
  value: string;
  tone: "ok" | "pending";
};

function describeArSnapshot(
  endOfDayAr: Awaited<ReturnType<typeof fetchSoftDentEndOfDayAr>> | undefined,
  isError: boolean,
): SnapshotCard {
  if (isError || !endOfDayAr) {
    return { label: "Daily A/R", value: "DAYSHEET not imported yet", tone: "pending" };
  }
  if (endOfDayAr.available && typeof endOfDayAr.total_ar === "number") {
    return { label: "Daily A/R", value: formatCurrency(endOfDayAr.total_ar), tone: "ok" };
  }
  if (endOfDayAr.freshness_status === "stale") {
    return { label: "Daily A/R", value: "Last report is stale", tone: "pending" };
  }
  return { label: "Daily A/R", value: "DAYSHEET not imported yet", tone: "pending" };
}

function describeClaimsSnapshot(
  financialSummary: Awaited<ReturnType<typeof fetchFinancialSummary>> | undefined,
): SnapshotCard {
  const claims = financialSummary?.claimsSummary;
  if (!claims?.available) {
    return { label: "Claims follow-up", value: "Claims export not imported yet", tone: "pending" };
  }
  const count = claims.unsubmitted_claims_count ?? 0;
  return { label: "Claims follow-up", value: `${count} to review`, tone: "ok" };
}

function describeTasksSnapshot(
  metrics: Awaited<ReturnType<typeof fetchOfficeManagerTaskMetrics>> | undefined,
): SnapshotCard {
  const open = metrics?.open_count ?? 0;
  return { label: "Open tasks", value: `${open} open`, tone: open > 0 ? "ok" : "pending" };
}

function describeDraftsSnapshot(draftsAwaitingReview: number): SnapshotCard {
  if (draftsAwaitingReview > 0) {
    return { label: "Drafts", value: `${draftsAwaitingReview} awaiting review`, tone: "ok" };
  }
  return { label: "Drafts", value: "None awaiting review", tone: "pending" };
}

function TodaysMission({
  financialSummary,
  endOfDayAr,
  endOfDayArError,
  taskMetrics,
  draftsAwaitingReview,
}: {
  financialSummary?: Awaited<ReturnType<typeof fetchFinancialSummary>>;
  endOfDayAr?: Awaited<ReturnType<typeof fetchSoftDentEndOfDayAr>>;
  endOfDayArError: boolean;
  taskMetrics?: Awaited<ReturnType<typeof fetchOfficeManagerTaskMetrics>>;
  draftsAwaitingReview: number;
}) {
  const cards: SnapshotCard[] = [
    describeArSnapshot(endOfDayAr, endOfDayArError),
    describeClaimsSnapshot(financialSummary),
    describeTasksSnapshot(taskMetrics),
    describeDraftsSnapshot(draftsAwaitingReview),
  ];

  return (
    <section className="hal-today-section" aria-labelledby="hal-today-title">
      <h2 id="hal-today-title" className="hal-section-title">
        Today&apos;s Mission
      </h2>
      <div className="hal-snapshot-grid">
        {cards.map((card) => (
          <div key={card.label} className={`hal-snapshot-card hal-snapshot-card--${card.tone}`}>
            <span>{card.label}</span>
            <strong>{card.value}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}

function AutomationCenter({
  onPrefillDraftQuery,
  onAskPrefill,
}: {
  onPrefillDraftQuery: (query: string) => void;
  onAskPrefill: (question: string) => void;
}) {
  const tiles: { badge: string; title: string; description: string; action: string; onClick: () => void }[] = [
    {
      badge: "PC",
      title: "Prepare Patient Call",
      description: "Creates a local patient/claim summary for staff review.",
      action: "Prepare summary",
      onClick: () => onPrefillDraftQuery("patient call prep summary"),
    },
    {
      badge: "CL",
      title: "Review Claims",
      description: "Checks claim follow-up readiness and drafts local next steps.",
      action: "Review claims",
      onClick: () => onPrefillDraftQuery("denied claim follow-up checklist"),
    },
    {
      badge: "CP",
      title: "Claim Packet Readiness",
      description: "Checks local claim packet facts, missing items, and draft readiness.",
      action: "Review packets",
      onClick: () => onAskPrefill("claim packet readiness"),
    },
    {
      badge: "AR",
      title: "Daily A/R Check",
      description: "Reads the SoftDent DAYSHEET when imported.",
      action: "Check A/R",
      onClick: () => onAskPrefill("Check today's A/R"),
    },
    {
      badge: "MH",
      title: "Morning Huddle",
      description: "Creates a short staff huddle summary.",
      action: "Draft huddle",
      onClick: () => onAskPrefill("Prepare morning huddle"),
    },
    {
      badge: "MD",
      title: "Missing Documents",
      description: "Prepares a local review list for missing records.",
      action: "List documents",
      onClick: () => onPrefillDraftQuery("missing documentation checklist"),
    },
    {
      badge: "TK",
      title: "Create Office Task",
      description: "Adds an internal office follow-up task.",
      action: "Create task",
      onClick: () => onAskPrefill("Create a local office task for staff follow-up"),
    },
  ];

  return (
    <section className="hal-automation-center" aria-labelledby="hal-automation-title">
      <h2 id="hal-automation-title" className="hal-section-title">
        Automation Center
      </h2>
      <div className="hal-automation-grid">
        {tiles.map((tile) => (
          <article key={tile.title} className="hal-automation-tile">
            <div className="hal-automation-tile__head">
              <span className="hal-automation-tile__badge" aria-hidden="true">
                {tile.badge}
              </span>
              <h3>{tile.title}</h3>
            </div>
            <p>{tile.description}</p>
            <button type="button" className="hal-automation-tile__action" onClick={tile.onClick}>
              {tile.action}
            </button>
          </article>
        ))}
      </div>
      <p className="hal-muted-line">Every tile prepares a local draft or review item. Nothing is submitted.</p>
    </section>
  );
}

type WorkQueueItem = { id: string; label: string };

function WorkQueueBuckets({
  arAvailable,
  claimsAvailable,
  draftsAwaitingReview,
  packetsReady,
}: {
  arAvailable: boolean;
  claimsAvailable: boolean;
  draftsAwaitingReview: number;
  packetsReady: number;
}) {
  const needsReview: WorkQueueItem[] = [];
  if (draftsAwaitingReview > 0) {
    needsReview.push({ id: "drafts", label: `${draftsAwaitingReview} draft(s) awaiting human review` });
  }
  if (packetsReady > 0) {
    needsReview.push({ id: "packets", label: `${packetsReady} local packet(s) ready for internal use` });
  }
  if (needsReview.length === 0) {
    needsReview.push({ id: "drafts-empty", label: "No drafts awaiting review yet" });
  }

  const ready: WorkQueueItem[] = [
    { id: "ask", label: "Ask HAL" },
    { id: "tasks", label: "Local office tasks" },
    { id: "huddle", label: "Morning huddle draft" },
  ];

  const blocked: WorkQueueItem[] = [];
  if (!claimsAvailable) {
    blocked.push({ id: "claims", label: "Claims follow-up needs claims export" });
  }
  blocked.push({ id: "treatment", label: "Treatment plans need treatment-plan export" });
  if (!arAvailable) {
    blocked.push({ id: "ar", label: "A/R needs DAYSHEET import" });
  }

  const buckets: { key: string; title: string; items: WorkQueueItem[] }[] = [
    { key: "needs-review", title: "Needs Review", items: needsReview },
    { key: "ready", title: "Ready", items: ready },
    { key: "blocked", title: "Blocked", items: blocked },
  ];

  return (
    <section className="hal-section" aria-labelledby="hal-work-queue-title">
      <h2 id="hal-work-queue-title" className="hal-section-title">
        Work Queue
      </h2>
      <div className="hal-work-queue-grid">
        {buckets.map((bucket) => (
          <div key={bucket.key} className={`hal-queue-bucket hal-queue-bucket--${bucket.key}`}>
            <h3>{bucket.title}</h3>
            <ul>
              {bucket.items.map((item) => (
                <li key={item.id}>{item.label}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}

function CollapsiblePanel({
  title,
  description,
  defaultOpen = false,
  children,
}: {
  title: string;
  description?: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  return (
    <details className="hal-workstation-card hal-work-queue" open={defaultOpen}>
      <summary>
        <span className="hal-work-queue__title">{title}</span>
        {description ? <span className="hal-work-queue__hint">{description}</span> : null}
      </summary>
      <div className="hal-work-queue__content">{children}</div>
    </details>
  );
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
  const [selectedDraft, setSelectedDraft] = useState<SoftDentDraftArtifact | null>(null);
  const [selectedPacket, setSelectedPacket] = useState<SoftDentLocalPacketArtifact | null>(null);
  const [draftPrefillQuery, setDraftPrefillQuery] = useState("");
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
  const halStatusQuery = useQuery({
    queryKey: ["hal-status"],
    queryFn: fetchHalStatus,
  });
  const endOfDayArQuery = useQuery({
    queryKey: ["softdent-end-of-day-ar"],
    queryFn: fetchSoftDentEndOfDayAr,
  });
  const taskMetricsQuery = useQuery({
    queryKey: ["office-manager-task-metrics"],
    queryFn: fetchOfficeManagerTaskMetrics,
  });
  const halMutation = useMutation({
    mutationFn: (nextQuestion: string) =>
      askHalQuestion(nextQuestion, {
        conversationId: conversationIdRef.current,
      }),
    onSettled: () => {
      askInFlightRef.current = false;
    },
  });
  const actionMutation = useMutation({
    mutationFn: executeMonitorReviewAction,
  });

  const trimmedQuestion = question.trim();
  const questionTooShort = trimmedQuestion.length > 0 && trimmedQuestion.length < HAL_QUESTION_MIN_LENGTH;
  const canSubmitQuestion = isHalQuestionSubmittable(question) && !halMutation.isPending;

  function submitHalQuestion() {
    if (!isHalQuestionSubmittable(question) || halMutation.isPending || askInFlightRef.current) {
      return;
    }
    askInFlightRef.current = true;
    actionMutation.reset();
    setSpeechError(null);
    setIsSpeaking(false);
    halMutation.mutate(trimmedQuestion);
  }

  function handleAsk(e: FormEvent) {
    e.preventDefault();
    submitHalQuestion();
  }

  function askPrefilledQuestion(prefilled: string) {
    const trimmed = prefilled.trim();
    setQuestion(trimmed);
    if (!isHalQuestionSubmittable(trimmed) || halMutation.isPending || askInFlightRef.current) {
      return;
    }
    askInFlightRef.current = true;
    actionMutation.reset();
    setSpeechError(null);
    setIsSpeaking(false);
    halMutation.mutate(trimmed);
  }

  function handleRetryAsk() {
    submitHalQuestion();
  }

  const response = halMutation.data;
  const reviewAction = response?.review_actions.find((item) => item.action_type === "SET_LUMINANCE");
  const taskMetrics = taskMetricsQuery.data;
  const hasOpenTasks = (taskMetrics?.open_count ?? 0) > 0 || (taskMetrics?.urgent_open_count ?? 0) > 0;
  const draftsAwaitingReview = selectedDraft ? 1 : 0;
  const packetsReady = selectedPacket ? 1 : 0;
  const arAvailable = endOfDayArQuery.data?.available === true && typeof endOfDayArQuery.data?.total_ar === "number";
  const claimsAvailable = financialSummaryQuery.data?.claimsSummary?.available === true;

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
        const englishChromeVoice = voices.find(
          (voice) => /^en(-|$)/i.test(voice.lang) && /google|chrome/i.test(`${voice.name} ${voice.voiceURI}`),
        );
        if (englishChromeVoice) {
          return englishChromeVoice.name;
        }
        const englishVoice = voices.find((voice) => /^en(-|$)/i.test(voice.lang));
        if (englishVoice) {
          return englishVoice.name;
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

  const speechControls = response ? (
    <div className="hal-answer-card__section hal-speech-controls">
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
      <span>{speechRate.toFixed(1)}x</span>
      <button type="button" className="refresh-button" onClick={handleSpeakResponse}>
        Read It Aloud
      </button>
      {isSpeaking ? (
        <button type="button" className="refresh-button" onClick={handleStopSpeaking}>
          Stop Reading
        </button>
      ) : null}
      {speechError ? <span>{speechError}</span> : null}
    </div>
  ) : null;

  return (
    <div className="dashboard-page dashboard-page--hal hal-workstation-page">
      <div className="page-content">
        <header className="page-header hal-workstation-header">
          <p className="eyebrow">HAL</p>
          <h1>HAL Command Center</h1>
          <p>HAL runs the front-office command center. See what needs attention, ask HAL, and prepare local drafts for review.</p>
        </header>

        <div className="hal-office-layout">
          <div className="hal-workstation-main">
            <HalCommandCenter
              question={question}
              setQuestion={setQuestion}
              questionTooShort={questionTooShort}
              canSubmitQuestion={canSubmitQuestion}
              isPending={halMutation.isPending}
              onSubmit={handleAsk}
              suggestions={HAL_PROMPT_SUGGESTIONS}
            />

            {halMutation.isError ? (
              <div className="hal-workstation-card">
                <h2>That request did not go through</h2>
                <p>
                  {halMutation.error instanceof Error
                    ? halMutation.error.message
                    : "HAL could not finish that request. Check permissions or source availability."}
                </p>
                <button type="button" className="refresh-button" onClick={handleRetryAsk} disabled={!canSubmitQuestion}>
                  {halMutation.isPending ? "Retrying..." : "Try Again"}
                </button>
              </div>
            ) : null}

            <HalRecommendationBlock response={response} speechControls={speechControls} />

            {reviewAction ? (
              <section className="hal-workstation-card hal-review-actions">
                <h2>Before Anything Changes</h2>
                <div className="hal-review-actions__card">
                  <div className="hal-answer-card__section hal-answer-card__section--lead">{reviewAction.title}</div>
                  <div className="hal-answer-card__section">{reviewAction.confirmation_message}</div>
                  <div className="hal-answer-card__section">
                    <strong>Approval status:</strong> {humanizeLabel(reviewAction.status)}
                  </div>
                  <button
                    type="button"
                    className="refresh-button"
                    onClick={handleApproveDisplayAdjustment}
                    disabled={actionMutation.isPending}
                  >
                    {actionMutation.isPending ? "Approving..." : `Approve brightness change to ${reviewAction.target_value}%`}
                  </button>
                  {actionMutation.data ? (
                    <div className="hal-review-actions__result">
                      <strong>Action result:</strong> {humanizeLabel(actionMutation.data.status)}
                      {actionMutation.data.applied_value !== null ? ` (${actionMutation.data.applied_value}%)` : ""}
                      {actionMutation.data.error ? ` - ${actionMutation.data.error}` : ""}
                    </div>
                  ) : null}
                  {actionMutation.isError ? (
                    <div className="hal-review-actions__result hal-review-actions__result--error">
                      {actionMutation.error instanceof Error
                        ? actionMutation.error.message
                        : "Unable to execute the reviewed action."}
                    </div>
                  ) : null}
                </div>
              </section>
            ) : null}

            <TodaysMission
              financialSummary={financialSummaryQuery.data}
              endOfDayAr={endOfDayArQuery.data}
              endOfDayArError={endOfDayArQuery.isError}
              taskMetrics={taskMetricsQuery.data}
              draftsAwaitingReview={draftsAwaitingReview}
            />

            <AutomationCenter onPrefillDraftQuery={setDraftPrefillQuery} onAskPrefill={askPrefilledQuestion} />

            <WorkQueueBuckets
              arAvailable={arAvailable}
              claimsAvailable={claimsAvailable}
              draftsAwaitingReview={draftsAwaitingReview}
              packetsReady={packetsReady}
            />

            <section className="hal-section" aria-labelledby="hal-office-work-title">
              <h2 id="hal-office-work-title" className="hal-section-title">
                Office work
              </h2>
              <CollapsiblePanel title="Priorities to Review" description="What needs review today (local only)">
                <TodaysAttentionPanel />
              </CollapsiblePanel>
              <CollapsiblePanel
                title="Local Tasks"
                description={hasOpenTasks ? "Open tasks need attention" : "No open tasks"}
                defaultOpen={hasOpenTasks}
              >
                <LocalOfficeTasksPanel />
              </CollapsiblePanel>
              <CollapsiblePanel title="Drafts for Review" description="Local review items only">
                <DraftsForReviewPanel
                  selectedDraft={selectedDraft}
                  onDraftCreated={setSelectedDraft}
                  initialPatientQuery={draftPrefillQuery}
                />
                <ApprovedLocalPacketsPanel
                  selectedDraft={selectedDraft}
                  selectedPacket={selectedPacket}
                  onPacketCreated={setSelectedPacket}
                />
              </CollapsiblePanel>
              <CollapsiblePanel title="Claim Packet Readiness" description="Local packet facts and missing items">
                <ClaimPacketReadinessPanel onAskPrefill={askPrefilledQuestion} />
              </CollapsiblePanel>
              <CollapsiblePanel title="Claim Follow-Up">
                <ClaimsFollowUpPanel
                  financialSummary={financialSummaryQuery.data}
                  onPrefillDraftQuery={setDraftPrefillQuery}
                />
              </CollapsiblePanel>
              <CollapsiblePanel title="Patient Prep">
                <PatientPrepPanel onPrefillDraftQuery={setDraftPrefillQuery} />
              </CollapsiblePanel>
              <CollapsiblePanel title="Treatment Follow-Up">
                <TreatmentPlanFollowUpPanel />
              </CollapsiblePanel>
              <CollapsiblePanel title="Hygiene Recall">
                <HygieneRecallPanel />
              </CollapsiblePanel>
              <CollapsiblePanel title="Compliance Checklist">
                <ComplianceChecklistPanel />
              </CollapsiblePanel>
              <CollapsiblePanel title="Vendor Issues">
                <VendorIssueTrackerPanel />
              </CollapsiblePanel>
              <CollapsiblePanel title="Reports">
                <OfficeManagerReportsPanel />
              </CollapsiblePanel>
            </section>

            <p className="hal-safety-footer" role="note">
              HAL is local-only and read-only. Drafts require human review. No SoftDent writeback, email, fax, upload,
              Gateway, or payer submission.
            </p>

            <details className="hal-workstation-card hal-details-drawer">
              <summary>Advanced details</summary>
              <div className="hal-details-drawer__content">
                {response ? (
                  <section className="hal-advanced-session" aria-labelledby="hal-session-details-title">
                    <h2 id="hal-session-details-title">Diagnostics and safeguards</h2>
                    <p>
                      <strong>Reference ID:</strong> {response.audit_id}
                    </p>
                    <p>
                      <strong>Response profile:</strong> {response.voice_profile.label} · {response.voice_profile.tone}
                    </p>
                    <p>
                      <strong>Answer lane:</strong> {humanizeLaneLabel(response.voice_profile.lane)}
                    </p>
                    {response.answer_lane ? (
                      <p>
                        <strong>Internal lane:</strong> {humanizeLaneLabel(response.answer_lane)}
                      </p>
                    ) : null}
                    {response.model_used ? (
                      <p>
                        <strong>Model used:</strong> {response.model_used}
                      </p>
                    ) : null}
                    {typeof response.escalated === "boolean" ? (
                      <p>
                        <strong>Escalated:</strong> {response.escalated ? "Yes" : "No"}
                      </p>
                    ) : null}
                    {(response.voice_profile.style_notes ?? []).length ? (
                      <p>
                        <strong>Style notes:</strong> {response.voice_profile.style_notes.join(" ")}
                      </p>
                    ) : null}
                    <p>
                      <strong>Saved question:</strong> {response.sanitized_question}
                    </p>
                    <p>
                      <strong>Built-in safeguards:</strong> {response.guardrails.map(humanizeGuardrail).join(", ")}
                    </p>
                    <p>
                      <strong>Governance:</strong>{" "}
                      {(response.governance_notes ?? []).length
                        ? response.governance_notes.map((item) => `${item.label}: ${item.detail}`).join(" | ")
                        : "No governed memory changes were saved silently."}
                    </p>
                  </section>
                ) : null}
                {(endOfDayArQuery.data?.missing_data_codes ?? []).length ? (
                  <section className="hal-advanced-session" aria-labelledby="hal-raw-codes-title">
                    <h2 id="hal-raw-codes-title">Missing data codes (raw)</h2>
                    <p>{(endOfDayArQuery.data?.missing_data_codes ?? []).join(", ")}</p>
                  </section>
                ) : null}
                <HalSystemHealthPanel
                  halStatus={halStatusQuery.data}
                  financialSummary={financialSummaryQuery.data}
                  isLoading={halStatusQuery.isPending || financialSummaryQuery.isPending}
                />
                <HalSourcesPanel response={response} />
              </div>
            </details>
          </div>
        </div>
      </div>
    </div>
  );
}
