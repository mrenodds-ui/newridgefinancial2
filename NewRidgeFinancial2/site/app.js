// NewRidgeFinancial 2.0 — mission-control pages (nav from PageSchema).

const NR2_WORKSTATION_ONLY =
  typeof window !== "undefined" && !!window.NR2_WORKSTATION_ONLY;
const NR2_FINANCIAL_ONLY =
  typeof window !== "undefined" && !!window.NR2_FINANCIAL_ONLY && !NR2_WORKSTATION_ONLY;

/** Real SideNotesIM.exe — NR2 Workstation only; HAL financial app uses local staff notes + office channel. */
function sideNotesImEnabled() {
  return Boolean(NR2_WORKSTATION_ONLY);
}

function workstationFastHalEnabled() {
  if (typeof globalThis !== "undefined") {
    if (globalThis._halWorkstationFastMode === false) return false;
    if (globalThis._halWorkstationFastMode === true) return true;
    if (globalThis.NR2_WORKSTATION_FAST_HAL === false) return false;
    if (globalThis.NR2_WORKSTATION_FAST_HAL === true) return true;
    if (NR2_WORKSTATION_ONLY && globalThis.NR2_WORKSTATION_FAST_HAL !== false) return true;
  }
  return false;
}

function getPages() {
  if (NR2_WORKSTATION_ONLY && typeof WorkstationSchema !== "undefined" && WorkstationSchema.page) {
    const ws = WorkstationSchema.page;
    return [{ id: ws.id, label: ws.label, title: ws.title }];
  }
  if (NR2_WORKSTATION_ONLY && typeof PageSchema !== "undefined" && PageSchema.byId) {
    const ws = PageSchema.byId("workstation");
    return ws ? [{ id: ws.id, label: ws.label, title: ws.title }] : [];
  }
  if (typeof PageSchema !== "undefined" && PageSchema.navPages) {
    return PageSchema.navPages();
  }
  return [{ id: "hal", label: "HAL", title: "HAL Command Center" }];
}

function appPages() {
  return getPages();
}

function defaultPageId() {
  if (NR2_WORKSTATION_ONLY) return "workstation";
  const preferred = getPages().find((p) => p.id === "financial");
  if (preferred) return preferred.id;
  const staff = getPages().find((p) => p.id !== "hal");
  return staff ? staff.id : getPages()[0]?.id || "financial";
}

function resolvePageId(raw) {
  const cleaned = String(raw || "")
    .replace(/^#/, "")
    .split(/[?&]/)[0]
    .trim();
  if (NR2_FINANCIAL_ONLY && cleaned === "workstation") return defaultPageId();
  if (cleaned && getPages().some((p) => p.id === cleaned)) return cleaned;
  return defaultPageId();
}

const FALLBACK_HAL = {
  status: { title: "HAL Command Center", summary: "Local program manager.", posture: ["Local-only", "Read-only"] },
  askHal: { title: "Ask HAL", summary: "Local manager.", suggestions: ["Show priorities"], response: "I can navigate pages and explain status." },
  sources: { title: "Sources", summary: "Read-only.", items: [] },
  reasoning: { title: "Reasoning", summary: "Local lanes.", actions: [] },
  workSurfaces: { title: "Work surfaces", summary: "Open pages.", items: [] },
  consent: { title: "Consent", summary: "Staff consent required before outbound actions.", categories: [], examples: [] },
  priorities: { title: "Priorities", items: [] },
  registry: [],
};

const FALLBACK_MODELS = { config: { mode: "offline" }, lanes: [] };

const sidebar = document.getElementById("sidebar");
let nav = document.getElementById("nav");
const appPage = document.getElementById("appPage");

function halMountRoot() {
  return appPage;
}

function isHalPageVisible() {
  const root = halMountRoot();
  return !!(root && !root.hidden && root.querySelector(".ms-page--hal"));
}
const workstationPage = document.getElementById("workstationPage");
const workstationPageRoot = document.getElementById("workstationPageRoot");
const drawer = document.getElementById("drawer");
const drawerClose = document.getElementById("drawerClose");
const drawerTitle = document.getElementById("drawerTitle");
const drawerContent = document.getElementById("drawerContent");
const buttons = {};
let halData = FALLBACK_HAL;
let halModels = FALLBACK_MODELS;
let currentDrawerKey = null;
let halChatHistory = [];
let workstationChatHistory = [];
let workstationAskDraft = "";
let workstationAskLoading = false;
let officeChannelData = { schema: "nr2-office-channel-v1", messages: [] };
let officeChannelDraft = "";
let officeChannelTargets = ["all"];
let officeChannelGroup = "";
let officeChannelPickerOpen = false;
let workstationMainTab = "send";
let workstationLeftTab = "users";
let workstationReadIds = new Set();
let workstationSendReturnTab = "send";
let officeChannelLoading = false;
let officeChannelSendFlash = false;
let workstationStationName = null;
let workstationMessagePrompts = null;
let workstationPromptsEditing = false;
let workstationRenderDeferred = false;
let officeChannelAnnouncedIds = new Set();
let sidenotesMessages = [];
let sidenotesLive = false;
let sidenotesAnnouncedIds = new Set();
let workstationPopupSeenIds = new Set();
let workstationPopupBaselineDone = false;
let officeChannelPollTimer = null;
let officeWorkflowDigestKey = "";
let officeChannelHubLive = false;
let workstationSyncStatus = { loading: false, message: "", consentEnabled: true, lastHealth: null };
let halAudit = [];
let halAskDraft = "";
let halAskLoading = false;
let halModelAbortController = null;
let nr2DesignSchemaVersion = typeof PageSchema !== "undefined" ? PageSchema.SCHEMA_VERSION : null;

function persistLocal(key, value) {
  DesktopBridge.storageSet(key, value).catch(() => {});
}

function hasRuntimeAccess() {
  const bridge = window.DesktopBridge;
  if (bridge && bridge.hasRuntimeAccess && bridge.hasRuntimeAccess()) return true;
  return Boolean(bridge && bridge.hasDesktopApi && bridge.hasDesktopApi());
}

function isDesktopMode() {
  const bridge = window.DesktopBridge;
  return Boolean(bridge && bridge.hasDesktopApi && bridge.hasDesktopApi());
}

function desktopRequiredMessage(feature) {
  if (window.DesktopBridge && DesktopBridge.desktopRequiredMessage) {
    return DesktopBridge.desktopRequiredMessage(feature);
  }
  return `${feature || "This feature"} requires the NR2 server. Run StartProgram.bat and open http://127.0.0.1:8765/ in your browser.`;
}

function dismissAllPopupBoxes() {
  if (typeof document === "undefined") return;
  ["runtimeModeBanner", "halProactiveBanner", "opsHealthBanner", "halActionNotice"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.remove();
  });
  closeDrawer();
}

function renderRuntimeModeBanner() {
  dismissAllPopupBoxes();
  if (NR2_WORKSTATION_ONLY) return;
  if (hasRuntimeAccess()) return;
  const msg = serverRequiredMessage("Full NR2 data access");
  let banner = document.querySelector(".runtime-banner");
  if (!banner) {
    banner = document.createElement("div");
    banner.className = "runtime-banner";
    banner.setAttribute("role", "status");
    document.body.insertBefore(banner, document.body.firstChild);
  }
  banner.innerHTML = `<strong>NR2 server offline</strong><span>${msg}</span>`;
}

function serverRequiredMessage(feature) {
  if (window.DesktopBridge && DesktopBridge.desktopRequiredMessage) {
    return DesktopBridge.desktopRequiredMessage(feature);
  }
  return `${feature || "This feature"} requires the NR2 server. Run StartProgram.bat and open http://127.0.0.1:8765/ in your browser.`;
}

function enforceSingleFinancialTab() {
  const LOCK_KEY = "nr2_financial_tab_lock";
  const LEASE_TTL_MS = 6000;
  const HEARTBEAT_MS = 2000;

  function nr2EpochCheckBroadcast() {
    if (NR2_WORKSTATION_ONLY) return;
    if (window.PageSchema && window.PageSchema.LAYOUT_EPOCH !== "moonshot-mockup") {
      if (navigator.serviceWorker && navigator.serviceWorker.controller) {
        navigator.serviceWorker.controller.postMessage({ type: "NR2_KILL_LEGACY" });
      }
      if (window.BroadcastChannel) {
        const bc = new BroadcastChannel("nr2_tab");
        bc.postMessage({ action: "KILL_LEGACY", build: "hal-10082" });
      }
    }
  }

  function readLock() {
    try {
      return JSON.parse(localStorage.getItem(LOCK_KEY));
    } catch {
      return null;
    }
  }

  function writeLock(id) {
    localStorage.setItem(LOCK_KEY, JSON.stringify({ id, ts: Date.now() }));
  }

  function clearMyLock(id) {
    const cur = readLock();
    if (cur && cur.id === id) localStorage.removeItem(LOCK_KEY);
  }

  function canAcquire(myId) {
    const cur = readLock();
    if (!cur) return true;
    if (cur.id === myId) return true;
    const stale = Date.now() - cur.ts > LEASE_TTL_MS;
    return stale;
  }

  function showTabBlockedMessage() {
    const app = document.getElementById("app") || document.body;
    app.innerHTML =
      '<div style="font-family:system-ui;padding:2rem;text-align:center;">' +
      "<h2>NewRidge Financial is already open</h2>" +
      "<p>This application can only run in one tab at a time to protect financial data.</p>" +
      '<p>Please return to the other tab, or wait a few seconds and <a href="javascript:location.reload()">try again</a>.</p>' +
      "</div>";
  }

  function acquireTabLock() {
    const myId = `${performance.now().toFixed(0)}-${Math.random().toString(36).slice(2, 7)}`;

    if (!canAcquire(myId)) {
      showTabBlockedMessage();
      return false;
    }

    writeLock(myId);
    const heartbeat = window.setInterval(() => {
      writeLock(myId);
      nr2EpochCheckBroadcast();
    }, HEARTBEAT_MS);
    setInterval(nr2EpochCheckBroadcast, 6000);
    window.addEventListener("beforeunload", () => {
      clearInterval(heartbeat);
      clearMyLock(myId);
    });
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) return;
      writeLock(myId);
    });
    return true;
  }

  acquireTabLock();
}

function saveChatHistory() {
  persistLocal("halChatHistory", halChatHistory);
}

function saveWorkstationChatHistory() {
  persistLocal("workstationChatHistory", workstationChatHistory);
}

function isWorkstationHalPlaceholderMessage(message) {
  const text = String((message && message.text) || "").trim();
  if (!text) return true;
  return /^(HAL 9000 )?(gathering|reasoning|escalating|thinking locally|reasoning locally|escalating locally)\b/i.test(text);
}

function sanitizeWorkstationChatHistory(list) {
  if (!Array.isArray(list)) return [];
  return list.filter((message) => message && !isWorkstationHalPlaceholderMessage(message));
}

function defaultWorkstationMessagePrompts() {
  if (window.WorkstationPage && WorkstationPage.defaultMessagePrompts) {
    return WorkstationPage.defaultMessagePrompts();
  }
  return [];
}

function normalizeWorkstationMessagePrompts(list) {
  if (window.WorkstationPage && WorkstationPage.normalizeMessagePrompts) {
    return WorkstationPage.normalizeMessagePrompts(list);
  }
  return defaultWorkstationMessagePrompts();
}

function effectiveWorkstationMessagePrompts() {
  return normalizeWorkstationMessagePrompts(workstationMessagePrompts || defaultWorkstationMessagePrompts());
}

function saveWorkstationMessagePrompts(prompts) {
  workstationMessagePrompts = normalizeWorkstationMessagePrompts(prompts);
  persistLocal("workstationMessagePrompts", workstationMessagePrompts);
}

function collectWorkstationPromptEditsFromDom(root) {
  const scope = root || workstationPageRoot;
  if (!scope) return effectiveWorkstationMessagePrompts();
  const defaults = defaultWorkstationMessagePrompts();
  const WP = window.WorkstationPage || {};
  const templateFromBody = WP.templateFromPromptBody || ((body) => `{station}: ${String(body || "").trim()}`);
  const labelFromBody = WP.labelFromPromptBody || ((body, fb) => fb || "Quick note");
  return defaults.map((fallback, index) => {
    const input = scope.querySelector(`[data-ws-prompt-body="${index}"]`);
    const body = input ? String(input.value || "").trim() : promptBodyFromTemplate(fallback.template);
    return {
      label: labelFromBody(body, fallback.label),
      template: templateFromBody(body),
    };
  });
}

function promptBodyFromTemplate(template) {
  if (window.WorkstationPage && WorkstationPage.promptBodyFromTemplate) {
    return WorkstationPage.promptBodyFromTemplate(template);
  }
  return String(template || "");
}

function workstationStationLabel() {
  if (workstationStationName) return String(workstationStationName);
  if (typeof globalThis !== "undefined" && globalThis._nr2WorkstationStation) {
    return String(globalThis._nr2WorkstationStation);
  }
  return "Workstation";
}

function applyWorkstationStation(name, { persist = true } = {}) {
  const trimmed = String(name || "").trim();
  if (!trimmed) return;
  workstationStationName = trimmed;
  globalThis._nr2WorkstationStation = trimmed;
  if (persist) persistLocal("workstationStationName", trimmed);
  if (persist && typeof DesktopBridge !== "undefined" && DesktopBridge.setPopupStation) {
    DesktopBridge.setPopupStation(trimmed).catch(() => {});
  }
  if (typeof HalHubClient !== "undefined" && HalHubClient.sendHeartbeat && trimmed !== "Workstation") {
    startWorkstationHubHeartbeat();
    HalHubClient.sendHeartbeat({ station: trimmed }).catch(() => {});
  }
}

async function resolveWorkstationStationFromInbox() {
  if (workstationStationName) return workstationStationName;
  const saved = await DesktopBridge.storageGet("workstationStationName");
  if (saved) {
    applyWorkstationStation(saved, { persist: false });
    return workstationStationName;
  }
  const inbox = halSideNotesInbox;
  if (inbox && inbox.monitor && inbox.monitor.station) {
    applyWorkstationStation(inbox.monitor.station, { persist: true });
    return workstationStationName;
  }
  try {
    const localInbox = await DesktopBridge.readDataFile("sidenotes-inbox.json");
    if (localInbox && localInbox.monitor && localInbox.monitor.station) {
      applyWorkstationStation(localInbox.monitor.station, { persist: true });
    }
  } catch (_) {
    /* optional */
  }
  return workstationStationName;
}

async function refreshSideNotesMessages() {
  if (!sideNotesImEnabled()) return { messages: [] };
  if (typeof SideNotesHub === "undefined") return { messages: [] };
  await loadSideNotesInbox().catch(() => {});
  const station = workstationStationLabel();
  try {
    const live = await SideNotesHub.fetchMessages(station === "Workstation" ? "" : station);
    sidenotesMessages = Array.isArray(live.messages) ? live.messages : [];
    sidenotesLive = !!(live && live.ok);
    if (!sideNotesHelperSpeaks()) {
      maybeAnnounceSideNotesMessages(sidenotesMessages);
    } else {
      markSideNotesInboxAnnounced(halSideNotesInbox);
    }
    maybePopupIncomingWorkstationMessages(sidenotesMessages, "sidenotes");
  } catch (_) {
    sidenotesMessages = [];
    sidenotesLive = false;
  }
  return { messages: sidenotesMessages };
}

function messageTargetsThisStation(item, source) {
  const station = workstationStationLabel();
  if (source === "sidenotes" && typeof SideNotesHub !== "undefined" && SideNotesHub.messageTargetsForStation) {
    return SideNotesHub.messageTargetsForStation(item, station);
  }
  if (typeof OfficeHub !== "undefined" && OfficeHub.messageTargetsForStation) {
    return OfficeHub.messageTargetsForStation(item, station);
  }
  return true;
}

function isIncomingMessageForPopup(item, source) {
  const station = workstationStationLabel();
  const from = String((item && item.from) || "")
    .trim()
    .toLowerCase();
  const self = String(station || "")
    .trim()
    .toLowerCase();
  if (from && self && from === self) return false;
  if (!messageTargetsThisStation(item, source)) return false;
  if (source === "sidenotes" && item && item.unread === false) return false;
  return true;
}

