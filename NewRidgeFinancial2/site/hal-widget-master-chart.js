/**
 * HAL Widget Master Chart
 *
 * One operational map for every widget HAL owns: where it appears, what it
 * does, what data it expects, and what makes it ready.
 */
const HalWidgetMasterChart = (function () {
  function halSkillsApi() {
    if (typeof HalSkills !== "undefined") return HalSkills;
    if (typeof window !== "undefined" && window.HalSkills) return window.HalSkills;
    try {
      return require("./hal-skills.js");
    } catch (err) {
      if (typeof console !== "undefined" && console.error) {
        console.error("[HalWidgetMasterChart] Failed to load hal-skills:", err);
      }
      return null;
    }
  }

  const DETAILS = {
    practiceFinancialOverview: {
      title: "Practice Financial Overview",
      purpose: "Owner-level view of revenue, net income, production, and collections.",
      expectedData: ["QuickBooks revenue", "QuickBooks expenses", "SoftDent dashboard production", "SoftDent dashboard collections"],
      readyWhen: "QuickBooks revenue/expenses and SoftDent dashboard production are loaded.",
      primarySystem: "SoftDent + QuickBooks",
    },
    nr2KpiRibbon: {
      title: "Cross-Analytics KPI Ribbon",
      purpose: "Composite ribbon of reconciliation variance, collection lag, QB revenue, and SoftDent production.",
      expectedData: ["SoftDent dashboard production", "QuickBooks monthly P&L", "Optional SoftDent A/R aging"],
      readyWhen: "At least one Tier-1 analytics tile has verified data.",
      primarySystem: "NR2 Analytics",
    },
    nr2ProductionReconciliation: {
      title: "Production vs QuickBooks Reconciliation",
      purpose: "Compare monthly SoftDent production to QuickBooks revenue by period.",
      expectedData: ["SoftDent dashboard monthly production", "QuickBooks monthly TotalIncome rows"],
      readyWhen: "Matching periods exist in both SoftDent dashboard and QuickBooks P&L imports.",
      primarySystem: "SoftDent + QuickBooks",
    },
    nr2CollectionLag: {
      title: "Collection Lag (DSO)",
      purpose: "Surface days-sales-outstanding proxy from A/R aging or monthly collections ratio.",
      expectedData: ["SoftDent A/R aging buckets", "Or SoftDent production/collections for proxy"],
      readyWhen: "A/R aging export is loaded or latest month has production and collections.",
      primarySystem: "SoftDent",
    },
    nr2GoalScorecard: {
      title: "Production Goal Scorecard",
      purpose: "Compare YTD SoftDent production against operator goal for executive pacing.",
      expectedData: ["SoftDent dashboard production rows", "Optional NR2_GOAL_PRODUCTION_YTD override"],
      readyWhen: "YTD production sum is available from imported SoftDent dashboard rows.",
      primarySystem: "SoftDent",
    },
    nr2AlertTicker: {
      title: "Exception Alert Ticker",
      purpose: "Rolling strip of cross-analytics exceptions (variance, lag, A/R 90+ concentration).",
      expectedData: ["SoftDent dashboard", "QuickBooks monthly P&L", "SoftDent A/R aging"],
      readyWhen: "Analytics snapshot can evaluate at least one threshold rule.",
      primarySystem: "NR2 Analytics",
    },
    nr2MonthlyTrendCombo: {
      title: "Executive Monthly Trend",
      purpose: "Overlay SoftDent production, collections, and QuickBooks revenue by month.",
      expectedData: ["SoftDent dashboard monthly rows", "QuickBooks monthly revenue rows"],
      readyWhen: "At least one shared month exists across SoftDent and QuickBooks imports.",
      primarySystem: "NR2 Analytics",
    },
    nr2ProviderCompensationWidget: {
      title: "Provider Production Share",
      purpose: "Show provider production share bars for compensation review.",
      expectedData: ["SoftDent provider rows", "Or sd_procedures ODBC extract"],
      readyWhen: "Provider production rows are present in snapshot or ODBC extract.",
      primarySystem: "SoftDent",
    },
    softdentProductionDaily: {
      title: "SoftDent Production Trend",
      purpose: "Show recent SoftDent production by period from sd_procedures or daysheet/dashboard fallback.",
      expectedData: ["sd_procedures ODBC extract", "Or daysheet/dashboard production rows"],
      readyWhen: "sd_procedures has daily rows or dashboard/daysheet export includes period production history.",
      primarySystem: "SoftDent",
    },
    financialProductionTrend: {
      title: "Production Trend & YTD",
      purpose: "Show current production, 12-month trend, and year-to-date production/collection indicators.",
      expectedData: ["SoftDent dashboard production", "Period labels", "YTD production/collections metrics"],
      readyWhen: "SoftDent dashboard export has current-period production.",
      primarySystem: "SoftDent",
    },
    payerMixAndCollections: {
      title: "Payer Mix & Collections",
      purpose: "Show payer share and collection-rate posture for owner review.",
      expectedData: ["SoftDent collections", "Payer mix fields", "Collection-rate source"],
      readyWhen: "Collections and payer mix are present or the widget degrades visibly.",
      primarySystem: "SoftDent",
    },
    providerPerformance: {
      title: "Provider Performance",
      purpose: "Show provider production split and top provider contribution.",
      expectedData: ["SoftDent dashboard provider rows", "Provider production amounts"],
      readyWhen: "Provider rows are present in the financial dashboard cache.",
      primarySystem: "SoftDent",
    },
    ebitdaNormalization: {
      title: "EBITDA Normalization",
      purpose: "Surface potential EBITDA add-backs and expense-category totals.",
      expectedData: ["QuickBooks expenses", "QuickBooks expense categories", "Staff-reviewed add-back candidates"],
      readyWhen: "QuickBooks expense categories and expense totals are loaded.",
      primarySystem: "QuickBooks",
    },
    quickbooksProfitLossDetail: {
      title: "QuickBooks P&L Detail",
      purpose: "Show revenue, COGS, gross profit, operating expenses, and net income.",
      expectedData: ["QuickBooks revenue", "QuickBooks expenses", "QuickBooks P&L summary"],
      readyWhen: "QuickBooks revenue and expenses are available from the import cache.",
      primarySystem: "QuickBooks",
    },
    quickbooksMonthlyRevenue: {
      title: "Monthly Revenue Trend",
      purpose: "Chart QuickBooks monthly TotalIncome from the read-only P&L cache.",
      expectedData: ["QuickBooks revenue/P&L monthly rows with TotalIncome"],
      readyWhen: "QuickBooks P&L import includes monthly revenue rows.",
      primarySystem: "QuickBooks",
    },
    quickbooksNetIncomeSummary: {
      title: "Net Income Summary",
      purpose: "Show YTD and latest-month net income from QuickBooks P&L rows.",
      expectedData: ["QuickBooks monthly P&L with NetIncome"],
      readyWhen: "Monthly P&L rows include net income.",
      primarySystem: "QuickBooks",
    },
    quickbooksBalanceSheetSummary: {
      title: "Balance Sheet Summary",
      purpose: "Summarize assets and equity proxy from QuickBooks A/R and P&L.",
      expectedData: ["QuickBooks A/R export", "QuickBooks P&L totals"],
      readyWhen: "A/R and P&L imports are present.",
      primarySystem: "QuickBooks",
    },
    quickbooksCashFlowTrend: {
      title: "Cash Flow Trend",
      purpose: "Show monthly net cash flow proxy from income minus expenses.",
      expectedData: ["QuickBooks monthly P&L rows"],
      readyWhen: "At least two months of P&L data exist.",
      primarySystem: "QuickBooks",
    },
    quickbooksRevenueByService: {
      title: "Revenue by Service",
      purpose: "Category/service revenue breakdown for owner review.",
      expectedData: ["QuickBooks expense categories or P&L revenue proxy"],
      readyWhen: "Category slices or revenue total is available.",
      primarySystem: "QuickBooks",
    },
    quickbooksArAging: {
      title: "QuickBooks A/R Aging",
      purpose: "QuickBooks-side A/R aging for cross-check with SoftDent dental A/R.",
      expectedData: ["QuickBooks A/R export or SDK probe ar_aging"],
      readyWhen: "A/R buckets are loaded from import cache.",
      primarySystem: "QuickBooks",
    },
    quickbooksExpenseBreakdown: {
      title: "Operating Expenses",
      purpose: "Show monthly expense trend and category breakdown for owner review.",
      expectedData: ["QuickBooks monthly expenses", "QuickBooks expense category slices"],
      readyWhen: "QuickBooks expense categories or monthly expense series are loaded.",
      primarySystem: "QuickBooks",
    },
    accountsPayableAutomation: {
      title: "Accounts Payable Automation",
      purpose: "Track accounting-document review and vendor/posting readiness.",
      expectedData: ["Local accounting document queue", "QuickBooks expenses", "Vendor document metadata"],
      readyWhen: "Local accounting documents or vendor import data are present.",
      primarySystem: "Local documents + QuickBooks",
    },
    documentIntakeQueue: {
      title: "Document Intake Queue",
      purpose: "Show local documents waiting for review, status, and posting flow.",
      expectedData: ["Local document queue", "Document status", "Vendor/date/amount fields"],
      readyWhen: "At least one local accounting document exists in the queue.",
      primarySystem: "Local documents",
    },
    documentPreview: {
      title: "Document Preview",
      purpose: "Show the selected document's extracted metadata and preview pane.",
      expectedData: ["Selected document metadata", "Extracted vendor/date/amount fields"],
      readyWhen: "A document is selected and its metadata is available.",
      primarySystem: "Local documents",
    },
    periodCloseAndPosting: {
      title: "Period Close & Posting",
      purpose: "Summarize period document counts, posting readiness, and review workload.",
      expectedData: ["Accounting document period assignment", "Posting status", "Human-reviewed readiness"],
      readyWhen: "Documents have period/status fields for close review.",
      primarySystem: "Local documents",
    },
    journalPostingQueue: {
      title: "Journal Posting Queue",
      purpose: "Show local SQLite journal posting queue for reviewed accruals.",
      expectedData: ["Local journal queue", "Pending review counts", "Ready-to-export entries"],
      readyWhen: "NR2 server (Start Program) exposes the local journal posting queue.",
      primarySystem: "Local SQLite",
    },
    smartClaimsAndReceivables: {
      title: "Smart Claims & Receivables",
      purpose: "Connect claims posture with verified receivables data without fabricating A/R.",
      expectedData: ["SoftDent claims", "Verified SoftDent A/R aging"],
      readyWhen: "SoftDent claims and a verified A/R source are both available.",
      primarySystem: "SoftDent",
    },
    claimsPipeline: {
      title: "Claims Pipeline",
      purpose: "Show claim cards by lane and claim lifecycle status.",
      expectedData: ["SoftDent claims", "Claim status", "Claim amount", "Patient/payer fields"],
      readyWhen: "SoftDent claims export contains claim rows with status values.",
      primarySystem: "SoftDent",
    },
    arAgingAndCollections: {
      title: "A/R Aging & Collections",
      purpose: "Show verified A/R buckets and collections trend posture.",
      expectedData: ["SoftDent A/R aging", "Collections trend when available"],
      readyWhen: "Verified SoftDent A/R aging export is loaded.",
      primarySystem: "SoftDent",
    },
    arOutstandingClaims: {
      title: "A/R Outstanding Claims",
      purpose: "Show top outstanding claim detail when claims and balances are verified.",
      expectedData: ["SoftDent claims", "Verified A/R balance source"],
      readyWhen: "Outstanding claim detail exists or the widget explains the missing source.",
      primarySystem: "SoftDent",
    },
    careDeliveryPerformance: {
      title: "Care Delivery Performance",
      purpose: "Show SoftDent daysheet/A/R hero metrics and care delivery snapshot.",
      expectedData: ["SoftDent dashboard", "Verified patient balance or A/R source"],
      readyWhen: "SoftDent dashboard export has current values.",
      primarySystem: "SoftDent",
    },
    softdentArAging: {
      title: "SoftDent A/R Aging",
      purpose: "Show SoftDent aging buckets on the SoftDent source page.",
      expectedData: ["SoftDent A/R aging buckets", "Bucket balances"],
      readyWhen: "SoftDent A/R aging export is loaded and validated.",
      primarySystem: "SoftDent",
    },
    softdentResponsibility: {
      title: "SoftDent Responsibility Split",
      purpose: "Show insurance versus patient responsibility when sourced.",
      expectedData: ["SoftDent insurance responsibility", "SoftDent patient responsibility"],
      readyWhen: "Responsibility values are present or the widget degrades.",
      primarySystem: "SoftDent",
    },
    newPatients: {
      title: "New Patients",
      purpose: "Show practice-performance new patient count when the collector exists.",
      expectedData: ["SoftDent new patient export"],
      readyWhen: "A SoftDent new-patient export is configured and loaded.",
      primarySystem: "SoftDent",
    },
    treatmentPlanSummary: {
      title: "Treatment Plan Summary",
      purpose: "Show treatment plans presented, accepted, and presented value.",
      expectedData: ["SoftDent treatment plan summary export"],
      readyWhen: "A treatment-plan summary export is configured and loaded.",
      primarySystem: "SoftDent",
    },
    caseAcceptance: {
      title: "Case Acceptance",
      purpose: "Show case acceptance rate and accepted/presented counts.",
      expectedData: ["SoftDent case acceptance export", "Derived treatment-plan summary"],
      readyWhen: "Dedicated or derived case-acceptance data is configured and loaded.",
      primarySystem: "SoftDent",
    },
    hygieneRecall: {
      title: "Hygiene & Recall",
      purpose: "Show hygiene completed and recall due counts by period.",
      expectedData: ["SoftDent hygiene_recall_summary export"],
      readyWhen: "Hygiene/recall summary export is configured and loaded.",
      primarySystem: "SoftDent",
    },
    softdentOperatoryGrid: {
      title: "Operatory Schedule",
      purpose: "Show operatory chair columns and scheduled slots from SoftDent.",
      expectedData: ["SoftDent operatory schedule export (operatory_schedule.json)", "operatoryChairs array with name and slots"],
      readyWhen: "operatory_schedule.json is present with a non-empty operatoryChairs array.",
      primarySystem: "SoftDent",
    },
    softdentCollectionsDaily: {
      title: "Collections Trend",
      purpose: "Daily or monthly collections trend from sd_payments or dashboard.",
      expectedData: ["sd_payments ODBC extract", "SoftDent dashboard collections"],
      readyWhen: "Collections points exist in sd_payments or dashboard rows.",
      primarySystem: "SoftDent",
    },
    softdentNewPatientsMTD: {
      title: "New Patients (MTD)",
      purpose: "Count new patients for the current month.",
      expectedData: ["sd_patients first_visit_date", "softdent_new_patients.csv"],
      readyWhen: "New patient count is available for the current period.",
      primarySystem: "SoftDent",
    },
    softdentClaimsOutstanding: {
      title: "Outstanding Claims",
      purpose: "List top outstanding claims with balances and status.",
      expectedData: ["sd_claims", "softdent_claims_export.csv"],
      readyWhen: "Claims with outstanding balances are in the extract.",
      primarySystem: "SoftDent",
    },
    softdentProviderProduction: {
      title: "Provider Production (Daily)",
      purpose: "Provider-level production from sd_procedures or dashboard.",
      expectedData: ["sd_procedures by provider", "Financial dashboard provider rows"],
      readyWhen: "Provider production rows are present.",
      primarySystem: "SoftDent",
    },
    softdentAppointmentsSnapshot: {
      title: "Appointments Snapshot",
      purpose: "Recent appointment rows from sd_appointments or operatory schedule.",
      expectedData: ["sd_appointments", "operatoryChairs[]"],
      readyWhen: "Appointment or operatory schedule data is loaded.",
      primarySystem: "SoftDent",
    },
    narrativeWorkflow: {
      title: "Narrative Workflow",
      purpose: "Track local narrative drafting, draft history, and source-fact safety.",
      expectedData: ["Local narrative drafts", "SoftDent claims facts when available"],
      readyWhen: "A local draft exists or claim source facts can ground narrative work.",
      primarySystem: "Local drafts + SoftDent",
    },
    documentLibrary: {
      title: "Document Library",
      purpose: "Show local document-library index volume and selected metadata.",
      expectedData: ["Local library documents", "Indexed document metadata"],
      readyWhen: "The local document library has indexed records.",
      primarySystem: "Local documents",
    },
    halImportHealth: {
      title: "Import & Source Health",
      purpose: "Summarize import diagnostics across SoftDent and QuickBooks dataset contracts.",
      expectedData: ["Import bundle diagnostics", "Dataset connected/partial/missing counts"],
      readyWhen: "Import diagnostics are available and no blocking datasets are missing or stale.",
      primarySystem: "Import cache",
    },
    officeManagerPriorities: {
      title: "Office Manager Priorities",
      purpose: "Group HAL attention items and local office tasks for the morning huddle.",
      expectedData: ["Widget feed attention items", "Local office tasks"],
      readyWhen: "HAL has widget priorities or local office tasks to review.",
      primarySystem: "HAL + local tasks",
    },
    officeManagerSurfaces: {
      title: "Staff Work Surfaces",
      purpose: "Jump links to every staff page HAL monitors with live readiness counts.",
      expectedData: ["Widget feed surface counts", "Page schema navigation"],
      readyWhen: "Staff page schema and widget feed are loaded.",
      primarySystem: "HAL navigation",
    },
    halAskHal: {
      title: "Ask HAL",
      purpose: "Command center for questions, widget explanations, and staff navigation.",
      expectedData: ["HAL models", "Widget feed", "Program snapshot"],
      readyWhen: "HAL runtime and widget feed are available.",
      primarySystem: "HAL",
    },
    halMorningBriefing: {
      title: "Morning Briefing",
      purpose: "Cross-domain synthesis card with KPI ribbon and consent-gated actuators.",
      expectedData: ["HalProactive morning briefing", "Import health summary", "KPI tiles"],
      readyWhen: "Proactive briefing lane has import data to synthesize.",
      primarySystem: "HAL",
    },
    halSituationalHero: {
      title: "Situational Hero",
      purpose: "Living command posture with alert ticker and quick HAL prompt chips.",
      expectedData: ["Morning briefing sentence", "Alert ticker widgets", "Collection lag / reconciliation signals"],
      readyWhen: "Widget feed and proactive briefing are loaded.",
      primarySystem: "HAL",
    },
    sidenotesProgram: {
      title: "SideNotes Program",
      purpose: "Monitor SideNotesIM workstation routing and local note handoff.",
      expectedData: ["SideNotes hub inbox", "Workstation watcher status"],
      readyWhen: "SideNotes hub path is configured and watchers are online.",
      primarySystem: "SideNotesIM",
    },
  };

  function widgetOrder() {
    const skills = halSkillsApi();
    return skills && Array.isArray(skills.WIDGET_ORDER) ? skills.WIDGET_ORDER : Object.keys(DETAILS);
  }

  function widgetNav() {
    const skills = halSkillsApi();
    return skills && skills.WIDGET_NAV ? skills.WIDGET_NAV : {};
  }

  function widgetDataReady(widgetKey, feed) {
    if (!feed || !feed.widgets) return null;
    const widget = feed.widgets[widgetKey];
    if (!widget || !widget.status) return false;
    return widget.status === "SUCCESS";
  }

  function all(feed) {
    const nav = widgetNav();
    return widgetOrder().map((key, index) => {
      const detail = DETAILS[key] || {};
      const page = nav[key] || "unknown";
      if (page === "unknown" && typeof console !== "undefined" && console.warn) {
        console.warn(`[HalWidgetMasterChart] Widget "${key}" has no page mapping in WIDGET_NAV`);
      }
      return {
        key,
        order: index + 1,
        title: detail.title || key,
        page,
        purpose: detail.purpose || "Widget purpose not documented.",
        primarySystem: detail.primarySystem || "Unknown",
        expectedData: detail.expectedData || [],
        readyWhen: detail.readyWhen || "Required local data is available and validated.",
        dataReady: widgetDataReady(key, feed),
      };
    });
  }

  function byPage(feed) {
    return all(feed).reduce((acc, row) => {
      if (!acc[row.page]) acc[row.page] = [];
      acc[row.page].push(row);
      return acc;
    }, {});
  }

  function formatForHal(feed) {
    const groups = byPage(feed);
    const lines = ["HAL Widget Master Chart", "Use this as the placement guide before reading or explaining widgets."];
    if (feed && feed.widgets) {
      lines.push("", "Readiness reflects the current widget feed (SUCCESS = ready now).");
    }
    Object.keys(groups).forEach((page) => {
      lines.push("", page.toUpperCase());
      groups[page].forEach((row) => {
        lines.push(`- ${row.title} (${row.key})`);
        lines.push(`  Does: ${row.purpose}`);
        lines.push(`  Expected: ${row.expectedData.join("; ") || "No expected data documented."}`);
        lines.push(`  Ready when: ${row.readyWhen}`);
        if (typeof row.dataReady === "boolean") {
          lines.push(`  Ready now: ${row.dataReady ? "yes" : "no"}`);
        }
      });
    });
    return lines.join("\n");
  }

  function find(widgetKey, feed) {
    return all(feed).find((row) => row.key === widgetKey) || null;
  }

  return {
    DETAILS,
    all,
    byPage,
    find,
    formatForHal,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalWidgetMasterChart;
}
if (typeof window !== "undefined") {
  window.HalWidgetMasterChart = HalWidgetMasterChart;
}
