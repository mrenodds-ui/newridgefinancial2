/**
 * NR2-Apex Ticker Tape — top + bottom telemetry tracks
 * Build: hal-10340
 */
(function () {
  "use strict";

  const CONFIG = {
    endpoint: "/api/apex/ticker",
    interval: 30000,
    maxItems: 24,
    muteKey: "nr2-apex-ticker-muted",
  };

  class ApexTicker {
    constructor() {
      this.track = document.getElementById("ticker-track");
      this.trackBottom = document.getElementById("ticker-track-bottom");
      this.items = [];
      this.timer = null;
      this.muted = false;
      this.init();
    }

    async init() {
      this.wireMute();
      await this.fetch();
      this.timer = setInterval(() => this.fetch(), CONFIG.interval);
      document.addEventListener("visibilitychange", () => {
        if (!document.hidden) this.fetch();
      });
    }

    wireMute() {
      try {
        this.muted = sessionStorage.getItem(CONFIG.muteKey) === "1";
      } catch (_err) {
        this.muted = false;
      }
      this.applyMute();
      const btn = document.getElementById("btn-ticker-mute");
      if (!btn) return;
      btn.addEventListener("click", () => {
        this.muted = !this.muted;
        try {
          sessionStorage.setItem(CONFIG.muteKey, this.muted ? "1" : "0");
        } catch (_err) {
          /* ignore */
        }
        this.applyMute();
      });
    }

    applyMute() {
      document.body.classList.toggle("apex-ticker-muted", !!this.muted);
      const btn = document.getElementById("btn-ticker-mute");
      if (btn) {
        btn.classList.toggle("is-muted", !!this.muted);
        btn.textContent = this.muted ? "Resume Ticker" : "Mute Ticker";
      }
    }

    async fetch() {
      try {
        let res;
        if (window.Apex && typeof window.Apex.apexFetch === "function") {
          res = await window.Apex.apexFetch(`${CONFIG.endpoint}?_=${Date.now()}`);
        } else {
          res = await fetch(`${CONFIG.endpoint}?_=${Date.now()}`, {
            credentials: "same-origin",
            cache: "no-store",
          });
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        this.update(data.items || []);
      } catch (_err) {
        this.update([{ type: "system", text: "TICKER OFFLINE — CHECK BRIDGE LINK" }]);
      }
    }

    update(items) {
      const sanitized = (items || []).slice(0, CONFIG.maxItems).map((item) => {
        const type = String((item && item.type) || "system");
        let text = "";
        if (item && item.text) text = String(item.text);
        else if (item && item.label) {
          const val = item.value;
          if (val === null || val === undefined || val === "") {
            text = `${item.label}: —`;
          } else {
            text = `${item.label}: ${val}${item.unit ? " " + item.unit : ""}`;
          }
        } else {
          text = "DATA UNAVAILABLE";
        }
        return { type, text, severity: (item && item.severity) || "info" };
      });
      if (JSON.stringify(sanitized) === JSON.stringify(this.items)) return;
      this.items = sanitized;
      this.render();
    }

    renderTrack(trackEl, items) {
      if (!trackEl) return;
      const html = items
        .map((item) => {
          const cls = `apex-ticker__item apex-ticker__item--${item.type}`;
          const prefix =
            item.type === "metric" ? "◈ " : item.type === "alert" ? "▲ " : item.type === "hal" ? "◐ " : "• ";
          return `<span class="${cls}">${prefix}${this.escape(item.text)}</span>`;
        })
        .join("");
      trackEl.innerHTML = html + html;
    }

    render() {
      this.renderTrack(this.track, this.items);
      const ops = this.items.slice().sort((a, b) => {
        const rank = (t) => (t === "alert" ? 0 : t === "hal" ? 1 : t === "system" ? 2 : 3);
        return rank(a.type) - rank(b.type);
      });
      this.renderTrack(this.trackBottom, ops);
    }

    escape(text) {
      return String(text == null ? "" : text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }
  }

  function boot() {
    window.ApexTicker = new ApexTicker();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
