import { downloadSampleFile } from "../../utils/downloadSampleFile";

import { useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { formatCurrency } from "../../../utils/formatting";
import {
  type FinancialSummaryResponse,
  fetchFinancialSummary,
  refreshHalFinancialSources,
  uploadQuickBooksImport,
  uploadSoftDentImport,
} from "../../api/client";
import { useAuthSession } from "../../hooks/useAuthSession";
import { queryClient, queryKeys } from "../../queryClient";
import type { ImportRecord } from "../../types/dashboard";
import { type NormalizedStagedFile, downloadNormalizedStagedFile, normalizeImportedData } from "../../utils/normalizeImportedData";
import { parseCsvPreview } from "../../utils/parseCsvPreview";
import ImportHistoryVirtualized from "./ImportHistoryVirtualized";
import { SoftDentCoveragePanel } from "./SoftDentCoveragePanel";
import "./importpanel.css";

function normalizeColumn(value: string) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function hasAnyColumn(columns: Set<string>, candidates: string[]) {
  return candidates.some((candidate) => columns.has(candidate));
}

type PreviewRow = Record<string, unknown>;

function buildValidationMessage(reportType: string, data: Record<string, unknown>[]) {
  if (!data.length) {
    return "This file does not contain any rows to import.";
  }

  const columns = new Set(Object.keys(data[0] ?? {}).map(normalizeColumn));

  if (["Production", "Collections", "Production and Collections"].includes(reportType)) {
    const hasProvider = hasAnyColumn(columns, ["provider", "provider_name", "doctor"]);
    const hasProduction = hasAnyColumn(columns, ["production", "gross_production", "net_production"]);
    const hasCollections = hasAnyColumn(columns, ["collections", "collection_total", "deposit_total"]);
    if (!hasProvider || !hasProduction || !hasCollections) {
      return "Missing columns for a production file. Include provider, production, and collections.";
    }
    return null;
  }

  if (reportType === "Profit and Loss") {
    const hasIncome = hasAnyColumn(columns, ["income", "income_total", "revenue"]);
    const hasExpenses = hasAnyColumn(columns, ["expense_total", "expenses", "amount"]);
    if (!hasIncome || !hasExpenses) {
      return "Missing columns for a profit and loss file. Include income or revenue plus expenses.";
    }
    return null;
  }

  if (reportType === "A/R Aging") {
    const hasAging = hasAnyColumn(columns, ["current_balance", "balance_30", "balance_60", "balance_90", "total_ar"]);
    if (!hasAging) {
      return "Missing columns for an A/R aging file. Include balances for current, 30, 60, or 90+.";
    }
    return null;
  }

  if (reportType === "Expenses by Category") {
    const hasCategory = hasAnyColumn(columns, ["expense_category", "category", "account_name"]);
    const hasAmount = hasAnyColumn(columns, ["total_amount", "amount", "expense_total"]);
    if (!hasCategory || !hasAmount) {
      return "Missing columns for an expense category file. Include a category or account plus an amount.";
    }
    return null;
  }

  return "We could not match this file to a supported import type. Review the sheet and column names before continuing.";
}

function toNumber(value: number | string | null | undefined) {
  if (typeof value === "number") return Number.isFinite(value) ? value : 0;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
}

function toImportStatus(status: string | null | undefined): ImportRecord["status"] {
  const normalized = (status ?? "").toLowerCase();
  if (!normalized) return "pending";
  if (["ok", "ready", "available", "loaded", "connected", "success", "healthy"].includes(normalized)) {
    return "success";
  }
  if (normalized.includes("error") || normalized.includes("fail") || normalized.includes("unavailable")) {
    return "error";
  }
  return "pending";
}

export function buildLiveImportHistory(financialSummary: FinancialSummaryResponse | undefined): ImportRecord[] {
  if (!financialSummary) {
    return [];
  }

  const generatedAt = financialSummary.generatedAt ?? new Date().toISOString();
  const softDentImportedAt = financialSummary.latestSoftDentRefreshAt ?? financialSummary.lastRefreshed ?? generatedAt;
  const quickBooksImportedAt = financialSummary.quickBooksStatus?.lastImportedAtUtc ?? financialSummary.lastRefreshed ?? generatedAt;

  const softDentRows =
    (financialSummary.monthlyKpis?.length ?? 0) +
    (financialSummary.trailing12Months?.length ?? 0) +
    (financialSummary.providerProduction?.length ?? 0) +
    (financialSummary.topAdaCodes?.length ?? 0);

  const quickBooksRows =
    Object.values(financialSummary.quickBooksStatus?.rowCounts ?? {}).reduce((sum, count) => sum + toNumber(count), 0) ||
    (financialSummary.quickBooksProfitLossSummary?.length ?? 0) +
      (financialSummary.quickBooksExpenseCategories?.length ?? 0) +
      (financialSummary.quickBooksMonthlyExpenses?.length ?? 0);

  return [
    {
      id: "live-softdent-summary",
      source: "softdent",
      reportType: "SoftDent dashboard update",
      fileName: "SoftDent monthly summary",
      importedAt: softDentImportedAt,
      rowCount: softDentRows,
      status: financialSummary.latestSoftDentRefreshAt ? "success" : "pending",
      errorMessage:
        financialSummary.dataFreshnessStatus === "stale" ? "SoftDent numbers are marked out of date until a newer export is added." : undefined,
    },
    {
      id: "live-quickbooks-summary",
      source: "quickbooks",
      reportType: "QuickBooks live update",
      fileName: "QuickBooks live summary",
      importedAt: quickBooksImportedAt,
      rowCount: quickBooksRows,
      status: toImportStatus(financialSummary.quickBooksStatus?.status),
      errorMessage: financialSummary.quickBooksStatus?.lastError ?? financialSummary.quickBooksStatus?.message ?? undefined,
    },
  ];
}

export default function ImportPanel() {
  const {
    isAuthenticated,
    isAdmin,
    isLoading: isAuthSessionLoading,
    isError: isAuthSessionError,
    isSessionVerified,
    isRoleKnown,
    error: authSessionError,
    sessionStatusCode,
  } = useAuthSession();
  const [history, setHistory] = useState<ImportRecord[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const [previewFile, setPreviewFile] = useState<File | null>(null);
  const [previewSheetNames, setPreviewSheetNames] = useState<string[]>([]);
  const [selectedSheetName, setSelectedSheetName] = useState<string>("");
  const [detectedReportType, setDetectedReportType] = useState<string>("Unknown");
  const [normalizedFiles, setNormalizedFiles] = useState<NormalizedStagedFile[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const financialSummaryQuery = useQuery({
    queryKey: ["financial-summary"],
    queryFn: fetchFinancialSummary,
    enabled: isSessionVerified,
  });
  const verifiedFinancialSummary = isSessionVerified ? financialSummaryQuery.data : undefined;
  const softDentCoverage = verifiedFinancialSummary?.softDentCoverage ?? null;
  const claimsSummary = verifiedFinancialSummary?.claimsSummary ?? null;
  const liveHistory = buildLiveImportHistory(verifiedFinancialSummary);
  const combinedHistory = isSessionVerified
    ? [...history, ...liveHistory.filter((record) => !history.some((item) => item.id === record.id))]
    : history;
  const [validationMsg, setValidationMsg] = useState<string | null>(null);
  const [parsing, setParsing] = useState(false);
  const [previewData, setPreviewData] = useState<PreviewRow[] | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [stagingMessage, setStagingMessage] = useState<string | null>(null);
  const [stagingError, setStagingError] = useState<string | null>(null);
  const currentSource = previewFile?.name.toLowerCase().includes("quickbooks") ? "quickbooks" : "softdent";
  const previewColumns = previewData ? Object.keys(previewData[0] ?? {}) : [];
  const importsRequireAdmin = isAuthenticated && isRoleKnown && !isAuthSessionLoading && !isAdmin;
  const importControlsLocked = isAuthenticated && (!isRoleKnown || isAuthSessionLoading || !isAdmin);
  const hasSessionVerificationError = isAuthenticated && isAuthSessionError && sessionStatusCode !== 401;
  const liveCoverageMessage = isAuthSessionLoading
    ? "Checking your access before loading the latest file status and coverage details."
    : hasSessionVerificationError
      ? "Your workspace could not be verified right now."
      : "Sign in from the dashboard banner to see the latest file status and SoftDent file details.";

  async function invalidateHalViews() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["financial-summary"] }),
      queryClient.invalidateQueries({ queryKey: queryKeys.adminSummary }),
      queryClient.invalidateQueries({ queryKey: queryKeys.halStatus }),
      queryClient.invalidateQueries({ queryKey: ["hal-field-timeframes"] }),
      queryClient.invalidateQueries({ queryKey: queryKeys.halAudits }),
    ]);
  }

  async function handleFile(file: File, options?: { sheetName?: string | null }) {
    setValidationMsg(null);
    setPreviewError(null);
    setStagingMessage(null);
    setStagingError(null);
    setParsing(true);
    try {
      const parsed = await parseCsvPreview(file, options);
      const data = parsed.rows;
      const source = file.name.toLowerCase().includes("quickbooks") ? "quickbooks" : "softdent";
      const normalized = normalizeImportedData(data, source, parsed.detectedReportType);
      setPreviewFile(file);
      setPreviewSheetNames(parsed.sheetNames);
      setSelectedSheetName(parsed.selectedSheetName ?? "");
      setDetectedReportType(parsed.detectedReportType);
      setNormalizedFiles(normalized.stagedFiles);
      setValidationMsg(buildValidationMessage(parsed.detectedReportType, data));
      setPreviewData(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setPreviewError(`This file could not be opened. ${message}`);
      setPreviewFile(null);
      setPreviewSheetNames([]);
      setSelectedSheetName("");
      setDetectedReportType("Unknown");
      setNormalizedFiles([]);
      setPreviewData(null);
    } finally {
      setParsing(false);
    }
  }

  async function commitPreviewImport() {
    if (importControlsLocked) {
      setStagingMessage(null);
      setStagingError(
        isAuthSessionError
          ? authSessionError?.message || "We could not confirm your sign-in for file imports. Try signing in again."
          : "Only admin accounts can add files.",
      );
      return;
    }

    if (previewFile && previewData) {
      const normalized = normalizeImportedData(previewData, currentSource, detectedReportType);
      const importedAt = new Date().toISOString();
      const historyRecord: ImportRecord = {
        id: `${Date.now()}`,
        source: currentSource,
        reportType: detectedReportType,
        fileName: previewFile.name,
        importedAt,
        rowCount: previewData.length,
        status: "success",
      };

      if (currentSource === "softdent") {
        try {
          await uploadSoftDentImport(previewFile);
          await refreshHalFinancialSources();
          await invalidateHalViews();
          setHistory((prev) => [historyRecord, ...prev]);
          setStagingMessage("SoftDent file added and dashboard pages refreshed.");
          setStagingError(null);
        } catch (error) {
          const message = error instanceof Error ? error.message : String(error);
          setStagingError(`SoftDent import could not be completed. ${message}`);
        }
      } else if (normalized.stagedFiles.length > 0) {
        try {
          for (const file of normalized.stagedFiles) {
            await uploadQuickBooksImport(
              new File([file.content], file.fileName, {
                type: file.mimeType,
              }),
            );
          }
          await refreshHalFinancialSources();
          await invalidateHalViews();
          setHistory((prev) => [historyRecord, ...prev]);
          setStagingMessage(`${normalized.stagedFiles.length} QuickBooks file(s) added and dashboard pages refreshed.`);
          setStagingError(null);
        } catch (error) {
          const message = error instanceof Error ? error.message : String(error);
          setStagingError(`QuickBooks import could not be completed. ${message}`);
        }
      } else if (currentSource === "quickbooks") {
        setStagingError("This QuickBooks file could not be prepared for import, so the dashboard was not updated.");
      }
    }

    setPreviewFile(null);
    setPreviewSheetNames([]);
    setSelectedSheetName("");
    setDetectedReportType("Unknown");
    setNormalizedFiles([]);
    setPreviewData(null);
  }

  function handleChooseFile() {
    if (importControlsLocked) return;
    fileInputRef.current?.click();
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (importControlsLocked) {
      e.target.value = "";
      return;
    }
    const file = e.target.files?.[0];
    if (!file) return;
    handleFile(file);
    e.target.value = "";
  }

  function handleDragOver(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(true);
  }

  function handleDragLeave(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (importControlsLocked) {
      return;
    }
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFile(e.dataTransfer.files[0]);
    }
  }

  return (
    <section className="dashboard-import-card">
      <div className="dashboard-import-title">
        Add a File
        <span className="dashboard-import-title-download" title="Click to download a sample file for import.">
          <button className="dashboard-import-btn dashboard-import-btn-download" onClick={downloadSampleFile} type="button">
            Download Example File
          </button>
        </span>
        <span
          className="dashboard-import-title-tip"
          title="Tip: For production updates, use a file with provider, production, and collections columns."
        >
          ℹ️ Tip: For production updates, use provider, production, and collections columns.
        </span>
      </div>
      <div className="dashboard-import-helper">Add SoftDent or QuickBooks Excel/CSV files.</div>
      <div
        className={`dashboard-import-file-row${dragActive ? " dashboard-import-file-row-active" : ""}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <label htmlFor="import-file-input" className="visually-hidden">
          Choose file to import
        </label>
        <input
          id="import-file-input"
          type="file"
          accept=".csv,.xls,.xlsx,.txt"
          ref={fileInputRef}
          className="dashboard-import-file-input"
          onChange={handleFileChange}
          disabled={importControlsLocked}
          title="Choose file to import"
        />
        <button type="button" className="dashboard-import-btn" onClick={handleChooseFile} disabled={importControlsLocked}>
          Choose File
        </button>
        <span className="dashboard-import-helper">
          Or drag and drop a file here. Dashboard pages refresh after the import finishes.
        </span>
      </div>
      {importsRequireAdmin ? <div className="dashboard-import-warning">Only admin accounts can add files.</div> : null}
      {parsing && (
        <div className="dashboard-import-parse">
          <span className="spinner" aria-live="polite">
            Parsing file...
          </span>
        </div>
      )}
      {previewError && <div className="dashboard-import-error">{previewError}</div>}
      {stagingError && <div className="dashboard-import-warning">{stagingError}</div>}
      {stagingMessage && <div className="dashboard-import-helper">{stagingMessage}</div>}
      {validationMsg && (
        <div className={validationMsg.startsWith("Missing") ? "dashboard-import-error" : "dashboard-import-warning"}>{validationMsg}</div>
      )}
      {isSessionVerified && financialSummaryQuery.isError && (
        <div className="dashboard-import-warning">The latest file status is temporarily unavailable. Try again after the next update.</div>
      )}
      <div className="dashboard-import-history">
        <h3>SoftDent File Check</h3>
        {isSessionVerified ? (
          <>
            <div className="dashboard-import-helper">
              {claimsSummary?.available
                ? `Current claims totals: ${
                    claimsSummary.true_outstanding_claims_amount != null
                      ? formatCurrency(claimsSummary.true_outstanding_claims_amount)
                      : "Unavailable"
                  } outstanding and ${
                    claimsSummary.unsubmitted_claims_amount != null
                      ? formatCurrency(claimsSummary.unsubmitted_claims_amount)
                      : "Unavailable"
                  } unsubmitted.`
                : "Claims totals will appear after the approved SoftDent claim files are added."}
            </div>
            <SoftDentCoveragePanel coverage={softDentCoverage} emptyMessage="SoftDent file details are unavailable right now." />
          </>
        ) : (
          <div className="dashboard-import-helper">{liveCoverageMessage}</div>
        )}
      </div>
      {previewData && (
        <div className="dashboard-import-preview">
          <strong>Preview</strong>
          <div className="dashboard-import-helper">
            Detected file type: <strong>{detectedReportType}</strong>
          </div>
          {previewSheetNames.length > 1 && previewFile ? (
            <label className="dashboard-import-helper">
              Workbook sheet
              <select
                value={selectedSheetName}
                onChange={(event) => {
                  const nextSheetName = event.target.value;
                  setSelectedSheetName(nextSheetName);
                  void handleFile(previewFile, { sheetName: nextSheetName });
                }}
              >
                {previewSheetNames.map((sheetName) => (
                  <option key={sheetName} value={sheetName}>
                    {sheetName}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          {normalizedFiles.length > 0 && currentSource === "quickbooks" ? (
            <div className="dashboard-import-helper">
              QuickBooks files ready to add:
              {normalizedFiles.map((file) => (
                <button
                  key={file.fileName}
                  type="button"
                  className="dashboard-import-btn dashboard-import-btn-download"
                  onClick={() => downloadNormalizedStagedFile(file)}
                >
                  {file.fileName}
                </button>
              ))}
            </div>
          ) : null}
          <div className="dashboard-import-preview-table-wrap">
            <table className="dashboard-import-preview-table">
              <thead>
                <tr>
                  {previewColumns.map((col) => (
                    <th key={col} className="dashboard-import-preview-th">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {previewData.slice(0, 10).map((row) => {
                  const rowKey = `${previewFile?.name ?? "preview"}:${JSON.stringify(row)}`;
                  return (
                    <tr key={rowKey}>
                      {previewColumns.map((col) => (
                        <td key={col} className="dashboard-import-preview-td">
                          {String(row[col] ?? "")}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {previewData.length > 10 && <div className="dashboard-import-preview-info">Showing first 10 rows</div>}
          </div>
          <button
            type="button"
            className="dashboard-import-preview-btn"
            onClick={() => {
              void commitPreviewImport();
            }}
            disabled={importControlsLocked}
          >
            Add to Dashboard
          </button>
          <button
            type="button"
            className="dashboard-import-preview-cancel"
            onClick={() => {
              setPreviewFile(null);
              setPreviewSheetNames([]);
              setSelectedSheetName("");
              setDetectedReportType("Unknown");
              setNormalizedFiles([]);
              setStagingError(null);
              setPreviewData(null);
            }}
          >
            Cancel
          </button>
        </div>
      )}
      <ImportHistoryVirtualized history={combinedHistory} />
    </section>
  );
}
