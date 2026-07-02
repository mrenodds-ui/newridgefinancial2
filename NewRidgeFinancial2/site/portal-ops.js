/**
 * Portal-derived NR2 ops APIs — integration health, support bundle, closeout, reports.
 */
const PortalOps = (function () {
  function desktop() {
    return typeof DesktopBridge !== "undefined" ? DesktopBridge : window.DesktopBridge;
  }

  async function fetchLoopbackJson(path, options) {
    const url = `http://127.0.0.1:8765${path}`;
    const port = typeof window !== "undefined" && window.location && window.location.port;
    const base =
      port && port !== "8765"
        ? `${window.location.protocol}//${window.location.hostname}:8765${path}`
        : url;
    const resp = await fetch(base, options || { cache: "no-store" });
    if (!resp.ok) throw new Error(`HTTP ${resp.status} for ${path}`);
    return resp.json();
  }

  async function getIntegrationHealth() {
    const db = desktop();
    if (db && db.hasDesktopApi && db.hasDesktopApi() && typeof db.getIntegrationHealth === "function") {
      return db.getIntegrationHealth();
    }
    return fetchLoopbackJson("/api/integration-health");
  }

  async function getAutomationRegistry() {
    const db = desktop();
    if (db && db.hasDesktopApi && db.hasDesktopApi() && typeof db.getAutomationRegistry === "function") {
      return db.getAutomationRegistry();
    }
    return fetchLoopbackJson("/api/automation-registry");
  }

  async function buildSupportBundle(note) {
    const db = desktop();
    if (db && db.hasDesktopApi && db.hasDesktopApi() && typeof db.buildSupportBundle === "function") {
      return db.buildSupportBundle(String(note || ""));
    }
    return fetchLoopbackJson("/api/support-bundle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note: String(note || "") }),
    });
  }

  async function getFinancialReports(syncExports) {
    const db = desktop();
    if (db && db.hasDesktopApi && db.hasDesktopApi() && typeof db.getFinancialReports === "function") {
      return db.getFinancialReports(Boolean(syncExports));
    }
    const q = syncExports ? "?syncExports=1" : "";
    return fetchLoopbackJson(`/api/financial-reports${q}`);
  }

  async function getDailyCloseout() {
    const db = desktop();
    if (db && db.hasDesktopApi && db.hasDesktopApi() && typeof db.getDailyCloseout === "function") {
      return db.getDailyCloseout();
    }
    return fetchLoopbackJson("/api/daily-closeout");
  }

  async function getProgramHelp(query) {
    const db = desktop();
    if (db && db.hasDesktopApi && db.hasDesktopApi() && typeof db.getProgramHelp === "function") {
      return db.getProgramHelp(String(query || ""));
    }
    return { text: "Program help requires the NR2 desktop bridge.", match: null };
  }

  function formatIntegrationHealth(snapshot) {
    if (!snapshot || !snapshot.integrations) return "Integration health unavailable.";
    const lines = [
      `Integration health: ${String(snapshot.status || "unknown").toUpperCase()} (${snapshot.ok_count || 0}/${snapshot.enabled_count || 0} OK).`,
      "",
    ];
    (snapshot.integrations || []).forEach((row) => {
      const flag = row.ok ? "OK" : String(row.status || "FAIL").toUpperCase();
      lines.push(`- ${row.label}: ${flag} — ${row.detail || ""}`);
      if (!row.ok && row.actionHint) lines.push(`  Next: ${row.actionHint}`);
    });
    return lines.join("\n");
  }

  function formatAutomationRegistry(payload) {
    if (!payload || !payload.jobs) return "Automation registry unavailable.";
    const lines = [`Automation jobs (${payload.summary?.total || 0} registered):`, ""];
    (payload.jobs || []).forEach((job) => {
      const last = job.lastRun && job.lastRun.ranAt ? ` last ${job.lastRun.ranAt}` : " never run";
      lines.push(`- ${job.label}: ${job.status || "unknown"}${last}`);
      if (job.description) lines.push(`  ${job.description}`);
    });
    return lines.join("\n");
  }

  function formatDailyCloseout(payload) {
    if (typeof DailyCloseout !== "undefined" && DailyCloseout.formatText) {
      return DailyCloseout.formatText(payload);
    }
    if (!payload || !payload.items) return "Daily closeout unavailable.";
    const lines = [`Daily closeout: ${String(payload.overall || "").toUpperCase()} — ${payload.summary || ""}`, ""];
    (payload.items || []).forEach((row) => {
      lines.push(`- [${String(row.status || "").toUpperCase()}] ${row.label}: ${row.detail || ""}`);
    });
    return lines.join("\n");
  }

  return {
    getIntegrationHealth,
    getAutomationRegistry,
    buildSupportBundle,
    getFinancialReports,
    getDailyCloseout,
    getProgramHelp,
    formatIntegrationHealth,
    formatAutomationRegistry,
    formatDailyCloseout,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = PortalOps;
}
if (typeof globalThis !== "undefined") {
  globalThis.PortalOps = PortalOps;
}
