import { type ParsedTabularFile, parseTabularFile } from "./parseTabularFile";

export function parseCsvPreview(file: File, options?: { sheetName?: string | null }): Promise<ParsedTabularFile> {
  return parseTabularFile(file, options);
}
