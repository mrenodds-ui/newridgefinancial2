import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
    fetchClaimPacketReadiness: vi.fn(),
    fetchHalPatientDossier: vi.fn(),
    fetchHalStatus: vi.fn(),
    fetchOfficeManagerAttention: vi.fn(),
    fetchOfficeManagerTaskMetrics: vi.fn(),
    fetchOfficeManagerTasks: vi.fn(),
    fetchSoftDentEndOfDayAr: vi.fn(),
    updateOfficeManagerTask: vi.fn(),
  };
});

import {
  askHalQuestion,
  fetchFinancialSummary,
  fetchClaimPacketReadiness,
  fetchHalStatus,
  fetchOfficeManagerAttention,
  fetchOfficeManagerTaskMetrics,
  fetchOfficeManagerTasks,
  fetchSoftDentEndOfDayAr,
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
    claimsSummary: { available: false },
  } as unknown as Awaited<ReturnType<typeof fetchFinancialSummary>>);
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
  vi.mocked(fetchClaimPacketReadiness).mockResolvedValue({
    generated_at_utc: "2026-06-27T14:00:00Z",
    summary: {
      ready_count: 1,
      needs_review_count: 2,
      blocked_count: 3,
      total_count: 6,
    },
    items: [
      {
        packet_id: "packet-blocked-1",
        claim_ref: "CLAIM-1001",
        status: "blocked",
        priority: "high",
        blockers: ["Clinical note missing"],
        missing_items: ["Clinical note missing"],
        available_items: [],
        recommended_next_actions: ["Review packet facts before any operational use."],
        can_prepare_local_draft: false,
        local_draft_status: "needs_facts",
        safety: {
          local_only: true,
          not_submitted: true,
          human_review_required: true,
          external_delivery_allowed: false,
          softdent_writeback_allowed: false,
          payer_contact_allowed: false,
        },
        source_basis: ["SoftDent claims export"],
        staff_summary: "Blocked: Clinical note missing.",
        procedure_refs: [],
      },
    ],
    safety_disclaimer: "Local only",
    safety: {
      local_only: true,
      not_submitted: true,
      human_review_required: true,
      external_delivery_allowed: false,
      softdent_writeback_allowed: false,
      payer_contact_allowed: false,
    },
    local_only: true,
    submission_status: "not_submitted",
  });
  vi.mocked(fetchSoftDentEndOfDayAr).mockResolvedValue({
    available: false,
    report_date: null,
    generated_at: null,
    source_file: "",
    source_modified_at_utc: "",
    freshness_status: "unknown",
    parse_status: "missing",
    total_ar: null,
    patient_ar: null,
    insurance_ar: null,
    aging_buckets: {},
    credits: null,
    collection_total: null,
    production_total: null,
    office_scope: null,
    provider_scope: null,
    source_refs: [],
    missing_data_codes: ["missing_softdent_ar"],
    limitations: ["Daily End-of-Day report A/R is unavailable."],
    stale_reason: null,
    page_number: null,
    page_count: null,
    source_label: "Daily End-of-Day report A/R",
  });
  vi.mocked(askHalQuestion).mockResolvedValue({
    mode: "local-rag-phase-1",
    answer: "Office manager answer for staff.",
    sanitized_question: "What should staff focus on today?",
    sanitization_findings: [],
    retrieved_context: [],
    guardrails: ["approved local read-only scope", "audit log recorded"],
    audit_id: "hal-ref-12345",
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

describe("HAL Command Center page", () => {
  it("shows Ask HAL, Today's Mission, Automation Center, and Work Queue sections", async () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "HAL Command Center" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ask HAL" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Today's Mission" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Automation Center" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Work Queue" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Office work" })).toBeInTheDocument();
  });

  it("renders Automation Center tiles with safe labels", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Prepare Patient Call" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Review Claims" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Claim Packet Readiness" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Daily A/R Check" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Morning Huddle" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Missing Documents" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Create Office Task" })).toBeInTheDocument();
  });

  it("renders scan-friendly initial badges on Automation Center tiles", () => {
    renderPage();
    const automation = screen.getByRole("heading", { name: "Automation Center" }).closest("section");
    expect(automation).not.toBeNull();
    const within_ = within(automation as HTMLElement);
    for (const badge of ["PC", "CL", "CP", "AR", "MH", "MD", "TK"]) {
      expect(within_.getByText(badge)).toBeInTheDocument();
    }
  });

  it("renders the Work Queue after the Automation Center", () => {
    renderPage();
    const automation = screen.getByRole("heading", { name: "Automation Center" });
    const workQueue = screen.getByRole("heading", { name: "Work Queue" });
    const position = automation.compareDocumentPosition(workQueue);
    expect(position & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("uses staff-facing Office Work labels", () => {
    renderPage();
    expect(screen.getByText("Patient Prep")).toBeInTheDocument();
    expect(screen.getByText("Claim Follow-Up")).toBeInTheDocument();
    expect(screen.getByText("Drafts for Review")).toBeInTheDocument();
    expect(screen.getByText("Local Tasks")).toBeInTheDocument();
    expect(screen.getByText("Vendor Issues")).toBeInTheDocument();
  });

  it("renders Work Queue buckets including blocked items in plain English", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Needs Review" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Ready" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Blocked" })).toBeInTheDocument();
    expect(screen.getByText(/Claims follow-up needs claims export/i)).toBeInTheDocument();
    expect(screen.getByText(/A\/R needs DAYSHEET import/i)).toBeInTheDocument();
  });

  it("renders the four suggested prompt chips", () => {
    renderPage();
    expect(screen.getByRole("button", { name: "What needs attention today?" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Prepare morning huddle" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review claims needing follow-up" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check today's A/R" })).toBeInTheDocument();
  });

  it("keeps exactly one Ask HAL button", () => {
    renderPage();
    expect(screen.getAllByRole("button", { name: "Ask HAL" })).toHaveLength(1);
  });

  it("collapses Advanced details by default", () => {
    renderPage();
    const summary = screen.getByText("Advanced details");
    const details = summary.closest("details");
    expect(details).not.toBeNull();
    expect(details).not.toHaveAttribute("open");
  });

  it("keeps the office-manager attention list collapsed by default", () => {
    renderPage();
    const summary = screen.getByText("Priorities to Review");
    const details = summary.closest("details");
    expect(details).not.toBeNull();
    expect(details).not.toHaveAttribute("open");
  });

  it("places Automation Center directly after Today's Mission in the main flow", async () => {
    renderPage();
    const mission = await screen.findByRole("heading", { name: "Today's Mission" });
    const automation = screen.getByRole("heading", { name: "Automation Center" });
    const position = mission.compareDocumentPosition(automation);
    expect(position & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("shows staff-friendly missing labels in Today cards and never $0", async () => {
    renderPage();
    const todayHeading = await screen.findByRole("heading", { name: "Today's Mission" });
    const todaySection = todayHeading.closest("section");
    expect(todaySection).not.toBeNull();
    const today = within(todaySection as HTMLElement);
    expect(today.getByText(/DAYSHEET not imported yet/i)).toBeInTheDocument();
    expect(today.getByText(/Claims export not imported yet/i)).toBeInTheDocument();
    expect(today.queryByText(/missing_softdent_ar/i)).toBeNull();
    expect(today.queryByText("$0")).toBeNull();
    expect(today.queryByText("$0.00")).toBeNull();
  });

  it("does not render submit/send/fax/upload/gateway/writeback controls", async () => {
    renderPage();
    await screen.findByRole("heading", { name: "Today's Mission" });
    expect(
      screen.queryByRole("button", {
        name: /submit|send|fax|upload|gateway|write to softdent|mark submitted/i,
      }),
    ).toBeNull();
  });

  it("sends on Enter and inserts newline on Shift+Enter", async () => {
    renderPage();
    const textarea = screen.getByLabelText(/What do you want HAL to help with/i);

    fireEvent.change(textarea, { target: { value: "Review patient claim" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: true });
    expect(askHalQuestion).not.toHaveBeenCalled();
    expect(textarea).toHaveValue("Review patient claim\n");

    fireEvent.keyDown(textarea, { key: "Enter" });
    await waitFor(() => expect(askHalQuestion).toHaveBeenCalledTimes(1));
  });

  it("shows exactly one concise global safety footer", () => {
    renderPage();
    const footer = screen.getByText(/HAL is local-only and read-only\. Drafts require human review\./i);
    expect(footer).toBeInTheDocument();
    expect(footer).toHaveClass("hal-safety-footer");
  });

  it("tucks voice / read-aloud controls into a collapsed Accessibility section after an answer", async () => {
    renderPage();
    fireEvent.change(screen.getByLabelText(/What do you want HAL to help with/i), {
      target: { value: "What should staff focus on today?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask HAL" }));
    await waitFor(() => expect(askHalQuestion).toHaveBeenCalled());

    const summary = await screen.findByText(/Accessibility \(read aloud\)/i);
    const details = summary.closest("details");
    expect(details).not.toBeNull();
    expect(details).not.toHaveAttribute("open");
    expect(within(details as HTMLElement).getByRole("button", { name: "Read It Aloud" })).toBeInTheDocument();
  });

  it("expands Advanced details to reveal reference ID and safeguards after an answer", async () => {
    renderPage();
    fireEvent.change(screen.getByLabelText(/What do you want HAL to help with/i), {
      target: { value: "What should staff focus on today?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask HAL" }));
    await waitFor(() => expect(askHalQuestion).toHaveBeenCalled());

    expect(screen.queryByText(/Internal lane:/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Model used:/i)).not.toBeInTheDocument();

    const summary = screen.getByText("Advanced details");
    fireEvent.click(summary);

    expect(await screen.findByText(/hal-ref-12345/)).toBeInTheDocument();
    expect(screen.getByText(/Built-in safeguards:/i)).toBeInTheDocument();
  });

  it("renders Claim Packet Readiness counts and plain-English missing items when expanded", async () => {
    renderPage();
    const officeWork = screen.getByRole("heading", { name: "Office work" }).closest("section");
    expect(officeWork).not.toBeNull();
    const panelSummary = within(officeWork as HTMLElement).getByText("Claim Packet Readiness");
    fireEvent.click(panelSummary);
    const panel = await within(officeWork as HTMLElement).findByLabelText("Claim packet readiness counts");
    expect(within(panel).getByText("Ready")).toBeInTheDocument();
    expect(within(panel).getByText("Needs Review")).toBeInTheDocument();
    expect(within(panel).getByText("Blocked")).toBeInTheDocument();
    expect(within(officeWork as HTMLElement).getByText(/Blocked: Clinical note missing\./i)).toBeInTheDocument();
    expect(within(officeWork as HTMLElement).queryByText(/missing_clinical_note/i)).toBeNull();
    expect(within(officeWork as HTMLElement).getByRole("button", { name: "Review packet" })).toBeInTheDocument();
    expect(within(officeWork as HTMLElement).getByRole("button", { name: "View missing items" })).toBeInTheDocument();
    expect(within(officeWork as HTMLElement).getByRole("button", { name: "Prepare local draft" })).toBeDisabled();
  });
});
