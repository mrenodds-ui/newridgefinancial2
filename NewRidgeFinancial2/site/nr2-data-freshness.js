/**
 * Phase V0 — Data freshness chips (Moonshot REAUDIT4 SHOULD).
 * Renders SoftDent/QB/ERA import age levels. No dollar amounts.
 */
(function () {
  "use strict";

  function apiBase() {
    try {
      if (window.ApexCore && typeof window.ApexCore.apiBase === "function") {
        return window.ApexCore.apiBase();
      }
    } catch (_) {}
    return "/api/apex";
  }

  function ensureBar() {
    let bar = document.getElementById("nr2-freshness-bar");
    if (bar) return bar;
    bar = document.createElement("div");
    bar.id = "nr2-freshness-bar";
    bar.className = "nr2-freshness-bar";
    bar.setAttribute("aria-live", "polite");
    bar.hidden = true;
    const stage = document.getElementById("apex-stage");
    if (stage && stage.parentNode) {
      stage.parentNode.insertBefore(bar, stage);
    } else {
      document.body.prepend(bar);
    }
    return bar;
  }

  function render(status) {
    const bar = ensureBar();
    if (!status) {
      bar.hidden = true;
      bar.innerHTML = "";
      return;
    }
    const chips = Array.isArray(status.chips) ? status.chips.slice() : [];
    // Moonshot Phase 2 REC-004: surface SoftDent/QB age when stale/critical or import degraded.
    if (status.importDegraded) {
      chips.unshift({
        source: "imports",
        level: "stale",
        ageHours: null,
        label: "Import Degraded",
      });
    }
    const force =
      status.forceShow ||
      status.importDegraded ||
      chips.some((c) => c && (c.level === "critical" || c.level === "stale"));
    if (!status.enabled && !force) {
      bar.hidden = true;
      bar.innerHTML = "";
      return;
    }
    if (!chips.length) {
      bar.hidden = true;
      bar.innerHTML = "";
      return;
    }
    bar.hidden = false;
    bar.innerHTML = chips
      .map((c) => {
        const level = String((c && c.level) || "unknown");
        const src = String((c && (c.label || c.source)) || "?");
        const age =
          c && c.ageHours != null
            ? `${Number(c.ageHours).toFixed(1)}h`
            : c && c.label
              ? ""
              : "n/a";
        const ageBit = age ? `: ${age}` : "";
        const title =
          (c && c.alert) ||
          (level === "critical"
            ? `${src} older than 7 days — refresh SoftDent/QuickBooks`
            : `${src} last import age`);
        return `<span class="nr2-freshness-chip nr2-freshness-chip--${level}" title="${title}">${src}${ageBit}</span>`;
      })
      .join("");
  }

  function currentPageId() {
    try {
      const stage = document.getElementById("apex-stage");
      if (stage && stage.dataset && stage.dataset.page) return String(stage.dataset.page);
      const hash = String(location.hash || "").replace(/^#/, "");
      return String(hash.split("/")[0] || "").toLowerCase();
    } catch (_) {
      return "";
    }
  }

  async function refresh() {
    try {
      const res = await fetch(`${apiBase()}/hal/sync-status`, { credentials: "same-origin" });
      let body = null;
      if (res.ok) body = await res.json();
      // Merge HAL status importDegraded (Phase 1+2 honesty).
      try {
        const hs = await fetch(`${apiBase()}/hal/status`, { credentials: "same-origin" });
        if (hs.ok) {
          const hal = await hs.json();
          body = body || { enabled: true, chips: [] };
          body.importDegraded = !!(hal && hal.importDegraded);
          if (hal && hal.importDegraded) body.forceShow = true;
        }
      } catch (_) {}
      // hal-10619: always surface freshness strip on Financial / SoftDent money pages
      const page = currentPageId();
      if (body && (page === "financial" || page === "softdent")) {
        body.forceShow = true;
        body.enabled = true;
      }
      if (body) render(body);
    } catch (_) {}
  }

  function boot() {
    refresh();
    setInterval(refresh, 60000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  window.Nr2DataFreshness = { refresh, render };
})();
