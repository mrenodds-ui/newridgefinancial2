/** Moonshot page panel layouts — inlined manifest (no external JSON). */
const MOONSHOT_PAGE_LAYOUTS = {
  "version": 1,
  "source": "moonshot-kimi-k2.6-elite",
  "generated": "2026-07-08",
  "pages": {
    "financial": {
      "title": "Owner Financial Dashboard",
      "shell": "widget-grid",
      "panels": [
        {
          "id": "fin-alert-ticker",
          "type": "custom",
          "widgetKey": "nr2AlertTicker",
          "colSpan": 12,
          "title": "Exception Alert Ticker",
          "dataBind": "PageCanvasData.nr2AlertTicker()"
        },
        {
          "id": "fin-hero-kpis",
          "type": "hero-kpi",
          "colSpan": 12,
          "dataBind": "PageCanvasData.financialKpis()",
          "kpis": [
            { "widgetKey": "practiceFinancialOverview", "label": "Production MTD" },
            { "widgetKey": "softdentCollectionsDaily", "label": "Collections MTD" },
            { "widgetKey": "quickbooksNetIncomeSummary", "label": "Net Income YTD" },
            { "widgetKey": "nr2CollectionLag", "label": "A/R Days" },
            { "widgetKey": "nr2GoalScorecard", "label": "Goal Attainment" }
          ]
        },
        {
          "id": "fin-monthly-trend",
          "type": "chart",
          "widgetKey": "nr2MonthlyTrendCombo",
          "colSpan": 8,
          "title": "Executive Monthly Trend",
          "dataBind": "PageCanvasData.nr2MonthlyTrendCombo()",
          "chartType": "dual"
        },
        {
          "id": "fin-collection-lag",
          "type": "gauge",
          "widgetKey": "nr2CollectionLag",
          "colSpan": 4,
          "title": "Collection Lag (DSO)",
          "dataBind": "PageCanvasData.nr2CollectionLag()"
        },
        {
          "id": "fin-reconciliation",
          "type": "table",
          "widgetKey": "nr2ProductionReconciliation",
          "colSpan": 6,
          "title": "Production vs QuickBooks Reconciliation",
          "dataBind": "PageCanvasData.nr2ProductionReconciliation()"
        },
        {
          "id": "fin-daily-production",
          "type": "chart",
          "widgetKey": "softdentProductionDaily",
          "colSpan": 6,
          "title": "SoftDent Production Trend",
          "dataBind": "PageCanvasData.softdentProductionDailySeries()",
          "chartType": "bar"
        },
        {
          "id": "fin-provider-performance",
          "type": "stat-grid",
          "widgetKey": "providerPerformance",
          "colSpan": 6,
          "title": "Provider Performance",
          "dataBind": "PageCanvasData.providerBars()"
        },
        {
          "id": "fin-provider-production",
          "type": "table",
          "widgetKey": "softdentProviderProduction",
          "colSpan": 6,
          "title": "Provider Production",
          "dataBind": "PageCanvasData.softdentProviderProductionData()"
        },
        {
          "id": "fin-provider-comp",
          "type": "stat-grid",
          "widgetKey": "nr2ProviderCompensationWidget",
          "colSpan": 6,
          "title": "Provider Production Share",
          "dataBind": "PageCanvasData.nr2ProviderCompensation()"
        },
        {
          "id": "fin-collections-daily",
          "type": "chart",
          "widgetKey": "softdentCollectionsDaily",
          "colSpan": 6,
          "title": "Collections Trend",
          "dataBind": "PageCanvasData.softdentCollectionsDailySeries()",
          "chartType": "bar"
        },
        {
          "id": "fin-new-patients-mtd",
          "type": "stat-grid",
          "widgetKey": "softdentNewPatientsMTD",
          "colSpan": 4,
          "title": "New Patients",
          "dataBind": "PageCanvasData.softdentNewPatientsMtdData()"
        },
        {
          "id": "fin-claims-outstanding",
          "type": "stat-grid",
          "widgetKey": "softdentClaimsOutstanding",
          "colSpan": 4,
          "title": "Outstanding Claims",
          "dataBind": "PageCanvasData.softdentClaimsOutstandingData()"
        },
        {
          "id": "fin-new-patients",
          "type": "chart",
          "widgetKey": "newPatients",
          "colSpan": 4,
          "title": "New Patient Flow",
          "dataBind": "PageCanvasData.metrics('newPatients')",
          "chartType": "bar"
        },
        {
          "id": "fin-appointments",
          "type": "table",
          "widgetKey": "softdentAppointmentsSnapshot",
          "colSpan": 12,
          "title": "Appointments Snapshot",
          "dataBind": "PageCanvasData.softdentAppointmentsSnapshotData()"
        }
      ]
    },
    "taxes": {
      "title": "S Corp Tax Planning",
      "shell": "widget-grid",
      "panels": [
        {
          "id": "tax-qb-pl",
          "type": "table",
          "widgetKey": "quickbooksProfitLossDetail",
          "colSpan": 6,
          "title": "Book Income (QuickBooks YTD)",
          "dataBind": "PageCanvasData.quickbooksPlRows()"
        },
        {
          "id": "tax-ebitda",
          "type": "table",
          "widgetKey": "ebitdaNormalization",
          "colSpan": 6,
          "title": "Owner Add-backs & Adjustments",
          "dataBind": "PageCanvasData.ebitdaRows()"
        },
        {
          "id": "tax-monthly-revenue",
          "type": "chart",
          "widgetKey": "quickbooksMonthlyRevenue",
          "colSpan": 6,
          "title": "Monthly Revenue Trend",
          "dataBind": "PageCanvasData.quickbooksMonthlyRevenueSeries()",
          "chartType": "bar"
        },
        {
          "id": "tax-net-income",
          "type": "stat-grid",
          "widgetKey": "quickbooksNetIncomeSummary",
          "colSpan": 6,
          "title": "Net Income Summary",
          "dataBind": "PageCanvasData.quickbooksNetIncomeSummary()"
        },
        {
          "id": "tax-balance-sheet",
          "type": "table",
          "widgetKey": "quickbooksBalanceSheetSummary",
          "colSpan": 6,
          "title": "Balance Sheet Summary",
          "dataBind": "PageCanvasData.quickbooksBalanceSheetSummary()"
        },
        {
          "id": "tax-cash-flow",
          "type": "chart",
          "widgetKey": "quickbooksCashFlowTrend",
          "colSpan": 6,
          "title": "Cash Flow Trend",
          "dataBind": "PageCanvasData.quickbooksCashFlowTrend()",
          "chartType": "dual"
        },
        {
          "id": "tax-revenue-service",
          "type": "donut",
          "widgetKey": "quickbooksRevenueByService",
          "colSpan": 4,
          "title": "Revenue by Service",
          "dataBind": "PageCanvasData.quickbooksRevenueByService()",
          "chartType": "donut"
        },
        {
          "id": "tax-ar-aging",
          "type": "table",
          "widgetKey": "quickbooksArAging",
          "colSpan": 8,
          "title": "QuickBooks A/R Aging",
          "dataBind": "PageCanvasData.quickbooksQbArAging()"
        },
        {
          "id": "tax-expense-breakdown",
          "type": "stat-grid",
          "widgetKey": "quickbooksExpenseBreakdown",
          "colSpan": 6,
          "title": "Operating Expenses",
          "dataBind": "PageCanvasData.quickbooksExpenseBars()"
        },
        {
          "id": "tax-ap",
          "type": "table",
          "widgetKey": "accountsPayableAutomation",
          "colSpan": 6,
          "title": "Accounts Payable",
          "dataBind": "PageCanvasData.metrics('accountsPayableAutomation')"
        },
        {
          "id": "tax-period-close",
          "type": "stat-grid",
          "widgetKey": "periodCloseAndPosting",
          "colSpan": 6,
          "title": "Period Close",
          "dataBind": "PageCanvasData.documentsPeriodStats()"
        },
        {
          "id": "tax-journal-queue",
          "type": "table",
          "widgetKey": "journalPostingQueue",
          "colSpan": 6,
          "title": "Journal Entries",
          "dataBind": "PageCanvasData.journalQueueItems()"
        }
      ]
    },
    "hal": {
      "title": "HAL Command Center",
      "shell": "dashboard-grid",
      "panels": [
        {
          "id": "hal-ask",
          "type": "custom",
          "widgetKey": "halAskHal",
          "colSpan": 12,
          "title": "Ask HAL",
          "dataBind": "PageCanvasData.widget('halAskHal')"
        },
        {
          "id": "hal-import-health",
          "type": "stat-grid",
          "widgetKey": "halImportHealth",
          "colSpan": 3,
          "title": "Import & Source Health",
          "dataBind": "PageCanvasData.integrationMetric('halImportHealth')"
        },
        {
          "id": "hal-fin-overview",
          "type": "stat-grid",
          "widgetKey": "practiceFinancialOverview",
          "colSpan": 3,
          "title": "Practice Financial Overview",
          "dataBind": "PageCanvasData.metrics('practiceFinancialOverview')"
        },
        {
          "id": "hal-care-delivery",
          "type": "stat-grid",
          "widgetKey": "careDeliveryPerformance",
          "colSpan": 3,
          "title": "Care Delivery Performance",
          "dataBind": "PageCanvasData.metrics('careDeliveryPerformance')"
        },
        {
          "id": "hal-qb-pl",
          "type": "stat-grid",
          "widgetKey": "quickbooksProfitLossDetail",
          "colSpan": 3,
          "title": "Profit & Loss Summary",
          "dataBind": "PageCanvasData.metrics('quickbooksProfitLossDetail')"
        },
        {
          "id": "hal-surfaces",
          "type": "kanban",
          "widgetKey": "officeManagerSurfaces",
          "colSpan": 12,
          "title": "Staff Work Surfaces",
          "dataBind": "PageCanvasData.metrics('officeManagerSurfaces')"
        }
      ]
    },
    "softdent": {
      "title": "Care Delivery & Practice Velocity",
      "shell": "widget-grid",
      "panels": [
        {
          "id": "sd-hero-kpis",
          "type": "hero-kpi",
          "colSpan": 12,
          "dataBind": "PageCanvasData.softdentHeroKpis()",
          "kpis": [
            { "widgetKey": "careDeliveryPerformance", "label": "Production MTD" },
            { "widgetKey": "softdentNewPatientsMTD", "label": "New Patients" },
            { "widgetKey": "softdentCollectionsDaily", "label": "Collections Trend" },
            { "widgetKey": "softdentClaimsOutstanding", "label": "Outstanding Claims" }
          ]
        },
        {
          "id": "sd-op-grid",
          "type": "custom",
          "widgetKey": "softdentOperatoryGrid",
          "colSpan": 8,
          "title": "Operatory Schedule",
          "dataBind": "PageCanvasData.softdentOperatoryGrid()"
        },
        {
          "id": "sd-appt-snapshot",
          "type": "stat-grid",
          "widgetKey": "softdentAppointmentsSnapshot",
          "colSpan": 4,
          "title": "Appointments Snapshot",
          "dataBind": "PageCanvasData.softdentAppointmentStats()"
        },
        {
          "id": "sd-ar-aging",
          "type": "heatmap",
          "widgetKey": "softdentArAging",
          "colSpan": 6,
          "title": "Accounts Receivable Aging",
          "dataBind": "PageCanvasData.softdentArAgingHeatmap()"
        },
        {
          "id": "sd-resp-donut",
          "type": "donut",
          "widgetKey": "softdentResponsibility",
          "colSpan": 3,
          "title": "Insurance vs Patient Balance",
          "dataBind": "PageCanvasData.softdentResponsibilityDonut()"
        },
        {
          "id": "sd-case-gauge",
          "type": "gauge",
          "widgetKey": "caseAcceptance",
          "colSpan": 3,
          "title": "Case Acceptance Rate",
          "dataBind": "PageCanvasData.metrics('caseAcceptance')"
        },
        {
          "id": "sd-tx-funnel",
          "type": "funnel",
          "widgetKey": "treatmentPlanSummary",
          "colSpan": 6,
          "title": "Treatment Plans Presented",
          "dataBind": "PageCanvasData.treatmentPlanFunnel()"
        },
        {
          "id": "sd-hyg-gauge",
          "type": "gauge",
          "widgetKey": "hygieneRecall",
          "colSpan": 3,
          "title": "Hygiene & Recall",
          "dataBind": "PageCanvasData.hygieneRecallGauge()"
        },
        {
          "id": "sd-prov-bar",
          "type": "chart",
          "widgetKey": "softdentProviderProduction",
          "colSpan": 3,
          "title": "Provider Production",
          "dataBind": "PageCanvasData.softdentProviderProductionData()",
          "chartType": "bar"
        }
      ]
    },
    "narratives": {
      "title": "Clinical Documentation & Justification Composer",
      "shell": "widget-grid",
      "panels": [
        {
          "id": "nar-composer",
          "type": "kanban",
          "widgetKey": "narrativeWorkflow",
          "colSpan": 12,
          "title": "Narrative Composer",
          "dataBind": "PageCanvasData.narrativeKanban()"
        }
      ]
    },
    "claims": {
      "title": "Open Insurance Claims",
      "shell": "widget-grid",
      "panels": [
        {
          "id": "clm-analytics",
          "type": "hero-kpi",
          "colSpan": 12,
          "dataBind": "PageCanvasData.claimsPipelineSummary()",
          "kpis": [
            { "halSubpanel": "claimsKpiTotal", "label": "Total Open Value" },
            { "halSubpanel": "claimsKpiAge", "label": "Average Age" },
            { "halSubpanel": "claimsKpiDenied", "label": "Denial Rate" },
            { "halSubpanel": "claimsKpiAttachments", "label": "Pending Attachments" }
          ]
        },
        {
          "id": "clm-pipeline",
          "type": "kanban",
          "widgetKey": "claimsPipeline",
          "colSpan": 12,
          "title": "Open Insurance Claims",
          "dataBind": "PageCanvasData.claimsKanban()"
        }
      ]
    },
    "ar": {
      "title": "A/R Mission Control",
      "shell": "widget-grid",
      "panels": [
        {
          "id": "ar-hero-kpis",
          "type": "hero-kpi",
          "colSpan": 12,
          "dataBind": "PageCanvasData.arEliteKpis()",
          "kpis": [
            { "halSubpanel": "arKpiTotal", "label": "Total A/R" },
            { "halSubpanel": "arKpiCurrent", "label": "Current (0–30)" },
            { "halSubpanel": "arKpi3160", "label": "31–60 Days" },
            { "halSubpanel": "arKpi6190", "label": "61–90 Days" },
            { "halSubpanel": "arKpi90plus", "label": "90+ Days" },
            { "halSubpanel": "arKpiDso", "label": "DSO" }
          ]
        },
        {
          "id": "ar-aging-heatmap",
          "type": "custom",
          "widgetKey": "arAgingAndCollections",
          "colSpan": 8,
          "title": "A/R Waterfall & Collections Heatmap"
        },
        {
          "id": "ar-outstanding-claims",
          "type": "table",
          "widgetKey": "arOutstandingClaims",
          "colSpan": 4,
          "title": "Outstanding Claims",
          "dataBind": "PageCanvasData.arTopClaimsTable()"
        },
        {
          "id": "ar-follow-up-queue",
          "type": "kanban",
          "widgetKey": "smartClaimsAndReceivables",
          "colSpan": 12,
          "title": "Follow-up Queue",
          "dataBind": "PageCanvasData.arFollowUpKanban()"
        }
      ]
    },
    "quickbooks": {
      "title": "QuickBooks Integration",
      "shell": "dashboard-grid",
      "panels": [
        {
          "id": "qb-pl-summary",
          "type": "table",
          "widgetKey": "quickbooksProfitLossDetail",
          "colSpan": 6,
          "title": "Profit & Loss Summary (YTD)",
          "dataBind": "PageCanvasData.quickbooksPlRows()"
        },
        {
          "id": "qb-ebitda-bridge",
          "type": "table",
          "widgetKey": "ebitdaNormalization",
          "colSpan": 6,
          "title": "EBITDA Normalization",
          "dataBind": "PageCanvasData.ebitdaRows()"
        },
        {
          "id": "qb-cash-flow",
          "type": "chart",
          "widgetKey": "quickbooksCashFlowTrend",
          "colSpan": 8,
          "title": "Cash Flow Trend",
          "dataBind": "PageCanvasData.quickbooksCashFlowTrend()",
          "chartType": "dual"
        },
        {
          "id": "qb-expense-breakdown",
          "type": "stat-grid",
          "widgetKey": "quickbooksExpenseBreakdown",
          "colSpan": 4,
          "title": "Operating Expenses",
          "dataBind": "PageCanvasData.quickbooksExpenseBars()"
        },
        {
          "id": "qb-monthly-revenue",
          "type": "chart",
          "widgetKey": "quickbooksMonthlyRevenue",
          "colSpan": 6,
          "title": "Monthly Revenue Trend",
          "dataBind": "PageCanvasData.quickbooksMonthlyRevenueSeries()",
          "chartType": "bar"
        },
        {
          "id": "qb-net-income",
          "type": "stat-grid",
          "widgetKey": "quickbooksNetIncomeSummary",
          "colSpan": 6,
          "title": "Net Income Summary",
          "dataBind": "PageCanvasData.quickbooksNetIncomeSummary()"
        },
        {
          "id": "qb-balance-sheet",
          "type": "table",
          "widgetKey": "quickbooksBalanceSheetSummary",
          "colSpan": 6,
          "title": "Balance Sheet Summary",
          "dataBind": "PageCanvasData.quickbooksBalanceSheetSummary()"
        },
        {
          "id": "qb-revenue-service",
          "type": "donut",
          "widgetKey": "quickbooksRevenueByService",
          "colSpan": 3,
          "title": "Revenue by Service",
          "dataBind": "PageCanvasData.quickbooksRevenueByService()",
          "chartType": "donut"
        },
        {
          "id": "qb-ar-aging",
          "type": "table",
          "widgetKey": "quickbooksArAging",
          "colSpan": 3,
          "title": "QuickBooks A/R Aging",
          "dataBind": "PageCanvasData.quickbooksQbArAging()"
        }
      ]
    },
    "documents": {
      "title": "Accounting Documents",
      "shell": "widget-grid",
      "panels": [
        {
          "id": "doc-intake",
          "type": "table",
          "widgetKey": "documentIntakeQueue",
          "colSpan": 8,
          "title": "Recent Accounting Documents",
          "dataBind": "PageCanvasData.metrics('documentIntakeQueue')"
        },
        {
          "id": "doc-preview",
          "type": "custom",
          "widgetKey": "documentPreview",
          "colSpan": 4,
          "title": "Document Preview",
          "dataBind": "PageCanvasData.metrics('documentPreview')"
        },
        {
          "id": "period-close",
          "type": "gauge",
          "widgetKey": "periodCloseAndPosting",
          "colSpan": 6,
          "title": "Period Close",
          "dataBind": "PageCanvasData.metrics('periodCloseAndPosting')"
        },
        {
          "id": "ap-auto",
          "type": "funnel",
          "widgetKey": "accountsPayableAutomation",
          "colSpan": 6,
          "title": "Accounts Payable",
          "dataBind": "PageCanvasData.metrics('accountsPayableAutomation')"
        },
        {
          "id": "journal-queue",
          "type": "table",
          "widgetKey": "journalPostingQueue",
          "colSpan": 12,
          "title": "Journal Entries",
          "dataBind": "PageCanvasData.metrics('journalPostingQueue')"
        },
        {
          "id": "doc-sources",
          "type": "stat-grid",
          "halSubpanel": "documentsSourceBreakdown",
          "colSpan": 12,
          "title": "Source breakdown",
          "dataBind": "PageCanvasData.documentsSourceBreakdown()"
        }
      ]
    },
    "library": {
      "title": "Document Library",
      "shell": "widget-grid",
      "panels": [
        {
          "id": "lib-facets",
          "type": "custom",
          "halSubpanel": "categoryFacets",
          "colSpan": 3,
          "title": "Categories",
          "dataBind": "PageCanvasData.libraryFacets()"
        },
        {
          "id": "lib-main",
          "type": "table",
          "widgetKey": "documentLibrary",
          "colSpan": 9,
          "title": "Library & Preview",
          "dataBind": "PageCanvasData.metrics('documentLibrary')"
        }
      ]
    },
    "office-manager": {
      "title": "Office Command Center",
      "shell": "dashboard-grid",
      "panels": [
        {
          "id": "om-priorities",
          "type": "kanban",
          "widgetKey": "officeManagerPriorities",
          "colSpan": 8,
          "title": "Today's Focus",
          "dataBind": "PageCanvasData.metrics('officeManagerPriorities')"
        },
        {
          "id": "om-tasks",
          "type": "table",
          "halSubpanel": "officeTaskQueue",
          "colSpan": 12,
          "title": "Office task queue",
          "dataBind": "PageCanvasData.officeTaskRows()"
        },
        {
          "id": "om-surfaces",
          "type": "stat-grid",
          "widgetKey": "officeManagerSurfaces",
          "colSpan": 4,
          "title": "Staff Work Surfaces",
          "dataBind": "PageCanvasData.metrics('officeManagerSurfaces')"
        }
      ]
    }
  }
};

if (typeof module !== "undefined" && module.exports) {
  module.exports = MOONSHOT_PAGE_LAYOUTS;
}
if (typeof globalThis !== "undefined") {
  globalThis.MOONSHOT_PAGE_LAYOUTS = MOONSHOT_PAGE_LAYOUTS;
}
if (typeof window !== "undefined") {
  window.MOONSHOT_PAGE_LAYOUTS = MOONSHOT_PAGE_LAYOUTS;
}
