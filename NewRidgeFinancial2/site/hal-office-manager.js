/**
 * HAL internal office manager — priorities, briefings, and task upserts.
 * Autonomous locally; external writeback remains blocked.
 */
const HalOfficeManager = (function () {
  const ROLE_SUMMARY =
    "HAL is the internal office manager: it refreshes local imports, places validated data, prioritizes work, and creates local tasks. External writeback to SoftDent/QuickBooks and all outbound actions remain blocked.";

  const AUTONOMOUS_ALLOWED = [
    "refresh local imports",
    "place validated data into dashboards/widgets",
    "create and update local office tasks",
    "prioritize work queues",
    "monitor sidenotes",
    "draft internal review notes",
    "prepare staff briefings",
  ];

  const EXTERNAL_BLOCKED = [
    "post to QuickBooks",
    "write to SoftDent",
    "submit claims",
    "email/fax/upload/transmit",
    "pay bills",
    "delete records",
    "contact payers/patients/vendors",
    "approve financial transactions externally",
  ];

  function severityRank(severity) {
    if (severity === "critical") return 0;
    if (severity === "warning") return 1;
    if (severity === "info") return 2;
    return 3;
  }

  function categoryForDataset(datasetKey) {
    if (!datasetKey) return "data_sources";
    if (datasetKey.indexOf("claims") >= 0) return "claims";
    if (datasetKey.indexOf("ar") >= 0) return "ar";
    if (datasetKey.indexOf("quickbooks") >= 0 || datasetKey.indexOf("expense") >= 0) return "revenue";
    return "data_sources";
  }

  function navForCategory(category) {
    const map = {
      revenue: "quickbooks",
      claims: "claims",
      ar: "ar",
      accounting: "documents",
      data_sources: "financial",
      local_tasks: "office-manager",
      sidenotes: "hal",
    };
    return map[category] || "office-manager";
  }

  function pushPriority(list, seen, item) {
    if (!item || !item.id || seen.has(item.id)) return;
    seen.add(item.id);
    list.push(item);
  }

  function analyzeImportPriorities(snapshot, list, seen) {
    const diagnostics = snapshot && snapshot.importBundle && snapshot.importBundle.diagnostics;
    if (!diagnostics || !Array.isArray(diagnostics.datasets)) return;
    diagnostics.datasets.forEach((dataset) => {
      if (dataset.status === "connected") return;
      const category = categoryForDataset(dataset.datasetKey);
      const severity =
        dataset.status === "missing" && dataset.severity === "critical"
          ? "critical"
          : dataset.status === "stale"
            ? "warning"
            : dataset.status === "not_configured"
              ? "info"
              : "warning";
      pushPriority(list, seen, {
        id: `office-import-${dataset.datasetKey}`,
        category,
        severity,
        title: `${dataset.datasetKey} is ${dataset.status}`,
        detail: dataset.detail || "Import issue detected.",
        actionHint: dataset.collectorHint || "Review import status and collector configuration.",
        surface: navForCategory(category),
        navTarget: navForCategory(category),
        safetyBoundary: "local_only",
        autoTask: severity === "critical" || severity === "warning",
        source: "import",
        sourceId: `import-${dataset.status}-${dataset.datasetKey}`,
        evidence: [dataset.datasetKey, dataset.status],
      });
    });
  }

  function isExpectedInformationalValidation(issue) {
    const severity = String((issue && issue.severity) || "info").toLowerCase();
    if (severity !== "info") return false;
    const message = String((issue && issue.message) || "").toLowerCase();
    const metric = String((issue && issue.metricKey) || "").toLowerCase();
    // Expected open-month / cross-system scope notes — keep in validation feed, not office top priority.
    if (/informational only|different scopes/.test(message)) return true;
    if (/collections export is pending|export is pending/.test(message)) return true;
    if (/is incomplete|trailing rate/.test(message) && /collection/.test(metric + message)) return true;
    if (metric === "quickbooksartotal" && /softdent operational a\/r/.test(message)) return true;
    return false;
  }

  function validationPriorityTitle(issue) {
    const message = String((issue && issue.message) || "").trim();
    if (message) {
      const first = message.split(/[.—]/)[0].trim();
      if (first.length >= 12 && first.length <= 90) return first;
      if (first.length > 90) return `${first.slice(0, 87)}…`;
    }
    const widget = issue && issue.widgetKey ? String(issue.widgetKey) : "widget";
    const metric = issue && issue.metricKey ? String(issue.metricKey) : "metric";
    return `Review ${widget}: ${metric}`;
  }

  function analyzeWidgetValidationPriorities(snapshot, list, seen) {
    const feed = snapshot && snapshot.widgets;
    if (!feed || !feed.widgets) return;
    const validation = feed.accountingExcelValidation;
    if (validation && Array.isArray(validation.issues)) {
      validation.issues.forEach((issue, index) => {
        if (isExpectedInformationalValidation(issue)) return;
        const severity = issue.severity === "warning" || issue.severity === "critical" ? issue.severity : "info";
        pushPriority(list, seen, {
          id: `office-widget-validation-${issue.widgetKey}-${issue.metricKey || index}`,
          category: issue.widgetKey && issue.widgetKey.indexOf("quickbooks") >= 0 ? "revenue" : "data_sources",
          severity,
          title: validationPriorityTitle(issue),
          detail: issue.message || "Accounting/excel commit validation flagged this metric.",
          actionHint:
            severity === "info"
              ? "Informational cross-check — no staff action required unless totals look wrong."
              : "Reconcile source exports before trusting this widget value.",
          surface: (feed.widgets[issue.widgetKey] && feed.widgets[issue.widgetKey].navTarget) || "financial",
          navTarget: (feed.widgets[issue.widgetKey] && feed.widgets[issue.widgetKey].navTarget) || "financial",
          safetyBoundary: "local_only",
          autoTask: severity === "warning" || severity === "critical",
          source: "widget_validation",
          sourceId: `widget-validation-${issue.widgetKey}-${issue.metricKey || index}`,
          evidence: [issue.widgetKey, issue.metricKey, issue.message].filter(Boolean),
        });
      });
    }
    Object.keys(feed.widgets).forEach((key) => {
      const widget = feed.widgets[key];
      if (!widget || widget.status === "SUCCESS") return;
      if (widget.status !== "FAILED" && widget.status !== "DEGRADED") return;
      pushPriority(list, seen, {
        id: `office-widget-${key}`,
        category: key.indexOf("claim") >= 0 ? "claims" : key.indexOf("ar") >= 0 ? "ar" : "data_sources",
        severity: widget.status === "FAILED" ? "warning" : "info",
        title: `Widget needs data: ${widget.title || key}`,
        detail: widget.summary || "Widget is missing required import data.",
        actionHint: "Open the related page and verify the backing export.",
        surface: widget.navTarget || "financial",
        navTarget: widget.navTarget || "financial",
        safetyBoundary: "local_only",
        autoTask: widget.status === "FAILED",
        source: "widget",
        sourceId: `widget-${key}`,
        evidence: [key, widget.status],
      });
    });
  }

  function analyzeAttentionPriorities(snapshot, list, seen) {
    if (!window.HalSkills) return;
    const tasks = snapshot.officeTasks || [];
    const metrics = HalSkills.computeTaskMetrics(tasks);
    const attention = HalSkills.buildOfficeManagerAttention(snapshot, metrics);
    (attention.items || []).forEach((item) => {
      // Meta rollup of open tasks — useful in attention text, not as a competing office priority.
      if (item.itemId === "local-office-tasks-open") return;
      // Standing capability note, not actionable work.
      if (item.itemId === "vendor-tracker-local-only") return;
      if (item.severity === "info" && (item.count || 0) < 3 && !item.missingDataCodes) return;
      const category =
        item.category === "claims_follow_up"
          ? "claims"
          : item.category === "revenue"
            ? "revenue"
            : item.category === "local_tasks"
              ? "local_tasks"
              : "data_sources";
      pushPriority(list, seen, {
        id: `office-attention-${item.itemId}`,
        category,
        severity: item.severity === "critical" ? "critical" : item.severity === "warning" ? "warning" : "info",
        title: item.title,
        detail: item.detail,
        actionHint: item.actionHint || "Review locally in the office manager console.",
        surface: navForCategory(category),
        navTarget: navForCategory(category),
        safetyBoundary: "local_only",
        autoTask: item.severity === "warning" || item.severity === "critical",
        source: "attention",
        sourceId: `attention-${item.itemId}`,
        evidence: [item.title, item.count != null ? String(item.count) : null].filter(Boolean),
      });
    });
  }

  function analyzeSidenotePriorities(ctx, list, seen) {
    const notes = (ctx && ctx.halSideNotes) || [];
    const active = notes.filter((n) => n.status !== "archived" && n.priority === "high");
    if (!active.length) return;
    pushPriority(list, seen, {
      id: "office-sidenotes-high",
      category: "sidenotes",
      severity: active.length >= 3 ? "warning" : "info",
      title: "High-priority sidenotes need review",
      detail: `${active.length} high-priority sidenote(s) are active.`,
      actionHint: "Review sidenotes in HAL; no external delivery.",
      surface: "hal",
      navTarget: "hal",
      safetyBoundary: "local_only",
      autoTask: active.length >= 3,
      source: "sidenote",
      sourceId: "sidenotes-high-priority",
      evidence: active.slice(0, 3).map((n) => String(n.text || "").slice(0, 80)),
    });
  }

  function buildOfficePriorities(snapshot, ctx) {
    const list = [];
    const seen = new Set();
    analyzeImportPriorities(snapshot, list, seen);
    analyzeWidgetValidationPriorities(snapshot, list, seen);
    analyzeAttentionPriorities(snapshot, list, seen);
    analyzeSidenotePriorities(ctx, list, seen);
    list.sort((a, b) => {
      const rank = severityRank(a.severity) - severityRank(b.severity);
      if (rank !== 0) return rank;
      return String(a.title).localeCompare(String(b.title));
    });
    return list;
  }

  function postureFromPriorities(priorities, placement) {
    if (priorities.some((p) => p.severity === "critical")) return "needs_attention";
    if (placement && placement.refreshed) return "monitor";
    if (priorities.some((p) => p.severity === "warning")) return "monitor";
    return priorities.length ? "monitor" : "healthy";
  }

  function buildOfficeManagerState(snapshot, ctx, briefing) {
    const priorities = (briefing && briefing.officePriorities) || buildOfficePriorities(snapshot, ctx);
    const placement = briefing && briefing.placement;
    const halDid = [];
    if (placement && placement.refreshed) halDid.push("Refreshed local imports and re-placed dashboard data.");
    if (placement && placement.placed && placement.reason === "data-current") halDid.push("Verified imports are current.");
    if (briefing && briefing.autoTasks && briefing.autoTasks.created && briefing.autoTasks.created.length) {
      halDid.push(`Created or updated ${briefing.autoTasks.created.length} local office task(s).`);
    }
    const humanMustApprove = [
      "Posting to QuickBooks",
      "Writing back to SoftDent",
      "Submitting claims or contacting payers",
      "Paying bills or deleting records",
    ];
    return {
      role: "internal_office_manager",
      summary: ROLE_SUMMARY,
      posture: postureFromPriorities(priorities, placement),
      generatedAt: new Date().toISOString(),
      priorities,
      topPriority: priorities[0] || null,
      halDid,
      humanMustApprove,
      autonomousAllowed: AUTONOMOUS_ALLOWED.slice(),
      externalBlocked: EXTERNAL_BLOCKED.slice(),
    };
  }

  function claimsLaneSummary(snapshot) {
    const claims = snapshot && snapshot.claims;
    if (!claims) return null;
    const lanes = claims.laneTotals || claims.byStatus || {};
    const denied = Number(lanes.Denied || lanes.denied || 0) || 0;
    const review = Number(lanes["Needs Review"] || lanes.needsReview || 0) || 0;
    const ready = Number(lanes.Ready || lanes.ready || 0) || 0;
    const draft = Number(lanes.Draft || lanes.draft || 0) || 0;
    const total = Number(claims.total != null ? claims.total : denied + review + ready + draft) || 0;
    if (!total && !denied && !review) return null;
    const rows = claims.claims || claims.top || [];
    let genericPayer = 0;
    let namedPayer = 0;
    rows.forEach((row) => {
      const payer = String((row && (row.payer || row.Payer || row.tag)) || "")
        .trim()
        .toLowerCase();
      if (!payer || payer === "insurance" || payer === "unknown" || payer === "—" || payer === "-") {
        genericPayer += 1;
      } else {
        namedPayer += 1;
      }
    });
    return { total, denied, review, ready, draft, genericPayer, namedPayer, rowCount: rows.length };
  }

  function claimsReadinessBrief(snapshot) {
    const claims = snapshot && snapshot.claims;
    const rows = (claims && (claims.claims || claims.top)) || [];
    if (!rows.length) return null;
    if (typeof HalSkills === "undefined" || typeof HalSkills.buildClaimReadinessResponse !== "function") {
      return null;
    }
    const resp = HalSkills.buildClaimReadinessResponse(rows);
    const s = (resp && resp.summary) || {};
    const items = (resp && resp.items) || [];
    const daysheet = items.filter((i) => i.daysheetDerived).length;
    const highPriority = items.filter((i) => i.priority === "high").length;
    const topGaps = [];
    items.slice(0, 8).forEach((item) => {
      (item.missingItems || []).forEach((m) => {
        if (/Human review/i.test(m)) return;
        if (!topGaps.includes(m) && topGaps.length < 4) topGaps.push(m);
      });
    });
    const aging = resp.agingFollowUp || null;
    return {
      readyCount: Number(s.readyCount || 0) || 0,
      needsReviewCount: Number(s.needsReviewCount || 0) || 0,
      blockedCount: Number(s.blockedCount || 0) || 0,
      genericPayer: items.filter((i) => i.genericPayer).length,
      daysheetDerived: daysheet,
      highPriority,
      agingOver60: Number(s.agingOver60Count || (aging && aging.count) || 0) || 0,
      agingOver90: Number(s.agingOver90Count || (aging && aging.summary && aging.summary.over90) || 0) || 0,
      topGaps,
      examples: items
        .filter((i) => i.status !== "ready" || i.genericPayer || i.agingOver60)
        .slice(0, 3)
        .map((i) => ({
          claimRef: i.claimRef,
          status: i.status,
          summary: i.staffSummary,
          genericPayer: !!i.genericPayer,
          ageDays: i.ageDays,
        })),
    };
  }

  function formatDailyOfficeBriefing(state, snapshot) {
    const office = state || {};
    const priorities = office.priorities || [];
    const lines = [
      "HAL daily office briefing (internal office manager · external firewall locked):",
      office.summary || ROLE_SUMMARY,
      "",
      `Posture: ${office.posture || "unknown"}`,
      "",
      "HAL did internally:",
      ...(office.halDid && office.halDid.length ? office.halDid.map((item) => `- ${item}`) : ["- No autonomous placement actions this cycle."]),
      "",
      "Human must approve before any external action:",
      ...(office.humanMustApprove || EXTERNAL_BLOCKED).map((item) => `- ${item}`),
      "",
    ];
    const claimLanes = claimsLaneSummary(snapshot);
    if (claimLanes) {
      lines.push(
        "Claims from SoftDent import:",
        `- Total ${claimLanes.total} · Denied ${claimLanes.denied} · Needs Review ${claimLanes.review} · Ready ${claimLanes.ready} · Draft ${claimLanes.draft}`,
        claimLanes.denied || claimLanes.review
          ? "- Focus: work Denied / Needs Review before Ready; HAL drafts locally — staff submit."
          : "- No denied or needs-review backlog in the current import.",
      );
      if (claimLanes.rowCount && claimLanes.genericPayer > 0) {
        lines.push(
          `- Carrier gap: ${claimLanes.genericPayer} claim(s) labeled generic "Insurance" (named payers: ${claimLanes.namedPayer}). ` +
            "Claim↔payer join needs SoftDent InsCo / claims export or ODBC sd_claims — daysheet alone cannot supply carriers. Ask HAL: SoftDent extract status.",
        );
      } else if (claimLanes.namedPayer > 0) {
        lines.push(`- Carrier labels present on ${claimLanes.namedPayer} claim(s) — use join_claim_payers for phones/IDs.`);
      }
      const readiness = claimsReadinessBrief(snapshot);
      if (readiness) {
        lines.push(
          `- Packet readiness: Ready ${readiness.readyCount} · Needs review ${readiness.needsReviewCount} · Blocked ${readiness.blockedCount}` +
            (readiness.highPriority ? ` · High priority ${readiness.highPriority}` : "") +
            (readiness.daysheetDerived ? ` · Daysheet-derived ${readiness.daysheetDerived}` : "") +
            ".",
        );
        if (readiness.agingOver60 > 0) {
          lines.push(
            `- Aging follow-up: ${readiness.agingOver60} claim(s) ≥60 days` +
              (readiness.agingOver90 ? ` (${readiness.agingOver90} ≥90)` : "") +
              " — ask HAL for aging list or appeal packet.",
          );
        }
        if (readiness.topGaps.length) {
          lines.push(`- Common gaps: ${readiness.topGaps.join("; ")}.`);
        }
        readiness.examples.forEach((ex) => {
          const age = ex.ageDays != null ? ` · ${ex.ageDays}d` : "";
          lines.push(`- Example ${ex.claimRef || "?"}${age}: ${ex.summary}`);
        });
      }
      lines.push("");
    }
    const ar = snapshot && (snapshot.ar || (snapshot.softdent && snapshot.softdent.ar));
    if (ar) {
      lines.push(
        "A/R collections:",
        "- Ask HAL: who do I call today / build collections queue — staff owns patient contact.",
        "",
      );
    }
    if (!priorities.length) {
      lines.push("No urgent office priorities. HAL will keep monitoring imports, widgets, and local queues.");
      return lines.join("\n");
    }
    lines.push("Top office priorities:");
    priorities.slice(0, 8).forEach((item, index) => {
      lines.push(
        `${index + 1}. [${item.severity}] ${item.title} — ${item.detail} Next: ${item.actionHint} (open ${item.navTarget || item.surface}).`,
      );
    });
    const feed = snapshot && snapshot.widgets;
    if (feed && feed.accountingExcelValidation && feed.accountingExcelValidation.issues && feed.accountingExcelValidation.issues.length) {
      lines.push("", "Data integrity notes:");
      feed.accountingExcelValidation.issues.slice(0, 4).forEach((issue) => {
        lines.push(`- ${issue.widgetKey || "widget"}: ${issue.message || "validation review needed"}`);
      });
    }
    return lines.join("\n");
  }

  return {
    ROLE_SUMMARY,
    AUTONOMOUS_ALLOWED,
    EXTERNAL_BLOCKED,
    buildOfficePriorities,
    buildOfficeManagerState,
    formatDailyOfficeBriefing,
    claimsLaneSummary,
    claimsReadinessBrief,
    postureFromPriorities,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalOfficeManager;
}
if (typeof window !== "undefined") {
  window.HalOfficeManager = HalOfficeManager;
}
