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
    return `<div class="widget-grid${extraClass ? " " + esc(extraClass) : ""}" data-nr2-layout="moonshot-layout">`;
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
    const MC = typeof MoonshotMockupChrome !== "undefined" ? MoonshotMockupChrome : null;
    return MC && MC.sectionHead ? MC.sectionHead(title, subtitle) : "";
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

  function kpiRefHalAttrs(widgetKey, cmdLabel) {
    if (!widgetKey) return "";
    const label = cmdLabel || widgetKey;
    return ` data-hal-widget-key="${esc(widgetKey)}" data-hal-kpi-ref="${esc(widgetKey)}" data-hal-cmd="Explain ${esc(label)}" role="button" tabindex="0"`;
  }

  function kpiRefOnly(widgetKey, cmdLabel) {
    if (!widgetKey) return "";
    const label = cmdLabel || widgetKey;
    return ` data-hal-kpi-ref="${esc(widgetKey)}" data-hal-cmd="Explain ${esc(label)}" role="button" tabindex="0"`;
  }

  function canvasMetricTile(kpi, colSpan) {
    const widgetKey = kpi.widgetKey || "";
    const HW = halWidgetsApi();
    const widget = HW && widgetKey && activeFeed ? HW.widgetFromFeed(activeFeed, widgetKey) : null;
    const cmdLabel = (widget && widget.title) || kpi.label || widgetKey;
    const halCmd = widgetKey && cmdLabel ? ` data-hal-cmd="Explain ${esc(cmdLabel)}"` : "";
    const halTone = widgetKey && HW ? ` hal-widget-status hal-widget-status--${HW.statusTone(widget ? widget.status : "FAILED")}` : "";
    const attrs = kpi.halSubpanel
      ? ` data-hal-subpanel="${esc(kpi.halSubpanel)}"`
      : widgetKey
        ? kpiRefHalAttrs(widgetKey, cmdLabel)
        : "";
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
    if (list.length >= 4) {
      return `<div class="kpi-hero-row col-12">${list.map((kpi) => canvasHeroTile(kpi)).join("")}</div>`;
    }
    const span = list.length >= 4 ? 3 : list.length === 3 ? 4 : list.length === 2 ? 6 : 12;
    return list.map((kpi) => canvasMetricTile(kpi, span)).join("");
  }

  function canvasHeroTile(kpi) {
    const widgetKey = kpi.widgetKey || "";
    const HW = halWidgetsApi();
    const widget = HW && widgetKey && activeFeed ? HW.widgetFromFeed(activeFeed, widgetKey) : null;
    const cmdLabel = (widget && widget.title) || kpi.label || widgetKey;
    const halTone = widgetKey && HW ? ` hal-widget-status hal-widget-status--${HW.statusTone(widget ? widget.status : "FAILED")}` : "";
    const attrs = kpi.halSubpanel
      ? ` data-hal-subpanel="${esc(kpi.halSubpanel)}"`
      : widgetKey
        ? kpiRefHalAttrs(widgetKey, cmdLabel)
        : "";
    const trend = kpi.hint ? `<div class="kpi-hint">${esc(kpi.hint)}</div>` : "";
    const sparkHtml = kpi.spark && kpi.spark.length ? barSparkline(kpi.spark, kpi.tone) : "";
    return `<div class="kpi-hero-tile widget-glow-border${halTone}"${attrs}>
      <div class="kpi-label">${widgetHeaderIcon(widgetKey)}${esc(String(kpi.label || ""))}</div>
      <div class="kpi-value">${esc(kpi.value)}</div>
      ${sparkHtml}
      ${trend}
    </div>`;
  }

  function dashboardHost(inner) {
    return `<div class="dashboard-grid-host col-12">${inner}</div>`;
  }

  function dashboardPageOpen(extraClass) {
    return `<div class="nr2-dashboard-page${extraClass ? " " + esc(extraClass) : ""}" data-nr2-layout="moonshot-layout">`;
  }

  function claimsAnalyticsHtml(D) {
    const claims = D && D.allClaims ? D.allClaims() : [];
    const payerMap = {};
    claims.forEach((c) => {
      const p = String(c.payer || "Other").slice(0, 20);
      payerMap[p] = (payerMap[p] || 0) + 1;
    });
    const payerEntries = Object.entries(payerMap).sort((a, b) => b[1] - a[1]).slice(0, 5);
    const payerLabels = payerEntries.length ? payerEntries.map((e) => e[0]) : ["Delta Dental", "Cigna", "MetLife", "Self-pay", "Other"];
    const payerValues = payerEntries.length ? payerEntries.map((e) => e[1]) : [0, 0, 0, 0, 0];
    const total = Math.max(claims.length, 1);
    const volLabels = ["Week 1", "Week 2", "Week 3", "Week 4"];
    const volValues = volLabels.map((_, i) => Math.max(0, Math.round(total * (0.2 + i * 0.05))));
    return `${gridCol(
      6,
      canvasPanel({
        title: "Claim submission volume",
        accent: "purple",
        halSubpanel: "claimsVolumeTrend",
        chartHost: true,
        body: chartContainer(
          claims.length ? vBarChart(volLabels, volValues, "#a855f7") : canvasEmpty("Claims volume appears when SoftDent claims export is loaded."),
        ),
      }),
    )}${gridCol(
      6,
      canvasPanel({
        title: "Open claims by payer",
        accent: "purple",
        halSubpanel: "claimsPayerBreakdown",
        chartHost: true,
        body: chartContainer(
          payerEntries.length ? vBarChart(payerLabels, payerValues, "#f59e0b") : canvasEmpty("Payer breakdown appears when claims export is loaded."),
        ),
      }),
    )}`;
  }

  function officeDashboardWidget(title, widgetKey, halSubpanel, body, extraClass) {
    const attrs = halSubpanel
      ? ` data-hal-subpanel="${esc(halSubpanel)}"`
      : widgetKey
        ? ` data-hal-widget-key="${esc(widgetKey)}"`
        : "";
    return `<div class="widget widget-glow-border${extraClass ? " " + esc(extraClass) : ""}"${attrs}>
      <div class="widget-header"><div class="widget-title">${esc(title)}</div></div>
      <div class="widget-body">${body}</div>
    </div>`;
  }

  function canvasKpiTile(kpi) {
    const widgetKey = kpi.widgetKey || "";
    const cmdLabel = kpi.label || widgetKey;
    const halCmd = widgetKey ? kpiRefOnly(widgetKey, cmdLabel) : "";
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
          `<div class="stat-item"${kpi.widgetKey ? kpiRefOnly(kpi.widgetKey, kpi.label) : ""}><div class="stat-icon">${icons[i] || "◈"}</div><div class="stat-info"><h4>${esc(kpi.value)}</h4><span>${esc(kpi.label)}</span></div></div>`,
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

  function canvasPanel({ title, caption, accent, widgetKey, body, dataOnly, colSpan, chartHost, halSubpanel }) {
    const HW = halWidgetsApi();
    const useSubpanel = Boolean(halSubpanel);
    const chrome =
      HW && widgetKey && !useSubpanel
        ? HW.panelChrome(widgetKey, title, activeFeed, { dataOnly: dataOnly !== false })
        : {
            badge: "",
            note: "",
            attrs: useSubpanel
              ? ` data-hal-subpanel="${esc(halSubpanel)}"`
              : widgetKey
                ? ` data-hal-widget-key="${esc(widgetKey)}"`
                : "",
            toneClass: "",
            icon: "",
          };
    const chartHostAttr = "";
    const col = colSpan ? ` col-${colSpan}` : "";
    const accentClass = accent === "orange" ? " widget-accent-orange" : "";
    return `<section class="widget-card widget-glow-border widget-mount-glow${col}${accentClass}${(chrome.toneClass || "").trim() ? " " + esc(chrome.toneClass.trim()) : ""}"${chrome.attrs}${chartHostAttr}>
        <div class="widget-header"><span class="widget-title">${chrome.icon || widgetHeaderIcon(widgetKey)}${esc(title)}</span><div class="widget-menu" aria-hidden="true">⋮</div></div>
        <div class="widget-body">${body}${chrome.note || ""}</div>
        ${caption ? `<p class="widget-caption">${esc(caption)}</p>` : ""}
    </section>`;
  }

  function canvasStat(value, label, tone, widgetKey) {
    const toneClass = tone ? ` stat-box--${tone}` : "";
    const wk = widgetKey || "";
    const attrs = wk ? kpiRefOnly(wk, label) : "";
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
    const claimId = esc(item.id || "CLM");
    return `<div class="claim-card ${risk}" role="button" tabindex="0" data-hal-action="1" data-hal-page="${esc(pageId)}" data-hal-widget="${esc(wk)}" data-hal-payload-label="${esc(item.patient || item.id || "")}" data-claim-id="${claimId}">
      <div class="claim-header"><span class="claim-id">${claimId}</span><span class="risk-badge ${risk}">${esc(claimRiskLabel(risk))}</span></div>
      <div class="claim-patient">${esc(item.patient || "Unknown")}</div>
      <div class="claim-procedure">${esc(item.procedure || "—")}</div>
      <div class="claim-meta"><span class="claim-payer">${esc(item.payer || "—")}</span><span class="claim-amount">${fmtClaim(item.amount)}</span></div>
      <div class="claim-actions"><button type="button" class="chip chip--sm" data-narrative-draft="${claimId}">Draft with HAL</button></div>
    </div>`;
  }

  function renderKanbanCard(item, widgetKey, pageId, options) {
    if (options && options.narratives) {
      if (typeof item === "string") {
        return `<div class="narrative-card" role="button" tabindex="0"><strong>${esc(item)}</strong></div>`;
      }
      const title = item.patient || item.procedureCode || item.title || "Draft";
      const meta = [item.procedureCode, item.payer, item.amount].filter(Boolean).join(" · ");
      return `<div class="narrative-card" role="button" tabindex="0">
        <div class="narrative-card__title">${esc(title)}</div>
        ${meta ? `<div class="narrative-card__meta">${esc(meta)}</div>` : ""}
      </div>`;
    }
    return renderClaimCard(item, widgetKey, pageId);
  }

  function canvasKanbanLanes(lanes, widgetKey, options) {
    const pageId = activePageId || "ar";
    const claimsMode = (options && options.claims) || pageId === "claims";
    const narrativeMode = (options && options.narratives) || pageId === "narratives";
    const laneHtml = lanes
      .map((lane) => {
        const cards = (lane.items || []).map((item) => renderKanbanCard(item, widgetKey, pageId, options)).join("");
        return `<div class="kanban-column">
          <div class="column-header"><span>${esc(lane.lane)}</span><span class="column-count">${(lane.items || []).length}</span></div>
          <div class="column-content">${cards}</div>
        </div>`;
      })
      .join("");
    const boardClass = narrativeMode ? " kanban-board--narratives" : claimsMode ? " kanban-board--claims" : "";
    return `<div class="kanban-board${boardClass}" data-hal-subpanel="${esc(widgetKey || "kanban")}-board">${laneHtml}</div>`;
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

  function canvasNarrativeSelectors(options, claim) {
    const opts = options || {};
    const selFocus = (name, values, selected) =>
      `<label class="narrative-field"><span>${esc(name)}</span><select data-narrative-field="${esc(name.toLowerCase())}">${values
        .map((v) => `<option value="${esc(v)}"${v === selected ? " selected" : ""}>${esc(v)}</option>`)
        .join("")}</select></label>`;
    return `<div class="narrative-draft-controls" data-narrative-draft-panel="1">
      ${claim ? `<p class="widget-note">Claim ${esc(claim.id || "—")} · ${esc(claim.patient || "—")} · ${esc(claim.procedure || "—")}</p>` : ""}
      <div class="narrative-field-row">
        ${selFocus("Focus", opts.focuses || ["Medical Necessity"], opts.focus)}
        ${selFocus("Tone", opts.tones || ["Professional"], opts.tone)}
        ${selFocus("Length", opts.lengths || ["Standard", "Brief"], opts.length)}
      </div>
      <div class="composer-toolbar">
        <button type="button" class="chip" data-narrative-generate="1">Generate draft</button>
        <button type="button" class="chip" data-narrative-save="1">Save draft locally</button>
        <button type="button" class="chip chip--ghost" data-narrative-draft-close="1">Close</button>
      </div>
    </div>`;
  }

  function canvasNarrativeCitations(widgetKeys) {
    if (typeof NR2Tier3 !== "undefined" && NR2Tier3.renderCitationChipsHtml) {
      return NR2Tier3.renderCitationChipsHtml(["draft_insurance_narrative"], widgetKeys || ["narrativeWorkflow", "claimsPipeline"]);
    }
    return "";
  }

  function canvasTextArea(value, rows, editable) {
    const disabled = editable ? "" : " disabled";
    const bodyAttr = editable ? ` data-narrative-body="1"` : "";
    return `<textarea class="composer-textarea" rows="${rows || 10}"${disabled}${bodyAttr}>${esc(value)}</textarea>`;
  }

  function canvasSearch(placeholder, widgetKey) {
    const wk = widgetKey || "documentLibrary";
    return `<div class="search-container" data-hal-subpanel="${esc(wk)}-search">
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
    return `<p class="widget-empty">${esc(message || "No data yet — run Refresh imports or check export paths; HAL fills this when the source file lands in the import bundle.")}</p>`;
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
          `<div class="queue-item" data-hal-subpanel="${esc(widgetKey || "followUpQueue")}" data-hal-cmd="Review ${esc(item.label)}" role="button" tabindex="0"><div><div class="queue-patient">${esc(item.label)}</div><div class="queue-meta">${esc(item.meta)}</div></div><div style="text-align:right;">${item.amount ? `<div class="queue-amount">${esc(item.amount)}</div>` : ""}<button type="button" class="queue-action action-btn action-btn--sm" data-hal-action="1">Review</button></div></div>`,
      )
      .join("")}</div>`;
  }

  function canvasClaimSidebar(claim, widgetKey) {
    const wk = widgetKey || "claimsPipeline";
    const denial = claim && claim.status === "Denied";
    return `<div class="side-panel">
      <article class="panel-card" data-hal-subpanel="${esc(wk)}"><h4>Denial risk</h4><p>${denial ? "Selected claim is denied — review attachments and payer notes." : "Pipeline claims are monitored for denial patterns."}</p></article>
      <article class="panel-card" data-hal-subpanel="${esc(wk)}"><h4>ERA matches</h4><p>${claim ? `${esc(claim.payer || "Payer")} · ${fmtClaim(claim.amount)}` : "ERA reconciliation appears when claims export is loaded."}</p></article>
      <article class="panel-card" data-hal-subpanel="${esc(wk)}"><h4>Attachments</h4><p>${claim ? "Verify narrative and perio chart before resubmit." : "Attachment checklist populates from open claims."}</p></article>
    </div>`;
  }

  function canvasDocCards(rows, widgetKey) {
    if (!rows || !rows.length) return canvasEmpty("Library documents will appear when local library data is indexed.");
    return `<div class="document-grid">${rows
      .slice(0, 12)
      .map(
        (row) =>
          `<article class="doc-card library-card" data-hal-subpanel="${esc(widgetKey || "documentLibrary")}" data-hal-cmd="Open ${esc(row[0])}" role="button" tabindex="0"><strong>${esc(row[0])}</strong><span>${esc(row[1])}</span><em>${esc(row[2])}${row[3] ? ` · exp ${esc(row[3])}` : ""}</em></article>`,
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
          `<article class="focus-item"${s.widgetKey ? kpiRefHalAttrs(s.widgetKey, s.label) : ""}><span>${esc(String(s.label || "").toUpperCase())}</span><strong>${esc(s.value)}</strong></article>`,
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
    return `<div class="nr2-alert-ticker" role="status">${items
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
          `<div class="kpi-ribbon-tile kpi-ribbon-tile--${esc(tile.tone || "neutral")} kpi-glow-card"${kpiRefOnly(tile.widgetKey || "nr2KpiRibbon", tile.label)}><span>${esc(tile.label)}</span><strong>${esc(tile.value)}</strong></div>`,
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

  function renderSoftdentOdbcStrip(status) {
    if (!status) return "";
    const mode = String(status.lastMode || "none");
    const populated = status.populatedTables != null ? status.populatedTables : 0;
    const configured = status.odbcConfigured === true;
    const queries = status.queriesConfigured != null ? status.queriesConfigured : 0;
    const last = status.lastExtractAt ? String(status.lastExtractAt).slice(0, 19) : "never";
    const tone = mode === "odbc" ? "green" : mode.startsWith("sensei") ? "green" : populated >= 3 ? "blue" : "orange";
    const counts = status.tableCounts || {};
    const countLine = ["patients", "procedures", "payments", "claims"]
      .map((key) => `${key} ${counts["sd_" + key] != null ? counts["sd_" + key] : "—"}`)
      .join(" · ");
    const hint = configured
      ? queries
        ? "ODBC DSN + queries configured"
        : "DSN set — run schema discovery for SQL queries"
      : mode.startsWith("sensei")
        ? "Sensei DataSync live lane (Carestream JSON)"
        : "JSON/daysheet fallback lane (ODBC optional)";
    return `<div class="nr2-odbc-strip nr2-odbc-strip--${tone}" role="status" aria-label="SoftDent extract lane">
      <span class="nr2-odbc-strip__badge">sd_* extract · ${esc(mode)}</span>
      <span class="nr2-odbc-strip__meta">${esc(hint)} · ${populated}/7 tables · last ${esc(last)}</span>
      <span class="nr2-odbc-strip__counts">${esc(countLine)}</span>
    </div>`;
  }

  function renderNarrativesComposerBody(D, H) {
    const draft = D ? D.narrativeDraft() : "";
    const history = D ? D.narrativeHistoryRows() : [];
    const kpis = D && D.narrativeKpis ? D.narrativeKpis() : [];
    const composerOpts = D && D.narrativeComposerOptions ? D.narrativeComposerOptions() : {};
    const claim = D ? D.firstClaim() : null;
    const citationWidgets = D && D.narrativeCitationWidgets ? D.narrativeCitationWidgets() : [];
    const confidencePct = draft ? Math.min(95, 40 + Math.floor(draft.length / 20)) : 0;
    const cdtCodes = ["D2740 Crown", "D2950 Core buildup", "D4341 Perio scaling", "D7210 Extraction", "D6010 Implant"];
    const hero =
      kpis.length > 0
        ? H.heroKpiRow(
            kpis.map((k) => ({ ...k, widgetKey: undefined })),
            4,
          )
        : H.heroKpiRow([{ label: "Narrative Composer", value: "Ready" }], 1);
    return `${H.stackOpen("narratives-moonshot")}
      ${hero}
      ${canvasNarrativeSelectors(composerOpts, claim)}
      <div class="composer-grid">
        <div class="composer-panel panel" data-hal-subpanel="narrativeProcedureCodes">
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
        <div class="composer-panel panel">
          <div class="composer-toolbar">
            <button type="button" class="chip" data-hal-cmd="Insert prior history into narrative">Insert history</button>
            <button type="button" class="chip" data-narrative-generate="1">Draft with HAL</button>
            <button type="button" class="chip" data-narrative-save="1">Save draft locally</button>
          </div>
          <div class="composer-panel" data-hal-widget-key="narrativeWorkflow" data-narrative-claim-id="${esc(claim && claim.id ? claim.id : "")}">
            ${canvasTextArea(draft || "", 12, true)}
            ${draft ? `<div class="confidence-bar"><span style="color:var(--text-secondary)">AI Confidence:</span><div class="confidence-meter"><span class="confidence-fill" style="width:${confidencePct}%"></span></div><span>${confidencePct}%</span></div>${canvasNarrativeCitations(citationWidgets)}` : canvasEmpty("Start typing or ask HAL to draft a narrative for staff review.")}
          </div>
        </div>
        <div class="composer-panel panel" data-hal-subpanel="narrativeDraftHistory">
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
        <div class="composer-panel panel" data-hal-subpanel="narrativeReferences">
          <div class="panel-header"><span>Payer &amp; eligibility</span></div>
          <div class="panel-content">${
            typeof NarrativePayerPanel !== "undefined" && NarrativePayerPanel.renderHtml
              ? NarrativePayerPanel.renderHtml(claim)
              : `<div class="npp-muted">Load narrative-payer-panel.js for payer reference and eligibility cache.</div>`
          }</div>
        </div>
      </div>
    </div>`;
  }

  function renderTaxScenarioPanelHtml() {
    if (typeof NR2PageFilters !== "undefined" && NR2PageFilters.renderTaxScenarioPanelHtml) {
      return NR2PageFilters.renderTaxScenarioPanelHtml();
    }
    return "";
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

  function buildMoonshotHelpers() {
    return {
      esc,
      stackOpen,
      dashboardPageOpen,
      dashboardHost,
      gridCol,
      canvasGrid12,
      heroKpiRow,
      canvasMetricTile,
      canvasPanel,
      canvasEmpty,
      chartContainer,
      vBarChart,
      dualLineChart,
      conicDonut,
      canvasTable,
      canvasKanbanLanes,
      canvasStatGrid,
      canvasGauge,
      canvasFunnel,
      canvasHeatmap,
      canvasKpiGrid,
      canvasKpiRibbon,
      canvasGoalScorecard,
      canvasProviderCompShare,
      canvasMonthlyTrendCombo,
      canvasReconciliationTable,
      canvasAlertTicker,
      canvasFocusCards,
      canvasScheduleTimeline,
      canvasNavPills,
      canvasStatsBar,
      officeDashboardWidget,
      canvasNarrativeSelectors,
      canvasTextArea,
      canvasNarrativeCitations,
      canvasDocPreview,
      canvasOperatoryGrid,
      canvasRecallCalendar,
      canvasTimeline,
      canvasWizardSteps,
      canvasRingChart,
      canvasWaterfall,
      canvasPriorityQueue,
      hBarChart,
      finTrendChart,
      canvasCompareStrip,
      canvasAgingTiles,
      canvasClaimSidebar,
      canvasClaimSidebar,
      renderJournalQueuePanel,
      renderNarrativesComposerBody,
      renderSoftdentOdbcStrip,
      renderTaxScenarioPanelHtml,
      widgetHeaderIcon,
      kpiRefHalAttrs,
      kpiRefOnly,
      fmtClaim,
      parsePct,
      parseAmount,
      metricsFromWidget,
      wTitle,
      wKey,
      pageImportNotice,
      canvasImportNotice,
      canvasStat,
      canvasHeatmapPlaceholder,
      arHeatmapFromAging,
      dataApi,
    };
  }

  function mockupPreviewGate(pageId) {
    const H = buildMoonshotHelpers();
    const mockPath = `.local_logs/moonshot_financial_eval/page_mockups_elite/${pageId}.html`;
    const noticeHtml = canvasImportNotice(pageImportNotice(pageId));
    const gate = `<section class="widget-card col-12 ms-mockup-preview-gate" data-ms-page-gate="${H.esc(pageId)}">
      <div class="widget-header"><span class="widget-title">Mockup preview only</span><span class="ms-muted">Live wiring disabled</span></div>
      <p class="ms-mockup-preview-gate__lead">Staff page bodies render from elite HTML mockups only. Layout engine integration is not wired until operator sign-off.</p>
      <p class="ms-mockup-preview-gate__path"><code>${H.esc(mockPath)}</code></p>
      <p class="ms-muted">Gallery index: <code>.local_logs/moonshot_financial_eval/page_mockups_elite/index.html</code></p>
    </section>`;
    return noticeHtml + gate;
  }

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
    return mockupPreviewGate(pageId);
  }

  function setFeed(feed, programSnapshot) {
    activeFeed = feed || null;
    if (programSnapshot !== undefined) activeSnapshot = programSnapshot || null;
    const D = dataApi();
    if (D) D.bind(activeFeed, activeSnapshot);
  }

  function hasPage(pageId) {
    if (typeof PageSchema !== "undefined" && typeof PageSchema.isStaffPage === "function") {
      return PageSchema.isStaffPage(pageId);
    }
    return false;
  }

  return { renderBody, hasPage, setFeed, buildMoonshotHelpers, mockupPreviewGate };
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

/**
 * page-canvas.js — data-resolution + empty-state guard
 */

// 1. Shared honesty / resolution helpers
PageCanvas.hasRenderableData = function(datasetKey, minRows = 1) {
  function okRows(rows) {
    if (Array.isArray(rows)) return rows.length >= minRows;
    return false;
  }
  const binderRows = {
    "softdent.procedures": () =>
      typeof PageCanvasData !== "undefined" && PageCanvasData.softdentProcedures
        ? PageCanvasData.softdentProcedures()
        : [],
    "softdent.claimStatus": () =>
      typeof PageCanvasData !== "undefined" && PageCanvasData.softdentClaimStatus
        ? PageCanvasData.softdentClaimStatus()
        : [],
    "quickbooks.expenseCategories": () =>
      typeof PageCanvasData !== "undefined" && PageCanvasData.quickbooksExpenseCategories
        ? PageCanvasData.quickbooksExpenseCategories().rows
        : [],
    "quickbooks.ar": () =>
      typeof PageCanvasData !== "undefined" && PageCanvasData.quickbooksAr ? PageCanvasData.quickbooksAr().rows : [],
  };
  if (binderRows[datasetKey]) {
    const rows = binderRows[datasetKey]();
    if (okRows(rows)) return true;
  }
  const snap = (typeof window !== "undefined" && window.HAL?.bus?.snapshot?.datasets) || {};
  const ds = snap[datasetKey];
  if (!ds) return false;
  const rows = Array.isArray(ds) ? ds : (ds.rows || ds.data);
  if (Array.isArray(rows)) return rows.length >= minRows;
  if (typeof ds === "object" && Object.keys(ds).length > 0) return true;
  return false;
};

// Resolve passed page data against live HAL bus datasets when renderer bag is empty
PageCanvas.resolveData = function(pageId, passedData) {
  if (passedData && Object.keys(passedData).length > 0) return passedData;
  const out = { ...(passedData || {}) };
  const snap =
    (typeof window !== "undefined" && window.HAL?.bus?.snapshot?.datasets) || {};
  Object.keys(snap).forEach((dsKey) => {
    if (dsKey.startsWith(pageId + ".")) {
      const short = dsKey.split(".").pop();
      out[short] = snap[dsKey];
    }
  });
  if (pageId === "softdent" && typeof PageCanvasData !== "undefined") {
    if (PageCanvasData.softdentProcedures) out.procedures = PageCanvasData.softdentProcedures();
    if (PageCanvasData.softdentClaimStatus) out.claimStatus = PageCanvasData.softdentClaimStatus();
  }
  if (pageId === "financial" || pageId === "quickbooks") {
    const D = typeof PageCanvasData !== "undefined" ? PageCanvasData : null;
    if (D && D.quickbooksKpis) {
      const kpis = D.quickbooksKpis() || [];
      kpis.forEach((k) => {
        if (k && k.widgetKey === "quickbooksNetIncomeSummary") out.netIncome = k.value;
      });
    }
  }
  return out;
};

PageCanvas.moonshotPreviewHtml = function moonshotPreviewHtml(pageId, feed, snapshot) {
  return typeof this.renderBody === "function" ? this.renderBody(pageId, feed, snapshot) : "";
};
