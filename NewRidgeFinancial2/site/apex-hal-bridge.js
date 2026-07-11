/**
 * NR2-Apex — HAL bridge: status poll, suggestion panel, sidebar orb
 * Build: hal-10240
 */
(function () {
  "use strict";

  const POLL_MS = 120000;
  const SUGGEST_AUTO_MS = 0; // no auto popup — sidebar text still updates

  let pollTimer = null;
  let dismissTimer = null;
  let lastSuggestion = "";
  let lastStatus = "idle";

  function panel() {
    return document.getElementById("apex-hal-suggest");
  }

  function orb() {
    return document.getElementById("sidebar-hal-orb") || document.querySelector(".hal-orb");
  }

  function statusLabel() {
    return document.getElementById("sidebar-hal-status") || document.querySelector("#apex-hal-status span");
  }

  function suggestionTextEl() {
    return document.getElementById("hal-suggestion-text");
  }

  function ensurePanel() {
    let el = panel();
    if (el) return el;
    el = document.createElement("aside");
    el.id = "apex-hal-suggest";
    el.setAttribute("role", "status");
    el.setAttribute("aria-live", "polite");
    el.innerHTML = `
      <button type="button" class="apex-suggest-close" data-suggest-close aria-label="Dismiss">×</button>
      <div class="apex-suggest-kicker">HAL suggestion</div>
      <p class="apex-suggest-body" data-suggest-body></p>
      <div class="apex-suggest-actions">
        <button type="button" class="apex-suggest-btn is-primary" data-suggest-ask>Ask HAL</button>
        <button type="button" class="apex-suggest-btn" data-suggest-sync>Sync</button>
        <button type="button" class="apex-suggest-btn" data-suggest-dismiss>Dismiss</button>
      </div>
    `;
    document.body.appendChild(el);
    el.querySelector("[data-suggest-close]")?.addEventListener("click", hideSuggestion);
    el.querySelector("[data-suggest-dismiss]")?.addEventListener("click", hideSuggestion);
    el.querySelector("[data-suggest-ask]")?.addEventListener("click", () => {
      const text = lastSuggestion || (el.querySelector("[data-suggest-body]") || {}).textContent || "";
      hideSuggestion();
      if (window.Apex && typeof window.Apex.askHalFromBridge === "function") {
        window.Apex.askHalFromBridge(text);
      } else if (window.Apex && typeof window.Apex.loadPage === "function") {
        window.Apex.loadPage("hal");
      }
    });
    el.querySelector("[data-suggest-sync]")?.addEventListener("click", () => {
      hideSuggestion();
      if (window.Apex && typeof window.Apex.triggerSync === "function") {
        window.Apex.triggerSync();
      }
    });
    return el;
  }

  function setHeaderStatus(status, label) {
    lastStatus = String(status || "idle");
    const o = orb();
    const span = statusLabel();
    if (o) {
      o.classList.toggle(
        "is-live",
        lastStatus === "busy" || lastStatus === "syncing" || lastStatus === "live" || lastStatus === "ready"
      );
    }
    if (span) {
      span.textContent = label || statusLabelText(lastStatus);
    }
  }

  function statusLabelText(status) {
    if (status === "busy" || status === "syncing") return "HAL Busy";
    if (status === "live" || status === "ready") return "HAL Live";
    if (status === "degraded") return "HAL Degraded";
    return "HAL Standby";
  }

  function showSuggestion(text, opts) {
    const msg = String(text || "").trim();
    if (!msg) return;
    const force = opts && opts.force;
    if (!force && msg === lastSuggestion) return;
    lastSuggestion = msg;
    const side = suggestionTextEl();
    if (side) side.textContent = msg;
    const el = ensurePanel();
    const body = el.querySelector("[data-suggest-body]");
    if (body) body.textContent = msg;
    el.classList.add("is-open");
    if (dismissTimer) clearTimeout(dismissTimer);
    const autoMs = (opts && opts.autoMs) || SUGGEST_AUTO_MS;
    if (autoMs > 0) {
      dismissTimer = setTimeout(hideSuggestion, autoMs);
    }
  }

  function hideSuggestion() {
    const el = panel();
    if (el) el.classList.remove("is-open");
    if (dismissTimer) {
      clearTimeout(dismissTimer);
      dismissTimer = null;
    }
  }

  async function fetchStatus() {
    if (!window.Apex || typeof window.Apex.apexFetch !== "function") {
      return null;
    }
    try {
      const res = await window.Apex.apexFetch("/api/apex/hal/status");
      if (!res.ok) return null;
      return await res.json();
    } catch (_err) {
      return null;
    }
  }

  async function pollOnce(opts) {
    const data = await fetchStatus();
    if (!data) return;
    const status = String(data.status || "idle");
    const label = data.statusLabel || statusLabelText(status);
    setHeaderStatus(status, label);
    const suggestion = String(data.suggestion || "").trim();
    if (suggestion) {
      const side = suggestionTextEl();
      if (side) side.textContent = suggestion;
      lastSuggestion = suggestion;
      if (opts && opts.showSuggest !== false) {
        showSuggestion(suggestion, { force: !!(opts && opts.forceSuggest) });
      }
    }
    if (window.Apex && typeof window.Apex.onHalStatus === "function") {
      window.Apex.onHalStatus(data);
    }
    return data;
  }

  function start() {
    ensurePanel();
    if (pollTimer) clearInterval(pollTimer);
    // Sidebar suggestion text only — do not slam the floating panel (looked like page refresh).
    pollOnce({ showSuggest: false });
    pollTimer = setInterval(() => pollOnce({ showSuggest: false }), POLL_MS);
  }

  function stop() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
    hideSuggestion();
  }

  window.ApexHal = {
    start,
    stop,
    pollOnce,
    showSuggestion,
    hideSuggestion,
    setHeaderStatus,
    get lastSuggestion() {
      return lastSuggestion;
    },
    get lastStatus() {
      return lastStatus;
    },
  };

  function boot() {
    const tryStart = () => {
      if (window.Apex && typeof window.Apex.apexFetch === "function") {
        start();
        return true;
      }
      return false;
    };
    if (tryStart()) return;
    let attempts = 0;
    const t = setInterval(() => {
      attempts += 1;
      if (tryStart() || attempts > 40) clearInterval(t);
    }, 250);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
