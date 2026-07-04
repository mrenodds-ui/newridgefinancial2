// NewRidgeFinancial 2.0 — mission-control pages (nav from PageSchema).

function getPages() {
  if (typeof PageSchema !== "undefined" && PageSchema.navPages) {
    return PageSchema.navPages();
  }
  return [{ id: "hal", label: "HAL", title: "HAL Command Center" }];
}

function appPages() {
  return getPages();
}

function defaultPageId() {
  const staff = getPages().find((p) => p.id !== "hal");
  return staff ? staff.id : getPages()[0]?.id || "financial";
}

function resolvePageId(raw) {
  const cleaned = String(raw || "")
    .replace(/^#/, "")
    .split(/[?&]/)[0]
    .trim();
  if (cleaned && getPages().some((p) => p.id === cleaned)) return cleaned;
  return defaultPageId();
}

const FALLBACK_HAL = {
  status: { title: "HAL Command Center", summary: "Local program manager.", posture: ["Local-only", "Read-only"] },
  askHal: { title: "Ask HAL", summary: "Local manager.", suggestions: ["Show priorities"], response: "I can navigate pages and explain status." },
  sources: { title: "Sources", summary: "Read-only.", items: [] },
  reasoning: { title: "Reasoning", summary: "Local lanes.", actions: [] },
  workSurfaces: { title: "Work surfaces", summary: "Open pages.", items: [] },
  firewall: { title: "Firewall", summary: "External-action firewall is off.", blocked: [], allowed: [], examples: [] },
  priorities: { title: "Priorities", items: [] },
  registry: [],
};

const FALLBACK_MODELS = { config: { mode: "offline" }, lanes: [] };

const sidebar = document.getElementById("sidebar");
let nav = document.getElementById("nav");
const appPage = document.getElementById("appPage");
const halPage = document.getElementById("halPage");
const halPageRoot = document.getElementById("halPageRoot");
const drawer = document.getElementById("drawer");
const drawerClose = document.getElementById("drawerClose");
const drawerTitle = document.getElementById("drawerTitle");
const drawerContent = document.getElementById("drawerContent");
const buttons = {};
let halData = FALLBACK_HAL;
let halModels = FALLBACK_MODELS;
let currentDrawerKey = null;
let halChatHistory = [];
let halAudit = [];
let halAskDraft = "";
let halAskLoading = false;
let halModelAbortController = null;
let nr2DesignSchemaVersion = typeof PageSchema !== "undefined" ? PageSchema.SCHEMA_VERSION : null;

function persistLocal(key, value) {
  DesktopBridge.storageSet(key, value).catch(() => {});
}

function isDesktopMode() {
  return Boolean(window.DesktopBridge && DesktopBridge.hasDesktopApi && DesktopBridge.hasDesktopApi());
}

function desktopRequiredMessage(feature) {
  if (window.DesktopBridge && DesktopBridge.desktopRequiredMessage) {
    return DesktopBridge.desktopRequiredMessage(feature);
  }
  return `${feature || "This feature"} requires the NR2 desktop app. Browser mode is a UI preview only.`;
}

function renderRuntimeModeBanner() {
  if (isDesktopMode()) {
    const existing = document.getElementById("runtimeModeBanner");
    if (existing) existing.remove();
    return;
  }
  let banner = document.getElementById("runtimeModeBanner");
  if (!banner) {
    banner = document.createElement("div");
    banner.id = "runtimeModeBanner";
    banner.className = "runtime-banner";
    document.body.prepend(banner);
  }
  banner.innerHTML = `
    <strong>Browser preview mode</strong>
    <span>${escapeHtml(desktopRequiredMessage("Full NR2 data access"))}</span>
  `;
}

function saveChatHistory() {
  persistLocal("halChatHistory", halChatHistory);
}

let halWorkSession = null;

function saveWorkSession() {
  persistLocal("halWorkSession", halWorkSession);
}

// Local office-manager tasks (ported HAL skill). Local-only; HAL reads SoftDent and QuickBooks only.
let halOfficeTasks = [];

function saveOfficeTasks() {
  if (typeof OfficeTaskStore !== "undefined") {
    OfficeTaskStore.save(halOfficeTasks);
    return;
  }
  persistLocal("halOfficeTasks", halOfficeTasks);
}

let halWidgetRefreshInFlight = null;
let sideNoteMonitorTickInFlight = false;
let halLiveWidgetEvents = [];

function invalidateProgramCaches(reason) {
  programContextCache = null;
  const Svc = typeof Services !== "undefined" ? Services : window.Services;
  if (Svc && typeof Svc.invalidateSnapshot === "function") Svc.invalidateSnapshot();
  if (typeof SnapshotStore !== "undefined") SnapshotStore.invalidate(reason || "app");
}

// HAL proactive program assessment (independent local recommendations).
let halProactiveBriefing = null;

async function runHalProactiveCycle(options) {
  if (!window.HalProactive) return null;
  try {
    halProactiveBriefing = await HalProactive.runCycle(buildHalAgentCtx(), options);
    if (halProactiveBriefing) {
      halData.runtime = Object.assign({}, halData.runtime || {}, {
        proactiveBriefing: halProactiveBriefing,
        officeManager: halProactiveBriefing.officeManager || null,
      });
    }
    renderProactiveBanner();
    if (currentDrawerKey === "priorities") renderPanel("priorities");
    return halProactiveBriefing;
  } catch {
    return null;
  }
}

function renderProactiveBanner() {
  if (typeof document === "undefined" || !window.HalProactive) return;
  const pageId = (window.location.hash || "").replace("#", "") || "financial";
  if (typeof PageSchema !== "undefined" && PageSchema.isStaffPage && PageSchema.isStaffPage(pageId)) return;
  const existing = document.getElementById("halProactiveBanner");
  if (existing) existing.remove();
  const briefing = halProactiveBriefing || HalProactive.getLastBriefing();
  if (!HalProactive.shouldSurfaceBanner(briefing)) return;
  const top = briefing.topAction;
  const acted = briefing.placement && briefing.placement.refreshed;
  const banner = document.createElement("div");
  banner.id = "halProactiveBanner";
  banner.className = "proactive-banner";
  const label = acted ? "HAL placed data" : "HAL is fixing";
  const message = acted
    ? briefing.headline || "HAL refreshed imports and placed updated data into dashboards."
    : top
      ? `${top.title} — ${top.rationale}`
      : briefing.headline || "HAL is monitoring program data.";
  banner.innerHTML = `<strong>${escapeHtml(label)}</strong><span>${escapeHtml(message)}</span>`;
  const actions = document.createElement("div");
  actions.className = "proactive-banner__actions";
  if (top && top.action && top.action.type === "navigate" && top.action.target) {
    const openBtn = document.createElement("button");
    openBtn.type = "button";
    openBtn.className = "proactive-banner__btn";
    openBtn.textContent = `Open ${top.action.target}`;
    openBtn.addEventListener("click", () => select(top.action.target));
    actions.appendChild(openBtn);
  }
  const askBtn = document.createElement("button");
  askBtn.type = "button";
  askBtn.className = "proactive-banner__btn proactive-banner__btn--ghost";
  askBtn.textContent = "Ask HAL why";
  askBtn.addEventListener("click", () => {
    openDrawer("askHal");
    setTimeout(() => handleHalSubmit("What should HAL do for the program right now?"), 50);
  });
  actions.appendChild(askBtn);
  banner.appendChild(actions);
  const app = document.querySelector(".app");
  if (app && app.parentNode) app.parentNode.insertBefore(banner, app);
}

function scheduleHalWidgetRefresh(snapshot) {
  if (halWidgetRefreshInFlight) return halWidgetRefreshInFlight;
  halWidgetRefreshInFlight = refreshHalWidgetFeed(snapshot)
    .then(async (feed) => {
      await runHalProactiveCycle();
      renderHalScreen();
      if (currentDrawerKey === "sources") renderPanel("sources");
      const currentId = (window.location.hash || "").replace("#", "") || getPages()[0].id;
      if (currentId !== "hal" && appPage && !appPage.hidden && PageViews && PageViews.hasPage(currentId)) {
        PageViews.renderPageView(appPage, halData, currentId, select, halWidgetFeed, halProgramSnapshot);
      }
      refreshOpsHealthStatus().catch(() => {
        /* ops health optional */
      });
      return feed;
    })
    .finally(() => {
      halWidgetRefreshInFlight = null;
    });
  return halWidgetRefreshInFlight;
}

let halSideNotes = [];
let halSideNoteMonitor = null;
let halSideNoteMonitorTimer = null;
// Live SideNotesIM feed captured by the local watcher helper (routing only).
let halSideNotesInbox = null;
let halSideNotesAnnouncedIds = new Set();
let nr2SidenotesHubPath = null;
// HAL manager dashboard widgets (derived from program snapshot).
let halWidgetFeed = null;
let halProgramSnapshot = null;
let halStressTest = {
  running: false,
  total: 2000000,
  processed: 0,
  failureTotal: 0,
  distinctFailures: 0,
  intentCount: 0,
  rate: 0,
  status: "Idle",
  topFailures: [],
};
let halStressRunner = null;
const SIDENOTE_MONITOR_MS = 8000;
const SIDENOTE_INBOX_FILES = [
  "sidenotes-inbox.json",
  "sidenotes-inbox-server.json",
  "sidenotes-inbox-room-2.json",
  "sidenotes-inbox-room-3.json",
  "sidenotes-inbox-room-4.json",
  "sidenotes-inbox-room-5.json",
  "sidenotes-inbox-frontdesk-1.json",
  "sidenotes-inbox-frontdesk-2.json",
  "sidenotes-inbox-office-manager.json",
];

function saveSideNotes() {
  persistLocal("halSideNotes", halSideNotes);
  invalidateProgramCaches("side-notes");
  refreshSideNoteMonitor({ patchUi: true });
  scheduleHalWidgetRefresh();
}

async function tryReadSideNotesInbox(name) {
  try {
    const data = await DesktopBridge.readDataFile(name);
    return data && Array.isArray(data.items) ? data : null;
  } catch {
    return null;
  }
}

function mergeSideNotesInboxes(inboxes) {
  const valid = inboxes.filter(Boolean);
  if (!valid.length) return null;
  const monitorRows = valid
    .map((inbox) => inbox.monitor || null)
    .filter(Boolean)
    .map((mon) => Object.assign({}, mon, { live: isSideNotesWatcherLive({ monitor: mon }) }));
  const liveRows = monitorRows.filter((mon) => mon.live);
  const itemsByKey = new Map();
  valid.forEach((inbox) => {
    const station = (inbox.monitor && inbox.monitor.station) || "Unknown";
    (inbox.items || []).forEach((item) => {
      if (!item) return;
      const key = `${station}::${item.id || item.rowId || ""}::${item.date || ""}::${item.time || ""}`;
      if (!itemsByKey.has(key)) {
        itemsByKey.set(
          key,
          Object.assign({}, item, {
            sourceStation: item.sourceStation || station,
            announceId: key,
          }),
        );
      }
    });
  });
  const checkedAt = monitorRows
    .map((mon) => mon.checkedAt)
    .filter(Boolean)
    .sort()
    .pop();
  return {
    meta: { schema: "nr2-sidenotes-inbox-v1", source: "SideNotesIM", localOnly: true, merged: true },
    generatedAt: checkedAt || new Date().toISOString(),
    monitor: {
      checkedAt,
      station: liveRows.length > 1 ? "Network" : (liveRows[0] && liveRows[0].station) || (monitorRows[0] && monitorRows[0].station) || "Network",
      status: liveRows.length ? "live" : "offline",
      announce: liveRows.some((mon) => mon.announce),
      bellSuppressed: liveRows.some((mon) => mon.bellSuppressed),
      voiceStyle: (liveRows.find((mon) => mon.voiceStyle) || monitorRows.find((mon) => mon.voiceStyle) || {}).voiceStyle || "",
      duckMusic: liveRows.some((mon) => mon.duckMusic),
      stationCount: liveRows.length,
      totalStations: monitorRows.length,
      stations: monitorRows,
    },
    items: Array.from(itemsByKey.values()).sort((a, b) => {
      const aText = [a.date, a.time, a.rowId].filter(Boolean).join(" ");
      const bText = [b.date, b.time, b.rowId].filter(Boolean).join(" ");
      return aText.localeCompare(bText);
    }),
  };
}

// Read the SideNotesIM inboxes written by workstation watcher helpers. Missing
// station files are expected until that PC has the helper installed/running.
async function loadSideNotesInbox() {
  const inboxes = await Promise.all(SIDENOTE_INBOX_FILES.map(tryReadSideNotesInbox));
  const data = mergeSideNotesInboxes(inboxes);
  halSideNotesInbox = data;
  if (data) maybeAnnounceSideNotesInbox(data);
  return halSideNotesInbox;
}

function isSideNotesWatcherLive(inbox) {
  const mon = inbox && inbox.monitor;
  if (!mon) return false;
  const checkedMs = mon.checkedAt ? Date.parse(mon.checkedAt) : NaN;
  return Number.isFinite(checkedMs) && Date.now() - checkedMs < 45000;
}

function maybeAnnounceSideNotesInbox(inbox) {
  if (!inbox || !Array.isArray(inbox.items) || !window.HalVoice) return;
  const live = isSideNotesWatcherLive(inbox);
  const helperSpeaks = live && inbox.monitor && inbox.monitor.announce;
  // When the watcher is speaking via SAPI, skip browser TTS to avoid doubling up.
  if (helperSpeaks) {
    inbox.items.forEach((m) => {
      if (m && (m.announceId || m.id)) halSideNotesAnnouncedIds.add(m.announceId || m.id);
    });
    return;
  }
  for (const item of inbox.items) {
    const announceId = item && (item.announceId || item.id);
    if (!item || !announceId || halSideNotesAnnouncedIds.has(announceId)) continue;
    halSideNotesAnnouncedIds.add(announceId);
    HalVoice.announceSidenote(item.senderLabel || item.sender, !!item.broadcast);
  }
}

function refreshSideNoteMonitor({ patchUi } = {}) {
  if (!window.HalSkills) return halSideNoteMonitor;
  const prev = halSideNoteMonitor;
  halSideNoteMonitor = HalSkills.buildSideNoteMonitor(halSideNotes, prev);
  persistLocal("halSideNoteMonitor", halSideNoteMonitor);
  if (patchUi && halPageRoot && !halTypeTimer) {
    patchSideNoteMonitorDom();
  }
  return halSideNoteMonitor;
}

function patchSideNoteMonitorDom() {
  if (!halPageRoot || !window.HalPage) return;
  const el = halPageRoot.querySelector(".hp-sidenotes-program");
  if (!el) return;
  el.innerHTML = HalPage.sideNotesMonitorHtml(halSideNotes, halSideNoteMonitor, halSideNotesInbox, nr2SidenotesHubPath);
}

function scrollHalPanelIntoView(panelKey) {
  if (!halPageRoot || !panelKey) return;
  const panel = halPageRoot.querySelector(`[data-panel="${panelKey}"]`);
  if (panel && typeof panel.scrollIntoView === "function") {
    panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}

function isHalPanelTarget(target) {
  return target === "sidenotes";
}

async function activateSideNotesPanel({ scroll } = {}) {
  await loadSideNotesInbox();
  refreshSideNoteMonitor({ patchUi: true });
  if (scroll) scrollHalPanelIntoView("sidenotes");
}

async function runHalPageCmd(cmd, opts) {
  const text = String(cmd || "").trim();
  if (!text) return;
  const openHal = !opts || opts.openHal !== false;
  if (openHal && halPage && halPage.hidden) select("hal");
  await handleHalSubmit(text);
  renderHalScreen();
}

async function handleHalChromeInteraction(event) {
  const widgetNav = event.target.closest("[data-hal-widget-nav]");
  if (widgetNav) {
    const target = widgetNav.getAttribute("data-hal-widget-nav");
    if (target) select(target);
    return true;
  }
  const suggest = event.target.closest("[data-hal-suggest]");
  if (suggest) {
    await runHalPageCmd(suggest.getAttribute("data-hal-suggest"));
    return true;
  }
  const widgetCard = event.target.closest("[data-hal-widget-key]");
  if (widgetCard && !event.target.closest("[data-hal-widget-nav]") && !event.target.closest("[data-hal-action]")) {
    let cmd = widgetCard.getAttribute("data-hal-cmd");
    if (!cmd) {
      const key = widgetCard.getAttribute("data-hal-widget-key");
      if (key) cmd = `Explain ${key} widget on this page`;
    }
    if (cmd) {
      await runHalPageCmd(cmd);
      return true;
    }
  }
  const cmdEl = event.target.closest("[data-hal-cmd]");
  if (cmdEl) {
    await runHalPageCmd(cmdEl.getAttribute("data-hal-cmd"));
    return true;
  }
  return false;
}

function handleHalPageNav(target) {
  if (!target) return;
  if (isHalPanelTarget(target)) {
    activateSideNotesPanel({ scroll: true }).then(() => renderHalScreen());
    return;
  }
  select(target);
}

function handleHalSurfaceNav(target) {
  handleHalPageNav(target);
}

function sideNotesDrawerHtml() {
  const data = (halData && halData.sidenotes) || {};
  const inbox = halSideNotesInbox;
  const online = window.HalPage && HalPage.isSideNotesInboxLive ? HalPage.isSideNotesInboxLive(inbox) : false;
  const steps = (data.setupSteps || [])
    .map((step, index) => `<li>${index + 1}. ${escapeHtml(step)}</li>`)
    .join("");
  const hub = nr2SidenotesHubPath
    ? `<p class="drawer-meta">Hub folder: <code>${escapeHtml(nr2SidenotesHubPath)}</code></p>`
    : `<p class="drawer-meta">Set <code>${escapeHtml(data.hubEnv || "NR2_SIDENOTES_HUB_DATA")}</code> to the shared workstation data folder.</p>`;
  const stations = (inbox && inbox.monitor && inbox.monitor.stations) || [];
  const stationRows = stations.length
    ? stations
        .map(
          (station) =>
            `<tr><td>${escapeHtml(station.station || "—")}</td><td>${station.live ? "live" : "offline"}</td><td>${escapeHtml(station.checkedAt || "—")}</td></tr>`,
        )
        .join("")
    : `<tr><td colspan="3">No watchers yet</td></tr>`;
  const feed = ((inbox && inbox.items) || [])
    .slice(-8)
    .reverse()
    .map(
      (item) =>
        `<li>${escapeHtml(item.senderLabel || item.sender || "Unknown")} → ${escapeHtml(item.recipientLabel || item.recipient || "—")} · ${escapeHtml([item.date, item.time].filter(Boolean).join(" "))}</li>`,
    )
    .join("");
  const localNotes = (halSideNotes || [])
    .filter((n) => n.status !== "archived")
    .slice(0, 8)
    .map((n) => `<li>${escapeHtml(n.text)} <em>(${escapeHtml(n.priority)})</em></li>`)
    .join("");
  const commands = ["Monitor sidenotes", "Show sidenotes", "Add sidenote: follow up on hygiene recall"]
    .map((cmd) => `<button class="drawer-action drawer-action--sm" type="button" data-hal-command="${escapeHtml(cmd)}">${escapeHtml(cmd)}</button>`)
    .join("");
  return `
    <p>${escapeHtml(data.summary || "SideNotesIM external program integration.")}</p>
    ${hub}
    <p class="drawer-meta">Helper: <code>${escapeHtml(data.helperPath || "sidenotes-helper/run-sidenotes-helper.bat")}</code> · network status: <strong>${online ? "live" : "offline"}</strong></p>
    <div class="drawer-section">
      <h3 class="drawer-section__title">Workstation setup</h3>
      <ol class="drawer-checklist drawer-checklist--ordered">${steps || "<li>See sidenotes-helper/README.md</li>"}</ol>
    </div>
    <div class="drawer-section">
      <h3 class="drawer-section__title">Station watchers</h3>
      <table class="hp-table hp-sn-stations"><thead><tr><th>Station</th><th>Status</th><th>Checked</th></tr></thead><tbody>${stationRows}</tbody></table>
    </div>
    <div class="drawer-section">
      <h3 class="drawer-section__title">Recent SideNotesIM routing</h3>
      <ul class="drawer-checklist">${feed || "<li>No messages in merged inbox yet.</li>"}</ul>
    </div>
    <div class="drawer-section">
      <h3 class="drawer-section__title">Local HAL notes</h3>
      <ul class="drawer-checklist">${localNotes || "<li>No local notes yet.</li>"}</ul>
    </div>
    <div class="drawer-section">
      <h3 class="drawer-section__title">HAL commands</h3>
      <div class="drawer-grid">${commands}</div>
    </div>`;
}

function startSideNoteMonitor() {
  if (halSideNoteMonitorTimer) return;
  refreshSideNoteMonitor();
  loadSideNotesInbox().then(() => patchSideNoteMonitorDom());
  // HAL watches sidenotes app-wide — the loop keeps running regardless of which
  // page is on screen, so monitoring continues with the panel not visible. It
  // only patches the DOM when the HAL panel happens to be mounted. (No backend:
  // this cannot run while the app is fully closed; HAL re-checks on next open.)
  halSideNoteMonitorTimer = setInterval(async () => {
    if (sideNoteMonitorTickInFlight) return;
    sideNoteMonitorTickInFlight = true;
    try {
      await loadSideNotesInbox();
      refreshSideNoteMonitor({ patchUi: true });
    } finally {
      sideNoteMonitorTickInFlight = false;
    }
  }, SIDENOTE_MONITOR_MS);
}

function stopSideNoteMonitor() {
  if (!halSideNoteMonitorTimer) return;
  clearInterval(halSideNoteMonitorTimer);
  halSideNoteMonitorTimer = null;
}

let documentSyncListenerBound = false;
let documentSourceRefreshTimer = null;
const DOCUMENT_SOURCE_REFRESH_MS = 30 * 60 * 1000;
let importCoordinatorRefreshTimer = null;
const IMPORT_COORDINATOR_REFRESH_MS = 15 * 60 * 1000;

function startDocumentSyncListener() {
  if (documentSyncListenerBound || typeof window === "undefined") return;
  documentSyncListenerBound = true;
  window.addEventListener("nr2:documents-synced", () => {
    invalidateProgramCaches("documents-synced");
    scheduleHalWidgetRefresh();
  });
}

function startDocumentSourceRefreshTimer() {
  if (documentSourceRefreshTimer || typeof window === "undefined") return;
  if (!window.Services || typeof Services.documents?.list !== "function") return;
  documentSourceRefreshTimer = setInterval(() => {
    Services.documents.list({}).catch(() => {
      /* background document sync optional */
    });
  }, DOCUMENT_SOURCE_REFRESH_MS);
}

function startImportCoordinatorRefreshTimer() {
  if (importCoordinatorRefreshTimer || typeof window === "undefined") return;
  importCoordinatorRefreshTimer = setInterval(() => {
    if (typeof ImportCoordinator !== "undefined") {
      ImportCoordinator.refresh({ reason: "scheduled" }).catch(() => {
        /* scheduled import refresh optional */
      });
      return;
    }
    refreshImportsInBackground();
  }, IMPORT_COORDINATOR_REFRESH_MS);
}

function addSideNote(text) {
  const trimmed = String(text || "").trim();
  if (trimmed.length < 2) return null;
  const note = HalSkills.createSideNote({ text: trimmed });
  halSideNotes.unshift(note);
  saveSideNotes();
  return note;
}

function startWorkSession(sessionId) {
  const template = HalCore.sessionTemplateById(halData, sessionId);
  if (!template) return false;
  halWorkSession = HalCore.createSessionState(template);
  saveWorkSession();
  logAudit("Start " + template.label, "session: start:" + sessionId);
  return true;
}

function resetWorkSession() {
  halWorkSession = null;
  clearEvidencePacket();
  saveWorkSession();
  logAudit("Reset work session", "session: reset");
}

function toggleWorkSessionCheck(checkId) {
  if (!halWorkSession) return;
  halWorkSession = HalCore.toggleSessionCheck(halWorkSession, Number(checkId));
  saveWorkSession();
  logAudit("Toggle check " + checkId, "session: check");
}

function workSessionStatusText() {
  if (!halWorkSession) return "No active work session.";
  const progress = HalCore.sessionProgress(halWorkSession);
  const pending = halWorkSession.checklist.filter((c) => !c.done).length;
  return (
    "Active: " +
    halWorkSession.label +
    " (" +
    progress +
    "% complete, " +
    pending +
    " checks remaining). Safety: " +
    halWorkSession.safety
  );
}

function workSessionPanelHtml() {
  const ws = halData.workSessions || { summary: "", templates: [] };
  if (halWorkSession) {
    const progress = HalCore.sessionProgress(halWorkSession);
    const checks = halWorkSession.checklist
      .map(
        (item) =>
          `<button class="hal-session__check${item.done ? " hal-session__check--done" : ""}" type="button" data-session-toggle="${item.id}">
            <span class="hal-session__box">${item.done ? "✓" : ""}</span>
            <span>${escapeHtml(item.text)}</span>
          </button>`,
      )
      .join("");
    const verify = (halWorkSession.verify || []).map((v) => `<li>${escapeHtml(v)}</li>`).join("");
    const handoff = halWorkSession.handoffNote
      ? `<pre class="hal-session__note">${escapeHtml(halWorkSession.handoffNote)}</pre>`
      : "";
    return `<div class="drawer-section hal-session">
      <h3 class="drawer-section__title">Active work session</h3>
      <p class="drawer-meta">${escapeHtml(halWorkSession.purpose)}</p>
      <p class="drawer-meta">Progress: ${progress}% · ${escapeHtml(halWorkSession.safety)}</p>
      <div class="hal-session__checks">${checks}</div>
      ${verify ? `<ul class="drawer-checklist"><strong>Human must verify:</strong>${verify}</ul>` : ""}
      ${handoff}
      <div class="drawer-card__actions">
        <button class="drawer-action drawer-action--sm" type="button" data-session-handoff>Draft handoff note</button>
        <button class="drawer-action drawer-action--sm" type="button" data-open-page="${escapeHtml(halWorkSession.targetPage)}">Open page</button>
        <button class="drawer-action drawer-action--sm" type="button" data-session-reset>Reset session</button>
      </div>
    </div>`;
  }
  const starters = (ws.templates || [])
    .map(
      (t) =>
        `<button class="drawer-action" type="button" data-session-start="${escapeHtml(t.id)}">${escapeHtml(t.command)}</button>`,
    )
    .join("");
  return `<div class="drawer-section hal-session">
    <h3 class="drawer-section__title">Work sessions</h3>
    <p class="drawer-meta">${escapeHtml(ws.summary || "Start a read-only guided checklist.")}</p>
    <div class="drawer-grid">${starters}</div>
  </div>`;
}

function bindWorkSessionControls(root) {
  root.querySelectorAll("[data-session-start]").forEach((button) => {
    button.addEventListener("click", () => {
      const id = button.dataset.sessionStart;
      if (startWorkSession(id)) {
        if (currentDrawerKey) renderPanel(currentDrawerKey);
        else openDrawer("askHal");
      }
    });
  });
  root.querySelectorAll("[data-session-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      toggleWorkSessionCheck(button.dataset.sessionToggle);
      if (currentDrawerKey) renderPanel(currentDrawerKey);
    });
  });
  root.querySelectorAll("[data-session-reset]").forEach((button) => {
    button.addEventListener("click", () => {
      resetWorkSession();
      if (currentDrawerKey) renderPanel(currentDrawerKey);
    });
  });
  root.querySelectorAll("[data-session-handoff]").forEach((button) => {
    button.addEventListener("click", () => {
      if (!halWorkSession) return;
      halWorkSession.handoffNote = HalCore.draftHandoffNote(halWorkSession, halData);
      saveWorkSession();
      logAudit("Draft handoff", "session: handoff");
      if (currentDrawerKey === "askHal") {
        halChatHistory.push({ role: "hal", text: halWorkSession.handoffNote, lane: "session", actions: [] });
        saveChatHistory();
        renderChatLog();
      }
      if (currentDrawerKey) renderPanel(currentDrawerKey);
    });
  });
}

