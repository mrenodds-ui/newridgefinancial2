import { beforeEach, describe, expect, it } from "vitest";

import { db, mergeKpiSnapshots, resolveKpiConflict } from "../db";

describe("kpi conflict handling", () => {
  beforeEach(async () => {
    db.close();
    await db.delete();
    await db.open();
  });

  it("prefers the newest timestamp for same-period snapshots", () => {
    const local = {
      period: "2026-05",
      production: 100,
      collections: 90,
      overheadPercentage: 30,
      updatedAt: "2026-05-23T01:00:00.000Z",
    };
    const incomingOlder = {
      ...local,
      production: 120,
      updatedAt: "2026-05-23T00:59:00.000Z",
    };
    const incomingNewer = {
      ...local,
      production: 130,
      updatedAt: "2026-05-23T01:01:00.000Z",
    };

    expect(resolveKpiConflict(local, incomingOlder).production).toBe(100);
    expect(resolveKpiConflict(local, incomingNewer).production).toBe(130);
  });

  it("keeps newer existing rows during merge", async () => {
    await db.kpiSnapshots.put({
      period: "2026-05",
      production: 145,
      collections: 131,
      overheadPercentage: 24,
      updatedAt: "2026-05-23T05:00:00.000Z",
    });

    await mergeKpiSnapshots([
      {
        period: "2026-05",
        production: 125,
        collections: 119,
        overheadPercentage: 27,
        updatedAt: "2026-05-23T04:00:00.000Z",
      },
    ]);

    const row = await db.kpiSnapshots.get("2026-05");
    expect(row?.production).toBe(145);
  });
});