function maybePopupIncomingWorkstationMessages(messages, source) {
  if (!NR2_WORKSTATION_ONLY) return;
  if (typeof globalThis !== "undefined" && globalThis.NR2_PYTHON_POPUP_WATCHER) return;
  if (typeof WorkstationMessagePopup === "undefined") return;
  if (!Array.isArray(messages)) {
    if (!workstationPopupBaselineDone) workstationPopupBaselineDone = true;
    return;
  }
  for (const item of messages) {
    const id = item && item.id;
    if (!id) continue;
    const key = String(id);
    if (!workstationPopupBaselineDone) {
      workstationPopupSeenIds.add(key);
      continue;
    }
    if (workstationPopupSeenIds.has(key)) continue;
    workstationPopupSeenIds.add(key);
    if (!isIncomingMessageForPopup(item, source)) continue;
    const text = String((item && item.text) || "").trim();
    if (!text) continue;
    WorkstationMessagePopup.present({
      id: key,
      from: (item && item.from) || "Office",
      text,
      target: item && item.target,
      targets: item && item.targets,
    });
  }
  if (!workstationPopupBaselineDone) workstationPopupBaselineDone = true;
}

function openWorkstationHistoryTab() {
  workstationMainTab = "history";
  markWorkstationInboxRead(mergedInboxMessagesForUi());
  renderWorkstationScreen();
}
if (typeof globalThis !== "undefined") globalThis.openWorkstationHistoryTab = openWorkstationHistoryTab;

function maybeAnnounceSideNotesMessages(messages) {
  if (typeof WorkstationMessagePopup !== "undefined") return;
  if (sideNotesHelperSpeaks()) return;
  if (!window.HalVoice || !Array.isArray(messages)) return;
  if (workstationPage && workstationPage.hidden) return;
  const station = workstationStationLabel();
  const forStation =
    typeof SideNotesHub !== "undefined" && SideNotesHub.messageTargetsForStation
      ? (item) => SideNotesHub.messageTargetsForStation(item, station)
      : () => true;
  for (const item of messages) {
    const id = item && item.id;
    if (!id || sidenotesAnnouncedIds.has(id)) continue;
    if (!forStation(item)) continue;
    if (item.unread === false) continue;
    const fromSelf = String(item.from || "").trim().toLowerCase() === String(station).trim().toLowerCase();
    if (fromSelf) continue;
    sidenotesAnnouncedIds.add(id);
    const sender = item.from || "Unknown";
    const broadcast = /^(all|everyone)$/i.test(String(item.target || ""));
    if (HalVoice.announceSidenote) HalVoice.announceSidenote(sender, broadcast);
  }
}

async function refreshOfficeChannel() {
  if (typeof OfficeHub === "undefined") return officeChannelData;
  try {
    const live = await OfficeHub.fetchChannel();
    const fallback = await OfficeHub.loadFallback();
    officeChannelData = OfficeHub.mergeChannels(live, fallback);
    officeChannelHubLive = !!(live && live.messages && !live.localOnly);
  } catch (_) {
    officeChannelData = { schema: "nr2-office-channel-v1", messages: [] };
  }
  maybeAnnounceOfficeChannel(officeChannelData.messages || []);
  await refreshHubBroadcastBadge();
  if (NR2_WORKSTATION_ONLY) {
    maybePopupIncomingWorkstationMessages(officeChannelData.messages || [], "hub");
    await refreshSideNotesMessages();
  }
  return officeChannelData;
}

function normalizeOfficeChannelTargetsList(list) {
  if (!Array.isArray(list) || !list.length) return [];
  const cleaned = list.map((s) => String(s).trim()).filter(Boolean);
  if (cleaned.some((t) => /^(all|everyone)$/i.test(t))) return ["all"];
  const seen = new Set();
  const out = [];
  cleaned.forEach((name) => {
    const key = name.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    out.push(name);
  });
  return out;
}

function toggleOfficeChannelTarget(name) {
  officeChannelGroup = "";
  const raw = String(name || "").trim();
  if (!raw) return;
  if (/^(all|everyone)$/i.test(raw)) {
    officeChannelTargets = ["all"];
    return;
  }
  let list = officeChannelTargets.filter((t) => !/^(all|everyone)$/i.test(String(t)));
  const key = raw.toLowerCase();
  const self = String(workstationStationLabel() || "").toLowerCase();
  if (key === self) return;
  const idx = list.findIndex((t) => String(t).toLowerCase() === key);
  if (idx >= 0) list = list.filter((_, i) => i !== idx);
  else list = list.concat(raw);
  officeChannelTargets = normalizeOfficeChannelTargetsList(list);
}

function selectOfficeChannelTarget(name) {
  const raw = String(name || "").trim();
  officeChannelGroup = "";
  if (!raw || /^(all|everyone)$/i.test(raw)) officeChannelTargets = ["all"];
  else officeChannelTargets = [raw];
}

function selectOfficeChannelGroup(groupId) {
  const id = String(groupId || "").trim();
  officeChannelGroup = id;
  const groups =
    typeof WorkstationSchema !== "undefined" && Array.isArray(WorkstationSchema.STATION_GROUPS)
      ? WorkstationSchema.STATION_GROUPS
      : [];
  const group = groups.find((g) => g.id === id);
  if (!group || !Array.isArray(group.members) || !group.members.length) return;
  if (group.members.some((m) => /^(all|everyone)$/i.test(String(m)))) {
    officeChannelTargets = ["all"];
    return;
  }
  officeChannelTargets = normalizeOfficeChannelTargetsList(group.members.slice());
}

function loadWorkstationReadIdsFromStorage(raw) {
  if (Array.isArray(raw)) workstationReadIds = new Set(raw.map(String));
  else workstationReadIds = new Set();
}

function mergedInboxMessagesForUi() {
  return [...(officeChannelData.messages || []), ...(sidenotesMessages || [])];
}

function saveWorkstationReadIds() {
  persistLocal("workstationReadIds", [...workstationReadIds]);
}

function markWorkstationInboxRead(messages) {
  if (!Array.isArray(messages)) return;
  let changed = false;
  messages.forEach((m) => {
    const id = String((m && m.id) || `${m && m.from}-${m && m.at}-${m && m.text}`);
    if (!workstationReadIds.has(id)) {
      workstationReadIds.add(id);
      changed = true;
    }
  });
  if (changed) saveWorkstationReadIds();
}

function workstationPracticeName() {
  if (typeof globalThis !== "undefined" && globalThis.NR2_PRACTICE_NAME) {
    return String(globalThis.NR2_PRACTICE_NAME);
  }
  if (typeof WorkstationSchema !== "undefined" && WorkstationSchema.practiceName) {
    return WorkstationSchema.practiceName;
  }
  const page =
    typeof WorkstationSchema !== "undefined" && WorkstationSchema.page ? WorkstationSchema.page : null;
  if (page && page.practiceName) return page.practiceName;
  if (halData && halData.status && halData.status.title) return String(halData.status.title);
  return "Office";
}

async function mirrorMessageToSideNotes(partial) {
  if (!sideNotesImEnabled()) return;
  if (typeof SideNotesHub === "undefined" || !SideNotesHub.sendMessage) return;
  try {
    const status = await SideNotesHub.status();
    if (!status || !status.ok) return;
  } catch (_) {
    return;
  }
  const text = String((partial && partial.text) || "").trim();
  const from = String((partial && partial.from) || workstationStationLabel()).trim();
  if (!text || !from || from === "Workstation") return;
  const targets = normalizeOfficeChannelTargetsList((partial && partial.targets) || ["all"]);
  if (!targets.length || targets.includes("all")) {
    await SideNotesHub.sendMessage({ from, targets: ["all"], text }).catch(() => {});
    return;
  }
  for (const target of targets) {
    await SideNotesHub.sendMessage({ from, targets: [target], text }).catch(() => {});
  }
}

function isWorkstationMessagingMode() {
  return (
    NR2_WORKSTATION_ONLY ||
    (workstationPage && !workstationPage.hidden)
  );
}

function maybeAnnounceOfficeChannel(messages) {
  if (!window.HalVoice || !Array.isArray(messages)) return;
  if (workstationPage && workstationPage.hidden) return;
  const station = workstationStationLabel();
  const forStation =
    typeof OfficeHub !== "undefined" && OfficeHub.messageTargetsForStation
      ? (item) => OfficeHub.messageTargetsForStation(item, station)
      : () => true;
  for (const item of messages) {
    const id = item && item.id;
    if (!item || !item.speak || item.hubAnnounced || !id || officeChannelAnnouncedIds.has(id)) continue;
    if (!forStation(item)) continue;
    officeChannelAnnouncedIds.add(id);
    if (HalVoice.speakOfficeAnnounce) HalVoice.speakOfficeAnnounce(item.text);
    else if (HalVoice.speak) HalVoice.speak(String(item.text || ""), { interrupt: true });
  }
}

async function postOfficeChannelMessage(partial) {
  if (typeof OfficeHub === "undefined") return null;
  const isWorkstationUi = isWorkstationMessagingMode();
  if (isWorkstationUi) {
    officeChannelLoading = true;
    officeChannelSendFlash = false;
    workstationSendReturnTab = workstationMainTab;
    renderWorkstationScreen();
  }
  try {
    let res = null;
    const routeViaHub =
      typeof HalHubClient !== "undefined" &&
      HalHubClient.submitToHalHub &&
      (isWorkstationUi || isDesktopMode() || (partial && (partial.role === "hal" || partial.hub === true)));
    if (routeViaHub) {
      res = await HalHubClient.submitToHalHub(partial);
    } else {
      res = await OfficeHub.appendMessage(partial);
    }
    await mirrorMessageToSideNotes(partial);
    if (isWorkstationUi) await notifyHubBroadcastAfterOfficeSend(partial);
    else {
      const targets = normalizeOfficeChannelTargetsList(
        (partial && partial.targets) || (partial && partial.target ? [partial.target] : []),
      );
      if (targets.includes("all")) {
        await notifyHubBroadcastAfterOfficeSend(partial);
        if (
          typeof SideNotesOfficeFallback !== "undefined" &&
          SideNotesOfficeFallback.workstationReachable &&
          SideNotesOfficeFallback.recordBroadcastFallback
        ) {
          const wsUp = await SideNotesOfficeFallback.workstationReachable();
          if (!wsUp) {
            SideNotesOfficeFallback.recordBroadcastFallback({
              from: (partial && partial.from) || "Staff",
              target: "all",
              channel: "office",
            });
            patchHubBroadcastBadgeDom();
          }
        }
      }
    }
    await refreshOfficeChannel();
    if (isWorkstationUi) await refreshSideNotesMessages().catch(() => {});
    const msg = res && (res.message || (res.dispatch && res.dispatch.messages && res.dispatch.messages[0] && res.dispatch.messages[0].message));
    if (msg && msg.speak && !msg.hubAnnounced) maybeAnnounceOfficeChannel([msg]);
    if (isWorkstationUi) {
      officeChannelDraft = "";
      officeChannelLoading = false;
      officeChannelSendFlash = true;
      renderWorkstationScreen();
      window.setTimeout(() => {
        officeChannelSendFlash = false;
        workstationMainTab = workstationSendReturnTab || "send";
        if (workstationPage && !workstationPage.hidden) renderWorkstationScreen();
      }, 900);
    }
    return res;
  } catch (_) {
    if (isWorkstationUi) {
      officeChannelLoading = false;
      renderWorkstationScreen();
    }
    return null;
  }
}

async function sendHalOfficePopupMessage(text, targets, options) {
  const body = String(text || "").trim();
  if (!body) return null;
  const list = normalizeOfficeChannelTargetsList(targets || ["all"]);
  return postOfficeChannelMessage({
    role: "hal",
    from: "HAL",
    text: body,
    speak: !!(options && options.speak),
    type: (options && options.type) || "announce",
    targets: list.length ? list : ["all"],
    target: list.includes("all") ? "all" : list.join(", "),
    hub: true,
  });
}
if (typeof globalThis !== "undefined") globalThis.sendHalOfficePopupMessage = sendHalOfficePopupMessage;

async function tickOfficeWorkflowMonitor() {
  if (!workstationPage || workstationPage.hidden) return;
  if (!window.HalCore || !halData) return;
  const waiting = HalCore.registryList(halData).filter((entry) => /blocked|needs review/i.test(entry.state));
  if (!waiting.length) {
    officeWorkflowDigestKey = "";
    return;
  }
  const key = waiting.map((entry) => `${entry.id}:${entry.state}`).join("|");
  if (key === officeWorkflowDigestKey) return;
  officeWorkflowDigestKey = key;
  const names = waiting
    .slice(0, 3)
    .map((entry) => entry.name)
    .join(", ");
  await postOfficeChannelMessage({
    role: "hal",
    from: "HAL",
    text: `Workflow: ${names} need attention. Refresh imports before outbound steps.`,
    speak: false,
    type: "workflow",
  });
}

function startOfficeChannelPoll() {
  if (officeChannelPollTimer) return;
  const pollMs = NR2_WORKSTATION_ONLY ? 3000 : 12000;
  refreshOfficeChannel()
    .then(() => renderWorkstationScreen())
    .catch(() => {});
  tickOfficeWorkflowMonitor().catch(() => {});
  officeChannelPollTimer = window.setInterval(() => {
    refreshOfficeChannel()
      .then(() => {
        renderWorkstationScreen();
        return tickOfficeWorkflowMonitor();
      })
      .catch(() => {});
  }, pollMs);
}

function stopOfficeChannelPoll() {
  if (officeChannelPollTimer) {
    clearInterval(officeChannelPollTimer);
    officeChannelPollTimer = null;
  }
}

let halHubProcessTimer = null;
let workstationHeartbeatTimer = null;
const WORKSTATION_HEARTBEAT_MS = 30000;

function startWorkstationHubHeartbeat() {
  if (workstationHeartbeatTimer) return;
  if (typeof HalHubClient === "undefined" || !HalHubClient.sendHeartbeat) return;
  const tick = () => {
    const station = workstationStationLabel();
    if (!station || station === "Workstation") return;
    HalHubClient.sendHeartbeat({ station }).catch(() => {});
  };
  tick();
  workstationHeartbeatTimer = window.setInterval(tick, WORKSTATION_HEARTBEAT_MS);
}

function stopWorkstationHubHeartbeat() {
  if (workstationHeartbeatTimer) {
    clearInterval(workstationHeartbeatTimer);
    workstationHeartbeatTimer = null;
  }
}

function mergeHubStationsIntoInbox(inbox, hubStations) {
  if (!hubStations || !Array.isArray(hubStations.stations)) return inbox;
  const hubMonitor = hubStations.monitor || {};
  const hubRows = hubStations.stations;
  if (!inbox) {
    return {
      meta: { schema: "nr2-sidenotes-inbox-v1", source: "HAL hub", merged: true },
      generatedAt: hubStations.checkedAt || new Date().toISOString(),
      monitor: Object.assign(
        {
          checkedAt: hubStations.checkedAt || null,
          station: hubMonitor.station || "Network",
          status: hubMonitor.status || "offline",
          stationCount: hubStations.stationCount || 0,
          totalStations: hubStations.totalStations || hubRows.length,
          stations: hubRows,
        },
        hubMonitor,
      ),
      items: [],
    };
  }
  const normalize =
    typeof HalPage !== "undefined" && HalPage.normalizeStationName
      ? HalPage.normalizeStationName
      : (value) =>
          String(value || "")
            .trim()
            .toLowerCase();
  const byName = new Map();
  ((inbox.monitor && inbox.monitor.stations) || []).forEach((row) => {
    if (row && row.station) byName.set(normalize(row.station), Object.assign({}, row));
  });
  hubRows.forEach((row) => {
    if (!row || !row.station) return;
    const key = normalize(row.station);
    const prev = byName.get(key);
    const nr2Live = row.live === true && String(row.source || "").startsWith("nr2");
    if (nr2Live) {
      byName.set(
        key,
        Object.assign({}, prev || {}, row, {
          live: true,
          status: "live",
          nr2Workstation: true,
        }),
      );
    } else if (!prev) {
      byName.set(key, row);
    }
  });
  const roster =
    typeof HalPage !== "undefined" && HalPage.buildStationRoster
      ? HalPage.buildStationRoster(Array.from(byName.values()))
      : Array.from(byName.values());
  const liveCount = roster.filter((row) => row.live).length;
  const totalStations =
    hubStations.totalStations ||
    (typeof HalPage !== "undefined" && HalPage.WORKSTATION_STATIONS
      ? HalPage.WORKSTATION_STATIONS.length
      : roster.length);
  return Object.assign({}, inbox, {
    monitor: Object.assign({}, inbox.monitor || {}, hubMonitor, {
      stations: roster,
      stationCount: liveCount,
      totalStations,
      nr2WorkstationCount: hubStations.nr2WorkstationCount || 0,
      checkedAt: hubStations.checkedAt || (inbox.monitor && inbox.monitor.checkedAt) || null,
      status: liveCount ? "live" : inbox.monitor && inbox.monitor.status,
    }),
  });
}

