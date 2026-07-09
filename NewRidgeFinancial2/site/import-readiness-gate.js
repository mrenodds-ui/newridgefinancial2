/**
 * Read-path modal interstitial — blocks financial pages when import readiness is not fresh.
 */
const ImportReadinessGate = (function () {
  const FINANCIAL_PAGES = new Set(["financial", "ar", "quickbooks", "claims"]);
  const DISMISS_KEY = "nr2ImportGateDismissed";
  let gateEl = null;

  function isFinancialPage(pageId) {
    return FINANCIAL_PAGES.has(String(pageId || ""));
  }

  function needsGate(readiness) {
    if (!readiness) return true;
    return String(readiness.level || "unknown") !== "fresh";
  }

  function dismissSession() {
    try {
      sessionStorage.setItem(DISMISS_KEY, "1");
    } catch {
      /* storage unavailable */
    }
  }

  function isDismissed() {
    try {
      return sessionStorage.getItem(DISMISS_KEY) === "1";
    } catch {
      return false;
    }
  }

  function clearDismiss() {
    try {
      sessionStorage.removeItem(DISMISS_KEY);
    } catch {
      /* storage unavailable */
    }
  }

  async function fetchReadiness() {
    const db = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
    if (!db) return null;
    if (typeof db.getImportReadiness === "function") return db.getImportReadiness();
    if (typeof db.getCachedImportReadiness === "function") return db.getCachedImportReadiness();
    return null;
  }

  function buildGateHtml(readiness) {
    const level = (readiness && readiness.level) || "unknown";
    const err = (readiness && readiness.error) || "Import data is not current.";
    const loaded = (readiness && readiness.loadedAt) || "unknown";
    return (
      `<div id="nr2-import-readiness-gate" role="alertdialog" aria-modal="true" aria-labelledby="nr2-import-gate-title">` +
      `<div class="nr2-import-gate__card">` +
      `<h2 id="nr2-import-gate-title">Import data not fresh</h2>` +
      `<p><strong>Do not act on financial data.</strong> Status: ${level}. Last load: ${loaded}.</p>` +
      `<p>${err}</p>` +
      `<div class="nr2-import-gate__actions">` +
      `<button type="button" class="nr2-import-gate__btn" data-import-gate-refresh>Refresh imports</button>` +
      `<button type="button" class="nr2-import-gate__btn nr2-import-gate__btn--muted" data-import-gate-dismiss>Dismiss with warning</button>` +
      `</div></div></div>`
    );
  }

  function removeGate() {
    if (gateEl) {
      gateEl.remove();
      gateEl = null;
    }
  }

  function wireGate(container) {
    const refreshBtn = container.querySelector("[data-import-gate-refresh]");
    const dismissBtn = container.querySelector("[data-import-gate-dismiss]");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", async () => {
        refreshBtn.disabled = true;
        try {
          if (typeof Services !== "undefined" && typeof Services.refreshImports === "function") {
            await Services.refreshImports({ reason: "import-gate", waitForCompletion: true });
          } else if (typeof DesktopBridge !== "undefined" && typeof DesktopBridge.refreshImports === "function") {
            await DesktopBridge.refreshImports();
          }
          clearDismiss();
          await onReadinessChanged();
        } catch {
          /* refresh optional */
        }
        refreshBtn.disabled = false;
      });
    }
    if (dismissBtn) {
      dismissBtn.addEventListener("click", () => {
        dismissSession();
        removeGate();
      });
    }
  }

  function staffMockEmbedPage(pageId) {
    if (typeof window === "undefined") return false;
    if (
      window.NR2_STAFF_MOCK_ONLY ||
      document.documentElement.getAttribute("data-nr2-staff-render") === "mock-embed"
    ) {
      const build = window.NR2_BUILD || {};
      const live =
        build.staffRenderMode === "live-wire-pilot" && Array.isArray(build.liveWirePages)
          ? build.liveWirePages
          : Array.isArray(window.NR2_LIVE_WIRE_PAGES)
            ? window.NR2_LIVE_WIRE_PAGES
            : [];
      if (live.length && pageId) return !live.includes(pageId);
      return true;
    }
    return false;
  }

  async function evaluate(pageId) {
    if (staffMockEmbedPage(pageId)) {
      removeGate();
      return;
    }
    if (typeof ImportTrafficBanner !== "undefined") {
      removeGate();
      return;
    }
    if (!isFinancialPage(pageId)) {
      removeGate();
      return;
    }
    if (isDismissed()) return;
    const readiness = await fetchReadiness();
    if (!needsGate(readiness)) {
      removeGate();
      clearDismiss();
      return;
    }
    if (gateEl) return;
    const wrap = document.createElement("div");
    wrap.innerHTML = buildGateHtml(readiness);
    gateEl = wrap.firstElementChild;
    if (gateEl) {
      document.body.appendChild(gateEl);
      wireGate(gateEl);
    }
  }

  async function onReadinessChanged() {
    const pageId = (window.location.hash || "").replace("#", "");
    await evaluate(pageId);
  }

  function liveWirePilotActive() {
    const build = typeof window !== "undefined" && window.NR2_BUILD ? window.NR2_BUILD : null;
    if (build && build.staffRenderMode === "live-wire-pilot") return true;
    return typeof window !== "undefined" && window.NR2_STAFF_RENDER_MODE === "live-wire-pilot";
  }

  function installListeners() {
    if (typeof window === "undefined") return;
    if (staffMockEmbedPage("financial") && !liveWirePilotActive()) return;
    window.addEventListener("nr2-import-readiness-changed", () => {
      onReadinessChanged();
      window.dispatchEvent(new CustomEvent("nr2:page-refresh-requested"));
    });
  }

  return { evaluate, onReadinessChanged, installListeners, isFinancialPage, clearDismiss };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = ImportReadinessGate;
}
if (typeof window !== "undefined") {
  window.ImportReadinessGate = ImportReadinessGate;
}
