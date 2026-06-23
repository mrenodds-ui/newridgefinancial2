import { z } from "zod";
import {
  type AppPreference,
  type ImportJob,
  type KpiSnapshot,
  listBackupImportJobs,
  listBackupKpiSnapshots,
  listBackupPreferences,
  replaceBackupData,
} from "../db";
import { openTextFile, saveTextFile } from "./fileAccess";

const browserBackupSchema = z.object({
  version: z.literal(1),
  exportedAt: z.string(),
  kpiSnapshots: z.array(
    z.object({
      period: z.string(),
      production: z.number(),
      collections: z.number(),
      overheadPercentage: z.number(),
      updatedAt: z.string(),
    }),
  ),
  preferences: z.array(
    z.object({
      key: z.string(),
      value: z.string(),
      updatedAt: z.string(),
    }),
  ),
  importJobs: z.array(
    z.object({
      id: z.number().optional(),
      source: z.enum(["softdent", "quickbooks", "practice-central"]),
      status: z.enum(["queued", "running", "done", "error"]),
      startedAt: z.string(),
      finishedAt: z.string().optional(),
      message: z.string().optional(),
    }),
  ),
});

export type BrowserBackup = z.infer<typeof browserBackupSchema>;

export function createBrowserBackupFileName(now = new Date()): string {
  const stamp = now.toISOString().slice(0, 10);
  return `newridge-financial-backup-${stamp}.json`;
}

export async function createBrowserBackup(): Promise<BrowserBackup> {
  const [kpiSnapshots, preferences, importJobs] = await Promise.all([
    listBackupKpiSnapshots(),
    listBackupPreferences(),
    listBackupImportJobs(),
  ]);

  return {
    version: 1,
    exportedAt: new Date().toISOString(),
    kpiSnapshots,
    preferences,
    importJobs,
  };
}

export function serializeBrowserBackup(backup: BrowserBackup): string {
  return JSON.stringify(browserBackupSchema.parse(backup), null, 2);
}

export function parseBrowserBackup(contents: string): BrowserBackup {
  return browserBackupSchema.parse(JSON.parse(contents));
}

export async function exportBrowserBackup(globalScope?: Window & typeof globalThis): Promise<void> {
  const backup = await createBrowserBackup();
  const contents = serializeBrowserBackup(backup);
  await saveTextFile({
    fileName: createBrowserBackupFileName(),
    contents,
    mimeType: "application/json",
    globalScope: globalScope as never,
    documentRef: globalScope?.document,
  });
}

export async function importBrowserBackupFile(file: File): Promise<BrowserBackup> {
  const contents = await file.text();
  const backup = parseBrowserBackup(contents);
  await restoreBrowserBackup(backup);
  return backup;
}

export async function chooseBrowserBackupFile(globalScope?: Window & typeof globalThis): Promise<File | null> {
  return openTextFile({
    mimeType: "application/json",
    globalScope: globalScope as never,
  });
}

export async function restoreBrowserBackup(backup: BrowserBackup): Promise<void> {
  const parsed = browserBackupSchema.parse(backup);
  await replaceBackupData({
    kpiSnapshots: parsed.kpiSnapshots as KpiSnapshot[],
    preferences: parsed.preferences as AppPreference[],
    importJobs: parsed.importJobs as ImportJob[],
  });
}
