/**
 * Program strength — boot self-heal, repair cycle, and strength reporting.
 */
const ProgramStrength = (function () {
  function desktop() {
    return typeof DesktopBridge !== "undefined" ? DesktopBridge : window.DesktopBridge;
  }

  async function fetchSelfHeal(options) {
    const opts = options || {};
    const db = desktop();
    if (db && db.hasDesktopApi && db.hasDesktopApi() && typeof db.runProgramSelfHeal === "function") {
      return db.runProgramSelfHeal(opts);
    }
    const body = JSON.stringify({
      fullPull: Boolean(opts.fullPull),
      documentsOnly: Boolean(opts.documentsOnly),
      reason: opts.reason || "ui",
    });
    const port = typeof window !== "undefined" && window.location && window.location.port;
    const base =
      port && port !== "8765"
        ? `${window.location.protocol}//${window.location.hostname}:8765/api/self-heal`
        : "http://127.0.0.1:8765/api/self-heal";
    const resp = await fetch(base, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    });
    if (!resp.ok) throw new Error(`Self-heal HTTP ${resp.status}`);
    return resp.json();
  }

  function formatReport(report) {
    if (!report) return "Program self-heal unavailable.";
    if (report.summary) return report.summary;
    if (report.healthText) return report.healthText;
    return `Program self-heal: ${String(report.status || "unknown").toUpperCase()}`;
  }

  async function runSelfHeal(options) {
    const opts = options || {};
    const report = await fetchSelfHeal(opts);
    if (typeof window !== "undefined") {
      try {
        window.dispatchEvent(new CustomEvent("nr2:program-self-heal", { detail: report }));
      } catch {
        /* optional */
      }
    }
    return report;
  }

  async function runBootHeal(ctx) {
    if (typeof sessionStorage !== "undefined" && sessionStorage.getItem("nr2BootSelfHeal") === "1") {
      return null;
    }
    let health = null;
    try {
      if (typeof PortalOps !== "undefined" && PortalOps.getIntegrationHealth) {
        health = await PortalOps.getIntegrationHealth();
      }
    } catch {
      health = null;
    }
    const status = health && String(health.status || "").toLowerCase();
    const needsHeal = !health || status === "degraded" || status === "fail";
    if (!needsHeal) return null;
    const report = await runSelfHeal({ reason: "boot", fullPull: false });
    if (typeof sessionStorage !== "undefined") sessionStorage.setItem("nr2BootSelfHeal", "1");
    if (ctx && typeof ctx.invalidateProgramCaches === "function") ctx.invalidateProgramCaches("boot-self-heal");
    if (ctx && typeof ctx.scheduleHalWidgetRefresh === "function") {
      await ctx.scheduleHalWidgetRefresh().catch(() => {
        /* optional */
      });
    }
    if (ctx && typeof ctx.refreshOpsHealthStatus === "function") {
      await ctx.refreshOpsHealthStatus().catch(() => {
        /* optional */
      });
    }
    return report;
  }

  async function runAutonomousHealLoop(ctx) {
    const steps = [];
    try {
      if (typeof PortalOps !== "undefined" && PortalOps.getIntegrationHealth) {
        const health = await PortalOps.getIntegrationHealth();
        const status = health && String(health.status || "").toLowerCase();
        steps.push({ step: "integration-health", status: status || "unknown" });
        if (!health || status === "degraded" || status === "fail" || status === "failed") {
          steps.push({ step: "self-heal", report: await runSelfHeal({ reason: "auto-heal", fullPull: false }) });
        }
      } else {
        steps.push({ step: "self-heal", report: await runSelfHeal({ reason: "auto-heal", fullPull: false }) });
      }
    } catch (err) {
      steps.push({ step: "error", message: err && err.message ? err.message : String(err) });
    }
    if (ctx && typeof ctx.invalidateProgramCaches === "function") ctx.invalidateProgramCaches("auto-heal");
    if (ctx && typeof ctx.scheduleHalWidgetRefresh === "function") {
      await ctx.scheduleHalWidgetRefresh().catch(() => {});
    }
    if (typeof window !== "undefined" && window.HalProactive && ctx) {
      await HalProactive.runCycle(ctx, { force: true, forcePlacement: true }).catch(() => {});
      steps.push({ step: "proactive-cycle", ok: true });
    }
    if (ctx && typeof ctx.refreshOpsHealthStatus === "function") {
      await ctx.refreshOpsHealthStatus().catch(() => {});
    }
    return { ok: true, steps };
  }

  return {
    runSelfHeal,
    runBootHeal,
    runAutonomousHealLoop,
    formatReport,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = ProgramStrength;
}
if (typeof globalThis !== "undefined") {
  globalThis.ProgramStrength = ProgramStrength;
}
if (typeof window !== "undefined") {
  window.ProgramStrength = ProgramStrength;
}