let halEvidencePacket = null;

function loadEvidencePacket() {
  try {
    const saved = sessionStorage.getItem("halEvidencePacket");
    if (saved) halEvidencePacket = JSON.parse(saved);
  } catch (error) {
    halEvidencePacket = null;
  }
}

function saveEvidencePacket() {
  try {
    persistLocal("halEvidencePacket", halEvidencePacket);
  } catch (error) {
    /* sessionStorage may be unavailable. */
  }
}

function buildEvidencePacketFromSession() {
  if (!halWorkSession) return null;
  halEvidencePacket = HalCore.buildEvidencePacket(halWorkSession, halData, halModels);
  saveEvidencePacket();
  if (halEvidencePacket) logAudit("Build evidence packet", "packet: build");
  return halEvidencePacket;
}

function clearEvidencePacket() {
  halEvidencePacket = null;
  saveEvidencePacket();
  logAudit("Clear evidence packet", "packet: clear");
}

function evidencePacketPanelHtml() {
  const ep = halData.evidencePackets || { summary: "", commands: {} };
  const packetBody = halEvidencePacket
    ? `<pre class="hal-packet__body" id="halPacketBody">${escapeHtml(halEvidencePacket.text)}</pre>`
    : `<p class="drawer-meta">No evidence packet built yet.${halWorkSession ? " Click Build Packet to assemble one from the active session." : " Start a work session first."}</p>`;
  const buildDisabled = halWorkSession ? "" : " disabled";
  const actionBtns = halEvidencePacket
    ? `<button class="drawer-action drawer-action--sm" type="button" data-packet-copy>Copy packet text</button>
       <button class="drawer-action drawer-action--sm" type="button" data-packet-show>Show in chat</button>
       <button class="drawer-action drawer-action--sm" type="button" data-packet-clear>Clear packet</button>`
    : `<button class="drawer-action drawer-action--sm" type="button" data-packet-build${buildDisabled}>Build packet</button>`;
  return `<div class="drawer-section hal-packet">
    <h3 class="drawer-section__title">${escapeHtml(ep.title || "Evidence packet")}</h3>
    <p class="drawer-meta">${escapeHtml(ep.summary || "")}</p>
    ${packetBody}
    <div class="drawer-card__actions">${actionBtns}</div>
  </div>`;
}

function bindEvidencePacketControls(root) {
  root.querySelectorAll("[data-packet-build]").forEach((button) => {
    button.addEventListener("click", () => {
      if (!buildEvidencePacketFromSession()) return;
      if (currentDrawerKey) renderPanel(currentDrawerKey);
    });
  });
  root.querySelectorAll("[data-packet-clear]").forEach((button) => {
    button.addEventListener("click", () => {
      clearEvidencePacket();
      if (currentDrawerKey) renderPanel(currentDrawerKey);
    });
  });
  root.querySelectorAll("[data-packet-copy]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!halEvidencePacket || !halEvidencePacket.text) return;
      try {
        await DesktopBridge.writeClipboard(halEvidencePacket.text);
        logAudit("Copy packet text", "packet: copy");
        renderAuditLog();
      } catch (error) {
        logAudit("Copy packet failed", "packet: copy-failed");
        renderAuditLog();
      }
    });
  });
  root.querySelectorAll("[data-packet-show]").forEach((button) => {
    button.addEventListener("click", () => {
      if (!halEvidencePacket) return;
      if (currentDrawerKey === "askHal") {
        halChatHistory.push({ role: "hal", text: halEvidencePacket.text, lane: "packet", actions: [] });
        saveChatHistory();
        renderChatLog();
      } else {
        openDrawer("askHal");
        setTimeout(() => {
          halChatHistory.push({ role: "hal", text: halEvidencePacket.text, lane: "packet", actions: [] });
          saveChatHistory();
          renderChatLog();
        }, 50);
      }
      logAudit("Show evidence packet", "packet: show");
      renderAuditLog();
    });
  });
}

let halReadinessDiagnostics = null;

function loadReadinessDiagnostics() {
  try {
    const saved = sessionStorage.getItem("halDiagnostics");
    if (saved) halReadinessDiagnostics = JSON.parse(saved);
  } catch (error) {
    halReadinessDiagnostics = null;
  }
}

function saveReadinessDiagnostics() {
  try {
    persistLocal("halDiagnostics", halReadinessDiagnostics);
  } catch (error) {
    /* sessionStorage may be unavailable. */
  }
}

function collectReadinessRuntime() {
  return {
    halImage: "",
    storageMode: isDesktopMode() ? "sqlite" : "sessionStorage",
    desktopBridgeOk: isDesktopMode(),
    activeSession: halWorkSession,
  };
}

function runReadinessDiagnostics() {
  halReadinessDiagnostics = HalCore.runReadinessChecks(halData, halModels, getPages(), collectReadinessRuntime());
  saveReadinessDiagnostics();
  logAudit("Run readiness check", "readiness: run");
  return halReadinessDiagnostics;
}

function clearReadinessDiagnostics() {
  halReadinessDiagnostics = null;
  saveReadinessDiagnostics();
  logAudit("Clear diagnostics", "readiness: clear");
}

function staffUseGateText() {
  if (!halReadinessDiagnostics) {
    return "No diagnostics available yet. Say \"Run readiness check\" first, then ask if HAL is ready for staff use.";
  }
  const gate = halReadinessDiagnostics.gate || HalCore.staffUseGate(halReadinessDiagnostics);
  const lines = ["Staff use gate: " + gate.status + " — " + gate.headline, gate.detail];
  if (gate.blockers && gate.blockers.length) {
    lines.push("", "Blockers:", ...gate.blockers.map((entry) => "- " + entry));
  }
  if (gate.warnings && gate.warnings.length) {
    lines.push("", "Warnings:", ...gate.warnings.map((entry) => "- " + entry));
  }
  lines.push("", "(Local diagnostic only · read-only · human review required)");
  return lines.join("\n");
}

function readinessStatusClass(status) {
  if (status === "Pass") return "hal-ready--pass";
  if (status === "Warning") return "hal-ready--warn";
  return "hal-ready--fail";
}

