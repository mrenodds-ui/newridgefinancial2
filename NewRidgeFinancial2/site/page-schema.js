/**
 * Staff-facing page schema — canonical design from hal-page-designs.canvas.tsx.
 * Single source of truth for nav, page chrome, HAL commands, and widget inventory.
 */
(function () {
  "use strict";
  if (typeof window === "undefined") return;
  delete window.NR2_LEGACY_SCHEMA;
  delete window.OLD_PAGE_SCHEMA;
  delete window.PageSchemaLegacy;
  window.__NR2_SCHEMA_LOADED = "hal-10090";
})();

const PageSchema = (function () {
  const SCHEMA_VERSION = "hal-10090";

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

  const PAGES = {
    financial: {
      id: "financial",
      label: "Financial",
      title: "Owner Financial Dashboard",
      subtitle: "Executive cockpit for practice performance, production analytics, and collection metrics",
      accent: "green",
      filters: [
        "📅 Year to Date",
        "📅 Last 12 Months",
        "🏢 Ridgefield (Main)",
        "👤 All Providers",
        "🔄 Refresh Data",
      ],
      commands: ["Summarize MTD production", "Compare to prior month", "Explain payer mix"],
      safety: "🔒 Local data only",
      widgets: [
        { key: "nr2AlertTicker", title: "Exception Alert Ticker" },
        { key: "practiceFinancialOverview", title: "Practice Financial Overview" },
        { key: "nr2KpiRibbon", title: "Cross-Analytics KPI Ribbon" },
        { key: "nr2GoalScorecard", title: "Production Goal Scorecard" },
        { key: "nr2MonthlyTrendCombo", title: "Executive Monthly Trend" },
        { key: "financialProductionTrend", title: "Production MTD & 12-Month Trend" },
        { key: "nr2ProductionReconciliation", title: "Production vs QuickBooks Reconciliation" },
        { key: "nr2CollectionLag", title: "Collection Lag (DSO)" },
        { key: "nr2ProviderCompensationWidget", title: "Provider Production Share" },
        { key: "softdentProductionDaily", title: "SoftDent Production Trend" },
        { key: "payerMixAndCollections", title: "Payer Mix & Collection Rate" },
      ],
    },
    taxes: {
      id: "taxes",
      label: "Taxes",
      title: "S Corp Tax Planning",
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
        { key: "taxBookToTaxBridge", title: "Book-to-Tax Bridge" },
        { key: "taxReasonableComp", title: "Reasonable Compensation Scenarios" },
        { key: "taxQuarterlyEstimates", title: "Quarterly Tax Estimates" },
        { key: "taxFederalStateSplit", title: "Federal / State Tax Split" },
      ],
    },
    softdent: {
      id: "softdent",
      label: "SoftDent",
      title: "Clinical & Practice Performance",
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
        {
          key: "softdentOperatoryGrid",
          title: "Operatory Schedule",
          dataContract: "softdent.operatory → operatoryChairs[] in operatory_schedule.json",
        },
      ],
    },
    quickbooks: {
      id: "quickbooks",
      label: "QuickBooks",
      title: "QuickBooks Integration",
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
      id: "ar",
      label: "A/R",
      title: "A/R & Collections",
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
      id: "claims",
      label: "Claims",
      title: "Claims Workbench",
      subtitle: "Open insurance claims, attachments, and payer detail",
      accent: "purple",
      filters: ["All Claims", "High Risk", "Unmatched", "Missing Attachments"],
      commands: ["Show open claims", "Review denied claims", "Open claim detail"],
      safety: "Local-only · Human review required · No payer submission",
      widgets: [{ key: "claimsPipeline", title: "Open Insurance Claims" }],
    },
    narratives: {
      id: "narratives",
      label: "Narratives",
      title: "Insurance Narratives",
      subtitle: "Clinical Documentation & Justification Composer",
      accent: "pink",
      filters: ["Drafts", "Crown cases", "Delta Dental"],
      commands: ["Draft crown narrative", "Insert prior history", "Save draft for review"],
      safety: "Draft only · Human review required · No submission",
      widgets: [{ key: "narrativeWorkflow", title: "Narrative Composer" }],
    },
    documents: {
      id: "documents",
      label: "Documents",
      title: "Accounting Documents",
      subtitle: "New Ridge Family Dental · Ridgefield, CT · Automated intake & GL workflow",
      accent: "cyan",
      filters: ["All Sources", "OCR Inbox", "Period Close", "Journal Entries", "AP Automation", "Exceptions"],
      commands: ["Browse recent documents", "Preview selected document", "Review journal entries"],
      safety: "Review-gated · Journal draft only",
      widgets: [
        { key: "documentIntakeQueue", title: "Recent Accounting Documents" },
        { key: "documentPreview", title: "Document Preview" },
        { key: "periodCloseAndPosting", title: "June Period Close" },
        { key: "accountsPayableAutomation", title: "Accounts Payable" },
        { key: "journalPostingQueue", title: "June Journal Entries" },
      ],
    },
    library: {
      id: "library",
      label: "Library",
      title: "Document Library",
      subtitle: "New Ridge Family Dental · Centralized repository",
      accent: "gray",
      filters: ["All Categories", "Contracts", "Invoices", "Insurance", "Compliance"],
      commands: ["Search library", "Open selected file", "Filter by category"],
      safety: "Read-only · Local library",
      widgets: [{ key: "documentLibrary", title: "Library & Preview" }],
    },
    "office-manager": {
      id: "office-manager",
      label: "Office Manager",
      title: "Office Command Center",
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
      id: "hal",
      label: "HAL",
      title: "HAL Command Center",
      subtitle: "Ask questions · office message hub · monitor widgets",
      accent: "gold",
      filters: ["Current period", "All surfaces", "Office channel"],
      commands: [
        "Make a plan for today",
        "Send office announcement",
        "Show manager dashboard widgets",
        "Import status",
      ],
      safety: "Local manager · Office channel hub · Consent before outbound",
      navGroups: [
        {
          label: "Command",
          widgets: ["halAskHal"],
        },
        {
          label: "Health",
          widgets: [
            "halImportHealth",
            "practiceFinancialOverview",
            "careDeliveryPerformance",
            "quickbooksProfitLossDetail",
          ],
        },
        {
          label: "Surfaces",
          widgets: ["officeManagerSurfaces", "sidenotesProgram"],
        },
      ],
      widgets: [
        { key: "halAskHal", title: "Ask HAL" },
        { key: "halImportHealth", title: "Import & Source Health" },
        { key: "practiceFinancialOverview", title: "Practice Financial Overview" },
        { key: "careDeliveryPerformance", title: "Care Delivery Summary" },
        { key: "quickbooksProfitLossDetail", title: "Profit & Loss Summary" },
        { key: "officeManagerSurfaces", title: "Staff Work Surfaces" },
        { key: "sidenotesProgram", title: "Staff Notes" },
      ],
    },
  };

  const STAFF_PAGE_IDS = NAV_GROUPS.flatMap((group) => group.pages).filter((id) => id !== "hal");

  function byId(pageId) {
    return PAGES[pageId] || null;
  }

  function flatNav() {
    return NAV_GROUPS.flatMap((group) => group.pages.map((id) => PAGES[id]).filter(Boolean));
  }

  function navPages() {
    return flatNav().map(({ id, label, title }) => ({ id, label, title }));
  }

  function isStaffPage(pageId) {
    return STAFF_PAGE_IDS.includes(pageId);
  }

  function commandsFor(pageId) {
    const page = byId(pageId);
    return (page && page.commands) || [];
  }

  function insightFor(pageId) {
    return null;
  }

  function widgetsFor(pageId) {
    const page = byId(pageId);
    return (page && page.widgets) || [];
  }

  return {
    SCHEMA_VERSION,
    PRACTICE,
    NAV_GROUPS,
    PAGES,
    STAFF_PAGE_IDS,
    byId,
    flatNav,
    navPages,
    isStaffPage,
    commandsFor,
    insightFor,
    widgetsFor,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = PageSchema;
}
if (typeof globalThis !== "undefined") {
  globalThis.PageSchema = PageSchema;
}
if (typeof window !== "undefined") {
  window.PageSchema = PageSchema;
}

PageSchema.SCHEMA_VERSION = "hal-10090";
Object.defineProperty(PageSchema, "LAYOUT_EPOCH", {
  value: "moonshot-mockup",
  writable: false,
  configurable: false,
});
