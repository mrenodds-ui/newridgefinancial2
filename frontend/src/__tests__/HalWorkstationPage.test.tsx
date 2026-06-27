import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AskHal9000Page from "../pages/AskHal9000Page";
import { defaultHalVoiceProfile } from "../api/schemas";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    askHalQuestion: vi.fn(),
    createHalConversationId: vi.fn(() => "hal-test-session"),
    createSoftDentDraft: vi.fn(),
    createSoftDentLocalPacket: vi.fn(),
    createOfficeManagerTask: vi.fn(),
    executeMonitorReviewAction: vi.fn(),
    fetchFinancialSummary: vi.fn(),
    fetchHalPatientDossier: vi.fn(),
    fetchHalStatus: vi.fn(),
    fetchOfficeManagerAttention: vi.fn(),
    fetchOfficeManagerTaskMetrics: vi.fn(),
    fetchOfficeManagerTasks: vi.fn(),
    updateOfficeManagerTask: vi.fn(),
  };
});

import {
  askHalQuestion,
  createSoftDentDraft,
  createSoftDentLocalPacket,
  fetchFinancialSummary,
  fetchHalStatus,
  fetchOfficeManagerAttention,
  fetchOfficeManagerTaskMetrics,
  fetchOfficeManagerTasks,
} from "../api/client";

function buildHalResponse(overrides: Record<string, unknown> = {}): Awaited<ReturnType<typeof askHalQuestion>> {
  return {
    mode: "local-rag-phase-1",
    answer:
      "Practical answer for staff. Verified SoftDent context supports the recommendation. Prepare a draft for human review.",
    sanitized_question: "Patient John Doe claim review",
    sanitization_findings: [],
    retrieved_context: [],
    guardrails: ["approved local read-only scope"],
    audit_id: "hal-test-audit",
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
  } as unknown as Awaited<ReturnType<typeof askHalQuestion>>;
}

function buildDraft() {
  return {
    draft_id: "sdd-ui-test",
    draft_type: "insurance_narrative_proposal" as const,
    patient_label: "John Doe",
    title: "Insurance narrative proposal for John Doe",
    body: "Draft only. Requires human review. Not submitted. Not written to SoftDent. No email, fax, upload, or Gateway action was performed.",
    checklist_items: ["Review payer facts."],
    source_fact_refs: ["claim:CLM-1001"],
    missing_data_codes: ["missing_softdent_ar"],
    limitations: ["Patient A/R is unavailable; do not state $0."],
    review_required: true,
    external_action_performed: false,
  };
}

