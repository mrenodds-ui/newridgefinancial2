/**
 * SideNotes-style incoming message popups for NR2 Workstation.
 * Shows an in-app toast and asks the desktop shell for a small always-on-top balloon.
 */
const WorkstationMessagePopup = (function () {
  const AUTO_MS = 12000;
  const MAX_STACK = 5;

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function truncate(text, max) {
    const t = String(text || "").trim();
    if (t.length <= max) return t;
    return t.slice(0, max).replace(/\s+\S*$/, "") + "…";
  }

  function targetsLabel(item) {
    if (typeof OfficeHub !== "undefined" && OfficeHub.normalizeTargets) {
      const { targets } = OfficeHub.normalizeTargets(item || {});
      if (targets.some((t) => /^(all|everyone)$/i.test(String(t)))) return "Everyone";
      if (targets.length === 1) return targets[0];
      if (targets.length <= 3) return targets.join(" · ");
      return targets.slice(0, 2).join(" · ") + " +" + (targets.length - 2);
    }
    const target = String((item && item.target) || "Everyone");
    return /^(all|everyone)$/i.test(target) ? "Everyone" : target;
  }

  function showToast(item) {
    const stack = document.getElementById("wsMessagePopupStack");
    if (!stack) return;
    const from = String(item.from || "Office");
    const text = truncate(item.text, 220);
    const route = targetsLabel(item);
    const el = document.createElement("article");
    el.className = "ws-sn-popup";
    el.setAttribute("role", "status");
    el.innerHTML =
      `<p class="ws-sn-popup__from">${escapeHtml(from)}</p>
      <p class="ws-sn-popup__text">${escapeHtml(text)}</p>
      <footer class="ws-sn-popup__foot">
        <button type="button" class="ws-sn-popup__open" data-ws-popup-open>Open Messages</button>
        <button type="button" class="ws-sn-popup__close" data-ws-popup-dismiss aria-label="Dismiss">×</button>
      </footer>`;
    stack.appendChild(el);
    requestAnimationFrame(() => el.classList.add("ws-sn-popup--show"));
    const dismiss = () => {
      el.classList.remove("ws-sn-popup--show");
      window.setTimeout(() => el.remove(), 220);
    };
    el.querySelector("[data-ws-popup-dismiss]")?.addEventListener("click", (event) => {
      event.stopPropagation();
      dismiss();
    });
    el.querySelector("[data-ws-popup-open]")?.addEventListener("click", (event) => {
      event.stopPropagation();
      if (typeof globalThis.openWorkstationHistoryTab === "function") globalThis.openWorkstationHistoryTab();
      dismiss();
    });
    window.setTimeout(dismiss, AUTO_MS);
    while (stack.children.length > MAX_STACK) {
      stack.firstElementChild?.remove();
    }
  }

  function showNativeBalloon(item) {
    if (typeof DesktopBridge === "undefined" || !DesktopBridge.showWorkstationMessagePopup) return;
    DesktopBridge.showWorkstationMessagePopup({
      id: item.id || "",
      from: item.from || "Office",
      text: String(item.text || ""),
      target: targetsLabel(item),
    }).catch(() => {});
  }

  function present(item) {
    showToast(item);
    showNativeBalloon(item);
    // Same HAL neural voice as program/SideNotes (sender only — never speak message body).
    try {
      const mute =
        window.NR2_WORKSTATION_MUTE_HAL_VOICE === true ||
        (item && item.muteHalVoice === true);
      if (!mute && typeof HalVoice !== "undefined" && HalVoice.announceSidenote) {
        const from = String((item && item.from) || "Office");
        const route = targetsLabel(item);
        const broadcast = /everyone/i.test(route) || /^(all|everyone)$/i.test(String((item && item.target) || ""));
        HalVoice.announceSidenote(from, broadcast);
      }
    } catch (_err) {
      /* ignore TTS failures — popup still shows */
    }
  }

  return { present, targetsLabel, truncate };
})();

if (typeof globalThis !== "undefined") globalThis.WorkstationMessagePopup = WorkstationMessagePopup;
