import { describe, expect, it } from "vitest";

import { healthSchema, kpiResponseSchema } from "../api/schemas";

describe("zod schemas", () => {
  it("validates kpi response", () => {
    const parsed = kpiResponseSchema.parse({
      items: [
        {
          period: "2026-05",
          production: 10,
          collections: 9,
          overhead_percentage: 30,
        },
      ],
    });
    expect(parsed.items[0].period).toBe("2026-05");
  });

  it("validates health response", () => {
    const parsed = healthSchema.parse({
      status: "ok",
      service: "New Ridge Family Financial",
    });
    expect(parsed.status).toBe("ok");
  });

  it("accepts the minimal live health response", () => {
    const parsed = healthSchema.parse({
      status: "ok",
    });
    expect(parsed.service).toBe("New Ridge Family Financial");
  });
});
