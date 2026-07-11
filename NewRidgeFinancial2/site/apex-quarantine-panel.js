/**
 * Phase W2 — Quarantine review panel actions (Moonshot REAUDIT5 SHOULD).
 * Retry / purge via existing U2b+W2 HAL endpoints. No SoftDent write-back.
 */
(function () {
  "use strict";

  function apiBase() {
    try {
      if (window.Apex && window.Apex.config && window.Apex.config.apiBase) {
        return window.Apex.config.apiBase;
      }
    } catch (_) {}
    return "/api/apex";
  }

  async function apexPost(path, body) {
    const opts = {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    };
    if (window.Apex && typeof window.Apex.apexFetch === "function") {
      return window.Apex.apexFetch(path, opts);
    }
    const res = await fetch(`${apiBase()}${path}`, opts);
    return res.json();
  }

  async function refreshPage() {
    try {
      if (window.Apex && typeof window.Apex.loadPage === "function") {
        const hash = (location.hash || "").replace(/^#/, "").trim() || "financial";
        await window.Apex.loadPage(hash, { silent: true });
        return;
      }
    } catch (_) {}
    window.dispatchEvent(new CustomEvent("nr2-quarantine-changed"));
  }

  async function onClick(event) {
    const retry = event.target.closest("[data-q-retry]");
    const purge = event.target.closest("[data-q-purge]");
    const refresh = event.target.closest("[data-q-refresh]");
    if (!retry && !purge && !refresh) return;

    if (refresh) {
      event.preventDefault();
      await refreshPage();
      return;
    }

    const name = (retry || purge).getAttribute(retry ? "data-q-retry" : "data-q-purge");
    if (!name) return;
    event.preventDefault();
    const btn = retry || purge;
    btn.disabled = true;
    try {
      const path = retry ? "/hal/import-quarantine-retry" : "/hal/import-quarantine-purge";
      const data = await apexPost(path, { name });
      if (!data || !data.ok) {
        const err = (data && (data.error || data.reason)) || "action_failed";
        window.alert(`Quarantine ${retry ? "retry" : "purge"} failed: ${err}`);
      }
      await refreshPage();
    } catch (err) {
      window.alert(`Quarantine action error: ${err && err.message ? err.message : err}`);
    } finally {
      btn.disabled = false;
    }
  }

  function boot() {
    document.addEventListener("click", onClick);
    window.addEventListener("nr2-quarantine-changed", () => {
      /* reserved for SSE/live refresh hooks */
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  window.Nr2QuarantinePanel = { refreshPage };
})();
