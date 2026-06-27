import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "../App";
import { clearApiBasicAuthCredentials, setApiBasicAuthCredentials } from "../api/basicAuth";
import {
  type FinancialSummaryResponse,
  askHalQuestion,
  draftJournalEntry,
  executeMonitorReviewAction,
  fetchAccountingPolicyAnswer,
  fetchAccountingPostingQueue,
  fetchAccountingPostingQueueActivity,
  fetchAdminSummary,
  fetchHalStatus,
  fetchHealth,
} from "../api/client";
import { accountingPostingQueueEntrySchema, defaultHalVoiceProfile } from "../api/schemas";
import { server } from "../mocks/server";
import { queryClient } from "../queryClient";
import { DRAFT_STATUS_DRAFT_ONLY } from "../utils/journalDraftStatus";
import { ENQUEUE_MODE_AUTO_VALIDATED_AI } from "../utils/postingQueueLineage";
import { POSTING_QUEUE_STATUS_PENDING_REVIEW } from "../utils/postingQueueStatus";

function buildHalAskMockResponse(overrides: Record<string, unknown> = {}) {
  return {
    mode: "local-rag-phase-1",
    answer: "HAL handled: example",
    sanitized_question: "",
    sanitization_findings: [],
    retrieved_context: [],
    guardrails: ["approved local read-only scope"],
    audit_id: "hal-ask-mock-1",
    access_policy: {
      mode: "local-rag-phase-1",
      auth_requirement: "auth",
      network_boundary: "local",
      audited: true,
      allowed_sources: [],
      disallowed_actions: [],
    },
    review_actions: [],
    voice_profile: defaultHalVoiceProfile,
    governance_notes: [],
    ...overrides,
  };
}

function renderApp(pathname: string): void {
  cleanup();
  queryClient.clear();
  setApiBasicAuthCredentials("admin", "password");
  window.history.pushState({}, "", pathname);
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter basename="/app" initialEntries={[pathname]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  clearApiBasicAuthCredentials();
  queryClient.clear();
  cleanup();
});

