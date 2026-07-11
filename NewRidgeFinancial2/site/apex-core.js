/**
 * NR2-Apex Core — Bridge mosaic, silent refresh, print, session-aware fetch
 * Build: hal-10493 (V2 explain cache + mobile polish)
 */
(function () {
  "use strict";

  const SESSION_HEADER = "X-NR2-Session-Token";
  const REFRESH_HEADER = "X-NR2-Refresh-Token";
  const ASSET_V = "hal-10493";
  const WB_VIEW_KEY = "nr2-apex-claims-wb-view";
  const CPA_FLAG_KEY = "nr2-apex-cpa-flags";
  const PARENT_PAGES = new Set([
    "financial",
    "taxes",
    "softdent",
    "quickbooks",
    "ar",
    "claims",
    "narratives",
    "documents",
    "library",
    "office-manager",
    "hal",
  ]);
  const SUBPAGE_LINKS = {
    financial: [
      { sub: null, label: "Overview" },
      { sub: "workpapers", label: "Workpapers" },
      { sub: "providers", label: "Providers" },
      { sub: "periods", label: "Periods" },
    ],
    taxes: [
      { sub: null, label: "Overview" },
      { sub: "entities", label: "Entities" },
      { sub: "calendar", label: "Calendar" },
      { sub: "workpapers", label: "Workpapers" },
    ],
    softdent: [
      { sub: null, label: "Overview" },
      { sub: "register", label: "Register" },
      { sub: "schedule", label: "Schedule" },
    ],
    quickbooks: [
      { sub: null, label: "Overview" },
      { sub: "coa", label: "COA" },
      { sub: "vendors", label: "Vendors" },
    ],
    claims: [
      { sub: null, label: "Workbench" },
      { sub: "detail", label: "Detail" },
      { sub: "batch", label: "Batch" },
      { sub: "era", label: "ERA" },
      { sub: "attachments", label: "Attachments" },
    ],
    ar: [
      { sub: null, label: "Overview" },
      { sub: "collections", label: "Collections" },
      { sub: "aging-detail", label: "Aging Detail" },
      { sub: "forecast", label: "Forecast" },
    ],
    narratives: [
      { sub: null, label: "Workspace" },
      { sub: "templates", label: "Templates" },
      { sub: "history", label: "History" },
      { sub: "audit", label: "Audit" },
    ],
    documents: [
      { sub: null, label: "Overview" },
      { sub: "claim-docs", label: "Claim Docs" },
      { sub: "tax-docs", label: "Tax Docs" },
    ],
    library: [
      { sub: null, label: "Overview" },
      { sub: "payers", label: "Payers" },
      { sub: "codes", label: "Codes" },
    ],
    "office-manager": [
      { sub: null, label: "Overview" },
      { sub: "huddle", label: "Huddle" },
      { sub: "tasks", label: "Tasks" },
    ],
    hal: [
      { sub: null, label: "Chat" },
      { sub: "history", label: "History" },
      { sub: "system-logs", label: "System Logs" },
    ],
  };
  const SUBPAGE_TITLES = {
    workpapers: "Workpapers",
    providers: "Providers",
    periods: "Periods",
    entities: "Entities",
    calendar: "Calendar",
    register: "Register",
    schedule: "Schedule",
    coa: "COA",
    vendors: "Vendors",
    detail: "Detail",
    batch: "Batch",
    era: "ERA",
    attachments: "Attachments",
    collections: "Collections",
    "aging-detail": "Aging Detail",
    forecast: "Forecast",
    templates: "Templates",
    history: "History",
    audit: "Audit",
    "claim-docs": "Claim Docs",
    "tax-docs": "Tax Docs",
    payers: "Payers",
    codes: "Codes",
    huddle: "Huddle",
    tasks: "Tasks",
    "system-logs": "System Logs",
  };

  function formatPatientDisplay(name) {
    const raw = String(name || "").trim();
    if (!raw) return "—";
    if (raw.includes(",")) return raw;
    const parts = raw.split(/\s+/).filter(Boolean);
    if (parts.length >= 2) {
      const last = parts[parts.length - 1];
      const first = parts.slice(0, -1).join(" ");
      return `${last}, ${first}`;
    }
    return raw;
  }

  function attachmentDotHtml(att) {
    if (!att || typeof att !== "object") {
      return `<span class="apex-wb-att apex-wb-att--unknown" title="Attachments not on import">—</span>`;
    }
    const cur = Number(att.current);
    const req = att.required;
    if (req != null && Number.isFinite(Number(req))) {
      const ok = Number.isFinite(cur) && cur >= Number(req);
      return `<span class="apex-wb-att ${ok ? "apex-wb-att--ok" : "apex-wb-att--missing"}" title="${
        ok ? "Attachments complete" : "Missing attachments"
      }">${ok ? "●" : "○"}</span>`;
    }
    if (Number.isFinite(cur) && cur > 0) {
      return `<span class="apex-wb-att apex-wb-att--ok" title="${cur} attachment(s)">●</span>`;
    }
    return `<span class="apex-wb-att apex-wb-att--unknown" title="No attachment count">—</span>`;
  }

  function preferredWorkbenchView(fallback) {
    try {
      const v = sessionStorage.getItem(WB_VIEW_KEY) || localStorage.getItem(WB_VIEW_KEY);
      if (v === "table" || v === "kanban") return v;
    } catch (_err) {
      /* ignore */
    }
    return fallback === "kanban" ? "kanban" : "table";
  }

  function persistWorkbenchView(view) {
    const v = view === "kanban" ? "kanban" : "table";
    try {
      localStorage.setItem(WB_VIEW_KEY, v);
      sessionStorage.setItem(WB_VIEW_KEY, v);
    } catch (_err) {
      /* ignore */
    }
  }

  const PAGE_TITLES = {
    financial: "Financial",
    taxes: "Taxes",
    softdent: "SoftDent",
    quickbooks: "QuickBooks",
    ar: "A/R",
    claims: "Claims",
    narratives: "Narratives",
    documents: "Documents",
    library: "Library",
    "office-manager": "Office Manager",
    hal: "HAL",
  };

  function instrumentSize(spec) {
    const type = String((spec && spec.type) || "kpi");
    if (spec && spec.size) return String(spec.size);
    if (type === "hal-chat") return "hal-chat";
    if (type === "chart" || type === "bar" || type === "line") return "l";
    if (
      type === "pulse" ||
      type === "remainder" ||
      type === "funnel" ||
      type === "countdown" ||
      type === "horizontal-bar" ||
      type === "donut" ||
      type === "stacked-bar" ||
      type === "waterfall" ||
      type === "revenue-composition" ||
      type === "treemap" ||
      type === "scatter-plot" ||
      type === "pareto-chart" ||
      type === "utilization-board" ||
      type === "schedule-list" ||
      type === "patient-dossier-card"
    )
      return "l";
    if (type === "dual-axis-trend" || type === "timeline-lanes" || type === "status-matrix" || type === "radial-gauge" || type === "action-list" || type === "bar-list")
      return "m";
    if (type === "credit-float") return "strip";
    if (type === "bullet" || type === "scrubber") return type === "scrubber" ? "full" : "s";
    if (type === "heatmap" || type === "calculator" || type === "categorize" || type === "tax-library")
      return "xl";
    if (type === "ebitda-scrubber" || type === "filing-workflow" || type === "claim-shelf") return "full";
    if (type === "scenario-manager" || type === "workpaper") return type === "scenario-manager" ? "xl" : "l";
    if (type === "workpaper-scrubber" || type === "claim-detail-card") return "full";
    if (type === "collection-task-list" || type === "huddle-mosaic" || type === "batch-selector") return "full";
    if (type === "attachment-dropzone" || type === "payer-reference-card") return "full";
    if (type === "era-matching-table" || type === "forecast-trend-line" || type === "period-variance-chart")
      return "full";
    if (type === "data-table" || type === "tax-calendar" || type === "task-board") return "full";
    if (type === "status") return "s";
    if (type === "quarantine-panel") return "full";
    if (type === "ai-insight") return "l";
    return "s";
  }

  const config = {
    refreshInterval: 30 * 60 * 1000, // 30 minutes — avoid page flicker from silent widget polls
    apiBase: "/api/apex",
    halChatEndpoint: "/api/hal/evaluate-query",
    animStagger: 50,
  };

  const ICONS = {
    print:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9V3h12v6"/><path d="M6 17H4a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-2"/><rect x="6" y="13" width="12" height="8" rx="1"/></svg>',
    refresh:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12a9 9 0 1 1-2.6-6.3"/><polyline points="21 3 21 9 15 9"/></svg>',
  };

  let sessionToken = "";
  let currentPage = "financial";
  let currentSub = null;
  let currentQuery = {};
  let refreshTimer = null;
  const widgets = new Map();
  let lastHalStatus = null;
  let halChatBusy = false;
  /** Persist HAL chat across remounts so hover/silent refresh cannot wipe replies. */
  const halTranscript = [];
  const HAL_TRANSCRIPT_MAX = 80;

  const stage = () => document.getElementById("apex-stage");
  const metaEl = () => document.getElementById("apex-meta");

  async function ensureSessionToken(forceRefresh) {
    if (sessionToken && !forceRefresh) return sessionToken;
    try {
      const res = await fetch("/api/app-info", {
        cache: "no-store",
        credentials: "same-origin",
      });
      const refresh = res.headers.get(REFRESH_HEADER);
      if (refresh) sessionToken = refresh.trim();
      if (!res.ok) return sessionToken || "";
      const info = await res.json();
      sessionToken = String((info && (info.sessionToken || info.csrfToken)) || sessionToken || "").trim();
    } catch (_err) {
      if (!sessionToken) sessionToken = "";
    }
    return sessionToken;
  }

  function captureSessionRefresh(res) {
    if (!res || !res.headers) return "";
    const rotated =
      res.headers.get(REFRESH_HEADER) ||
      res.headers.get(SESSION_HEADER) ||
      res.headers.get("X-NR2-Session") ||
      "";
    if (rotated) sessionToken = rotated.trim();
    return rotated.trim();
  }

  async function apexFetch(url, options, _retried) {
    const opts = Object.assign({ credentials: "same-origin", cache: "no-store" }, options || {});
    opts.headers = Object.assign({}, opts.headers || {});
    const token = await ensureSessionToken(Boolean(_retried));
    if (token) opts.headers[SESSION_HEADER] = token;
    const isForm = typeof FormData !== "undefined" && opts.body instanceof FormData;
    if (opts.body && !isForm && !opts.headers["Content-Type"]) {
      opts.headers["Content-Type"] = "application/json";
    }
    const res = await fetch(url, opts);
    const refreshed = captureSessionRefresh(res);
    if (res.status === 403 && !_retried) {
      // Stale token / binding after NR2 restart — always re-bind via app-info and retry once.
      sessionToken = refreshed || "";
      await ensureSessionToken(true);
      if (sessionToken) {
        return apexFetch(url, options, true);
      }
    }
    return res;
  }

  function formatMoney(n) {
    if (n === null || n === undefined || n === "") return null;
    const num = Number(n);
    if (!Number.isFinite(num)) return null;
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    }).format(num);
  }

  function formatCount(n) {
    if (n === null || n === undefined || n === "") return null;
    const num = Number(n);
    if (!Number.isFinite(num)) return null;
    return new Intl.NumberFormat("en-US").format(num);
  }

  class Widget {
    constructor(spec) {
      this.spec = spec || {};
      this.id = String(this.spec.id || "");
      this.type = String(this.spec.type || "kpi");
      this.element = null;
    }

    render(index) {
      const el = document.createElement("article");
      const size = instrumentSize(this.spec);
      el.className = `apex-widget apex-inst apex-inst--${size}`;
      el.dataset.widgetId = this.id;
      el.style.animationDelay = `${index * config.animStagger}ms`;
      if (this.type === "hal-chat") {
        el.classList.add("apex-widget--hal-chat", "apex-inst--hal-chat");
      }
      if (this.spec.alert) {
        el.classList.add("apex-alert-pulse");
        if (this.spec.alertReason) el.title = String(this.spec.alertReason);
      }
      if (this.spec.status === "awaiting-migration" || this.spec.status === "empty") {
        el.classList.add("apex-widget--status");
        el.dataset.empty = "true";
      }
      el.innerHTML = this.getTemplate();
      this.element = el;
      this.attachEvents();
      this.mountChart();
      this.maybeRollup();
      return el;
    }

    getTemplate() {
      const label = this.escape(this.spec.label || this.id || "Widget");
      const printBtn = `<button type="button" class="apex-icon-btn" data-action="print" title="Print">${ICONS.print}</button>`;

      if (this.type === "hal-chat") {
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
          </header>
          <div class="apex-hal-chat" data-hal-chat>
            <div class="apex-hal-chat__messages" data-hal-messages aria-live="polite"></div>
            <div class="apex-hal-chat__chips" data-hal-chips></div>
            <form class="apex-hal-chat__form" data-hal-form>
              <textarea class="apex-hal-chat__input" data-hal-input rows="2" placeholder="Ask HAL…" aria-label="Ask HAL"></textarea>
              <button type="submit" class="apex-hal-chat__send" data-hal-send>Send</button>
            </form>
            <div class="apex-kpi-hint">${this.escape(this.spec.hint || "Local HAL command surface")}</div>
          </div>
        `;
      }

      if (this.type === "ai-insight") {
        const insight = this.spec.insight && typeof this.spec.insight === "object" ? this.spec.insight : null;
        const empty = this.spec.status === "empty" || !insight;
        if (empty) {
          return `
            <header class="apex-widget-header">
              <span class="apex-widget-label">${label}</span>
              ${printBtn}
            </header>
            <div class="apex-kpi-value is-empty">${this.escape(this.spec.emptyMessage || "No structured insight")}</div>
            <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
          `;
        }
        const data = insight.data && typeof insight.data === "object" ? insight.data : {};
        const refs = Array.isArray(insight.source_refs) ? insight.source_refs : [];
        const conf = this.escape(String(insight.confidence || ""));
        const wt = this.escape(String(insight.widget_type || ""));
        let body = "";
        if (insight.widget_type === "kpi-card") {
          const unit = data.unit === "dollars" ? "$" : data.unit === "percent" ? "%" : "";
          const val =
            data.value == null || data.value === ""
              ? "—"
              : unit === "$"
                ? formatMoney(data.value)
                : unit === "%"
                  ? `${Number(data.value).toFixed(1)}%`
                  : String(data.value);
          body = `<div class="apex-kpi-value">${this.escape(val)}</div>
            <div class="apex-kpi-hint">${this.escape(data.trend_direction || "")} ${
            data.trend_percent != null ? this.escape(String(data.trend_percent) + "%") : ""
          }</div>`;
        } else if (insight.widget_type === "trend-chart") {
          const series = Array.isArray(data.series) ? data.series : [];
          body = `<ul class="apex-huddle-list">${series
            .map(
              (s) =>
                `<li class="apex-huddle-item">${this.escape((s && s.label) || "")}: ${
                  s && s.value != null ? this.escape(String(s.value)) : "—"
                }</li>`
            )
            .join("")}</ul>`;
        } else if (insight.widget_type === "alert-banner") {
          body = `<div class="hal-insight-banner"><div class="apex-kpi-value">${this.escape(String(data.severity || "info").toUpperCase())}</div>
            <div class="apex-kpi-hint">${this.escape(String(data.message || ""))}</div></div>`;
        }
        const cta =
          insight.action_cta && insight.action_cta.route
            ? `<button type="button" class="apex-btn apex-btn--small" data-insight-route="${this.escape(
                insight.action_cta.route
              )}">${this.escape(insight.action_cta.label || "Open")}</button>`
            : "";
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            <span class="apex-kpi-hint">${wt} · ${conf}</span>
            ${printBtn}
          </header>
          ${body}
          <p class="apex-kpi-hint">${this.escape(String(insight.explanation || ""))}</p>
          <div class="apex-kpi-hint">sources: ${this.escape(refs.join(" · ") || "—")}</div>
          ${cta}
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "quarantine-panel") {
        const items = Array.isArray(this.spec.items) ? this.spec.items : [];
        const rows = items.length
          ? `<table class="apex-q-table" data-quarantine-table>
              <thead><tr><th>File</th><th>Error</th><th>Attempts</th><th></th></tr></thead>
              <tbody>
                ${items
                  .map((it) => {
                    const name = this.escape(String((it && it.name) || ""));
                    const err = this.escape(String((it && (it.error_code || it.error)) || "—"));
                    const attempts =
                      it && it.row_count != null ? this.escape(String(it.row_count)) : "—";
                    return `<tr data-q-name="${name}">
                      <td class="apex-q-name">${name}</td>
                      <td>${err}</td>
                      <td>${attempts}</td>
                      <td class="apex-q-actions">
                        <button type="button" class="apex-btn apex-btn--small" data-q-retry="${name}">Retry</button>
                        <button type="button" class="apex-btn apex-btn--small" data-q-purge="${name}">Purge</button>
                      </td>
                    </tr>`;
                  })
                  .join("")}
              </tbody>
            </table>`
          : `<div class="apex-kpi-value is-empty">${this.escape(
              this.spec.message || "No quarantined imports"
            )}</div>`;
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            <button type="button" class="apex-btn apex-btn--small" data-q-refresh>Refresh</button>
            ${printBtn}
          </header>
          ${rows}
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "status" || this.spec.status === "awaiting-migration") {
        const checks = Array.isArray(this.spec.checks) ? this.spec.checks : [];
        const actions = Array.isArray(this.spec.actions) ? this.spec.actions : [];
        const checkHtml = checks.length
          ? `<ul class="apex-c0-checks">${checks
              .map(
                (c) =>
                  `<li class="${c.ok ? "is-ok" : "is-gap"}"><span>${c.ok ? "✓" : "○"}</span> ${this.escape(
                    c.label || ""
                  )}<small>${this.escape(c.detail || "")}</small></li>`
              )
              .join("")}</ul>`
          : "";
        const actionHtml = actions.length
          ? `<ol class="apex-c0-actions">${actions
              .map((a) => `<li>${this.escape(a.label || a.id || "")}</li>`)
              .join("")}</ol>`
          : "";
        const refreshBtn = this.spec.refreshUrl
          ? `<button type="button" class="apex-btn apex-btn--small" data-c0-refresh>Refresh SoftDent period imports</button>`
          : "";
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          <div class="apex-kpi-value is-empty" data-kpi-value>${this.escape(this.spec.message || "Awaiting migration")}</div>
          ${checkHtml}
          ${actionHtml}
          ${refreshBtn}
          <div class="apex-kpi-hint" data-kpi-hint>${this.escape(this.spec.hint || "Phased Apex migration.")}</div>
        `;
      }

      if (this.type === "chart" || this.type === "bar" || this.type === "line") {
        const empty = !(this.spec.series && this.spec.series.length) && !(this.spec.values && this.spec.values.length);
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            <div class="apex-widget-actions">
              <button type="button" class="apex-icon-btn" data-action="focus" title="Focus">⛶</button>
              ${printBtn}
            </div>
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty" data-kpi-value>${this.escape(this.spec.emptyMessage || "No chart data")}</div>
                 <div class="apex-kpi-hint" data-kpi-hint>${this.escape(this.spec.hint || "Import SoftDent / financial exports to populate.")}</div>`
              : `<div class="apex-chart-host"><canvas data-chart></canvas></div>
                 <div class="apex-kpi-hint" data-kpi-hint>${this.escape(this.spec.hint || "")}</div>`
          }
        `;
      }

      if (this.type === "horizontal-bar") {
        const bars = Array.isArray(this.spec.bars) ? this.spec.bars : [];
        const empty = !bars.length;
        const max = Math.max(...bars.map((b) => Number(b.value) || 0), 1);
        const rows = bars
          .map((b) => {
            const v = Number(b.value) || 0;
            const pct = Math.max(4, Math.round((v / max) * 100));
            return `<div class="apex-hbar-row">
              <span class="apex-hbar-label">${this.escape(b.label || "")}</span>
              <div class="apex-hbar-track"><i style="width:${pct}%"></i></div>
              <span class="apex-hbar-val">${this.escape(formatMoney(v) || String(v))}</span>
            </div>`;
          })
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty">${this.escape(this.spec.emptyMessage || "No bars")}</div>`
              : `<div class="apex-hbar">${rows}</div>`
          }
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "donut") {
        const slices = Array.isArray(this.spec.slices) ? this.spec.slices : [];
        const empty = !slices.length;
        const total = slices.reduce((a, s) => a + (Number(s.value) || 0), 0) || 1;
        let acc = 0;
        const colors = ["#00f0ff", "#ffb800", "#ff0066", "#7cffc4", "#a78bfa", "#38bdf8"];
        const stops = slices
          .map((s, i) => {
            const v = Number(s.value) || 0;
            const start = (acc / total) * 100;
            acc += v;
            const end = (acc / total) * 100;
            return `${colors[i % colors.length]} ${start}% ${end}%`;
          })
          .join(", ");
        const legend = slices
          .map((s, i) => {
            const v = Number(s.value) || 0;
            const pct = Math.round((v / total) * 100);
            const disp =
              this.spec.unit === "count" ? formatCount(v) : formatMoney(v) || String(v);
            return `<div class="apex-donut-leg"><i style="background:${colors[i % colors.length]}"></i>
              <span>${this.escape(s.label || "")}</span>
              <strong>${this.escape(disp || "")} · ${pct}%</strong></div>`;
          })
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty">${this.escape(this.spec.emptyMessage || "No slices")}</div>`
              : `<div class="apex-donut-wrap">
                  <div class="apex-donut" style="background:conic-gradient(${stops})"></div>
                  <div class="apex-donut-legend">${legend}</div>
                </div>`
          }
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "bullet") {
        const empty = this.spec.status === "empty" || this.spec.value == null;
        const val = Number(this.spec.value) || 0;
        const pct = Math.max(0, Math.min(110, val));
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty" data-kpi-value>${this.escape(this.spec.emptyMessage || "No ratio")}</div>`
              : `<div class="apex-kpi-value" data-kpi-value data-rollup="${val}">${this.escape(val.toFixed(1) + "%")}</div>
                 <div class="apex-bullet">
                   <div class="apex-bullet-ranges">
                     <span class="apex-bullet-r apex-bullet-r--warn" style="width:77%"></span>
                     <span class="apex-bullet-r apex-bullet-r--mid" style="width:9%"></span>
                     <span class="apex-bullet-r apex-bullet-r--ok" style="width:14%"></span>
                   </div>
                   <div class="apex-bullet-marker" style="left:${Math.min(100, (pct / 110) * 100)}%"></div>
                 </div>`
          }
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "waterfall") {
        const data = this.spec.data && typeof this.spec.data === "object" ? this.spec.data : {};
        const steps = Array.isArray(this.spec.steps)
          ? this.spec.steps
          : Array.isArray(data.steps)
            ? data.steps
            : [];
        const empty = !steps.length || this.spec.status === "empty";
        const showCite = !!this.spec.showCitations;
        const max = Math.max(...steps.map((s) => Math.abs(Number(s.value) || 0)), 1);
        const kindMap = { start: "start", add: "add", sub: "sub", end: "end", positive: "positive", total: "total", negative: "sub" };
        const connMap = { start: "", add: "↑", sub: "↓", end: "=", positive: "", total: "=", negative: "↓" };
        const rows = steps
          .map((s, idx) => {
            const v = s.value;
            const has = v !== null && v !== undefined && Number.isFinite(Number(v));
            const num = has ? Number(v) : 0;
            const pct = has ? Math.max(6, Math.round((Math.abs(num) / max) * 100)) : 6;
            const kind = kindMap[s.kind] || kindMap[s.type] || "positive";
            const citeKey = s.citeKey || "";
            const cite = showCite && s.citation
              ? `<button type="button" class="apex-wf-cite" data-cite-key="${this.escape(citeKey)}" title="Open source rows">${this.escape(s.citation)}</button>`
              : "";
            const conn = idx === 0 ? "" : connMap[kind] || "·";
            return `<div class="apex-wf-row apex-wf-row--${this.escape(kind)}${has ? "" : " is-empty"}">
              <span class="apex-wf-conn" aria-hidden="true">${this.escape(conn)}</span>
              <span class="apex-wf-label">${this.escape(s.label || "")}${cite}</span>
              <div class="apex-wf-track"><i style="width:${pct}%"></i></div>
              <span class="apex-wf-val">${this.escape(has ? formatMoney(num) || String(num) : "$—")}</span>
            </div>`;
          })
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            <div class="apex-widget-actions">
              <button type="button" class="apex-icon-btn" data-action="focus" title="Focus">⛶</button>
              ${printBtn}
            </div>
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty">${this.escape(
                  data.emptyMessage || this.spec.emptyMessage || "No steps"
                )}</div>
                 ${steps.length ? `<div class="apex-waterfall apex-waterfall--muted">${rows}</div>` : ""}`
              : `<div class="apex-waterfall">${rows}</div>`
          }
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "stacked-bar") {
        const segs = Array.isArray(this.spec.segments) ? this.spec.segments : [];
        const empty = !segs.length;
        const total = segs.reduce((a, s) => a + (Number(s.value) || 0), 0) || 1;
        const stack = segs
          .map((s) => {
            const v = Number(s.value) || 0;
            const pct = Math.max(4, Math.round((v / total) * 100));
            return `<div class="apex-stack-seg" style="width:${pct}%" title="${this.escape(s.label)}: ${this.escape(
              formatMoney(v) || ""
            )}"><span>${this.escape(s.label)}</span></div>`;
          })
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty">${this.escape(this.spec.emptyMessage || "No split")}</div>`
              : `<div class="apex-stack-bar apex-stack-bar--tall">${stack}</div>
                 <div class="apex-stack-meta">${segs
                   .map(
                     (s) =>
                       `<span>${this.escape(s.label)}: ${this.escape(formatMoney(s.value) || "—")}</span>`
                   )
                   .join(" · ")}</div>`
          }
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "scrubber") {
        const periods = Array.isArray(this.spec.periods) ? this.spec.periods : [];
        const active = String(this.spec.active || "");
        const empty = !periods.length;
        const chips = periods
          .map((p) => {
            const on = String(p) === active ? " is-active" : "";
            return `<button type="button" class="apex-scrub-chip${on}" data-period="${this.escape(p)}">${this.escape(
              p
            )}</button>`;
          })
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty">${this.escape(this.spec.emptyMessage || "No periods")}</div>`
              : `<div class="apex-scrubber" data-scrubber>${chips}</div>`
          }
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "tax-library") {
        const files = Array.isArray(this.spec.files) ? this.spec.files : [];
        const empty = !files.length;
        const rows = files
          .map((f) => {
            const path = encodeURIComponent(f.relPath || "");
            return `<div class="apex-taxlib-row">
              <span class="apex-taxlib-meta">${this.escape(f.year || "—")} · ${this.escape(f.jurisdiction || "—")}</span>
              <span class="apex-taxlib-name">${this.escape(f.name || "")}</span>
              <a class="apex-taxlib-dl" href="/api/apex/tax-returns/file?path=${path}" download>Download</a>
            </div>`;
          })
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty">${this.escape(this.spec.emptyMessage || "No tax returns")}</div>`
              : `<div class="apex-taxlib-list">${rows}</div>`
          }
          <form class="apex-taxlib-upload" data-tax-upload>
            <label>Year <input name="year" type="text" maxlength="4" placeholder="2024" required /></label>
            <label>Jurisdiction
              <select name="jurisdiction">
                <option value="federal">Federal</option>
                <option value="kansas">Kansas</option>
                <option value="other">Other</option>
              </select>
            </label>
            <input name="file" type="file" accept=".pdf,image/*" required />
            <button type="submit" class="apex-btn apex-btn--small">Upload return</button>
          </form>
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "ebitda-scrubber") {
        const empty = this.spec.status === "empty";
        const locked = !!this.spec.locked;
        const sc = this.spec.scrubber || {};
        const bookE = this.spec.bookEbitda;
        const planE = this.spec.planningEbitda;
        const slider = (key, cfg) => {
          if (!cfg) return "";
          const val = cfg.value != null ? cfg.value : cfg.default;
          return `<label class="apex-scrub-slider">
            <span>${this.escape(cfg.label || key)}</span>
            <input type="range" data-scrub-key="${this.escape(key)}"
              min="${Number(cfg.min) || 0}" max="${Number(cfg.max) || 1}" step="${Number(cfg.step) || 1}"
              value="${Number(val) || 0}" ${locked ? "disabled" : ""} />
            <output data-scrub-out="${this.escape(key)}">${this.escape(formatMoney(val) || String(val))}</output>
          </label>`;
        };
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            <div class="apex-widget-actions">
              <button type="button" class="apex-icon-btn" data-action="focus" title="Focus">⛶</button>
              ${printBtn}
            </div>
          </header>
          <div class="apex-ebitda-banner">${this.escape(this.spec.disclaimer || "PLANNING ONLY — NOT BOOKED TO QUICKBOOKS")}${
            locked ? " · FILING LOCKED" : ""
          }</div>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty">${this.escape(this.spec.emptyMessage || "Need QB net income")}</div>`
              : `<div class="apex-ebitda-scrub" data-ebitda-scrub
                  data-book-net="${this.spec.bookNetIncome != null ? this.spec.bookNetIncome : ""}"
                  data-book-ebitda="${bookE != null ? bookE : ""}"
                  data-locked="${locked ? "1" : "0"}">
                  <div class="apex-ebitda-cols">
                    <div class="apex-ebitda-col apex-ebitda-col--book">
                      <div class="apex-ebitda-col-title">🔒 Book (locked)</div>
                      <div class="apex-kpi-value" data-book-out>${this.escape(formatMoney(bookE) || "—")}</div>
                      <div class="apex-kpi-hint">From QB imports · ${this.escape(this.spec.periodLabel || "")}</div>
                    </div>
                    <div class="apex-ebitda-col apex-ebitda-col--plan">
                      <div class="apex-ebitda-col-title">✏️ Planning</div>
                      <div class="apex-kpi-value" data-plan-out>${this.escape(formatMoney(planE) || "—")}</div>
                      <div class="apex-kpi-delta" data-delta-out></div>
                    </div>
                  </div>
                  <div class="apex-ebitda-sliders">
                    ${slider("officerSalary", sc.officerSalary)}
                    ${slider("depreciation", sc.depreciation)}
                    ${slider("interest", sc.interest)}
                    ${slider("oneTime", sc.oneTime)}
                  </div>
                  <div class="apex-ebitda-actions">
                    <button type="button" class="apex-btn apex-btn--small" data-scrub-reset ${locked ? "disabled" : ""}>Restore from Imports</button>
                    <button type="button" class="apex-btn apex-btn--small" data-scrub-save ${locked ? "disabled" : ""}>Save Scenario</button>
                    <input type="text" data-scrub-name placeholder="Scenario name" maxlength="48" ${locked ? "disabled" : ""} />
                    <select data-scrub-load><option value="">Load scenario…</option></select>
                  </div>
                </div>`
          }
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "scenario-manager") {
        const rows = Array.isArray(this.spec.scenarios) ? this.spec.scenarios : [];
        const empty = !rows.length || this.spec.status === "empty";
        const list = rows
          .map((s) => {
            const inputs = s.inputs || {};
            const summary = Object.keys(inputs)
              .slice(0, 4)
              .map((k) => `${k}:${formatMoney(inputs[k]) || inputs[k]}`)
              .join(" · ");
            return `<div class="apex-scenario-row" data-scenario-id="${this.escape(s.id || "")}">
              <label><input type="checkbox" data-compare-id value="${this.escape(s.id || "")}" /> ${this.escape(
              s.name || s.id || ""
            )}</label>
              <span class="apex-scenario-meta">${this.escape((s.savedAt || "").slice(0, 19))} · plan ${this.escape(
              formatMoney(s.planningEbitda) || "—"
            )}</span>
              <span class="apex-scenario-inputs">${this.escape(summary)}</span>
              <button type="button" class="apex-btn apex-btn--small" data-scenario-load>Load</button>
              <button type="button" class="apex-btn apex-btn--small" data-scenario-del>Delete</button>
            </div>`;
          })
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            <div class="apex-widget-actions">
              <button type="button" class="apex-icon-btn" data-action="focus" title="Focus">⛶</button>
              ${printBtn}
            </div>
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty">${this.escape(this.spec.emptyMessage || "No saved scenarios")}</div>`
              : `<div class="apex-scenario-list" data-scenario-manager>${list}
                  <div class="apex-scenario-actions">
                    <button type="button" class="apex-btn apex-btn--small" data-scenario-compare>Compare selected (≤3)</button>
                  </div>
                  <pre class="apex-scenario-diff" data-scenario-diff hidden></pre>
                </div>`
          }
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "filing-workflow") {
        const states = Array.isArray(this.spec.states) ? this.spec.states : ["DRAFT", "CPA_REVIEW", "CLIENT_APPROVED", "FILED", "LOCKED"];
        const cur = String(this.spec.state || "DRAFT");
        const returns = Array.isArray(this.spec.taxReturns) ? this.spec.taxReturns : [];
        const steps = states
          .map((st) => {
            const on = st === cur ? " is-active" : "";
            const done = states.indexOf(st) <= states.indexOf(cur) ? " is-done" : "";
            return `<button type="button" class="apex-filing-step${on}${done}" data-filing-state="${this.escape(st)}">${this.escape(
              st
            )}</button>`;
          })
          .join("");
        const opts = returns
          .map(
            (f) =>
              `<option value="${this.escape(f.relPath || "")}" ${
                f.relPath === this.spec.filedRelPath ? "selected" : ""
              }>${this.escape((f.year || "") + " " + (f.jurisdiction || "") + " · " + (f.name || ""))}</option>`
          )
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            <div class="apex-widget-actions">
              <button type="button" class="apex-icon-btn" data-action="focus" title="Focus">⛶</button>
              ${printBtn}
            </div>
          </header>
          <div class="apex-filing" data-filing-workflow data-current="${this.escape(cur)}">
            <div class="apex-filing-steps">${steps}</div>
            <label class="apex-filing-note">Note <input type="text" data-filing-note maxlength="240" value="${this.escape(
              this.spec.note || ""
            )}" /></label>
            <label class="apex-filing-path">Library PDF
              <select data-filing-path>
                <option value="">Select tax return…</option>
                ${opts}
              </select>
            </label>
            <form class="apex-filing-upload" data-filing-upload>
              <input name="year" type="text" maxlength="4" placeholder="Year" required />
              <select name="jurisdiction">
                <option value="federal">Federal</option>
                <option value="kansas">Kansas</option>
                <option value="other">Other</option>
              </select>
              <input name="file" type="file" accept=".pdf,image/*" required />
              <button type="submit" class="apex-btn apex-btn--small">Upload & link</button>
            </form>
            <button type="button" class="apex-btn apex-btn--small" data-filing-apply>Apply state</button>
          </div>
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "workpaper") {
        const empty = this.spec.status === "empty";
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            <div class="apex-widget-actions">
              <button type="button" class="apex-icon-btn" data-action="focus" title="Focus">⛶</button>
              ${printBtn}
            </div>
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty">${this.escape(this.spec.emptyMessage || "Need QB book income")}</div>`
              : `<div class="apex-workpaper" data-workpaper>
                  <button type="button" class="apex-btn" data-workpaper-export>Generate CPA Workpaper</button>
                  <p class="apex-kpi-hint">Opens printable HTML with book-to-tax + EBITDA citations.</p>
                </div>`
          }
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "workpaper-scrubber") {
        const cats = Array.isArray(this.spec.categories) ? this.spec.categories : [];
        const empty = this.spec.status === "empty" || !cats.length;
        const rows = cats
          .map((c) => {
            const id = String((c && c.id) || "");
            const amt =
              c && c.amount != null && Number.isFinite(Number(c.amount))
                ? formatMoney(c.amount)
                : "—";
            return `<tr data-wp-cat="${this.escape(id)}">
              <td><label class="apex-wp-flag"><input type="checkbox" data-cpa-flag value="${this.escape(
                id
              )}" /> Flag</label></td>
              <td>${this.escape((c && c.label) || "")}</td>
              <td class="apex-num">${this.escape(amt || "—")}</td>
              <td class="apex-cite">${this.escape((c && c.citation) || "")}</td>
            </tr>`;
          })
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty">${this.escape(
                  this.spec.emptyMessage || "No categories"
                )}</div>`
              : `<div class="apex-workpaper-scrubber" data-workpaper-scrubber>
                  <table class="apex-cite-table">
                    <thead><tr><th>CPA</th><th>Category</th><th>Amount</th><th>Citation</th></tr></thead>
                    <tbody>${rows}</tbody>
                  </table>
                </div>`
          }
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "claim-detail-card") {
        const claim = this.spec.claim && typeof this.spec.claim === "object" ? this.spec.claim : null;
        const empty = this.spec.status === "empty" || !claim;
        if (empty) {
          return `
            <header class="apex-widget-header">
              <span class="apex-widget-label">${label}</span>
              ${printBtn}
            </header>
            <div class="apex-kpi-value is-empty">${this.escape(
              this.spec.emptyMessage || "No claim selected"
            )}</div>
            <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
            <div class="apex-claim-detail-actions">
              <button type="button" class="apex-btn" data-back-claims>Back to Claims</button>
            </div>
          `;
        }
        const procs = Array.isArray(claim.procedures) ? claim.procedures.join(", ") : "—";
        const billed =
          claim.billedAmount != null && Number.isFinite(Number(claim.billedAmount))
            ? formatMoney(claim.billedAmount)
            : "— (not on import)";
        const cid = String(claim.claimId || this.spec.claimId || "");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          <dl class="apex-claim-dl apex-claim-detail-card" data-claim-detail data-claim-id="${this.escape(cid)}">
            <div><dt>Claim ID</dt><dd>${this.escape(cid)}</dd></div>
            <div><dt>Patient</dt><dd>${this.escape(claim.patientInitials || claim.patientName || "—")}</dd></div>
            <div><dt>Date of service</dt><dd>${this.escape(claim.date || "—")}</dd></div>
            <div><dt>Age (days)</dt><dd>${this.escape(
              claim.ageDays != null ? String(claim.ageDays) : "—"
            )}</dd></div>
            <div><dt>Payer</dt><dd>${this.escape(claim.payer || "—")}</dd></div>
            <div><dt>Status</dt><dd>${this.escape(claim.status || "—")}</dd></div>
            <div><dt>Procedures</dt><dd>${this.escape(procs)}</dd></div>
            <div><dt>Billed</dt><dd>${this.escape(billed)}</dd></div>
          </dl>
          <div class="apex-claim-detail-actions">
            <button type="button" class="apex-btn" data-back-claims>Back to Claims</button>
            <button type="button" class="apex-btn apex-btn--primary" data-draft-narrative-sub>Draft Narrative</button>
          </div>
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "collection-task-list") {
        const seeds = Array.isArray(this.spec.seeds) ? this.spec.seeds : [];
        const notes = Array.isArray(this.spec.notes) ? this.spec.notes : [];
        const empty = this.spec.status === "empty" && !seeds.length && !notes.length;
        const seedRows = seeds
          .map((s) => {
            const cid = String((s && s.claimId) || "");
            const amt =
              s && s.billedAmount != null && Number.isFinite(Number(s.billedAmount))
                ? formatMoney(s.billedAmount)
                : "—";
            return `<tr>
              <td>${this.escape(cid)}</td>
              <td>${this.escape((s && s.patientInitials) || "—")}</td>
              <td>${this.escape(String((s && s.ageDays) != null ? s.ageDays : "—"))}</td>
              <td>${this.escape((s && s.bucket) || "—")}</td>
              <td>${this.escape(amt || "—")}</td>
              <td><button type="button" class="apex-btn apex-btn--small" data-col-seed-claim="${this.escape(
                cid
              )}" data-col-initials="${this.escape((s && s.patientInitials) || "")}">Log</button></td>
            </tr>`;
          })
          .join("");
        const noteRows = notes
          .map((n) => {
            return `<tr>
              <td>${this.escape((n && n.claimId) || "")}</td>
              <td>${this.escape((n && n.patientInitials) || "—")}</td>
              <td>${this.escape((n && n.status) || "")}</td>
              <td>${this.escape((n && n.followUp) || "—")}</td>
              <td colspan="2">${this.escape((n && n.note) || "")}</td>
            </tr>`;
          })
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty">${this.escape(
                  this.spec.emptyMessage || "No collection items"
                )}</div>`
              : `<div class="apex-collection-bench" data-collection-bench>
                  <form class="apex-col-form" data-col-form>
                    <input name="claimId" placeholder="Claim ID" required />
                    <input name="patientInitials" placeholder="Initials" maxlength="8" />
                    <select name="status">
                      <option value="called">called</option>
                      <option value="promised">promised</option>
                      <option value="disputed">disputed</option>
                      <option value="open">open</option>
                      <option value="closed">closed</option>
                    </select>
                    <input name="followUp" placeholder="Follow-up YYYY-MM-DD" />
                    <input name="note" placeholder="Note (local only)" />
                    <button type="submit" class="apex-btn apex-btn--primary">Save note</button>
                  </form>
                  <h3 class="apex-subhead">Aged claim seeds</h3>
                  <table class="apex-cite-table"><thead><tr>
                    <th>Claim</th><th>Pt</th><th>Age</th><th>Bucket</th><th>Billed</th><th></th>
                  </tr></thead><tbody>${seedRows || "<tr><td colspan='6'>None</td></tr>"}</tbody></table>
                  <h3 class="apex-subhead">Local notes</h3>
                  <table class="apex-cite-table"><thead><tr>
                    <th>Claim</th><th>Pt</th><th>Status</th><th>Follow-up</th><th colspan="2">Note</th>
                  </tr></thead><tbody>${noteRows || "<tr><td colspan='6'>None yet</td></tr>"}</tbody></table>
                </div>`
          }
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "huddle-mosaic") {
        const priorities = Array.isArray(this.spec.priorities) ? this.spec.priorities : [];
        const history = Array.isArray(this.spec.history) ? this.spec.history : [];
        const tasks = Array.isArray(this.spec.tasks) ? this.spec.tasks : [];
        const list = priorities
          .map((p) => `<li class="apex-huddle-item">${this.escape(String(p))}</li>`)
          .join("");
        const hist = history
          .map(
            (h) =>
              `<li class="apex-huddle-hist">${this.escape((h && h.createdAt) || "")} · ${this.escape(
                String(((h && h.priorities) || []).length)
              )} items</li>`
          )
          .join("");
        const taskRows = tasks
          .map(
            (t) =>
              `<li class="apex-huddle-task">${this.escape((t && t.title) || "")}${
                t && t.dueDate ? " · due " + this.escape(t.dueDate) : ""
              }</li>`
          )
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          <div class="apex-huddle-mosaic" data-huddle-mosaic>
            <ol class="apex-huddle-list">${list || `<li class="apex-huddle-item">No priorities flagged</li>`}</ol>
            <div class="apex-claim-detail-actions">
              <button type="button" class="apex-btn apex-btn--primary" data-huddle-save>Save huddle snapshot</button>
            </div>
            <form class="apex-col-form" data-huddle-task-form>
              <input name="title" placeholder="New office task" required />
              <input name="assignee" placeholder="Assignee" />
              <input name="dueDate" placeholder="Due YYYY-MM-DD" />
              <button type="submit" class="apex-btn">Add task</button>
            </form>
            <h3 class="apex-subhead">Open tasks</h3>
            <ul class="apex-huddle-list">${taskRows || "<li class='apex-huddle-item'>None</li>"}</ul>
            <h3 class="apex-subhead">Recent huddle history</h3>
            <ul class="apex-huddle-list">${hist || "<li class='apex-huddle-item'>None saved yet</li>"}</ul>
          </div>
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "batch-selector") {
        const cands = Array.isArray(this.spec.candidates) ? this.spec.candidates : [];
        const empty = this.spec.status === "empty" || !cands.length;
        const rows = cands
          .map((c) => {
            const cid = String((c && c.claimId) || "");
            const amt =
              c && c.billedAmount != null && Number.isFinite(Number(c.billedAmount))
                ? formatMoney(c.billedAmount)
                : "—";
            return `<tr>
              <td><input type="checkbox" data-batch-claim value="${this.escape(cid)}" /></td>
              <td>${this.escape(cid)}</td>
              <td>${this.escape((c && c.patientInitials) || "—")}</td>
              <td>${this.escape((c && c.payer) || "—")}</td>
              <td>${this.escape(String((c && c.ageDays) != null ? c.ageDays : "—"))}</td>
              <td>${this.escape((c && c.status) || "—")}</td>
              <td>${this.escape(amt || "—")}</td>
            </tr>`;
          })
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            <div class="apex-widget-actions">
              <button type="button" class="apex-btn apex-btn--primary" data-batch-seed>Seed Narratives</button>
              ${printBtn}
            </div>
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty">${this.escape(
                  this.spec.emptyMessage || "No candidates"
                )}</div>`
              : `<div class="apex-batch-selector" data-batch-selector>
                  <table class="apex-cite-table">
                    <thead><tr>
                      <th></th><th>Claim</th><th>Pt</th><th>Payer</th><th>Age</th><th>Status</th><th>Billed</th>
                    </tr></thead>
                    <tbody>${rows}</tbody>
                  </table>
                </div>`
          }
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "attachment-dropzone") {
        const items = Array.isArray(this.spec.items) ? this.spec.items : [];
        const empty = this.spec.status === "empty" || !items.length;
        const prefill = String(this.spec.claimId || "");
        const rows = items
          .map(
            (it) =>
              `<div class="apex-att-row"><strong>${this.escape(it.claimId || "")}</strong>
              <span>${this.escape(it.filename || "")}</span>
              <span class="apex-kpi-hint">${this.escape(String(it.bytes != null ? it.bytes + " B" : ""))} · ${this.escape(
                it.at || ""
              )}</span></div>`
          )
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          <div class="apex-dropzone" data-attachment-dropzone>
            <form class="apex-att-upload apex-col-form" data-claim-att-upload>
              <input type="text" name="claimId" placeholder="Claim ID" value="${this.escape(prefill)}" required />
              <input type="file" name="file" accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg" required />
              <input type="text" name="note" placeholder="Note (optional)" />
              <button type="submit" class="apex-btn apex-btn--primary">Upload</button>
            </form>
            <p class="apex-kpi-hint">Dropzone: PDF / PNG / JPG · max 10MB · ${this.escape(
              this.spec.storageRoot || "local claim_attachments"
            )}</p>
            ${
              empty
                ? `<div class="apex-kpi-value is-empty">${this.escape(
                    this.spec.emptyMessage || "No attachments"
                  )}</div>`
                : `<div class="apex-att-list">${rows}</div>`
            }
          </div>
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "payer-reference-card") {
        const payers = Array.isArray(this.spec.payers) ? this.spec.payers : [];
        const empty = this.spec.status === "empty" || !payers.length;
        const cards = payers
          .map(
            (p) => `<article class="apex-payer-card">
              <h3>${this.escape((p && p.payerName) || "")}</h3>
              <p class="apex-kpi-hint">Appeal deadline: ${this.escape(
                p && p.appealDeadlineDays != null ? String(p.appealDeadlineDays) + " days" : "—"
              )} · Contact: ${this.escape((p && p.contact) || "—")}</p>
              <p>${this.escape((p && p.guidelines) || "")}</p>
            </article>`
          )
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          <div class="apex-payer-lib" data-payer-reference>
            <form class="apex-col-form" data-payer-form>
              <input name="payerName" placeholder="Payer name" required />
              <input name="appealDeadlineDays" placeholder="Appeal days" />
              <input name="contact" placeholder="Contact" />
              <input name="guidelines" placeholder="Guidelines / requirements" />
              <button type="submit" class="apex-btn apex-btn--primary">Save payer</button>
            </form>
            ${
              empty
                ? `<div class="apex-kpi-value is-empty">${this.escape(
                    this.spec.emptyMessage || "No payers"
                  )}</div>`
                : `<div class="apex-payer-grid">${cards}</div>`
            }
          </div>
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "era-matching-table") {
        const rows = Array.isArray(this.spec.rows) ? this.spec.rows : [];
        const history = Array.isArray(this.spec.history) ? this.spec.history : [];
        const empty = this.spec.status === "empty" || !rows.length;
        const body = rows
          .map((r) => {
            const paid =
              r && r.paidAmount != null && Number.isFinite(Number(r.paidAmount))
                ? formatMoney(r.paidAmount)
                : "—";
            const conf =
              r && r.confidence != null && Number.isFinite(Number(r.confidence))
                ? (Number(r.confidence) * 100).toFixed(0) + "%"
                : "—";
            return `<tr>
              <td>${this.escape((r && r.claimId) || "")}</td>
              <td>${this.escape((r && r.patientInitials) || "—")}</td>
              <td>${this.escape(conf)}</td>
              <td>${this.escape(paid || "—")}</td>
              <td>${this.escape((r && r.denialCode) || "—")}</td>
              <td>${this.escape((r && r.sourceFile) || "—")}</td>
            </tr>`;
          })
          .join("");
        const hist = history
          .map(
            (h) =>
              `<li>${this.escape((h && h.at) || "")} · ${this.escape((h && h.filename) || "era")} · matched ${this.escape(
                String((h && h.matchedCount) != null ? h.matchedCount : "—")
              )}/${this.escape(String((h && h.segmentCount) != null ? h.segmentCount : "—"))}</li>`
          )
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          <div class="apex-era-table" data-era-matching>
            <form class="apex-att-upload apex-col-form" data-era-upload title="Upload ERA/835 text">
              <input type="file" name="file" accept=".txt,.835,.era,*" required />
              <button type="submit" class="apex-btn apex-btn--primary">Ingest ERA 835</button>
            </form>
            ${
              empty
                ? `<div class="apex-kpi-value is-empty">${this.escape(
                    this.spec.emptyMessage || "Awaiting ERA 835 Pipeline"
                  )}</div>`
                : `<table class="apex-cite-table"><thead><tr>
                    <th>Claim</th><th>Pt</th><th>Conf</th><th>Paid</th><th>Code</th><th>File</th>
                  </tr></thead><tbody>${body}</tbody></table>`
            }
            <h3 class="apex-subhead">Ingest history</h3>
            <ul class="apex-huddle-list">${hist || "<li>None yet</li>"}</ul>
          </div>
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "forecast-trend-line") {
        const points = Array.isArray(this.spec.points) ? this.spec.points : [];
        const empty = this.spec.status === "empty" || this.spec.blocked || !points.length;
        const max = Math.max(...points.map((p) => Number(p.value) || 0), 1);
        const bars = points
          .map((p) => {
            const v = Number(p.value) || 0;
            const pct = Math.max(6, Math.round((v / max) * 100));
            return `<div class="apex-forecast-col" title="${this.escape(p.label || "")}: ${this.escape(
              String(v)
            )}">
              <div class="apex-forecast-bar" style="height:${pct}%"></div>
              <span>${this.escape(String(p.label || "").slice(5) || p.label || "")}</span>
            </div>`;
          })
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty">${this.escape(
                  this.spec.emptyMessage || "Awaiting ERA 835 Pipeline"
                )}</div>`
              : `<div class="apex-forecast-trend" data-forecast-trend>${bars}</div>`
          }
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "period-variance-chart") {
        const bars = Array.isArray(this.spec.bars) ? this.spec.bars : [];
        const empty = this.spec.status === "empty" || this.spec.blocked || !bars.length;
        const max = Math.max(...bars.map((b) => Math.abs(Number(b.value) || 0)), 1);
        const rows = bars
          .map((b) => {
            const v = Number(b.value) || 0;
            const pct = Math.max(6, Math.round((Math.abs(v) / max) * 100));
            const neg = v < 0;
            return `<div class="apex-var-row${neg ? " is-down" : ""}">
              <span class="apex-var-label">${this.escape((b && b.label) || "")}</span>
              <div class="apex-var-track"><i style="width:${pct}%"></i></div>
              <span class="apex-var-val">${this.escape(formatMoney(v) || String(v))}</span>
            </div>`;
          })
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty">${this.escape(
                  this.spec.emptyMessage || "Awaiting multi-period imports"
                )}</div>`
              : `<div class="apex-period-variance" data-period-variance>${rows}</div>`
          }
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "data-table") {
        const cols = Array.isArray(this.spec.columns) ? this.spec.columns : [];
        const rows = Array.isArray(this.spec.rows) ? this.spec.rows : [];
        const empty = this.spec.status === "empty" || !rows.length;
        const head = cols.map((c) => `<th>${this.escape(c)}</th>`).join("");
        const body = rows
          .map((r) => {
            const cells = cols
              .map((c) => {
                let v = r && r[c];
                if (c.toLowerCase().includes("amount") || c === "fee" || c === "billedAmount") {
                  v =
                    v != null && Number.isFinite(Number(v)) ? formatMoney(v) : v == null ? "—" : v;
                }
                return `<td>${this.escape(v == null ? "—" : String(v))}</td>`;
              })
              .join("");
            return `<tr>${cells}</tr>`;
          })
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty">${this.escape(
                  this.spec.emptyMessage || "No rows"
                )}</div>`
              : `<div class="apex-data-table-wrap"><table class="apex-cite-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`
          }
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "tax-calendar") {
        const items = Array.isArray(this.spec.items) ? this.spec.items : [];
        const empty = this.spec.status === "empty" || !items.length;
        const cards = items
          .map((it) => {
            const amt =
              it && it.amount != null && Number.isFinite(Number(it.amount))
                ? formatMoney(it.amount)
                : "—";
            return `<article class="apex-payer-card">
              <h3>${this.escape((it && it.label) || "Q")}</h3>
              <p><strong>${this.escape(amt || "—")}</strong> · due ${this.escape((it && it.due) || "—")}</p>
              <p class="apex-kpi-hint">${it && it.logged ? "Payment logged (local)" : "Not logged"}</p>
              <button type="button" class="apex-btn apex-btn--small" data-tax-log="${this.escape(
                (it && it.label) || ""
              )}">Log payment</button>
            </article>`;
          })
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty">${this.escape(
                  this.spec.emptyMessage || "No quarters"
                )}</div>`
              : `<div class="apex-payer-grid" data-tax-calendar>${cards}</div>`
          }
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "task-board") {
        const tasks = Array.isArray(this.spec.tasks) ? this.spec.tasks : [];
        const empty = this.spec.status === "empty" && !tasks.length;
        const list = tasks
          .map(
            (t) => `<li class="apex-huddle-task${t && t.done ? " is-done" : ""}">
              <label><input type="checkbox" data-task-toggle="${this.escape(String((t && t.id) || ""))}" ${
              t && t.done ? "checked" : ""
            }/> ${this.escape((t && t.title) || "")}</label>
              <span class="apex-kpi-hint">${this.escape((t && t.assignee) || "")} ${this.escape(
              (t && t.dueDate) || ""
            )}</span>
            </li>`
          )
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          <div class="apex-task-board" data-task-board>
            <form class="apex-col-form" data-task-form>
              <input name="title" placeholder="Task title" required />
              <input name="assignee" placeholder="Assignee" />
              <input name="dueDate" placeholder="Due YYYY-MM-DD" />
              <button type="submit" class="apex-btn apex-btn--primary">Add task</button>
            </form>
            ${
              empty
                ? `<div class="apex-kpi-value is-empty">${this.escape(
                    this.spec.emptyMessage || "No tasks"
                  )}</div>`
                : `<ul class="apex-huddle-list">${list}</ul>`
            }
          </div>
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "pulse") {
        const segs = Array.isArray(this.spec.segments) ? this.spec.segments : [];
        const empty = this.spec.status === "empty" || !segs.length;
        const max = Math.max(...segs.map((s) => Number(s.value) || 0), 1);
        const bars = segs
          .map((s) => {
            const v = Number(s.value) || 0;
            const pct = Math.max(6, Math.round((v / max) * 100));
            return `<div class="apex-pulse-bar" style="height:${pct}%" title="${this.escape(s.label || "")}: ${this.escape(
              formatMoney(v) || String(v)
            )}"></div>`;
          })
          .join("");
        const raw = this.spec.value;
        const display =
          raw !== null && raw !== undefined && Number.isFinite(Number(raw))
            ? formatMoney(raw)
            : this.spec.emptyMessage || "No data";
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          <div class="apex-kpi-value${empty ? " is-empty" : ""}">${this.escape(display)}</div>
          <div class="apex-kpi-delta">${this.escape(this.spec.deltaLabel || "")}</div>
          <div class="apex-pulse-track">${empty ? "" : bars}</div>
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "remainder") {
        const empty = this.spec.status === "empty";
        const segs = Array.isArray(this.spec.segments) ? this.spec.segments : [];
        const total = segs.reduce((a, s) => a + (Number(s.value) || 0), 0) || 1;
        const stack = segs
          .map((s) => {
            const v = Number(s.value) || 0;
            const pct = Math.max(2, Math.round((v / total) * 100));
            return `<div class="apex-stack-seg" style="width:${pct}%" title="${this.escape(s.label)}: ${this.escape(
              formatMoney(v) || ""
            )}"><span>${this.escape(s.label)}</span></div>`;
          })
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty">${this.escape(this.spec.emptyMessage || "No A/R totals")}</div>`
              : `<div class="apex-remainder-grid">
                  <div><span class="apex-mini-label">Gross A/R</span><div class="apex-kpi-value">${this.escape(
                    formatMoney(this.spec.gross) || "—"
                  )}</div></div>
                  <div><span class="apex-mini-label">90+ Priority</span><div class="apex-kpi-value">${this.escape(
                    formatMoney(this.spec.priorityVintage) || "—"
                  )}</div></div>
                  <div><span class="apex-mini-label">Under 90</span><div class="apex-kpi-value">${this.escape(
                    formatMoney(this.spec.underNinety) || "—"
                  )}</div></div>
                </div>
                <div class="apex-stack-bar">${stack}</div>`
          }
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "funnel") {
        const data = this.spec.data && typeof this.spec.data === "object" ? this.spec.data : {};
        let stages = Array.isArray(this.spec.stages)
          ? this.spec.stages
          : Array.isArray(data.stages)
            ? data.stages
            : [];
        const empty = !stages.length || this.spec.status === "empty";
        // Consult empty: single gray stage with — / $—
        if (empty && !stages.length) {
          stages = [{ name: "Presented", stage: "Presented", count: null, value: null, conversionRate: null }];
        }
        const max = Math.max(...stages.map((s) => Number(s.count) || 0), 1);
        const rows = stages
          .map((s, idx) => {
            const n = s.count;
            const has = n !== null && n !== undefined && Number.isFinite(Number(n));
            const num = has ? Number(n) : 0;
            const pct = has ? Math.max(8, Math.round((num / max) * 100)) : empty ? 40 : 8;
            const stageName = s.stage || s.name || "";
            const valHint =
              s.value !== null && s.value !== undefined && Number.isFinite(Number(s.value))
                ? formatMoney(s.value) || String(s.value)
                : "$—";
            const rate =
              !empty && s.conversionRate !== null && s.conversionRate !== undefined
                ? `<span class="apex-funnel-rate apex-funnel-connector">↓ ${this.escape(String(s.conversionRate))}%</span>`
                : idx > 0 && !empty
                  ? `<span class="apex-funnel-connector">↓</span>`
                  : "";
            return `<div class="apex-funnel-row${empty ? " is-empty" : ""}"><span class="apex-funnel-label">${this.escape(
              stageName
            )}</span><div class="apex-funnel-bar"><i style="width:${pct}%"></i></div><span class="apex-funnel-count">${this.escape(
              has ? formatCount(num) || "0" : "—"
            )}</span><span class="apex-funnel-val">${this.escape(valHint)}</span>${rate}</div>`;
          })
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty">${this.escape(
                  data.emptyMessage || this.spec.emptyMessage || "No claims stages"
                )}</div>`
              : ""
          }
          <div class="apex-funnel${empty ? " apex-funnel--empty" : ""}">${rows}</div>
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "treemap") {
        const data = this.spec.data && typeof this.spec.data === "object" ? this.spec.data : {};
        const cats = Array.isArray(data.categories) ? data.categories : [];
        const empty = this.spec.status === "empty" || !cats.length;
        // Consult: SVG <rect> nested proportional layout (squarified-lite row pack)
        const W = 320;
        const H = 140;
        const weights = cats.map((c) => {
          const v = c.value;
          const has = v !== null && v !== undefined && Number.isFinite(Number(v));
          return has ? Math.max(Number(v), 0.01) : 1;
        });
        const sum = weights.reduce((a, b) => a + b, 0) || 1;
        let x = 0;
        const rects = cats
          .map((c, i) => {
            const w = (weights[i] / sum) * W;
            const v = c.value;
            const has = v !== null && v !== undefined && Number.isFinite(Number(v));
            const rawName = String(c.name || "Category—");
            const name = this.escape(rawName.slice(0, 14));
            const val = this.escape(has ? formatMoney(v) || String(v) : "$—");
            const kids = Array.isArray(c.children) ? c.children : [];
            let childRects = "";
            if (kids.length && w > 40) {
              const cw = w / kids.length;
              childRects = kids
                .map((ch, j) => {
                  const cv = ch.value;
                  const chas = cv !== null && cv !== undefined && Number.isFinite(Number(cv));
                  const cx = x + j * cw;
                  return `<rect class="apex-treemap-cell" x="${cx + 1}" y="${H * 0.55}" width="${Math.max(
                    cw - 2,
                    2
                  )}" height="${H * 0.4}" />
                    <text class="apex-treemap-label" x="${cx + 4}" y="${H * 0.7}">${this.escape(
                    String(ch.name || "Sub—").slice(0, 8)
                  )}</text>
                    <text class="apex-treemap-value" x="${cx + 4}" y="${H * 0.85}">${this.escape(
                    chas ? formatMoney(cv) || String(cv) : "$—"
                  )}</text>`;
                })
                .join("");
            }
            const block = `<g class="apex-treemap-g">
              <rect class="apex-treemap-cell" x="${x}" y="0" width="${Math.max(w - 1, 2)}" height="${
              kids.length ? H * 0.52 : H
            }" />
              <text class="apex-treemap-label" x="${x + 4}" y="14">${name}</text>
              <text class="apex-treemap-value" x="${x + 4}" y="28">${val}</text>
              ${childRects}
            </g>`;
            x += w;
            return block;
          })
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty">${this.escape(
                  data.emptyMessage || "Expense hierarchy unavailable"
                )}</div>
                 <svg class="apex-treemap-svg apex-treemap--empty" viewBox="0 0 ${W} ${H}" role="img" aria-label="${label}">
                   <rect class="apex-treemap-cell" x="0" y="0" width="${W / 3 - 2}" height="${H}" />
                   <rect class="apex-treemap-cell" x="${W / 3}" y="0" width="${W / 3 - 2}" height="${H}" />
                   <rect class="apex-treemap-cell" x="${(2 * W) / 3}" y="0" width="${W / 3}" height="${H}" />
                   <text class="apex-treemap-label" x="8" y="18">Category—</text>
                   <text class="apex-treemap-value" x="8" y="34">$—</text>
                   <text class="apex-treemap-label" x="${W / 3 + 8}" y="18">Category—</text>
                   <text class="apex-treemap-value" x="${W / 3 + 8}" y="34">$—</text>
                   <text class="apex-treemap-label" x="${(2 * W) / 3 + 8}" y="18">Category—</text>
                   <text class="apex-treemap-value" x="${(2 * W) / 3 + 8}" y="34">$—</text>
                 </svg>`
              : `<svg class="apex-treemap-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="${label}">
            ${rects}
          </svg>`
          }
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "scatter-plot") {
        const data = this.spec.data && typeof this.spec.data === "object" ? this.spec.data : {};
        const points = Array.isArray(data.points) ? data.points : [];
        const empty = this.spec.status === "empty" || !points.length;
        const xs = points.map((p) => Number(p.x)).filter((n) => Number.isFinite(n));
        const ys = points.map((p) => Number(p.y)).filter((n) => Number.isFinite(n));
        const maxX = Math.max(...xs, 1);
        const maxY = Math.max(...ys, 1);
        const median = (arr) => {
          if (!arr.length) return null;
          const sorted = [...arr].sort((a, b) => a - b);
          const mid = Math.floor(sorted.length / 2);
          return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
        };
        const medX =
          data.medianX != null && Number.isFinite(Number(data.medianX))
            ? Number(data.medianX)
            : median(xs);
        const medY =
          data.medianY != null && Number.isFinite(Number(data.medianY))
            ? Number(data.medianY)
            : median(ys);
        const qx = medX != null ? (medX / maxX) * 100 : 50;
        const qy = medY != null ? 100 - (medY / maxY) * 100 : 50;
        // Consult: SVG <circle> elements + quadrant lines
        const dots = points
          .map((p) => {
            const hasX = p.x !== null && p.x !== undefined && Number.isFinite(Number(p.x));
            const hasY = p.y !== null && p.y !== undefined && Number.isFinite(Number(p.y));
            const x = empty && !hasX && !hasY ? 8 : hasX ? (Number(p.x) / maxX) * 100 : 8;
            const y = empty && !hasX && !hasY ? 92 : hasY ? 100 - (Number(p.y) / maxY) * 100 : 92;
            const r = Math.min(Math.max(Number(p.r) || 5, 3), 14) / 2;
            let tone = "ok";
            if (hasX && hasY && Number(p.y) < Number(p.x) * 0.7) tone = "underpaid";
            if (hasX && hasY && Number(p.y) < Number(p.x) * 0.4) tone = "low-collect";
            return `<circle class="apex-scatter-point apex-scatter-point--${tone}" cx="${x}" cy="${y}" r="${r}" data-x="${x}" data-y="${y}" data-label="${this.escape(
              p.label || p.code || "D—"
            )}"><title>${this.escape(p.label || p.code || "D—")}</title></circle>`;
          })
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            <div class="apex-widget-actions">
              <button type="button" class="apex-icon-btn" data-action="focus" title="Focus">⛶</button>
              ${printBtn}
            </div>
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty">${this.escape(data.emptyMessage || "Cost data unavailable")}</div>`
              : ""
          }
          <div class="apex-scatter" data-scatter>
            <span class="apex-scatter-ylab">${this.escape(data.yLabel || "Net Collection")} ($—)</span>
            <div class="apex-scatter-plot">
              <svg class="apex-scatter-svg" viewBox="0 0 100 100" preserveAspectRatio="none" data-scatter-svg>
                <line class="apex-scatter-quad-svg" x1="${qx}" y1="0" x2="${qx}" y2="100" />
                <line class="apex-scatter-quad-svg" x1="0" y1="${qy}" x2="100" y2="${qy}" />
                ${dots}
                <line class="apex-scatter-cross-v" data-scatter-cross-v x1="0" y1="0" x2="0" y2="100" visibility="hidden" />
                <line class="apex-scatter-cross-h" data-scatter-cross-h x1="0" y1="0" x2="100" y2="0" visibility="hidden" />
              </svg>
            </div>
            <span class="apex-scatter-xlab">${this.escape(data.xLabel || "Billed Fee")} ($—)</span>
          </div>
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "pareto-chart") {
        const data = this.spec.data && typeof this.spec.data === "object" ? this.spec.data : {};
        let bars = Array.isArray(data.bars) ? data.bars : [];
        let cumulative = Array.isArray(data.cumulative) ? data.cumulative : [];
        const threshold = Number(data.threshold) || 80;
        const empty = this.spec.status === "empty" || !bars.length;
        // Consult empty: gray zeroed bars + cumulative hugs 0%
        if (empty && !bars.length) {
          bars = [{ code: "—", amount: null, count: 0, pct: 0 }];
          cumulative = [0];
        }
        const maxPct = Math.max(...bars.map((b) => Number(b.pct) || 0), 1);
        const rows = bars
          .map((b, i) => {
            const pct = Number(b.pct) || 0;
            const width = empty ? 4 : Math.max(4, Math.round((pct / maxPct) * 100));
            const cum = cumulative[i] != null ? cumulative[i] : empty ? 0 : "";
            return `<div class="apex-pareto-row${empty ? " is-empty" : ""}">
              <span class="apex-pareto-code">${this.escape(b.code || "CO—")}</span>
              <div class="apex-pareto-track"><i class="apex-pareto-bar" style="width:${width}%"></i></div>
              <span class="apex-pareto-amt">${this.escape(
                b.amount != null && Number.isFinite(Number(b.amount)) ? formatMoney(b.amount) || String(b.amount) : "$—"
              )}</span>
              <span class="apex-pareto-cum">${this.escape(cum !== "" ? `${cum}%` : "0%")}</span>
            </div>`;
          })
          .join("");
        // Cumulative % on Y; threshold = horizontal line at 80%
        const n = Math.max(bars.length, 1);
        const pts = (cumulative.length ? cumulative : [0])
          .slice(0, bars.length)
          .map((c, i) => {
            const px = ((i + 0.5) / n) * 100;
            const py = 100 - Math.max(0, Math.min(100, Number(c) || 0));
            return `${px},${py}`;
          })
          .join(" ");
        const threshY = 100 - threshold;
        const lineSvg = `<svg class="apex-pareto-svg" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
               <polyline class="apex-pareto-line" points="${pts}" />
               <line class="apex-pareto-threshold" x1="0" y1="${threshY}" x2="100" y2="${threshY}" />
             </svg>`;
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty">${this.escape(data.emptyMessage || "No denials recorded")}</div>`
              : ""
          }
          <div class="apex-pareto${empty ? " apex-pareto--empty" : ""}" style="--pareto-threshold:${threshold}%">
            ${lineSvg}
            ${rows}
          </div>
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "timeline-lanes") {
        const data = this.spec.data && typeof this.spec.data === "object" ? this.spec.data : {};
        let lanes = Array.isArray(data.lanes) ? data.lanes : [];
        const empty = this.spec.status === "empty" || !lanes.length;
        // Consult empty: collapse to single line with zeroed segments
        if (empty && !lanes.length) {
          lanes = [
            {
              code: "D—",
              total: 0,
              segments: [
                { bucket: "0-30", count: 0, color: "cyan" },
                { bucket: "31-60", count: 0, color: "amber" },
                { bucket: "61-90", count: 0, color: "magenta" },
                { bucket: "90+", count: 0, color: "alert" },
              ],
            },
          ];
        }
        const rows = lanes
          .map((lane) => {
            const segs = Array.isArray(lane.segments) ? lane.segments : [];
            const total = segs.reduce((a, s) => a + (Number(s.count) || 0), 0) || 1;
            const segHtml = segs
              .map((s) => {
                const n = Number(s.count) || 0;
                const w = Math.max(n ? 8 : 2, Math.round((n / total) * 100));
                return `<span class="apex-lane-segment apex-lane-segment--${this.escape(
                  s.color || "cyan"
                )}" style="flex:${w}" title="${this.escape(s.bucket || "")}: ${n}">${n}</span>`;
              })
              .join("");
            return `<div class="apex-lane-row">
              <span class="apex-lane-code">${this.escape(lane.code || "D—")}</span>
              <div class="apex-lane-track">${segHtml}</div>
              <span class="apex-lane-total">${this.escape(
                lane.total != null ? String(lane.total) : "0"
              )}</span>
            </div>`;
          })
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty">${this.escape(data.emptyMessage || "No pending pre-auths")}</div>`
              : ""
          }
          <div class="apex-lanes${empty ? " apex-lanes--empty" : ""}">${rows}</div>
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "credit-float") {
        const data = this.spec.data && typeof this.spec.data === "object" ? this.spec.data : {};
        const credits = Array.isArray(data.credits) ? data.credits : [];
        const empty = this.spec.status === "empty" || !credits.length;
        const pills = credits
          .map((c) => {
            const amt =
              c.amount != null && Number.isFinite(Number(c.amount))
                ? formatMoney(c.amount) || String(c.amount)
                : "$—";
            return `<span class="apex-float-pill">${this.escape(c.patientHash || "P—")}: ${this.escape(amt)}</span>`;
          })
          .join("");
        const total =
          data.total != null && Number.isFinite(Number(data.total))
            ? formatMoney(data.total) || String(data.total)
            : "$—";
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          ${
            empty
              ? `<div class="apex-float-strip"><span class="apex-float-pill apex-float-pill--empty">${this.escape(
                  data.emptyMessage || "No unapplied credits"
                )}</span></div>`
              : `<div class="apex-float-strip">
                   <span class="apex-float-label">UNAPPLIED CREDITS</span>
                   <div class="apex-float-pills">${pills}</div>
                   <span class="apex-float-total">Total: ${this.escape(total)}</span>
                 </div>`
          }
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "status-matrix") {
        const data = this.spec.data && typeof this.spec.data === "object" ? this.spec.data : {};
        let patients = Array.isArray(data.patients) ? data.patients : [];
        const empty = this.spec.status === "empty" || !patients.length;
        // Consult empty: all gray dots
        if (empty && !patients.length) {
          patients = [
            { hash: "P—", elig: null, ben: null, breakdown: null },
            { hash: "P—", elig: null, ben: null, breakdown: null },
            { hash: "P—", elig: null, ben: null, breakdown: null },
          ];
        }
        const tone = (v) => {
          const s = String(v || "").toLowerCase();
          if (s === "verified" || s === "ok" || s === "yes") return "verified";
          if (s === "pending" || s === "wait") return "pending";
          if (s === "failed" || s === "fail" || s === "no") return "failed";
          return "unknown";
        };
        const rows = patients
          .map((p) => {
            return `<div class="apex-matrix-row">
              <span class="apex-matrix-hash">${this.escape(p.hash || "P—")}</span>
              <i class="apex-matrix-dot apex-matrix-dot--${tone(p.elig)}" title="Elig"></i>
              <i class="apex-matrix-dot apex-matrix-dot--${tone(p.ben)}" title="Ben"></i>
              <i class="apex-matrix-dot apex-matrix-dot--${tone(p.breakdown)}" title="Breakdown"></i>
            </div>`;
          })
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty">${this.escape(
                  data.emptyMessage || "Verification tracking disabled"
                )}</div>`
              : ""
          }
          <div class="apex-matrix${empty ? " apex-matrix--empty" : ""}">
            <div class="apex-matrix-head"><span></span><span>Elig</span><span>Ben</span><span>Break</span></div>
            ${rows}
            <div class="apex-matrix-legend">●Verified ○Pending ◉Failed</div>
          </div>
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "utilization-board") {
        const data = this.spec.data && typeof this.spec.data === "object" ? this.spec.data : {};
        const ops = Array.isArray(data.operatories) ? data.operatories : [];
        const empty = this.spec.status === "empty" || !ops.length;
        // Coding consult: grid rows = operatories, columns = time slots
        const times = [];
        ops.forEach((op) => {
          (Array.isArray(op.slots) ? op.slots : []).forEach((slot) => {
            const t = String((slot && slot.time) || "").trim();
            if (t && !times.includes(t)) times.push(t);
          });
        });
        times.sort();
        const head =
          times.length > 0
            ? `<div class="apex-op-grid-head"><span class="apex-op-grid-corner">Op</span>${times
                .map((t) => `<span>${this.escape(t)}</span>`)
                .join("")}</div>`
            : "";
        const rows = ops
          .map((op) => {
            const slots = Array.isArray(op.slots) ? op.slots : [];
            const byTime = {};
            slots.forEach((slot) => {
              byTime[String(slot.time || "")] = slot;
            });
            const cells =
              times.length > 0
                ? times
                    .map((t) => {
                      const slot = byTime[t] || { status: "open" };
                      const st = String(slot.status || "open").toLowerCase();
                      const tone = st.includes("book")
                        ? "booked"
                        : st.includes("block")
                          ? "blocked"
                          : "open";
                      return `<span class="apex-op-slot apex-op-slot--${tone}" title="${this.escape(t)}">${this.escape(
                        tone === "booked" ? slot.patientHash || "•" : tone === "blocked" ? "×" : ""
                      )}</span>`;
                    })
                    .join("")
                : slots
                    .map((slot) => {
                      const st = String(slot.status || "open").toLowerCase();
                      const tone = st.includes("book")
                        ? "booked"
                        : st.includes("block")
                          ? "blocked"
                          : "open";
                      return `<span class="apex-op-slot apex-op-slot--${tone}">${this.escape(
                        tone === "booked" ? slot.patientHash || "•" : ""
                      )}</span>`;
                    })
                    .join("");
            return `<div class="apex-op-grid-row" style="--op-cols:${Math.max(times.length, slots.length, 1)}">
              <strong class="apex-op-grid-name">${this.escape(op.name || "Op—")}</strong>
              <div class="apex-op-grid-slots">${cells}</div>
            </div>`;
          })
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty">${this.escape(data.emptyMessage || "No schedule data")}</div>`
              : `<div class="apex-op-grid">${head}${rows}
                   <div class="apex-op-legend">amber=booked · cyan outline=open · gray=blocked</div>
                 </div>`
          }
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "schedule-list") {
        const data = this.spec.data && typeof this.spec.data === "object" ? this.spec.data : {};
        const days = Array.isArray(data.days) ? data.days : [];
        const empty = this.spec.status === "empty" || !days.some((d) => d && (d.count > 0 || (d.slots && d.slots.length)));
        const dayHtml = days
          .map((day) => {
            const slots = Array.isArray(day.slots) ? day.slots : [];
            const rows = slots.length
              ? slots
                  .map((s) => {
                    const hash = String((s && (s.patientHash || s.initials)) || "——");
                    const pid = String((s && s.patientId) || "");
                    return `<button type="button" class="apex-sched-slot" data-om-patient-id="${this.escape(
                      pid
                    )}" data-om-patient-hash="${this.escape(hash)}" title="Ask HAL about this patient">
                      <span class="apex-sched-hash">${this.escape(hash)}</span>
                      <span class="apex-sched-meta">${this.escape(String((s && s.time) || "—"))} · ${this.escape(
                      String((s && s.provider) || "—")
                    )} · ${this.escape(String((s && s.status) || ""))}</span>
                    </button>`;
                  })
                  .join("")
              : `<div class="apex-kpi-value is-empty">${this.escape(
                  day.emptyMessage || `No SoftDent appointments for ${day.date || "day"}.`
                )}</div>`;
            return `<div class="apex-sched-day">
              <div class="apex-sched-day-head"><strong>${this.escape(
                String(day.dayName || "")
              )}</strong> ${this.escape(String(day.date || ""))} · ${this.escape(
              String(day.count != null ? day.count : slots.length)
            )}</div>
              <div class="apex-sched-slots">${rows}</div>
            </div>`;
          })
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty">${this.escape(
                  data.emptyMessage || "No appointments found for Mon–Thu — verify SoftDent sync."
                )}</div>`
              : `<div class="apex-sched-list" data-schedule-list>
                   <div class="apex-sched-range">${this.escape(String(data.dateRange || ""))}</div>
                   ${dayHtml}
                 </div>`
          }
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "action-list" || this.type === "bar-list") {
        const data = this.spec.data && typeof this.spec.data === "object" ? this.spec.data : {};
        const items = Array.isArray(data.items)
          ? data.items
          : Array.isArray(data.rows)
            ? data.rows.map((r) => ({
                id: r.provider,
                payer: "",
                status: `${r.appointments != null ? r.appointments : 0} appts`,
                amount: null,
                serviceDate: "",
                label: r.provider,
              }))
            : [];
        const empty = this.spec.status === "empty" || !items.length;
        const list = items
          .map((it) => {
            const amt = it.amount != null && it.amount !== "" ? String(it.amount) : "";
            const labelText = it.label || it.id || "—";
            return `<li class="apex-action-li">
              <strong>${this.escape(String(labelText))}</strong>
              <span>${this.escape(String(it.payer || ""))}${it.status ? " · " + this.escape(String(it.status)) : ""}</span>
              <span>${this.escape(amt || (it.serviceDate ? String(it.serviceDate) : ""))}</span>
            </li>`;
          })
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty">${this.escape(
                  data.emptyMessage || this.spec.emptyMessage || "No items"
                )}</div>`
              : `<ul class="apex-action-list">${list}</ul>`
          }
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "patient-dossier-card") {
        const data = this.spec.data && typeof this.spec.data === "object" ? this.spec.data : {};
        const empty = this.spec.status === "empty" && !data.patientHash;
        const gap = data.schemaGap
          ? `<div class="apex-kpi-hint">${this.escape(String(data.schemaGap))}</div>`
          : "";
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          ${
            empty || (!data.patientHash && !data.initials)
              ? `<div class="apex-kpi-value is-empty">${this.escape(
                  data.emptyMessage || "Select a patient from Mon–Thu schedule."
                )}</div>`
              : `<div class="apex-dossier-card">
                   <div class="apex-dossier-hash">${this.escape(String(data.patientHash || "——"))} · ${this.escape(
                     String(data.initials || "P—")
                   )}</div>
                   <div>Carrier: ${this.escape(String(data.primaryCarrier || "unknown"))}</div>
                   <div>Open claims: ${this.escape(
                     data.openClaims != null ? String(data.openClaims) : "unknown"
                   )}</div>
                   <div>Last visit: ${this.escape(String(data.lastVisit || "unknown"))}</div>
                   <div>Balance: ${this.escape(String(data.accountBalance || "unavailable"))}</div>
                   <div>Notes: ${data.hasClinicalNotes ? "on file" : "none"}</div>
                 </div>`
          }
          ${gap}
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "radial-gauge") {
        const data = this.spec.data && typeof this.spec.data === "object" ? this.spec.data : {};
        const empty = this.spec.status === "empty" || data.due == null;
        const pct = data.pctScheduled != null && Number.isFinite(Number(data.pctScheduled))
          ? Math.max(0, Math.min(100, Number(data.pctScheduled)))
          : null;
        const target = 80;
        const r = 42;
        const c = 2 * Math.PI * r;
        const fill = pct == null ? 0 : (pct / 100) * c * 0.75;
        const track = c * 0.75;
        // Amber target marker at 80% along 270° arc (starts at 135°)
        const targetAngle = 135 + (target / 100) * 270;
        const rad = (targetAngle * Math.PI) / 180;
        const tx = 60 + r * Math.cos(rad);
        const ty = 58 + r * Math.sin(rad);
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty">${this.escape(
                  data.emptyMessage || "Recall tracking unavailable"
                )}</div>
                 <div class="apex-gauge apex-gauge--empty">
                   <svg viewBox="0 0 120 100" class="apex-gauge-svg" aria-hidden="true">
                     <circle class="apex-gauge-arc apex-gauge-arc--track" cx="60" cy="58" r="${r}"
                       stroke-dasharray="${track} ${c}" stroke-dashoffset="0" transform="rotate(135 60 58)" />
                     <text x="60" y="62" text-anchor="middle" class="apex-gauge-pct">—%</text>
                   </svg>
                 </div>`
              : `<div class="apex-gauge">
                   <svg viewBox="0 0 120 100" class="apex-gauge-svg" aria-hidden="true">
                     <circle class="apex-gauge-arc apex-gauge-arc--track" cx="60" cy="58" r="${r}"
                       stroke-dasharray="${track} ${c}" stroke-dashoffset="0" transform="rotate(135 60 58)" />
                     <circle class="apex-gauge-arc apex-gauge-arc--fill" cx="60" cy="58" r="${r}"
                       stroke-dasharray="${fill} ${c}" stroke-dashoffset="0" transform="rotate(135 60 58)" />
                     <circle class="apex-gauge-target" cx="${tx.toFixed(1)}" cy="${ty.toFixed(1)}" r="3.5" />
                     <text x="60" y="62" text-anchor="middle" class="apex-gauge-pct">${this.escape(
                       pct != null ? `${pct}%` : "—%"
                     )}</text>
                   </svg>
                   <div class="apex-gauge-meta">Due: ${this.escape(
                     data.due != null ? String(data.due) : "—"
                   )} · Target: 80% · Sch: ${this.escape(
                     data.scheduled != null ? String(data.scheduled) : "—"
                   )}${
                     data.contacted != null ? ` · Contacted: ${this.escape(String(data.contacted))}` : ""
                   }</div>
                 </div>`
          }
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "claim-shelf") {
        const tiles = Array.isArray(this.spec.tiles) ? this.spec.tiles : [];
        const empty = !tiles.length || this.spec.status === "empty";
        const bucket = String(this.spec.bucket || "30");
        const count = typeof this.spec.count === "number" ? this.spec.count : tiles.length;
        const tileHtml = tiles
          .map((t) => {
            const id = String((t && t.claimId) || "");
            const name = String((t && t.patientName) || "—");
            const date = String((t && t.date) || "—");
            const age = t && typeof t.ageDays === "number" ? `${t.ageDays}d` : "";
            return `<button type="button" class="apex-claims-tile apex-claims-tile--${this.escape(
              bucket
            )}" data-claim-id="${this.escape(id)}" data-claim-tile title="${this.escape(id)}">
              <label class="apex-claims-tile__check"><input type="checkbox" data-bulk-claim value="${this.escape(
                id
              )}" aria-label="Select ${this.escape(id)}" /></label>
              <span class="apex-claims-tile__id">${this.escape(id)}</span>
              <span class="apex-claims-tile__name">${this.escape(name)}</span>
              <span class="apex-claims-tile__date">${this.escape(date)}${age ? " · " + this.escape(age) : ""}</span>
            </button>`;
          })
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label} <em class="apex-claims-shelf__count">${this.escape(
              String(count)
            )}</em></span>
            <div class="apex-widget-actions">
              <button type="button" class="apex-btn apex-btn--small" data-action="bulk-appeal" title="Generate appeal packet for selected">Bulk appeal</button>
              ${printBtn}
            </div>
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty">${this.escape(
                  this.spec.emptyMessage || "No claims in this aging bucket"
                )}</div>`
              : `<div class="apex-claims-shelf" data-claims-shelf data-bucket="${this.escape(
                  bucket
                )}"><div class="apex-claims-shelf__track">${tileHtml}</div>
                <div class="apex-claims-shelf__meta">Viewing ${this.escape(String(tiles.length))} of ${this.escape(
                  String(count)
                )} · click tile for detail</div></div>`
          }
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "countdown") {
        const items = Array.isArray(this.spec.items) ? this.spec.items : [];
        const empty = !items.length;
        const days =
          typeof this.spec.daysRemaining === "number" ? `${this.spec.daysRemaining}d` : "—";
        const list = items
          .map(
            (it) =>
              `<div class="apex-countdown-item"><span>${this.escape(it.label || "Q")}</span><strong>${this.escape(
                formatMoney(it.amount) || "—"
              )}</strong></div>`
          )
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty">${this.escape(this.spec.emptyMessage || "No quarterly estimates")}</div>`
              : `<div class="apex-countdown-hero"><span class="apex-mini-label">Next due ${this.escape(
                  this.spec.nextDue || "—"
                )}</span><div class="apex-kpi-value">${this.escape(days)}</div>
                <div class="apex-kpi-delta">${this.escape(formatMoney(this.spec.nextAmount) || "amount —")}</div></div>
                <div class="apex-countdown-list">${list}</div>`
          }
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "heatmap") {
        const grid = Array.isArray(this.spec.grid) ? this.spec.grid : [];
        const empty = !grid.length;
        const cells = grid
          .map(
            (g) =>
              `<div class="apex-heat-cell risk-${this.escape(g.risk || "low")}" title="${this.escape(g.label)}">
                <span class="apex-heat-name">${this.escape(g.label)}</span>
                <span class="apex-heat-bal">${this.escape(formatMoney(g.balance) || "—")}</span>
                <span class="apex-heat-age">${this.escape(g.ageBucket || "")}</span>
              </div>`
          )
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty">${this.escape(this.spec.emptyMessage || "No A/R rows")}</div>`
              : `<div class="apex-heat-grid">${cells}</div>`
          }
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "calculator") {
        const samples = Array.isArray(this.spec.feeSamples) ? this.spec.feeSamples : [];
        const opts = samples
          .map((s) => `<option value="${Number(s.fee) || 0}">${this.escape(s.code)} — ${this.escape(formatMoney(s.fee) || "")}</option>`)
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          <div class="apex-calc" data-calc>
            <label class="apex-calc-field">Fee / UCR
              <select data-calc-fee>${opts || '<option value="0">Enter fee manually</option>'}</select>
            </label>
            <label class="apex-calc-field">Or custom fee
              <input type="number" min="0" step="0.01" data-calc-custom placeholder="0.00" />
            </label>
            <label class="apex-calc-field">Plan coverage %
              <input type="number" min="0" max="100" step="1" value="80" data-calc-cov />
            </label>
            <label class="apex-calc-field">Deductible remaining
              <input type="number" min="0" step="0.01" value="0" data-calc-ded />
            </label>
            <div class="apex-calc-result">
              <span class="apex-mini-label">Est. patient responsibility</span>
              <div class="apex-kpi-value" data-calc-out>—</div>
            </div>
          </div>
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      if (this.type === "categorize") {
        const rows = Array.isArray(this.spec.suggestions) ? this.spec.suggestions : [];
        const empty = !rows.length;
        const list = rows
          .map((r) => {
            const amt =
              r.amount !== null && r.amount !== undefined && Number.isFinite(Number(r.amount))
                ? formatMoney(r.amount)
                : "—";
            return `<div class="apex-cat-row">
              <div class="apex-cat-memo">${this.escape(r.memo || "")}</div>
              <div class="apex-cat-meta"><span>${this.escape(r.existing || "—")}</span>
              <span class="apex-cat-arrow">→</span>
              <strong>${this.escape(r.suggested || "Uncategorized")}</strong>
              <span class="apex-cat-amt">${this.escape(amt || "—")}</span></div>
            </div>`;
          })
          .join("");
        return `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty">${this.escape(this.spec.emptyMessage || "No expense memos")}</div>`
              : `<div class="apex-cat-list">${list}</div>`
          }
          <div class="apex-kpi-hint">${this.escape(this.spec.hint || "")}</div>
        `;
      }

      const unit = String(this.spec.unit || "money");
      const raw = this.spec.value;
      const hasValue = raw !== null && raw !== undefined && raw !== "" && Number.isFinite(Number(raw));
      const display = hasValue
        ? unit === "count"
          ? formatCount(raw)
          : unit === "percent"
            ? `${Number(raw).toFixed(1)}%`
            : formatMoney(raw)
        : this.spec.emptyMessage || "No data";
      const delta = this.spec.delta;
      let deltaHtml = "";
      if (typeof delta === "number" && Number.isFinite(delta)) {
        const down = delta < 0;
        deltaHtml = `<div class="apex-kpi-delta${down ? " is-down" : ""}" data-kpi-delta>${down ? "▼" : "▲"} ${Math.abs(delta * 100).toFixed(1)}%</div>`;
      } else if (this.spec.deltaLabel) {
        deltaHtml = `<div class="apex-kpi-delta" data-kpi-delta>${this.escape(this.spec.deltaLabel)}</div>`;
      }
      const spark = Array.isArray(this.spec.sparkline) ? this.spec.sparkline : [];
      const maxSpark = Math.max(...spark.map(Number).filter(Number.isFinite), 1);
      const sparkHtml = spark.length
        ? `<div class="apex-sparkline" data-sparkline>${spark
            .map((h) => {
              const n = Number(h);
              const pct = Number.isFinite(n) ? Math.max(8, Math.round((n / maxSpark) * 100)) : 8;
              return `<div class="apex-spark-bar" style="height:${pct}%"></div>`;
            })
            .join("")}</div>`
        : "";

      return `
        <header class="apex-widget-header">
          <span class="apex-widget-label">${label}</span>
          ${printBtn}
        </header>
        <div class="apex-kpi-value${hasValue ? "" : " is-empty"}" data-kpi-value${hasValue ? ` data-rollup="${Number(raw)}"` : ""}>${this.escape(display)}</div>
        ${deltaHtml}
        ${sparkHtml}
        <div class="apex-kpi-hint" data-kpi-hint>${this.escape(this.spec.hint || "")}</div>
      `;
    }

    escape(s) {
      return String(s == null ? "" : s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    mountChart() {
      const canvas = this.element && this.element.querySelector("canvas[data-chart]");
      if (!canvas || typeof window.ApexChartWidget !== "function") return;
      const chartType = this.spec.chartType || (this.type === "bar" ? "bar" : "line");
      let values = [];
      let labels = [];
      if (Array.isArray(this.spec.series) && this.spec.series.length) {
        values = this.spec.series.map((s) => Number(s.value) || 0);
        labels = this.spec.series.map((s) => String(s.label || ""));
      } else if (Array.isArray(this.spec.values)) {
        values = this.spec.values.map((v) => Number(v) || 0);
      }
      if (!values.length) return;
      // eslint-disable-next-line no-new
      new window.ApexChartWidget(canvas, { values, labels }, chartType);
    }

    /** In-place update without destroying the DOM node (no flash). */
    patch(spec) {
      if (!this.element || this.type === "hal-chat") return false;
      const prev = JSON.stringify(this.spec);
      this.spec = spec || {};
      this.type = String(this.spec.type || this.type || "kpi");
      const next = JSON.stringify(this.spec);
      if (prev === next) {
        this.element.classList.remove("is-updating");
        return true;
      }

      if (this.type === "chart" || this.type === "bar" || this.type === "line") {
        // Charts: rebuild host content only
        const label = this.escape(this.spec.label || this.id || "Widget");
        const printBtn = `<button type="button" class="apex-icon-btn" data-action="print" title="Print">${ICONS.print}</button>`;
        const empty = !(this.spec.series && this.spec.series.length) && !(this.spec.values && this.spec.values.length);
        this.element.innerHTML = `
          <header class="apex-widget-header">
            <span class="apex-widget-label">${label}</span>
            ${printBtn}
          </header>
          ${
            empty
              ? `<div class="apex-kpi-value is-empty" data-kpi-value>${this.escape(this.spec.emptyMessage || "No chart data")}</div>
                 <div class="apex-kpi-hint" data-kpi-hint>${this.escape(this.spec.hint || "")}</div>`
              : `<div class="apex-chart-host"><canvas data-chart></canvas></div>
                 <div class="apex-kpi-hint" data-kpi-hint>${this.escape(this.spec.hint || "")}</div>`
          }
        `;
        this.attachEvents();
        this.mountChart();
      } else {
        // KPI / status: patch text nodes
        const valueEl = this.element.querySelector("[data-kpi-value]");
        const hintEl = this.element.querySelector("[data-kpi-hint]");
        const deltaEl = this.element.querySelector("[data-kpi-delta]");
        const sparkEl = this.element.querySelector("[data-sparkline]");

        if (this.type === "status" || this.spec.status === "awaiting-migration") {
          if (valueEl) {
            valueEl.textContent = this.spec.message || "—";
            valueEl.classList.add("is-empty");
          }
          if (hintEl) hintEl.textContent = this.spec.hint || "";
        } else {
          const unit = String(this.spec.unit || "money");
          const raw = this.spec.value;
          const hasValue = raw !== null && raw !== undefined && raw !== "" && Number.isFinite(Number(raw));
          const display = hasValue
            ? unit === "count"
              ? formatCount(raw)
              : unit === "percent"
                ? `${Number(raw).toFixed(1)}%`
                : formatMoney(raw)
            : this.spec.emptyMessage || "No data";
          if (valueEl) {
            valueEl.textContent = display;
            valueEl.classList.toggle("is-empty", !hasValue);
          }
          if (hintEl) hintEl.textContent = this.spec.hint || "";
          if (typeof this.spec.delta === "number" && Number.isFinite(this.spec.delta)) {
            const down = this.spec.delta < 0;
            const text = `${down ? "▼" : "▲"} ${Math.abs(this.spec.delta * 100).toFixed(1)}%`;
            if (deltaEl) {
              deltaEl.textContent = text;
              deltaEl.classList.toggle("is-down", down);
            } else if (valueEl) {
              const d = document.createElement("div");
              d.className = `apex-kpi-delta${down ? " is-down" : ""}`;
              d.dataset.kpiDelta = "";
              d.textContent = text;
              valueEl.insertAdjacentElement("afterend", d);
            }
          } else if (this.spec.deltaLabel && deltaEl) {
            deltaEl.textContent = this.spec.deltaLabel;
          }
          if (sparkEl && Array.isArray(this.spec.sparkline)) {
            const spark = this.spec.sparkline;
            const maxSpark = Math.max(...spark.map(Number).filter(Number.isFinite), 1);
            sparkEl.innerHTML = spark
              .map((h) => {
                const n = Number(h);
                const pct = Number.isFinite(n) ? Math.max(8, Math.round((n / maxSpark) * 100)) : 8;
                return `<div class="apex-spark-bar" style="height:${pct}%"></div>`;
              })
              .join("");
          }
        }
      }

      this.element.classList.remove("is-updating");
      this.element.classList.add("is-patched");
      setTimeout(() => this.element && this.element.classList.remove("is-patched"), 500);
      return true;
    }

    maybeRollup() {
      const el = this.element && this.element.querySelector("[data-kpi-value][data-rollup]");
      if (!el || !window.ApexMotion || typeof window.ApexMotion.animateValue !== "function") return;
      const end = Number(el.getAttribute("data-rollup"));
      if (!Number.isFinite(end)) return;
      const unit = String(this.spec.unit || "money");
      const formatter = (n) => {
        if (unit === "count") return formatCount(Math.round(n)) || "0";
        if (unit === "percent") return `${Number(n).toFixed(1)}%`;
        return formatMoney(n) || "—";
      };
      window.ApexMotion.animateValue(el, 0, end, 700, formatter);
    }

    attachEvents() {
      const header = this.element.querySelector(".apex-widget-header");
      if (header && this.type !== "hal-chat" && !header.querySelector('[data-action="ask-hal"]')) {
        const ask = document.createElement("button");
        ask.type = "button";
        ask.className = "apex-icon-btn apex-ask-hal-btn";
        ask.dataset.action = "ask-hal";
        ask.title = "Ask HAL about this widget";
        ask.setAttribute("aria-label", "Ask HAL");
        ask.textContent = "◐";
        const actions = header.querySelector(".apex-widget-actions");
        if (actions) actions.insertBefore(ask, actions.firstChild);
        else header.appendChild(ask);
      }
      const btn = this.element.querySelector('[data-action="print"]');
      if (btn) {
        btn.addEventListener("click", () => printPage(this.id));
      }
      const askBtn = this.element.querySelector('[data-action="ask-hal"]');
      if (askBtn) {
        askBtn.addEventListener("click", () => askHalAboutWidget(this.spec));
      }
      const focusBtn = this.element.querySelector('[data-action="focus"]');
      if (focusBtn) {
        focusBtn.addEventListener("click", () => toggleFocus(this.element));
      }
      if (this.type === "waterfall") {
        this.element.querySelectorAll("[data-cite-key]").forEach((btn) => {
          btn.addEventListener("click", () => openCitationModal(btn.getAttribute("data-cite-key") || "", btn.textContent || ""));
        });
      }
      if (this.type === "scatter-plot") {
        const plot = this.element.querySelector("[data-scatter] .apex-scatter-plot");
        const svg = this.element.querySelector("[data-scatter-svg]");
        const crossV = this.element.querySelector("[data-scatter-cross-v]");
        const crossH = this.element.querySelector("[data-scatter-cross-h]");
        if (plot && svg && crossV && crossH) {
          const circles = Array.from(svg.querySelectorAll("circle.apex-scatter-point"));
          plot.addEventListener("mousemove", (ev) => {
            const rect = plot.getBoundingClientRect();
            let x = ((ev.clientX - rect.left) / rect.width) * 100;
            let y = ((ev.clientY - rect.top) / rect.height) * 100;
            // Consult: snap to nearest point
            if (circles.length) {
              let best = null;
              let bestD = Infinity;
              circles.forEach((c) => {
                const cx = Number(c.getAttribute("cx")) || 0;
                const cy = Number(c.getAttribute("cy")) || 0;
                const d = (cx - x) * (cx - x) + (cy - y) * (cy - y);
                if (d < bestD) {
                  bestD = d;
                  best = { cx, cy };
                }
              });
              if (best) {
                x = best.cx;
                y = best.cy;
              }
            }
            crossV.setAttribute("visibility", "visible");
            crossH.setAttribute("visibility", "visible");
            crossV.setAttribute("x1", String(x));
            crossV.setAttribute("x2", String(x));
            crossH.setAttribute("y1", String(y));
            crossH.setAttribute("y2", String(y));
          });
          plot.addEventListener("mouseleave", () => {
            crossV.setAttribute("visibility", "hidden");
            crossH.setAttribute("visibility", "hidden");
          });
        }
      }
      if (this.type === "status") {
        const refreshBtn = this.element.querySelector("[data-c0-refresh]");
        if (refreshBtn && refreshBtn.dataset.wired !== "1") {
          refreshBtn.dataset.wired = "1";
          refreshBtn.addEventListener("click", async () => {
            refreshBtn.disabled = true;
            refreshBtn.textContent = "Refreshing…";
            try {
              const res = await apexFetch(`${config.apiBase}/softdent/refresh-period`, {
                method: "POST",
                body: JSON.stringify({}),
              });
              const data = await res.json().catch(() => ({}));
              const meta = metaEl();
              if (meta) {
                meta.textContent = data.ok
                  ? `HAL · SoftDent period refresh OK — ${data.nextStep || "reloading"}`
                  : `HAL · Period refresh issue — ${data.error || data.nextStep || "see C0"}`;
                meta.classList.add("is-live");
              }
              await loadPage(currentPage, { silent: false });
            } catch (err) {
              window.alert(String((err && err.message) || err));
              refreshBtn.disabled = false;
              refreshBtn.textContent = "Refresh SoftDent period imports";
            }
          });
        }
      }
      if (this.type === "hal-chat") {
        wireHalChat(this.element);
      }
      if (this.type === "calculator") {
        wireCalculator(this.element);
      }
      if (this.type === "tax-library") {
        wireTaxLibrary(this.element);
      }
      if (this.type === "ebitda-scrubber") {
        wireEbitdaScrubber(this.element, this.spec);
      }
      if (this.type === "scenario-manager") {
        wireScenarioManager(this.element);
      }
      if (this.type === "filing-workflow") {
        wireFilingWorkflow(this.element);
      }
      if (this.type === "workpaper") {
        wireWorkpaper(this.element);
      }
      if (this.type === "scrubber") {
        this.element.querySelectorAll("[data-period]").forEach((chip) => {
          chip.addEventListener("click", () => {
            this.element.querySelectorAll(".apex-scrub-chip").forEach((c) => c.classList.remove("is-active"));
            chip.classList.add("is-active");
            const meta = metaEl();
            if (meta) {
              meta.textContent = `${meta.textContent.split(" · Period:")[0]} · Period: ${chip.dataset.period}`;
            }
          });
        });
      }
      if (
        this.type === "financial-command-strip" ||
        this.type === "revenue-composition" ||
        this.type === "dual-axis-trend"
      ) {
        this.element.querySelectorAll("[data-fin-cmd-action]").forEach((btn) => {
          if (btn.dataset.wired === "1") return;
          btn.dataset.wired = "1";
          btn.addEventListener("click", async () => {
            const act = btn.getAttribute("data-fin-cmd-action") || "refresh_softdent_period";
            btn.disabled = true;
            const prev = btn.textContent;
            btn.textContent = "Working…";
            try {
              if (act === "sync_imports") {
                await runHalBoardActions([{ type: "sync_imports", fullSync: true }, { type: "refresh_page" }]);
              } else if (act === "focus_ebitda") {
                const el = findWidgetEl("ebitda-station");
                if (el) {
                  el.scrollIntoView({ behavior: "smooth", block: "center" });
                  el.classList.add("apex-hal-highlight");
                  setTimeout(() => el.classList.remove("apex-hal-highlight"), 3500);
                }
              } else {
                await runHalBoardActions([
                  { type: "refresh_softdent_period" },
                  { type: "refresh_page" },
                ]);
              }
            } catch (err) {
              window.alert(String((err && err.message) || err));
            } finally {
              btn.disabled = false;
              btn.textContent = prev;
            }
          });
        });
      }
      if (this.type === "scenario-manager") {
        wireScenarioManager(this.element);
      }
      if (this.type === "filing-workflow") {
        wireFilingWorkflow(this.element);
      }
      if (this.type === "workpaper") {
        wireWorkpaper(this.element);
      }
      if (this.type === "workpaper-scrubber") {
        wireWorkpaperScrubber(this.element);
      }
      if (this.type === "claim-detail-card") {
        wireClaimDetailCard(this.element, this.spec);
      }
      if (this.type === "collection-task-list") {
        wireCollectionTaskList(this.element, this.spec);
      }
      if (this.type === "huddle-mosaic") {
        wireHuddleMosaic(this.element, this.spec);
      }
      if (this.type === "batch-selector") {
        wireBatchSelector(this.element);
      }
      if (this.type === "attachment-dropzone") {
        wireAttachmentDropzone(this.element);
      }
      if (this.type === "payer-reference-card") {
        wirePayerReferenceCard(this.element);
      }
      if (this.type === "era-matching-table") {
        wireEraMatchingTable(this.element);
      }
      if (this.type === "tax-calendar") {
        wireTaxCalendar(this.element);
      }
      if (this.type === "task-board") {
        wireTaskBoard(this.element);
      }
      if (this.type === "claim-shelf") {
        wireClaimShelf(this.element, this.spec);
      }
      if (this.type === "schedule-list") {
        wireOmScheduleList(this.element);
      }
      if (this.type === "claims-kanban" || this.type === "claims-workbench") {
        wireClaimsKanban(this.element, this.spec);
      }
      if (this.type === "claims-aging-exposure") {
        wireClaimsAgingExposure(this.element);
      }
      if (this.type === "claims-critical-actions") {
        wireClaimsCriticalActions(this.element);
      }
      if (this.type === "claim-attachments") {
        wireClaimAttachments(this.element);
      }
      if (this.type === "status" || this.spec.rememberForm) {
        wireHalSaidRemember(this.element);
      }
      if (this.type === "ai-insight") {
        wireAiInsight(this.element);
      }
    }
  }

  function askHalAboutWidget(spec) {
    const s = spec || {};
    const data = s.data && typeof s.data === "object" ? s.data : {};
    const widgetId = String(s.id || s.widgetId || "");
    const status = String(s.status || (data && data.emptyMessage && !data.bars && !data.points ? "empty" : "ok"));
    const context = {
      widgetId,
      page: currentPage,
      status: status || "ok",
    };

    // Consult §4 — widget-specific HAL context (PHI-safe)
    if (widgetId === "denial-pareto" || s.type === "pareto-chart") {
      const codes = Array.isArray(s.denialCodes)
        ? s.denialCodes
        : Array.isArray(data.bars)
          ? data.bars.map((b) => b && b.code).filter(Boolean)
          : [];
      if (codes.length) context.denialCodes = codes.slice(0, 12);
    }
    if (
      widgetId === "unapplied-credit-float" ||
      widgetId === "verification-matrix" ||
      widgetId === "operatory-util-board" ||
      s.type === "credit-float" ||
      s.type === "status-matrix" ||
      s.type === "utilization-board"
    ) {
      const hashes = [];
      if (Array.isArray(data.credits)) {
        data.credits.forEach((c) => {
          if (c && c.patientHash) hashes.push(String(c.patientHash));
        });
      }
      if (Array.isArray(data.patients)) {
        data.patients.forEach((p) => {
          if (p && p.hash) hashes.push(String(p.hash));
        });
      }
      if (Array.isArray(data.operatories)) {
        data.operatories.forEach((op) => {
          (Array.isArray(op.slots) ? op.slots : []).forEach((slot) => {
            if (slot && slot.patientHash) hashes.push(String(slot.patientHash));
          });
        });
      }
      if (hashes.length) context.patientHash = hashes.slice(0, 12);
    }

    const parts = [
      `Widget context (do not invent dollars beyond these figures):`,
      `page=${currentPage}`,
      `id=${widgetId}`,
      `widgetId=${widgetId}`,
      `label=${s.label || s.title || ""}`,
      `type=${s.type || ""}`,
      `context=${JSON.stringify(context)}`,
    ];
    if (s.value !== null && s.value !== undefined && s.value !== "") {
      parts.push(`value=${s.value}${s.unit ? " " + s.unit : ""}`);
    }
    if (s.status === "empty" || s.status === "awaiting-migration") {
      parts.push(`dataStatus=EMPTY`);
      parts.push(`emptyMessage=${s.emptyMessage || data.emptyMessage || "No data"}`);
      parts.push(`Ask: which widgets are empty? · how do I get SoftDent/QuickBooks exports? · Sync imports`);
    } else {
      parts.push(`dataStatus=SHOWING`);
    }
    if (context.denialCodes) {
      parts.push(`denialCodes=${context.denialCodes.join(",")}`);
    }
    if (context.patientHash) {
      parts.push(`patientHash=${context.patientHash.join(",")}`);
    }
    if (s.type === "claim-shelf") {
      parts.push(`bucket=${s.bucket || ""}`);
      parts.push(`tileCount=${Array.isArray(s.tiles) ? s.tiles.length : 0}`);
      if (!Array.isArray(s.tiles) || !s.tiles.length) {
        parts.push(`This aging shelf is empty — need SoftDent claims with Age/Days or ServiceDate, then Sync.`);
      } else {
        parts.push(`Ask: focus this aging shelf, sync imports, or find a claim by ID.`);
      }
    }
    if (s.hint) parts.push(`hint=${s.hint}`);
    if (s.message) parts.push(`message=${s.message}`);
    if (Array.isArray(s.bars) && s.bars.length) {
      parts.push(
        "bars=" +
          s.bars
            .slice(0, 8)
            .map((b) => `${b.label}:${b.value}`)
            .join("; ")
      );
    }
    if (Array.isArray(s.slices) && s.slices.length) {
      parts.push(
        "slices=" +
          s.slices
            .slice(0, 8)
            .map((b) => `${b.label}:${b.value}`)
            .join("; ")
      );
    }
    if (Array.isArray(s.steps) && s.steps.length) {
      parts.push(
        "steps=" +
          s.steps
            .slice(0, 10)
            .map((b) => `${b.label}:${b.value}`)
            .join("; ")
      );
    }
    if (Array.isArray(s.segments) && s.segments.length) {
      parts.push(
        "segments=" +
          s.segments
            .slice(0, 8)
            .map((b) => `${b.label}:${b.value}`)
            .join("; ")
      );
    }
    parts.push("Explain what this means for the practice and what to prioritize next.");

    // Consult §4 — deterministic focus/highlight via board-actions before chat
    const query = `Explain this widget`;
    apexFetch(`${config.apiBase}/hal/board-actions`, {
      method: "POST",
      body: JSON.stringify({ query, page: currentPage, context }),
    })
      .then((res) => res.json().catch(() => ({})))
      .then((board) => {
        if (board && Array.isArray(board.actions) && board.actions.length) {
          return runHalBoardActions(board.actions);
        }
        // Fallback: focus locally if board did not handle
        return runHalBoardActions([
          { type: "focus_widget", widgetId },
          { type: "highlight_widget", widgetId, ms: 4000 },
        ]);
      })
      .catch(() => {})
      .finally(() => {
        askHalFromBridge(parts.join(" | "));
      });
  }

  function wireTaxLibrary(root) {
    const form = root.querySelector("[data-tax-upload]");
    if (!form || form.dataset.wired === "1") return;
    form.dataset.wired = "1";
    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const fd = new FormData(form);
      try {
        const res = await apexFetch("/api/apex/tax-returns/upload", { method: "POST", body: fd });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || data.ok === false) {
          window.alert(data.error || `Upload failed (HTTP ${res.status})`);
          return;
        }
        await loadPage("documents", { silent: false });
      } catch (err) {
        window.alert(String((err && err.message) || err));
      }
    });
  }

  const EBITDA_SCENARIO_KEY = "nr2:apex:ebitda-scenarios";

  function loadEbitdaScenarios() {
    try {
      const raw = localStorage.getItem(EBITDA_SCENARIO_KEY);
      const parsed = raw ? JSON.parse(raw) : {};
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch (_err) {
      return {};
    }
  }

  function saveEbitdaScenarios(map) {
    try {
      localStorage.setItem(EBITDA_SCENARIO_KEY, JSON.stringify(map || {}));
    } catch (_err) {
      /* ignore quota */
    }
  }

  function collectScrubberInputs(box) {
    const inputs = {};
    if (!box) return inputs;
    box.querySelectorAll("[data-scrub-key]").forEach((input) => {
      inputs[input.getAttribute("data-scrub-key")] = Number(input.value) || 0;
    });
    return inputs;
  }

  function applyScrubberInputs(box, inputs) {
    if (!box || !inputs) return;
    Object.keys(inputs).forEach((k) => {
      const input = box.querySelector(`[data-scrub-key="${k}"]`);
      if (input && !input.disabled) input.value = String(inputs[k]);
    });
    box.dispatchEvent(new CustomEvent("apex-scrub-recalc"));
  }

  async function persistScenarioToApi(name, inputs, bookNet, planEbitda) {
    const res = await apexFetch(`${config.apiBase}/scenarios/save`, {
      method: "POST",
      body: JSON.stringify({
        name,
        inputs,
        bookNetIncome: Number.isFinite(bookNet) ? bookNet : null,
        planningEbitda: Number.isFinite(planEbitda) ? planEbitda : null,
      }),
    });
    return res.json().catch(() => ({}));
  }

  function wireEbitdaScrubber(root, spec) {
    const box = root.querySelector("[data-ebitda-scrub]");
    if (!box || box.dataset.wired === "1") return;
    box.dataset.wired = "1";
    const locked = box.getAttribute("data-locked") === "1";
    const bookNet = Number(box.getAttribute("data-book-net"));
    const defaults = {};
    const scrub = (spec && spec.scrubber) || {};
    Object.keys(scrub).forEach((k) => {
      defaults[k] = scrub[k] && scrub[k].default != null ? Number(scrub[k].default) : 0;
    });

    const recalc = () => {
      const dep = Number((box.querySelector('[data-scrub-key="depreciation"]') || {}).value) || 0;
      const interest = Number((box.querySelector('[data-scrub-key="interest"]') || {}).value) || 0;
      const oneTime = Number((box.querySelector('[data-scrub-key="oneTime"]') || {}).value) || 0;
      const salaryEl = box.querySelector('[data-scrub-key="officerSalary"]');
      const salary = salaryEl ? Number(salaryEl.value) || 0 : 0;
      box.querySelectorAll("[data-scrub-out]").forEach((out) => {
        const key = out.getAttribute("data-scrub-out");
        const input = box.querySelector(`[data-scrub-key="${key}"]`);
        if (!input) return;
        const n = Number(input.value);
        out.textContent = formatMoney(n) || String(n);
      });
      const plan = (Number.isFinite(bookNet) ? bookNet : 0) + dep + interest + oneTime;
      const bookE = Number(box.getAttribute("data-book-ebitda"));
      const planOut = box.querySelector("[data-plan-out]");
      const deltaOut = box.querySelector("[data-delta-out]");
      if (planOut) planOut.textContent = formatMoney(plan) || "—";
      if (deltaOut && Number.isFinite(bookE)) {
        const d = plan - bookE;
        deltaOut.textContent = `Δ vs book ${d >= 0 ? "+" : ""}${formatMoney(d) || d}`;
        deltaOut.classList.toggle("is-down", d < 0);
      }
      box.dataset.planEbitda = String(plan);
      void salary; // scenario note only — salary does not invent into Book KPIs
    };

    box.addEventListener("apex-scrub-recalc", recalc);
    box.querySelectorAll("input[type=range]").forEach((el) => {
      el.addEventListener("input", recalc);
    });

    const resetBtn = box.querySelector("[data-scrub-reset]");
    if (resetBtn) {
      resetBtn.addEventListener("click", () => {
        if (locked) return;
        Object.keys(defaults).forEach((k) => {
          const input = box.querySelector(`[data-scrub-key="${k}"]`);
          if (input) input.value = String(defaults[k]);
        });
        recalc();
      });
    }

    const loadSel = box.querySelector("[data-scrub-load]");
    const refreshLoad = async () => {
      if (!loadSel) return;
      const local = loadEbitdaScenarios();
      let apiRows = [];
      try {
        const res = await apexFetch(`${config.apiBase}/scenarios`);
        const data = await res.json().catch(() => ({}));
        apiRows = Array.isArray(data.scenarios) ? data.scenarios : [];
      } catch (_err) {
        apiRows = [];
      }
      const cur = loadSel.value;
      loadSel.innerHTML = '<option value="">Load scenario…</option>';
      apiRows.forEach((row) => {
        const opt = document.createElement("option");
        opt.value = `api:${row.id}`;
        opt.textContent = `${row.name || row.id} (store)`;
        opt.dataset.inputs = JSON.stringify(row.inputs || {});
        loadSel.appendChild(opt);
      });
      Object.keys(local)
        .sort()
        .forEach((name) => {
          const opt = document.createElement("option");
          opt.value = `local:${name}`;
          opt.textContent = `${name} (browser)`;
          opt.dataset.inputs = JSON.stringify((local[name] && local[name].inputs) || {});
          loadSel.appendChild(opt);
        });
      if (cur) loadSel.value = cur;
    };
    refreshLoad();

    const saveBtn = box.querySelector("[data-scrub-save]");
    if (saveBtn) {
      saveBtn.addEventListener("click", async () => {
        if (locked) return;
        const nameEl = box.querySelector("[data-scrub-name]");
        const name = String((nameEl && nameEl.value) || "").trim() || `Scenario ${new Date().toISOString().slice(0, 16)}`;
        const inputs = collectScrubberInputs(box);
        const plan = Number(box.dataset.planEbitda);
        const map = loadEbitdaScenarios();
        map[name] = { savedAt: new Date().toISOString(), inputs, bookNetIncome: bookNet };
        saveEbitdaScenarios(map);
        try {
          await persistScenarioToApi(name, inputs, bookNet, plan);
        } catch (_err) {
          /* local still saved */
        }
        await refreshLoad();
        if (nameEl) nameEl.value = name;
        const meta = metaEl();
        if (meta) {
          meta.textContent = `HAL · Saved EBITDA scenario "${name}" (NR2 store — not QB)`;
          meta.classList.add("is-live");
        }
      });
    }
    if (loadSel) {
      loadSel.addEventListener("change", () => {
        const opt = loadSel.selectedOptions[0];
        if (!opt || !opt.dataset.inputs) return;
        try {
          applyScrubberInputs(box, JSON.parse(opt.dataset.inputs));
        } catch (_err) {
          /* ignore */
        }
        recalc();
      });
    }
    // Expose for HAL set_inputs / save_scenario
    box._apexApplyInputs = (inputs) => {
      applyScrubberInputs(box, inputs);
      recalc();
    };
    box._apexSaveNamed = async (name) => {
      if (locked) return { ok: false, error: "filing locked" };
      const inputs = collectScrubberInputs(box);
      const plan = Number(box.dataset.planEbitda);
      const map = loadEbitdaScenarios();
      map[name] = { savedAt: new Date().toISOString(), inputs, bookNetIncome: bookNet };
      saveEbitdaScenarios(map);
      return persistScenarioToApi(name, inputs, bookNet, plan);
    };
    recalc();
  }

  function wireScenarioManager(root) {
    const box = root.querySelector("[data-scenario-manager]");
    if (!box || box.dataset.wired === "1") return;
    box.dataset.wired = "1";
    box.addEventListener("click", async (ev) => {
      const row = ev.target.closest("[data-scenario-id]");
      const id = row && row.getAttribute("data-scenario-id");
      if (ev.target.matches("[data-scenario-del]") && id) {
        if (!window.confirm("Delete this scenario?")) return;
        await apexFetch(`${config.apiBase}/scenarios/delete`, {
          method: "POST",
          body: JSON.stringify({ id }),
        });
        await loadPage(currentPage, { silent: false });
        return;
      }
      if (ev.target.matches("[data-scenario-load]") && id) {
        const scrub = document.querySelector("[data-ebitda-scrub]");
        if (!scrub || !scrub._apexApplyInputs) return;
        try {
          const res = await apexFetch(`${config.apiBase}/scenarios`);
          const data = await res.json().catch(() => ({}));
          const hit = (data.scenarios || []).find((s) => s.id === id);
          if (hit) scrub._apexApplyInputs(hit.inputs || {});
        } catch (_err) {
          /* ignore */
        }
        return;
      }
      if (ev.target.matches("[data-scenario-compare]")) {
        const ids = Array.from(box.querySelectorAll("[data-compare-id]:checked"))
          .map((el) => el.value)
          .slice(0, 3);
        const diffEl = box.querySelector("[data-scenario-diff]");
        if (!ids.length || !diffEl) return;
        try {
          const res = await apexFetch(`${config.apiBase}/scenarios/compare`, {
            method: "POST",
            body: JSON.stringify({ ids }),
          });
          const data = await res.json().catch(() => ({}));
          const lines = (data.diffs || []).map(
            (d) => `${d.key}: ${JSON.stringify(d.values)} spread=${d.spread}${d.flag ? " ⚠" : ""}`
          );
          diffEl.hidden = false;
          diffEl.textContent = lines.join("\n") || "No diffs";
        } catch (err) {
          if (diffEl) {
            diffEl.hidden = false;
            diffEl.textContent = String((err && err.message) || err);
          }
        }
      }
    });
  }

  function wireFilingWorkflow(root) {
    const box = root.querySelector("[data-filing-workflow]");
    if (!box || box.dataset.wired === "1") return;
    box.dataset.wired = "1";
    let selected = box.getAttribute("data-current") || "DRAFT";
    box.querySelectorAll("[data-filing-state]").forEach((btn) => {
      btn.addEventListener("click", () => {
        selected = btn.getAttribute("data-filing-state") || selected;
        box.querySelectorAll("[data-filing-state]").forEach((b) => b.classList.toggle("is-active", b === btn));
      });
    });
    const upload = box.querySelector("[data-filing-upload]");
    if (upload) {
      upload.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        const fd = new FormData(upload);
        try {
          const res = await apexFetch("/api/apex/tax-returns/upload", { method: "POST", body: fd });
          const data = await res.json().catch(() => ({}));
          if (!res.ok || data.ok === false) {
            window.alert(data.error || `Upload failed (HTTP ${res.status})`);
            return;
          }
          const path = data.relPath || data.path || "";
          const sel = box.querySelector("[data-filing-path]");
          if (sel && path) {
            const opt = document.createElement("option");
            opt.value = path;
            opt.textContent = path;
            opt.selected = true;
            sel.appendChild(opt);
            sel.value = path;
          }
          selected = "FILED";
          box.querySelectorAll("[data-filing-state]").forEach((b) =>
            b.classList.toggle("is-active", b.getAttribute("data-filing-state") === "FILED")
          );
        } catch (err) {
          window.alert(String((err && err.message) || err));
        }
      });
    }
    const applyBtn = box.querySelector("[data-filing-apply]");
    if (applyBtn) {
      applyBtn.addEventListener("click", async () => {
        const note = (box.querySelector("[data-filing-note]") || {}).value || "";
        const pathEl = box.querySelector("[data-filing-path]");
        const path = pathEl ? pathEl.value || "" : "";
        if (selected === "FILED" && !path) {
          window.alert("FILED requires a tax return PDF from the library (select or upload).");
          return;
        }
        const res = await apexFetch(`${config.apiBase}/filing/set`, {
          method: "POST",
          body: JSON.stringify({ state: selected, note, filedRelPath: path }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || data.ok === false) {
          window.alert(data.error || `Filing update failed (HTTP ${res.status})`);
          return;
        }
        await loadPage(currentPage, { silent: false });
      });
    }
  }

  async function openCitationModal(citeKey, citationLabel) {
    let modal = document.getElementById("apex-cite-modal");
    if (!modal) {
      modal = document.createElement("div");
      modal.id = "apex-cite-modal";
      modal.className = "apex-cite-modal";
      modal.innerHTML = `<div class="apex-cite-modal__panel" role="dialog" aria-modal="true">
        <header><strong data-cite-title>Citation</strong><button type="button" data-cite-close>Close</button></header>
        <div class="apex-cite-modal__body" data-cite-body>Loading…</div>
      </div>`;
      document.body.appendChild(modal);
      modal.addEventListener("click", (ev) => {
        if (ev.target === modal || ev.target.matches("[data-cite-close]")) modal.classList.remove("is-open");
      });
    }
    const title = modal.querySelector("[data-cite-title]");
    const body = modal.querySelector("[data-cite-body]");
    if (title) title.textContent = citationLabel || citeKey || "Citation";
    if (body) body.textContent = "Loading…";
    modal.classList.add("is-open");
    try {
      const res = await apexFetch(`${config.apiBase}/citations/qb?key=${encodeURIComponent(citeKey || "")}`);
      const data = await res.json().catch(() => ({}));
      if (!body) return;
      if (data.empty || !(data.rows || []).length) {
        body.innerHTML = `<p class="apex-kpi-hint">${escapeHtml(data.emptyReason || "No QB rows for this citation.")}</p>
          <p class="apex-kpi-hint">Source: ${escapeHtml(data.source || "—")}</p>`;
        return;
      }
      const rows = (data.rows || [])
        .map(
          (r) =>
            `<tr><td>${escapeHtml(r.label || "")}</td><td>${escapeHtml(formatMoney(r.amount) || "—")}</td><td>${escapeHtml(
              r.scope || ""
            )}</td><td>${escapeHtml(r.memo || "")}</td></tr>`
        )
        .join("");
      body.innerHTML = `<p class="apex-kpi-hint">${escapeHtml(data.source || "")}${
        data.total != null ? " · total " + escapeHtml(formatMoney(data.total) || "") : ""
      }</p>
        <table class="apex-cite-table"><thead><tr><th>Label</th><th>Amount</th><th>Scope</th><th>Memo</th></tr></thead>
        <tbody>${rows}</tbody></table>`;
    } catch (err) {
      if (body) body.textContent = String((err && err.message) || err);
    }
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function wireWorkpaper(root) {
    const box = root.querySelector("[data-workpaper]");
    if (!box || box.dataset.wired === "1") return;
    box.dataset.wired = "1";
    const btn = box.querySelector("[data-workpaper-export]");
    if (!btn) return;
    btn.addEventListener("click", async () => {
      try {
        const res = await apexFetch(`${config.apiBase}/workpapers/generate`, {
          method: "POST",
          body: JSON.stringify({}),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || data.ok === false) {
          window.alert(data.error || `Workpaper failed (HTTP ${res.status})`);
          return;
        }
        const url = data.download_url || data.url;
        if (url) window.open(url, "_blank", "noopener");
      } catch (err) {
        window.alert(String((err && err.message) || err));
      }
    });
  }

  function loadCpaFlags() {
    try {
      const raw = sessionStorage.getItem(CPA_FLAG_KEY);
      const parsed = raw ? JSON.parse(raw) : {};
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch (_err) {
      return {};
    }
  }

  function saveCpaFlags(flags) {
    try {
      sessionStorage.setItem(CPA_FLAG_KEY, JSON.stringify(flags || {}));
    } catch (_err) {
      /* ignore */
    }
  }

  function wireWorkpaperScrubber(root) {
    const box = root.querySelector("[data-workpaper-scrubber]");
    if (!box || box.dataset.wired === "1") return;
    box.dataset.wired = "1";
    const flags = loadCpaFlags();
    box.querySelectorAll("[data-cpa-flag]").forEach((input) => {
      const id = String(input.value || "");
      input.checked = !!flags[id];
      input.addEventListener("change", () => {
        const next = loadCpaFlags();
        if (input.checked) next[id] = true;
        else delete next[id];
        saveCpaFlags(next);
      });
    });
  }

  function wireClaimDetailCard(root, spec) {
    if (!root || root.dataset.wiredDetail === "1") return;
    root.dataset.wiredDetail = "1";
    const back = root.querySelector("[data-back-claims]");
    if (back) {
      back.addEventListener("click", () => loadPage("claims"));
    }
    const draft = root.querySelector("[data-draft-narrative-sub]");
    if (draft) {
      draft.addEventListener("click", () => {
        const claim = (spec && spec.claim) || {};
        const cid = String((claim && claim.claimId) || (spec && spec.claimId) || "");
        try {
          sessionStorage.setItem(
            "nr2-apex-narrative-seed",
            JSON.stringify({
              claimId: cid,
              patientName: "",
              payer: (claim && claim.payer) || "",
              date: (claim && claim.date) || "",
            })
          );
          sessionStorage.setItem("nr2-apex-focused-claim", cid);
        } catch (_err) {
          /* ignore */
        }
        loadPage("narratives");
      });
    }
  }

  function wireCollectionTaskList(root, _spec) {
    if (!root || root.dataset.wiredCol === "1") return;
    root.dataset.wiredCol = "1";
    const form = root.querySelector("[data-col-form]");
    if (form) {
      form.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        const fd = new FormData(form);
        const body = {
          claimId: String(fd.get("claimId") || "").trim(),
          patientInitials: String(fd.get("patientInitials") || "").trim(),
          status: String(fd.get("status") || "open"),
          followUp: String(fd.get("followUp") || "").trim(),
          note: String(fd.get("note") || "").trim(),
        };
        try {
          const res = await apexFetch(`${config.apiBase}/local/collection-notes`, {
            method: "POST",
            body: JSON.stringify(body),
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok || data.ok === false) {
            window.alert(data.error || `Save failed (HTTP ${res.status})`);
            return;
          }
          await loadPage("ar/collections");
        } catch (err) {
          window.alert(String((err && err.message) || err));
        }
      });
    }
    root.querySelectorAll("[data-col-seed-claim]").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (!form) return;
        const claimInput = form.querySelector('[name="claimId"]');
        const initInput = form.querySelector('[name="patientInitials"]');
        if (claimInput) claimInput.value = btn.getAttribute("data-col-seed-claim") || "";
        if (initInput) initInput.value = btn.getAttribute("data-col-initials") || "";
        claimInput && claimInput.focus();
      });
    });
  }

  function wireHuddleMosaic(root, spec) {
    if (!root || root.dataset.wiredHuddle === "1") return;
    root.dataset.wiredHuddle = "1";
    const saveBtn = root.querySelector("[data-huddle-save]");
    if (saveBtn) {
      saveBtn.addEventListener("click", async () => {
        const priorities = Array.isArray(spec && spec.priorities) ? spec.priorities : [];
        try {
          const res = await apexFetch(`${config.apiBase}/local/huddle`, {
            method: "POST",
            body: JSON.stringify({ priorities }),
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok || data.ok === false) {
            window.alert(data.error || `Huddle save failed (HTTP ${res.status})`);
            return;
          }
          await loadPage("office-manager/huddle");
        } catch (err) {
          window.alert(String((err && err.message) || err));
        }
      });
    }
    const taskForm = root.querySelector("[data-huddle-task-form]");
    if (taskForm) {
      taskForm.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        const fd = new FormData(taskForm);
        const body = {
          title: String(fd.get("title") || "").trim(),
          assignee: String(fd.get("assignee") || "").trim(),
          dueDate: String(fd.get("dueDate") || "").trim(),
        };
        try {
          const res = await apexFetch(`${config.apiBase}/local/tasks`, {
            method: "POST",
            body: JSON.stringify(body),
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok || data.ok === false) {
            window.alert(data.error || `Task save failed (HTTP ${res.status})`);
            return;
          }
          await loadPage("office-manager/huddle");
        } catch (err) {
          window.alert(String((err && err.message) || err));
        }
      });
    }
  }

  function wireBatchSelector(root) {
    if (!root || root.dataset.wiredBatch === "1") return;
    root.dataset.wiredBatch = "1";
    const seedBtn = root.querySelector("[data-batch-seed]");
    if (!seedBtn) return;
    seedBtn.addEventListener("click", async () => {
      const ids = Array.from(root.querySelectorAll("[data-batch-claim]:checked")).map((el) => el.value);
      if (!ids.length) {
        window.alert("Select at least one claim.");
        return;
      }
      try {
        const res = await apexFetch(`${config.apiBase}/narratives/batch-seed`, {
          method: "POST",
          body: JSON.stringify({ claimIds: ids }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || data.ok === false) {
          window.alert(data.error || `Batch seed failed (HTTP ${res.status})`);
          return;
        }
        try {
          sessionStorage.setItem("nr2-apex-narrative-seed", JSON.stringify(data.seed || { claimIds: ids }));
        } catch (_err) {
          /* ignore */
        }
        loadPage("narratives");
      } catch (err) {
        window.alert(String((err && err.message) || err));
      }
    });
  }

  function wireAttachmentDropzone(root) {
    if (!root || root.dataset.wiredDrop === "1") return;
    root.dataset.wiredDrop = "1";
    const form = root.querySelector("[data-claim-att-upload]");
    if (!form) return;
    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const fd = new FormData(form);
      const cid = String(fd.get("claimId") || "").trim();
      try {
        const res = await apexFetch(`${config.apiBase}/claims/attachments`, { method: "POST", body: fd });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || data.ok === false) {
          window.alert(data.error || "Upload failed");
          return;
        }
        const hash =
          currentPage === "claims" && currentSub === "attachments"
            ? cid
              ? `claims/attachments?id=${encodeURIComponent(cid)}`
              : "claims/attachments"
            : cid
              ? `documents/claim-docs?id=${encodeURIComponent(cid)}`
              : "documents/claim-docs";
        await loadPage(hash);
      } catch (err) {
        window.alert(String((err && err.message) || err));
      }
    });
  }

  function wirePayerReferenceCard(root) {
    if (!root || root.dataset.wiredPayer === "1") return;
    root.dataset.wiredPayer = "1";
    const form = root.querySelector("[data-payer-form]");
    if (!form) return;
    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const fd = new FormData(form);
      const body = {
        payerName: String(fd.get("payerName") || "").trim(),
        appealDeadlineDays: String(fd.get("appealDeadlineDays") || "").trim(),
        contact: String(fd.get("contact") || "").trim(),
        guidelines: String(fd.get("guidelines") || "").trim(),
      };
      try {
        const res = await apexFetch(`${config.apiBase}/local/payers`, {
          method: "POST",
          body: JSON.stringify(body),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || data.ok === false) {
          window.alert(data.error || `Save failed (HTTP ${res.status})`);
          return;
        }
        await loadPage("library/payers");
      } catch (err) {
        window.alert(String((err && err.message) || err));
      }
    });
  }

  function wireEraMatchingTable(root) {
    if (!root || root.dataset.wiredEra === "1") return;
    root.dataset.wiredEra = "1";
    const era = root.querySelector("[data-era-upload]");
    if (!era) return;
    era.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const fd = new FormData(era);
      try {
        const res = await apexFetch(`${config.apiBase}/claims/era-ingest`, { method: "POST", body: fd });
        const data = await res.json().catch(() => ({}));
        window.alert(
          data.ok
            ? `ERA ingested: ${data.matchedCount || 0} matched of ${data.segmentCount || 0} segments`
            : data.error || "ERA ingest failed"
        );
        if (data.ok) await loadPage("claims/era");
      } catch (err) {
        window.alert(String((err && err.message) || err));
      }
    });
  }

  function wireTaxCalendar(root) {
    if (!root || root.dataset.wiredTaxCal === "1") return;
    root.dataset.wiredTaxCal = "1";
    root.querySelectorAll("[data-tax-log]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const quarter = btn.getAttribute("data-tax-log") || "";
        try {
          const res = await apexFetch(`${config.apiBase}/local/tax-payments`, {
            method: "POST",
            body: JSON.stringify({ quarter }),
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok || data.ok === false) {
            window.alert(data.error || "Log failed");
            return;
          }
          await loadPage("taxes/calendar");
        } catch (err) {
          window.alert(String((err && err.message) || err));
        }
      });
    });
  }

  function wireTaskBoard(root) {
    if (!root || root.dataset.wiredTasks === "1") return;
    root.dataset.wiredTasks = "1";
    const form = root.querySelector("[data-task-form]");
    if (form) {
      form.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        const fd = new FormData(form);
        try {
          const res = await apexFetch(`${config.apiBase}/local/tasks`, {
            method: "POST",
            body: JSON.stringify({
              title: String(fd.get("title") || "").trim(),
              assignee: String(fd.get("assignee") || "").trim(),
              dueDate: String(fd.get("dueDate") || "").trim(),
            }),
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok || data.ok === false) {
            window.alert(data.error || "Task save failed");
            return;
          }
          await loadPage("office-manager/tasks");
        } catch (err) {
          window.alert(String((err && err.message) || err));
        }
      });
    }
    root.querySelectorAll("[data-task-toggle]").forEach((cb) => {
      cb.addEventListener("change", async () => {
        const id = cb.getAttribute("data-task-toggle");
        try {
          await apexFetch(`${config.apiBase}/local/tasks`, {
            method: "POST",
            body: JSON.stringify({ id: Number(id), done: cb.checked }),
          });
          await loadPage("office-manager/tasks", { silent: true });
        } catch (_err) {
          /* ignore */
        }
      });
    });
  }

  function closeClaimDrawer() {
    const drawer = document.getElementById("apex-claim-drawer");
    if (drawer) drawer.remove();
    document.body.classList.remove("apex-claim-drawer-open");
  }

  async function openClaimDrawer(claimId) {
    const id = String(claimId || "").trim();
    if (!id) return;
    closeClaimDrawer();
    const drawer = document.createElement("aside");
    drawer.id = "apex-claim-drawer";
    drawer.className = "apex-claim-drawer";
    drawer.setAttribute("role", "dialog");
    drawer.setAttribute("aria-label", "Claim detail");
    drawer.innerHTML = `<header class="apex-claim-drawer__head">
      <h2>Claim ${escapeHtml(id)}</h2>
      <button type="button" class="apex-icon-btn" data-close-drawer aria-label="Close">×</button>
    </header>
    <div class="apex-claim-drawer__body">Loading import-backed claim…</div>
    <footer class="apex-claim-drawer__foot">
      <button type="button" class="apex-btn apex-btn--primary" data-draft-narrative disabled>Draft Narrative</button>
    </footer>`;
    document.body.appendChild(drawer);
    document.body.classList.add("apex-claim-drawer-open");
    drawer.querySelector("[data-close-drawer]")?.addEventListener("click", closeClaimDrawer);
    const esc = (ev) => {
      if (ev.key === "Escape") {
        closeClaimDrawer();
        document.removeEventListener("keydown", esc);
      }
    };
    document.addEventListener("keydown", esc);
    try {
      const res = await apexFetch(`${config.apiBase}/claims/${encodeURIComponent(id)}`);
      const data = await res.json().catch(() => ({}));
      const body = drawer.querySelector(".apex-claim-drawer__body");
      const draftBtn = drawer.querySelector("[data-draft-narrative]");
      if (!res.ok || data.ok === false) {
        if (body) body.textContent = data.error || "Claim not found in SoftDent import.";
        return;
      }
      const procs = Array.isArray(data.procedures) ? data.procedures.join(", ") : "—";
      const billed =
        data.billedAmount != null && Number.isFinite(Number(data.billedAmount))
          ? formatMoney(data.billedAmount)
          : "— (not on import)";
      if (body) {
        body.innerHTML = `<dl class="apex-claim-dl">
          <div><dt>Claim ID</dt><dd>${escapeHtml(data.claimId || id)}</dd></div>
          <div><dt>Patient</dt><dd>${escapeHtml(data.patientName || "—")}</dd></div>
          <div><dt>Date of service</dt><dd>${escapeHtml(data.date || "—")}</dd></div>
          <div><dt>Age (days)</dt><dd>${escapeHtml(data.ageDays != null ? String(data.ageDays) : "—")}</dd></div>
          <div><dt>Payer</dt><dd>${escapeHtml(data.payer || "—")}</dd></div>
          <div><dt>Status</dt><dd>${escapeHtml(data.status || "—")}</dd></div>
          <div><dt>Procedures</dt><dd>${escapeHtml(procs)}</dd></div>
          <div><dt>Billed</dt><dd>${escapeHtml(billed)}</dd></div>
        </dl>
        <p class="apex-kpi-hint">Source: SoftDent import · never invented.</p>`;
      }
      if (draftBtn) {
        draftBtn.disabled = false;
        draftBtn.addEventListener("click", () => {
          try {
            sessionStorage.setItem(
              "nr2-apex-narrative-seed",
              JSON.stringify({
                claimId: data.claimId || id,
                patientName: data.patientName || "",
                payer: data.payer || "",
                date: data.date || "",
              })
            );
          } catch (_err) {
            /* ignore */
          }
          closeClaimDrawer();
          loadPage("narratives");
        });
      }
    } catch (err) {
      const body = drawer.querySelector(".apex-claim-drawer__body");
      if (body) body.textContent = String((err && err.message) || err);
    }
  }

  function wireClaimShelf(root, spec) {
    if (!root || root.dataset.claimShelfWired === "1") return;
    root.dataset.claimShelfWired = "1";
    root.querySelectorAll("[data-claim-tile]").forEach((tile) => {
      tile.addEventListener("click", (ev) => {
        if (ev.target && (ev.target.closest("label") || ev.target.matches("input"))) return;
        const cid = tile.getAttribute("data-claim-id");
        openClaimDrawer(cid);
      });
    });
    root.querySelectorAll("[data-bulk-claim]").forEach((cb) => {
      cb.addEventListener("click", (ev) => ev.stopPropagation());
    });
    const bulk = root.querySelector('[data-action="bulk-appeal"]');
    if (bulk) {
      bulk.addEventListener("click", () => {
        const ids = Array.from(root.querySelectorAll("[data-bulk-claim]:checked")).map((el) => el.value);
        if (!ids.length) {
          window.alert("Select one or more claim tiles first.");
          return;
        }
        try {
          sessionStorage.setItem(
            "nr2-apex-narrative-seed",
            JSON.stringify({ claimIds: ids, bulkAppeal: true, bucket: (spec && spec.bucket) || "" })
          );
        } catch (_err) {
          /* ignore */
        }
        loadPage("narratives");
      });
    }
  }

  function wireOmScheduleList(root) {
    if (!root || root.dataset.omSchedWired === "1") return;
    root.dataset.omSchedWired = "1";
    root.querySelectorAll("[data-om-patient-id], [data-om-patient-hash]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const pid = btn.getAttribute("data-om-patient-id") || "";
        const hash = btn.getAttribute("data-om-patient-hash") || "";
        const key = pid || hash;
        if (!key) return;
        if (typeof HalAgent !== "undefined" && typeof HalAgent.setOMPatientContext === "function") {
          HalAgent.setOMPatientContext(key);
        } else if (typeof window !== "undefined") {
          window.NR2_OM_PATIENT_CONTEXT = key;
        }
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (bridge && typeof bridge.auditHalPatientContext === "function") {
          bridge.auditHalPatientContext({
            patientHash: hash || String(key).slice(0, 4),
            action: "set_context",
            timestamp: new Date().toISOString(),
          });
        }
        // Soft visual selection
        root.querySelectorAll(".apex-sched-slot.is-selected").forEach((el) => el.classList.remove("is-selected"));
        btn.classList.add("is-selected");
        try {
          window.dispatchEvent(
            new CustomEvent("nr2-om-patient-context", { detail: { patientId: key, patientHash: hash } })
          );
        } catch (_e) {
          /* ignore */
        }
      });
    });
  }

  function findWidgetEl(widgetId) {
    const id = String(widgetId || "").replace(/\\/g, "").replace(/"/g, "");
    if (!id) return null;
    const direct = document.querySelector(`[data-widget-id="${id}"]`);
    if (direct) return direct;
    return (
      Array.from(document.querySelectorAll("[data-alias-ids]")).find((el) => {
        const aliases = String(el.getAttribute("data-alias-ids") || "").split(/\s+/);
        return aliases.includes(id);
      }) || null
    );
  }

  function applyKanbanFilter(root, filter) {
    const f = String(filter || "all");
    root.querySelectorAll("[data-kanban-filter]").forEach((btn) => {
      btn.classList.toggle("is-active", btn.getAttribute("data-kanban-filter") === f);
    });
    const matchItem = (el) => {
      let show = true;
      if (f === "high-risk") show = el.getAttribute("data-risk") === "high";
      else if (f === "unmatched") {
        const col = el.getAttribute("data-column") || "";
        show = col !== "eraMatched" && col !== "paid" && el.getAttribute("data-has-era") !== "1";
      } else if (f === "missing-attachments") {
        show =
          el.getAttribute("data-has-att") === "1" &&
          (!!el.querySelector(".apex-claim-card__att.is-missing") ||
            !!el.querySelector(".apex-wb-att--missing") ||
            (() => {
              const attCell = el.querySelector("td:nth-child(8)");
              if (!attCell) return false;
              const t = String(attCell.textContent || "");
              const m = t.match(/^(\d+)\/(\d+)$/);
              return m ? Number(m[1]) < Number(m[2]) : false;
            })());
      } else if (f === "bucket-30" || f === "bucket-60" || f === "bucket-90") {
        const want = f.replace("bucket-", "");
        show = el.getAttribute("data-bucket") === want;
      }
      return show;
    };
    root.querySelectorAll("[data-claim-card]").forEach((card) => {
      card.hidden = !matchItem(card);
    });
    root.querySelectorAll("[data-claim-row]").forEach((row) => {
      row.hidden = !matchItem(row);
    });
  }

  function setClaimsWorkbenchView(root, view) {
    const v = view === "kanban" ? "kanban" : "table";
    const wb = root.querySelector("[data-claims-workbench]") || root;
    wb.setAttribute("data-view", v);
    root.querySelectorAll("[data-wb-view]").forEach((btn) => {
      btn.classList.toggle("is-active", btn.getAttribute("data-wb-view") === v);
    });
    persistWorkbenchView(v);
  }

  function wireClaimsAgingExposure(root) {
    if (!root || root.dataset.agingWired === "1") return;
    root.dataset.agingWired = "1";
    root.querySelectorAll("[data-age-bucket]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const bucket = btn.getAttribute("data-age-bucket") || "";
        const board = findWidgetEl("claims-kanban-board");
        if (!board) return;
        board.scrollIntoView({ behavior: "smooth", block: "center" });
        applyKanbanFilter(board, bucket ? `bucket-${bucket}` : "all");
        board.classList.add("apex-hal-highlight");
        setTimeout(() => board.classList.remove("apex-hal-highlight"), 2500);
      });
    });
  }

  function wireClaimsCriticalActions(root) {
    if (!root || root.dataset.critWired === "1") return;
    root.dataset.critWired = "1";
    root.querySelectorAll("[data-crit-filter]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const filter = btn.getAttribute("data-crit-filter") || "all";
        if (filter === "__sync__") {
          try {
            const res = await apexFetch(`${config.apiBase}/sync/trigger`, {
              method: "POST",
              body: JSON.stringify({}),
            });
            const data = await res.json().catch(() => ({}));
            window.alert(data.message || data.error || (data.ok ? "Sync triggered" : "Sync failed"));
            if (data.ok) await loadPage("claims", { silent: false });
          } catch (err) {
            window.alert(String((err && err.message) || err));
          }
          return;
        }
        const board = findWidgetEl("claims-kanban-board");
        if (!board) return;
        board.scrollIntoView({ behavior: "smooth", block: "center" });
        applyKanbanFilter(board, filter);
        board.classList.add("apex-hal-highlight");
        setTimeout(() => board.classList.remove("apex-hal-highlight"), 2500);
      });
    });
  }

  function wireClaimsKanban(root, _spec) {
    if (!root || root.dataset.claimsKanbanWired === "1") return;
    root.dataset.claimsKanbanWired = "1";
    root.querySelectorAll("[data-wb-view]").forEach((btn) => {
      btn.addEventListener("click", () => {
        setClaimsWorkbenchView(root, btn.getAttribute("data-wb-view"));
      });
    });
    root.querySelectorAll("[data-claim-card], [data-claim-row]").forEach((card) => {
      card.addEventListener("click", (ev) => {
        if (ev.target && (ev.target.closest("[data-claim-actions]") || ev.target.closest(".apex-wb-acts"))) return;
        if (ev.target && (ev.target.closest("label") || ev.target.matches("input"))) return;
        openClaimDrawer(card.getAttribute("data-claim-id"));
      });
    });
    root.querySelectorAll("[data-claim-act]").forEach((btn) => {
      btn.addEventListener("click", async (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        const card = btn.closest("[data-claim-card], [data-claim-row]");
        const claimId = card && card.getAttribute("data-claim-id");
        const action = btn.getAttribute("data-claim-act");
        if (!claimId || !action) return;
        const patientName = (card && card.getAttribute("data-patient")) || "";
        if (action === "open") {
          openClaimDrawer(claimId);
          return;
        }
        if (action === "generate-narrative") {
          try {
            await apexFetch(`${config.apiBase}/claims/actions`, {
              method: "POST",
              body: JSON.stringify({ claimId, action, patientName }),
            });
          } catch (_err) {
            /* continue to narratives */
          }
          try {
            sessionStorage.setItem(
              "nr2-apex-narrative-seed",
              JSON.stringify({ claimId, patientName, voiceCarry: true })
            );
            sessionStorage.setItem("nr2-apex-focused-claim", claimId);
          } catch (_err) {
            /* ignore */
          }
          loadPage("narratives");
          return;
        }
        let note = "";
        if (action === "follow-up-note") {
          note = window.prompt("Follow-up note (stored in NR2 only — not SoftDent):", "") || "";
          if (!note.trim()) return;
        } else if (action === "schedule-callback") {
          note = window.prompt("Callback note / when (NR2 only):", "Callback requested") || "";
        }
        try {
          const res = await apexFetch(`${config.apiBase}/claims/actions`, {
            method: "POST",
            body: JSON.stringify({ claimId, action, note, patientName }),
          });
          const data = await res.json().catch(() => ({}));
          window.alert(data.message || data.error || (data.ok ? "Action recorded" : "Failed"));
        } catch (err) {
          window.alert(String((err && err.message) || err));
        }
      });
    });
    root.querySelectorAll("[data-batch-claim]").forEach((cb) => {
      cb.addEventListener("click", (ev) => ev.stopPropagation());
    });
    root.querySelectorAll("[data-kanban-filter]").forEach((btn) => {
      btn.addEventListener("click", () => {
        applyKanbanFilter(root, btn.getAttribute("data-kanban-filter"));
      });
    });
    const batch = root.querySelector('[data-action="batch-narratives"]');
    if (batch) {
      batch.addEventListener("click", () => {
        const ids = Array.from(root.querySelectorAll("[data-batch-claim]:checked")).map((el) => el.value);
        if (ids.length) {
          try {
            sessionStorage.setItem(
              "nr2-apex-narrative-seed",
              JSON.stringify({ claimIds: ids, claimId: ids[0], bulkAppeal: true, batchNarrative: true })
            );
          } catch (_err) {
            /* ignore */
          }
        }
        loadPage("claims/batch");
      });
    }
  }

  function wireClaimAttachments(root) {
    if (!root || root.dataset.attWired === "1") return;
    root.dataset.attWired = "1";
    const form = root.querySelector("[data-claim-att-upload]");
    if (form) {
      form.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        const fd = new FormData(form);
        try {
          const res = await apexFetch(`${config.apiBase}/claims/attachments`, { method: "POST", body: fd });
          const data = await res.json().catch(() => ({}));
          if (!res.ok || data.ok === false) {
            window.alert(data.error || "Upload failed");
            return;
          }
          await loadPage(
            currentSub === "claim-docs"
              ? formatApexHash("documents", "claim-docs", currentQuery)
              : "documents"
          );
        } catch (err) {
          window.alert(String((err && err.message) || err));
        }
      });
    }
    const era = root.querySelector("[data-era-upload]");
    if (era) {
      era.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        const fd = new FormData(era);
        try {
          const res = await apexFetch(`${config.apiBase}/claims/era-ingest`, { method: "POST", body: fd });
          const data = await res.json().catch(() => ({}));
          window.alert(
            data.ok
              ? `ERA ingested: ${data.matchedCount || 0} matched of ${data.segmentCount || 0} segments`
              : data.error || "ERA ingest failed"
          );
          if (data.ok) await loadPage("claims", { silent: false });
        } catch (err) {
          window.alert(String((err && err.message) || err));
        }
      });
    }
    const signoffForm = root.querySelector("[data-clinical-signoff-form]");
    if (signoffForm) {
      signoffForm.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        const fd = new FormData(signoffForm);
        try {
          const res = await apexFetch(`${config.apiBase}/hal/clinical-signoff`, {
            method: "POST",
            body: JSON.stringify({
              claimId: String(fd.get("claimId") || "").trim(),
              narrativeId: String(fd.get("narrativeId") || "").trim(),
            }),
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok || data.ok === false) {
            window.alert(data.error || "Sign-off request failed");
            return;
          }
          await loadPage("narratives");
        } catch (err) {
          window.alert(String((err && err.message) || err));
        }
      });
    }
    root.querySelectorAll("[data-signoff-approve], [data-signoff-reject]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-signoff-approve") || btn.getAttribute("data-signoff-reject");
        const status = btn.hasAttribute("data-signoff-approve") ? "approved" : "rejected";
        try {
          const res = await apexFetch(`${config.apiBase}/hal/clinical-signoff`, {
            method: "POST",
            body: JSON.stringify({ id, status }),
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok || data.ok === false) {
            window.alert(data.error || "Update failed");
            return;
          }
          await loadPage(currentPage || "narratives");
        } catch (err) {
          window.alert(String((err && err.message) || err));
        }
      });
    });
    root.querySelectorAll("[data-eob-posted]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const claimId = btn.getAttribute("data-eob-posted") || "";
        try {
          const res = await apexFetch(`${config.apiBase}/hal/eob-posted`, {
            method: "POST",
            body: JSON.stringify({ claimId }),
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok || data.ok === false) {
            window.alert(data.error || "Mark posted failed");
            return;
          }
          await loadPage(currentPage || "office-manager");
        } catch (err) {
          window.alert(String((err && err.message) || err));
        }
      });
    });
  }

  function wireAiInsight(root) {
    if (!root || root.dataset.wiredInsight === "1") return;
    root.dataset.wiredInsight = "1";
    root.querySelectorAll("[data-insight-route]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const page = btn.getAttribute("data-insight-route") || "hal";
        loadPage(page);
      });
    });
  }

  function wireHalSaidRemember(root) {
    if (!root || root.dataset.wiredRemember === "1") return;
    const form = root.querySelector("[data-hal-remember-form]");
    if (!form) return;
    root.dataset.wiredRemember = "1";
    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const fd = new FormData(form);
      try {
        const res = await apexFetch(`${config.apiBase}/hal/remember-structured`, {
          method: "POST",
          body: JSON.stringify({
            category: String(fd.get("category") || "").trim(),
            payerId: String(fd.get("payerId") || "").trim(),
            fact: String(fd.get("fact") || "").trim(),
          }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || data.ok === false) {
          window.alert(data.error || "Remember failed");
          return;
        }
        window.alert("Saved to learned memories (no PHI).");
        form.reset();
      } catch (err) {
        window.alert(String((err && err.message) || err));
      }
    });
  }

  function focusClaimTile(claimId) {
    const id = String(claimId || "").trim();
    if (!id) return;
    const tile = document.querySelector(`[data-claim-id="${CSS.escape ? CSS.escape(id) : id.replace(/"/g, "")}"]`);
    if (tile) {
      tile.scrollIntoView({ behavior: "smooth", block: "center", inline: "center" });
      tile.classList.add("apex-hal-highlight");
      setTimeout(() => tile.classList.remove("apex-hal-highlight"), 4000);
      const shelf = tile.closest(".apex-inst, .apex-widget");
      if (shelf) {
        shelf.scrollIntoView({ behavior: "smooth", block: "center" });
        shelf.classList.add("apex-hal-highlight");
        setTimeout(() => shelf.classList.remove("apex-hal-highlight"), 4000);
      }
    }
  }

  function toggleFocus(el) {
    if (!el) return;
    const open = document.querySelector(".apex-widget.is-focused");
    if (open && open !== el) open.classList.remove("is-focused");
    const on = el.classList.toggle("is-focused");
    document.body.classList.toggle("apex-focus-open", on);
    if (on) {
      const esc = (ev) => {
        if (ev.key === "Escape") {
          el.classList.remove("is-focused");
          document.body.classList.remove("apex-focus-open");
          document.removeEventListener("keydown", esc);
        }
      };
      document.addEventListener("keydown", esc);
    }
  }

  function wireCalculator(root) {
    const box = root.querySelector("[data-calc]");
    if (!box || box.dataset.wired === "1") return;
    box.dataset.wired = "1";
    const feeSel = box.querySelector("[data-calc-fee]");
    const custom = box.querySelector("[data-calc-custom]");
    const cov = box.querySelector("[data-calc-cov]");
    const ded = box.querySelector("[data-calc-ded]");
    const out = box.querySelector("[data-calc-out]");
    const recalc = () => {
      const feeCustom = custom && custom.value !== "" ? Number(custom.value) : NaN;
      const fee = Number.isFinite(feeCustom) ? feeCustom : Number((feeSel && feeSel.value) || 0);
      const coverage = Math.min(100, Math.max(0, Number((cov && cov.value) || 0))) / 100;
      const deductible = Math.max(0, Number((ded && ded.value) || 0));
      if (!Number.isFinite(fee) || fee <= 0) {
        if (out) out.textContent = "—";
        return;
      }
      const afterDed = Math.max(0, fee - deductible);
      const planPays = afterDed * coverage;
      const patient = fee - planPays;
      if (out) out.textContent = formatMoney(patient) || "—";
    };
    [feeSel, custom, cov, ded].forEach((el) => el && el.addEventListener("input", recalc));
    recalc();
  }

  function appendHalMessage(logEl, role, text, opts) {
    if (!logEl) return;
    const persist = !(opts && opts.skipPersist);
    const row = document.createElement("div");
    row.className = `apex-hal-chat__msg apex-hal-chat__msg--${role}`;

    const content = document.createElement("div");
    content.className = "apex-hal-chat__msg-text";
    content.textContent = text == null ? "" : String(text);
    row.appendChild(content);

    if (role === "hal" || role === "system") {
      const meta = document.createElement("div");
      meta.className = "apex-hal-chat__meta-row";
      const time = document.createElement("time");
      time.dateTime = new Date().toISOString();
      time.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      meta.appendChild(time);
      if (role === "hal") {
        const copyBtn = document.createElement("button");
        copyBtn.type = "button";
        copyBtn.className = "apex-hal-chat__copy";
        copyBtn.textContent = "Copy";
        copyBtn.addEventListener("click", async () => {
          try {
            await navigator.clipboard.writeText(String(text == null ? "" : text));
            copyBtn.textContent = "Copied";
            setTimeout(() => {
              copyBtn.textContent = "Copy";
            }, 2000);
          } catch (_err) {
            /* ignore */
          }
        });
        meta.appendChild(copyBtn);
        if (opts && (opts.spokenExcerpt || opts.readSummary)) {
          const report = {
            summary: String(text == null ? "" : text),
            spokenExcerpt: String(opts.spokenExcerpt || text || ""),
            tool: opts.tool || "hal",
          };
          if (typeof HalReports !== "undefined" && HalReports.attachReadButton) {
            HalReports.remember(report);
            HalReports.attachReadButton(meta, report);
          }
        }
      }
      row.appendChild(meta);
    }

    logEl.appendChild(row);
    logEl.scrollTop = logEl.scrollHeight;
    if (persist) {
      halTranscript.push({ role: String(role || "hal"), text: String(text == null ? "" : text) });
      if (halTranscript.length > HAL_TRANSCRIPT_MAX) {
        halTranscript.splice(0, halTranscript.length - HAL_TRANSCRIPT_MAX);
      }
    }
  }

  function restoreHalTranscript(logEl) {
    if (!logEl || !halTranscript.length) return;
    if (logEl.childElementCount) return;
    halTranscript.forEach((entry) => {
      appendHalMessage(logEl, entry.role, entry.text, { skipPersist: true });
    });
  }

  function finalizeHalPending(pending, reply) {
    const text = String(reply == null ? "" : reply);
    if (pending) pending.textContent = text;
    // Replace the trailing "Thinking…" transcript entry with the real reply.
    for (let i = halTranscript.length - 1; i >= 0; i -= 1) {
      if (halTranscript[i].role === "hal" && halTranscript[i].text === "Thinking…") {
        halTranscript[i] = { role: "hal", text };
        return;
      }
    }
    halTranscript.push({ role: "hal", text });
    if (halTranscript.length > HAL_TRANSCRIPT_MAX) {
      halTranscript.splice(0,halTranscript.length - HAL_TRANSCRIPT_MAX);
    }
  }

  async function runHalBoardActions(actions) {
    const list = Array.isArray(actions) ? actions : [];
    const results = [];
    for (const action of list) {
      if (!action || !action.type) continue;
      const type = String(action.type);
      try {
        if (type === "sync_imports") {
          await triggerSync();
          results.push("synced");
        } else if (type === "refresh_softdent_period") {
          try {
            const res = await apexFetch(`${config.apiBase}/softdent/refresh-period`, {
              method: "POST",
              body: JSON.stringify({}),
            });
            const data = await res.json().catch(() => ({}));
            results.push(data.ok ? "period_ok" : "period_fail");
            const meta = metaEl();
            if (meta && data.nextStep) {
              meta.textContent = `HAL · ${data.nextStep}`;
              meta.classList.add("is-live");
            }
          } catch (_err) {
            results.push("period_fail");
          }
        } else if (type === "navigate") {
          const page = String(action.page || "").trim();
          if (page && page !== currentPage) {
            await loadPage(page);
            results.push(`nav:${page}`);
          }
        } else if (type === "refresh_page") {
          await loadPage(currentPage, { silent: true });
          results.push("refreshed");
        } else if (type === "refresh_widget") {
          // Phase 3: targeted refresh — silent page reload then re-focus widget
          const id = String(action.widgetId || "").trim();
          await loadPage(currentPage, { silent: true });
          if (id) {
            await new Promise((r) => setTimeout(r, 80));
            const el = findWidgetEl(id);
            if (el) {
              el.scrollIntoView({ behavior: "smooth", block: "center" });
              el.classList.add("apex-hal-highlight");
              setTimeout(() => el.classList.remove("apex-hal-highlight"), Number(action.ms) || 2500);
            }
          }
          results.push(id ? `refresh_widget:${id}` : "refresh_widget");
        } else if (type === "focus_widget" || type === "highlight_widget") {
          const id = String(action.widgetId || "").trim();
          if (!id) continue;
          // Allow navigate to settle
          await new Promise((r) => setTimeout(r, 80));
          const el = document.querySelector(`[data-widget-id="${id.replace(/\\/g, "").replace(/"/g, "")}"]`);
          if (el) {
            el.scrollIntoView({ behavior: "smooth", block: "center" });
            if (type === "focus_widget") toggleFocus(el);
            el.classList.add("apex-hal-highlight");
            const ms = Number(action.ms) || 3500;
            setTimeout(() => el.classList.remove("apex-hal-highlight"), ms);
            results.push(`${type}:${id}`);
          }
        } else if (type === "set_status_banner") {
          const meta = metaEl();
          if (meta) {
            const msg = String(action.message || "");
            const hint = String(action.hint || "");
            meta.textContent = `HAL · ${msg}${hint ? " — " + hint : ""}`;
            meta.classList.add("is-live");
            meta.classList.toggle("is-warn", action.tone === "warn");
          }
          results.push("banner");
        } else if (type === "set_inputs") {
          await new Promise((r) => setTimeout(r, 120));
          const scrub = document.querySelector("[data-ebitda-scrub]");
          if (scrub && typeof scrub._apexApplyInputs === "function" && action.inputs) {
            scrub._apexApplyInputs(action.inputs);
            results.push("set_inputs");
          }
        } else if (type === "save_scenario") {
          await new Promise((r) => setTimeout(r, 120));
          const scrub = document.querySelector("[data-ebitda-scrub]");
          const name = String(action.name || "HAL scenario").trim();
          if (scrub && typeof scrub._apexSaveNamed === "function") {
            await scrub._apexSaveNamed(name);
            results.push(`save:${name}`);
          }
        } else if (type === "focus_claim_tile") {
          await new Promise((r) => setTimeout(r, 100));
          focusClaimTile(action.claimId);
          results.push(`focus_claim:${action.claimId || ""}`);
        } else if (type === "open_claim_detail") {
          await new Promise((r) => setTimeout(r, 120));
          await openClaimDrawer(action.claimId);
          results.push(`open_claim:${action.claimId || ""}`);
        } else if (type === "narrative_append") {
          if (currentPage !== "narratives") {
            await loadPage("narratives");
            await new Promise((r) => setTimeout(r, 200));
          }
          const section = String(action.section || "notes");
          const text = String(action.text || "");
          const mode = String(action.mode || "append");
          if (window.ApexNarratives && typeof window.ApexNarratives.applyVoiceText === "function") {
            window.ApexNarratives.applyVoiceText(section, text, mode);
            results.push(`narrative:${mode}:${section}`);
          }
        } else if (type === "run_tool") {
          const cfg = window.NR2_CONFIG || {};
          if (cfg.voiceReportsEnabled === false) {
            results.push("run_tool:disabled");
            continue;
          }
          const toolId = String(action.tool || "").trim();
          const def = window.HalAgent && HalAgent.TOOL_DEFS && HalAgent.TOOL_DEFS[toolId];
          if (!def || typeof def.run !== "function") {
            results.push(`run_tool:missing:${toolId}`);
            continue;
          }
          const toolRes = await def.run({}, { query: "" }, { speak: action.speak !== false });
          if (toolRes && toolRes.summary) {
            const logEl = document.querySelector("[data-hal-messages]");
            if (logEl && typeof appendHalMessage === "function") {
              appendHalMessage(logEl, "hal", String(toolRes.summary).slice(0, 4000), {
                skipPersist: true,
                spokenExcerpt: toolRes.spokenExcerpt || "",
                tool: toolId,
                readSummary: true,
              });
            }
            if (typeof HalReports !== "undefined" && HalReports.remember) {
              HalReports.remember({
                tool: toolId,
                summary: toolRes.summary,
                spokenExcerpt: toolRes.spokenExcerpt || toolRes.summary,
              });
            }
          }
          results.push(toolRes && toolRes.ok !== false ? `run_tool:${toolId}` : `run_tool_fail:${toolId}`);
        } else if (type === "focus_claims_bucket") {
          const bucket = String(action.bucket || "30");
          const wid = `claims-aging-${bucket}`;
          await new Promise((r) => setTimeout(r, 80));
          const el = document.querySelector(`[data-widget-id="${wid}"]`);
          if (el) {
            el.scrollIntoView({ behavior: "smooth", block: "center" });
            toggleFocus(el);
            el.classList.add("apex-hal-highlight");
            setTimeout(() => el.classList.remove("apex-hal-highlight"), 4000);
            results.push(`focus_bucket:${bucket}`);
          }
        }
      } catch (_err) {
        results.push(`fail:${type}`);
      }
    }
    return results;
  }

  let orchestratorEnabledCache = null;
  let orchestratorEnabledAt = 0;

  async function refreshOrchestratorEnabled() {
    const now = Date.now();
    if (orchestratorEnabledCache !== null && now - orchestratorEnabledAt < 30000) {
      return orchestratorEnabledCache;
    }
    try {
      const res = await apexFetch(`${config.apiBase}/hal/orchestrator`);
      const data = await res.json().catch(() => ({}));
      orchestratorEnabledCache = !!(data && data.enabled);
      orchestratorEnabledAt = now;
      return orchestratorEnabledCache;
    } catch (_err) {
      orchestratorEnabledCache = false;
      orchestratorEnabledAt = now;
      return false;
    }
  }

  async function askHal(query, logEl) {
    const q = String(query || "").trim();
    if (!q) return;
    if (!logEl) {
      await loadPage("hal");
      const chat = document.querySelector("[data-hal-messages]");
      if (chat) askHal(q, chat);
      return;
    }
    appendHalMessage(logEl, "user", q);
    appendHalMessage(logEl, "hal", "Thinking…");
    const pending = logEl.lastElementChild;
    if (window.ApexHal && typeof window.ApexHal.setHeaderStatus === "function") {
      window.ApexHal.setHeaderStatus("busy", "HAL Busy");
    }
    if (window.ApexHalBrain && typeof window.ApexHalBrain.setState === "function") {
      window.ApexHalBrain.setState("thinking");
    }
    const t0 = Date.now();
    halChatBusy = true;
    try {
      // 1) Deterministic board control (sync/focus/navigate) — never invents $
      let board = null;
      try {
        const boardRes = await apexFetch(`${config.apiBase}/hal/board-actions`, {
          method: "POST",
          body: JSON.stringify({ query: q, page: currentPage }),
        });
        board = await boardRes.json().catch(() => null);
      } catch (_err) {
        board = null;
      }

      if (board && board.handled && Array.isArray(board.actions) && board.actions.length) {
        await runHalBoardActions(board.actions);
        const reply = String(board.reply || "Board updated from imports.");
        if (pending) {
          finalizeHalPending(pending, reply);
        } else appendHalMessage(logEl, "hal", reply);
        if (window.ApexHalBrain && typeof window.ApexHalBrain.setState === "function") {
          window.ApexHalBrain.setState("reply");
        }
        return;
      }

      // 2) Conversational HAL — Phase I0 orchestrator when flagged; else evaluate-query
      const useOrch = await refreshOrchestratorEnabled();
      const chatUrl = useOrch ? `${config.apiBase}/hal/orchestrate` : config.halChatEndpoint;
      const chatBody = useOrch
        ? {
            query: q,
            page: currentPage,
            shiftContext: {
              page: currentPage,
              boardHint: board && board.reply ? board.reply : undefined,
              honesty: "Do not invent financial dollar amounts. Prefer import-backed facts.",
            },
          }
        : {
            query: q,
            lane: "chat8b",
            shiftContext: {
              page: currentPage,
              boardHint: board && board.reply ? board.reply : undefined,
              honesty: "Do not invent financial dollar amounts. Prefer import-backed facts.",
            },
          };
      const res = await apexFetch(chatUrl, {
        method: "POST",
        body: JSON.stringify(chatBody),
      });
      const data = await res.json().catch(() => ({}));
      let reply = "";
      if (data && (data.text || data.answer || data.reply)) {
        reply = String(data.text || data.answer || data.reply);
        if (useOrch && data.lane) {
          reply = `${reply}\n\n— lane: ${data.lane}${data.classification && data.classification.reason ? ` (${data.classification.reason})` : ""}${
            data.structured ? " · structured insight" : data.insightError ? ` · insight: ${data.insightError}` : ""
          }`;
        }
        if (useOrch && data.structured && data.insight && currentPage === "hal") {
          try {
            // Soft-refresh HAL page so ai-insight widget can pick up last insight via session
            sessionStorage.setItem("nr2-apex-last-insight", JSON.stringify(data.insight));
          } catch (_e) {
            /* ignore */
          }
        }
      } else if (data && data.error) {
        const reason = data.reason ? ` (${data.reason})` : "";
        reply = `HAL unavailable: ${data.error}${reason}`;
      } else if (!res.ok) {
        let reason = "";
        try {
          reason = data && data.reason ? ` · ${data.reason}` : "";
        } catch (_e) {
          /* ignore */
        }
        reply = `HAL request failed (HTTP ${res.status}${reason}). Hard-refresh the page if this persists.`;
      } else {
        reply = "HAL returned no text for that query.";
      }
      // Optional trailing action marker from model (ignored if invents dollars — we only allow known types)
      const marker = reply.match(/<!--HAL_ACTIONS:(\[[\s\S]*?\])-->/);
      if (marker) {
        try {
          const extra = JSON.parse(marker[1]);
          const safe = (Array.isArray(extra) ? extra : []).filter((a) =>
            a &&
            [
              "sync_imports",
              "refresh_page",
              "refresh_widget",
              "navigate",
              "focus_widget",
              "highlight_widget",
              "set_status_banner",
              "set_inputs",
              "save_scenario",
              "refresh_softdent_period",
              "focus_claim_tile",
              "open_claim_detail",
              "focus_claims_bucket",
              "narrative_append",
              "narrative_from_focused_claim",
              "run_tool",
            ].includes(a.type)
          );
          if (safe.length) await runHalBoardActions(safe);
        } catch (_err) {
          /* ignore bad marker */
        }
        reply = reply.replace(/<!--HAL_ACTIONS:\[[\s\S]*?\]-->/, "").trim();
      }
      if (pending) {
        finalizeHalPending(pending, reply);
      } else appendHalMessage(logEl, "hal", reply);
      if (window.ApexHalBrain && typeof window.ApexHalBrain.setState === "function") {
        window.ApexHalBrain.setState("reply");
      }
    } catch (err) {
      const msg = `HAL bridge error: ${String((err && err.message) || err)}`;
      if (pending) finalizeHalPending(pending, msg);
      else appendHalMessage(logEl, "hal", msg);
      if (window.ApexHalBrain && typeof window.ApexHalBrain.setState === "function") {
        window.ApexHalBrain.setState("idle");
      }
    } finally {
      halChatBusy = false;
      if (window.ApexHal && typeof window.ApexHal.setHeaderStatus === "function") {
        const st = (lastHalStatus && lastHalStatus.status) || "idle";
        window.ApexHal.setHeaderStatus(st, (lastHalStatus && lastHalStatus.statusLabel) || undefined);
      }
      void t0;
    }
  }

  async function loadHalSuggestionChips(chipHost, logEl) {
    if (!chipHost) return;
    const chips = [
      { label: "Sync & refill board", query: "Sync imports and populate the widgets" },
      { label: "Import status", query: "Verify SoftDent and QuickBooks import status" },
      { label: "Which widgets empty?", query: "Which widgets are empty on this page?" },
      { label: "All pages widget health", query: "Which widgets are empty on all pages?" },
      { label: "What should HAL learn?", query: "What would you like to learn?" },
      { label: "Tx plan data status", query: "Treatment planning data status" },
      { label: "Delta pay for D0274?", query: "How much will Delta Dental typically pay for D0274?" },
      { label: "Dictate to findings", query: "dictate findings: clinical exam supports the billed procedure" },
      { label: "How to get SoftDent exports", query: "How do I get SoftDent exports?" },
      { label: "How to get QuickBooks exports", query: "How do I get QuickBooks exports?" },
      { label: "Focus EBITDA scrubber", query: "Focus the EBITDA scrubber" },
      { label: "Focus A/R", query: "Show me A/R aging flow" },
      { label: "Focus 90-day claims", query: "Focus 90-day claims" },
      { label: "Claims aging status", query: "Claims import status" },
      { label: "Categorize assist", query: "Open categorize suggestions" },
      { label: "Print view", action: "print" },
    ];
    try {
      const res = await apexFetch(`${config.apiBase}/hal/status`);
      if (res.ok) {
        const data = await res.json();
        lastHalStatus = data;
        if (data && data.suggestion) {
          chips.unshift({ label: "Suggestion", query: String(data.suggestion) });
          if (logEl && !logEl.childElementCount) {
            appendHalMessage(logEl, "hal", String(data.suggestion));
          }
        }
      }
    } catch (_err) {
      /* chips still work offline */
    }
    chipHost.innerHTML = chips
      .map(
        (c) =>
          `<button type="button" class="apex-hal-chat__chip" data-chip-query="${c.query ? escapeAttr(c.query) : ""}" data-chip-action="${c.action || ""}">${escapeAttr(
            c.label
          )}</button>`
      )
      .join("");
    chipHost.querySelectorAll("[data-chip-action], [data-chip-query]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const action = btn.getAttribute("data-chip-action");
        const query = btn.getAttribute("data-chip-query");
        if (action === "print") {
          printPage();
          return;
        }
        if (action === "sync") {
          triggerSync();
          return;
        }
        if (query) askHal(query, logEl);
      });
    });
  }

  function escapeAttr(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;");
  }

  function wireHalChat(root) {
    const panel = root.querySelector("[data-hal-chat]");
    if (!panel || panel.dataset.wired === "1") return;
    panel.dataset.wired = "1";
    const logEl = panel.querySelector("[data-hal-messages]");
    const form = panel.querySelector("[data-hal-form]");
    const input = panel.querySelector("[data-hal-input]");
    const chips = panel.querySelector("[data-hal-chips]");
    restoreHalTranscript(logEl);
    loadHalSuggestionChips(chips, logEl);
    if (form && input) {
      form.addEventListener("submit", (ev) => {
        ev.preventDefault();
        const q = input.value;
        input.value = "";
        askHal(q, logEl);
      });
    }
  }

  function sameWidgetIds(list) {
    const ids = (list || []).map((s) => String((s && s.id) || "")).filter(Boolean);
    if (ids.length !== widgets.size) return false;
    return ids.every((id) => widgets.has(id));
  }

  function patchWidgets(list) {
    if (!sameWidgetIds(list)) return false;
    (list || []).forEach((spec) => {
      const id = String((spec && spec.id) || "");
      const w = widgets.get(id);
      if (!w) return;
      if (w.type === "hal-chat" || (spec && spec.type === "hal-chat")) {
        w.spec = spec;
        // Chat DOM is preserved across silent refresh; still clear the updating
        // overlay so pointer-events stay enabled for follow-up questions.
        if (w.element) w.element.classList.remove("is-updating");
        return;
      }
      w.patch(spec);
    });
    return true;
  }

  function softRenderHalMain(list) {
    const root = stage();
    if (!root) return false;
    const main = root.querySelector(".apex-hal-main");
    const rail = root.querySelector(".apex-hal-rail");
    const chatHost = rail && rail.querySelector(".apex-widget--hal-chat, .apex-inst--hal-chat");
    if (!main || !rail || !chatHost) return false;

    const specs = list || [];
    const chatSpec = specs.find((s) => s && s.type === "hal-chat");
    const mainSpecs = chatSpec ? specs.filter((s) => s !== chatSpec) : specs;

    // Drop non-chat widgets from the registry; keep chat DOM + history.
    Array.from(widgets.entries()).forEach(([id, w]) => {
      if (w && w.type !== "hal-chat") widgets.delete(id);
    });

    if (window.ApexHalBrain && typeof window.ApexHalBrain.destroy === "function") {
      window.ApexHalBrain.destroy();
    }
    main.innerHTML = "";
    if (window.ApexHalBrain && typeof window.ApexHalBrain.mount === "function") {
      window.ApexHalBrain.mount(main);
    }
    mainSpecs.forEach((spec, idx) => {
      const widget = new Widget(spec);
      widgets.set(widget.id, widget);
      main.appendChild(widget.render(idx));
    });
    if (chatSpec) {
      const existing = Array.from(widgets.values()).find((w) => w && w.type === "hal-chat");
      if (existing) {
        existing.spec = chatSpec;
        if (existing.element) existing.element.classList.remove("is-updating");
      } else {
        widgets.set(String(chatSpec.id || "hal-chat"), Object.assign(new Widget(chatSpec), { element: chatHost }));
      }
    }
    if (window.ApexMotion && typeof window.ApexMotion.enableHoloTilt === "function") {
      window.ApexMotion.enableHoloTilt(main);
    }
    return true;
  }

  function renderWidgets(list) {
    const root = stage();
    if (!root) return;
    if (window.ApexHalBrain && typeof window.ApexHalBrain.destroy === "function") {
      window.ApexHalBrain.destroy();
    }
    root.innerHTML = "";
    widgets.clear();

    const isHal = currentPage === "hal";
    const specs = list || [];
    const chatSpec = isHal ? specs.find((s) => s && s.type === "hal-chat") : null;
    const mainSpecs = chatSpec ? specs.filter((s) => s !== chatSpec) : specs;

    if (isHal && chatSpec) {
      root.className = "apex-stage apex-stage--hal";
      const main = document.createElement("div");
      main.className = "apex-mosaic apex-hal-main";
      const rail = document.createElement("aside");
      rail.className = "apex-hal-rail";
      root.appendChild(main);
      root.appendChild(rail);

      if (window.ApexHalBrain && typeof window.ApexHalBrain.mount === "function") {
        window.ApexHalBrain.mount(main);
      }

      mainSpecs.forEach((spec, idx) => {
        const widget = new Widget(spec);
        widgets.set(widget.id, widget);
        main.appendChild(widget.render(idx));
      });
      const chatWidget = new Widget(chatSpec);
      widgets.set(chatWidget.id, chatWidget);
      rail.appendChild(chatWidget.render(mainSpecs.length));
      if (window.ApexMotion && typeof window.ApexMotion.enableHoloTilt === "function") {
        window.ApexMotion.enableHoloTilt(main);
      }
      return;
    }

    root.className = "apex-stage apex-mosaic";
    root.dataset.page = currentPage;
    let orderedSpecs = specs;
    try {
      if (window.Nr2DashboardLayout && typeof window.Nr2DashboardLayout.orderSpecs === "function") {
        const local =
          typeof window.Nr2DashboardLayout.loadLocal === "function"
            ? window.Nr2DashboardLayout.loadLocal(currentPage)
            : null;
        if (local) orderedSpecs = window.Nr2DashboardLayout.orderSpecs(specs, local);
        window.Nr2DashboardLayout.markStage(root, currentPage);
        if (typeof window.Nr2DashboardLayout.fetchLayout === "function") {
          window.Nr2DashboardLayout.fetchLayout(currentPage).catch(() => {});
        }
      }
    } catch (_) {}
    orderedSpecs.forEach((spec, idx) => {
      const widget = new Widget(spec);
      widgets.set(widget.id, widget);
      const el = widget.render(idx);
      if (spec && spec.layout && el && el.style) {
        const w = Number(spec.layout.w);
        if (w >= 12) el.classList.add("apex-inst--full");
        else if (w >= 8) el.classList.add("apex-inst--xl");
        else if (w >= 6) el.classList.add("apex-inst--l");
      }
      root.appendChild(el);
    });
    if (window.ApexMotion && typeof window.ApexMotion.enableHoloTilt === "function") {
      window.ApexMotion.enableHoloTilt(root);
    }
  }

  function parseApexHash(raw) {
    const hash = String(raw || "")
      .replace(/^#/, "")
      .trim();
    if (!hash) return { parent: "financial", sub: null, query: {} };
    const qIdx = hash.indexOf("?");
    const pathPart = qIdx >= 0 ? hash.slice(0, qIdx) : hash;
    const queryPart = qIdx >= 0 ? hash.slice(qIdx + 1) : "";
    const query = {};
    if (queryPart) {
      try {
        new URLSearchParams(queryPart).forEach((v, k) => {
          query[k] = v;
        });
      } catch (_err) {
        /* ignore */
      }
    }
    const parts = pathPart.split("/").filter(Boolean);
    let parent = String(parts[0] || "financial")
      .toLowerCase()
      .replace(/[^a-z0-9\-]/g, "");
    let sub = parts[1]
      ? String(parts[1])
          .toLowerCase()
          .replace(/[^a-z0-9\-]/g, "")
      : null;
    if (!PARENT_PAGES.has(parent)) {
      parent = "financial";
      sub = null;
    }
    if (sub === "") sub = null;
    return { parent, sub, query };
  }

  function formatApexHash(parent, sub, query) {
    let h = String(parent || "financial").trim();
    if (sub) h += `/${sub}`;
    const id = query && query.id ? String(query.id).trim() : "";
    if (id) h += `?id=${encodeURIComponent(id)}`;
    return h;
  }

  function routeKey(parent, sub, query) {
    return formatApexHash(parent, sub, query || {});
  }

  function renderSubnav(parent, sub) {
    const nav = document.getElementById("apex-subnav");
    if (!nav) return;
    const links = SUBPAGE_LINKS[parent];
    if (!links || !links.length) {
      nav.hidden = true;
      nav.innerHTML = "";
      nav.classList.remove("is-visible");
      return;
    }
    nav.hidden = false;
    nav.classList.add("is-visible");
    nav.innerHTML = links
      .map((item) => {
        const active = (item.sub || null) === (sub || null);
        return `<button type="button" class="apex-subnav-btn${active ? " is-active" : ""}" data-sub-parent="${parent}" data-sub="${
          item.sub || ""
        }">${escapeHtml(item.label)}</button>`;
      })
      .join("");
    nav.querySelectorAll("[data-sub-parent]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const p = btn.getAttribute("data-sub-parent") || parent;
        const s = btn.getAttribute("data-sub") || "";
        const q = s === "detail" && currentQuery.id ? { id: currentQuery.id } : {};
        loadPage(formatApexHash(p, s || null, q));
      });
    });
  }

  function setPageTitle(pageId, sub) {
    const el = document.getElementById("apex-page-title");
    if (el) {
      const base = PAGE_TITLES[pageId] || pageId || "Apex";
      const subLabel = sub ? SUBPAGE_TITLES[sub] || sub : "";
      el.textContent = subLabel ? `${base} · ${subLabel}` : base;
      if (window.ApexMotion && typeof window.ApexMotion.triggerGlitch === "function") {
        window.ApexMotion.triggerGlitch(el);
      }
    }
    if (window.ApexMotion && typeof window.ApexMotion.flashStage === "function") {
      window.ApexMotion.flashStage();
    }
  }

  function setMeta(payload) {
    const el = metaEl();
    if (!el) return;
    const at = payload && payload.refreshedAt ? payload.refreshedAt : "—";
    const page = payload && payload.page ? payload.page : routeKey(currentPage, currentSub, currentQuery);
    const note = payload && payload.sourceNote ? payload.sourceNote : "";
    el.textContent = `Page: ${page} · Refreshed: ${at}${note ? " · " + note : ""}`;
    el.classList.add("is-live");
    setTimeout(() => el.classList.remove("is-live"), 1200);
  }

  function setHash(parent, sub, query) {
    const desired = `#${formatApexHash(parent, sub, query)}`;
    if (location.hash !== desired) {
      history.replaceState(null, "", desired);
    }
  }

  async function loadPage(pageIdOrHash, opts) {
    let silent = Boolean(opts && opts.silent);
    const parsed = parseApexHash(pageIdOrHash || formatApexHash(currentPage, currentSub, currentQuery));
    currentPage = parsed.parent || currentPage || "financial";
    currentSub = parsed.sub;
    currentQuery = parsed.query && typeof parsed.query === "object" ? parsed.query : {};
    // Never wipe HAL chat while a reply is in flight (auto-refresh / nav race).
    if (halChatBusy && currentPage === "hal") silent = true;
    setHash(currentPage, currentSub, currentQuery);
    setPageTitle(currentPage, currentSub);
    renderSubnav(currentPage, currentSub);
    const root = stage();
    if (!root) return;

    document.querySelectorAll(".apex-nav-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.page === currentPage);
    });

    // Interactive narratives workspace (not KPI mosaic)
    if (currentPage === "narratives" && !currentSub) {
      if (refreshTimer) clearInterval(refreshTimer);
      if (window.ApexHalBrain && typeof window.ApexHalBrain.destroy === "function") {
        window.ApexHalBrain.destroy();
      }
      if (!silent || !window.ApexNarratives || !window.ApexNarratives.isActive()) {
        root.className = "apex-stage apex-mosaic";
        root.innerHTML = '<div class="apex-status-msg">Loading narratives bridge…</div>';
        if (window.ApexNarratives && typeof window.ApexNarratives.mount === "function") {
          await window.ApexNarratives.mount(root);
        } else {
          root.innerHTML =
            '<div class="apex-status-msg is-error">Narratives module missing (apex-narratives.js).</div>';
        }
      }
      setMeta({ page: "narratives", refreshedAt: new Date().toISOString(), sourceNote: "interactive narratives bridge" });
      return;
    }

    if (!silent) {
      root.className =
        currentPage === "hal" && !currentSub ? "apex-stage apex-stage--hal" : "apex-stage apex-mosaic";
      root.dataset.page = currentPage;
      if (currentSub) root.dataset.sub = currentSub;
      else delete root.dataset.sub;
      root.innerHTML = '<div class="apex-status-msg">Loading bridge instruments…</div>';
    } else {
      root.dataset.page = currentPage;
      if (currentSub) root.dataset.sub = currentSub;
      else delete root.dataset.sub;
      root.querySelectorAll(".apex-inst, .apex-widget").forEach((el) => {
        // Keep HAL chat interactive during silent refresh (it is not re-patched).
        if (el.classList.contains("apex-widget--hal-chat")) return;
        el.classList.add("is-updating");
      });
    }

    try {
      const res = await apexFetch(`${config.apiBase}/widgets/${encodeURIComponent(currentPage)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const payload = await res.json();
      const list = payload.widgets || [];
      if (silent && widgets.size && patchWidgets(list)) {
        /* in-place — no flash */
      } else if (silent && currentPage === "hal" && !currentSub) {
        // Never full-remount HAL on silent refresh — that wiped chat history on hover/timer races.
        if (!softRenderHalMain(list)) {
          root.querySelectorAll(".apex-inst, .apex-widget").forEach((el) => el.classList.remove("is-updating"));
        }
      } else {
        renderWidgets(list);
        if (currentPage === "hal" && !currentSub) {
          restoreHalTranscript(document.querySelector("[data-hal-messages]"));
        }
        if (!silent) {
          root.classList.add("is-entering");
          setTimeout(() => root.classList.remove("is-entering"), 400);
        }
      }
      setMeta(payload);
      startAutoRefresh();
    } catch (err) {
      if (!silent) {
        root.className = "apex-stage apex-mosaic";
        root.innerHTML = `<div class="apex-status-msg is-error">Error loading data: ${String(
          (err && err.message) || err
        )}</div>`;
      } else {
        root.querySelectorAll(".apex-inst, .apex-widget").forEach((el) => el.classList.remove("is-updating"));
      }
    }
  }

  function startAutoRefresh() {
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = setInterval(
      () => loadPage(formatApexHash(currentPage, currentSub, currentQuery), { silent: true }),
      config.refreshInterval
    );
  }

  async function printPage(widgetId) {
    let packetUrl = "";
    try {
      const res = await apexFetch(`${config.apiBase}/print/view`, {
        method: "POST",
        body: JSON.stringify({
          page: currentPage,
          widgets: widgetId ? [widgetId] : Array.from(widgets.keys()),
          format: "browser",
        }),
      });
      if (res.ok) {
        const data = await res.json();
        packetUrl = (data && data.url) || "";
      }
    } catch (_err) {
      /* print still proceeds locally */
    }
    if (packetUrl) {
      window.open(packetUrl, "_blank", "noopener,width=720,height=640");
      return;
    }
    document.body.classList.add("is-printing");
    window.print();
    setTimeout(() => document.body.classList.remove("is-printing"), 500);
  }

  async function triggerSync() {
    const header = document.getElementById("apex-header");
    if (header) header.classList.add("is-syncing");
    if (window.ApexHal && typeof window.ApexHal.setHeaderStatus === "function") {
      window.ApexHal.setHeaderStatus("syncing", "Syncing…");
    }
    let syncNote = "";
    try {
      const res = await apexFetch(`${config.apiBase}/sync/trigger`, {
        method: "POST",
        body: JSON.stringify({ page: currentPage, fullSync: true }),
      });
      const data = await res.json().catch(() => ({}));
      const fresh = data && data.freshness;
      if (fresh && fresh.message) syncNote = String(fresh.message);
      else if (data && data.loadedAt) syncNote = `Synced · ${data.loadedAt}`;
      if (data && data.ok === false) syncNote = data.error || "Sync error";
    } catch (_err) {
      syncNote = "Sync request failed — refreshing anyway";
    }
    await loadPage(formatApexHash(currentPage, currentSub, currentQuery), { silent: true });
    const meta = metaEl();
    if (meta && syncNote) {
      meta.textContent = `${meta.textContent} · ${syncNote}`;
      meta.classList.add("is-live");
    }
    if (header) header.classList.remove("is-syncing");
    if (window.ApexHal && typeof window.ApexHal.pollOnce === "function") {
      window.ApexHal.pollOnce({ showSuggest: true, forceSuggest: true });
    } else if (window.ApexHal && typeof window.ApexHal.setHeaderStatus === "function") {
      window.ApexHal.setHeaderStatus("idle", "HAL Standby");
    }
  }

  function askHalFromBridge(text) {
    const q = String(text || "").trim();
    if (!q) return;
    if (currentPage !== "hal") {
      loadPage("hal").then(() => {
        const logEl = document.querySelector("[data-hal-messages]");
        askHal(q, logEl);
      });
      return;
    }
    const logEl = document.querySelector("[data-hal-messages]");
    askHal(q, logEl);
  }

  function onHalStatus(data) {
    lastHalStatus = data;
  }

  function wireUi() {
    document.querySelectorAll("[data-page]").forEach((btn) => {
      btn.addEventListener("click", () => loadPage(btn.dataset.page));
    });
    const printBtn = document.getElementById("btn-print");
    const refreshBtn = document.getElementById("btn-refresh");
    const askHal = document.getElementById("btn-ask-hal");
    if (printBtn) {
      printBtn.innerHTML = ICONS.print;
      printBtn.addEventListener("click", () => printPage());
    }
    if (refreshBtn) {
      refreshBtn.innerHTML = ICONS.refresh;
      refreshBtn.addEventListener("click", () => triggerSync());
    }
    if (askHal) {
      askHal.addEventListener("click", () => {
        const suggestion =
          (document.getElementById("hal-suggestion-text") || {}).textContent ||
          (window.ApexHal && window.ApexHal.lastSuggestion) ||
          "What should I prioritize today?";
        askHalFromBridge(String(suggestion).trim() || "What should I prioritize today?");
      });
    }
    window.addEventListener("hashchange", () => {
      const hash = (location.hash || "").replace(/^#/, "").trim();
      const next = routeKey(currentPage, currentSub, currentQuery);
      if (hash && hash !== next) loadPage(hash);
    });
  }

  async function init() {
    wireUi();
    await ensureSessionToken();
    const hash = (location.hash || "").replace(/^#/, "").trim();
    const start = hash || "financial";
    await loadPage(start);
  }

  window.Apex = {
    loadPage,
    config,
    assetVersion: ASSET_V,
    printPage,
    triggerSync,
    apexFetch,
    askHalFromBridge,
    runHalBoardActions,
    onHalStatus,
    openClaimDrawer,
    closeClaimDrawer,
    focusClaimTile,
    parseApexHash,
    formatApexHash,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
