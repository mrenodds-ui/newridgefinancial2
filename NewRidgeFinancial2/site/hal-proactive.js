/**
 * HAL proactive program manager — autonomous internal data placement.
 * HAL runs import refresh and places data into dashboards/widgets (read-only externally).
 */
const HalProactive = (function () {
  const TASK_PREFIX = "HAL: ";
  const CYCLE_MIN_MS = 5 * 60 * 1000;
  const PLACEMENT_TIMER_MS = 5 * 60 * 1000;
  const BRIEFING_CHECK_MS = 60 * 1000;
  const MAX_RECOMMENDATIONS = 8;
  const AUTO_TASK_SEVERITIES = new Set(["critical", "warning"]);

  let lastCycleAt = 0;
  let lastBriefing = null;
  let lastPlacementAt = 0;
  let placementTimer = null;
  let briefingTimer = null;
  let lastRefreshSignature = null;

  // Fingerprint of dataset statuses. When this is unchanged between cycles a
  // repeat auto-refresh cannot improve anything (the upstream exports have not
  // changed), so HAL skips it instead of refreshing every cycle forever.
  function diagnosticsSignature(diagnostics) {
    if (!diagnostics || !Array.isArray(diagnostics.datasets)) return "";
    return diagnostics.datasets
      .map((item) => `${item.datasetKey || item.system || "?"}:${item.status}`)
      .sort()
      .join("|");
  }

  function hasRuntimeAccess() {
    const desktop = typeof DesktopBridge !== "undefined" ? DesktopBridge : typeof window !== "undefined" ? window.DesktopBridge : null;
    if (!desktop) return false;
    if (desktop.hasRuntimeAccess && desktop.hasRuntimeAccess()) return true;
    return Boolean(desktop.hasDesktopApi && desktop.hasDesktopApi());
  }

  function needsAutonomousRefresh(diagnostics) {
    if (!diagnostics || !Array.isArray(diagnostics.datasets)) return false;
    // Automated datasets that are missing, stale, or only partially loaded
    // should trigger a refresh so HAL keeps trying to fill widgets. Datasets
    // marked not_configured are automated === false and stay excluded — there
    // is no collector to run for them.
    return diagnostics.datasets.some(
      (item) =>
        item.automated !== false &&
        (item.status === "missing" || item.status === "stale" || item.status === "partial"),
    );
  }

  async function runAutonomousPlacement(ctx, diagnostics, options) {
    const force = options && options.force;
    if (!hasRuntimeAccess()) {
      return { placed: false, reason: "browser-only", refreshed: false };
    }
    const halData = (ctx && ctx.halData) || {};
    const pullApproved = halData.practiceSourcePull ? halData.practiceSourcePull.approved !== false : true;
    if (pullApproved) {
      try {
        const Svc = ctx && ctx.Services;
        if (Svc && typeof Svc.pullPracticeSources === "function") {
          await Svc.pullPracticeSources({ reason: force ? "hal-force" : "hal-auto" });
        } else {
          const desktop = typeof DesktopBridge !== "undefined" ? DesktopBridge : window.DesktopBridge;
          if (desktop && typeof desktop.pullPracticeSources === "function") {
            await desktop.pullPracticeSources();
          }
        }
      } catch {
        /* direct source pull optional; import refresh below may still help */
      }
    }
    if (!force && !needsAutonomousRefresh(diagnostics)) {
      return { placed: true, reason: "data-current", refreshed: false };
    }
    const now = Date.now();
    if (!force && lastPlacementAt && now - lastPlacementAt < CYCLE_MIN_MS) {
      return { placed: false, reason: "throttled", refreshed: false };
    }
    const signature = diagnosticsSignature(diagnostics);
    if (!force && signature && signature === lastRefreshSignature) {
      return { placed: true, reason: "no-upstream-change", refreshed: false };
    }
    try {
      const coord =
        typeof ImportCoordinator !== "undefined"
          ? ImportCoordinator
          : typeof globalThis !== "undefined" && globalThis.ImportCoordinator
            ? globalThis.ImportCoordinator
            : null;
      if (coord && typeof coord.refresh === "function") {
        await coord.refresh({ reason: "hal-auto" });
      } else if (ctx && ctx.Services && typeof ctx.Services.refreshImports === "function") {
        await ctx.Services.refreshImports({ reason: "hal-auto", waitForCompletion: true });
      } else {
        return { placed: false, reason: "no-refresh-path", refreshed: false };
      }
      if (ctx && typeof ctx.clearProgramContextCache === "function") ctx.clearProgramContextCache();
      if (ctx && typeof ctx.invalidateProgramCaches === "function") ctx.invalidateProgramCaches("hal-auto");
      else if (typeof SnapshotStore !== "undefined") SnapshotStore.invalidate("hal-auto");
      lastPlacementAt = now;
      lastRefreshSignature = signature;
      return { placed: true, reason: "import-refresh-complete", refreshed: true };
    } catch (err) {
      const failed = { placed: false, reason: err && err.message ? err.message : "placement-failed", refreshed: false };
      if (
        typeof ProgramStrength !== "undefined" &&
        ProgramStrength.runAutonomousHealLoop &&
        ctx &&
        failed.reason === "placement-failed"
      ) {
        ProgramStrength.runAutonomousHealLoop(ctx).catch(() => {});
      }
      return failed;
    }
  }

  function startPlacementTimer(ctxProvider) {
    if (placementTimer || typeof window === "undefined") return;
    placementTimer = setInterval(() => {
      const ctx = typeof ctxProvider === "function" ? ctxProvider() : ctxProvider;
      if (ctx) runCycle(ctx).catch(() => {});
    }, PLACEMENT_TIMER_MS);
  }

  function stopPlacementTimer() {
    if (!placementTimer) return;
    clearInterval(placementTimer);
    placementTimer = null;
  }

  function diagnosticsApi() {
    if (typeof ImportDiagnostics !== "undefined") return ImportDiagnostics;
    if (typeof window !== "undefined" && window.ImportDiagnostics) return window.ImportDiagnostics;
    try {
      return require("./import-diagnostics.js");
    } catch {
      return null;
    }
  }

  function statusLabel(status) {
    const diag = diagnosticsApi();
    if (diag && typeof diag.statusLabel === "function") return diag.statusLabel(status);
    const labels = {
      connected: "Connected",
      partial: "Partial",
      stale: "Stale",
      not_configured: "Not Configured",
      missing: "Missing",
    };
    return labels[status] || status;
  }

  function severityRank(severity) {
    if (severity === "critical") return 0;
    if (severity === "warning") return 1;
    if (severity === "info") return 2;
    return 3;
  }

  function pushRecommendation(list, seen, item) {
    if (!item || !item.id || seen.has(item.id)) return;
    seen.add(item.id);
    list.push(item);
  }

  function analyzeImportDiagnostics(snapshot, recommendations, seen) {
    const bundle = snapshot && snapshot.importBundle;
    const diagApi = diagnosticsApi();
    const diagnostics =
      (bundle && bundle.diagnostics) || (bundle && diagApi ? diagApi.evaluateBundle(bundle) : null);
    if (!diagnostics || !Array.isArray(diagnostics.datasets)) return diagnostics;

    diagnostics.datasets.forEach((dataset) => {
      if (dataset.status === "connected") return;
      const label = statusLabel(dataset.status);
      const collector = dataset.collectorHint ? ` Check: ${dataset.collectorHint}.` : "";
      if (dataset.status === "not_configured") {
        pushRecommendation(recommendations, seen, {
          id: `import-not-configured-${dataset.datasetKey}`,
          severity: dataset.severity === "critical" ? "warning" : "info",
          title: `${dataset.datasetKey} is not automated`,
          rationale: dataset.detail || "No collector is configured for this dataset.",
          action: { type: "explain", target: dataset.system === "quickbooks" ? "quickbooks" : "softdent" },
          autoTaskTitle: null,
        });
        return;
      }
      const navTarget =
        dataset.datasetKey.indexOf("claims") >= 0
          ? "claims"
          : dataset.datasetKey.indexOf("ar") >= 0
            ? "ar"
            : dataset.system === "quickbooks"
              ? "quickbooks"
              : "financial";
      pushRecommendation(recommendations, seen, {
        id: `import-${dataset.status}-${dataset.datasetKey}`,
        severity: dataset.severity === "critical" ? "critical" : dataset.status === "stale" ? "warning" : "info",
        title: `${dataset.datasetKey} is ${label}`,
        rationale: `${dataset.detail || "Import issue detected."}${collector}`,
        action:
          dataset.status === "missing" || dataset.status === "stale"
            ? { type: "command", command: "Show import status" }
            : { type: "navigate", target: navTarget },
        autoTaskTitle:
          dataset.severity === "critical" && (dataset.status === "missing" || dataset.status === "stale")
            ? `${TASK_PREFIX}Repair ${dataset.datasetKey} import (${label})`
            : null,
      });
    });
    return diagnostics;
  }

  function analyzeWidgets(snapshot, recommendations, seen) {
    const feed = snapshot && snapshot.widgets;
    if (!feed || !feed.widgets) return;
    const priority = [];
    Object.keys(feed.widgets).forEach((key) => {
      const widget = feed.widgets[key];
      if (!widget || widget.status === "SUCCESS") return;
      if (widget.status === "FAILED" || widget.status === "DEGRADED") {
        priority.push({
          id: `widget-${key}`,
          severity: widget.status === "FAILED" ? "warning" : "info",
          title: `Fill ${widget.title || key}`,
          rationale: widget.summary || "Widget is missing required import data.",
          action: { type: "navigate", target: widget.navTarget || "financial" },
          autoTaskTitle: widget.status === "FAILED" ? `${TASK_PREFIX}Review missing data for ${widget.title || key}` : null,
        });
      }
    });
    priority.sort((a, b) => severityRank(a.severity) - severityRank(b.severity));
    priority.slice(0, 3).forEach((item) => pushRecommendation(recommendations, seen, item));
  }

  function analyzeAttention(snapshot, recommendations, seen) {
    if (!window.HalSkills) return;
    const tasks = snapshot.officeTasks || [];
    const metrics = HalSkills.computeTaskMetrics(tasks);
    const attention = HalSkills.buildOfficeManagerAttention(snapshot, metrics);
    (attention.items || []).forEach((item) => {
      if (item.severity === "info" && (item.count || 0) < 3) return;
      const navTarget =
        item.category === "claims_follow_up"
          ? "claims"
          : item.category === "revenue"
            ? "quickbooks"
            : item.category === "local_tasks"
              ? "office-manager"
              : "financial";
      pushRecommendation(recommendations, seen, {
        id: `attention-${item.itemId}`,
        severity: item.severity === "critical" ? "critical" : item.severity === "warning" ? "warning" : "info",
        title: item.title,
        rationale: item.detail,
        action: { type: "navigate", target: navTarget },
        autoTaskTitle:
          item.severity === "warning" || item.severity === "critical"
            ? `${TASK_PREFIX}${item.title}`
            : null,
      });
    });
  }

  function analyzeRuntimeIssues(snapshot, recommendations, seen) {
    const issues = snapshot.runtimeIssues || [];
    issues.slice(0, 4).forEach((issue, index) => {
      pushRecommendation(recommendations, seen, {
        id: `runtime-${issue.source || index}-${index}`,
        severity: "warning",
        title: `Runtime issue: ${issue.source || "program"}`,
        rationale: issue.message || "A runtime issue was recorded.",
        action: { type: "command", command: "Show diagnostics" },
        autoTaskTitle: `${TASK_PREFIX}Investigate runtime issue (${issue.source || "program"})`,
      });
    });
  }

  function analyzeDataQuality(snapshot, recommendations, seen) {
    const dashboards = (snapshot && snapshot.dashboards) || {};
    const fin = dashboards.financial;
    if (fin && fin.dataSource === "empty") {
      pushRecommendation(recommendations, seen, {
        id: "financial-dashboard-empty",
        severity: "critical",
        title: "Financial dashboard has no import data",
        rationale: "Production and collections views are empty. Verify SoftDent and QuickBooks collectors before making decisions.",
        action: { type: "command", command: "Show import status" },
        autoTaskTitle: `${TASK_PREFIX}Restore financial import data`,
      });
    }
    if (fin && (fin.importDepth === "partial" || fin.importDepth === "degraded")) {
      pushRecommendation(recommendations, seen, {
        id: fin.importDepth === "degraded" ? "financial-dashboard-degraded" : "financial-dashboard-partial",
        severity: fin.importDepth === "degraded" ? "warning" : "info",
        title: fin.importDepth === "degraded" ? "Financial dashboard is degraded" : "Financial dashboard is partial",
        rationale:
          fin.importDepth === "degraded"
            ? "Collections, period alignment, or reconcile checks failed. HAL will not treat this month as complete."
            : "Trend, payer mix, quality detail, or a single source is incomplete. HAL will not fabricate missing metrics.",
        action: { type: "navigate", target: "financial" },
        autoTaskTitle: null,
      });
    }
  }

  function buildProactiveBriefing(snapshot, ctx) {
    const recommendations = [];
    const seen = new Set();
    const diagnostics = analyzeImportDiagnostics(snapshot, recommendations, seen);
    analyzeDataQuality(snapshot, recommendations, seen);
    analyzeWidgets(snapshot, recommendations, seen);
    analyzeAttention(snapshot, recommendations, seen);
    analyzeRuntimeIssues(snapshot, recommendations, seen);

    const officeApi = officeManagerApi();
    const officePriorities = officeApi ? officeApi.buildOfficePriorities(snapshot, ctx) : [];
    mergeOfficeRecommendations(recommendations, seen, officePriorities);

    recommendations.sort((a, b) => {
      const rank = severityRank(a.severity) - severityRank(b.severity);
      if (rank !== 0) return rank;
      return String(a.title).localeCompare(String(b.title));
    });

    const trimmed = recommendations.slice(0, MAX_RECOMMENDATIONS);
    const top = trimmed[0] || null;
    const headline = top
      ? `HAL is acting: ${top.title}`
      : "HAL placed current data — program imports and surfaces look healthy.";

    return {
      generatedAt: new Date().toISOString(),
      headline,
      independenceNote:
        "HAL is the internal office manager: it autonomously refreshes local imports, places validated data, prioritizes work, and creates local tasks. External writeback to SoftDent/QuickBooks remains blocked.",
      programPosture: top ? (top.severity === "critical" ? "needs_attention" : "monitor") : "healthy",
      diagnosticsSummary: diagnostics && diagnostics.summary ? diagnostics.summary : null,
      recommendations: trimmed,
      topAction: top,
      recommendationCount: trimmed.length,
      placement: null,
      officePriorities,
      officeManager: null,
    };
  }

  function applyPlacementToBriefing(briefing, placement) {
    if (!briefing) return briefing;
    briefing.placement = placement || null;
    const browserOnly = placement && (placement.reason === "browser-only" || placement.reason === "no-refresh-path");
    if (placement && placement.refreshed && !browserOnly) {
      briefing.headline = "HAL refreshed imports and placed updated data into dashboards.";
      briefing.programPosture = "monitor";
    } else if (placement && placement.placed && placement.reason === "data-current") {
      briefing.headline = "HAL verified imports — data is current in dashboards and widgets.";
    } else if (placement && placement.placed && placement.reason === "no-upstream-change") {
      briefing.headline = "HAL checked imports — no upstream export changes since the last refresh.";
      briefing.programPosture = "monitor";
    } else if (placement && placement.reason === "throttled") {
      briefing.headline = "HAL placement is waiting — refresh was throttled. Use Force HAL placement if you just added exports.";
      briefing.programPosture = "monitor";
    } else if (placement && placement.reason === "browser-only") {
      briefing.headline = "HAL placement needs the desktop app — browser preview cannot refresh imports.";
      briefing.programPosture = "monitor";
    } else if (placement && placement.reason === "no-refresh-path") {
      briefing.headline = "HAL could not refresh imports in this runtime — launch Start Program on the desktop app.";
      briefing.programPosture = "monitor";
    }
    return briefing;
  }

  function formatProactiveBriefing(briefing, opts) {
    if (!briefing) return "Proactive briefing unavailable.";
    opts = opts || {};
    const chatMode = opts.chatMode === true;

    if (chatMode) {
      const lines = [briefing.headline || "Here's what needs attention."];
      if (briefing.placement) {
        const refreshNote =
          briefing.placement.refreshed && briefing.placement.reason !== "browser-only"
            ? " Imports refreshed."
            : briefing.placement.reason === "browser-only"
              ? " Browser preview — use Start Program for live imports."
              : "";
        lines.push(`Placement: ${briefing.placement.placed ? "active" : "skipped"} (${briefing.placement.reason}).${refreshNote}`);
      }
      const recs = (briefing.recommendations || []).slice(0, 3);
      if (recs.length) {
        lines.push("", "Top priorities:");
        recs.forEach((item, index) => {
          const action =
            item.action && item.action.type === "navigate"
              ? `Open ${item.action.target}`
              : item.action && item.action.command
                ? item.action.command
                : "Review locally";
          lines.push(`${index + 1}. [${item.severity}] ${item.title} — Next: ${action}.`);
        });
      } else {
        lines.push("", "Nothing urgent — imports and surfaces look steady.");
      }
      return lines.join("\n");
    }

    const lines = [
      "HAL internal office manager (local placement only · external firewall locked):",
      briefing.headline,
      briefing.independenceNote,
      "",
    ];
    if (briefing.placement) {
      const refreshNote =
        briefing.placement.refreshed && briefing.placement.reason !== "browser-only"
          ? " — import refresh completed."
          : briefing.placement.reason === "browser-only"
            ? " — browser preview cannot refresh imports (use Start Program)."
            : "";
      lines.push(
        `Placement: ${briefing.placement.placed ? "active" : "skipped"} (${briefing.placement.reason})${refreshNote}`,
        "",
      );
    }
    if (briefing.diagnosticsSummary) {
      const s = briefing.diagnosticsSummary;
      lines.push(
        `Import datasets: ${s.connected} connected, ${s.partial} partial, ${s.stale} stale, ${s.missing} missing, ${s.notConfigured} not configured.`,
        "",
      );
    }
    if (!briefing.recommendations.length) {
      lines.push("No urgent recommendations. HAL will keep monitoring imports and surfaces.");
    } else {
      lines.push("Recommended actions (best for the program):");
      briefing.recommendations.forEach((item, index) => {
        const action =
          item.action && item.action.type === "navigate"
            ? `Open ${item.action.target}`
            : item.action && item.action.command
              ? item.action.command
              : "Review locally";
        lines.push(`${index + 1}. [${item.severity}] ${item.title} — ${item.rationale} Next: ${action}.`);
      });
    }
    if (briefing.officeManager && Array.isArray(briefing.officePriorities) && briefing.officePriorities.length) {
      lines.push("", "Office priorities:");
      briefing.officePriorities.slice(0, 5).forEach((item, index) => {
        lines.push(`${index + 1}. [${item.severity}] ${item.title} — ${item.detail}`);
      });
    }
    return lines.join("\n");
  }

  function officeManagerApi() {
    if (typeof HalOfficeManager !== "undefined") return HalOfficeManager;
    if (typeof window !== "undefined" && window.HalOfficeManager) return window.HalOfficeManager;
    try {
      return require("./hal-office-manager.js");
    } catch {
      return null;
    }
  }

  function priorityToRecommendation(priority) {
    return {
      id: priority.id,
      severity: priority.severity,
      title: priority.title,
      rationale: priority.detail,
      action: { type: "navigate", target: priority.navTarget || priority.surface || "office-manager" },
      autoTaskTitle: priority.autoTask ? `${TASK_PREFIX}${priority.title}` : null,
      sourceId: priority.sourceId,
      officePriority: priority,
    };
  }

  function mergeOfficeRecommendations(recommendations, seen, officePriorities) {
    officePriorities.slice(0, 6).forEach((priority) => {
      if (seen.has(priority.id)) return;
      pushRecommendation(recommendations, seen, priorityToRecommendation(priority));
    });
  }

  function taskExists(tasks, title) {
    const normalized = String(title || "").trim().toLowerCase();
    return (tasks || []).some((task) => String(task.title || "").trim().toLowerCase() === normalized);
  }

  async function applyAutoTasks(briefing, ctx) {
    if (!briefing || !window.HalSkills || !ctx || typeof ctx.getOfficeTasks !== "function") {
      return { created: [], updated: [], skipped: 0 };
    }
    const created = [];
    const updated = [];
    let skipped = 0;
    let tasks = (await ctx.getOfficeTasks()) || [];
    const activeSourceIds = [];

    async function persistTasks(nextTasks) {
      if (typeof OfficeTaskStore !== "undefined" && typeof OfficeTaskStore.replaceAll === "function") {
        tasks = await OfficeTaskStore.replaceAll(nextTasks);
      } else if (typeof ctx.setOfficeTasks === "function") {
        await ctx.setOfficeTasks(nextTasks);
        tasks = nextTasks;
      } else {
        tasks = nextTasks;
      }
    }

    for (const item of briefing.recommendations || []) {
      const sourceId = item.sourceId || item.id;
      if (sourceId) activeSourceIds.push(sourceId);
      if (!item.autoTaskTitle || !AUTO_TASK_SEVERITIES.has(item.severity)) continue;
      const priority = item.officePriority;
      try {
        const result = HalSkills.upsertHalTask(
          tasks,
          {
            title: item.autoTaskTitle,
            priority: item.severity === "critical" ? "urgent" : "normal",
            notes: item.rationale,
            description: item.rationale,
            source: priority && priority.source ? priority.source : "hal-proactive",
            sourceId,
            surface: priority && priority.surface ? priority.surface : null,
            dueHint: priority && priority.actionHint ? priority.actionHint : null,
            blockingReason: priority && priority.detail ? priority.detail : null,
            sourceRefs: priority && priority.evidence ? priority.evidence : [],
          },
          { actor: "hal-proactive" },
        );
        tasks = result.tasks;
        if (result.created) created.push(result.task);
        else updated.push(result.task);
      } catch {
        skipped += 1;
      }
    }

    for (const priority of briefing.officePriorities || []) {
      if (!priority.autoTask || !AUTO_TASK_SEVERITIES.has(priority.severity)) continue;
      if (priority.sourceId) activeSourceIds.push(priority.sourceId);
      if ((briefing.recommendations || []).some((item) => item.sourceId === priority.sourceId && item.autoTaskTitle)) continue;
      try {
        const result = HalSkills.upsertHalTask(
          tasks,
          {
            title: `${TASK_PREFIX}${priority.title}`,
            priority: priority.severity === "critical" ? "urgent" : "normal",
            notes: priority.detail,
            description: priority.detail,
            source: priority.source,
            sourceId: priority.sourceId,
            surface: priority.surface,
            dueHint: priority.actionHint,
            blockingReason: priority.detail,
            sourceRefs: priority.evidence || [],
          },
          { actor: "hal-office-manager" },
        );
        tasks = result.tasks;
        if (result.created) created.push(result.task);
        else updated.push(result.task);
      } catch {
        skipped += 1;
      }
    }

    tasks = HalSkills.autoResolveHalTasks(tasks, activeSourceIds);
    await persistTasks(tasks);
    return { created, updated, skipped };
  }

  async function runCycle(ctx, options) {
    const force = options && options.force;
    const skipPlacement = options && options.skipPlacement;
    const now = Date.now();
    if (!force && lastCycleAt && now - lastCycleAt < CYCLE_MIN_MS && lastBriefing) {
      return lastBriefing;
    }
    let snapshot =
      ctx && typeof ctx.loadProgramSnapshot === "function" ? await ctx.loadProgramSnapshot() : null;
    if (!snapshot) return null;

    const diagApi = diagnosticsApi();
    const initialDiagnostics =
      (snapshot.importBundle && snapshot.importBundle.diagnostics) ||
      (snapshot.importBundle && diagApi ? diagApi.evaluateBundle(snapshot.importBundle) : null);

    let placement = { placed: false, reason: "skipped", refreshed: false };
    const forcePlacement = options && options.forcePlacement;
    if (!skipPlacement) {
      placement = await runAutonomousPlacement(ctx, initialDiagnostics, { force: forcePlacement });
      const browserOnly = placement.reason === "browser-only" || placement.reason === "no-refresh-path";
      if (!browserOnly && (placement.refreshed || forcePlacement) && typeof ctx.loadProgramSnapshot === "function") {
        snapshot = await ctx.loadProgramSnapshot();
        if (ctx && typeof ctx.refreshHalWidgetFeed === "function") {
          await ctx.refreshHalWidgetFeed(snapshot);
        }
        if (forcePlacement && !placement.refreshed) {
          placement = Object.assign({}, placement, {
            placed: true,
            reason: placement.reason === "data-current" ? "force-widget-feed" : placement.reason,
            refreshed: true,
          });
        }
      }
    }

    const briefing = buildProactiveBriefing(snapshot, ctx);
    applyPlacementToBriefing(briefing, placement);
    briefing.autoTasks = await applyAutoTasks(briefing, ctx);
    const officeApi = officeManagerApi();
    if (officeApi) {
      briefing.officeManager = officeApi.buildOfficeManagerState(snapshot, ctx, briefing);
      if (officeApi.postureFromPriorities) {
        briefing.programPosture = officeApi.postureFromPriorities(briefing.officePriorities || [], placement);
      }
    }
    lastCycleAt = now;
    lastBriefing = briefing;
    return briefing;
  }

  function getLastBriefing() {
    return lastBriefing;
  }

  function shouldSurfaceBanner(briefing) {
    if (!briefing) return false;
    if (briefing.placement && briefing.placement.refreshed) return true;
    if (!briefing.topAction) return false;
    return briefing.programPosture === "needs_attention" || briefing.topAction.severity === "critical";
  }

  function scheduledBriefingKey(kind, date) {
    const d = date || new Date();
    return `${kind}:${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
  }

  async function readScheduledBriefingKey() {
    if (typeof DesktopBridge === "undefined" || !DesktopBridge.storageGet) return null;
    try {
      return await DesktopBridge.storageGet("halScheduledBriefingKey");
    } catch {
      return null;
    }
  }

  async function writeScheduledBriefingKey(key) {
    if (typeof DesktopBridge === "undefined" || !DesktopBridge.storageSet) return;
    try {
      await DesktopBridge.storageSet("halScheduledBriefingKey", key);
    } catch {
      /* optional */
    }
  }

  function currentScheduledBriefingKind() {
    const hour = new Date().getHours();
    if (hour >= 7 && hour < 9) return "morning";
    if (hour >= 17 && hour < 20) return "eod";
    return null;
  }

  async function maybeFireScheduledBriefing(ctx, options) {
    const kind = (options && options.scheduledKind) || currentScheduledBriefingKind();
    if (!kind || !ctx) return null;
    const key = scheduledBriefingKey(kind);
    const last = await readScheduledBriefingKey();
    if (last === key && !(options && options.force)) return null;
    const briefing = await runCycle(ctx, {
      force: true,
      forcePlacement: kind === "morning",
      scheduledKind: kind,
      showScheduledNotice: true,
    });
    await writeScheduledBriefingKey(key);
    if (briefing && typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("nr2:scheduled-briefing", { detail: { kind, briefing } }));
    }
    return briefing;
  }

  function startBriefingScheduler(ctxProvider) {
    if (briefingTimer || typeof window === "undefined") return;
    briefingTimer = setInterval(() => {
      const ctx = typeof ctxProvider === "function" ? ctxProvider() : ctxProvider;
      if (ctx) maybeFireScheduledBriefing(ctx).catch(() => {});
    }, BRIEFING_CHECK_MS);
  }

  function stopBriefingScheduler() {
    if (!briefingTimer) return;
    clearInterval(briefingTimer);
    briefingTimer = null;
  }

  return {
    TASK_PREFIX,
    CYCLE_MIN_MS,
    buildProactiveBriefing,
    formatProactiveBriefing,
    applyAutoTasks,
    runAutonomousPlacement,
    runCycle,
    getLastBriefing,
    shouldSurfaceBanner,
    startPlacementTimer,
    stopPlacementTimer,
    startBriefingScheduler,
    stopBriefingScheduler,
    maybeFireScheduledBriefing,
    needsAutonomousRefresh,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalProactive;
}
if (typeof window !== "undefined") {
  window.HalProactive = HalProactive;
}
