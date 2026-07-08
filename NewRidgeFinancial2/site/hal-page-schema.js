/**
 * HAL Command Center page schema — derived from PageSchema (single source of truth).
 * Layout zones stay HAL-specific; widget catalog mirrors staff page inventory.
 */
(function () {
  if (typeof window === "undefined") return;
  if (window.NR2_WORKSTATION_ONLY) return;
  if (!window.PageSchema) {
    throw new Error("[NR2] HAL_SCHEMA_ABORT: PageSchema missing. Legacy schema retired.");
  }
  if (window.PageSchema.LAYOUT_EPOCH !== "moonshot-mockup") {
    throw new Error("[NR2] HAL_SCHEMA_ABORT: Expected moonshot-mockup epoch.");
  }
  window.PageSchema.SCHEMA_VERSION = "hal-10092";
})();

const HalPageSchema = (function () {
  function pageSchemaApi() {
    if (typeof PageSchema !== "undefined") return PageSchema;
    if (typeof globalThis !== "undefined" && globalThis.PageSchema) return globalThis.PageSchema;
    return null;
  }

  const GRID = {
    className: "dashboard-grid",
    areas: {
      command: "command",
      status: "status",
      widgets: "widgets",
      nav: "nav",
      sidenotes: "sidenotes",
      session: "session",
    },
  };

  const ZONES = [
    { id: "command", gridArea: "command", title: "Ask HAL", kind: "command-composer" },
    { id: "status", gridArea: "status", title: "Program Status", kind: "status-rail" },
    { id: "widgets", gridArea: "widgets", title: "Manager Widgets", kind: "widget-monitor" },
    { id: "nav", gridArea: "nav", title: "Staff Work Surfaces", kind: "surface-list", icon: { type: "ui", key: "surface" } },
    { id: "sidenotes", gridArea: "sidenotes", title: "Staff Notes", kind: "sidenotes", icon: { type: "nav", key: "sidenotes" } },
    { id: "session", gridArea: "session", title: "Session", kind: "session-footer" },
  ];

  const SECTION_META = {
    Overview: { accent: "green", iconPage: "financial", title: "Financial Widgets" },
    Clinical: { accent: "green", iconPage: "softdent", title: "Clinical Widgets" },
    Revenue: { accent: "blue", iconPage: "quickbooks", title: "Revenue & A/R" },
    Operations: { accent: "yellow", iconPage: "office-manager", title: "Operations" },
  };

  /** Staff-page widget groups only — HAL meta widgets already have dedicated panels on the HAL page. */
  function buildWidgetGroups(PS) {
    if (!PS || !PS.NAV_GROUPS) return [];

    const groups = [];

    PS.NAV_GROUPS.forEach((group) => {
      const pageIds = group.pages.filter((id) => id !== "hal");
      const seen = new Set();
      const widgets = [];
      pageIds.forEach((pageId) => {
        const entries = PS.widgetsFor ? PS.widgetsFor(pageId) : (PS.byId(pageId) && PS.byId(pageId).widgets) || [];
        entries.forEach((entry) => {
          if (!entry || !entry.key || seen.has(entry.key)) return;
          seen.add(entry.key);
          widgets.push({ key: entry.key, nav: pageId, title: entry.title });
        });
      });
      if (!widgets.length) return;
      const meta = SECTION_META[group.section] || { accent: "gray", iconPage: pageIds[0] || "financial" };
      groups.push({
        id: String(group.section || "group")
          .toLowerCase()
          .replace(/\s+/g, "-"),
        title: meta.title || group.section,
        accent: meta.accent,
        icon: { type: "nav", key: meta.iconPage },
        widgets,
      });
    });

    return groups;
  }

  function buildPage(PS, widgetGroups) {
    const hal = PS && PS.byId ? PS.byId("hal") : null;
    const widgets = widgetGroups.flatMap((group) => group.widgets);
    if (hal) {
      return {
        id: hal.id,
        label: hal.label,
        title: hal.title,
        subtitle: hal.subtitle,
        accent: hal.accent,
        safety: hal.safety,
        commands: hal.commands,
        filters: hal.filters,
        widgets,
      };
    }
    return {
      id: "hal",
      label: "HAL",
      title: "HAL Command Center",
      subtitle: "Ask HAL · monitor widgets · open staff surfaces",
      accent: "gold",
      safety: "Local manager · Consent before outbound · Direct-first imports",
      commands: ["Make a plan for today", "Show manager dashboard widgets", "Import status", "What needs review"],
      widgets,
    };
  }

  const PS = pageSchemaApi();
  const WIDGET_GROUPS = buildWidgetGroups(PS);
  const PAGE = buildPage(PS, WIDGET_GROUPS);

  function zoneById(id) {
    return ZONES.find((z) => z.id === id) || null;
  }

  function widgetGroupZones() {
    return WIDGET_GROUPS;
  }

  function syncedSchemaVersion() {
    const ps = pageSchemaApi();
    return (ps && ps.SCHEMA_VERSION) || "hal-10040";
  }

  return {
    get SCHEMA_VERSION() {
      return syncedSchemaVersion();
    },
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
