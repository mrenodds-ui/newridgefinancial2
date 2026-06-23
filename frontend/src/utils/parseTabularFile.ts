import Papa from "papaparse";
import * as XLSX from "xlsx";

export type ParsedTabularFile = {
  rows: Record<string, unknown>[];
  sheetNames: string[];
  selectedSheetName: string | null;
  detectedReportType: string;
  sourceFormat: "excel" | "delimited";
};

function normalizeToken(value: string) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function detectReportType(rows: Record<string, unknown>[], fileName: string, sheetName?: string | null) {
  const labels = [fileName, sheetName ?? ""].map(normalizeToken).filter(Boolean).join(" ");

  if (labels.includes("profit and loss") || labels.includes("p l") || labels.includes("p&l")) {
    return "Profit and Loss";
  }
  if (labels.includes("ar aging") || labels.includes("a r aging") || labels.includes("aging")) {
    return "A/R Aging";
  }
  if (labels.includes("expense") && labels.includes("categor")) {
    return "Expenses by Category";
  }
  if (labels.includes("collection") && labels.includes("production")) {
    return "Production and Collections";
  }
  if (labels.includes("collection")) {
    return "Collections";
  }
  if (labels.includes("production")) {
    return "Production";
  }

  const columns = new Set(Object.keys(rows[0] ?? {}).map((key) => normalizeToken(key).replace(/ /g, "_")));

  if (
    (columns.has("income") || columns.has("income_total") || columns.has("revenue")) &&
    (columns.has("expenses") || columns.has("expense_total") || columns.has("net_income"))
  ) {
    return "Profit and Loss";
  }

  if (
    (columns.has("expense_category") || columns.has("category") || columns.has("account_name")) &&
    (columns.has("amount") || columns.has("total_amount") || columns.has("expense_total"))
  ) {
    return "Expenses by Category";
  }

  if (
    columns.has("balance_30") ||
    columns.has("balance_60") ||
    columns.has("balance_90") ||
    columns.has("current_balance") ||
    columns.has("total_ar")
  ) {
    return "A/R Aging";
  }

  if (
    (columns.has("provider") || columns.has("provider_name")) &&
    (columns.has("production") || columns.has("gross_production")) &&
    columns.has("collections")
  ) {
    return "Production and Collections";
  }

  return "Unknown";
}

function isExcelFile(file: File) {
  return (
    /\.(xlsx|xls)$/i.test(file.name) ||
    file.type === "application/vnd.ms-excel" ||
    file.type === "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
  );
}

function parseDelimitedFile(file: File): Promise<Record<string, unknown>[]> {
  return new Promise((resolve, reject) => {
    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      complete: (results) => {
        if (results.errors && results.errors.length > 0) {
          reject(new Error(results.errors[0].message));
          return;
        }
        resolve(results.data as Record<string, unknown>[]);
      },
      error: (err) => reject(err),
    });
  });
}

async function parseExcelFile(file: File, requestedSheetName?: string | null): Promise<ParsedTabularFile> {
  const buffer = await file.arrayBuffer();
  const workbook = XLSX.read(buffer, { type: "array" });
  const sheetNames = workbook.SheetNames;
  const selectedSheetName = requestedSheetName && sheetNames.includes(requestedSheetName) ? requestedSheetName : sheetNames[0];
  if (!selectedSheetName) {
    throw new Error("Workbook does not contain any sheets.");
  }

  const worksheet = workbook.Sheets[selectedSheetName];
  const rows = XLSX.utils.sheet_to_json<Record<string, unknown>>(worksheet, {
    defval: "",
    raw: false,
  });

  if (!rows.length) {
    throw new Error("Workbook sheet is empty.");
  }

  return {
    rows,
    sheetNames,
    selectedSheetName,
    detectedReportType: detectReportType(rows, file.name, selectedSheetName),
    sourceFormat: "excel",
  };
}

export async function parseTabularFile(file: File, options?: { sheetName?: string | null }): Promise<ParsedTabularFile> {
  if (isExcelFile(file)) {
    return parseExcelFile(file, options?.sheetName);
  }
  const rows = await parseDelimitedFile(file);
  return {
    rows,
    sheetNames: [],
    selectedSheetName: null,
    detectedReportType: detectReportType(rows, file.name, null),
    sourceFormat: "delimited",
  };
}
