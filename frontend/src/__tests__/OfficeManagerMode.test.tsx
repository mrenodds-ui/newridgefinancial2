import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AskHal9000Page from "../pages/AskHal9000Page";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    askHalQuestion: vi.fn(),
    createHalConversationId: vi.fn(() => "hal-test-session"),
    createOfficeManagerTask: vi.fn(),
    createSoftDentDraft: vi.fn(),
    createSoftDentLocalPacket: vi.fn(),
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
  createOfficeManagerTask,
  fetchFinancialSummary,
  fetchHalStatus,
  fetchOfficeManagerAttention,
  fetchOfficeManagerTaskMetrics,
  fetchOfficeManagerTasks,
} from "../api/client";
import { defaultHalVoiceProfile } from "../api/schemas";

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
    claimsSummary: {
      available: true,
      unsubmitted_claims_count: 2,
      unsubmitted_claims_amount: 1200,
      true_outstanding_claims_count: 1,
      true_outstanding_claims_amount: 800,
      top_unsubmitted_payers: [],
      top_outstanding_payers: [],
    },
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
  vi.mocked(fetchOfficeManagerAttention).mockResolvedValue({
    generated_at_utc: "2026-06-26T20:00:00Z",
    summary: "2 office-manager attention item(s) are visible.",
    safety_disclaimer: "Local only",
    items: [
      {
        item_id: "claims-unsubmitted",
        category: "claims_follow_up",
        severity: "info",
        title: "Unsubmitted claims need follow-up",
        detail: "2 unsubmitted claim(s) are visible.",
        action_hint: "Review claims follow-up.",
        source_key: "claimsSummary",
        missing_data_codes: [],
        count: 2,
        local_only: true,
        external_action_performed: false,
      },
      {
        item_id: "treatment-plan-unavailable",
        category: "treatment_plan",
        severity: "info",
        title: "Treatment plan follow-up is limited",
        detail: "No approved treatment-plan export source is available yet.",
        action_hint: "Use local tasks.",
        source_key: "treatment_plan",
        missing_data_codes: ["missing_treatment_plan_export"],
        local_only: true,
        external_action_performed: false,
      },
    ],
    missing_data_codes: ["missing_treatment_plan_export"],
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
  vi.mocked(createOfficeManagerTask).mockResolvedValue({
    task_id: "omt-test",
    title: "Review denial packet",
    description: "",
    category: "claim",
    status: "open",
    priority: "normal",
    source_refs: [],
    missing_data_codes: [],
    created_by: "admin",
    created_at_utc: "2026-06-26T20:00:00Z",
    updated_at_utc: "2026-06-26T20:00:00Z",
    local_only: true,
    external_action_performed: false,
    softdent_writeback_performed: false,
  });
  vi.mocked(askHalQuestion).mockResolvedValue({
    mode: "local-rag-phase-1",
    answer: "Office manager answer.",
    sanitized_question: "What should staff focus on today?",
    sanitization_findings: [],
    retrieved_context: [],
    guardrails: [],
    audit_id: "hal-test",
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
  } as unknown as Awaited<ReturnType<typeof askHalQuestion>>);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("Office Manager Mode", () => {
  it("renders data-driven Today attention and missing-data notices", async () => {
    renderPage();
    expect(await screen.findByText(/Unsubmitted claims need follow-up/i)).toBeInTheDocument();
    expect(screen.getByText(/Treatment plan follow-up is limited/i)).toBeInTheDocument();
    expect(screen.getAllByText(/missing_treatment_plan_export/i).length).toBeGreaterThan(0);
  });

  it("creates a local office task without forbidden controls", async () => {
    renderPage();
    fireEvent.change(screen.getByLabelText(/Task title/i), { target: { value: "Review denial packet" } });
    fireEvent.click(screen.getByRole("button", { name: /Create local task/i }));
    await waitFor(() => expect(createOfficeManagerTask).toHaveBeenCalled());
    expect(
      screen.queryByRole("button", { name: /submit|send|fax|upload|gateway|write to softdent|mark submitted/i }),
    ).toBeNull();
  });

  it("shows claims follow-up and patient prep sections", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { name: /Unpaid, aging, and denied claim review/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Patient \/ claim summary/i })).toBeInTheDocument();
    expect(screen.getAllByText(/Local only/i).length).toBeGreaterThan(0);
  });
});
