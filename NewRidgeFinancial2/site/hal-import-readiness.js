/**
 * HAL import-awareness guard — Moonshot Phase C (server-backed, pre-LLM hard block).
 */
const HalImportReadiness = (function () {
  const FINANCIAL_INTENT =
    /\b(revenue|collection|receivable|a\/r|\bar\b|profit|loss|ebitda|tax|posting|ledger|reconcil|month[- ]end|cash flow|forecast|project|production|quickbooks|financial|aging|claim status)\b/i;
  const FINANCIAL_INTENT_EXTENDED =
    /\b(owe|balance|paid|bill|money|amount\s*due|outstanding|receivable|insurance|eob|era)\b/i;

  function isFinancialQuery(query) {
    const q = String(query || "");
    return FINANCIAL_INTENT.test(q) || FINANCIAL_INTENT_EXTENDED.test(q);
  }

  function staleBannerHtml(readiness) {
    const level = (readiness && readiness.level) || "unknown";
    const loaded = (readiness && readiness.loadedAt) || "unknown";
    return (
      `<div class="hal-stale-data-warning" role="alert">` +
      `<strong>DATA NOT CURRENT — DO NOT ACT</strong> ` +
      `(import level: ${level}, loaded: ${loaded}). Refresh imports before financial decisions.` +
      `</div>`
    );
  }

  function wrapWithStaleBanner(text, readiness) {
    const body = String(text || "");
    if (!readiness || readiness.level === "fresh") return body;
    return staleBannerHtml(readiness) + body;
  }

  async function fetchGuard(query) {
    const db = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
    if (db && typeof db.fetchHalImportGuard === "function") {
      return db.fetchHalImportGuard(query);
    }
    return { blocked: false };
  }

  async function guardBeforeModel(query, ctx) {
    const q = String(query || "").trim();
    if (!q || !isFinancialQuery(q)) return null;
    const guard = await fetchGuard(q);
    if (!guard || !guard.blocked) return null;
    const readiness = guard.readiness || {};
    const text =
      "**DATA NOT CURRENT — DO NOT ACT**\n\n" +
      (guard.message ||
        "Import data is not fresh. HAL cannot provide financial advice until imports are refreshed.") +
      (readiness.error ? `\n\nDetail: ${readiness.error}` : "");
    return {
      text: wrapWithStaleBanner(text, readiness),
      lane: "readiness · blocked",
      actions: [{ label: "Refresh imports", query: "Refresh imports", action: { type: "refreshImports" } }],
      intent: "readiness:import-stale",
      plan: { questionType: "readiness", tools: [], useModelEnhancement: false },
      toolResults: {},
      selfCheck: { pass: true, issues: [], importBlocked: true },
    };
  }

  function buildImportReadinessContext(readiness) {
    if (!readiness) return "";
    const lines = [
      "[IMPORT_CONTEXT]",
      `Status: ${String(readiness.level || "unknown").toUpperCase()}`,
      `LoadedAt: ${readiness.loadedAt || "unknown"}`,
      `AgeHours: ${readiness.ageHours != null ? readiness.ageHours : "unknown"}`,
      `Ok: ${readiness.ok ? "yes" : "no"}`,
    ];
    if (readiness.error) lines.push(`Error: ${readiness.error}`);
    if (readiness.summary) lines.push(`Summary: ${JSON.stringify(readiness.summary)}`);
    lines.push("You must not provide numeric projections or financial advice when Status is not FRESH.");
    lines.push("[END_IMPORT_CONTEXT]");
    return lines.join("\n");
  }

  return {
    guardBeforeModel,
    wrapWithStaleBanner,
    buildImportReadinessContext,
    fetchGuard,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalImportReadiness;
}
if (typeof window !== "undefined") {
  window.HalImportReadiness = HalImportReadiness;
}
