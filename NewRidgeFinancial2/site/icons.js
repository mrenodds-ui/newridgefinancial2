/**
 * Shared inline SVG icons for nav, HAL widgets, and page surfaces.
 * Uses currentColor so icons inherit sidebar/toolbar/badge tones.
 */
const AppIcons = (function () {
  const BASE =
    'xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"';

  function svg(paths, className) {
    const cls = className ? ` class="${className}"` : ' class="app-ico"';
    return `<svg${cls} ${BASE}>${paths}</svg>`;
  }

  const NAV = {
    financial: svg('<path d="M3 20V4"/><path d="M7 16l3-5 3 3 4-6 4 8"/>'),
    softdent: svg('<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M8 12h8"/><path d="M12 8v8"/>'),
    quickbooks: svg('<path d="M12 2v20"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>'),
    ar: svg('<path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/>'),
    claims: svg('<path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/><path d="M9 12h6"/><path d="M9 16h6"/>'),
    narratives: svg('<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>'),
    documents: svg('<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6"/><path d="M8 13h8"/><path d="M8 17h5"/>'),
    library: svg('<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z"/>'),
    "office-manager": svg('<circle cx="12" cy="12" r="3"/><path d="M12 2v3"/><path d="M12 19v3"/><path d="m4.9 4.9 2.1 2.1"/><path d="m16.9 16.9 2.1 2.1"/><path d="M2 12h3"/><path d="M19 12h3"/><path d="m4.9 19.1 2.1-2.1"/><path d="m16.9 7.1 2.1-2.1"/>'),
    hal: svg('<path d="M12 3 4 9v6l8 6 8-6V9Z"/><path d="M12 12 4 9"/><path d="m12 12 8-3"/><path d="M12 12v9"/>'),
  };

  const WIDGET = {
    practiceFinancialOverview: NAV.financial,
    financialProductionTrend: svg('<path d="M3 20V4"/><path d="M7 16l3-5 3 3 4-6 4 8"/>'),
    payerMixAndCollections: svg('<path d="M12 3v18"/><path d="M3 8h18"/><path d="M7 12h10"/>'),
    providerPerformance: svg('<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>'),
    dataFreshnessQuality: svg('<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>'),
    ebitdaNormalization: svg('<path d="M4 19h16"/><path d="M7 16V8"/><path d="M12 16V5"/><path d="M17 16v-4"/>'),
    quickbooksProfitLossDetail: NAV.quickbooks,
    quickbooksSyncHealth: svg('<path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/>'),
    accountsPayableAutomation: svg('<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M19 8v6"/><path d="M22 11h-6"/>'),
    documentIntakeQueue: svg('<path d="M4 6h16"/><path d="M4 10h16"/><path d="M4 14h10"/><path d="M4 18h7"/>'),
    documentPreview: svg('<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>'),
    periodCloseAndPosting: svg('<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4"/><path d="M8 2v4"/><path d="M3 10h18"/>'),
    smartClaimsAndReceivables: NAV.claims,
    claimsPipeline: svg('<path d="M6 3h12l4 6-10 12L2 9Z"/>'),
    claimReadinessAndSafety: svg('<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/>'),
    careDeliveryPerformance: NAV.softdent,
    softdentArAging: svg('<path d="M12 2v20"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>'),
    softdentResponsibility: svg('<path d="M16 3h5v5"/><path d="M8 3H3v5"/><path d="M21 16v5h-5"/><path d="M8 21H3v-5"/>'),
    softdentSourceHealth: svg('<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/>'),
    softdentExportHistory: svg('<path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/>'),
    newPatients: svg('<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M19 8v6"/><path d="M22 11h-6"/>'),
    treatmentPlanSummary: svg('<path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>'),
    caseAcceptance: svg('<path d="m9 12 2 2 4-4"/><circle cx="12" cy="12" r="9"/>'),
    arAgingAndCollections: NAV.ar,
    arOutstandingClaims: NAV.claims,
    narrativeWorkflow: NAV.narratives,
    documentLibrary: NAV.library,
    halCommandPalette: NAV.hal,
    officeManagerPriorities: NAV["office-manager"],
    officeManagerTasks: svg('<path d="M8 6h13"/><path d="M8 12h13"/><path d="M8 18h13"/><path d="M3 6h.01"/><path d="M3 12h.01"/><path d="M3 18h.01"/>'),
    officeManagerBoundaries: svg('<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="M9 12h6"/>'),
    officeManagerSurfaces: svg('<rect x="3" y="4" width="7" height="7" rx="1"/><rect x="14" y="4" width="7" height="7" rx="1"/><rect x="3" y="15" width="7" height="5" rx="1"/><rect x="14" y="15" width="7" height="5" rx="1"/>'),
  };

  const UI = {
    chevronDown: svg('<path d="m6 9 6 6 6-6"/>'),
    filter: svg('<path d="M3 5h18"/><path d="M6 12h12"/><path d="M10 19h4"/>'),
    more: svg('<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>'),
    export: svg('<path d="M12 3v12"/><path d="m7 8 5-5 5 5"/><path d="M5 21h14"/>'),
    externalLink: svg('<path d="M14 3h7v7"/><path d="M10 14 21 3"/><path d="M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5"/>'),
    lock: svg('<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>'),
    shield: WIDGET.claimReadinessAndSafety,
    empty: svg('<path d="M4 4h16v16H4Z"/><path d="M8 9h8"/><path d="M8 13h5"/>'),
    error: svg('<path d="M12 9v4"/><path d="M12 17h.01"/><path d="M10.3 3.9 2.6 17.4A2 2 0 0 0 4.3 20h15.4a2 2 0 0 0 1.7-2.6L13.7 3.9a2 2 0 0 0-3.4 0Z"/>'),
    pin: svg('<path d="M12 17v5"/><path d="M8 3h8l-1 8 3 3v3H6v-3l3-3Z"/>'),
    unpin: svg('<path d="m3 3 18 18"/><path d="M12 17v5"/><path d="M8 3h8l-1 8 3 3v3H8"/>'),
    close: svg('<path d="M18 6 6 18"/><path d="m6 6 12 12"/>'),
    voice: svg('<path d="M11 5 6 9H3v6h3l5 4Z"/><path d="M16 9.5a4 4 0 0 1 0 5"/><path d="M19 7a8 8 0 0 1 0 10"/>'),
  };

  const GLANCE = [
    svg('<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>'),
    svg('<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4"/><path d="M8 2v4"/><path d="M3 10h18"/>'),
    NAV.claims,
    NAV.narratives,
    NAV.financial,
    NAV.ar,
  ];

  function nav(pageId) {
    return NAV[pageId] || NAV.hal;
  }

  function widget(widgetKey) {
    return WIDGET[widgetKey] || NAV.hal;
  }

  function ui(iconKey) {
    return UI[iconKey] || NAV.hal;
  }

  function hal() {
    return NAV.hal;
  }

  function glance(index) {
    return GLANCE[index] || svg('<circle cx="12" cy="12" r="2"/>');
  }

  function isSvg(value) {
    return Boolean(value && String(value).includes("<svg"));
  }

  function wrap(className, icon) {
    if (!icon) return "";
    return `<span class="${className}">${icon}</span>`;
  }

  return { nav, widget, ui, hal, glance, isSvg, wrap, NAV, WIDGET, UI };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = AppIcons;
}
if (typeof window !== "undefined") {
  window.AppIcons = AppIcons;
}
