// NewRidgeFinancial 2.0 — mission-control pages.

const PAGES = [
  { id: "financial", label: "Financial dashboard", title: "Owner Financial Dashboard", icon: "⌁" },
  { id: "softdent", label: "SoftDent", title: "SoftDent", icon: "◫" },
  { id: "quickbooks", label: "QuickBooks", title: "QuickBooks", icon: "$" },
  { id: "ar", label: "A/R & Collections", title: "A/R & Collections", icon: "↻" },
  { id: "claims", label: "Claims Workbench", title: "Patient Claims Workbench", icon: "□" },
  { id: "narratives", label: "Insurance Narratives", title: "Insurance Narratives", icon: "✎" },
  { id: "documents", label: "Accounting Documents", title: "Accounting Documents", icon: "▤" },
  { id: "library", label: "Document Library", title: "Document Library", icon: "▣" },
  { id: "office-manager", label: "Office Manager", title: "Office Manager", icon: "◎" },
  { id: "hal", label: "HAL Command Center", title: "HAL Command Center", icon: "◇" },
];

const FALLBACK_HAL = {
  status: { title: "HAL Command Center", summary: "Local program manager.", posture: ["Local-only", "Read-only"] },
  askHal: { title: "Ask HAL", summary: "Local manager.", suggestions: ["Show priorities"], response: "I can navigate pages and explain status." },
  sources: { title: "Sources", summary: "Read-only.", items: [] },
  reasoning: { title: "Reasoning", summary: "Local lanes.", actions: [] },
  workSurfaces: { title: "Work surfaces", summary: "Open pages.", items: [] },
  firewall: { title: "Firewall", summary: "External actions blocked.", blocked: [], allowed: [], examples: [] },
  priorities: { title: "Priorities", items: [] },
  registry: [],
};

const FALLBACK_MODELS = { config: { mode: "offline" }, lanes: [] };

const sidebar = document.getElementById("sidebar");
let nav = document.getElementById("nav");
const pageTitle = document.getElementById("pageTitle");
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

function persistLocal(key, value) {
  DesktopBridge.storageSet(key, value).catch(() => {});
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
  persistLocal("halOfficeTasks", halOfficeTasks);
}

let halSideNotes = [];
let halSideNoteMonitor = null;
let halSideNoteMonitorTimer = null;
// Live SideNotesIM feed captured by the local watcher helper (routing only).
let halSideNotesInbox = null;
let halSideNotesAnnouncedIds = new Set();
// HAL manager dashboard widgets (derived from program snapshot).
let halWidgetFeed = null;
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
  programContextCache = null;
  programSnapshotCache = null;
  refreshSideNoteMonitor({ patchUi: true });
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
  const el = halPageRoot.querySelector(".hp-sidenotes-monitor");
  if (!el) return;
  el.outerHTML = HalPage.sideNotesMonitorHtml(halSideNotes, halSideNoteMonitor, halSideNotesInbox);
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
    await loadSideNotesInbox();
    await refreshHalWidgetFeed();
    refreshSideNoteMonitor({ patchUi: true });
  }, SIDENOTE_MONITOR_MS);
}

function stopSideNoteMonitor() {
  if (!halSideNoteMonitorTimer) return;
  clearInterval(halSideNoteMonitorTimer);
  halSideNoteMonitorTimer = null;
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
        await navigator.clipboard.writeText(halEvidencePacket.text);
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
    hotspotCount: 8,
    sessionStorageOk: DesktopBridge.hasDesktopApi(),
    activeSession: halWorkSession,
  };
}

function runReadinessDiagnostics() {
  halReadinessDiagnostics = HalCore.runReadinessChecks(halData, halModels, PAGES, collectReadinessRuntime());
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
let programSnapshotCache = null;
let programSnapshotAt = 0;
const PROGRAM_CONTEXT_TTL_MS = 60000;
const PROGRAM_SNAPSHOT_TTL_MS = 45000;

async function refreshHalWidgetFeed(snapshot) {
  if (!window.HalSkills) return halWidgetFeed;
  const snap = snapshot || (await loadProgramSnapshot());
  if (!snap) {
    halWidgetFeed = null;
    return null;
  }
  halWidgetFeed = HalSkills.buildWidgetFeed(snap);
  halData.runtime = Object.assign({}, halData.runtime || {}, { widgetFeed: halWidgetFeed });
  return halWidgetFeed;
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
    halWidgetFeed = HalSkills.buildWidgetFeed(snapshot);
    halData.runtime = Object.assign({}, halData.runtime || {}, { widgetFeed: halWidgetFeed });
    snapshot.widgets = halWidgetFeed;
  }
  return snapshot;
}