async function refreshHalHubStations() {
  if (typeof HalHubClient === "undefined" || !HalHubClient.fetchStations) return null;
  try {
    return await HalHubClient.fetchStations();
  } catch (_) {
    return null;
  }
}

function startHalHubDispatcher() {
  if (NR2_WORKSTATION_ONLY) return;
  if (halHubProcessTimer) return;
  if (typeof HalHubClient === "undefined" || !HalHubClient.processPending) return;
  const tick = () => {
    HalHubClient.processPending().catch(() => {});
  };
  tick();
  halHubProcessTimer = window.setInterval(tick, 4000);
}

function stopHalHubDispatcher() {
  if (halHubProcessTimer) {
    clearInterval(halHubProcessTimer);
    halHubProcessTimer = null;
  }
}

function workstationComposeFieldFocused() {
  const el = document.activeElement;
  if (!el || !workstationPage || workstationPage.hidden) return false;
  if (!workstationPage.contains(el)) return false;
  if (el.id === "wsQaInput" || el.id === "wsOfficeInput" || el.id === "wsOfficeChatInput") return true;
  return !!(el.matches && el.matches(".ws-prompt-edit-input"));
}

function syncWorkstationDraftsFromDom() {
  const qa = document.getElementById("wsQaInput");
  if (qa) workstationAskDraft = qa.value || "";
  const office = document.getElementById("wsOfficeInput");
  const chat = document.getElementById("wsOfficeChatInput");
  const compose = office || chat;
  if (compose) officeChannelDraft = compose.value || "";
}

function renderWorkstationScreen(options) {
  const force = !!(options && options.force);
  syncWorkstationDraftsFromDom();
  if (!force && workstationComposeFieldFocused()) {
    workstationRenderDeferred = true;
    return;
  }
  workstationRenderDeferred = false;
  const root = document.getElementById("workstationPageRoot");
  if (!root || !window.WorkstationPage) return;
  WorkstationPage.render({
    root: root,
    workstationChatHistory,
    workstationAskDraft,
    workstationAskLoading,
    officeChannel: officeChannelData,
    officeChannelDraft,
    officeChannelTargets,
    officeChannelGroup,
    workstationLeftTab,
    workstationReadIds,
    practiceName: workstationPracticeName(),
    officeChannelPickerOpen,
    workstationMainTab,
    officeChannelLoading,
    officeChannelSendFlash,
    workstationMessagePrompts: effectiveWorkstationMessagePrompts(),
    workstationPromptsEditing,
    stationLabel: workstationStationLabel(),
    officeHubLive: officeChannelHubLive,
    sidenotesMessages,
    sidenotesLive,
    halSideNotes,
    halSideNoteMonitor:
      halSideNoteMonitor || (window.HalSkills ? HalSkills.buildSideNoteMonitor(halSideNotes) : null),
    halSideNotesInbox,
    nr2SidenotesHubPath,
    halData,
    halModels,
    halWidgetFeed,
    halProgramSnapshot,
    workstationSyncStatus,
  });
}

async function postOperatorAudit(action, detail) {
  const pageId = NR2_WORKSTATION_ONLY ? "workstation" : resolvePageId(window.location.hash);
  const payload = {
    action: String(action || "unknown"),
    pageKey: pageId,
    widgetKey: detail && detail.widgetKey ? detail.widgetKey : null,
    detail: detail && typeof detail === "object" ? detail : { intent: String(detail || "") },
  };
  try {
    if (typeof DesktopBridge !== "undefined" && typeof DesktopBridge.loopbackJson === "function") {
      await DesktopBridge.loopbackJson("/api/audit/log", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return;
    }
    if (typeof fetch !== "function") return;
    const port = window.location.port || "8765";
    const host = window.location.hostname || "127.0.0.1";
    await fetch(`${window.location.protocol}//${host}:${port}/api/audit/log`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
    });
  } catch {
    /* fire-and-forget */
  }
}

async function loadLocalSidenotesBridge() {
  try {
    let data = null;
    if (typeof DesktopBridge !== "undefined" && typeof DesktopBridge.loopbackJson === "function") {
      data = await DesktopBridge.loopbackJson("/api/sidenotes/local");
    } else if (typeof fetch === "function") {
      const port = window.location.port || "8765";
      const host = window.location.hostname || "127.0.0.1";
      const res = await fetch(`${window.location.protocol}//${host}:${port}/api/sidenotes/local`, { cache: "no-store" });
      if (!res.ok) return;
      data = await res.json();
    }
    const notes = (data && data.notes) || [];
    if (!notes.length || !window.HalSkills) return;
    notes.forEach((row) => {
      const exists = halSideNotes.some((n) => n.noteId === row.id || n.sourceId === row.id);
      if (exists) return;
      const note = HalSkills.createSideNote(
        {
          text: `[${row.source || "workstation"}${row.station ? " · " + row.station : ""}] ${row.text}`,
          source: row.source || "workstation",
          sourceId: row.id,
        },
        { actor: "sidenote-bridge" },
      );
      halSideNotes.unshift(note);
    });
    if (notes.length) saveSideNotes();
  } catch {
    /* optional bridge */
  }
}

async function refreshWorkstationSyncHealth() {
  if (!window.Services || typeof Services.fetchHealth !== "function") return;
  const health = await Services.fetchHealth();
  if (health) {
    workstationSyncStatus = Object.assign({}, workstationSyncStatus, {
      lastHealth: health,
      consentEnabled: health.consentExecutorEnabled !== false,
    });
  }
}

async function runWorkstationSync(kind) {
  if (!window.Services) return;
  const key = String(kind || "").toLowerCase();
  workstationSyncStatus = Object.assign({}, workstationSyncStatus, {
    loading: true,
    message: key === "qb" ? "Syncing QuickBooks…" : key === "softdent" ? "Syncing SoftDent…" : "Refreshing imports…",
  });
  renderWorkstationScreen({ force: true });
  postOperatorAudit("workstation:sync:" + key, { widgetKey: "workstationSync" });
  try {
    let result = null;
    if (key === "qb" && typeof Services.syncQuickBooks === "function") {
      result = await Services.syncQuickBooks({ force: true });
    } else if (key === "softdent" && typeof Services.syncSoftdentOdbc === "function") {
      result = await Services.syncSoftdentOdbc();
    } else if (typeof Services.refreshImports === "function") {
      result = await Services.refreshImports({ reason: "workstation-sync", waitForCompletion: true });
    }
    const ok = !result || result.ok !== false;
    const detail =
      result && result.refreshed
        ? "QuickBooks refresh completed."
        : result && result.message
          ? result.message
          : result && result.error
            ? String(result.error)
            : ok
              ? "Sync completed."
              : "Sync failed.";
    workstationSyncStatus = Object.assign({}, workstationSyncStatus, {
      loading: false,
      message: detail,
    });
    showHalActionNotice(detail, ok ? "info" : "warn");
    await refreshWorkstationSyncHealth();
  } catch (err) {
    workstationSyncStatus = Object.assign({}, workstationSyncStatus, {
      loading: false,
      message: err && err.message ? err.message : "Sync failed.",
    });
    showHalActionNotice(workstationSyncStatus.message, "warn");
  }
  renderWorkstationScreen({ force: true });
}

async function postWorkstationSidenote(text) {
  const station = workstationStationLabel();
  const payload = {
    text,
    source: "workstation",
    station: station !== "Workstation" ? station : null,
    timestamp: new Date().toISOString(),
  };
  try {
    if (typeof DesktopBridge !== "undefined" && typeof DesktopBridge.loopbackJson === "function") {
      return DesktopBridge.loopbackJson("/api/sidenote", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    }
    if (typeof fetch !== "function") return null;
    const port = window.location.port || "8766";
    const host = window.location.hostname || "127.0.0.1";
    const res = await fetch(`${window.location.protocol}//${host}:${port}/api/sidenote`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
    });
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

async function handleWorkstationHalSubmit(query) {
  const trimmed = String(query || "").trim();
  if (!trimmed) return;
  globalThis._halWorkstationQaMode = true;
  const savedHist = halChatHistory;
  const savedSave = saveChatHistory;
  if (halTypeTimer) {
    clearInterval(halTypeTimer);
    halTypeTimer = null;
  }
  halChatHistory = [];
  saveChatHistory = saveWorkstationChatHistory;
  workstationAskLoading = true;
  renderWorkstationScreen();
  try {
    await handleHalSubmit(trimmed);
    const lastUser = [...halChatHistory].reverse().find((m) => m.role === "user");
    const lastHal = [...halChatHistory].reverse().find((m) => m.role === "hal");
    workstationChatHistory = sanitizeWorkstationChatHistory([lastUser, lastHal].filter(Boolean));
    saveWorkstationChatHistory();
  } finally {
    halChatHistory = savedHist;
    saveChatHistory = savedSave;
    workstationAskLoading = false;
    globalThis._halWorkstationQaMode = false;
    renderWorkstationScreen();
    requestAnimationFrame(() => typewriteWorkstationHalReply());
  }
}

async function handleOfficeChannelSubmit(query, speak) {
  const trimmed = String(query || "").trim();
  if (!trimmed) return;
  if (workstationStationLabel() === "Workstation") return;
  let text = trimmed;
  let doSpeak = speak !== false;
  let type = "announce";
  if (/^note:\s*/i.test(text)) {
    text = text.replace(/^note:\s*/i, "").trim();
    doSpeak = false;
    type = "note";
  } else if (/^announce:\s*/i.test(text)) {
    text = text.replace(/^announce:\s*/i, "").trim();
    doSpeak = true;
  }
  if (!text) return;
  const targets = normalizeOfficeChannelTargetsList(officeChannelTargets);
  if (!targets.length) return;
  await postOfficeChannelMessage({
    role: "staff",
    from: workstationStationLabel(),
    text,
    speak: doSpeak,
    type,
    targets,
    target: targets.includes("all") ? "all" : targets.join(", "),
  });
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
  if (typeof NR2SoftdentDaily !== "undefined" && typeof NR2SoftdentDaily.clearLiveCache === "function") {
    NR2SoftdentDaily.clearLiveCache();
  }
  if (typeof SnapshotStore !== "undefined") SnapshotStore.invalidate(reason || "app");
}

// HAL proactive program assessment (independent local recommendations).
let halProactiveBriefing = null;
let halMorningBriefing = null;

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
    if (options && options.showBootNotice && halProactiveBriefing && halProactiveBriefing.headline) {
      showHalActionNotice(`HAL briefing: ${halProactiveBriefing.headline}`, "info");
    }
    if (options && options.showScheduledNotice && halProactiveBriefing && halProactiveBriefing.headline) {
      const label = options.scheduledKind === "eod" ? "End-of-day" : "Morning";
      showHalActionNotice(`${label} briefing: ${halProactiveBriefing.headline}`, "info");
    }
    if (currentDrawerKey === "priorities") renderPanel("priorities");
    return halProactiveBriefing;
  } catch {
    return null;
  }
}

function renderProactiveBanner() {
  const existing = typeof document !== "undefined" ? document.getElementById("halProactiveBanner") : null;
  if (existing) existing.remove();
}

