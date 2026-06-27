import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "../App";
import {
  approveAndExportInsuranceNarrativeWorkflow,
  createInsuranceNarrativeDraftWorkflow,
  type InsuranceNarrativeWorkflowResult,
} from "../api/client";
import { clearApiBasicAuthCredentials, setApiAuthenticatedUsername } from "../api/basicAuth";
import { DashboardDataProvider } from "../context/DashboardDataContext";
import InsuranceNarrativesPage from "../pages/InsuranceNarrativesPage";
import { server } from "../mocks/server";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    createInsuranceNarrativeDraftWorkflow: vi.fn(),
    approveAndExportInsuranceNarrativeWorkflow: vi.fn(),
  };
});

function buildBlockedDraftResult(): InsuranceNarrativeWorkflowResult {
  return {
    packet: {
      packet_id: "narrative-packet-blocked",
      created_at: "2026-06-26T10:00:00+00:00",
      actor: "local-operator",
      narrative_type: "appeal",
      patient: { patient_ref: "CHART-A", label: "Patient ref CHART-A" },
      claim: { claim_id: "CLAIM-1001" },
      procedures: [],
      source_facts: [],
      missing_data: [
        {
          code: "missing_softdent_ar",
          label: "SoftDent accounts receivable export",
          severity: "warning",
          why_it_matters: "A/R unavailable",
          blocking: false,
        },
        {
          code: "missing_scoped_claim_row",
          label: "Scoped claim row",
          severity: "critical",
          why_it_matters: "No matching claim export row",
          blocking: true,
        },
      ],
      audit_metadata: { created_at: "2026-06-26T10:00:00+00:00", created_by: "local-operator" },
    },
    draft: {
      draft_id: "narrative-draft-blocked",
      packet_id: "narrative-packet-blocked",
      narrative_type: "appeal",
      status: "blocked_missing_data",
      sections: [],
      citations: [],
      warnings: [],
      missing_data: [],
      created_at: "2026-06-26T10:00:00+00:00",
      actor: "local-operator",
      audit_metadata: { created_at: "2026-06-26T10:00:00+00:00", created_by: "local-operator" },
    },
    status: "blocked_missing_data",
    warnings: [],
    audit_events: [],
  };
}

function buildHappyDraftResult(): InsuranceNarrativeWorkflowResult {
  return {
    packet: {
      packet_id: "narrative-packet-happy",
      created_at: "2026-06-26T10:00:00+00:00",
      actor: "local-operator",
      narrative_type: "appeal",
      patient: { patient_ref: "CHART-EXPORT", label: "Patient ref CHART-EXPORT" },
      claim: { claim_id: "CLAIM-EXPORT-1", status: "Denied", payer_name: "Delta Dental" },
      procedures: [
        {
          procedure_id: "PROC-CROWN-30",
          description: "Crown buildup tooth 30",
          code: "D2950",
          service_date: "2026-06-12",
        },
      ],
      source_facts: [
        {
          fact_id: "fact-CLAIM-EXPORT-1-claim-status-export",
          source_type: "claim",
          source_label: "softdent_claim_status_export.csv",
          text: "Claim denied.",
          supports: ["claim_status"],
        },
        {
          fact_id: "fact-NOTE-1001-clinical-note",
          source_type: "clinical_note",
          source_label: "softdent_clinical_notes_export.csv",
          text: 'Clinical note documents buildup.',
          supports: ["clinical_note"],
        },
      ],
      missing_data: [
        {
          code: "missing_softdent_ar",
          label: "SoftDent accounts receivable export",
          severity: "warning",
          why_it_matters: "A/R unavailable",
          blocking: false,
        },
      ],
      audit_metadata: {
        created_at: "2026-06-26T10:00:00+00:00",
        created_by: "local-operator",
        adapter_name: "softdent_export_file",
        source_mode: "export_file",
      },
    },
    draft: {
      draft_id: "narrative-draft-happy",
      packet_id: "narrative-packet-happy",
      narrative_type: "appeal",
      status: "ready_for_human_review",
      sections: [{ key: "purpose", title: "Purpose", body: "Draft body" }],
      citations: [
        {
          fact_id: "fact-CLAIM-EXPORT-1-claim-status-export",
          section_key: "supporting_facts",
          excerpt: "Claim denied.",
        },
      ],
      warnings: [],
      missing_data: [],
      created_at: "2026-06-26T10:00:00+00:00",
      actor: "local-operator",
      approval_required: true,
      audit_metadata: { created_at: "2026-06-26T10:00:00+00:00", created_by: "local-operator" },
    },
    status: "draft_created",
    warnings: [],
    audit_events: [],
  };
}

