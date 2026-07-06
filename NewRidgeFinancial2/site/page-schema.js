/**
 * Staff-facing page schema — canonical design from hal-page-designs.canvas.tsx.
 * Single source of truth for nav, page chrome, HAL commands, and widget inventory.
 */
const PageSchema = (function () {
  const SCHEMA_VERSION = "hal-10025";

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
      subtitle: "Production, collections, payer mix, and provider contribution",
      accent: "green",
      filters: ["June 2025", "All providers", "Ridgefield"],
      commands: ["Summarize MTD production", "Compare to prior month", "Explain payer mix"],
      safety: "Read-only · SoftDent & QuickBooks source data",
      insight: {
        tone: "success",
        title: "June is tracking above plan",
        body: "Production is 4.2% above May. Collection rate is 0.8 points below the 85% target — Martinez crown balance is the largest open insurance claim.",
      },
      widgets: [
        { key: "practiceFinancialOverview", title: "Practice Financial Overview" },
        { key: "financialProductionTrend", title: "Production MTD & 12-Month Trend" },
        { key: "payerMixAndCollections", title: "Payer Mix & Collection Rate" },
        { key: "providerPerformance", title: "Production by Provider" },
      ],
    },
    taxes: {
      id: "taxes",
      label: "Taxes",
      title: "S Corporation Tax Planning",
      subtitle: "Federal and Kansas owner-level tax checklist for the practice S corp",
      accent: "blue",
      filters: ["Tax year 2025", "S corporation", "Kansas"],
      commands: [
        "Show book-to-tax bridge",
        "Model reasonable comp at $220K",
        "Summarize quarterly tax estimates",
        "Compare distributions vs W-2 wages",
      ],
      safety: "Read-only · HAL tax engine + MemoAI · CPA review required before filing",
      insight: {
        tone: "info",
        title: "Tax engine models book-to-tax from QuickBooks",
        body: "HAL computes K-1 estimates, reasonable-comp scenarios, and quarterly vouchers from your import. MemoAI cites federal and Kansas S corp rules. Confirm all amounts with your CPA before filing.",
      },
      widgets: [
        { key: "quickbooksProfitLossDetail", title: "Book Income (QuickBooks YTD)" },
        { key: "ebitdaNormalization", title: "Owner Add-backs & Adjustments" },
      ],
    },
    softdent: {
      id: "softdent",
      label: "SoftDent",
      title: "Clinical & Practice Performance",
      subtitle: "Care delivery, receivables, hygiene, and case acceptance",
      accent: "green",
      filters: ["June 2025", "All operatories", "All providers"],
      commands: ["Review A/R aging", "Open new patient summary", "Explain case acceptance"],
      safety: "Read-only · HAL reads SoftDent only",
      insight: {
        tone: "info",
        title: "Case acceptance holding steady",
        body: "73% acceptance on $214,800 presented this month. Hygiene reappointment rate is 91% — two open blocks tomorrow afternoon.",
      },
      widgets: [
        { key: "careDeliveryPerformance", title: "Care Delivery Summary" },
        { key: "softdentArAging", title: "Accounts Receivable Aging" },
        { key: "softdentResponsibility", title: "Insurance vs Patient Balance" },
        { key: "newPatients", title: "New Patients (MTD)" },
        { key: "treatmentPlanSummary", title: "Treatment Plans Presented" },
        { key: "caseAcceptance", title: "Case Acceptance Rate" },
        { key: "hygieneRecall", title: "Hygiene & Recall" },
      ],
    },
    quickbooks: {
      id: "quickbooks",
      label: "QuickBooks",
      title: "Practice Accounting",
      subtitle: "Profit & loss, operating expenses, and EBITDA normalization",
      accent: "blue",
      filters: ["YTD 2025", "Accrual basis", "All accounts"],
      commands: ["Explain YTD net income", "Review EBITDA add-backs", "Show supply spend"],
      safety: "Read-only · HAL reads QuickBooks only",
      insight: {
        tone: "info",
        title: "Net income ahead of prior year",
        body: "YTD net income is $886,559. Supply spend is 2.1% above budget — Henry Schein invoice #88421 is $14,280.",
      },
      widgets: [
        { key: "quickbooksProfitLossDetail", title: "Profit & Loss Summary (YTD)" },
        { key: "ebitdaNormalization", title: "EBITDA Normalization" },
        { key: "quickbooksProfitLossDetail", title: "Operating Expenses" },
      ],
    },
    ar: {
      id: "ar",
      label: "A/R",
      title: "Accounts Receivable & Collections",
      subtitle: "Outstanding balances and open insurance claims",
      accent: "orange",
      filters: ["All payers", "Balance > $500", "Age > 45 days"],
      commands: ["List claims over 60 days", "Prioritize follow-up calls", "Summarize collections"],
      safety: "Read-only · No payer contact",
      insight: {
        tone: "warning",
        title: "One account over 90 days",
        body: "Williams self-pay balance ($720) needs a payment-plan call. Martinez crown claim is the largest insurance balance at $1,240.",
      },
      widgets: [
        { key: "arAgingAndCollections", title: "Aging & Collections Trend" },
        { key: "arOutstandingClaims", title: "Outstanding Claims" },
        { key: "smartClaimsAndReceivables", title: "Follow-up Queue" },
      ],
    },
    claims: {
      id: "claims",
      label: "Claims",
      title: "Insurance Claims Workbench",
      subtitle: "Open insurance claims, attachments, and payer detail",
      accent: "purple",
      filters: ["All payers", "Open claims", "June submissions"],
      commands: ["Show open claims", "Review denied claims", "Open claim detail"],
      safety: "Local-only · Human review required · No payer submission",
      insight: {
        tone: "warning",
        title: "2 denied claims need review",
        body: "Martinez D2740 is the largest open balance at $1,240. Delta Dental requires a pre-operative radiograph on file.",
      },
      widgets: [{ key: "claimsPipeline", title: "Open Insurance Claims" }],
    },
    narratives: {
      id: "narratives",
      label: "Narratives",
      title: "Insurance Narratives",
      subtitle: "Clinical justification for crown, bridge, and periodontal cases",
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
      subtitle: "Intake, preview, period close, and journal posting",
      accent: "cyan",
      filters: ["June close", "Needs review", "All categories"],
      commands: ["Browse recent documents", "Preview selected document", "Review journal entries"],
      safety: "Review-gated · Journal draft only",
      insight: {
        tone: "info",
        title: "June period close in progress",
        body: "Henry Schein invoice ($14,280) and June payroll accrual ($42,800) are the remaining items for owner approval.",
      },
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
      subtitle: "Payer contracts, compliance files, and vendor agreements",
      accent: "gray",
      filters: ["All categories", "Contracts", "Compliance"],
      commands: ["Search library", "Open selected file", "Filter by category"],
      safety: "Read-only · Local library",
      widgets: [{ key: "documentLibrary", title: "Library & Preview" }],
    },
    "office-manager": {
      id: "office-manager",
      label: "Office Manager",
      title: "Office Manager Dashboard",
      subtitle: "Production, billing, and today's clinical schedule",
      accent: "yellow",
      filters: ["Today", "All departments", "Ridgefield"],
      commands: ["Show today's priorities", "Summarize open A/R", "Jump to billing"],
      safety: "HAL office manager · Local tasks · Consent before outbound actions",
      insight: {
        tone: "info",
        title: "Morning huddle at 8:30 AM",
        body: "June production is ahead of plan. Billing should focus on denied perio claims; scheduling has a hygiene opening tomorrow at 2:30 PM.",
      },
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
      widgets: [
        { key: "halAskHal", title: "Ask HAL" },
        { key: "halImportHealth", title: "Import & Source Health" },
        { key: "practiceFinancialOverview", title: "Practice Financial Overview" },
        { key: "careDeliveryPerformance", title: "Care Delivery Summary" },
        { key: "quickbooksProfitLossDetail", title: "Profit & Loss Summary" },
        { key: "officeManagerSurfaces", title: "Staff Work Surfaces" },
        { key: "sidenotesProgram", title: "SideNotes" },
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
    const page = byId(pageId);
    return (page && page.insight) || null;
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