function buildPacket() {
  return {
    packet_id: "sdp-ui-test",
    source_draft_id: "sdd-ui-test",
    packet_type: "approved_narrative_packet" as const,
    patient_label: "John Doe",
    title: "Approved narrative packet for John Doe",
    body: "Local only. Approved for internal office use. Not submitted. Not written to SoftDent. No email, fax, upload, or Gateway/E-Services action was performed.",
    checklist_items: ["Review payer facts."],
    source_fact_refs: ["claim:CLM-1001"],
    missing_data_codes: ["missing_softdent_ar"],
    limitations: ["Local only."],
    approval_attestation: {
      approved_by: "Billing Lead",
      approval_note: "Reviewed for internal use only.",
      reviewed_at_utc: "2026-06-26T18:00:00Z",
      attestation_checked: true,
      acknowledged_local_only: true,
      acknowledged_not_submitted: true,
      acknowledged_no_softdent_writeback: true,
      acknowledged_no_external_delivery: true,
    },
    submission_status: "not_submitted" as const,
    external_action_performed: false,
    softdent_writeback_performed: false,
    local_only: true,
  };
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <AskHal9000Page />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.mocked(fetchFinancialSummary).mockResolvedValue({
    latestAr: null,
    monthlyKpis: [],
    trailing12Months: [],
    calendarYearKpis: [],
    fourYearMonthlyKpis: [],
    providerProduction: [],
    topAdaCodes: [],
  } as Awaited<ReturnType<typeof fetchFinancialSummary>>);
  vi.mocked(fetchHalStatus).mockResolvedValue({
    mode: "local-rag-phase-1",
    backend: "chroma",
    document_count: 0,
    storage_path: "",
    vector_path: "",
    embedding_provider: "onnx",
    financial_sources: {},
    operating_picture: {},
  } as unknown as Awaited<ReturnType<typeof fetchHalStatus>>);
  vi.mocked(askHalQuestion).mockResolvedValue(buildHalResponse());
  vi.mocked(createSoftDentDraft).mockResolvedValue(buildDraft());
  vi.mocked(createSoftDentLocalPacket).mockResolvedValue(buildPacket());
  vi.mocked(fetchOfficeManagerAttention).mockResolvedValue({
    generated_at_utc: "2026-06-26T20:00:00Z",
    summary: "Attention summary",
    safety_disclaimer: "Local only",
    items: [],
    missing_data_codes: [],
    local_only: true,
    external_action_performed: false,
    softdent_writeback_performed: false,
    submission_status: "not_submitted",
  });
  vi.mocked(fetchOfficeManagerTasks).mockResolvedValue({
    items: [],
    total_count: 0,
    local_only: true,
    external_action_performed: false,
    softdent_writeback_performed: false,
    submission_status: "not_submitted",
  });
  vi.mocked(fetchOfficeManagerTaskMetrics).mockResolvedValue({
    open_count: 0,
    in_progress_count: 0,
    blocked_count: 0,
    completed_count: 0,
    dismissed_count: 0,
    urgent_open_count: 0,
    local_only: true,
    external_action_performed: false,
    softdent_writeback_performed: false,
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("HAL workstation page", () => {
  it("keeps Ask HAL disabled under 3 characters and asks normally", async () => {
    renderPage();
    const askButton = screen.getByRole("button", { name: /Ask HAL/i });
    expect(askButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/What do you want HAL to help with/i), { target: { value: "hi" } });
    expect(askButton).toBeDisabled();
    expect(screen.getByText(/Ask at least 3 characters/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/What do you want HAL to help with/i), {
      target: { value: "Review patient claim" },
    });
    fireEvent.click(askButton);

    await waitFor(() => expect(askHalQuestion).toHaveBeenCalled());
    expect(askHalQuestion).toHaveBeenCalledWith(
      "Review patient claim",
      expect.objectContaining({ conversationId: "hal-test-session" }),
    );
  });

  it("sends on Enter and inserts a newline on Shift+Enter", async () => {
    renderPage();
    const textarea = screen.getByLabelText(/What do you want HAL to help with/i);

    fireEvent.change(textarea, { target: { value: "Review patient claim" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: true });
    expect(askHalQuestion).not.toHaveBeenCalled();
    expect(textarea).toHaveValue("Review patient claim\n");

    fireEvent.keyDown(textarea, { key: "Enter" });
    await waitFor(() => expect(askHalQuestion).toHaveBeenCalledTimes(1));
    expect(askHalQuestion).toHaveBeenCalledWith(
      "Review patient claim",
      expect.objectContaining({ conversationId: "hal-test-session" }),
    );
  });

  it("does not send blank input or double-submit while pending", async () => {
    let resolveRequest: (() => void) | undefined;
    vi.mocked(askHalQuestion).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveRequest = () =>
            resolve(
              buildHalResponse({
                answer: "Pending answer",
              }),
            );
        }),
    );

    renderPage();
    const textarea = screen.getByLabelText(/What do you want HAL to help with/i);
    fireEvent.keyDown(textarea, { key: "Enter" });
    expect(askHalQuestion).not.toHaveBeenCalled();

    fireEvent.change(textarea, { target: { value: "Review patient claim" } });
    fireEvent.click(screen.getByRole("button", { name: /Ask HAL/i }));
    await waitFor(() => expect(askHalQuestion).toHaveBeenCalledTimes(1));
    fireEvent.keyDown(textarea, { key: "Enter" });
    expect(askHalQuestion).toHaveBeenCalledTimes(1);

    resolveRequest?.();
    await waitFor(() => expect(screen.getByText(/Here's what I found/i)).toBeInTheDocument());
  });

  it("renders friendly source labels instead of raw README chunk IDs", async () => {
    vi.mocked(askHalQuestion).mockResolvedValue(
      buildHalResponse({
        retrieved_context: [
          {
            source_id: "readme-chunk-68",
            title: "README chunk 68",
            category: "documentation",
            excerpt: "Approved local guidance only.",
          },
        ],
      }),
    );
    renderPage();
    fireEvent.change(screen.getByLabelText(/What do you want HAL to help with/i), {
      target: { value: "What sources did you use?" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Ask HAL/i }));

    expect(await screen.findByText("README guidance")).toBeInTheDocument();
    expect(screen.queryByText("README chunk 68")).toBeNull();
  });

  it("does not render raw README chunk IDs for generic help responses", async () => {
    vi.mocked(askHalQuestion).mockResolvedValue(
      buildHalResponse({
        mode: "local-rag-phase-1:generic-help",
        answer:
          "Yes. I can help with local office tasks, claim follow-up drafts, patient prep summaries, report checklists, SoftDent export review, and internal office-manager summaries. I stay local and read-only.",
        retrieved_context: [],
      }),
    );
    renderPage();
    fireEvent.change(screen.getByLabelText(/What do you want HAL to help with/i), {
      target: { value: "can you help me" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Ask HAL/i }));

    expect(await screen.findByText(/Yes\. I can help with local office tasks/i)).toBeInTheDocument();
    expect(screen.queryByText(/README chunk/i)).toBeNull();
    expect(screen.queryByText(/Relevant context/i)).toBeNull();
    expect(screen.queryByLabelText(/Use deeper second opinion/i)).toBeNull();
  });

  it("creates draft and local packet artifacts with required safety wording", async () => {
    renderPage();
    fireEvent.change(screen.getAllByLabelText(/Patient \/ claim question/i)[0], {
      target: { value: "Patient John Doe denied crown claim" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Create review draft/i }));

    await waitFor(() => expect(createSoftDentDraft).toHaveBeenCalled());
    await waitFor(() => expect(screen.getAllByText(/Draft only/i).length).toBeGreaterThan(0));
    expect(screen.getAllByText(/Requires human review/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Not written to SoftDent/i).length).toBeGreaterThan(0);

    expect(screen.getByRole("button", { name: /Create local packet/i })).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Approved by/i), { target: { value: "Billing Lead" } });
    fireEvent.change(screen.getByLabelText(/Approval note/i), {
      target: { value: "Reviewed for internal office use only." },
    });
    fireEvent.click(screen.getByLabelText(/reviewed the draft/i));
    fireEvent.click(screen.getByLabelText(/^Local only/i));
    fireEvent.click(screen.getByLabelText(/not_submitted/i));
    fireEvent.click(screen.getByLabelText(/Not written to SoftDent/i));
    fireEvent.click(screen.getByLabelText(/No external delivery/i));
    fireEvent.click(screen.getByRole("button", { name: /Create local packet/i }));

    await waitFor(() => expect(createSoftDentLocalPacket).toHaveBeenCalled());
    expect(await screen.findByText(/Submission status/i)).toBeInTheDocument();
    expect(screen.getAllByText(/not_submitted/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/External action/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText("false").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/SoftDent writeback/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Local only/i).length).toBeGreaterThan(0);
  });

  it("does not render forbidden external delivery controls", () => {
    renderPage();
    expect(screen.queryByRole("button", { name: /submit|send|fax|upload|gateway|write to softdent|mark submitted/i })).toBeNull();
  });

  it("hides raw CSV-like source excerpts", async () => {
    vi.mocked(askHalQuestion).mockResolvedValue(
      buildHalResponse({
        retrieved_context: [
          {
            source_id: "raw-csv",
            title: "SoftDent claims",
            category: "softdent_tool",
            excerpt: "PatientName,MRN,ClaimId,Payer\nJohn Doe,778899,CLM-1001,Delta",
          },
        ],
      }),
    );
    renderPage();
    fireEvent.change(screen.getByLabelText(/What do you want HAL to help with/i), { target: { value: "Review claim" } });
    fireEvent.click(screen.getByRole("button", { name: /Ask HAL/i }));

    expect(await screen.findByText(/Raw CSV-like content was hidden/i)).toBeInTheDocument();
    expect(screen.queryByText(/PatientName,MRN,ClaimId/)).toBeNull();
  });
});
