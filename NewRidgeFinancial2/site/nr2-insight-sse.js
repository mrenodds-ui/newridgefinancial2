/**
 * N0 — Live AI insight SSE client (hal-ai-insight widget).
 * EventSource → /api/apex/hal/insight-stream; 5s poll fallback on insight-latest.
 */
const NR2InsightSSE = (function () {
  let source = null;
  let pollTimer = null;
  let lastGen = "";

  function apiBase() {
    try {
      if (window.Apex && window.Apex.config && window.Apex.config.apiBase) {
        return String(window.Apex.config.apiBase).replace(/\/$/, "");
      }
    } catch (_e) {
      /* ignore */
    }
    return "/api/apex";
  }

  function applyInsight(payload) {
    if (!payload || !payload.ok) return;
    const gen = String(payload.generation || "");
    if (gen && gen === lastGen) return;
    lastGen = gen;
    const insight = payload.insight;
    if (insight && typeof insight === "object") {
      try {
        sessionStorage.setItem("nr2-apex-last-insight", JSON.stringify(insight));
      } catch (_e) {
        /* ignore */
      }
    }
    window.dispatchEvent(new CustomEvent("nr2-insight-updated", { detail: payload }));
    // Patch visible ai-insight card without full page reload when present
    const card = document.querySelector('[data-widget-id="hal-ai-insight"]');
    if (card && payload.widget && payload.widget.status === "ok" && insight) {
      const title = card.querySelector(".apex-kpi-label, .apex-widget-label");
      const value = card.querySelector(".apex-kpi-value");
      const hint = card.querySelector(".apex-kpi-hint");
      if (title) title.textContent = String(insight.title || "AI Insight");
      if (value) {
        value.classList.remove("is-empty");
        const data = insight.data || {};
        value.textContent =
          data.value != null
            ? String(data.value) + (data.unit && data.unit !== "text" ? ` ${data.unit}` : "")
            : String(insight.explanation || insight.title || "Updated");
      }
      if (hint) hint.textContent = String(insight.explanation || "");
      card.setAttribute("data-insight-gen", gen);
    } else if (
      typeof window.Apex === "object" &&
      typeof window.Apex.loadPage === "function" &&
      String(window.location.hash || "").includes("hal")
    ) {
      try {
        window.Apex.loadPage("hal");
      } catch (_e) {
        /* ignore */
      }
    }
  }
  async function pollLatest() {
    try {
      const url = `${apiBase()}/hal/insight-latest`;
      const res = await fetch(url, { cache: "no-store" });
      const data = await res.json();
      applyInsight(data);
    } catch (_e) {
      /* optional */
    }
  }

  function connectSse() {
    if (typeof EventSource === "undefined") {
      pollLatest();
      return;
    }
    if (source) {
      try {
        source.close();
      } catch (_e) {
        /* ignore */
      }
    }
    const url = `${apiBase()}/hal/insight-stream`;
    source = new EventSource(url);
    source.addEventListener("insight", (ev) => {
      try {
        applyInsight(JSON.parse(ev.data || "{}"));
      } catch (_e) {
        pollLatest();
      }
    });
    source.onmessage = (ev) => {
      try {
        applyInsight(JSON.parse(ev.data || "{}"));
      } catch (_e) {
        /* ignore */
      }
    };
    source.onerror = () => {
      if (source) source.close();
      source = null;
      setTimeout(connectSse, 30000);
      pollLatest();
    };
  }

  function install() {
    if (typeof document === "undefined") return;
    connectSse();
    pollLatest();
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(pollLatest, 5000);
  }

  return { install, pollLatest, connectSse, applyInsight };
})();

if (typeof window !== "undefined") {
  window.NR2InsightSSE = NR2InsightSSE;
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => NR2InsightSSE.install());
  } else {
    NR2InsightSSE.install();
  }
}
