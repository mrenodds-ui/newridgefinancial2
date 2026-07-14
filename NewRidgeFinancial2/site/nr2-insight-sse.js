/**
 * N0 — Live AI insight SSE client (hal-ai-insight widget).
 * EventSource → /api/apex/hal/insight-stream; 5s poll fallback on insight-latest.
 * Never hard-remounts #hal — that wiped the Ask HAL composer (looked like a full page refresh).
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

  function dataMessage(insight) {
    const data = insight && insight.data && typeof insight.data === "object" ? insight.data : null;
    return data && data.message != null ? String(data.message) : "";
  }

  function patchInsightCard(card, insight, gen) {
    if (!card || !insight) return false;
    const title = card.querySelector(".apex-kpi-label, .apex-widget-label");
    const value = card.querySelector(".apex-kpi-value");
    const hints = card.querySelectorAll(".apex-kpi-hint");
    if (title) title.textContent = String(insight.title || "AI Insight");
    if (value) {
      value.classList.remove("is-empty");
      const data = insight.data || {};
      value.textContent =
        data.value != null
          ? String(data.value) + (data.unit && data.unit !== "text" ? ` ${data.unit}` : "")
          : String(insight.explanation || insight.title || "Updated");
    }
    if (hints && hints.length) {
      const explanation = String(insight.explanation || dataMessage(insight) || "");
      // Prefer a body hint when present; keep badge hint (type · confidence) alone.
      if (hints.length >= 2 && explanation) {
        hints[hints.length - 2].textContent = explanation;
      } else if (explanation) {
        hints[hints.length - 1].textContent = explanation;
      }
    }
    card.setAttribute("data-insight-gen", gen);
    return true;
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
    const card = document.querySelector('[data-widget-id="hal-ai-insight"]');
    if (card && insight) {
      patchInsightCard(card, insight, gen);
      return;
    }
    // Card not mounted yet or empty insight — wait for next poll / normal page paint.
    // Never remount HAL from this client (hal-10626).
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
