import { beforeEach, describe, expect, it } from "vitest";

import {
  createBrowserBackup,
  createBrowserBackupFileName,
  parseBrowserBackup,
  restoreBrowserBackup,
  serializeBrowserBackup,
} from "../browser/browserBackup";
import { type AppPreference, type ImportJob, type KpiSnapshot, db } from "../db";

describe("browser backup", () => {
  beforeEach(async () => {
    db.close();
    await db.delete();
    await db.open();
  });

  it("serializes and parses a backup payload", async () => {
    await db.kpiSnapshots.bulkPut([
      {
        period: "2026-05",
        production: 100,
        collections: 90,
        overheadPercentage: 30,
        updatedAt: "2026-05-23T00:00:00.000Z",
      },
    ] satisfies KpiSnapshot[]);
    await db.preferences.bulkPut([
      {
        key: "theme",
        value: "light",
        updatedAt: "2026-05-23T00:00:00.000Z",
      },
    ] satisfies AppPreference[]);
    await db.importJobs.bulkPut([
      {
        source: "softdent",
        status: "done",
        startedAt: "2026-05-23T00:00:00.000Z",
        finishedAt: "2026-05-23T00:00:00.000Z",
      },
    ] satisfies ImportJob[]);

    const backup = await createBrowserBackup();
    const serialized = serializeBrowserBackup(backup);
    const parsed = parseBrowserBackup(serialized);

    expect(parsed.version).toBe(1);
    expect(parsed.kpiSnapshots).toHaveLength(1);
    expect(parsed.preferences).toHaveLength(1);
    expect(parsed.importJobs).toHaveLength(1);
    expect(createBrowserBackupFileName(new Date("2026-05-23T00:00:00.000Z"))).toBe("newridge-financial-backup-2026-05-23.json");
  });

  it("restores a backup into indexeddb", async () => {
    await restoreBrowserBackup({
      version: 1,
      exportedAt: "2026-05-23T00:00:00.000Z",
      kpiSnapshots: [
        {
          period: "2026-04",
          production: 120,
          collections: 110,
          overheadPercentage: 25,
          updatedAt: "2026-05-23T00:00:00.000Z",
        },
      ],
      preferences: [
        {
          key: "theme",
          value: "dark",
          updatedAt: "2026-05-23T00:00:00.000Z",
        },
      ],
      importJobs: [
        {
          source: "quickbooks",
          status: "done",
          startedAt: "2026-05-23T00:00:00.000Z",
          finishedAt: "2026-05-23T00:00:00.000Z",
          message: "restored",
        },
      ],
    });

    const kpis = await db.kpiSnapshots.toArray();
    const preferences = await db.preferences.toArray();
    const jobs = await db.importJobs.toArray();

    expect(kpis).toHaveLength(1);
    expect(preferences).toHaveLength(1);
    expect(jobs).toHaveLength(1);
    expect(preferences[0].value).toBe("dark");
  });
});