function gateStatusClass(status) {
  if (status === "Ready") return "hal-gate--pass";
  if (status === "Ready with warnings") return "hal-gate--warn";
  if (status === "Not ready") return "hal-gate--fail";
  return "hal-gate--unknown";
}

function staffUseGateHtml() {
  if (!halReadinessDiagnostics) return "";
  const gate = halReadinessDiagnostics.gate || HalCore.staffUseGate(halReadinessDiagnostics);
  const list = (items, label) =>
    items && items.length
      ? `<div class="drawer-meta"><strong>${label}</strong><ul class="hal-gate__list">${items
          .map((entry) => `<li>${escapeHtml(entry)}</li>`)
          .join("")}</ul></div>`
      : "";
  return `<div class="hal-gate ${gateStatusClass(gate.status)}">
    <div class="hal-gate__head">
      <strong>${escapeHtml(gate.headline)}</strong>
      <span class="hal-gate__status">${escapeHtml(gate.status)}</span>
    </div>
    <p>${escapeHtml(gate.detail)}</p>
    ${list(gate.blockers, "Blockers")}
    ${list(gate.warnings, "Warnings")}
  </div>`;
}

function readinessPanelHtml() {
  const cfg = halData.readiness || { title: "HAL readiness", summary: "" };
  const cards = halReadinessDiagnostics
    ? halReadinessDiagnostics.results
        .map(
          (item) =>
            `<div class="drawer-card hal-ready-card ${readinessStatusClass(item.status)}">
              <div class="hal-ready-card__head">
                <strong>${escapeHtml(item.label)}</strong>
                <span class="hal-ready-card__status">${escapeHtml(item.status)}</span>
              </div>
              <p>${escapeHtml(item.detail)}</p>
              ${item.next ? `<p class="drawer-meta">Next: ${escapeHtml(item.next)}</p>` : ""}
            </div>`,
        )
        .join("")
    : `<p class="drawer-meta">No diagnostics run yet. Click Run Readiness Check or ask HAL to check itself.</p>`;
  const overall = halReadinessDiagnostics
    ? `<p class="drawer-meta">Overall: <strong>${escapeHtml(halReadinessDiagnostics.overall)}</strong> · ${escapeHtml(halReadinessDiagnostics.ranAt)}</p>`
    : "";
  return `<div class="drawer-section hal-readiness">
    <h3 class="drawer-section__title">${escapeHtml(cfg.title || "HAL readiness")}</h3>
    <p class="drawer-meta">${escapeHtml(cfg.summary || "")}</p>
    ${staffUseGateHtml()}
    ${overall}
    <div class="drawer-grid">${cards}</div>
    <div class="drawer-card__actions">
      <button class="drawer-action drawer-action--sm" type="button" data-readiness-run>Run readiness check</button>
      <button class="drawer-action drawer-action--sm" type="button" data-readiness-gate${halReadinessDiagnostics ? "" : " disabled"}>Staff use gate</button>
      <button class="drawer-action drawer-action--sm" type="button" data-readiness-show${halReadinessDiagnostics ? "" : " disabled"}>Show diagnostics</button>
      <button class="drawer-action drawer-action--sm" type="button" data-readiness-clear${halReadinessDiagnostics ? "" : " disabled"}>Clear diagnostics</button>
    </div>
  </div>`;
}

function bindReadinessControls(root) {
  root.querySelectorAll("[data-readiness-run]").forEach((button) => {
    button.addEventListener("click", () => {
      runReadinessDiagnostics();
      if (currentDrawerKey) renderPanel(currentDrawerKey);
    });
  });
  root.querySelectorAll("[data-readiness-show]").forEach((button) => {
    button.addEventListener("click", () => {
      if (!halReadinessDiagnostics) return;
      const text = HalCore.formatReadinessSummary(halReadinessDiagnostics);
      if (currentDrawerKey === "askHal") {
        halChatHistory.push({ role: "hal", text, lane: "readiness", actions: [] });
        saveChatHistory();
        renderChatLog();
      } else {
        openDrawer("askHal");
        setTimeout(() => {
          halChatHistory.push({ role: "hal", text, lane: "readiness", actions: [] });
          saveChatHistory();
          renderChatLog();
        }, 50);
      }
    });
  });
  root.querySelectorAll("[data-readiness-gate]").forEach((button) => {
    button.addEventListener("click", () => {
      if (!halReadinessDiagnostics) return;
      const text = staffUseGateText();
      if (currentDrawerKey === "askHal") {
        halChatHistory.push({ role: "hal", text, lane: "readiness", actions: [] });
        saveChatHistory();
        renderChatLog();
      } else {
        openDrawer("askHal");
        setTimeout(() => {
          halChatHistory.push({ role: "hal", text, lane: "readiness", actions: [] });
          saveChatHistory();
          renderChatLog();
        }, 50);
      }
    });
  });
  root.querySelectorAll("[data-readiness-clear]").forEach((button) => {
    button.addEventListener("click", () => {
      clearReadinessDiagnostics();
      if (currentDrawerKey) renderPanel(currentDrawerKey);
    });
  });
}

let halOperatorReport = null;

let programContextCache = null;
let programContextAt = 0;
const PROGRAM_CONTEXT_TTL_MS = 60000;

async function refreshHalWidgetFeed(snapshot) {
  if (!window.HalSkills) return halWidgetFeed;
  const snap = snapshot || (await loadProgramSnapshot());
  if (!snap) {
    halWidgetFeed = null;
    halProgramSnapshot = null;
    return null;
  }
  halProgramSnapshot = snap;
  halWidgetFeed = HalSkills.buildWidgetFeed(snap);
  halData.runtime = Object.assign({}, halData.runtime || {}, { widgetFeed: halWidgetFeed });
  return halWidgetFeed;
}

function flashHalWidgets(pageId) {
  const bridge = typeof HalLiveWidgetBridge !== "undefined" ? HalLiveWidgetBridge : window.HalLiveWidgetBridge;
  if (!bridge || typeof bridge.flashElement !== "function" || !appPage) return;
  const scope = pageId ? appPage.querySelector(`[data-pv-page="${pageId}"]`) || appPage : appPage;
  scope.querySelectorAll("[data-hal-widget-key]").forEach((el) => bridge.flashElement(el, "cyan"));
}

function showHalActionNotice(message, tone) {
  if (typeof document === "undefined" || !message) return;
  const existing = document.getElementById("halActionNotice");
  if (existing) existing.remove();
  const notice = document.createElement("div");
  notice.id = "halActionNotice";
  notice.className = `hal-action-notice hal-action-notice--${tone || "info"}`;
  notice.setAttribute("role", "status");
  const closeIcon = typeof AppIcons !== "undefined" ? AppIcons.ui("close") : "";
  notice.innerHTML = `<span>${escapeHtml(message)}</span><button type="button" class="hal-action-notice__close" aria-label="Dismiss">${closeIcon}</button>`;
  notice.querySelector(".hal-action-notice__close").addEventListener("click", () => notice.remove());
  const app = document.querySelector(".app");
  if (app && app.parentNode) app.parentNode.insertBefore(notice, app);
  window.setTimeout(() => {
    if (notice.isConnected) notice.remove();
  }, 8000);
}

async function forceHalWidgetPlacement(detail) {
  const pageId =
    (detail && detail.pageId) ||
    (window.location.hash || "").replace("#", "") ||
    (getPages()[0] && getPages()[0].id) ||
    "financial";
  let placementNote = "";

  invalidateProgramCaches("hal-force-widget-placement");

  const desktop = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
  if (desktop && desktop.hasDesktopApi && desktop.hasDesktopApi()) {
    try {
      if (typeof ImportCoordinator !== "undefined") {
        await ImportCoordinator.refresh({ reason: "hal-force-place" });
      } else if (typeof Services !== "undefined" && Services.refreshImports) {
        await Services.refreshImports({ reason: "hal-force-place", waitForCompletion: true });
      }
      placementNote = "Imports refreshed and widget feed rebuilt.";
    } catch (err) {
      placementNote = `Import refresh issue: ${err && err.message ? err.message : String(err)}. Rebuilt widget feed from cached data.`;
    }
  } else {
    placementNote = "Browser preview: rebuilt widget feed from available preview data only.";
  }

  const snapshot = await loadProgramSnapshot();
  await refreshHalWidgetFeed(snapshot);

  if (window.HalProactive) {
    halProactiveBriefing = await HalProactive.runCycle(buildHalAgentCtx(), { force: true, forcePlacement: true });
    if (halProactiveBriefing) {
      halData.runtime = Object.assign({}, halData.runtime || {}, {
        proactiveBriefing: halProactiveBriefing,
        officeManager: halProactiveBriefing.officeManager || null,
        lastWidgetPlacement: {
          at: new Date().toISOString(),
          pageId,
          reason: (detail && detail.reason) || "user-force",
        },
      });
      renderProactiveBanner();
    }
  }

  await scheduleHalWidgetRefresh(snapshot);
  flashHalWidgets(pageId);
  showHalActionNotice(placementNote, desktop && desktop.hasDesktopApi && desktop.hasDesktopApi() ? "info" : "warn");

  return { placementNote, feed: halWidgetFeed, pageId };
}

function handleHalLiveWidgetEvent(event) {
  const detail = event && event.detail ? event.detail : null;
  if (!detail || !detail.widgetKey) return;
  const record = Object.assign(
    {
      at: new Date().toISOString(),
      pageId: "unknown",
      library: "custom",
      eventType: "interaction",
      payload: {},
      halAction: "Record widget interaction",
    },
    detail,
  );
  halLiveWidgetEvents.unshift(record);
  if (halLiveWidgetEvents.length > 40) halLiveWidgetEvents.length = 40;
  halData.runtime = Object.assign({}, halData.runtime || {}, {
    liveWidgetEvents: halLiveWidgetEvents.slice(0, 20),
    lastLiveWidgetEvent: record,
  });
  invalidateProgramCaches("hal-live-widget-event");
  scheduleHalWidgetRefresh();
  const action = String(record.halAction || "").trim();
  if (action) {
    void runHalPageCmd(action);
  }
}

async function loadProgramSnapshot() {
  const Svc = typeof Services !== "undefined" ? Services : window.Services;
  if (!Svc || typeof Svc.readProgramSnapshot !== "function") return null;
  const base = await Svc.readProgramSnapshot();
  if (!base) return null;
  const monitor = halSideNoteMonitor || (window.HalSkills ? HalSkills.buildSideNoteMonitor(halSideNotes) : null);
  const active = halSideNotes.filter((n) => n.status !== "archived");
  const snapshot = Object.assign({}, base, {
    sideNotes: {
      total: halSideNotes.length,
      activeCount: active.length,
      monitor,
      top: active.slice(0, 8).map((n) => ({
        noteId: n.noteId,
        text: n.text.slice(0, 120),
        status: n.status,
        priority: n.priority,
        updatedAt: n.updatedAt,
      })),
    },
  });
  if (window.HalSkills) {
    halProgramSnapshot = snapshot;
    halWidgetFeed = HalSkills.buildWidgetFeed(snapshot);
    halData.runtime = Object.assign({}, halData.runtime || {}, { widgetFeed: halWidgetFeed });
    snapshot.widgets = halWidgetFeed;
  }
  return snapshot;
}

async function loadCachedProgramSnapshot() {
  return loadProgramSnapshot();
}

async function getProgramContextText() {
  const now = Date.now();
  if (!programContextCache || now - programContextAt > PROGRAM_CONTEXT_TTL_MS) {
    programContextCache = await loadProgramSnapshot();
    programContextAt = now;
  }
  return HalCore.summarizeProgramSnapshot(programContextCache, halData);
}

function loadOperatorReport() {
  try {
    const saved = sessionStorage.getItem("halOperatorReport");
    if (saved) halOperatorReport = JSON.parse(saved);
  } catch (error) {
    halOperatorReport = null;
  }
}

function saveOperatorReport() {
  try {
    persistLocal("halOperatorReport", halOperatorReport);
  } catch (error) {
    /* sessionStorage may be unavailable. */
  }
}

function runOperatorSmokeTest() {
  halOperatorReport = HalCore.runOperatorSmokeTest(halData, halModels, getPages(), collectReadinessRuntime());
  saveOperatorReport();
  logAudit("Run operator smoke test", "operator: smoke");
  return halOperatorReport;
}

function clearOperatorReport() {
  halOperatorReport = null;
  saveOperatorReport();
  logAudit("Clear operator report", "operator: clear");
}

function staffHandoffSummaryText() {
  return HalCore.buildHandoffSummary(halData, halModels, {
    readiness: halReadinessDiagnostics,
    session: halWorkSession,
    packet: halEvidencePacket,
    smoke: halOperatorReport,
  });
}

function operatorPanelHtml() {
  const cfg = halData.operator || { title: "Operator acceptance", summary: "" };
  const steps = halOperatorReport
    ? halOperatorReport.steps
        .map(
          (step) =>
            `<div class="drawer-card hal-ready-card ${readinessStatusClass(step.status)}">
              <div class="hal-ready-card__head">
                <strong>${escapeHtml(step.label)}</strong>
                <span class="hal-ready-card__status">${escapeHtml(step.status)}</span>
              </div>
              <p>${escapeHtml(step.detail)}</p>
            </div>`,
        )
        .join("")
    : `<p class="drawer-meta">No smoke test run yet. Click Run Smoke Test to verify HAL end-to-end.</p>`;
  const overall = halOperatorReport
    ? `<p class="drawer-meta">Smoke result: <strong>${escapeHtml(halOperatorReport.overall)}</strong> · ${escapeHtml(halOperatorReport.ranAt)}</p>`
    : "";
  return `<div class="drawer-section hal-operator">
    <h3 class="drawer-section__title">${escapeHtml(cfg.title || "Operator acceptance")}</h3>
    <p class="drawer-meta">${escapeHtml(cfg.summary || "")}</p>
    ${overall}
    <div class="drawer-grid">${steps}</div>
    <div class="drawer-card__actions">
      <button class="drawer-action drawer-action--sm" type="button" data-operator-smoke>Run smoke test</button>
      <button class="drawer-action drawer-action--sm" type="button" data-operator-handoff>Staff handoff summary</button>
      <button class="drawer-action drawer-action--sm" type="button" data-operator-clear${halOperatorReport ? "" : " disabled"}>Clear smoke report</button>
    </div>
  </div>`;
}

function postToHalChat(text, lane) {
  if (currentDrawerKey === "askHal") {
    halChatHistory.push({ role: "hal", text, lane, actions: [] });
    saveChatHistory();
    renderChatLog();
  } else {
    openDrawer("askHal");
    setTimeout(() => {
      halChatHistory.push({ role: "hal", text, lane, actions: [] });
      saveChatHistory();
      renderChatLog();
    }, 50);
  }
}

function bindOperatorControls(root) {
  root.querySelectorAll("[data-operator-smoke]").forEach((button) => {
    button.addEventListener("click", () => {
      const report = runOperatorSmokeTest();
      postToHalChat(HalCore.formatSmokeTestSummary(report), "operator");
      if (currentDrawerKey) renderPanel(currentDrawerKey);
    });
  });
  root.querySelectorAll("[data-operator-handoff]").forEach((button) => {
    button.addEventListener("click", () => {
      logAudit("Staff handoff summary", "operator: handoff-summary");
      postToHalChat(staffHandoffSummaryText(), "operator");
    });
  });
  root.querySelectorAll("[data-operator-clear]").forEach((button) => {
    button.addEventListener("click", () => {
      clearOperatorReport();
      if (currentDrawerKey) renderPanel(currentDrawerKey);
    });
  });
}

function drawerHealthBadge(key) {
  const health = HalCore.deriveDrawerHealth(halData, halModels, getPages(), halReadinessDiagnostics);
  const status = health[key];
  if (!status) return "";
  return `<span class="hal-badge ${readinessStatusClass(status)}" title="Readiness: ${escapeHtml(status)}">${escapeHtml(status)}</span>`;
}

function registryList() {
  return HalCore.registryList(halData);
}

function registryById(id) {
  return HalCore.registryById(halData, id);
}

function pageInfoMap() {
  return HalCore.pageInfoMap(halData, getPages());
}

function localModelConfig() {
  return HalCore.laneRuntime(halModels, "chat8b");
}

function escalationModelConfig() {
  return HalCore.laneRuntime(halModels, "escalate30b");
}

function ossModelConfig() {
  return HalCore.laneRuntime(halModels, "oss120b");
}

const ollamaModelCache = { at: 0, names: null, loading: null };

async function refreshOllamaModelNames() {
  const runtime = HalCore.laneRuntime(halModels, "chat8b");
  if (!runtime || !runtime.endpoint) return [];
  const base = String(runtime.endpoint).replace(/\/api\/chat\/?$/i, "");
  try {
    const res = await fetch(base + "/api/tags", { cache: "no-store" });
    if (!res.ok) return [];
    const data = await res.json();
    const names = (data.models || []).map((m) => m.name).filter(Boolean);
    ollamaModelCache.names = new Set(names);
    ollamaModelCache.at = Date.now();
    return names;
  } catch {
    return [];
  }
}

