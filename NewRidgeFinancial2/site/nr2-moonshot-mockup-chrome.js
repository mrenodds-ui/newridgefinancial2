/**
 * Moonshot 2026-07-07 mockup chrome — production-only shell for financial program.
 * No pv-canvas-* classes; matches .local_logs/.../page_mockups/*.html structure.
 */
const MoonshotMockupChrome = (function () {
  const NAV_ICONS = {
    financial: "📊",
    taxes: "📑",
    hal: "🤖",
    softdent: "🦷",
    narratives: "📝",
    claims: "📋",
    ar: "💰",
    quickbooks: "📚",
    documents: "📄",
    library: "📖",
    "office-manager": "⚙️",
  };

  function esc(value) {
    return String(value == null ? "" : value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function pageLabel(page) {
    if (!page) return "";
    if (page.id === "office-manager") return "Office Mgr";
    return page.label || page.id;
  }

  function pageWidgets(page) {
    if (!page || !Array.isArray(page.widgets)) return [];
    const seen = new Set();
    return page.widgets.filter((widget) => {
      if (!widget || !widget.key || seen.has(widget.key)) return false;
      seen.add(widget.key);
      return true;
    });
  }

  function halWidgetPanelKey(widgetKey) {
    const map = {
      halAskHal: "askHal",
      halMorningBriefing: "morningBriefing",
      halSituationalHero: "situationalHero",
      halImportHealth: "importHealth",
      sidenotesProgram: "sidenotes",
      officeManagerSurfaces: "workSurfaces",
    };
    return map[widgetKey] || null;
  }

  function renderNavSubitems(page, activeId) {
    if (!page || page.id !== activeId) return "";
    if (Array.isArray(page.navGroups) && page.navGroups.length) {
      const widgets = pageWidgets(page);
      const byKey = Object.fromEntries(widgets.map((widget) => [widget.key, widget]));
      const groups = page.navGroups
        .map((group) => {
          const keys = Array.isArray(group.widgets) ? group.widgets : [];
          const items = keys
            .map((key) => byKey[key])
            .filter(Boolean)
            .map((widget) => {
              const label = widget.title || widget.key;
              const panel = page.id === "hal" ? halWidgetPanelKey(widget.key) : null;
              const attrs = panel
                ? ` data-nav-page="${esc(page.id)}" data-nav-panel="${esc(panel)}"`
                : ` data-nav-page="${esc(page.id)}" data-nav-widget="${esc(widget.key)}"`;
              return `<button type="button" class="nav-subitem"${attrs} title="${esc(label)}">
          <span class="nav-subitem__label">${esc(label)}</span>
        </button>`;
            })
            .join("");
          if (!items) return "";
          return `<div class="nav-subgroup">
          <p class="nav-subgroup__title">${esc(group.label || "")}</p>
          ${items}
        </div>`;
        })
        .join("");
      if (groups) {
        return `<div class="nav-sublist nav-sublist--grouped" aria-label="${esc(pageLabel(page))} sections">${groups}</div>`;
      }
    }
    const widgets = pageWidgets(page);
    if (!widgets.length) return "";
    const items = widgets
      .map((widget) => {
        const label = widget.title || widget.key;
        const panel = page.id === "hal" ? halWidgetPanelKey(widget.key) : null;
        const attrs = panel
          ? ` data-nav-page="${esc(page.id)}" data-nav-panel="${esc(panel)}"`
          : ` data-nav-page="${esc(page.id)}" data-nav-widget="${esc(widget.key)}"`;
        return `<button type="button" class="nav-subitem"${attrs} title="${esc(label)}">
          <span class="nav-subitem__label">${esc(label)}</span>
        </button>`;
      })
      .join("");
    return `<div class="nav-sublist" aria-label="${esc(pageLabel(page))} sections">${items}</div>`;
  }

  function renderNavItem(page, activeId) {
    const icon = NAV_ICONS[page.id] || "•";
    const active = page.id === activeId ? " active" : "";
    return `<div class="nav-page${active ? " nav-page--active" : ""}">
        <button type="button" class="nav-item${active}" data-nav="${esc(page.id)}" aria-current="${page.id === activeId ? "page" : "false"}" aria-expanded="${page.id === activeId && pageWidgets(page).length ? "true" : "false"}">
          <span class="nav-icon" aria-hidden="true">${icon}</span>
          <span class="nav-label">${esc(pageLabel(page))}</span>
        </button>
        ${renderNavSubitems(page, activeId)}
      </div>`;
  }

  function renderNavRail(activeId) {
    const schema = typeof PageSchema !== "undefined" ? PageSchema : null;
    const practice = schema && schema.PRACTICE ? schema.PRACTICE : null;
    const groups = (schema && schema.NAV_GROUPS) || [];

    const sections = groups
      .map((group) => {
        const items = (group.pages || [])
          .map((pageId) => schema && schema.byId ? schema.byId(pageId) : null)
          .filter(Boolean)
          .map((page) => renderNavItem(page, activeId))
          .join("");
        if (!items) return "";
        return `<div class="nav-section">
          <p class="nav-section__title">${esc(group.section || "")}</p>
          ${items}
        </div>`;
      })
      .join("");

    const practiceBlock = practice
      ? `<div class="nav-practice">
        <strong class="nav-practice__name">${esc(practice.name || "New Ridge Family Dental")}</strong>
        <span class="nav-practice__meta">${esc(practice.location || "Ridgefield, Connecticut")}</span>
      </div>`
      : "";

    return `<div class="nav-brand">
        <h2>NEW RIDGE</h2>
        <span>Financial 2.0</span>
      </div>
      ${practiceBlock}
      <nav class="nav-rail-items" id="nav">${sections}</nav>`;
  }

  function practiceMetaLine(practice) {
    if (!practice) return "";
    const parts = [practice.location, practice.descriptor, practice.period].filter(Boolean);
    return parts.join(" • ");
  }

  function renderTopHeader(state) {
    const practice = typeof PageSchema !== "undefined" ? PageSchema.PRACTICE : null;
    const safety = (state && state.safety) || (practice && practice.safety) || "Local data only";
    return `<header class="top-header">
      <div class="practice-info">
        <h1>${esc(practice ? practice.name : "New Ridge Family Dental")}</h1>
        <p>${esc(practiceMetaLine(practice))}</p>
      </div>
      <div class="safety-badge" title="Imports and HAL run on this machine only">${esc(safety)}</div>
    </header>`;
  }

  function renderHero(schema) {
    if (!schema) return "";
    return `<section class="hero">
      <h2>${esc(schema.title || "")}</h2>
      <p>${esc(schema.subtitle || "")}</p>
      <div class="accent-stripe" aria-hidden="true"></div>
    </section>`;
  }

  function renderFilterBar(filters, pageId) {
    const PF = typeof NR2PageFilters !== "undefined" ? NR2PageFilters : null;
    const activeIdx = PF && pageId ? (PF.getPage(pageId).chipIndex || 0) : 0;
    const chips = (filters || [])
      .map(
        (label, i) =>
          `<button type="button" class="chip${i === activeIdx ? " active" : ""}" data-nr2-filter-chip="${i}" aria-pressed="${i === activeIdx ? "true" : "false"}">${esc(label)}</button>`,
      )
      .join("");
    return `<div class="filter-bar"${pageId ? ` data-nr2-filter-bar="${esc(pageId)}"` : ""}>${chips}</div>`;
  }

  function renderPageCommandChips(commands) {
    const list = (commands || []).slice(0, 6);
    if (!list.length) return "";
    const chips = list
      .map((cmd) => {
        const label = String(cmd || "").trim();
        if (!label) return "";
        return `<button type="button" class="prompt-chip" data-page-command="${esc(label)}">${esc(label)}</button>`;
      })
      .join("");
    return `<div class="prompt-chips prompt-chips--page" data-nr2-hal-commands>${chips}</div>`;
  }

  const STAFF_HEADER_TOOL_PAGES = new Set([
    "financial",
    "taxes",
    "softdent",
    "quickbooks",
    "ar",
    "claims",
    "documents",
    "office-manager",
    "narratives",
    "library",
  ]);

  function renderQuickbooksSyncBadge(readiness) {
    const level = String((readiness && readiness.level) || "unknown").toLowerCase();
    const cold =
      typeof NR2QbReports !== "undefined" &&
      NR2QbReports.isCacheCold &&
      typeof window !== "undefined" &&
      window.__nr2ProgramSnapshot &&
      NR2QbReports.isCacheCold(window.__nr2ProgramSnapshot);
    if (cold || level === "missing" || level === "unknown") {
      const msg =
        typeof NR2QbReports !== "undefined" && NR2QbReports.emptyStateMessage
          ? NR2QbReports.emptyStateMessage()
          : "Awaiting QuickBooks sync";
      return `<div class="sync-badge sync-badge--cold" role="status">
      <span class="sync-indicator" style="background:var(--accent-amber, #ffb800)"></span>
      <span>${esc(msg)}</span>
    </div>`;
    }
    const fresh = level === "fresh";
    const color = fresh ? "var(--accent-green, #2ecc71)" : "var(--accent-amber, #ffb800)";
    const label = fresh ? "QuickBooks synced" : level === "syncing" ? "Sync in progress" : "Sync stale — review import";
    return `<div class="sync-badge" role="status">
      <span class="sync-indicator" style="background:${color}"></span>
      <span>${esc(label)}</span>
    </div>`;
  }

  function renderImportSyncBadge(readiness, schemaId) {
    if (schemaId === "quickbooks") return renderQuickbooksSyncBadge(readiness);
    const level = String((readiness && readiness.level) || "unknown").toLowerCase();
    const fresh = level === "fresh";
    const syncing = level === "syncing";
    const color = fresh ? "var(--accent-green, #2ecc71)" : "var(--accent-amber, #ffb800)";
    const labels = {
      financial: fresh ? "Imports synced" : syncing ? "Sync in progress" : "Import stale — review data",
      taxes: fresh ? "Tax sources synced" : syncing ? "Sync in progress" : "Tax data stale",
      softdent: fresh ? "SoftDent synced" : syncing ? "Sync in progress" : "SoftDent stale",
      ar: fresh ? "A/R sources synced" : syncing ? "Sync in progress" : "A/R data stale",
      claims: fresh ? "Claims synced" : syncing ? "Sync in progress" : "Claims stale",
      documents: fresh ? "Documents synced" : syncing ? "Sync in progress" : "Documents stale",
      "office-manager": fresh ? "Operations synced" : syncing ? "Sync in progress" : "Operations stale",
      narratives: fresh ? "Narratives synced" : syncing ? "Sync in progress" : "Narratives stale",
      library: fresh ? "Library synced" : syncing ? "Sync in progress" : "Library stale",
    };
    const label = labels[schemaId] || (fresh ? "Local imports fresh" : syncing ? "Sync in progress" : "Import stale — review sync");
    return `<div class="sync-badge" role="status">
      <span class="sync-indicator" style="background:${color}"></span>
      <span>${esc(label)}</span>
    </div>`;
  }

  function renderFinancialCpaExportButton() {
    return `<button type="button" class="cpa-export-btn" data-nr2-export="cpa-packet" aria-label="Export CPA packet zip">CPA export</button>`;
  }

  function renderPageStoryboardButton() {
    return `<button type="button" class="storyboard-export-btn" data-nr2-export="page-storyboard" aria-label="Export page storyboard zip for PDF print">Storyboard</button>`;
  }

  function renderPageHeaderTools(schema, opts, commandChipsHtml) {
    const o = opts || {};
    if (!schema || !schema.id) return commandChipsHtml ? `<div class="page-header-tools">${commandChipsHtml}</div>` : "";
    const parts = [];
    if (STAFF_HEADER_TOOL_PAGES.has(schema.id)) {
      parts.push(renderImportSyncBadge(o.importReadiness, schema.id));
      if (typeof NR2Tier3 !== "undefined" && NR2Tier3.renderSemanticZoomToggle) {
        parts.push(NR2Tier3.renderSemanticZoomToggle(schema.id));
      }
      parts.push(renderPageStoryboardButton());
    }
    if (schema.id === "financial") parts.push(renderFinancialCpaExportButton());
    if (commandChipsHtml) parts.push(commandChipsHtml);
    if (!parts.length) return "";
    return `<div class="page-header-tools">${parts.join("")}</div>`;
  }

  function renderHalInsight(insight) {
    if (!insight) return "";
    const body = insight.body || insight.title || "";
    return `<div class="hal-insight" role="status" aria-label="HAL insight">
      <div class="hal-icon" aria-hidden="true">AI</div>
      <div class="hal-text">
        <strong>HAL Insight</strong>
        <p>${esc(body)}</p>
      </div>
    </div>`;
  }

  function renderAlertStrip(state, opts) {
    const o = opts || {};
    if (o.alertStripHtml) {
      return `<div class="alert-strip">${o.alertStripHtml}</div>`;
    }
    const briefing = state && state.halData && state.halData.runtime && state.halData.runtime.proactiveBriefing;
    const text =
      (briefing && briefing.headline) ||
      (state && state.safety) ||
      "HAL monitors local SoftDent and QuickBooks imports only.";
    return `<div class="alert-strip" role="status">
      <div class="alert-icon" aria-hidden="true">!</div>
      <span class="alert-text">${esc(text)}</span>
      <span class="alert-meta">Local data only</span>
    </div>`;
  }

  function pageChromeHal(state, schema, opts) {
    const o = opts || {};
    const toolbar = o.halToolbar || o.toolbarActions || "";
    return `<div class="ms-page-chrome ms-page-chrome--hal">
      ${renderAlertStrip(state, o)}
      <header class="header">
        <div class="header-title">
          <h2>${esc(schema.title || "HAL Command Center")}</h2>
          <span class="badge badge-live">LIVE</span>
        </div>
        <div class="header-status">${toolbar}</div>
      </header>
    </div>`;
  }

  function pageChrome(state, schema, insight, opts) {
    const o = opts || {};
    const commands =
      typeof PageSchema !== "undefined" && PageSchema.commandsFor && schema && schema.id
        ? PageSchema.commandsFor(schema.id)
        : schema && schema.commands
          ? schema.commands
          : [];
    const commandChips =
      typeof window !== "undefined" && window.NR2_FLAGS && window.NR2_FLAGS.hal_commands === false
        ? ""
        : renderPageCommandChips(commands);
    const headerTools = renderPageHeaderTools(schema, o, commandChips);
    return `<div class="ms-page-chrome">
      ${renderTopHeader(state)}
      ${renderHero(schema)}
      ${headerTools}
      ${renderFilterBar(schema && schema.filters, schema && schema.id)}
      ${insight ? renderHalInsight(insight) : ""}
      ${o.halReadinessStrip || ""}
    </div>`;
  }

  function halWidgetsApi() {
    if (typeof HalPageWidgets !== "undefined") return HalPageWidgets;
    if (typeof globalThis !== "undefined" && globalThis.HalPageWidgets) return globalThis.HalPageWidgets;
    return null;
  }

  function proactiveInsight(halData) {
    const briefing = halData && halData.runtime && halData.runtime.proactiveBriefing;
    if (!briefing || !briefing.headline) return null;
    const top = briefing.topAction;
    const body = top
      ? `${top.title}${top.rationale ? ` — ${top.rationale}` : ""}`
      : briefing.headline;
    const tone =
      briefing.placement && briefing.placement.refreshed
        ? "success"
        : Array.isArray(briefing.blockers) && briefing.blockers.length
          ? "warning"
          : "info";
    return { tone, title: briefing.headline, body };
  }

  function mockupInsight(state) {
    const proactive = proactiveInsight(state && state.halData);
    if (proactive) {
      return { title: "HAL Insight", body: proactive.body || proactive.title };
    }
    const feed = (state && state.halWidgetFeed) || {};
    const pageId = state && state.pageId;
    const HW = halWidgetsApi();
    if (HW && pageId) {
      const first = HW.widgetsForPage(pageId, feed).find((item) => item.widget && item.widget.summary);
      if (first && first.widget.summary) {
        return { title: "HAL Insight", body: first.widget.summary };
      }
    }
    return { title: "HAL Insight", body: "HAL reads local SoftDent and QuickBooks imports only." };
  }

  function pageShell(state, opts) {
    const o = opts || {};
    if (o.compact) return "";
    const schema = typeof PageSchema !== "undefined" && state && state.pageId ? PageSchema.byId(state.pageId) : null;
    if (!schema) {
      return `<div class="ms-page-chrome ms-page-chrome--missing" role="alert"><p>Page unavailable.</p></div>`;
    }
    if (state.pageId === "hal") {
      return pageChromeHal(state, schema, o);
    }
    const HW = halWidgetsApi();
    const halReadinessStrip =
      HW && typeof HW.canvasPageStrip === "function" && state.halWidgetFeed
        ? HW.canvasPageStrip(state.pageId, state.halWidgetFeed)
        : "";
    return pageChrome(state, schema, mockupInsight(state), { halReadinessStrip, ...(o || {}) });
  }

  function pageContent(state, bodyHtml, chromeOpts) {
    const bodyClass = state && state.pageId === "hal" ? "ms-hal-page-body" : "ms-page-body";
    return `${pageShell(state, chromeOpts || {})}<div class="${bodyClass}">${bodyHtml || ""}</div>`;
  }

  function canvasShell(state, opts) {
    return pageShell(state, opts);
  }

  function sectionHead(title, subtitle) {
    return `<header class="widget-section-head">
      <h2>${esc(title)}</h2>
      ${subtitle ? `<p>${esc(subtitle)}</p>` : ""}
    </header>`;
  }

  let _halExportTimer = null;
  const EXPORT_WAIT_LIMIT_MS = 30000;

  function setHalReadiness(widgets, waitingExports) {
    const strip = document.getElementById("nr2-hal-readiness");
    if (!strip) return;

    clearTimeout(_halExportTimer);
    strip.style.background = "";
    strip.style.color = "";

    const hasWidgets = Array.isArray(widgets) && widgets.length > 0;

    if (!hasWidgets) {
      if (waitingExports > 0) {
        strip.textContent = `HAL · 0 ready · ${waitingExports} waiting on export`;
        _halExportTimer = setTimeout(() => {
          strip.textContent = "HAL · Data sync delayed — figures may be incomplete";
          strip.style.background = "#fff3cd";
          strip.style.color = "#664d03";
          window.dispatchEvent(new CustomEvent("nr2-hal-stalled", { detail: { waitingExports } }));
        }, EXPORT_WAIT_LIMIT_MS);
      } else {
        strip.textContent = "HAL · Syncing…";
      }
      return;
    }

    const readyCount = widgets.filter((w) => w.ready !== false).length;
    strip.textContent = `HAL · ${readyCount} ready · ${widgets.length - readyCount} pending`;
  }

  function refreshHalReadinessStrip(pageId, feed) {
    const HW = halWidgetsApi();
    if (!HW || !pageId) return;
    const readiness = HW.pageReadiness(pageId, feed || {});
    const widgets = readiness.items.map((item) => ({
      ready: item.widget && String(item.widget.status).toUpperCase() === "SUCCESS",
    }));
    setHalReadiness(widgets, readiness.empty);
  }

  if (typeof window !== "undefined") {
    window.addEventListener("nr2-hal-stalled", () => {
      document.querySelectorAll('[data-nr2-layout="moonshot-mockup-grid"], [data-nr2-layout="moonshot-grid"]').forEach((grid) => {
        grid.classList.add("nr2-data-stale");
      });
    });
  }

  return {
    NAV_ICONS,
    renderNavRail,
    pageChrome,
    pageChromeHal,
    pageContent,
    pageShell,
    canvasShell,
    sectionHead,
    renderHalInsight,
    renderAlertStrip,
    refreshHalReadinessStrip,
    setHalReadiness,
    mockupInsight,
  };
})();

if (typeof window !== "undefined") {
  window.MoonshotMockupChrome = MoonshotMockupChrome;
  window.PageChrome = MoonshotMockupChrome;
}
if (typeof globalThis !== "undefined") {
  globalThis.MoonshotMockupChrome = MoonshotMockupChrome;
  globalThis.PageChrome = MoonshotMockupChrome;
}
if (typeof module !== "undefined" && module.exports) {
  module.exports = MoonshotMockupChrome;
}
