/**
 * Enforced widget metric contract — no cross-source fallbacks.
 * Browser + Node compatible.
 */
const WidgetContract = (function () {
  const MISSING = "—";
  const NOT_CONFIGURED = "Not Configured";

  const FALLBACK_WIDGETS = {
    practiceFinancialOverview: {
      title: "Practice Financial Overview",
      navTarget: "financial",
      metrics: {
        monthlyRevenue: { dataset: "quickbooks.revenue", dashboard: "quickbooks", path: "revenue" },
        monthlyNetIncome: { dataset: "quickbooks.revenue", dashboard: "quickbooks", compute: "qbNetIncome" },
        productionTotal: { dataset: "softdent.dashboard", dashboard: "softdent", path: "production" },
        collectionsTotal: { dataset: "softdent.dashboard", dashboard: "softdent", path: "collections" },
      },
    },
    financialProductionTrend: {
      title: "Production Trend & YTD",
      navTarget: "financial",
      metrics: {
        productionMtd: { dataset: "softdent.dashboard", dashboard: "financial", path: "productionMtd.value" },
        productionTrendLatest: { dataset: "softdent.dashboard", dashboard: "financial", path: "productionTrend.production", index: -1 },
        ytdProduction: { dataset: "softdent.dashboard", dashboard: "financial", path: "productionTrend.ytd", label: "YTD Production" },
        ytdCollectionRate: { dataset: "softdent.dashboard", dashboard: "financial", path: "productionTrend.ytd", label: "Trailing Collection Rate" },
      },
    },
    nr2ProductionReconciliation: {
      title: "Production vs QuickBooks Reconciliation",
      navTarget: "financial",
      metrics: {
        productionTrendLatest: { dataset: "softdent.dashboard", dashboard: "financial", path: "productionTrend.production", index: -1 },
        monthlyRevenue: { dataset: "quickbooks.revenue", dashboard: "quickbooks", path: "revenue" },
      },
    },
    nr2CollectionLag: {
      title: "Collection Lag (DSO)",
      navTarget: "financial",
      metrics: {
        collectionRate: { dataset: "softdent.dashboard", dashboard: "financial", path: "payerMix.rate" },
        totalOutstanding: { dataset: "softdent.ar", dashboard: "ar", path: "kpis", index: 0, subpath: "value" },
      },
    },
    nr2KpiRibbon: {
      title: "Cross-Analytics KPI Ribbon",
      navTarget: "financial",
      metrics: {
        productionTotal: { dataset: "softdent.dashboard", dashboard: "softdent", path: "production" },
        monthlyRevenue: { dataset: "quickbooks.revenue", dashboard: "quickbooks", path: "revenue" },
      },
    },
    softdentProductionDaily: {
      title: "SoftDent Production Trend",
      navTarget: "financial",
      metrics: {
        productionTrendLatest: { dataset: "softdent.dashboard", dashboard: "financial", path: "productionTrend.production", index: -1 },
        productionMtd: { dataset: "softdent.dashboard", dashboard: "financial", path: "productionMtd.value" },
      },
    },
    quickbooksMonthlyRevenue: {
      title: "Monthly Revenue Trend",
      navTarget: "quickbooks",
      metrics: {
        monthlyRevenue: { dataset: "quickbooks.revenue", dashboard: "quickbooks", path: "revenue" },
        monthlyExpensesLatest: { dataset: "quickbooks.expenses", dashboard: "quickbooks", path: "expenses" },
      },
    },
    payerMixAndCollections: {
      title: "Payer Mix & Collections",
      navTarget: "financial",
      metrics: {
        payerMixTotal: { dataset: "softdent.dashboard", dashboard: "financial", path: "payerMix.total" },
        collectionRate: { dataset: "softdent.dashboard", dashboard: "financial", path: "payerMix.rate" },
        topPayer: { dataset: "softdent.dashboard", dashboard: "financial", path: "payerMix.slices", index: 0, subpath: "label" },
        topPayerShare: { dataset: "softdent.dashboard", dashboard: "financial", path: "payerMix.slices", index: 0, subpath: "pct", suffix: "%" },
      },
    },
    providerPerformance: {
      title: "Provider Performance",
      navTarget: "financial",
      metrics: {
        providerCount: { dataset: "softdent.dashboard", dashboard: "financial", path: "providers.rows", length: true },
        topProvider: { dataset: "softdent.dashboard", dashboard: "financial", path: "providers.rows", index: 0, subpath: "name" },
        topProviderProduction: { dataset: "softdent.dashboard", dashboard: "financial", path: "providers.rows", index: 0, subpath: "amount" },
        providerTotal: { dataset: "softdent.dashboard", dashboard: "financial", path: "providers.total.amount" },
      },
    },
    newPatients: {
      title: "New Patients",
      navTarget: "softdent",
      metrics: {
        newPatientCount: { dataset: "softdent.newPatients", dashboard: "practice", path: "newPatients.count" },
        period: { dataset: "softdent.newPatients", dashboard: "practice", path: "newPatients.period" },
      },
    },
    treatmentPlanSummary: {
      title: "Treatment Plan Summary",
      navTarget: "softdent",
      metrics: {
        plansPresented: { dataset: "softdent.treatmentPlans", dashboard: "practice", path: "treatmentPlans.presented" },
        plansAccepted: { dataset: "softdent.treatmentPlans", dashboard: "practice", path: "treatmentPlans.accepted" },
        presentedValue: { dataset: "softdent.treatmentPlans", dashboard: "practice", path: "treatmentPlans.presentedValue" },
      },
    },
    caseAcceptance: {
      title: "Case Acceptance",
      navTarget: "softdent",
      metrics: {
        acceptanceRate: { dataset: "softdent.caseAcceptance", dashboard: "practice", path: "caseAcceptance.rate" },
        acceptedCount: { dataset: "softdent.caseAcceptance", dashboard: "practice", path: "caseAcceptance.accepted" },
        presentedCount: { dataset: "softdent.caseAcceptance", dashboard: "practice", path: "caseAcceptance.presented" },
      },
    },
    hygieneRecall: {
      title: "Hygiene & Recall",
      navTarget: "softdent",
      metrics: {
        hygieneCompleted: { dataset: "softdent.hygieneRecall", dashboard: "practice", path: "hygieneRecall.completed" },
        recallDue: { dataset: "softdent.hygieneRecall", dashboard: "practice", path: "hygieneRecall.due" },
        period: { dataset: "softdent.hygieneRecall", dashboard: "practice", path: "hygieneRecall.period" },
      },
    },
  };

  function isNode() {
    return typeof window === "undefined";
  }

  function loadManifestWidgets() {
    if (!isNode()) return null;
    try {
      const fs = require("node:fs");
      const pathMod = require("node:path");
      const manifestPath = pathMod.join(__dirname, "..", "import-manifest.json");
      const payload = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
      return payload.widgets || null;
    } catch {
      return null;
    }
  }

  function widgets() {
    return loadManifestWidgets() || FALLBACK_WIDGETS;
  }

  function getPath(obj, path) {
    if (!path) return obj;
    return String(path)
      .split(".")
      .reduce((acc, key) => (acc == null ? undefined : acc[key]), obj);
  }

  function formatValue(value, binding) {
    if (value === null || value === undefined || value === "") return MISSING;
    if (binding && binding.suffix && typeof value === "number") return `${value}${binding.suffix}`;
    return value;
  }

  function datasetEntry(diagnostics, datasetKey) {
    if (!diagnostics || !Array.isArray(diagnostics.datasets)) return null;
    return diagnostics.datasets.find((item) => item.datasetKey === datasetKey) || null;
  }

  function resolveMetric(binding, ctx) {
    const datasetKey = binding.dataset;
    const entry = datasetEntry(ctx.diagnostics, datasetKey);
    if (entry && entry.status === "not_configured") {
      return { value: NOT_CONFIGURED, state: "not_configured", dataset: datasetKey };
    }
    const dash = (ctx.dashboards && ctx.dashboards[binding.dashboard]) || {};
    if (dash.dataSource !== "import" && dash.dataSource !== "persisted") {
      return { value: MISSING, state: entry && entry.status === "stale" ? "stale" : "missing", dataset: datasetKey };
    }
    if (binding.compute === "qbNetIncome") {
      const revenue = getPath(ctx.dashboards.quickbooks, "revenue");
      const expenses = getPath(ctx.dashboards.quickbooks, "expenses");
      if (revenue == null || expenses == null) {
        return { value: MISSING, state: "missing", dataset: datasetKey };
      }
      const net = Number(revenue) - Number(expenses);
      return { value: Number.isFinite(net) ? net : MISSING, state: "ok", dataset: datasetKey };
    }
    if (binding.path === "collections" && dash.collectionsPending) {
      return { value: MISSING, state: "pending", dataset: datasetKey };
    }
    let raw = getPath(dash, binding.path);
    if (binding.label && Array.isArray(raw)) {
      const row = raw.find((item) => String(item.label || "") === binding.label);
      raw = row ? row.value : null;
    }
    if (binding.length) {
      raw = Array.isArray(raw) && raw.length ? raw.length : null;
    }
    if (binding.index != null && Array.isArray(raw)) {
      const item = raw[binding.index < 0 ? raw.length + binding.index : binding.index];
      raw = binding.subpath ? getPath(item, binding.subpath) : item;
    }
    if (raw === null || raw === undefined || raw === "") {
      return { value: MISSING, state: entry && entry.status === "partial" ? "partial" : "missing", dataset: datasetKey };
    }
    return { value: formatValue(raw, binding), state: "ok", dataset: datasetKey };
  }

  function buildWidgetMetrics(widgetKey, ctx) {
    const contract = widgets()[widgetKey];
    if (!contract) return { metrics: {}, states: [], contract: null };
    const metrics = {};
    const states = [];
    Object.keys(contract.metrics || {}).forEach((metricKey) => {
      const resolved = resolveMetric(contract.metrics[metricKey], ctx);
      metrics[metricKey] = resolved.value;
      states.push(resolved.state);
    });
    return { metrics, states, contract };
  }

  function widgetStatusFromStates(states) {
    if (!states.length) return "FAILED";
    const problemStates = new Set(["missing", "stale", "partial", "pending"]);
    const hasProblem = states.some((state) => problemStates.has(state));
    if (states.every((state) => state === "ok")) return "SUCCESS";
    if (hasProblem) return states.some((state) => state === "ok") ? "DEGRADED" : "FAILED";
    if (states.some((state) => state === "ok")) return "DEGRADED";
    if (states.every((state) => state === "not_configured")) return "FAILED";
    return "FAILED";
  }

  function formatContractForHal(widgetKey) {
    const contract = widgets()[widgetKey];
    if (!contract) return `Unknown widget: ${widgetKey}`;
    const lines = [`${contract.title} (${widgetKey}):`];
    Object.entries(contract.metrics || {}).forEach(([metricKey, binding]) => {
      lines.push(`  - ${metricKey}: dataset=${binding.dataset}, dashboard=${binding.dashboard}, path=${binding.path || binding.compute || "—"}`);
    });
    return lines.join("\n");
  }

  function formatAllContractsForHal() {
    return Object.keys(widgets())
      .map((key) => formatContractForHal(key))
      .join("\n\n");
  }

  return {
    MISSING,
    NOT_CONFIGURED,
    widgets,
    resolveMetric,
    buildWidgetMetrics,
    widgetStatusFromStates,
    formatContractForHal,
    formatAllContractsForHal,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = WidgetContract;
}
if (typeof window !== "undefined") {
  window.WidgetContract = WidgetContract;
}
