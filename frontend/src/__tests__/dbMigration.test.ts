import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { countQueuedSyncMutations, db, enqueueSyncMutation, getPreference, listKpiSnapshots } from "../db";
import { createKpiRecord, listKpiRecords } from "../kpiRecords";

function deleteIndexedDb(name: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.deleteDatabase(name);
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
    request.onblocked = () => reject(new Error("Delete blocked"));
  });
}

async function createLegacyV1Database(): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    const request = indexedDB.open("newridgeFinancialBrowserDb", 1);

    request.onupgradeneeded = () => {
      const database = request.result;
      const kpiSnapshots = database.createObjectStore("kpiSnapshots", {
        keyPath: "period",
      });
      kpiSnapshots.createIndex("updatedAt", "updatedAt", { unique: false });

      const preferences = database.createObjectStore("preferences", {
        keyPath: "key",
      });
      preferences.createIndex("updatedAt", "updatedAt", { unique: false });

      const importJobs = database.createObjectStore("importJobs", {
        keyPath: "id",
        autoIncrement: true,
      });
      importJobs.createIndex("source", "source", { unique: false });
      importJobs.createIndex("status", "status", { unique: false });
      importJobs.createIndex("startedAt", "startedAt", { unique: false });
      importJobs.createIndex("finishedAt", "finishedAt", { unique: false });
    };

    request.onsuccess = () => {
      const database = request.result;
      const tx = database.transaction(["kpiSnapshots", "preferences", "importJobs"], "readwrite");
      tx.objectStore("kpiSnapshots").put({
        period: "2026-05",
        production: 100,
        collections: 95,
        overheadPercentage: 26,
        updatedAt: "2026-05-22T00:00:00.000Z",
      });
      tx.objectStore("preferences").put({
        key: "theme",
        value: "light",
        updatedAt: "2026-05-22T00:00:00.000Z",
      });
      tx.oncomplete = () => {
        database.close();
        resolve();
      };
      tx.onerror = () => reject(tx.error);
    };

    request.onerror = () => reject(request.error);
  });
}

describe("db migration compatibility", () => {
  beforeEach(async () => {
    db.close();
    await deleteIndexedDb("newridgeFinancialBrowserDb");
  });

  afterEach(async () => {
    db.close();
    await deleteIndexedDb("newridgeFinancialBrowserDb");
  });

  it("opens legacy v1 data and adds v2 sync queue without losing records", async () => {
    await createLegacyV1Database();

    await db.open();

    const kpis = await listKpiSnapshots();
    const theme = await getPreference("theme");

    expect(kpis).toHaveLength(1);
    expect(kpis[0].period).toBe("2026-05");
    expect(theme).toBe("light");

    await enqueueSyncMutation("admin-refresh", "{}");
    const queuedCount = await countQueuedSyncMutations();
    expect(queuedCount).toBe(1);

    await createKpiRecord({
      period: "2026-06",
      production: 140000,
      collections: 130000,
      overhead_percentage: 24,
    });

    const localRecords = await listKpiRecords();
    expect(localRecords).toHaveLength(1);
  });
});
