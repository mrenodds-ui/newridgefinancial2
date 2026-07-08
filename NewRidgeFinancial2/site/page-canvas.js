/**
 * Staff page bodies — Moonshot high-tech canvas layouts (PageCanvas + PageCanvasData).
 * Widget keys and HAL badges come from PageSchema + halWidgetFeed.
 */
const PageCanvas = (function () {
  let activeFeed = null;
  let activeSnapshot = null;
  let activePageId = null;

  function mockupLayout() {
    return typeof PageSchema !== "undefined" && PageSchema.LAYOUT_EPOCH === "moonshot-mockup";
  }

  function stackOpen(extraClass) {
    return `<div class="widget-grid${extraClass ? " " + esc(extraClass) : ""}" data-nr2-layout="moonshot-mockup-grid">`;
  }

  function metricRowOpen() {
    return "";
  }

  function metricRowClose() {
    return "";
  }

  function splitRow(left, right) {
    return `${gridCol(6, left)}${gridCol(6, right)}`;
  }

  function esc(v) {
    if (typeof UI !== "undefined" && UI.esc) return UI.esc(v);
    return String(v == null ? "" : v)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function sectionHead(title, subtitle) {
    const PC = typeof PageChrome !== "undefined" ? PageChrome : null;
    return PC ? PC.sectionHead(title, subtitle) : "";
  }

  function pageMeta(pageId) {
    return typeof PageSchema !== "undefined" && PageSchema.byId ? PageSchema.byId(pageId) : null;
  }

  function wTitle(pageId, i) {
    const p = pageMeta(pageId);
    return (p && p.widgets && p.widgets[i] && p.widgets[i].title) || "";
  }

  function wKey(pageId, i) {
    const p = pageMeta(pageId);
    return (p && p.widgets && p.widgets[i] && p.widgets[i].key) || "";
  }

  function halWidgetsApi() {
    if (typeof HalPageWidgets !== "undefined") return HalPageWidgets;
    if (typeof globalThis !== "undefined" && globalThis.HalPageWidgets) return globalThis.HalPageWidgets;
    return null;
  }

  function svgSparkline(values, color) {
    if (!values || !values.length) return "";
    const w = 120;
    const h = 36;
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    const pts = values
      .map((v, i) => `${((i / (values.length - 1)) * w).toFixed(1)},${(h - ((v - min) / range) * (h - 4) - 2).toFixed(1)}`)
      .join(" ");
    return `<svg class="sparkline-svg" viewBox="0 0 ${w} ${h}" aria-hidden="true"><polyline fill="none" stroke="${color || "#d6b15e"}" stroke-width="2" points="${pts}"/></svg>`;
  }

  function finTrendChart(production, average, maxVal) {
    const w = 460;
    const h = 150;
    const pad = { t: 8, r: 8, b: 6, l: 6 };
    const max = maxVal || Math.max(...production, ...(average || production));
    const min = 0;
    const range = max - min || 1;
    const innerW = w - pad.l - pad.r;
    const innerH = h - pad.t - pad.b;
    const xAt = (i, len) => pad.l + (i / (len - 1)) * innerW;
    const yAt = (v) => pad.t + innerH - ((v - min) / range) * innerH;
    const grid = [0, 1, 2, 3, 4, 5, 6]
      .map((t) => {
        const y = pad.t + (innerH * t) / 6;
        return `<line x1="${pad.l}" y1="${y.toFixed(1)}" x2="${w - pad.r}" y2="${y.toFixed(1)}" class="chart-grid-line"/>`;
      })
      .join("");
    const path = (vals) => vals.map((v, i) => `${i ? "L" : "M"}${xAt(i, vals.length).toFixed(1)},${yAt(v).toFixed(1)}`).join(" ");
    const dots = production
      .map((v, i) => `<circle cx="${xAt(i, production.length).toFixed(1)}" cy="${yAt(v).toFixed(1)}" r="2.6" fill="#d6b15e"/>`)
      .join("");
    const avgLine = average ? `<path d="${path(average)}" fill="none" stroke="#64748b" stroke-width="2" stroke-dasharray="5 4"/>` : "";
    return `<svg class="trend-chart-svg" viewBox="0 0 ${w} ${h}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Trend chart">${grid}${avgLine}<path d="${path(production)}" fill="none" stroke="#d6b15e" stroke-width="2.5"/>${dots}</svg>`;
  }

  function dualLineChart(labels, series, height) {
    const h = height || 120;
    const w = 460;
    const pad = { t: 8, r: 8, b: 22, l: 8 };
    const normalized = (series || []).map((s) => {
      if (!s) return s;
      if (Array.isArray(s.data)) return s;
      if (Array.isArray(s.values)) return Object.assign({}, s, { data: s.values });
      return s;
    });
    const all = normalized.flatMap((s) => (s && Array.isArray(s.data) ? s.data : []));
    const max = Math.max(...all, 1) * 1.05;
    const min = 0;
    const range = max - min || 1;
    const innerW = w - pad.l - pad.r;
    const innerH = h - pad.t - pad.b;
    const xAt = (i, len) => pad.l + (i / Math.max(len - 1, 1)) * innerW;
    const yAt = (v) => pad.t + innerH - ((v - min) / range) * innerH;
    const colors = { info: "#60a5fa", success: "#78a86b", warning: "#fb923c" };
    const paths = normalized
      .filter((s) => s && Array.isArray(s.data) && s.data.length)
      .map((s) => {
        const stroke = colors[s.tone] || "#d6b15e";
        const d = s.data.map((v, i) => `${i ? "L" : "M"}${xAt(i, s.data.length).toFixed(1)},${yAt(v).toFixed(1)}`).join(" ");
        return `<path d="${d}" fill="none" stroke="${stroke}" stroke-width="2.5"/>`;
      })
      .join("");
    const xLabels = (labels || [])
      .map((label, i) => `<text x="${xAt(i, labels.length)}" y="${h - 4}" class="chart-axis-label" text-anchor="middle">${esc(label)}</text>`)
      .join("");
    return `<svg class="trend-chart-svg" viewBox="0 0 ${w} ${h}" preserveAspectRatio="xMidYMid meet" role="img">${paths}${xLabels}</svg>`;
  }

  function vBarChart(labels, values, color) {
    const max = Math.max(...values, 1);
    return `<div class="bar-chart">${values
      .map(
        (v, i) =>
          `<div class="bar-chart-column"><span class="bar-chart-fill" style="height:${Math.max(8, (v / max) * 100)}%;background:${color || "#d6b15e"}"></span><span class="bar-chart-label">${esc(labels[i] || "")}</span></div>`,
      )
      .join("")}</div>`;
  }

  function hBarChart(items, valueKey, labelKey, pctKey) {
    const max = Math.max(...items.map((i) => i[pctKey] || 0), 1);
    return `<div class="provider-list">${items
      .map((item) => {
        const pct = item[pctKey] || 0;
        return `<div class="provider-item"><span class="provider-name">${esc(item[labelKey])}</span><div class="provider-bar-bg"><span class="provider-bar-fill" style="width:${(pct / max) * 100}%"></span></div><span class="provider-amount">${esc(item[valueKey])}</span><span class="provider-pct">${pct}%</span></div>`;
      })
      .join("")}</div>`;
  }

  function chartContainer(inner, tall) {
    return `<div class="chart-container${tall ? " tall" : ""}">${inner}</div>`;
  }

  function conicDonut(slices, center, size) {
    const sz = size || 104;
    let acc = 0;
    const stops = slices.map((s) => {
      const start = acc;
      acc += s.pct;
      return `${s.color} ${start}% ${acc}%`;
    });
    const legend = slices
      .map(
        (s) =>
          `<div class="legend-row"><span class="legend-dot" style="background:${s.color}"></span><span>${esc(s.label)}</span><strong>${s.pct}%</strong></div>`,
      )
      .join("");
    return `<div class="donut-wrap"><div class="donut-chart" style="width:${sz}px;height:${sz}px;background:conic-gradient(${stops.join(", ")})"><div class="donut-hole">${center || ""}</div></div><div class="chart-legend">${legend}</div></div>`;
  }

  function barSparkline(values, tone) {
    if (!values || !values.length) return "";
    const max = Math.max(...values);
    const min = Math.min(...values);
    const range = max - min || 1;
    const bars = values
      .map((v, i) => {
        const h = Math.max(3, ((v - min) / range) * 20);
        const opacity = i === values.length - 1 ? 1 : 0.35 + (i / values.length) * 0.45;
        return `<span class="kpi-spark-bar" style="height:${h.toFixed(1)}px;opacity:${opacity.toFixed(2)}"></span>`;
      })
      .join("");
    const toneClass = tone ? ` kpi-spark-bars--${tone}` : "";
    return `<div class="kpi-spark-bars${toneClass}">${bars}</div>`;
  }

  function widgetHeaderIcon(widgetKey) {
    if (!widgetKey || typeof AppIcons === "undefined") return "";
    return `<span class="ms-panel-ico">${AppIcons.widget(widgetKey)}</span>`;
  }

  function canvasMetricTile(kpi, colSpan) {
    const widgetKey = kpi.widgetKey || "";
    const HW = halWidgetsApi();
    const widget = HW && widgetKey && activeFeed ? HW.widgetFromFeed(activeFeed, widgetKey) : null;
    const cmdLabel = (widget && widget.title) || kpi.label || widgetKey;
    const halCmd = widgetKey && cmdLabel ? ` data-hal-cmd="Explain ${esc(cmdLabel)}"` : "";
    const halTone = widgetKey && HW ? ` hal-widget-status hal-widget-status--${HW.statusTone(widget ? widget.status : "FAILED")}` : "";
    const attrs = widgetKey ? ` data-hal-widget-key="${esc(widgetKey)}"${halCmd} role="button" tabindex="0"` : "";
    const trend = kpi.hint ? `<div class="trend-indicator"><span>↑</span> ${esc(kpi.hint)}</div>` : "";
    const sparkHtml = kpi.spark && kpi.spark.length ? barSparkline(kpi.spark, kpi.tone) : "";
    const col = colSpan || 3;
    return `<div class="widget-card col-${col} kpi-large kpi-glow-card${halTone}"${attrs}>
        <div class="widget-header"><span class="widget-title">${widgetHeaderIcon(widgetKey)}${esc(String(kpi.label || ""))}</span><div class="widget-menu" aria-hidden="true">⋮</div></div>
        <div class="kpi-value">${esc(kpi.value)}</div>
        ${sparkHtml}
        ${trend}
      </div>`;
  }

  function heroKpiRow(kpis, max = 4) {
    const list = (kpis || []).slice(0, max);
    if (!list.length) return "";
    const span = list.length >= 4 ? 3 : list.length === 3 ? 4 : list.length === 2 ? 6 : 12;
    return list.map((kpi) => canvasMetricTile(kpi, span)).join("");
  }

  function dashboardHost(inner) {
    return `<div class="dashboard-grid-host col-12">${inner}</div>`;
  }

  function canvasKpiTile(kpi) {
    const widgetKey = kpi.widgetKey || "";
    const cmdLabel = kpi.label || widgetKey;
    const halCmd = widgetKey ? ` data-hal-widget-key="${esc(widgetKey)}" data-hal-cmd="Explain ${esc(cmdLabel)}" role="button" tabindex="0"` : "";
    const deltaClass = kpi.tone === "success" ? "kpi-positive" : kpi.tone === "warning" ? "kpi-negative" : "";
    const arrow = kpi.tone === "warning" ? "↓" : "↑";
    const delta = kpi.hint ? `<div class="kpi-delta ${deltaClass}"><span>${arrow}</span> ${esc(kpi.hint)}</div>` : "";
    const sparkHtml = kpi.spark && kpi.spark.length ? barSparkline(kpi.spark, kpi.tone) : "";
    return `<div class="kpi-tile"${halCmd}><div class="kpi-label">${esc(kpi.label)}</div><div class="kpi-value">${esc(kpi.value)}</div>${sparkHtml}${delta}</div>`;
  }

  function canvasKpiGrid(kpis) {
    if (!kpis || !kpis.length) return "";
    return `<div class="kpi-grid col-12">${kpis.map(canvasKpiTile).join("")}</div>`;
  }

  function canvasStatsBar(kpis) {
    const icons = ["👥", "💰", "⏱️", "🦷", "⚠️"];
    if (!kpis || !kpis.length) return "";
    return `<div class="stats-bar">${kpis
      .slice(0, 5)
      .map(
        (kpi, i) =>
          `<div class="stat-item"${kpi.widgetKey ? ` data-hal-widget-key="${esc(kpi.widgetKey)}"` : ""}><div class="stat-icon">${icons[i] || "◈"}</div><div class="stat-info"><h4>${esc(kpi.value)}</h4><span>${esc(kpi.label)}</span></div></div>`,
      )
      .join("")}</div>`;
  }

  function canvasCompareStrip(items) {
    return `<div class="compare-strip">${items
      .map(
        (item) => `<div class="compare-item">
        <span class="compare-label">${esc(item.label)}</span>
        <strong class="compare-value">${esc(item.value)}</strong>
        <span class="compare-delta compare-delta--${esc(item.tone || "neutral")}">${esc(item.delta)}</span>
      </div>`,
      )
      .join("")}</div>`;
  }

  function canvasPanel({ title, caption, accent, widgetKey, body, dataOnly, colSpan }) {
    const HW = halWidgetsApi();
    const chrome =
      HW && widgetKey
        ? HW.panelChrome(widgetKey, title, activeFeed, { dataOnly: dataOnly !== false })
        : {
            badge: "",
            note: "",
            attrs: widgetKey ? ` data-hal-widget-key="${esc(widgetKey)}"` : "",
            toneClass: "",
            icon: "",
          };
    const col = colSpan ? ` col-${colSpan}` : "";
    const accentClass = accent === "orange" ? " widget-accent-orange" : "";
    return `<section class="widget-card widget-glow-border widget-mount-glow${col}${accentClass}${(chrome.toneClass || "").trim() ? " " + esc(chrome.toneClass.trim()) : ""}"${chrome.attrs}>
        <div class="widget-header"><span class="widget-title">${chrome.icon || widgetHeaderIcon(widgetKey)}${esc(title)}</span><div class="widget-menu" aria-hidden="true">⋮</div></div>
        <div class="widget-body">${body}${chrome.note || ""}</div>
        ${caption ? `<p class="widget-caption">${esc(caption)}</p>` : ""}
      </section>`;
  }

  function canvasStat(value, label, tone, widgetKey) {
    const toneClass = tone ? ` stat-box--${tone}` : "";
    const wk = widgetKey || "";
    const attrs = wk ? ` data-hal-widget-key="${esc(wk)}" data-hal-cmd="Explain ${esc(label)}" role="button" tabindex="0"` : "";
    return `<div class="stat-box${toneClass}"${attrs}><strong>${esc(value)}</strong><span>${esc(label)}</span></div>`;
  }

  function canvasStatGrid(stats) {
    return `<div class="stat-grid">${stats.map((s) => canvasStat(s.value, s.label, s.tone, s.widgetKey)).join("")}</div>`;
  }

  function canvasTable(headers, rows, striped) {
    const head = `<tr>${headers.map((h) => `<th>${esc(h)}</th>`).join("")}</tr>`;
    const body = rows
      .map((row) => `<tr>${row.map((cell) => `<td>${esc(cell)}</td>`).join("")}</tr>`)
      .join("");
    return `<div class="table-wrap"><table class="data-table${striped ? " data-table--striped" : ""}"><thead>${head}</thead><tbody>${body}</tbody></table></div>`;
  }

  function claimRiskClass(item, laneName) {
    if (item && typeof item === "object") {
      if (item.status === "Denied") return "risk-high";
      if (item.status === "Ready") return "risk-low";
      if (/matched/i.test(String(item.status || ""))) return "matched";
    }
    if (laneName === "Denied") return "risk-high";
    if (laneName === "Ready") return "risk-low";
    return "risk-medium";
  }

  function claimRiskLabel(risk) {
    if (risk === "risk-high") return "High Risk";
    if (risk === "risk-low") return "Low Risk";
    if (risk === "matched") return "Matched";
    return "Med Risk";
  }

  function renderClaimCard(item, widgetKey, pageId) {
    const wk = widgetKey || "smartClaimsAndReceivables";
    if (typeof item === "string") {
      return `<div class="claim-card risk-medium" role="button" tabindex="0" data-hal-action="1" data-hal-page="${esc(pageId)}" data-hal-widget="${esc(wk)}" data-hal-payload-label="${esc(item)}"><div class="claim-patient">${esc(item)}</div></div>`;
    }
    const risk = claimRiskClass(item, item.status);
    return `<div class="claim-card ${risk}" role="button" tabindex="0" data-hal-action="1" data-hal-page="${esc(pageId)}" data-hal-widget="${esc(wk)}" data-hal-payload-label="${esc(item.patient || item.id || "")}">
      <div class="claim-header"><span class="claim-id">${esc(item.id || "CLM")}</span><span class="risk-badge ${risk}">${esc(claimRiskLabel(risk))}</span></div>
      <div class="claim-patient">${esc(item.patient || "Unknown")}</div>
      <div class="claim-procedure">${esc(item.procedure || "—")}</div>
      <div class="claim-meta"><span class="claim-payer">${esc(item.payer || "—")}</span><span class="claim-amount">${fmtClaim(item.amount)}</span></div>
    </div>`;
  }

  function canvasKanbanLanes(lanes, widgetKey, options) {
    const pageId = activePageId || "ar";
    const claimsMode = (options && options.claims) || pageId === "claims";
    const laneHtml = lanes
      .map((lane) => {
        const cards = (lane.items || []).map((item) => renderClaimCard(item, widgetKey, pageId)).join("");
        return `<div class="kanban-column">
          <div class="column-header"><span>${esc(lane.lane)}</span><span class="column-count">${(lane.items || []).length}</span></div>
          <div class="column-content">${cards}</div>
        </div>`;
      })
      .join("");
    return `<div class="kanban-board claims-pipeline${claimsMode ? " kanban-board--claims" : ""}" data-hal-widget-key="${esc(widgetKey || "")}">${laneHtml}</div>`;
  }

  function canvasTimeline(items) {
    return `<div class="status-timeline">${items
      .map(
        (item) => `<div class="timeline-item${item.active ? " timeline-item--active" : ""}">
        <span class="timeline-time">${esc(item.time)}</span>
        <strong>${esc(item.title)}</strong>
        <em>${esc(item.detail)}</em>
      </div>`,
      )
      .join("")}</div>`;
  }

  function canvasDocPreview(title, pages) {
    return `<div class="doc-preview">
      <div class="doc-preview-cover">
        <strong>${esc(title)}</strong>
        <span>${esc(String(pages))} pages · PDF preview</span>
      </div>
    </div>`;
  }

  function canvasTextArea(value, rows, editable) {
    const disabled = editable ? "" : " disabled";
    const bodyAttr = editable ? ` data-narrative-body="1"` : "";
    return `<textarea class="composer-textarea" rows="${rows || 10}"${disabled}${bodyAttr}>${esc(value)}</textarea>`;
  }

  function canvasSearch(placeholder, widgetKey) {
    const wk = widgetKey || "documentLibrary";
    return `<div class="search-container" data-hal-widget-key="${esc(wk)}">
      <input class="search-box" type="search" placeholder="${esc(placeholder)}" data-hal-library-query="1" aria-label="Search library" />
      <button type="button" class="search-action" data-hal-library-search="1">Search with HAL</button>
    </div>`;
  }

  function canvasUsageBar(segments, labelLeft, labelRight) {
    const total = segments.reduce((sum, s) => sum + s.value, 0) || 100;
    const fills = segments
      .map((s) => {
        const color = s.color === "green" ? "var(--sage)" : s.color === "gray" ? "#64748b" : s.color || "#d6b15e";
        return `<span style="width:${(s.value / total) * 100}%;background:${color}"></span>`;
      })
      .join("");
    return `<div class="usage-bar">
      <div class="usage-bar-head"><span>${esc(labelLeft)}</span><span>${esc(labelRight)}</span></div>
      <div class="usage-bar-track">${fills}</div>
    </div>`;
  }

  function canvasEmpty(message) {
    return `<p class="widget-empty">${esc(message || "No data yet — HAL fills this when the source export is available.")}</p>`;
  }

  function canvasImportNotice(notice) {
    if (!notice) return "";
    const staleBadge = notice.stale
      ? `<p class="sync-stale-badge" role="status">${esc(notice.staleLabel || "Last-known data — sync stale")}</p>`
      : "";
    if (!notice.message) return staleBadge;
    const tone = notice.tone || "info";
    return `${staleBadge}<p class="ms-import-notice ms-import-notice--${esc(tone)}" role="status">${esc(notice.message)}</p>`;
  }

  function pageImportNotice(pageId) {
    const D = dataApi();
    if (!D) return null;
    const map = {
      financial: D.financialImportNotice,
      softdent: D.softdentImportNotice,
      quickbooks: D.quickbooksImportNotice,
      ar: D.arImportNotice,
      claims: D.claimsImportNotice,
      documents: D.documentsImportNotice,
      library: D.libraryImportNotice,
      "office-manager": D.officeManagerImportNotice,
      narratives: D.narrativesImportNotice,
      taxes: D.taxesImportNotice,
    };
    const fn = map[pageId];
    return fn ? fn() : null;
  }

  function dataApi() {
    return typeof PageCanvasData !== "undefined" ? PageCanvasData : null;
  }

  function canvasImportHealthGrid() {
    const D = dataApi();
    const cards = D ? D.importHealthCards() : [];
    if (!cards.length) {
      return `<div class="operatory-grid">${canvasEmpty("SoftDent import status will appear here after the dashboard export loads.")}</div>`;
    }
    return `<div class="operatory-grid">${cards
      .map(
        (o) => `<article class="operatory-card operatory-card--${esc(o.tone)}">
        <header><span>${esc(o.patient)}</span><em>${esc(o.op)}</em></header>
        <p>${esc(o.procedure)}</p>
        <span>${esc(o.provider)}</span>
      </article>`,
      )
      .join("")}</div>`;
  }

  function widgetTone(key) {
    const HW = halWidgetsApi();
    if (!HW || !activeFeed) return undefined;
    const w = HW.widgetFromFeed(activeFeed, key);
    const tone = HW.statusTone(w ? w.status : "FAILED");
    return tone === "ok" ? "success" : tone === "warn" ? "warning" : undefined;
  }

  function metricsFromWidget(key) {
    const HW = halWidgetsApi();
    const w = HW && activeFeed ? HW.widgetFromFeed(activeFeed, key) : null;
    return (w && w.metrics) || {};
  }

  function fmtClaim(value) {
    const D = dataApi();
    return D ? D.fmt(value) : String(value == null ? "—" : value);
  }

  function canvasOperatoryGrid(chairs) {
    if (!chairs || !chairs.length) {
      return `<div class="operatory-grid operatory-grid--empty">${canvasEmpty("No operatory schedule available — awaiting operatory_schedule.json export.")}</div>`;
    }
    return `<div class="operatory-grid">${chairs
      .map((chair) => {
        const slots = chair.slots || chair.appointments || [];
        return `<div class="operatory-column operatory-chair">
          <header class="operatory-column__head">${esc(chair.name || chair.label || "Operatory")}</header>
          ${slots.length
            ? slots
                .map(
                  (slot) => `<article class="operatory-slot operatory-slot--${esc(slot.tone || "default")}">
              <time>${esc(slot.time || "")}</time>
              <strong>${esc(slot.patient || slot.title || "")}</strong>
              <span>${esc(slot.procedure || slot.detail || "")}</span>
            </article>`,
                )
                .join("")
            : `<p class="widget-empty">No appointments</p>`}
        </div>`;
      })
      .join("")}</div>`;
  }

  function canvasNavPills(pageIds) {
    const pages = pageIds
      .map((id) => {
        const p = pageMeta(id);
        if (!p) return "";
        return `<button type="button" class="chip" data-ms-nav="${esc(id)}" data-hal-widget-nav="${esc(id)}" data-hal-suggest="Open ${esc(p.label)}">${esc(p.label)}</button>`;
      })
      .join("");
    return `<div class="filter-bar filter-bar--nav">${pages}</div>`;
  }

  function parsePct(value) {
    const n = parseFloat(String(value == null ? "" : value).replace(/[%$,]/g, ""));
    return Number.isFinite(n) ? Math.max(0, Math.min(100, n)) : 0;
  }

  function gridCol(span, html) {
    if (html.includes('class="widget-card')) {
      return html.replace('class="widget-card', `class="widget-card col-${span}`);
    }
    return `<div class="widget-card col-${span}"><div class="widget-body">${html}</div></div>`;
  }

  function canvasGrid12(colsHtml) {
    return colsHtml;
  }

  function canvasGauge(pct, label, color) {
    const p = Math.max(0, Math.min(100, pct || 0));
    const arc = (p / 100) * 157;
    return `<div class="gauge-container" role="img" aria-label="${esc(label || "Gauge")} ${p}%">
      <svg viewBox="0 0 120 70" class="gauge-svg" aria-hidden="true">
        <path d="M 10 65 A 50 50 0 0 1 110 65" fill="none" stroke="var(--line-subtle)" stroke-width="8"/>
        <path d="M 10 65 A 50 50 0 0 1 110 65" fill="none" stroke="${color || "var(--gold)"}" stroke-width="8" stroke-dasharray="${arc.toFixed(1)} 157" stroke-linecap="round"/>
      </svg>
      <strong class="gauge-value">${p}%</strong>
      ${label ? `<span class="gauge-label">${esc(label)}</span>` : ""}
    </div>`;
  }

  function canvasRingChart(pct, label) {
    const p = Math.max(0, Math.min(100, pct || 0));
    return `<div class="ring-chart"><div class="ring-donut" style="--ring-chart-pct:${p}%"><div class="ring-hole"><strong>${p}%</strong><span>${esc(label || "")}</span></div></div></div>`;
  }

  function canvasAgingTiles(aging) {
    if (!aging || !aging.labels || !aging.labels.length) return canvasEmpty("A/R aging buckets will appear when export data is loaded.");
    const max = Math.max(...aging.values, 1);
    return `<div class="aging-grid">${aging.labels
      .map((label, i) => {
        const v = aging.values[i] || 0;
        const width = Math.max(6, (v / max) * 100);
        return `<div class="aging-tile"><span>${esc(label)}</span><strong>${esc(String(v))}</strong><div class="aging-bar"><span style="width:${width.toFixed(1)}%"></span></div></div>`;
      })
      .join("")}</div>`;
  }

  function canvasFunnel(steps) {
    if (!steps || !steps.length) return canvasEmpty("Funnel metrics will appear when case acceptance data is loaded.");
    const amounts = steps.map((step) => parseAmount(step.count != null ? step.count : step.value));
    const base = Math.max(amounts[0] || 0, ...amounts, 1);
    const maxIdx = amounts.reduce((best, val, idx, arr) => (val > arr[best] ? idx : best), 0);
    return `<div class="funnel-chart">${steps
      .map((step, i) => {
        const amt = amounts[i];
        const widthPct = base > 0 ? Math.max(8, Math.round((amt / base) * 100)) : 0;
        const pctLabel = step.pct != null ? step.pct : base > 0 ? `${Math.round((amt / base) * 100)}%` : "—";
        const activeCls = i === maxIdx && amt > 0 ? " funnel-step--active" : "";
        return `<div class="funnel-step${activeCls}">
          <span class="funnel-label">${esc(step.label)}</span>
          <div class="funnel-bar" style="width:${widthPct}%">${esc(String(step.value != null ? step.value : amt || "—"))}</div>
          <span class="funnel-value">${esc(String(pctLabel))}</span>
        </div>`;
      })
      .join("")}</div>`;
  }

  function canvasHeatmap(rowLabels, colLabels, matrix) {
    if (!matrix || !matrix.length) return canvasEmpty("Aging heatmap will appear when A/R dashboard data is loaded.");
    const head = `<div class="heatmap-cell heatmap-header">Payer Type</div>${colLabels
      .map((c) => `<div class="heatmap-cell heatmap-header">${esc(c)}</div>`)
      .join("")}`;
    const body = matrix
      .map((row, ri) => {
        const label = `<div class="heatmap-cell" style="text-align:left;font-weight:600;">${esc(rowLabels[ri] || "")}</div>`;
        const cells = row
          .map((val) => {
            const n = parseAmount(val);
            const alpha = Math.min(0.85, 0.15 + n / 100);
            return `<div class="heatmap-cell" style="background:rgba(96,165,250,${alpha.toFixed(2)})">${esc(String(val))}</div>`;
          })
          .join("");
        return `${label}${cells}`;
      })
      .join("");
    return `<div class="heatmap-grid" role="img" aria-label="Aging heatmap">${head}${body}</div>`;
  }

  function canvasHeatmapPlaceholder() {
    return canvasHeatmap(
      ["Awaiting import"],
      ["0-30 Days", "31-60 Days", "61-90 Days", "91+ Days"],
      [["—", "—", "—", "—"]],
    );
  }

  function parseAmount(value) {
    if (typeof value === "number" && Number.isFinite(value)) return value;
    const n = Number(String(value || "").replace(/[$,%]/g, "").replace(/,/g, ""));
    return Number.isFinite(n) ? n : 0;
  }

  function canvasWaterfall(items) {
    if (!items || !items.length) return canvasEmpty("Waterfall chart will appear when trend data is loaded.");
    const nums = items.map((i) => Math.abs(parseAmount(i.value)));
    const max = Math.max(...nums, 1);
    return `<div class="waterfall-chart">${items
      .map((item) => {
        const h = Math.max(8, (Math.abs(parseAmount(item.value)) / max) * 100);
        const tone = item.type === "neg" ? "neg" : item.type === "total" ? "total" : "pos";
        return `<div class="waterfall-bar"><span class="waterfall-value">${esc(item.value)}</span><span class="waterfall-fill waterfall-fill--${tone}" style="height:${h.toFixed(1)}%"></span><span class="waterfall-label">${esc(item.label)}</span></div>`;
      })
      .join("")}</div>`;
  }

  function canvasTreemap(items, labelKey, valueKey) {
    if (!items || !items.length) {
      return `<div class="treemap-list">${canvasEmpty("Expense breakdown will appear when QuickBooks export is loaded.")}</div>`;
    }
    const max = Math.max(...items.map((i) => parseAmount(i[valueKey])), 1);
    return `<div class="treemap-list">${items
      .slice(0, 8)
      .map((item) => {
        const v = parseAmount(item[valueKey]);
        const w = Math.max(8, (v / max) * 100);
        return `<div class="treemap-row"><span>${esc(item[labelKey])}</span><div class="treemap-track"><span class="treemap-fill" style="width:${w.toFixed(1)}%"></span></div><strong>${esc(item[valueKey])}</strong></div>`;
      })
      .join("")}</div>`;
  }

  function canvasPriorityQueue(lanes, widgetKey) {
    const items = [];
    (lanes || []).forEach((lane) => {
      (lane.items || []).slice(0, 5).forEach((item) => {
        if (item && typeof item === "object") {
          items.push({
            label: item.patient || item.id || "Follow-up",
            meta: `${item.payer || lane.lane} · ${item.procedure || "Review"}`,
            amount: fmtClaim(item.amount),
          });
        } else {
          items.push({ label: String(item), meta: lane.lane, amount: "" });
        }
      });
    });
    if (!items.length) return canvasEmpty("Follow-up queue will appear when claims import is loaded.");
    return `<div class="queue-list">${items
      .map(
        (item) =>
          `<div class="queue-item" data-hal-widget-key="${esc(widgetKey || "")}" data-hal-cmd="Review ${esc(item.label)}" role="button" tabindex="0"><div><div class="queue-patient">${esc(item.label)}</div><div class="queue-meta">${esc(item.meta)}</div></div><div style="text-align:right;">${item.amount ? `<div class="queue-amount">${esc(item.amount)}</div>` : ""}<button type="button" class="queue-action action-btn action-btn--sm" data-hal-action="1">Review</button></div></div>`,
      )
      .join("")}</div>`;
  }

  function canvasClaimSidebar(claim, widgetKey) {
    const wk = widgetKey || "claimsPipeline";
    const denial = claim && claim.status === "Denied";
    return `<div class="side-panel">
      <article class="panel-card" data-hal-widget-key="${esc(wk)}"><h4>Denial risk</h4><p>${denial ? "Selected claim is denied — review attachments and payer notes." : "Pipeline claims are monitored for denial patterns."}</p></article>
      <article class="panel-card" data-hal-widget-key="${esc(wk)}"><h4>ERA matches</h4><p>${claim ? `${esc(claim.payer || "Payer")} · ${fmtClaim(claim.amount)}` : "ERA reconciliation appears when claims export is loaded."}</p></article>
      <article class="panel-card" data-hal-widget-key="${esc(wk)}"><h4>Attachments</h4><p>${claim ? "Verify narrative and perio chart before resubmit." : "Attachment checklist populates from open claims."}</p></article>
    </div>`;
  }

  function canvasDocCards(rows, widgetKey) {
    if (!rows || !rows.length) return canvasEmpty("Library documents will appear when local library data is indexed.");
    return `<div class="document-grid">${rows
      .slice(0, 12)
      .map(
        (row) =>
          `<article class="doc-card library-card" data-hal-widget-key="${esc(widgetKey || "")}" data-hal-cmd="Open ${esc(row[0])}" role="button" tabindex="0"><strong>${esc(row[0])}</strong><span>${esc(row[1])}</span><em>${esc(row[2])}${row[3] ? ` · exp ${esc(row[3])}` : ""}</em></article>`,
      )
      .join("")}</div>`;
  }

  function canvasWizardSteps(steps, activeIdx) {
    return `<div class="wizard-steps">${(steps || [])
      .map((label, i) => {
        const cls = i < activeIdx ? "done" : i === activeIdx ? "active" : "";
        return `<span class="wizard-step wizard-step--${cls}">${i + 1}. ${esc(label)}</span>`;
      })
      .join("")}</div>`;
  }

  function canvasRecallCalendar(practice) {
    const due = parseAmount(practice && practice.recallDue);
    const days = Array.from({ length: 14 }, (_, i) => {
      const hot = due > 0 && i % 5 === 0;
      const warm = due > 0 && i % 3 === 1;
      const cls = hot ? "hot" : warm ? "warm" : "";
      return `<div class="recall-day recall-day--${cls}">${i + 1}</div>`;
    }).join("");
    return `<div class="recall-calendar">${days}</div>${practice && practice.recallDue ? `<p class="widget-note">${esc(practice.recallDue)} over next 14 days</p>` : ""}`;
  }

  function canvasFocusCards(stats) {
    if (!stats || !stats.length) return canvasEmpty("Focus metrics will appear when office data is loaded.");
    return `<div class="focus-list">${stats
      .slice(0, 3)
      .map(
        (s) =>
          `<article class="focus-item"${s.widgetKey ? ` data-hal-widget-key="${esc(s.widgetKey)}" data-hal-cmd="Explain ${esc(s.label)}" role="button" tabindex="0"` : ""}><span>${esc(String(s.label || "").toUpperCase())}</span><strong>${esc(s.value)}</strong></article>`,
      )
      .join("")}</div>`;
  }

  function canvasScheduleTimeline(items) {
    if (!items || !items.length) return canvasEmpty("Schedule timeline will appear from local task updates.");
    return `<div class="schedule-timeline">${items
      .slice(0, 8)
      .map(
        (item) =>
          `<div class="schedule-row"><time>${esc(item.time)}</time><span>${esc(item.title)}</span><em>${esc(item.detail)}</em></div>`,
      )
      .join("")}</div>`;
  }

  function arHeatmapFromAging(aging) {
    if (!aging) return null;
    const cols = aging.labels.slice(0, 4);
    const vals = aging.values.slice(0, 4);
    const payer = ["Insurance", "Patient", "Other"];
    const matrix = payer.map((label, rowIdx) => {
      const factor = rowIdx === 0 ? 0.55 : rowIdx === 1 ? 0.35 : 0.1;
      return vals.map((v) => String(Math.round(Number(v || 0) * factor)));
    });
    return {
      rowLabels: payer,
      colLabels: cols,
      matrix,
    };
  }

  function canvasAlertTicker(items) {
    if (!items || !items.length) return "";
    return `<div class="nr2-alert-ticker" role="status" data-hal-widget-key="nr2AlertTicker">${items
      .map(
        (item) =>
          `<span class="nr2-alert-ticker__item nr2-alert-ticker__item--${esc(item.level || "info")}">${esc(item.text || "")}</span>`,
      )
      .join("")}</div>`;
  }

  function canvasGoalScorecard(goal) {
    if (!goal || !goal.hasData) {
      return canvasEmpty("Production goal scorecard appears when SoftDent dashboard production rows are loaded.");
    }
    const pct = goal.pctOfGoal != null ? `${goal.pctOfGoal}%` : "—";
    const pctNum = goal.pctOfGoal != null ? Number(goal.pctOfGoal) : 0;
    return `${canvasGauge(pctNum, "Of YTD goal", goal.tone === "ok" ? "var(--sage)" : "var(--accent-amber)")}${canvasStatGrid([
      { value: fmtClaim(goal.ytdProduction), label: "YTD production", widgetKey: "nr2GoalScorecard" },
      { value: fmtClaim(goal.targetProduction), label: "Goal target", widgetKey: "nr2GoalScorecard" },
      { value: pct, label: "Progress", tone: goal.tone, widgetKey: "nr2GoalScorecard" },
    ])}`;
  }

  function canvasProviderCompShare(payload) {
    const rows = (payload && payload.providers) || [];
    if (!rows.length) {
      return canvasEmpty("Provider production share appears when SoftDent provider rows or ODBC extract are loaded.");
    }
    return `${hBarChart(
      rows.map((row) => ({ name: row.name, amount: row.production, pct: row.pct })),
      "amount",
      "name",
      "pct",
    )}<div class="total-row"><span>Total production</span><strong>${fmtClaim(payload.totalProduction)}</strong></div>`;
  }

  function canvasMonthlyTrendCombo(combo) {
    if (!combo || !combo.hasData || !combo.labels || !combo.labels.length) {
      return canvasEmpty("Executive monthly trend populates when SoftDent and QuickBooks share monthly periods.");
    }
    return `${chartContainer(
      dualLineChart(
        combo.labels,
        [
          { tone: "info", data: combo.production || [] },
          { tone: "success", data: combo.revenue || [] },
        ],
        150,
      ),
      true,
    )}${chartContainer(
      dualLineChart(combo.labels, [{ tone: "warning", data: combo.collections || [] }], 90),
      true,
    )}`;
  }

  function canvasKpiRibbon(tiles) {
    if (!tiles || !tiles.length) {
      return `<div class="kpi-ribbon">${canvasEmpty("Cross-analytics KPI ribbon populates when SoftDent and QuickBooks imports share comparable periods.")}</div>`;
    }
    return `<div class="kpi-ribbon">${tiles
      .map(
        (tile) =>
          `<div class="kpi-ribbon-tile kpi-ribbon-tile--${esc(tile.tone || "neutral")} kpi-glow-card" data-hal-widget-key="${esc(tile.widgetKey || "nr2KpiRibbon")}" role="button" tabindex="0"><span>${esc(tile.label)}</span><strong>${esc(tile.value)}</strong></div>`,
      )
      .join("")}</div>`;
  }

  function canvasReconciliationTable(recon) {
    const rows = (recon && recon.rows) || [];
    if (!rows.length) {
      return canvasEmpty("Production reconciliation appears when SoftDent dashboard and QuickBooks monthly P&amp;L share periods.");
    }
    const tableRows = rows.map((row) => [
      row.period,
      row.softdentProduction != null ? `$${Math.round(row.softdentProduction).toLocaleString()}` : "—",
      row.quickbooksRevenue != null ? `$${Math.round(row.quickbooksRevenue).toLocaleString()}` : "—",
      row.variancePct != null ? `${row.variancePct}%` : "—",
    ]);
    return canvasTable(["Period", "SoftDent production", "QB revenue", "Variance"], tableRows, true);
  }

  function renderFinancial() {
    const D = dataApi();
    const kpis = D ? D.financialKpis() : [];
    const trend = D ? D.productionTrendSeries() : null;
    const payer = D ? D.payerDonut() : null;
    const providers = D ? D.providerBars() : null;
    const aging = D ? D.softdentAgingBars() : null;
    const payerMetrics = metricsFromWidget("payerMixAndCollections");
    const collectionPct = parsePct(payerMetrics.collectionRate || payerMetrics.latestMonthCollectionRate);
    const compare = D && D.financialCompare ? D.financialCompare() : [];
    const priorCompare = D && D.financialPriorCompare ? D.financialPriorCompare() : [];
    const finFilters =
      typeof NR2PageFilters !== "undefined" && NR2PageFilters.filterContext
        ? NR2PageFilters.filterContext("financial")
        : {};
    const ribbon = D && D.nr2KpiRibbonTiles ? D.nr2KpiRibbonTiles() : { tiles: [] };
    const alerts = D && D.nr2AlertTicker ? D.nr2AlertTicker() : { items: [] };
    const goal = D && D.nr2GoalScorecard ? D.nr2GoalScorecard() : {};
    const combo = D && D.nr2MonthlyTrendCombo ? D.nr2MonthlyTrendCombo() : {};
    const provComp = D && D.nr2ProviderCompensation ? D.nr2ProviderCompensation() : {};
    const recon = D && D.nr2ProductionReconciliation ? D.nr2ProductionReconciliation() : { rows: [] };
    const lag = D && D.nr2CollectionLag ? D.nr2CollectionLag() : {};
    const prodDaily = D && D.softdentProductionDailySeries ? D.softdentProductionDailySeries() : { points: [] };
    const lagKpi = lag.hasData
      ? [{ label: "Collection lag (DSO)", value: `${lag.avgLagDays} days`, hint: lag.dsoProxy ? "A/R weighted" : "Monthly proxy", widgetKey: "nr2CollectionLag" }]
      : [{ label: "Collection lag (DSO)", value: "—", hint: "Awaiting A/R aging export", widgetKey: "nr2CollectionLag" }];

    const alertItems =
      alerts.items && alerts.items.length
        ? alerts.items
        : [{ level: "ok", text: "Load imports to evaluate cross-analytics exception thresholds.", widgetKey: "nr2AlertTicker" }];

    return `${stackOpen()}
      ${canvasAlertTicker(alertItems)}
      ${
        finFilters.compareMode && priorCompare.length
          ? canvasPanel({
              title: "Compare mode — current vs prior month",
              accent: "green",
              widgetKey: "practiceFinancialOverview",
              colSpan: 12,
              body: `<div class="compare-mode-grid">${canvasCompareStrip(compare)}${canvasCompareStrip(priorCompare)}</div>`,
            })
          : ""
      }
      ${canvasPanel({
        title: "Cross-Analytics KPI Ribbon",
        accent: "green",
        widgetKey: "nr2KpiRibbon",
        colSpan: 12,
        body: canvasKpiRibbon(ribbon.tiles),
      })}
      ${heroKpiRow(kpis, 4)}
      ${canvasGrid12(`
        ${gridCol(
          8,
          canvasPanel({
            title: "Executive Monthly Trend",
            accent: "green",
            caption: "SoftDent production, collections, and QuickBooks revenue",
            widgetKey: "nr2MonthlyTrendCombo",
            body: canvasMonthlyTrendCombo(combo),
          }),
        )}
        ${gridCol(
          4,
          canvasPanel({
            title: "Production Goal Scorecard",
            accent: "green",
            caption: "YTD production vs operator goal",
            widgetKey: "nr2GoalScorecard",
            body: canvasGoalScorecard(goal),
          }),
        )}
        ${gridCol(
          12,
          canvasPanel({
            title: "Production vs QuickBooks Reconciliation",
            accent: "green",
            caption: recon.latest && recon.latest.variancePct != null ? `Latest variance ${recon.latest.variancePct}%` : "Monthly SoftDent production vs QB revenue",
            widgetKey: "nr2ProductionReconciliation",
            body: canvasReconciliationTable(recon),
          }),
        )}
        ${gridCol(
          6,
          canvasPanel({
            title: "Collection Lag",
            accent: "orange",
            caption: lag.summary || "DSO proxy from A/R aging buckets",
            widgetKey: "nr2CollectionLag",
            body: canvasKpiGrid(lagKpi),
          }),
        )}
        ${gridCol(
          6,
          canvasPanel({
            title: "SoftDent Production Trend",
            accent: "green",
            caption: prodDaily.granularity === "daily" ? "Daily production (daysheet)" : "Monthly production from dashboard export",
            widgetKey: "softdentProductionDaily",
            body:
              prodDaily.points && prodDaily.points.length
                ? chartContainer(
                    vBarChart(
                      prodDaily.points.map((p) => p.date),
                      prodDaily.points.map((p) => p.production),
                      "#60a5fa",
                    ),
                  )
                : canvasEmpty("Production trend appears when SoftDent dashboard or daysheet export is loaded."),
          }),
        )}
        ${gridCol(
          8,
          canvasPanel({
            title: wTitle("financial", 2),
            accent: "green",
            caption: "12-month production vs trailing average",
            widgetKey: "financialProductionTrend",
            body: trend ? chartContainer(finTrendChart(trend.production, trend.average, trend.max), true) : canvasEmpty("12-month production trend unavailable."),
          }),
        )}
        ${gridCol(
          4,
          canvasPanel({
            title: wTitle("financial", 6),
            accent: "green",
            caption: "Collection rate gauge",
            widgetKey: "payerMixAndCollections",
            body: `${canvasGauge(collectionPct, "Collection rate", "var(--sage)")}${payer ? conicDonut(payer.slices, payer.center, 88) : ""}`,
          }),
        )}
        ${gridCol(
          6,
          canvasPanel({
            title: "Provider production share",
            accent: "green",
            caption: "Provider production split",
            widgetKey: "nr2ProviderCompensationWidget",
            body: canvasProviderCompShare(provComp.hasData ? provComp : providers ? { providers: providers.items.map((item) => ({ name: item.name, production: parseAmount(item.amount), pct: item.pct })), totalProduction: parseAmount(providers.total), hasData: true } : { providers: [] }),
          }),
        )}
        ${gridCol(
          6,
          canvasPanel({
            title: "A/R aging summary",
            accent: "green",
            caption: "SoftDent receivables buckets",
            widgetKey: "practiceFinancialOverview",
            body: `${canvasAgingTiles(aging)}${compare.length ? canvasCompareStrip(compare) : ""}`,
          }),
        )}
      `)}
    </div>`;
  }

  function renderSoftdent() {
    const D = dataApi();
    const kpis = D ? D.softdentKpis() : [];
    const practice = D ? D.practiceStats() : {};
    const aging = D ? D.softdentAgingBars() : null;
    const collDaily = D && D.softdentCollectionsDailySeries ? D.softdentCollectionsDailySeries() : { labels: [], values: [] };
    const npMtd = D && D.softdentNewPatientsMtdData ? D.softdentNewPatientsMtdData() : { count: 0 };
    const claimsOut = D && D.softdentClaimsOutstandingData ? D.softdentClaimsOutstandingData() : { claims: [] };
    const provProd = D && D.softdentProviderProductionData ? D.softdentProviderProductionData() : { providers: [] };
    const apptSnap = D && D.softdentAppointmentsSnapshotData ? D.softdentAppointmentsSnapshotData() : { appointments: [] };
    const ca = metricsFromWidget("caseAcceptance");
    const funnelCounts = [
      parseAmount(ca.plansPresented || practice.treatmentPresented),
      parseAmount(ca.plansAccepted || practice.caseAccepted),
      parseAmount(ca.plansScheduled || practice.treatmentScheduled),
      parseAmount(ca.plansCompleted || practice.treatmentCompleted),
    ];
    const funnelSteps = [
      { label: "Presented", value: fmtClaim(practice.treatmentPresented || ca.plansPresented), count: funnelCounts[0] },
      { label: "Accepted", value: fmtClaim(ca.plansAccepted || practice.caseAccepted), count: funnelCounts[1] },
      { label: "Scheduled", value: fmtClaim(practice.treatmentScheduled || ca.plansScheduled), count: funnelCounts[2] },
      { label: "Completed", value: fmtClaim(practice.treatmentCompleted || ca.plansCompleted), count: funnelCounts[3] },
    ];
    return `${stackOpen()}
      ${heroKpiRow(kpis, 4)}
      ${canvasGrid12(`
        ${gridCol(
          12,
          canvasPanel({
            title: "Operatory Schedule",
            accent: "green",
            caption: "Today's chair timeline",
            widgetKey: "softdentOperatoryGrid",
            body: canvasOperatoryGrid(D ? D.softdentOperatoryGrid() : null),
          }),
        )}
        ${gridCol(
          8,
          canvasPanel({
            title: "Collections Trend",
            accent: "green",
            caption: "Collections from sd_payments or dashboard export",
            widgetKey: "softdentCollectionsDaily",
            body: collDaily.hasData
              ? chartContainer(vBarChart(collDaily.labels, collDaily.values, "#34d399"))
              : canvasEmpty("Collections trend appears when sd_payments or SoftDent dashboard collections are loaded."),
          }),
        )}
        ${gridCol(
          4,
          canvasPanel({
            title: "Appointments Snapshot",
            accent: "green",
            widgetKey: "softdentAppointmentsSnapshot",
            body: apptSnap.hasData
              ? canvasTable(
                  ["Date", "Patient", "Provider", "Status"],
                  apptSnap.appointments.map((a) => [a.date, a.patientId, a.provider, a.status]),
                  true,
                )
              : canvasEmpty("Appointment snapshot appears when sd_appointments or operatory schedule is loaded."),
          }),
        )}
        ${gridCol(
          6,
          canvasPanel({
            title: wTitle("softdent", 9),
            accent: "green",
            caption: "Case acceptance funnel",
            widgetKey: wKey("softdent", 9),
            body: canvasFunnel(funnelSteps),
          }),
        )}
        ${gridCol(
          6,
          canvasPanel({
            title: "Provider Production",
            accent: "green",
            widgetKey: "softdentProviderProduction",
            body: provProd.hasData
              ? hBarChart(
                  provProd.providers.map((p) => ({
                    name: p.providerCode,
                    amount: `$${Math.round(p.production).toLocaleString()}`,
                    pct: provProd.total ? Math.round((p.production / provProd.total) * 100) : 0,
                  })),
                  "amount",
                  "name",
                  "pct",
                )
              : canvasEmpty("Provider production appears when sd_procedures or financial provider rows are loaded."),
          }),
        )}
        ${gridCol(
          6,
          canvasPanel({
            title: wTitle("softdent", 6),
            accent: "green",
            caption: "A/R aging buckets",
            widgetKey: wKey("softdent", 6),
            body: aging ? chartContainer(vBarChart(aging.labels, aging.values, "#60a5fa")) : canvasEmpty("A/R aging buckets will appear when SoftDent A/R export is loaded."),
          }),
        )}
        ${gridCol(
          6,
          canvasPanel({
            title: wTitle("softdent", 7),
            widgetKey: wKey("softdent", 7),
            body: (() => {
              const resp = D ? D.softdentResponsibilityDonut() : null;
              return resp ? conicDonut(resp.slices, "") : canvasEmpty("Insurance vs patient split unavailable.");
            })(),
          }),
        )}
        ${gridCol(
          6,
          canvasPanel({
            title: "Outstanding Claims",
            accent: "orange",
            widgetKey: "softdentClaimsOutstanding",
            body: claimsOut.hasData
              ? canvasTable(
                  ["Claim", "Patient", "Amount", "Status"],
                  claimsOut.claims.map((c) => [c.claimId, c.patientName, `$${c.amount.toLocaleString()}`, c.status]),
                  true,
                )
              : canvasEmpty("Outstanding claims appear when sd_claims or SoftDent claims export is loaded."),
          }),
        )}
        ${gridCol(
          3,
          canvasPanel({
            title: "New Patients (MTD)",
            accent: "green",
            widgetKey: "softdentNewPatientsMTD",
            body: canvasStat(npMtd.hasData ? String(npMtd.count) : practice.newPatients || "—", "New patients MTD", npMtd.hasData ? "success" : undefined, "softdentNewPatientsMTD"),
          }),
        )}
        ${gridCol(
          3,
          canvasPanel({
            title: wTitle("softdent", 8),
            widgetKey: wKey("softdent", 8),
            body: canvasStat(practice.treatmentPresented || "—", "Treatment presented", undefined, wKey("softdent", 8)),
          }),
        )}
        ${gridCol(
          12,
          canvasPanel({
            title: wTitle("softdent", 0),
            accent: "green",
            caption: "Care delivery at a glance",
            widgetKey: wKey("softdent", 0),
            body: canvasStatGrid(D ? D.softdentGlanceStats() : []),
          }),
        )}
        ${gridCol(
          12,
          canvasPanel({
            title: wTitle("softdent", 10),
            accent: "green",
            caption: "Hygiene recall calendar · next 14 days",
            widgetKey: wKey("softdent", 10),
            body: `${canvasRecallCalendar(practice)}${canvasStat(practice.hygieneCompleted || "—", "Hygiene completed", widgetTone("hygieneRecall") === "success" ? "success" : undefined, wKey("softdent", 10))}`,
          }),
        )}
      `)}
    </div>`;
  }

  function quickbooksViewMode() {
    if (typeof window !== "undefined") {
      const hash = String(window.location.hash || "");
      if (/[?&]qb=classic/i.test(hash) || /[?&]view=legacy/i.test(hash)) return "legacy";
    }
    try {
      return localStorage.getItem("qb.viewMode") || "mockup";
    } catch {
      return "mockup";
    }
  }

  function quickbooksViewToggleHtml(nextMode) {
    const label = nextMode === "legacy" ? "Switch to classic treemap view" : "Switch to mockup dashboard view";
    return `<p class="widget-caption"><button type="button" class="prompt-chip" data-qb-view-toggle="${esc(nextMode)}">${esc(label)}</button></p>`;
  }

  function renderQuickbooksLegacy() {
    const D = dataApi();
    const kpis = D ? D.quickbooksKpis() : [];
    const plRows = D ? D.quickbooksPlRows() : [];
    const expenseDonut = D ? D.quickbooksExpenseDonut() : null;
    const treemapItems = expenseDonut
      ? expenseDonut.slices.map((s) => ({ label: s.label, amount: `${s.pct}%` }))
      : [];
    const waterfallItems = kpis.slice(0, 4).map((k, i) => ({
      label: k.label,
      value: k.value,
      type: i === kpis.length - 1 ? "total" : "pos",
    }));
    const reconcileRows = plRows.length
      ? plRows.slice(0, 8).map((row) => [row[0], row[1], "QuickBooks", "Synced"])
      : [];

    return `${stackOpen()}
      ${metricRowOpen()}${kpis.map(canvasMetricTile).join("")}${metricRowClose()}
      ${canvasGrid12(`
        ${gridCol(
          7,
          canvasPanel({
            title: wTitle("quickbooks", 1) || "Operating expenses",
            widgetKey: "quickbooksExpenseBreakdown",
            body: treemapItems.length
              ? canvasTreemap(treemapItems, "label", "amount")
              : canvasEmpty("Awaiting QuickBooks sync — expense breakdown will appear when export is loaded."),
          }),
        )}
        ${gridCol(
          5,
          canvasPanel({
            title: wTitle("quickbooks", 0) || "Profit & Loss summary",
            widgetKey: "quickbooksProfitLossDetail",
            body: waterfallItems.length
              ? canvasWaterfall(waterfallItems)
              : canvasEmpty("Awaiting QuickBooks sync — P&amp;L summary will appear when export is loaded."),
          }),
        )}
      `)}
      ${canvasPanel({
        title: "QuickBooks ↔ NR2 Reconciliation",
        widgetKey: "ebitdaNormalization",
        colSpan: 12,
        body: reconcileRows.length
          ? canvasTable(["Account", "Amount", "Source", "Sync"], reconcileRows, true)
          : canvasEmpty("Awaiting QuickBooks sync — P&amp;L rows will appear when export is loaded."),
      })}
      ${quickbooksViewToggleHtml("mockup")}
    </div>`;
  }

  function renderQuickbooks() {
    if (quickbooksViewMode() === "legacy") return renderQuickbooksLegacy();
    const D = dataApi();
    const kpis = D ? D.quickbooksKpis() : [];
    const plRows = D ? D.quickbooksPlRows() : [];
    const expenseBars = D ? D.quickbooksExpenseBars() : null;
    const plTrend = D ? D.quickbooksPlTrend() : null;
    const moRev = D && D.quickbooksMonthlyRevenueSeries ? D.quickbooksMonthlyRevenueSeries() : { labels: [], values: [] };
    const netInc = D && D.quickbooksNetIncomeSummary ? D.quickbooksNetIncomeSummary() : {};
    const bs = D && D.quickbooksBalanceSheetSummary ? D.quickbooksBalanceSheetSummary() : { assets: [] };
    const cf = D && D.quickbooksCashFlowTrend ? D.quickbooksCashFlowTrend() : { labels: [], net: [] };
    const revSvc = D && D.quickbooksRevenueByService ? D.quickbooksRevenueByService() : { slices: [] };
    const qbAr = D && D.quickbooksQbArAging ? D.quickbooksQbArAging() : { buckets: [] };
    const reconcileRows = plRows.length
      ? plRows.slice(0, 8).map((row) => [row[0], row[1], "QuickBooks", "Synced"])
      : [];

    const kpiCards = (kpis.length ? kpis : [{ label: "Net income YTD", value: "—" }])
      .slice(0, 4)
      .map((k, i) => {
        const widgetKey = k.widgetKey || (i === 3 ? "ebitdaNormalization" : "quickbooksProfitLossDetail");
        const delta = k.delta ? `<span class="trend${String(k.delta).trim().startsWith("-") ? " negative" : ""}">${esc(k.delta)}</span>` : "";
        const sparkHtml = k.spark && k.spark.length ? barSparkline(k.spark, k.tone) : "";
        return `<div class="card kpi-card kpi-glow-card" data-hal-widget-key="${esc(widgetKey)}">
          <div class="card-header"><span class="card-title">${widgetHeaderIcon(widgetKey)}${esc(k.label || k.title || "KPI")}</span></div>
          <div class="card-value">${esc(k.value || "—")}</div>
          ${sparkHtml}
          ${delta}
        </div>`;
      })
      .join("");

    const plChartBody = plTrend
      ? chartContainer(dualLineChart(plTrend.labels, plTrend.series), true)
      : chartContainer(canvasEmpty("Awaiting QuickBooks sync — P&amp;L trend will appear when export is loaded."));

    const expenseBody = expenseBars
      ? chartContainer(vBarChart(expenseBars.labels, expenseBars.values, "#00d4aa"))
      : chartContainer(canvasEmpty("Awaiting QuickBooks sync — expense breakdown will appear when export is loaded."));

    return `${stackOpen()}
      ${dashboardHost(`<div class="dashboard-grid">${kpiCards}</div>`)}
      ${dashboardHost(`<div class="dashboard-grid">
        <div class="card chart-large widget-glow-border" data-hal-widget-key="quickbooksProfitLossDetail">
          <div class="card-header"><span class="card-title">${widgetHeaderIcon("quickbooksProfitLossDetail")}Profit &amp; Loss Trend (YTD)</span></div>
          ${plChartBody}
        </div>
        <div class="card chart-medium widget-glow-border" data-hal-widget-key="quickbooksExpenseBreakdown">
          <div class="card-header"><span class="card-title">${widgetHeaderIcon("quickbooksExpenseBreakdown")}Operating Expenses</span></div>
          ${expenseBody}
        </div>
      </div>`)}
      ${dashboardHost(`<div class="dashboard-grid">
        <div class="card kpi-card kpi-glow-card" data-hal-widget-key="quickbooksNetIncomeSummary">
          <div class="card-header"><span class="card-title">${widgetHeaderIcon("quickbooksNetIncomeSummary")}Net Income (YTD)</span></div>
          <div class="card-value">${netInc.hasData && netInc.ytdNetIncome != null ? esc(`$${Math.round(netInc.ytdNetIncome).toLocaleString()}`) : "—"}</div>
          ${netInc.latestMonth ? `<span class="trend">${esc(netInc.latestMonth)} latest</span>` : ""}
        </div>
        <div class="card chart-medium widget-glow-border" data-hal-widget-key="quickbooksMonthlyRevenue">
          <div class="card-header"><span class="card-title">${widgetHeaderIcon("quickbooksMonthlyRevenue")}Monthly Revenue Trend</span></div>
          ${
            moRev.hasData
              ? chartContainer(vBarChart(moRev.labels, moRev.values, "#00d4ff"))
              : canvasEmpty("Monthly revenue trend appears when QuickBooks P&amp;L monthly rows are in the import cache.")
          }
        </div>
        <div class="card chart-medium widget-glow-border" data-hal-widget-key="quickbooksCashFlowTrend">
          <div class="card-header"><span class="card-title">${widgetHeaderIcon("quickbooksCashFlowTrend")}Cash Flow Trend</span></div>
          ${
            cf.hasData
              ? chartContainer(dualLineChart(cf.labels, [{ label: "Net", tone: "success", data: cf.net }]), true)
              : canvasEmpty("Cash flow trend appears when QuickBooks monthly P&amp;L rows are in the import cache.")
          }
        </div>
      </div>`)}
      ${dashboardHost(`<div class="dashboard-grid">
        <div class="card chart-medium widget-glow-border" data-hal-widget-key="quickbooksBalanceSheetSummary">
          <div class="card-header"><span class="card-title">${widgetHeaderIcon("quickbooksBalanceSheetSummary")}Balance Sheet Summary</span></div>
          ${
            bs.hasData
              ? canvasTable(
                  ["Asset", "Amount"],
                  (bs.assets || []).map((row) => [row.label, `$${Math.round(row.amount).toLocaleString()}`]),
                  true,
                )
              : canvasEmpty("Balance sheet summary appears when QuickBooks A/R and P&amp;L imports are loaded.")
          }
        </div>
        <div class="card chart-medium widget-glow-border" data-hal-widget-key="quickbooksRevenueByService">
          <div class="card-header"><span class="card-title">${widgetHeaderIcon("quickbooksRevenueByService")}Revenue by Service</span></div>
          ${
            revSvc.hasData
              ? chartContainer(vBarChart(revSvc.slices.map((s) => s.label), revSvc.slices.map((s) => s.amount), "#00d4aa"))
              : canvasEmpty("Revenue-by-service appears when QuickBooks category exports are loaded.")
          }
        </div>
        <div class="card chart-medium widget-glow-border" data-hal-widget-key="quickbooksArAging">
          <div class="card-header"><span class="card-title">${widgetHeaderIcon("quickbooksArAging")}QuickBooks A/R Aging</span></div>
          ${
            qbAr.hasData
              ? chartContainer(vBarChart(qbAr.buckets.map((b) => b.bucket), qbAr.buckets.map((b) => b.balance), "#f59e0b"))
              : canvasEmpty("QuickBooks A/R aging appears when quickbooks_ar.csv or SDK probe is loaded.")
          }
        </div>
      </div>`)}
      ${dashboardHost(`<div class="dashboard-grid">
        <div class="card chart-full widget-accent-orange widget-glow-border" data-hal-widget-key="ebitdaNormalization">
          <div class="card-header"><span class="card-title">${widgetHeaderIcon("ebitdaNormalization")}QuickBooks ↔ NR2 Reconciliation</span></div>
          ${reconcileRows.length ? canvasTable(["Account", "Amount", "Source", "Sync"], reconcileRows, true) : canvasEmpty("Awaiting QuickBooks sync — P&amp;L rows will appear when export is loaded.")}
        </div>
      </div>`)}
      ${quickbooksViewToggleHtml("legacy")}
    </div>`;
  }

  function renderAr() {
    const D = dataApi();
    const kpis = D ? D.arKpis() : [];
    const chart = D ? D.arCollectionsChart() : null;
    const claims = D ? D.arTopClaimsTable() : [];
    const kanban = D ? D.arFollowUpKanban() : [];
    const aging = D ? D.softdentAgingBars() : null;
    const heat = arHeatmapFromAging(aging);
    const payerDonut = D ? D.payerDonut() : null;
    const kanbanLanes =
      kanban.length > 0
        ? kanban
        : [
            { lane: "Needs call", tone: "orange", items: [] },
            { lane: "Awaiting payer", tone: "blue", items: [] },
            { lane: "Ready to close", tone: "green", items: [] },
          ];
    const waterfallItems = chart
      ? chart.labels.slice(-5).map((label, i) => ({
          label,
          value: String(chart.series[1] && chart.series[1].data[i] != null ? chart.series[1].data[i] : "—"),
          type: "pos",
        }))
      : [];
    return `${stackOpen()}
      ${canvasKpiGrid(kpis)}
      ${canvasGrid12(`
        ${gridCol(
          8,
          canvasPanel({
            title: wTitle("ar", 2),
            accent: "orange",
            caption: "Priority follow-up queue",
            widgetKey: wKey("ar", 2),
            body: canvasPriorityQueue(kanbanLanes, wKey("ar", 2)),
          }),
        )}
        ${gridCol(
          4,
          canvasPanel({
            title: "Payer mix",
            accent: "orange",
            caption: "Collections by payer",
            widgetKey: wKey("ar", 0),
            body: payerDonut ? conicDonut(payerDonut.slices, payerDonut.center, 96) : canvasEmpty("Payer mix will appear when collections data is loaded."),
          }),
        )}
        ${gridCol(
          8,
          canvasPanel({
            title: wTitle("ar", 0),
            accent: "orange",
            caption: "Payer × aging heatmap",
            widgetKey: wKey("ar", 0),
            body: heat ? canvasHeatmap(heat.rowLabels, heat.colLabels, heat.matrix) : canvasHeatmapPlaceholder(),
          }),
        )}
        ${gridCol(
          4,
          canvasPanel({
            title: "Collections waterfall",
            accent: "orange",
            caption: "Recent collections trend",
            widgetKey: wKey("ar", 0),
            body: waterfallItems.length ? chartContainer(canvasWaterfall(waterfallItems)) : chart ? chartContainer(dualLineChart(chart.labels, chart.series)) : canvasEmpty("Collections trend will appear when A/R dashboard data is loaded."),
          }),
        )}
        ${gridCol(
          12,
          canvasPanel({
            title: wTitle("ar", 1),
            accent: "orange",
            caption: "Top outstanding claims",
            widgetKey: wKey("ar", 1),
            body: claims.length
              ? canvasTable(["Patient", "Procedure", "Payer", "Balance", "Age"], claims, true)
              : canvasEmpty("Outstanding claim detail will appear when SoftDent claims export is loaded."),
          }),
        )}
      `)}
    </div>`;
  }

  function renderClaims() {
    const D = dataApi();
    const kpis = D ? D.claimsKpis() : [];
    const lanes = D ? D.claimsKanban() : [];
    const claim = D ? D.firstClaim() : null;
    const kanbanLanes =
      lanes.length > 0
        ? lanes
        : [
            { lane: "Draft", tone: "muted", items: [] },
            { lane: "Needs Review", tone: "orange", items: [] },
            { lane: "Ready", tone: "green", items: [] },
            { lane: "Denied", tone: "orange", items: [] },
          ];
    return `${stackOpen()}
      ${heroKpiRow(kpis, 4)}
      ${canvasGrid12(`
        ${gridCol(
          8,
          canvasPanel({
            title: wTitle("claims", 0),
            accent: "purple",
            caption: lanes.length ? "Claims pipeline from SoftDent import" : "Pipeline lanes · waiting on claims export",
            widgetKey: wKey("claims", 0),
            body: canvasKanbanLanes(kanbanLanes, wKey("claims", 0), { claims: true }),
          }),
        )}
        ${gridCol(
          4,
          canvasPanel({
            title: "Pipeline analytics",
            accent: "purple",
            caption: "Denial risk · ERA · attachments",
            widgetKey: "claimsPipeline",
            body: canvasClaimSidebar(claim, wKey("claims", 0)),
          }),
        )}
        ${gridCol(
          6,
          canvasPanel({
            title: "Claim detail",
            accent: "purple",
            caption: claim ? `${claim.patient || "Claim"} · ${claim.procedure || "—"}` : "Selected claim",
            widgetKey: "claimsPipeline",
            body: claim
              ? `<div class="claim-detail">
                <strong>${esc(claim.procedure || claim.id || "Claim")}</strong>
                <p>${esc(claim.patient || "—")} · ${esc(claim.payer || "—")}</p>
                ${canvasStatGrid([
                  { value: fmtClaim(claim.amount), label: "Billed amount" },
                  { value: fmtClaim(claim.serviceDate), label: "Service date" },
                ])}
              </div>`
              : canvasEmpty("Select a claim from the pipeline when claims import is loaded."),
          }),
        )}
        ${gridCol(
          6,
          canvasPanel({
            title: "Claim status",
            caption: claim ? claim.id || "First open claim" : "Claim history",
            widgetKey: "claimsPipeline",
            body: claim
              ? canvasTimeline([
                  { time: fmtClaim(claim.serviceDate), title: claim.status || "Open", detail: `${fmtClaim(claim.amount)} · ${claim.payer || "—"}`, active: true },
                  { time: "Import", title: "SoftDent claims export", detail: "Read-only workbench" },
                ])
              : canvasEmpty("Claim history will appear with SoftDent claims data."),
          }),
        )}
      `)}
    </div>`;
  }

  function renderNarratives() {
    const D = dataApi();
    const draft = D ? D.narrativeDraft() : "";
    const history = D ? D.narrativeHistoryRows() : [];
    const kpis = D && D.narrativeKpis ? D.narrativeKpis() : [];
    const confidencePct = draft ? Math.min(95, 40 + Math.floor(draft.length / 20)) : 0;
    const cdtCodes = ["D2740 Crown", "D2950 Core buildup", "D4341 Perio scaling", "D7210 Extraction", "D6010 Implant"];
    return `${stackOpen()}
      ${kpis.length ? `${metricRowOpen()}${kpis.map(canvasMetricTile).join("")}${metricRowClose()}` : `${metricRowOpen()}${canvasMetricTile({ label: "Narrative Composer", value: "Ready", widgetKey: wKey("narratives", 0) })}${metricRowClose()}`}
      <div class="composer-grid">
        <div class="panel" data-hal-widget-key="${esc(wKey("narratives", 0))}">
          <div class="panel-header"><span>Procedure Codes</span><span style="font-size:12px;color:var(--text-secondary)">CDT 2024</span></div>
          <div class="panel-content">
            <input class="search-box" type="search" placeholder="Search codes…" aria-label="Search CDT codes" />
            <div class="cdt-list">${cdtCodes
              .map(
                (code, i) =>
                  `<div class="cdt-item${i === 0 ? " active" : ""}" role="listitem"><div class="cdt-code">${esc(code.split(" ")[0])}</div><div class="cdt-desc">${esc(code.slice(code.indexOf(" ") + 1))}</div></div>`,
              )
              .join("")}</div>
          </div>
        </div>
        <div class="panel">
          <div class="composer-toolbar">
            <button type="button" class="chip" data-hal-cmd="Insert prior history into narrative">Insert history</button>
            <button type="button" class="chip" data-hal-cmd="Draft crown narrative">Draft with HAL</button>
            <button type="button" class="chip" data-narrative-save="1">Save draft locally</button>
          </div>
          <div class="composer-panel" data-hal-widget-key="${esc(wKey("narratives", 0))}">
            ${canvasTextArea(draft || "", 12, true)}
            ${draft ? `<div class="confidence-bar"><span style="color:var(--text-secondary)">AI Confidence:</span><div class="confidence-meter"><span class="confidence-fill" style="width:${confidencePct}%"></span></div><span>${confidencePct}%</span></div>` : canvasEmpty("Start typing or ask HAL to draft a narrative for staff review.")}
          </div>
        </div>
        <div class="panel" data-hal-widget-key="${esc(wKey("narratives", 0))}">
          <div class="panel-header"><span>Draft history</span></div>
          <div class="panel-content">${
            history.length
              ? history
                  .map(
                    ([ver, updated, focus]) =>
                      `<article class="doc-card"><strong>${esc(ver)}</strong><span>${esc(updated)}</span><em>${esc(focus)}</em></article>`,
                  )
                  .join("")
              : canvasEmpty("Saved drafts appear here after local save or HAL-assisted drafting.")
          }</div>
        </div>
      </div>
    </div>`;
  }

  function renderJournalQueuePanel(items) {
    if (!items.length) {
      return canvasEmpty("Journal posting queue requires the NR2 server. Run StartProgram.bat.");
    }
    const body = items
      .map((entry) => {
        const id = esc(entry.id || entry.entryId || "");
        const status = String(entry.status || "unknown");
        const pending = /pending/i.test(status);
        const actions = pending
          ? `<div class="journal-actions">
              <button type="button" class="action-btn action-btn--sm" data-journal-review="${id}" data-journal-action="approve">Approve</button>
              <button type="button" class="action-btn action-btn--sm action-btn--ghost" data-journal-review="${id}" data-journal-action="reject">Reject</button>
            </div>`
          : `<span class="text-muted">${esc(status)}</span>`;
        return `<tr>
          <td>${esc(entry.title || entry.description || entry.memo || entry.id || "Entry")}</td>
          <td>${esc(entry.amount != null ? entry.amount : "—")}</td>
          <td>${esc(entry.category || entry.account || "Journal")}</td>
          <td>${esc(entry.period || entry.createdAt || "—")}</td>
          <td>${actions}</td>
        </tr>`;
      })
      .join("");
    return `<div class="table-wrap"><table class="data-table data-table--compact data-table--striped">
      <thead><tr><th>Entry</th><th>Amount</th><th>Category</th><th>Period</th><th>Review</th></tr></thead>
      <tbody>${body}</tbody>
    </table></div>
    <div class="journal-toolbar">
      <button type="button" class="action-btn" data-journal-approve-all="1">Approve all pending</button>
      <button type="button" class="action-btn" data-journal-export="1">Export approved CSV</button>
    </div>`;
  }

  function renderDocuments() {
    const D = dataApi();
    const kpis = D ? D.documentsKpis() : [];
    const queue = D ? D.documentsQueueRows() : [];
    const doc = D ? D.firstDocument() : null;
    const periodStats = D ? D.documentsPeriodStats() : [];
    const journalItems = D ? D.journalQueueItems() : [];
    const ap = metricsFromWidget("accountsPayableAutomation");
    const postedPct = parsePct(periodStats[1] && periodStats[1].value);
    const wizardSteps = ["Intake", "Review", "Approve", "Post", "Close"];
    return `${stackOpen()}
      ${heroKpiRow(kpis, 4)}
      ${canvasGrid12(`
        ${gridCol(
          12,
          canvasPanel({
            title: wTitle("documents", 2),
            accent: "cyan",
            caption: "Period close wizard",
            widgetKey: wKey("documents", 2),
            body: `${canvasWizardSteps(wizardSteps, postedPct > 0 ? 2 : 0)}${periodStats.length ? canvasStatGrid(periodStats) : canvasEmpty("Period close metrics will appear when documents are assigned to a period.")}`,
          }),
        )}
        ${gridCol(
          8,
          canvasPanel({
            title: wTitle("documents", 0),
            accent: "cyan",
            caption: "OCR intake queue",
            widgetKey: wKey("documents", 0),
            body: queue.length ? canvasTable(["Document", "Category", "Amount", "Date"], queue, true) : canvasEmpty("Accounting documents will appear when the local document queue is populated."),
          }),
        )}
        ${gridCol(
          4,
          canvasPanel({
            title: wTitle("documents", 1),
            accent: "cyan",
            widgetKey: wKey("documents", 1),
            body: `${canvasDocPreview(doc ? doc.vendor || doc.id || "Document" : "Document preview", doc && doc.pages ? doc.pages : 1)}${doc ? "" : canvasEmpty("Document preview will appear when a document is selected.")}`,
          }),
        )}
        ${gridCol(
          12,
          canvasPanel({
            title: wTitle("documents", 4),
            caption: "Local journal queue",
            widgetKey: wKey("documents", 4),
            body: journalItems.length ? renderJournalQueuePanel(journalItems) : canvasEmpty("Journal posting queue requires the NR2 server. Run StartProgram.bat."),
          }),
        )}
        ${gridCol(
          6,
          canvasPanel({
            title: wTitle("documents", 3),
            accent: "cyan",
            widgetKey: wKey("documents", 3),
            body: `${canvasRingChart(postedPct, "Posted")}${canvasStat(fmtClaim(ap.expenseTotal), "Expense total", "warning", wKey("documents", 3))}`,
          }),
        )}
        ${gridCol(
          6,
          canvasPanel({
            title: "Source breakdown",
            accent: "cyan",
            widgetKey: wKey("documents", 0),
            body: canvasStatGrid(D ? D.documentsSourceBreakdown() : []),
          }),
        )}
      `)}
    </div>`;
  }

  function renderLibrary() {
    const D = dataApi();
    const kpis = D ? D.libraryKpis() : [];
    const rows = D ? D.libraryRows() : [];
    const doc = D ? D.firstLibraryDoc() : null;
    return `${stackOpen()}
      ${heroKpiRow(kpis, 4)}
      ${canvasSearch("Search contracts, compliance, vendors…", wKey("library", 0))}
      ${canvasGrid12(`${splitRow(
        canvasPanel({
          title: wTitle("library", 0),
          accent: "gray",
          caption: "Document library grid",
          widgetKey: wKey("library", 0),
          body: canvasDocCards(rows, wKey("library", 0)),
        }),
        canvasPanel({
          title: "Preview",
          accent: "gray",
          widgetKey: wKey("library", 0),
          body: `${canvasDocPreview(doc ? doc.title || doc.name || "Document" : "Library preview", doc && doc.pages ? doc.pages : 1)}
            ${doc ? `<div class="side-panel-meta">
              <article class="panel-card"><h4>Metadata</h4><p>${esc(doc.title || doc.name || "Document")} · ${esc(doc.category || "—")}</p></article>
              <article class="panel-card"><h4>Contract alert</h4><p>${doc.expires ? `Expires ${esc(doc.expires)}` : "No expiry on file."}</p></article>
            </div>` : canvasEmpty("Select a library document to preview.")}`,
        }),
      )}`)}
    </div>`;
  }

  function taxUsageBar(segments, total, caption) {
    const sum = segments.reduce((acc, s) => acc + (Number(s.amount) || 0), 0);
    const denom = total || sum || 1;
    const bars = segments
      .map((s) => {
        const pct = Math.max(4, Math.round((Number(s.amount) / denom) * 100));
        const color = s.id === "federal" ? "#60a5fa" : s.id === "kansas" ? "#c084fc" : "#78a86b";
        return `<div class="tax-split-seg" style="width:${pct}%;background:${color}" title="${esc(s.label)} ${esc(fmtTaxMoney(s.amount))}"></div>`;
      })
      .join("");
    const legend = segments
      .map((s) => `<span class="tax-split-key"><i style="background:${s.id === "federal" ? "#60a5fa" : "#c084fc"}"></i>${esc(s.label)} · ${esc(fmtTaxMoney(s.amount))}</span>`)
      .join("");
    return `<div class="tax-split-chart"><div class="tax-split-track">${bars}</div><div class="tax-split-legend">${legend}</div>${caption ? `<p class="tax-split-caption">${esc(caption)}</p>` : ""}</div>`;
  }

  function fmtTaxMoney(value) {
    if (typeof TaxEngine !== "undefined" && TaxEngine.formatMoney) return TaxEngine.formatMoney(value);
    return String(value == null ? "—" : value);
  }

  function renderTaxes() {
    const D = dataApi();
    const kpis = D ? D.taxKpis() : [];
    const bridge = D ? D.taxBridgeRows() : [];
    const scenarios = D ? D.taxCompScenarioRows() : [];
    const quarterly = D ? D.taxQuarterlyRows() : [];
    const split = D ? D.taxSplit() : [];
    const citations = D ? D.taxMemoCitations() : [];
    const federal = D ? D.taxFederalRows() : [];
    const kansas = D ? D.taxKansasRows() : [];
    const calendar = D ? D.taxCalendarRows() : [];
    const bookIncome = D ? D.taxBookIncomeRows() : [];
    const ebitda = D ? D.taxEbitdaRows() : [];
    const disclaimer = D ? D.taxDisclaimer() : "";
    const hasBook = D ? D.taxHasBookData() : false;
    const plan = D && D.taxPlan ? D.taxPlan() : null;
    const totalTax = plan ? plan.totalOwnerTaxEstimate : 0;
    const memoList = citations.length
      ? `<ul class="tax-memo-list">${citations
          .map((id) => `<li><strong>${esc(id)}</strong><span>docs/hal_knowledge/memories.jsonl</span></li>`)
          .join("")}</ul>`
      : canvasEmpty("MemoAI tax citations appear when the tax engine runs.");
    const compBars =
      plan && plan.compScenarios
        ? `<div class="bar-chart">${plan.compScenarios
            .map((s) => {
              const max = Math.max(...plan.compScenarios.map((x) => x.employerFica), 1);
              return `<div class="bar-chart-column${s.selected ? " bar-chart-column--active" : ""}"><span class="bar-chart-fill" style="height:${Math.max(8, (s.employerFica / max) * 100)}%;background:#60a5fa"></span><span class="bar-chart-label">${esc(fmtTaxMoney(s.salary))}</span></div>`;
            })
            .join("")}</div>`
        : canvasEmpty("Load QuickBooks P&amp;L to model compensation scenarios.");
    return `${stackOpen()}
      ${typeof NR2PageFilters !== "undefined" && NR2PageFilters.renderTaxScenarioPanelHtml ? NR2PageFilters.renderTaxScenarioPanelHtml() : ""}
      ${heroKpiRow(kpis, 4)}
      ${canvasGrid12(`
        ${gridCol(
          12,
          canvasPanel({
            title: "Related surfaces",
            widgetKey: "taxBookToTaxBridge",
            body: canvasNavPills(["financial", "quickbooks", "documents"]),
          }),
        )}
        ${gridCol(
          8,
          canvasPanel({
            title: "Book-to-tax bridge",
            accent: "blue",
            caption: plan ? `${plan.federalRateLabel} · ${plan.kansasRateLabel}` : "Planning rates",
            widgetKey: "taxBookToTaxBridge",
            body: bridge.length
              ? `${canvasWaterfall(bridge.slice(0, 6).map((row, i) => ({ label: row[0], value: row[1], type: i === 0 ? "total" : "neg" })))}${canvasTable(["Line item", "Amount"], bridge, true)}`
              : canvasEmpty("P&amp;L net income will drive the book-to-tax bridge when QuickBooks export is loaded."),
          }),
        )}
        ${gridCol(
          4,
          canvasPanel({
            title: "Estimated owner tax split",
            accent: "blue",
            caption: "Federal + Kansas on K-1 flow-through",
            widgetKey: "taxFederalStateSplit",
            body:
              split.length && totalTax
                ? taxUsageBar(split, totalTax, `Planning total ${fmtTaxMoney(totalTax)} · not a filed return`)
                : taxUsageBar(
                    [
                      { id: "federal", label: "Federal", amount: 0 },
                      { id: "kansas", label: "Kansas", amount: 0 },
                    ],
                    1,
                    "Tax split appears when book income is available.",
                  ),
          }),
        )}
        ${gridCol(
          6,
          canvasPanel({
            title: "Reasonable compensation scenarios",
            accent: "blue",
            caption: "Employer FICA by modeled W-2",
            widgetKey: "taxReasonableComp",
            body: `${canvasGauge(plan && plan.compScenarios && plan.compScenarios[0] ? parsePct(plan.compScenarios[0].employerFica) : 0, "Employer FICA", "#60a5fa")}${compBars}`,
          }),
        )}
        ${gridCol(
          6,
          canvasPanel({
            title: "Quarterly estimates",
            accent: "blue",
            caption: "1040-ES + Kansas vouchers",
            widgetKey: "taxQuarterlyEstimates",
            body: quarterly.length
              ? canvasTable(["Period", "Federal", "Kansas", "Due", "Status"], quarterly, true)
              : canvasEmpty("Quarterly plan appears when book income is available."),
          }),
        )}
        ${splitRow(
          canvasPanel({
            title: wTitle("taxes", 0),
            accent: "blue",
            widgetKey: "quickbooksProfitLossDetail",
            body: bookIncome.length
              ? canvasTable(["Account", "Amount", "Notes"], bookIncome, true)
              : canvasEmpty("P&amp;L rows will appear when QuickBooks export is loaded."),
          }),
          canvasPanel({
            title: wTitle("taxes", 1),
            accent: "blue",
            widgetKey: "ebitdaNormalization",
            body: ebitda.length
              ? canvasTable(["Adjustment", "Amount", "Reviewer", "Notes"], ebitda, true)
              : canvasEmpty("EBITDA add-backs will appear when expense categories are loaded."),
          }),
        )}
        ${splitRow(
          canvasPanel({
            title: "Key deadlines",
            accent: "blue",
            caption: "Calendar-year S corp",
            widgetKey: "taxQuarterlyEstimates",
            body: calendar.length ? canvasTable(["Date", "Jurisdiction", "Action"], calendar, true) : canvasEmpty("—"),
          }),
          canvasPanel({
            title: "MemoAI evidence",
            accent: "green",
            caption: "Memories cited for this plan",
            widgetKey: "taxBookToTaxBridge",
            body: memoList,
          }),
        )}
        ${gridCol(
          12,
          `<details class="widget-card col-12 details-panel"><summary>Federal &amp; Kansas obligations</summary>${splitRow(
            canvasPanel({
              title: "Federal obligations",
              accent: "blue",
              widgetKey: "taxFederalStateSplit",
              body: federal.length ? canvasTable(["Item", "Purpose", "Timing", "Notes"], federal, true) : canvasEmpty("—"),
            }),
            canvasPanel({
              title: "Kansas obligations",
              accent: "blue",
              widgetKey: "taxFederalStateSplit",
              body: kansas.length ? canvasTable(["Item", "Purpose", "Timing", "Notes"], kansas, true) : canvasEmpty("—"),
            }),
          )}</details>`,
        )}
      `)}
    </div>`;
  }

  function renderOfficeManager() {
    const D = dataApi();
    const kpis = D ? D.officeKpis() : [];
    const kanban = D ? D.officeKanban() : [];
    const tasks = D ? D.officeTaskRows() : [];
    const timeline = D ? D.officeTimeline() : [];
    const kanbanLanes =
      kanban.length > 0
        ? kanban
        : [
            { lane: "Billing", tone: "orange", items: [] },
            { lane: "Scheduling", tone: "blue", items: [] },
            { lane: "Owner review", tone: "green", items: [] },
          ];
    const staffPages =
      typeof PageSchema !== "undefined" && PageSchema.NAV_GROUPS
        ? PageSchema.NAV_GROUPS.flatMap((g) => g.pages).filter((id) => id !== "hal" && id !== "office-manager")
        : ["financial", "softdent", "narratives", "claims", "ar", "quickbooks", "documents", "library"];
    return `${stackOpen()}
      ${D && D.opsDataPanelHtml ? D.opsDataPanelHtml() : ""}
      ${canvasStatsBar(kpis)}
      ${canvasGrid12(`
        ${splitRow(
          canvasPanel({
            title: wTitle("office-manager", 0),
            accent: "yellow",
            caption: "Today's priorities",
            widgetKey: wKey("office-manager", 0),
            body: canvasFocusCards(kpis),
          }),
          canvasPanel({
            title: "Office task queue",
            accent: "yellow",
            caption: D ? D.periodSubtitle() : "Local tasks",
            widgetKey: wKey("office-manager", 0),
            body: tasks.length ? canvasTable(["Due", "Category", "Task", "Status"], tasks, true) : canvasEmpty("Local office tasks will appear when HAL or staff create them."),
          }),
        )}
        ${gridCol(
          12,
          canvasPanel({
            title: "Operatory schedule",
            accent: "yellow",
            caption: "Today's timeline",
            widgetKey: wKey("office-manager", 0),
            body: canvasScheduleTimeline(timeline.length ? timeline : [{ time: "8:30", title: "Morning huddle", detail: "Review open tasks" }]),
          }),
        )}
        ${gridCol(
          12,
          canvasPanel({
            title: wTitle("office-manager", 0),
            accent: "yellow",
            caption: "HAL office priorities kanban",
            widgetKey: wKey("office-manager", 0),
            body: canvasKanbanLanes(kanbanLanes, wKey("office-manager", 0)),
          }),
        )}
        ${gridCol(
          12,
          canvasPanel({
            title: wTitle("office-manager", 1),
            caption: "Jump to staff work surfaces",
            widgetKey: wKey("office-manager", 1),
            body: canvasNavPills(staffPages),
          }),
        )}
      `)}
    </div>`;
  }

  const RENDERERS = {
    financial: renderFinancial,
    taxes: renderTaxes,
    softdent: renderSoftdent,
    quickbooks: renderQuickbooks,
    ar: renderAr,
    claims: renderClaims,
    narratives: renderNarratives,
    documents: renderDocuments,
    library: renderLibrary,
    "office-manager": renderOfficeManager,
  };

  function renderBody(pageId, feed, programSnapshot) {
    if (
      typeof window !== "undefined" &&
      (!window.PageSchema || window.PageSchema.LAYOUT_EPOCH !== "moonshot-mockup")
    ) {
      throw new Error("[NR2] PageCanvas: Moonshot epoch required. Legacy layout retired.");
    }
    activePageId = pageId;
    activeFeed = feed || null;
    activeSnapshot = programSnapshot || null;
    const D = dataApi();
    if (D) D.bind(activeFeed, activeSnapshot);
    const fn = RENDERERS[pageId];
    const html = fn ? fn() : "";
    const noticeHtml = canvasImportNotice(pageImportNotice(pageId));
    return noticeHtml + (html || "");
  }

  function setFeed(feed, programSnapshot) {
    activeFeed = feed || null;
    if (programSnapshot !== undefined) activeSnapshot = programSnapshot || null;
    const D = dataApi();
    if (D) D.bind(activeFeed, activeSnapshot);
  }

  function hasPage(pageId) {
    return Boolean(RENDERERS[pageId]);
  }

  return { renderBody, hasPage, setFeed };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = PageCanvas;
}
if (typeof globalThis !== "undefined") {
  globalThis.PageCanvas = PageCanvas;
}
if (typeof window !== "undefined") {
  window.PageCanvas = PageCanvas;
}
