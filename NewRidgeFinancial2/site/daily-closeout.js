/**
 * Daily closeout checklist (portal-style ops layer on NR2 integration health + reports).
 */
const DailyCloseout = (function () {
  function formatText(payload) {
    if (!payload) return "Daily closeout unavailable.";
    const lines = [
      `Daily closeout (${payload.period || "today"}): ${String(payload.overall || "").toUpperCase()} — ${payload.summary || ""}`,
      "",
    ];
    (payload.items || []).forEach((row) => {
      lines.push(`- [${String(row.status || "").toUpperCase()}] ${row.label}: ${row.detail || ""}`);
    });
    return lines.join("\n");
  }

  async function load() {
    if (typeof PortalOps !== "undefined" && PortalOps.getDailyCloseout) {
      return PortalOps.getDailyCloseout();
    }
    throw new Error("PortalOps is not loaded.");
  }

  return { load, formatText };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = DailyCloseout;
}
if (typeof globalThis !== "undefined") {
  globalThis.DailyCloseout = DailyCloseout;
}
