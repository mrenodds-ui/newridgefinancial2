import { beforeEach, describe, expect, it } from "vitest";

import { db, getPreference, listKpiSnapshots, setPreference, upsertKpiSnapshots } from "../db";

describe("db helpers", () => {
  beforeEach(async () => {
    db.close();
    await db.delete();
    await db.open();
  });

  it("writes and reads kpi snapshots", async () => {
    await upsertKpiSnapshots([
      {
        period: "2026-05",
        production: 100,
        collections: 90,
        overheadPercentage: 42,
        updatedAt: new Date().toISOString(),
      },
    ]);

    const rows = await listKpiSnapshots();
    expect(rows).toHaveLength(1);
    expect(rows[0].period).toBe("2026-05");
  });

  it("persists preferences", async () => {
    await setPreference("theme", "dark");
    const value = await getPreference("theme");
    expect(value).toBe("dark");
  });
});