async function loadCachedProgramSnapshot() {
  const now = Date.now();
  if (!programSnapshotCache || now - programSnapshotAt > PROGRAM_SNAPSHOT_TTL_MS) {
    programSnapshotCache = await loadProgramSnapshot();
    programSnapshotAt = now;
  }
  return programSnapshotCache;
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
  halOperatorReport = HalCore.runOperatorSmokeTest(halData, halModels, PAGES, collectReadinessRuntime());
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
  const health = HalCore.deriveDrawerHealth(halData, halModels, PAGES, halReadinessDiagnostics);
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
  return HalCore.pageInfoMap(halData, PAGES);
}

function localModelConfig() {
  return HalCore.laneRuntime(halModels, "chat14b");
}

function reasoningModelConfig() {
  return HalCore.laneRuntime(halModels, "reason21b");
}

function escalationModelConfig() {
  return HalCore.laneRuntime(halModels, "escalate30b");
}

function localModelReady() {
  return HalCore.laneReady(halModels, "chat14b");
}

function reasoningModelReady() {
  return HalCore.laneReady(halModels, "reason21b");
}

function escalationModelReady() {
  return HalCore.laneReady(halModels, "escalate30b");
}

function offlineModelMessage(laneId) {
  const lane = HalCore.modelLanes(halModels).find((entry) => entry.id === laneId) || HalCore.modelLanes(halModels)[0];
  const name = lane && lane.name ? lane.name : "local chat lane";
  const model = lane && lane.model ? lane.model : "local model";
  return (
    "I could not reach the " +
    name +
    " (" +
    model +
    ") on this machine, so I can only answer from the local program registry right now. " +
    "Make sure the local model service is running, then try again."
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

async function runModel(runtime, systemPrompt, userText, draftLabel, onToken) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), runtime.timeoutMs || 60000);
  const wantStream = typeof onToken === "function";
  const payload = {
    model: runtime.model,
    stream: wantStream,
    messages: [
      { role: "system", content: systemPrompt },
      { role: "user", content: userText },
    ],
    options: { temperature: typeof runtime.temperature === "number" ? runtime.temperature : 0.2 },
  };
  if (typeof runtime.think === "boolean") payload.think = runtime.think;
  try {
    const response = await fetch(runtime.endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
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
      raw = data && data.message && data.message.content ? data.message.content : "";
    }

    const text = HalCore.cleanModelText(raw);
    if (!text) throw new Error("empty model response");
    return text + "\n\n(" + draftLabel + " · read-only · verify before acting)";
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
  return HalCore.routeHalCommand(halData, halModels, PAGES, rawQuery);
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

function renderChatLog() {
  const log = document.getElementById("halChatLog");
  if (!log) return;
  log.innerHTML = halChatHistory
    .map((message) => {
      const lane = message.lane ? `<span class="hal-msg__lane">${escapeHtml(message.lane)}</span>` : "";
      const actions = normalizeActions(message.actions)
        .map((action) => {
          if (action.type === "openPage") {
            return `<button class="hal-msg__action" type="button" data-open-page="${escapeHtml(action.page)}">${escapeHtml(action.label)}</button>`;
          }
          return "";
        })
        .join("");
      return `<div class="hal-msg hal-msg--${message.role === "user" ? "user" : "hal"}">
        <span class="hal-msg__who">${message.role === "user" ? "You" : "HAL"}${lane}</span>
        <div class="hal-msg__text">${escapeHtml(message.text)}</div>
        ${actions ? `<div class="hal-msg__actions">${actions}</div>` : ""}
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

function buildHalAgentCtx(extras) {
  return Object.assign({
    halData,
    halModels,
    pages: PAGES,
    halOfficeTasks,
    halWorkSession,
    halEvidencePacket,
    halReadinessDiagnostics,
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
    runModel,
    localModelReady,
    reasoningModelReady,
    escalationModelReady,
    offlineModelMessage,
    localModelConfig,
    reasoningModelConfig,
    escalationModelConfig,
    persistGet: (key) => DesktopBridge.storageGet(key),
    persistSet: (key, value) => persistLocal(key, value),
    getCurrentPage: () => window.location.hash.replace("#", "") || PAGES[0].id,
    clearProgramContextCache: () => {
      programContextCache = null;
      programSnapshotCache = null;
    },
    setHalWidgetFeed: (feed) => {
      halWidgetFeed = feed;
    },
    refreshSideNoteMonitor,
    addSideNote,
    addOfficeTask: (task) => {
      halOfficeTasks.unshift(task);
      saveOfficeTasks();
      programSnapshotCache = null;
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
  halChatHistory.push({ role: "user", text: trimmed, actions: [] });
  saveChatHistory();

  const preRoute = routeHalCommand(trimmed);
  const isModelLane = !!(preRoute.useModel || preRoute.useReasoning || preRoute.useEscalation);
  let placeholder = null;
  let streamRenderAt = 0;
  if (isModelLane && window.HalAgent) {
    const lane = preRoute.lane || "chat14b";
    const label = preRoute.useEscalation ? "Escalating" : preRoute.useReasoning ? "Reasoning" : "Thinking";
    placeholder = { role: "hal", text: label + " locally…", lane, actions: [] };
    halChatHistory.push(placeholder);
    saveChatHistory();
    // Show the placeholder on both surfaces and suppress the typewriter so live
    // streamed tokens are written directly instead of being re-animated.
    halTypeSig = halChatHistory.length + ":" + placeholder.text.length;
    renderChatLog();
    renderHalScreen();
  }

  // Live token stream → write straight into the visible HAL bubbles, throttled.
  const onToken = placeholder
    ? (partial) => {
        if (!partial) return;
        placeholder.text = partial;
        const now = Date.now();
        if (now - streamRenderAt < 60) return;
        streamRenderAt = now;
        renderChatLog();
        setInlineHalStreamingText(partial);
      }
    : undefined;

  let outcome = null;
  if (window.HalAgent) {
    outcome = await HalAgent.processQuery(trimmed, buildHalAgentCtx(onToken ? { onToken } : null));
  } else {
    outcome = await HalRouteExec.execute(preRoute, trimmed, {}, buildHalAgentCtx());
  }
  if (!outcome) return;

  if (placeholder) {
    placeholder.text = outcome.text;
    placeholder.lane = outcome.lane || placeholder.lane;
    placeholder.actions = normalizeActions(outcome.actions);
    // We already showed the streamed text; stop the typewriter from replaying it.
    halTypeSig = halChatHistory.length + ":" + String(outcome.text).length;
  } else {
    halChatHistory.push({
      role: "hal",
      text: outcome.text,
      lane: outcome.lane || "local",
      actions: normalizeActions(outcome.actions),
    });
  }
  logAudit(trimmed, outcome.intent);
  saveChatHistory();
  renderChatLog();
  renderAuditLog();
  if (outcome.refreshHal) renderHalScreen();
  if (outcome.refreshPanel && currentDrawerKey) renderPanel(currentDrawerKey);
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
      logAudit("Open " + button.dataset.openPage, "navigate: drawer");
      closeDrawer();
      select(button.dataset.openPage);
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

function sourceHealthCards(items) {
  if (!items || items.length === 0) return "";
  return `<div class="drawer-grid">${items
    .map((item) => {
      const warn = item.warning ? `<p class="drawer-warn">${escapeHtml(item.warning)}</p>` : "";
      const checklist = (item.checklist || [])
        .map((c) => `<li>${escapeHtml(c)}</li>`)
        .join("");
      const openBtn = item.target
        ? `<button class="drawer-action drawer-action--sm" type="button" data-open-page="${escapeHtml(item.target)}">Open ${escapeHtml(item.label)}</button>`
        : "";
      return `<div class="drawer-card drawer-card--source">
        <strong>${escapeHtml(item.label)}</strong>
        <span class="status-chip">${escapeHtml(item.status)}</span>
        <p>${escapeHtml(item.detail)}</p>
        ${item.freshness ? `<p class="drawer-meta">Freshness: ${escapeHtml(item.freshness)}</p>` : ""}
        ${item.syncState ? `<p class="drawer-meta">Sync: ${escapeHtml(item.syncState)}</p>` : ""}
        ${warn}
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
      return `<div class="drawer-card drawer-card--surface">
        <strong>${escapeHtml(item.label)}</strong>
        <p>${escapeHtml(item.detail)}</p>
        ${reg ? `<p class="drawer-meta">Safety: ${escapeHtml(reg.safety)} · ${escapeHtml(reg.state)}</p>` : ""}
        ${reg ? `<p class="drawer-meta">Next: ${escapeHtml(reg.nextAction)}</p>` : ""}
        ${blocked ? `<div>${blocked}</div>` : ""}
        <div class="drawer-card__actions">
          <button class="drawer-action drawer-action--sm" type="button" data-open-page="${escapeHtml(item.target)}">Open page</button>
          <button class="drawer-action drawer-action--sm" type="button" data-hal-command="Explain ${escapeHtml(item.label)}">Explain</button>
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
      <p class="drawer-meta">Type a proposed action. HAL checks the firewall before any model call.</p>
      <form class="hal-chat__form" id="firewallSimForm" autocomplete="off">
        <input id="firewallSimInput" class="hal-chat__input" type="text" placeholder="e.g. Submit the denied claim" aria-label="Test firewall" />
        <button class="hal-chat__send" type="submit">Test</button>
      </form>
      <div class="drawer-card" id="firewallSimResult">Enter an action above to test.</div>
      <div class="hal-suggest">${examples}</div>
    </div>`;
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
  return staticHtml + groupHtml + workSessionPanelHtml() + evidencePacketPanelHtml();
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
    drawerContent.innerHTML = `<p>${escapeHtml(data.summary)}</p>${sourceHealthCards(data.items)}`;
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
      const verdict = HalCore.firewallVerdict(input.value, data);
      result.innerHTML = `<strong>${verdict.allowed ? "Allowed" : "Blocked"}</strong><p>${escapeHtml(verdict.text)}</p>`;
      logAudit(input.value, verdict.intent);
      renderAuditLog();
    });
    drawerContent.querySelectorAll("[data-firewall-test]").forEach((button) => {
      button.addEventListener("click", () => {
        input.value = button.dataset.firewallTest;
        const verdict = HalCore.firewallVerdict(input.value, data);
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
  // Only type a given HAL message once; unrelated re-renders keep the same
  // signature and are skipped so the text does not replay.
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
    return;
  }
  p.textContent = "";
  p.classList.add("hp-typing");
  const step = Math.max(1, Math.ceil(full.length / 140));
  const typeDelayMs = 245; // 3.4x slower than the previous 72ms cadence.
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
      if (window.HalVoice && full.length <= 320) {
        HalVoice.speakHalReply(full);
      }
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
    pages: PAGES,
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
    halAskLoading: false,
    halInlineFirewallResult: null,
    halSideNotes,
    halSideNoteMonitor: halSideNoteMonitor || (window.HalSkills ? HalSkills.buildSideNoteMonitor(halSideNotes) : null),
    halSideNotesInbox,
    halWidgetFeed,
    halStressTest,
    halAgentHealth: window.HalAgent ? HalAgent.getHealth() : null,
  });
  typewriteLastHalMessage();
}

function renderSidebar(activeId) {
  if (!sidebar || !window.UI) return;
  sidebar.innerHTML = UI.Sidebar({
    activeId,
    nav: PAGES.map((page) => ({
      id: page.id,
      label: page.label,
      icon: page.icon,
    })),
    brand: "New Ridge Family Financial",
    kicker: "Financial OS",
    user: {
      initials: "NR",
      name: "New Ridge Owner",
      role: "Administrator",
    },
    status: "All systems operational",
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
  const page = PAGES.find((p) => p.id === id) || PAGES[0];
  const isHal = page.id === "hal" && !PageViews.hasPage(page.id);
  if (halPage) halPage.hidden = !isHal;
  if (appPage) {
    appPage.hidden = isHal;
    if (!isHal && PageViews.hasPage(page.id)) {
      PageViews.renderPageView(appPage, halData, page.id, select);
    }
  }
  pageTitle.textContent = page.title;
  renderSidebar(page.id);
  if (isHal) renderHalScreen();
  closeDrawer();
  if (window.location.hash !== "#" + page.id) {
    window.location.hash = page.id;
  }
}

renderSidebar(window.location.hash.replace("#", "") || PAGES[0].id);

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
    }
  });

  halPage.addEventListener("click", async (event) => {
    const drawerBtn = event.target.closest("[data-hal-drawer]");
    if (drawerBtn) {
      openDrawer(drawerBtn.getAttribute("data-hal-drawer"));
      return;
    }
    const suggest = event.target.closest("[data-hal-suggest]");
    if (suggest) {
      await handleHalSubmit(suggest.getAttribute("data-hal-suggest"));
      renderHalScreen();
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
    const widgetNav = event.target.closest("[data-hal-widget-nav]");
    if (widgetNav) {
      const target = widgetNav.getAttribute("data-hal-widget-nav");
      if (target) select(target);
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
      await handleHalSubmit(cmd.getAttribute("data-hal-cmd"));
      renderHalScreen();
    }
  });
}

if (appPage) {
  appPage.addEventListener("click", (event) => {
    const navBtn = event.target.closest("[data-pv-nav]");
    if (navBtn) select(navBtn.getAttribute("data-pv-nav"));
  });
}

document.addEventListener("click", (event) => {
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
  if (event.key === "Escape") closeDrawer();
});
window.addEventListener("hashchange", () => {
  const id = window.location.hash.replace("#", "");
  if (id) select(id);
});

async function loadPersistedState() {
  halAudit = (await DesktopBridge.storageGet("halAudit")) || [];
  halChatHistory = (await DesktopBridge.storageGet("halChatHistory")) || [];
  halWorkSession = (await DesktopBridge.storageGet("halWorkSession")) || null;
  halEvidencePacket = (await DesktopBridge.storageGet("halEvidencePacket")) || null;
  halReadinessDiagnostics = (await DesktopBridge.storageGet("halDiagnostics")) || null;
  halOperatorReport = (await DesktopBridge.storageGet("halOperatorReport")) || null;
  halOfficeTasks = (await DesktopBridge.storageGet("halOfficeTasks")) || [];
  halSideNotes = (await DesktopBridge.storageGet("halSideNotes")) || [];
  halSideNoteMonitor = (await DesktopBridge.storageGet("halSideNoteMonitor")) || null;
  refreshSideNoteMonitor();
}

async function boot() {
  await loadPersistedState();
  try {
    halData = await DesktopBridge.readDataFile("hal-manager.json");
  } catch {
    halData = FALLBACK_HAL;
  }
  try {
    halModels = await DesktopBridge.readDataFile("hal-models.json");
  } catch {
    halModels = FALLBACK_MODELS;
  }
  await refreshHalWidgetFeed();
  if (window.HalAgent) await HalAgent.loadMemory(buildHalAgentCtx());
  // Start HAL's sidenote watch app-wide so monitoring continues even when the
  // HAL panel is not the visible page. (Frontend-only: stops when the app is
  // closed; HAL re-checks persisted notes on the next launch.)
  startSideNoteMonitor();
  const initial = window.location.hash.replace("#", "") || PAGES[0].id;
  select(initial);
}

// Pick up sidenote edits made in another tab/window of the app (browser dev
// fallback uses sessionStorage which is per-tab, so this mainly helps when a
// shared storage backend fires `storage` events). HAL refreshes its monitor
// without needing its panel on screen.
if (typeof window !== "undefined") {
  window.addEventListener("storage", async (event) => {
    if (event && event.key && event.key !== "halSideNotes") return;
    halSideNotes = (await DesktopBridge.storageGet("halSideNotes")) || halSideNotes;
    programContextCache = null;
    await refreshHalWidgetFeed();
    refreshSideNoteMonitor({ patchUi: true });
  });
}

DesktopBridge.whenReady(() => {
  boot();
});
