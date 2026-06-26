import { useMutation, useQuery } from "@tanstack/react-query";
import { type FormEvent, useEffect, useRef, useState } from "react";

import {
  askHalQuestion,
  createHalConversationId,
  executeMonitorReviewAction,
  fetchFinancialSummary,
  fetchHalStatus,
  type SoftDentDraftArtifact,
  type SoftDentLocalPacketArtifact,
} from "../api/client";
import { ApprovedLocalPacketsPanel } from "../components/hal/ApprovedLocalPacketsPanel";
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

function isHalQuestionSubmittable(value: string): boolean {
  return value.trim().length >= HAL_QUESTION_MIN_LENGTH;
}

function humanizeLabel(value: string) {
  return value.replaceAll("_", " ");
}

function humanizeLaneLabel(value: string) {
  return value.replaceAll("_", " ");
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
  const [useSecondOpinion, setUseSecondOpinion] = useState(false);
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

  const trimmedQuestion = question.trim();
  const questionTooShort = trimmedQuestion.length > 0 && trimmedQuestion.length < HAL_QUESTION_MIN_LENGTH;
  const canSubmitQuestion = isHalQuestionSubmittable(question) && !halMutation.isPending;

  function submitHalQuestion(lane: "primary" | "second_opinion") {
    if (!isHalQuestionSubmittable(question) || halMutation.isPending || askInFlightRef.current) {
      return;
    }
    askInFlightRef.current = true;
    setLastRequestLane(lane);
    actionMutation.reset();
    setSpeechError(null);
    setIsSpeaking(false);
    halMutation.mutate({ nextQuestion: trimmedQuestion, lane });
  }

  function handleAsk(e: FormEvent) {
    e.preventDefault();
    submitHalQuestion(useSecondOpinion ? "second_opinion" : "primary");
  }

  function handleRetryAsk() {
    submitHalQuestion(lastRequestLane);
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
          <p className="eyebrow">HAL workstation</p>
          <h1>Ask HAL</h1>
          <p>
            HAL is the dental office manager assistant: read authorized facts, prepare drafts for review, approve local
            packets, and track local office tasks while staying local only — still not submitted, still not written to
            SoftDent, and still no external delivery.
          </p>
        </header>

        <div className="hal-workstation-layout">
          <div className="hal-workstation-main">
            <HalCommandCenter
              question={question}
              setQuestion={setQuestion}
              useSecondOpinion={useSecondOpinion}
              setUseSecondOpinion={setUseSecondOpinion}
              questionTooShort={questionTooShort}
              canSubmitQuestion={canSubmitQuestion}
              isPending={halMutation.isPending}
              onSubmit={handleAsk}
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

            <HalRecommendationBlock response={response} reviewDepth={lastRequestLane} speechControls={speechControls} />

            {response ? (
              <section className="hal-workstation-card">
                <h2>Safeguards and session details</h2>
                <p>
                  <strong>Response profile:</strong> {response.voice_profile.label} · {response.voice_profile.tone}
                </p>
                <p>
                  <strong>Answer lane:</strong> {humanizeLaneLabel(response.voice_profile.lane)}
                </p>
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
            <PatientPrepPanel onPrefillDraftQuery={setDraftPrefillQuery} />
            <ClaimsFollowUpPanel
              financialSummary={financialSummaryQuery.data}
              onPrefillDraftQuery={setDraftPrefillQuery}
            />
            <LocalOfficeTasksPanel />
            <TreatmentPlanFollowUpPanel />
            <HygieneRecallPanel />
            <ComplianceChecklistPanel />
            <VendorIssueTrackerPanel />
            <OfficeManagerReportsPanel />
          </div>

          <aside className="hal-workstation-side">
            <TodaysAttentionPanel />
            <HalSystemHealthPanel
              halStatus={halStatusQuery.data}
              financialSummary={financialSummaryQuery.data}
              isLoading={halStatusQuery.isPending || financialSummaryQuery.isPending}
            />
            <HalSourcesPanel response={response} />
          </aside>
        </div>
      </div>
    </div>
  );
}
