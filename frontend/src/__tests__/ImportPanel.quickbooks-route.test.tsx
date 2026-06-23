import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { clearApiBasicAuthCredentials, setApiBasicAuthCredentials } from "../api/basicAuth";
import type { FinancialSummaryResponse } from "../api/client";
import { fetchAuthSession, fetchFinancialSummary, refreshHalFinancialSources, uploadQuickBooksImport, uploadSoftDentImport } from "../api/client";
import ImportPanel from "../components/dashboard/ImportPanel";
import { queryClient } from "../queryClient";
import { normalizeImportedData } from "../utils/normalizeImportedData";
import { parseCsvPreview } from "../utils/parseCsvPreview";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    fetchAuthSession: vi.fn(),
    fetchFinancialSummary: vi.fn(),
    refreshHalFinancialSources: vi.fn(),
    uploadQuickBooksImport: vi.fn(),
    uploadSoftDentImport: vi.fn(),
  };
});

vi.mock("../utils/normalizeImportedData", async () => {
  const actual = await vi.importActual<typeof import("../utils/normalizeImportedData")>("../utils/normalizeImportedData");
  return {
    ...actual,
    normalizeImportedData: vi.fn(),
    downloadNormalizedStagedFile: vi.fn(),
  };
});

vi.mock("../utils/parseCsvPreview", () => ({
  parseCsvPreview: vi.fn(),
}));

vi.mock("../components/dashboard/SoftDentCoveragePanel", () => ({
  SoftDentCoveragePanel: () => <div data-testid="softdent-coverage-panel" />,
}));

vi.mock("../components/dashboard/ImportHistoryVirtualized", () => ({
  default: ({ history }: { history: unknown[] }) => <div data-testid="import-history">{history.length}</div>,
}));

function buildFinancialSummary(): FinancialSummaryResponse {
  return {
    generatedAt: "2026-06-22T09:00:00Z",
    lastRefreshed: "2026-06-22T08:45:00Z",
    latestSoftDentRefreshAt: null,
    latestAr: null,
    claimsSummary: null,
    softDentCoverage: null,
    monthlyKpis: [],
    trailing12Months: [],
    calendarYearKpis: [],
    fourYearMonthlyKpis: [],
    providerProduction: [],
    topAdaCodes: [],
    quickBooksStatus: {
      status: "ok",
      lastCheckedAtUtc: "2026-06-22T08:40:00Z",
      lastImportedAtUtc: "2026-06-22T08:30:00Z",
      rowCounts: {},
    },
    quickBooksProfitLossSummary: [],
    quickBooksExpenseCategories: [],
    quickBooksMonthlyExpenses: [],
    quickBooksEbitdaCandidates: [],
  } as FinancialSummaryResponse;
}

function renderImportPanel() {
  queryClient.clear();
  render(
    <QueryClientProvider client={queryClient}>
      <ImportPanel />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  clearApiBasicAuthCredentials();
  queryClient.clear();
  vi.restoreAllMocks();
  vi.clearAllMocks();
});

describe("ImportPanel QuickBooks routing", () => {
  it("imports normalized QuickBooks files through the canonical backend route", async () => {
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries").mockResolvedValue(undefined);
    vi.mocked(fetchAuthSession).mockResolvedValue({
      username: "admin",
      display_name: "Administrator",
      roles: ["dashboard:read", "hal:operator", "hal:index:refresh", "admin"],
    });
    vi.mocked(fetchFinancialSummary).mockResolvedValue(buildFinancialSummary());
    vi.mocked(refreshHalFinancialSources).mockResolvedValue({} as never);
    vi.mocked(uploadQuickBooksImport).mockResolvedValue({ message: "ok" });
    vi.mocked(uploadSoftDentImport).mockResolvedValue({ message: "ok" });
    vi.mocked(parseCsvPreview).mockResolvedValue({
      rows: [{ income: 1000, expense_total: 250 }],
      sheetNames: [],
      selectedSheetName: null,
      detectedReportType: "Profit and Loss",
      sourceFormat: "delimited",
    });
    vi.mocked(normalizeImportedData).mockReturnValue({
      dashboardRows: [{ income: 1000, expense_total: 250 }],
      stagedFiles: [
        {
          fileName: "quickbooks_profit_and_loss.csv",
          content: "income,expense_total\n1000,250\n",
          mimeType: "text/csv",
        },
        {
          fileName: "quickbooks_expenses_by_category.csv",
          content: "expense_category,total_amount\nPayroll,250\n",
          mimeType: "text/csv",
        },
      ],
    });

    renderImportPanel();

    const fileInput = screen.getByLabelText(/choose file to import/i);
    const file = new File(["income,expense_total\n1000,250\n"], "quickbooks-june.csv", { type: "text/csv" });

    fireEvent.change(fileInput, { target: { files: [file] } });

    await screen.findByText(/detected report type:/i);
    await screen.findByText(/quickbooks staged files ready:/i);

    fireEvent.click(screen.getByRole("button", { name: "Import Data" }));

    await waitFor(() => {
      expect(uploadQuickBooksImport).toHaveBeenCalledTimes(2);
    });

    expect(uploadSoftDentImport).not.toHaveBeenCalled();
    expect(refreshHalFinancialSources).toHaveBeenCalledTimes(1);
    expect(invalidateSpy).toHaveBeenCalledTimes(5);
    expect(
      vi.mocked(uploadQuickBooksImport).mock.calls.map(([uploadedFile]) => ({
        name: uploadedFile.name,
        isFile: uploadedFile instanceof File,
      })),
    ).toEqual([
      { name: "quickbooks_profit_and_loss.csv", isFile: true },
      { name: "quickbooks_expenses_by_category.csv", isFile: true },
    ]);
    expect(
      await screen.findByText(
        /2 QuickBooks file\(s\) imported through the canonical backend pipeline and HAL page feeds were refreshed\./i,
      ),
    ).toBeInTheDocument();
  });

  it("locks import actions for authenticated viewers", async () => {
    setApiBasicAuthCredentials("viewer", "viewer-password");
    vi.mocked(fetchAuthSession).mockResolvedValue({
      username: "viewer",
      display_name: "Viewer",
      roles: ["dashboard:read"],
    });
    vi.mocked(fetchFinancialSummary).mockResolvedValue(buildFinancialSummary());

    renderImportPanel();

    expect(await screen.findByText(/Imports require an admin account after sign-in\./i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Choose File" })).toBeDisabled();
  });

  it("does not render live import history or coverage data until the session is verified", async () => {
    setApiBasicAuthCredentials("admin", "password");
    vi.mocked(fetchAuthSession).mockImplementation(() => new Promise(() => {}));
    vi.mocked(fetchFinancialSummary).mockResolvedValue(buildFinancialSummary());

    renderImportPanel();

    expect(await screen.findByText(/Verifying the current dashboard session before loading live HAL source status and coverage details\./i)).toBeInTheDocument();
    expect(screen.getByTestId("import-history")).toHaveTextContent("0");
    expect(screen.queryByText(/Live claims aggregate snapshot:/i)).not.toBeInTheDocument();
    expect(fetchFinancialSummary).not.toHaveBeenCalled();
  });
});
