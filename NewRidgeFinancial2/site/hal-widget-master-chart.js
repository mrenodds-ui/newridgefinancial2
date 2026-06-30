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
    } catch {
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
    dataFreshnessQuality: {
      title: "Data Freshness & Quality",
      purpose: "Show source freshness, sync status, and quality-score posture.",
      expectedData: ["SoftDent export timestamps", "QuickBooks export timestamps", "Import diagnostics"],
      readyWhen: "Import diagnostics can score the available local datasets.",
      primarySystem: "SoftDent + QuickBooks",
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
    quickbooksSyncHealth: {
      title: "QuickBooks Sync Health",
      purpose: "Show local QuickBooks connection/import freshness and expense trend.",
      expectedData: ["QuickBooks import files", "QuickBooks sync metadata", "Monthly expenses"],
      readyWhen: "QuickBooks import files are copied into the canonical import folder.",
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
    claimReadinessAndSafety: {
      title: "Claim Readiness & Safety",
      purpose: "Show readiness checks and enforce no-submission safety posture.",
      expectedData: ["SoftDent claims", "Local readiness checks", "Safety rules"],
      readyWhen: "Claims are present and readiness checks can run locally.",
      primarySystem: "SoftDent + local checks",
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
    softdentSourceHealth: {
      title: "SoftDent Source Health",
      purpose: "Show source file health and read-only import status.",
      expectedData: ["SoftDent dashboard", "SoftDent claims", "SoftDent clinical notes", "Optional SoftDent A/R"],
      readyWhen: "Diagnostics can evaluate configured SoftDent datasets.",
      primarySystem: "SoftDent",
    },
    softdentExportHistory: {
      title: "SoftDent Export History",
      purpose: "Show recent local SoftDent exports and cache freshness.",
      expectedData: ["SoftDent export files", "Source file timestamps", "Record counts"],
      readyWhen: "Canonical SoftDent import folder has export files.",
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
  };

  function widgetOrder() {
    const skills = halSkillsApi();
    return skills && Array.isArray(skills.WIDGET_ORDER) ? skills.WIDGET_ORDER : Object.keys(DETAILS);
  }

  function widgetNav() {
    const skills = halSkillsApi();
    return skills && skills.WIDGET_NAV ? skills.WIDGET_NAV : {};
  }

  function all() {
    const nav = widgetNav();
    return widgetOrder().map((key, index) => {
      const detail = DETAILS[key] || {};
      return {
        key,
        order: index + 1,
        title: detail.title || key,
        page: nav[key] || "unknown",
        purpose: detail.purpose || "Widget purpose not documented.",
        primarySystem: detail.primarySystem || "Unknown",
        expectedData: detail.expectedData || [],
        readyWhen: detail.readyWhen || "Required local data is available and validated.",
      };
    });
  }

  function byPage() {
    return all().reduce((acc, row) => {
      if (!acc[row.page]) acc[row.page] = [];
      acc[row.page].push(row);
      return acc;
    }, {});
  }

  function formatForHal() {
    const groups = byPage();
    const lines = ["HAL Widget Master Chart", "Use this as the placement guide before reading or explaining widgets."];
    Object.keys(groups).forEach((page) => {
      lines.push("", page.toUpperCase());
      groups[page].forEach((row) => {
        lines.push(`- ${row.title} (${row.key})`);
        lines.push(`  Does: ${row.purpose}`);
        lines.push(`  Expected: ${row.expectedData.join("; ") || "No expected data documented."}`);
        lines.push(`  Ready when: ${row.readyWhen}`);
      });
    });
    return lines.join("\n");
  }

  function find(widgetKey) {
    return all().find((row) => row.key === widgetKey) || null;
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
