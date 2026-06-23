import { useState } from "react";

import type { ImportRecord } from "../types/dashboard";
import { parseTabularFile } from "../utils/parseTabularFile";

type ImportedRow = Record<string, unknown>;

export function useFileImport(onData: (data: ImportedRow[]) => void, onHistory: (record: ImportRecord) => void, _profile: string) {
  const [error, setError] = useState<string | null>(null);

  function validateFile(file: File): string | null {
    const allowedTypes = [
      "text/csv",
      "application/vnd.ms-excel",
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "text/plain",
    ];
    if (!allowedTypes.includes(file.type) && !file.name.match(/\.(csv|xls|xlsx|txt)$/i)) {
      return "Unsupported file type. Please upload a CSV, XLS, XLSX, or TXT file.";
    }
    if (file.size > 5 * 1024 * 1024) {
      return "File is too large. Maximum size is 5MB.";
    }
    return null;
  }

  async function handleFile(file: File, options?: { sheetName?: string | null }) {
    const validationError = validateFile(file);
    if (validationError) {
      setError(validationError);
      return;
    }
    try {
      const parsed = await parseTabularFile(file, options);
      const rowCount = parsed.rows.length;
      const now = new Date().toISOString();
      const newRecord: ImportRecord = {
        id: `${Date.now()}`,
        source: file.name.toLowerCase().includes("quickbooks") ? "quickbooks" : "softdent",
        reportType: parsed.detectedReportType,
        fileName: file.name,
        importedAt: now,
        rowCount,
        status: "success",
      };
      setError(null);
      onHistory(newRecord);
      onData(parsed.rows);
    } catch (err) {
      const now = new Date().toISOString();
      const message = err instanceof Error ? err.message : String(err);
      const newRecord: ImportRecord = {
        id: `${Date.now()}`,
        source: file.name.toLowerCase().includes("quickbooks") ? "quickbooks" : "softdent",
        reportType: "Unknown",
        fileName: file.name,
        importedAt: now,
        rowCount: 0,
        status: "error",
        errorMessage: message,
      };
      onHistory(newRecord);
      setError(message);
    }
  }

  return { handleFile, error };
}
