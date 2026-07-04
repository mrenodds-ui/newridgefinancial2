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

  async function buildCloseoutRunbook(snapshot) {
    const [health, closeout, automation] = await Promise.all([
      getIntegrationHealth().catch(() => null),
      getDailyCloseout().catch(() => null),
      getAutomationRegistry().catch(() => null),
    ]);
    const journal = (snapshot && snapshot.journalPostingQueue) || {};
    const items = Array.isArray(journal.items) ? journal.items : [];
    const pendingJournal = items.filter((row) => String(row.status || "").toLowerCase().includes("pending")).length;
    const fin = snapshot && snapshot.dashboards && snapshot.dashboards.financial;
    let reconciliation = null;
    if (typeof MonthEndClose !== "undefined" && MonthEndClose.buildReconciliationPayload && snapshot) {
      reconciliation = MonthEndClose.buildReconciliationPayload(snapshot);
    }
    return { health, closeout, automation, journal: { pendingJournal, total: items.length, items: items.slice(0, 8) }, reconciliation, financial: fin || null };
  }

  function formatCloseoutRunbook(payload) {
    if (!payload) return "Closeout runbook unavailable.";
    const lines = ["Month-end / closeout runbook (local review only):", ""];
    if (payload.health) {
      lines.push(formatIntegrationHealth(payload.health));
      lines.push("");
    }
    if (payload.closeout) {
      lines.push(formatDailyCloseout(payload.closeout));
      lines.push("");
    }
    if (payload.reconciliation && payload.reconciliation.checklist) {
      const checklist = payload.reconciliation.checklist;
      lines.push(`Reconciliation checklist (${checklist.period}): ${checklist.summary}`);
      (checklist.items || []).forEach((row) => {
        lines.push(`- [${String(row.status || "").toUpperCase()}] ${row.label}: ${row.detail || ""}`);
      });
      lines.push("");
    }
    lines.push(`Journal posting queue: ${payload.journal?.pendingJournal || 0} pending of ${payload.journal?.total || 0} item(s).`);
    if ((payload.journal?.items || []).length) {
      payload.journal.items.forEach((row) => {
        lines.push(`  · ${row.title || row.id || "Entry"} — ${row.status || "unknown"}${row.amount != null ? ` ($${row.amount})` : ""}`);
      });
      lines.push("");
    }
    if (payload.automation) {
      lines.push(formatAutomationRegistry(payload.automation));
      lines.push("");
    }
    lines.push("Next safe actions:");
    lines.push("1. Refresh imports if any integration is degraded.");
    lines.push("2. Review journal queue on Accounting Documents.");
    lines.push("3. Run readiness check before staff handoff.");
    lines.push("4. Say “build support bundle” if IT needs diagnostics.");
    return lines.join("\n");
  }

  function formatOpsHealthFromSnapshot(snapshot) {
    if (!snapshot) return "Program snapshot unavailable.";
    const lines = ["NR2 integration snapshot (local read-only):", ""];
    const bundle = snapshot.importBundle;
    const diag = bundle && bundle.diagnostics;
    if (diag) {
      const overall = diag.overallStatus || diag.status || "unknown";
      lines.push(`Import bundle: ${String(overall).toUpperCase()}`);
      (diag.datasets || [])
        .filter((row) => row.severity === "critical" && row.status !== "connected")
        .slice(0, 4)
        .forEach((row) => lines.push(`  - ${row.datasetKey}: ${row.status} (${row.detail || "check export"})`));
    } else {
      lines.push("Import bundle: diagnostics unavailable — refresh imports.");
    }
    const jq = snapshot.journalPostingQueue || {};
    const jm = jq.metrics || {};
    lines.push(
      `Journal queue: ${jm.pendingReview != null ? jm.pendingReview : jm.pending || 0} pending · ${jm.ready != null ? jm.ready : jm.approved || 0} approved`,
    );
    const docs = snapshot.documents || {};
    const sc = docs.sourceCounts || {};
    lines.push(
      `Documents: ${docs.queueCount || 0} rows (QB ${sc.quickbooks || 0}, SD ${sc.softdent || 0}, OCR ${sc.ocr || 0}, manual ${sc.manual || 0})`,
    );
    if (Array.isArray(snapshot.runtimeIssues) && snapshot.runtimeIssues.length) {
      lines.push(`Runtime issues: ${snapshot.runtimeIssues.length} (see support bundle for detail)`);
    }
    lines.push("", "Actions: Refresh imports · Review journal queue · Export support bundle");
    return lines.join("\n");
  }

  return {
    getIntegrationHealth,
    getAutomationRegistry,
    buildSupportBundle,
    getFinancialReports,
    getDailyCloseout,
    getProgramHelp,
    buildCloseoutRunbook,
    formatIntegrationHealth,
    formatOpsHealthFromSnapshot,
    formatAutomationRegistry,
    formatDailyCloseout,
    formatCloseoutRunbook,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = PortalOps;
}
if (typeof globalThis !== "undefined") {
  globalThis.PortalOps = PortalOps;
}
