/**
 * HAL orchestrator — multi-agent triage for billing, accounting, claims, compliance, ops.
 */
const HalOrchestrator = (function () {
  const AGENTS = [
    { id: "billing", label: "Billing agent", focus: ["claims", "denials", "narratives", "payer"] },
    { id: "accounting", label: "Accounting agent", focus: ["posting", "journal", "quickbooks", "period close"] },
    { id: "claims", label: "Claims agent", focus: ["packet", "readiness", "submit", "review"] },
    { id: "compliance", label: "Compliance agent", focus: ["consent", "audit", "phi", "policy"] },
    { id: "ops", label: "Ops agent", focus: ["imports", "widgets", "health", "placement"] },
  ];

  let lastTriage = null;

  function scoreItem(text, keywords) {
    const lower = String(text || "").toLowerCase();
    return keywords.reduce((sum, kw) => (lower.includes(kw) ? sum + 1 : sum), 0);
  }

  function triageFromRecommendations(recommendations) {
    const buckets = {};
    AGENTS.forEach((a) => {
      buckets[a.id] = [];
    });
    (recommendations || []).forEach((rec) => {
      const blob = `${rec.title || ""} ${rec.detail || ""} ${rec.sourceId || ""}`;
      let best = "ops";
      let bestScore = 0;
      AGENTS.forEach((agent) => {
        const s = scoreItem(blob, agent.focus);
        if (s > bestScore) {
          bestScore = s;
          best = agent.id;
        }
      });
      buckets[best].push(rec);
    });
    return buckets;
  }

  function triageFromDiagnostics(diagnostics) {
    const items = [];
    if (!diagnostics || !Array.isArray(diagnostics.datasets)) return items;
    diagnostics.datasets.forEach((ds) => {
      if (ds.status === "ok" || ds.status === "current") return;
      items.push({
        severity: ds.status === "missing" ? "critical" : "warning",
        title: `${ds.label || ds.datasetKey || "Dataset"} ${ds.status}`,
        sourceId: `import-${ds.status}-${ds.datasetKey || "unknown"}`,
        detail: ds.message || "Import needs refresh",
      });
    });
    return items;
  }

  function runTriage(ctx, options) {
    const opts = options || {};
    const snapshot = (ctx && ctx.halProgramSnapshot) || {};
    const briefing =
      (typeof HalProactive !== "undefined" && HalProactive.getLastBriefing && HalProactive.getLastBriefing()) || null;
    const recs = (briefing && briefing.recommendations) || [];
    const diagItems = triageFromDiagnostics((ctx && ctx.importDiagnostics) || snapshot.importDiagnostics);
    const combined = recs.slice();
    diagItems.forEach((item) => {
      if (!combined.some((r) => r.sourceId === item.sourceId)) combined.push(item);
    });
    const buckets = triageFromRecommendations(combined);
    const agents = AGENTS.map((agent) => ({
      id: agent.id,
      label: agent.label,
      count: (buckets[agent.id] || []).length,
      items: (buckets[agent.id] || []).slice(0, opts.limitPerAgent || 5),
    }));
    const report = {
      ok: true,
      at: new Date().toISOString(),
      agentCount: AGENTS.length,
      totalItems: combined.length,
      agents,
      topAgent: agents.slice().sort((a, b) => b.count - a.count)[0] || null,
    };
    lastTriage = report;
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("nr2:hal-orchestrator-triage", { detail: report }));
    }
    return report;
  }

  function formatReport(report) {
    if (!report) return "Orchestrator triage unavailable.";
    const lines = [
      `HAL orchestrator — ${report.agentCount} agents · ${report.totalItems} work items.`,
      report.topAgent ? `Lead agent: ${report.topAgent.label} (${report.topAgent.count} items).` : "",
      "",
    ];
    (report.agents || []).forEach((agent) => {
      lines.push(`${agent.label} (${agent.count}):`);
      if (!agent.items.length) {
        lines.push("  — clear");
      } else {
        agent.items.forEach((item, i) => {
          lines.push(`  ${i + 1}. [${item.severity || "info"}] ${item.title || item.sourceId || "—"}`);
        });
      }
      lines.push("");
    });
    return lines.filter(Boolean).join("\n");
  }

  function getLastTriage() {
    return lastTriage;
  }

  return {
    AGENTS,
    runTriage,
    formatReport,
    getLastTriage,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalOrchestrator;
}
if (typeof globalThis !== "undefined") {
  globalThis.HalOrchestrator = HalOrchestrator;
}
if (typeof window !== "undefined") {
  window.HalOrchestrator = HalOrchestrator;
}
