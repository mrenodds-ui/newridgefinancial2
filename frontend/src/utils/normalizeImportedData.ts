type ImportSource = "softdent" | "quickbooks";

export type NormalizedStagedFile = {
  fileName: string;
  mimeType: string;
  content: string;
};

export type NormalizedImportResult = {
  dashboardRows: Record<string, unknown>[];
  stagedFiles: NormalizedStagedFile[];
};

function normalizeKey(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "");
}

function getValue(row: Record<string, unknown>, keys: string[]) {
  const entries = Object.entries(row);
  for (const key of keys) {
    const found = entries.find(
      ([entryKey, value]) =>
        normalizeKey(entryKey) === normalizeKey(key) && value !== null && value !== undefined && String(value).trim() !== "",
    );
    if (found) return found[1];
  }
  return "";
}

function toNumber(value: unknown) {
  if (typeof value === "number") return Number.isFinite(value) ? value : 0;
  const parsed = Number(
    String(value ?? "")
      .replace(/[$,]/g, "")
      .trim(),
  );
  return Number.isFinite(parsed) ? parsed : 0;
}

function toCsv(rows: Record<string, unknown>[]) {
  if (!rows.length) return "";
  const headers = Object.keys(rows[0]);
  const escapeCsv = (value: unknown) => {
    const text = String(value ?? "");
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  return [headers.join(","), ...rows.map((row) => headers.map((header) => escapeCsv(row[header])).join(","))].join("\n");
}

function normalizeSoftDentDashboardRows(rows: Record<string, unknown>[]) {
  return rows
    .map((row) => ({
      provider: String(getValue(row, ["provider", "provider_name", "doctor"]) || "Unknown"),
      period: String(getValue(row, ["period", "year_month", "month", "report_period"]) || ""),
      production: toNumber(getValue(row, ["production", "gross_production", "net_production"])),
      collections: toNumber(getValue(row, ["collections", "collection_total", "deposit_total"])),
      insurance: toNumber(getValue(row, ["insurance", "insurance_amount"])),
      patient: toNumber(getValue(row, ["patient", "patient_amount"])),
    }))
    .filter((row) => row.provider || row.production || row.collections || row.period);
}

export function normalizeImportedData(rows: Record<string, unknown>[], source: ImportSource, reportType: string): NormalizedImportResult {
  if (source === "softdent" && ["Production", "Collections", "Production and Collections"].includes(reportType)) {
    const dashboardRows = normalizeSoftDentDashboardRows(rows);
    return {
      dashboardRows,
      stagedFiles: [],
    };
  }

  if (source === "softdent" && reportType === "A/R Aging") {
    return {
      dashboardRows: rows,
      stagedFiles: [],
    };
  }

  if (source === "softdent" && reportType === "Unknown") {
    return {
      dashboardRows: rows,
      stagedFiles: [],
    };
  }

  if (source === "quickbooks") {
    return {
      dashboardRows: rows,
      stagedFiles: rows.length
        ? [
            {
              fileName: `quickbooks_${reportType.toLowerCase().replace(/[^a-z0-9]+/g, "_") || "export"}.csv`,
              mimeType: "text/csv",
              content: toCsv(rows),
            },
          ]
        : [],
    };
  }

  return { dashboardRows: rows, stagedFiles: [] };
}

export function downloadNormalizedStagedFile(file: NormalizedStagedFile) {
  const blob = new Blob([file.content], { type: file.mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = file.fileName;
  anchor.click();
  URL.revokeObjectURL(url);
}
