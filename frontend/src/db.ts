import Dexie, { type Table } from "dexie";

import { broadcastBrowserSyncMessage, createBrowserSyncMessage } from "./browser/crossTabSync";
import { withWebLock } from "./browser/webLocks";
import type { KpiRecord } from "./kpiRecords";

export interface KpiSnapshot {
  period: string;
  production: number;
  collections: number;
  overheadPercentage: number;
  updatedAt: string;
}

export type KpiConflictStrategy = "newest-wins";

export interface AppPreference {
  key: string;
  value: string;
  updatedAt: string;
}

export interface ImportJob {
  id?: number;
  source: "softdent" | "quickbooks" | "practice-central";
  status: "queued" | "running" | "done" | "error";
  startedAt: string;
  finishedAt?: string;
  message?: string;
}

export interface SyncQueueItem {
  id?: number;
  mutation: "admin-refresh";
  payload: string;
  status: "queued" | "failed";
  attempts: number;
  createdAt: string;
  updatedAt: string;
  lastError?: string;
}

class BrowserDb extends Dexie {
  kpiSnapshots!: Table<KpiSnapshot, string>;
  kpiRecords!: Table<KpiRecord, string>;
  preferences!: Table<AppPreference, string>;
  importJobs!: Table<ImportJob, number>;
  syncQueue!: Table<SyncQueueItem, number>;

  constructor() {
    super("newridgeFinancialBrowserDb");
    this.version(1).stores({
      kpiSnapshots: "period, updatedAt",
      preferences: "key, updatedAt",
      importJobs: "++id, source, status, startedAt, finishedAt",
    });
    this.version(2).stores({
      kpiSnapshots: "period, updatedAt",
      preferences: "key, updatedAt",
      importJobs: "++id, source, status, startedAt, finishedAt",
      syncQueue: "++id, mutation, status, attempts, updatedAt",
    });
    this.version(3).stores({
      kpiSnapshots: "period, updatedAt",
      kpiRecords: "id, period, updatedAt, createdAt",
      preferences: "key, updatedAt",
      importJobs: "++id, source, status, startedAt, finishedAt",
      syncQueue: "++id, mutation, status, attempts, updatedAt",
    });
    this.version(4).stores({
      kpiSnapshots: "period, updatedAt",
      kpiRecords: "id, period, updated_at, created_at",
      preferences: "key, updatedAt",
      importJobs: "++id, source, status, startedAt, finishedAt",
      syncQueue: "++id, mutation, status, attempts, updatedAt",
    });
  }
}

export const db = new BrowserDb();

