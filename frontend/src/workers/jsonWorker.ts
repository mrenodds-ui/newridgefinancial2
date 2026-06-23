/// <reference lib="webworker" />

import { expose } from "comlink";

import { type KpiResponse, kpiResponseSchema } from "../api/schemas";

export interface JsonWorkerApi {
  parseKpi(payload: unknown): Promise<KpiResponse>;
}

const api: JsonWorkerApi = {
  async parseKpi(payload: unknown): Promise<KpiResponse> {
    return kpiResponseSchema.parse(payload);
  },
};

expose(api);
