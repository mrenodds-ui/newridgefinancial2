import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { clearApiBasicAuthCredentials } from "../api/basicAuth";
import { fetchFinancialSummary, refreshHalFinancialSources } from "../api/client";

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
});