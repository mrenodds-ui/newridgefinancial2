import { afterEach, describe, expect, it, vi } from "vitest";

import {
  broadcastBrowserSyncMessage,
  createBrowserSyncMessage,
  createBrowserSyncSubscriber,
  createCacheInvalidatedMessage,
  createSessionClearedMessage,
} from "../browser/crossTabSync";
import { requestPersistentStorage } from "../browser/storagePersistence";
import { withWebLock } from "../browser/webLocks";
import { parseKpiPayload } from "../workers/jsonWorkerClient";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("browser helpers", () => {
  it("creates broadcast messages", () => {
    const message = createBrowserSyncMessage("admin-refreshed");
    expect(message.topic).toBe("admin-refreshed");
    expect(message.timestamp).toContain("T");
  });

  it("creates typed cache/session broadcast messages", () => {
    expect(createCacheInvalidatedMessage().topic).toBe("cache-invalidated");
    expect(createSessionClearedMessage().topic).toBe("session-cleared");
  });

  it("falls back when broadcast channels are unavailable", () => {
    const channel = createBrowserSyncSubscriber(() => undefined, "sync", {} as typeof globalThis);
    expect(channel.supported).toBe(false);
    expect(channel.post(createBrowserSyncMessage("kpis-updated"))).toBe(false);
    channel.close();
  });

  it("broadcasts through an injected channel when available", () => {
    const posted: unknown[] = [];
    let closed = false;

    class FakeBroadcastChannel {
      onmessage: ((event: MessageEvent<unknown>) => void) | null = null;
      constructor(public name: string) {}
      postMessage(message: unknown) {
        posted.push(message);
      }
      close() {
        closed = true;
      }
    }

    const result = broadcastBrowserSyncMessage(createBrowserSyncMessage("import-jobs-updated"), "sync", {
      BroadcastChannel: FakeBroadcastChannel,
    } as typeof globalThis);

    expect(result).toBe(true);
    expect(posted).toHaveLength(1);
    expect(closed).toBe(true);
  });

  it("returns unsupported persistent storage result without storage manager", async () => {
    const result = await requestPersistentStorage(undefined);
    expect(result).toEqual({
      supported: false,
      persisted: false,
      granted: false,
    });
  });

  it("runs a lock-protected task when locks are unavailable", async () => {
    const result = await withWebLock("jobs", () => "done", undefined);
    expect(result).toBe("done");
  });

  it("uses a lock manager when available", async () => {
    const request = vi.fn(async (_name: string, options: { mode: string }, callback: () => string) => {
      expect(options.mode).toBe("exclusive");
      return callback();
    });

    const result = await withWebLock("jobs", () => "done", {
      request,
    } as unknown as LockManager);

    expect(result).toBe("done");
    expect(request).toHaveBeenCalledTimes(1);
  });

  it("falls back to direct validation when Worker is unavailable", async () => {
    vi.stubGlobal("Worker", undefined);
    const payload = {
      items: [
        {
          period: "2026-05",
          production: 10,
          collections: 9,
          overhead_percentage: 3,
        },
      ],
    };

    const result = await parseKpiPayload(payload);
    expect(result.items).toHaveLength(1);
    expect(result.items[0].period).toBe("2026-05");
  });
});
