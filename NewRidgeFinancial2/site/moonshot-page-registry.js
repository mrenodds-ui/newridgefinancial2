/**
 * Moonshot page registry — nav metadata + panel layouts from moonshot-page-layouts.js.
 */
const MoonshotPageRegistry = (function () {
  const SCHEMA_VERSION = "hal-10151";
  const LAYOUT_EPOCH = "moonshot-mockup";

  const PRACTICE = {
    name: "New Ridge Family Dental",
    descriptor: "Family & cosmetic dentistry",
    location: "Ridgefield, Connecticut",
    period: "June 2025",
    reportRange: "Jun 1 – Jun 30, 2025",
    operator: "Dr. Michael Reno",
  };

  const NAV_GROUPS = [
    { section: "Overview", pages: ["financial", "taxes", "hal"] },
    { section: "Clinical", pages: ["softdent", "narratives", "claims"] },
    { section: "Revenue", pages: ["ar", "quickbooks"] },
    { section: "Operations", pages: ["documents", "library", "office-manager"] },
  ];

  const PAGE_META = {
    financial: {
      label: "Financial",
      subtitle: "Executive cockpit for practice performance, production analytics, and collection metrics",
      accent: "green",
      filters: ["📅 Year to Date", "📅 Last 12 Months", "🏢 Ridgefield (Main)", "👤 All Providers", "🔄 Refresh Data"],
      commands: ["Summarize MTD production", "Compare to prior month", "Explain payer mix"],
      safety: "🔒 Local data only",
      widgets: [
        { key: "nr2AlertTicker", title: "Exception Alert Ticker" },
        { key: "practiceFinancialOverview", title: "Practice Financial Overview" },
        { key: "financialProductionTrend", title: "Collections MTD" },
        { key: "payerMixAndCollections", title: "Net Income YTD" },
        { key: "nr2KpiRibbon", title: "A/R Days" },
        { key: "nr2GoalScorecard", title: "Goal Attainment" },
        { key: "nr2MonthlyTrendCombo", title: "Executive Monthly Trend" },
        { key: "nr2CollectionLag", title: "Collection Lag (DSO)" },
        { key: "nr2ProductionReconciliation", title: "Production vs QuickBooks Reconciliation" },
        { key: "softdentProductionDaily", title: "SoftDent Production Trend" },
        { key: "providerPerformance", title: "Provider Performance" },
        { key: "softdentProviderProduction", title: "Provider Production (Daily)" },
        { key: "nr2ProviderCompensationWidget", title: "Provider Production Share" },
        { key: "softdentCollectionsDaily", title: "Collections Trend" },
        { key: "softdentNewPatientsMTD", title: "New Patients (MTD)" },
        { key: "softdentClaimsOutstanding", title: "Outstanding Claims" },
        { key: "newPatients", title: "New Patient Flow" },
        { key: "softdentAppointmentsSnapshot", title: "Appointments Snapshot" },
      ],
    },
    taxes: {
      label: "Taxes",
      subtitle: "Book-to-tax bridge, reasonable compensation analysis, and quarterly compliance",
      accent: "blue",
      filters: ["Tax year 2025", "S corporation", "Kansas", "Q3 estimates"],
      commands: [
        "Show book-to-tax bridge",
        "Model reasonable comp at $220K",
        "Summarize quarterly tax estimates",
        "Compare distributions vs W-2 wages",
      ],
      safety: "Read-only · HAL tax engine + MemoAI · CPA review required before filing",
      widgets: [
        { key: "quickbooksProfitLossDetail", title: "Book Income (QuickBooks YTD)" },
        { key: "ebitdaNormalization", title: "Owner Add-backs & Adjustments" },
        { key: "quickbooksMonthlyRevenue", title: "Monthly Revenue Trend" },
        { key: "quickbooksNetIncomeSummary", title: "Net Income Summary" },
        { key: "quickbooksBalanceSheetSummary", title: "Balance Sheet Summary" },
        { key: "quickbooksCashFlowTrend", title: "Cash Flow Trend" },
        { key: "quickbooksRevenueByService", title: "Revenue by Service" },
        { key: "quickbooksArAging", title: "QuickBooks A/R Aging" },
        { key: "quickbooksExpenseBreakdown", title: "Operating Expenses" },
        { key: "accountsPayableAutomation", title: "Accounts Payable" },
        { key: "periodCloseAndPosting", title: "Period Close" },
        { key: "journalPostingQueue", title: "Journal Entries" },
      ],
    },
    softdent: {
      label: "SoftDent",
      subtitle: "Care Delivery & Practice Velocity · New Ridge Family Dental",
      accent: "green",
      filters: ["Today", "This Week", "MTD", "QTD", "All Providers"],
      commands: ["Review A/R aging", "Open new patient summary", "Explain case acceptance"],
      safety: "Read-only · HAL reads SoftDent only",
      widgets: [
        { key: "careDeliveryPerformance", title: "Care Delivery Summary" },
        { key: "softdentCollectionsDaily", title: "Collections Trend" },
        { key: "softdentNewPatientsMTD", title: "New Patients (MTD)" },
        { key: "softdentClaimsOutstanding", title: "Outstanding Claims" },
        { key: "softdentProviderProduction", title: "Provider Production (Daily)" },
        { key: "softdentAppointmentsSnapshot", title: "Appointments Snapshot" },
        { key: "softdentArAging", title: "Accounts Receivable Aging" },
        { key: "softdentResponsibility", title: "Insurance vs Patient Balance" },
        { key: "treatmentPlanSummary", title: "Treatment Plans Presented" },
        { key: "caseAcceptance", title: "Case Acceptance Rate" },
        { key: "hygieneRecall", title: "Hygiene & Recall" },
        { key: "softdentOperatoryGrid", title: "Operatory Schedule" },
      ],
    },
    quickbooks: {
      label: "QuickBooks",
      subtitle: "Real-time financial synchronization · Ridgefield, CT",
      accent: "blue",
      filters: ["YTD 2025", "Accrual basis", "Live connection"],
      commands: ["Explain YTD net income", "Review EBITDA add-backs", "Show supply spend"],
      safety: "Read-only · HAL reads QuickBooks only",
      widgets: [
        { key: "quickbooksProfitLossDetail", title: "Profit & Loss Summary (YTD)" },
        { key: "quickbooksMonthlyRevenue", title: "Monthly Revenue Trend" },
        { key: "quickbooksNetIncomeSummary", title: "Net Income Summary" },
        { key: "quickbooksBalanceSheetSummary", title: "Balance Sheet Summary" },
        { key: "quickbooksCashFlowTrend", title: "Cash Flow Trend" },
        { key: "quickbooksRevenueByService", title: "Revenue by Service" },
        { key: "quickbooksArAging", title: "QuickBooks A/R Aging" },
        { key: "ebitdaNormalization", title: "EBITDA Normalization" },
        { key: "quickbooksExpenseBreakdown", title: "Operating Expenses" },
      ],
    },
    ar: {
      label: "A/R",
      subtitle: "New Ridge Family Dental · Ridgefield, CT · Revenue Cycle Management",
      accent: "orange",
      filters: ["Last 30 Days", "Last Quarter", "Insurance Only", "Patient Balance", "Export CSV"],
      commands: ["List claims over 60 days", "Prioritize follow-up calls", "Summarize collections"],
      safety: "Read-only · No payer contact",
      widgets: [
        { key: "arAgingAndCollections", title: "Aging & Collections Trend" },
        { key: "arOutstandingClaims", title: "Outstanding Claims" },
        { key: "smartClaimsAndReceivables", title: "Follow-up Queue" },
      ],
    },
    claims: {
      label: "Claims",
      subtitle: "Open insurance claims, attachments, and payer detail",
      accent: "purple",
      filters: ["All Claims", "High Risk", "Unmatched", "Missing Attachments"],
      commands: ["Show open claims", "Review denied claims", "Open claim detail"],
      safety: "Local-only · Human review required · No payer submission",
      widgets: [{ key: "claimsPipeline", title: "Open Insurance Claims" }],
    },
    narratives: {
      label: "Narratives",
      subtitle: "Clinical Documentation & Justification Composer",
      accent: "pink",
      filters: ["Drafts", "Crown cases", "Delta Dental"],
      commands: ["Draft crown narrative", "Insert prior history", "Save draft for review"],
      safety: "Draft only · Human review required · No submission",
      widgets: [{ key: "narrativeWorkflow", title: "Narrative Composer" }],
    },
    documents: {
      label: "Documents",
      subtitle: "New Ridge Family Dental · Ridgefield, CT · Automated intake & GL workflow",
      accent: "cyan",
      filters: ["All Sources", "OCR Inbox", "Period Close", "Journal Entries", "AP Automation", "Exceptions"],
      commands: ["Browse recent documents", "Preview selected document", "Review journal entries"],
      safety: "Review-gated · Journal draft only",
      widgets: [
        { key: "documentIntakeQueue", title: "Recent Accounting Documents" },
        { key: "documentPreview", title: "Document Preview" },
        { key: "periodCloseAndPosting", title: "Period Close" },
        { key: "accountsPayableAutomation", title: "Accounts Payable" },
        { key: "journalPostingQueue", title: "Journal Entries" },
      ],
    },
    library: {
      label: "Library",
      subtitle: "New Ridge Family Dental · Centralized repository",
      accent: "gray",
      filters: ["All Categories", "Contracts", "Invoices", "Insurance", "Compliance"],
      commands: ["Search library", "Open selected file", "Filter by category"],
      safety: "Read-only · Local library",
      widgets: [{ key: "documentLibrary", title: "Library & Preview" }],
    },
    "office-manager": {
      label: "Office Manager",
      subtitle: "Production, billing, and today's clinical schedule",
      accent: "yellow",
      filters: ["Today", "All departments", "Ridgefield"],
      commands: ["Show today's priorities", "Summarize open A/R", "Jump to billing"],
      safety: "HAL office manager · Local tasks · Consent before outbound actions",
      widgets: [
        { key: "officeManagerPriorities", title: "Today's Focus" },
        { key: "officeManagerSurfaces", title: "Staff Work Surfaces" },
      ],
    },
    hal: {
      label: "HAL",
      subtitle: "Ask questions · office message hub · monitor widgets",
      accent: "gold",
      filters: ["Current period", "All surfaces", "Office channel"],
      commands: ["Make a plan for today", "Send office announcement", "Show manager dashboard widgets", "Import status"],
      safety: "Local manager · Office channel hub · Consent before outbound",
      navGroups: [
        { label: "Command", widgets: ["halAskHal"] },
        {
          label: "Health",
          widgets: ["halImportHealth", "practiceFinancialOverview", "careDeliveryPerformance", "quickbooksProfitLossDetail"],
        },
        { label: "Surfaces", widgets: ["officeManagerSurfaces"] },
      ],
      widgets: [
        { key: "halAskHal", title: "Ask HAL" },
        { key: "halImportHealth", title: "Import & Source Health" },
        { key: "practiceFinancialOverview", title: "Practice Financial Overview" },
        { key: "careDeliveryPerformance", title: "Care Delivery Summary" },
        { key: "quickbooksProfitLossDetail", title: "Profit & Loss Summary" },
        { key: "officeManagerSurfaces", title: "Staff Work Surfaces" },
      ],
    },
  };

  let MANIFEST = null;

  function staffMockOnly() {
    if (typeof globalThis !== "undefined" && globalThis.NR2_STAFF_MOCK_ONLY) return true;
    if (typeof window === "undefined") return false;
    if (window.NR2_STAFF_MOCK_ONLY) return true;
    try {
      if (document.documentElement.getAttribute("data-nr2-staff-render") === "mock-embed") return true;
    } catch (_e) {
      /* ignore */
    }
    // Stale cached index.html may omit head flags; elite catalog implies mock-embed staff shell.
    if (Array.isArray(window.__NR2_MOCKUP_ELITE_PAGES) && window.__NR2_MOCKUP_ELITE_PAGES.length > 0) {
      return true;
    }
    return false;
  }

  function elitePageIds() {
    const catalog =
      typeof globalThis !== "undefined" && Array.isArray(globalThis.__NR2_MOCKUP_ELITE_PAGES)
        ? globalThis.__NR2_MOCKUP_ELITE_PAGES
        : typeof window !== "undefined" && Array.isArray(window.__NR2_MOCKUP_ELITE_PAGES)
          ? window.__NR2_MOCKUP_ELITE_PAGES
          : null;
    return catalog && catalog.length ? catalog.slice() : null;
  }

  function hasMockPreview(pageId) {
    const elite = elitePageIds();
    if (staffMockOnly() && elite) return elite.includes(pageId);
    if (pageId === "hal") return false;
    return Boolean(PAGE_META[pageId]);
  }

  function loadManifest() {
    if (MANIFEST) return MANIFEST;
    if (typeof MOONSHOT_PAGE_LAYOUTS !== "undefined") {
      MANIFEST = MOONSHOT_PAGE_LAYOUTS;
      return MANIFEST;
    }
    try {
      if (typeof require !== "undefined") {
        MANIFEST = require("./moonshot-page-layouts.js");
        return MANIFEST;
      }
    } catch (_e) {
      /* browser without script tag */
    }
    return MANIFEST;
  }

  function widgetsFromPanels(panels) {
    const seen = new Set();
    const out = [];
    const add = (key, title) => {
      if (!key || seen.has(key)) return;
      seen.add(key);
      out.push({ key, title: title || key });
    };
    for (const panel of panels || []) {
      add(panel.widgetKey, panel.title);
      if (Array.isArray(panel.kpis)) {
        for (const kpi of panel.kpis) add(kpi.widgetKey, kpi.label || kpi.widgetKey);
      }
    }
    return out;
  }

  function buildPages() {
    const m = loadManifest();
    const pages = (m && m.pages) || {};
    const navOrder = NAV_GROUPS.flatMap((group) => group.pages);
    const elite = elitePageIds();
    let pageIds = Object.keys(pages).length ? Object.keys(pages) : Object.keys(PAGE_META);
    if (staffMockOnly() && elite && elite.length) {
      pageIds = navOrder.filter((id) => elite.includes(id));
      for (const id of elite) {
        if (!pageIds.includes(id)) pageIds.push(id);
      }
    }
    const out = {};
    for (const id of pageIds) {
      const spec = pages[id] || {};
      const meta = PAGE_META[id] || {
        label: id.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
        subtitle: "Elite mock preview — add PAGE_META in moonshot-page-registry.js for chrome labels",
        accent: "green",
      };
      const mockOnlyStaff = staffMockOnly();
      out[id] = {
        id,
        label: meta.label || id,
        title: spec.title || meta.title || id,
        subtitle: meta.subtitle || "",
        accent: meta.accent || "green",
        filters: meta.filters || [],
        commands: meta.commands || [],
        safety: meta.safety || "",
        navGroups: mockOnlyStaff ? undefined : meta.navGroups,
        widgets: mockOnlyStaff ? [] : meta.widgets || widgetsFromPanels(spec.panels),
      };
    }
    return out;
  }

  let PAGES = null;

  function pagesMap() {
    if (!PAGES) PAGES = buildPages();
    return PAGES;
  }

  function byId(pageId) {
    return pagesMap()[pageId] || null;
  }

  function pageMeta(pageId) {
    return PAGE_META[pageId] || null;
  }

  function pageMetaWidgets(pageId) {
    const meta = PAGE_META[pageId];
    return (meta && Array.isArray(meta.widgets) ? meta.widgets : [])
      .map((w) => w && w.key)
      .filter(Boolean);
  }

  function flatNav() {
    return NAV_GROUPS.flatMap((group) => group.pages.map((id) => pagesMap()[id]).filter(Boolean));
  }

  function staffPageIds() {
    if (staffMockOnly()) {
      const elite = elitePageIds();
      if (elite && elite.length) return elite.slice();
    }
    return Object.keys(pagesMap()).filter((id) => id !== "hal");
  }

  function navPages() {
    return flatNav().map(({ id, label, title }) => ({ id, label, title }));
  }

  function isStaffPage(pageId) {
    if (staffMockOnly()) return hasMockPreview(pageId);
    if (pageId === "hal") return false;
    return staffPageIds().includes(pageId);
  }

  function commandsFor(pageId) {
    const page = byId(pageId);
    return (page && page.commands) || [];
  }

  function insightFor(_pageId) {
    return null;
  }

  function widgetsFor(pageId) {
    const page = byId(pageId);
    return (page && page.widgets) || [];
  }

  return {
    SCHEMA_VERSION,
    LAYOUT_EPOCH,
    PRACTICE,
    NAV_GROUPS,
    get PAGES() {
      return pagesMap();
    },
    get STAFF_PAGE_IDS() {
      return staffPageIds();
    },
    byId,
    pageMeta,
    pageMetaWidgets,
    flatNav,
    navPages,
    isStaffPage,
    hasMockPreview,
    commandsFor,
    insightFor,
    widgetsFor,
    loadManifest,
  };
})();

const PageSchema = MoonshotPageRegistry;

if (typeof module !== "undefined" && module.exports) {
  module.exports = PageSchema;
}
if (typeof globalThis !== "undefined") {
  globalThis.PageSchema = PageSchema;
  globalThis.MoonshotPageRegistry = MoonshotPageRegistry;
}
if (typeof window !== "undefined") {
  window.PageSchema = PageSchema;
  window.MoonshotPageRegistry = MoonshotPageRegistry;
  delete window.NR2_LEGACY_SCHEMA;
  delete window.OLD_PAGE_SCHEMA;
  delete window.PageSchemaLegacy;
  delete window.HalPageSchema;
}








