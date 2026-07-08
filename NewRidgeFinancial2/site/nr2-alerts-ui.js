/**
 * HAL proactive alerts — SSE client + toast banner (Phase 2 E).
 */
const NR2AlertsUI = (function () {
  let source = null;
  let reconnectTimer = null;

  function esc(v) {
    return String(v == null ? "" : v)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }

  async function fetchJson(path, opts) {
    if (typeof DesktopBridge !== "undefined" && DesktopBridge.loopbackJson) {
      return DesktopBridge.loopbackJson(path, opts);
    }
    const r = await fetch(path, opts || { cache: "no-store" });
    return r.json();
  }

  function severityClass(sev) {
    const s = String(sev || "medium").toLowerCase();
    if (s === "high") return "nr2-alert--high";
    if (s === "low") return "nr2-alert--low";
    return "nr2-alert--medium";
  }

  function ensureHost() {
    let host = document.getElementById("nr2-alerts-toast-host");
    if (!host) {
      host = document.createElement("div");
      host.id = "nr2-alerts-toast-host";
      host.className = "nr2-alerts-toast-host";
      host.setAttribute("aria-live", "polite");
      document.body.appendChild(host);
    }
    return host;
  }

  function shouldShowAlert(alert) {
    if (!alert) return false;
    const type = String(alert.alertType || alert.alert_type || "");
    const body = String(alert.body || "");
    const title = String(alert.title || "");
    if (type === "import_failure" && /syncing/i.test(body)) return false;
    if (title === "Import pipeline requires attention" && /syncing/i.test(body)) return false;
    if (typeof ImportTrafficBanner !== "undefined" && type === "import_failure") return false;
    return true;
  }

  function dedupeAlerts(items) {
    const seen = new Set();
    const out = [];
    for (const alert of Array.isArray(items) ? items : []) {
      if (!shouldShowAlert(alert)) continue;
      const key = `${alert.alertType || ""}|${alert.title || ""}|${alert.body || ""}`;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(alert);
    }
    return out;
  }

  function renderToasts(items) {
    const host = ensureHost();
    const list = dedupeAlerts(items).slice(0, 3);
    host.innerHTML = list
      .map(
        (a) =>
          `<div class="nr2-alert-toast ${severityClass(a.severity)}" data-alert-id="${esc(a.id)}">` +
          `<strong>${esc(a.title || "Alert")}</strong>` +
          `<p>${esc((a.body || "").slice(0, 160))}</p>` +
          `<button type="button" class="nr2-alert-ack" data-alert-id="${esc(a.id)}">Acknowledge</button>` +
          `</div>`,
      )
      .join("");
    host.querySelectorAll(".nr2-alert-ack").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-alert-id");
        if (!id) return;
        btn.disabled = true;
        try {
          await fetchJson(`/api/alerts/${encodeURIComponent(id)}/ack`, { method: "POST", body: "{}" });
          const card = btn.closest("[data-alert-id]");
          if (card) card.remove();
        } catch {
          btn.disabled = false;
        }
      });
    });
  }

  async function pollActive() {
    try {
      const data = await fetchJson("/api/alerts/active");
      renderToasts((data && data.items) || []);
    } catch {
      /* optional */
    }
  }

  function connectSse() {
    if (typeof EventSource === "undefined") {
      pollActive();
      return;
    }
    if (source) {
      try {
        source.close();
      } catch {
        /* ignore */
      }
    }
    const url = "/api/alerts/stream";
    source = new EventSource(url);
    source.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data || "{}");
        renderToasts((data && data.items) || []);
        window.dispatchEvent(new CustomEvent("nr2-alerts-updated", { detail: data }));
      } catch {
        pollActive();
      }
    };
    source.onerror = () => {
      if (source) source.close();
      source = null;
      clearTimeout(reconnectTimer);
      reconnectTimer = setTimeout(connectSse, 30000);
      pollActive();
    };
  }

  function install() {
    if (typeof document === "undefined") return;
    connectSse();
    pollActive();
  }

  return { install, pollActive, renderToasts, connectSse };
})();

if (typeof window !== "undefined") {
  window.NR2AlertsUI = NR2AlertsUI;
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => NR2AlertsUI.install());
  else NR2AlertsUI.install();
}
