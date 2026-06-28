/**
 * NewRidgeFinancial 2.0 — program pages built from shared UI components + Services.
 * Visual layout matches PNG mockups; data comes from the service layer (seeded once,
 * then persisted). Interactive pages support real CRUD, validation, and async states.
 */
const PageViews = (function () {
  function resolveUI() {
    if (typeof UI !== "undefined") return UI;
    if (typeof window !== "undefined" && window.UI) return window.UI;
    try {
      return require("./components.js");
    } catch {
      return null;
    }
  }
  function resolveSvc() {
    if (typeof Services !== "undefined") return Services;
    if (typeof window !== "undefined" && window.Services) return window.Services;
    try {
      return require("./services.js");
    } catch {
      return null;
    }
  }
  const U = resolveUI();
  const Svc = resolveSvc();

  const PAGE_OUTLINES = {
    financial: { eyebrow: "Owner financial dashboard", subtitle: "Mission control for practice performance.", chips: ["Read-only review", "No writeback"] },
    softdent: { eyebrow: "SoftDent", subtitle: "System of Record: SoftDent", chips: ["Read-only", "No writeback"] },
    quickbooks: { eyebrow: "QuickBooks", subtitle: "Financials synced from QuickBooks Online (Read-Only)", chips: ["Read-only sync", "Owner review"] },
    ar: { eyebrow: "A/R & collections", subtitle: "Accounts receivable and collections oversight.", chips: ["SoftDent read-only", "No payer contact"] },
    claims: { eyebrow: "Patient claims workbench", subtitle: "Intelligent claim lifecycle management and readiness control.", chips: ["Local-only", "Human review required", "No payer submission"] },
    narratives: { eyebrow: "Insurance narratives", subtitle: "Compose and manage insurance narratives with full control and visibility.", chips: ["Draft only", "Human review required", "No writeback"] },
    documents: { eyebrow: "Accounting documents", subtitle: "Document intake, review, and posting queue management.", chips: ["Review-gated", "Journal draft only"] },
    library: { eyebrow: "Document library", subtitle: "Centralized repository for mission critical documents and resources.", chips: ["Policies", "Statements", "Claims", "Clinical", "Reports"] },
    "office-manager": { eyebrow: "Office Manager", subtitle: "Staff oversight and work-surface coordination.", chips: ["Staff oversight", "Read-only", "Approval required"] },
    hal: { eyebrow: "HAL Command Center", subtitle: "Direct. Orchestrate. Protect.", chips: ["Local manager", "Read-only", "External firewall"] },
  };

  const MOCK_IMAGES = {};

  const MOCK_NAV = [
    ["financial", "Financial Dashboard"],
    ["softdent", "SoftDent"],
    ["quickbooks", "QuickBooks"],
    ["ar", "A/R & Collections"],
    ["claims", "Claims Workbench"],
    ["narratives", "Insurance Narratives"],
    ["documents", "Accounting Documents"],
    ["library", "Document Library"],
    ["hal", "HAL Command Center"],
  ];

  function esc(v) {
    return U ? U.esc(v) : String(v == null ? "" : v);
  }

  function registryEntry(halData, pageId) {
    return ((halData && halData.registry) || []).find((e) => e.id === pageId) || null;
  }

  function buildPageState(halData, pageId) {
    const outline = PAGE_OUTLINES[pageId] || null;
    const reg = registryEntry(halData, pageId);
    return {
      pageId,
      title: (reg && reg.name) || (outline && outline.eyebrow) || pageId,
      eyebrow: (outline && outline.eyebrow) || "Program page",
      subtitle: (outline && outline.subtitle) || (reg && reg.purpose) || "",
      chips: (outline && outline.chips) || [],
      safety: (reg && reg.safety) || "Read-only · No writeback",
      registryState: (reg && reg.state) || "unknown",
      dataSource: "services",
      seedDataUsed: true,
    };
  }

  function stateTone(state) {
    const v = String(state || "").toLowerCase();
    if (v === "ready") return "ok";
    if (v === "blocked") return "red";
    if (v.includes("review")) return "warn";
    return "muted";
  }

  /* ---- Shared page shell ---- */
  function pageShell(state, body, extraClass) {
    return `
      <article class="pv pv--${esc(state.pageId)} pv--app${extraClass ? " " + esc(extraClass) : ""}" data-pv-page="${esc(state.pageId)}">
        ${body}
      </article>`;
  }

  function topBar(state, actions, safetyOverride) {
    if (!U) return "";
    const allActions = actions || [];
    return U.TopBar({
      title: state.title,
      subtitle: state.subtitle,
      safety: safetyOverride || state.safety,
      demo: true,
      actions: allActions || [],
    });
  }

  function toolbarDate(label) {
    return U ? U.Button({ label, icon: "📅", variant: "toolbar", disabled: true }) : "";
  }

  function toolbarBtn(label, icon, attrs) {
    return U ? U.Button({ label, icon, variant: "toolbar", attrs: attrs || {} }) : "";
  }

  function badge(text, tone) {
    return U ? U.StatusBadge(text, tone) : esc(text);
  }

  function card(title, body, cls, headRight) {
    return U ? U.Card({ title, body, className: cls, headRight }) : body;
  }

  /* ---- Chart / visualization helpers (render real service data) ---- */
  function trendClass(dir) {
    if (dir === "up") return "pv-trend--up";
    if (dir === "down") return "pv-trend--down";
    return "";
  }

  function svgSparkline(values, color) {
    if (!values || !values.length) return "";
    const w = 120, h = 36, min = Math.min(...values), max = Math.max(...values), range = max - min || 1;
    const pts = values.map((v, i) => `${((i / (values.length - 1)) * w).toFixed(1)},${(h - ((v - min) / range) * (h - 4) - 2).toFixed(1)}`).join(" ");
    return `<svg class="pv-spark" viewBox="0 0 ${w} ${h}" aria-hidden="true"><polyline fill="none" stroke="${color || "#d6b15e"}" stroke-width="2" points="${pts}"/></svg>`;
  }

  function svgLineChart(series, labels, height) {
    const h = height || 180, w = 480, pad = { t: 12, r: 12, b: 28, l: 48 };
    const all = series.flatMap((s) => s.values), min = Math.min(...all) * 0.95, max = Math.max(...all) * 1.05, range = max - min || 1;
    const innerW = w - pad.l - pad.r, innerH = h - pad.t - pad.b;
    const xAt = (i, len) => pad.l + (i / (len - 1)) * innerW;
    const yAt = (v) => pad.t + innerH - ((v - min) / range) * innerH;
    const grid = [0, 0.25, 0.5, 0.75, 1].map((t) => {
      const y = pad.t + innerH * (1 - t);
      return `<line x1="${pad.l}" y1="${y}" x2="${w - pad.r}" y2="${y}" class="pv-chart-line"/><text x="${pad.l - 6}" y="${y + 4}" class="pv-chart-axis" text-anchor="end">${Math.round((min + range * t) / 1000)}K</text>`;
    }).join("");
    const paths = series.map((s) => {
      const d = s.values.map((v, i) => `${i ? "L" : "M"}${xAt(i, s.values.length).toFixed(1)},${yAt(v).toFixed(1)}`).join(" ");
      return `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="2.5"${s.dashed ? ' stroke-dasharray="6 4"' : ""}/>`;
    }).join("");
    const xLabels = (labels || []).filter((_, i, arr) => i % Math.ceil(arr.length / 6) === 0 || i === arr.length - 1)
      .map((label) => `<text x="${xAt(labels.indexOf(label), labels.length)}" y="${h - 6}" class="pv-chart-axis" text-anchor="middle">${esc(label)}</text>`).join("");
    return `<svg class="pv-svg-chart" viewBox="0 0 ${w} ${h}" role="img">${grid}${paths}${xLabels}</svg>`;
  }

  function conicDonut(slices, center, size) {
    const sz = size || 160;
    let acc = 0;
    const stops = slices.map((s) => { const start = acc; acc += s.pct; return `${s.color} ${start}% ${acc}%`; });
    const legend = slices.map((s) => `<div class="pv-legend__row"><span class="pv-legend__dot" style="background:${s.color}"></span><span>${esc(s.label)}</span><strong>${esc(s.amount || s.pct + "%")}</strong>${s.pct != null && s.amount ? `<em>${s.pct}%</em>` : ""}</div>`).join("");
    return `<div class="pv-donut-wrap"><div class="pv-donut-chart" style="width:${sz}px;height:${sz}px;background:conic-gradient(${stops.join(", ")})"><div class="pv-donut-chart__hole">${center || ""}</div></div><div class="pv-legend">${legend}</div></div>`;
  }

  function hBarChart(items, valueKey, labelKey, pctKey) {
    const max = Math.max(...items.map((i) => i[pctKey] || 0), 1);
    return `<div class="pv-hbars">${items.map((item) => {
      const pct = item[pctKey] || 0;
      return `<div class="pv-hbar"><span class="pv-hbar__label">${esc(item[labelKey])}</span><div class="pv-hbar__track"><span class="pv-hbar__fill" style="width:${(pct / max) * 100}%"></span></div><span class="pv-hbar__val">${esc(item[valueKey])}</span><span class="pv-hbar__pct">${pct}%</span></div>`;
    }).join("")}</div>`;
  }

  function vBarChart(labels, values, color) {
    const max = Math.max(...values, 1);
    return `<div class="pv-vbars">${values.map((v, i) => `<div class="pv-vbar"><span class="pv-vbar__fill" style="height:${Math.max(8, (v / max) * 100)}%;background:${color || "#d6b15e"}"></span><span class="pv-vbar__lbl">${esc(labels[i] || "")}</span></div>`).join("")}</div>`;
  }

  function kpiRow(kpis) {
    return `<div class="pv-kpi-row pv-kpi-row--${Math.min(kpis.length, 5)}">${kpis.map((k) => {
      const tone = k.tone ? ` pv-kpi--${k.tone}` : "";
      const trend = k.trend ? `<span class="pv-trend ${trendClass(k.trendDir)}">${esc(k.trend)}</span>` : "";
      const sub = k.sub ? `<span class="pv-kpi__sub">${esc(k.sub)}</span>` : "";
      const spark = k.spark ? svgSparkline(k.spark, "#d6b15e") : "";
      return `<article class="pv-kpi pv-kpi--rich${tone}"><span class="pv-kpi__label">${esc(k.label)}</span><strong class="pv-kpi__value">${esc(k.value)}</strong>${trend}${sub}${spark}</article>`;
    }).join("")}</div>`;
  }

  function pageFooter(left, right) {
    return `<footer class="pv-page-foot"><span>${left || ""}</span><span>${right || ""}</span></footer>`;
  }

  /* ---- Mount helper ---- */
  async function mountPage(container, state, renderFn, onNavigate) {
    if (!container) return;
    const slotId = `pv-body-${state.pageId}`;
    container.innerHTML = pageShell(state, `<div class="pv-body" id="${slotId}">${U ? U.LoadingState({ label: "Loading page data…" }) : "Loading…"}</div>`);
    wireCommon(container, state, onNavigate, () => mountPage(container, state, renderFn, onNavigate));

    const slot = container.querySelector(`#${slotId}`);
    try {
      if (!Svc) throw new Error("Services layer unavailable");
      const html = await renderFn(state, slot);
      if (slot) slot.innerHTML = html;
    } catch (err) {
      if (slot) slot.innerHTML = U ? U.ErrorState({ message: err.message || String(err), title: "Unable to load page" }) : esc(err.message);
      const retry = slot && slot.querySelector("[data-retry]");
      if (retry) retry.addEventListener("click", () => mountPage(container, state, renderFn, onNavigate));
    }
  }

  function wireCommon(container, state, onNavigate, refresh) {
    container.querySelectorAll("[data-pv-nav]").forEach((btn) => btn.addEventListener("click", () => onNavigate && onNavigate(btn.getAttribute("data-pv-nav"))));
    const ref = container.querySelector("[data-pv-refresh]");
    if (ref) ref.addEventListener("click", refresh);
  }

  function wireModal(container) {
    container.querySelectorAll("[data-modal-close]").forEach((el) => {
      el.addEventListener("click", () => {
        const id = el.getAttribute("data-modal-close");
        const modal = container.querySelector(`#${id}`);
        if (modal) { modal.classList.remove("pv-modal--open"); modal.setAttribute("aria-hidden", "true"); }
      });
    });
  }

  /* ============ Page renderers ============ */

  /* Fixed-scale money area chart for the Production MTD card. */
  function finAreaChart(values, maxVal) {
    const w = 320, h = 116, pad = { t: 8, r: 6, b: 6, l: 6 };
    const max = maxVal || Math.max(...values), min = 0, range = max - min || 1;
    const innerW = w - pad.l - pad.r, innerH = h - pad.t - pad.b;
    const xAt = (i) => pad.l + (i / (values.length - 1)) * innerW;
    const yAt = (v) => pad.t + innerH - ((v - min) / range) * innerH;
    const line = values.map((v, i) => `${i ? "L" : "M"}${xAt(i).toFixed(1)},${yAt(v).toFixed(1)}`).join(" ");
    const area = `${line} L${xAt(values.length - 1).toFixed(1)},${(pad.t + innerH).toFixed(1)} L${pad.l},${(pad.t + innerH).toFixed(1)} Z`;
    return `<svg class="pv-fin-area" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img" aria-label="Production MTD trend">
      <defs><linearGradient id="finProdFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="rgba(214,177,94,0.35)"/><stop offset="100%" stop-color="rgba(214,177,94,0)"/></linearGradient></defs>
      <path d="${area}" fill="url(#finProdFill)"/>
      <path d="${line}" fill="none" stroke="#d6b15e" stroke-width="2"/>
    </svg>`;
  }

  /* Fixed-scale dual-line chart for the 12-Month Trend card. */
  function finTrendChart(production, average, maxVal) {
    const w = 460, h = 150, pad = { t: 8, r: 8, b: 6, l: 6 };
    const max = maxVal || Math.max(...production, ...average), min = 0, range = max - min || 1;
    const innerW = w - pad.l - pad.r, innerH = h - pad.t - pad.b;
    const xAt = (i, len) => pad.l + (i / (len - 1)) * innerW;
    const yAt = (v) => pad.t + innerH - ((v - min) / range) * innerH;
    const grid = [0, 1, 2, 3, 4, 5, 6].map((t) => { const y = pad.t + (innerH * t) / 6; return `<line x1="${pad.l}" y1="${y.toFixed(1)}" x2="${w - pad.r}" y2="${y.toFixed(1)}" class="pv-chart-line"/>`; }).join("");
    const path = (vals) => vals.map((v, i) => `${i ? "L" : "M"}${xAt(i, vals.length).toFixed(1)},${yAt(v).toFixed(1)}`).join(" ");
    const dots = production.map((v, i) => `<circle cx="${xAt(i, production.length).toFixed(1)}" cy="${yAt(v).toFixed(1)}" r="2.6" fill="#d6b15e"/>`).join("");
    return `<svg class="pv-fin-line" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img" aria-label="12 month production trend">
      ${grid}
      <path d="${path(average)}" fill="none" stroke="#64748b" stroke-width="2" stroke-dasharray="5 4"/>
      <path d="${path(production)}" fill="none" stroke="#d6b15e" stroke-width="2.5"/>
      ${dots}
    </svg>`;
  }

  function trendArrow(dir) {
    return dir === "down" ? "↓" : "↑";
  }

  async function renderFinancial(state) {
    const d = await Svc.readDashboard("financial");
    const p = d.productionMtd;

    const prodCard = `
      <section class="pv-card pv-fin-prod">
        <div class="pv-card__head"><h3>Production MTD <i class="pv-info">ⓘ</i></h3></div>
        <div class="pv-fin-prod__grid">
          <div class="pv-fin-prod__left">
            <strong class="pv-fin-prod__value">${esc(p.value)}</strong>
            <div class="pv-fin-prod__delta"><span class="pv-trend pv-trend--${esc(p.trendDir)}">${trendArrow(p.trendDir)} ${esc(p.trend)}</span></div>
            <span class="pv-fin-prod__vs">${esc(p.vs)}</span>
          </div>
          <div class="pv-fin-prod__chart">
            <div class="pv-fin-prod__y">${p.chart.yLabels.map((l) => `<span>${esc(l)}</span>`).join("")}</div>
            <div class="pv-fin-prod__plot">
              ${finAreaChart(p.chart.values, 1500)}
              <div class="pv-fin-prod__x">${p.chart.xLabels.map((l) => `<span>${esc(l)}</span>`).join("")}</div>
            </div>
          </div>
        </div>
      </section>`;

    const metricCol = (m) => `
      <div class="pv-fin-metric">
        <span class="pv-fin-metric__label">${esc(m.label)} <i class="pv-info">ⓘ</i></span>
        <strong class="pv-fin-metric__value pv-kpi--${esc(m.tone)}">${esc(m.value)}</strong>
        <span class="pv-trend pv-trend--${esc(m.trendDir)}">${trendArrow(m.trendDir)} ${esc(m.trend)}</span>
        <span class="pv-fin-metric__vs">${esc(m.vs)}</span>
        <div class="pv-fin-metric__sub">
          <span class="pv-fin-metric__sublabel">${esc(m.subLabel)}</span>
          <span class="pv-fin-metric__subval">${esc(m.subValue)} <em class="pv-trend pv-trend--${esc(m.subTrendDir)}">${esc(m.subTrend)}</em></span>
        </div>
      </div>`;
    const metricsCard = `<section class="pv-card pv-fin-metrics">${d.metrics.map(metricCol).join("")}</section>`;

    const t = d.productionTrend;
    const ytd = t.ytd.map((y) => `<div class="pv-ytd"><span>${esc(y.label)}</span><strong>${esc(y.value)}</strong><em class="pv-trend pv-trend--${esc(y.trendDir)}">${trendArrow(y.trendDir)} ${esc(y.trend)}</em></div>`).join("");
    const trendCard = card(
      "Production — 12 Month Trend",
      `<div class="pv-fin-trend">
        <div class="pv-fin-trend__y">${t.yLabels.map((l) => `<span>${esc(l)}</span>`).join("")}</div>
        <div class="pv-fin-trend__plot">${finTrendChart(t.production, t.average, 1400)}<div class="pv-fin-trend__x">${t.labels.map((l) => `<span>${esc(l)}</span>`).join("")}</div></div>
      </div>
      <div class="pv-fin-legend"><span><i class="pv-swatch" style="background:#d6b15e"></i> Production</span><span><i class="pv-swatch pv-swatch--dash" style="background:#64748b"></i> 12 Mo. Avg.</span></div>
      <div class="pv-ytd-row">${ytd}</div>`,
      "pv-card--chart",
    );

    const pm = d.payerMix;
    let acc = 0;
    const stops = pm.slices.map((s) => { const a = acc; acc += s.pct; return `${s.color} ${a}% ${acc}%`; }).join(", ");
    const payerLegend = pm.slices.map((s) => `<div class="pv-payer"><span class="pv-payer__dot" style="background:${s.color}"></span><span class="pv-payer__label">${esc(s.label)}</span><span class="pv-payer__vals"><strong class="pv-payer__pct" style="color:${s.color}">${s.pct}%</strong><em class="pv-payer__amt">${esc(s.amount)}</em></span></div>`).join("");
    const payerCard = card(
      "Payer Mix — MTD Collections",
      `<div class="pv-payer-wrap">
        <div class="pv-donut-chart" style="background:conic-gradient(${stops})"><div class="pv-donut-chart__hole"><strong>${esc(pm.total)}</strong><span>Total</span></div></div>
        <div class="pv-payer-legend">${payerLegend}</div>
      </div>
      <div class="pv-payer-foot"><span>INSURANCE COLLECTION RATE</span><strong>${esc(pm.rate)}</strong><em class="pv-trend pv-trend--up">${esc(pm.rateTrend)}</em></div>`,
      "pv-card--donut",
    );

    const prov = d.providers;
    const provMax = Math.max(...prov.rows.map((r) => r.pct), 1);
    const provBars = prov.rows.map((r) => `<div class="pv-hbar"><span class="pv-hbar__label">${esc(r.name)}</span><div class="pv-hbar__track"><span class="pv-hbar__fill" style="width:${(r.pct / provMax) * 100}%"></span></div><span class="pv-hbar__val">${esc(r.amount)}</span><span class="pv-hbar__pct">${r.pct}%</span></div>`).join("");
    const providerCard = card(
      "Production by Provider — MTD",
      `<div class="pv-hbars">${provBars}</div><div class="pv-total-row"><span>Total</span><strong>${esc(prov.total.amount)}</strong><em>${prov.total.pct}%</em></div>`,
      "pv-card--bars",
    );

    const freshCells = d.freshness.map((f) => {
      const ok = f.status === "Synced";
      return `<article class="pv-fresh-cell">
        <span class="pv-fresh-cell__sys">${esc(f.system)}</span>
        <span class="pv-fresh-cell__status ${ok ? "pv-fresh-cell__status--ok" : "pv-fresh-cell__status--warn"}">${ok ? "✓" : "⚠"} ${esc(f.status)}</span>
        <span class="pv-fresh-cell__date">${esc(f.date)} ${esc(f.time)}</span>
        <span class="pv-fresh-cell__freq">(${esc(f.freq)})</span>
      </article>`;
    }).join("");
    const freshCard = card("Data Freshness", `<div class="pv-fresh-cards">${freshCells}</div>`, "pv-card--half");

    const qualityCats = d.quality.categories.map((c) => `<div class="pv-qcat"><span>✓ ${esc(c.label)}</span><strong>${c.score}/100</strong></div>`).join("");
    const qualityCard = card(
      "Data Quality Score",
      `<div class="pv-quality"><div class="pv-quality__ring pv-quality__ring--green"><strong>${d.quality.score}</strong><span>/100</span></div><div class="pv-quality__cats">${qualityCats}</div></div><a class="pv-gold-link" href="#">View Data Quality →</a>`,
      "pv-card--half",
    );

    const header = U.TopBar({
      title: "Owner Financial Dashboard",
      subtitle: state.subtitle,
      safety: state.safety,
      demo: true,
      actions: [toolbarDate(d.dateRange), toolbarBtn(d.compareRange, "▾"), toolbarBtn("Filters", "⛃")],
    });
    return `
      ${header}
      <div class="pv-fin-top">${prodCard}${metricsCard}</div>
      <div class="pv-bento pv-bento--financial">
        ${trendCard}
        ${payerCard}
        ${providerCard}
        ${freshCard}
        ${qualityCard}
      </div>
      ${pageFooter(`<em>${esc(d.footer.disclaimer)}</em>`, `Last refreshed: ${esc(d.footer.refreshed)} ↻`)}
    `;
  }

  function softdentSparkline(values) {
    const w = 260, h = 78, pad = { t: 6, r: 4, b: 4, l: 4 };
    const min = Math.min(...values) * 0.92, max = Math.max(...values) * 1.04, range = max - min || 1;
    const innerW = w - pad.l - pad.r, innerH = h - pad.t - pad.b;
    const xAt = (i) => pad.l + (i / (values.length - 1)) * innerW;
    const yAt = (v) => pad.t + innerH - ((v - min) / range) * innerH;
    const line = values.map((v, i) => `${i ? "L" : "M"}${xAt(i).toFixed(1)},${yAt(v).toFixed(1)}`).join(" ");
    const area = `${line} L${xAt(values.length - 1).toFixed(1)},${(pad.t + innerH).toFixed(1)} L${pad.l},${(pad.t + innerH).toFixed(1)} Z`;
    return `<svg class="pv-softdent-spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-label="Daysheet A/R trend">
      <defs><linearGradient id="sdHeroFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="rgba(214,177,94,0.34)"/><stop offset="100%" stop-color="rgba(214,177,94,0)"/></linearGradient></defs>
      <path d="${area}" fill="url(#sdHeroFill)"/><path d="${line}" fill="none" stroke="#d6b15e" stroke-width="2.4"/>
    </svg>`;
  }

  async function renderSoftdent(state) {
    const d = await Svc.readDashboard("softdent");
    const header = U.TopBar({
      title: "SoftDent",
      subtitle: `System of Record: ${d.source || "SoftDent"}`,
      safety: state.safety,
      demo: true,
      actions: [toolbarDate(d.date), toolbarBtn("Filters", "⛃"), toolbarBtn("⋯", "")],
    });

    const hero = `<section class="pv-card pv-sd-hero">
      <div class="pv-card__head"><h3>${esc(d.hero.label)} <i class="pv-info">ⓘ</i></h3><span class="pv-trend pv-trend--${esc(d.hero.trendDir)}">↑ ${esc(d.hero.trend)}</span></div>
      <div class="pv-sd-hero__body">
        <div class="pv-sd-hero__value"><strong>${esc(d.hero.value)}</strong><span>${esc(d.hero.subtitle)}</span></div>
        <div class="pv-sd-hero__spark">${softdentSparkline(d.hero.spark || [1, 2, 3])}</div>
      </div>
      <div class="pv-sd-submetrics">${d.subMetrics.map((m) => `<div><span>${esc(m.label)}</span><strong>${esc(m.value)}</strong></div>`).join("")}</div>
    </section>`;

    const agingColors = ["#78a86b", "#d6b15e", "#f0a868", "#e97854", "#8b5cf6"];
    let agingAcc = 0;
    const agingStops = d.aging.map((a, i) => { const start = agingAcc; agingAcc += a.pct; return `${agingColors[i]} ${start}% ${agingAcc}%`; }).join(", ");
    const agingRows = d.aging.map((a, i) => `<div class="pv-sd-aging-row"><span><i style="background:${agingColors[i]}"></i>${esc(a.bucket)}</span><strong>${esc(a.amount)}</strong><em>${a.pct}%</em></div>`).join("");
    const agingCard = `<section class="pv-card pv-sd-aging">
      <div class="pv-card__head"><h3>A/R Aging Buckets <i class="pv-info">ⓘ</i></h3></div>
      <div class="pv-sd-aging__grid">
        <div class="pv-sd-aging__rows">${agingRows}<div class="pv-sd-aging-row pv-sd-aging-row--total"><span>Total</span><strong>${esc(d.hero.value)}</strong><em>100%</em></div></div>
        <div class="pv-donut-chart pv-sd-aging__donut" style="background:conic-gradient(${agingStops})"><div class="pv-donut-chart__hole"><strong>${esc(d.hero.value)}</strong><span>Total A/R</span></div></div>
      </div>
    </section>`;

    const resp = d.responsibility;
    const respStops = `#3f73e6 0% ${resp.insurance.pct}%, #d6b15e ${resp.insurance.pct}% 100%`;
    const responsibilityCard = `<section class="pv-card pv-sd-resp">
      <div class="pv-card__head"><h3>Insurance vs Patient Responsibility <i class="pv-info">ⓘ</i></h3></div>
      <div class="pv-sd-resp__grid">
        <div class="pv-donut-chart pv-sd-resp__donut" style="background:conic-gradient(${respStops})"><div class="pv-donut-chart__hole"><strong>${esc(resp.total)}</strong><span>Total A/R</span></div></div>
        <div class="pv-sd-resp__legend">
          <div><span><i style="background:#3f73e6"></i>Insurance</span><strong>${esc(resp.insurance.amount)}</strong><em>${resp.insurance.pct}%</em></div>
          <div><span><i style="background:#d6b15e"></i>Patient Responsibility</span><strong>${esc(resp.patient.amount)}</strong><em>${resp.patient.pct}%</em></div>
          <footer><span>Est. Collectability (Patient)</span><strong>${esc(resp.collectability)}</strong><span>Est. Collectable</span><strong>${esc(resp.collectable)}</strong></footer>
        </div>
      </div>
    </section>`;

    const sourceHealth = `<section class="pv-card pv-sd-health">
      <div class="pv-card__head"><h3>Source Health <span>(Read-Only)</span> <i class="pv-info">ⓘ</i></h3></div>
      <div class="pv-sd-health__grid">
        <div class="pv-sd-shield">♢</div>
        <div class="pv-sd-health__rows">${d.health.map((h) => `<div><span>✓ ${esc(h.label)}</span><strong>${esc(h.value)}</strong></div>`).join("")}</div>
      </div>
      <p class="pv-sd-readonly">This is a read-only connection.<br/>All data is sourced from SoftDent.</p>
    </section>`;

    const glanceIcons = ["♧", "♤", "⌄", "▣", "$", "⇩"];
    const glance = `<section class="pv-card pv-sd-glance">
      <div class="pv-card__head"><h3>At a Glance <i class="pv-info">ⓘ</i></h3></div>
      <div class="pv-sd-glance__rows">${d.glance.map((g, i) => `<div><span>${glanceIcons[i] || "•"} ${esc(g.label)}</span><strong>${esc(g.value)}</strong></div>`).join("")}</div>
    </section>`;

    const exportRows = d.exports.map((e) => [
      esc(e.name),
      esc(e.source),
      esc(e.dataset),
      badge(e.status, "ok"),
      esc(e.completed),
      esc(e.records),
      esc(e.size),
      `<span class="pv-table-actions">⇩  ▤</span>`,
    ]);
    const exportsCard = card(
      "Recent Exports",
      U.Table({ columns: ["Export Name", "Source", "Data Set", "Status", "Completed", "Records", "File Size", "Actions"], rows: exportRows }) + `<a class="pv-gold-link pv-sd-export-link" href="#">View all exports →</a>`,
      "pv-card--wide pv-sd-exports",
    );

    return `
      ${header}
      <div class="pv-bento pv-bento--softdent">
        ${hero}
        ${agingCard}
        ${responsibilityCard}
        ${sourceHealth}
        ${glance}
        ${exportsCard}
      </div>`;
  }

  async function renderQuickbooks(state) {
    const d = await Svc.readDashboard("quickbooks");
    const plList = `<div class="pv-pl">${d.pl.rows
      .map(
        (r) =>
          `<div class="pv-pl__row${r.highlight ? " pv-pl__row--net" : ""}">
            <span class="pv-pl__cat">${esc(r.category)}</span>
            <span class="pv-pl__amt">${esc(r.amount)}</span>
            <span class="pv-pl__chg ${r.changeTone === "up" ? "pv-trend--up" : "pv-trend--down"}">${esc(r.change)}${r.sub ? `<small>${esc(r.sub)}</small>` : ""}</span>
          </div>`,
      )
      .join("")}</div>`;
    const ebitdaRows = d.ebitdaCandidates.map((r) => [esc(r.desc), esc(r.amount), badge(r.type, r.typeTone), `<a class="pv-gold-link" href="#">Review</a>`]);
    const syncRows = Object.entries(d.sync).map(([k, v]) => `<div class="pv-sync-row"><span>${esc(k.replace(/([A-Z])/g, " $1"))}</span><strong>${k === "status" ? badge(v, "ok") : esc(v)}</strong></div>`).join("");
    return `
      ${topBar(state, [`<span class="pv-sync-badge">${badge(d.syncStatus, "ok")} Last sync: ${esc(d.lastSync)}</span>`, toolbarBtn("View in QuickBooks", "↗")])}
      <div class="pv-bento pv-bento--quickbooks">
        ${card(`P&L Summary (YTD)`, `<span class="pv-card-range">${esc(d.pl.range)}</span>` + plList, "pv-card--pl")}
        ${card("Monthly Expenses", `<span class="pv-card-range">Last 12 Months</span>` + vBarChart(d.monthlyExpenses.labels, d.monthlyExpenses.values) + `<span class="pv-legend-inline"><i style="background:#d6b15e"></i> Operating Expenses</span>`, "pv-card--bars")}
        ${card("Expense Categories (YTD)", conicDonut(d.expenseCategories.slices, `<strong>${esc(d.expenseCategories.total)}</strong><span>Total</span>`) + `<a class="pv-gold-link" href="#">View all categories →</a>`, "pv-card--cats")}
        ${card("EBITDA Candidates", `<p class="pv-muted">Expenses that may be add-backs for EBITDA normalization</p>` + U.Table({ columns: ["Category / Description", "YTD Amount", "Type", "Action"], rows: ebitdaRows }) + `<div class="pv-total-row"><span>Total Potential Add-Backs</span><strong class="pv-gold">${esc(d.ebitdaTotal)}</strong></div><a class="pv-gold-link" href="#">Manage EBITDA Adjustments →</a>`, "pv-card--wide")}
        ${card("QuickBooks Sync", syncRows + `<p class="pv-lock-note">🔒 This is a read-only connection. No data is written to QuickBooks.</p><a class="pv-gold-link" href="#">Manage Integration →</a>`, "pv-card--sync")}
      </div>`;
  }

  async function renderAr(state) {
    const d = await Svc.readDashboard("ar");
    const agingCards = d.aging.map((a) => `<article class="pv-aging-card${a.active ? " pv-aging-card--active" : ""}" data-aging-bucket="${esc(a.label)}"><span>${esc(a.label)}</span><strong>${esc(a.amount)}</strong><em>${a.pct}%</em>${svgSparkline([a.pct, a.pct * 0.9, a.pct * 1.1, a.pct], "#d6b15e")}</article>`).join("");
    const claimRows = d.topClaims.map((c) => [esc(c.claim), esc(c.patient), esc(c.insurance), esc(c.dos), esc(c.billed), esc(c.outstanding), `<span class="pv-days-warn">${c.days}</span>`]);
    const followUp = d.followUp.map((f) => `<div class="pv-follow"><div class="pv-follow__head"><span class="pv-follow__dot pv-follow__dot--${f.tone}"></span><strong>${esc(f.status)}</strong><span>${f.count} total</span><a class="pv-gold-link" href="#">View All</a></div>${f.items.map((i) => `<div class="pv-follow__item"><span>${esc(i.label)}</span><em>${i.count} claims</em><span class="pv-chev">›</span></div>`).join("")}</div>`).join("");
    return `
      ${topBar(state, [toolbarDate(d.dateRange), toolbarBtn("Filters", "⛃"), toolbarBtn("Export", "⬆")])}
      ${kpiRow(d.kpis)}
      <div class="pv-bento pv-bento--ar">
        ${card("Aging Buckets", `<div class="pv-aging-cards">${agingCards}</div>`)}
        ${card("Collections Trend", svgLineChart([{ values: d.collectionsTrend.current, color: "#d6b15e" }, { values: d.collectionsTrend.prior, color: "#64748b", dashed: true }], d.collectionsTrend.labels) + `<span class="pv-legend-inline"><i style="background:#d6b15e"></i> Collections <i style="background:#64748b"></i> Prior 30 Days</span>`, "pv-card--chart")}
        ${card("Top Outstanding Claims", U.Table({ columns: ["Claim #", "Patient", "Insurance", "DOS", "Billed", "Outstanding", "Days"], rows: claimRows }) + `<a class="pv-gold-link" href="#">View All Claims ›</a>`, "pv-card--wide")}
        ${card("Follow-up Queue", followUp)}
      </div>`;
  }

  /* ---- Claims (interactive CRUD) ---- */
  function claimCardHtml(c, selected) {
    return `<article class="pv-claim-card${selected ? " pv-claim-card--selected" : ""}" data-claim-id="${esc(c.id)}" tabindex="0"><div class="pv-claim-card__head"><strong>${esc(c.id)}</strong>${c.tag ? badge(c.tag, c.tagTone) : ""}</div><span>${esc(c.patient)} · DOB ${esc(c.dob)}</span><span>${esc(c.procedure)} · ${esc(c.amount)}</span><em>${esc(c.age || "")}</em></article>`;
  }

  function claimsBody(state, data, selectedId) {
    const lanes = ["Draft", "Needs Review", "Ready", "Denied"];
    const byLane = Object.fromEntries(lanes.map((l) => [l, []]));
    (data.claims || []).forEach((c) => { if (byLane[c.status]) byLane[c.status].push(c); });
    const kanban = lanes.map((name) => {
      const tone = name === "Denied" ? "red" : name === "Ready" ? "ok" : name === "Needs Review" ? "warn" : "muted";
      const cards = byLane[name] || [];
      return `<div class="pv-lane pv-lane--${tone}"><div class="pv-lane__title"><span>${esc(name)}</span><strong>${cards.length}</strong></div>${cards.map((c) => claimCardHtml(c, c.id === selectedId)).join("")}</div>`;
    }).join("");
    const claimRec = (data.claims || []).find((c) => c.id === selectedId);
    const det = (data.detailById || {})[selectedId] || (claimRec
      ? { id: claimRec.id, patient: claimRec.patient, dob: claimRec.dob, age: "—", insurance: "—", billed: claimRec.amount, dos: "—", procedure: claimRec.procedure, code: claimRec.procedure, provider: "—", npi: "—", validation: 0, alert: "Local workbench only · payer submission locked." }
      : null);
    const currentStatus = claimRec ? claimRec.status : "Draft";
    const detailPane = det ? `
      <aside class="pv-claim-detail">
        <div class="pv-claim-detail__head"><strong>${esc(det.id)}</strong><span>${esc(det.patient)}</span></div>
        <dl class="pv-detail-meta">
          <div><dt>DOB</dt><dd>${esc(det.dob)} (Age ${det.age})</dd></div>
          <div><dt>Insurance</dt><dd>${esc(det.insurance)}</dd></div>
          <div><dt>Billed</dt><dd>${esc(det.billed)}</dd></div>
          <div><dt>DOS</dt><dd>${esc(det.dos)}</dd></div>
        </dl>
        <div class="pv-tabs"><span class="pv-tab pv-tab--active">Details</span><span class="pv-tab">Codes</span><span class="pv-tab">Documents</span><span class="pv-tab">Activity</span></div>
        <dl class="pv-detail-list">
          <div><dt>Procedure</dt><dd>${esc(det.procedure)}</dd></div>
          <div><dt>ADA Code</dt><dd>${esc(det.code)}</dd></div>
          <div><dt>Provider</dt><dd>${esc(det.provider)}</dd></div>
          <div><dt>NPI</dt><dd>${esc(det.npi)}</dd></div>
          <div><dt>Validation Score</dt><dd><div class="pv-progress"><span style="width:${det.validation}%"></span></div> ${det.validation}/100</dd></div>
        </dl>
        <div class="pv-detail-alert">${esc(det.alert)}</div>
        <div class="pv-claim-actions">
          <label class="pv-field"><span class="pv-field__label">Move to lane</span><select class="pv-input" data-claim-status="${esc(selectedId)}">${lanes.map((l) => `<option value="${esc(l)}"${currentStatus === l ? " selected" : ""}>${esc(l)}</option>`).join("")}</select></label>
          ${U.Button({ label: "Delete claim", variant: "secondary", attrs: { "data-claim-delete": selectedId } })}
        </div>
      </aside>` : `<aside class="pv-claim-detail">${U.EmptyState({ title: "Select a claim", message: "Choose a claim card to view details and update status." })}</aside>`;
    const readiness = data.readiness || { overall: "—", slices: [] };
    return `
      ${topBar(state, [`<span class="pv-safety-chip">Safety Posture: ${esc(data.safety)}</span>`, toolbarBtn("Actions", "▾"), U.Button({ label: "New claim", variant: "primary", attrs: { "data-claim-create": "1" } })])}
      ${kpiRow(data.kpis || [])}
      <div class="pv-claims-layout">
        <section class="pv-card pv-card--wide pv-claims-main">
          <div class="pv-card__head"><h3>Claims pipeline</h3></div>
          <div class="pv-kanban">${kanban}</div>
          <div class="pv-claims-bottom">
            ${card("Claim Readiness", conicDonut(readiness.slices, `<strong>${esc(readiness.overall)}</strong><span>Overall Readiness</span>`, 140), "pv-card--inline")}
            ${card("Safety Posture", `<div class="pv-shield pv-shield--gold">🛡</div><ul class="pv-checklist"><li>✓ Claims can be created and edited</li><li>✓ Validation runs locally</li><li class="pv-checklist--lock">🔒 Payer submission locked</li></ul>`, "pv-card--inline")}
          </div>
        </section>
        ${detailPane}
      </div>
      ${U.Modal({ id: "claim-create-modal", open: false, title: "Create claim", body: `<form id="claim-create-form" class="pv-form-grid">${U.FormField({ id: "cc-patient", name: "patient", label: "Patient name", required: true })}${U.FormField({ id: "cc-procedure", name: "procedure", label: "Procedure code", required: true })}${U.FormField({ id: "cc-amount", name: "amount", label: "Amount", placeholder: "$0.00", required: true })}</form>`, footer: `${U.Button({ label: "Cancel", attrs: { "data-modal-close": "claim-create-modal" } })} ${U.Button({ label: "Create", variant: "primary", attrs: { "data-claim-submit": "1" } })}` })}`;
  }

  async function wireClaims(container, state, onNavigate) {
    let selectedId = "CLM-0009712";
    async function refresh() {
      const slot = container.querySelector(".pv-body") || container;
      slot.innerHTML = U.LoadingState({ label: "Updating claims…" });
      try {
        const data = await Svc.claims.list();
        if (!selectedId && data.claims.length) selectedId = data.claims[0].id;
        slot.innerHTML = claimsBody(state, data, selectedId);
        wireClaimsInteractions(container, state, onNavigate, refresh, () => selectedId, (id) => { selectedId = id; });
      } catch (err) {
        slot.innerHTML = U.ErrorState({ message: err.message });
        slot.querySelector("[data-retry]")?.addEventListener("click", refresh);
      }
    }
    await refresh();
  }

  function wireClaimsInteractions(container, state, onNavigate, refresh, getSelected, setSelected) {
    wireCommon(container, state, onNavigate, refresh);
    wireModal(container);
    container.querySelectorAll("[data-claim-id]").forEach((el) => {
      el.addEventListener("click", () => { setSelected(el.getAttribute("data-claim-id")); refresh(); });
    });
    const createBtn = container.querySelector("[data-claim-create]");
    if (createBtn) createBtn.addEventListener("click", () => container.querySelector("#claim-create-modal")?.classList.add("pv-modal--open"));
    const submitBtn = container.querySelector("[data-claim-submit]");
    if (submitBtn) submitBtn.addEventListener("click", async () => {
      const form = container.querySelector("#claim-create-form");
      const patient = form?.querySelector('[name="patient"]')?.value?.trim();
      const procedure = form?.querySelector('[name="procedure"]')?.value?.trim();
      const amount = form?.querySelector('[name="amount"]')?.value?.trim();
      if (!patient || !procedure || !amount) { alert("Patient, procedure, and amount are required."); return; }
      submitBtn.disabled = true;
      try {
        const claim = await Svc.claims.create({ patient, procedure, amount, status: "Draft", dob: "—", age: "just now" });
        setSelected(claim.id);
        container.querySelector("#claim-create-modal")?.classList.remove("pv-modal--open");
        refresh();
      } catch (err) { alert(err.message); } finally { submitBtn.disabled = false; }
    });
    container.querySelectorAll("[data-claim-status]").forEach((sel) => {
      sel.addEventListener("change", async () => {
        const id = sel.getAttribute("data-claim-status");
        try { await Svc.claims.updateStatus(id, sel.value); refresh(); } catch (err) { alert(err.message); }
      });
    });
    container.querySelectorAll("[data-claim-delete]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!confirm("Delete this claim from the local workbench?")) return;
        try { await Svc.claims.remove(btn.getAttribute("data-claim-delete")); setSelected(null); refresh(); } catch (err) { alert(err.message); }
      });
    });
  }

  /* ---- Narratives (interactive) ---- */
  let narrativeWorking = null;

  function narrativesBody(state, data) {
    const bar = data.context || {};
    const comp = narrativeWorking || data.composer;
    const keyPointsHtml = (comp.keyPoints || []).map((p, i) => `<div class="pv-keypoint"><input type="checkbox" checked disabled /><span>${esc(p)}</span><button type="button" data-kp-remove="${i}">×</button></div>`).join("");
    const histRows = (data.drafts || []).map((h) => [h.latest ? `<strong>${esc(h.version)} Latest</strong>` : esc(h.version), esc(h.modified), String(h.points), esc(h.length), esc(h.focus), `${esc(h.by)} <button type="button" class="pv-gold-link" data-draft-delete="${esc(h.version)}">Delete</button>`]);
    return `
      ${topBar(state, [toolbarBtn("View Only", "👁"), toolbarBtn("?", "")])}
      <div class="pv-patient-bar">${[["Patient", bar.patient], ["DOB", bar.dob], ["Claim #", bar.claim], ["Insurance", bar.insurance], ["DOS", bar.dos], ["Procedure", bar.procedure], ["Status", badge(bar.status, "warn")]].map(([l, v]) => `<div><span>${esc(l)}</span>${typeof v === "string" && v.startsWith("<") ? v : `<strong>${esc(v)}</strong>`}</div>`).join("")}</div>
      <div class="pv-two-pane pv-two-pane--narratives">
        <article class="pv-card" id="narrative-composer">
          <div class="pv-card__head"><h3>Narrative Composer</h3><span>${U.Button({ label: "AI Assist", variant: "secondary", className: "pv-pill pv-pill--purple", disabled: true })} <button type="button" class="pv-gold-link" data-narrative-clear="1">Clear</button></span></div>
          <div class="pv-composer-fields">
            ${U.FormField({ id: "n-tone", name: "tone", label: "Tone", type: "select", value: comp.tone, options: ["Professional", "Clinical", "Concise"] })}
            ${U.FormField({ id: "n-length", name: "length", label: "Length", type: "select", value: comp.length, options: ["Brief", "Standard", "Detailed"] })}
            ${U.FormField({ id: "n-focus", name: "focus", label: "Focus", type: "select", value: comp.focus, options: ["Medical Necessity", "Clinical Findings", "Prior Treatment"] })}
          </div>
          <div class="pv-keypoints"><div class="pv-keypoints__head"><strong>Key Points</strong><span data-kp-count>${(comp.keyPoints || []).length} / 10</span></div><div data-kp-list>${keyPointsHtml}</div>
            <div class="pv-kp-add"><input class="pv-input" id="n-kp-input" placeholder="Add key point…" /><button type="button" class="pv-button" data-kp-add="1">+ Add</button></div>
          </div>
          ${U.FormField({ id: "n-context", name: "context", label: "Additional Context", type: "textarea", value: comp.context, placeholder: "Optional context…" })}
          <div class="pv-composer-actions">${U.Button({ label: "Save as Draft", attrs: { "data-narrative-save": "1" } })} ${U.Button({ label: "✨ Generate Narrative", variant: "primary", attrs: { "data-narrative-generate": "1" } })}</div>
          <p class="pv-field__error" data-narrative-error></p>
        </article>
        <div class="pv-narratives-right">
          <article class="pv-card"><div class="pv-card__head"><h3>Draft Narrative Preview</h3>${U.Button({ label: "Copy", attrs: { "data-narrative-copy": "1" } })}</div><div class="pv-draft-box" data-draft-preview>${esc(data.draftText || "Generate or save a draft to preview.")}</div><p class="pv-lock-note">ℹ This narrative has not been submitted and has not been written back to any system.</p></article>
          <article class="pv-card"><div class="pv-card__head"><h3>Draft History</h3><span>${(data.drafts || []).length} drafts</span></div>${U.Table({ columns: ["Version", "Modified", "Key Points", "Length", "Focus", "Modified By"], rows: histRows, emptyTitle: "No drafts yet", emptyMessage: "Save or generate a narrative to build history." })}</article>
        </div>
      </div>
      <div class="pv-safety-foot">🛡 <strong>Safety mode active</strong> · No narratives are submitted automatically. No writeback to PMS or clearinghouse.</div>`;
  }

  function readComposerForm(container) {
    const tone = container.querySelector("#n-tone")?.value;
    const length = container.querySelector("#n-length")?.value;
    const focus = container.querySelector("#n-focus")?.value;
    const context = container.querySelector("#n-context")?.value || "";
    const keyPoints = narrativeWorking?.keyPoints || [];
    return { tone, length, focus, context, keyPoints };
  }

  function validateNarrative(payload) {
    if (!payload.keyPoints || !payload.keyPoints.length) return "Add at least one key point.";
    if (payload.keyPoints.length > 10) return "Maximum 10 key points.";
    return null;
  }

  async function wireNarratives(container, state, onNavigate) {
    async function refresh() {
      const slot = container.querySelector(".pv-body") || container;
      slot.innerHTML = U.LoadingState({ label: "Loading narratives…" });
      try {
        const data = await Svc.narratives.getState();
        if (!narrativeWorking) narrativeWorking = Object.assign({}, data.composer, { keyPoints: (data.composer.keyPoints || []).slice() });
        slot.innerHTML = narrativesBody(state, data);
        wireNarrativesInteractions(container, state, onNavigate, refresh);
      } catch (err) {
        slot.innerHTML = U.ErrorState({ message: err.message });
        slot.querySelector("[data-retry]")?.addEventListener("click", refresh);
      }
    }
    await refresh();
  }

  function wireNarrativesInteractions(container, state, onNavigate, refresh) {
    wireCommon(container, state, onNavigate, refresh);
    const errEl = container.querySelector("[data-narrative-error]");
    container.querySelector("[data-kp-add]")?.addEventListener("click", () => {
      const input = container.querySelector("#n-kp-input");
      const val = input?.value?.trim();
      if (!val) return;
      if (!narrativeWorking) narrativeWorking = { keyPoints: [] };
      if (narrativeWorking.keyPoints.length >= 10) { if (errEl) errEl.textContent = "Maximum 10 key points."; return; }
      narrativeWorking.keyPoints.push(val);
      if (input) input.value = "";
      refresh();
    });
    container.querySelectorAll("[data-kp-remove]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const idx = Number(btn.getAttribute("data-kp-remove"));
        narrativeWorking.keyPoints.splice(idx, 1);
        refresh();
      });
    });
    container.querySelector("[data-narrative-clear]")?.addEventListener("click", () => {
      narrativeWorking = { tone: "Professional", length: "Standard", focus: "Medical Necessity", keyPoints: [], context: "" };
      refresh();
    });
    container.querySelector("[data-narrative-generate]")?.addEventListener("click", async (ev) => {
      const payload = readComposerForm(container);
      const err = validateNarrative(payload);
      if (err) { if (errEl) errEl.textContent = err; return; }
      if (errEl) errEl.textContent = "";
      ev.target.disabled = true;
      ev.target.textContent = "Generating…";
      try {
        const text = await Svc.narratives.generate(payload);
        container.querySelector("[data-draft-preview]").textContent = text;
        narrativeWorking = Object.assign({}, payload);
        await Svc.narratives.saveDraft(Object.assign({}, payload, { text }));
        refresh();
      } catch (e) { if (errEl) errEl.textContent = e.message; } finally { ev.target.disabled = false; ev.target.textContent = "✨ Generate Narrative"; }
    });
    container.querySelector("[data-narrative-save]")?.addEventListener("click", async () => {
      const payload = readComposerForm(container);
      const preview = container.querySelector("[data-draft-preview]")?.textContent || "";
      const err = validateNarrative(payload);
      if (err) { if (errEl) errEl.textContent = err; return; }
      try { await Svc.narratives.saveDraft(Object.assign({}, payload, { text: preview })); refresh(); } catch (e) { if (errEl) errEl.textContent = e.message; }
    });
    container.querySelector("[data-narrative-copy]")?.addEventListener("click", () => {
      const text = container.querySelector("[data-draft-preview]")?.textContent;
      if (text && navigator.clipboard) navigator.clipboard.writeText(text);
    });
    container.querySelectorAll("[data-draft-delete]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!confirm("Delete this draft version?")) return;
        await Svc.narratives.deleteDraft(btn.getAttribute("data-draft-delete"));
        refresh();
      });
    });
  }

  /* ---- Documents (interactive) ---- */
  function documentsBody(state, data, selectedId, filter) {
    const queueRows = data.queue.map((q) => ({
      key: q.id,
      className: q.id === selectedId ? "pv-row-selected" : "",
      cells: [esc(q.id), esc(q.type), esc(q.vendor), esc(q.date), esc(q.amount), badge(q.status, q.statusTone), String(q.age)],
    }));
    const preview = data.preview || {};
    const posting = data.posting || [];
    const period = data.period || {};
    return `
      ${topBar(state, [badge("Read-Only", "warn"), `<span class="pv-entity">Entity: ${esc(data.entity)}</span>`])}
      <div class="pv-bento pv-bento--documents">
        ${card("Document Intake & Posting Queue", `<div class="pv-search"><input type="search" class="pv-input" id="doc-search" placeholder="Search documents…" value="${esc(filter.query || "")}" /><button class="pv-button" type="button" data-doc-filter="1">Apply</button><select class="pv-input" id="doc-status"><option value="All"${!filter.status || filter.status === "All" ? " selected" : ""}>All statuses</option><option value="Pending Review"${filter.status === "Pending Review" ? " selected" : ""}>Pending Review</option><option value="Ready to Post"${filter.status === "Ready to Post" ? " selected" : ""}>Ready to Post</option><option value="Posted"${filter.status === "Posted" ? " selected" : ""}>Posted</option></select></div>${U.Table({ columns: ["ID", "Document Type", "Vendor / Entity", "Document Date", "Amount", "Status", "Age (Days)"], rows: queueRows, emptyTitle: "No documents match", emptyMessage: "Try clearing filters or refreshing." })}`, "pv-card--queue")}
        ${card("Selected Document Preview", preview.vendor ? `<div class="pv-invoice-preview"><div class="pv-invoice-preview__head">${esc(preview.vendor)}</div><p>Invoice # ${esc(preview.invoice)}</p><p>Date: ${esc(preview.date)}</p><p class="pv-invoice-preview__total">Total ${esc(preview.total)}</p></div><footer class="pv-preview-foot">${esc(preview.file || "")} · ${esc(preview.pages || "")} · Uploaded ${esc(preview.uploaded || "")}</footer>` : U.EmptyState({ title: "No document selected", message: "Select a row to preview." }), "pv-card--preview")}
        ${card("Posting Queue Review", `<div class="pv-post-grid">${posting.map((p) => `<article class="pv-post-card pv-post-card--${p.tone}"><span>${esc(p.label)}</span><strong>${p.count}</strong>${p.amount ? `<em>${esc(String(p.amount))}</em>` : ""}</article>`).join("")}</div><div class="pv-review-workload"><span>Review Workload</span><div><i style="width:${esc(period.reviewedPct || 24)}%"></i></div><em>${esc(period.reviewedPct || 24)}%</em></div><a class="pv-gold-link" href="#">View All Documents →</a>`, "pv-card--wide")}
        ${card("Period Summary", `<div class="pv-period-summary"><dl>${[["Period", period.label], ["Documents", period.documents], ["Total Amount", period.totalAmount], ["Posted Amount", period.postedAmount], ["Pending Amount", period.pendingAmount]].map(([l, v]) => `<div><dt>${esc(l)}</dt><dd>${esc(v || "—")}</dd></div>`).join("")}</dl>${conicDonut([{ label: "Posted", pct: period.postedPct || 88, color: "#3f73e6" }, { label: "Pending", pct: period.pendingPct || 11, color: "#d6b15e" }, { label: "Ready to Post", pct: period.readyPct || 1, color: "#78a86b" }], `<strong>${esc(period.postedPct || 88)}%</strong><span>Posted</span>`, 142)}</div><a class="pv-gold-link" href="#">View Period Close →</a>`, "pv-card--period")}
        ${selectedId ? `<div class="pv-doc-actions">${U.FormField({ id: "doc-new-status", name: "status", label: "Update status", type: "select", value: (data.queue.find((q) => q.id === selectedId) || {}).status, options: ["Pending Review", "Ready to Post", "Posted"] })} ${U.Button({ label: "Save status", variant: "primary", attrs: { "data-doc-save": selectedId } })} ${U.Button({ label: "Remove", attrs: { "data-doc-delete": selectedId } })}</div>` : ""}
      </div>`;
  }

  async function wireDocuments(container, state, onNavigate) {
    let selectedId = "DOC-2025-05891";
    let filter = { query: "", status: "All" };
    async function refresh() {
      const slot = container.querySelector(".pv-body") || container;
      slot.innerHTML = U.LoadingState({ label: "Loading documents…" });
      try {
        const list = await Svc.documents.list(filter);
        if (selectedId && !list.queue.find((q) => q.id === selectedId) && list.queue.length) selectedId = list.queue[0].id;
        const detail = selectedId ? await Svc.documents.get(selectedId) : { preview: null };
        slot.innerHTML = documentsBody(state, Object.assign({}, list, { preview: detail.preview, queue: list.queue }), selectedId, filter);
        wireDocumentsInteractions(container, state, onNavigate, refresh, () => selectedId, (id) => { selectedId = id; }, () => filter, (f) => { filter = f; });
      } catch (err) {
        slot.innerHTML = U.ErrorState({ message: err.message });
        slot.querySelector("[data-retry]")?.addEventListener("click", refresh);
      }
    }
    await refresh();
  }

  function wireDocumentsInteractions(container, state, onNavigate, refresh, getSelected, setSelected, getFilter, setFilter) {
    wireCommon(container, state, onNavigate, refresh);
    container.querySelectorAll("[data-row]").forEach((row) => {
      row.addEventListener("click", () => { setSelected(row.getAttribute("data-row")); refresh(); });
    });
    container.querySelector("[data-doc-filter]")?.addEventListener("click", () => {
      setFilter({ query: container.querySelector("#doc-search")?.value || "", status: container.querySelector("#doc-status")?.value || "All" });
      refresh();
    });
    container.querySelector("[data-doc-save]")?.addEventListener("click", async (ev) => {
      const id = ev.target.getAttribute("data-doc-save");
      const status = container.querySelector("#doc-new-status")?.value;
      try { await Svc.documents.updateStatus(id, status); refresh(); } catch (e) { alert(e.message); }
    });
    container.querySelector("[data-doc-delete]")?.addEventListener("click", async (ev) => {
      const id = ev.target.getAttribute("data-doc-delete");
      if (!confirm("Remove document from queue?")) return;
      try { await Svc.documents.remove(id); setSelected(null); refresh(); } catch (e) { alert(e.message); }
    });
  }

  /* ---- Library (interactive search) ---- */
  function libraryBody(state, data, selectedTitle, query, typeFilter) {
    const docCards = (data.docs || []).map((doc) => `<article class="pv-doc-card${doc.title === selectedTitle ? " pv-doc-card--selected" : ""}" data-lib-doc="${esc(doc.title)}" tabindex="0"><div class="pv-doc-card__head"><span class="pv-file-icon pv-file-icon--${doc.tone}">${esc(doc.type)}</span>${badge("Read-Only", "demo")}</div><strong>${esc(doc.title)}</strong><span>${esc(doc.type)} · ${esc(doc.size)}</span><div class="pv-chips">${(doc.tags || []).map((t) => `<span class="pv-chip">${esc(t)}</span>`).join("")}</div><footer>Updated ${esc(doc.updated)} · ${esc(doc.by)}</footer></article>`).join("");
    const det = data.detail || {};
    return `
      ${topBar(state, [`<span class="pv-storage"><strong>${(data.results || 0).toLocaleString()}</strong> Documents · ${data.storage?.usedPct || 0}% of ${esc(data.storage?.capacity || "")}</span>`])}
      <div class="pv-library-layout">
        <div class="pv-library-main">
          <div class="pv-search pv-search--library"><input type="search" class="pv-input" id="lib-search" placeholder="Search documents…" value="${esc(query || "")}" /><button class="pv-button" type="button" data-lib-search="1">Search</button><a class="pv-gold-link" href="#" data-lib-reset="1">Reset Filters</a></div>
          <div class="pv-filter-row"><select class="pv-input" id="lib-type"><option value="All">Document Type</option>${["PDF", "DOCX", "XLSX", "PPTX"].map((t) => `<option value="${t}"${typeFilter === t ? " selected" : ""}>${t}</option>`).join("")}</select></div>
          <div class="pv-results-head"><strong class="pv-gold">${(data.results || 0).toLocaleString()} RESULTS</strong></div>
          <div class="pv-doc-grid pv-doc-grid--rich">${docCards || U.EmptyState({ title: "No documents found", message: "Adjust search or filters." })}</div>
        </div>
        <aside class="pv-library-detail">${det.title ? `<div class="pv-detail-head"><span class="pv-file-icon pv-file-icon--red">${esc(det.type || "PDF")}</span><div><strong>${esc(det.title)}</strong><span>${esc(det.type)} · ${esc(det.size)}</span></div>${badge("Read-Only", "demo")}</div><div class="pv-tabs"><span class="pv-tab pv-tab--active">Preview</span><span class="pv-tab">Details</span><span class="pv-tab">Activity</span></div><div class="pv-doc-preview-frame"><div class="pv-doc-preview-cover"><div class="pv-phoenix">🦅</div><strong>OPERATION PHOENIX</strong><span>MISSION BRIEFING</span></div></div><dl class="pv-detail-list">${[["Classification", det.classification], ["Document Type", det.docType], ["Mission", det.mission], ["Uploaded By", det.uploadedBy], ["Date Added", det.dateAdded], ["Checksum", det.checksum], ["File Path", det.path]].filter(([, v]) => v).map(([l, v]) => `<div><dt>${esc(l)}</dt><dd>${esc(v)}</dd></div>`).join("")}</dl>` : U.EmptyState({ title: "Select a document", message: "Click a card to preview details." })}</aside>
      </div>`;
  }

  async function wireLibrary(container, state, onNavigate) {
    let selectedTitle = "Operation Phoenix Briefing";
    let query = "";
    let typeFilter = "All";
    async function refresh() {
      const slot = container.querySelector(".pv-body") || container;
      slot.innerHTML = U.LoadingState({ label: "Loading library…" });
      try {
        const data = await Svc.library.search(query, { type: typeFilter });
        if (selectedTitle && !data.docs.find((d) => d.title === selectedTitle) && data.docs.length) selectedTitle = data.docs[0].title;
        const detail = selectedTitle ? (await Svc.library.get(selectedTitle)).detail : null;
        slot.innerHTML = libraryBody(state, Object.assign({}, data, { detail }), selectedTitle, query, typeFilter);
        wireLibraryInteractions(container, state, onNavigate, refresh, () => selectedTitle, (t) => { selectedTitle = t; }, () => query, (q) => { query = q; }, () => typeFilter, (t) => { typeFilter = t; });
      } catch (err) {
        slot.innerHTML = U.ErrorState({ message: err.message });
        slot.querySelector("[data-retry]")?.addEventListener("click", refresh);
      }
    }
    await refresh();
  }

  function wireLibraryInteractions(container, state, onNavigate, refresh, getSel, setSel, getQ, setQ, getType, setType) {
    wireCommon(container, state, onNavigate, refresh);
    container.querySelectorAll("[data-lib-doc]").forEach((el) => el.addEventListener("click", () => { setSel(el.getAttribute("data-lib-doc")); refresh(); }));
    container.querySelector("[data-lib-search]")?.addEventListener("click", () => { setQ(container.querySelector("#lib-search")?.value || ""); setType(container.querySelector("#lib-type")?.value || "All"); refresh(); });
    container.querySelector("[data-lib-reset]")?.addEventListener("click", (e) => { e.preventDefault(); setQ(""); setType("All"); refresh(); });
  }

  async function renderOfficeManager(state, halData) {
    const surfaces = await Svc.officeManager.surfaces(halData);
    if (!surfaces.length) return `${topBar(state)}${U.EmptyState({ title: "No work surfaces", message: "HAL registry has no linked work surfaces yet." })}`;
    return `
      ${topBar(state)}
      ${card("Work surfaces", `<div class="pv-work-grid">${surfaces.map((s) => `<article class="pv-work-card" data-pv-nav="${esc(s.target)}" tabindex="0"><strong>${esc(s.label)}</strong><span>${esc(s.state)}</span><p>${esc(s.detail)}</p>${s.nextAction ? `<em>${esc(s.nextAction)}</em>` : ""}</article>`).join("")}</div>`, "pv-card--wide", String(surfaces.length))}`;
  }

  const PAGE_RENDERERS = {
    financial: renderFinancial,
    softdent: renderSoftdent,
    quickbooks: renderQuickbooks,
    ar: renderAr,
    "office-manager": renderOfficeManager,
  };

  const INTERACTIVE_PAGES = new Set(["claims", "narratives", "documents", "library"]);

  function renderMockImage(container, pageId, onNavigate) {
    const src = MOCK_IMAGES[pageId];
    const nav = MOCK_NAV.map(
      ([id, label]) => `<button type="button" data-pv-nav="${esc(id)}"${id === pageId ? ' class="is-active"' : ""}>${esc(label)}</button>`,
    ).join("");
    container.innerHTML = `
      <article class="pv-mock-page pv--${esc(pageId)} pv--mock-image" data-pv-page="${esc(pageId)}">
        <img class="pv-mock-page__image" src="${esc(src)}" alt="${esc((PAGE_OUTLINES[pageId] && PAGE_OUTLINES[pageId].eyebrow) || pageId)} mockup" />
        <nav class="pv-mock-nav" aria-label="Page navigation">${nav}</nav>
      </article>`;
    if (typeof onNavigate === "function") {
      container.querySelectorAll("[data-pv-nav]").forEach((button) => {
        button.addEventListener("click", () => onNavigate(button.getAttribute("data-pv-nav")));
      });
    }
  }

  function renderPageView(container, halData, pageId, onNavigate) {
    if (!container) return;

    if (MOCK_IMAGES[pageId]) {
      renderMockImage(container, pageId, onNavigate);
      return;
    }

    if (!U || !Svc) return;
    const state = buildPageState(halData, pageId);

    if (INTERACTIVE_PAGES.has(pageId)) {
      container.innerHTML = pageShell(state, `<div class="pv-body">${U.LoadingState({ label: "Loading…" })}</div>`);
      if (pageId === "claims") wireClaims(container, state, onNavigate);
      else if (pageId === "narratives") wireNarratives(container, state, onNavigate);
      else if (pageId === "documents") wireDocuments(container, state, onNavigate);
      else if (pageId === "library") wireLibrary(container, state, onNavigate);
      return;
    }

    const renderFn = PAGE_RENDERERS[pageId];
    if (!renderFn) {
      container.innerHTML = pageShell(state, `${topBar(state)}${U.EmptyState({ title: "Page not configured", message: `No renderer for ${pageId}.` })}`);
      wireCommon(container, state, onNavigate, () => renderPageView(container, halData, pageId, onNavigate));
      return;
    }

    mountPage(container, state, (s) => renderFn(s, halData), onNavigate);
  }

  function hasPage(pageId) {
    if (pageId === "hal") return false;
    return Boolean(MOCK_IMAGES[pageId] || PAGE_OUTLINES[pageId]);
  }

  /** Async full HTML preview for tests and drift comparison. */
  async function previewPageHtml(halData, pageId) {
    if (MOCK_IMAGES[pageId]) {
      const nav = MOCK_NAV.map(([id, label]) => `<button type="button" data-pv-nav="${esc(id)}">${esc(label)}</button>`).join("");
      return `<article class="pv-mock-page pv--${esc(pageId)} pv--mock-image" data-pv-page="${esc(pageId)}"><img class="pv-mock-page__image" src="${esc(MOCK_IMAGES[pageId])}" alt="${esc(pageId)} mockup" /><nav class="pv-mock-nav">${nav}</nav></article>`;
    }
    const state = buildPageState(halData, pageId);
    if (!U || !Svc) return pageShell(state, "<p>UI/Services unavailable</p>");
    if (pageId === "claims") {
      const data = await Svc.claims.list();
      return pageShell(state, claimsBody(state, data, "CLM-0009712"));
    }
    if (pageId === "narratives") {
      const data = await Svc.narratives.getState();
      narrativeWorking = Object.assign({}, data.composer, { keyPoints: (data.composer.keyPoints || []).slice() });
      return pageShell(state, narrativesBody(state, data));
    }
    if (pageId === "documents") {
      const list = await Svc.documents.list({ query: "", status: "All" });
      const detail = await Svc.documents.get("DOC-2025-05891");
      return pageShell(state, documentsBody(state, Object.assign({}, list, { preview: detail.preview }), "DOC-2025-05891", { query: "", status: "All" }));
    }
    if (pageId === "library") {
      const data = await Svc.library.search("", { type: "All" });
      const detail = (await Svc.library.get("Operation Phoenix Briefing")).detail;
      return pageShell(state, libraryBody(state, Object.assign({}, data, { detail }), "Operation Phoenix Briefing", "", "All"));
    }
    const renderFn = PAGE_RENDERERS[pageId];
    if (renderFn) return pageShell(state, await renderFn(state, halData));
    return pageShell(state, U.EmptyState({ title: "Page not configured", message: pageId }));
  }

  return { PAGE_OUTLINES, buildPageState, renderPageView, previewPageHtml, hasPage, stateTone };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = PageViews;
}
if (typeof window !== "undefined") {
  window.PageViews = PageViews;
}