function scheduleHalWidgetRefresh(snapshot, options) {
  const repaint = !!(options && options.repaint);
  if (halWidgetRefreshInFlight) return halWidgetRefreshInFlight;
  halWidgetRefreshInFlight = refreshHalWidgetFeed(snapshot)
    .then(async (feed) => {
      await runHalProactiveCycle();
      renderHalScreen();
      if (currentDrawerKey === "sources") renderPanel("sources");
      const currentId = (window.location.hash || "").replace("#", "") || getPages()[0].id;
      if (PageViews && PageViews.setHalFeed) {
        PageViews.setHalFeed(halWidgetFeed, halProgramSnapshot);
      }
      if (
        currentId !== "hal" &&
        appPage &&
        !appPage.hidden &&
        PageViews &&
        PageViews.hasPage(currentId)
      ) {
        PageViews.renderPageView(appPage, halData, currentId, select, halWidgetFeed, halProgramSnapshot);
        if (typeof PageChrome !== "undefined" && PageChrome.refreshHalReadinessStrip) {
          PageChrome.refreshHalReadinessStrip(currentId, halWidgetFeed);
        }
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
const SIDENOTE_INBOX_FILES = (function buildSideNoteInboxFiles() {
  const roster =
    typeof HalPage !== "undefined" && HalPage.WORKSTATION_STATIONS
      ? HalPage.WORKSTATION_STATIONS
      : [
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
  const slug =
    typeof HalPage !== "undefined" && HalPage.stationSlug
      ? HalPage.stationSlug
      : (name) =>
          String(name || "")
            .trim()
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "-")
            .replace(/^-+|-+$/g, "") || "unknown";
  return ["sidenotes-inbox.json", ...roster.map((name) => `sidenotes-inbox-${slug(name)}.json`)];
})();

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
  const roster =
    typeof HalPage !== "undefined" && HalPage.buildStationRoster
      ? HalPage.buildStationRoster(monitorRows)
      : monitorRows;
  const totalStations =
    typeof HalPage !== "undefined" && HalPage.WORKSTATION_STATIONS
      ? HalPage.WORKSTATION_STATIONS.length
      : roster.length;
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
      totalStations,
      stations: roster,
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
  if (!sideNotesImEnabled()) {
    halSideNotesInbox = null;
    return null;
  }
  const inboxes = await Promise.all(SIDENOTE_INBOX_FILES.map(tryReadSideNotesInbox));
  let data = mergeSideNotesInboxes(inboxes);
  let hubStations = null;
  try {
    hubStations = await Promise.race([
      refreshHalHubStations(),
      new Promise((resolve) => window.setTimeout(() => resolve(null), 2500)),
    ]);
  } catch (_) {
    hubStations = null;
  }
  if (hubStations) data = mergeHubStationsIntoInbox(data, hubStations);
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

function sideNotesHelperSpeaks(inbox) {
  const data = inbox || halSideNotesInbox;
  if (!data || !data.monitor) return false;
  return isSideNotesWatcherLive(data) && !!data.monitor.announce;
}

function markSideNotesInboxAnnounced(inbox) {
  const items = inbox && Array.isArray(inbox.items) ? inbox.items : [];
  items.forEach((m) => {
    if (m && (m.announceId || m.id)) halSideNotesAnnouncedIds.add(m.announceId || m.id);
  });
}

function maybeAnnounceSideNotesInbox(inbox) {
  if (!inbox || !Array.isArray(inbox.items) || !window.HalVoice) return;
  if (sideNotesHelperSpeaks(inbox)) {
    markSideNotesInboxAnnounced(inbox);
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
  if (patchUi) {
    if (workstationPage && !workstationPage.hidden) {
      renderWorkstationScreen();
    } else if (halMountRoot() && !halTypeTimer) {
      patchSideNoteMonitorDom();
    }
  }
  return halSideNoteMonitor;
}

function patchSideNoteMonitorDom() {
  const root = halMountRoot();
  if (!root || !window.HalPage) return;
  const el = root.querySelector(".sidenotes-program");
  if (!el) return;
  el.innerHTML = HalPage.sideNotesMonitorHtml(halSideNotes, halSideNoteMonitor, halSideNotesInbox, nr2SidenotesHubPath);
}

function scrollHalPanelIntoView(panelKey) {
  const root = halMountRoot();
  if (!root || !panelKey) return;
  const panel = root.querySelector(`[data-panel="${panelKey}"]`);
  if (panel && typeof panel.scrollIntoView === "function") {
    panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}

function scrollStaffWidgetIntoView(widgetKey) {
  const root = appPage || document.getElementById("appPage");
  if (!root || !widgetKey) return;
  const target = root.querySelector(`[data-hal-widget-key="${widgetKey}"]`);
  if (target && typeof target.scrollIntoView === "function") {
    target.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}

function scrollPageSectionIntoView(pageId, opts) {
  const o = opts || {};
  if (pageId === "hal") {
    if (o.panelKey) scrollHalPanelIntoView(o.panelKey);
    else if (o.widgetKey) {
      const panelMap = {
        halAskHal: "askHal",
        halImportHealth: "importHealth",
        sidenotesProgram: "sidenotes",
        officeManagerSurfaces: "workSurfaces",
      };
      const panel = panelMap[o.widgetKey];
      if (panel) scrollHalPanelIntoView(panel);
      else scrollStaffWidgetIntoView(o.widgetKey);
    }
    return;
  }
  if (o.widgetKey) scrollStaffWidgetIntoView(o.widgetKey);
}

function isHalPanelTarget(target) {
  return target === "sidenotes";
}

async function activateSideNotesPanel({ scroll } = {}) {
  await loadSideNotesInbox();
  refreshSideNoteMonitor({ patchUi: true });
  if (scroll) scrollHalPanelIntoView("sidenotes");
}

let hubLastBroadcast = null;

async function ensureHubToken() {
  if (typeof window !== "undefined" && window.NR2_HUB_TOKEN) return window.NR2_HUB_TOKEN;
  try {
    const res = await fetch("/api/app-info", { cache: "no-store" });
    if (res.ok) {
      const info = await res.json();
      if (info && info.hubToken && typeof window !== "undefined") {
        window.NR2_HUB_TOKEN = String(info.hubToken);
      }
    }
  } catch {
    /* optional */
  }
  return typeof window !== "undefined" ? window.NR2_HUB_TOKEN || null : null;
}

async function refreshHubBroadcastBadge() {
  await ensureHubToken();
  let serverBroadcast = null;
  try {
    const headers = {};
    if (typeof window !== "undefined" && window.NR2_HUB_TOKEN) {
      headers["X-Hub-Token"] = String(window.NR2_HUB_TOKEN);
    }
    const res = await fetch("/api/hub/last-broadcast", { cache: "no-store", headers });
    if (res.ok) {
      serverBroadcast = await res.json();
      if (serverBroadcast && serverBroadcast.at) {
        hubLastBroadcast = serverBroadcast;
        if (typeof window !== "undefined") window.__NR2_HUB_BROADCAST = hubLastBroadcast;
      }
    }
  } catch {
    serverBroadcast = null;
  }
  if (!serverBroadcast || !serverBroadcast.at) {
    if (
      typeof SideNotesOfficeFallback !== "undefined" &&
      SideNotesOfficeFallback.applyFallbackBroadcast
    ) {
      const fb = SideNotesOfficeFallback.applyFallbackBroadcast();
      if (fb && fb.at) hubLastBroadcast = fb;
      else {
        hubLastBroadcast = null;
        if (typeof window !== "undefined") window.__NR2_HUB_BROADCAST = null;
      }
    } else {
      hubLastBroadcast = null;
      if (typeof window !== "undefined") window.__NR2_HUB_BROADCAST = null;
    }
  }
  patchHubBroadcastBadgeDom();
}

function patchHubBroadcastBadgeDom() {
  const root = halMountRoot();
  if (!root || !window.HalPage || typeof HalPage.hubBroadcastBadgeHtml !== "function") return;
  const html = HalPage.hubBroadcastBadgeHtml();
  root.querySelectorAll(".sidenotes-monitor .sidenote-head").forEach((head) => {
    const existing = head.querySelector(".sidenote-badge--hub-broadcast");
    if (!html) {
      if (existing) existing.remove();
      return;
    }
    if (existing) {
      existing.outerHTML = html;
    } else {
      const title = head.querySelector("h4");
      if (title) title.insertAdjacentHTML("afterend", html);
    }
  });
}

async function notifyHubBroadcastAfterOfficeSend(partial) {
  await ensureHubToken();
  const targets = normalizeOfficeChannelTargetsList(
    (partial && partial.targets) || (partial && partial.target ? [partial.target] : []),
  );
  if (!targets.includes("all")) return;
  const payload = {
    from: (partial && partial.from) || workstationStationName || "Workstation",
    target: "all",
    channel: "office",
  };
  try {
    if (typeof HalHubClient !== "undefined" && HalHubClient.notifyHubBroadcast) {
      await HalHubClient.notifyHubBroadcast(payload);
    } else {
      await fetch("/api/hub/notify", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(typeof window !== "undefined" && window.NR2_HUB_TOKEN ? { "X-Hub-Token": String(window.NR2_HUB_TOKEN) } : {}),
        },
        body: JSON.stringify(payload),
      });
    }
  } catch {
    /* 8765 may be offline — badge poll stays quiet */
  }
}

function buildPageHalContext(pageId) {
  const pid = pageId || resolvePageId(window.location.hash);
  const schema = typeof PageSchema !== "undefined" && PageSchema.byId ? PageSchema.byId(pid) : null;
  const D = typeof PageCanvasData !== "undefined" ? PageCanvasData : null;
  const lines = [`Active page: ${schema ? schema.title : pid}`];
  if (!D) return lines.join("\n");
  if (pid === "financial" && D.financialKpis) {
    D.financialKpis()
      .slice(0, 4)
      .forEach((k) => lines.push(`${k.label}: ${k.value}`));
  } else if (pid === "quickbooks" && D.quickbooksKpis) {
    D.quickbooksKpis()
      .slice(0, 4)
      .forEach((k) => lines.push(`${k.label}: ${k.value}`));
  } else if (pid === "softdent" && D.softdentKpis) {
    D.softdentKpis()
      .slice(0, 4)
      .forEach((k) => lines.push(`${k.label}: ${k.value}`));
  } else if (pid === "ar" && D.arKpis) {
    D.arKpis()
      .slice(0, 4)
      .forEach((k) => lines.push(`${k.label}: ${k.value}`));
  }
  return lines.join("\n");
}

async function handleHalActuatorClick(button) {
  if (!button || !button.hasAttribute("data-hal-consent")) return;
  const actionId = button.getAttribute("data-hal-actuator") || "";
  const target = button.getAttribute("data-hal-actuator-target") || button.getAttribute("data-open-page") || null;
  const halAction = button.getAttribute("data-hal-action");
  if (halAction === "openPage" && target) {
    logAudit("HAL actuator navigate: " + target, "actuator: consent");
    select(target);
    return;
  }
  if (
    window.HalAgentLoop &&
    typeof HalAgentLoop.executeActuatorIfConsented === "function" &&
    (actionId === "refresh-imports" || actionId === "sync-qb" || actionId === "sync-softdent")
  ) {
    button.disabled = true;
    try {
      const result = await HalAgentLoop.executeActuatorIfConsented(
        { actionId, target, label: button.textContent },
        buildHalAgentCtx(),
      );
      if (result && result.navigate) {
        select(result.navigate);
      } else if (result && result.ok) {
        showHalActionNotice(result.message || "Action completed.", "info");
        invalidateProgramCaches("hal-actuator");
        scheduleHalWidgetRefresh();
      } else {
        showHalActionNotice("Action blocked — " + ((result && result.reason) || "unavailable"), "warn");
      }
    } finally {
      button.disabled = false;
    }
    return;
  }
  if (halAction === "refreshImports" || actionId === "refresh-imports") {
    await handleHalSubmit("Refresh imports");
    return;
  }
  await handleHalSubmit(button.getAttribute("data-hal-followup") || button.textContent || "Proceed");
}

async function runHalPageCmd(cmd, opts) {
  const text = String(cmd || "").trim();
  if (!text) return;
  const openHal = !opts || opts.openHal !== false;
  if (openHal && !isHalPageVisible()) select("hal");
  const pageId = resolvePageId(window.location.hash);
  const withContext = !(opts && opts.raw);
  const query = withContext ? `${text}\n\n[Page context]\n${buildPageHalContext(pageId)}` : text;
  await handleHalSubmit(query);
  renderHalScreen();
}
if (typeof window !== "undefined") {
  window.NR2_FLAGS = Object.assign({ hal_commands: true }, window.NR2_FLAGS || {});
  window.runHalPageCmd = runHalPageCmd;
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
  if (widgetCard && !event.target.closest("[data-hal-widget-nav]") && !event.target.closest("[data-hal-action]") && !event.target.closest("[data-hal-actuator]")) {
    const openPage = widgetCard.getAttribute("data-open-page");
    const scrollWidget = widgetCard.getAttribute("data-hal-scroll-widget") || widgetCard.getAttribute("data-hal-widget-key");
    if (openPage && openPage !== "hal") {
      select(openPage);
      if (scrollWidget) setTimeout(() => scrollStaffWidgetIntoView(scrollWidget), 120);
    }
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
  const voicePtt = event.target.closest("[data-hal-voice-ptt]");
  if (voicePtt) {
    const briefing =
      (typeof HalProactive !== "undefined" && HalProactive.lastBriefing && HalProactive.lastBriefing.morningBriefing) ||
      null;
    const line =
      (briefing && briefing.sentence) ||
      "HAL is monitoring SoftDent and QuickBooks imports on this workstation.";
    if (typeof HalVoice !== "undefined" && HalVoice.speak) HalVoice.speak(line, { interrupt: true });
    else if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.speak(new SpeechSynthesisUtterance(line));
    }
    return true;
  }
  const actuatorBtn = event.target.closest("[data-hal-actuator]");
  if (actuatorBtn) {
    await handleHalActuatorClick(actuatorBtn);
    return true;
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
  if (!sideNotesImEnabled()) {
    const localNotes = (halSideNotes || [])
      .filter((n) => n.status !== "archived")
      .slice(0, 8)
      .map((n) => `<li>${escapeHtml(n.text)} · ${escapeHtml(n.priority || "normal")}</li>`)
      .join("");
    const commands = ["Monitor sidenotes", "Show sidenotes", "Add sidenote: follow up on hygiene recall"]
      .map((cmd) => `<button type="button" class="drawer-action" data-hal-command="${escapeHtml(cmd)}">${escapeHtml(cmd)}</button>`)
      .join("");
    return `<p>Local HAL staff notes on this device. Office messaging uses <strong>NR2 Workstation</strong>, not SideNotesIM.</p>
    <div class="drawer-section">
      <h3 class="drawer-section__title">Active notes</h3>
      <ul class="drawer-checklist">${localNotes || "<li>No local notes yet.</li>"}</ul>
    </div>
    <div class="drawer-section">
      <h3 class="drawer-section__title">HAL commands</h3>
      <div class="drawer-grid">${commands}</div>
    </div>`;
  }
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
      <table class="data-table sidenote-stations-table"><thead><tr><th>Station</th><th>Status</th><th>Checked</th></tr></thead><tbody>${stationRows}</tbody></table>
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
  if (!sideNotesImEnabled()) {
    return;
  }
  loadSideNotesInbox().then(() => patchSideNoteMonitorDom());
  // SideNotesIM watcher inbox — workstation only. Local HAL staff notes still refresh above.
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
    storageMode: hasRuntimeAccess() ? "sqlite" : "sessionStorage",
    desktopBridgeOk: hasRuntimeAccess(),
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
  snap.sidenotesInbox = sideNotesImEnabled() ? halSideNotesInbox || null : null;
  snap.sidenotesHubPath = sideNotesImEnabled() ? nr2SidenotesHubPath || null : null;
  halProgramSnapshot = snap;
  halWidgetFeed = HalSkills.buildWidgetFeed(snap);
  halData.runtime = Object.assign({}, halData.runtime || {}, { widgetFeed: halWidgetFeed });
  return halWidgetFeed;
}

function flashHalWidgets(_pageId) {
  /* Widget flash disabled — avoids transient rings on every page. */
}

function showHalActionNotice(_message, _tone) {
  /* Top HAL notice bar disabled — avoids transient banner pop-in on every refresh. */
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
  if (desktop && desktop.hasRuntimeAccess && desktop.hasRuntimeAccess()) {
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

  await scheduleHalWidgetRefresh(snapshot, { repaint: true });
  flashHalWidgets(pageId);
  showHalActionNotice(placementNote, desktop && desktop.hasRuntimeAccess && desktop.hasRuntimeAccess() ? "info" : "warn");

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
        text: String(n.text || "").slice(0, 120),
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
  const runtime = HalCore.laneRuntime(halModels, "chat8b");
  if (!workstationFastHalEnabled()) return runtime;
  const cfg = Object.assign({ fastChat: true }, runtime);
  cfg.options = Object.assign({}, cfg.options || {}, { num_predict: 768 });
  return cfg;
}

function escalationModelConfig() {
  return HalCore.laneRuntime(halModels, "escalate30b");
}

function ossModelConfig() {
  return HalCore.laneRuntime(halModels, "oss120b");
}

const ollamaModelCache = { at: 0, names: null, loading: null };

async function refreshOllamaModelNames() {
  try {
    if (typeof DesktopBridge !== "undefined" && typeof DesktopBridge.loopbackJson === "function") {
      const data = await DesktopBridge.loopbackJson("/api/ollama/tags");
      const names = (data.models || [])
        .map((m) => (typeof m === "string" ? m : m && m.name))
        .filter(Boolean);
      ollamaModelCache.names = new Set(names);
      ollamaModelCache.at = Date.now();
      return names;
    }
  } catch {
    /* fall through to direct probe on plain HTTP dev only */
  }
  const runtime = HalCore.laneRuntime(halModels, "chat8b");
  if (!runtime || !runtime.endpoint) return [];
  if (typeof window !== "undefined" && window.location && window.location.protocol === "https:") {
    return [];
  }
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
    preferForAllAgentLoops: cfg.preferForAllAgentLoops === true,
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
  if (typeof HalChat9000 !== "undefined" && HalChat9000.cloudForChat(halModels, plan) && cloudModelReady()) {
    return true;
  }
  if (!plan || !plan.agentToolLoop || !cloudModelReady()) return false;
  const cfg = HalCore.modelConfig(halModels).cloudReasoning || {};
  if (cfg.enabled === true) return true;
  if (cfg.autoEnableWhenKeySet === false || !getCloudApiKey()) return false;
  if (cfg.preferForAllAgentLoops === true) return true;
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
  // Natural-voice sampling applies to the fast 8B chat lane only — not reasoning/escalation.
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
  if (
    typeof DesktopBridge !== "undefined" &&
    typeof DesktopBridge.hasLoopbackApi === "function" &&
    DesktopBridge.hasLoopbackApi() &&
    typeof DesktopBridge.evaluateHalQuery === "function" &&
    !(runtime && runtime.cloud)
  ) {
    try {
      const gateway = await DesktopBridge.evaluateHalQuery({
        query: userText,
        model: runtime.model,
        systemPrompt: systemPrompt,
        messages: payload.messages,
        options: payload.options,
        stream: wantStream,
        onToken: wantStream && typeof onToken === "function" ? onToken : undefined,
        signal: abortSignal,
        shiftContext: typeof window !== "undefined" && window.nr2ShiftState ? window.nr2ShiftState : undefined,
        sessionId: typeof window !== "undefined" && window.nr2HalSessionId ? window.nr2HalSessionId : undefined,
      });
      if (gateway && (gateway.blocked || gateway.error === "HAL_UNAVAILABLE_STALE_DATA")) {
        throw new Error("HAL_UNAVAILABLE_STALE_DATA");
      }
      const rawGateway = (gateway && (gateway.text || (gateway.message && gateway.message.content))) || "";
      const textGw = HalCore.cleanModelText(rawGateway);
      if (structuredOllama) {
        const lane = (gateway && gateway.resolvedLane) || (runtime.reasoningLane ? "reason21b" : "chat8b");
        if (typeof window !== "undefined" && gateway && gateway.resolvedLane) {
          window.dispatchEvent(new CustomEvent("nr2-hal-lane-used", { detail: { lane: gateway.resolvedLane } }));
        }
        return { text: textGw || "", toolCalls: [], lane: lane };
      }
      if (runtime && runtime.fastChat) return textGw;
      return textGw + "\n\n(" + draftLabel + " · gateway · verify before acting)";
    } catch (gatewayErr) {
      if (gatewayErr && (gatewayErr.message === "HAL_UNAVAILABLE_STALE_DATA" || gatewayErr.status === 503)) {
        throw new Error("HAL_UNAVAILABLE_STALE_DATA");
      }
      throw gatewayErr;
    } finally {
      clearTimeout(timer);
    }
  }
  clearTimeout(timer);
  throw new Error("HAL gateway required — start NR2 on port 8765");
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
  postOperatorAudit(String(query || intent || "audit"), { intent: String(intent || "") });
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
  const withActuators = withPatches.replace(/<<<actuator\s+([\s\S]*?)>>>/gi, (full, body) => {
    if (window.HalAgentLoop && typeof HalAgentLoop.parseActuatorProposals === "function") {
      const proposals = HalAgentLoop.parseActuatorProposals(full);
      if (proposals.length && typeof HalAgentLoop.renderActuatorButtonsHtml === "function") {
        return `<div class="hal-msg__actuators prompt-chips">${HalAgentLoop.renderActuatorButtonsHtml(proposals)}</div>`;
      }
    }
    return "";
  });
  const withTools = withActuators.replace(/<<<tool[\s\S]*?>>>/gi, "");

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
  return `<div class="hal-msg__followups prompt-chips">${chips
    .map((c) => {
      const label = escapeHtml(c.label);
      const consentAttr = c.consent ? ' data-hal-consent="1"' : c.cancel ? ' data-hal-cancel="1"' : "";
      if (c.action && c.action.type === "openPage" && c.action.page) {
        return `<button type="button" class="prompt-chip prompt-chip--action" data-hal-action="openPage" data-open-page="${escapeHtml(c.action.page)}" data-hal-followup="${escapeHtml(c.query || c.label)}"${consentAttr}>${label}</button>`;
      }
      if (c.action && c.action.type === "refreshImports") {
        return `<button type="button" class="prompt-chip prompt-chip--action" data-hal-action="refreshImports" data-hal-followup="Refresh imports"${consentAttr}>${label}</button>`;
      }
      return `<button type="button" class="prompt-chip${c.consent ? " prompt-chip--action" : ""}" data-hal-followup="${escapeHtml(c.query || c.label)}"${consentAttr}>${label}</button>`;
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
          ? `<button type="button" class="prompt-chip prompt-chip--action" data-hal-apply-patches="${idx}">Apply patches</button>`
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
  log.querySelectorAll("[data-hal-actuator]").forEach((button) => {
    button.addEventListener("click", () => {
      handleHalActuatorClick(button);
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
      if (button.hasAttribute("data-hal-consent")) {
        executeHalConsentAction(button.getAttribute("data-hal-followup") || "I consent");
        return;
      }
      if (button.hasAttribute("data-hal-cancel")) {
        handleHalSubmit("Cancel");
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
    workstationFastHal: workstationFastHalEnabled,
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

async function executeHalConsentAction(consentText) {
  const pending = window.HalConsent ? await HalConsent.loadPending() : null;
  if (!pending || !window.HalOutbound) {
    halChatHistory.push({
      role: "hal",
      text: "No pending outbound action to execute. Ask HAL to email, export, or post first.",
      lane: "local",
      actions: [],
    });
    return;
  }
  try {
    const result = await HalOutbound.executePending(pending, consentText);
    HalConsent.clearPending();
    const actions = [];
    if (result && result.exportPath) {
      actions.push({ type: "openPage", page: "quickbooks", label: "Open QuickBooks page" });
    }
    halChatHistory.push({
      role: "hal",
      text: HalOutbound.formatResult(result),
      lane: "local",
      intent: "outbound:executed",
      actions,
    });
    logAudit(consentText, "outbound:executed");
  } catch (error) {
    const detail = error && error.message ? error.message : String(error);
    halChatHistory.push({ role: "hal", text: `Outbound action failed: ${detail}`, lane: "error", actions: [] });
    logAudit(consentText, "outbound:error");
  }
}

function refreshHalSubmitUi(wsSilent, opts) {
  const o = opts || {};
  if (wsSilent) {
    workstationAskLoading = !!halAskLoading;
    renderWorkstationScreen();
    if (o.scrollQaLog) {
      requestAnimationFrame(() => {
        const log = document.getElementById("wsQaLog");
        if (log) log.scrollTop = log.scrollHeight;
      });
    }
    return;
  }
  if (o.halScreenOnly) {
    renderHalScreen();
    return;
  }
  if (o.chatLogOnly) {
    renderChatLog();
    return;
  }
  renderChatLog();
  renderHalScreen();
}

async function handleHalSubmit(query) {
  const trimmed = String(query).trim();
  if (!trimmed) return;
  const wsSilent = !!globalThis._halWorkstationQaMode;

  if (window.HalConsent) {
    await HalConsent.loadPending();
    if (HalConsent.isCancelPhrase(trimmed)) {
      HalConsent.clearPending();
      halChatHistory.push({ role: "user", text: trimmed, actions: [] });
      halChatHistory.push({ role: "hal", text: "Cancelled the pending outbound action.", lane: "local", actions: [] });
      saveChatHistory();
      refreshHalSubmitUi(wsSilent, { chatLogOnly: true });
      return;
    }
    if (HalConsent.isConsentPhrase(trimmed)) {
      halAskLoading = true;
      halChatHistory.push({ role: "user", text: trimmed, actions: [] });
      refreshHalSubmitUi(wsSilent);
      await executeHalConsentAction(trimmed);
      halAskLoading = false;
      saveChatHistory();
      refreshHalSubmitUi(wsSilent);
      return;
    }
  }

  if (halModelAbortController) halModelAbortController.abort();
  halModelAbortController = new AbortController();
  const abortSignal = halModelAbortController.signal;

  if (window.HalVoice && HalVoice.cancelSpeech) HalVoice.cancelSpeech();
  if (halTypeTimer) {
    clearInterval(halTypeTimer);
    halTypeTimer = null;
  }
  halAskLoading = false;

  if (window.HalCore && /\b(keep going|what else)\b/i.test(trimmed)) {
    const halReplies = halChatHistory.filter((m) => m.role === "hal" && m.text && String(m.text).trim());
    const sourceHal = halReplies.length ? halReplies[halReplies.length - 1] : null;
    if (sourceHal) {
      const pool = [
        "Also check whether imports finished syncing — stale exports often explain the next gap on the same topic.",
        "If that page still looks empty, refresh imports and re-open it before drawing conclusions.",
        "Staff should clear any needs-review registry line tied to this workflow before outbound steps.",
        "Name a specific widget if you want a narrower drill-down on the same point.",
      ];
      const extra = HalCore.pickVariant ? HalCore.pickVariant(pool) : pool[0];
      const base = String(sourceHal.text).trim().replace(/[.!?]\s*$/, "");
      const continued = `${base}. ${extra}`;
      halChatHistory.push({ role: "user", text: trimmed, actions: [] });
      halChatHistory.push({
        role: "hal",
        text: continued,
        lane: "local",
        actions: [],
        intent: "capability:continue-followup",
        userQuery: trimmed,
        skipChatSpeech: wsSilent,
      });
      saveChatHistory();
      refreshHalSubmitUi(wsSilent);
      logAudit(trimmed, "capability:continue-followup");
      return;
    }
  }

  if (halAskLoading) {
    const last = halChatHistory[halChatHistory.length - 1];
    if (last && last.role === "hal" && /gathering|thinking locally|reasoning locally|escalating locally/i.test(last.text)) {
      halChatHistory.pop();
    }
  }

  if (window.HalCore && HalCore.wantsBriefReply && HalCore.wantsBriefReply(trimmed)) {
    const halReplies = halChatHistory.filter((m) => m.role === "hal" && m.text && String(m.text).trim());
    const lastHal = halReplies.length ? halReplies[halReplies.length - 1] : null;
    let sourceHal = lastHal;
    if (lastHal && lastHal.intent === "capability:correction-imports" && halReplies.length >= 2) {
      sourceHal = halReplies[halReplies.length - 2];
    }
    if (sourceHal) {
      let source = String(sourceHal.text)
        .replace(/^to clarify\s*[—,-]\s*/i, "")
        .trim();
      const sentences = HalCore.splitSentences(source);
      let brief = sentences.slice(0, 2).join(" ").trim() || source.slice(0, 220).trim();
      if (HalCore.countWords && HalCore.countWords(brief) > 55) {
        brief = sentences[0] || brief.slice(0, 200).trim();
      }
      halChatHistory.push({ role: "user", text: trimmed, actions: [] });
      halChatHistory.push({
        role: "hal",
        text: brief,
        lane: "local",
        actions: [],
        intent: "capability:brief-followup",
        userQuery: trimmed,
        skipChatSpeech: wsSilent,
      });
      saveChatHistory();
      refreshHalSubmitUi(wsSilent);
      logAudit(trimmed, "capability:brief-followup");
      return;
    }
  }

  const effectiveQuery = expandHalUserQuery(trimmed);
  halAskLoading = true;
  refreshHalSubmitUi(wsSilent, { halScreenOnly: true });
  halChatHistory.push({ role: "user", text: trimmed, actions: [] });
  saveChatHistory();

  const preRoute = routeHalCommand(trimmed);
  const interviewMode = typeof globalThis !== "undefined" && globalThis._halInterviewMode;
  const fastTextRoute =
    typeof HalIndependentThought !== "undefined" &&
    HalIndependentThought.isFastTextRoute &&
    HalIndependentThought.isFastTextRoute(preRoute, trimmed);

  if (fastTextRoute && typeof HalRouteExec !== "undefined") {
    let fastOutcome = null;
    const fastTimer = setTimeout(() => {
      if (halModelAbortController && !halModelAbortController.signal.aborted) halModelAbortController.abort();
    }, 60000);
    try {
      fastOutcome = await HalRouteExec.execute(preRoute, effectiveQuery, {}, buildHalAgentCtx({ abortSignal }));
      if (fastOutcome && fastOutcome.text) {
        if (typeof HalCore !== "undefined" && HalCore.polishChatReply) {
          fastOutcome.text = HalCore.polishChatReply(fastOutcome.text, trimmed, preRoute, {
            halModels,
            halData,
            pages: getPages(),
            synthesize: false,
          });
        }
        halChatHistory.push({
          role: "hal",
          text: fastOutcome.text,
          lane: fastOutcome.lane || "local",
          actions: normalizeActions(fastOutcome.actions),
          intent: fastOutcome.intent || preRoute.intent || "",
          userQuery: trimmed,
          skipChatSpeech: wsSilent,
        });
        logAudit(trimmed, fastOutcome.intent || preRoute.intent);
      }
    } catch (error) {
      const detail = error && error.message ? error.message : String(error);
      halChatHistory.push({
        role: "hal",
        text: "HAL hit an error on a fast local route: " + detail,
        lane: "error",
        actions: [],
      });
    } finally {
      clearTimeout(fastTimer);
      halAskLoading = false;
      saveChatHistory();
      refreshHalSubmitUi(wsSilent);
    }
    return;
  }

  const aboutMePath =
    preRoute.useHalAboutMe &&
    typeof HalAgent !== "undefined" &&
    HalAgent.composeAboutMeInterview;

  if (aboutMePath) {
    let aboutOutcome = null;
    const aboutTimer = setTimeout(() => {
      if (halModelAbortController && !halModelAbortController.signal.aborted) halModelAbortController.abort();
    }, 120000);
    try {
      aboutOutcome = await Promise.race([
        HalAgent.composeAboutMeInterview(buildHalAgentCtx({ abortSignal })),
        new Promise((_, reject) =>
          setTimeout(() => reject(new Error("about-me compose timeout")), 90000),
        ),
      ]);
      if (aboutOutcome && aboutOutcome.text) {
        halChatHistory.push({
          role: "hal",
          text: aboutOutcome.text,
          lane: aboutOutcome.lane || "local",
          actions: normalizeActions(aboutOutcome.actions),
          intent: aboutOutcome.intent || preRoute.intent || "",
          userQuery: trimmed,
        });
        logAudit(trimmed, aboutOutcome.intent || preRoute.intent);
      }
    } catch (error) {
      const detail = error && error.message ? error.message : String(error);
      const fallback =
        "I read the local registry and import bundle — staff drive outbound steps while I stay read-only. " +
        "Ask about a specific page or import status for a narrower read on this office. " +
        "Nothing external runs without your consent on each action.";
      halChatHistory.push({
        role: "hal",
        text: /timeout/i.test(detail) ? fallback : "HAL hit an error on about-me: " + detail,
        lane: "local",
        actions: [],
        intent: preRoute.intent || "ops: hal-about-me",
        userQuery: trimmed,
      });
    } finally {
      clearTimeout(aboutTimer);
      halAskLoading = false;
      saveChatHistory();
      refreshHalSubmitUi(wsSilent);
    }
    return;
  }

  const isModelLane = !!(preRoute.useModel || preRoute.useReasoning || preRoute.useEscalation);
  const chat9000Cfg = halModels && halModels.config && halModels.config.chat9000;
  const chat9000On = !!(chat9000Cfg && chat9000Cfg.enabled !== false);
  let placeholder = null;
  let streamRenderAt = 0;
  if (isModelLane && window.HalAgent) {
    const lane = preRoute.lane || "chat8b";
    const label = preRoute.useEscalation
      ? "Escalating"
      : preRoute.useReasoning
        ? chat9000On
          ? "HAL 9000 reasoning"
          : "Reasoning"
        : chat9000On
          ? "HAL 9000 gathering"
          : "Gathering evidence";
    placeholder = { role: "hal", text: label + "…", lane, actions: [] };
    halChatHistory.push(placeholder);
    saveChatHistory();
    halTypeSig = halChatHistory.length + ":" + placeholder.text.length;
    refreshHalSubmitUi(wsSilent);
  }

  const onToolProgress = placeholder
    ? (ev) => {
        if (!ev || !placeholder) return;
        placeholder.tools = placeholder.tools || [];
        if (ev.phase === "start" && ev.tool && !placeholder.tools.includes(ev.tool)) {
          placeholder.tools.push(ev.tool);
          placeholder.text = "Gathering: " + formatHalToolsUsed(placeholder.tools) + "…";
          if (!wsSilent) refreshHalSubmitUi(wsSilent, { chatLogOnly: true });
        }
      }
    : undefined;

  const onToken = placeholder
    ? (partial) => {
        if (!partial) return;
        placeholder.text = partial;
        if (wsSilent) return;
        const now = Date.now();
        if (now - streamRenderAt < 40) return;
        streamRenderAt = now;
        refreshHalSubmitUi(wsSilent, { chatLogOnly: true, scrollQaLog: true });
        setInlineHalStreamingText(partial);
      }
    : undefined;

  let outcome = null;
  const queryTimeoutMs = interviewMode
    ? Number(globalThis._halInterviewTimeoutMs) || 240000
    : preRoute.useEscalation
      ? 180000
      : preRoute.useReasoning
        ? chat9000On
          ? 150000
          : 120000
        : chat9000On
          ? 90000
          : 60000;
  const queryTimer = setTimeout(() => {
    if (halModelAbortController && !halModelAbortController.signal.aborted) {
      halModelAbortController.abort();
    }
  }, queryTimeoutMs);
  try {
    if (window.HalAgent) {
      outcome = await HalAgent.processQuery(
        effectiveQuery,
        buildHalAgentCtx(onToken || onToolProgress ? { onToken, onToolProgress, abortSignal, routeQuery: trimmed } : { abortSignal, routeQuery: trimmed }),
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

    if (window.HalConsent) {
      const intent = String(outcome.intent || "");
      const needsConsent =
        /consent-required|consent:\s*required|capability:consent/i.test(intent) ||
        (HalConsent.outboundKind(trimmed, intent) && /consent|outbound|email|quickbooks|post|submit/i.test(String(outcome.text || "")));
      if (needsConsent) {
        const pending = HalConsent.createPendingFromQuery(trimmed, intent, { draftBody: outcome.text });
        outcome.text = HalConsent.wrapReplyWithConsent(outcome.text, pending);
        outcome.followUpChips = HalConsent.followUpChips(pending);
      }
    }

    if (placeholder) {
      placeholder.text = outcome.text;
      placeholder.lane = outcome.lane || placeholder.lane;
      placeholder.actions = normalizeActions(outcome.actions);
      placeholder.followUpChips = outcome.followUpChips || [];
      placeholder.intent = outcome.intent || "";
      placeholder.spokenScript = outcome.spokenScript || "";
      placeholder.skipChatSpeech = wsSilent || !!outcome.skipSpeech;
      placeholder.userQuery = trimmed;
      placeholder.tools = (outcome.plan && outcome.plan.tools) || placeholder.tools || [];
      placeholder.toolSummaries = summarizeToolResultsBrief(outcome.toolResults);
      placeholder.agentLoopTurns = outcome.agentLoopTurns || 0;
      const loopTools = placeholder.tools || [];
      placeholder.agentLoop = [
        { phase: "Plan", detail: outcome.intent || "Local route" },
        ...(loopTools.slice(0, 4).map((t) => ({ phase: "Tool", detail: String(t) }))),
        { phase: "Result", detail: String(outcome.lane || "local") },
      ];
    } else {
      const loopTools = (outcome.plan && outcome.plan.tools) || [];
      halChatHistory.push({
        role: "hal",
        text: outcome.text,
        lane: outcome.lane || "local",
        actions: normalizeActions(outcome.actions),
        followUpChips: outcome.followUpChips || [],
        intent: outcome.intent || "",
        spokenScript: outcome.spokenScript || "",
        skipChatSpeech: wsSilent || !!outcome.skipSpeech,
        userQuery: trimmed,
        tools: loopTools,
        toolSummaries: summarizeToolResultsBrief(outcome.toolResults),
        agentLoopTurns: outcome.agentLoopTurns || 0,
        agentLoop: [
          { phase: "Plan", detail: outcome.intent || "Local route" },
          ...loopTools.slice(0, 4).map((t) => ({ phase: "Tool", detail: String(t) })),
          { phase: "Result", detail: String(outcome.lane || "local") },
        ],
      });
    }
    logAudit(trimmed, outcome.intent);
  } catch (error) {
    if (error && error.name === "AbortError") {
      const abortText =
        "That question took too long locally — I stopped to keep the chat responsive. Try a narrower ask or refresh imports first.";
      if (placeholder) {
        placeholder.text = abortText;
        placeholder.lane = "local";
      } else {
        halChatHistory.push({ role: "hal", text: abortText, lane: "local", actions: [] });
      }
      logAudit(trimmed, "timeout");
    } else {
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
    }
  } finally {
    clearTimeout(queryTimer);
    halAskLoading = false;
    saveChatHistory();
    refreshHalSubmitUi(wsSilent);
    renderAuditLog();
    if (outcome && outcome.refreshPanel && currentDrawerKey) renderPanel(currentDrawerKey);
    if (outcome && /^sidenotes:/.test(String(outcome.intent || ""))) scrollHalPanelIntoView("sidenotes");
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
      const target = button.dataset.openPage || button.getAttribute("data-open-page");
      const scrollWidget =
        button.dataset.halScrollWidget || button.getAttribute("data-hal-scroll-widget") || "";
      logAudit("Open " + target, "navigate: drawer");
      closeDrawer();
      if (isHalPanelTarget(target)) {
        if (!isHalPageVisible()) select("hal");
        handleHalSurfaceNav(target);
        return;
      }
      select(target);
      if (scrollWidget) {
        setTimeout(() => scrollStaffWidgetIntoView(scrollWidget), 120);
      }
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

function validationArtifactsDrawerHtml() {
  const items =
    (halProgramSnapshot && halProgramSnapshot.importBundle && halProgramSnapshot.importBundle.validationArtifacts) || [];
  if (!items.length) return "";
  const summary = items.find((item) => item.key === "focusedValidatorSummary") || null;
  const slices = summary ? items.filter((item) => item.key !== "focusedValidatorSummary") : items;
  const now = Date.now();
  const ageText = (value) => {
    const then = Date.parse(value || "");
    if (!Number.isFinite(then)) return "time unknown";
    const minutes = Math.max(0, Math.round((now - then) / 60000));
    if (minutes < 1) return "updated just now";
    if (minutes === 1) return "updated 1 min ago";
    if (minutes < 60) return `updated ${minutes} min ago`;
    const hours = Math.round(minutes / 60);
    if (hours === 1) return "updated 1 hour ago";
    if (hours < 48) return `updated ${hours} hours ago`;
    const days = Math.round(hours / 24);
    return `updated ${days} days ago`;
  };
  const staleClass = (value) => {
    const then = Date.parse(value || "");
    if (!Number.isFinite(then)) return "drawer-meta";
    return now - then > 6 * 60 * 60 * 1000 ? "drawer-warn" : "drawer-meta";
  };
  const renderItem = (item) => {
    const state = item.ok ? "PASS" : "FAIL";
    const count = item.testsRun ? ` · tests ${item.testsRun}` : "";
    const dur = item.durationSec ? ` · ${item.durationSec}s` : "";
    const problem = (item.errors && item.errors[0] && (item.errors[0].message || item.errors[0].details)) || (item.failures && item.failures[0] && item.failures[0].test) || "";
    return `<li><strong>${escapeHtml(item.label)}</strong>: ${escapeHtml(state)}${escapeHtml(count)}${escapeHtml(dur)}<br><span class="${staleClass(item.updatedAt)}">${escapeHtml(ageText(item.updatedAt))}</span>${problem ? `<br><span class="drawer-meta">${escapeHtml(String(problem))}</span>` : ""}</li>`;
  };
  const detailBlock = slices.length && summary
    ? `<details class="drawer-meta"><summary>Show slice details (${slices.length})</summary><ul class="drawer-checklist">${slices.map(renderItem).join("")}</ul></details>`
    : `<ul class="drawer-checklist">${slices.map(renderItem).join("")}</ul>`;
  return `<div class="drawer-card drawer-card--source"><strong>Focused validators</strong>${summary ? `<p class="${staleClass(summary.updatedAt)}"><strong>${escapeHtml(summary.label)}</strong>: ${escapeHtml(summary.ok ? "PASS" : "FAIL")} · ${escapeHtml(ageText(summary.updatedAt))}${summary.testsRun ? ` · tests ${escapeHtml(String(summary.testsRun))}` : ""}${summary.durationSec ? ` · ${escapeHtml(String(summary.durationSec))}s` : ""}</p>` : ""}${detailBlock}</div>`;
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

function consentPanel(data) {
  const cfg = data || {};
  const examples = (cfg.examples || [])
    .map(
      (ex) =>
        `<button class="status-chip hal-suggest__chip" type="button" data-consent-test="${escapeHtml(ex.text)}">${escapeHtml(ex.text)}</button>`,
    )
    .join("");
  const categories = (cfg.categories || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");
  return `
    <p>${escapeHtml(cfg.summary || "Staff consent required before outbound actions.")}</p>
    ${categories ? `<div><strong>Consent categories</strong><ul class="drawer-list">${categories}</ul></div>` : ""}
    <div class="drawer-section">
      <h3 class="drawer-section__title">Consent checker</h3>
      <p class="drawer-meta">Type a proposed action. Outbound delivery requires your explicit consent — nothing is blocked by a firewall.</p>
      <form class="hal-chat__form" id="consentSimForm" autocomplete="off">
        <input id="consentSimInput" class="hal-chat__input" type="text" placeholder="e.g. Email the payer about this claim" aria-label="Test consent policy" />
        <button class="hal-chat__send" type="submit">Check</button>
      </form>
      <div class="drawer-card" id="consentSimResult">Enter an action above to check.</div>
      <div class="hal-suggest">${examples}</div>
    </div>`;
}

function firewallPanel(data) {
  return consentPanel(data);
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
    drawerContent.innerHTML = `<p>${escapeHtml(data.summary)}</p>${sourceHealthCards(drawerSourceItems())}${validationArtifactsDrawerHtml()}${runtimeIssuesDrawerHtml()}`;
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

  if (key === "consent" || key === "firewall") {
    const consentData = halData.consent || data || {};
    drawerContent.innerHTML = consentPanel(consentData);
    const form = document.getElementById("consentSimForm");
    const input = document.getElementById("consentSimInput");
    const result = document.getElementById("consentSimResult");
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const verdict = HalCore.consentVerdict(input.value, consentData, halData);
      result.innerHTML = `<strong>${verdict.intent === "consent: required" ? "Consent required" : "Local OK"}</strong><p>${escapeHtml(verdict.text)}</p>`;
      logAudit(input.value, verdict.intent);
      renderAuditLog();
    });
    drawerContent.querySelectorAll("[data-consent-test]").forEach((button) => {
      button.addEventListener("click", () => {
        input.value = button.dataset.consentTest;
        const verdict = HalCore.consentVerdict(input.value, consentData, halData);
        result.innerHTML = `<strong>${verdict.intent === "consent: required" ? "Consent required" : "Local OK"}</strong><p>${escapeHtml(verdict.text)}</p>`;
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

function openDrawer(_key) {
  closeDrawer();
}

function closeDrawer() {
  currentDrawerKey = null;
  if (!drawer) return;
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
    halPageVisible: isHalPageVisible(),
    drawerOpen: drawer && drawer.classList.contains("open"),
  });
}

function handleNr2Export(scope) {
  if (scope === "cpa-packet") {
    exportCpaPacketFlow();
    return;
  }
  if (scope === "page-storyboard") {
    exportPageStoryboardFlow();
    return;
  }
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
    halPageVisible: isHalPageVisible(),
  });
}

async function exportPageStoryboardFlow() {
  const pageId = resolvePageId(window.location.hash);
  if (typeof Services !== "undefined" && typeof Services.exportPageStoryboard === "function") {
    showHalActionNotice("Building page storyboard…", "info");
    try {
      const result = await Services.exportPageStoryboard(pageId);
      if (!result || !result.ok) {
        showHalActionNotice((result && result.error) || "Storyboard export failed.", "warn");
        return;
      }
      const EU = typeof ExportUtils !== "undefined" ? ExportUtils : null;
      if (!EU || typeof EU.downloadBlob !== "function") {
        showHalActionNotice("Export utilities failed to load.", "warn");
        return;
      }
      EU.downloadBlob(result.filename, result.blob);
      postOperatorAudit("export:page-storyboard", { pageKey: pageId });
      showHalActionNotice(`Storyboard downloaded (${result.filename}). Open storyboard.html → Print → Save as PDF.`, "success");
      return;
    } catch (err) {
      showHalActionNotice(String((err && err.message) || err || "Storyboard export failed."), "warn");
      return;
    }
  }
  const EU = typeof ExportUtils !== "undefined" ? ExportUtils : null;
  if (EU && typeof EU.exportPageStoryboardHtml === "function") {
    const result = EU.exportPageStoryboardHtml({ pageId, snapshot: halProgramSnapshot, feed: halWidgetFeed });
    if (result && result.ok) {
      postOperatorAudit("export:page-storyboard-local", { pageKey: pageId });
      showHalActionNotice(`Storyboard saved (${result.filename}). Open in browser → Print → Save as PDF.`, "success");
    }
    return;
  }
  showHalActionNotice("Storyboard export requires the NR2 server.", "warn");
}

async function exportCpaPacketFlow() {
  if (typeof Services === "undefined" || typeof Services.exportCpaPacket !== "function") {
    showHalActionNotice("CPA export requires the NR2 server.", "warn");
    return;
  }
  showHalActionNotice("Building CPA packet…", "info");
  try {
    const result = await Services.exportCpaPacket();
    if (!result || !result.ok) {
      showHalActionNotice((result && result.error) || "CPA export failed.", "warn");
      return;
    }
    const EU = typeof ExportUtils !== "undefined" ? ExportUtils : null;
    if (!EU || typeof EU.downloadBlob !== "function") {
      showHalActionNotice("Export utilities failed to load.", "warn");
      return;
    }
    EU.downloadBlob(result.filename, result.blob);
    postOperatorAudit("export:cpa-packet", { pageKey: "financial", widgetKey: "practiceFinancialOverview" });
    showHalActionNotice(`CPA packet downloaded (${result.filename}).`, "success");
  } catch (err) {
    showHalActionNotice(String((err && err.message) || err || "CPA export failed."), "warn");
  }
}

let nr2OpsHealth = null;
let nr2SidebarStatus = "All systems operational";
let nr2SidebarBadges = {};

function removeOpsHealthBanner() {
  const existing = document.getElementById("opsHealthBanner");
  if (existing) existing.remove();
}

function renderOpsHealthBanner(_health) {
  removeOpsHealthBanner();
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
let workstationHalTypeSig = null;

function typewriteWorkstationHalReply() {
  const log = document.getElementById("wsQaLog");
  if (!log) return;
  const rows = log.querySelectorAll(".ws-sn-hal-row--hal:not(.ws-sn-hal-row--loading)");
  if (!rows.length) return;
  const p = rows[rows.length - 1].querySelector(".ws-sn-hal-row__text");
  if (!p) return;
  const full = String(p.textContent || "");
  if (!full.trim()) return;
  const sig = full.length + ":" + full.slice(0, 48);
  if (sig === workstationHalTypeSig && halTypeTimer) return;
  workstationHalTypeSig = sig;
  if (halTypeTimer) {
    clearInterval(halTypeTimer);
    halTypeTimer = null;
  }
  const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce || full.length < 2) {
    p.textContent = full;
    p.classList.remove("ws-sn-hal-typing");
    return;
  }
  p.textContent = "";
  p.classList.add("ws-sn-hal-typing");
  const step = Math.max(1, Math.ceil(full.length / 90));
  const typeDelayMs = Math.max(20, Math.min(45, Math.floor(3200 / Math.max(Math.ceil(full.length / step), 1))));
  let i = 0;
  halTypeTimer = setInterval(() => {
    i += step;
    p.textContent = full.slice(0, i);
    log.scrollTop = log.scrollHeight;
    if (i >= full.length) {
      clearInterval(halTypeTimer);
      halTypeTimer = null;
      p.textContent = full;
      p.classList.remove("ws-sn-hal-typing");
    }
  }, typeDelayMs);
}

function setInlineHalStreamingText(text) {
  const root = halMountRoot();
  if (!root) return;
  const box = root.querySelector(".chat-messages");
  if (!box) return;
  const rows = box.querySelectorAll(".message.message-hal");
  if (!rows.length) return;
  const p = rows[rows.length - 1].querySelector("p");
  if (!p) return;
  if (halTypeTimer) {
    clearInterval(halTypeTimer);
    halTypeTimer = null;
  }
  p.classList.remove("message-typing");
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
        ? HalCore.toSpokenScript(displayText, query, route, { preferBrief, halModels })
        : "";
  return { query, route, preferBrief, spokenText, halModels };
}

function typewriteLastHalMessage() {
  const root = halMountRoot();
  if (!root) return;
  const box = root.querySelector(".chat-messages");
  if (!box) return;
  const rows = box.querySelectorAll(".message");
  if (!rows.length) return;
  const last = rows[rows.length - 1];
  if (!last.classList.contains("message-hal")) return;
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
  const lastHal = halChatHistory.length ? halChatHistory[halChatHistory.length - 1] : null;
  if (lastHal && lastHal.skipChatSpeech) {
    p.textContent = full;
    p.classList.remove("message-typing");
    return;
  }
  const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce || full.length < 2) {
    p.textContent = full;
    p.classList.remove("message-typing");
    if (window.HalVoice && HalVoice.speakHalReply && !window._halRandomQaSkipSpeech && !(lastHal && lastHal.speechStarted)) {
      const speechCtx = halSpeechContextForLastReply(full);
      HalVoice.speakHalReply(full, { interrupt: true, ...speechCtx });
    }
    return;
  }
  p.textContent = "";
  p.classList.add("message-typing");
  const step = Math.max(1, Math.ceil(full.length / 110));
  const iterations = Math.ceil(full.length / step);
  let speechMs = 2400;
  const speechCtx = halSpeechContextForLastReply(full);
  if (window.HalVoice && !window._halRandomQaSkipSpeech && !(lastHal && lastHal.speechStarted)) {
    if (HalVoice.speakHalReply) {
      const spoken = HalVoice.speakHalReply(full, { interrupt: true, ...speechCtx });
      speechMs = (spoken && spoken.durationMs) || speechMs;
    } else if (HalVoice.estimateDurationMs) {
      speechMs = HalVoice.estimateDurationMs(speechCtx.spokenText || full);
    }
  } else if (window.HalVoice && HalVoice.estimateConversationalDurationMs) {
    speechMs = HalVoice.estimateConversationalDurationMs(speechCtx.spokenText || full);
  } else if (window.HalVoice && HalVoice.estimateDurationMs) {
    speechMs = HalVoice.estimateDurationMs(speechCtx.spokenText || full);
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
      p.classList.remove("message-typing");
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
    statusEl.className = "stress-status";
    if (st.status === "Pass") statusEl.classList.add("stress-status--ok");
    else if (st.status === "Fail") statusEl.classList.add("stress-status--fail");
    else if (st.running) statusEl.classList.add("stress-status--run");
  }

  const failEl = document.getElementById("hpStressFailures");
  if (failEl) failEl.classList.toggle("stress-fail-num", !!st.failureTotal);

  const list = document.getElementById("hpStressFailList");
  if (list && Array.isArray(st.topFailures)) {
    list.innerHTML = st.topFailures.length
      ? st.topFailures
          .slice(0, 12)
          .map(
            (f) =>
              `<li><span class="stress-fail-count">${escapeHtml(String(f.count))}×</span> <code>${escapeHtml(f.stage)}</code> — ${escapeHtml(f.error)}<br><em class="text-muted">${escapeHtml(String(f.example || "").slice(0, 120))}</em></li>`,
          )
          .join("")
      : '<li class="stress-empty">No failures yet.</li>';
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
  const root = halMountRoot();
  if (!root || !window.HalPage) return;
  HalPage.render({
    root,
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
    halMorningBriefing,
    halStressTest,
    halAgentHealth: window.HalAgent ? HalAgent.getHealth() : null,
    sidenotesHubPath: nr2SidenotesHubPath,
  });
  typewriteLastHalMessage();
}

function renderSidebar(activeId) {
  if (NR2_WORKSTATION_ONLY) return;
  if (!sidebar || typeof PageSchema === "undefined") return;
  if (PageSchema.LAYOUT_EPOCH !== "moonshot-mockup") {
    sidebar.innerHTML =
      '<div class="sidebar__boot-error">Legacy schema blocked. Reload with ?v=hal-10084&__nr2_purge=1</div>';
    return;
  }
  const MC =
    (typeof MoonshotMockupChrome !== "undefined" && MoonshotMockupChrome) ||
    (typeof globalThis !== "undefined" && globalThis.MoonshotMockupChrome) ||
    null;
  if (!MC || typeof MC.renderNavRail !== "function") {
    sidebar.innerHTML = '<div class="sidebar__boot-error">Moonshot mockup chrome failed to load.</div>';
    return;
  }
  sidebar.className = "nav-rail";
  sidebar.setAttribute("aria-label", "Main navigation");
  sidebar.innerHTML = MC.renderNavRail(activeId);
  nav = document.getElementById("nav");
  Object.keys(buttons).forEach((key) => delete buttons[key]);
  if (!nav) return;
  nav.querySelectorAll("[data-nav]").forEach((button) => {
    const id = button.getAttribute("data-nav");
    buttons[id] = button;
    button.addEventListener("click", () => select(id));
  });
  nav.querySelectorAll("[data-nav-widget], [data-nav-panel]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      const pageId = button.getAttribute("data-nav-page");
      const widgetKey = button.getAttribute("data-nav-widget");
      const panelKey = button.getAttribute("data-nav-panel");
      if (!pageId) return;
      const scrollOpts = panelKey ? { panelKey } : widgetKey ? { widgetKey } : null;
      if (pageId === activeId) {
        if (scrollOpts) scrollPageSectionIntoView(pageId, scrollOpts);
        return;
      }
      select(pageId, scrollOpts ? { scrollTo: scrollOpts } : undefined);
    });
  });
}

function select(id, options) {
  if (NR2_WORKSTATION_ONLY) {
    if (workstationPage) workstationPage.hidden = false;
    renderWorkstationScreen();
    stopOfficeChannelPoll();
    startOfficeChannelPoll();
    loadSideNotesInbox()
      .then(() => resolveWorkstationStationFromInbox())
      .then(() => {
        refreshSideNoteMonitor({ patchUi: false });
        renderWorkstationScreen();
      })
      .catch(() => renderWorkstationScreen());
    return;
  }
  const pageId = resolvePageId(id);
  const page = getPages().find((p) => p.id === pageId) || getPages().find((p) => p.id === defaultPageId()) || getPages()[0];
  if (!page) return;
  const isHal = page.id === "hal" && PageViews && !PageViews.hasPage(page.id);
  const isWorkstation =
    !NR2_FINANCIAL_ONLY && page.id === "workstation" && PageViews && !PageViews.hasPage(page.id);
  if (appPage) {
    if (isHal) {
      appPage.hidden = false;
      renderHalScreen();
      activateSideNotesPanel().catch(() => {
        /* sidenotes inbox optional */
      });
    } else if (!isWorkstation) {
      appPage.hidden = false;
      if (PageViews && PageViews.hasPage(page.id)) {
        PageViews.renderPageView(appPage, halData, page.id, select, halWidgetFeed, halProgramSnapshot);
        if (typeof PageChrome !== "undefined" && PageChrome.refreshHalReadinessStrip) {
          PageChrome.refreshHalReadinessStrip(page.id, halWidgetFeed);
        }
      } else if (window.UI && window.UI.ErrorState) {
        appPage.innerHTML = `<div class="page-view"><article class="ms-page" data-pv-page="${page.id}">${UI.ErrorState({
          title: "Page not available",
          message: `Could not open "${page.id}". Choose a page from the sidebar or restart Start Program.`,
        })}</article></div>`;
      }
    } else {
      appPage.hidden = true;
    }
  }
  renderSidebar(page.id);
  if (isWorkstation) {
    stopOfficeChannelPoll();
    startOfficeChannelPoll();
    loadSideNotesInbox()
      .then(() => resolveWorkstationStationFromInbox())
      .then(() => {
        refreshSideNoteMonitor({ patchUi: false });
        renderWorkstationScreen();
      })
      .catch(() => renderWorkstationScreen());
  } else {
    stopOfficeChannelPoll();
  }
  closeDrawer();
  const nextHash = "#" + page.id;
  if (window.location.hash !== nextHash) {
    window.location.hash = page.id;
  }
  if (typeof ImportReadinessGate !== "undefined" && ImportReadinessGate.evaluate) {
    ImportReadinessGate.evaluate(page.id);
  }
  if (
    !NR2_WORKSTATION_ONLY &&
    (page.id === "quickbooks" || page.id === "financial" || page.id === "hal") &&
    typeof Services !== "undefined" &&
    Services.ensureQuickBooksFresh
  ) {
    Services.ensureQuickBooksFresh()
      .then((qb) => {
        if (qb && qb.refreshed) {
          invalidateProgramCaches("qb-sync-if-stale");
          scheduleHalWidgetRefresh();
          if (appPage && !appPage.hidden && PageViews && PageViews.hasPage(page.id)) {
            PageViews.renderPageView(appPage, halData, page.id, select, halWidgetFeed, halProgramSnapshot);
          }
        }
      })
      .catch(() => {});
  }
  if (
    !NR2_WORKSTATION_ONLY &&
    page.id === "softdent" &&
    typeof NR2SoftdentDaily !== "undefined" &&
    typeof NR2SoftdentDaily.prefetchLive === "function"
  ) {
    NR2SoftdentDaily.prefetchLive()
      .then(() => {
        if (appPage && !appPage.hidden && PageViews && PageViews.hasPage(page.id)) {
          PageViews.renderPageView(appPage, halData, page.id, select, halWidgetFeed, halProgramSnapshot);
        }
      })
      .catch(() => {});
  }
  const scrollTo = options && options.scrollTo;
  if (scrollTo) {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => scrollPageSectionIntoView(page.id, scrollTo));
    });
  }
}

function assertDesignSchemaLoaded() {
  if (NR2_WORKSTATION_ONLY) {
    if (typeof NR2Boot !== "undefined" && !NR2Boot.ready) return false;
    if (typeof WorkstationSchema !== "undefined" && typeof PageChrome !== "undefined") return true;
    const frame = document.getElementById("pageFrame");
    if (frame) {
      frame.innerHTML =
        '<div class="pv-state pv-state--error" role="alert"><strong class="pv-state__title">Workstation schema failed to load</strong><p class="pv-state__msg">workstation-schema.js and page-chrome.js are required. Launch Start Workstation.bat and reload.</p></div>';
    }
    return false;
  }
  if (typeof NR2Boot !== "undefined" && !NR2Boot.ready) return false;
  const hasPageSchema = typeof PageSchema !== "undefined" && typeof PageChrome !== "undefined";
  if (hasPageSchema) return true;
  const frame = document.getElementById("pageFrame");
  if (frame) {
    frame.innerHTML =
      '<div class="pv-state pv-state--error" role="alert"><strong class="pv-state__title">Design schema failed to load</strong><p class="pv-state__msg">page-schema.js and page-chrome.js are required. Run StartProgram.bat and reload http://127.0.0.1:8765/.</p></div>';
  }
  return false;
}

function renderSchemaVersionMismatch(pythonVersion, jsVersion) {
  const frame = document.getElementById("pageFrame");
  const sidebar = document.getElementById("sidebar");
  if (sidebar) sidebar.innerHTML = "";
  if (!frame) return;
  const launcher = NR2_WORKSTATION_ONLY ? "Start Workstation" : "Start Program";
  const mismatchTitle = NR2_WORKSTATION_ONLY ? "Desktop build mismatch" : "Build mismatch";
  const serverLabel = NR2_WORKSTATION_ONLY ? "Desktop shell reports" : "NR2 server reports";
  const inner =
    `<strong class="pv-state__title">${mismatchTitle}</strong>` +
    `<p class="pv-state__msg">${serverLabel} <strong>${String(pythonVersion).replace(/</g, "&lt;")}</strong> but the loaded page schema is <strong>${String(jsVersion).replace(/</g, "&lt;")}</strong>.</p>` +
    `<p class="pv-state__msg">Close this tab or window completely, then launch <strong>${launcher}</strong> again.</p>`;
  if (NR2_WORKSTATION_ONLY && frame.querySelector("#workstationPage")) {
    let banner = frame.querySelector(".nr2-boot-error");
    if (!banner) {
      banner = document.createElement("div");
      banner.className = "pv-state pv-state--error nr2-boot-error ws-boot-error";
      banner.setAttribute("role", "alert");
      frame.insertBefore(banner, frame.firstChild);
    }
    banner.innerHTML = inner;
    return;
  }
  frame.innerHTML = `<div class="pv-state pv-state--error nr2-boot-error" role="alert">${inner}</div>`;
}

renderRuntimeModeBanner();
if (!NR2_WORKSTATION_ONLY && assertDesignSchemaLoaded()) {
  renderSidebar(resolvePageId(window.location.hash));
}

if (drawerClose) {
  drawerClose.addEventListener("click", closeDrawer);
}

if (appPage) {
  appPage.addEventListener("submit", async (event) => {
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

  appPage.addEventListener("keydown", (event) => {
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

  appPage.addEventListener("dblclick", async (event) => {
    const ring = event.target.closest("[data-hal-ring-cmd]");
    if (!ring) return;
    const cmd = ring.getAttribute("data-hal-ring-cmd");
    if (!cmd) return;
    await handleHalSubmit(cmd);
    renderHalScreen();
  });

  appPage.addEventListener("click", async (event) => {
    const copyResponse = event.target.closest("[data-hal-copy-response]");
    if (copyResponse) {
      const row = copyResponse.closest(".message");
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
    if (widgetCard && !event.target.closest("[data-hal-widget-nav]") && !event.target.closest("[data-hal-action]") && !event.target.closest("[data-hal-actuator]")) {
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
    const actuatorBtn = event.target.closest("[data-hal-actuator]");
    if (actuatorBtn) {
      event.stopPropagation();
      await handleHalActuatorClick(actuatorBtn);
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
    const aboutMeBtn = event.target.closest("[data-hal-about-me]");
    if (aboutMeBtn) {
      const q =
        typeof HalAboutMe !== "undefined" && HalAboutMe.queryText
          ? HalAboutMe.queryText()
          : "HAL about me";
      await handleHalSubmit(q);
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

if (workstationPage) {
  workstationPage.addEventListener("submit", async (event) => {
    if (event.target.id === "wsQaForm") {
      event.preventDefault();
      const input = document.getElementById("wsQaInput");
      const value = input ? input.value : "";
      workstationAskDraft = value;
      await handleWorkstationHalSubmit(value);
      if (input) {
        input.value = "";
        workstationAskDraft = "";
      }
      return;
    }
    if (event.target.id === "wsOfficeForm" || event.target.id === "wsOfficeChatForm") {
      event.preventDefault();
      const form = event.target;
      const fromChat = form.id === "wsOfficeChatForm";
      const input = document.getElementById(fromChat ? "wsOfficeChatInput" : "wsOfficeInput");
      const value = input ? input.value : "";
      if (fromChat) officeChannelTargets = ["all"];
      await handleOfficeChannelSubmit(value, false);
      if (input) input.value = "";
      officeChannelDraft = "";
      return;
    }
  });

  workstationPage.addEventListener("input", (event) => {
    const target = event.target;
    if (!target) return;
    if (target.id === "wsQaInput") {
      workstationAskDraft = target.value || "";
      return;
    }
    if (target.id === "wsOfficeInput" || target.id === "wsOfficeChatInput") {
      officeChannelDraft = target.value || "";
    }
  });

  workstationPage.addEventListener("focusout", () => {
    window.setTimeout(() => {
      if (!workstationRenderDeferred) return;
      if (workstationComposeFieldFocused()) return;
      renderWorkstationScreen({ force: true });
    }, 0);
  });

  workstationPage.addEventListener("change", (event) => {
    const target = event.target;
    if (!target) return;
    if (target.matches("[data-ws-station-select]")) {
      const name = target.value || "";
      if (name) {
        applyWorkstationStation(name);
        renderWorkstationScreen();
      }
      return;
    }
  });

  workstationPage.addEventListener("keydown", (event) => {
    const target = event.target;
    if (!target || event.key !== "Enter" || event.shiftKey) return;
    if (target.id === "wsQaInput") {
      event.preventDefault();
      const form = document.getElementById("wsQaForm");
      if (form && typeof form.requestSubmit === "function") form.requestSubmit();
      return;
    }
    if (target.id === "wsOfficeInput" || target.id === "wsOfficeChatInput") {
      event.preventDefault();
      const form = target.closest("form");
      if (form && typeof form.requestSubmit === "function") form.requestSubmit();
    }
    const halCmdKey = event.target.closest("[data-hal-cmd],[data-hal-activity-cmd]");
    if (halCmdKey && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      const cmd =
        halCmdKey.getAttribute("data-hal-cmd") || halCmdKey.getAttribute("data-hal-activity-cmd");
      if (cmd) handleWorkstationHalSubmit(cmd);
    }
  });

  workstationPage.addEventListener("click", async (event) => {
    const copyResponse = event.target.closest("[data-hal-copy-response]");
    if (copyResponse) {
      const row = copyResponse.closest(".message");
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
    const suggest = event.target.closest("[data-hal-suggest]");
    if (suggest) {
      await handleWorkstationHalSubmit(suggest.getAttribute("data-hal-suggest"));
      return;
    }
    const followup = event.target.closest("[data-hal-followup]");
    if (followup) {
      await handleWorkstationHalSubmit(followup.getAttribute("data-hal-followup"));
      return;
    }
    const voiceTest = event.target.closest("[data-hal-voice-test]");
    if (voiceTest) {
      if (window.HalVoice) HalVoice.test();
      return;
    }
    const officePrompt = event.target.closest("[data-ws-office-prompt]");
    if (officePrompt) {
      if (workstationPromptsEditing) return;
      const text = officePrompt.getAttribute("data-ws-office-prompt") || "";
      if (!text.trim()) return;
      await handleOfficeChannelSubmit(text, false);
      return;
    }
    const promptEdit = event.target.closest("[data-ws-prompt-edit]");
    if (promptEdit) {
      workstationPromptsEditing = true;
      renderWorkstationScreen();
      const first = workstationPageRoot && workstationPageRoot.querySelector("[data-ws-prompt-body='0']");
      if (first && typeof first.focus === "function") first.focus();
      return;
    }
    const promptSave = event.target.closest("[data-ws-prompt-save]");
    if (promptSave) {
      const next = collectWorkstationPromptEditsFromDom(workstationPageRoot);
      saveWorkstationMessagePrompts(next);
      workstationPromptsEditing = false;
      renderWorkstationScreen();
      return;
    }
    const promptCancel = event.target.closest("[data-ws-prompt-cancel]");
    if (promptCancel) {
      workstationPromptsEditing = false;
      renderWorkstationScreen();
      return;
    }
    const promptReset = event.target.closest("[data-ws-prompt-reset]");
    if (promptReset) {
      saveWorkstationMessagePrompts(defaultWorkstationMessagePrompts());
      workstationPromptsEditing = false;
      renderWorkstationScreen();
      return;
    }
    const snLeftTab = event.target.closest("[data-ws-sn-left-tab]");
    if (snLeftTab) {
      workstationLeftTab = String(snLeftTab.getAttribute("data-ws-sn-left-tab") || "users").toLowerCase();
      renderWorkstationScreen();
      return;
    }
    const snGroup = event.target.closest("[data-ws-sn-group]");
    if (snGroup) {
      selectOfficeChannelGroup(snGroup.getAttribute("data-ws-sn-group"));
      workstationLeftTab = "groups";
      renderWorkstationScreen();
      return;
    }
    const snTarget = event.target.closest("[data-ws-sn-target]");
    if (snTarget) {
      toggleOfficeChannelTarget(snTarget.getAttribute("data-ws-sn-target") || "all");
      workstationLeftTab = "users";
      renderWorkstationScreen();
      return;
    }
    const targetPick = event.target.closest("[data-ws-office-target]");
    if (targetPick) {
      toggleOfficeChannelTarget(targetPick.getAttribute("data-ws-office-target") || "all");
      officeChannelPickerOpen = false;
      renderWorkstationScreen();
      return;
    }
    const clearDraft = event.target.closest("[data-ws-office-clear]");
    if (clearDraft) {
      officeChannelDraft = "";
      renderWorkstationScreen();
      return;
    }
    const openPicker = event.target.closest("[data-ws-open-picker]");
    if (openPicker) {
      officeChannelPickerOpen = true;
      renderWorkstationScreen();
      return;
    }
    const closePicker = event.target.closest("[data-ws-close-picker]");
    if (closePicker) {
      officeChannelPickerOpen = false;
      renderWorkstationScreen();
      return;
    }
    const syncBtn = event.target.closest("[data-ws-sync]");
    if (syncBtn) {
      await runWorkstationSync(syncBtn.getAttribute("data-ws-sync"));
      return;
    }
    const openHal = event.target.closest("[data-ws-open-hal]");
    if (openHal) {
      const url = `${String(window.NR2_HAL_HUB_URL || "http://127.0.0.1:8765").replace(/\/+$/, "")}/#hal`;
      window.open(url, "_blank", "noopener");
      return;
    }
    const pageTab = event.target.closest("[data-ws-page-tab]");
    if (pageTab) {
      const next = String(pageTab.getAttribute("data-ws-page-tab") || "send").toLowerCase();
      workstationMainTab =
        next === "askhal"
          ? "askhal"
          : next === "history"
            ? "history"
            : next === "officechat"
              ? "officechat"
              : next === "sync"
                ? "sync"
                : "send";
      if (workstationMainTab === "history" || workstationMainTab === "officechat") {
        markWorkstationInboxRead(mergedInboxMessagesForUi());
      }
      if (workstationMainTab === "officechat") {
        officeChannelTargets = ["all"];
        officeChannelGroup = "everyone";
      }
      if (workstationMainTab === "sync") {
        refreshWorkstationSyncHealth().then(() => renderWorkstationScreen({ force: true }));
      }
      if (workstationMainTab !== "send" && workstationMainTab !== "officechat") workstationPromptsEditing = false;
      renderWorkstationScreen();
      return;
    }
    const sideNoteAdd = event.target.closest("[data-hal-sidenote-add]");
    if (sideNoteAdd) {
      const input = document.getElementById("hpSideNoteInput");
      const text = input ? input.value : "";
      if (String(text).trim().length >= 2) {
        addSideNote(text);
        if (input) input.value = "";
        renderWorkstationScreen();
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
        renderWorkstationScreen();
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
        renderWorkstationScreen();
      }
      return;
    }
    const cmd = event.target.closest("[data-hal-cmd]");
    if (cmd) {
      await handleWorkstationHalSubmit(cmd.getAttribute("data-hal-cmd"));
    }
  });
}

if (appPage) {
  appPage.addEventListener("click", async (event) => {
    const pageCmd = event.target.closest("[data-page-command]");
    if (pageCmd && window.NR2_FLAGS && window.NR2_FLAGS.hal_commands !== false) {
      await runHalPageCmd(pageCmd.getAttribute("data-page-command"));
      return;
    }
    const qbToggle = event.target.closest("[data-qb-view-toggle]");
    if (qbToggle) {
      const mode = qbToggle.getAttribute("data-qb-view-toggle") || "mockup";
      try {
        localStorage.setItem("qb.viewMode", mode === "legacy" ? "legacy" : "mockup");
      } catch {
        /* private mode */
      }
      const currentId = resolvePageId(window.location.hash);
      if (currentId === "quickbooks" && PageViews && PageViews.hasPage("quickbooks")) {
        PageViews.renderPageView(appPage, halData, "quickbooks", select, halWidgetFeed, halProgramSnapshot);
        if (typeof PageChrome !== "undefined" && PageChrome.refreshHalReadinessStrip) {
          PageChrome.refreshHalReadinessStrip("quickbooks", halWidgetFeed);
        }
        if (typeof NR2MoonshotUI !== "undefined" && NR2MoonshotUI.enhancePage) {
          NR2MoonshotUI.enhancePage("quickbooks", appPage).catch(() => {});
        }
      }
      return;
    }
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
    const navBtn = event.target.closest("[data-ms-nav]");
    if (navBtn) select(navBtn.getAttribute("data-ms-nav"));
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
  if (!drawer || !currentDrawerKey) return;
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
  if (NR2_WORKSTATION_ONLY) {
    workstationChatHistory = sanitizeWorkstationChatHistory(
      (await DesktopBridge.storageGet("workstationChatHistory")) || [],
    );
    if (workstationChatHistory.length > 2) {
      workstationChatHistory = workstationChatHistory.slice(-2);
    }
    saveWorkstationChatHistory();
    const savedPrompts = await DesktopBridge.storageGet("workstationMessagePrompts");
    workstationMessagePrompts = savedPrompts ? normalizeWorkstationMessagePrompts(savedPrompts) : null;
    const savedStation = await DesktopBridge.storageGet("workstationStationName");
    if (savedStation) applyWorkstationStation(savedStation, { persist: false });
    loadWorkstationReadIdsFromStorage(await DesktopBridge.storageGet("workstationReadIds"));
  }
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
    if (typeof Services.prefetchSoftdentDaily === "function") {
      Services.prefetchSoftdentDaily().catch(() => {});
    }
    await scheduleHalWidgetRefresh();
  } catch {
    /* background import sync optional */
  }
}

function renderWorkstationDesktopRequired(message) {
  const frame = document.getElementById("pageFrame");
  if (!frame) return;
  const root = document.getElementById("workstationPageRoot");
  const msg = message || "NR2 Office Workstation runs only in the desktop app.";
  const inner =
    `<strong class="pv-state__title">Desktop app required</strong>` +
    `<p class="pv-state__msg">${String(msg).replace(/</g, "&lt;")}</p>` +
    `<p class="pv-state__msg">Close any browser tab. Launch <strong>Start Workstation</strong> or double-click the <strong>NR2 Workstation</strong> shortcut.</p>`;
  if (root) {
    root.innerHTML = `<div class="pv-state pv-state--error nr2-boot-error ws-boot-error" role="alert">${inner}</div>`;
    return;
  }
  frame.innerHTML = `<div class="pv-state pv-state--error nr2-boot-error" role="alert">${inner}</div>`;
}

async function boot() {
  renderRuntimeModeBanner();
  if (!NR2_WORKSTATION_ONLY && typeof DesktopBridge !== "undefined" && DesktopBridge.isLoopbackHost && DesktopBridge.isLoopbackHost()) {
    enforceSingleFinancialTab();
  }
  if (NR2_WORKSTATION_ONLY) {
    document.title = "NR2 Office Workstation";
    document.body.classList.add("nr2-workstation-app");
    const sidebar = document.getElementById("sidebar");
    if (sidebar) sidebar.setAttribute("hidden", "");
    if (!DesktopBridge.hasDesktopApi || !DesktopBridge.hasDesktopApi()) {
      renderWorkstationDesktopRequired(
        "This URL is for the pywebview desktop window only — not for Chrome, Edge, or other browsers.",
      );
      return;
    }
    select("workstation");
  }
  if (typeof NR2Boot !== "undefined" && !NR2Boot.ready) {
    if (NR2_WORKSTATION_ONLY) select("workstation");
    return;
  }
  await loadPersistedState();
  try {
    if (typeof NR2Boot !== "undefined" && NR2Boot.verifyDesktopManifest) {
      const manifest = await NR2Boot.verifyDesktopManifest();
      if (!manifest.ok) {
        if (manifest.mode === "workstation-desktop-required") {
          renderWorkstationDesktopRequired(manifest.error);
          return;
        }
        if (manifest.pythonVersion && manifest.jsVersion) {
          renderSchemaVersionMismatch(manifest.pythonVersion, manifest.jsVersion);
        } else if (manifest.manifestVersion && manifest.jsVersion) {
          renderSchemaVersionMismatch(manifest.manifestVersion, manifest.jsVersion);
        }
        if (!NR2_WORKSTATION_ONLY) return;
      }
    }
    const info = await DesktopBridge.getAppInfo();
    if (sideNotesImEnabled() && info && info.sidenotesHub) nr2SidenotesHubPath = info.sidenotesHub;
    if (info && info.halHubUrl) window.NR2_HAL_HUB_URL = info.halHubUrl;
    if (info && info.hubPopupWatcher) {
      globalThis.NR2_PYTHON_POPUP_WATCHER = true;
      if (typeof DesktopBridge !== "undefined" && DesktopBridge.flushMessagePopups) {
        const flushPopups = () => DesktopBridge.flushMessagePopups().catch(() => {});
        flushPopups();
        window.setInterval(flushPopups, 400);
      }
    }
    if (info && info.workstationFastHal === false) {
      globalThis._halWorkstationFastMode = false;
      globalThis.NR2_WORKSTATION_FAST_HAL = false;
    } else if (NR2_WORKSTATION_ONLY && (info == null || info.workstationFastHal !== false)) {
      globalThis._halWorkstationFastMode = true;
    }
    if (info && info.designSchemaVersion) {
      nr2DesignSchemaVersion = info.designSchemaVersion;
      const expectedSchemaVersion =
        NR2_WORKSTATION_ONLY && typeof WorkstationSchema !== "undefined" && WorkstationSchema.SCHEMA_VERSION
          ? WorkstationSchema.SCHEMA_VERSION
          : PageSchema && PageSchema.SCHEMA_VERSION
            ? PageSchema.SCHEMA_VERSION
            : null;
      if (expectedSchemaVersion && info.designSchemaVersion !== expectedSchemaVersion) {
        renderSchemaVersionMismatch(info.designSchemaVersion, expectedSchemaVersion);
        if (!NR2_WORKSTATION_ONLY) return;
      }
      if (!NR2_WORKSTATION_ONLY) {
        renderSidebar(window.location.hash.replace("#", "") || getPages()[0].id);
      }
    }
  } catch {
    if (NR2_WORKSTATION_ONLY) {
      renderWorkstationDesktopRequired("Could not connect to the NR2 Workstation desktop shell.");
      return;
    }
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
  if (window.HalEmployee && typeof HalEmployee.ensureTargetLevel === "function") {
    HalEmployee.ensureTargetLevel(halModels, 7);
  }
  const bootInitialPage = resolvePageId(window.location.hash);
  if (bootInitialPage === "hal" && appPage && typeof select === "function") {
    select("hal");
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
  const skipAutonomousHal = NR2_WORKSTATION_ONLY && workstationFastHalEnabled();
  if (!skipAutonomousHal && window.HalProactive && typeof HalProactive.startPlacementTimer === "function") {
    HalProactive.startPlacementTimer(buildHalAgentCtx);
    if (typeof HalProactive.startBriefingScheduler === "function") {
      HalProactive.startBriefingScheduler(buildHalAgentCtx);
    }
  }
  if (!skipAutonomousHal && window.HalAutonomousOps && typeof HalAutonomousOps.start === "function") {
    HalAutonomousOps.start(buildHalAgentCtx);
  }
  if (!skipAutonomousHal && window.HalDirector && typeof HalDirector.start === "function") {
    HalDirector.start(buildHalAgentCtx);
  }
  startSideNoteMonitor();
  startDocumentSyncListener();
  startDocumentSourceRefreshTimer();
  startImportCoordinatorRefreshTimer();
  await refreshHalWidgetFeed().catch(() => {
    /* widget feed optional on boot */
  });
  if (!skipAutonomousHal && window.HalProactive && typeof HalProactive.maybeFireMorningBriefingOnBoot === "function") {
    HalProactive.maybeFireMorningBriefingOnBoot(buildHalAgentCtx())
      .then((card) => {
        if (!card) return;
        halMorningBriefing = card;
        if (halProactiveBriefing) {
          halProactiveBriefing.morningBriefing = card;
        }
        renderHalScreen();
        if (window.HalHubClient && typeof HalHubClient.pushMorningBriefingToWorkstation === "function") {
          HalHubClient.pushMorningBriefingToWorkstation(card).catch(() => {});
        }
        showHalActionNotice(`Morning briefing: ${card.sentence}`, "info");
      })
      .catch(() => {});
  }
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
  const initial = NR2_WORKSTATION_ONLY ? "workstation" : resolvePageId(window.location.hash);
  select(initial);
  if (!NR2_WORKSTATION_ONLY) startHalHubDispatcher();
  if (NR2_WORKSTATION_ONLY) {
    startWorkstationHubHeartbeat();
    refreshWorkstationSyncHealth().catch(() => {});
    return;
  }
  loadLocalSidenotesBridge().catch(() => {});
  if (typeof ImportCoordinator !== "undefined") {
    ImportCoordinator.refresh({ reason: "boot" })
      .then(() => forceHalWidgetPlacement({ reason: "boot" }))
      .catch(() => forceHalWidgetPlacement({ reason: "boot-fallback" }));
  } else {
    refreshImportsInBackground();
    forceHalWidgetPlacement({ reason: "boot" }).catch(() => {
      runHalProactiveCycle({ force: true, forcePlacement: true, showBootNotice: true }).catch(() => {
        /* proactive cycle optional on boot */
      });
    });
  }
  if (window.HalConsent && HalConsent.loadPending) {
    HalConsent.loadPending().catch(() => {});
  }
  if (typeof window !== "undefined") {
    window.addEventListener("nr2:scheduled-briefing", async (event) => {
      const detail = event && event.detail;
      if (!detail || !detail.briefing) return;
      const label = detail.kind === "eod" ? "End-of-day" : "Morning";
      if (detail.briefing.headline) {
        showHalActionNotice(`${label} briefing: ${detail.briefing.headline}`, "info");
      }
      if (detail.kind !== "eod" || !window.HalProactive || !HalProactive.formatProactiveBriefing) return;
      const body = HalProactive.formatProactiveBriefing(detail.briefing);
      const port = window.location.port || "8765";
      try {
        await fetch(`${window.location.protocol}//${window.location.hostname || "127.0.0.1"}:${port}/api/outbound/briefing-email`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            subject: "NR2 end-of-day HAL briefing",
            body,
            consentText: "Scheduled internal briefing",
            actor: "HAL",
          }),
        });
      } catch {
        /* Set NR2_BRIEFING_EMAIL_TO and SMTP to enable EOD email digest */
      }
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
  window.addEventListener("nr2:page-refresh-requested", () => {
    const currentId = (window.location.hash || "").replace("#", "") || getPages()[0].id;
    if (currentId !== "hal" && appPage && !appPage.hidden && PageViews && PageViews.hasPage(currentId)) {
      PageViews.renderPageView(appPage, halData, currentId, select, halWidgetFeed, halProgramSnapshot);
      if (typeof PageChrome !== "undefined" && PageChrome.refreshHalReadinessStrip) {
        PageChrome.refreshHalReadinessStrip(currentId, halWidgetFeed);
      }
    }
  });
  window.addEventListener("nr2:narratives-updated", () => {
    invalidateProgramCaches("narratives-updated");
    scheduleHalWidgetRefresh();
  });
}

DesktopBridge.whenReady(() => {
  DesktopBridge.installClipboardHandlers();
  if (typeof ImportReadinessGate !== "undefined" && ImportReadinessGate.installListeners) {
    ImportReadinessGate.installListeners();
  }
  if (typeof SideNotesOfficeFallback !== "undefined" && SideNotesOfficeFallback.install) {
    SideNotesOfficeFallback.install();
  }
  if (typeof NR2Boot !== "undefined" && !NR2Boot.ready) return;
  boot();
});
