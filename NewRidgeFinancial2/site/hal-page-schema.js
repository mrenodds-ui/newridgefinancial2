/**
 * HAL Command Center page schema (hal-102).
 * Cleaner layout: Ask HAL + status rail, compact widget monitor, quick nav, session footer.
 */
const HalPageSchema = (function () {
  const SCHEMA_VERSION = "hal-104";

  const GRID = {
    className: "hp-grid hp-grid--hal-102",
    areas: {
      command: "command",
      status: "status",
      widgets: "widgets",
      nav: "nav",
      sidenotes: "sidenotes",
      session: "session",
    },
  };

  /** Widget catalog grouped for the compact monitor (not separate grid cards). */
  const WIDGET_GROUPS = [
    {
      id: "financial",
      title: "Financial Widgets",
      accent: "green",
      icon: { type: "nav", key: "financial" },
      widgets: [
        { key: "practiceFinancialOverview", nav: "financial" },
        { key: "financialProductionTrend", nav: "financial" },
        { key: "payerMixAndCollections", nav: "financial" },
        { key: "providerPerformance", nav: "financial" },
      ],
    },
    {
      id: "clinical",
      title: "Clinical Widgets",
      accent: "green",
      icon: { type: "nav", key: "softdent" },
      widgets: [
        { key: "careDeliveryPerformance", nav: "softdent" },
        { key: "softdentArAging", nav: "softdent" },
        { key: "softdentResponsibility", nav: "softdent" },
        { key: "newPatients", nav: "softdent" },
        { key: "treatmentPlanSummary", nav: "softdent" },
        { key: "caseAcceptance", nav: "softdent" },
        { key: "hygieneRecall", nav: "softdent" },
      ],
    },
    {
      id: "revenue",
      title: "Revenue & A/R",
      accent: "blue",
      icon: { type: "nav", key: "quickbooks" },
      widgets: [
        { key: "quickbooksProfitLossDetail", nav: "quickbooks" },
        { key: "ebitdaNormalization", nav: "quickbooks" },
        { key: "arAgingAndCollections", nav: "ar" },
        { key: "arOutstandingClaims", nav: "ar" },
        { key: "smartClaimsAndReceivables", nav: "ar" },
        { key: "claimsPipeline", nav: "claims" },
      ],
    },
    {
      id: "ops",
      title: "Operations",
      accent: "yellow",
      icon: { type: "nav", key: "office-manager" },
      widgets: [
        { key: "documentIntakeQueue", nav: "documents" },
        { key: "documentPreview", nav: "documents" },
        { key: "periodCloseAndPosting", nav: "documents" },
        { key: "journalPostingQueue", nav: "documents" },
        { key: "accountsPayableAutomation", nav: "documents" },
        { key: "narrativeWorkflow", nav: "narratives" },
        { key: "documentLibrary", nav: "library" },
        { key: "halImportHealth", nav: "hal" },
        { key: "officeManagerPriorities", nav: "office-manager" },
        { key: "officeManagerSurfaces", nav: "office-manager" },
      ],
    },
  ];

  const ZONES = [
    { id: "command", gridArea: "command", title: "Ask HAL", kind: "command-composer" },
    { id: "status", gridArea: "status", title: "Program Status", kind: "status-rail" },
    { id: "widgets", gridArea: "widgets", title: "Manager Widgets", kind: "widget-monitor" },
    { id: "nav", gridArea: "nav", title: "Staff Work Surfaces", kind: "surface-list", icon: { type: "ui", key: "surface" } },
    { id: "sidenotes", gridArea: "sidenotes", title: "SideNotes", kind: "sidenotes", icon: { type: "nav", key: "sidenotes" } },
    { id: "session", gridArea: "session", title: "Session", kind: "session-footer" },
  ];

  const PAGE = {
    id: "hal",
    label: "HAL",
    title: "HAL Command Center",
    subtitle: "Ask HAL · monitor widgets · open staff surfaces",
    accent: "gold",
    safety: "Local manager · Consent before outbound · Direct-first imports",
    commands: ["Make a plan for today", "Show manager dashboard widgets", "Import status", "What needs review"],
    widgets: WIDGET_GROUPS.flatMap((g) => g.widgets).concat([{ key: "halAskHal" }, { key: "sidenotesProgram" }]),
  };

  function zoneById(id) {
    return ZONES.find((z) => z.id === id) || null;
  }

  function widgetGroupZones() {
    return WIDGET_GROUPS;
  }

  return {
    SCHEMA_VERSION,
    GRID,
    ZONES,
    WIDGET_GROUPS,
    PAGE,
    zoneById,
    widgetGroupZones,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalPageSchema;
}
if (typeof globalThis !== "undefined") {
  globalThis.HalPageSchema = HalPageSchema;
}
