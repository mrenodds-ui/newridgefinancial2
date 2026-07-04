/**
 * Staff page bodies — canvas layout from hal-page-designs.canvas.tsx.
 * Widget keys and HAL badges come from PageSchema + halWidgetFeed.
 */
const PageCanvas = (function () {
  let activeFeed = null;
  let activeSnapshot = null;
  let activePageId = null;

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
    return `<svg class="pv-spark" viewBox="0 0 ${w} ${h}" aria-hidden="true"><polyline fill="none" stroke="${color || "#d6b15e"}" stroke-width="2" points="${pts}"/></svg>`;
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
        return `<line x1="${pad.l}" y1="${y.toFixed(1)}" x2="${w - pad.r}" y2="${y.toFixed(1)}" class="pv-chart-line"/>`;
      })
      .join("");
    const path = (vals) => vals.map((v, i) => `${i ? "L" : "M"}${xAt(i, vals.length).toFixed(1)},${yAt(v).toFixed(1)}`).join(" ");
    const dots = production
      .map((v, i) => `<circle cx="${xAt(i, production.length).toFixed(1)}" cy="${yAt(v).toFixed(1)}" r="2.6" fill="#d6b15e"/>`)
      .join("");
    const avgLine = average ? `<path d="${path(average)}" fill="none" stroke="#64748b" stroke-width="2" stroke-dasharray="5 4"/>` : "";
    return `<svg class="pv-fin-line" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img" aria-label="Trend chart">${grid}${avgLine}<path d="${path(production)}" fill="none" stroke="#d6b15e" stroke-width="2.5"/>${dots}</svg>`;
  }

  function dualLineChart(labels, series, height) {
    const h = height || 120;
    const w = 460;
    const pad = { t: 8, r: 8, b: 22, l: 8 };
    const all = series.flatMap((s) => s.data);
    const max = Math.max(...all) * 1.05;
    const min = 0;
    const range = max - min || 1;
    const innerW = w - pad.l - pad.r;
    const innerH = h - pad.t - pad.b;
    const xAt = (i, len) => pad.l + (i / (len - 1)) * innerW;
    const yAt = (v) => pad.t + innerH - ((v - min) / range) * innerH;
    const colors = { info: "#60a5fa", success: "#78a86b", warning: "#fb923c" };
    const paths = series
      .map((s) => {
        const stroke = colors[s.tone] || "#d6b15e";
        const d = s.data.map((v, i) => `${i ? "L" : "M"}${xAt(i, s.data.length).toFixed(1)},${yAt(v).toFixed(1)}`).join(" ");
        return `<path d="${d}" fill="none" stroke="${stroke}" stroke-width="2.5"/>`;
      })
      .join("");
    const xLabels = (labels || [])
      .map((label, i) => `<text x="${xAt(i, labels.length)}" y="${h - 4}" class="pv-chart-axis" text-anchor="middle">${esc(label)}</text>`)
      .join("");
    return `<svg class="pv-fin-line" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img">${paths}${xLabels}</svg>`;
  }

  function vBarChart(labels, values, color) {
    const max = Math.max(...values, 1);
    return `<div class="pv-vbars">${values
      .map(
        (v, i) =>
          `<div class="pv-vbar"><span class="pv-vbar__fill" style="height:${Math.max(8, (v / max) * 100)}%;background:${color || "#d6b15e"}"></span><span class="pv-vbar__lbl">${esc(labels[i] || "")}</span></div>`,
      )
      .join("")}</div>`;
  }

  function hBarChart(items, valueKey, labelKey, pctKey) {
    const max = Math.max(...items.map((i) => i[pctKey] || 0), 1);
    return `<div class="pv-hbars">${items
      .map((item) => {
        const pct = item[pctKey] || 0;
        return `<div class="pv-hbar"><span class="pv-hbar__label">${esc(item[labelKey])}</span><div class="pv-hbar__track"><span class="pv-hbar__fill" style="width:${(pct / max) * 100}%"></span></div><span class="pv-hbar__val">${esc(item[valueKey])}</span><span class="pv-hbar__pct">${pct}%</span></div>`;
      })
      .join("")}</div>`;
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
          `<div class="pv-legend__row"><span class="pv-legend__dot" style="background:${s.color}"></span><span>${esc(s.label)}</span><strong>${s.pct}%</strong></div>`,
      )
      .join("");
    return `<div class="pv-donut-wrap"><div class="pv-donut-chart" style="width:${sz}px;height:${sz}px;background:conic-gradient(${stops.join(", ")})"><div class="pv-donut-chart__hole">${center || ""}</div></div><div class="pv-legend">${legend}</div></div>`;
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
        return `<span class="pv-kpi-bar" style="height:${h.toFixed(1)}px;opacity:${opacity.toFixed(2)}"></span>`;
      })
      .join("");
    const toneClass = tone ? ` pv-kpi-bars--${tone}` : "";
    return `<div class="pv-kpi-bars${toneClass}">${bars}</div>`;
  }

  function canvasMetricTile(kpi) {
    const toneClass = kpi.tone ? ` pv-canvas-metric--${kpi.tone}` : "";
    const widgetKey = kpi.widgetKey || "";
    const HW = halWidgetsApi();
    const widget = HW && widgetKey && activeFeed ? HW.widgetFromFeed(activeFeed, widgetKey) : null;
    const icon =
      widgetKey && typeof AppIcons !== "undefined"
        ? `<span class="pv-canvas-metric__ico">${AppIcons.widget(widgetKey)}</span>`
        : "";
    const statusDot = HW && widgetKey && HW.halStatusDot ? HW.halStatusDot(widgetKey, widget) : "";
    const cmdLabel = (widget && widget.title) || kpi.label || widgetKey;
    const halCmd = widgetKey && cmdLabel ? ` data-hal-cmd="Explain ${esc(cmdLabel)}"` : "";
    const halTone = widgetKey && HW ? ` pv-hal-widget pv-hal-widget--${HW.statusTone(widget ? widget.status : "FAILED")}` : "";
    const attrs = widgetKey ? ` data-hal-widget-key="${esc(widgetKey)}"${halCmd} role="button" tabindex="0"` : "";
    const deltaTone = kpi.tone === "success" ? "success" : kpi.tone === "warning" ? "warning" : "neutral";
    const deltaPill = kpi.hint ? `<span class="pv-kpi-delta pv-kpi-delta--${deltaTone}">${esc(kpi.hint)}</span>` : "";
    const spark = kpi.spark ? barSparkline(kpi.spark, kpi.tone || "default") : "";
    return `<article class="pv-canvas-metric pv-canvas-metric--hero${toneClass}${halTone}"${attrs}>
      <div class="pv-canvas-metric__head">
        <span class="pv-canvas-metric__label">${esc(String(kpi.label || "").toUpperCase())}</span>
        <span class="pv-canvas-metric__ico-wrap">${icon}${statusDot}</span>
      </div>
      <div class="pv-canvas-metric__value-row">
        <strong class="pv-canvas-metric__value">${esc(kpi.value)}</strong>
        ${deltaPill}
      </div>
      ${spark}
    </article>`;
  }

  function canvasCompareStrip(items) {
    return `<div class="pv-canvas-compare">${items
      .map(
        (item) => `<div class="pv-canvas-compare__item">
        <span class="pv-canvas-compare__label">${esc(item.label)}</span>
        <strong class="pv-canvas-compare__value">${esc(item.value)}</strong>
        <span class="pv-canvas-compare__delta${item.tone ? ` pv-canvas-compare__delta--${esc(item.tone)}` : ""}">${esc(item.delta)}</span>
      </div>`,
      )
      .join("")}</div>`;
  }

  function canvasPanel({ title, caption, accent, widgetKey, body, dataOnly }) {
    const accentClass = accent ? ` pv-canvas-panel--${esc(accent)}` : "";
    const HW = halWidgetsApi();
    const chrome =
      HW && widgetKey
        ? HW.panelChrome(widgetKey, title, activeFeed, { dataOnly: dataOnly !== false })
        : {
            badge: "",
            note: "",
            attrs: widgetKey ? ` data-hal-widget-key="${esc(widgetKey)}"` : "",
            toneClass: "",
            icon: widgetKey && typeof AppIcons !== "undefined" ? `<span class="pv-canvas-panel__ico">${AppIcons.widget(widgetKey)}</span>` : "",
          };
    return `<section class="pv-canvas-panel${accentClass}${(chrome.toneClass || "").trim()}"${chrome.attrs}>
      <header class="pv-canvas-panel__head">${chrome.icon}<h3>${esc(title)}</h3>${chrome.badge}</header>
      <div class="pv-canvas-panel__body">${body}${chrome.note || ""}</div>
      ${caption ? `<footer class="pv-canvas-panel__foot">${esc(caption)}</footer>` : ""}
    </section>`;
  }

  function canvasStat(value, label, tone, widgetKey) {
    const toneClass = tone ? ` pv-canvas-stat--${tone}` : "";
    const wk = widgetKey || "";
    const icon =
      wk && typeof AppIcons !== "undefined" ? `<span class="pv-canvas-stat__ico">${AppIcons.widget(wk)}</span>` : "";
    const attrs = wk ? ` data-hal-widget-key="${esc(wk)}" data-hal-cmd="Explain ${esc(label)}" role="button" tabindex="0"` : "";
    return `<div class="pv-canvas-stat${toneClass}"${attrs}>${icon}<strong>${esc(value)}</strong><span>${esc(label)}</span></div>`;
  }

  function canvasStatGrid(stats) {
    return `<div class="pv-canvas-stat-grid">${stats.map((s) => canvasStat(s.value, s.label, s.tone, s.widgetKey)).join("")}</div>`;
  }

  function canvasTable(headers, rows, striped) {
    const head = `<tr>${headers.map((h) => `<th>${esc(h)}</th>`).join("")}</tr>`;
    const body = rows
      .map((row) => `<tr>${row.map((cell) => `<td>${esc(cell)}</td>`).join("")}</tr>`)
      .join("");
    return `<div class="pv-table-wrap"><table class="pv-table${striped ? " pv-table--striped" : ""}"><thead>${head}</thead><tbody>${body}</tbody></table></div>`;
  }

  function canvasKanbanLanes(lanes, widgetKey) {
    const pageId = activePageId || "ar";
    const laneHtml = lanes
      .map((lane) => {
        const cards = (lane.items || [])
          .map(
            (item) =>
              `<button type="button" class="pv-hal-kanban__card" data-hal-action="1" data-hal-page="${esc(pageId)}" data-hal-widget="${esc(widgetKey || "smartClaimsAndReceivables")}" data-hal-library="Kanban pilot" data-hal-event="cardSelected" data-hal-payload-label="${esc(item)}" data-hal-next="Review selected pipeline card"><span>${esc(item)}</span></button>`,
          )
          .join("");
        return `<section class="pv-hal-kanban__lane pv-hal-kanban__lane--${esc(lane.tone || "muted")}">
          <div class="pv-hal-kanban__lane-head"><span>${esc(lane.lane)}</span><strong>${(lane.items || []).length}</strong></div>
          ${cards}
        </section>`;
      })
      .join("");
    return `<div class="pv-hal-kanban" data-hal-widget-key="${esc(widgetKey || "")}"><div class="pv-hal-kanban__lanes">${laneHtml}</div></div>`;
  }

  function canvasTimeline(items) {
    return `<div class="pv-canvas-timeline">${items
      .map(
        (item) => `<div class="pv-canvas-timeline__item${item.active ? " pv-canvas-timeline__item--active" : ""}">
        <span class="pv-canvas-timeline__time">${esc(item.time)}</span>
        <strong>${esc(item.title)}</strong>
        <em>${esc(item.detail)}</em>
      </div>`,
      )
      .join("")}</div>`;
  }

  function canvasDocPreview(title, pages) {
    return `<div class="pv-doc-preview-frame pv-hal-pdf">
      <div class="pv-doc-preview-cover">
        <strong>${esc(title)}</strong>
        <span class="pv-storage">${esc(String(pages))} pages · PDF preview</span>
      </div>
    </div>`;
  }

  function canvasTextArea(value, rows, editable) {
    const disabled = editable ? "" : " disabled";
    const bodyAttr = editable ? ` data-narrative-body="1"` : "";
    return `<textarea class="pv-canvas-textarea" rows="${rows || 10}"${disabled}${bodyAttr}>${esc(value)}</textarea>`;
  }

  function canvasSearch(placeholder, widgetKey) {
    const wk = widgetKey || "documentLibrary";
    return `<div class="pv-canvas-search-wrap" data-hal-widget-key="${esc(wk)}">
      <input class="pv-canvas-search" type="search" placeholder="${esc(placeholder)}" data-hal-library-query="1" aria-label="Search library" />
      <button type="button" class="pv-button pv-button--sm" data-hal-library-search="1">Search with HAL</button>
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
    return `<div class="pv-usage-bar">
      <div class="pv-usage-bar__head"><span>${esc(labelLeft)}</span><span>${esc(labelRight)}</span></div>
      <div class="pv-usage-bar__track">${fills}</div>
    </div>`;
  }

  function canvasEmpty(message) {
    return `<p class="pv-canvas-empty pv-muted">${esc(message || "No data yet — HAL fills this when the source export is available.")}</p>`;
  }

  function canvasImportNotice(notice) {
    if (!notice || !notice.message) return "";
    const toneClass =
      notice.tone === "error"
        ? " pv-hal-widget__note--off"
        : notice.tone === "warning"
          ? " pv-hal-widget__note--warn"
          : "";
    return `<p class="pv-hal-widget__note pv-canvas-import-notice${toneClass}">${esc(notice.message)}</p>`;
  }

  function dataApi() {
    return typeof PageCanvasData !== "undefined" ? PageCanvasData : null;
  }

  function canvasImportHealthGrid() {
    const D = dataApi();
    const cards = D ? D.importHealthCards() : [];
    if (!cards.length) {
      return `<div class="pv-canvas-operatory-grid">${canvasEmpty("SoftDent import status will appear here after the dashboard export loads.")}</div>`;
    }
    return `<div class="pv-canvas-operatory-grid">${cards
      .map(
        (o) => `<article class="pv-canvas-operatory-card pv-canvas-operatory-card--${esc(o.tone)}">
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

  function canvasOperatoryGrid() {
    return canvasImportHealthGrid();
  }

  function canvasNavPills(pageIds) {
    const pages = pageIds
      .map((id) => {
        const p = pageMeta(id);
        if (!p) return "";
        const icon = typeof AppIcons !== "undefined" ? AppIcons.nav(id) : "";
        return `<button type="button" class="pv-filter-pill pv-canvas-nav-pill" data-pv-nav="${esc(id)}" data-hal-widget-nav="${esc(id)}" data-hal-suggest="Open ${esc(p.label)}"><span class="pv-canvas-nav-pill__ico">${icon}</span><span>${esc(p.label)}</span></button>`;
      })
      .join("");
    return `<div class="pv-canvas-nav-pills">${pages}</div>`;
  }

  function renderFinancial() {
    const D = dataApi();
    const kpis = D ? D.financialKpis() : [];
    const weekly = D ? D.financialWeeklyBars() : null;
    const ytd = D ? D.financialYtdBars() : null;
    const trend = D ? D.productionTrendSeries() : null;
    const payer = D ? D.payerDonut() : null;
    const providers = D ? D.providerBars() : null;
    const weekMax = weekly ? Math.max(...weekly.values, 1) : 1;
    const weekBars = weekly
      ? weekly.values
          .map(
            (v, i) =>
              `<div class="pv-vbar"><span class="pv-vbar__fill" style="height:${Math.max(8, (v / weekMax) * 100)}%;background:var(--sage)"></span><span class="pv-vbar__lbl">${esc(weekly.labels[i])}</span></div>`,
          )
          .join("")
      : canvasEmpty("Production trend data will appear when SoftDent dashboard export is loaded.");
    const ytdMax = ytd ? Math.max(...ytd.values, 1) : 1;
    const ytdBars = ytd
      ? ytd.labels
          .map(
            (label, i) =>
              `<div class="pv-vbar"><span class="pv-vbar__fill" style="height:${Math.max(8, (ytd.values[i] / ytdMax) * 100)}%;background:#60a5fa"></span><span class="pv-vbar__lbl">${esc(label)}</span></div>`,
          )
          .join("")
      : canvasEmpty("QuickBooks YTD totals will appear when P&amp;L export is loaded.");

    return `<div class="pv-canvas-stack">
      ${canvasImportNotice(D ? D.financialImportNotice() : null)}
      <div class="pv-canvas-metric-grid pv-canvas-metric-grid--hero">${kpis.map(canvasMetricTile).join("")}</div>
      ${sectionHead("Performance snapshot", D ? D.periodSubtitle() : "Import snapshot")}
      <div class="pv-canvas-grid-2">
        ${canvasPanel({
          title: wTitle("financial", 1),
          accent: "green",
          caption: weekly ? weekly.caption : "Production trend",
          widgetKey: wKey("financial", 1),
          body: `<div class="pv-vbars">${weekBars}</div>`,
        })}
        ${canvasPanel({
          title: wTitle("financial", 0),
          accent: "green",
          caption: ytd ? ytd.caption : "QuickBooks + SoftDent overview",
          widgetKey: wKey("financial", 0),
          body: `<div class="pv-vbars">${ytdBars}</div>`,
        })}
      </div>
      ${sectionHead("Trends & mix", "From HAL widget feed and import dashboards")}
      <div class="pv-canvas-grid-3">
        ${canvasPanel({
          title: wTitle("financial", 1),
          caption: "Production trend",
          widgetKey: wKey("financial", 1),
          body: trend ? finTrendChart(trend.production, trend.average, trend.max) : canvasEmpty("12-month production trend unavailable."),
        })}
        ${canvasPanel({
          title: wTitle("financial", 2),
          caption: "Payer mix & collections",
          widgetKey: wKey("financial", 2),
          body: payer ? conicDonut(payer.slices, payer.center) : canvasEmpty("Payer mix will appear when collections data is loaded."),
        })}
        ${canvasPanel({
          title: wTitle("financial", 3),
          caption: "Provider production split",
          widgetKey: wKey("financial", 3),
          body: providers
            ? `${hBarChart(providers.items, "amount", "name", "pct")}<div class="pv-total-row"><span>Total</span><strong>${esc(providers.total)}</strong></div>`
            : canvasEmpty("Provider rows will appear when SoftDent dashboard export includes providers."),
        })}
      </div>
    </div>`;
  }

  function renderSoftdent() {
    const D = dataApi();
    const kpis = D ? D.softdentKpis() : [];
    const practice = D ? D.practiceStats() : {};
    const aging = D ? D.softdentAgingBars() : null;
    const resp = D ? D.softdentResponsibilityDonut() : null;
    const caseRateNum = parseFloat(String(practice.caseRate || "").replace("%", ""));
    return `<div class="pv-canvas-stack">
      ${canvasImportNotice(D ? D.softdentImportNotice() : null)}
      <div class="pv-canvas-metric-grid pv-canvas-metric-grid--hero">${kpis.map(canvasMetricTile).join("")}</div>
      ${sectionHead("Care delivery", D ? D.periodSubtitle() : "SoftDent source")}
      ${canvasPanel({
        title: wTitle("softdent", 0),
        accent: "green",
        caption: "Care delivery and collections",
        widgetKey: wKey("softdent", 0),
        body: canvasStatGrid(D ? D.softdentGlanceStats() : []),
      })}
      <div class="pv-canvas-grid-2">
        ${canvasPanel({
          title: wTitle("softdent", 1),
          caption: "A/R aging buckets",
          widgetKey: wKey("softdent", 1),
          body: aging
            ? vBarChart(aging.labels, aging.values, "#60a5fa")
            : canvasEmpty("A/R aging buckets will appear when SoftDent A/R export is loaded."),
        })}
        ${canvasPanel({
          title: wTitle("softdent", 2),
          caption: "Balance responsibility split",
          widgetKey: wKey("softdent", 2),
          body: resp ? conicDonut(resp.slices, "") : canvasEmpty("Insurance vs patient split unavailable."),
        })}
      </div>
      <div class="pv-canvas-grid-3">
        ${canvasPanel({
          title: wTitle("softdent", 3),
          widgetKey: wKey("softdent", 3),
          body: `${canvasStat(practice.newPatients || "—", "New patients MTD", widgetTone("newPatients") === "success" ? "success" : undefined, wKey("softdent", 3))}${practice.newPatientsHint ? `<p class="pv-canvas-note">${esc(practice.newPatientsHint)}</p>` : ""}`,
        })}
        ${canvasPanel({
          title: wTitle("softdent", 4),
          widgetKey: wKey("softdent", 4),
          body: `${canvasStat(practice.treatmentPresented || "—", "Treatment presented", undefined, wKey("softdent", 4))}`,
        })}
        ${canvasPanel({
          title: wTitle("softdent", 5),
          widgetKey: wKey("softdent", 5),
          body: `${canvasStat(practice.caseRate || "—", "Case acceptance", widgetTone("caseAcceptance") === "success" ? "success" : undefined, wKey("softdent", 5))}${
            practice.caseAccepted && Number.isFinite(caseRateNum)
              ? canvasUsageBar(
                  [
                    { id: "accepted", value: caseRateNum, color: "green" },
                    { id: "open", value: Math.max(0, 100 - caseRateNum), color: "gray" },
                  ],
                  "Accepted vs presented",
                  practice.caseAccepted,
                )
              : ""
          }`,
        })}
      </div>
    </div>`;
  }

  function renderQuickbooks() {
    const D = dataApi();
    const kpis = D ? D.quickbooksKpis() : [];
    const plRows = D ? D.quickbooksPlRows() : [];
    const expenseBars = D ? D.quickbooksExpenseBars() : null;
    const expenseDonut = D ? D.quickbooksExpenseDonut() : null;
    const ebitda = D ? D.ebitdaRows() : [];
    const importNotice = D ? D.quickbooksImportNotice() : null;
    return `<div class="pv-canvas-stack">
      ${canvasImportNotice(importNotice)}
      <div class="pv-canvas-metric-grid pv-canvas-metric-grid--hero">${kpis.map(canvasMetricTile).join("")}</div>
      <div class="pv-canvas-grid-3">
        ${canvasPanel({
          title: wTitle("quickbooks", 0),
          accent: "blue",
          caption: "QuickBooks P&amp;L import",
          widgetKey: wKey("quickbooks", 0),
          body: plRows.length ? canvasTable(["Account", "Amount", "Notes"], plRows, true) : canvasEmpty("P&amp;L rows will appear when QuickBooks export is loaded."),
        })}
        ${canvasPanel({
          title: "Monthly operating expenses",
          caption: "Operating expenses from import",
          widgetKey: wKey("quickbooks", 0),
          body: expenseBars ? vBarChart(expenseBars.labels, expenseBars.values, "#fb923c") : canvasEmpty("Monthly expense trend unavailable."),
        })}
        ${canvasPanel({
          title: "Expense mix",
          caption: "Expense categories",
          widgetKey: wKey("quickbooks", 0),
          body: expenseDonut ? conicDonut(expenseDonut.slices, "") : canvasEmpty("Expense category mix unavailable."),
        })}
      </div>
      ${canvasPanel({
        title: wTitle("quickbooks", 1),
        accent: "blue",
        caption: "EBITDA normalization from HAL feed",
        widgetKey: wKey("quickbooks", 1),
        body: ebitda.length
          ? canvasTable(["Adjustment", "Amount", "Reviewer", "Notes"], ebitda, true)
          : canvasEmpty("EBITDA add-backs will appear when QuickBooks expense categories are loaded."),
      })}
    </div>`;
  }

  function renderAr() {
    const D = dataApi();
    const kpis = D ? D.arKpis() : [];
    const chart = D ? D.arCollectionsChart() : null;
    const claims = D ? D.arTopClaimsTable() : [];
    const kanban = D ? D.arFollowUpKanban() : [];
    const kanbanLanes =
      kanban.length > 0
        ? kanban
        : [
            { lane: "Needs call", tone: "orange", items: [] },
            { lane: "Awaiting payer", tone: "blue", items: [] },
            { lane: "Ready to close", tone: "green", items: [] },
          ];
    return `<div class="pv-canvas-stack">
      ${canvasImportNotice(D ? D.arImportNotice() : null)}
      <div class="pv-canvas-metric-grid pv-canvas-metric-grid--hero">${kpis.map(canvasMetricTile).join("")}</div>
      ${canvasPanel({
        title: wTitle("ar", 0),
        accent: "orange",
        caption: "Collections trend",
        widgetKey: wKey("ar", 0),
        body: chart ? dualLineChart(chart.labels, chart.series) : canvasEmpty("Collections trend will appear when A/R dashboard data is loaded."),
      })}
      ${canvasPanel({
        title: wTitle("ar", 1),
        accent: "orange",
        caption: "Top outstanding claims",
        widgetKey: wKey("ar", 1),
        body: claims.length
          ? canvasTable(["Patient", "Procedure", "Payer", "Balance", "Age"], claims, true)
          : canvasEmpty("Outstanding claim detail will appear when SoftDent claims export is loaded."),
      })}
      ${canvasPanel({
        title: wTitle("ar", 2),
        accent: "orange",
        caption: kanban.length ? "A/R follow-up lanes" : "Follow-up queue · waiting on claims import",
        widgetKey: wKey("ar", 2),
        body: canvasKanbanLanes(kanbanLanes, wKey("ar", 2)),
      })}
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
    return `<div class="pv-canvas-stack">
      ${canvasImportNotice(D ? D.claimsImportNotice() : null)}
      <div class="pv-canvas-metric-grid pv-canvas-metric-grid--hero">${kpis.map(canvasMetricTile).join("")}</div>
      ${canvasPanel({
        title: wTitle("claims", 0),
        accent: "purple",
        caption: lanes.length ? "Claims pipeline from SoftDent import" : "Pipeline lanes · waiting on claims export",
        widgetKey: wKey("claims", 0),
        body: canvasKanbanLanes(kanbanLanes, wKey("claims", 0)),
      })}
      <div class="pv-canvas-grid-split">
        ${canvasPanel({
          title: "Claim detail",
          accent: "purple",
          caption: claim ? `${claim.patient || "Claim"} · ${claim.procedure || "—"}` : "Selected claim",
          widgetKey: wKey("claims", 0),
          body: claim
            ? `<div class="pv-canvas-detail">
            <strong>${esc(claim.procedure || claim.id || "Claim")}</strong>
            <p>${esc(claim.patient || "—")} · ${esc(claim.payer || "—")}</p>
            <hr />
            ${canvasStatGrid([
              { value: fmtClaim(claim.amount), label: "Billed amount" },
              { value: fmtClaim(claim.serviceDate), label: "Service date" },
            ])}
          </div>`
            : canvasEmpty("Select a claim from the pipeline when claims import is loaded."),
        })}
        ${canvasPanel({
          title: "Claim status",
          caption: claim ? claim.id || "First open claim" : "Claim history",
          widgetKey: wKey("claims", 0),
          body: claim
            ? canvasTimeline([
                { time: fmtClaim(claim.serviceDate), title: claim.status || "Open", detail: `${fmtClaim(claim.amount)} · ${claim.payer || "—"}`, active: true },
                { time: "Import", title: "SoftDent claims export", detail: "Read-only workbench" },
              ])
            : canvasEmpty("Claim history will appear with SoftDent claims data."),
        })}
      </div>
    </div>`;
  }

  function renderNarratives() {
    const D = dataApi();
    const draft = D ? D.narrativeDraft() : "";
    const history = D ? D.narrativeHistoryRows() : [];
    const kpis = D && D.narrativeKpis ? D.narrativeKpis() : [];
    return `<div class="pv-canvas-stack">
      ${canvasImportNotice(D ? D.narrativesImportNotice() : null)}
      ${kpis.length ? `<div class="pv-canvas-metric-grid pv-canvas-metric-grid--hero">${kpis.map(canvasMetricTile).join("")}</div>` : ""}
      <div class="pv-canvas-grid-split">
        ${canvasPanel({
          title: wTitle("narratives", 0),
          accent: "pink",
          caption: "Insurance narrative composer",
          widgetKey: wKey("narratives", 0),
          body: `<div class="pv-hal-editor" data-hal-widget-key="${esc(wKey("narratives", 0))}">
            <div class="pv-canvas-toolbar-row">
              <button type="button" class="btn btn--ghost" data-hal-cmd="Insert prior history into narrative">Insert history</button>
              <button type="button" class="btn btn--ghost" data-hal-cmd="Draft crown narrative">Draft with HAL</button>
              <button type="button" class="btn btn--secondary" data-narrative-save="1">Save draft locally</button>
            </div>
            ${canvasTextArea(draft || "", 10, true)}
            ${draft ? "" : canvasEmpty("Start typing or ask HAL to draft a narrative for staff review.")}
          </div>`,
        })}
        ${canvasPanel({
          title: "Draft history",
          caption: "Local narrative drafts",
          widgetKey: wKey("narratives", 0),
          body: history.length
            ? canvasTable(["Version", "Updated", "Focus", "Author"], history, true)
            : canvasEmpty("Saved drafts appear here after local save or HAL-assisted drafting."),
        })}
      </div>
    </div>`;
  }

  function renderJournalQueuePanel(items) {
    if (!items.length) {
      return canvasEmpty("Journal posting queue is available in desktop mode.");
    }
    const body = items
      .map((entry) => {
        const id = esc(entry.id || entry.entryId || "");
        const status = String(entry.status || "unknown");
        const pending = /pending/i.test(status);
        const actions = pending
          ? `<div class="pv-journal-actions">
              <button type="button" class="pv-button pv-button--sm" data-journal-review="${id}" data-journal-action="approve">Approve</button>
              <button type="button" class="pv-button pv-button--sm pv-button--ghost" data-journal-review="${id}" data-journal-action="reject">Reject</button>
            </div>`
          : `<span class="pv-muted">${esc(status)}</span>`;
        return `<tr>
          <td>${esc(entry.title || entry.description || entry.memo || entry.id || "Entry")}</td>
          <td>${esc(entry.amount != null ? entry.amount : "—")}</td>
          <td>${esc(entry.category || entry.account || "Journal")}</td>
          <td>${esc(entry.period || entry.createdAt || "—")}</td>
          <td>${actions}</td>
        </tr>`;
      })
      .join("");
    return `<div class="pv-table-wrap"><table class="pv-table pv-table--compact pv-table--striped">
      <thead><tr><th>Entry</th><th>Amount</th><th>Category</th><th>Period</th><th>Review</th></tr></thead>
      <tbody>${body}</tbody>
    </table></div>
    <div class="pv-journal-toolbar">
      <button type="button" class="pv-button" data-journal-approve-all="1">Approve all pending</button>
      <button type="button" class="pv-button" data-journal-export="1">Export approved CSV</button>
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
    return `<div class="pv-canvas-stack">
      ${canvasImportNotice(D ? D.documentsImportNotice() : null)}
      <div class="pv-canvas-metric-grid pv-canvas-metric-grid--hero">${kpis.map(canvasMetricTile).join("")}</div>
      ${sectionHead("Document sources", "Queue rows by import origin")}
      ${canvasPanel({
        title: "Source breakdown",
        accent: "cyan",
        widgetKey: wKey("documents", 0),
        body: canvasStatGrid(D ? D.documentsSourceBreakdown() : []),
      })}
      <div class="pv-canvas-grid-split">
        ${canvasPanel({
          title: wTitle("documents", 0),
          accent: "cyan",
          caption: "Document intake queue",
          widgetKey: wKey("documents", 0),
          body: queue.length ? canvasTable(["Document", "Category", "Amount", "Date"], queue, true) : canvasEmpty("Accounting documents will appear when the local document queue is populated."),
        })}
        ${canvasPanel({
          title: wTitle("documents", 1),
          accent: "cyan",
          widgetKey: wKey("documents", 1),
          body: `${canvasDocPreview(doc ? doc.vendor || doc.id || "Document" : "Document preview", doc && doc.pages ? doc.pages : 1)}${doc ? "" : canvasEmpty("Document preview will appear when a document is selected.")}`,
        })}
      </div>
      <div class="pv-canvas-grid-2">
        ${canvasPanel({
          title: wTitle("documents", 2),
          widgetKey: wKey("documents", 2),
          body: periodStats.length ? canvasStatGrid(periodStats) : canvasEmpty("Period close metrics will appear when documents are assigned to a period."),
        })}
        ${canvasPanel({
          title: wTitle("documents", 3),
          widgetKey: wKey("documents", 3),
          body: `${canvasStat(fmtClaim(ap.expenseTotal), "Expense total", "warning", wKey("documents", 3))}`,
        })}
      </div>
      ${canvasPanel({
        title: wTitle("documents", 4),
        caption: "Local journal queue",
        widgetKey: wKey("documents", 4),
        body: journalItems.length ? renderJournalQueuePanel(journalItems) : canvasEmpty("Journal posting queue is available in desktop mode."),
      })}
    </div>`;
  }

  function renderLibrary() {
    const D = dataApi();
    const kpis = D ? D.libraryKpis() : [];
    const rows = D ? D.libraryRows() : [];
    const doc = D ? D.firstLibraryDoc() : null;
    return `<div class="pv-canvas-stack">
      ${canvasImportNotice(D ? D.libraryImportNotice() : null)}
      <div class="pv-canvas-metric-grid pv-canvas-metric-grid--hero">${kpis.map(canvasMetricTile).join("")}</div>
      ${canvasSearch("Search contracts, compliance, vendors…", wKey("library", 0))}
      <div class="pv-canvas-grid-split">
        ${canvasPanel({
          title: wTitle("library", 0),
          accent: "gray",
          caption: "Local document library",
          widgetKey: wKey("library", 0),
          body: rows.length ? canvasTable(["Document", "Category", "Updated", "Expires"], rows, true) : canvasEmpty("Library documents will appear when local library data is indexed."),
        })}
        ${canvasPanel({
          title: "Preview",
          accent: "gray",
          widgetKey: wKey("library", 0),
          body: `${canvasDocPreview(doc ? doc.title || doc.name || "Document" : "Library preview", doc && doc.pages ? doc.pages : 1)}${doc ? "" : canvasEmpty("Select a library document to preview.")}`,
        })}
      </div>
    </div>`;
  }

  function taxUsageBar(segments, total, caption) {
    const sum = segments.reduce((acc, s) => acc + (Number(s.amount) || 0), 0);
    const denom = total || sum || 1;
    const bars = segments
      .map((s) => {
        const pct = Math.max(4, Math.round((Number(s.amount) / denom) * 100));
        const color = s.id === "federal" ? "#60a5fa" : s.id === "kansas" ? "#c084fc" : "#78a86b";
        return `<div class="pv-tax-split__seg" style="width:${pct}%;background:${color}" title="${esc(s.label)} ${esc(fmtTaxMoney(s.amount))}"></div>`;
      })
      .join("");
    const legend = segments
      .map((s) => `<span class="pv-tax-split__key"><i style="background:${s.id === "federal" ? "#60a5fa" : "#c084fc"}"></i>${esc(s.label)} · ${esc(fmtTaxMoney(s.amount))}</span>`)
      .join("");
    return `<div class="pv-tax-split"><div class="pv-tax-split__track">${bars}</div><div class="pv-tax-split__legend">${legend}</div>${caption ? `<p class="pv-tax-split__cap">${esc(caption)}</p>` : ""}</div>`;
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
      ? `<ul class="pv-tax-memo">${citations
          .map((id) => `<li><strong>${esc(id)}</strong><span>docs/hal_knowledge/memories.jsonl</span></li>`)
          .join("")}</ul>`
      : canvasEmpty("MemoAI tax citations appear when the tax engine runs.");
    const compBars =
      plan && plan.compScenarios
        ? `<div class="pv-vbars">${plan.compScenarios
            .map((s) => {
              const max = Math.max(...plan.compScenarios.map((x) => x.employerFica), 1);
              return `<div class="pv-vbar${s.selected ? " pv-vbar--active" : ""}"><span class="pv-vbar__fill" style="height:${Math.max(8, (s.employerFica / max) * 100)}%;background:#60a5fa"></span><span class="pv-vbar__lbl">${esc(fmtTaxMoney(s.salary))}</span></div>`;
            })
            .join("")}</div>`
        : canvasEmpty("Load QuickBooks P&amp;L to model compensation scenarios.");
    return `<div class="pv-canvas-stack pv-canvas-stack--taxes">
      ${canvasImportNotice(D ? D.taxesImportNotice() : null)}
      <div class="pv-tax-disclaimer">${esc(disclaimer)}</div>
      <div class="pv-canvas-metric-grid pv-canvas-metric-grid--hero">${kpis.map(canvasMetricTile).join("")}</div>
      ${sectionHead("Book → tax bridge", plan && plan.periodLabel ? plan.periodLabel : "QuickBooks import → 1120-S prep")}
      ${canvasPanel({
        title: "Book-to-tax bridge",
        accent: "blue",
        caption: plan ? `${plan.federalRateLabel} · ${plan.kansasRateLabel}` : "Planning rates",
        widgetKey: wKey("taxes", 0),
        body: bridge.length
          ? canvasTable(["Line item", "Amount"], bridge, true)
          : canvasEmpty("P&amp;L net income will drive the book-to-tax bridge when QuickBooks export is loaded."),
      })}
      <div class="pv-canvas-grid-split">
        ${canvasPanel({
          title: "Reasonable compensation scenarios",
          accent: "blue",
          caption: "Employer FICA by modeled W-2 · IRC §162",
          widgetKey: wKey("taxes", 0),
          body: `${compBars}${scenarios.length ? canvasTable(["W-2", "Est. K-1", "Employer FICA", "HAL note"], scenarios, true) : ""}`,
        })}
        ${canvasPanel({
          title: "Estimated owner tax split",
          accent: "blue",
          caption: "Federal + Kansas on K-1 flow-through",
          widgetKey: wKey("taxes", 0),
          body:
            split.length && totalTax
              ? taxUsageBar(split, totalTax, `Planning total ${fmtTaxMoney(totalTax)} · not a filed return`)
              : canvasEmpty("Tax split appears when book income is available."),
        })}
      </div>
      <div class="pv-canvas-grid-split">
        ${canvasPanel({
          title: "Quarterly estimates",
          accent: "blue",
          caption: "1040-ES + Kansas vouchers",
          widgetKey: wKey("taxes", 0),
          body: quarterly.length
            ? canvasTable(["Period", "Federal", "Kansas", "Due", "Status"], quarterly, true)
            : canvasEmpty("Quarterly plan appears when book income is available."),
        })}
        ${canvasPanel({
          title: "MemoAI evidence",
          accent: "green",
          caption: "Memories cited for this plan",
          widgetKey: wKey("taxes", 0),
          body: memoList,
        })}
      </div>
      ${sectionHead("Reference checklists", "Filing obligations · confirm with CPA")}
      <div class="pv-canvas-grid-split">
        ${canvasPanel({
          title: "Federal obligations",
          accent: "blue",
          widgetKey: wKey("taxes", 0),
          body: federal.length ? canvasTable(["Item", "Purpose", "Timing", "Notes"], federal, true) : canvasEmpty("—"),
        })}
        ${canvasPanel({
          title: "Kansas obligations",
          accent: "blue",
          widgetKey: wKey("taxes", 0),
          body: kansas.length ? canvasTable(["Item", "Purpose", "Timing", "Notes"], kansas, true) : canvasEmpty("—"),
        })}
      </div>
      ${canvasPanel({
        title: "Key deadlines",
        accent: "blue",
        caption: "Calendar-year S corp",
        widgetKey: wKey("taxes", 0),
        body: calendar.length ? canvasTable(["Date", "Jurisdiction", "Action"], calendar, true) : canvasEmpty("—"),
      })}
      ${sectionHead("Book cross-check", hasBook ? "Live import attached" : "Waiting on QuickBooks export")}
      <div class="pv-canvas-grid-split">
        ${canvasPanel({
          title: wTitle("taxes", 0),
          accent: "blue",
          widgetKey: wKey("taxes", 0),
          body: bookIncome.length
            ? canvasTable(["Account", "Amount", "Notes"], bookIncome, true)
            : canvasEmpty("P&amp;L rows will appear when QuickBooks export is loaded."),
        })}
        ${canvasPanel({
          title: wTitle("taxes", 1),
          accent: "blue",
          widgetKey: wKey("taxes", 1),
          body: ebitda.length
            ? canvasTable(["Adjustment", "Amount", "Reviewer", "Notes"], ebitda, true)
            : canvasEmpty("EBITDA add-backs will appear when expense categories are loaded."),
        })}
      </div>
      ${canvasPanel({
        title: "Related surfaces",
        widgetKey: wKey("taxes", 0),
        body: canvasNavPills(["financial", "quickbooks", "documents"]),
      })}
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
    return `<div class="pv-canvas-stack">
      ${canvasImportNotice(D ? D.officeManagerImportNotice() : null)}
      ${D && D.opsDataPanelHtml ? D.opsDataPanelHtml() : ""}
      <div class="pv-canvas-metric-grid pv-canvas-metric-grid--hero">${kpis.map(canvasMetricTile).join("")}</div>
      ${canvasPanel({
        title: wTitle("office-manager", 0),
        accent: "yellow",
        caption: "HAL office priorities",
        widgetKey: wKey("office-manager", 0),
        body: canvasKanbanLanes(kanbanLanes, wKey("office-manager", 0)),
      })}
      <div class="pv-canvas-grid-split">
        ${canvasPanel({
          title: "Office task queue",
          accent: "yellow",
          caption: D ? D.periodSubtitle() : "Local tasks",
          widgetKey: wKey("office-manager", 0),
          body: tasks.length ? canvasTable(["Due", "Category", "Task", "Status"], tasks, true) : canvasEmpty("Local office tasks will appear when HAL or staff create them."),
        })}
        ${canvasPanel({
          title: "Activity snapshot",
          widgetKey: wKey("office-manager", 0),
          body: timeline.length ? canvasTimeline(timeline) : canvasEmpty("Recent office activity will appear from local task updates."),
        })}
      </div>
      ${canvasPanel({
        title: wTitle("office-manager", 1),
        caption: "Jump to staff work surfaces",
        widgetKey: wKey("office-manager", 1),
        body: canvasNavPills(staffPages),
      })}
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
    activePageId = pageId;
    activeFeed = feed || null;
    activeSnapshot = programSnapshot || null;
    const D = dataApi();
    if (D) D.bind(activeFeed, activeSnapshot);
    const fn = RENDERERS[pageId];
    return fn ? fn() : "";
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
