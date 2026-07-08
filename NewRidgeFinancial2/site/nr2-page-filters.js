/**
 * Moonshot Tier S2 — interactive page filters (hal-10083).
 * Filter chips, global period scrubber, taxes what-if sliders.
 */
const NR2PageFilters = (function () {
  const STORAGE_KEY = "nr2_page_filters_v1";
  const COMP_MIN = 180000;
  const COMP_MAX = 280000;
  const COMP_STEP = 10000;

  const DEFAULTS = {
    financial: { chipIndex: 0, periodRange: "ytd", compareMode: false, scrubPeriod: null },
    taxes: { chipIndex: 0, modeledW2: 220000, revenueAdjPct: 0, scrubPeriod: null },
    softdent: { chipIndex: 2, scrubPeriod: null },
    quickbooks: { chipIndex: 0, scrubPeriod: null },
    ar: { chipIndex: 0, scrubPeriod: null },
    claims: { chipIndex: 0, scrubPeriod: null },
    documents: { chipIndex: 0, scrubPeriod: null },
    library: { chipIndex: 0 },
    narratives: { chipIndex: 0 },
    "office-manager": { chipIndex: 0 },
  };

  let cache = null;

  function loadAll() {
    if (cache) return cache;
    try {
      const raw = typeof sessionStorage !== "undefined" ? sessionStorage.getItem(STORAGE_KEY) : null;
      cache = raw ? JSON.parse(raw) : {};
    } catch {
      cache = {};
    }
    return cache;
  }

  function saveAll() {
    try {
      if (typeof sessionStorage !== "undefined") sessionStorage.setItem(STORAGE_KEY, JSON.stringify(loadAll()));
    } catch {
      /* sessionStorage optional */
    }
  }

  function pageDefaults(pageId) {
    return Object.assign({}, DEFAULTS[pageId] || { chipIndex: 0 });
  }

  function getPage(pageId) {
    const all = loadAll();
    if (!all[pageId]) all[pageId] = pageDefaults(pageId);
    return Object.assign(pageDefaults(pageId), all[pageId]);
  }

  function setPage(pageId, patch) {
    const all = loadAll();
    all[pageId] = Object.assign(pageDefaults(pageId), all[pageId] || {}, patch || {});
    cache = all;
    saveAll();
    return all[pageId];
  }

  function filterContext(pageId) {
    return getPage(pageId);
  }

  function esc(v) {
    return String(v == null ? "" : v)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function formatMoney(n) {
    if (typeof TaxEngine !== "undefined" && TaxEngine.formatMoney) return TaxEngine.formatMoney(n);
    return `$${Math.round(Number(n) || 0).toLocaleString("en-US")}`;
  }

  function formatPeriodLabel(period) {
    const m = String(period).match(/^(\d{4})-(\d{2})$/);
    if (!m) return period;
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    return `${months[Number(m[2]) - 1] || m[2]} ${m[1]}`;
  }

  function chipRefreshLabel(label) {
    return /refresh|sync/i.test(String(label || ""));
  }

  function parseChipEffect(pageId, label, index) {
    const l = String(label || "");
    if (chipRefreshLabel(l)) return { action: "refresh" };
    if (pageId === "financial") {
      if (/year to date/i.test(l)) return { periodRange: "ytd", compareMode: false, chipIndex: index };
      if (/last 12/i.test(l)) return { periodRange: "l12m", compareMode: true, chipIndex: index };
    }
    return { chipIndex: index };
  }

  function periodsFromSnapshot(snapshot) {
    const rows = [];
    const bundle = (snapshot && snapshot.importBundle) || {};
    const sd = bundle.softdent || {};
    const qb = bundle.quickbooks || {};
    const addFrom = (list, field) => {
      (list || []).forEach((row) => {
        const p = row && (row[field] || row.period || row.Period);
        if (p) rows.push(String(p).trim().slice(0, 7));
      });
    };
    addFrom((sd.dashboard && sd.dashboard.rows) || [], "period");
    addFrom((qb.revenue && qb.revenue.rows) || [], "Period");
    const fin = snapshot && snapshot.dashboards && snapshot.dashboards.financial;
    const trend = fin && fin.productionTrend && fin.productionTrend.labels;
    if (Array.isArray(trend)) trend.forEach((label) => rows.push(String(label).slice(0, 7)));
    const unique = Array.from(new Set(rows.filter(Boolean))).sort();
    if (!unique.length && typeof HalPeriodRequirements !== "undefined" && HalPeriodRequirements.relevantPeriodLabels) {
      return HalPeriodRequirements.relevantPeriodLabels();
    }
    return unique.slice(-12);
  }

  function applyPeriodSlice(labels, values, filters) {
    if (!labels.length || !values.length) return { labels, values };
    const f = filters || {};
    if (f.scrubPeriod) {
      const key = String(f.scrubPeriod).slice(0, 7);
      const idx = labels.findIndex((label) => String(label).slice(0, 7) === key);
      if (idx >= 0) return { labels: labels.slice(0, idx + 1), values: values.slice(0, idx + 1) };
    }
    if (f.periodRange === "l12m") {
      return { labels: labels.slice(-12), values: values.slice(-12) };
    }
    const year = new Date().getFullYear();
    const pairs = labels
      .map((label, i) => ({ label, value: values[i] }))
      .filter((row) => String(row.label).includes(String(year)));
    if (pairs.length) {
      return { labels: pairs.map((row) => row.label), values: pairs.map((row) => row.value) };
    }
    return { labels, values };
  }

  function renderPeriodScrubberHtml(pageId, periods, selected) {
    if (!periods || periods.length < 2) return "";
    const sel = selected || periods[periods.length - 1];
    const pills = periods
      .map(
        (p) =>
          `<button type="button" class="period-scrubber__pill${p === sel ? " active" : ""}" data-nr2-scrub-period="${esc(
            p,
          )}" aria-pressed="${p === sel ? "true" : "false"}">${esc(formatPeriodLabel(p))}</button>`,
      )
      .join("");
    return `<div class="period-scrubber" data-nr2-period-scrubber="${esc(pageId)}" role="group" aria-label="Period filter">
      <span class="period-scrubber__label">Period</span>
      <div class="period-scrubber__track">${pills}</div>
    </div>`;
  }

  async function handleRefresh() {
    const coord = typeof ImportCoordinator !== "undefined" ? ImportCoordinator : null;
    if (coord && typeof coord.refresh === "function") {
      await coord.refresh({ reason: "filter-chip-refresh" });
    } else if (typeof Services !== "undefined" && typeof Services.refreshImports === "function") {
      await Services.refreshImports({ reason: "filter-chip-refresh", waitForCompletion: true });
    }
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("nr2:page-refresh-requested"));
      window.dispatchEvent(new CustomEvent("nr2-import-readiness-changed"));
    }
  }

  function requestPageRefresh(onChange) {
    if (onChange) onChange();
    else if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent("nr2:page-refresh-requested"));
  }

  function attachPeriodScrubber(root, pageId, snapshot, onChange) {
    const periods = periodsFromSnapshot(snapshot);
    const state = getPage(pageId);
    const bar = root.querySelector(".filter-bar");
    if (!bar || periods.length < 2) return;
    let scrub = root.querySelector("[data-nr2-period-scrubber]");
    const html = renderPeriodScrubberHtml(pageId, periods, state.scrubPeriod || periods[periods.length - 1]);
    if (scrub) scrub.outerHTML = html;
    else bar.insertAdjacentHTML("afterend", html);
    scrub = root.querySelector("[data-nr2-period-scrubber]");
    if (!scrub) return;
    scrub.querySelectorAll("[data-nr2-scrub-period]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const period = btn.getAttribute("data-nr2-scrub-period");
        setPage(pageId, { scrubPeriod: period });
        scrub.querySelectorAll("[data-nr2-scrub-period]").forEach((b) => {
          b.classList.toggle("active", b === btn);
          b.setAttribute("aria-pressed", b === btn ? "true" : "false");
        });
        requestPageRefresh(onChange);
      });
    });
  }

  function buildTaxNarrative(w2, adjPct) {
    const adj = adjPct ? ` Book income adjusted ${adjPct > 0 ? "up" : "down"} ${Math.abs(adjPct)}% for planning.` : "";
    const comp =
      w2 >= 260000
        ? "Higher W-2 reduces distribution room but strengthens reasonable-comp documentation."
        : w2 <= 180000
          ? "Lower W-2 increases audit risk if distributions are high — confirm with CPA."
          : "Modeled W-2 sits in a balanced planning band for dental S corp owners.";
    return `HAL scenario:${adj} ${comp} Estimates are planning-only — not a filed return.`;
  }

  function renderTaxScenarioPanelHtml() {
    const state = getPage("taxes");
    return `<div class="nr2-scenario-panel col-12" data-nr2-scenario-panel="taxes">
      <div class="nr2-scenario-panel__head"><strong>What-if scenario</strong><span class="nr2-scenario-panel__hint">Live HAL narrative · CPA review required</span></div>
      <div class="nr2-scenario-sliders">
        <label class="nr2-scenario-slider"><span>Officer W-2</span><input type="range" data-nr2-tax-w2 min="${COMP_MIN}" max="${COMP_MAX}" step="${COMP_STEP}" value="${state.modeledW2 || 220000}" /><output data-nr2-tax-w2-value>${formatMoney(state.modeledW2 || 220000)}</output></label>
        <label class="nr2-scenario-slider"><span>Book revenue adj.</span><input type="range" data-nr2-tax-rev-adj min="-20" max="20" step="1" value="${state.revenueAdjPct || 0}" /><output data-nr2-tax-rev-adj-value>${state.revenueAdjPct || 0}%</output></label>
      </div>
      <p class="nr2-scenario-narrative" data-nr2-tax-narrative>${esc(buildTaxNarrative(state.modeledW2 || 220000, state.revenueAdjPct || 0))}</p>
    </div>`;
  }

  function bindTaxScenarioSliders(root, pageId, onChange) {
    if (pageId !== "taxes") return;
    const panel = root.querySelector("[data-nr2-scenario-panel]");
    if (!panel || panel.dataset.nr2ScenarioWired === "1") return;
    panel.dataset.nr2ScenarioWired = "1";
    const w2 = panel.querySelector("[data-nr2-tax-w2]");
    const rev = panel.querySelector("[data-nr2-tax-rev-adj]");
    const w2Out = panel.querySelector("[data-nr2-tax-w2-value]");
    const revOut = panel.querySelector("[data-nr2-tax-rev-adj-value]");
    const narrative = panel.querySelector("[data-nr2-tax-narrative]");
    const state = getPage("taxes");
    if (w2) w2.value = String(state.modeledW2 || 220000);
    if (rev) rev.value = String(state.revenueAdjPct || 0);

    const apply = (opts) => {
      const silent = opts && opts.silent;
      const modeledW2 = w2 ? Number(w2.value) : 220000;
      const revenueAdjPct = rev ? Number(rev.value) : 0;
      if (w2Out) w2Out.textContent = formatMoney(modeledW2);
      if (revOut) revOut.textContent = `${revenueAdjPct > 0 ? "+" : ""}${revenueAdjPct}%`;
      setPage("taxes", { modeledW2, revenueAdjPct });
      if (narrative) narrative.textContent = buildTaxNarrative(modeledW2, revenueAdjPct);
      if (!silent) requestPageRefresh(onChange);
    };
    if (w2) w2.addEventListener("input", () => apply());
    if (rev) rev.addEventListener("input", () => apply());
    apply({ silent: true });
  }

  function bindFilterBar(root, pageId, opts) {
    const o = opts || {};
    const bar = root && root.querySelector(".filter-bar");
    if (!bar || bar.dataset.nr2FiltersWired === "1") return;
    bar.dataset.nr2FiltersWired = "1";
    const state = getPage(pageId);
    bar.querySelectorAll("[data-nr2-filter-chip]").forEach((btn) => {
      const idx = Number(btn.getAttribute("data-nr2-filter-chip") || 0);
      btn.classList.toggle("active", idx === state.chipIndex);
      btn.addEventListener("click", async () => {
        const label = btn.textContent || "";
        const effect = parseChipEffect(pageId, label, idx);
        if (effect.action === "refresh") {
          await handleRefresh();
          return;
        }
        setPage(pageId, effect);
        bar.querySelectorAll("[data-nr2-filter-chip]").forEach((b) => {
          const i = Number(b.getAttribute("data-nr2-filter-chip") || 0);
          b.classList.toggle("active", i === idx);
          b.setAttribute("aria-pressed", i === idx ? "true" : "false");
        });
        requestPageRefresh(o.onChange);
      });
    });
    attachPeriodScrubber(root, pageId, o.snapshot, o.onChange);
    bindTaxScenarioSliders(root, pageId, o.onChange);
  }

  function mountPageFilters(root, pageId, opts) {
    bindFilterBar(root, pageId, opts);
  }

  return {
    getPage,
    setPage,
    filterContext,
    parseChipEffect,
    periodsFromSnapshot,
    applyPeriodSlice,
    renderPeriodScrubberHtml,
    renderTaxScenarioPanelHtml,
    mountPageFilters,
    bindFilterBar,
    buildTaxNarrative,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = NR2PageFilters;
}
if (typeof globalThis !== "undefined") {
  globalThis.NR2PageFilters = NR2PageFilters;
}
if (typeof window !== "undefined") {
  window.NR2PageFilters = NR2PageFilters;
}
