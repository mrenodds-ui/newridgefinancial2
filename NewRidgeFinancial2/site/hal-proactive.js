/**
 * HAL proactive program manager — autonomous internal data placement.
 * HAL runs import refresh and places data into dashboards/widgets (read-only externally).
 */
const HalProactive = (function () {
  const TASK_PREFIX = "HAL: ";
  const CYCLE_MIN_MS = 5 * 60 * 1000;
  const PLACEMENT_TIMER_MS = 5 * 60 * 1000;
  const BRIEFING_CHECK_MS = 60 * 1000;
  const MORNING_BRIEFING_STALE_MS = 18 * 60 * 60 * 1000;
  const MORNING_BRIEFING_KEY = "halLastMorningBriefingAt";
  const MAX_RECOMMENDATIONS = 8;
  const AUTO_TASK_SEVERITIES = new Set(["critical", "warning"]);

  let lastCycleAt = 0;
  let lastBriefing = null;
  let lastMorningBriefing = null;
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

  function analyzeArCollections(snapshot, recommendations, seen) {
    const ar =
      (snapshot && snapshot.ar) ||
      (snapshot && snapshot.softdent && snapshot.softdent.ar) ||
      null;
    const rows = (ar && (ar.rows || ar.top || ar.accounts)) || [];
    let highBucket = 0;
    let total = 0;
    rows.forEach((row) => {
      const bucket = String((row && (row.Aging || row.Bucket || row.bucket || row.label)) || "");
      const bal = Number(
        String((row && (row.Balance || row.Outstanding || row.amount || row.Amount)) || "0")
          .replace(/[$,]/g, "")
      );
      if (!Number.isFinite(bal) || bal <= 0) return;
      total += 1;
      if (/90|120|\+/.test(bucket)) highBucket += 1;
    });
    // Also use A/R KPI tiles when row-level data is thin
    const kpis = (ar && ar.kpis) || [];
    const kpi90 = kpis.find((k) => /90/i.test(String((k && k.label) || "")));
    if (!total && kpi90 && /[1-9]/.test(String(kpi90.value || ""))) {
      highBucket = 1;
      total = 1;
    }
    if (!total && !highBucket) return;
    pushRecommendation(recommendations, seen, {
      id: "ar-collections-call-list",
      severity: highBucket > 0 ? "warning" : "info",
      title: "Collections call list ready",
      rationale:
        highBucket > 0
          ? `${highBucket} A/R line(s) in 90+ aging — work the seeded collections queue before write-off risk.`
          : `${total} A/R balance(s) available — work seeded collections queue for staff follow-up.`,
      action: { type: "command", command: "Who do I call today for collections?" },
      // Prefer seeded-queue wording; morning tick already writes collections_seed work rows.
      autoTaskTitle: `${TASK_PREFIX}Work seeded collections queue`,
      sourceId: "collections-queue-open",
    });
  }

  async function fetchAutonomousWork() {
    try {
      const bridge =
        typeof DesktopBridge !== "undefined"
          ? DesktopBridge
          : typeof window !== "undefined"
            ? window.DesktopBridge
            : null;
      if (!bridge || typeof bridge.loopbackJson !== "function") return null;
      const data = await bridge.loopbackJson("/api/scheduler/work?openOnly=1&limit=50", { method: "GET" });
      if (!data || !data.ok) return null;
      return data.items || [];
    } catch {
      return null;
    }
  }

  function analyzeClaimsAging(snapshot, recommendations, seen) {
    const claims = snapshot && snapshot.claims;
    const rows = (claims && (claims.claims || claims.top)) || [];
    if (
      !rows.length ||
      typeof HalSkills === "undefined" ||
      typeof HalSkills.buildClaimsAgingFollowUp !== "function"
    ) {
      return;
    }
    const aging = HalSkills.buildClaimsAgingFollowUp(rows, { minDays: 60 });
    if (!aging || !aging.count) return;
    const over90 = (aging.summary && aging.summary.over90) || 0;
    pushRecommendation(recommendations, seen, {
      id: "claims-aging-followup",
      severity: over90 > 0 || (aging.summary && aging.summary.denied) ? "critical" : "warning",
      title: "Claims aging follow-up",
      rationale:
        `${aging.count} claim(s) ≥60 days` +
        (over90 ? ` (${over90} ≥90)` : "") +
        " — schedule claims_aging call / appeal packet; staff owns dial.",
      action: { type: "command", command: "List claims aging follow-up over 60 days" },
      autoTaskTitle: `${TASK_PREFIX}Work claims aging ≥60 days (${aging.count})`,
    });
  }

  function analyzeCollectionDepositVariance(snapshot, recommendations, seen) {
    const api =
      typeof NR2Analytics !== "undefined"
        ? NR2Analytics
        : typeof window !== "undefined" && window.NR2Analytics
          ? window.NR2Analytics
          : null;
    if (!api || typeof api.collectionDepositVariance !== "function") return;
    const depVar = api.collectionDepositVariance(snapshot);
    if (!depVar || !depVar.hasData || depVar.variancePct == null) return;
    const threshold = depVar.thresholdPct != null ? Number(depVar.thresholdPct) : 8;
    if (Math.abs(depVar.variancePct) <= threshold) return;
    pushRecommendation(recommendations, seen, {
      id: "collection-deposit-variance",
      severity: Math.abs(depVar.variancePct) > threshold * 1.5 ? "critical" : "warning",
      title: "Collections vs QuickBooks deposits variance",
      rationale: depVar.summary || `Variance ${depVar.variancePct}% exceeds ${threshold}% review threshold.`,
      action: { type: "command", command: "Draft deposit reconciliation from collections vs deposits" },
      autoTaskTitle: `${TASK_PREFIX}Review collections vs QB deposits (${depVar.period || "latest"})`,
      depositVariance: {
        period: depVar.period,
        softdentCollections: depVar.softdentCollections,
        quickbooksDeposits: depVar.quickbooksDeposits,
        variancePct: depVar.variancePct,
      },
    });
  }

  function analyzeCrossDomain(snapshot, recommendations, seen) {
    const cross =
      typeof HalSkills !== "undefined" && HalSkills.crossReconcileSkill
        ? HalSkills.crossReconcileSkill(snapshot)
        : null;
    if (!cross || !cross.sentence) return cross;
    const severity = cross.risk ? (cross.domains.includes("imports") ? "critical" : "warning") : "info";
    pushRecommendation(recommendations, seen, {
      id: "cross-domain-synthesis",
      severity,
      title: "Cross-domain synthesis",
      rationale: cross.sentence,
      action: cross.actuators && cross.actuators[0] && cross.actuators[0].actionId === "navigate"
        ? { type: "navigate", target: cross.actuators[0].target || "financial" }
        : { type: "command", command: "Show cross-domain briefing" },
      autoTaskTitle: severity === "critical" ? `${TASK_PREFIX}Review cross-domain variance` : null,
      crossDomain: cross,
    });
    return cross;
  }

  function buildMorningBriefingCard(snapshot) {
    const cross =
      typeof HalSkills !== "undefined" && HalSkills.crossReconcileSkill
        ? HalSkills.crossReconcileSkill(snapshot)
        : {
            sentence: "Cross-domain briefing unavailable — refresh imports and reload.",
            domains: [],
            kpiTiles: [],
            actuators: [{ label: "Refresh imports", actionId: "refresh-imports", requiresConsent: true }],
          };
    const feed = snapshot && snapshot.widgets;
    const importHealth = feed && feed.widgets && feed.widgets.halImportHealth;
    const ribbonWidget = feed && feed.widgets && feed.widgets.nr2KpiRibbon;
    const kpiTiles =
      cross.kpiTiles && cross.kpiTiles.length
        ? cross.kpiTiles
        : ribbonWidget && ribbonWidget.metrics
          ? Object.keys(ribbonWidget.metrics)
              .slice(0, 4)
              .map((key) => ({ label: key, value: ribbonWidget.metrics[key], tone: "neutral" }))
          : [];
    const claims = snapshot && snapshot.claims;
    const lanes = (claims && (claims.laneTotals || claims.byStatus)) || {};
    const claimRows = (claims && (claims.claims || claims.top)) || [];
    let genericPayer = 0;
    let namedPayer = 0;
    claimRows.forEach((row) => {
      const payer = String((row && (row.payer || row.Payer || row.tag)) || "")
        .trim()
        .toLowerCase();
      if (!payer || payer === "insurance" || payer === "unknown" || payer === "—" || payer === "-") {
        genericPayer += 1;
      } else {
        namedPayer += 1;
      }
    });
    let readiness = null;
    if (
      claimRows.length &&
      typeof HalSkills !== "undefined" &&
      typeof HalSkills.buildClaimReadinessResponse === "function"
    ) {
      const resp = HalSkills.buildClaimReadinessResponse(claimRows);
      const s = (resp && resp.summary) || {};
      const items = (resp && resp.items) || [];
      readiness = {
        readyCount: Number(s.readyCount || 0) || 0,
        needsReviewCount: Number(s.needsReviewCount || 0) || 0,
        blockedCount: Number(s.blockedCount || 0) || 0,
        daysheetDerived: items.filter((i) => i.daysheetDerived).length,
        highPriority: items.filter((i) => i.priority === "high").length,
        topGaps: [],
      };
      items.slice(0, 8).forEach((item) => {
        (item.missingItems || []).forEach((m) => {
          if (/Human review/i.test(m)) return;
          if (!readiness.topGaps.includes(m) && readiness.topGaps.length < 3) readiness.topGaps.push(m);
        });
      });
    }
    let aging = null;
    if (
      claimRows.length &&
      typeof HalSkills !== "undefined" &&
      typeof HalSkills.buildClaimsAgingFollowUp === "function"
    ) {
      const agingResp = HalSkills.buildClaimsAgingFollowUp(claimRows, { minDays: 60 });
      aging = {
        count: agingResp.count || 0,
        over90: (agingResp.summary && agingResp.summary.over90) || 0,
        denied: (agingResp.summary && agingResp.summary.denied) || 0,
        top: (agingResp.items || []).slice(0, 3).map((i) => ({
          claimRef: i.claimRef,
          ageDays: i.ageDays,
          status: i.status,
          payerLabel: i.payerLabel,
        })),
      };
    }
    const claimsSummary = claims
      ? {
          total: Number(claims.total || 0) || 0,
          denied: Number(lanes.Denied || lanes.denied || 0) || 0,
          needsReview: Number(lanes["Needs Review"] || lanes.needsReview || 0) || 0,
          ready: Number(lanes.Ready || lanes.ready || 0) || 0,
          genericPayer,
          namedPayer,
          readiness,
          aging,
        }
      : null;
    return {
      generatedAt: new Date().toISOString(),
      kind: "morning",
      sentence: cross.sentence,
      domains: cross.domains || [],
      risk: cross.risk || null,
      opportunity: cross.opportunity || null,
      importHealthStatus: cross.importHealthStatus || (importHealth && importHealth.status) || "UNKNOWN",
      importHealthSummary: cross.importHealthSummary || (importHealth && importHealth.summary) || "",
      claimsSummary,
      eraPending: null,
      postingPending: null,
      softdentOdbc: null,
      kpiTiles,
      actuators: cross.actuators || [],
      reconSummary: cross.reconSummary || "",
      netIncomeLatest: cross.netIncomeLatest != null ? cross.netIncomeLatest : null,
    };
  }

  async function fetchPostingPendingSummary() {
    try {
      const bridge =
        typeof DesktopBridge !== "undefined"
          ? DesktopBridge
          : typeof window !== "undefined"
            ? window.DesktopBridge
            : null;
      if (!bridge || typeof bridge.loopbackJson !== "function") return null;
      const data = await bridge.loopbackJson("/api/posting-queue?limit=25&status=pending_review", {
        method: "GET",
      });
      const items = (data && data.items) || [];
      return {
        count: items.length,
        top: items.slice(0, 3).map((i) => ({
          queueId: i.queue_id || i.queueId || i.id,
          amount: i.amount,
          description: i.description,
        })),
      };
    } catch {
      return null;
    }
  }

  async function fetchSoftdentOdbcBrief() {
    try {
      const bridge =
        typeof DesktopBridge !== "undefined"
          ? DesktopBridge
          : typeof window !== "undefined"
            ? window.DesktopBridge
            : null;
      if (!bridge || typeof bridge.loopbackJson !== "function") return null;
      const data = await bridge.loopbackJson("/api/softdent/odbc-status", { method: "GET" });
      if (!data) return null;
      const counts = data.tableCounts || {};
      const sdClaims = Number(counts.sd_claims || 0) || 0;
      const hasClaimsQuery = Array.isArray(data.configuredQueryTables)
        ? data.configuredQueryTables.includes("sd_claims")
        : false;
      return {
        odbcConfigured: !!data.odbcConfigured,
        stale: !!data.stale,
        sdClaimsRows: sdClaims,
        hasClaimsQuery,
        lastMode: data.lastMode || null,
        nextSteps: (data.nextSteps || []).slice(0, 2),
      };
    } catch {
      return null;
    }
  }

  async function fetchEraPendingSummary() {
    try {
      const bridge =
        typeof DesktopBridge !== "undefined"
          ? DesktopBridge
          : typeof window !== "undefined"
            ? window.DesktopBridge
            : null;
      if (!bridge || typeof bridge.loopbackJson !== "function") return null;
      const data = await bridge.loopbackJson("/api/era/pending-matches?limit=25", { method: "GET" });
      if (!data || !data.ok) return null;
      const items = data.items || [];
      return {
        count: items.length,
        lowConfidence: items.filter((i) => i.confidenceBadge === "low" || Number(i.confidence || 0) < 0.6).length,
        top: items.slice(0, 3).map((i) => ({
          referenceId: i.referenceId || i.id,
          predictedClaimId: i.predictedClaimId,
          confidenceBadge: i.confidenceBadge,
          paidAmount: i.paidAmount,
        })),
      };
    } catch {
      return null;
    }
  }

  async function analyzeEraPending(recommendations, seen) {
    const era = await fetchEraPendingSummary();
    if (!era || !era.count) return;
    pushRecommendation(recommendations, seen, {
      id: "era-pending-matches",
      severity: era.lowConfidence > 0 ? "warning" : "info",
      title: "ERA/EOB matches need review",
      rationale: `${era.count} pending match(es)` + (era.lowConfidence ? ` · ${era.lowConfidence} low confidence` : "") + " — confirm before posting.",
      action: { type: "command", command: "List pending ERA matches" },
      autoTaskTitle: `${TASK_PREFIX}Review ERA/EOB pending matches (${era.count})`,
    });
  }

  async function analyzePostingPending(recommendations, seen) {
    const posting = await fetchPostingPendingSummary();
    if (!posting || !posting.count) return;
    pushRecommendation(recommendations, seen, {
      id: "posting-queue-pending",
      severity: posting.count >= 5 ? "warning" : "info",
      title: "Accounting posting queue needs review",
      rationale: `${posting.count} journal(s) awaiting staff approve/export — not posted live.`,
      action: { type: "command", command: "List posting queue" },
      autoTaskTitle: `${TASK_PREFIX}Review posting queue (${posting.count})`,
    });
  }

  async function analyzeSoftdentOdbcGap(recommendations, seen, snapshot) {
    const odbc = await fetchSoftdentOdbcBrief();
    const claims = snapshot && snapshot.claims;
    const claimRows = (claims && (claims.claims || claims.top)) || [];
    let generic = 0;
    claimRows.forEach((row) => {
      const payer = String((row && (row.payer || row.Payer || row.tag)) || "")
        .trim()
        .toLowerCase();
      if (!payer || payer === "insurance" || payer === "unknown" || payer === "—" || payer === "-") {
        generic += 1;
      }
    });
    if (!odbc && !generic) return;
    if (generic > 0 || (odbc && odbc.odbcConfigured && !odbc.hasClaimsQuery && (odbc.sdClaimsRows || 0) === 0)) {
      pushRecommendation(recommendations, seen, {
        id: "softdent-named-payer-gap",
        severity: generic > 0 ? "warning" : "info",
        title: "SoftDent named-payer / ODBC gap",
        rationale:
          (generic > 0 ? `${generic} claim(s) still say generic Insurance. ` : "") +
          (odbc
            ? `ODBC ${odbc.odbcConfigured ? "on" : "off"} · claims query ${odbc.hasClaimsQuery ? "ready" : "missing"} · sd_claims ${odbc.sdClaimsRows || 0}.`
            : "Ask HAL for SoftDent extract status."),
        action: { type: "command", command: "SoftDent extract status" },
        autoTaskTitle: `${TASK_PREFIX}Close SoftDent named-payer gap`,
      });
    }
  }

  async function enrichMorningBriefingCard(card) {
    if (!card) return card;
    const [era, posting, odbc] = await Promise.all([
      fetchEraPendingSummary(),
      fetchPostingPendingSummary(),
      fetchSoftdentOdbcBrief(),
    ]);
    if (era) card.eraPending = era;
    if (posting) card.postingPending = posting;
    if (odbc) card.softdentOdbc = odbc;
    return card;
  }

  function isMorningBriefingStale(lastAt, nowMs) {
    const now = nowMs != null ? nowMs : Date.now();
    if (!lastAt || !Number.isFinite(lastAt)) return true;
    return now - lastAt > MORNING_BRIEFING_STALE_MS;
  }

  async function readLastMorningBriefingAt() {
    if (typeof DesktopBridge !== "undefined" && DesktopBridge.storageGet) {
      try {
        const raw = await DesktopBridge.storageGet(MORNING_BRIEFING_KEY);
        if (raw != null) {
          const n = Number(raw);
          return Number.isFinite(n) ? n : Date.parse(String(raw)) || 0;
        }
      } catch {
        /* optional */
      }
    }
    if (typeof localStorage !== "undefined") {
      try {
        const raw = localStorage.getItem(MORNING_BRIEFING_KEY);
        if (raw) {
          const n = Number(raw);
          return Number.isFinite(n) ? n : Date.parse(raw) || 0;
        }
      } catch {
        /* optional */
      }
    }
    return 0;
  }

  async function writeLastMorningBriefingAt(ts) {
    const value = ts != null ? ts : Date.now();
    if (typeof DesktopBridge !== "undefined" && DesktopBridge.storageSet) {
      try {
        await DesktopBridge.storageSet(MORNING_BRIEFING_KEY, value);
      } catch {
        /* optional */
      }
    }
    if (typeof localStorage !== "undefined") {
      try {
        localStorage.setItem(MORNING_BRIEFING_KEY, String(value));
      } catch {
        /* optional */
      }
    }
  }

  function formatMorningBriefingCard(card) {
    if (!card) return "Morning briefing unavailable.";
    const lines = ["HAL morning briefing (cross-domain · consent-gated actions):", card.sentence || ""];
    if (card.domains && card.domains.length) {
      lines.push(`Domains: ${card.domains.join(", ")}.`);
    }
    if (card.importHealthSummary) {
      lines.push(`Import health: ${card.importHealthStatus || "—"} — ${card.importHealthSummary}`);
    }
    if (card.claimsSummary) {
      const c = card.claimsSummary;
      lines.push(
        `Claims import: ${c.total || 0} total · Denied ${c.denied || 0} · Needs Review ${c.needsReview || 0} · Ready ${c.ready || 0}.`,
      );
      if ((c.denied || 0) + (c.needsReview || 0) > 0) {
        lines.push("Billing focus: clear Denied / Needs Review lanes; HAL can draft narratives locally.");
      }
      if ((c.genericPayer || 0) > 0) {
        lines.push(
          `Carrier gap: ${c.genericPayer} claim(s) still say "Insurance" (named: ${c.namedPayer || 0}). Prefer SoftDent claims export / ODBC for real Payer labels.`,
        );
      }
      if (c.readiness) {
        const r = c.readiness;
        lines.push(
          `Packet readiness: Ready ${r.readyCount} · Needs review ${r.needsReviewCount} · Blocked ${r.blockedCount}` +
            (r.highPriority ? ` · High priority ${r.highPriority}` : "") +
            (r.daysheetDerived ? ` · Daysheet-derived ${r.daysheetDerived}` : "") +
            ".",
        );
        if (r.topGaps && r.topGaps.length) {
          lines.push(`Common claim gaps: ${r.topGaps.join("; ")}.`);
        }
      }
      if (c.aging && c.aging.count > 0) {
        lines.push(
          `Aging follow-up: ${c.aging.count} claim(s) ≥60 days` +
            (c.aging.over90 ? ` (${c.aging.over90} ≥90)` : "") +
            (c.aging.denied ? ` · ${c.aging.denied} denied` : "") +
            ".",
        );
        (c.aging.top || []).forEach((row) => {
          lines.push(
            `- ${row.claimRef || "?"} · ${row.ageDays}d · ${row.status || "?"} · ${row.payerLabel || "Insurance"}`,
          );
        });
        lines.push("Ask HAL: list claims aging follow-up / build appeal packet for a denied claim.");
      }
    }
    if (card.eraPending && card.eraPending.count > 0) {
      lines.push(
        `ERA/EOB pending review: ${card.eraPending.count}` +
          (card.eraPending.lowConfidence ? ` (${card.eraPending.lowConfidence} low confidence)` : "") +
          ".",
      );
      (card.eraPending.top || []).forEach((row) => {
        lines.push(
          `- ${row.referenceId || "?"} → claim ${row.predictedClaimId || "?"} · ${row.confidenceBadge || "?"}` +
            (row.paidAmount != null ? ` · $${row.paidAmount}` : ""),
        );
      });
      lines.push("Ask HAL: list pending ERA matches — staff confirms before posting.");
    }
    if (card.postingPending && card.postingPending.count > 0) {
      lines.push(`Posting queue pending review: ${card.postingPending.count}.`);
      (card.postingPending.top || []).forEach((row) => {
        lines.push(
          `- ${row.queueId || "?"} · $${row.amount ?? "?"} · ${String(row.description || "journal").slice(0, 80)}`,
        );
      });
      lines.push("Ask HAL: list posting queue / batch approve postings (consent-gated).");
    }
    if (card.softdentOdbc) {
      const o = card.softdentOdbc;
      const named = card.claimsSummary && card.claimsSummary.namedPayer;
      const generic = card.claimsSummary && card.claimsSummary.genericPayer;
      lines.push(
        `SoftDent ODBC/extract: ${o.odbcConfigured ? "DSN configured" : "DSN not set"}` +
          (o.hasClaimsQuery ? " · claims query ready" : " · claims query missing") +
          ` · sd_claims ${o.sdClaimsRows || 0}` +
          (o.stale ? " · stale" : "") +
          (named != null ? ` · named payers ${named}` : "") +
          (generic ? ` · generic Insurance ${generic}` : "") +
          ".",
      );
      (o.nextSteps || []).slice(0, 1).forEach((step) => lines.push(`- Next: ${step}`));
      if (generic > 0 || (!named && (card.claimsSummary || {}).total > 0)) {
        lines.push("Ask HAL: SoftDent extract status — named Payer labels need claims CSV/ODBC.");
      }
    }
    if (card.kpiTiles && card.kpiTiles.length) {
      lines.push(
        "KPI ribbon:",
        ...card.kpiTiles.map((tile) => `- ${tile.label}: ${tile.value}`),
      );
    }
    if (card.reconSummary) {
      lines.push(`Deposit / recon note: ${card.reconSummary}`);
      lines.push("Ask HAL: draft deposit reconciliation from collections vs deposits.");
    }
    return lines.join("\n");
  }

  async function maybeFireMorningBriefingOnBoot(ctx, options) {
    if (!ctx) return null;
    const force = options && options.force;
    const lastAt = await readLastMorningBriefingAt();
    if (!force && !isMorningBriefingStale(lastAt)) {
      return lastMorningBriefing;
    }
    let snapshot =
      typeof ctx.loadProgramSnapshot === "function" ? await ctx.loadProgramSnapshot() : null;
    if (!snapshot) return null;
    if (typeof ctx.refreshHalWidgetFeed === "function") {
      const feed = await ctx.refreshHalWidgetFeed(snapshot);
      if (feed) snapshot = Object.assign({}, snapshot, { widgets: feed });
    }
    let card = buildMorningBriefingCard(snapshot);
    card = (await enrichMorningBriefingCard(card)) || card;
    lastMorningBriefing = card;
    await writeLastMorningBriefingAt(Date.now());
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("nr2:morning-briefing", { detail: { card } }));
    }
    return card;
  }

  function getLastMorningBriefing() {
    return lastMorningBriefing;
  }

  function buildProactiveBriefing(snapshot, ctx) {
    const recommendations = [];
    const seen = new Set();
    const crossDomain = analyzeCrossDomain(snapshot, recommendations, seen);
    const diagnostics = analyzeImportDiagnostics(snapshot, recommendations, seen);
    analyzeDataQuality(snapshot, recommendations, seen);
    analyzeCollectionDepositVariance(snapshot, recommendations, seen);
    analyzeArCollections(snapshot, recommendations, seen);
    analyzeClaimsAging(snapshot, recommendations, seen);
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
      crossDomain,
      morningBriefing: buildMorningBriefingCard(snapshot),
    };
  }

  async function buildProactiveBriefingAsync(snapshot, ctx) {
    const briefing = buildProactiveBriefing(snapshot, ctx);
    const seen = new Set((briefing.recommendations || []).map((r) => r.id));
    await Promise.all([
      analyzeEraPending(briefing.recommendations, seen),
      analyzePostingPending(briefing.recommendations, seen),
      analyzeSoftdentOdbcGap(briefing.recommendations, seen, snapshot),
    ]);
    briefing.recommendations.sort((a, b) => {
      const rank = severityRank(a.severity) - severityRank(b.severity);
      if (rank !== 0) return rank;
      return String(a.title).localeCompare(String(b.title));
    });
    briefing.recommendations = briefing.recommendations.slice(0, MAX_RECOMMENDATIONS);
    briefing.recommendationCount = briefing.recommendations.length;
    briefing.topAction = briefing.recommendations[0] || null;
    if (briefing.topAction) {
      briefing.headline = `HAL is acting: ${briefing.topAction.title}`;
      briefing.programPosture =
        briefing.topAction.severity === "critical" ? "needs_attention" : "monitor";
    }
    if (briefing.morningBriefing) {
      briefing.morningBriefing = await enrichMorningBriefingCard(briefing.morningBriefing);
    }
    return briefing;
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
      briefing.headline = "HAL placement needs the NR2 server — run StartProgram.bat and open http://127.0.0.1:8765/.";
      briefing.programPosture = "monitor";
    } else if (placement && placement.reason === "no-refresh-path") {
      briefing.headline = "HAL could not refresh imports — ensure StartProgram.bat is running and reload the browser tab.";
      briefing.programPosture = "monitor";
    }
    return briefing;
  }

  function formatProactiveBriefing(briefing, opts) {
    if (!briefing) return "Proactive briefing unavailable.";
    opts = opts || {};
    const spokenMode = opts.spoken === true;
    const chatMode = opts.chatMode === true || spokenMode;

    if (chatMode) {
      const lines = [briefing.headline || "Here's what needs attention."];
      if (briefing.placement) {
        const refreshNote =
          briefing.placement.refreshed && briefing.placement.reason !== "browser-only"
            ? " Imports refreshed."
            : briefing.placement.reason === "browser-only"
              ? " NR2 server offline — run StartProgram.bat."
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
      "HAL internal office manager (local placement · consent-gated outbound):",
      briefing.headline,
      briefing.independenceNote,
      "",
    ];
    if (briefing.placement) {
      const refreshNote =
        briefing.placement.refreshed && briefing.placement.reason !== "browser-only"
          ? " — import refresh completed."
          : briefing.placement.reason === "browser-only"
            ? " — NR2 server offline (run StartProgram.bat)."
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

    // Sync headless scheduler work ledger → office tasks (survives UI-closed morning ticks)
    const ledger = (await fetchAutonomousWork()) || [];
    if (ledger.length) {
      briefing.autonomousWork = ledger;
      for (const row of ledger) {
        const sourceId = row.sourceId || row.id;
        if (sourceId) activeSourceIds.push(sourceId);
        const pri = row.priority === "urgent" ? "urgent" : "normal";
        try {
          const result = HalSkills.upsertHalTask(
            tasks,
            {
              title: row.title && String(row.title).startsWith(TASK_PREFIX) ? row.title : `${TASK_PREFIX}${row.title}`,
              priority: pri,
              notes: row.detail,
              description: row.detail,
              source: "hal-autonomous-work",
              sourceId,
              dueHint: row.kind,
              blockingReason: row.detail,
              sourceRefs: row.meta ? [row.meta] : [],
            },
            { actor: "hal-scheduler" },
          );
          tasks = result.tasks;
          if (result.created) created.push(result.task);
          else updated.push(result.task);
        } catch {
          skipped += 1;
        }
      }
    }

    tasks = HalSkills.autoResolveHalTasks(tasks, activeSourceIds);
    await persistTasks(tasks);
    return { created, updated, skipped, autonomousWorkCount: ledger.length };
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

    const briefing = await buildProactiveBriefingAsync(snapshot, ctx);
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
      if (typeof HalVoice !== "undefined" && HalVoice.speakHalBriefing && !window.HAL_SKIP_SPEECH) {
        const IT = typeof HalIndependentThought !== "undefined" ? HalIndependentThought : null;
        if (IT && IT.isEnabled(ctx.halModels)) {
          /* Independent thought: no scheduled briefing script read aloud. */
        } else {
        const spoken = formatProactiveBriefing(briefing, { spoken: true });
        HalVoice.speakHalBriefing(spoken, { kind }).catch(() => {});
        }
      }
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
    MORNING_BRIEFING_STALE_MS,
    MORNING_BRIEFING_KEY,
    buildProactiveBriefing,
    buildProactiveBriefingAsync,
    enrichMorningBriefingCard,
    buildMorningBriefingCard,
    formatMorningBriefingCard,
    formatProactiveBriefing,
    isMorningBriefingStale,
    readLastMorningBriefingAt,
    writeLastMorningBriefingAt,
    maybeFireMorningBriefingOnBoot,
    getLastMorningBriefing,
    applyAutoTasks,
    fetchAutonomousWork,
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
