/**
 * HAL Command Center — client-side screen renderer (no backend).
 * Values come from hal-manager.json / hal-models.json and session audit log only.
 */
const HalPage = (function () {
  const WORKSTATION_STATIONS = [
    "Frontdesk 1",
    "Frontdesk 2",
    "Office Manager",
    "Room 1",
    "Room 2",
    "Room 3",
    "Room 4",
    "Room 5",
    "Server",
    "Darkroom",
  ];

  function normalizeStationName(value) {
    return String(value || "")
      .replace(/[_-]+/g, " ")
      .trim()
      .toLowerCase()
      .replace(/\s+/g, " ");
  }

  function stationSlug(value) {
    return (
      String(value || "")
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "") || "unknown"
    );
  }

  function buildStationRoster(monitorRows) {
    const rows = Array.isArray(monitorRows) ? monitorRows : [];
    const byName = new Map();
    rows.forEach((row) => {
      if (row && row.station) byName.set(normalizeStationName(row.station), row);
    });
    return WORKSTATION_STATIONS.map((name) => {
      const hit = byName.get(normalizeStationName(name));
      if (hit) return Object.assign({}, hit, { station: name, live: hit.live === true });
      return {
        station: name,
        live: false,
        status: "offline",
        announce: false,
        bellSuppressed: false,
        checkedAt: "",
      };
    });
  }

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
    return icon ? api.wrap("header-icon", icon) : "";
  }

  function widgetIcon(key) {
    const api = iconsApi();
    if (!api) return "";
    const icon = api.widget(key);
    return icon ? api.wrap("header-icon header-icon header-icon--widget", icon) : "";
  }

  function navIcon(pageId) {
    const api = iconsApi();
    if (!api) return "";
    const icon = api.nav(pageId);
    return icon ? api.wrap("header-icon", icon) : "";
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
    return icon && api ? api.wrap("header-icon", icon) : "";
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
    return `<button type="button" class="prompt-chip prompt-chip--icon" ${attrs}>${promptIcon(label)}<span class="prompt-chip-label">${esc(label)}</span></button>`;
  }

  function cardHead(titleHtml, drawerKey, drawerLabel, iconSvg) {
    const iconPart = iconSvg
      ? `<button type="button" class="header-icon header-icon--btn" data-hal-drawer="${esc(drawerKey)}" title="${esc(drawerLabel)}" aria-label="${esc(drawerLabel)}">${iconSvg}</button>`
      : "";
    return `<div class="widget-header"><span class="widget-title">${iconPart}${titleHtml}</span>${drawerInfoBtn(drawerKey, drawerLabel)}</div>`;
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
    return `<button type="button" class="info-btn" data-hal-drawer="${esc(panelKey)}" title="${esc(label)}" aria-label="${esc(label)}">${uiIcon("info")}<span class="info-btn__label">i</span></button>`;
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
    return `<p class="session-note">${esc(message)}</p>`;
  }

  function isSideNotesInboxLive(inbox) {
    const mon = inbox && inbox.monitor;
    if (!mon) return false;
    const checkedMs = mon.checkedAt ? Date.parse(mon.checkedAt) : NaN;
    return Number.isFinite(checkedMs) && Date.now() - checkedMs < 45000;
  }

  function staffFacingMode(opts) {
    return !!(opts && (opts.staffFacing || opts.hideDiagnostics));
  }

  function stationRosterHtml(inbox, opts) {
    const staff = staffFacingMode(opts);
    const monitorRows = (inbox && inbox.monitor && inbox.monitor.stations) || [];
    const stations = buildStationRoster(monitorRows);
    const rows = stations
      .map((station) => {
        const live = station.live === true;
        const badge = live
          ? '<span class="sidenote-badge sidenote-badge--ok">LIVE</span>'
          : '<span class="sidenote-badge sidenote-badge--off">OFFLINE</span>';
        const checked = station.checkedAt ? esc(station.checkedAt.slice(11, 19)) : "—";
        if (staff) {
          return `<tr>
          <td><strong>${esc(station.station || "—")}</strong></td>
          <td>${badge}</td>
          <td>${esc(checked)}</td>
        </tr>`;
        }
        const flags = station.live
          ? [
              station.nr2Workstation || String(station.source || "").startsWith("nr2")
                ? "NR2 workstation"
                : station.announce
                  ? "SideNotes voice"
                  : "SideNotes silent",
              station.announce ? "voice" : "silent",
              station.bellSuppressed ? "bell muted" : "bell on",
            ]
              .filter((v, i, arr) => arr.indexOf(v) === i)
              .join(" · ")
          : "awaiting client";
        const checkedUtc = station.checkedAt ? esc(station.checkedAt.slice(11, 19)) + " UTC" : "—";
        return `<tr>
          <td><strong>${esc(station.station || "—")}</strong></td>
          <td>${badge}</td>
          <td>${esc(flags)}</td>
          <td>${esc(checkedUtc)}</td>
        </tr>`;
      })
      .join("");
    const head = staff
      ? "<thead><tr><th>Station</th><th>Status</th><th>Last seen</th></tr></thead>"
      : "<thead><tr><th>Station</th><th>Watcher</th><th>Mode</th><th>Checked</th></tr></thead>";
    return `<div class="sidenote-stations-wrap">
      <table class="data-table sidenote-stations-table">${head}<tbody>${rows}</tbody></table>
    </div>`;
  }

  function sideNotesImIntegration(opts) {
    if (opts && Object.prototype.hasOwnProperty.call(opts, "sideNotesIm")) return !!opts.sideNotesIm;
    return typeof globalThis !== "undefined" && !!globalThis.NR2_WORKSTATION_ONLY;
  }

  function sideNotesHubFootnote(hubPath, online) {
    const hub = hubPath ? `<code>${esc(hubPath)}</code>` : "<code>NR2_SIDENOTES_HUB_DATA</code> (not configured)";
    return `<p class="sidenote-foot">Shared hub: ${hub} · external SideNotesIM helper · routing metadata only · ${online ? "network feed active" : "waiting for watchers"}</p>`;
  }

  function liveSideNotesHtml(inbox, opts) {
    const staff = staffFacingMode(opts);
    const mon = (inbox && inbox.monitor) || {};
    const online = isSideNotesInboxLive(inbox);
    const items = (inbox && Array.isArray(inbox.items) ? inbox.items : []).slice().reverse();
    const statusBadge = online
      ? '<span class="sidenote-badge sidenote-badge--ok badge-live">LIVE</span>'
      : '<span class="sidenote-badge sidenote-badge--off badge-offline">OFFLINE</span>';
    const totalStations = mon.totalStations || WORKSTATION_STATIONS.length;
    const liveCount = mon.stationCount != null ? mon.stationCount : 0;
    const stationText =
      totalStations > 1
        ? staff
          ? `${liveCount} of ${totalStations} workstations`
          : `${liveCount}/${totalStations} stations live`
        : `station ${mon.station || "—"}`;
    const flags = online
      ? `<span class="sidenote-stat">${staff ? esc(stationText) : `${mon.announce ? "voice on" : "voice off"} · ${mon.bellSuppressed ? "bell muted" : "bell on"} · ${esc(stationText)}${mon.voiceStyle === "hal9000" ? " · HAL 9000 voice" : ""}`}</span>`
      : staff
        ? '<span class="sidenote-stat">Not connected</span>'
        : '<span class="sidenote-stat">watcher not running</span>';
    const voiceBtn = staff
      ? ""
      : `<button type="button" class="sidenote-voice-btn" data-hal-voice-test title="Test HAL voice (neural TTS)" aria-label="Test HAL voice">${uiIcon("voice")} TEST VOICE</button>`;
    const checked = online && mon.checkedAt ? esc(mon.checkedAt.slice(11, 19)) + (staff ? "" : " UTC") : "";
    const checkedHtml = checked && !staff ? `<span class="sidenote-time">checked ${checked}</span>` : "";
    let listHtml;
    if (!online) {
      listHtml = staff
        ? '<li class="sidenote-empty">SideNotesIM watcher offline on this PC. Open SideNotesIM to read message text.</li>'
        : '<li class="sidenote-empty">SideNotesIM watcher offline. Run <code>run-sidenotes-helper.bat</code> to let HAL announce incoming messages.</li>';
    } else if (!items.length) {
      listHtml = '<li class="sidenote-empty">No new messages.</li>';
    } else {
      listHtml = items
        .slice(0, 8)
        .map((m) => {
          const kind = m.broadcast
            ? '<span class="sidenote-tag sidenote-tag sidenote-tag--cast">ALL</span>'
            : '<span class="sidenote-tag">DM</span>';
          const dot = m.unread ? '<span class="sidenote-dot" title="unread"></span>' : "";
          const when = esc([m.date, m.time].filter(Boolean).join(" "));
          const sender = m.senderLabel || m.sender || "Unknown";
          const recipient = m.recipientLabel || m.recipient || "—";
          const source = !staff && m.sourceStation ? ` · via ${esc(m.sourceStation)}` : "";
          return `<li class="sidenote-item sidenote-item--live">
              ${dot}${kind}
              <span class="sidenote-item__text"><strong>${esc(sender)}</strong> <span class="sidenote-arrow">→ ${esc(recipient)}</span></span>
              <span class="sidenote-item__meta">${when}${source}</span>
            </li>`;
        })
        .join("");
    }
    const title = staff ? "SIDENOTESIM ALERTS" : "SIDENOTESIM MONITOR";
    const footnote = staff
      ? '<p class="sidenote-foot ws-feed-note">Routing only — open SideNotesIM to read message text. HAL announces the sender name only.</p>'
      : '<p class="sidenote-foot">HAL voice (neural) announces sender only · message text is never read</p>';
    return `<div class="sidenote-live">
      <div class="sidenote-head">
        <h4>${title}</h4>
        ${hubBroadcastBadgeHtml()}
        ${statusBadge}
        ${flags}
        ${voiceBtn}
        ${checkedHtml}
      </div>
      <ul class="sidenote-list">${listHtml}</ul>
      ${footnote}
    </div>`;
  }

  function hubBroadcastBadgeHtml() {
    const hub = typeof window !== "undefined" && window.__NR2_HUB_BROADCAST;
    if (!hub || !hub.at) return "";
    const from = hub.from ? String(hub.from) : "office";
    return `<span class="sidenote-badge sidenote-badge--change sidenote-badge--hub-broadcast" title="Office broadcast from ${esc(from)}">OFFICE BROADCAST</span>`;
  }

  function sideNotesMonitorHtml(halSideNotes, halSideNoteMonitor, halSideNotesInbox, hubPath, opts) {
    const expandWatchers = !!(opts && opts.expandWatchers);
    const staff = staffFacingMode(opts);
    const showSideNotesIm = sideNotesImIntegration(opts);
    const notes = Array.isArray(halSideNotes) ? halSideNotes : [];
    const mon = halSideNoteMonitor || { activeCount: 0, openCount: 0, pinnedCount: 0, highPriorityCount: 0 };
    const active = notes.filter((n) => n.status !== "archived");
    const changeBadge = mon.hasChanges
      ? '<span class="sidenote-badge sidenote-badge--change">CHANGED</span>'
      : '<span class="sidenote-badge sidenote-badge--ok">WATCHING</span>';
    const listHtml = active.length
      ? active
          .slice(0, 5)
          .map(
            (n) => `<li class="sidenote-item sidenote-item--${esc(n.status)}">
              <span class="sidenote-item__text">${esc(n.text)}</span>
              <span class="sidenote-item__meta">${esc(n.priority)}</span>
              <button type="button" class="sidenote-btn" data-hal-sidenote-pin="${esc(n.noteId)}" title="Pin or unpin" aria-label="Pin or unpin sidenote">${n.status === "pinned" ? uiIcon("pin") : uiIcon("unpin")}</button>
              <button type="button" class="sidenote-btn sidenote-btn sidenote-btn--dim" data-hal-sidenote-archive="${esc(n.noteId)}" title="Archive" aria-label="Archive sidenote">${uiIcon("close")}</button>
            </li>`,
          )
          .join("")
      : '<li class="sidenote-empty">No local notes — add one below or ask HAL.</li>';
    const hideRoster = staff && opts && opts.hideWorkstationRoster;
    const hideLocalNotes = staff && opts && opts.hideLocalNotes;
    return `<div class="sidenotes-monitor">
      ${showSideNotesIm ? liveSideNotesHtml(halSideNotesInbox, opts) : ""}
      ${
        showSideNotesIm && !hideRoster
          ? `<details class="details-panel"${expandWatchers ? " open" : ""}>
        <summary>${staff ? "Workstations" : `Workstation watchers (${WORKSTATION_STATIONS.length})`}</summary>
        ${stationRosterHtml(halSideNotesInbox, opts)}
      </details>`
          : ""
      }
      ${
        hideLocalNotes
          ? ""
          : `<div class="sidenote-head sidenote-head sidenote-head--local">
        <h4>LOCAL NOTES</h4>
        ${
          staff && opts && opts.stationLabel
            ? `<span class="sidenote-compose-station"><span class="sidenote-badge sidenote-badge--ok">FROM</span> <strong>${esc(opts.stationLabel)}</strong></span>`
            : `${changeBadge}<span class="sidenote-stat">${mon.activeCount || 0} active · ${mon.pinnedCount || 0} pinned</span>`
        }
      </div>
      <ul class="sidenote-list">${listHtml}</ul>
      <form class="sidenote-form" id="hpSideNoteForm" onsubmit="return false">
        <input class="sidenote-input" id="hpSideNoteInput" type="text" maxlength="500" placeholder="${staff ? "Quick note for this station" : "Quick sidenote — local only, HAL monitors changes"}" aria-label="Add sidenote" />
        <button type="button" class="sidenote-add" data-hal-sidenote-add>${uiIcon("add")} ADD</button>
      </form>`
      }
      ${
        staff
          ? ""
          : `<div class="prompt-chips sidenote-actions prompt-chips">
        <button type="button" class="prompt-chip prompt-chip--icon" data-hal-cmd="Monitor sidenotes">${uiIcon("monitor")} Monitor</button>
        <button type="button" class="prompt-chip prompt-chip--icon" data-hal-cmd="Show sidenotes">${navIcon("sidenotes")} Show notes</button>
        ${showSideNotesIm ? `<button type="button" class="prompt-chip prompt-chip--icon" data-hal-drawer="sidenotes">${uiIcon("info")} Setup</button>` : ""}
      </div>
      ${showSideNotesIm ? sideNotesHubFootnote(hubPath, isSideNotesInboxLive(halSideNotesInbox)) : '<p class="sidenote-foot">Local staff notes only — office messaging uses NR2 Workstation, not SideNotesIM.</p>'}`
      }
    </div>`;
  }

  function sideNotesProgramCardHtml(halSideNotes, halSideNoteMonitor, halSideNotesInbox, hubPath) {
    const showSideNotesIm = sideNotesImIntegration();
    const online = isSideNotesInboxLive(halSideNotesInbox);
    const stationCount = (halSideNotesInbox && halSideNotesInbox.monitor && halSideNotesInbox.monitor.stationCount) || 0;
    const totalStations =
      (halSideNotesInbox && halSideNotesInbox.monitor && halSideNotesInbox.monitor.totalStations) ||
      WORKSTATION_STATIONS.length;
    const unread = (Array.isArray(halSideNotesInbox && halSideNotesInbox.items) ? halSideNotesInbox.items : []).filter(
      (m) => m && m.unread,
    ).length;
    const activeNotes = (Array.isArray(halSideNotes) ? halSideNotes : []).filter((n) => n && n.status !== "archived").length;
    const statusChip = showSideNotesIm
      ? online
        ? `<span class="sidenote-badge sidenote-badge--ok">${stationCount}/${totalStations} LIVE</span>`
        : '<span class="sidenote-badge sidenote-badge--off">WATCHERS OFFLINE</span>'
      : `<span class="sidenote-badge sidenote-badge--ok">${activeNotes} LOCAL</span>`;
    const cardTitle = showSideNotesIm
      ? `SIDENOTES PROGRAM <span class="text-muted">(SIDENOTESIM · EXTERNAL)</span>`
      : "STAFF NOTES";
    const cardHint = showSideNotesIm
      ? "Open SideNotes program setup and station detail"
      : "Local HAL scratch notes — use NR2 Workstation for office messaging";
    return `<section class="widget-card hal-panel--sidenotes" data-panel="sidenotes">
      ${cardHead(cardTitle, "sidenotes", cardHint, cardIconRaw("nav", "sidenotes"))}
      <div class="sidenote-head-tools">${statusChip}${showSideNotesIm && unread ? `<span class="sidenote-badge sidenote-badge--change">${unread} UNREAD</span>` : ""}</div>
      <div class="sidenotes-program">${sideNotesMonitorHtml(halSideNotes, halSideNoteMonitor, halSideNotesInbox, hubPath)}</div>
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
    if (s === "SUCCESS") return "status-badge status-badge--ok";
    if (s === "DEGRADED") return "status-badge status-badge--warn";
    return "status-badge status-badge--off";
  }

  function widgetsMonitorHtml(halWidgetFeed) {
    if (!halWidgetFeed || !halWidgetFeed.widgets) {
      return `<div class="widget-monitor" data-panel="widgets">
        <div class="sidenote-head"><h4>MANAGER DASHBOARD WIDGETS</h4><span class="sidenote-badge sidenote-badge--off">NO FEED</span></div>
        <p class="sidenote-empty">Widget feed not loaded yet. <button type="button" class="prompt-chip" data-hal-cmd="Show manager dashboard widgets">Load widgets</button></p>
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
        return `<article class="widget-card span-1" data-hal-widget-key="${esc(key)}" data-hal-cmd="${esc(widgetCmd)}" title="${esc(widgetCmd)}">
          <div class="widget-header"><span class="widget-title">${esc(w.title)}</span></div>
          <div class="metric-large">${esc(widgetMetricsText(w) || w.status)}</div>
          <div class="metric-delta"><span>${esc(w.status)}</span></div>
          <p class="widget-summary">${esc(w.summary)}</p>
          <div class="widget-footer"><button type="button" class="widget-open-btn" data-hal-widget-nav="${esc(nav)}">${uiIcon("externalLink")} OPEN PAGE</button></div>
        </article>`;
      })
      .join("");
    const publish = (halWidgetFeed.jobs && halWidgetFeed.jobs.widgetPublish && halWidgetFeed.jobs.widgetPublish.status) || "—";
    const widgetCount = typeof HalSkills !== "undefined" && HalSkills.WIDGET_ORDER ? HalSkills.WIDGET_ORDER.length : Object.keys(halWidgetFeed.widgets || {}).length;
    return `<div class="widget-monitor" data-panel="widgets">
      <div class="sidenote-head"><h4>MANAGER DASHBOARD WIDGETS</h4><span class="sidenote-stat">${widgetCount} widgets · import cache · publish ${esc(publish)}</span></div>
      <div class="metric-widget-grid">${cards}</div>
      <p class="sidenote-foot">HAL-managed widgets · local only · A/R from verified sources only</p>
    </div>`;
  }

  function aiStatRow(label, value, ok) {
    return `<div><dt>${esc(label)}</dt><dd${ok ? ' class="text-ok"' : ""}>${esc(value)}</dd></div>`;
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
    const configuredKeys = [
      localModel.model,
      escalationModel.model,
      reasoningModel.model,
      cm.helper && cm.helper.model,
      cm.general && cm.general.model,
    ].filter(Boolean);
    const inventoryOrdered = [...new Set([...configuredKeys, ...inventory])];
    const inventoryPreview = inventoryOrdered.slice(0, 8).join(" · ");
    const inventoryMore = inventoryOrdered.length > 8 ? ` +${inventoryOrdered.length - 8} more` : "";
    const runtimes = [cfg.localModel, cfg.reasoningModel, cfg.escalationModel];
    const webResearchOn = cfg.webResearch && cfg.webResearch.enabled === true;
    const cloudCfg = cfg.cloudReasoning || {};
    const cloudKeySet =
      typeof globalThis !== "undefined" &&
      typeof globalThis.getCloudApiKey === "function" &&
      !!globalThis.getCloudApiKey();
    const cloudReady =
      cloudKeySet &&
      cloudCfg.useForAgentLoop !== false &&
      (cloudCfg.enabled === true || cloudCfg.autoEnableWhenKeySet !== false);
    const lanesLive =
      cfg.mode === "online" &&
      cfg.externalCallsEnabled === false &&
      runtimes.every((runtime) => runtime && runtime.enabled && String(runtime.endpoint || "").includes("127.0.0.1"));
    const displayLabel = lanesLive ? (webResearchOn ? "(local models + web research)" : "(local only)") : "(display only)";

    return `
      <div class="ai-readiness-panel">
        <p class="ai-readiness-panel__title">LOCAL AI READINESS <span class="text-muted">${displayLabel}</span></p>
        <dl class="stats-grid stats-grid--ai">
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
          ${aiStatRow("CLOUD AGENT", cloudReady ? (cloudCfg.enabled ? "Ready · key set" : "Ready · complex tasks when key set") : cloudCfg.enabled ? "Enabled · key missing" : "Off · add key for complex tasks", cloudReady)}
        </dl>
        <div class="cloud-key-row text-muted">
          <label for="hal-cloud-key-input">Optional cloud agent key (session):</label>
          <input id="hal-cloud-key-input" type="password" autocomplete="off" placeholder="sk-…" class="input-field input-sm" />
          <label class="inline-check"><input id="hal-cloud-key-persist" type="checkbox" /> Remember locally</label>
          <button type="button" class="action-btn action-btn action-btn--sm" onclick="setCloudApiKeyFromHalPage()">Save key</button>
        </div>
        <p class="ai-readiness-inventory"><b>Available inventory:</b> ${esc(inventoryPreview)}${esc(inventoryMore)} <em class="text-muted">${lanesLive ? "(routed locally on query)" : "(not routed)"}</em></p>
        <p class="widget-footer widget-footer--ai">${esc(rd.dataPolicy || "No sensitive raw data sent to any model.")}</p>
      </div>`;
  }

  function stressTestHtml(st) {
    const s = st || {};
    const total = Number(s.total) || 2000000;
    const processed = Number(s.processed) || 0;
    const pct = total > 0 ? Math.min(100, Math.round((processed / total) * 100)) : 0;
    const running = !!s.running;
    const status = s.status || (running ? "Running" : processed > 0 && !s.failureTotal ? "Pass" : processed > 0 ? "Fail" : "Idle");
    const statusClass = status === "Pass" ? "stress-status stress-status--ok" : status === "Fail" ? "stress-status stress-status--fail" : running ? "stress-status stress-status--run" : "";
    const failures = Array.isArray(s.topFailures) ? s.topFailures : [];
    const failRows = failures.length
      ? failures
          .slice(0, 12)
          .map(
            (f) =>
              `<li><span class="stress-fail-count">${esc(f.count)}×</span> <code>${esc(f.stage)}</code> — ${esc(f.error)}<br><em class="text-muted">${esc(String(f.example || "").slice(0, 120))}</em></li>`,
          )
          .join("")
      : '<li class="stress-empty">No failures yet.</li>';

    return `<div class="stress-panel" id="hpStressPanel">
      <div class="stress-head">
        <h4>ASK HAL STRESS TEST</h4>
        <span class="stress-status ${statusClass}" id="hpStressStatus">${esc(status)}</span>
      </div>
      <p class="stress-note">Routes, handlers, agent planner, and self-check — no live model calls. Generates questions on the fly so 2M+ runs stay in memory.</p>
      <div class="stress-panel__row">
        <label class="stress-label" for="hpStressCount">Questions</label>
        <input class="stress-input" id="hpStressCount" type="number" min="100" step="1000" value="${esc(total)}" ${running ? "disabled" : ""} />
        <button type="button" class="stress-run" id="hpStressRun" data-hal-stress-run ${running ? "disabled" : ""}>${uiIcon("check")} Run</button>
        <button type="button" class="stress-stop" id="hpStressStop" data-hal-stress-stop ${running ? "" : "disabled"}>${uiIcon("close")} Stop</button>
      </div>
      <div class="stress-bar" aria-hidden="true"><span class="stress-bar-fill" id="hpStressBar" style="width:${pct}%"></span></div>
      <dl class="stress-stats">
        <div><dt>Processed</dt><dd id="hpStressProcessed">${esc(processed.toLocaleString())}</dd></div>
        <div><dt>Total</dt><dd id="hpStressTotal">${esc(total.toLocaleString())}</dd></div>
        <div><dt>Rate</dt><dd id="hpStressRate">${esc(s.rate ? s.rate.toLocaleString() + " q/s" : "—")}</dd></div>
        <div><dt>Failures</dt><dd id="hpStressFailures" class="${s.failureTotal ? "stress-fail-num" : ""}">${esc(String(s.failureTotal || 0))}</dd></div>
        <div><dt>Distinct</dt><dd id="hpStressDistinct">${esc(String(s.distinctFailures || 0))}</dd></div>
        <div><dt>Intents</dt><dd id="hpStressIntents">${esc(String(s.intentCount || "—"))}</dd></div>
      </dl>
      <ul class="stress-failures" id="hpStressFailList">${failRows}</ul>
    </div>`;
  }

  function agentHealthHtml(health, models, inbox) {
    const h = health || {};
    const rd = (models && models.readinessDisplay) || {};
    const inboxLive = inbox && inbox.monitor ? "Live" : "Offline";
    const selfCheckClass = String(h.lastSelfCheck || "").startsWith("pass") || h.lastSelfCheck === "none" ? "text-ok" : "stress-fail-num";
    return `<div class="agent-health-panel">
      <div class="stress-head">
        <h4>HAL RUNTIME HEALTH</h4>
        <span class="stress-status stress-status--ok">${esc(h.architectureVersion || "hal-agent")}</span>
      </div>
      <dl class="stress-stats">
        <div><dt>Model</dt><dd>${esc((rd.configuredModels && rd.configuredModels.local && rd.configuredModels.local.model) || rd.runningModel || "—")}</dd></div>
        <div><dt>GPU</dt><dd>${esc(rd.gpuStatus || "—")}</dd></div>
        <div><dt>Budget</dt><dd>${esc(h.budget ? `${h.budget.maxTools} tools · ${h.budget.maxRecentTurns} turns` : "—")}</dd></div>
        <div><dt>Last Intent</dt><dd>${esc(h.lastIntent || "—")}</dd></div>
        <div><dt>Last tools</dt><dd>${esc(Array.isArray(h.lastTools) && h.lastTools.length ? h.lastTools.join(", ") : "—")}</dd></div>
        <div><dt>Self-Check</dt><dd class="${selfCheckClass}">${esc(h.lastSelfCheck || "none")}</dd></div>
        <div><dt>Repairs</dt><dd class="${h.repairCount ? "stress-fail-num" : ""}">${esc(String(h.repairCount || 0))}</dd></div>
        <div><dt>Latency</dt><dd>${esc(h.lastLatencyMs ? h.lastLatencyMs + " ms" : "—")}</dd></div>
        <div><dt>SideNotes</dt><dd>${esc(inboxLive)}</dd></div>
      </dl>
      <p class="widget-footer text-muted">Agent uses cached snapshots, bounded tools, local memory, and self-check before final answers.</p>
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

  function halStatusRing(label, value, pct, tone) {
    const r = 16;
    const c = 2 * Math.PI * r;
    const dash = Math.max(0, Math.min(c, (Number(pct) / 100) * c)).toFixed(2);
    return `<div class="hal-status-ring hal-status-pulse hal-status-ring--${tone} badge-live" data-health-score="${esc(String(pct))}" aria-label="${esc(label)}">
      <svg width="40" height="40" viewBox="0 0 40 40" aria-hidden="true">
        <circle cx="20" cy="20" r="${r}" fill="none" stroke="#333333" stroke-width="3"/>
        <circle cx="20" cy="20" r="${r}" fill="none" stroke="currentColor" stroke-width="3" stroke-dasharray="${dash} ${c.toFixed(2)}" transform="rotate(-90 20 20)"/>
      </svg>
      <span class="hal-status-ring__label">${esc(label)} <b>${esc(value)}</b></span>
    </div>`;
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
      importMode === "direct-first" ? `<span class="header-badge import-badge">Direct-first</span>` : "";

    const health = (halWidgetFeed && halWidgetFeed.sourceHealth) || {};
    const connected = health.connected != null ? health.connected : 0;
    const missing = health.missing != null ? health.missing : 0;
    const partial = health.partial != null ? health.partial : 0;
    const healthTotal = Math.max(1, connected + partial + missing);
    const healthPct = Math.round((connected / healthTotal) * 100);

    const halStatusToolbar = `<div class="hal-status-grid">
            ${halStatusRing("HAL STATUS", halStatusLabel, halLoaded ? 100 : 12, halLoaded ? "green" : "cyan")}
            ${halStatusRing("LOCAL CORE", coreStatusLabel, healthPct, healthPct >= 80 ? "green" : "cyan")}
            <button type="button" class="hal-consent-chip" data-hal-about-me title="HAL speaks your executive partner briefing">ABOUT ME</button>
            <button type="button" class="hal-consent-chip" data-hal-cmd="Explain staff consent policy" title="Consent policy">CONSENT ON</button>
            ${directBadge}
            <span class="header-clock"><strong>${esc(now.toISOString().slice(11, 19))} UTC</strong><span>${esc(now.toISOString().slice(0, 10))}</span></span>
          </div>`;

    const H = canvasHelpers();
    const Canvas = typeof HalPageCanvas !== "undefined" ? HalPageCanvas : null;
    const askHtml = Canvas && Canvas.renderAskHal ? Canvas.renderAskHal(ctx, H) : "";
    const dashHtml = Canvas && Canvas.renderDashboard ? Canvas.renderDashboard(ctx, H) : Canvas ? Canvas.render(ctx, H) : widgetsMonitorHtml(halWidgetFeed);
    const gridClass =
      Canvas && Canvas.gridClassName ? Canvas.gridClassName() : "dashboard-grid";
    const halBodyInner = `<div class="hal-dashboard hal-dashboard--compact hal-cyber-grid"><div class="content-wrapper">
      <div class="${gridClass}">${dashHtml}</div>
      <aside class="chat-rail" aria-label="Ask HAL">${askHtml}</aside>
    </div></div>`;
    const halState =
      typeof PageViews !== "undefined" && PageViews.buildPageState
        ? PageViews.buildPageState(halData, "hal", halWidgetFeed, ctx.halProgramSnapshot)
        : { pageId: "hal", halData, halWidgetFeed, programSnapshot: ctx.halProgramSnapshot };
    const MC = typeof MoonshotMockupChrome !== "undefined" ? MoonshotMockupChrome : null;
    if (MC && typeof MC.pageContent === "function") {
      root.innerHTML = `<article class="ms-page ms-page--hal" data-ms-page="hal">${MC.pageContent(halState, halBodyInner, {
        halToolbar: halStatusToolbar,
      })}</article>`;
      const pilot = typeof HalPilotWidgets !== "undefined" ? HalPilotWidgets : null;
      if (pilot && typeof pilot.init === "function") pilot.init(root);
    } else {
      root.innerHTML = halBodyInner;
    }

    const input = root.querySelector("#hpAskInput");
    if (input && ctx.halAskDraft) input.value = ctx.halAskDraft;
  }

  return {
    render,
    sideNotesMonitorHtml,
    sideNotesProgramCardHtml,
    widgetsMonitorHtml,
    isSideNotesInboxLive,
    surfNavTarget,
    WORKSTATION_STATIONS,
    buildStationRoster,
    stationRosterHtml,
    stationSlug,
    normalizeStationName,
    hubBroadcastBadgeHtml,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalPage;
}
if (typeof window !== "undefined") {
  window.HalPage = HalPage;
}
