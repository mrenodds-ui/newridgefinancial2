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

  function iconsApi() {
    if (typeof AppIcons !== "undefined") return AppIcons;
    if (typeof globalThis !== "undefined" && globalThis.AppIcons) return globalThis.AppIcons;
    if (typeof window !== "undefined" && window.AppIcons) return window.AppIcons;
    return null;
  }

  function uiIcon(key) {
    const api = iconsApi();
    if (!api) return "";
    const icon = api.ui(key);
    return icon ? api.wrap("hp-ico", icon) : "";
  }

  function widgetIcon(key) {
    const api = iconsApi();
    if (!api) return "";
    const icon = api.widget(key);
    return icon ? api.wrap("hp-ico hp-ico--widget", icon) : "";
  }

  function navIcon(pageId) {
    const api = iconsApi();
    if (!api) return "";
    const icon = api.nav(pageId);
    return icon ? api.wrap("hp-ico", icon) : "";
  }

  function cardIconRaw(type, key) {
    const api = iconsApi();
    if (!api) return "";
    if (type === "nav") return api.nav(key) || "";
    if (type === "widget") return api.widget(key) || "";
    if (type === "ui") return api.ui(key) || "";
    if (type === "hal") return api.hal() || "";
    return "";
  }

  function cardIcon(type, key) {
    const icon = cardIconRaw(type, key);
    const api = iconsApi();
    return icon && api ? api.wrap("hp-card__ico", icon) : "";
  }

  function promptIcon(text) {
    const q = String(text || "").toLowerCase();
    if (q.includes("sidenote")) return navIcon("sidenotes");
    if (q.includes("widget") || q.includes("fill all") || q.includes("missing data by widget")) {
      return widgetIcon("officeManagerPriorities");
    }
    if (q.includes("claim")) return navIcon("claims");
    if (q.includes("journal") || q.includes("accounting") || q.includes("reconcil")) return navIcon("documents");
    if (q.includes("import") || q.includes("pull") || q.includes("softdent") || q.includes("quickbooks")) {
      return navIcon("softdent");
    }
    if (q.includes("briefing") || q.includes("attention") || q.includes("plan for today")) {
      return navIcon("office-manager");
    }
    if (q.includes("firewall")) return uiIcon("shield");
    if (q.includes("snapshot") || q.includes("program") || q.includes("blocked") || q.includes("ready")) {
      return cardIcon("hal");
    }
    if (q.includes("task")) return widgetIcon("officeManagerPriorities");
    if (q.includes("library") || q.includes("search") || q.includes("narrative")) return navIcon("narratives");
    if (q.includes("readiness") || q.includes("smoke") || q.includes("handoff")) return uiIcon("check");
    if (q.includes("monitor")) return uiIcon("monitor");
    return uiIcon("send");
  }

  function actionChip(label, attrs) {
    return `<button type="button" class="hp-action hp-action--icon" ${attrs}>${promptIcon(label)}<span class="hp-action__text">${esc(label)}</span></button>`;
  }

  function cardHead(titleHtml, drawerKey, drawerLabel, iconSvg) {
    const iconPart = iconSvg
      ? `<button type="button" class="hp-card__ico hp-card__ico--btn" data-hal-drawer="${esc(drawerKey)}" title="${esc(drawerLabel)}" aria-label="${esc(drawerLabel)}">${iconSvg}</button>`
      : "";
    return `<div class="hp-card__head"><h3>${iconPart}${titleHtml}</h3>${drawerInfoBtn(drawerKey, drawerLabel)}</div>`;
  }

  function surfNavTarget(item) {
    const target = item && item.target;
    if (target === "hal" || target === "sidenotes") return "sidenotes";
    return target || "";
  }

  function surfNavIcon(item) {
    const target = surfNavTarget(item);
    if (target === "sidenotes") return navIcon("sidenotes");
    return navIcon(item && item.target);
  }

  function drawerInfoBtn(panelKey, label) {
    return `<button type="button" class="hp-info" data-hal-drawer="${esc(panelKey)}" title="${esc(label)}" aria-label="${esc(label)}">${uiIcon("info")}<span class="hp-info__label">i</span></button>`;
  }

  function formatStatus(value) {
    return String(value || "unknown")
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());
  }

  // Widget status → friendly staff-surface state.
  function mapSurfaceState(status) {
    if (status === "SUCCESS") return "Ready";
    if (status === "DEGRADED") return "Needs review";
    if (status === "FAILED") return "No data";
    return "unknown";
  }

  function emptyNote(message) {
    return `<p class="hp-live-note">${esc(message)}</p>`;
  }

  function isSideNotesInboxLive(inbox) {
    const mon = inbox && inbox.monitor;
    if (!mon) return false;
    const checkedMs = mon.checkedAt ? Date.parse(mon.checkedAt) : NaN;
    return Number.isFinite(checkedMs) && Date.now() - checkedMs < 45000;
  }

  function stationRosterHtml(inbox) {
    const stations = (inbox && inbox.monitor && inbox.monitor.stations) || [];
    if (!stations.length) {
      return `<p class="hp-sn-empty">No workstation watchers registered yet. Run <code>run-sidenotes-helper.bat</code> on each SideNotesIM PC.</p>`;
    }
    const rows = stations
      .map((station) => {
        const live = station.live === true;
        const badge = live
          ? '<span class="hp-sn-badge hp-sn-badge--ok">LIVE</span>'
          : '<span class="hp-sn-badge hp-sn-badge--off">OFFLINE</span>';
        const flags = [
          station.announce ? "voice" : "silent",
          station.bellSuppressed ? "bell muted" : "bell on",
        ].join(" · ");
        const checked = station.checkedAt ? esc(station.checkedAt.slice(11, 19)) + " UTC" : "—";
        return `<tr>
          <td><strong>${esc(station.station || "—")}</strong></td>
          <td>${badge}</td>
          <td>${esc(flags)}</td>
          <td>${esc(checked)}</td>
        </tr>`;
      })
      .join("");
    return `<div class="hp-sn-stations-wrap">
      <table class="hp-table hp-sn-stations"><thead><tr><th>Station</th><th>Watcher</th><th>Mode</th><th>Checked</th></tr></thead><tbody>${rows}</tbody></table>
    </div>`;
  }

  function sideNotesHubFootnote(hubPath, online) {
    const hub = hubPath ? `<code>${esc(hubPath)}</code>` : "<code>NR2_SIDENOTES_HUB_DATA</code> (not configured)";
    return `<p class="hp-sn-foot">Shared hub: ${hub} · external SideNotesIM helper · routing metadata only · ${online ? "network feed active" : "waiting for watchers"}</p>`;
  }

  function liveSideNotesHtml(inbox) {
    // Live feed from the SideNotesIM watcher helper (routing metadata only —
    // message bodies are never read). `inbox` is null when the helper is offline.
    const mon = (inbox && inbox.monitor) || {};
    const online = isSideNotesInboxLive(inbox);
    const items = (inbox && Array.isArray(inbox.items) ? inbox.items : []).slice().reverse();
    const statusBadge = online
      ? '<span class="hp-sn-badge hp-sn-badge--ok">LIVE</span>'
      : '<span class="hp-sn-badge hp-sn-badge--off">OFFLINE</span>';
    const stationText =
      mon.stationCount && mon.stationCount > 1
        ? `${mon.stationCount}/${mon.totalStations || mon.stationCount} stations live`
        : `station ${mon.station || "—"}`;
    const flags = online
      ? `<span class="hp-sn-stat">${mon.announce ? "voice on" : "voice off"} · ${mon.bellSuppressed ? "bell muted" : "bell on"} · ${esc(stationText)}${mon.voiceStyle === "hal9000" ? " · HAL 9000 voice" : ""}</span>`
      : '<span class="hp-sn-stat">watcher not running</span>';
    const voiceBtn =
      `<button type="button" class="hp-sn-voice" data-hal-voice-test title="Test HAL 9000 voice" aria-label="Test HAL 9000 voice">${uiIcon("voice")} TEST VOICE</button>`;
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
          const source = m.sourceStation ? ` · via ${esc(m.sourceStation)}` : "";
          return `<li class="hp-sn-item hp-sn-item--live">
              ${dot}${kind}
              <span class="hp-sn-item__text"><strong>${esc(sender)}</strong> <span class="hp-sn-arrow">→ ${esc(recipient)}</span></span>
              <span class="hp-sn-item__meta">${when}${source}</span>
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

  function sideNotesMonitorHtml(halSideNotes, halSideNoteMonitor, halSideNotesInbox, hubPath) {
    const notes = Array.isArray(halSideNotes) ? halSideNotes : [];
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
              <button type="button" class="hp-sn-btn" data-hal-sidenote-pin="${esc(n.noteId)}" title="Pin or unpin" aria-label="Pin or unpin sidenote">${n.status === "pinned" ? uiIcon("pin") : uiIcon("unpin")}</button>
              <button type="button" class="hp-sn-btn hp-sn-btn--dim" data-hal-sidenote-archive="${esc(n.noteId)}" title="Archive" aria-label="Archive sidenote">${uiIcon("close")}</button>
            </li>`,
          )
          .join("")
      : '<li class="hp-sn-empty">No local notes — add one below or ask HAL.</li>';
    return `<div class="hp-sidenotes-monitor" data-panel="sidenotes">
      ${liveSideNotesHtml(halSideNotesInbox)}
      <details class="hp-details">
        <summary>Workstation watchers</summary>
        ${stationRosterHtml(halSideNotesInbox)}
      </details>
      <div class="hp-sn-head hp-sn-head--local">
        <h4>LOCAL NOTES</h4>
        ${changeBadge}
        <span class="hp-sn-stat">${mon.activeCount || 0} active · ${mon.pinnedCount || 0} pinned</span>
      </div>
      <ul class="hp-sn-list">${listHtml}</ul>
      <form class="hp-sn-form" id="hpSideNoteForm" onsubmit="return false">
        <input class="hp-sn-input" id="hpSideNoteInput" type="text" maxlength="500" placeholder="Quick sidenote — local only, HAL monitors changes" aria-label="Add sidenote" />
        <button type="button" class="hp-sn-add" data-hal-sidenote-add>${uiIcon("add")} ADD</button>
      </form>
      <div class="hp-chips hp-sn-actions">
        <button type="button" class="hp-action hp-action--icon" data-hal-cmd="Monitor sidenotes">${uiIcon("monitor")} Monitor</button>
        <button type="button" class="hp-action hp-action--icon" data-hal-cmd="Show sidenotes">${navIcon("sidenotes")} Show notes</button>
        <button type="button" class="hp-action hp-action--icon" data-hal-drawer="sidenotes">${uiIcon("info")} Setup</button>
      </div>
      ${sideNotesHubFootnote(hubPath, isSideNotesInboxLive(halSideNotesInbox))}
    </div>`;
  }

  function sideNotesProgramCardHtml(halSideNotes, halSideNoteMonitor, halSideNotesInbox, hubPath) {
    const online = isSideNotesInboxLive(halSideNotesInbox);
    const stationCount = (halSideNotesInbox && halSideNotesInbox.monitor && halSideNotesInbox.monitor.stationCount) || 0;
    const unread = (Array.isArray(halSideNotesInbox && halSideNotesInbox.items) ? halSideNotesInbox.items : []).filter(
      (m) => m && m.unread,
    ).length;
    const statusChip = online
      ? `<span class="hp-sn-badge hp-sn-badge--ok">${stationCount > 1 ? stationCount + " STATIONS" : "LIVE"}</span>`
      : '<span class="hp-sn-badge hp-sn-badge--off">WATCHERS OFFLINE</span>';
    return `<section class="hp-card hp-card--sidenotes" data-panel="sidenotes" style="grid-area:sidenotes;">
      ${cardHead(
        `SIDENOTES PROGRAM <span class="hp-muted">(SIDENOTESIM · EXTERNAL)</span>`,
        "sidenotes",
        "Open SideNotes program setup and station detail",
        cardIconRaw("nav", "sidenotes"),
      )}
      <div class="hp-sn-head__tools hp-sn-head__tools--card">${statusChip}${unread ? `<span class="hp-sn-badge hp-sn-badge--change">${unread} UNREAD</span>` : ""}</div>
      <div class="hp-sidenotes-program">${sideNotesMonitorHtml(halSideNotes, halSideNoteMonitor, halSideNotesInbox, hubPath)}</div>
    </section>`;
  }

  function widgetMetricsText(widget) {
    if (typeof HalSkills !== "undefined" && HalSkills.formatWidgetMetrics) {
      return HalSkills.formatWidgetMetrics(widget);
    }
    const metrics = (widget && widget.metrics) || {};
    const pairs = Object.entries(metrics)
      .filter(([, v]) => v !== null && v !== undefined && v !== "")
      .map(([k, v]) => `${k}: ${v}`);
    return pairs.length ? pairs.join(" · ") : "No verified metrics in this snapshot.";
  }

  function widgetStatusClass(status) {
    const s = String(status || "").toUpperCase();
    if (s === "SUCCESS") return "hp-wg-badge--ok";
    if (s === "DEGRADED") return "hp-wg-badge--warn";
    return "hp-wg-badge--off";
  }

  function widgetsMonitorHtml(halWidgetFeed) {
    if (!halWidgetFeed || !halWidgetFeed.widgets) {
      return `<div class="hp-widgets" data-panel="widgets">
        <div class="hp-sn-head"><h4>MANAGER DASHBOARD WIDGETS</h4><span class="hp-sn-badge hp-sn-badge--off">NO FEED</span></div>
        <p class="hp-sn-empty">Widget feed not loaded yet. <button type="button" class="hp-action" data-hal-cmd="Show manager dashboard widgets">Load widgets</button></p>
      </div>`;
    }
    const order =
      typeof HalSkills !== "undefined" && HalSkills.WIDGET_ORDER
        ? HalSkills.WIDGET_ORDER
        : Object.keys(halWidgetFeed.widgets);
    const cards = order
      .map((key) => {
        const w = halWidgetFeed.widgets[key];
        if (!w) return "";
        const nav = w.navTarget || "";
        const widgetCmd = `Explain why the ${w.title} widget shows its current status and what data is missing`;
        return `<article class="hp-wg-card hp-wg-card--active" data-hal-widget-key="${esc(key)}" data-hal-cmd="${esc(widgetCmd)}" title="${esc(widgetCmd)}">
          <div class="hp-wg-head">
            <span class="hp-wg-ico">${widgetIcon(key)}</span>
            <strong>${esc(w.title)}</strong>
            <span class="hp-wg-badge ${widgetStatusClass(w.status)}">${esc(w.status)}</span>
          </div>
          <p class="hp-wg-metrics">${esc(widgetMetricsText(w))}</p>
          <p class="hp-wg-summary">${esc(w.summary)}</p>
          <button type="button" class="hp-wg-open" data-hal-widget-nav="${esc(nav)}">${uiIcon("externalLink")} OPEN PAGE</button>
        </article>`;
      })
      .join("");
    const publish = (halWidgetFeed.jobs && halWidgetFeed.jobs.widgetPublish && halWidgetFeed.jobs.widgetPublish.status) || "—";
    const widgetCount = typeof HalSkills !== "undefined" && HalSkills.WIDGET_ORDER ? HalSkills.WIDGET_ORDER.length : Object.keys(halWidgetFeed.widgets || {}).length;
    return `<div class="hp-widgets" data-panel="widgets">
      <div class="hp-sn-head"><h4>MANAGER DASHBOARD WIDGETS</h4><span class="hp-sn-stat">${widgetCount} widgets · import cache · publish ${esc(publish)}</span></div>
      <div class="hp-wg-grid">${cards}</div>
      <p class="hp-sn-foot">HAL-managed widgets · local only · A/R from verified sources only</p>
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
    const webResearchOn = cfg.webResearch && cfg.webResearch.enabled === true;
    const lanesLive =
      cfg.mode === "online" &&
      cfg.externalCallsEnabled === false &&
      runtimes.every((runtime) => runtime && runtime.enabled && String(runtime.endpoint || "").includes("127.0.0.1"));
    const displayLabel = lanesLive ? (webResearchOn ? "(local models + web research)" : "(local only)") : "(display only)";

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

  function stressTestHtml(st) {
    const s = st || {};
    const total = Number(s.total) || 2000000;
    const processed = Number(s.processed) || 0;
    const pct = total > 0 ? Math.min(100, Math.round((processed / total) * 100)) : 0;
    const running = !!s.running;
    const status = s.status || (running ? "Running" : processed > 0 && !s.failureTotal ? "Pass" : processed > 0 ? "Fail" : "Idle");
    const statusClass = status === "Pass" ? "hp-stress__status--ok" : status === "Fail" ? "hp-stress__status--fail" : running ? "hp-stress__status--run" : "";
    const failures = Array.isArray(s.topFailures) ? s.topFailures : [];
    const failRows = failures.length
      ? failures
          .slice(0, 12)
          .map(
            (f) =>
              `<li><span class="hp-stress__fail-count">${esc(f.count)}×</span> <code>${esc(f.stage)}</code> — ${esc(f.error)}<br><em class="hp-muted">${esc(String(f.example || "").slice(0, 120))}</em></li>`,
          )
          .join("")
      : '<li class="hp-stress__empty">No failures yet.</li>';

    return `<div class="hp-stress" id="hpStressPanel">
      <div class="hp-stress__head">
        <h4>ASK HAL STRESS TEST</h4>
        <span class="hp-stress__status ${statusClass}" id="hpStressStatus">${esc(status)}</span>
      </div>
      <p class="hp-stress__note">Routes, handlers, agent planner, and self-check — no live model calls. Generates questions on the fly so 2M+ runs stay in memory.</p>
      <div class="hp-stress__row">
        <label class="hp-stress__label" for="hpStressCount">Questions</label>
        <input class="hp-stress__input" id="hpStressCount" type="number" min="100" step="1000" value="${esc(total)}" ${running ? "disabled" : ""} />
        <button type="button" class="hp-stress__run" id="hpStressRun" data-hal-stress-run ${running ? "disabled" : ""}>${uiIcon("check")} Run</button>
        <button type="button" class="hp-stress__stop" id="hpStressStop" data-hal-stress-stop ${running ? "" : "disabled"}>${uiIcon("close")} Stop</button>
      </div>
      <div class="hp-stress__bar" aria-hidden="true"><span class="hp-stress__bar-fill" id="hpStressBar" style="width:${pct}%"></span></div>
      <dl class="hp-stress__stats">
        <div><dt>Processed</dt><dd id="hpStressProcessed">${esc(processed.toLocaleString())}</dd></div>
        <div><dt>Total</dt><dd id="hpStressTotal">${esc(total.toLocaleString())}</dd></div>
        <div><dt>Rate</dt><dd id="hpStressRate">${esc(s.rate ? s.rate.toLocaleString() + " q/s" : "—")}</dd></div>
        <div><dt>Failures</dt><dd id="hpStressFailures" class="${s.failureTotal ? "hp-stress__fail-num" : ""}">${esc(String(s.failureTotal || 0))}</dd></div>
        <div><dt>Distinct</dt><dd id="hpStressDistinct">${esc(String(s.distinctFailures || 0))}</dd></div>
        <div><dt>Intents</dt><dd id="hpStressIntents">${esc(String(s.intentCount || "—"))}</dd></div>
      </dl>
      <ul class="hp-stress__failures" id="hpStressFailList">${failRows}</ul>
    </div>`;
  }

  function agentHealthHtml(health, models, inbox) {
    const h = health || {};
    const rd = (models && models.readinessDisplay) || {};
    const inboxLive = inbox && inbox.monitor ? "Live" : "Offline";
    const selfCheckClass = String(h.lastSelfCheck || "").startsWith("pass") || h.lastSelfCheck === "none" ? "hp-ok" : "hp-stress__fail-num";
    return `<div class="hp-agent-health">
      <div class="hp-stress__head">
        <h4>HAL RUNTIME HEALTH</h4>
        <span class="hp-stress__status hp-stress__status--ok">${esc(h.architectureVersion || "hal-agent")}</span>
      </div>
      <dl class="hp-stress__stats">
        <div><dt>Model</dt><dd>${esc((rd.configuredModels && rd.configuredModels.local && rd.configuredModels.local.model) || rd.runningModel || "—")}</dd></div>
        <div><dt>GPU</dt><dd>${esc(rd.gpuStatus || "—")}</dd></div>
        <div><dt>Budget</dt><dd>${esc(h.budget ? `${h.budget.maxTools} tools · ${h.budget.maxRecentTurns} turns` : "—")}</dd></div>
        <div><dt>Last Intent</dt><dd>${esc(h.lastIntent || "—")}</dd></div>
        <div><dt>Self-Check</dt><dd class="${selfCheckClass}">${esc(h.lastSelfCheck || "none")}</dd></div>
        <div><dt>Repairs</dt><dd class="${h.repairCount ? "hp-stress__fail-num" : ""}">${esc(String(h.repairCount || 0))}</dd></div>
        <div><dt>Latency</dt><dd>${esc(h.lastLatencyMs ? h.lastLatencyMs + " ms" : "—")}</dd></div>
        <div><dt>SideNotes</dt><dd>${esc(inboxLive)}</dd></div>
      </dl>
      <p class="hp-card__foot hp-muted">Agent uses cached snapshots, bounded tools, local memory, and self-check before final answers.</p>
    </div>`;
  }

  function canvasHelpers() {
    return {
      esc,
      uiIcon,
      widgetIcon,
      navIcon,
      cardIconRaw,
      cardHead,
      actionChip,
      promptIcon,
      emptyNote,
      sideNotesProgramCardHtml,
      aiReadinessHtml,
      agentHealthHtml,
      stressTestHtml,
      surfNavTarget,
      surfNavIcon,
      mapSurfaceState,
    };
  }

  function render(ctx) {
    const root = ctx.root;
    if (!root) return;
    const { halData, halModels, halWidgetFeed } = ctx;
    const registry = halData.registry || [];
    const tally = (pred) => registry.filter((e) => pred(String(e.state || "").toLowerCase())).length;
    const readyCount = tally((s) => s === "ready");
    const blockedCount = tally((s) => s === "blocked");
    const halLoaded = registry.length > 0;
    const halStatusLabel = halLoaded ? "ONLINE" : "OFFLINE";
    const coreStatusLabel = halLoaded ? "HEALTHY" : "CHECK";
    const now = new Date();
    const importMode =
      (ctx.halProgramSnapshot && ctx.halProgramSnapshot.importBundle && ctx.halProgramSnapshot.importBundle.importMode) ||
      (halWidgetFeed && halWidgetFeed.importMode) ||
      "";
    const directBadge =
      importMode === "direct-first" ? `<span class="pv-badge pv-badge--import">Direct-first</span>` : "";

    const halStatusToolbar = `
            <button type="button" class="hp-status hp-status--btn" data-hal-cmd="What can you do" title="Ask HAL what it can do"><i class="hp-status__dot hp-status__dot--ok" aria-hidden="true"></i>HAL STATUS <b>${esc(halStatusLabel)}</b></button>
            <button type="button" class="hp-status hp-status--btn" data-hal-cmd="Run readiness check" title="Run local readiness check"><i class="hp-status__dot hp-status__dot--ok" aria-hidden="true"></i>LOCAL CORE <b>${esc(coreStatusLabel)}</b></button>
            <button type="button" class="hp-status hp-status--btn hp-status--red" data-hal-cmd="Explain the external action firewall" title="Explain the external action firewall"><i class="hp-status__dot hp-status__dot--red" aria-hidden="true"></i>FIREWALL <b>ACTIVE</b></button>
            ${directBadge}
            <span class="hp-clock"><strong>${esc(now.toISOString().slice(11, 19))} UTC</strong><span>${esc(now.toISOString().slice(0, 10))}</span></span>`;

    const gridClass =
      typeof HalPageCanvas !== "undefined" && HalPageCanvas.gridClassName ? HalPageCanvas.gridClassName() : "hp-grid hp-grid--hal-102";
    const hpGridHtml =
      typeof HalPageCanvas !== "undefined" && HalPageCanvas.render
        ? HalPageCanvas.render(ctx, canvasHelpers())
        : widgetsMonitorHtml(halWidgetFeed);

    const halBodyInner = `<div class="hp-body"><div class="${gridClass}">${hpGridHtml}</div></div>`;
    const halState =
      typeof PageViews !== "undefined" && PageViews.buildPageState
        ? PageViews.buildPageState(halData, "hal", halWidgetFeed, ctx.halProgramSnapshot)
        : { pageId: "hal", halData, halWidgetFeed, programSnapshot: ctx.halProgramSnapshot };
    const PC = typeof PageChrome !== "undefined" ? PageChrome : null;
    if (PC && typeof PC.pageContent === "function") {
      root.innerHTML = `<article class="pv pv--hal pv--app pv--canvas" data-pv-page="hal">${PC.pageContent(halState, halBodyInner, {
        toolbarActions: halStatusToolbar,
        dataBadge: halLoaded
          ? `<span class="pv-badge pv-badge--import">${esc(readyCount)} ready · ${esc(blockedCount)} blocked</span>`
          : `<span class="pv-badge pv-badge--warn">Registry offline</span>`,
      })}</article>`;
      const pilot = typeof HalPilotWidgets !== "undefined" ? HalPilotWidgets : null;
      if (pilot && typeof pilot.init === "function") pilot.init(root);
    } else {
      root.innerHTML = halBodyInner;
    }

    const input = root.querySelector("#hpAskInput");
    if (input && ctx.halAskDraft) input.value = ctx.halAskDraft;
  }

  return { render, sideNotesMonitorHtml, sideNotesProgramCardHtml, widgetsMonitorHtml, isSideNotesInboxLive, surfNavTarget };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalPage;
}
if (typeof window !== "undefined") {
  window.HalPage = HalPage;
}
