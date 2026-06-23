import { describe, expect, it, vi } from "vitest";

import { getAdminRefreshSyncTag, registerAdminRefreshBackgroundSync, supportsBackgroundSync } from "../offline/backgroundSync";

describe("background sync helper", () => {
  it("returns false when sync API is unavailable", async () => {
    const registration = {} as ServiceWorkerRegistration;
    expect(supportsBackgroundSync(registration)).toBe(false);
    await expect(registerAdminRefreshBackgroundSync(registration)).resolves.toBe(false);
  });

  it("registers background sync when supported", async () => {
    const register = vi.fn().mockResolvedValue(undefined);
    const registration = {
      sync: {
        register,
      },
    } as unknown as ServiceWorkerRegistration;

    expect(supportsBackgroundSync(registration)).toBe(true);
    await expect(registerAdminRefreshBackgroundSync(registration)).resolves.toBe(true);
    expect(register).toHaveBeenCalledWith(getAdminRefreshSyncTag());
  });
});
