import { describe, expect, it, vi } from "vitest";

import type { FinancialSummaryResponse } from "../api/client";
import { buildLiveImportHistory } from "../components/dashboard/ImportPanel";

describe("buildLiveImportHistory", () => {
  it("does not use lastCheckedAtUtc as a fallback for importedAt", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-20T12:00:00Z"));

    const payload: FinancialSummaryResponse = {
      generatedAt: "2026-06-20T12:00:00Z",
      lastRefreshed: "2026-06-20T10:00:00Z",
      latestAr: null,
      monthlyKpis: [],
      trailing12Months: [],
      calendarYearKpis: [],
      fourYearMonthlyKpis: [],
      providerProduction: [],
      topAdaCodes: [],
      quickBooksStatus: {
        status: "ok",
        lastCheckedAtUtc: "2026-06-20T11:00:00Z",
      },
      quickBooksProfitLossSummary: [],
      quickBooksExpenseCategories: [],
      quickBooksMonthlyExpenses: [],
      quickBooksEbitdaCandidates: [],
    };

    const records = buildLiveImportHistory(payload);
    const quickbooksRecord = records.find((record) => record.id === "live-quickbooks-summary");

    expect(quickbooksRecord?.importedAt).toBe("2026-06-20T10:00:00Z");

    vi.useRealTimers();
  });
});
