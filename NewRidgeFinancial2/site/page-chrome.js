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
    const schema = schemaApi() && state && state.pageId ? schemaApi().byId(state.pageId) : null;
    if (schema && schema.insight) return schema.insight;
    const proactive = proactiveInsight(state && state.halData);
    if (proactive) return proactive;
    const feed = state && state.halWidgetFeed;
    const pageId = state && state.pageId;
    const HW = halWidgetsApi();
    if (HW && feed && pageId) {
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

  function canvasShell(state, opts) {
    const o = opts || {};
    const U = ui();
    const schema = schemaApi() && state && state.pageId ? schemaApi().byId(state.pageId) : null;
    if (!U || !schema) {
      return `<div class="pv-canvas-shell pv-canvas-shell--missing" role="alert">
        <p class="pv-canvas-shell__error">Page schema unavailable for <strong>${esc(state && state.pageId)}</strong>. Reload the desktop app.</p>
      </div>`;
    }
    const insight = resolveInsight(state);
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
    return U.CanvasShell({
      hero,
      toolbar,
      insight: insight ? U.PageInsight(insight) : "",
      strip: "",
      commands: halCommandSurface(state.pageId, schema.title, { registry: state.halData && state.halData.registry }),
    });
  }

  function pageContent(state, bodyHtml, chromeOpts) {
    return `${canvasShell(state, chromeOpts || {})}<div class="pv-canvas-body">${bodyHtml || ""}</div>`;
  }

  function sectionHead(title, subtitle) {
    return `<header class="pv-section-head">
      <h2 class="pv-section-head__title">${esc(title)}</h2>
      ${subtitle ? `<p class="pv-section-head__subtitle">${esc(subtitle)}</p>` : ""}
    </header>`;
  }

  return {
    canvasShell,
    pageContent,
    halStrip,
    halCommandSurface,
    proactiveInsight,
    resolveInsight,
    sectionHead,
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
