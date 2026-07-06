/**
 * HAL transparency — lane badge, session audit panel, block explanations.
 */
const HalTransparency = (function () {
  function esc(v) {
    return String(v == null ? "" : v)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }

  function ensureSessionId() {
    if (typeof window === "undefined") return "node-session";
    if (!window.nr2HalSessionId) {
      window.nr2HalSessionId = "hal-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 8);
    }
    return window.nr2HalSessionId;
  }

  function laneLabel(lane) {
    const map = { chat8b: "Chat 8B", reason21b: "Reason 21B", escalate30b: "Escalate 30B", cloud: "Cloud" };
    return map[String(lane || "").toLowerCase()] || String(lane || "—");
  }

  function renderLaneBadge(lane) {
    const host =
      (typeof document !== "undefined" && document.getElementById("halLaneBadge")) ||
      (typeof document !== "undefined" && document.querySelector("[data-hal-lane-badge]"));
    if (!host) return;
    host.textContent = laneLabel(lane);
    host.setAttribute("data-lane", String(lane || ""));
    host.classList.add("nr2-hal-lane-badge");
  }

  async function loadSessionAudit() {
    const db = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
    if (!db || typeof db.fetchHalSessionAudit !== "function") return null;
    ensureSessionId();
    try {
      return await db.fetchHalSessionAudit(window.nr2HalSessionId);
    } catch {
      return null;
    }
  }

  async function renderAuditPanel(container) {
    if (!container) return;
    const session = await loadSessionAudit();
    const events = (session && session.session && session.session.events) || [];
    const shift = typeof window !== "undefined" ? window.nr2ShiftState : null;
    container.innerHTML =
      `<section class="nr2-panel nr2-panel--hal-audit"><h3>HAL Session Audit</h3>` +
      `<p class="nr2-muted">Session ${esc(ensureSessionId())}</p>` +
      (shift
        ? `<p>Tier ${esc(shift.tier)} · ${esc(shift.levelName || "")} · ${shift.active ? "On shift" : "Off shift"}</p>`
        : `<p class="nr2-muted">Shift context loading…</p>`) +
      (events.length
        ? `<ul class="nr2-hal-audit-list">${events
            .slice(-12)
            .reverse()
            .map(
              (ev) =>
                `<li>${esc(ev.ts || "")} · ${esc(ev.type || ev.lane || "")}` +
                `${ev.blocked ? " · blocked" : ""}` +
                `${ev.error ? " · " + esc(ev.error) : ""}</li>`,
            )
            .join("")}</ul>`
        : `<p class="nr2-muted">No audit events yet for this session.</p>`) +
      `<button type="button" class="nr2-hal-audit-refresh">Refresh audit</button>` +
      `</section>`;
    const btn = container.querySelector(".nr2-hal-audit-refresh");
    if (btn) {
      btn.addEventListener("click", () => renderAuditPanel(container));
    }
  }

  async function explainBlock(error, readiness) {
    const db = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
    if (!db || typeof db.explainHalBlock !== "function") {
      return { explanation: String(error || "Blocked") };
    }
    return db.explainHalBlock({
      error: error,
      readiness: readiness,
      sessionId: ensureSessionId(),
    });
  }

  function install() {
    if (typeof window === "undefined") return;
    ensureSessionId();
    window.addEventListener("nr2-hal-lane-used", (ev) => {
      const lane = ev && ev.detail && ev.detail.lane;
      if (lane) renderLaneBadge(lane);
    });
    window.addEventListener("nr2-shift-state-changed", () => {
      const panel = document.getElementById("halTransparencyPanel");
      if (panel) renderAuditPanel(panel).catch(() => {});
    });
    const halRoot = document.getElementById("halPageRoot");
    if (halRoot && !document.getElementById("halLaneBadge")) {
      const badge = document.createElement("span");
      badge.id = "halLaneBadge";
      badge.className = "nr2-hal-lane-badge";
      badge.textContent = "—";
      halRoot.prepend(badge);
    }
    let panel = document.getElementById("halTransparencyPanel");
    if (!panel && halRoot) {
      panel = document.createElement("div");
      panel.id = "halTransparencyPanel";
      panel.className = "nr2-hal-transparency";
      halRoot.appendChild(panel);
    }
    if (panel) renderAuditPanel(panel).catch(() => {});
  }

  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", install, { once: true });
    } else {
      install();
    }
  }

  return {
    ensureSessionId,
    laneLabel,
    renderLaneBadge,
    renderAuditPanel,
    explainBlock,
    install,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalTransparency;
}
if (typeof window !== "undefined") {
  window.HalTransparency = HalTransparency;
}
