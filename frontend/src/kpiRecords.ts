import { z } from "zod";

import { clearKpiRecordRows, deleteKpiRecordRow, getKpiRecordRow, listKpiRecordRows, putKpiRecord } from "./db";

const periodPattern = /^\d{4}-(0[1-9]|1[0-2])$/;

export const kpiRecordFormSchema = z.object({
  period: z.string().trim().regex(periodPattern, "Use YYYY-MM format."),
  production: z.coerce.number().finite().nonnegative("Production must be 0 or more."),
  collections: z.coerce.number().finite().nonnegative("Collections must be 0 or more."),
  overhead_percentage: z.coerce.number().finite().min(0, "Overhead must be at least 0.").max(100, "Overhead must be 100 or less."),
});

export const kpiRecordSchema = kpiRecordFormSchema.extend({
  id: z.string().min(1),
  created_at: z.string().datetime(),
  updated_at: z.string().datetime(),
});

export type KpiRecordFormValues = z.infer<typeof kpiRecordFormSchema>;
export type KpiRecord = z.infer<typeof kpiRecordSchema>;

function createRecordId(): string {
  if (typeof globalThis.crypto?.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }

  return `kpi-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export async function createKpiRecord(values: KpiRecordFormValues): Promise<KpiRecord> {
  const now = new Date().toISOString();
  const record = kpiRecordSchema.parse({
    ...kpiRecordFormSchema.parse(values),
    id: createRecordId(),
    created_at: now,
    updated_at: now,
  });

  await putKpiRecord(record);
  return record;
}

export async function getKpiRecord(id: string): Promise<KpiRecord | undefined> {
  const record = await getKpiRecordRow(id);
  return record ? kpiRecordSchema.parse(record) : undefined;
}

export async function listKpiRecords(): Promise<KpiRecord[]> {
  const records = await listKpiRecordRows();
  return records.map((record) => kpiRecordSchema.parse(record));
}

export async function updateKpiRecord(id: string, values: KpiRecordFormValues): Promise<KpiRecord> {
  const existing = await getKpiRecord(id);
  if (!existing) {
    throw new Error("KPI record not found.");
  }

  const updated = kpiRecordSchema.parse({
    ...existing,
    ...kpiRecordFormSchema.parse(values),
    updated_at: new Date().toISOString(),
  });

  await putKpiRecord(updated);
  return updated;
}

export async function deleteKpiRecord(id: string): Promise<void> {
  await deleteKpiRecordRow(id);
}

export async function clearKpiRecords(): Promise<void> {
  await clearKpiRecordRows();
}
