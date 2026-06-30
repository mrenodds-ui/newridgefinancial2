/**
 * HAL pilot widgets
 *
 * Local zero-dependency adapters that prove the HAL event contract before we
 * bring in full ECharts/Tabulator. They intentionally expose the same event
 * concepts: chart click, row selection, and widget flash.
 */
const HalPilotWidgets = (function () {
  const LEGACY_WIDGET_SCHEMA = {
    mode: "preserve-existing-page-data",
    note: "Plain adapters enhance existing page HTML and data shapes; they do not replace source dashboard schemas.",
    eventContract: ["pageId", "widgetKey", "library", "eventType", "payload", "halAction", "flash"],
  };

  function esc(value) {
    return String(value == null ? "" : value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function fmt(value) {
    if (typeof value !== "number" || !Number.isFinite(value)) return String(value == null ? "—" : value);
    return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  }

  function emit(card, detail) {
    const bridge =
      typeof HalLiveWidgetBridge !== "undefined"
        ? HalLiveWidgetBridge
        : typeof window !== "undefined"
          ? window.HalLiveWidgetBridge
          : null;
    if (!bridge || typeof bridge.report !== "function") return;
    const event = bridge.report(detail);
    if (typeof bridge.flashElement === "function") bridge.flashElement(card, event.flash);
  }

  function financialOverviewChart(metrics) {
    const items = (metrics || [])
      .map((m) => ({
        label: m.label || "Metric",
        value: Number(String(m.value || "").replace(/[$,]/g, "")),
        display: m.value || "—",
        tone: m.tone || "gold",
        trend: m.trend || "—",
      }))
      .filter((m) => Number.isFinite(m.value));
    const max = Math.max(...items.map((item) => Math.abs(item.value)), 1);
    const bars = items
      .map((item) => {
        const pct = Math.max(6, Math.min(100, (Math.abs(item.value) / max) * 100));
        return `<button type="button" class="pv-hal-echart__bar pv-hal-echart__bar--${esc(item.tone)}" data-hal-chart-bar="${esc(item.label)}" data-hal-value="${esc(item.value)}" style="--pv-bar:${pct}%">
          <span class="pv-hal-echart__bar-fill"></span>
          <span class="pv-hal-echart__bar-label">${esc(item.label)}</span>
          <strong>${esc(item.display)}</strong>
          <em>${esc(item.trend)}</em>
        </button>`;
      })
      .join("");
    return `<div class="pv-hal-pilot pv-hal-echart" data-hal-pilot="financial-overview" role="group" aria-label="HAL interactive financial overview">
      <div class="pv-hal-pilot__toolbar"><span>ECharts pilot</span><em>click a bar → HAL report</em></div>
      <div class="pv-hal-echart__bars">${bars || `<p class="pv-muted">Awaiting import data for financial overview.</p>`}</div>
    </div>`;
  }

  function freshnessGrid(freshness, quality) {
    const rows = (freshness || []).map((f, index) => ({
      system: f.system || "Unknown",
      status: f.status || "Unknown",
      date: [f.date, f.time].filter(Boolean).join(" ") || "—",
      freq: f.freq || "—",
      quality: quality && quality.categories && quality.categories[index] ? `${quality.categories[index].score}/100` : "—",
      ok: f.status === "Synced" || f.status === "Imported",
    }));
    const body = rows
      .map(
        (row, index) => `<button type="button" class="pv-hal-tabulator__row" data-hal-grid-row="${index}" data-system="${esc(row.system)}" data-status="${esc(row.status)}">
          <span>${esc(row.system)}</span>
          <strong class="${row.ok ? "is-ok" : "is-warn"}">${esc(row.status)}</strong>
          <span>${esc(row.date)}</span>
          <span>${esc(row.freq)}</span>
          <em>${esc(row.quality)}</em>
        </button>`,
      )
      .join("");
    return `<div class="pv-hal-pilot pv-hal-tabulator" data-hal-pilot="freshness-grid" role="grid" aria-label="HAL interactive data freshness grid">
      <div class="pv-hal-pilot__toolbar"><span>Tabulator pilot</span><em>select row → HAL report</em></div>
      <div class="pv-hal-tabulator__head"><span>System</span><span>Status</span><span>Last sync</span><span>Cadence</span><span>Quality</span></div>
      <div class="pv-hal-tabulator__body">${body || `<p class="pv-muted">Awaiting source freshness data.</p>`}</div>
    </div>`;
  }

  function actionAttrs(detail) {
    const d = detail || {};
    return [
      `data-hal-action="1"`,
      `data-hal-page="${esc(d.pageId || "unknown")}"`,
      `data-hal-widget="${esc(d.widgetKey || "unknown")}"`,
      `data-hal-library="${esc(d.library || "plain widget")}"`,
      `data-hal-event="${esc(d.eventType || "interaction")}"`,
      `data-hal-payload-label="${esc(d.payloadLabel || "")}"`,
      `data-hal-payload-value="${esc(d.payloadValue || "")}"`,
      `data-hal-next="${esc(d.halAction || "Review selected widget item")}"`,
      `data-hal-flash="${esc(d.flash || "gold")}"`,
    ].join(" ");
  }

  function plainDataGrid(config) {
    const cfg = config || {};
    const columns = cfg.columns || [];
    const rows = cfg.rows || [];
    const rowKeys = cfg.rowKeys || [];
    const selectedKey = cfg.selectedKey != null ? String(cfg.selectedKey) : null;
    const head = columns.map((col) => `<span>${esc(col)}</span>`).join("");
    const body = rows
      .map((row, rowIndex) => {
        const cells = Array.isArray(row) ? row : columns.map((col) => row[col] || row[col.toLowerCase()] || "");
        const label = cells.filter(Boolean).slice(0, 2).join(" · ") || `row ${rowIndex + 1}`;
        const rowKey = rowKeys[rowIndex] != null ? String(rowKeys[rowIndex]) : "";
        const rowKeyAttr = rowKey ? ` data-row-key="${esc(rowKey)}"` : "";
        const isSelected = rowKey && selectedKey != null && rowKey === selectedKey;
        const selectedClass = isSelected ? " is-selected" : "";
        return `<button type="button" class="pv-hal-grid__row${selectedClass}"${rowKeyAttr} aria-selected="${isSelected ? "true" : "false"}" ${actionAttrs({
          pageId: cfg.pageId,
          widgetKey: cfg.widgetKey,
          library: cfg.library || "AG Grid plain",
          eventType: "rowSelected",
          payloadLabel: label,
          payloadValue: rowKey || rowIndex + 1,
          halAction: cfg.halAction || `Explain selected ${cfg.title || "grid"} row`,
          flash: cfg.flash || "cyan",
        })}>${cells.map((cell) => `<span>${esc(cell)}</span>`).join("")}</button>`;
      })
      .join("");
    return `<div class="pv-hal-pilot pv-hal-grid" data-hal-pilot="plain-grid" style="--pv-grid-cols: repeat(${Math.max(columns.length, 1)}, minmax(0, 1fr))">
      <div class="pv-hal-pilot__toolbar"><span>${esc(cfg.library || "AG Grid plain")}</span><em>${esc(cfg.hint || "select row -> HAL report")}</em></div>
      <div class="pv-hal-grid__head">${head}</div>
      <div class="pv-hal-grid__body">${body || `<p class="pv-muted">${esc(cfg.empty || "Awaiting rows.")}</p>`}</div>
    </div>`;
  }

  function plainKanban(config) {
    const cfg = config || {};
    const lanes = cfg.lanes || [];
    const laneHtml = lanes
      .map((lane) => {
        const cards = (lane.cards || [])
          .map((card, idx) => `<button type="button" class="pv-hal-kanban__card" ${actionAttrs({
            pageId: cfg.pageId,
            widgetKey: cfg.widgetKey,
            library: cfg.library || "SortableJS Kanban plain",
            eventType: "cardSelected",
            payloadLabel: `${lane.name}: ${card.title || card.id || idx + 1}`,
            payloadValue: card.id || idx + 1,
            halAction: card.halAction || cfg.halAction || "Review selected pipeline card",
            flash: lane.tone === "red" ? "red" : lane.tone === "ok" ? "cyan" : "gold",
          })}><strong>${esc(card.title || card.id || "Item")}</strong><span>${esc(card.detail || "")}</span><em>${esc(card.meta || "")}</em></button>`)
          .join("");
        return `<section class="pv-hal-kanban__lane pv-hal-kanban__lane--${esc(lane.tone || "muted")}">
          <div class="pv-hal-kanban__lane-head"><span>${esc(lane.name)}</span><strong>${(lane.cards || []).length}</strong></div>
          ${cards || `<p class="pv-muted">${esc(lane.empty || "No cards.")}</p>`}
        </section>`;
      })
      .join("");
    return `<div class="pv-hal-pilot pv-hal-kanban" data-hal-pilot="plain-kanban">
      <div class="pv-hal-pilot__toolbar"><span>${esc(cfg.library || "SortableJS Kanban plain")}</span><em>${esc(cfg.hint || "select card -> HAL report")}</em></div>
      <div class="pv-hal-kanban__lanes">${laneHtml}</div>
    </div>`;
  }

  function plainTimeline(config) {
    const cfg = config || {};
    const items = cfg.items || [];
    const html = items
      .map((item, idx) => `<button type="button" class="pv-hal-timeline__item pv-hal-timeline__item--${esc(item.tone || "muted")}" ${actionAttrs({
        pageId: cfg.pageId,
        widgetKey: cfg.widgetKey,
        library: cfg.library || "vis-timeline plain",
        eventType: "timelineItemSelected",
        payloadLabel: item.title || `item ${idx + 1}`,
        payloadValue: item.time || idx + 1,
        halAction: item.halAction || cfg.halAction || "Explain selected timeline item",
        flash: item.tone === "red" ? "red" : item.tone === "ok" ? "cyan" : "gold",
      })}><span>${esc(item.time || "")}</span><strong>${esc(item.title || "Milestone")}</strong><em>${esc(item.detail || "")}</em></button>`)
      .join("");
    return `<div class="pv-hal-pilot pv-hal-timeline" data-hal-pilot="plain-timeline">
      <div class="pv-hal-pilot__toolbar"><span>${esc(cfg.library || "vis-timeline plain")}</span><em>${esc(cfg.hint || "select milestone -> HAL report")}</em></div>
      <div class="pv-hal-timeline__rail">${html || `<p class="pv-muted">${esc(cfg.empty || "Awaiting timeline items.")}</p>`}</div>
    </div>`;
  }

  function plainEditor(config) {
    const cfg = config || {};
    const clauses = (cfg.clauses || []).map((clause) => `<span class="pv-hal-editor__clause">${esc(clause)}</span>`).join("");
    return `<div class="pv-hal-pilot pv-hal-editor" data-hal-pilot="plain-editor">
      <div class="pv-hal-pilot__toolbar"><span>${esc(cfg.library || "Tiptap plain")}</span><em>${esc(cfg.hint || "select clause -> HAL report")}</em></div>
      <button type="button" class="pv-hal-editor__surface" ${actionAttrs({
        pageId: cfg.pageId || "narratives",
        widgetKey: cfg.widgetKey || "narrativeWorkflow",
        library: cfg.library || "Tiptap plain",
        eventType: "editorFocused",
        payloadLabel: cfg.title || "Narrative editor",
        payloadValue: (cfg.clauses || []).length,
        halAction: cfg.halAction || "Review HAL narrative draft support",
        flash: "gold",
      })}>
        <strong>${esc(cfg.title || "HAL-assisted draft surface")}</strong>
        <p>${esc(cfg.body || "HAL can draft, annotate, and track human edits here.")}</p>
        <div>${clauses}</div>
      </button>
    </div>`;
  }

  function plainPdf(config) {
    const cfg = config || {};
    return `<div class="pv-hal-pilot pv-hal-pdf" data-hal-pilot="plain-pdf">
      <div class="pv-hal-pilot__toolbar"><span>${esc(cfg.library || "PDF.js plain")}</span><em>${esc(cfg.hint || "select region -> HAL report")}</em></div>
      <button type="button" class="pv-hal-pdf__page" ${actionAttrs({
        pageId: cfg.pageId || "documents",
        widgetKey: cfg.widgetKey || "documentPreview",
        library: cfg.library || "PDF.js plain",
        eventType: "regionSelected",
        payloadLabel: cfg.title || "document preview",
        payloadValue: cfg.value || "",
        halAction: cfg.halAction || "Explain selected document region",
        flash: "cyan",
      })}>
        <span>${esc(cfg.kicker || "Document preview")}</span>
        <strong>${esc(cfg.title || "Awaiting selected document")}</strong>
        <p>${esc(cfg.body || "HAL can highlight the exact line, amount, vendor, or date it references.")}</p>
        <i>${esc(cfg.footer || "Read-only preview")}</i>
      </button>
    </div>`;
  }

  function plainCommandPalette(config) {
    const cfg = config || {};
    const commands = (cfg.commands || []).map((cmd) => `<button type="button" ${actionAttrs({
      pageId: cfg.pageId || "global",
      widgetKey: cfg.widgetKey || "halCommandPalette",
      library: cfg.library || "kbar plain",
      eventType: "commandRun",
      payloadLabel: cmd,
      halAction: cmd,
      flash: "gold",
    })}>${esc(cmd)}</button>`).join("");
    const forceBtn = cfg.includeForce
      ? `<button type="button" class="pv-hal-command__force" data-hal-force-place="1" data-hal-page="${esc(cfg.pageId || "global")}">Force HAL to place data in widgets</button>`
      : "";
    return `<div class="pv-hal-pilot pv-hal-command" data-hal-pilot="plain-command">
      <div class="pv-hal-pilot__toolbar"><span>${esc(cfg.library || "kbar plain")}</span><em>run command -> HAL report</em></div>
      <div class="pv-hal-command__box"><span>Ask HAL or jump to action</span>${forceBtn}${commands}</div>
    </div>`;
  }

  function init(root) {
    if (!root) return;
    root.querySelectorAll("[data-hal-pilot-initialized]").forEach((el) => el.removeAttribute("data-hal-pilot-initialized"));

    root.querySelectorAll("[data-hal-action]:not([data-hal-pilot-initialized])").forEach((el) => {
      el.setAttribute("data-hal-pilot-initialized", "1");
      el.addEventListener("click", () => {
        const widget = el.closest("[data-hal-pilot]") || el;
        const card = el.closest("[data-hal-widget-key]") || widget;
        if (widget && widget.querySelectorAll) {
          widget.querySelectorAll(".is-selected").forEach((selected) => selected.classList.remove("is-selected"));
        }
        el.classList.add("is-selected");
        emit(card, {
          pageId: el.getAttribute("data-hal-page") || "unknown",
          widgetKey: el.getAttribute("data-hal-widget") || "unknown",
          library: el.getAttribute("data-hal-library") || "plain widget",
          eventType: el.getAttribute("data-hal-event") || "interaction",
          payload: {
            label: el.getAttribute("data-hal-payload-label") || "",
            value: el.getAttribute("data-hal-payload-value") || "",
          },
          halAction: el.getAttribute("data-hal-next") || "Review selected widget item",
          flash: el.getAttribute("data-hal-flash") || "gold",
        });
      });
    });

    root.querySelectorAll("[data-hal-force-place]:not([data-hal-force-bound])").forEach((btn) => {
      btn.setAttribute("data-hal-force-bound", "1");
      btn.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (typeof window !== "undefined" && typeof window.CustomEvent === "function") {
          window.dispatchEvent(
            new CustomEvent("hal-force-widget-placement", {
              detail: {
                pageId: btn.getAttribute("data-hal-page") || "financial",
                reason: "ui-force",
              },
            }),
          );
        }
      });
    });

    root.querySelectorAll("[data-hal-pilot='financial-overview']:not([data-hal-pilot-initialized])").forEach((widget) => {
      widget.setAttribute("data-hal-pilot-initialized", "1");
      widget.querySelectorAll("[data-hal-chart-bar]").forEach((bar) => {
        bar.addEventListener("click", () => {
          const card = bar.closest("[data-hal-widget-key]") || widget;
          const metric = bar.getAttribute("data-hal-chart-bar");
          const value = Number(bar.getAttribute("data-hal-value"));
          emit(card, {
            pageId: "financial",
            widgetKey: "practiceFinancialOverview",
            library: "ECharts pilot",
            eventType: "click",
            payload: { metric, value: Number.isFinite(value) ? value : null, display: fmt(value) },
            halAction: `Explain ${metric} in the financial overview`,
            flash: "gold",
          });
        });
      });
    });

    root.querySelectorAll("[data-hal-pilot='freshness-grid']:not([data-hal-pilot-initialized])").forEach((widget) => {
      widget.setAttribute("data-hal-pilot-initialized", "1");
      widget.querySelectorAll("[data-hal-grid-row]").forEach((row) => {
        row.addEventListener("click", () => {
          widget.querySelectorAll(".pv-hal-tabulator__row.is-selected").forEach((el) => el.classList.remove("is-selected"));
          row.classList.add("is-selected");
          const card = row.closest("[data-hal-widget-key]") || widget;
          emit(card, {
            pageId: "financial",
            widgetKey: "dataFreshnessQuality",
            library: "Tabulator pilot",
            eventType: "rowSelected",
            payload: {
              system: row.getAttribute("data-system"),
              status: row.getAttribute("data-status"),
            },
            halAction: "Open import diagnostics for the selected source",
            flash: row.getAttribute("data-status") === "Synced" || row.getAttribute("data-status") === "Imported" ? "cyan" : "red",
          });
        });
      });
    });
  }

  return {
    LEGACY_WIDGET_SCHEMA,
    financialOverviewChart,
    freshnessGrid,
    plainCommandPalette,
    plainDataGrid,
    plainEditor,
    plainKanban,
    plainPdf,
    plainTimeline,
    init,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalPilotWidgets;
}
if (typeof window !== "undefined") {
  window.HalPilotWidgets = HalPilotWidgets;
}