async function ensureOllamaModelCache(maxAgeMs) {
  const age = maxAgeMs == null ? 45000 : maxAgeMs;
  if (ollamaModelCache.names && Date.now() - ollamaModelCache.at < age) return ollamaModelCache.names;
  if (ollamaModelCache.loading) return ollamaModelCache.loading;
  ollamaModelCache.loading = refreshOllamaModelNames().finally(() => {
    ollamaModelCache.loading = null;
  });
  return ollamaModelCache.loading;
}
window.ensureOllamaModelCache = ensureOllamaModelCache;
globalThis.getCloudApiKey = getCloudApiKey;
window.getCloudApiKey = getCloudApiKey;
window.setCloudApiKeyFromHalPage = function saveCloudKeyFromHalPage() {
  const input = document.getElementById("hal-cloud-key-input");
  const persist = document.getElementById("hal-cloud-key-persist");
  setCloudApiKey(input ? input.value : "", persist && persist.checked);
  if (typeof renderHalScreen === "function") renderHalScreen();
};

function ollamaHasModel(modelName) {
  if (!modelName) return false;
  if (!ollamaModelCache.names) return false;
  if (ollamaModelCache.names.has(modelName)) return true;
  const base = String(modelName).split(":")[0];
  for (const n of ollamaModelCache.names) {
    if (n === modelName || n.startsWith(base + ":")) return true;
  }
  return false;
}

function laneModelInstalled(laneId) {
  if (!HalCore.laneReady(halModels, laneId)) return false;
  const rt = HalCore.laneRuntime(halModels, laneId);
  if (!rt || !rt.model) return false;
  return ollamaHasModel(rt.model);
}

function localModelReady() {
  return laneModelInstalled("chat8b");
}

function reason21bAvailable() {
  return laneModelInstalled("reason21b");
}

function reasoningModelReady() {
  return reason21bAvailable() || laneModelInstalled("chat8b");
}

function reasoningModelConfig() {
  if (laneModelInstalled("reason21b")) return HalCore.laneRuntime(halModels, "reason21b");
  return Object.assign({ fastChat: true, reasonFallback: true }, HalCore.laneRuntime(halModels, "chat8b"));
}

function escalationModelReady() {
  return HalCore.laneReady(halModels, "escalate30b");
}

function ossModelReady() {
  return HalCore.laneReady(halModels, "oss120b");
}

function getCloudApiKey() {
  try {
    return sessionStorage.getItem("NR2_CLOUD_API_KEY") || localStorage.getItem("NR2_CLOUD_API_KEY") || "";
  } catch {
    return "";
  }
}

function setCloudApiKey(key, persist) {
  const value = String(key || "").trim();
  try {
    sessionStorage.setItem("NR2_CLOUD_API_KEY", value);
    if (persist) localStorage.setItem("NR2_CLOUD_API_KEY", value);
    else localStorage.removeItem("NR2_CLOUD_API_KEY");
  } catch {
    /* storage may be unavailable in preview */
  }
}

function sanitizeForCloud(text) {
  return String(text || "")
    .replace(/\b\d{3}-\d{2}-\d{4}\b/g, "[redacted-id]")
    .replace(/\b\d{9,12}\b/g, "[redacted-number]")
    .replace(/\$[\d,]+(?:\.\d{2})?/g, "[amount]")
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, "[email]")
    .replace(/\bpatient[:\s]+[^\n,]{2,40}/gi, "patient: [redacted]");
}

function cloudModelConfig() {
  const cfg = HalCore.modelConfig(halModels).cloudReasoning || {};
  if (!cfg.endpoint) return null;
  const hasKey = !!getCloudApiKey();
  const active = cfg.enabled === true || (cfg.autoEnableWhenKeySet !== false && hasKey);
  if (!active) return null;
  return {
    cloud: true,
    endpoint: cfg.endpoint,
    model: cfg.model || "gpt-4o-mini",
    timeoutMs: cfg.timeoutMs || 120000,
    useForAgentLoop: cfg.useForAgentLoop !== false,
    autoEnableWhenKeySet: cfg.autoEnableWhenKeySet !== false,
    preferForTaskCompletion: cfg.preferForTaskCompletion !== false,
    options: cfg.options || {},
  };
}

function cloudModelReady() {
  const cfg = cloudModelConfig();
  if (!cfg || !cfg.useForAgentLoop) return false;
  return !!getCloudApiKey();
}

function cloudAgentEligible(plan) {
  if (!plan || !plan.agentToolLoop || !cloudModelReady()) return false;
  const cfg = HalCore.modelConfig(halModels).cloudReasoning || {};
  if (cfg.enabled === true) return true;
  if (cfg.autoEnableWhenKeySet === false || !getCloudApiKey()) return false;
  if (cfg.preferForTaskCompletion === false) return false;
  return !!(plan.isTaskCompletionQuery || plan.isInvestigateQuery || plan.isComplexInvestigationQuery);
}

function offlineModelMessage(laneId) {
  if (window.HalCore && HalCore.offlineModelChatMessage) {
    return HalCore.offlineModelChatMessage(laneId, halModels, halData, "");
  }
  const lane = HalCore.modelLanes(halModels).find((entry) => entry.id === laneId) || HalCore.modelLanes(halModels)[0];
  const name = lane && lane.name ? lane.name : "local chat lane";
  const model = lane && lane.model ? lane.model : "local model";
  return (
    "The local chat model (" +
    name +
    " · " +
    model +
    ") is offline. I can still answer from the program registry — ask about a page, imports, or readiness."
  );
}

function modelHealthSummary() {
  const lanes = HalCore.modelLanes(halModels);
  return lanes
    .map((lane) => {
      const ready = HalCore.laneReady(halModels, lane.id);
      return `${lane.name}: ${ready ? "ready" : "offline"} (${lane.model})`;
    })
    .join(" · ");
}

function naturalVoiceConfig() {
  const config = HalCore.modelConfig(halModels);
  return (config && config.naturalVoice) || {};
}

function modelRuntimeOptions(runtime) {
  const voice = naturalVoiceConfig();
  const profile = voice.sampling || {};
  const options = Object.assign(
    {
      temperature: typeof runtime.temperature === "number" ? runtime.temperature : 0.2,
    },
    runtime.options || {},
  );
  // Miranda voice sampling is for the fast 8B chat lane only — not reasoning/escalation.
  if (runtime && runtime.fastChat) {
    Object.assign(options, profile);
  }

  ["temperature", "min_p", "top_p", "repeat_penalty", "presence_penalty", "frequency_penalty", "num_ctx"].forEach((key) => {
    if (typeof options[key] === "string") {
      const parsed = Number(options[key]);
      if (Number.isFinite(parsed)) options[key] = parsed;
    }
  });
  return options;
}

function modelMessages(systemPrompt, userText, runtime) {
  const voice = naturalVoiceConfig();
  const styleRules = Array.isArray(voice.instructions) ? voice.instructions.filter(Boolean) : [];
  const fewShots = Array.isArray(voice.fewShotMessages) ? voice.fewShotMessages : [];
  const prechat = runtime && runtime.fastChat ? fewShots.slice(0, 8) : fewShots;
  let system = styleRules.length ? systemPrompt + "\n\nVoice and cadence:\n" + styleRules.map((line) => "- " + line).join("\n") : systemPrompt;
  if (typeof HalAgentProgramming !== "undefined" && HalAgentProgramming.contract && !/^PROGRAMMING:/m.test(system)) {
    system = HalAgentProgramming.wrapSystemPrompt(system);
  }
  return [{ role: "system", content: system }]
    .concat(
      prechat
        .filter((msg) => msg && (msg.role === "user" || msg.role === "assistant") && msg.content)
        .slice(0, 8)
        .map((msg) => ({ role: msg.role, content: String(msg.content) })),
    )
    .concat([{ role: "user", content: userText }]);
}

