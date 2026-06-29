/**
 * NR2 runtime issue recorder — surfaces failures instead of silent fallbacks.
 */
const RuntimeIssues = (function () {
  const issues = [];
  const MAX_ISSUES = 40;

  function record(source, error, context) {
    const entry = {
      at: new Date().toISOString(),
      source: String(source || "unknown"),
      message: error && error.message ? String(error.message) : String(error || "unknown error"),
      context: context || null,
    };
    issues.unshift(entry);
    if (issues.length > MAX_ISSUES) issues.length = MAX_ISSUES;
    return entry;
  }

  function list() {
    return issues.slice();
  }

  function latest(source) {
    if (!source) return issues[0] || null;
    return issues.find((item) => item.source === source) || null;
  }

  function clear() {
    issues.length = 0;
  }

  return { record, list, latest, clear };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = RuntimeIssues;
}
if (typeof window !== "undefined") {
  window.RuntimeIssues = RuntimeIssues;
}
if (typeof globalThis !== "undefined") {
  globalThis.RuntimeIssues = RuntimeIssues;
}
