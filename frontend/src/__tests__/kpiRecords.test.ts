import { beforeEach, describe, expect, it } from "vitest";

import { db } from "../db";
import {
  clearKpiRecords,
  createKpiRecord,
  deleteKpiRecord,
  getKpiRecord,
  kpiRecordFormSchema,
  listKpiRecords,
  updateKpiRecord,
} from "../kpiRecords";

describe("local KPI records", () => {
  beforeEach(async () => {
    db.close();
    await db.delete();
    await db.open();
    await clearKpiRecords();
  });

  it("accepts valid record input", () => {
    const parsed = kpiRecordFormSchema.parse({
      period: "2026-05",
      production: 135000,
      collections: 126500,
      overhead_percentage: 26,
    });

    expect(parsed.period).toBe("2026-05");
  });

  it("rejects invalid record input", () => {
    const result = kpiRecordFormSchema.safeParse({
      period: "May 2026",
      production: -1,
      collections: 126500,
      overhead_percentage: 126,
    });

    expect(result.success).toBe(false);
  });

  it("creates, lists, updates, deletes, and persists records", async () => {
    const created = await createKpiRecord({
      period: "2026-05",
      production: 135000,
      collections: 126500,
      overhead_percentage: 26,
    });

    expect(created.id).toBeTruthy();
    expect(created.created_at).toBeTruthy();
    expect(created.updated_at).toBeTruthy();

    let records = await listKpiRecords();
    expect(records).toHaveLength(1);
    expect(records[0].period).toBe("2026-05");

    await db.close();
    await db.open();

    const reopened = await getKpiRecord(created.id);
    expect(reopened?.production).toBe(135000);

    const updated = await updateKpiRecord(created.id, {
      period: "2026-06",
      production: 140000,
      collections: 130000,
      overhead_percentage: 24,
    });

    expect(updated.period).toBe("2026-06");
    expect(updated.created_at).toBe(created.created_at);
    expect(updated.updated_at).not.toBe(created.updated_at);

    records = await listKpiRecords();
    expect(records[0].period).toBe("2026-06");

    await deleteKpiRecord(created.id);
    records = await listKpiRecords();
    expect(records).toHaveLength(0);
  });
});
