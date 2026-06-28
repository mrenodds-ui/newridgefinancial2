/**
 * HAL Command Center — client-side screen renderer (no backend).
 * Values come from hal-manager.json / hal-models.json and session audit log only.
 */
const HalPage = (function () {
  function esc(value) {
    return String(value == null ? "" : value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function formatStatus(value) {
    return String(value || "unknown")
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());
  }

  function mapSourceStatus(item) {
    const sync = String(item.syncState || "").toLowerCase();
    if (sync.includes("blocked")) return "blocked";
    if (sync.includes("pending")) return "pending";
    if (item.warning) return "error";
    return "unknown";
  }

  function emptyNote(message) {
    return `<p class="hp-live-note">${esc(message)}</p>`;
  }

  function render(ctx) {
    const root = ctx.root;
    if (!root) return;
    const { halData, halModels, halAudit, halChatHistory, halAskDraft, halAskLoading, halInlineFirewallResult } = ctx;
    const suggestions = (halData.askHal?.suggestions || []).slice(0, 5);
    const messages = (halChatHistory || []).slice(-4);
    const chatHtml = messages.length
      ? messages
          .map(
            (m) =>
              `<div class="hp-chat-row hp-chat-row--${m.role === "user" ? "user" : "hal"}">
                <span>${m.role === "user" ? "You" : "HAL"}${m.lane ? ` · ${esc(m.lane)}` : ""}</span>
                <p>${esc(m.text)}</p>
              </div>`,
          )
          .join("")
      : emptyNote("No HAL responses yet. Ask a question to begin.");

    const sourceRows = ((halData.sources && halData.sources.items) || [])
      .map((item) => {
        const status = mapSourceStatus(item);
        return `<tr>
          <td>${esc(item.label)}</td>
          <td>${esc(item.status || "unknown")}</td>
          <td>${esc(item.freshness || "Not available")}</td>
          <td>${esc(formatStatus(status))}</td>
        </tr>`;
      })
      .join("");

    const surfaces = ((halData.workSurfaces && halData.workSurfaces.items) || [])
      .map((item) => {
        const reg = (halData.registry || []).find((e) => e.id === item.target);
        const state = reg ? reg.state : "unknown";
        return `<li>
          <span class="hp-surf__ico" aria-hidden="true">◳</span>
          <div class="hp-surf__main"><strong>${esc(item.label)}</strong><span>${esc(item.detail || "")}</span></div>
          <div class="hp-surf__meta">
            <span>State<br><b>${esc(state)}</b></span>
            <span>Updated<br><b>Not available</b></span>
            <span>Items<br><b>—</b></span>
          </div>
        </li>`;
      })
      .join("");

    const activity = (halAudit || []).slice(-5).reverse();
    const activityHtml = activity.length
      ? activity
          .map(
            (row) =>
              `<li><i class="hp-log__dot hp-log__dot--gold" aria-hidden="true"></i><span>${esc(row.query || row.label || "")}</span><time>${esc(row.time || "")}</time></li>`,
          )
          .join("")
      : emptyNote("No HAL activity in this session yet.");

    const insights = (halData.registry || [])
      .filter((e) => e.nextAction)
      .slice(0, 4)
      .map((e) => {
        const conf =
          String(e.state).toLowerCase() === "blocked"
            ? "high"
            : String(e.state).toLowerCase().includes("review")
              ? "medium"
              : "low";
        return `<li><i class="hp-log__dot hp-log__dot--gold" aria-hidden="true"></i><span>${esc(e.name)}: ${esc(e.nextAction)}</span><b class="hp-conf hp-conf--${conf === "high" ? "high" : conf === "medium" ? "med" : "low"}">${esc(conf)} confidence</b></li>`;
      })
      .join("");

    const blocked = (halData.firewall?.blocked || []).slice(0, 5);
    const fwList = blocked.map((item) => `<li><span>${esc(item)}</span><b>BLOCKED</b></li>`).join("");

    const now = new Date();
    const registry = halData.registry || [];
    const tally = (pred) => registry.filter((e) => pred(String(e.state || "").toLowerCase())).length;
    const readyCount = tally((s) => s === "ready");
    const blockedCount = tally((s) => s === "blocked");
    // HAL is a local read-only manager: it is online/healthy whenever its
    // program registry has loaded. Individual lane states are surfaced
    // separately as READY / BLOCKED counts below, not as HAL's own health.
    const halLoaded = registry.length > 0;
    const halStatusLabel = halLoaded ? "ONLINE" : "OFFLINE";
    const coreStatusLabel = halLoaded ? "HEALTHY" : "CHECK";
    const modeLabel = halModels?.config?.mode === "online" ? "Auto" : "Registry-only";

    const toothMark = `
      <svg class="hp-top__tooth" viewBox="0 0 64 64" aria-hidden="true">
        <path d="M20.9 7.8c4.4 0 7.1 2.4 11.1 2.4s6.7-2.4 11.1-2.4c7.8 0 13.2 6.3 13.2 15.1 0 5.4-2.4 10.4-4.7 15.2-2.2 4.6-3.4 9.7-4.4 14.7-.6 3.1-2.5 5.2-5.1 5.2-3.1 0-4.5-2.9-5.6-6.4l-2.1-6.7c-.7-2.3-1.4-3.8-2.4-3.8s-1.7 1.5-2.4 3.8l-2.1 6.7c-1.1 3.5-2.5 6.4-5.6 6.4-2.6 0-4.5-2.1-5.1-5.2-1-5-2.2-10.1-4.4-14.7-2.3-4.8-4.7-9.8-4.7-15.2C7.7 14.1 13.1 7.8 20.9 7.8Z"
          fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
      </svg>`;

    root.innerHTML = `
      <div class="hp-body">
        <header class="hp-top">
          <div class="hp-top__brand">
            <span class="hp-top__mark" aria-hidden="true">${toothMark}</span>
            <div class="hp-top__copy"><strong>HAL COMMAND CENTER</strong><span>Direct. Orchestrate. Protect.</span></div>
          </div>
          <div class="hp-top__status">
            <span class="hp-status"><i class="hp-status__dot hp-status__dot--ok" aria-hidden="true"></i>HAL STATUS <b>${esc(halStatusLabel)}</b></span>
            <span class="hp-status"><i class="hp-status__dot hp-status__dot--ok" aria-hidden="true"></i>LOCAL CORE <b>${esc(coreStatusLabel)}</b></span>
            <span class="hp-status hp-status--red"><i class="hp-status__dot hp-status__dot--red" aria-hidden="true"></i>FIREWALL <b>ACTIVE</b></span>
            <span class="hp-clock"><strong>${esc(now.toISOString().slice(11, 19))} UTC</strong><span>${esc(now.toISOString().slice(0, 10))}</span></span>
          </div>
        </header>
        <div class="hp-grid">
          <section class="hp-card hp-card--ask" data-panel="askHal" style="grid-area:ask;">
            <div class="hp-card__head"><h3>ASK HAL</h3><button type="button" class="hp-info" data-hal-drawer="askHal">i</button></div>
            <form class="hp-ask__box hp-live-form" id="hpAskForm">
              <textarea class="hp-live-input hp-live-textarea" id="hpAskInput" rows="3" placeholder="Ask HAL anything. Be direct." aria-label="Ask HAL">${esc(halAskDraft || "")}</textarea>
              <div class="hp-ask__bar">
                <span class="hp-ask__mode">MODE</span>
                <span class="hp-ask__sel">${esc(halModels?.config?.mode === "online" ? "Auto" : "Registry only")}</span>
                <button class="hp-ask__send hp-live-send" type="submit" ${halAskLoading ? "disabled" : ""}>${halAskLoading ? "…" : "➤ ASK HAL"}</button>
              </div>
            </form>
            <div class="hp-inline-chat">${chatHtml}</div>
            <div class="hp-chips hp-live-actions">${suggestions.map((s) => `<button type="button" class="hp-action" data-hal-suggest="${esc(s)}">${esc(s)}</button>`).join("")}</div>
          </section>
          <section class="hp-card hp-card--reason" data-panel="reasoning" style="grid-area:reason;">
            <div class="hp-card__head"><h3>LOCAL REASONING CORE</h3><button type="button" class="hp-info" data-hal-drawer="reasoning">i</button></div>
            <div class="hp-reason">
              <div class="hp-ring">
                <span class="hp-ring__ico" aria-hidden="true">◈</span>
                <strong>${esc(registry.length)}</strong>
                <span>PROGRAMS TRACKED</span>
              </div>
              <dl class="hp-stats">
                <div><dt>STATUS</dt><dd class="${halLoaded ? "hp-ok" : ""}">${esc(halLoaded ? "Active" : "Idle")}</dd></div>
                <div><dt>MODE</dt><dd>${esc(modeLabel)}</dd></div>
                <div><dt>READY</dt><dd class="hp-ok">${esc(readyCount)}</dd></div>
                <div><dt>BLOCKED</dt><dd>${esc(blockedCount)}</dd></div>
              </dl>
            </div>
            <p class="hp-card__foot">All reasoning stays local. No data leaves this environment.</p>
            <div class="hp-chips">${(halData.reasoning?.actions || []).map((a) => `<button type="button" class="hp-action" data-hal-cmd="${esc(a.command)}">${esc(a.label)}</button>`).join("") || emptyNote("No reasoning actions configured.")}</div>
          </section>
          <section class="hp-card" data-panel="sources" style="grid-area:source;">
            <div class="hp-card__head"><h3>SOURCE INTAKE <span class="hp-muted">(READ-ONLY)</span></h3><button type="button" class="hp-info" data-hal-drawer="sources">i</button></div>
            <table class="hp-table"><thead><tr><th>SOURCE</th><th>TYPE</th><th>FRESHNESS</th><th>STATUS</th></tr></thead><tbody>${sourceRows || `<tr><td colspan="4">No sources configured</td></tr>`}</tbody></table>
          </section>
          <section class="hp-card" data-panel="workSurfaces" style="grid-area:staff;">
            <div class="hp-card__head"><h3>STAFF WORK SURFACES</h3><button type="button" class="hp-info" data-hal-drawer="workSurfaces">i</button></div>
            <ul class="hp-surf">${surfaces || emptyNote("No work surfaces configured.")}</ul>
          </section>
          <section class="hp-card hp-card--fw" data-panel="firewall" style="grid-area:firewall;">
            <div class="hp-card__head"><h3>EXTERNAL ACTION FIREWALL</h3><button type="button" class="hp-info" data-hal-drawer="firewall">i</button></div>
            <p class="hp-fw__active"><span>✓</span> ENFORCED (read-only program)</p>
            <ul class="hp-fw__list">${fwList}</ul>
            ${halInlineFirewallResult ? `<p class="hp-live-note">${esc(halInlineFirewallResult.text || "")}</p>` : ""}
          </section>
          <section class="hp-card" data-panel="status" style="grid-area:recent;">
            <div class="hp-card__head"><h3>RECENT HAL ACTIVITY</h3><button type="button" class="hp-info" data-hal-drawer="status">i</button></div>
            <ul class="hp-log">${activityHtml}</ul>
          </section>
          <section class="hp-card" data-panel="priorities" style="grid-area:insights;">
            <div class="hp-card__head"><h3>HAL INSIGHTS</h3><button type="button" class="hp-info" data-hal-drawer="priorities">i</button></div>
            <ul class="hp-insight">${insights || emptyNote("No registry insights available.")}</ul>
          </section>
          <section class="hp-card" data-panel="controls" style="grid-area:controls;">
            <div class="hp-card__head"><h3>SYSTEM CONTROLS</h3><button type="button" class="hp-info" data-hal-drawer="controls">i</button></div>
            <div class="hp-ctrl">
              <button type="button" class="hp-ctrl__btn" data-hal-cmd="Run readiness check"><span class="hp-ctrl__ico">✓</span><strong>Readiness</strong><span>Local check</span></button>
              <button type="button" class="hp-ctrl__btn" data-hal-cmd="Run operator smoke test"><span class="hp-ctrl__ico">⛉</span><strong>Smoke test</strong><span>Local only</span></button>
              <button type="button" class="hp-ctrl__btn" data-hal-cmd="Staff handoff summary"><span class="hp-ctrl__ico">▤</span><strong>Handoff</strong><span>Build summary</span></button>
              <button type="button" class="hp-ctrl__btn" data-hal-drawer="status"><span class="hp-ctrl__ico">▦</span><strong>Audit log</strong><span>${(halAudit || []).length} actions</span></button>
            </div>
          </section>
        </div>
      </div>`;

    const input = root.querySelector("#hpAskInput");
    if (input && halAskDraft) input.value = halAskDraft;
  }

  return { render };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalPage;
}
if (typeof window !== "undefined") {
  window.HalPage = HalPage;
}
