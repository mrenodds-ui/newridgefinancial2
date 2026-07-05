/**
 * HAL employee shift runner — standing-consent actions on autonomous ops tick (levels 2–5).
 */
const HalEmployeeRunner = (function () {
  const SHIFT_MIN_MS = 30 * 60 * 1000;
  let lastShiftAt = 0;
  let lastReport = null;

  function hasRuntime() {
    const db = typeof DesktopBridge !== "undefined" ? DesktopBridge : typeof window !== "undefined" ? window.DesktopBridge : null;
    return Boolean(db && ((db.hasRuntimeAccess && db.hasRuntimeAccess()) || (db.hasDesktopApi && db.hasDesktopApi()) || (db.hasLoopbackApi && db.hasLoopbackApi())));
  }

  async function runLevel3Tasks(ctx, halModels) {
    const steps = [];
    if (!HalEmployee || HalEmployee.getTargetLevel(halModels) < 3) return steps;
    if (typeof HalOrchestrator === "undefined" || !HalOrchestrator.runTriage) return steps;
    const triage = HalOrchestrator.runTriage(ctx);
    steps.push({ step: "orchestrator-denied-claims", count: triage && triage.totalItems });
    if (typeof OfficeTaskStore !== "undefined" && OfficeTaskStore.upsert && triage && Array.isArray(triage.agents)) {
      const claims = triage.agents.find((a) => /claim|billing/i.test(a.id || a.label || ""));
      if (claims && claims.count > 0) {
        await OfficeTaskStore.upsert({
          taskId: `hal-emp-claims-${new Date().toISOString().slice(0, 10)}`,
          title: `HAL: review ${claims.count} billing/claims item(s)`,
          status: "open",
          priority: "high",
          assignee: "HAL",
          source: "employee-level-3",
          createdAt: new Date().toISOString(),
        }).catch(() => {});
        steps.push({ step: "hal-task-claims", ok: true });
      }
    }
    return steps;
  }

  async function runLevel5Sync(ctx, halModels) {
    const steps = [];
    if (!HalEmployee || HalEmployee.getTargetLevel(halModels) < 5) return steps;
    const pol = HalEmployee.policiesForLevel(5);
    if (!pol["cross-system-sync"]) return steps;
    const feed = ctx && ctx.halWidgetFeed;
    const widgets = (feed && feed.widgets) || {};
    const ar = widgets.arAgingAndCollections;
    const prod = widgets.softdentProductionSummary || widgets.productionSummary;
    if (ar && prod && ar.status === "SUCCESS" && prod.status === "SUCCESS") {
      await HalEmployee.recordWork(
        "cross-system-sync",
        "Checked production vs A/R widgets — both verified; no auto-fix applied.",
        halModels,
        { ok: true },
      );
      steps.push({ step: "cross-system-sync", ok: true });
    }
    if (pol["auto-task-ownership"] && typeof OfficeTaskStore !== "undefined" && OfficeTaskStore.list) {
      const tasks = await OfficeTaskStore.list().catch(() => []);
      const halOpen = tasks.filter((t) => t.assignee === "HAL" && t.status !== "done").length;
      steps.push({ step: "hal-owned-tasks", count: halOpen });
    }
    return steps;
  }

  async function runShift(ctx, halModels, opts) {
    const options = opts || {};
    const HE = typeof HalEmployee !== "undefined" ? HalEmployee : window.HalEmployee;
    if (!HE) return { ok: false, reason: "hal-employee-not-loaded" };
    const target = HE.getTargetLevel(halModels);
    if (target < 2 && !options.force) return { ok: true, skipped: true, reason: "level-below-2" };
    if (!hasRuntime()) return { ok: false, reason: "no-runtime" };

    const now = Date.now();
    const pol = typeof HalEmployee !== "undefined" ? HalEmployee.policiesForLevel(HalEmployee.getTargetLevel(halModels)) : {};
    const continuous = Boolean(pol["continuous-shift"]);
    if (!options.force && !continuous && now - lastShiftAt < SHIFT_MIN_MS) {
      return { ok: true, skipped: true, reason: "shift-cooldown", lastShiftAt };
    }
    lastShiftAt = now;

    const steps = [];
    const db = typeof DesktopBridge !== "undefined" ? DesktopBridge : window.DesktopBridge;
    const consent = HE.standingConsentText(halModels);

    if (db && typeof db.runEmployeeShift === "function") {
      try {
        const remote = await db.runEmployeeShift({ targetLevel: target, dryRun: Boolean(options.dryRun) });
        steps.push({ step: "server-shift", ...(remote || {}) });
      } catch (err) {
        steps.push({ step: "server-shift", ok: false, error: err && err.message ? err.message : String(err) });
      }
    } else if (typeof HalOutbound !== "undefined") {
      if (HE.standingAllows("qb-export", halModels)) {
        try {
          const r = await HalOutbound.executePending({ kind: "qb-export" }, consent);
          steps.push({ step: "qb-export", ...(r || {}) });
          await HE.recordWork("qb-export", "Standing consent IIF export", halModels, r);
        } catch (err) {
          steps.push({ step: "qb-export", ok: false, error: String(err) });
        }
      }
      if (HE.standingAllows("qbo-post", halModels)) {
        try {
          const r = await HalOutbound.executePending({ kind: "qbo-post" }, consent);
          steps.push({ step: "qbo-post", ...(r || {}) });
          await HE.recordWork("qbo-post", "Standing consent QBO post", halModels, r);
        } catch (err) {
          steps.push({ step: "qbo-post", ok: false, error: String(err) });
        }
      }
    }

    if (target >= 3) {
      const l3 = await runLevel3Tasks(ctx, halModels);
      steps.push(...l3);
    }
    if (target >= 5) {
      const l5 = await runLevel5Sync(ctx, halModels);
      steps.push(...l5);
    }

    lastReport = { ok: true, at: new Date().toISOString(), targetLevel: target, steps };
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("nr2:hal-employee-shift", { detail: lastReport }));
    }
    return lastReport;
  }

  function getLastReport() {
    return lastReport;
  }

  return {
    runShift,
    getLastReport,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalEmployeeRunner;
}
if (typeof globalThis !== "undefined") {
  globalThis.HalEmployeeRunner = HalEmployeeRunner;
}
if (typeof window !== "undefined") {
  window.HalEmployeeRunner = HalEmployeeRunner;
}
