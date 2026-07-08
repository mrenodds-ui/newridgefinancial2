/**
 * Canvas-aligned page chrome — shared by staff pages and HAL Command Center.
 * Reads metadata from PageSchema (single source of truth).
 */
const PageChrome = (function () {
  function esc(value) {
    return String(value == null ? "" : value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function ui() {
    if (typeof UI !== "undefined") return UI;
    if (typeof globalThis !== "undefined" && globalThis.UI) return globalThis.UI;
    return null;
  }

  function schemaApi() {
    if (typeof PageSchema !== "undefined") return PageSchema;
    if (typeof globalThis !== "undefined" && globalThis.PageSchema) return globalThis.PageSchema;
    return null;
  }

  function halWidgetsApi() {
    if (typeof HalPageWidgets !== "undefined") return HalPageWidgets;
    if (typeof globalThis !== "undefined" && globalThis.HalPageWidgets) return globalThis.HalPageWidgets;
    return null;
  }

  function halStrip(pageId, feed) {
    const HW = halWidgetsApi();
    if (!HW || typeof HW.pageStrip !== "function") return "";
    return HW.pageStrip(pageId, feed);
  }

  function canvasHalStrip(pageId, feed) {
    const HW = halWidgetsApi();
    if (HW && typeof HW.canvasPageStrip === "function") {
      return HW.canvasPageStrip(pageId, feed);
    }
    return halStrip(pageId, feed);
  }

  function halCommandSurface(pageId, title, feed) {
    const U = ui();
    if (!U || typeof U.CanvasCommandStrip !== "function") return "";
    const schema = schemaApi();
    const pageCmds = schema && schema.commandsFor ? schema.commandsFor(pageId) : [];
    const commands = pageCmds.slice(0, 3);
    if (!commands.length) return "";
    return `<div class="pv-hal-command-wrap">${U.CanvasCommandStrip({ pageId, commands })}</div>`;
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

  function resolveInsight(state) {
    const proactive = proactiveInsight(state && state.halData);
    if (proactive) return proactive;
    const feed = (state && state.halWidgetFeed) || {};
    const pageId = state && state.pageId;
    const HW = halWidgetsApi();
    if (HW && pageId) {
      const readiness = HW.pageReadiness(pageId, feed);
      if (readiness.total) {
        const tone = readiness.empty === readiness.total ? "warning" : readiness.partial > 0 ? "info" : "success";
        const parts = [`${readiness.ready} ready`];
        if (readiness.partial) parts.push(`${readiness.partial} partial`);
        if (readiness.empty) parts.push(`${readiness.empty} waiting on export`);
        const first = HW.widgetsForPage(pageId, feed).find((item) => item.widget && item.widget.summary);
        return {
          tone,
          title: `HAL · ${parts.join(" · ")} on this page`,
          body: (first && first.widget.summary) || "HAL reads local SoftDent and QuickBooks imports only.",
        };
      }
    }
    return null;
  }

  function isMockupLayout(state) {
    return schemaApi() && schemaApi().LAYOUT_EPOCH === "moonshot-mockup";
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

  function mockupShell(state, opts) {
    const o = opts || {};
    if (o.compact) return "";
    const schema = schemaApi() && state && state.pageId ? schemaApi().byId(state.pageId) : null;
    const MC =
      (typeof MoonshotMockupChrome !== "undefined" && MoonshotMockupChrome) ||
      (typeof globalThis !== "undefined" && globalThis.MoonshotMockupChrome) ||
      null;
    if (!schema || !MC) {
      return `<div class="ms-page-chrome ms-page-chrome--missing" role="alert"><p>Page schema unavailable.</p></div>`;
    }
    if (state.pageId === "hal" && typeof MC.pageChromeHal === "function") {
      return MC.pageChromeHal(state, schema, o);
    }
    const HW =
      (typeof HalPageWidgets !== "undefined" && HalPageWidgets) ||
      (typeof globalThis !== "undefined" && globalThis.HalPageWidgets) ||
      null;
    const halReadinessStrip =
      HW && typeof HW.canvasPageStrip === "function" && state.halWidgetFeed
        ? HW.canvasPageStrip(state.pageId, state.halWidgetFeed)
        : "";
    return MC.pageChrome(state, schema, mockupInsight(state), { halReadinessStrip, ...(o || {}) });
  }

  function canvasShell(state, opts) {
    if (isMockupLayout(state)) return mockupShell(state, opts);
    const o = opts || {};
    const U = ui();
    const schema = schemaApi() && state && state.pageId ? schemaApi().byId(state.pageId) : null;
    if (!U || !schema) {
      return `<div class="pv-canvas-shell pv-canvas-shell--missing" role="alert">
        <p class="pv-canvas-shell__error">Page schema unavailable for <strong>${esc(state && state.pageId)}</strong>. Run StartProgram.bat and reload http://127.0.0.1:8765/.</p>
      </div>`;
    }
    const insight = o.compact ? null : resolveInsight(state);
    const practice = schemaApi() && schemaApi().PRACTICE ? schemaApi().PRACTICE : null;
    const periodLabel = o.periodLabel
      ? `<span class="pv-hero-period">${esc(o.periodLabel)}</span>${o.reportRange ? `<span class="pv-hero-range">${esc(o.reportRange)}</span>` : ""}`
      : practice && practice.period
        ? `<span class="pv-hero-period">${esc(practice.period)}</span>${practice.reportRange ? `<span class="pv-hero-range">${esc(practice.reportRange)}</span>` : ""}`
        : "";
    const hero = U.PageHero({
      label: schema.label,
      title: schema.title,
      subtitle: schema.subtitle,
      accent: schema.accent,
      periodLabel,
    });
    const printAction = U.Button
      ? U.Button({
          label: "Print",
          icon: typeof AppIcons !== "undefined" ? AppIcons.ui("print") : "",
          variant: "toolbar",
          attrs: { "data-nr2-print": "page", type: "button", "aria-label": "Print this page" },
        })
      : "";
    const exportAction = U.Button
      ? U.Button({
          label: "Export",
          icon: typeof AppIcons !== "undefined" ? AppIcons.ui("export") : "",
          variant: "toolbar",
          attrs: { "data-nr2-export": "page", type: "button", "aria-label": "Export this page as CSV" },
        })
      : "";
    const toolbarActions = o.toolbarActions || `${printAction}${exportAction}`;
    const toolbar = U.PageToolbar({
      filters: schema.filters || [],
      actions: toolbarActions,
    });
    const feed = (state && state.halWidgetFeed) || null;
    const freshnessStrip = (o && o.importFreshnessHtml) || "";
    const halStripHtml =
      state && state.pageId && state.pageId !== "hal" ? canvasHalStrip(state.pageId, feed) : "";
    const combinedStrip = `${freshnessStrip}${halStripHtml}`;
    return U.CanvasShell({
      hero,
      toolbar,
      insight: insight ? U.PageInsight(insight) : "",
      strip: combinedStrip,
      commands: o.compact ? "" : halCommandSurface(state.pageId, schema.title, { registry: state.halData && state.halData.registry }),
    });
  }

  function pageContent(state, bodyHtml, chromeOpts) {
    const bodyClass = state && state.pageId === "hal" ? "ms-hal-page-body" : "ms-page-body";
    return `${mockupShell(state, chromeOpts || {})}<div class="${bodyClass}">${bodyHtml || ""}</div>`;
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
    canvasShell,
    pageContent,
    halStrip,
    halCommandSurface,
    proactiveInsight,
    resolveInsight,
    sectionHead,
    setHalReadiness,
    refreshHalReadinessStrip,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = PageChrome;
}
if (typeof globalThis !== "undefined") {
  globalThis.PageChrome = PageChrome;
}
if (typeof window !== "undefined") {
  window.PageChrome = PageChrome;
}