function buildExportResult(): InsuranceNarrativeWorkflowResult {
  const draftResult = buildHappyDraftResult();
  return {
    ...draftResult,
    review: {
      review_id: "narrative-review-1",
      packet_id: draftResult.packet.packet_id,
      draft_id: draftResult.draft.draft_id,
      draft_status: "ready_for_human_review",
      status: "approved",
      reviewer: "local-reviewer",
      reviewed_at: "2026-06-26T10:01:00+00:00",
      notes: "Reviewed for local export.",
      approval_attestation: true,
    },
    export: {
      export_id: "narrative-export-1",
      packet_id: draftResult.packet.packet_id,
      draft_id: draftResult.draft.draft_id,
      review_id: "narrative-review-1",
      format: "markdown",
      title: "Insurance Narrative Export — appeal",
      body: '# Export\n\n[fact-CLAIM-EXPORT-1-claim-status-export]\n\n## Submission Status\nNot submitted',
      citations: draftResult.draft.citations,
      missing_data_disclosures: draftResult.packet.missing_data,
      submission_status: "not_submitted",
      created_at: "2026-06-26T10:01:00+00:00",
      actor: "local-operator",
    },
    status: "export_created",
  };
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/insurance-narratives"]}>
        <Routes>
          <Route path="/insurance-narratives" element={<InsuranceNarrativesPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function renderAppAsOperator() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <DashboardDataProvider>
        <MemoryRouter basename="/app" initialEntries={["/app/insurance-narratives"]}>
          <App />
        </MemoryRouter>
      </DashboardDataProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  clearApiBasicAuthCredentials();
  vi.clearAllMocks();
});

