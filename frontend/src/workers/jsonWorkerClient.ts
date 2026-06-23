import { wrap } from "comlink";

import { type KpiResponse, kpiResponseSchema } from "../api/schemas";
import type { JsonWorkerApi } from "./jsonWorker";

export async function parseKpiPayload(payload: unknown): Promise<KpiResponse> {
  if (typeof Worker === "undefined") {
    return kpiResponseSchema.parse(payload);
  }

  const worker = new Worker(new URL("./jsonWorker.ts", import.meta.url), {
    type: "module",
  });
  try {
    const api = wrap<JsonWorkerApi>(worker);
    return await api.parseKpi(payload);
  } finally {
    worker.terminate();
  }
}