describe("api mocks", () => {
  it("mocks the health endpoint", async () => {
    const payload = await fetchHealth();
    expect(payload.status).toBe("ok");
  });

  it("mocks the admin endpoint and renders the admin screen", async () => {
    const payload = await fetchAdminSummary();
    expect(payload.kpis).toHaveLength(2);
    const halStatus = await fetchHalStatus();
    expect(halStatus.backend).toBe("chroma");
    const postingQueueActivity = await fetchAccountingPostingQueueActivity(10);
    expect(postingQueueActivity.items[0].enqueue_mode).toBe(ENQUEUE_MODE_AUTO_VALIDATED_AI);
    expect(postingQueueActivity.items[0]).not.toHaveProperty("lines");

    renderApp("/app/admin");

    expect(await screen.findByRole("heading", { name: "Owner financial dashboard" })).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByRole("button", {
          name: /HAL Refresh SoftDent \+ QuickBooks/i,
        }),
      ).toBeInTheDocument(),
    );
    expect(await screen.findByText("HAL Retrieval Status")).toBeInTheDocument();
    expect(screen.getByText("onnx-minilm")).toBeInTheDocument();
    expect(screen.getByText(/SOFTDENT SNAPSHOT/)).toBeInTheDocument();
    expect(screen.getByText(/SOFTDENT PRACTICE PRODUCTION/)).toBeInTheDocument();
    expect(screen.getByText(/SOFTDENT PAYER MIX/)).toBeInTheDocument();
    expect(screen.getByText(/SOFTDENT COLLECTIONS DELTA/)).toBeInTheDocument();
    expect(screen.getByText(/SOFTDENT CLAIMS/)).toBeInTheDocument();
    expect(screen.getByText(/SOFTDENT CLINICAL NOTES/)).toBeInTheDocument();
    expect(screen.getAllByText(/production 135000.0, collections 126500.0/)).toHaveLength(3);
    expect(screen.getByText(/SoftDent practice production for 2026-05: production 135000.0, collections 126500.0, insurance 74500.0, patient 52000.0./)).toBeInTheDocument();
    expect(screen.getByText(/insurance collections share 0.5889, patient collections share 0.4111/)).toBeInTheDocument();
    expect(screen.getByText(/delta 8500.0, collection ratio 0.937/)).toBeInTheDocument();
    expect(screen.getAllByText(/Source file: softdent_dashboard_data.json/)).toHaveLength(4);
    expect(screen.getByText(/ClaimStatus=Denied/)).toBeInTheDocument();
    expect(screen.getByText(/ClinicalNote=PATIENT_REDACTED sensitivity persists/)).toBeInTheDocument();
    expect(screen.getByText(/Source file: softdent_claims_export.csv/)).toBeInTheDocument();
    expect(screen.getByText(/Source file: softdent_clinical_notes_data.json/)).toBeInTheDocument();
    expect(screen.getAllByText("high confidence").length).toBeGreaterThan(0);
    expect(screen.getByText("review suggested")).toBeInTheDocument();
    expect(screen.getByText(/contains clinical-note source/)).toBeInTheDocument();
    expect(screen.getByText("QuickBooks HAL Tool Readiness")).toBeInTheDocument();
    expect(screen.getAllByText(/TotalIncome=60040.78/)).toHaveLength(2);
    expect(screen.getByText(/TotalExpense=25333.48/)).toBeInTheDocument();
    expect(screen.getAllByText(/Last checked: 2026-06-15T12:00:00\+00:00/)).toHaveLength(9);
    expect(screen.getAllByText("manual review").length).toBeGreaterThan(0);
    expect(screen.getByText(/live quickbooks summary missing/)).toBeInTheDocument();
    expect(screen.getByText("Configured SQL")).toBeInTheDocument();
    expect(screen.getByText("2026-05 · practice-wide")).toBeInTheDocument();
    expect(screen.getByText("QuickBooks Posting Queue")).toBeInTheDocument();
    expect(screen.getByText("Recent Posting Queue Activity")).toBeInTheDocument();
    expect(screen.getByText("Queue prepaid insurance entry for QuickBooks Desktop review.")).toBeInTheDocument();
    expect(screen.getByText("Queue vendor bill for QuickBooks Desktop review.")).toBeInTheDocument();
    expect(screen.getByText("Pending review")).toBeInTheDocument();
    expect(screen.getByText("Approved")).toBeInTheDocument();
    expect(screen.getByText("Recent Accounting Copilot Audits")).toBeInTheDocument();
    expect(screen.getByText(/local-rag-phase-1:accounting-policy/)).toBeInTheDocument();
    expect(screen.getByText(/local-rag-phase-1:journal-draft/)).toBeInTheDocument();
    expect(screen.getByText(/Queue handoff: pending review · qbd-queue-1001 · auto-validated AI/)).toBeInTheDocument();
    expect(screen.getByText(/Draft lineage: auto-validated AI draft/)).toBeInTheDocument();
    expect(screen.getByText("SoftDent Coverage Accountability")).toBeInTheDocument();
    expect(screen.getByText(/HAL now treats missing page report lanes as operator-visible issues/)).toBeInTheDocument();
    expect(screen.getByText(/Needed: 2/)).toBeInTheDocument();
    expect(screen.getByText(/Partial: 1/)).toBeInTheDocument();
    expect(screen.getByText(/Ready: 4/)).toBeInTheDocument();
    expect(screen.getByText(/True outstanding: \$12,401 across 9 claim\(s\)/)).toBeInTheDocument();
    expect(screen.getByText(/Unsubmitted: \$3,840 across 4 claim\(s\)/)).toBeInTheDocument();
    expect(screen.getByText(/Top outstanding payers: Delta Dental \$7,100 · MetLife \$3,801/)).toBeInTheDocument();
    expect(screen.getByText(/Top unsubmitted payers: Delta Dental \$2,200 · Cigna \$1,640/)).toBeInTheDocument();
    expect(screen.getByText(/Page coverage gaps/)).toBeInTheDocument();
    expect(screen.getByText(/SoftDent page coverage has 2 missing and 1 limited report lane\(s\)/)).toBeInTheDocument();
  });

  it("rejects invalid enqueue_mode values in the posting queue schema", () => {
    expect(() =>
      accountingPostingQueueEntrySchema.parse({
        queue_id: "qbd-queue-9999",
        created_at_utc: "2026-06-15T12:30:00Z",
        actor: "hal_operator",
        target_system: "quickbooks_desktop",
        status: POSTING_QUEUE_STATUS_PENDING_REVIEW,
        description: "Invalid lineage payload",
        transaction_date: "2026-06-15",
        accounting_period: "2026-06",
        amount: 100,
        transaction_type: null,
        source_audit_id: "hal-source-999",
        enqueue_mode: "legacy_import",
        lines: [],
        validation: {
          balanced: true,
          debit_total: 100,
          credit_total: 100,
          open_period: true,
          account_validation_passed: true,
          issues: [],
        },
        reviewer_actor: null,
        reviewed_at_utc: null,
        review_note: null,
        review_required: true,
      }),
    ).toThrow();
  });

  it("rejects invalid draft_status values in the journal draft schema", async () => {
    const { journalDraftResponseSchema } = await import("../api/schemas");

    expect(() =>
      journalDraftResponseSchema.parse({
        mode: "local-rag-phase-1",
        summary: "Drafted journal entry.",
        lines: [],
        validation: {
          balanced: true,
          debit_total: 100,
          credit_total: 100,
          open_period: true,
          account_validation_passed: true,
          issues: [],
        },
        supporting_context: [],
        review_required: true,
        draft_status: "queued_elsewhere",
        queue_id: null,
        queue_status: null,
        enqueue_error: null,
        audit_id: "hal-journal-1",
        access_policy: {
          mode: "local-rag-phase-1",
          auth_requirement: "auth",
          network_boundary: "local",
          audited: true,
          allowed_sources: [],
          disallowed_actions: [],
        },
      }),
    ).toThrow();

    expect(
      journalDraftResponseSchema.parse({
        mode: "local-rag-phase-1",
        summary: "Drafted journal entry.",
        lines: [],
        validation: {
          balanced: true,
          debit_total: 100,
          credit_total: 100,
          open_period: true,
          account_validation_passed: true,
          issues: [],
        },
        supporting_context: [],
        review_required: true,
        draft_status: DRAFT_STATUS_DRAFT_ONLY,
        queue_id: null,
        queue_status: null,
        enqueue_error: null,
        audit_id: "hal-journal-1",
        access_policy: {
          mode: "local-rag-phase-1",
          auth_requirement: "auth",
          network_boundary: "local",
          audited: true,
          allowed_sources: [],
          disallowed_actions: [],
        },
      }).draft_status,
    ).toBe(DRAFT_STATUS_DRAFT_ONLY);
  });

  it("renders the HAL review-action workflow", async () => {
    const halPayload = await askHalQuestion("Change brightness to 30% on the primary monitor.");
    expect(halPayload.review_actions[0]?.action_type).toBe("SET_LUMINANCE");

    const executionPayload = await executeMonitorReviewAction({
      action_type: "SET_LUMINANCE",
      target_value: 30,
      human_review_required: true,
      status: "pending_confirmation",
      user_confirmed: true,
    });
    expect(executionPayload.status).toBe("executed");

    renderApp("/app/hal");

    expect(await screen.findByRole("heading", { name: "HAL Command Center" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("What do you want HAL to help with?"), {
      target: {
        value: "Change brightness to 30% on the primary monitor.",
      },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask HAL" }));

    expect(await screen.findByText("Here's what I found")).toBeInTheDocument();
    expect(screen.getAllByText(/I can help with that\./).length).toBeGreaterThan(0);
    expect(screen.getByText(/Reference ID:/)).toBeInTheDocument();
    expect(screen.getByText(/Built-in safeguards:/)).toBeInTheDocument();
    expect(screen.getByText(/Verified Physical Monitor Parameters/)).toBeInTheDocument();
    expect(screen.getByText(/Approve brightness change to 30%/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Approve brightness change to 30%" }));

    expect(await screen.findByText(/Action result:/)).toBeInTheDocument();
    expect(screen.getByText(/executed/)).toBeInTheDocument();
  });

  it("resolves the legacy hal-9000 route to the current HAL page", async () => {
    renderApp("/app/hal-9000");

    expect(await screen.findByRole("heading", { name: "HAL Command Center" })).toBeInTheDocument();
    expect(screen.getByLabelText("What do you want HAL to help with?")).toBeInTheDocument();
  });

  it("does not attach the full dashboard summary payload to HAL ask requests", async () => {
    server.use(
      http.post("/api/hal9000", async ({ request }) => {
        const payload = (await request.json()) as {
          question?: string;
          summary?: { latestDailyKpi?: { gross_production?: number } };
        };
        expect(payload.question).toBe("What is the latest daily gross production?");
        expect(payload.summary).toBeUndefined();
        return HttpResponse.json(
          buildHalAskMockResponse({
            answer: "Latest daily gross production is $7,759.",
            sanitized_question: payload.question || "",
            audit_id: "hal-ask-summary-1",
          }),
        );
      }),
    );

    const halPayload = await askHalQuestion("What is the latest daily gross production?");

    expect(halPayload.answer).toMatch(/7,759/);
  });

  it("uses the single Ask HAL endpoint for all chat requests", async () => {
    server.use(
      http.post("/api/hal9000", async ({ request }) => {
        const payload = (await request.json()) as {
          question?: string;
        };
        expect(payload.question).toBe("Give me a deeper review of the latest daily gross production.");
        return HttpResponse.json(
          buildHalAskMockResponse({
            mode: "local-rag-phase-1:deeper-review",
            answer: "HAL deeper review: collections are not present in the verified context.",
            sanitized_question: payload.question || "",
            guardrails: ["approved local read-only scope", "internal 30B deeper review after frontline answer was inconclusive"],
            audit_id: "hal-ask-deeper-review-1",
            voice_profile: {
              lane: "deeper_review",
              label: "HAL needed a deeper review",
              tone: "grounded and staff-assistant",
              style_notes: [],
            },
          }),
        );
      }),
    );

    const halPayload = await askHalQuestion("Give me a deeper review of the latest daily gross production.");

    expect(halPayload.mode).toBe("local-rag-phase-1:deeper-review");
    expect(halPayload.voice_profile.label).toBe("HAL needed a deeper review");
  });

  it("blocks overlapping HAL submits on the Ask Hal page while a request is still running", async () => {
    let requestCount = 0;
    let resolveRequest: (() => void) | undefined;

    server.use(
      http.post("/api/hal9000", async ({ request }) => {
        requestCount += 1;
        const payload = (await request.json()) as { question?: string };
        await new Promise<void>((resolve) => {
          resolveRequest = () => resolve();
        });
        return HttpResponse.json(
          buildHalAskMockResponse({
            answer: `HAL handled: ${payload.question || ""}`,
            sanitized_question: payload.question || "",
            audit_id: "hal-ask-overlap-1",
          }),
        );
      }),
    );

    renderApp("/app/hal");

    fireEvent.change(await screen.findByLabelText("What do you want HAL to help with?"), {
      target: {
        value: "Give me the current operating picture.",
      },
    });

    const askButton = screen.getByRole("button", { name: "Ask HAL" });
    fireEvent.click(askButton);
    fireEvent.click(askButton);

    await waitFor(() => expect(requestCount).toBe(1));

    if (!resolveRequest) {
      throw new Error("Expected HAL overlap test request to be pending before release.");
    }

    resolveRequest();

    expect(await screen.findByText(/Here's what I found/)).toBeInTheDocument();
    expect(screen.getAllByText(/HAL handled: Give me the current operating picture\./).length).toBeGreaterThan(0);
  });

  it("does not submit HAL questions shorter than three characters", async () => {
    let requestCount = 0;
    server.use(
      http.post("/api/hal9000", async () => {
        requestCount += 1;
        return HttpResponse.json(
          buildHalAskMockResponse({
            answer: "HAL should not have been called.",
            sanitized_question: "hi",
            audit_id: "hal-ask-too-short-1",
          }),
        );
      }),
    );

    renderApp("/app/hal");

    fireEvent.change(await screen.findByLabelText("What do you want HAL to help with?"), {
      target: { value: "hi" },
    });

    expect(screen.getByText("Ask at least 3 characters.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ask HAL" })).toBeDisabled();
    expect(screen.queryByLabelText(/Use deeper second opinion/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Ask HAL" }));

    expect(requestCount).toBe(0);
  });

  it("submits HAL questions of at least three characters", async () => {
    let capturedQuestion = "";
    server.use(
      http.post("/api/hal9000", async ({ request }) => {
        const payload = (await request.json()) as { question?: string };
        capturedQuestion = payload.question || "";
        return HttpResponse.json(
          buildHalAskMockResponse({
            answer: "Here is what needs attention today.",
            sanitized_question: capturedQuestion,
            audit_id: "hal-ask-valid-length-1",
          }),
        );
      }),
    );

    renderApp("/app/hal");

    fireEvent.change(await screen.findByLabelText("What do you want HAL to help with?"), {
      target: { value: "What needs my attention today?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask HAL" }));

    expect(await screen.findByText("Here's what I found")).toBeInTheDocument();
    expect(capturedQuestion).toBe("What needs my attention today?");
    expect(screen.getAllByText(/Here is what needs attention today\./).length).toBeGreaterThan(0);
  });

  it("shows a generic error when HAL returns a malformed response shape", async () => {
    server.use(
      http.post("/api/hal9000", async () =>
        HttpResponse.json({
          mode: "local-rag-phase-1",
          answer: "broken",
        }),
      ),
    );

    await expect(askHalQuestion("What is the status?")).rejects.toThrow(
      /HAL returned an unexpected response shape\. Reference: hal-schema\./,
    );

    renderApp("/app/hal");
    fireEvent.change(await screen.findByLabelText("What do you want HAL to help with?"), {
      target: { value: "What is the status?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask HAL" }));

    expect(await screen.findByText(/HAL returned an unexpected response shape/)).toBeInTheDocument();
    expect(screen.queryByText(/invalid_type/)).not.toBeInTheDocument();
    expect(screen.queryByText(/voice_profile/)).not.toBeInTheDocument();
  });

  it("keeps the HAL page focused on the core ask-and-answer workflow", async () => {
    renderApp("/app/hal");

    expect(await screen.findByRole("heading", { name: "HAL Command Center" })).toBeInTheDocument();
    expect(screen.queryByText("Chart Requests")).not.toBeInTheDocument();
    expect(screen.queryByText("Recent Chart Requests")).not.toBeInTheDocument();
    expect(screen.queryByText("Accounting Files")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Chart idea")).not.toBeInTheDocument();
  });

  it("uses browser speech synthesis for the HAL response", async () => {
    window.localStorage.setItem("halSpeechVoice", "Chrome Kansas Voice");
    window.localStorage.setItem("halSpeechRate", "1.3");
    const speak = vi.fn(
      (utterance: {
        onstart?: (() => void) | null;
        onend?: (() => void) | null;
      }) => {
        utterance.onstart?.();
        utterance.onend?.();
      },
    );
    const cancel = vi.fn();
    const getVoices = vi.fn(() => [
      {
        name: "Google US English",
        lang: "en-US",
        voiceURI: "Google US English",
      },
      {
        name: "Chrome Kansas Voice",
        lang: "en-US",
        voiceURI: "Chrome Kansas Voice",
      },
    ]);

    Object.defineProperty(window, "speechSynthesis", {
      configurable: true,
      writable: true,
      value: { speak, cancel, getVoices, onvoiceschanged: null },
    });

    class MockSpeechSynthesisUtterance {
      text: string;
      onstart: (() => void) | null = null;
      onend: (() => void) | null = null;
      onerror: (() => void) | null = null;

      constructor(text: string) {
        this.text = text;
      }
    }

    Object.defineProperty(globalThis, "SpeechSynthesisUtterance", {
      configurable: true,
      writable: true,
      value: MockSpeechSynthesisUtterance,
    });

    renderApp("/app/hal");

    expect(await screen.findByRole("heading", { name: "HAL Command Center" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("What do you want HAL to help with?"), {
      target: {
        value: "Change brightness to 30% on the primary monitor.",
      },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask HAL" }));

    expect(await screen.findByText("Here's what I found")).toBeInTheDocument();
    expect(screen.getByText(/Response profile:/)).toBeInTheDocument();
    expect(screen.getByText(/Governance:/)).toBeInTheDocument();
    expect(screen.getByLabelText("Voice")).toBeInTheDocument();
    expect(screen.getByLabelText("Speech rate")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("Voice")).toHaveValue("Chrome Kansas Voice"));
    await waitFor(() => expect(screen.getByLabelText("Speech rate")).toHaveValue("1.3"));
    expect(speak).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Read It Aloud" }));

    expect(cancel).toHaveBeenCalled();
    expect(speak).toHaveBeenCalledTimes(1);
    expect((speak.mock.calls[0]?.[0] as { text: string }).text).toContain("I can help with that. I found the current monitor settings");
    expect((speak.mock.calls[0]?.[0] as { voice?: { name?: string }; rate?: number }).voice?.name).toBe("Chrome Kansas Voice");
    expect((speak.mock.calls[0]?.[0] as { rate?: number }).rate).toBe(1.3);
    fireEvent.change(screen.getByLabelText("Voice"), {
      target: { value: "Google US English" },
    });
    fireEvent.change(screen.getByLabelText("Speech rate"), {
      target: { value: "1.1" },
    });
    await waitFor(() => expect(screen.getByLabelText("Voice")).toHaveValue("Google US English"));
    await waitFor(() => expect(screen.getByLabelText("Speech rate")).toHaveValue("1.1"));
    fireEvent.click(screen.getByRole("button", { name: "Read It Aloud" }));
    expect((speak.mock.calls[1]?.[0] as { voice?: { name?: string }; rate?: number }).voice?.name).toBe("Google US English");
    expect((speak.mock.calls[1]?.[0] as { rate?: number }).rate).toBe(1.1);
    expect(window.localStorage.getItem("halSpeechVoice")).toBe("Google US English");
    expect(window.localStorage.getItem("halSpeechRate")).toBe("1.1");
  });

  it("does not auto-play HAL speech in automated browser sessions", async () => {
    const originalWebdriver = Object.getOwnPropertyDescriptor(window.navigator, "webdriver");
    const speak = vi.fn();
    const cancel = vi.fn();

    Object.defineProperty(window.navigator, "webdriver", {
      configurable: true,
      get: () => true,
    });

    Object.defineProperty(window, "speechSynthesis", {
      configurable: true,
      writable: true,
      value: { speak, cancel, getVoices: vi.fn(() => []), onvoiceschanged: null },
    });

    class MockSpeechSynthesisUtterance {
      text: string;
      onstart: (() => void) | null = null;
      onend: (() => void) | null = null;
      onerror: (() => void) | null = null;

      constructor(text: string) {
        this.text = text;
      }
    }

    Object.defineProperty(globalThis, "SpeechSynthesisUtterance", {
      configurable: true,
      writable: true,
      value: MockSpeechSynthesisUtterance,
    });

    try {
      renderApp("/app/hal");

      expect(await screen.findByRole("heading", { name: "HAL Command Center" })).toBeInTheDocument();
      fireEvent.change(screen.getByLabelText("What do you want HAL to help with?"), {
        target: {
          value: "Change brightness to 30% on the primary monitor.",
        },
      });
      fireEvent.click(screen.getByRole("button", { name: "Ask HAL" }));

      expect(await screen.findByText("Here's what I found")).toBeInTheDocument();
      expect(speak).not.toHaveBeenCalled();

      fireEvent.click(screen.getByRole("button", { name: "Read It Aloud" }));

      expect(cancel).toHaveBeenCalledTimes(1);
      expect(speak).toHaveBeenCalledTimes(1);
    } finally {
      if (originalWebdriver) {
        Object.defineProperty(window.navigator, "webdriver", originalWebdriver);
      } else {
        Reflect.deleteProperty(window.navigator, "webdriver");
      }
    }
  });

  it("shows the exact HAL error and lets the user retry", async () => {
    let attempts = 0;
    server.use(
      http.post("/api/hal9000", async () => {
        attempts += 1;
        if (attempts === 1) {
          return HttpResponse.json({ detail: "HAL request failed: RuntimeError: upstream timeout" }, { status: 503 });
        }
        return HttpResponse.json({
          mode: "local-rag-phase-1",
          answer: "I retried the request and the connection is back.",
          sanitized_question: "status",
          sanitization_findings: [],
          retrieved_context: [],
          guardrails: ["approved local read-only scope", "deterministic server facts first"],
          audit_id: "hal-retry-1",
          access_policy: {
            mode: "local-rag-phase-1",
            auth_requirement: "Per-user HTTP Basic credentials loaded from deployment configuration with HAL-specific roles are required.",
            network_boundary: "Local-only backend mediation; no direct browser-to-model access.",
            audited: true,
            allowed_sources: ["approved_local_read_only_scope"],
            disallowed_actions: ["direct_hardware_writes"],
          },
          voice_profile: {
            lane: "primary",
            label: "Primary response",
            tone: "direct and grounded",
            style_notes: [],
          },
          governance_notes: [],
          review_actions: [],
        });
      }),
    );

    renderApp("/app/hal");

    fireEvent.change(await screen.findByLabelText("What do you want HAL to help with?"), {
      target: { value: "status" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask HAL" }));

    expect(await screen.findByText("HAL request failed: RuntimeError: upstream timeout")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try Again" }));

    expect(await screen.findByText("Here's what I found")).toBeInTheDocument();
    expect(screen.getAllByText("I retried the request and the connection is back.").length).toBeGreaterThan(0);
    expect(attempts).toBe(2);
  });

  it("renders the claims workbench workflow", async () => {
    renderApp("/app/claims-workbench");

    expect(await screen.findByRole("heading", { name: "Patient Claims Workbench" })).toBeInTheDocument();
    expect(screen.getByText("Claims aggregate snapshot")).toBeInTheDocument();
    expect(
      await screen.findByText(
        /Approved SoftDent aggregate claim exports are now feeding true outstanding and unsubmitted claim exposure into this page/,
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("$12,401")).toBeInTheDocument();
    expect(screen.getByText("9")).toBeInTheDocument();
    expect(screen.getByText("$3,840")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText(/Top outstanding payers: Delta Dental \$7,100 · MetLife \$3,801/)).toBeInTheDocument();
    expect(screen.getByText(/Top unsubmitted payers: Delta Dental \$2,200 · Cigna \$1,640/)).toBeInTheDocument();
    expect(
      screen.getByText(/Coverage gaps still limit parts of this page: Unsubmitted Claims, Treatment Plans, Payment Plans/),
    ).toBeInTheDocument();
    expect(screen.getByText(/Page coverage gaps/)).toBeInTheDocument();
    expect(screen.getAllByText(/Claims export/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Clinical notes export/)).toBeInTheDocument();
    expect(await screen.findByText("high confidence")).toBeInTheDocument();
    expect(await screen.findByText("review suggested")).toBeInTheDocument();
    expect(await screen.findByText(/contains clinical-note source/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Lookup question"), {
      target: { value: "Patient John Doe MRN 778899 claim lookup." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Lookup patient dossier" }));
    expect(await screen.findByText(/Patient-specific SoftDent claim and\/or clinical-note context matched/)).toBeInTheDocument();
    expect(screen.getAllByText(/Response profile:/).length).toBeGreaterThan(0);

    fireEvent.change(screen.getByLabelText("Narrative request"), {
      target: {
        value: "Patient John Doe MRN 778899 needs an insurance narrative for the denied crown buildup claim.",
      },
    });
    fireEvent.click(screen.getByRole("button", { name: "Generate narrative" }));
    expect(await screen.findByText(/Narrative output/)).toBeInTheDocument();
    expect(screen.getByText(/Insurance narrative for John Doe/)).toBeInTheDocument();
    expect(screen.getAllByText(/Governance:/).length).toBeGreaterThan(0);
  });

  it("renders the journal draft workflow", async () => {
    const payload = await draftJournalEntry({
      description: "Record prepaid insurance for June coverage.",
      transaction_date: "2026-06-15",
      accounting_period: "2026-06",
      amount: 1200,
    });
    expect(payload.validation.balanced).toBe(true);

    renderApp("/app/journal-draft");

    expect(await screen.findByRole("heading", { name: "Journal draft review" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Transaction Description"), {
      target: { value: "Record prepaid insurance for June coverage." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Draft journal entry" }));

    expect(await screen.findByText("Drafted Journal Entry")).toBeInTheDocument();
    expect(screen.getByText(/Review required before posting/)).toBeInTheDocument();
    expect(screen.getAllByRole("cell", { name: "Prepaid Insurance" })).toHaveLength(1);
    expect(screen.getByText("Cash")).toBeInTheDocument();
    expect(screen.getAllByText("1200.00")).toHaveLength(4);
    expect(screen.getByText(/Balanced:/)).toBeInTheDocument();
    expect(screen.getByText(/No validation issues/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Queue for QuickBooks review" }));
    expect(await screen.findByText(/Queue status:/)).toBeInTheDocument();
    expect(screen.getByText(/pending review/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Transaction Description"), {
      target: { value: "Record June supplies accrual." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Draft journal entry" }));

    expect(await screen.findByText("Drafted Journal Entry")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText(/Queue status:/)).not.toBeInTheDocument());
  });

  it("can auto-enqueue a validated local AI draft from the journal draft workflow", async () => {
    renderApp("/app/journal-draft");

    expect(await screen.findByRole("heading", { name: "Journal draft review" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Transaction Description"), {
      target: {
        value: "Vendor invoice for dental supplies, $700 due next month.",
      },
    });
    fireEvent.change(screen.getByLabelText("Raw Source Text"), {
      target: {
        value: "Invoice 4881 from Dental Supply Co. Items: gloves, bibs, and trays. Total due 700 dollars next month.",
      },
    });
    fireEvent.click(screen.getByLabelText("Parse with local AI"));
    fireEvent.click(screen.getByLabelText("Auto-enqueue validated draft for human review"));
    fireEvent.click(screen.getByRole("button", { name: "Draft journal entry" }));

    expect(await screen.findByText(/Draft status:/)).toBeInTheDocument();
    expect(screen.getByText("qbd-queue-mock-001")).toBeInTheDocument();
    expect(screen.getByText(/already been auto-enqueued/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Queue for QuickBooks review" })).toBeDisabled();
  });

  it("blocks invalid journal amounts before submitting", async () => {
    renderApp("/app/journal-draft");

    expect(await screen.findByRole("heading", { name: "Journal draft review" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Transaction Description"), {
      target: { value: "Record prepaid insurance for June coverage." },
    });
    fireEvent.change(screen.getByLabelText("Amount"), {
      target: { value: "0" },
    });

    expect(screen.getByText("Enter a positive amount before drafting or queueing a journal entry.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Draft journal entry" })).toBeDisabled();
    expect(screen.queryByText("Drafted Journal Entry")).not.toBeInTheDocument();
  });

  it("renders the accounting policy workflow", async () => {
    const payload = await fetchAccountingPolicyAnswer({
      question: "How should prepaid insurance be treated at period end?",
      topic: "prepaids",
      accounting_standard: "GAAP",
    });
    expect(payload.citations).toHaveLength(2);

    renderApp("/app/accounting-policy");

    expect(
      await screen.findByRole("heading", {
        name: "Accounting policy guidance",
      }),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Policy Question"), {
      target: {
        value: "How should prepaid insurance be treated at period end?",
      },
    });
    fireEvent.click(screen.getByRole("button", { name: "Get policy guidance" }));

    expect(await screen.findByText("Draft Policy Guidance")).toBeInTheDocument();
    expect(screen.getByText(/draft guidance under GAAP/i)).toBeInTheDocument();
    expect(screen.getByText(/Response profile:/)).toBeInTheDocument();
    expect(screen.getByText(/Governance:/)).toBeInTheDocument();
    expect(screen.getByText(/Confidence:/)).toBeInTheDocument();
    expect(screen.getAllByText(/hal_phi_rag_architecture chunk 24/)).toHaveLength(1);
    expect(screen.getAllByText(/API chunk 1/)).toHaveLength(1);
  });

  it("renders the posting queue review workflow", async () => {
    const payload = await fetchAccountingPostingQueue({ limit: 10 });
    expect(payload.count).toBeGreaterThan(0);
    const expectedRangeText = new RegExp(`Showing 1-${payload.total_count} of ${payload.total_count}`);

    renderApp("/app/posting-queue");

    expect(await screen.findByRole("heading", { name: "Posting queue review" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "All" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Pending Review" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approved" })).toBeInTheDocument();
    const targetHeading = await screen.findByRole("heading", {
      name: "Queue prepaid insurance entry for QuickBooks Desktop review.",
    });
    const targetCard = targetHeading.closest(".hal-answer-card");
    expect(targetCard).not.toBeNull();
    expect(
      within(targetCard as HTMLElement).getByText(/Linked to an auto-validated AI draft in the accounting copilot flow/),
    ).toBeInTheDocument();
    fireEvent.change(within(targetCard as HTMLElement).getByLabelText("Review note"), {
      target: { value: "Approved after matching the June support package." },
    });
    fireEvent.click(
      within(targetCard as HTMLElement).getByRole("button", {
        name: "Approve draft",
      }),
    );

    expect(await screen.findByText("approved")).toBeInTheDocument();
    expect(screen.getAllByText(/Reviewed by:/)).toHaveLength(2);
    expect(screen.getByText(/Approved after matching the June support package/)).toBeInTheDocument();
    expect(await screen.findByText(expectedRangeText)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Rejected" }));
    expect(await screen.findByText(/No posting queue items are available for the selected filter/)).toBeInTheDocument();
    expect(await screen.findByText(/Showing 0-0 of 0/)).toBeInTheDocument();
  });
});
