/**
 * Single-flight program snapshot cache keyed to import coordinator version.
 */
const SnapshotStore = (function () {
  let snapshot = null;
  let snapshotAt = 0;
  let importVersion = 0;
  let inFlight = null;
  let invalidationReason = null;
  const TTL_MS = 45000;

  function invalidate(reason) {
    invalidationReason = reason || "manual";
    snapshot = null;
    snapshotAt = 0;
  }

  function noteImportVersion(version) {
    if (typeof version === "number" && version !== importVersion) {
      importVersion = version;
      invalidate("import-version");
    }
  }

  async function build(builder) {
    if (typeof builder !== "function") return null;
    if (inFlight) return inFlight;
    inFlight = Promise.resolve()
      .then(() => builder())
      .then((built) => {
        snapshot = built;
        snapshotAt = Date.now();
        invalidationReason = null;
        return built;
      })
      .finally(() => {
        inFlight = null;
      });
    return inFlight;
  }

  async function get(builder, options) {
    const force = Boolean(options && options.force);
    const now = Date.now();
    if (!force && snapshot && now - snapshotAt < TTL_MS) return snapshot;
    if (inFlight) return inFlight;
    return build(builder);
  }

  function peek() {
    return snapshot;
  }

  function status() {
    return {
      hasSnapshot: Boolean(snapshot),
      snapshotAt,
      importVersion,
      invalidationReason,
      inFlight: Boolean(inFlight),
    };
  }

  return {
    invalidate,
    noteImportVersion,
    get,
    build,
    peek,
    status,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = SnapshotStore;
}
if (typeof window !== "undefined") {
  window.SnapshotStore = SnapshotStore;
}
if (typeof globalThis !== "undefined") {
  globalThis.SnapshotStore = SnapshotStore;
}
