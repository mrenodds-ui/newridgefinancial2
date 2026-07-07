/**
 * Persistent import traffic-light banner — Moonshot Phase 8.
 */
const ImportTrafficBanner = (function () {
  const THROTTLE_MS = 60000;
  let lastRefreshAt = 0;

  function esc(v) {
    return String(v == null ? "" : v)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }

  function tone(level) {
    if (level === "fresh") return "green";
    if (level === "syncing") return "yellow";
    if (level === "stale") return "yellow";
    return "red";
  }

  function minutesSince(readiness) {
    const h = readiness && readiness.ageHours;
    if (h == null) return "unknown";
    return Math.round(Number(h) * 60);
  }

  function html(readiness) {
    const level = (readiness && readiness.level) || "unknown";
    const t = tone(level);
    const mins = minutesSince(readiness);
    const completeness = readiness && readiness.completeness;
    const compText =
      completeness && completeness.scorePct != null
        ? ` · completeness ${completeness.scorePct}%`
        : "";
    return (
      `<div id="nr2-import-traffic-banner" class="nr2-import-traffic nr2-import-traffic--${t}" role="status">` +
      `<span class="nr2-import-traffic__dot" aria-hidden="true"></span>` +
      `<strong>Import ${esc(level.toUpperCase())}</strong>` +
      `<span> · ${mins === "unknown" ? "sync time unknown" : mins + " min since load"}${esc(compText)}</span>` +
      `<button type="button" class="nr2-import-traffic__refresh" data-nr2-force-refresh>Force Refresh</button>` +
      `</div>`
    );
  }

  function mount(readiness) {
    if (typeof document === "undefined") return;
    let bar = document.getElementById("nr2-import-traffic-banner");
    if (!bar) {
      const host = document.getElementById("appPage") || document.body;
      const wrap = document.createElement("div");
      wrap.innerHTML = html(readiness);
      bar = wrap.firstElementChild;
      if (bar && host.firstChild) host.insertBefore(bar, host.firstChild);
      else if (bar) host.prepend(bar);
    } else {
      bar.outerHTML = html(readiness);
      bar = document.getElementById("nr2-import-traffic-banner");
    }
    const btn = bar && bar.querySelector("[data-nr2-force-refresh]");
    if (btn && !btn.dataset.wired) {
      btn.dataset.wired = "1";
      btn.addEventListener("click", async () => {
        const now = Date.now();
        if (now - lastRefreshAt < THROTTLE_MS) return;
        lastRefreshAt = now;
        if (typeof DesktopBridge !== "undefined" && DesktopBridge.refreshImports) {
          await DesktopBridge.refreshImports();
        }
      });
    }
  }

  function install() {
    if (typeof window === "undefined") return;
    window.addEventListener("nr2-import-readiness-changed", (ev) => {
      mount((ev && ev.detail) || (typeof DesktopBridge !== "undefined" && DesktopBridge.getCachedImportReadiness && DesktopBridge.getCachedImportReadiness()));
    });
    const cached =
      typeof DesktopBridge !== "undefined" && DesktopBridge.getCachedImportReadiness
        ? DesktopBridge.getCachedImportReadiness()
        : null;
    if (cached) mount(cached);
  }

  return { mount, install, html };
})();

if (typeof window !== "undefined") {
  window.ImportTrafficBanner = ImportTrafficBanner;
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => ImportTrafficBanner.install());
  else ImportTrafficBanner.install();
}
