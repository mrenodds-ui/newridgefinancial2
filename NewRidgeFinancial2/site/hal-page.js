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

  function liveSideNotesHtml(inbox) {
    // Live feed from the SideNotesIM watcher helper (routing metadata only —
    // message bodies are never read). `inbox` is null when the helper is offline.
    const mon = (inbox && inbox.monitor) || {};
    // The inbox file persists after the watcher stops, so treat a stale
    // heartbeat (>45s) as offline rather than trusting mere file existence.
    const checkedMs = mon.checkedAt ? Date.parse(mon.checkedAt) : NaN;
    const fresh = Number.isFinite(checkedMs) && Date.now() - checkedMs < 45000;
    const online = !!(inbox && inbox.monitor) && fresh;
    const items = (inbox && Array.isArray(inbox.items) ? inbox.items : []).slice().reverse();
    const statusBadge = online
      ? '<span class="hp-sn-badge hp-sn-badge--ok">LIVE</span>'
      : '<span class="hp-sn-badge hp-sn-badge--off">OFFLINE</span>';
    const flags = online
      ? `<span class="hp-sn-stat">${mon.announce ? "voice on" : "voice off"} · ${mon.bellSuppressed ? "bell muted" : "bell on"} · station ${esc(mon.station || "—")}${mon.voiceStyle === "hal9000" ? " · HAL 9000 voice" : ""}</span>`
      : '<span class="hp-sn-stat">watcher not running</span>';
    const voiceBtn =
      '<button type="button" class="hp-sn-voice" data-hal-voice-test title="Test HAL 9000 voice" aria-label="Test HAL 9000 voice">◇ TEST VOICE</button>';
    const checked = online && mon.checkedAt ? esc(mon.checkedAt.slice(11, 19)) + " UTC" : "—";
    let listHtml;
    if (!online) {
      listHtml =
        '<li class="hp-sn-empty">SideNotesIM watcher offline. Run <code>run-sidenotes-helper.bat</code> to let HAL announce incoming messages.</li>';
    } else if (!items.length) {
      listHtml = '<li class="hp-sn-empty">No new messages since the watcher started.</li>';
    } else {
      listHtml = items
        .slice(0, 8)
        .map((m) => {
          const kind = m.broadcast
            ? '<span class="hp-sn-tag hp-sn-tag--cast">ALL</span>'
            : '<span class="hp-sn-tag">DM</span>';
          const dot = m.unread ? '<span class="hp-sn-dot" title="unread"></span>' : "";
          const when = esc([m.date, m.time].filter(Boolean).join(" "));
          const sender = m.senderLabel || m.sender || "Unknown";
          const recipient = m.recipientLabel || m.recipient || "—";
          return `<li class="hp-sn-item hp-sn-item--live">
              ${dot}${kind}
              <span class="hp-sn-item__text"><strong>${esc(sender)}</strong> <span class="hp-sn-arrow">→ ${esc(recipient)}</span></span>
              <span class="hp-sn-item__meta">${when}</span>
            </li>`;
        })
        .join("");
    }
    return `<div class="hp-sn-live">
      <div class="hp-sn-head">
        <h4>SIDENOTESIM MONITOR</h4>
        ${statusBadge}
        ${flags}
        ${voiceBtn}
        <span class="hp-sn-time">checked ${checked}</span>
      </div>
      <ul class="hp-sn-list">${listHtml}</ul>
      <p class="hp-sn-foot">HAL 9000 voice announces sender only · message text is never read</p>
    </div>`;
  }

  function sideNotesMonitorHtml(halSideNotes, halSideNoteMonitor, halSideNotesInbox) {
    const notes = halSideNotes || [];
    const mon = halSideNoteMonitor || { activeCount: 0, openCount: 0, pinnedCount: 0, highPriorityCount: 0 };
    const active = notes.filter((n) => n.status !== "archived");
    const changeBadge = mon.hasChanges
      ? '<span class="hp-sn-badge hp-sn-badge--change">CHANGED</span>'
      : '<span class="hp-sn-badge hp-sn-badge--ok">WATCHING</span>';
    const listHtml = active.length
      ? active
          .slice(0, 5)
          .map(
            (n) => `<li class="hp-sn-item hp-sn-item--${esc(n.status)}">
              <span class="hp-sn-item__text">${esc(n.text)}</span>
              <span class="hp-sn-item__meta">${esc(n.priority)}</span>
              <button type="button" class="hp-sn-btn" data-hal-sidenote-pin="${esc(n.noteId)}" title="Pin or unpin" aria-label="Pin or unpin sidenote">${n.status === "pinned" ? "◎" : "○"}</button>
              <button type="button" class="hp-sn-btn hp-sn-btn--dim" data-hal-sidenote-archive="${esc(n.noteId)}" title="Archive" aria-label="Archive sidenote">✕</button>
            </li>`,
          )
          .join("")
      : '<li class="hp-sn-empty">No local notes — add one below or ask HAL.</li>';
    return `<div class="hp-sidenotes-monitor" data-panel="sidenotes">
      ${liveSideNotesHtml(halSideNotesInbox)}
      <div class="hp-sn-head hp-sn-head--local">
        <h4>LOCAL NOTES</h4>
        ${changeBadge}
        <span class="hp-sn-stat">${mon.activeCount || 0} active · ${mon.pinnedCount || 0} pinned</span>
      </div>
      <ul class="hp-sn-list">${listHtml}</ul>
      <form class="hp-sn-form" id="hpSideNoteForm" onsubmit="return false">
        <input class="hp-sn-input" id="hpSideNoteInput" type="text" maxlength="500" placeholder="Quick sidenote — local only, HAL monitors changes" aria-label="Add sidenote" />
        <button type="button" class="hp-sn-add" data-hal-sidenote-add>+ ADD</button>
      </form>
      <p class="hp-sn-foot">Local scratch notes · not submitted · not written to SoftDent</p>
    </div>`;
  }

  function aiStatRow(label, value, ok) {
    return `<div><dt>${esc(label)}</dt><dd${ok ? ' class="hp-ok"' : ""}>${esc(value)}</dd></div>`;
  }

  function aiReadinessHtml(halModels) {
    const rd = halModels && halModels.readinessDisplay;
    if (!rd) return emptyNote("Local AI readiness not configured.");

    const cfg = (halModels && halModels.config) || {};
    const svc = rd.localAiService || {};
    const api = rd.api || {};
    const cm = rd.configuredModels || {};
    const localModel = cm.local || {};
    const reasoningModel = cm.reasoning || {};
    const escalationModel = cm.escalation || {};
    const inventory = rd.availableModels || [];
    const inventoryPreview = inventory.slice(0, 4).join(" · ");
    const inventoryMore = inventory.length > 4 ? ` +${inventory.length - 4} more` : "";
    const runtimes = [cfg.localModel, cfg.reasoningModel, cfg.escalationModel];
    const lanesLive =
      cfg.mode === "online" &&
      cfg.externalCallsEnabled === false &&
      runtimes.every((runtime) => runtime && runtime.enabled && String(runtime.endpoint || "").includes("127.0.0.1"));
    const displayLabel = lanesLive ? "(local only)" : "(display only)";

    return `
      <div class="hp-ai-ready">
        <p class="hp-ai-ready__title">LOCAL AI READINESS <span class="hp-muted">${displayLabel}</span></p>
        <dl class="hp-stats hp-stats--ai">
          ${aiStatRow("LOCAL AI SERVICE", `${svc.status || "Unknown"} · ${svc.name || "—"}`, svc.status === "Detected")}
          ${aiStatRow("OLLAMA API", `${api.status || "Unknown"} · ${api.version || "—"}`, api.status === "Reachable")}
          ${aiStatRow("ACTIVE LANE", rd.activeLane || cfg.activeLane || "—")}
          ${aiStatRow("LOCAL MODEL", `${localModel.model || cfg.localModel?.model || "—"} · ${localModel.available ? "available" : "missing"}`, !!localModel.available)}
          ${aiStatRow("REASONING MODEL", `${reasoningModel.model || "—"} · ${reasoningModel.available ? "available" : "missing"}`, !!reasoningModel.available)}
          ${aiStatRow("ESCALATION MODEL", `${escalationModel.model || "—"} · ${escalationModel.available ? "available" : "missing"}`, !!escalationModel.available)}
          ${aiStatRow("RUNNING MODEL", rd.runningModel || "none")}
          ${aiStatRow("GPU STATUS", rd.gpuStatus || "not verified", rd.gpu && rd.gpu.verified === true)}
          ${aiStatRow("BINDING", rd.bindingStatus || "not verified")}
          ${aiStatRow("LANE EXECUTION", lanesLive ? rd.laneExecution || "Enabled · local loopback only" : "Disabled")}
        </dl>
        <p class="hp-ai-ready__inventory"><b>Available inventory:</b> ${esc(inventoryPreview)}${esc(inventoryMore)} <em class="hp-muted">${lanesLive ? "(routed locally on query)" : "(not routed)"}</em></p>
        <p class="hp-card__foot hp-card__foot--ai">${esc(rd.dataPolicy || "No sensitive raw data sent to any model.")}</p>
      </div>`;
  }

  function render(ctx) {
    const root = ctx.root;
    if (!root) return;
    const { halData, halModels, halAudit, halChatHistory, halAskDraft, halAskLoading, halInlineFirewallResult, halSideNotes, halSideNoteMonitor, halSideNotesInbox } = ctx;
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

    // Manager signals derived from data already in ctx (no backend):
    // priorities/registry for next step + active work, firewall for allowed,
    // and the local audit log for the last local receipt/status.
    const needsReviewCount = tally((s) => s.includes("review"));
    const priorities = (halData.priorities && halData.priorities.items) || [];
    const nextSafeStep =
      priorities[0] || (registry.find((e) => e.nextAction) || {}).nextAction || "Review the Needs Review lane before any external step.";
    const programAccessLabel =
      halData.programAccess?.mode === "full-read"
        ? "Full read · all pages and services (local)"
        : "Registry only";
    const allowedActions = (halData.firewall && halData.firewall.allowed) || [];
    const auditList = halAudit || [];
    const lastReceipt = auditList.length ? auditList[auditList.length - 1] : null;
    const lastReceiptText = lastReceipt
      ? `${lastReceipt.time || ""} · ${lastReceipt.intent || lastReceipt.query || "local action"}`.trim()
      : "No local receipt this session";

    // HAL orb state: color/tempo variants while thinking or on warning.
    // Derived from data already in ctx (no backend, no polling).
    const liveUnread = !!(
      halSideNotesInbox &&
      Array.isArray(halSideNotesInbox.items) &&
      halSideNotesInbox.items.some((m) => m && m.unread)
    );
    const hasWarning =
      blockedCount > 0 ||
      liveUnread ||
      !!(halSideNoteMonitor && (halSideNoteMonitor.hasChanges || halSideNoteMonitor.highPriorityCount > 0)) ||
      !!(halInlineFirewallResult && /block/i.test(halInlineFirewallResult.text || ""));
    const ringState = !halLoaded
      ? "offline"
      : halAskLoading
        ? "thinking"
        : hasWarning
          ? "warning"
          : "ready";
    const ringStateLabel =
      ringState === "thinking"
        ? "THINKING"
        : ringState === "warning"
          ? "ATTENTION"
          : ringState === "offline"
            ? "OFFLINE"
            : "READY";
    const activeLaneModel =
      (halModels?.lanes || []).find((l) => l.id === halModels?.config?.activeLane)?.model ||
      halModels?.config?.localModel?.model ||
      "local";
    const ringTitle = `HAL ${ringStateLabel} · ${readyCount} ready · ${blockedCount} blocked · active lane ${activeLaneModel} · click for reasoning detail`;

    // HUD gauge: ready/blocked arcs around the rim, scaled to the registry.
    const gaugeR = 46;
    const gaugeC = 2 * Math.PI * gaugeR;
    const totalTracked = Math.max(registry.length, 1);
    const readyLen = (readyCount / totalTracked) * gaugeC;
    const blockedLen = (blockedCount / totalTracked) * gaugeC;
    const gaugeSvg = `
      <svg class="hp-ring__gauge" viewBox="0 0 100 100" aria-hidden="true">
        <circle class="hp-ring__gauge-track" cx="50" cy="50" r="${gaugeR}"></circle>
        <circle class="hp-ring__gauge-arc hp-ring__gauge-ready" cx="50" cy="50" r="${gaugeR}" stroke-dasharray="${readyLen.toFixed(2)} ${(gaugeC - readyLen).toFixed(2)}"></circle>
        <circle class="hp-ring__gauge-arc hp-ring__gauge-blocked" cx="50" cy="50" r="${gaugeR}" stroke-dasharray="${blockedLen.toFixed(2)} ${(gaugeC - blockedLen).toFixed(2)}" stroke-dashoffset="${(-readyLen).toFixed(2)}"></circle>
      </svg>`;

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
            <div class="hp-card__head"><h3>ASK HAL</h3><button type="button" class="hp-info" data-hal-drawer="askHal" title="Open Ask HAL detail and command examples" aria-label="Open Ask HAL detail and command examples">i</button></div>
            <form class="hp-ask__box hp-live-form" id="hpAskForm">
              <textarea class="hp-live-input hp-live-textarea" id="hpAskInput" rows="3" enterkeyhint="send" placeholder="Ask HAL anything. Be direct.  (Enter to send · Shift+Enter for a new line)" aria-label="Ask HAL">${esc(halAskDraft || "")}</textarea>
              <div class="hp-ask__bar">
                <span class="hp-ask__mode">MODE</span>
                <span class="hp-ask__sel">${esc(halModels?.config?.mode === "online" ? "Auto" : "Registry only")}</span>
                <span class="hp-ask__hint" aria-hidden="true">↵ Enter to send</span>
                <button class="hp-ask__send hp-live-send" type="submit" ${halAskLoading ? "disabled" : ""}>${halAskLoading ? "…" : "➤ SEND"}</button>
              </div>
            </form>
            <div class="hp-inline-chat">${chatHtml}</div>
            <div class="hp-chips hp-live-actions">${suggestions.map((s) => `<button type="button" class="hp-action" data-hal-suggest="${esc(s)}">${esc(s)}</button>`).join("")}</div>
          </section>
          <section class="hp-card hp-card--reason" data-panel="reasoning" style="grid-area:reason;">
            <div class="hp-card__head"><h3>LOCAL REASONING CORE</h3><button type="button" class="hp-info" data-hal-drawer="reasoning" title="Open reasoning detail: active work session, plan, and evidence packet" aria-label="Open reasoning detail: active work session, plan, and evidence packet">i</button></div>
            <div class="hp-reason">
              <div class="hp-ring hp-ring--${ringState}" data-hal-drawer="reasoning" role="button" tabindex="0" title="${esc(ringTitle)}" aria-label="${esc(ringTitle)}">
                ${gaugeSvg}
                <span class="hp-ring__bezel" aria-hidden="true"></span>
                <span class="hp-ring__radar" aria-hidden="true"></span>
                <div class="hp-ring__lens" aria-hidden="true">
                  <span class="hp-ring__iris"></span>
                  <span class="hp-ring__lens-glow"></span>
                  <span class="hp-ring__lens-hot"></span>
                  <span class="hp-ring__lens-glint"></span>
                  <div class="hp-ring__lens-data">
                    <span class="hp-ring__state">${esc(ringStateLabel)}</span>
                  </div>
                </div>
              </div>
              <dl class="hp-stats">
                <div><dt>STATUS</dt><dd class="${halLoaded ? "hp-ok" : ""}">${esc(halLoaded ? "Active" : "Idle")}</dd></div>
                <div><dt>MODE</dt><dd>${esc(modeLabel)}</dd></div>
                <div><dt>READY</dt><dd class="hp-ok">${esc(readyCount)}</dd></div>
                <div><dt>BLOCKED</dt><dd>${esc(blockedCount)}</dd></div>
              </dl>
            </div>
            ${aiReadinessHtml(halModels)}
            <p class="hp-card__foot">All reasoning stays local. No data leaves this environment.</p>
            <div class="hp-chips">${(halData.reasoning?.actions || []).map((a) => `<button type="button" class="hp-action" data-hal-cmd="${esc(a.command)}">${esc(a.label)}</button>`).join("") || emptyNote("No reasoning actions configured.")}</div>
          </section>
          <section class="hp-card" data-panel="sources" style="grid-area:source;">
            <div class="hp-card__head"><h3>SOURCE INTAKE <span class="hp-muted">(READ-ONLY)</span></h3><button type="button" class="hp-info" data-hal-drawer="sources" title="Open source intake detail" aria-label="Open source intake detail">i</button></div>
            <table class="hp-table"><thead><tr><th>SOURCE</th><th>TYPE</th><th>FRESHNESS</th><th>STATUS</th></tr></thead><tbody>${sourceRows || `<tr><td colspan="4">No sources configured</td></tr>`}</tbody></table>
            <p class="hp-card__foot hp-muted">Freshness shown is local sample data — no live ingestion in this build.</p>
            ${sideNotesMonitorHtml(halSideNotes, halSideNoteMonitor, halSideNotesInbox)}
          </section>
          <section class="hp-card" data-panel="workSurfaces" style="grid-area:staff;">
            <div class="hp-card__head"><h3>STAFF WORK SURFACES</h3><button type="button" class="hp-info" data-hal-drawer="workSurfaces" title="Open staff work surfaces detail" aria-label="Open staff work surfaces detail">i</button></div>
            <ul class="hp-surf">${surfaces || emptyNote("No work surfaces configured.")}</ul>
          </section>
          <section class="hp-card hp-card--fw" data-panel="firewall" style="grid-area:firewall;">
            <div class="hp-card__head"><h3>EXTERNAL ACTION FIREWALL</h3><button type="button" class="hp-info" data-hal-drawer="firewall" title="Open firewall detail: allowed actions, blocked actions, and simulator" aria-label="Open firewall detail: allowed actions, blocked actions, and simulator">i</button></div>
            <p class="hp-fw__active"><span>✓</span> ENFORCED (read-only program)</p>
            <ul class="hp-fw__list">${fwList}</ul>
            <p class="hp-fw__allowed"><b>Allowed (local):</b> ${allowedActions.length ? allowedActions.slice(0, 6).map(esc).join(" · ") : "Open pages · Explain status · Prepare notes"}</p>
            ${halInlineFirewallResult ? `<p class="hp-live-note">${esc(halInlineFirewallResult.text || "")}</p>` : ""}
          </section>
          <section class="hp-card" data-panel="status" style="grid-area:recent;">
            <div class="hp-card__head"><h3>RECENT HAL ACTIVITY</h3><button type="button" class="hp-info" data-hal-drawer="status" title="Open recent activity and local audit log" aria-label="Open recent activity and local audit log">i</button></div>
            <ul class="hp-log">${activityHtml}</ul>
          </section>
          <section class="hp-card" data-panel="priorities" style="grid-area:insights;">
            <div class="hp-card__head"><h3>HAL INSIGHTS</h3><button type="button" class="hp-info" data-hal-drawer="priorities" title="Open priorities, recommendations, and next steps" aria-label="Open priorities, recommendations, and next steps">i</button></div>
            <ul class="hp-insight">
              <li class="hp-insight__lead"><i class="hp-log__dot hp-log__dot--gold" aria-hidden="true"></i><span><b>PROGRAM ACCESS</b> — ${esc(programAccessLabel)} <em class="hp-muted">(writes blocked)</em></span></li>
              <li class="hp-insight__lead"><i class="hp-log__dot hp-log__dot--gold" aria-hidden="true"></i><span><b>NEXT SAFE STEP</b> — ${esc(nextSafeStep)}</span></li>
              <li class="hp-insight__lead"><i class="hp-log__dot hp-log__dot--gold" aria-hidden="true"></i><span><b>ACTIVE WORK</b> — ${esc(needsReviewCount)} in review · ${esc(blockedCount)} blocked <em class="hp-muted">(local registry)</em></span></li>
              ${insights || emptyNote("No registry insights available.")}
            </ul>
          </section>
          <section class="hp-card" data-panel="controls" style="grid-area:controls;">
            <div class="hp-card__head"><h3>SYSTEM CONTROLS</h3><button type="button" class="hp-info" data-hal-drawer="controls" title="Open system controls: readiness, smoke test, and local receipts" aria-label="Open system controls: readiness, smoke test, and local receipts">i</button></div>
            <div class="hp-ctrl">
              <button type="button" class="hp-ctrl__btn" data-hal-cmd="Run readiness check"><span class="hp-ctrl__ico">✓</span><strong>Readiness</strong><span>Local check</span></button>
              <button type="button" class="hp-ctrl__btn" data-hal-cmd="Run operator smoke test"><span class="hp-ctrl__ico">⛉</span><strong>Smoke test</strong><span>Local only</span></button>
              <button type="button" class="hp-ctrl__btn" data-hal-cmd="Staff handoff summary"><span class="hp-ctrl__ico">▤</span><strong>Handoff</strong><span>Build summary</span></button>
              <button type="button" class="hp-ctrl__btn" data-hal-drawer="status"><span class="hp-ctrl__ico">▦</span><strong>Audit log</strong><span>${auditList.length ? esc("Last " + (lastReceipt.time || "—")) : "0 actions"}</span></button>
            </div>
            <p class="hp-card__foot">Last local receipt: ${esc(lastReceiptText)} · receipts stay on this device.</p>
          </section>
        </div>
      </div>`;

    const input = root.querySelector("#hpAskInput");
    if (input && halAskDraft) input.value = halAskDraft;
  }

  return { render, sideNotesMonitorHtml };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalPage;
}
if (typeof window !== "undefined") {
  window.HalPage = HalPage;
}
