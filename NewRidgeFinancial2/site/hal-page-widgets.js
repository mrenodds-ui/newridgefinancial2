/**
 * HAL page widget bridge — wires HAL's widget feed into every staff page card.
 */
const HalPageWidgets = (function () {
  function esc(value) {
    return String(value == null ? "" : value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function widgetNavMap() {
    if (typeof HalSkills !== "undefined" && HalSkills.WIDGET_NAV) return HalSkills.WIDGET_NAV;
    return {};
  }

  function widgetFromFeed(feed, widgetKey) {
    if (!feed || !widgetKey) return null;
    return (
      (feed.widgets && feed.widgets[widgetKey]) ||
      (feed.officeWidgets && feed.officeWidgets[widgetKey]) ||
      null
    );
  }

  function statusTone(status) {
    const s = String(status || "").toUpperCase();
    if (s === "SUCCESS") return "ok";
    if (s === "DEGRADED") return "warn";
    return "off";
  }

  function statusLabel(status) {
    const s = String(status || "").toUpperCase();
    if (s === "SUCCESS") return "Ready";
    if (s === "DEGRADED") return "Partial data";
    return "No data yet";
  }

  function formatMetrics(widget) {
    if (!widget || !widget.metrics) return "";
    if (typeof HalSkills !== "undefined" && HalSkills.formatWidgetMetrics) {
      return HalSkills.formatWidgetMetrics(widget);
    }
    return Object.entries(widget.metrics)
      .filter(([, v]) => v !== null && v !== undefined && v !== "" && v !== "—")
      .slice(0, 3)
      .map(([k, v]) => `${k}: ${v}`)
      .join(" · ");
  }

  function halBadge(widgetKey, widget) {
    const status = widget ? widget.status : "FAILED";
    const tone = statusTone(status);
    const label = statusLabel(status);
    const mark = typeof AppIcons !== "undefined" ? AppIcons.widget(widgetKey) : "";
    return `<span class="pv-hal-widget__badge pv-hal-widget__badge--${tone}" title="HAL widget ${esc(widgetKey)}">${mark}<span class="pv-hal-widget__badge-copy">HAL · ${esc(label)}</span></span>`;
  }

  function widgetRequirementText(widget) {
    const key = widget && widget.key;
    const map =
      (typeof HalSkills !== "undefined" && HalSkills.WIDGET_FILL_REQUIREMENTS) ||
      (typeof window !== "undefined" && window.HalSkills && window.HalSkills.WIDGET_FILL_REQUIREMENTS) ||
      null;
    const reqs = key && map ? map[key] : null;
    if (Array.isArray(reqs) && reqs.length) return reqs.join("; ");
    return widget && widget.summary ? widget.summary : "";
  }

  function canConfigureWidget(widget) {
    if (!widget) return false;
    const status = String(widget.status || "").toUpperCase();
    if (status !== "FAILED") return false;
    const text = `${widget.summary || ""} ${formatMetrics(widget)}`.toLowerCase();
    return text.includes("not configured");
  }

  function halNote(widget) {
    if (!widget) {
      return `<p class="pv-hal-widget__note pv-hal-widget__note--off">No data yet — HAL fills this widget automatically once the source export is added. It is not broken.</p>`;
    }
    const status = String(widget.status || "FAILED").toUpperCase();
    const metrics = formatMetrics(widget);
    const needs = widgetRequirementText(widget);
    if (status === "SUCCESS") {
      const parts = [widget.summary, metrics].filter(Boolean);
      return parts.length ? `<p class="pv-hal-widget__note">${esc(parts.join(" · "))}</p>` : "";
    }
    const baseParts = [metrics].filter(Boolean);
    const base = baseParts.length ? `<p class="pv-hal-widget__note">${esc(baseParts.join(" · "))}</p>` : "";
    if (status === "DEGRADED") {
      const needsLine = needs ? ` To complete it, add: ${esc(needs)}.` : "";
      return `${base}<p class="pv-hal-widget__note pv-hal-widget__note--warn">Partial data — this widget is working and showing what the import currently contains. Some values are waiting on a fuller export.${needsLine}</p>`;
    }
    const needsLine = needs ? ` Needs: ${esc(needs)}.` : "";
    const configure = canConfigureWidget(widget)
      ? ` <button type="button" class="pv-hal-widget__configure" data-hal-configure-export="${esc(widget.key)}">Configure export</button>`
      : "";
    return `<p class="pv-hal-widget__note pv-hal-widget__note--off">No data yet — HAL fills this automatically once the required export is added. It is not broken.${needsLine}${configure}</p>`;
  }

  function widgetsForPage(pageId, feed) {
    const nav = widgetNavMap();
    const items = Object.keys(nav)
      .filter((key) => nav[key] === pageId)
      .map((key) => ({ key, widget: widgetFromFeed(feed, key) }));
    if (pageId === "office-manager" && feed && feed.officeWidgets) {
      Object.keys(feed.officeWidgets).forEach((key) => {
        if (!items.some((item) => item.key === key)) {
          items.push({ key, widget: feed.officeWidgets[key] });
        }
      });
    }
    if (pageId === "taxes") {
      ["quickbooksProfitLossDetail", "ebitdaNormalization"].forEach((key) => {
        if (!items.some((item) => item.key === key)) {
          items.push({ key, widget: widgetFromFeed(feed, key) });
        }
      });
    }
    return items;
  }

  function pageReadiness(pageId, feed) {
    const items = widgetsForPage(pageId, feed);
    let ready = 0;
    let partial = 0;
    let empty = 0;
    items.forEach((item) => {
      const status = item.widget ? String(item.widget.status).toUpperCase() : "FAILED";
      if (status === "SUCCESS") ready += 1;
      else if (status === "DEGRADED") partial += 1;
      else empty += 1;
    });
    return { ready, partial, empty, total: items.length, items };
  }

  function pageStrip(pageId, feed) {
    const { ready, partial, empty, total } = pageReadiness(pageId, feed);
    if (!total) return "";
    const tone = ready === total ? "ok" : ready > 0 || partial > 0 ? "warn" : "off";
    const parts = [`${ready} ready`];
    if (partial) parts.push(`${partial} partial`);
    if (empty) parts.push(`${empty} waiting on export`);
    return `<div class="pv-hal-strip pv-hal-strip--${tone}" role="status"><span class="pv-hal-strip__mark">${typeof AppIcons !== "undefined" ? AppIcons.hal() : ""}</span><strong>HAL</strong><span>${esc(parts.join(" · "))} on this page</span><button type="button" class="pv-hal-strip__force" data-hal-force-place="1" data-hal-page="${esc(pageId)}">Force HAL placement</button></div>`;
  }

  function canvasPageStrip(pageId, feed) {
    const { ready, partial, empty, total } = pageReadiness(pageId, feed);
    if (!total) return "";
    const mark = typeof AppIcons !== "undefined" ? AppIcons.hal() : "";
    const parts = [`${ready} ready`];
    if (partial) parts.push(`${partial} partial`);
    if (empty) parts.push(`${empty} waiting on export`);
    const tone = ready === total ? "ok" : ready > 0 || partial > 0 ? "warn" : "off";
    return `<div class="pv-canvas-hal-strip pv-hal-strip--${tone}" role="status"><span class="pv-hal-strip__mark">${mark}</span><strong>HAL</strong><span>${esc(parts.join(" · "))} on this page</span></div>`;
  }

  function panelChrome(widgetKey, title, feed) {
    const widget = widgetFromFeed(feed, widgetKey);
    const tone = statusTone(widget ? widget.status : "FAILED");
    const badge = widgetKey ? halBadge(widgetKey, widget) : "";
    const note = widgetKey ? halNote(widget) : "";
    const cmdLabel = (widget && widget.title) || title || widgetKey;
    const halCmd = widgetKey && cmdLabel ? `Explain ${cmdLabel}` : "";
    const cmdAttr = halCmd ? ` data-hal-cmd="${esc(halCmd)}"` : "";
    const attrs = widgetKey ? ` data-hal-widget-key="${esc(widgetKey)}"${cmdAttr}` : "";
    const icon =
      widgetKey && typeof AppIcons !== "undefined"
        ? `<span class="pv-canvas-panel__ico">${AppIcons.widget(widgetKey)}</span>`
        : "";
    return {
      badge,
      note,
      attrs,
      toneClass: widgetKey ? ` pv-hal-widget pv-hal-widget--${tone}` : "",
      icon,
    };
  }

  return {
    widgetFromFeed,
    widgetsForPage,
    pageReadiness,
    pageStrip,
    canvasPageStrip,
    panelChrome,
    halBadge,
    halNote,
    statusLabel,
    statusTone,
    formatMetrics,
    canConfigureWidget,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalPageWidgets;
}
if (typeof globalThis !== "undefined") {
  globalThis.HalPageWidgets = HalPageWidgets;
}
if (typeof window !== "undefined") {
  window.HalPageWidgets = HalPageWidgets;
}
