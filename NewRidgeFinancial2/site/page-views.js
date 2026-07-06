/**
 * NewRidgeFinancial 2.0 — staff page mount layer.
 * Body content from PageCanvas; chrome from PageChrome + PageSchema; HAL from halWidgetFeed.
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

  const U = resolveUI();

  function esc(v) {
    return U ? U.esc(v) : String(v == null ? "" : v);
  }

  function buildPageState(halData, pageId, halWidgetFeed, programSnapshot) {
    const schema = typeof PageSchema !== "undefined" ? PageSchema.byId(pageId) : null;
    const reg = ((halData && halData.registry) || []).find((e) => e.id === pageId) || null;
    return {
      pageId,
      halData: halData || null,
      halWidgetFeed: halWidgetFeed || null,
      programSnapshot: programSnapshot || null,
      title: (schema && schema.title) || (reg && reg.name) || pageId,
      eyebrow: (schema && schema.label) || "Program page",
      subtitle: (schema && schema.subtitle) || (reg && reg.purpose) || "",
      accent: (schema && schema.accent) || "gold",
      safety: (schema && schema.safety) || (reg && reg.safety) || "Read-only · HAL reads source data only",
      registryState: (reg && reg.state) || "unknown",
    };
  }

  function pageShell(state, body) {
    return `<article class="pv pv--${esc(state.pageId)} pv--app pv--canvas" data-pv-page="${esc(state.pageId)}">${body}</article>`;
  }

  function pageChrome(state, bodyHtml, chromeOpts) {
    const PC = typeof PageChrome !== "undefined" ? PageChrome : null;
    if (!PC) {
      return U
        ? U.ErrorState({
            title: "Design schema not loaded",
            message: "page-chrome.js must load before page-views.js. Restart the desktop app.",
          })
        : bodyHtml || "";
    }
    return PC.pageContent(state, bodyHtml, chromeOpts);
  }

  function wireCommon(container, onNavigate) {
    if (!container) return;
    container.querySelectorAll("[data-pv-nav]").forEach((btn) => {
      btn.addEventListener("click", () => onNavigate && onNavigate(btn.getAttribute("data-pv-nav")));
    });
    if (!container.dataset.nr2WiredExport) {
      container.dataset.nr2WiredExport = "1";
      container.addEventListener("click", async (event) => {
        const reconBtn = event.target.closest("[data-recon-export]");
        if (reconBtn) {
          event.preventDefault();
          const D = typeof PageCanvasData !== "undefined" ? PageCanvasData : null;
          const payload = D && D.monthEndReconciliationPayload ? D.monthEndReconciliationPayload() : null;
          if (!payload) return;
          const MEC = typeof MonthEndClose !== "undefined" ? MonthEndClose : null;
          const EU = typeof ExportUtils !== "undefined" ? ExportUtils : null;
          if (!MEC || !EU) return;
          const mode = reconBtn.getAttribute("data-recon-export");
          if (mode === "csv") {
            EU.exportText(`reconciliation-${payload.period || "period"}.csv`, MEC.formatReconciliationCsv(payload));
          } else {
            EU.exportText(`reconciliation-${payload.period || "period"}.txt`, MEC.formatReconciliationExport(payload));
          }
          return;
        }
        const copyBtn = event.target.closest("[data-recon-copy]");
        if (copyBtn) {
          event.preventDefault();
          const D = typeof PageCanvasData !== "undefined" ? PageCanvasData : null;
          const payload = D && D.monthEndReconciliationPayload ? D.monthEndReconciliationPayload() : null;
          const MEC = typeof MonthEndClose !== "undefined" ? MonthEndClose : null;
          if (!payload || !MEC || !MEC.formatReconciliationExport) return;
          const text = MEC.formatReconciliationExport(payload);
          if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(text);
          }
          return;
        }
        const journalBtn = event.target.closest("[data-journal-review]");
        if (journalBtn) {
          event.preventDefault();
          const db = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
          if (!db || typeof db.reviewPostingQueueEntry !== "function") return;
          const entryId = journalBtn.getAttribute("data-journal-review");
          const uiAction = journalBtn.getAttribute("data-journal-action") || "approve";
          const action = uiAction === "reject" ? "rejected" : "approved";
          await db.reviewPostingQueueEntry(entryId, action, "local-user", "");
          if (typeof window !== "undefined") {
            window.dispatchEvent(new CustomEvent("nr2:journal-queue-updated"));
          }
          if (typeof onNavigate === "function") onNavigate("documents");
          return;
        }
        const journalBulk = event.target.closest("[data-journal-approve-all]");
        if (journalBulk) {
          event.preventDefault();
          const db = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
          if (!db || typeof db.bulkReviewPostingQueue !== "function") return;
          await db.bulkReviewPostingQueue(
            "approved",
            "local-user",
            "Bulk approved from Accounting Documents (local review only).",
          );
          if (typeof window !== "undefined") {
            window.dispatchEvent(new CustomEvent("nr2:journal-queue-updated"));
          }
          if (typeof onNavigate === "function") onNavigate("documents");
          return;
        }
        const journalExport = event.target.closest("[data-journal-export]");
        if (journalExport) {
          event.preventDefault();
          const db = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
          if (db && typeof db.exportApprovedPostingQueue === "function") {
            await db.exportApprovedPostingQueue();
          }
          return;
        }
        const opsRefresh = event.target.closest("[data-ops-refresh-health]");
        if (opsRefresh) {
          event.preventDefault();
          const coord = typeof ImportCoordinator !== "undefined" ? ImportCoordinator : null;
          if (coord && typeof coord.refresh === "function") {
            await coord.refresh({ reason: "ops-health-panel" });
          } else if (typeof Services !== "undefined" && typeof Services.refreshImports === "function") {
            await Services.refreshImports({ reason: "ops-health-panel", waitForCompletion: true });
          }
          await refreshLiveIntegrationHealth();
          if (typeof window !== "undefined") {
            window.dispatchEvent(new CustomEvent("nr2:page-refresh-requested"));
          }
          return;
        }
        const opsBundle = event.target.closest("[data-ops-support-bundle]");
        if (opsBundle) {
          event.preventDefault();
          const db = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
          if (db && typeof db.buildSupportBundle === "function") {
            await db.buildSupportBundle("Office Manager support bundle");
          } else if (typeof PortalOps !== "undefined" && typeof PortalOps.buildSupportBundle === "function") {
            await PortalOps.buildSupportBundle({ note: "Office Manager support bundle" });
          }
          return;
        }
        const librarySearch = event.target.closest("[data-hal-library-search]");
        if (librarySearch) {
          event.preventDefault();
          const wrap = librarySearch.closest("[data-hal-widget-key]");
          const input = wrap && wrap.querySelector("[data-hal-library-query]");
          const q = input && input.value ? String(input.value).trim() : "";
          if (q && typeof window.runHalPageCmd === "function") {
            await window.runHalPageCmd(`Search library for ${q}`);
          }
          return;
        }
        const narrativeSave = event.target.closest("[data-narrative-save]");
        if (narrativeSave) {
          event.preventDefault();
          const editor = narrativeSave.closest("[data-hal-widget-key]");
          const textarea = editor && editor.querySelector("[data-narrative-body]");
          const text = textarea ? textarea.value : "";
          if (typeof Services !== "undefined" && Services.narratives && typeof Services.narratives.saveDraft === "function") {
            await Services.narratives.saveDraft({ text, focus: "Medical Necessity", length: "Standard" });
            if (typeof window !== "undefined") {
              window.dispatchEvent(new CustomEvent("nr2:page-refresh-requested"));
              window.dispatchEvent(new CustomEvent("nr2:narratives-updated"));
            }
          }
          return;
        }
      });
    }
    container.addEventListener("keydown", async (event) => {
      if (event.key !== "Enter") return;
      const input = event.target.closest("[data-hal-library-query]");
      if (!input) return;
      event.preventDefault();
      const q = String(input.value || "").trim();
      if (!q || typeof window.runHalPageCmd !== "function") return;
      await window.runHalPageCmd(`Search library for ${q}`);
    });
    const pilot =
      typeof HalPilotWidgets !== "undefined"
        ? HalPilotWidgets
        : typeof window !== "undefined"
          ? window.HalPilotWidgets
          : null;
    if (pilot && typeof pilot.init === "function") pilot.init(container);
  }

  function chromeOptsFromState(state) {
    const snap = state && state.programSnapshot;
    const fin = snap && snap.dashboards && snap.dashboards.financial;
    if (fin && fin.dateRange) {
      return {
        periodLabel: fin.dateRange,
        reportRange: fin.footer && fin.footer.refreshed ? `Refreshed ${fin.footer.refreshed}` : snap.label || "",
      };
    }
    const sd = snap && snap.dashboards && snap.dashboards.softdent;
    if (sd && sd.date) {
      return { periodLabel: sd.date, reportRange: sd.source || "" };
    }
    return snap && snap.label ? { periodLabel: snap.label, reportRange: "" } : null;
  }

  async function refreshLiveIntegrationHealth() {
    const Ops = typeof PortalOps !== "undefined" ? PortalOps : null;
    const Data = typeof PageCanvasData !== "undefined" ? PageCanvasData : null;
    if (!Ops || !Ops.getIntegrationHealth || !Data || !Data.setLiveIntegrationHealth) return null;
    try {
      const health = await Ops.getIntegrationHealth();
      Data.setLiveIntegrationHealth(health);
      return health;
    } catch {
      return null;
    }
  }

  function renderPageView(container, halData, pageId, onNavigate, halWidgetFeed, programSnapshot) {
    if (!container) return;
    const state = buildPageState(halData, pageId, halWidgetFeed, programSnapshot);
    const Canvas = typeof PageCanvas !== "undefined" ? PageCanvas : null;

    if (!hasPage(pageId) || !Canvas) {
      container.innerHTML = pageShell(
        state,
        pageChrome(
          state,
          U ? U.EmptyState({ title: "Page not configured", message: `No renderer for ${pageId}.` }) : "",
          chromeOptsFromState(state),
        ),
      );
      wireCommon(container, onNavigate);
      return;
    }

    container.innerHTML = pageShell(
      state,
      pageChrome(state, Canvas.renderBody(pageId, halWidgetFeed, programSnapshot), chromeOptsFromState(state)),
    );
    wireCommon(container, onNavigate);
    refreshLiveIntegrationHealth().catch(() => {
      /* integration health optional; skip second full repaint to avoid page flash */
    });
  }

  function previewPageHtml(halData, pageId, halWidgetFeed, programSnapshot) {
    const state = buildPageState(halData, pageId, halWidgetFeed, programSnapshot);
    const Canvas = typeof PageCanvas !== "undefined" ? PageCanvas : null;
    if (!hasPage(pageId) || !Canvas) {
      return pageShell(
        state,
        pageChrome(state, U ? U.EmptyState({ title: "Page not configured", message: pageId }) : "", chromeOptsFromState(state)),
      );
    }
    return pageShell(
      state,
      pageChrome(state, Canvas.renderBody(pageId, halWidgetFeed, programSnapshot), chromeOptsFromState(state)),
    );
  }

  function hasPage(pageId) {
    if (pageId === "hal") return false;
    if (typeof PageSchema !== "undefined" && PageSchema.isStaffPage) {
      return PageSchema.isStaffPage(pageId);
    }
    return typeof PageCanvas !== "undefined" && PageCanvas.hasPage(pageId);
  }

  function setHalFeed(feed, programSnapshot) {
    if (typeof PageCanvas !== "undefined" && PageCanvas.setFeed) PageCanvas.setFeed(feed, programSnapshot);
  }

  return { buildPageState, renderPageView, previewPageHtml, hasPage, setHalFeed, refreshLiveIntegrationHealth };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = PageViews;
}
if (typeof window !== "undefined") {
  window.PageViews = PageViews;
}
