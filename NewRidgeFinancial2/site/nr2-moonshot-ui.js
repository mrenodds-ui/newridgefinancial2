/**
 * Moonshot Phase 8 UI — OCR inbox, audit dashboard, clinical bridge, close wizard, charts.
 */
const NR2MoonshotUI = (function () {
  function esc(v) {
    return String(v == null ? "" : v)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }

  async function fetchJson(path) {
    if (typeof DesktopBridge !== "undefined" && DesktopBridge.loopbackJson) {
      return DesktopBridge.loopbackJson(path);
    }
    const r = await fetch(path, { cache: "no-store" });
    return r.json();
  }

  async function postJson(path, body) {
    if (typeof DesktopBridge !== "undefined" && DesktopBridge.loopbackJson) {
      return DesktopBridge.loopbackJson(path, { method: "POST", body: JSON.stringify(body || {}) });
    }
    const r = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    return r.json();
  }

  function pilotPhaseLabel(phase) {
    const p = String(phase || "shadow").toLowerCase();
    if (p === "cutover") return "Cutover — system of record";
    if (p === "supervised") return "Supervised pilot";
    return "Shadow mode";
  }

  async function renderPilotPhaseBanner() {
    if (typeof document === "undefined") return;
    let info = null;
    try {
      info = await fetchJson("/api/app-info");
    } catch {
      return;
    }
    const pilot = (info && info.pilot) || {};
    const phase = pilot.phase || "shadow";
    let bar = document.getElementById("nr2-pilot-phase-banner");
    if (!bar) {
      const host = document.getElementById("appPage") || document.body;
      bar = document.createElement("div");
      bar.id = "nr2-pilot-phase-banner";
      bar.className = "nr2-pilot-phase-banner";
      const traffic = document.getElementById("nr2-import-traffic-banner");
      if (traffic && traffic.parentNode) traffic.parentNode.insertBefore(bar, traffic.nextSibling);
      else if (host.firstChild) host.insertBefore(bar, host.firstChild);
      else host.appendChild(bar);
    }
    bar.className = `nr2-pilot-phase-banner nr2-pilot-phase-banner--${String(phase).replace(/[^a-z0-9_-]/gi, "")}`;
    bar.innerHTML =
      `<strong>Pilot:</strong> ${esc(pilotPhaseLabel(phase))}` +
      (pilot.systemOfRecord ? " · NR2 is system of record on this workstation" : " · SoftDent remains parallel system of record") +
      (pilot.cutoverAttested ? " · attested" : "");
    bar.setAttribute("role", "status");
  }

  function installPilotBanner() {
    renderPilotPhaseBanner().catch(() => {});
    if (typeof window !== "undefined") {
      window.addEventListener("nr2-import-readiness-changed", () => {
        renderPilotPhaseBanner().catch(() => {});
      });
    }
  }

  function confidenceBadgeClass(badge) {
    const b = String(badge || "low").toLowerCase();
    if (b === "high") return "nr2-era-badge--high";
    if (b === "medium") return "nr2-era-badge--medium";
    return "nr2-era-badge--low";
  }

  function renderEraMatchCard(match, host) {
    if (!host || !match) return;
    const card = document.createElement("article");
    card.className = "nr2-era-card";
    card.dataset.eraLineId = String(match.eraLineId || match.id || "");
    card.innerHTML =
      `<header><span class="nr2-era-badge ${confidenceBadgeClass(match.confidenceBadge)}">${esc(
        (match.confidenceBadge || "low").toUpperCase(),
      )}</span> ` +
      `<strong>${esc(match.referenceId || match.id)}</strong> → ${esc(match.predictedClaimId || "—")}</header>` +
      `<p class="nr2-muted">Confidence ${Math.round(Number(match.confidence || 0) * 100)}% · $${esc(match.paidAmount || "0")}</p>` +
      `<div class="nr2-era-actions">` +
      `<button type="button" class="nr2-era-up" title="Correct match">👍</button>` +
      `<button type="button" class="nr2-era-down" title="Wrong match">👎</button>` +
      `</div>`;
    card.querySelector(".nr2-era-up").addEventListener("click", async () => {
      await postJson("/api/era/match-feedback", {
        eraLineId: match.eraLineId || match.id,
        predictedClaimId: match.predictedClaimId,
        approved: true,
        confidence: match.confidence,
      });
      card.remove();
    });
    card.querySelector(".nr2-era-down").addEventListener("click", async () => {
      const corrected = window.prompt("Correct claim ID (optional):") || "";
      await postJson("/api/era/match-feedback", {
        eraLineId: match.eraLineId || match.id,
        predictedClaimId: match.predictedClaimId,
        correctedClaimId: corrected || undefined,
        approved: false,
        confidence: match.confidence,
      });
      card.remove();
    });
    host.appendChild(card);
  }

  async function renderEraMatchPanel(container) {
    if (!container) return;
    const data = await fetchJson("/api/era/pending-matches?limit=12");
    const items = (data && data.items) || [];
    const section = document.createElement("section");
    section.className = "nr2-panel nr2-panel--era";
    section.innerHTML = `<h3>ERA Match Review (${items.length})</h3><div class="nr2-era-list"></div>`;
    container.appendChild(section);
    const list = section.querySelector(".nr2-era-list");
    if (!items.length) {
      list.innerHTML = `<p class="nr2-muted">No ERA matches pending review.</p>`;
      return;
    }
    items.forEach((m) => renderEraMatchCard(m, list));
  }

  async function resolveOcrItem(excId, action) {
    return postJson(`/api/ocr-exceptions/${encodeURIComponent(excId)}/resolve`, { action });
  }

  async function renderOcrExceptions(container) {
    if (!container) return;
    const data = await fetchJson("/api/ocr-exceptions?status=pending");
    const items = (data && data.items) || [];
    container.insertAdjacentHTML(
      "beforeend",
      `<section class="nr2-panel nr2-panel--ocr"><h3>OCR Exceptions (${items.length})</h3>` +
        (items.length
          ? `<ul class="nr2-ocr-list">${items
              .map(
                (it) =>
                  `<li data-ocr-id="${esc(it.id)}"><strong>${esc(it.sourceDoc || it.id)}</strong> · ${esc(it.confidenceLabel || "low")} · ${esc(
                    it.preview || "",
                  ).slice(0, 120)}` +
                  `<span class="nr2-ocr-actions">` +
                  `<button type="button" class="nr2-ocr-resolve" data-action="enqueue">Queue posting</button>` +
                  `<button type="button" class="nr2-ocr-resolve" data-action="discard">Discard</button>` +
                  `</span></li>`,
              )
              .join("")}</ul>`
          : `<p class="nr2-muted">No low-confidence OCR items pending.</p>`) +
        `</section>`,
    );
    container.querySelectorAll(".nr2-ocr-resolve").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const li = btn.closest("[data-ocr-id]");
        const id = li && li.getAttribute("data-ocr-id");
        if (!id) return;
        btn.disabled = true;
        try {
          await resolveOcrItem(id, btn.getAttribute("data-action") || "resolve");
          if (li) li.remove();
        } catch {
          btn.disabled = false;
        }
      });
    });
  }

  async function renderAuditDashboard(container) {
    if (!container) return;
    const data = await fetchJson("/api/audit-log/mutations?limit=40");
    const items = (data && data.items) || [];
    container.insertAdjacentHTML(
      "beforeend",
      `<section class="nr2-panel nr2-panel--audit"><h3>Audit Log</h3><ul class="nr2-audit-list">${items
        .slice(0, 15)
        .map((it) => `<li>${esc(it.ts || "")} · ${esc(it.action || "")} · ${esc(it.actor || "")}</li>`)
        .join("")}</ul></section>`,
    );
  }

  async function renderClinicalBridge(container) {
    if (!container) return;
    const data = await fetchJson("/api/clinical-summaries?limit=5");
    const items = (data && data.items) || [];
    container.insertAdjacentHTML(
      "beforeend",
      `<section class="nr2-panel nr2-panel--clinical"><h3>Clinical Context (8766)</h3>` +
        `<textarea class="nr2-clinical-paste" rows="3" placeholder="Paste SideNotes clinical narrative for HAL claims context…"></textarea>` +
        (items.length
          ? `<ul>${items.map((it) => `<li>${esc(it.summary || it.text || "")}</li>`).join("")}</ul>`
          : `<p class="nr2-muted">No recent SideNotes summaries.</p>`) +
        `</section>`,
    );
  }

  function renderCloseWizard(container) {
    if (!container) return;
    container.insertAdjacentHTML(
      "beforeend",
      `<section class="nr2-panel nr2-panel--wizard"><h3>Month-End Close Wizard</h3>` +
        `<ol class="nr2-wizard-steps"><li>Verify import freshness</li><li>Confirm backup</li><li>Run HAL reconciliation</li><li>Approve closeout</li></ol>` +
        `<button type="button" class="nr2-wizard-run" data-nr2-close-wizard>Start wizard</button></section>`,
    );
    const btn = container.querySelector("[data-nr2-close-wizard]");
    if (btn) {
      btn.addEventListener("click", async () => {
        const health = await fetchJson("/api/health");
        const readiness = await fetchJson("/api/import-readiness?operation=posting");
        alert(
          `Close wizard check:\nDB: ${health.db ? "OK" : "FAIL"}\nOllama: ${health.ollama ? "OK" : "FAIL"}\nImport: ${readiness.level}`,
        );
      });
    }
  }

  function mapKanbanColumns(postingItems, ocrItems) {
    const today = new Date().toISOString().slice(0, 10);
    const items = Array.isArray(postingItems) ? postingItems : [];
    const ocr = Array.isArray(ocrItems) ? ocrItems : [];
    return {
      pendingOcr: ocr.map((it) => ({
        id: it.id,
        description: it.sourceDoc || it.id,
        amount: it.confidenceLabel,
      })),
      ready: items
        .filter((it) => it.status === "pending_review")
        .map((it) => ({ id: it.queueId, description: it.description, amount: it.amount })),
      exceptions: items
        .filter((it) => it.status === "rejected")
        .map((it) => ({ id: it.queueId, description: it.description, amount: it.amount })),
      postedToday: items
        .filter((it) => it.status === "approved" && String(it.reviewedAtUtc || "").slice(0, 10) === today)
        .map((it) => ({ id: it.queueId, description: it.description, amount: it.amount })),
    };
  }

  function resolveWidgetMount(root, widgetKey) {
    if (!root || !widgetKey) return null;
    const selectors = [
      `[data-nr2-chart-host="${widgetKey}"]`,
      `.widget-card[data-hal-widget-key="${widgetKey}"]`,
      `.panel[data-hal-widget-key="${widgetKey}"]`,
      `.card.chart-large[data-hal-widget-key="${widgetKey}"]`,
      `.card.chart-medium[data-hal-widget-key="${widgetKey}"]`,
      `.card.chart-full[data-hal-widget-key="${widgetKey}"]`,
    ];
    for (const selector of selectors) {
      const node = root.querySelector(selector);
      if (node) return node;
    }
    const fallback = root.querySelector(`[data-hal-widget-key="${widgetKey}"]`);
    if (
      fallback &&
      !fallback.matches(".kpi-tile,.kpi-card,.stat-item,.stat-box,.kpi-ribbon-tile,[data-hal-kpi-ref]")
    ) {
      return fallback;
    }
    return null;
  }

  function chartOverlayHost(root, widgetKey) {
    if (!root || !widgetKey) return null;
    const panel = resolveWidgetMount(root, widgetKey);
    if (!panel) return null;
    const body = panel.querySelector(".widget-body") || panel.querySelector(".card") || panel;
    if (
      body.querySelector(
        ".chart-container svg, .chart-container canvas, .sparkline-svg, .stat-grid, .data-table, .compare-mode-grid, .kpi-ribbon, .goal-scorecard",
      )
    ) {
      return null;
    }
    let container = body.querySelector(".chart-container[data-nr2-chart-host], .chart-container:empty");
    if (!container) {
      const hostAttr = panel.querySelector(`[data-nr2-chart-host="${widgetKey}"]`);
      if (hostAttr && !hostAttr.querySelector(".widget-body")) {
        container = hostAttr;
      }
    }
    if (!container) return null;
    container.classList.add("chart-mount", "chart-mount--canvas");
    container.replaceChildren();
    const host = document.createElement("div");
    host.className = "nr2-chart-mount";
    host.dataset.nr2ChartWidget = widgetKey;
    container.appendChild(host);
    return host;
  }

  function wrapEnhancementPanel(html) {
    return `<section class="widget-card col-12 nr2-panel-host">${html}</section>`;
  }

  async function mountPostingKanban(pageId, root) {
    if (pageId !== "documents" || !root || typeof NR2Charts === "undefined" || !NR2Charts.renderPostingKanban) return;
    const widgetKey = "periodCloseAndPosting";
    const host = chartOverlayHost(root, widgetKey);
    if (!host) return;
    const kanban = document.createElement("div");
    kanban.id = `nr2-posting-kanban-${pageId}`;
    host.appendChild(kanban);
    let posting = { items: [] };
    let ocr = { items: [] };
    try {
      posting = await fetchJson("/api/posting-queue?limit=50");
      ocr = await fetchJson("/api/ocr-exceptions?status=pending");
    } catch {
      /* optional */
    }
    NR2Charts.renderPostingKanban(kanban.id, mapKanbanColumns(posting.items, ocr.items));
  }

  function chartsEngine() {
    if (typeof window !== "undefined" && window.NR2Charts) return window.NR2Charts;
    return null;
  }

  function mountCanvasChart(root, widgetKey, renderFn) {
    const engine = chartsEngine();
    const host = engine && engine.overlayHost ? engine.overlayHost(root, widgetKey) : chartOverlayHost(root, widgetKey);
    if (!host) return null;
    if (engine && typeof engine.mount === "function") return engine.mount(host, renderFn);
    host.innerHTML = "";
    if (typeof renderFn === "function") renderFn(host);
    return host;
  }

  async function enhanceCanvasCharts(pageId, root) {
    if (!root) return;
    if (root.querySelector('[data-nr2-layout="moonshot-layout"]')) return;
    const charts = chartsEngine();
    if (!charts) return;
    if (pageId === "financial") {
      mountCanvasChart(root, "financialProductionTrend", (host) => {
        const canvas = document.createElement("canvas");
        canvas.id = "nr2-practice-pulse-canvas";
        canvas.width = 340;
        canvas.height = 120;
        host.appendChild(canvas);
        if (typeof charts.renderPracticePulse === "function") {
          fetchJson("/api/financial-reports")
            .then((reports) => {
              const ar = (reports && reports.arAging) || {};
              charts.renderPracticePulse("nr2-practice-pulse-canvas", {
                productionUsd: reports.productionUsd || ar.totalOutstanding,
                collectionsUsd: reports.collectionsUsd || 0,
                arTotalUsd: ar.totalOutstanding || 0,
              });
            })
            .catch(() => {});
        }
      });
    }
    if (pageId === "ar") {
      mountCanvasChart(root, "arAgingAndCollections", (host) => {
        const canvas = document.createElement("canvas");
        canvas.id = "nr2-ar-heatmap-canvas";
        canvas.width = 340;
        canvas.height = 120;
        host.appendChild(canvas);
        if (typeof charts.renderARHeatmap === "function") {
          fetchJson("/api/financial-reports")
            .then((reports) => {
              let buckets = (reports && reports.arAgingBuckets) || [];
              if (!buckets.length) {
                buckets = [
                  { bucket: "0-30", amount: 0 },
                  { bucket: "31-60", amount: 0 },
                  { bucket: "61-90", amount: 0 },
                  { bucket: "90+", amount: 0 },
                ];
              }
              charts.renderARHeatmap("nr2-ar-heatmap-canvas", buckets);
            })
            .catch(() => {});
        }
      });
    }
    if (pageId === "quickbooks") {
      mountCanvasChart(root, "quickbooksProfitLossDetail", (host) => {
        const canvas = document.createElement("canvas");
        canvas.id = "nr2-import-timeline-qb";
        canvas.width = 340;
        canvas.height = 100;
        host.appendChild(canvas);
        if (typeof charts.renderImportTimeline === "function") {
          fetchJson("/api/v1/import-readiness")
            .then((readiness) => {
              let sources = readiness && readiness.sources;
              if (!sources) {
                const cached =
                  typeof DesktopBridge !== "undefined" && DesktopBridge.getCachedImportReadiness
                    ? DesktopBridge.getCachedImportReadiness()
                    : null;
                sources = (cached && cached.sources) || [
                  { id: "quickbooks", name: "QuickBooks", lastSyncAt: cached && cached.loadedAt, level: cached && cached.level },
                ];
              }
              charts.renderImportTimeline("nr2-import-timeline-qb", sources);
            })
            .catch(() => {});
        }
      });
    }
    if (pageId === "softdent") {
      mountCanvasChart(root, "softdentArAging", (host) => {
        const canvas = document.createElement("canvas");
        canvas.id = "nr2-softdent-ar-heatmap";
        canvas.width = 340;
        canvas.height = 120;
        host.appendChild(canvas);
        if (typeof charts.renderARHeatmap === "function") {
          fetchJson("/api/financial-reports")
            .then((reports) => {
              let buckets = (reports && reports.arAgingBuckets) || [];
              if (!buckets.length) {
                buckets = [
                  { bucket: "0-30", amount: 0 },
                  { bucket: "31-60", amount: 0 },
                  { bucket: "61-90", amount: 0 },
                  { bucket: "90+", amount: 0 },
                ];
              }
              charts.renderARHeatmap("nr2-softdent-ar-heatmap", buckets);
            })
            .catch(() => {});
        }
      });
    }
    if (pageId === "documents") {
      await mountPostingKanban(pageId, root);
    }
    if (pageId === "taxes") {
      mountCanvasChart(root, "taxFederalStateSplit", (host) => {
        const canvas = document.createElement("canvas");
        canvas.id = "nr2-tax-import-timeline";
        canvas.width = 340;
        canvas.height = 90;
        host.appendChild(canvas);
        if (typeof charts.renderImportTimeline === "function") {
          fetchJson("/api/v1/import-readiness")
            .then((readiness) => {
              let sources = readiness && readiness.sources;
              if (!sources) {
                sources = [
                  { id: "quickbooks", name: "QuickBooks", level: "unknown" },
                  { id: "softdent", name: "SoftDent", level: "unknown" },
                ];
              }
              charts.renderImportTimeline("nr2-tax-import-timeline", sources);
            })
            .catch(() => {});
        }
      });
    }
    if (pageId === "office-manager") {
      mountCanvasChart(root, "officeManagerPriorities", (host) => {
        const canvas = document.createElement("canvas");
        canvas.id = "nr2-office-import-timeline";
        canvas.width = 340;
        canvas.height = 90;
        host.appendChild(canvas);
        if (typeof charts.renderImportTimeline === "function") {
          fetchJson("/api/import-readiness")
            .then((readiness) => {
              let sources = readiness && readiness.sources;
              if (!sources) {
                sources = [{ id: "bundle", name: "Import bundle", level: (readiness && readiness.level) || "unknown" }];
              }
              charts.renderImportTimeline("nr2-office-import-timeline", sources);
            })
            .catch(() => {});
        }
      });
    }
  }

  async function enhanceCanvasPanels(pageId, root) {
    if (!root) return;
    const panelHost = root.querySelector(".widget-grid") || root.querySelector(".stack") || root;
    if (!panelHost || panelHost.dataset.nr2MoonshotPanels === "1") return;
    panelHost.dataset.nr2MoonshotPanels = "1";
    const host = document.createElement("div");
    host.className = "widget-card col-12 nr2-panel-host";
    panelHost.appendChild(host);
    if (pageId === "financial" || pageId === "office-manager") await renderAuditDashboard(host);
    if (pageId === "claims" || pageId === "financial") await renderClinicalBridge(host);
    if (pageId === "claims" || pageId === "financial") await renderEraMatchPanel(host);
    if (pageId === "taxes" && !root.querySelector('[data-hal-widget-key="periodCloseAndPosting"]')) {
      renderCloseWizard(host);
    }
  }

  async function renderCharts(pageId, container) {
    if (!container || typeof NR2Charts === "undefined") return;
    if (pageId === "financial" || pageId === "ar") {
      const pulse = document.createElement("canvas");
      pulse.id = "nr2-practice-pulse";
      pulse.width = 360;
      pulse.height = 140;
      container.appendChild(pulse);
      const waterfall = document.createElement("canvas");
      waterfall.id = "nr2-ar-waterfall";
      waterfall.width = 360;
      waterfall.height = 120;
      container.appendChild(waterfall);
      let reports = {};
      try {
        reports = await fetchJson("/api/financial-reports");
      } catch {
        reports = {};
      }
      const ar = reports.arAging || {};
      const metrics = {
        productionUsd: reports.productionUsd || ar.totalOutstanding,
        collectionsUsd: reports.collectionsUsd || 0,
        arTotalUsd: ar.totalOutstanding || 0,
      };
      if (typeof NR2Charts !== "undefined" && NR2Charts.renderPracticePulse) {
        NR2Charts.renderPracticePulse("nr2-practice-pulse", metrics);
      }
      const heat = document.createElement("canvas");
      heat.id = "nr2-ar-heatmap";
      heat.width = 360;
      heat.height = 140;
      container.appendChild(heat);
      let buckets = [];
      try {
        const reports = await fetchJson("/api/financial-reports");
        buckets = (reports && reports.arAgingBuckets) || [];
      } catch {
        buckets = [];
      }
      if (!buckets.length) {
        buckets = [
          { bucket: "0-30", amount: 0 },
          { bucket: "31-60", amount: 0 },
          { bucket: "61-90", amount: 0 },
          { bucket: "90+", amount: 0 },
        ];
      }
      NR2Charts.renderARHeatmap("nr2-ar-heatmap", buckets);
      if (typeof NR2Charts.renderArWaterfall === "function") {
        NR2Charts.renderArWaterfall("nr2-ar-waterfall", buckets);
      }
    }
    if (pageId === "financial" || pageId === "quickbooks") {
      const timeline = document.createElement("canvas");
      timeline.id = "nr2-import-timeline";
      timeline.width = 360;
      timeline.height = 120;
      container.appendChild(timeline);
      let sources = null;
      try {
        const readiness = await fetchJson("/api/v1/import-readiness");
        sources = readiness && readiness.sources;
      } catch {
        sources = null;
      }
      if (!sources) {
        const cached =
          typeof DesktopBridge !== "undefined" && DesktopBridge.getCachedImportReadiness
            ? DesktopBridge.getCachedImportReadiness()
            : null;
        sources = (cached && cached.sources) || [
          { id: "bundle", name: "Import bundle", lastSyncAt: cached && cached.loadedAt, level: cached && cached.level },
        ];
      }
      NR2Charts.renderImportTimeline("nr2-import-timeline", sources);
    }
    if (pageId === "documents") {
      await mountPostingKanban(pageId, root);
    }
  }

  async function enhancePage(pageId, root) {
    if (!root) return;
    if (
      pageId !== "hal" &&
      typeof PageSchema !== "undefined" &&
      typeof PageSchema.isStaffPage === "function" &&
      PageSchema.isStaffPage(pageId)
    ) {
      return;
    }
    if (root.querySelector(".ms-mockup-preview-gate, .ms-mockup-preview-frame")) return;
    const isCanvas = typeof PageCanvas !== "undefined" && PageCanvas.hasPage && PageCanvas.hasPage(pageId);
    if (isCanvas) {
      await enhanceCanvasCharts(pageId, root);
      return;
    }
    const panelHost = root.querySelector(".ms-page-body") || root;
    if (!panelHost || panelHost.dataset.nr2MoonshotEnhanced) return;
    panelHost.dataset.nr2MoonshotEnhanced = "1";
    await renderCharts(pageId, panelHost);
    if (pageId === "documents") await renderOcrExceptions(panelHost);
    if (pageId === "financial" || pageId === "settings") await renderAuditDashboard(panelHost);
    if (pageId === "claims" || pageId === "financial") await renderClinicalBridge(panelHost);
    if (pageId === "claims" || pageId === "financial") await renderEraMatchPanel(panelHost);
    if (pageId === "financial" || pageId === "taxes") renderCloseWizard(panelHost);
  }

  function mountChart(host, renderFn) {
    if (!host) return null;
    host.classList.add("chart-mount");
    host.innerHTML = "";
    if (typeof renderFn === "function") renderFn(host);
    return host;
  }

  const chartMountPolicy = {
    mount: mountChart,
    overlayHost: chartOverlayHost,
    policy: "replace-not-stack",
  };

  return {
    enhancePage,
    enhanceCanvasCharts,
    enhanceCanvasPanels,
    renderEraMatchCard,
    renderEraMatchPanel,
    renderPilotPhaseBanner,
    installPilotBanner,
    mountChart,
    mountCanvasChart,
    resolveWidgetMount,
    chartMountPolicy,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = NR2MoonshotUI;
}
if (typeof window !== "undefined" && typeof document !== "undefined") {
  window.NR2MoonshotUI = NR2MoonshotUI;
  window.NR2Charts = Object.assign({}, window.NR2Charts || {}, NR2MoonshotUI.chartMountPolicy);
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => NR2MoonshotUI.installPilotBanner());
  } else {
    NR2MoonshotUI.installPilotBanner();
  }
}