export function normalizeIsoDate(value: string | undefined): number {
  if (!value) return 0;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function resolveKpiConflict(local: KpiSnapshot | undefined, incoming: KpiSnapshot): KpiSnapshot {
  if (!local) {
    return incoming;
  }
  return normalizeIsoDate(incoming.updatedAt) >= normalizeIsoDate(local.updatedAt) ? incoming : local;
}

export async function mergeKpiSnapshots(items: KpiSnapshot[], strategy: KpiConflictStrategy = "newest-wins"): Promise<void> {
  if (!items.length) return;

  await withWebLock("kpiSnapshots-write", async () => {
    await db.transaction("rw", db.kpiSnapshots, async () => {
      const periods = Array.from(new Set(items.map((item) => item.period)));
      const existingRows = await db.kpiSnapshots.bulkGet(periods);
      const existingByPeriod = new Map<string, KpiSnapshot>();
      for (const row of existingRows) {
        if (row) {
          existingByPeriod.set(row.period, row);
        }
      }

      const resolved = items.map((item) => {
        if (strategy === "newest-wins") {
          return resolveKpiConflict(existingByPeriod.get(item.period), item);
        }
        return item;
      });

      await db.kpiSnapshots.bulkPut(resolved);
    });
  });
  await setPreference("lastSyncAt", new Date().toISOString());
  broadcastBrowserSyncMessage(createBrowserSyncMessage("kpis-updated"));
}

export async function upsertKpiSnapshots(items: KpiSnapshot[]): Promise<void> {
  await mergeKpiSnapshots(items, "newest-wins");
}

export async function listKpiSnapshots(): Promise<KpiSnapshot[]> {
  return db.kpiSnapshots.orderBy("period").toArray();
}

export async function getPreference(key: string): Promise<string | undefined> {
  const row = await db.preferences.get(key);
  return row?.value;
}

export async function setPreference(key: string, value: string): Promise<void> {
  await withWebLock("preferences-write", async () => {
    await db.preferences.put({
      key,
      value,
      updatedAt: new Date().toISOString(),
    });
  });
  broadcastBrowserSyncMessage(createBrowserSyncMessage("preferences-updated"));
}

export async function addImportJob(job: Omit<ImportJob, "id">): Promise<number> {
  const id = await withWebLock("importJobs-write", async () => db.importJobs.add(job));
  broadcastBrowserSyncMessage(createBrowserSyncMessage("import-jobs-updated"));
  return id;
}

export async function updateImportJob(id: number, patch: Partial<ImportJob>): Promise<void> {
  await withWebLock("importJobs-write", async () => {
    await db.importJobs.update(id, patch);
  });
  broadcastBrowserSyncMessage(createBrowserSyncMessage("import-jobs-updated"));
}

export async function listImportJobs(limit = 20): Promise<ImportJob[]> {
  return db.importJobs.orderBy("id").reverse().limit(limit).toArray();
}

export async function enqueueSyncMutation(mutation: SyncQueueItem["mutation"], payload: string, errorMessage?: string): Promise<number> {
  const now = new Date().toISOString();
  const id = await withWebLock("syncQueue-write", async () =>
    db.syncQueue.add({
      mutation,
      payload,
      status: "queued",
      attempts: 0,
      createdAt: now,
      updatedAt: now,
      lastError: errorMessage,
    }),
  );
  broadcastBrowserSyncMessage(createBrowserSyncMessage("import-jobs-updated"));
  return id;
}

export async function listQueuedSyncMutations(mutation?: SyncQueueItem["mutation"]): Promise<SyncQueueItem[]> {
  const rows = mutation ? await db.syncQueue.where("mutation").equals(mutation).toArray() : await db.syncQueue.toArray();
  return rows.filter((row) => row.status === "queued" || row.status === "failed");
}

export async function deleteSyncQueueItem(id: number): Promise<void> {
  await withWebLock("syncQueue-write", async () => {
    await db.syncQueue.delete(id);
  });
  broadcastBrowserSyncMessage(createBrowserSyncMessage("import-jobs-updated"));
}

export async function markSyncQueueItemFailed(id: number, message: string): Promise<void> {
  await withWebLock("syncQueue-write", async () => {
    const row = await db.syncQueue.get(id);
    if (!row) return;
    await db.syncQueue.update(id, {
      status: "failed",
      attempts: row.attempts + 1,
      updatedAt: new Date().toISOString(),
      lastError: message,
    });
  });
  broadcastBrowserSyncMessage(createBrowserSyncMessage("import-jobs-updated"));
}

export async function countQueuedSyncMutations(): Promise<number> {
  const rows = await listQueuedSyncMutations();
  return rows.length;
}

export async function listBackupKpiSnapshots(): Promise<KpiSnapshot[]> {
  return db.kpiSnapshots.orderBy("period").toArray();
}

export async function listBackupPreferences(): Promise<AppPreference[]> {
  return db.preferences.orderBy("key").toArray();
}

export async function listBackupImportJobs(): Promise<ImportJob[]> {
  return db.importJobs.orderBy("id").toArray();
}

export async function replaceBackupData(data: {
  kpiSnapshots: KpiSnapshot[];
  preferences: AppPreference[];
  importJobs: ImportJob[];
}): Promise<void> {
  await withWebLock("browser-backup-restore", async () => {
    await db.transaction("rw", db.kpiSnapshots, db.preferences, db.importJobs, async () => {
      await Promise.all([db.kpiSnapshots.clear(), db.preferences.clear(), db.importJobs.clear()]);
      await Promise.all([
        db.kpiSnapshots.bulkPut(data.kpiSnapshots),
        db.preferences.bulkPut(data.preferences),
        db.importJobs.bulkPut(data.importJobs),
      ]);
    });
  });
  broadcastBrowserSyncMessage(createBrowserSyncMessage("backup-restored"));
}

export async function putKpiRecord(record: KpiRecord): Promise<void> {
  await withWebLock("kpiRecords-write", async () => {
    await db.kpiRecords.put(record);
  });
  broadcastBrowserSyncMessage(createBrowserSyncMessage("kpis-updated"));
}

export async function getKpiRecordRow(id: string): Promise<KpiRecord | undefined> {
  return db.kpiRecords.get(id);
}

export async function listKpiRecordRows(): Promise<KpiRecord[]> {
  return db.kpiRecords.orderBy("updated_at").reverse().toArray();
}

export async function deleteKpiRecordRow(id: string): Promise<void> {
  await withWebLock("kpiRecords-write", async () => {
    await db.kpiRecords.delete(id);
  });
  broadcastBrowserSyncMessage(createBrowserSyncMessage("kpis-updated"));
}

export async function clearKpiRecordRows(): Promise<void> {
  await withWebLock("kpiRecords-write", async () => {
    await db.kpiRecords.clear();
  });
  broadcastBrowserSyncMessage(createBrowserSyncMessage("kpis-updated"));
}