describe("InsuranceNarrativesPage", () => {
  it("renders adapter selector defaulting to fixture and no export-dir input", () => {
    renderPage();

    const adapterSelect = screen.getByLabelText("Data source");
    expect(adapterSelect).toHaveValue("fixture");
    expect(screen.getByDisplayValue("CHART-A")).toBeInTheDocument();
    expect(screen.queryByLabelText(/export dir/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/export directory/i)).not.toBeInTheDocument();
  });

  it("defaults run_checker to false and posts fixture adapter_mode", async () => {
    vi.mocked(createInsuranceNarrativeDraftWorkflow).mockResolvedValue(buildHappyDraftResult());

    renderPage();

    const checker = screen.getByRole("checkbox", { name: /run fast_review checker/i });
    expect(checker).not.toBeChecked();

    fireEvent.click(screen.getByRole("button", { name: "Create draft" }));

    await waitFor(() => expect(createInsuranceNarrativeDraftWorkflow).toHaveBeenCalled());
    expect(vi.mocked(createInsuranceNarrativeDraftWorkflow).mock.calls[0]?.[0]).toMatchObject({
      patient_ref: "CHART-A",
      claim_id: "CLAIM-1001",
      procedure_ids: ["PROC-CROWN-BUILDUP-3"],
      narrative_type: "denied_claim_resubmission",
      run_checker: false,
      adapter_mode: "fixture",
    });
  });

  it("selecting SoftDent export files posts adapter_mode=softdent_export_file with export samples", async () => {
    vi.mocked(createInsuranceNarrativeDraftWorkflow).mockResolvedValue(buildHappyDraftResult());

    renderPage();

    fireEvent.change(screen.getByLabelText("Data source"), {
      target: { value: "softdent_export_file" },
    });
    expect(screen.getByText(/SoftDent export mode reads server-configured local export files only/i)).toBeInTheDocument();
    expect(screen.getByDisplayValue("CHART-EXPORT")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Create draft" }));

    await waitFor(() => expect(createInsuranceNarrativeDraftWorkflow).toHaveBeenCalled());
    expect(vi.mocked(createInsuranceNarrativeDraftWorkflow).mock.calls[0]?.[0]).toMatchObject({
      patient_ref: "CHART-EXPORT",
      claim_id: "CLAIM-EXPORT-1",
      procedure_ids: ["PROC-CROWN-30"],
      narrative_type: "appeal",
      adapter_mode: "softdent_export_file",
    });
  });

  it("displays blocked missing-data draft result", async () => {
    vi.mocked(createInsuranceNarrativeDraftWorkflow).mockResolvedValue(buildBlockedDraftResult());

    renderPage();

    fireEvent.click(screen.getByRole("button", { name: "Create draft" }));

    expect((await screen.findAllByText("blocked_missing_data")).length).toBeGreaterThan(0);
    expect(screen.getByText(/missing_softdent_ar \(A\/R unavailable — not \$0\)/)).toBeInTheDocument();
    expect(screen.getByText(/missing_scoped_claim_row/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Approve and create local export/i })).not.toBeInTheDocument();
  });

  it("displays happy-path draft summary with source facts", async () => {
    vi.mocked(createInsuranceNarrativeDraftWorkflow).mockResolvedValue(buildHappyDraftResult());

    renderPage();
    fireEvent.change(screen.getByLabelText("Data source"), {
      target: { value: "softdent_export_file" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create draft" }));

    expect(await screen.findByText("narrative-packet-happy")).toBeInTheDocument();
    expect(screen.getByText("narrative-draft-happy")).toBeInTheDocument();
    expect(screen.getByText(/fact-CLAIM-EXPORT-1-claim-status-export/)).toBeInTheDocument();
    expect(screen.getByText(/fact-NOTE-1001-clinical-note/)).toBeInTheDocument();
    expect(screen.getByText(/missing_softdent_ar \(A\/R unavailable — not \$0\)/)).toBeInTheDocument();
  });

  it("requires approval attestation before approve/export", async () => {
    vi.mocked(createInsuranceNarrativeDraftWorkflow).mockResolvedValue(buildHappyDraftResult());

    renderPage();
    fireEvent.change(screen.getByLabelText("Data source"), {
      target: { value: "softdent_export_file" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create draft" }));
    await screen.findByText("narrative-draft-happy");

    const approveButton = screen.getByRole("button", { name: /Approve and create local export/i });
    expect(approveButton).toBeDisabled();

    fireEvent.click(screen.getByRole("checkbox", { name: /I attest this draft was human-reviewed/i }));
    expect(approveButton).not.toBeDisabled();
  });

  it("posts packet and draft for approve/export and shows not_submitted preview", async () => {
    const draftResult = buildHappyDraftResult();
    vi.mocked(createInsuranceNarrativeDraftWorkflow).mockResolvedValue(draftResult);
    vi.mocked(approveAndExportInsuranceNarrativeWorkflow).mockResolvedValue(buildExportResult());

    renderPage();
    fireEvent.change(screen.getByLabelText("Data source"), {
      target: { value: "softdent_export_file" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create draft" }));
    await screen.findByText("narrative-draft-happy");

    fireEvent.click(screen.getByRole("checkbox", { name: /I attest this draft was human-reviewed/i }));
    fireEvent.click(screen.getByRole("button", { name: /Approve and create local export/i }));

    await waitFor(() => expect(approveAndExportInsuranceNarrativeWorkflow).toHaveBeenCalled());
    expect(vi.mocked(approveAndExportInsuranceNarrativeWorkflow).mock.calls[0]?.[0]).toMatchObject({
      packet: draftResult.packet,
      draft: draftResult.draft,
      reviewer: "local-reviewer",
      export_format: "markdown",
      approval_attestation: true,
    });

    expect((await screen.findAllByText("not_submitted")).length).toBeGreaterThan(0);
    expect(screen.getByText(/Not submitted — local export only/i)).toBeInTheDocument();
    expect(screen.getByText(/\[fact-CLAIM-EXPORT-1-claim-status-export\]/)).toBeInTheDocument();
  });

  it("does not expose submit/send/fax/upload actions", () => {
    renderPage();

    const forbidden = [/submit/i, /send/i, /fax/i, /upload/i];
    for (const pattern of forbidden) {
      expect(screen.queryByRole("button", { name: pattern })).not.toBeInTheDocument();
    }
    expect(screen.getByRole("button", { name: "Create draft" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Approve and create local export/i })).not.toBeInTheDocument();
  });

  it("route requires hal:operator and renders after verified operator session", async () => {
    setApiAuthenticatedUsername("operator");
    server.use(
      http.get("/api/auth/session", () =>
        HttpResponse.json({
          username: "operator",
          display_name: "Operator",
          roles: ["hal:operator"],
        }),
      ),
    );

    renderAppAsOperator();

    expect(await screen.findByRole("heading", { name: "Operator narrative workflow" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create draft" })).toBeInTheDocument();
  });
});
