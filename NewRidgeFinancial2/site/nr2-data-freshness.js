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
    if (!status || !status.enabled) {
      bar.hidden = true;
      bar.innerHTML = "";
      return;
    }
    const chips = Array.isArray(status.chips) ? status.chips : [];
    bar.hidden = false;
    bar.innerHTML = chips
      .map((c) => {
        const level = String((c && c.level) || "unknown");
        const src = String((c && c.source) || "?");
        const age = c && c.ageHours != null ? `${Number(c.ageHours).toFixed(1)}h` : "n/a";
        return `<span class="nr2-freshness-chip nr2-freshness-chip--${level}" title="${src} last import age">${src}: ${age}</span>`;
      })
      .join("");
  }

  async function refresh() {
    try {
      const res = await fetch(`${apiBase()}/hal/sync-status`, { credentials: "same-origin" });
      if (!res.ok) return;
      const body = await res.json();
      render(body);
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