async function runModel(runtime, systemPrompt, userText, draftLabel, onToken, abortSignal) {
  if (!runtime || !runtime.cloud) await ensureOllamaModelCache();
  const controller = abortSignal ? null : new AbortController();
  const signal = abortSignal || (controller && controller.signal);
  const timer = setTimeout(() => {
    if (controller) controller.abort();
  }, runtime.timeoutMs || 60000);
  const structuredCloud = !!(runtime && runtime.cloud && runtime.structuredAgent);
  const structuredOllama = !!(
    runtime &&
    runtime.structuredAgent &&
    Array.isArray(runtime.ollamaTools) &&
    runtime.ollamaTools.length
  );
  const wantStream = typeof onToken === "function" && !structuredCloud && !structuredOllama;

  if (runtime && runtime.cloud) {
    const key = getCloudApiKey();
    if (!key) throw new Error("cloud api key missing");
    const messages = modelMessages(systemPrompt, userText, runtime);
    const payload = {
      model: runtime.model,
      stream: wantStream,
      messages,
      temperature: (runtime.options && runtime.options.temperature) || 0.2,
      max_tokens: (runtime.options && (runtime.options.max_tokens || runtime.options.num_predict)) || 2048,
    };
    if (Array.isArray(runtime.cloudTools) && runtime.cloudTools.length) {
      payload.tools = runtime.cloudTools;
      payload.tool_choice = "auto";
    }
    try {
      const response = await fetch(runtime.endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer " + key,
        },
        body: JSON.stringify(payload),
        signal,
      });
      if (signal && signal.aborted) throw new DOMException("Aborted", "AbortError");
      if (!response.ok) throw new Error("cloud model http " + response.status);

      let raw = "";
      if (wantStream && response.body && typeof response.body.getReader === "function") {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";
          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed || trimmed === "data: [DONE]") continue;
            const jsonLine = trimmed.startsWith("data:") ? trimmed.slice(5).trim() : trimmed;
            if (!jsonLine) continue;
            let chunk;
            try {
              chunk = JSON.parse(jsonLine);
            } catch {
              continue;
            }
            const delta =
              (chunk.choices &&
                chunk.choices[0] &&
                chunk.choices[0].delta &&
                chunk.choices[0].delta.content) ||
              (chunk.message && chunk.message.content) ||
              "";
            if (delta) {
              raw += delta;
              try {
                onToken(HalCore.cleanModelText(raw));
              } catch {
                /* display callback is best-effort */
              }
            }
          }
        }
      } else {
        const data = await response.json();
        const msg = data.choices && data.choices[0] && data.choices[0].message ? data.choices[0].message : null;
        raw = (msg && msg.content) || (data.message && data.message.content) || "";
        if (structuredCloud && msg) {
          const text = HalCore.cleanModelText(raw);
          if (text || (msg.tool_calls && msg.tool_calls.length)) {
            return {
              text,
              toolCalls: msg.tool_calls || [],
              lane: "cloud",
            };
          }
        }
      }
      const text = HalCore.cleanModelText(raw);
      if (!text && !(structuredCloud && runtime.cloudTools)) throw new Error("empty cloud model response");
      if (structuredCloud) {
        return { text: text || "", toolCalls: [], lane: "cloud" };
      }
      if (runtime && runtime.fastChat) return text;
      return text + "\n\n(" + draftLabel + " · cloud · verify before acting)";
    } catch (error) {
      if (error && error.name === "AbortError") throw error;
      throw error;
    } finally {
      clearTimeout(timer);
    }
  }

  const payload = {
    model: runtime.model,
    stream: wantStream,
    messages: modelMessages(systemPrompt, userText, runtime),
    options: modelRuntimeOptions(runtime),
  };
  if (typeof runtime.think === "boolean") payload.think = runtime.think;
  if (Array.isArray(runtime.ollamaTools) && runtime.ollamaTools.length) {
    payload.tools = runtime.ollamaTools;
  }
  try {
    const response = await fetch(runtime.endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal,
    });
    if (signal && signal.aborted) throw new DOMException("Aborted", "AbortError");
    if (!response.ok) throw new Error("model http " + response.status);

    let raw = "";
    if (wantStream && response.body && typeof response.body.getReader === "function") {
      // Ollama streams newline-delimited JSON; emit each delta for live display.
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let nl;
        while ((nl = buffer.indexOf("\n")) >= 0) {
          const line = buffer.slice(0, nl).trim();
          buffer = buffer.slice(nl + 1);
          if (!line) continue;
          let chunk;
          try {
            chunk = JSON.parse(line);
          } catch {
            continue;
          }
          const delta = chunk && chunk.message && chunk.message.content ? chunk.message.content : "";
          if (delta) {
            raw += delta;
            try {
              onToken(HalCore.cleanModelText(raw));
            } catch {
              /* display callback is best-effort */
            }
          }
        }
      }
    } else {
      const data = await response.json();
      const msg = data && data.message ? data.message : null;
      raw = msg && msg.content ? msg.content : "";
      if (structuredOllama && msg) {
        const text = HalCore.cleanModelText(raw);
        const toolCalls = msg.tool_calls || [];
        if (text || toolCalls.length) {
          const lane = runtime.reasonFallback ? "chat8b" : runtime.reasoningLane ? "reason21b" : "chat8b";
          return { text, toolCalls, lane };
        }
      }
    }

    const text = HalCore.cleanModelText(raw);
    if (!text && !structuredOllama) throw new Error("empty model response");
    if (structuredOllama) {
      return { text: text || "", toolCalls: [], lane: runtime.reasoningLane ? "reason21b" : "chat8b" };
    }
    if (runtime && runtime.fastChat) return text;
    return text + "\n\n(" + draftLabel + " · read-only · verify before acting)";
  } catch (error) {
    if (error && error.name === "AbortError") throw error;
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

function callLocalModel(userText) {
  return getProgramContextText().then((ctx) =>
    runModel(localModelConfig(), HalCore.buildSystemPrompt(halData, ctx), userText, "Local 24B draft"),
  );
}

function callReasoningModel(userText) {
  return getProgramContextText().then((ctx) =>
    runModel(reasoningModelConfig(), HalCore.buildReasoningPrompt(halData, ctx), userText, "Local reasoning draft"),
  );
}

function callEscalationModel(userText) {
  return getProgramContextText().then((ctx) =>
    runModel(escalationModelConfig(), HalCore.buildEscalationPrompt(halData, ctx), userText, "Local escalation draft"),
  );
}

function routeHalCommand(rawQuery) {
  return HalCore.routeHalCommand(halData, halModels, getPages(), rawQuery);
}

function logAudit(query, intent) {
  halAudit.push({ time: new Date().toLocaleTimeString(), query, intent });
  persistLocal("halAudit", halAudit);
}

function normalizeActions(actions) {
  return (actions || []).map((action) => {
    if (action.page && !action.type) return { type: "openPage", label: action.label, page: action.page };
    return action;
  });
}

function expandHalUserQuery(raw) {
  const trimmed = String(raw || "").trim();
  if (!trimmed) return trimmed;
  const turns = halChatHistory.map((m) => ({ role: m.role === "user" ? "user" : "hal", text: m.text }));
  if (window.HalCore && HalCore.expandCorrectionQuery) {
    if (HalCore.isCorrectionQuery && HalCore.isCorrectionQuery(trimmed)) {
      return HalCore.expandCorrectionQuery(trimmed, turns);
    }
  }
  let q = trimmed;
  if (window.HalCore && HalCore.resolveFollowUpQuery) {
    q = HalCore.resolveFollowUpQuery(q, turns);
  }
  if (window.HalCore && HalCore.expandAtMentions) {
    q = HalCore.expandAtMentions(q, getPages());
  }
  return q;
}

function formatHalMessageHtml(text) {
  const raw = String(text || "");
  if (!raw) return "";

  const withPatches = raw.replace(/<<<patch\s+([\s\S]*?)>>>/gi, (full, body) => {
    const fileMatch = body.match(/^\s*file:\s*(.+)$/im);
    const file = fileMatch ? fileMatch[1].trim() : "file";
    const preview = body.trim().slice(0, 280);
    return (
      '<details class="hal-msg__patch"><summary>Patch: ' +
      escapeHtml(file) +
      '</summary><pre class="hal-msg__codeblock">' +
      escapeHtml(preview) +
      (body.length > 280 ? "\n…" : "") +
      "</pre></details>"
    );
  });
  const withTools = withPatches.replace(/<<<tool[\s\S]*?>>>/gi, "");

  const blocks = [];
  let lastIndex = 0;
  const codeBlockRe = /```([\s\S]*?)```/g;
  let match;
  while ((match = codeBlockRe.exec(withTools)) !== null) {
    if (match.index > lastIndex) {
      blocks.push({ type: "text", value: withTools.slice(lastIndex, match.index) });
    }
    blocks.push({ type: "code", value: match[1].trim() });
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < withTools.length) blocks.push({ type: "text", value: withTools.slice(lastIndex) });
  if (!blocks.length) blocks.push({ type: "text", value: withTools });

  function inlineFormat(segment) {
    let s = escapeHtml(segment);
    s = s.replace(/`([^`\n]+)`/g, "<code class=\"hal-msg__code\">$1</code>");
    s = s.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/^\s*[-*•]\s+(.+)$/gm, "<span class=\"hal-msg__bullet\">• $1</span>");
    return s;
  }

  return blocks
    .map((block) => {
      if (block.type === "code") {
        return `<pre class="hal-msg__codeblock">${escapeHtml(block.value)}</pre>`;
      }
      return inlineFormat(block.value);
    })
    .join("");
}

function renderFollowUpChipsHtml(chips) {
  if (!chips || !chips.length) return "";
  return `<div class="hal-msg__followups hp-chips">${chips
    .map((c) => {
      const label = escapeHtml(c.label);
      if (c.action && c.action.type === "openPage" && c.action.page) {
        return `<button type="button" class="hp-chip hp-chip--action" data-hal-action="openPage" data-open-page="${escapeHtml(c.action.page)}" data-hal-followup="${escapeHtml(c.query || c.label)}">${label}</button>`;
      }
      if (c.action && c.action.type === "refreshImports") {
        return `<button type="button" class="hp-chip hp-chip--action" data-hal-action="refreshImports" data-hal-followup="Refresh imports">${label}</button>`;
      }
      return `<button type="button" class="hp-chip" data-hal-followup="${escapeHtml(c.query || c.label)}">${label}</button>`;
    })
    .join("")}</div>`;
}

function formatHalToolsUsed(tools) {
  if (!Array.isArray(tools) || !tools.length) return "";
  const labels = tools.map((id) =>
    String(id || "")
      .replace(/^read_/, "")
      .replace(/^search_/, "search ")
      .replace(/^grep_/, "grep ")
      .replace(/^run_/, "")
      .replace(/^lookup_/, "lookup ")
      .replace(/_/g, " "),
  );
  return labels.join(" · ");
}

function summarizeToolResultsBrief(toolResults) {
  if (!toolResults || typeof toolResults !== "object") return "";
  return Object.entries(toolResults)
    .map(([id, res]) => {
      const label = formatHalToolsUsed([id]) || id;
      const summary = res && res.summary ? String(res.summary).replace(/\s+/g, " ").trim().slice(0, 320) : "No data.";
      return label + " — " + summary;
    })
    .join("\n");
}

function renderChatLog() {
  const log = document.getElementById("halChatLog");
  if (!log) return;
  log.innerHTML = halChatHistory
    .map((message, idx) => {
      const lane = message.lane ? `<span class="hal-msg__lane">${escapeHtml(message.lane)}</span>` : "";
      const loopBadge =
        message.role === "hal" && message.agentLoopTurns > 0
          ? `<span class="hal-msg__loop">${message.agentLoopTurns} agent turn${message.agentLoopTurns > 1 ? "s" : ""}</span>`
          : "";
      const tools =
        message.role === "hal" && message.tools && message.tools.length
          ? `<div class="hal-msg__tools">Checked: ${escapeHtml(formatHalToolsUsed(message.tools))}</div>`
          : "";
      const toolDetails =
        message.role === "hal" && message.toolSummaries
          ? `<details class="hal-msg__tools-detail"><summary>Evidence detail</summary><pre class="hal-msg__tools-pre">${escapeHtml(message.toolSummaries)}</pre></details>`
          : "";
      const patchChip =
        message.role === "hal" && /<<<patch/i.test(String(message.text || ""))
          ? `<button type="button" class="hp-chip hp-chip--action" data-hal-apply-patches="${idx}">Apply patches</button>`
          : "";
      const actions = normalizeActions(message.actions)
        .map((action) => {
          if (action.type === "openPage") {
            return `<button class="hal-msg__action" type="button" data-open-page="${escapeHtml(action.page)}">${escapeHtml(action.label)}</button>`;
          }
          return "";
        })
        .join("");
      const followups = message.role === "hal" ? renderFollowUpChipsHtml(message.followUpChips) : "";
      return `<div class="hal-msg hal-msg--${message.role === "user" ? "user" : "hal"}">
        <span class="hal-msg__who">${message.role === "user" ? "You" : "HAL"}${lane}${loopBadge}</span>
        ${tools}
        ${toolDetails}
        <div class="hal-msg__text">${formatHalMessageHtml(message.text)}</div>
        ${patchChip ? `<div class="hal-msg__actions">${patchChip}</div>` : ""}
        ${actions ? `<div class="hal-msg__actions">${actions}</div>` : ""}
        ${followups}
      </div>`;
    })
    .join("");
  log.querySelectorAll("[data-open-page]").forEach((button) => {
    button.addEventListener("click", () => {
      const target = button.dataset.openPage;
      logAudit("Open " + target, "navigate: confirmed");
      closeDrawer();
      select(target);
    });
  });
  log.querySelectorAll("[data-hal-followup]").forEach((button) => {
    button.addEventListener("click", () => {
      const action = button.getAttribute("data-hal-action");
      if (action === "openPage" && button.dataset.openPage) {
        logAudit("Open " + button.dataset.openPage, "navigate: chip");
        closeDrawer();
        select(button.dataset.openPage);
        return;
      }
      if (action === "refreshImports") {
        handleHalSubmit("Refresh imports");
        return;
      }
      handleHalSubmit(button.getAttribute("data-hal-followup"));
    });
  });
  log.querySelectorAll("[data-hal-apply-patches]").forEach((button) => {
    button.addEventListener("click", async () => {
      const idx = parseInt(button.getAttribute("data-hal-apply-patches"), 10);
      const msg = halChatHistory[idx];
      if (!msg || !window.HalAgentLoop || typeof HalAgentLoop.parseAllPatches !== "function") return;
      const patches = HalAgentLoop.parseAllPatches(msg.text);
      if (!patches.length) return;
      button.disabled = true;
      button.textContent = "Applying…";
      try {
        let summary = "";
        if (typeof DesktopBridge !== "undefined" && typeof DesktopBridge.applyProgramPatches === "function") {
          const payload = await DesktopBridge.applyProgramPatches(patches, false);
          summary = payload && payload.text ? payload.text : "Patches applied.";
        } else {
          summary = "Desktop bridge unavailable — paste patches manually.";
        }
        halChatHistory.push({ role: "hal", text: summary, lane: "patch", actions: [] });
        saveChatHistory();
        renderChatLog();
        renderHalScreen();
      } catch (error) {
        button.disabled = false;
        button.textContent = "Apply patches";
        halChatHistory.push({
          role: "hal",
          text: "Patch apply failed: " + (error && error.message ? error.message : String(error)),
          lane: "error",
          actions: [],
        });
        saveChatHistory();
        renderChatLog();
      }
    });
  });
  log.scrollTop = log.scrollHeight;
}

function renderAuditLog() {
  const count = document.getElementById("halAuditCount");
  if (count) count.textContent = String(halAudit.length);
  const el = document.getElementById("halAuditLog");
  if (!el) return;
  if (halAudit.length === 0) {
    el.innerHTML = '<p class="hal-audit__empty">No actions yet this session.</p>';
    return;
  }
  el.innerHTML = halAudit
    .slice()
    .reverse()
    .map(
      (entry) =>
        `<div class="hal-audit__row"><span>${escapeHtml(entry.time)}</span><span>${escapeHtml(entry.intent)}</span><span>${escapeHtml(entry.query)}</span></div>`,
    )
    .join("");
}

function ctxAbortSignal(extras) {
  if (extras && extras.abortSignal) return extras.abortSignal;
  return halModelAbortController ? halModelAbortController.signal : undefined;
}

function buildHalAgentCtx(extras) {
  return Object.assign({
    halData,
    halModels,
    pages: getPages(),
    halOfficeTasks,
    getOfficeTasks: async () => {
      if (typeof OfficeTaskStore !== "undefined") return OfficeTaskStore.list();
      const snap = await loadCachedProgramSnapshot();
      return (snap && snap.officeTasks) || halOfficeTasks || [];
    },
    halWorkSession,
    halEvidencePacket,
    halReadinessDiagnostics,
    halLiveWidgetEvents,
    halSideNotes,
    halSideNoteMonitor,
    Services: typeof Services !== "undefined" ? Services : window.Services,
    ImportLoader: window.ImportLoader,
    loadProgramSnapshot: loadCachedProgramSnapshot,
    loadProgramSnapshotRaw: loadProgramSnapshot,
    refreshHalWidgetFeed,
    getProgramContextText,
    workSessionStatusText,
    runReadinessDiagnostics,
    staffUseGateText,
    staffHandoffSummaryText,
    runOperatorSmokeTest,
    runModel: (runtime, systemPrompt, userText, draftLabel, onToken) =>
      runModel(runtime, systemPrompt, userText, draftLabel, onToken, ctxAbortSignal(extras)),
    getChatHistory: () => halChatHistory.slice(-16),
    getWorkingTurns: () =>
      window.HalAgent && typeof HalAgent.getWorkingMemory === "function"
        ? (HalAgent.getWorkingMemory().turns || []).slice(-12)
        : halChatHistory.slice(-12).map((m) => ({ role: m.role, text: m.text })),
    localModelReady,
    reason21bAvailable,
    reasoningModelReady,
    ensureOllamaModelCache,
    escalationModelReady,
    ossModelReady,
    offlineModelMessage,
    localModelConfig,
    reasoningModelConfig,
    escalationModelConfig,
    ossModelConfig,
    cloudModelConfig,
    cloudModelReady,
    cloudAgentEligible,
    getCloudApiKey,
    setCloudApiKey,
    sanitizeForCloud,
    buildCloudToolSchemas:
      window.HalAgent && typeof HalAgent.buildCloudToolSchemas === "function"
        ? (ids) => HalAgent.buildCloudToolSchemas(ids)
        : () => [],
    persistGet: (key) => DesktopBridge.storageGet(key),
    persistSet: (key, value) => persistLocal(key, value),
    getCurrentPage: () => window.location.hash.replace("#", "") || getPages()[0].id,
    clearProgramContextCache: () => {
      invalidateProgramCaches("hal-agent");
    },
    invalidateProgramCaches,
    setHalWidgetFeed: (feed) => {
      halWidgetFeed = feed;
    },
    refreshSideNoteMonitor,
    addSideNote,
    addOfficeTask: async (task) => {
      if (typeof OfficeTaskStore !== "undefined") {
        halOfficeTasks = await OfficeTaskStore.add(task);
      } else {
        halOfficeTasks.unshift(task);
        saveOfficeTasks();
      }
      invalidateProgramCaches("office-task");
      scheduleHalWidgetRefresh();
    },
    setOfficeTasks: async (tasks) => {
      if (typeof OfficeTaskStore !== "undefined" && typeof OfficeTaskStore.replaceAll === "function") {
        halOfficeTasks = await OfficeTaskStore.replaceAll(tasks);
      } else {
        halOfficeTasks = Array.isArray(tasks) ? tasks.slice() : [];
        saveOfficeTasks();
      }
      invalidateProgramCaches("office-task");
      scheduleHalWidgetRefresh();
    },
    startWorkSession,
    resetWorkSession,
    draftSessionHandoff: () => {
      halWorkSession.handoffNote = HalCore.draftHandoffNote(halWorkSession, halData);
      saveWorkSession();
    },
    buildEvidencePacketFromSession,
    clearEvidencePacket,
    clearReadinessDiagnostics,
    runProactiveCycle: (options) => runHalProactiveCycle(options),
    forceWidgetPlacement: (detail) => forceHalWidgetPlacement(detail),
    normalizeActions,
    executeRoute: async (result, trimmed, toolResults) => {
      if (!window.HalRouteExec) return null;
      return HalRouteExec.execute(result, trimmed, toolResults, buildHalAgentCtx());
    },
  }, extras || {});
}

async function handleHalSubmit(query) {
  const trimmed = String(query).trim();
  if (!trimmed) return;

  if (halModelAbortController) halModelAbortController.abort();
  halModelAbortController = new AbortController();
  const abortSignal = halModelAbortController.signal;

  if (window.HalVoice && HalVoice.cancelSpeech) HalVoice.cancelSpeech();
  if (halTypeTimer) {
    clearInterval(halTypeTimer);
    halTypeTimer = null;
  }

  if (halAskLoading) {
    const last = halChatHistory[halChatHistory.length - 1];
    if (last && last.role === "hal" && /gathering|thinking locally|reasoning locally|escalating locally/i.test(last.text)) {
      halChatHistory.pop();
    }
  }

  const effectiveQuery = expandHalUserQuery(trimmed);
  halAskLoading = true;
  renderHalScreen();
  halChatHistory.push({ role: "user", text: trimmed, actions: [] });
  saveChatHistory();

  const preRoute = routeHalCommand(effectiveQuery);
  const isModelLane = !!(preRoute.useModel || preRoute.useReasoning || preRoute.useEscalation);
  let placeholder = null;
  let streamRenderAt = 0;
  if (isModelLane && window.HalAgent) {
    const lane = preRoute.lane || "chat8b";
    const label = preRoute.useEscalation ? "Escalating" : preRoute.useReasoning ? "Reasoning" : "Gathering evidence";
    placeholder = { role: "hal", text: label + " locally…", lane, actions: [] };
    halChatHistory.push(placeholder);
    saveChatHistory();
    halTypeSig = halChatHistory.length + ":" + placeholder.text.length;
    renderChatLog();
    renderHalScreen();
  }

  const onToolProgress = placeholder
    ? (ev) => {
        if (!ev || !placeholder) return;
        placeholder.tools = placeholder.tools || [];
        if (ev.phase === "start" && ev.tool && !placeholder.tools.includes(ev.tool)) {
          placeholder.tools.push(ev.tool);
          placeholder.text = "Gathering: " + formatHalToolsUsed(placeholder.tools) + "…";
          renderChatLog();
        }
      }
    : undefined;

  const onToken = placeholder
    ? (partial) => {
        if (!partial) return;
        placeholder.text = partial;
        const now = Date.now();
        if (now - streamRenderAt < 40) return;
        streamRenderAt = now;
        renderChatLog();
        setInlineHalStreamingText(partial);
      }
    : undefined;

  let outcome = null;
  try {
    if (window.HalAgent) {
      outcome = await HalAgent.processQuery(
        effectiveQuery,
        buildHalAgentCtx(onToken || onToolProgress ? { onToken, onToolProgress, abortSignal } : { abortSignal }),
      );
    } else {
      outcome = await HalRouteExec.execute(preRoute, effectiveQuery, {}, buildHalAgentCtx({ abortSignal }));
    }
    if (!outcome) {
      outcome = {
        text: "HAL did not return a response. Try again or ask a simpler local question.",
        lane: "local",
        intent: "error",
        actions: [],
      };
    }

    if (placeholder) {
      placeholder.text = outcome.text;
      placeholder.lane = outcome.lane || placeholder.lane;
      placeholder.actions = normalizeActions(outcome.actions);
      placeholder.followUpChips = outcome.followUpChips || [];
      placeholder.intent = outcome.intent || "";
      placeholder.spokenScript = outcome.spokenScript || "";
      placeholder.userQuery = trimmed;
      placeholder.tools = (outcome.plan && outcome.plan.tools) || placeholder.tools || [];
      placeholder.toolSummaries = summarizeToolResultsBrief(outcome.toolResults);
      placeholder.agentLoopTurns = outcome.agentLoopTurns || 0;
      halTypeSig = halChatHistory.length + ":" + String(outcome.text || "").length;
    } else {
      halChatHistory.push({
        role: "hal",
        text: outcome.text,
        lane: outcome.lane || "local",
        actions: normalizeActions(outcome.actions),
        followUpChips: outcome.followUpChips || [],
        intent: outcome.intent || "",
        spokenScript: outcome.spokenScript || "",
        userQuery: trimmed,
        tools: (outcome.plan && outcome.plan.tools) || [],
        toolSummaries: summarizeToolResultsBrief(outcome.toolResults),
        agentLoopTurns: outcome.agentLoopTurns || 0,
      });
    }
    logAudit(trimmed, outcome.intent);
  } catch (error) {
    if (error && error.name === "AbortError") return;
    const detail = error && error.message ? error.message : String(error);
    const failText =
      "HAL hit an error and could not finish: " +
      detail +
      ". If this keeps happening, restart Start Program and confirm Ollama is running.";
    if (placeholder) {
      placeholder.text = failText;
      placeholder.lane = "error";
    } else {
      halChatHistory.push({ role: "hal", text: failText, lane: "error", actions: [] });
    }
    if (typeof RuntimeIssues !== "undefined") RuntimeIssues.record("hal-chat", error);
    logAudit(trimmed, "error");
  } finally {
    halAskLoading = false;
    saveChatHistory();
    renderChatLog();
    renderAuditLog();
    if (outcome && outcome.refreshHal) renderHalScreen();
    if (outcome && outcome.refreshPanel && currentDrawerKey) renderPanel(currentDrawerKey);
    if (outcome && /^sidenotes:/.test(String(outcome.intent || ""))) scrollHalPanelIntoView("sidenotes");
    renderHalScreen();
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function bindOpenPageButtons(root) {
  root.querySelectorAll("[data-open-page]").forEach((button) => {
    button.addEventListener("click", () => {
      const target = button.dataset.openPage;
      logAudit("Open " + target, "navigate: drawer");
      closeDrawer();
      if (isHalPanelTarget(target)) {
        if (halPage && halPage.hidden) select("hal");
        handleHalSurfaceNav(target);
        return;
      }
      select(target);
    });
  });
}

function bindHalCommands(root) {
  root.querySelectorAll("[data-hal-command]").forEach((button) => {
    button.addEventListener("click", () => {
      const cmd = button.dataset.halCommand;
      if (currentDrawerKey === "askHal") {
        handleHalSubmit(cmd);
      } else {
        openDrawer("askHal");
        setTimeout(() => handleHalSubmit(cmd), 50);
      }
    });
  });
}

function runtimeIssuesDrawerHtml() {
  if (typeof RuntimeIssues === "undefined") return "";
  const issues = RuntimeIssues.list().slice(0, 6);
  if (!issues.length) return "";
  return `<div class="drawer-card drawer-card--warn"><strong>Runtime issues</strong><ul class="drawer-checklist">${issues
    .map((item) => `<li>${escapeHtml(item.source)}: ${escapeHtml(item.message)}</li>`)
    .join("")}</ul></div>`;
}

function drawerSourceItems() {
  const staticItems = (halData.sources && halData.sources.items) || [];
  const live = halWidgetFeed && halWidgetFeed.sourceHealth;
  if (!live) return staticItems;
  const labels = { softdent: "SoftDent", quickbooks: "QuickBooks", documents: "Documents", library: "Library" };
  return Object.keys(live).map((key) => {
    const h = live[key] || {};
    const fallback = staticItems.find((item) => item.target === key) || {};
    const connectionStatus = h.connectionStatus || (h.hasData ? "Connected" : fallback.status || "Missing");
    return {
      label: fallback.label || labels[key] || key,
      target: key,
      status: connectionStatus,
      detail: h.detail || fallback.detail || (h.hasData ? "Imported data loaded from local export cache." : "No import data loaded yet."),
      freshness: h.freshness || fallback.freshness || null,
      syncState: h.syncState || fallback.syncState || null,
      datasetSummary: h.datasetSummary || null,
      datasetLines: h.datasetLines || [],
      warning: h.hasData ? null : fallback.warning || null,
      checklist: fallback.checklist || [],
    };
  });
}

function sourceHealthCards(items) {
  if (!items || items.length === 0) return "";
  return `<div class="drawer-grid">${items
    .map((item) => {
      const warn = item.warning ? `<p class="drawer-warn">${escapeHtml(item.warning)}</p>` : "";
      const checklist = (item.checklist || [])
        .map((c) => `<li>${escapeHtml(c)}</li>`)
        .join("");
      const datasetLines = (item.datasetLines || [])
        .map((line) => `<li>${escapeHtml(line)}</li>`)
        .join("");
      const openBtn = item.target
        ? `<button class="drawer-action drawer-action--sm" type="button" data-open-page="${escapeHtml(item.target)}">Open ${escapeHtml(item.label)}</button>`
        : "";
      return `<div class="drawer-card drawer-card--source">
        <strong>${escapeHtml(item.label)}</strong>
        <span class="status-chip">${escapeHtml(item.status)}</span>
        <p>${escapeHtml(item.detail)}</p>
        ${item.datasetSummary ? `<p class="drawer-meta">Datasets: ${escapeHtml(item.datasetSummary)}</p>` : ""}
        ${item.freshness ? `<p class="drawer-meta">Freshness: ${escapeHtml(item.freshness)}</p>` : ""}
        ${item.syncState ? `<p class="drawer-meta">Sync: ${escapeHtml(item.syncState)}</p>` : ""}
        ${warn}
        ${datasetLines ? `<ul class="drawer-checklist">${datasetLines}</ul>` : ""}
        ${checklist ? `<ul class="drawer-checklist">${checklist}</ul>` : ""}
        ${openBtn}
      </div>`;
    })
    .join("")}</div>`;
}

function reasoningLanePanel() {
  const lanes = HalCore.deriveReasoningLanes(halData);
  const actions = (halData.reasoning && halData.reasoning.actions) || [];
  const laneHtml = lanes
    .map((lane) => {
      const entries = (lane.entries || [])
        .map(
          (entry) =>
            `<div class="drawer-card drawer-card--compact">
              <strong>${escapeHtml(entry.name)}</strong>
              <span class="status-chip${/blocked/i.test(entry.state) ? " status-chip--blocked" : ""}">${escapeHtml(entry.state)}</span>
              <p>${escapeHtml(entry.nextAction)}</p>
              <button class="drawer-action drawer-action--sm" type="button" data-open-page="${escapeHtml(entry.id)}">Open</button>
            </div>`,
        )
        .join("");
      return `<div class="drawer-section">
        <h3 class="drawer-section__title">${escapeHtml(lane.label)} (${lane.count})</h3>
        <p class="drawer-meta">${escapeHtml(lane.detail)}</p>
        <div class="drawer-grid">${entries || '<p class="drawer-meta">None</p>'}</div>
      </div>`;
    })
    .join("");
  const actionHtml = actions
    .map(
      (action) =>
        `<button class="drawer-action" type="button" data-hal-command="${escapeHtml(action.command)}">${escapeHtml(action.label)}</button>`,
    )
    .join("");
  return `${laneHtml}<div class="drawer-section"><h3 class="drawer-section__title">Actions</h3><div class="drawer-grid">${actionHtml}</div></div>${workSessionPanelHtml()}${evidencePacketPanelHtml()}`;
}

function workSurfacePanel(items) {
  if (!items || items.length === 0) return "";
  return `<div class="drawer-grid">${items
    .map((item) => {
      const reg = registryById(item.target);
      const related = reg && reg.related ? reg.related : [];
      const relatedBtns = related
        .map((id) => {
          const r = registryById(id);
          return r
            ? `<button class="status-chip hal-suggest__chip" type="button" data-open-page="${escapeHtml(id)}">${escapeHtml(r.name)}</button>`
            : "";
        })
        .join("");
      const blocked = reg && reg.blocked ? reg.blocked.map((b) => `<span class="status-chip status-chip--blocked">${escapeHtml(b)}</span>`).join("") : "";
      const pageTarget = item.target === "hal" || item.target === "sidenotes" ? "sidenotes" : item.target;
      return `<div class="drawer-card drawer-card--surface">
        <strong>${escapeHtml(item.label)}</strong>
        <p>${escapeHtml(item.detail)}</p>
        ${reg ? `<p class="drawer-meta">Safety: ${escapeHtml(reg.safety)} · ${escapeHtml(reg.state)}</p>` : ""}
        ${reg ? `<p class="drawer-meta">Next: ${escapeHtml(reg.nextAction)}</p>` : ""}
        ${blocked ? `<div>${blocked}</div>` : ""}
        <div class="drawer-card__actions">
          <button class="drawer-action drawer-action--sm" type="button" data-open-page="${escapeHtml(pageTarget)}">${pageTarget === "sidenotes" ? "Open SideNotes panel" : "Open page"}</button>
          <button class="drawer-action drawer-action--sm" type="button" data-hal-command="Explain ${escapeHtml(item.label)}">Explain</button>
          ${pageTarget === "sidenotes" ? `<button class="drawer-action drawer-action--sm" type="button" data-hal-command="Monitor sidenotes">Monitor</button>` : ""}
        </div>
        ${relatedBtns ? `<div class="hal-suggest">${relatedBtns}</div>` : ""}
      </div>`;
    })
    .join("")}</div>`;
}

function firewallPanel(data) {
  const examples = (data.examples || [])
    .map(
      (ex) =>
        `<button class="status-chip hal-suggest__chip" type="button" data-firewall-test="${escapeHtml(ex.text)}">${escapeHtml(ex.text)}</button>`,
    )
    .join("");
  return `
    <p>${escapeHtml(data.summary)}</p>
    <div><strong>Blocked</strong>${chips(data.blocked, true)}</div>
    <div><strong>Allowed</strong>${chips(data.allowed)}</div>
    <div class="drawer-section">
      <h3 class="drawer-section__title">Firewall simulator</h3>
      <p class="drawer-meta">Type a proposed action. With the firewall off, HAL routes the phrase through normal handlers instead of blocking it.</p>
      <form class="hal-chat__form" id="firewallSimForm" autocomplete="off">
        <input id="firewallSimInput" class="hal-chat__input" type="text" placeholder="e.g. Submit the denied claim" aria-label="Test firewall" />
        <button class="hal-chat__send" type="submit">Test</button>
      </form>
      <div class="drawer-card" id="firewallSimResult">Enter an action above to test.</div>
      <div class="hal-suggest">${examples}</div>
    </div>`;
}

function proactiveBriefingPanelHtml() {
  if (!window.HalProactive) return "";
  const briefing = halProactiveBriefing || HalProactive.getLastBriefing();
  if (!briefing) return "";
  const recs = briefing.recommendations || [];
  const cards = recs.length
    ? recs
        .slice(0, 6)
        .map(
          (item) =>
            `<div class="drawer-card drawer-card--compact">
              <strong>${escapeHtml(item.title)}</strong>
              <span class="status-chip${item.severity === "critical" ? " status-chip--blocked" : ""}">${escapeHtml(item.severity)}</span>
              <p>${escapeHtml(item.rationale)}</p>
              ${
                item.action && item.action.type === "navigate"
                  ? `<button class="drawer-action drawer-action--sm" type="button" data-open-page="${escapeHtml(item.action.target)}">Open ${escapeHtml(item.action.target)}</button>`
                  : item.action && item.action.command
                    ? `<button class="drawer-action drawer-action--sm" type="button" data-hal-command="${escapeHtml(item.action.command)}">${escapeHtml(item.action.command)}</button>`
                    : ""
              }
            </div>`,
        )
        .join("")
    : `<p class="drawer-meta">${escapeHtml(briefing.headline)}</p>`;
  return `<div class="drawer-section"><h3 class="drawer-section__title">HAL proactive assessment</h3><p class="drawer-meta">${escapeHtml(briefing.independenceNote)}</p><div class="drawer-grid">${cards}</div></div>`;
}

function prioritiesPanel() {
  const groups = HalCore.derivePriorityGroups(halData);
  const staticItems = (halData.priorities && halData.priorities.items) || [];
  const staticHtml = staticItems.length
    ? `<div class="drawer-section"><h3 class="drawer-section__title">Operator notes</h3>${numbered(staticItems)}</div>`
    : "";
  const groupHtml = groups
    .map((group) => {
      const cards = group.items
        .map(
          (item) =>
            `<div class="drawer-card drawer-card--compact">
              <strong>${escapeHtml(item.name)}</strong>
              <span class="status-chip${/blocked/i.test(item.state) ? " status-chip--blocked" : ""}">${escapeHtml(item.state)}</span>
              <p>${escapeHtml(item.nextAction)}</p>
              <button class="drawer-action drawer-action--sm" type="button" data-open-page="${escapeHtml(item.id)}">Open</button>
              <button class="drawer-action drawer-action--sm" type="button" data-hal-command="Draft review note for ${escapeHtml(item.name)}">Draft note</button>
            </div>`,
        )
        .join("");
      return `<div class="drawer-section"><h3 class="drawer-section__title">${escapeHtml(group.label)}</h3><div class="drawer-grid">${cards || '<p class="drawer-meta">None</p>'}</div></div>`;
    })
    .join("");
  return proactiveBriefingPanelHtml() + staticHtml + groupHtml + workSessionPanelHtml() + evidencePacketPanelHtml();
}

function statusPanel(data) {
  const laneDetails = HalCore.modelLaneDetails(halModels);
  return `
    <p>${escapeHtml(data.summary)}</p>
    ${chips(data.posture)}
    <p class="drawer-meta">Model health: ${escapeHtml(modelHealthSummary())}</p>
    <div class="drawer-grid">${laneDetails
      .map(
        (lane) =>
          `<div class="drawer-card">
            <strong>${escapeHtml(lane.name)}</strong>
            <span class="status-chip${lane.ready ? "" : " status-chip--blocked"}">${escapeHtml(lane.state)}${lane.ready ? " · ready" : " · offline"}</span>
            <p>${escapeHtml(lane.role)}</p>
            <p class="drawer-meta">Model: ${escapeHtml(lane.model)} · mode: ${escapeHtml(lane.mode)}</p>
            ${lane.nextStep ? `<p class="drawer-meta">Next: ${escapeHtml(lane.nextStep)}</p>` : ""}
          </div>`,
      )
      .join("")}</div>
    ${readinessPanelHtml()}
    ${operatorPanelHtml()}`;
}

function controlsPanel(data) {
  return `
    <p>${escapeHtml(data.summary)}</p>
    ${staffUseGateHtml()}
    ${readinessPanelHtml()}
    ${operatorPanelHtml()}`;
}

function chips(items, blocked = false) {
  if (!items || items.length === 0) return "";
  return `<div>${items
    .map((item) => `<span class="status-chip${blocked ? " status-chip--blocked" : ""}">${escapeHtml(item)}</span>`)
    .join("")}</div>`;
}

function numbered(items) {
  if (!items || items.length === 0) return "";
  return `<div class="drawer-grid">${items.map((item, i) => `<div class="drawer-card">${i + 1}. ${escapeHtml(item)}</div>`).join("")}</div>`;
}

function renderPanel(key) {
  const data = halData[key] || halData.status;
  const badge = drawerHealthBadge(key);
  drawerTitle.innerHTML = `${escapeHtml(data.title || "HAL Command Center")}${badge}`;

  if (key === "askHal") {
    if (halChatHistory.length === 0) {
      halChatHistory.push({ role: "hal", text: data.response, lane: "local", actions: [] });
      saveChatHistory();
    }
    drawerContent.innerHTML = `
      <p>${escapeHtml(data.summary)}</p>
      <p class="drawer-meta">Model health: ${escapeHtml(modelHealthSummary())}</p>
      ${workSessionPanelHtml()}
      ${evidencePacketPanelHtml()}
      ${readinessPanelHtml()}
      ${operatorPanelHtml()}
      <div class="hal-chat">
        <div class="hal-chat__log" id="halChatLog"></div>
        <div class="hal-suggest" id="halSuggest"></div>
        <form class="hal-chat__form" id="halChatForm" autocomplete="off">
          <input id="halChatInput" class="hal-chat__input" type="text"
            placeholder="Ask HAL to open a page, show priorities, or explain status" aria-label="Ask HAL" />
          <button class="hal-chat__send" type="submit">Send</button>
        </form>
        <p class="hal-chat__note">Local manager · read-only · external actions need human review</p>
      </div>
      <details class="hal-audit">
        <summary>Session log (<span id="halAuditCount">${halAudit.length}</span>)</summary>
        <div class="hal-audit__log" id="halAuditLog"></div>
      </details>
      <details class="hal-audit">
        <summary>Command examples</summary>
        <div class="hal-suggest" id="halExamples"></div>
      </details>`;
    const suggest = document.getElementById("halSuggest");
    (data.suggestions || []).forEach((text) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "status-chip hal-suggest__chip";
      chip.textContent = text;
      chip.addEventListener("click", () => handleHalSubmit(text));
      suggest.appendChild(chip);
    });
    const examples = document.getElementById("halExamples");
    (data.commandExamples || []).forEach((text) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "status-chip hal-suggest__chip";
      chip.textContent = text;
      chip.addEventListener("click", () => handleHalSubmit(text));
      examples.appendChild(chip);
    });
    document.getElementById("halChatForm").addEventListener("submit", (event) => {
      event.preventDefault();
      const input = document.getElementById("halChatInput");
      const value = input.value;
      input.value = "";
      handleHalSubmit(value);
    });
    renderChatLog();
    renderAuditLog();
    bindWorkSessionControls(drawerContent);
    bindEvidencePacketControls(drawerContent);
    bindReadinessControls(drawerContent);
    bindOperatorControls(drawerContent);
    bindOpenPageButtons(drawerContent);
    return;
  }

  if (key === "status") {
    drawerContent.innerHTML = statusPanel(data);
    bindReadinessControls(drawerContent);
    bindOperatorControls(drawerContent);
    return;
  }

  if (key === "controls") {
    drawerContent.innerHTML = controlsPanel(data);
    bindReadinessControls(drawerContent);
    bindOperatorControls(drawerContent);
    return;
  }

  if (key === "sources") {
    drawerContent.innerHTML = `<p>${escapeHtml(data.summary)}</p>${sourceHealthCards(drawerSourceItems())}${runtimeIssuesDrawerHtml()}`;
    bindOpenPageButtons(drawerContent);
    return;
  }

  if (key === "reasoning") {
    drawerContent.innerHTML = `<p>${escapeHtml(data.summary)}</p>${reasoningLanePanel()}`;
    bindOpenPageButtons(drawerContent);
    bindHalCommands(drawerContent);
    bindWorkSessionControls(drawerContent);
    bindEvidencePacketControls(drawerContent);
    return;
  }

  if (key === "workSurfaces") {
    drawerContent.innerHTML = `<p>${escapeHtml(data.summary)}</p>${workSurfacePanel(data.items)}`;
    bindOpenPageButtons(drawerContent);
    bindHalCommands(drawerContent);
    return;
  }

  if (key === "firewall") {
    drawerContent.innerHTML = firewallPanel(data);
    const form = document.getElementById("firewallSimForm");
    const input = document.getElementById("firewallSimInput");
    const result = document.getElementById("firewallSimResult");
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const verdict = HalCore.firewallVerdict(input.value, data, halData, halModels);
      result.innerHTML = `<strong>${verdict.allowed ? "Allowed" : "Blocked"}</strong><p>${escapeHtml(verdict.text)}</p>`;
      logAudit(input.value, verdict.intent);
      renderAuditLog();
    });
    drawerContent.querySelectorAll("[data-firewall-test]").forEach((button) => {
      button.addEventListener("click", () => {
        input.value = button.dataset.firewallTest;
        const verdict = HalCore.firewallVerdict(input.value, data, halData, halModels);
        result.innerHTML = `<strong>${verdict.allowed ? "Allowed" : "Blocked"}</strong><p>${escapeHtml(verdict.text)}</p>`;
        logAudit(input.value, verdict.intent);
        renderAuditLog();
      });
    });
    return;
  }

  if (key === "priorities") {
    drawerContent.innerHTML = prioritiesPanel();
    bindOpenPageButtons(drawerContent);
    bindHalCommands(drawerContent);
    bindWorkSessionControls(drawerContent);
    bindEvidencePacketControls(drawerContent);
    return;
  }

  if (key === "sidenotes") {
    drawerContent.innerHTML = sideNotesDrawerHtml();
    bindHalCommands(drawerContent);
    return;
  }

  drawerContent.innerHTML = `<p>${escapeHtml(data.summary || "")}</p>`;
}

function openDrawer(key) {
  currentDrawerKey = key;
  renderPanel(key);
  drawer.classList.add("open");
  drawer.setAttribute("aria-hidden", "false");
}

function closeDrawer() {
  currentDrawerKey = null;
  drawer.classList.remove("open");
  drawer.setAttribute("aria-hidden", "true");
}

function handleNr2Print(scope) {
  const PU = typeof PrintUtils !== "undefined" ? PrintUtils : null;
  if (!PU) {
    showHalActionNotice("Print utilities failed to load. Reload the app.", "warn");
    return;
  }
  const pageId = resolvePageId(window.location.hash);
  const page = getPages().find((p) => p.id === pageId);
  const printScope = scope || "page";
  if (printScope === "drawer") {
    PU.printDrawer();
    return;
  }
  PU.printCurrentView({
    pageId,
    title: page ? page.title : pageId,
    halPageVisible: halPage && !halPage.hidden,
    drawerOpen: drawer && drawer.classList.contains("open"),
  });
}

function handleNr2Export(scope) {
  const EU = typeof ExportUtils !== "undefined" ? ExportUtils : null;
  if (!EU) {
    showHalActionNotice("Export utilities failed to load. Reload the app.", "warn");
    return;
  }
  const pageId = resolvePageId(window.location.hash);
  EU.exportCurrentPage({
    pageId,
    snapshot: halProgramSnapshot,
    feed: halWidgetFeed,
    halPageVisible: halPage && !halPage.hidden,
  });
}

let nr2OpsHealth = null;
let nr2SidebarStatus = "All systems operational";
let nr2SidebarBadges = {};

function removeOpsHealthBanner() {
  const existing = document.getElementById("opsHealthBanner");
  if (existing) existing.remove();
}

function renderOpsHealthBanner(health) {
  if (typeof document === "undefined") return;
  let banner = document.getElementById("opsHealthBanner");
  if (!banner) {
    banner = document.createElement("div");
    banner.id = "opsHealthBanner";
    banner.className = "ops-health-banner";
    const app = document.querySelector(".app");
    if (app && app.parentNode) app.parentNode.insertBefore(banner, app);
    else document.body.prepend(banner);
  }
  const status = String(health?.status || "degraded").toUpperCase();
  const failed = (health?.integrations || []).filter((row) => !row.ok).slice(0, 2);
  const hint = failed.map((row) => row.label).join(", ");
  banner.innerHTML = `<strong>Integration health: ${escapeHtml(status)}</strong><span>${escapeHtml(hint || "Review imports and automation jobs.")} · Ask HAL: integration health</span>`;
}

function buildSidebarPages() {
  if (typeof PageSchema === "undefined" || !PageSchema.PAGES) return {};
  const pages = PageSchema.PAGES;
  const out = {};
  Object.keys(pages).forEach((id) => {
    const page = pages[id];
    out[id] = Object.assign({}, page, { badge: nr2SidebarBadges[id] || "" });
  });
  return out;
}

async function refreshOpsHealthStatus() {
  let status = nr2DesignSchemaVersion ? `Design ${nr2DesignSchemaVersion}` : "All systems operational";
  const badges = {};
  try {
    if (typeof PortalOps !== "undefined" && PortalOps.getIntegrationHealth) {
      const health = await PortalOps.getIntegrationHealth();
      nr2OpsHealth = health;
      const hs = String(health?.status || "").toLowerCase();
      if (hs === "degraded" || hs === "fail") {
        status = `Integration ${hs.toUpperCase()} — ${health.ok_count || 0}/${health.enabled_count || 0} OK`;
        renderOpsHealthBanner(health);
      } else {
        removeOpsHealthBanner();
      }
    }
  } catch {
    removeOpsHealthBanner();
  }

  const feed = halWidgetFeed;
  if (feed && feed.widgets) {
    const widgets = Object.values(feed.widgets);
    const failed = widgets.filter((w) => w && w.status === "FAILED").length;
    const degraded = widgets.filter((w) => w && w.status === "DEGRADED").length;
    if (failed || degraded) {
      status = failed
        ? `${failed} widget(s) failed — review HAL monitor`
        : `${degraded} widget(s) degraded — review HAL monitor`;
      badges.hal = String(failed || degraded);
    }
  }

  const jq = halProgramSnapshot && halProgramSnapshot.journalPostingQueue;
  const pending = (jq && jq.items ? jq.items : []).filter((row) => /pending/i.test(String(row.status || ""))).length;
  if (pending > 0) badges.documents = String(pending);

  nr2SidebarStatus = status;
  nr2SidebarBadges = badges;
  const activeId = resolvePageId(window.location.hash);
  renderSidebar(activeId);
}

let halTypeSig = null;
let halTypeTimer = null;

function setInlineHalStreamingText(text) {
  if (!halPageRoot) return;
  const box = halPageRoot.querySelector(".hp-inline-chat");
  if (!box) return;
  const rows = box.querySelectorAll(".hp-chat-row--hal");
  if (!rows.length) return;
  const p = rows[rows.length - 1].querySelector("p");
  if (!p) return;
  if (halTypeTimer) {
    clearInterval(halTypeTimer);
    halTypeTimer = null;
  }
  p.classList.remove("hp-typing");
  p.textContent = text;
  box.scrollTop = box.scrollHeight;
}

function halSpeechContextForLastReply(displayText) {
  const hist = halChatHistory || [];
  const lastHal = hist.length ? hist[hist.length - 1] : null;
  let query = lastHal && lastHal.userQuery ? lastHal.userQuery : "";
  if (!query) {
    for (let i = hist.length - 2; i >= 0; i--) {
      if (hist[i].role === "user") {
        query = hist[i].text;
        break;
      }
    }
  }
  const route = lastHal && lastHal.intent ? { intent: lastHal.intent } : {};
  const preferBrief =
    window.HalAgent && typeof HalAgent.getWorkingMemory === "function"
      ? !!HalAgent.getWorkingMemory().preferBrief
      : false;
  const spokenText =
    lastHal && lastHal.spokenScript
      ? lastHal.spokenScript
      : window.HalCore && HalCore.toSpokenScript
        ? HalCore.toSpokenScript(displayText, query, route, { preferBrief })
        : "";
  return { query, route, preferBrief, spokenText };
}

function typewriteLastHalMessage() {
  if (!halPageRoot) return;
  const box = halPageRoot.querySelector(".hp-inline-chat");
  if (!box) return;
  const rows = box.querySelectorAll(".hp-chat-row");
  if (!rows.length) return;
  const last = rows[rows.length - 1];
  if (!last.classList.contains("hp-chat-row--hal")) return;
  const p = last.querySelector("p");
  if (!p) return;
  const full = p.textContent;
  const sig = halChatHistory.length + ":" + full.length;
  if (sig === halTypeSig) return;
  halTypeSig = sig;
  if (halTypeTimer) {
    clearInterval(halTypeTimer);
    halTypeTimer = null;
  }
  const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce || full.length < 2) {
    p.textContent = full;
    p.classList.remove("hp-typing");
    if (window.HalVoice && HalVoice.speakHalReply) {
      const speechCtx = halSpeechContextForLastReply(full);
      HalVoice.speakHalReply(full, { interrupt: true, ...speechCtx });
    }
    return;
  }
  p.textContent = "";
  p.classList.add("hp-typing");
  const step = Math.max(1, Math.ceil(full.length / 110));
  const iterations = Math.ceil(full.length / step);
  let speechMs = 2400;
  const speechCtx = halSpeechContextForLastReply(full);
  if (window.HalVoice) {
    if (HalVoice.speakHalReply) {
      const spoken = HalVoice.speakHalReply(full, { interrupt: true, ...speechCtx });
      speechMs = (spoken && spoken.durationMs) || speechMs;
    } else if (HalVoice.estimateDurationMs) {
      speechMs = HalVoice.estimateDurationMs(speechCtx.spokenText || full);
    }
  }
  // Type quickly enough to stay ahead of HAL's voice, but not instant.
  const typeDelayMs = Math.max(16, Math.min(42, Math.floor(speechMs / Math.max(iterations, 1))));
  let i = 0;
  halTypeTimer = setInterval(() => {
    i += step;
    p.textContent = full.slice(0, i);
    box.scrollTop = box.scrollHeight;
    if (i >= full.length) {
      clearInterval(halTypeTimer);
      halTypeTimer = null;
      p.textContent = full;
      p.classList.remove("hp-typing");
    }
  }, typeDelayMs);
}

function updateHalStressUi() {
  const panel = document.getElementById("hpStressPanel");
  if (!panel) return;
  const st = halStressTest;
  const total = Number(st.total) || 0;
  const processed = Number(st.processed) || 0;
  const pct = total > 0 ? Math.min(100, Math.round((processed / total) * 100)) : 0;

  const set = (id, text) => {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  };

  set("hpStressStatus", st.status || "Idle");
  set("hpStressProcessed", processed.toLocaleString());
  set("hpStressTotal", total.toLocaleString());
  set("hpStressRate", st.rate ? st.rate.toLocaleString() + " q/s" : "—");
  set("hpStressFailures", String(st.failureTotal || 0));
  set("hpStressDistinct", String(st.distinctFailures || 0));
  set("hpStressIntents", st.intentCount ? String(st.intentCount) : "—");

  const bar = document.getElementById("hpStressBar");
  if (bar) bar.style.width = pct + "%";

  const statusEl = document.getElementById("hpStressStatus");
  if (statusEl) {
    statusEl.className = "hp-stress__status";
    if (st.status === "Pass") statusEl.classList.add("hp-stress__status--ok");
    else if (st.status === "Fail") statusEl.classList.add("hp-stress__status--fail");
    else if (st.running) statusEl.classList.add("hp-stress__status--run");
  }

  const failEl = document.getElementById("hpStressFailures");
  if (failEl) failEl.classList.toggle("hp-stress__fail-num", !!st.failureTotal);

  const list = document.getElementById("hpStressFailList");
  if (list && Array.isArray(st.topFailures)) {
    list.innerHTML = st.topFailures.length
      ? st.topFailures
          .slice(0, 12)
          .map(
            (f) =>
              `<li><span class="hp-stress__fail-count">${escapeHtml(String(f.count))}×</span> <code>${escapeHtml(f.stage)}</code> — ${escapeHtml(f.error)}<br><em class="hp-muted">${escapeHtml(String(f.example || "").slice(0, 120))}</em></li>`,
          )
          .join("")
      : '<li class="hp-stress__empty">No failures yet.</li>';
  }

  const runBtn = document.getElementById("hpStressRun");
  const stopBtn = document.getElementById("hpStressStop");
  const countInput = document.getElementById("hpStressCount");
  if (runBtn) runBtn.disabled = !!st.running;
  if (stopBtn) stopBtn.disabled = !st.running;
  if (countInput) countInput.disabled = !!st.running;
}

async function startHalStressTest(count) {
  if (halStressTest.running || !window.HalStressHarness || !window.HalSkills) return;
  const total = Math.max(100, Number(count) || 2000000);
  const snapshot = await loadProgramSnapshot();
  const feed = (snapshot && snapshot.widgets) || HalSkills.buildWidgetFeed(snapshot);

  halStressRunner = HalStressHarness.createRunner({
    count: total,
    HalCore,
    HalSkills,
    HalAgent: window.HalAgent,
    halData,
    halModels,
    pages: getPages(),
    snapshot,
    feed,
  });

  halStressTest = {
    running: true,
    total,
    processed: 0,
    failureTotal: 0,
    distinctFailures: 0,
    intentCount: 0,
    rate: 0,
    status: "Running",
    topFailures: [],
  };
  updateHalStressUi();

  const batchSize = total >= 1000000 ? 100000 : total >= 100000 ? 50000 : 10000;
  const started = performance.now();
  let lastUi = started;

  function pump() {
    if (!halStressRunner || !halStressTest.running) return;
    const state = halStressRunner.runChunk(batchSize);
    const summary = halStressRunner.summary();
    const elapsed = (performance.now() - started) / 1000;
    halStressTest.processed = state.processed;
    halStressTest.failureTotal = summary.failureTotal;
    halStressTest.distinctFailures = summary.distinctFailures;
    halStressTest.intentCount = Object.keys(summary.intentCounts).length;
    halStressTest.rate = elapsed > 0 ? Math.round(state.processed / elapsed) : 0;
    halStressTest.topFailures = summary.topFailures;

    const now = performance.now();
    if (now - lastUi > 120 || state.done) {
      updateHalStressUi();
      lastUi = now;
    }

    if (state.done) {
      halStressTest.running = false;
      halStressTest.status = summary.failureTotal ? "Fail" : "Pass";
      halStressRunner = null;
      updateHalStressUi();
      return;
    }
    setTimeout(pump, 0);
  }

  setTimeout(pump, 0);
}

function stopHalStressTest() {
  if (halStressRunner) halStressRunner.cancel();
  if (!halStressTest.running) return;
  halStressTest.running = false;
  halStressTest.status = "Stopped";
  if (halStressRunner) {
    const summary = halStressRunner.summary();
    halStressTest.processed = summary.processed;
    halStressTest.failureTotal = summary.failureTotal;
    halStressTest.distinctFailures = summary.distinctFailures;
    halStressTest.topFailures = summary.topFailures;
    halStressRunner = null;
  }
  updateHalStressUi();
}

function renderHalScreen() {
  if (!halPageRoot || !window.HalPage) return;
  HalPage.render({
    root: halPageRoot,
    halData,
    halModels,
    halAudit,
    halChatHistory,
    halAskDraft,
    halAskLoading,
    halInlineFirewallResult: null,
    halSideNotes,
    halSideNoteMonitor: halSideNoteMonitor || (window.HalSkills ? HalSkills.buildSideNoteMonitor(halSideNotes) : null),
    halSideNotesInbox,
    halWidgetFeed,
    halProgramSnapshot,
    halProactiveBriefing,
    halStressTest,
    halAgentHealth: window.HalAgent ? HalAgent.getHealth() : null,
    sidenotesHubPath: nr2SidenotesHubPath,
  });
  typewriteLastHalMessage();
}

function renderSidebar(activeId) {
  if (!sidebar || !window.UI || typeof PageSchema === "undefined") return;
  sidebar.innerHTML = UI.Sidebar({
    activeId,
    navGroups: PageSchema.NAV_GROUPS,
    pages: buildSidebarPages(),
    practice: PageSchema.PRACTICE,
    user: {
      initials: "NR",
      name: PageSchema.PRACTICE.operator || "Dr. Michael Reno",
      role: "Owner",
    },
    status: nr2SidebarStatus,
  });
  nav = document.getElementById("nav");
  Object.keys(buttons).forEach((key) => delete buttons[key]);
  if (!nav) return;
  nav.querySelectorAll("[data-nav]").forEach((button) => {
    const id = button.getAttribute("data-nav");
    buttons[id] = button;
    button.addEventListener("click", () => select(id));
  });
}

function select(id) {
  const pageId = resolvePageId(id);
  const page = getPages().find((p) => p.id === pageId) || getPages().find((p) => p.id === defaultPageId()) || getPages()[0];
  if (!page) return;
  const isHal = page.id === "hal" && PageViews && !PageViews.hasPage(page.id);
  if (halPage) halPage.hidden = !isHal;
  if (appPage) {
    appPage.hidden = isHal;
    if (!isHal) {
      appPage.hidden = false;
      if (PageViews && PageViews.hasPage(page.id)) {
        PageViews.renderPageView(appPage, halData, page.id, select, halWidgetFeed, halProgramSnapshot);
      } else if (window.UI && window.UI.ErrorState) {
        appPage.innerHTML = `<div class="page-view"><article class="pv pv--app pv--canvas" data-pv-page="${page.id}">${UI.ErrorState({
          title: "Page not available",
          message: `Could not open "${page.id}". Choose a page from the sidebar or restart Start Program.`,
        })}</article></div>`;
      }
    }
  }
  renderSidebar(page.id);
  if (isHal) {
    renderHalScreen();
    activateSideNotesPanel().catch(() => {
      /* sidenotes inbox optional */
    });
  }
  closeDrawer();
  const nextHash = "#" + page.id;
  if (window.location.hash !== nextHash) {
    window.location.hash = page.id;
  }
}

function assertDesignSchemaLoaded() {
  if (typeof NR2Boot !== "undefined" && !NR2Boot.ready) return false;
  if (typeof PageSchema !== "undefined" && typeof PageChrome !== "undefined") return true;
  const frame = document.getElementById("pageFrame");
  if (frame) {
    frame.innerHTML =
      '<div class="pv-state pv-state--error" role="alert"><strong class="pv-state__title">Design schema failed to load</strong><p class="pv-state__msg">page-schema.js and page-chrome.js are required. Restart the desktop app.</p></div>';
  }
  return false;
}

function renderSchemaVersionMismatch(pythonVersion, jsVersion) {
  const frame = document.getElementById("pageFrame");
  const sidebar = document.getElementById("sidebar");
  if (sidebar) sidebar.innerHTML = "";
  if (!frame) return;
  frame.innerHTML =
    `<div class="pv-state pv-state--error nr2-boot-error" role="alert">` +
    `<strong class="pv-state__title">Desktop build mismatch</strong>` +
    `<p class="pv-state__msg">Python shell reports <strong>${String(pythonVersion).replace(/</g, "&lt;")}</strong> but the loaded page schema is <strong>${String(jsVersion).replace(/</g, "&lt;")}</strong>.</p>` +
    `<p class="pv-state__msg">Close this window completely, then launch <strong>Start Program</strong> again.</p>` +
    `</div>`;
}

renderRuntimeModeBanner();
if (assertDesignSchemaLoaded()) {
  renderSidebar(resolvePageId(window.location.hash));
}

drawerClose.addEventListener("click", closeDrawer);

if (halPage) {
  halPage.addEventListener("submit", async (event) => {
    if (event.target.id !== "hpAskForm") return;
    event.preventDefault();
    const input = document.getElementById("hpAskInput");
    const value = input ? input.value : "";
    halAskDraft = value;
    await handleHalSubmit(value);
    if (input) {
      input.value = "";
      halAskDraft = "";
    }
    renderHalScreen();
  });

  halPage.addEventListener("keydown", (event) => {
    const target = event.target;
    if (target && target.id === "hpSideNoteInput" && event.key === "Enter") {
      event.preventDefault();
      const text = target.value;
      if (String(text).trim().length >= 2) {
        addSideNote(text);
        target.value = "";
        renderHalScreen();
      }
      return;
    }
    if (target && target.id === "hpAskInput" && event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      const form = document.getElementById("hpAskForm");
      if (!form) return;
      if (typeof form.requestSubmit === "function") form.requestSubmit();
      else form.dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
      return;
    }
    const surfOpen = event.target.closest("[data-hal-surf-open]");
    if (surfOpen && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      handleHalSurfaceNav(surfOpen.getAttribute("data-hal-surf-open"));
      return;
    }
    const halCmdKey = event.target.closest("[data-hal-cmd],[data-hal-activity-cmd]");
    if (halCmdKey && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      const cmd =
        halCmdKey.getAttribute("data-hal-cmd") || halCmdKey.getAttribute("data-hal-activity-cmd");
      if (cmd) {
        handleHalSubmit(cmd).then(() => renderHalScreen());
      }
    }
  });

  halPage.addEventListener("dblclick", async (event) => {
    const ring = event.target.closest("[data-hal-ring-cmd]");
    if (!ring) return;
    const cmd = ring.getAttribute("data-hal-ring-cmd");
    if (!cmd) return;
    await handleHalSubmit(cmd);
    renderHalScreen();
  });

  halPage.addEventListener("click", async (event) => {
    const copyResponse = event.target.closest("[data-hal-copy-response]");
    if (copyResponse) {
      const row = copyResponse.closest(".hp-chat-row");
      const text = row && row.querySelector("p") ? row.querySelector("p").textContent : "";
      if (text) {
        DesktopBridge.writeClipboard(text)
          .then((ok) => {
            if (ok) logAudit("Copy HAL response", "clipboard: hal-response");
            renderAuditLog();
          })
          .catch(() => {
            /* clipboard optional */
          });
      }
      return;
    }
    const drawerBtn = event.target.closest("[data-hal-drawer]");
    if (drawerBtn) {
      openDrawer(drawerBtn.getAttribute("data-hal-drawer"));
      return;
    }
    const surfOpen = event.target.closest("[data-hal-surf-open]");
    if (surfOpen) {
      event.stopPropagation();
      handleHalSurfaceNav(surfOpen.getAttribute("data-hal-surf-open"));
      return;
    }
    const sourceOpen = event.target.closest("[data-hal-source-open]");
    if (sourceOpen) {
      event.stopPropagation();
      handleHalPageNav(sourceOpen.getAttribute("data-hal-source-open"));
      return;
    }
    const insightOpen = event.target.closest("[data-hal-insight-open]");
    if (insightOpen) {
      event.stopPropagation();
      handleHalPageNav(insightOpen.getAttribute("data-hal-insight-open"));
      return;
    }
    const widgetCard = event.target.closest("[data-hal-widget-key]");
    if (widgetCard && !event.target.closest("[data-hal-widget-nav]") && !event.target.closest("[data-hal-action]")) {
      let cmd = widgetCard.getAttribute("data-hal-cmd");
      if (!cmd) {
        const key = widgetCard.getAttribute("data-hal-widget-key");
        if (key) cmd = `Explain ${key} widget on this page`;
      }
      if (cmd) await runHalPageCmd(cmd, { openHal: false });
      return;
    }
    const activityReplay = event.target.closest("[data-hal-activity-cmd]");
    if (activityReplay) {
      const cmd = activityReplay.getAttribute("data-hal-activity-cmd");
      if (cmd) await runHalPageCmd(cmd);
      return;
    }
    const widgetNav = event.target.closest("[data-hal-widget-nav]");
    if (widgetNav) {
      const target = widgetNav.getAttribute("data-hal-widget-nav");
      if (target) select(target);
      return;
    }
    const suggest = event.target.closest("[data-hal-suggest]");
    if (suggest) {
      await runHalPageCmd(suggest.getAttribute("data-hal-suggest"));
      return;
    }
    const followup = event.target.closest("[data-hal-followup]");
    if (followup) {
      await handleHalSubmit(followup.getAttribute("data-hal-followup"));
      return;
    }
    const voiceTest = event.target.closest("[data-hal-voice-test]");
    if (voiceTest) {
      if (window.HalVoice) HalVoice.test();
      return;
    }
    const stressRun = event.target.closest("[data-hal-stress-run]");
    if (stressRun) {
      const countInput = document.getElementById("hpStressCount");
      const count = countInput ? parseInt(countInput.value, 10) : 2000000;
      startHalStressTest(count);
      return;
    }
    const stressStop = event.target.closest("[data-hal-stress-stop]");
    if (stressStop) {
      stopHalStressTest();
      return;
    }
    const sideNoteAdd = event.target.closest("[data-hal-sidenote-add]");
    if (sideNoteAdd) {
      const input = document.getElementById("hpSideNoteInput");
      const text = input ? input.value : "";
      if (String(text).trim().length >= 2) {
        addSideNote(text);
        if (input) input.value = "";
        renderHalScreen();
      }
      return;
    }
    const sideNotePin = event.target.closest("[data-hal-sidenote-pin]");
    if (sideNotePin) {
      const id = sideNotePin.getAttribute("data-hal-sidenote-pin");
      const idx = halSideNotes.findIndex((n) => n.noteId === id);
      if (idx >= 0) {
        const nextStatus = halSideNotes[idx].status === "pinned" ? "open" : "pinned";
        halSideNotes[idx] = HalSkills.applySideNoteUpdate(halSideNotes[idx], { status: nextStatus });
        saveSideNotes();
        renderHalScreen();
      }
      return;
    }
    const sideNoteArchive = event.target.closest("[data-hal-sidenote-archive]");
    if (sideNoteArchive) {
      const id = sideNoteArchive.getAttribute("data-hal-sidenote-archive");
      const idx = halSideNotes.findIndex((n) => n.noteId === id);
      if (idx >= 0) {
        halSideNotes[idx] = HalSkills.applySideNoteUpdate(halSideNotes[idx], { status: "archived" });
        saveSideNotes();
        renderHalScreen();
      }
      return;
    }
    const cmd = event.target.closest("[data-hal-cmd]");
    if (cmd) {
      await runHalPageCmd(cmd.getAttribute("data-hal-cmd"));
    }
  });
}

if (appPage) {
  appPage.addEventListener("click", async (event) => {
    if (await handleHalChromeInteraction(event)) return;
    const configure = event.target.closest("[data-hal-configure-export]");
    if (configure) {
      const widgetKey = configure.getAttribute("data-hal-configure-export") || "this widget";
      const labelMap = {
        newPatients: "SoftDent new patient export",
        treatmentPlanSummary: "SoftDent treatment plan summary export",
        caseAcceptance: "SoftDent case acceptance export",
      };
      select("softdent");
      showHalActionNotice(
        `${labelMap[widgetKey] || "Source export"} is not configured yet. Add the export file to the SoftDent import folder, then run Force HAL placement.`,
        "warn",
      );
      return;
    }
    const navBtn = event.target.closest("[data-pv-nav]");
    if (navBtn) select(navBtn.getAttribute("data-pv-nav"));
  });
}

document.addEventListener("click", (event) => {
  const printBtn = event.target.closest("[data-nr2-print]");
  if (printBtn) {
    event.preventDefault();
    handleNr2Print(printBtn.getAttribute("data-nr2-print"));
    return;
  }
  const exportBtn = event.target.closest("[data-nr2-export]");
  if (exportBtn) {
    event.preventDefault();
    handleNr2Export(exportBtn.getAttribute("data-nr2-export"));
    return;
  }
  if (!currentDrawerKey) return;
  const panel = drawer.querySelector(".drawer__panel");
  if (panel && panel.contains(event.target)) return;
  if (
    event.target.closest &&
    (event.target.closest("[data-hal-drawer]") || event.target.closest("#nav"))
  )
    return;
  closeDrawer();
});
window.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && String(event.key || "").toLowerCase() === "p") {
    event.preventDefault();
    handleNr2Print("page");
    return;
  }
  if (event.key === "Escape") closeDrawer();
});
window.addEventListener("hashchange", () => {
  select(window.location.hash);
});
window.addEventListener("hal-live-widget-event", handleHalLiveWidgetEvent);
window.addEventListener("hal-force-widget-placement", (event) => {
  forceHalWidgetPlacement((event && event.detail) || {}).catch(() => {
    /* force placement optional */
  });
});

async function loadPersistedState() {
  halAudit = (await DesktopBridge.storageGet("halAudit")) || [];
  halChatHistory = (await DesktopBridge.storageGet("halChatHistory")) || [];
  halWorkSession = (await DesktopBridge.storageGet("halWorkSession")) || null;
  halEvidencePacket = (await DesktopBridge.storageGet("halEvidencePacket")) || null;
  halReadinessDiagnostics = (await DesktopBridge.storageGet("halDiagnostics")) || null;
  halOperatorReport = (await DesktopBridge.storageGet("halOperatorReport")) || null;
  if (typeof OfficeTaskStore !== "undefined") {
    halOfficeTasks = await OfficeTaskStore.load();
  } else {
    halOfficeTasks = (await DesktopBridge.storageGet("halOfficeTasks")) || [];
  }
  halSideNotes = (await DesktopBridge.storageGet("halSideNotes")) || [];
  halSideNoteMonitor = (await DesktopBridge.storageGet("halSideNoteMonitor")) || null;
  refreshSideNoteMonitor();
}

async function refreshImportsInBackground() {
  if (typeof ImportCoordinator !== "undefined") {
    try {
      await ImportCoordinator.refresh({ reason: "background" });
    } catch {
      /* background import sync optional */
    }
    return;
  }
  if (!window.Services || typeof Services.refreshImports !== "function") return;
  try {
    await Services.refreshImports();
    invalidateProgramCaches("import-refresh");
    await scheduleHalWidgetRefresh();
  } catch {
    /* background import sync optional */
  }
}

async function boot() {
  renderRuntimeModeBanner();
  if (typeof NR2Boot !== "undefined" && !NR2Boot.ready) return;
  await loadPersistedState();
  try {
    if (typeof NR2Boot !== "undefined" && NR2Boot.verifyDesktopManifest) {
      const manifest = await NR2Boot.verifyDesktopManifest();
      if (!manifest.ok) {
        if (manifest.pythonVersion && manifest.jsVersion) {
          renderSchemaVersionMismatch(manifest.pythonVersion, manifest.jsVersion);
        } else if (manifest.manifestVersion && manifest.jsVersion) {
          renderSchemaVersionMismatch(manifest.manifestVersion, manifest.jsVersion);
        }
        return;
      }
    }
    const info = await DesktopBridge.getAppInfo();
    if (info && info.sidenotesHub) nr2SidenotesHubPath = info.sidenotesHub;
    if (info && info.designSchemaVersion) {
      nr2DesignSchemaVersion = info.designSchemaVersion;
      if (PageSchema && PageSchema.SCHEMA_VERSION && info.designSchemaVersion !== PageSchema.SCHEMA_VERSION) {
        renderSchemaVersionMismatch(info.designSchemaVersion, PageSchema.SCHEMA_VERSION);
        return;
      }
      renderSidebar(window.location.hash.replace("#", "") || getPages()[0].id);
    }
  } catch {
    /* desktop info optional in browser preview */
  }
  try {
    halData = await DesktopBridge.readDataFile("hal-manager.json");
  } catch {
    halData = FALLBACK_HAL;
  }
  try {
    halModels = await DesktopBridge.readDataFile("hal-models.json");
  } catch (err) {
    if (typeof RuntimeIssues !== "undefined") RuntimeIssues.record("app.boot", err, { file: "hal-models.json" });
    halModels = FALLBACK_MODELS;
  }
  await ensureOllamaModelCache(0).catch(() => {});
  if (typeof OfficeTaskStore !== "undefined") {
    OfficeTaskStore.onChange((tasks) => {
      halOfficeTasks = tasks;
      invalidateProgramCaches("office-tasks");
      scheduleHalWidgetRefresh();
    });
  }
  if (typeof ImportCoordinator !== "undefined") {
    ImportCoordinator.onComplete(() => {
      forceHalWidgetPlacement({ reason: "import-complete" }).catch(() => {
        invalidateProgramCaches("import-refresh");
        scheduleHalWidgetRefresh();
      });
    });
  }
  if (window.HalAgent) await HalAgent.loadMemory(buildHalAgentCtx());
  if (window.HalProactive && typeof HalProactive.startPlacementTimer === "function") {
    HalProactive.startPlacementTimer(buildHalAgentCtx);
  }
  startSideNoteMonitor();
  startDocumentSyncListener();
  startDocumentSourceRefreshTimer();
  startImportCoordinatorRefreshTimer();
  await refreshHalWidgetFeed().catch(() => {
    /* widget feed optional on boot */
  });
  refreshOpsHealthStatus().catch(() => {
    /* ops health optional on boot */
  });
  if (typeof ProgramStrength !== "undefined" && ProgramStrength.runBootHeal) {
    ProgramStrength.runBootHeal({
      invalidateProgramCaches,
      scheduleHalWidgetRefresh,
      refreshOpsHealthStatus,
    }).catch(() => {
      /* boot self-heal optional */
    });
  }
  const initial = resolvePageId(window.location.hash);
  select(initial);
  if (typeof ImportCoordinator !== "undefined") {
    ImportCoordinator.refresh({ reason: "boot" })
      .then(() => forceHalWidgetPlacement({ reason: "boot" }))
      .catch(() => forceHalWidgetPlacement({ reason: "boot-fallback" }));
  } else {
    refreshImportsInBackground();
    forceHalWidgetPlacement({ reason: "boot" }).catch(() => {
      runHalProactiveCycle({ force: true, forcePlacement: true }).catch(() => {
        /* proactive cycle optional on boot */
      });
    });
  }
}

// Pick up sidenote edits made in another tab/window of the app (browser dev
// fallback uses sessionStorage which is per-tab, so this mainly helps when a
// shared storage backend fires `storage` events). HAL refreshes its monitor
// without needing its panel on screen.
if (typeof window !== "undefined") {
  window.addEventListener("storage", async (event) => {
    if (event && event.key && event.key !== "halSideNotes") return;
    halSideNotes = (await DesktopBridge.storageGet("halSideNotes")) || halSideNotes;
    invalidateProgramCaches("side-notes-storage");
    scheduleHalWidgetRefresh();
    refreshSideNoteMonitor({ patchUi: true });
  });
  window.addEventListener("nr2:journal-queue-updated", () => {
    invalidateProgramCaches("journal-queue-updated");
    scheduleHalWidgetRefresh();
  });
}

DesktopBridge.whenReady(() => {
  DesktopBridge.installClipboardHandlers();
  if (typeof NR2Boot !== "undefined" && !NR2Boot.ready) return;
  boot();
});
