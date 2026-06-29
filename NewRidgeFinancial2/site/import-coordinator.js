/**
 * Single-flight import refresh coordinator.
 */
const ImportCoordinator = (function () {
  let inFlight = null;
  let version = 0;
  let lastBundle = null;
  let lastError = null;
  let lastStartedAt = null;
  let lastCompletedAt = null;
  let lastReason = null;
  const listeners = [];

  function onComplete(fn) {
    if (typeof fn === "function") listeners.push(fn);
  }

  function notifyComplete(bundle, err) {
    listeners.forEach((fn) => {
      try {
        fn(bundle, err);
      } catch {
        /* listener optional */
      }
    });
  }

  function status() {
    return {
      version,
      inFlight: Boolean(inFlight),
      lastStartedAt,
      lastCompletedAt,
      lastReason,
      lastError: lastError ? String(lastError.message || lastError) : null,
      hasBundle: Boolean(lastBundle),
    };
  }

  function resolveServices() {
    if (typeof globalThis !== "undefined" && globalThis.Services) return globalThis.Services;
    if (typeof window !== "undefined" && window.Services) return window.Services;
    return null;
  }

  function refresh(options) {
    const reason = (options && options.reason) || "manual";
    if (inFlight) return inFlight;
    lastReason = reason;
    lastStartedAt = new Date().toISOString();
    const Svc = resolveServices();
    if (!Svc || typeof Svc.refreshImports !== "function") {
      const err = new Error("Services.refreshImports unavailable");
      lastError = err;
      if (typeof globalThis !== "undefined" && globalThis.RuntimeIssues) {
        globalThis.RuntimeIssues.record("import-coordinator", err, { reason });
      } else if (typeof window !== "undefined" && window.RuntimeIssues) {
        window.RuntimeIssues.record("import-coordinator", err, { reason });
      }
      return Promise.reject(err);
    }
    inFlight = Svc.refreshImports({ reason })
      .then((bundle) => {
        version += 1;
        lastBundle = bundle;
        lastError = null;
        lastCompletedAt = new Date().toISOString();
        if (typeof globalThis !== "undefined" && globalThis.SnapshotStore) {
          globalThis.SnapshotStore.noteImportVersion(version);
        } else if (typeof window !== "undefined" && window.SnapshotStore) {
          window.SnapshotStore.noteImportVersion(version);
        }
        notifyComplete(bundle, null);
        return bundle;
      })
      .catch((err) => {
        lastError = err;
        lastCompletedAt = new Date().toISOString();
        if (typeof globalThis !== "undefined" && globalThis.RuntimeIssues) {
          globalThis.RuntimeIssues.record("import-coordinator", err, { reason });
        } else if (typeof window !== "undefined" && window.RuntimeIssues) {
          window.RuntimeIssues.record("import-coordinator", err, { reason });
        }
        notifyComplete(null, err);
        throw err;
      })
      .finally(() => {
        inFlight = null;
      });
    return inFlight;
  }

  return {
    refresh,
    onComplete,
    status,
    get version() {
      return version;
    },
    get lastBundle() {
      return lastBundle;
    },
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = ImportCoordinator;
}
if (typeof window !== "undefined") {
  window.ImportCoordinator = ImportCoordinator;
}
if (typeof globalThis !== "undefined") {
  globalThis.ImportCoordinator = ImportCoordinator;
}
