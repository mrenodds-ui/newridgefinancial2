import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
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
  fetchClaimPacketReadiness,
  fetchFinancialSummary,
  fetchHalStatus,
  fetchOfficeManagerAttention,
  fetchOfficeManagerTaskMetrics,
  fetchOfficeManagerTasks,
  fetchSoftDentEndOfDayAr,
} from "../api/client";

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <AskHal9000Page />
    </QueryClientProvider>,
  );
}

function getControlTower(): HTMLElement {
  const heading = screen.getByRole("heading", { name: "Local Claim Intelligence Control Tower" });
  const section = heading.closest("section");
  expect(section).not.toBeNull();
  return section as HTMLElement;
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
    items: [],
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
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("HAL Control Tower command center view", () => {
  it("renders the Control Tower section with local safety badges", () => {
    renderPage();
    const tower = getControlTower();
    const scoped = within(tower);
    expect(scoped.getByText("Local-Only")).toBeInTheDocument();
    expect(scoped.getByText("Read-Only Sources")).toBeInTheDocument();
    expect(scoped.getByText("Human Review Required")).toBeInTheDocument();
    expect(scoped.getByText("Not Submitted")).toBeInTheDocument();
  });

  it("renders read-only source intake cards and staff work surfaces", () => {
    renderPage();
    const scoped = within(getControlTower());
    expect(scoped.getByText("Read-only source intake")).toBeInTheDocument();
    expect(scoped.getByText("SoftDent DAYSHEET A/R")).toBeInTheDocument();
    expect(scoped.getByText("SoftDent claims export")).toBeInTheDocument();
    expect(scoped.getByText("Staff work surfaces")).toBeInTheDocument();
    expect(scoped.getByText("Claim packet review surface")).toBeInTheDocument();
  });

  it("renders the central HAL reasoning core and readiness lanes from the summary", async () => {
    renderPage();
    const scoped = within(getControlTower());
    expect(scoped.getByText(/HAL local reasoning/i)).toBeInTheDocument();
    expect(scoped.getByText("Ready lane")).toBeInTheDocument();
    expect(scoped.getByText("Needs-review lane")).toBeInTheDocument();
    expect(scoped.getByText("Blocked lane")).toBeInTheDocument();
    await waitFor(() => {
      const lanes = within(getControlTower()).getByLabelText("Claim packet readiness lanes");
      const readyLane = within(lanes).getByText("Ready lane").closest("div") as HTMLElement;
      expect(within(readyLane).getByText("1")).toBeInTheDocument();
    });
  });

  it("renders the claim packet readiness counts (total) in the core", async () => {
    renderPage();
    await waitFor(() => {
      const core = within(getControlTower()).getByLabelText("HAL local reasoning core");
      expect(within(core).getByText("6")).toBeInTheDocument();
    });
  });

  it("renders the external action firewall labels as prohibited indicators, not controls", () => {
    renderPage();
    const firewall = within(getControlTower()).getByLabelText("External action firewall");
    for (const label of [
      "No Email",
      "No Fax",
      "No Upload",
      "No Payer Contact",
      "No SoftDent Writeback",
      "No Cloud Fallback",
      "No 235B",
    ]) {
      const chip = within(firewall).getByText(label);
      expect(chip).toBeInTheDocument();
      expect(chip.tagName).not.toBe("BUTTON");
      expect(chip).toHaveAttribute("aria-disabled", "true");
    }
  });

  it("keeps exactly one Ask HAL button", () => {
    renderPage();
    expect(screen.getAllByRole("button", { name: "Ask HAL" })).toHaveLength(1);
  });

  it("does not introduce a second-opinion UI", () => {
    renderPage();
    expect(screen.queryByLabelText(/second opinion/i)).toBeNull();
    expect(screen.queryByText(/second opinion/i)).toBeNull();
  });

  it("does not render any unsafe external action controls in the Control Tower", () => {
    renderPage();
    const scoped = within(getControlTower());
    expect(
      scoped.queryByRole("button", {
        name: /submit|send|fax|upload|gateway|write to softdent|mark submitted|payer|email|cloud|235b/i,
      }),
    ).toBeNull();
    expect(scoped.queryAllByRole("button")).toHaveLength(0);
  });
});
