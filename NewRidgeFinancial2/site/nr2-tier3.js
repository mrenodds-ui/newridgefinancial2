/**
 * Moonshot Tier S3 (hal-10085) — semantic zoom, HAL presence, hero mirror, stream citations.
 */
const NR2Tier3 = (function () {
  const STORAGE_ZOOM = "nr2_semantic_zoom_v1";
  const EXECUTIVE_WIDGETS = {
    financial: ["nr2AlertTicker", "nr2KpiRibbon", "nr2MonthlyTrendCombo", "nr2ProductionReconciliation", "practiceFinancialOverview"],
    taxes: ["quickbooksProfitLossDetail", "taxBookToTaxBridge", "taxReasonableComp", "taxFederalStateSplit"],
    softdent: ["softdentOperatoryGrid", "careDeliveryPerformance", "softdentCollectionsDaily"],
    quickbooks: ["quickbooksProfitLossDetail", "quickbooksCashFlowTrend", "quickbooksNetIncomeSummary"],
    ar: ["arAgingAndCollections", "arTopClaimsQueue"],
    claims: ["claimsPipeline", "claimsRiskQueue"],
    documents: ["periodCloseAndPosting", "documentIntakeQueue"],
    "office-manager": ["officeManagerPriorities", "officeManagerHealth"],
  };

  let presenceState = "idle";
  let heroMirrorTimer = null;

  function esc(v) {
    return String(v == null ? "" : v)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function isWorkstation() {
    return !!(typeof globalThis !== "undefined" && globalThis.NR2_WORKSTATION_ONLY);
  }

  function isFinancialHub() {
    if (isWorkstation()) return false;
    const port = typeof window !== "undefined" && window.location ? String(window.location.port || "") : "";
    return !port || port === "8765";
  }

  function getZoomMode(pageId) {
    try {
      const raw = sessionStorage.getItem(STORAGE_ZOOM);
      const all = raw ? JSON.parse(raw) : {};
      return all[pageId] || "detail";
    } catch {
      return "detail";
    }
  }

  function setZoomMode(pageId, mode) {
    try {
      const raw = sessionStorage.getItem(STORAGE_ZOOM);
      const all = raw ? JSON.parse(raw) : {};
      all[pageId] = mode === "executive" ? "executive" : "detail";
      sessionStorage.setItem(STORAGE_ZOOM, JSON.stringify(all));
    } catch {
      /* ignore */
    }
  }

  function applySemanticZoom(root, pageId) {
    const body = root && (root.querySelector(".ms-page-body") || root.querySelector(".ms-page"));
    if (!body) return;
    const mode = getZoomMode(pageId);
    body.setAttribute("data-nr2-semantic-zoom", mode);
    const allow = EXECUTIVE_WIDGETS[pageId] || null;
    if (!allow) return;
    body.querySelectorAll("[data-hal-widget-key]").forEach((el) => {
      const key = el.getAttribute("data-hal-widget-key");
      const show = mode !== "executive" || allow.includes(key);
      el.classList.toggle("nr2-zoom-hidden", !show);
      if (mode === "executive" && show) el.classList.add("nr2-zoom-hero");
    });
    const toggle = root.querySelector("[data-nr2-semantic-zoom-toggle]");
    if (toggle) {
      toggle.setAttribute("aria-pressed", mode === "executive" ? "true" : "false");
      toggle.textContent = mode === "executive" ? "Detail view" : "Executive view";
    }
  }

  function bindSemanticZoom(root, pageId) {
    if (!root || !pageId || pageId === "hal") return;
    applySemanticZoom(root, pageId);
    if (root.dataset.nr2ZoomWired === "1") return;
    root.dataset.nr2ZoomWired = "1";
    root.addEventListener("click", (event) => {
      const btn = event.target.closest("[data-nr2-semantic-zoom-toggle]");
      if (btn) {
        event.preventDefault();
        const next = getZoomMode(pageId) === "executive" ? "detail" : "executive";
        setZoomMode(pageId, next);
        applySemanticZoom(root, pageId);
        return;
      }
      const drill = event.target.closest("[data-nr2-zoom-drill]");
      if (drill) {
        event.preventDefault();
        const key = drill.getAttribute("data-nr2-zoom-drill");
        setZoomMode(pageId, "detail");
        applySemanticZoom(root, pageId);
        if (key) {
          setTimeout(() => {
            if (typeof scrollStaffWidgetIntoView === "function") scrollStaffWidgetIntoView(key);
          }, 80);
        }
      }
    });
    root.querySelectorAll(".kpi-tile[data-hal-widget-key], .widget-mosaic-tile[data-hal-widget-key]").forEach((el) => {
      if (el.dataset.nr2ZoomDrillWired === "1") return;
      el.dataset.nr2ZoomDrillWired = "1";
      el.setAttribute("data-nr2-zoom-drill", el.getAttribute("data-hal-widget-key") || "");
    });
  }

  function syncPresence(opts) {
    const o = opts || {};
    let next = "idle";
    if (o.loading) next = "thinking";
    else if (o.alert) next = "alert";
    presenceState = next;
    if (typeof document === "undefined") return;
    document.querySelectorAll("[data-hal-presence-orb]").forEach((orb) => {
      orb.classList.remove("hal-presence-orb--idle", "hal-presence-orb--thinking", "hal-presence-orb--alert");
      orb.classList.add(`hal-presence-orb--${next}`);
      orb.setAttribute("data-hal-presence-state", next);
      orb.setAttribute(
        "aria-label",
        next === "thinking" ? "HAL thinking" : next === "alert" ? "HAL alert" : "HAL idle",
      );
    });
  }

  function detectAlertState() {
    try {
      const feed = typeof halWidgetFeed !== "undefined" ? halWidgetFeed : null;
      const briefing =
        typeof halData !== "undefined" && halData && halData.runtime && halData.runtime.proactiveBriefing
          ? halData.runtime.proactiveBriefing
          : null;
      if (briefing && Array.isArray(briefing.blockers) && briefing.blockers.length) return true;
      const D = typeof PageCanvasData !== "undefined" ? PageCanvasData : null;
      if (D && D.nr2AlertTicker) {
        const ticker = D.nr2AlertTicker();
        const items = (ticker && ticker.items) || [];
        if (items.some((item) => item && item.level && item.level !== "ok")) return true;
      }
      if (feed && feed.sourceHealth && feed.sourceHealth.missing > 0) return true;
    } catch {
      /* optional */
    }
    return false;
  }

  function refreshPresence() {
    syncPresence({
      loading: typeof halAskLoading !== "undefined" && halAskLoading,
      alert: detectAlertState(),
    });
  }

  function toolCitationLabel(toolId) {
    const id = String(toolId || "");
    if (/widget|feed/i.test(id)) return "Widget feed";
    if (/diagnostic|import/i.test(id)) return "Import diagnostics";
    if (/grep|semantic|read_program|read_file/i.test(id)) return "Program source";
    return id.replace(/_/g, " ").replace(/^read /, "").slice(0, 28);
  }

  function citationWidgetsFromTools(tools) {
    const keys = [];
    (tools || []).forEach((tool) => {
      const t = String(tool || "").toLowerCase();
      if (t.includes("widget") || t.includes("feed")) {
        ["practiceFinancialOverview", "nr2ProductionReconciliation", "quickbooksProfitLossDetail"].forEach((k) => {
          if (!keys.includes(k)) keys.push(k);
        });
      }
      if (t.includes("diagnostic") || t.includes("import")) {
        if (!keys.includes("halImportHealth")) keys.push("halImportHealth");
      }
    });
    return keys.slice(0, 4);
  }

  function renderCitationChipsHtml(tools, widgetKeys) {
    const keys = (widgetKeys && widgetKeys.length ? widgetKeys : citationWidgetsFromTools(tools)).slice(0, 5);
    if (!keys.length && !(tools && tools.length)) return "";
    const chips = (tools || [])
      .slice(0, 3)
      .map(
        (tool) =>
          `<span class="hal-citation-chip hal-citation-chip--tool" title="Source trace">${esc(toolCitationLabel(tool))}</span>`,
      )
      .join("");
    const widgets = keys
      .map(
        (key) =>
          `<button type="button" class="hal-citation-chip hal-citation-chip--widget" data-hal-citation-widget="${esc(key)}" title="Open widget source">${esc(key.replace(/([A-Z])/g, " $1").trim())}</button>`,
      )
      .join("");
    return `<div class="hal-stream-citations" aria-label="HAL source citations">${chips}${widgets}</div>`;
  }

  function bindCitationClicks(root) {
    if (!root || root.dataset.nr2CitationWired === "1") return;
    root.dataset.nr2CitationWired = "1";
    root.addEventListener("click", (event) => {
      const chip = event.target.closest("[data-hal-citation-widget]");
      if (!chip) return;
      event.preventDefault();
      const key = chip.getAttribute("data-hal-citation-widget");
      if (!key) return;
      const pageId = (window.location.hash || "").replace("#", "") || "financial";
      if (pageId === "hal") {
        if (typeof runHalPageCmd === "function") runHalPageCmd(`Explain ${key} widget source trace`);
        return;
      }
      if (typeof scrollStaffWidgetIntoView === "function") scrollStaffWidgetIntoView(key);
    });
  }

  function updateStreamCitations(tools, widgetKeys) {
    if (typeof document === "undefined") return;
    document.querySelectorAll(".hal-stream-citations--live").forEach((el) => el.remove());
    const html = renderCitationChipsHtml(tools, widgetKeys);
    if (!html) return;
    const host =
      document.querySelector(".chat-messages .message-hal:last-child") ||
      document.querySelector("#halChatLog .hal-msg--hal:last-child");
    if (!host) return;
    const wrap = document.createElement("div");
    wrap.className = "hal-stream-citations--live";
    wrap.innerHTML = html;
    host.appendChild(wrap);
    bindCitationClicks(host.closest(".ms-page") || document.getElementById("appPage") || document.body);
  }

  async function hubAuthHeadersForNotify() {
    const headers = { "Content-Type": "application/json" };
    if (typeof window !== "undefined" && window.NR2_HUB_TOKEN) {
      headers["X-Hub-Token"] = String(window.NR2_HUB_TOKEN);
      return headers;
    }
    try {
      const port = typeof window !== "undefined" && window.NR2_LOOPBACK_PORT ? Number(window.NR2_LOOPBACK_PORT) : 8765;
      const host = typeof window !== "undefined" && window.location ? window.location.hostname || "127.0.0.1" : "127.0.0.1";
      const protocol = typeof window !== "undefined" && window.location ? window.location.protocol || "http:" : "http:";
      const res = await fetch(`${protocol}//${host}:${port}/api/app-info`, { cache: "no-store" });
      if (res.ok) {
        const info = await res.json();
        if (info && info.hubToken && typeof window !== "undefined") {
          window.NR2_HUB_TOKEN = String(info.hubToken);
          headers["X-Hub-Token"] = window.NR2_HUB_TOKEN;
        }
      }
    } catch {
      /* optional */
    }
    return headers;
  }

  async function publishHeroMetrics(pageId) {
    if (!isFinancialHub()) return;
    const pid = pageId || "financial";
    const D = typeof PageCanvasData !== "undefined" ? PageCanvasData : null;
    if (!D) return;
    let metrics = [];
    if (pid === "financial" && D.financialKpis) metrics = D.financialKpis().slice(0, 4);
    else if (pid === "softdent" && D.softdentKpis) metrics = D.softdentKpis().slice(0, 4);
    else if (D.financialKpis) metrics = D.financialKpis().slice(0, 4);
    if (!metrics.length) return;
    const payload = {
      kind: "hero-metrics",
      channel: "hero-mirror",
      from: "Financial8765",
      target: "workstation",
      pageId: pid,
      heroMetrics: metrics.map((k) => ({ label: k.label, value: k.value, hint: k.hint || "" })),
      at: new Date().toISOString(),
    };
    try {
      const port = typeof window !== "undefined" && window.NR2_LOOPBACK_PORT ? Number(window.NR2_LOOPBACK_PORT) : 8765;
      const host = typeof window !== "undefined" && window.location ? window.location.hostname || "127.0.0.1" : "127.0.0.1";
      const protocol = typeof window !== "undefined" && window.location ? window.location.protocol || "http:" : "http:";
      const headers = await hubAuthHeadersForNotify();
      await fetch(`${protocol}//${host}:${port}/api/hub/notify`, {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
        cache: "no-store",
      });
    } catch {
      /* hub optional */
    }
  }

  function renderHeroMirrorStrip(metrics, pageId) {
    if (!metrics || !metrics.length) {
      return `<div class="nr2-hero-mirror nr2-hero-mirror--empty" role="status"><span class="nr2-hero-mirror__label">8765 mirror</span><span>Awaiting financial hub metrics…</span></div>`;
    }
    const tiles = metrics
      .slice(0, 4)
      .map(
        (m) =>
          `<div class="nr2-hero-mirror__tile"><span class="nr2-hero-mirror__value">${esc(m.value)}</span><span class="nr2-hero-mirror__label">${esc(m.label)}</span></div>`,
      )
      .join("");
    return `<div class="nr2-hero-mirror" role="status" aria-label="Financial hub hero metrics mirror">
      <span class="nr2-hero-mirror__badge">8765 · ${esc(pageId || "financial")}</span>
      <div class="nr2-hero-mirror__tiles">${tiles}</div>
    </div>`;
  }

  async function pollHeroMirror(root) {
    if (!isWorkstation()) return;
    const host = root || document.getElementById("workstationPage") || document.body;
    try {
      let data = null;
      if (typeof HalHubClient !== "undefined" && typeof HalHubClient.fetchLastBroadcast === "function") {
        data = await HalHubClient.fetchLastBroadcast();
      } else {
        const protocol = typeof window !== "undefined" && window.location ? window.location.protocol || "http:" : "http:";
        const hostname = typeof window !== "undefined" && window.location ? window.location.hostname || "127.0.0.1" : "127.0.0.1";
        const headers = {};
        if (typeof window !== "undefined" && window.NR2_HUB_TOKEN) headers["X-Hub-Token"] = String(window.NR2_HUB_TOKEN);
        const res = await fetch(`${protocol}//${hostname}:8765/api/hub/last-broadcast`, { cache: "no-store", headers });
        if (!res.ok) return;
        data = await res.json();
      }
      const broadcast =
        data && data.kind === "hero-metrics"
          ? data
          : data && data.lastBroadcast && data.lastBroadcast.kind === "hero-metrics"
            ? data.lastBroadcast
            : null;
      if (!broadcast || !Array.isArray(broadcast.heroMetrics)) return;
      let strip = host.querySelector(".nr2-hero-mirror");
      const html = renderHeroMirrorStrip(broadcast.heroMetrics, broadcast.pageId);
      if (strip) strip.outerHTML = html;
      else {
        const article = host.querySelector(".pv--workstation") || host.firstElementChild;
        if (article) article.insertAdjacentHTML("afterbegin", html);
      }
    } catch {
      /* optional */
    }
  }

  function startHeroMirrorConsumer(root) {
    if (!isWorkstation()) return;
    pollHeroMirror(root);
    if (heroMirrorTimer) clearInterval(heroMirrorTimer);
    heroMirrorTimer = setInterval(() => pollHeroMirror(root), 15000);
  }

  function mountPage(root, pageId, opts) {
    if (!root) return;
    bindSemanticZoom(root, pageId);
    bindCitationClicks(root);
    refreshPresence();
    if (isFinancialHub() && pageId === "financial") {
      publishHeroMetrics(pageId);
    }
  }

  function install() {
    refreshPresence();
    if (isWorkstation()) {
      startHeroMirrorConsumer(document.getElementById("workstationPage"));
    }
    if (typeof window !== "undefined") {
      window.addEventListener("nr2:page-refresh-requested", () => refreshPresence());
      window.addEventListener("nr2-import-readiness-changed", () => refreshPresence());
    }
  }

  function renderSemanticZoomToggle(pageId) {
    if (!pageId || pageId === "hal" || pageId === "workstation") return "";
    const mode = getZoomMode(pageId);
    const label = mode === "executive" ? "Detail view" : "Executive view";
    return `<button type="button" class="semantic-zoom-btn" data-nr2-semantic-zoom-toggle aria-pressed="${mode === "executive" ? "true" : "false"}">${label}</button>`;
  }

  return {
    install,
    mountPage,
    syncPresence,
    refreshPresence,
    publishHeroMetrics,
    pollHeroMirror,
    renderCitationChipsHtml,
    updateStreamCitations,
    renderSemanticZoomToggle,
    getZoomMode,
    setZoomMode,
    presenceState: () => presenceState,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = NR2Tier3;
}
if (typeof globalThis !== "undefined") {
  globalThis.NR2Tier3 = NR2Tier3;
}
if (typeof window !== "undefined") {
  window.NR2Tier3 = NR2Tier3;
}
