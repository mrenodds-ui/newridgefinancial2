/**
 * Empty program data shells — no mock/demo values.
 * Used when imports or persisted user data are unavailable.
 */
const EmptyStates = (function () {
  const PRIMARY_PROVIDER = "Dr. Michael Reno";
  const EMPTY_LANES = {
    Draft: { count: 0, cards: [], more: 0 },
    "Needs Review": { count: 0, cards: [], more: 0 },
    Ready: { count: 0, cards: [], more: 0 },
    Denied: { count: 0, cards: [], more: 0 },
  };

  const DASHBOARDS = {
    financial: {
      dataSource: "empty",
      dateRange: "Awaiting import data",
      compareRange: "",
      productionMtd: {
        label: "Production MTD",
        value: "—",
        trend: "—",
        trendDir: "down",
        vs: "Import SoftDent dashboard export to populate",
        chart: { yLabels: ["$0"], xLabels: ["—"], values: [0] },
      },
      metrics: [],
      productionTrend: {
        yLabels: ["$0"],
        labels: ["—"],
        production: [0],
        average: [0],
        ytd: [],
      },
      payerMix: { total: "—", rate: "—", rateTrend: "", slices: [] },
      providers: { rows: [{ name: PRIMARY_PROVIDER, amount: "—", pct: 100 }], total: { amount: "—", pct: 100 } },
      freshness: [
        { system: "SoftDent", status: "Missing", date: "—", time: "", freq: "Export" },
        { system: "QuickBooks", status: "Missing", date: "—", time: "", freq: "Export" },
      ],
      quality: { score: 0, categories: [] },
      footer: {
        disclaimer: "No import data loaded. HAL reads SoftDent and QuickBooks exports only.",
        refreshed: "—",
      },
    },
    softdent: {
      dataSource: "empty",
      date: "—",
      source: "SoftDent",
      status: "Awaiting import",
      hero: {
        label: "DAYSHEET A/R",
        value: "—",
        subtitle: "Awaiting SoftDent export",
        trend: "—",
        trendDir: "down",
        spark: [0, 0, 0],
      },
      subMetrics: [],
      aging: [],
      responsibility: {
        total: "—",
        insurance: { amount: "—", pct: 0 },
        patient: { amount: "—", pct: 0 },
        collectability: "—",
        collectable: "—",
      },
      health: [{ label: "Import Status", value: "No SoftDent files loaded", ok: false }],
      glance: [],
      exports: [],
    },
    quickbooks: {
      dataSource: "empty",
      syncStatus: "Awaiting import",
      lastSync: "—",
      pl: { range: "Awaiting QuickBooks export", rows: [] },
      monthlyExpenses: { labels: [], values: [] },
      expenseCategories: { total: "—", slices: [] },
      ebitdaCandidates: [],
      ebitdaTotal: "—",
      sync: {
        connection: "QuickBooks import",
        access: "Read-Only",
        frequency: "On file refresh",
        lastSync: "—",
        status: "Awaiting import",
      },
    },
    ar: {
      dataSource: "empty",
      dateRange: "Awaiting verified A/R export",
      kpis: [
        { label: "Total Outstanding", value: "—", tone: "muted" },
        { label: "vs. Prior 30 Days", value: "—", tone: "muted" },
        { label: "90+ Days %", value: "—", tone: "muted" },
      ],
      aging: [],
      collectionsTrend: { labels: [], current: [], prior: [] },
      topClaims: [],
      followUp: [],
    },
    practice: {
      dataSource: "empty",
      configured: { newPatients: false, treatmentPlans: false, caseAcceptance: false },
      newPatients: { count: null, period: null, status: "Not Configured" },
      treatmentPlans: { presented: null, accepted: null, presentedValue: null, status: "Not Configured" },
      caseAcceptance: { rate: null, presented: null, accepted: null, status: "Not Configured" },
    },
  };

  const STORES = {
    claims: {
      claims: [],
      laneTotals: { Draft: 0, "Needs Review": 0, Ready: 0, Denied: 0 },
      kpis: [],
      lanes: JSON.parse(JSON.stringify(EMPTY_LANES)),
      readiness: null,
      safety: "Read-Only Mode",
      detailById: {},
    },
    narratives: {
      context: {},
      composer: {
        tone: "Professional",
        length: "Standard",
        focus: "Medical Necessity",
        keyPoints: [],
        context: "",
      },
      draftText: "",
      drafts: [],
    },
    documents: {
      entity: "",
      queue: [],
      previewById: {},
      period: {
        label: "—",
        documents: 0,
        totalAmount: "—",
        postedAmount: "—",
        pendingAmount: "—",
        reviewedPct: 0,
        postedPct: 0,
        pendingPct: 0,
        readyPct: 0,
      },
    },
    library: {
      results: 0,
      storage: {},
      filters: [],
      docs: [],
      detailById: {},
    },
  };

  function dashboard(pageId) {
    const shell = DASHBOARDS[pageId];
    return shell ? JSON.parse(JSON.stringify(shell)) : null;
  }

  function store(key) {
    const shell = STORES[key];
    return shell ? JSON.parse(JSON.stringify(shell)) : {};
  }

  function dataBadge(dataSource) {
    if (dataSource === "import") return "Import data";
    if (dataSource === "persisted") return "Local data";
    return "No data loaded";
  }

  return { dashboard, store, dataBadge, EMPTY_LANES, PRIMARY_PROVIDER };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = EmptyStates;
}
if (typeof window !== "undefined") {
  window.EmptyStates = EmptyStates;
}
