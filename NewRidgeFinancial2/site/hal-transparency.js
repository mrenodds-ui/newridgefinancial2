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

  function renderLaneBadge(lane, routingReason) {
    const host =
      (typeof document !== "undefined" && document.getElementById("halLaneBadge")) ||
      (typeof document !== "undefined" && document.querySelector("[data-hal-lane-badge]"));
    if (!host) return;
    const suffix =
      routingReason === "financial_math_policy" || String(routingReason || "").includes("financial")
        ? " 💰"
        : "";
    host.textContent = laneLabel(lane) + suffix;
    host.setAttribute("data-lane", String(lane || ""));
    host.setAttribute("title", routingReason === "financial_math_policy" ? "Financial calculation mode enforced" : "");
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

  async function postJson(path, body) {
    if (typeof DesktopBridge !== "undefined" && DesktopBridge.loopbackJson) {
      return DesktopBridge.loopbackJson(path, { method: "POST", body: JSON.stringify(body || {}) });
    }
    const r = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    return r.json();
  }

  function ensureClockOutModal() {
    let modal = document.getElementById("nr2-clock-out-modal");
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = "nr2-clock-out-modal";
    modal.className = "nr2-modal nr2-modal--hidden";
    modal.innerHTML =
      `<div class="nr2-modal__backdrop" data-nr2-close-modal></div>` +
      `<div class="nr2-modal__panel" role="dialog" aria-labelledby="nr2-clock-out-title">` +
      `<h3 id="nr2-clock-out-title">End HAL Shift</h3>` +
      `<p class="nr2-muted">Generate shift handoff report and clock HAL out.</p>` +
      `<pre class="nr2-handoff-preview nr2-muted">Handoff preview will appear here.</pre>` +
      `<div class="nr2-modal__actions">` +
      `<button type="button" class="nr2-clock-out-cancel" data-nr2-close-modal>Cancel</button>` +
      `<button type="button" class="nr2-clock-out-confirm">Clock out &amp; save handoff</button>` +
      `</div></div>`;
    document.body.appendChild(modal);
    modal.querySelectorAll("[data-nr2-close-modal]").forEach((el) => {
      el.addEventListener("click", () => modal.classList.add("nr2-modal--hidden"));
    });
    return modal;
  }

  function openClockOutModal() {
    const modal = ensureClockOutModal();
    modal.classList.remove("nr2-modal--hidden");
    const preview = modal.querySelector(".nr2-handoff-preview");
    if (preview) preview.textContent = "Ready to compile open collections, import health, and month-end tasks.";
    const confirm = modal.querySelector(".nr2-clock-out-confirm");
    if (confirm && !confirm.dataset.wired) {
      confirm.dataset.wired = "1";
      confirm.addEventListener("click", async () => {
        confirm.disabled = true;
        try {
          const data = await postJson("/api/employee/clock-out", { employeeId: "HAL" });
          if (preview) preview.textContent = data.reportMarkdown || "Handoff saved.";
          window.nr2ShiftState = { active: false, tier: 0, levelName: "Off shift" };
          window.dispatchEvent(new CustomEvent("nr2-shift-state-changed", { detail: window.nr2ShiftState }));
        } catch (exc) {
          if (preview) preview.textContent = String(exc || "Clock-out failed.");
        } finally {
          confirm.disabled = false;
        }
      });
    }
  }

  function installClockOutButton(panel) {
    if (!panel || panel.querySelector("[data-nr2-clock-out]")) return;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "nr2-clock-out-btn";
    btn.dataset.nr2ClockOut = "1";
    btn.textContent = "Clock out shift";
    btn.addEventListener("click", openClockOutModal);
    panel.querySelector(".nr2-panel--hal-audit")?.appendChild(btn) ||
      panel.appendChild(btn);
  }

  function showActionConfidence(confidence, label) {
    if (typeof document === "undefined") return;
    const score = Number(confidence);
    if (!Number.isFinite(score)) return;
    let toast = document.getElementById("nr2-hal-confidence-toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "nr2-hal-confidence-toast";
      toast.className = "nr2-hal-confidence-toast";
      document.body.appendChild(toast);
    }
    const pct = Math.round(score * 100);
    toast.className = `nr2-hal-confidence-toast${score < 0.8 ? " nr2-hal-confidence-toast--warn" : ""}`;
    toast.textContent = `${label || "HAL confidence"}: ${pct}%${score < 0.8 ? " — human co-sign required" : ""}`;
    toast.hidden = false;
    window.clearTimeout(showActionConfidence._t);
    showActionConfidence._t = window.setTimeout(() => {
      toast.hidden = true;
    }, 6000);
  }

  function install() {
    if (typeof window === "undefined") return;
    ensureSessionId();
    window.addEventListener("nr2-hal-lane-used", (ev) => {
      const lane = ev && ev.detail && ev.detail.lane;
      const routingReason = ev && ev.detail && ev.detail.routingReason;
      if (lane) renderLaneBadge(lane, routingReason);
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
    if (panel) {
      renderAuditPanel(panel).catch(() => {});
      installClockOutButton(panel);
    }
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
    openClockOutModal,
    showActionConfidence,
    install,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalTransparency;
}
if (typeof window !== "undefined") {
  window.HalTransparency = HalTransparency;
}
