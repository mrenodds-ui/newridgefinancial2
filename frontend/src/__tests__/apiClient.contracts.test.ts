import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { clearApiBasicAuthCredentials } from "../api/basicAuth";
import { createSoftDentDraft, createSoftDentLocalPacket, createOfficeManagerTask, fetchFinancialSummary, fetchOfficeManagerAttention, refreshHalFinancialSources } from "../api/client";

function buildJsonResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? "OK" : "ERROR",
    headers: new Headers({ "content-type": "application/json" }),
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response;
}

function buildValidFinancialSummaryPayload() {
  return {
    latestAr: null,
    monthlyKpis: [],
    trailing12Months: [],
    calendarYearKpis: [],
    fourYearMonthlyKpis: [],
    providerProduction: [],
    topAdaCodes: [],
  };
}

describe("HAL API contract parsing", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
    clearApiBasicAuthCredentials();
  });

  afterEach(() => {
    clearApiBasicAuthCredentials();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("parses a valid financial summary payload", async () => {
    fetchMock.mockResolvedValue(buildJsonResponse(buildValidFinancialSummaryPayload()));

    await expect(fetchFinancialSummary()).resolves.toMatchObject({
      latestAr: null,
      monthlyKpis: [],
      trailing12Months: [],
    });
  });

  it("rejects malformed financial summary payloads", async () => {
    fetchMock.mockResolvedValue(
      buildJsonResponse({
        latestAr: null,
        monthlyKpis: "bad-payload",
        trailing12Months: [],
        calendarYearKpis: [],
        fourYearMonthlyKpis: [],
        providerProduction: [],
        topAdaCodes: [],
      }),
    );

    await expect(fetchFinancialSummary()).rejects.toThrow();
  });

  it("parses a valid HAL refresh payload", async () => {
    fetchMock.mockResolvedValue(
      buildJsonResponse({
        message: "Refresh completed",
        actor: "admin",
        refreshed_at_utc: "2026-06-23T04:00:00Z",
        refresh_report: { status: "ok" },
        financial_summary: buildValidFinancialSummaryPayload(),
        hal_status: { mode: "local" },
        admin_summary: {},
      }),
    );

    await expect(refreshHalFinancialSources()).resolves.toMatchObject({
      message: "Refresh completed",
      hal_status: { mode: "local" },
    });
  });

  it("rejects malformed HAL refresh payloads", async () => {
    fetchMock.mockResolvedValue(
      buildJsonResponse({
        message: "Refresh completed",
        actor: "admin",
        refreshed_at_utc: "2026-06-23T04:00:00Z",
        refresh_report: { status: "ok" },
        financial_summary: buildValidFinancialSummaryPayload(),
        hal_status: {},
        admin_summary: {},
      }),
    );

    await expect(refreshHalFinancialSources()).rejects.toThrow();
  });

  it("creates a SoftDent draft artifact with the expected payload", async () => {
    fetchMock.mockResolvedValue(
      buildJsonResponse({
        draft_id: "sdd-test",
        draft_type: "insurance_narrative_proposal",
        patient_label: "John Doe",
        title: "Insurance narrative proposal",
        body: "Draft only. Requires human review. Not submitted. Not written to SoftDent.",
        checklist_items: ["Review payer facts."],
        source_fact_refs: ["claim:CLM-1001"],
        missing_data_codes: ["missing_softdent_ar"],
        limitations: ["No A/R source."],
        review_required: true,
        external_action_performed: false,
      }),
    );

    await expect(
      createSoftDentDraft({
        patient_query: "Patient John Doe claim review",
        draft_type: "insurance_narrative_proposal",
        workflow_reason: "hal_workstation_review",
        include_clinical_context: true,
        include_ledger_context: false,
      }),
    ).resolves.toMatchObject({
      draft_id: "sdd-test",
      review_required: true,
      external_action_performed: false,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/hal9000/softdent-drafts"),
      expect.objectContaining({
        method: "POST",
        body: expect.stringContaining("insurance_narrative_proposal"),
      }),
    );
  });

  it("creates a SoftDent local packet artifact with attestation", async () => {
    fetchMock.mockResolvedValue(
      buildJsonResponse({
        packet_id: "sdp-test",
        source_draft_id: "sdd-test",
        packet_type: "approved_narrative_packet",
        patient_label: "John Doe",
        title: "Approved narrative packet",
        body: "Local only. Approved for internal office use. Not submitted. Not written to SoftDent.",
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
        submission_status: "not_submitted",
        external_action_performed: false,
        softdent_writeback_performed: false,
        local_only: true,
      }),
    );

    await expect(
      createSoftDentLocalPacket({
        draft_artifact: {
          draft_id: "sdd-test",
          draft_type: "insurance_narrative_proposal",
          patient_label: "John Doe",
          title: "Insurance narrative proposal",
          body: "Draft only.",
          checklist_items: [],
          source_fact_refs: ["claim:CLM-1001"],
          missing_data_codes: ["missing_softdent_ar"],
          limitations: [],
          review_required: true,
          external_action_performed: false,
        },
        packet_type: "approved_narrative_packet",
        approval_attestation: {
          approved_by: "Billing Lead",
          approval_note: "Reviewed for internal use only.",
          attestation_checked: true,
          acknowledged_local_only: true,
          acknowledged_not_submitted: true,
          acknowledged_no_softdent_writeback: true,
          acknowledged_no_external_delivery: true,
        },
      }),
    ).resolves.toMatchObject({
      packet_id: "sdp-test",
      submission_status: "not_submitted",
      external_action_performed: false,
      softdent_writeback_performed: false,
      local_only: true,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/hal9000/softdent-local-packets"),
      expect.objectContaining({
        method: "POST",
        body: expect.stringContaining("acknowledged_no_external_delivery"),
      }),
    );
  });

  it("loads office-manager attention with safety invariants", async () => {
    fetchMock.mockResolvedValue(
      buildJsonResponse({
        generated_at_utc: "2026-06-26T20:00:00Z",
        summary: "Attention summary",
        safety_disclaimer: "Local only",
        items: [],
        missing_data_codes: ["missing_treatment_plan_export"],
        local_only: true,
        external_action_performed: false,
        softdent_writeback_performed: false,
        submission_status: "not_submitted",
      }),
    );

    await expect(fetchOfficeManagerAttention()).resolves.toMatchObject({
      submission_status: "not_submitted",
      local_only: true,
      external_action_performed: false,
    });
  });

  it("creates a local office-manager task", async () => {
    fetchMock.mockResolvedValue(
      buildJsonResponse({
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
      }),
    );

    await expect(
      createOfficeManagerTask({
        title: "Review denial packet",
        description: "",
        category: "claim",
        priority: "normal",
        source_refs: [],
        missing_data_codes: [],
      }),
    ).resolves.toMatchObject({
      task_id: "omt-test",
      local_only: true,
      external_action_performed: false,
    });
  });
});