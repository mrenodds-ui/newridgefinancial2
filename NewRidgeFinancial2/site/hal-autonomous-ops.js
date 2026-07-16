/**
 * HAL autonomous ops — always-on heal, placement, orchestrator triage, audit rollup (hal-9000).
 * Starts on optical HAL / workstation boot. Server tick keeps OPS alive without the browser.
 */
const HalAutonomousOps = (function () {
  const TICK_MS = 3 * 60 * 1000;
  const HEAL_MIN_MS = 15 * 60 * 1000;
  const TRIAGE_MIN_MS = 10 * 60 * 1000;
  const PLACEMENT_MIN_MS = 20 * 60 * 1000;
  const SERVER_TICK_MIN_MS = 14 * 60 * 1000;

  let timer = null;
  let lastHealAt = 0;
  let lastTriageAt = 0;
  let lastPlacementAt = 0;
  let lastTickAt = 0;
  let lastServerTickAt = 0;
  let running = false;
  let lastReport = null;
  let ctxProviderRef = null;

  function hasRuntime() {
    const db = typeof DesktopBridge !== "undefined" ? DesktopBridge : typeof window !== "undefined" ? window.DesktopBridge : null;
    return Boolean(db && ((db.hasRuntimeAccess && db.hasRuntimeAccess()) || (db.hasDesktopApi && db.hasDesktopApi())));
  }

  function killSwitchOff() {
    if (typeof sessionStorage !== "undefined" && sessionStorage.getItem("nr2:hal9000:pause") === "1") return false;
    if (typeof localStorage !== "undefined" && localStorage.getItem("nr2:hal9000:pause") === "1") return false;
    return true;
  }

  async function runServerTick() {
    try {
      const res = await fetch("/api/hal/autonomous/tick", {
        method: "POST",
        cache: "no-store",
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        body: "{}",
      });
      return await res.json();
    } catch (err) {
      return { ok: false, error: String(err && err.message ? err.message : err) };
    }
  }

  async function runTick(ctxProvider) {
    if (!killSwitchOff()) return { ok: false, reason: "paused" };
    const ctx = typeof ctxProvider === "function" ? ctxProvider() : ctxProvider;
    const now = Date.now();
    const steps = [];
    lastTickAt = now;

    if (now - lastServerTickAt >= SERVER_TICK_MIN_MS) {
      lastServerTickAt = now;
      try {
        steps.push({ step: "server-autonomous-tick", result: await runServerTick() });
      } catch (err) {
        steps.push({ step: "server-autonomous-tick", error: err && err.message ? err.message : String(err) });
      }
    }

    if (hasRuntime() && now - lastHealAt >= HEAL_MIN_MS) {
      lastHealAt = now;
      try {
        const PS = typeof ProgramStrength !== "undefined" ? ProgramStrength : window.ProgramStrength;
        if (PS && PS.runAutonomousHealLoop && ctx) {
          steps.push({ step: "auto-heal", result: await PS.runAutonomousHealLoop(ctx) });
        }
      } catch (err) {
        steps.push({ step: "auto-heal", error: err && err.message ? err.message : String(err) });
      }
    }

    if (now - lastPlacementAt >= PLACEMENT_MIN_MS && typeof HalProactive !== "undefined" && HalProactive.runCycle && ctx) {
      lastPlacementAt = now;
      try {
        steps.push({ step: "proactive-cycle", result: await HalProactive.runCycle(ctx, { force: false }) });
      } catch (err) {
        steps.push({ step: "proactive-cycle", error: err && err.message ? err.message : String(err) });
      }
    }

    if (now - lastTriageAt >= TRIAGE_MIN_MS && typeof HalOrchestrator !== "undefined" && HalOrchestrator.runTriage) {
      lastTriageAt = now;
      try {
        steps.push({ step: "orchestrator-triage", result: HalOrchestrator.runTriage(ctx || {}) });
      } catch (err) {
        steps.push({ step: "orchestrator-triage", error: err && err.message ? err.message : String(err) });
      }
    }

    if (
      hasRuntime() &&
      typeof HalEmployeeRunner !== "undefined" &&
      HalEmployeeRunner.runShift &&
      typeof HalEmployee !== "undefined" &&
      ctx
    ) {
      try {
        const halModels = ctx && ctx.halModels;
        const target = HalEmployee.getTargetLevel(halModels);
        if (target >= 2) {
          steps.push({
            step: "employee-shift",
            result: await HalEmployeeRunner.runShift(ctx, halModels),
          });
        }
      } catch (err) {
        steps.push({ step: "employee-shift", error: err && err.message ? err.message : String(err) });
      }
    }

    if (typeof HalDirector !== "undefined" && HalDirector.runTick && ctx && ctx.halModels) {
      try {
        const halModels = ctx.halModels;
        if (typeof HalAscension10000 !== "undefined" && HalAscension10000.isEnabled(halModels)) {
          steps.push({ step: "director-tick", result: await HalDirector.runTick(() => ctx, halModels) });
        }
      } catch (err) {
        steps.push({ step: "director-tick", error: err && err.message ? err.message : String(err) });
      }
    }

    lastReport = { ok: true, at: new Date().toISOString(), steps, runtime: hasRuntime(), paused: false };
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("nr2:hal9000-tick", { detail: lastReport }));
    }
    return lastReport;
  }

  function start(ctxProvider) {
    if (timer || typeof window === "undefined") return false;
    ctxProviderRef = ctxProvider || ctxProviderRef;
    running = true;
    timer = setInterval(() => {
      runTick(ctxProviderRef).catch(() => {});
    }, TICK_MS);
    setTimeout(() => runTick(ctxProviderRef).catch(() => {}), 2500);
    return true;
  }

  function ensureStarted(ctxProvider) {
    if (running && timer) {
      if (ctxProvider) ctxProviderRef = ctxProvider;
      return true;
    }
    return start(ctxProvider);
  }

  function stop() {
    running = false;
    if (!timer) return;
    clearInterval(timer);
    timer = null;
  }

  function pause() {
    if (typeof sessionStorage !== "undefined") sessionStorage.setItem("nr2:hal9000:pause", "1");
  }

  function resume() {
    if (typeof sessionStorage !== "undefined") sessionStorage.removeItem("nr2:hal9000:pause");
  }

  function status() {
    return {
      ok: true,
      running,
      paused: !killSwitchOff(),
      runtime: hasRuntime(),
      lastTickAt: lastTickAt ? new Date(lastTickAt).toISOString() : null,
      lastReport,
      orchestrator: typeof HalOrchestrator !== "undefined" ? HalOrchestrator.getLastTriage() : null,
    };
  }

  function formatStatus(st) {
    const s = st || status();
    return [
      `HAL 9000 autonomous ops: ${s.running ? "running" : "stopped"}${s.paused ? " (paused)" : ""}.`,
      `Runtime: ${s.runtime ? "NR2 server" : "browser + server tick"}.`,
      s.lastTickAt ? `Last tick: ${s.lastTickAt}.` : "No tick yet.",
      s.orchestrator && s.orchestrator.topAgent
        ? `Orchestrator lead: ${s.orchestrator.topAgent.label} (${s.orchestrator.topAgent.count} items).`
        : "",
    ]
      .filter(Boolean)
      .join("\n");
  }

  return {
    start,
    ensureStarted,
    stop,
    pause,
    resume,
    runTick,
    status,
    formatStatus,
    getLastReport: () => lastReport,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalAutonomousOps;
}
if (typeof globalThis !== "undefined") {
  globalThis.HalAutonomousOps = HalAutonomousOps;
}
if (typeof window !== "undefined") {
  window.HalAutonomousOps = HalAutonomousOps;
}
