/**
 * NewRidgeFinancial 2.0 — staff page mount layer.
 * Body content from PageCanvas mock preview gate only (no layout wiring, no chart overlays).
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
    const pageClass = state && state.pageId === "hal" ? "ms-page ms-page--hal" : "ms-page";
    return `<article class="${pageClass}" data-ms-page="${esc(state.pageId)}">${body}</article>`;
  }

  function pageChrome(state, bodyHtml, chromeOpts) {
    const MC = typeof MoonshotMockupChrome !== "undefined" ? MoonshotMockupChrome : null;
    if (!MC || typeof MC.pageContent !== "function") {
      return U
        ? U.ErrorState({
            title: "Page shell not loaded",
            message: "nr2-moonshot-mockup-chrome.js must load before page-views.js. Run StartProgram.bat and reload http://127.0.0.1:8765/.",
          })
        : bodyHtml || "";
    }
    return MC.pageContent(state, bodyHtml, chromeOpts);
  }

  function wireCommon(container, onNavigate) {
    if (!container) return;
    container.querySelectorAll("[data-ms-nav]").forEach((btn) => {
      btn.addEventListener("click", () => onNavigate && onNavigate(btn.getAttribute("data-ms-nav")));
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
          event.stopPropagation();
          const panel = narrativeSave.closest("[data-narrative-draft-panel], .composer-grid, .ms-page") || narrativeSave.closest("[data-hal-widget-key]");
          const editor = panel && panel.querySelector("[data-narrative-body]");
          const textarea = editor || (panel && panel.querySelector("textarea.composer-textarea"));
          const text = textarea ? textarea.value : "";
          const controls = panel && panel.querySelector("[data-narrative-draft-panel]");
          const focusSel = controls && controls.querySelector('[data-narrative-field="focus"]');
          const toneSel = controls && controls.querySelector('[data-narrative-field="tone"]');
          const lengthSel = controls && controls.querySelector('[data-narrative-field="length"]');
          const focus = focusSel ? focusSel.value : "Medical Necessity";
          const tone = toneSel ? toneSel.value : "Professional";
          const length = lengthSel ? lengthSel.value : "Standard";
          const claimWrap = panel && panel.querySelector("[data-narrative-claim-id]");
          const claimId = claimWrap ? claimWrap.getAttribute("data-narrative-claim-id") : "";
          const D = typeof PageCanvasData !== "undefined" ? PageCanvasData : null;
          const claim =
            D && D.allClaims && claimId
              ? D.allClaims().find((c) => String(c.id) === claimId) || D.firstClaim()
              : D && D.firstClaim
                ? D.firstClaim()
                : null;
          if (typeof Services !== "undefined" && Services.narratives && typeof Services.narratives.saveDraft === "function") {
            try {
              await Services.narratives.saveDraft({
                text,
                focus,
                tone,
                length,
                claim,
                claimId: claim && claim.id,
                snapshot: typeof window !== "undefined" ? window.__nr2ProgramSnapshot : null,
              });
              if (typeof window !== "undefined") {
                window.dispatchEvent(new CustomEvent("nr2:page-refresh-requested"));
                window.dispatchEvent(new CustomEvent("nr2:narratives-updated"));
              }
            } catch (err) {
              if (typeof window !== "undefined") {
                window.alert(err && err.message ? err.message : "Narrative save blocked by review rules.");
              }
            }
          }
          return;
        }
        const narrativeGenerate = event.target.closest("[data-narrative-generate]");
        if (narrativeGenerate) {
          event.preventDefault();
          event.stopPropagation();
          const panel = narrativeGenerate.closest("[data-narrative-draft-panel], .composer-grid, .ms-page");
          const controls = panel && panel.querySelector("[data-narrative-draft-panel]");
          const focusSel = controls && controls.querySelector('[data-narrative-field="focus"]');
          const toneSel = controls && controls.querySelector('[data-narrative-field="tone"]');
          const lengthSel = controls && controls.querySelector('[data-narrative-field="length"]');
          const focus = focusSel ? focusSel.value : "Medical Necessity";
          const tone = toneSel ? toneSel.value : "Professional";
          const length = lengthSel ? lengthSel.value : "Standard";
          const claimWrap = panel && panel.querySelector("[data-narrative-claim-id]");
          const claimId = claimWrap ? claimWrap.getAttribute("data-narrative-claim-id") : "";
          const D = typeof PageCanvasData !== "undefined" ? PageCanvasData : null;
          const claim =
            D && D.allClaims && claimId
              ? D.allClaims().find((c) => String(c.id) === claimId) || D.firstClaim()
              : D && D.firstClaim
                ? D.firstClaim()
                : null;
          if (typeof Services !== "undefined" && Services.narratives && typeof Services.narratives.generate === "function") {
            const snap =
              (typeof window !== "undefined" && window.__nr2ProgramSnapshot) ||
              (typeof SnapshotStore !== "undefined" && SnapshotStore.get ? SnapshotStore.get() : null);
            const result = await Services.narratives.generate({ claim, snapshot: snap, focus, tone, length });
            const textarea = panel && panel.querySelector("[data-narrative-body], textarea.composer-textarea");
            if (textarea && result && result.text) textarea.value = result.text;
            if (result && result.blocked && typeof window !== "undefined") {
              window.alert(`Draft prepared with gaps: ${(result.missingFields || []).join(", ") || "review required"}`);
            }
            if (typeof window !== "undefined") {
              window.dispatchEvent(new CustomEvent("nr2:narratives-updated"));
              window.dispatchEvent(new CustomEvent("nr2:page-refresh-requested"));
            }
          }
          return;
        }
        const narrativeDraftBtn = event.target.closest("[data-narrative-draft]");
        if (narrativeDraftBtn) {
          event.preventDefault();
          event.stopPropagation();
          const claimId = narrativeDraftBtn.getAttribute("data-narrative-draft");
          const D = typeof PageCanvasData !== "undefined" ? PageCanvasData : null;
          if (D && typeof D.setSelectedClaimId === "function") D.setSelectedClaimId(claimId);
          if (typeof onNavigate === "function") onNavigate("claims");
          else if (typeof window !== "undefined") {
            window.dispatchEvent(new CustomEvent("nr2:page-refresh-requested"));
          }
          return;
        }
        const narrativeClose = event.target.closest("[data-narrative-draft-close]");
        if (narrativeClose) {
          event.preventDefault();
          const panel = narrativeClose.closest(".narrative-draft-panel, [data-narrative-draft-panel]");
          const textarea = panel && panel.querySelector("textarea");
          if (textarea) textarea.value = "";
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

  function staffMockEmbedMode() {
    return (
      (typeof window !== "undefined" && window.NR2_STAFF_MOCK_ONLY) ||
      (typeof document !== "undefined" &&
        document.documentElement.getAttribute("data-nr2-staff-render") === "mock-embed")
    );
  }

  function stripMockEmbedLiveChrome(container) {
    if (!staffMockEmbedMode() || !container) return;
    container
      .querySelectorAll(
        ".page-header-tools, .sync-badge, .storyboard-export-btn, .cpa-export-btn, .ms-import-notice, .ms-mockup-preview-banner, .filter-bar, .hal-insight, .hero, .top-header, .alert-strip, .ms-hal-readiness-strip, #nr2-hal-readiness, .ms-hal-strip",
      )
      .forEach((el) => el.remove());
  }

  function wireMockupPreviewFrames(container) {
    if (!container) return;
    const mockOnly =
      (typeof window !== "undefined" && window.NR2_STAFF_MOCK_ONLY) ||
      (typeof document !== "undefined" &&
        document.documentElement.getAttribute("data-nr2-staff-render") === "mock-embed");
    if (!mockOnly) return;
    container.querySelectorAll(".ms-mockup-preview-iframe").forEach((iframe) => {
      iframe.loading = "eager";
      const resize = () => {
        try {
          const doc = iframe.contentDocument;
          if (doc && doc.body) {
            iframe.style.height = `${Math.max(680, doc.body.scrollHeight + 32)}px`;
          }
        } catch (_err) {
          /* cross-origin guard */
        }
      };
      iframe.addEventListener("load", resize);
      if (iframe.contentDocument && iframe.contentDocument.readyState === "complete") resize();
    });
  }

  function chromeOptsFromState(state) {
    if (staffMockEmbedMode()) return null;
    const snap = state && state.programSnapshot;
    const opts = {};
    const bundle = snap && snap.importBundle;
    let syncStatus = (bundle && bundle.syncStatus) || null;
    const db = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
    if (db && typeof db.getCachedImportReadiness === "function") {
      const readiness = db.getCachedImportReadiness();
      if (readiness && readiness.level) syncStatus = readiness;
    }
    opts.importReadiness = syncStatus;
    if (typeof PageSchema !== "undefined" && PageSchema.LAYOUT_EPOCH === "moonshot-mockup") {
      return opts;
    }
    const fin = snap && snap.dashboards && snap.dashboards.financial;
    if (fin && fin.dateRange) {
      opts.periodLabel = fin.dateRange;
      opts.reportRange = fin.footer && fin.footer.refreshed ? `Refreshed ${fin.footer.refreshed}` : snap.label || "";
    } else {
      const sd = snap && snap.dashboards && snap.dashboards.softdent;
      if (sd && sd.date) {
        opts.periodLabel = sd.date;
        opts.reportRange = sd.source || "";
      } else if (snap && snap.label) {
        opts.periodLabel = snap.label;
        opts.reportRange = "";
      }
    }
    const IL = typeof ImportLoader !== "undefined" ? ImportLoader : null;
    if (IL && typeof IL.buildImportFreshnessBanner === "function" && state && state.pageId) {
      opts.importFreshnessHtml = IL.buildImportFreshnessBanner(bundle, syncStatus, state.pageId);
    }
    return Object.keys(opts).length ? opts : null;
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

    const workstationOnly =
      typeof window !== "undefined" && !!window.NR2_WORKSTATION_ONLY;

    // PERMANENT: Legacy path killed. Absence of Moonshot deps is fatal (financial app only).
    if (!workstationOnly) {
      if (!window.PageSchema || window.PageSchema.LAYOUT_EPOCH !== "moonshot-mockup") {
        container.innerHTML =
          '<div style="background:#900;color:#fff;padding:2rem;font-family:sans-serif;">[NR2] FATAL: Moonshot PageSchema required. Purging cache…</div>';
        if (window.emergencyPurgeAndReload) window.emergencyPurgeAndReload("MISSING_MOONSHOT_SCHEMA");
        return;
      }
      if (!window.PageCanvas || typeof window.PageCanvas.renderBody !== "function") {
        container.innerHTML =
          '<div style="background:#900;color:#fff;padding:2rem;font-family:sans-serif;">[NR2] FATAL: PageCanvas missing. Legacy renderer disabled.</div>';
        return;
      }
    }

    const state = buildPageState(halData, pageId, halWidgetFeed, programSnapshot);
    const Canvas = PageCanvas;

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
      pageChrome(state, '<div id="page-canvas"></div>', chromeOptsFromState(state)),
    );
    document.body.setAttribute("data-nr2-layout", "moonshot-mockup-grid");
    wireCommon(container, onNavigate);
    if (!staffMockEmbedMode() && typeof NR2PageFilters !== "undefined" && NR2PageFilters.mountPageFilters) {
      NR2PageFilters.mountPageFilters(container, pageId, { snapshot: programSnapshot });
    }
    const canvas = container.querySelector("#page-canvas");
    if (canvas && Canvas.renderBody) {
      if (typeof Canvas.setFeed === "function") {
        Canvas.setFeed(halWidgetFeed, programSnapshot);
      }
      canvas.innerHTML = Canvas.renderBody(pageId, halWidgetFeed, programSnapshot);
    }
    wireMockupPreviewFrames(container);
    stripMockEmbedLiveChrome(container);
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
      pageChrome(
        state,
        Canvas.renderBody(pageId, halWidgetFeed, programSnapshot),
        chromeOptsFromState(state),
      ),
    );
  }

  function hasPage(pageId) {
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