// nr2-moonshot-ui.js — Chart lifecycle (replace-not-stack)

window.NR2UI = window.NR2UI || {};

(function (NS) {
  const _charts = new WeakMap(); // canvas -> Chart instance

  /**
   * Mount a Chart.js instance on a <canvas>.
   * Replace-not-stack: destroys any existing chart on the exact canvas first.
   */
  NS.mountChart = function (canvas, type = 'bar', data = {}, options = {}) {
    if (!canvas || !(canvas instanceof HTMLCanvasElement)) {
      console.warn('[NR2UI] mountChart requires a <canvas> element');
      return null;
    }

    // Clear Chart.js global registry
    if (window.Chart && Chart.getChart) {
      const existing = Chart.getChart(canvas);
      if (existing) existing.destroy();
    }

    // Clear local WeakMap
    if (_charts.has(canvas)) {
      _charts.get(canvas).destroy();
      _charts.delete(canvas);
    }

    const ctx = canvas.getContext('2d');
    const chart = new Chart(ctx, {
      type,
      data: data.labels ? data : { labels: [], datasets: [] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom' } },
        ...options,
      },
    });

    _charts.set(canvas, chart);
    return chart;
  };

  /**
   * enhancePage — idempotent scan for chart placeholders.
   */
  NS.resolveChartPayload = function (widgetKey) {
    const D = typeof PageCanvasData !== "undefined" ? PageCanvasData : null;
    if (!D || !widgetKey) return null;
    if (widgetKey.startsWith("ar.chart")) {
      const aging = D.softdentAgingBars ? D.softdentAgingBars() : null;
      if (aging && aging.labels && aging.values) {
        return { labels: aging.labels, datasets: [{ label: "AR", data: aging.values }] };
      }
    }
    if (widgetKey.startsWith("claims.chart")) {
      const lanes = D.claimsKanban ? D.claimsKanban() : [];
      const counts = lanes.map((lane) => (Array.isArray(lane && lane.items) ? lane.items.length : 0));
      if (counts.some((n) => n > 0)) {
        return {
          labels: lanes.map((l) => (l && (l.lane || l.title)) || "Lane"),
          datasets: [{ label: "Claims", data: counts }],
        };
      }
    }
    if (/quickbooks|financial/i.test(widgetKey)) {
      const pl = D.quickbooksPlTrend ? D.quickbooksPlTrend() : null;
      if (pl && pl.labels && pl.series && pl.series[0]) {
        return { labels: pl.labels, datasets: [{ label: pl.series[0].label || "Trend", data: pl.series[0].values || pl.series[0].data }] };
      }
      const exp = D.quickbooksExpenseBars ? D.quickbooksExpenseBars() : null;
      if (exp && exp.labels && exp.values) {
        return { labels: exp.labels, datasets: [{ label: "Expenses", data: exp.values }] };
      }
    }
    return null;
  };

  NS.enhancePage = function () {
    if (!window.Chart) {
      console.warn('[NR2UI] Chart.js not loaded');
      return;
    }

    document.querySelectorAll('.chart-container[data-chart-type]').forEach((container) => {
      let canvas = container.querySelector('canvas');
      if (!canvas) {
        canvas = document.createElement('canvas');
        container.innerHTML = '';
        container.appendChild(canvas);
      }

      // Skip if already mounted
      if (Chart.getChart && Chart.getChart(canvas)) return;

      const type = container.dataset.chartType || 'bar';
      const widgetKey = container.dataset.widget;
      const payload =
        NS.resolveChartPayload(widgetKey) ||
        (window.NR2Data && window.NR2Data[widgetKey]) ||
        { labels: ['A', 'B', 'C'], datasets: [{ label: 'Dataset', data: [3, 1, 4] }] };

      NS.mountChart(canvas, type, payload);
    });
  };
})(window.NR2UI);
