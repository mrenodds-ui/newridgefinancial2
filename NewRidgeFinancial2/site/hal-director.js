/**
 * HAL director — practice director loop for ascension 10000 (employee levels 6–7).
 */
const HalDirector = (function () {
  const TICK_MS = 2 * 60 * 1000;
  let timer = null;
  let running = false;
  let lastDigest = null;
  let lastPredictiveAt = 0;

  function isEnabled(halModels) {
    const A = typeof HalAscension10000 !== "undefined" ? HalAscension10000 : globalThis.HalAscension10000;
    return A && A.directorEnabled(halModels);
  }

  function isRunning() {
    return running;
  }

  function predictiveItems(ctx) {
    const items = [];
    const diag = (ctx && ctx.importDiagnostics) || {};
    (diag.datasets || []).forEach((ds) => {
      if (ds.status === "ok" || ds.status === "current") return;
      items.push({
        kind: "import-stale",
        severity: ds.status === "missing" ? "critical" : "warning",
        title: `Predicted blocker: ${ds.label || ds.datasetKey}`,
        detail: ds.message || "Refresh before management review.",
        sourceId: `director-predict-${ds.datasetKey || "unknown"}`,
      });
    });
    const feed = ctx && ctx.halWidgetFeed;
    const widgets = (feed && feed.widgets) || {};
    Object.keys(widgets).forEach((key) => {
      const w = widgets[key];
      if (!w || String(w.status || "").toUpperCase() !== "FAILED") return;
      items.push({
        kind: "widget-failed",
        severity: "warning",
        title: `Widget recovery: ${w.title || key}`,
        detail: w.summary || "Placement or source issue.",
        sourceId: `director-widget-${key}`,
      });
    });
    return items.slice(0, 12);
  }

  function getExecutiveSummary(ctx) {
    const lines = ["Executive director digest:"];
    if (lastDigest && lastDigest.at) lines.push(`Last director tick: ${lastDigest.at}.`);
    const OR = typeof HalOrchestrator !== "undefined" ? HalOrchestrator : null;
    const triage = OR && OR.getLastTriage ? OR.getLastTriage() : null;
    if (triage && triage.topAgent) {
      lines.push(`Lead domain: ${triage.topAgent.label} (${triage.topAgent.count} items).`);
    }
    const predictive = predictiveItems(ctx);
    if (predictive.length) {
      lines.push(`Predictive alerts: ${predictive.length}.`);
      predictive.slice(0, 4).forEach((p, i) => lines.push(`${i + 1}. [${p.severity}] ${p.title}`));
    }
    const HE = typeof HalEmployee !== "undefined" ? HalEmployee : null;
    if (HE) lines.push(`Employee tier target: ${HE.getTargetLevel(ctx && ctx.halModels)}/7.`);
    return lines.join("\n");
  }

  async function delegateTasks(ctx, halModels) {
    const level = typeof HalEmployee !== "undefined" ? HalEmployee.getTargetLevel(halModels) : 0;
    if (level < 6 || typeof OfficeTaskStore === "undefined" || !OfficeTaskStore.upsert) return [];
    const created = [];
    for (const item of predictiveItems(ctx)) {
      try {
        await OfficeTaskStore.upsert({
          taskId: item.sourceId,
          title: `HAL Director: ${item.title}`,
          status: "open",
          priority: item.severity === "critical" ? "critical" : "high",
          assignee: "HAL",
          source: "hal-director",
          notes: item.detail,
          createdAt: new Date().toISOString(),
        });
        created.push(item.sourceId);
      } catch {
        /* optional */
      }
    }
    return created;
  }

  async function runLevel7AutoPrep(ctx, halModels) {
    const level = typeof HalEmployee !== "undefined" ? HalEmployee.getTargetLevel(halModels) : 0;
    if (level < 7 || typeof HalOutbound === "undefined" || typeof HalEmployee === "undefined") return null;
    if (!HalEmployee.standingAllows("payer-portal-rpa", halModels)) return null;
    const OR = typeof HalOrchestrator !== "undefined" ? HalOrchestrator : null;
    const triage = OR && OR.runTriage ? OR.runTriage(ctx, { limitPerAgent: 2 }) : null;
    const billing = triage && triage.agents ? triage.agents.find((a) => a.id === "billing" || a.id === "claims") : null;
    const top = billing && billing.items && billing.items[0];
    if (!top) return null;
    const consent = HalEmployee.standingConsentText(halModels);
    try {
      const result = await HalOutbound.executePending(
        {
          kind: "payer-portal-rpa",
          draft: { claimId: top.claimId || "", payer: top.payer || "", body: top.detail || top.title || "" },
          query: top.title || "",
        },
        consent,
      );
      await HalEmployee.recordWork("payer-portal-rpa", `Executive partner prep: ${top.title || "claim"}`, halModels, result);
      return result;
    } catch (err) {
      return { ok: false, error: err && err.message ? err.message : String(err) };
    }
  }

  async function runTick(ctxProvider, halModels) {
    const ctx = typeof ctxProvider === "function" ? ctxProvider() : ctxProvider;
    const models = halModels || (ctx && ctx.halModels) || null;
    if (!ctx || !isEnabled(models)) return { ok: false, reason: "director-disabled" };
    const now = Date.now();
    const steps = [];
    if (typeof HalOrchestrator !== "undefined" && HalOrchestrator.runTriage) {
      steps.push({ step: "director-triage", result: HalOrchestrator.runTriage(ctx, { limitPerAgent: 6 }) });
    }
    if (now - lastPredictiveAt >= TICK_MS) {
      lastPredictiveAt = now;
      const delegated = await delegateTasks(ctx, models);
      steps.push({ step: "director-delegate", count: delegated.length });
    }
    const l7 = await runLevel7AutoPrep(ctx, models);
    if (l7) steps.push({ step: "executive-partner-rpa", result: l7 });
    lastDigest = { ok: true, at: new Date().toISOString(), steps };
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("nr2:hal-director-tick", { detail: lastDigest }));
    }
    return lastDigest;
  }

  function start(ctxProvider, halModels) {
    if (timer || typeof window === "undefined") return;
    const resolveModels = () =>
      halModels ||
      (typeof ctxProvider === "function" && ctxProvider() && ctxProvider().halModels) ||
      null;
    if (!isEnabled(resolveModels())) return;
    running = true;
    timer = setInterval(() => {
      runTick(ctxProvider, resolveModels()).catch(() => {});
    }, TICK_MS);
    setTimeout(() => {
      runTick(ctxProvider, resolveModels()).catch(() => {});
    }, 12000);
  }

  function stop() {
    running = false;
    if (!timer) return;
    clearInterval(timer);
    timer = null;
  }

  function getLastDigest() {
    return lastDigest;
  }

  return {
    isEnabled,
    isRunning,
    start,
    stop,
    runTick,
    getExecutiveSummary,
    getLastDigest,
    predictiveItems,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalDirector;
}
if (typeof globalThis !== "undefined") {
  globalThis.HalDirector = HalDirector;
}
if (typeof window !== "undefined") {
  window.HalDirector = HalDirector;
}
