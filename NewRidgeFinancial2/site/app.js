// NewRidgeFinancial 2.0 — mission-control pages.

const PAGES = [
  { id: "financial", label: "Financial dashboard", title: "Owner Financial Dashboard", image: "pages/01-financial-dashboard.png" },
  { id: "softdent", label: "SoftDent", title: "SoftDent", image: "pages/02-softdent.png" },
  { id: "quickbooks", label: "QuickBooks", title: "QuickBooks", image: "pages/03-quickbooks.png" },
  { id: "ar", label: "A/R & Collections", title: "A/R & Collections", image: "pages/04-ar-collections.png" },
  { id: "claims", label: "Claims Workbench", title: "Patient Claims Workbench", image: "pages/05-claims-workbench.png" },
  { id: "narratives", label: "Insurance Narratives", title: "Insurance Narratives", image: "pages/06-insurance-narratives.png" },
  { id: "documents", label: "Accounting Documents", title: "Accounting Documents", image: "pages/07-accounting-documents.png" },
  { id: "library", label: "Document Library", title: "Document Library", image: "pages/08-document-library.png" },
  { id: "hal", label: "HAL Command Center", title: "HAL Command Center", image: "pages/09-hal-command-center.png" },
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

const HOTSPOTS = [
  { key: "askHal", label: "Ask HAL", left: 15, top: 15, width: 45, height: 17 },
  { key: "sources", label: "Source intake", left: 8, top: 37, width: 25, height: 34 },
  { key: "reasoning", label: "Reasoning core", left: 36, top: 37, width: 28, height: 34 },
  { key: "workSurfaces", label: "Work surfaces", left: 67, top: 37, width: 27, height: 34 },
  { key: "firewall", label: "External firewall", left: 9, top: 76, width: 84, height: 15 },
  { key: "priorities", label: "Priorities", left: 66, top: 13, width: 28, height: 19 },
];

const nav = document.getElementById("nav");
const img = document.getElementById("pageImage");
const pageTitle = document.getElementById("pageTitle");
const hotspotLayer = document.getElementById("hotspotLayer");
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

try {
  const savedAudit = sessionStorage.getItem("halAudit");
  if (savedAudit) halAudit = JSON.parse(savedAudit);
} catch (error) {
  halAudit = [];
}

try {
  const savedChat = sessionStorage.getItem("halChatHistory");
  if (savedChat) halChatHistory = JSON.parse(savedChat);
} catch (error) {
  halChatHistory = [];
}

function saveChatHistory() {
  try {
    sessionStorage.setItem("halChatHistory", JSON.stringify(halChatHistory));
  } catch (error) {
    /* sessionStorage may be unavailable. */
  }
}

let halWorkSession = null;

function loadWorkSession() {
  try {
    const saved = sessionStorage.getItem("halWorkSession");
    if (saved) halWorkSession = JSON.parse(saved);
  } catch (error) {
    halWorkSession = null;
  }
}

function saveWorkSession() {
  try {
    if (halWorkSession) sessionStorage.setItem("halWorkSession", JSON.stringify(halWorkSession));
    else sessionStorage.removeItem("halWorkSession");
  } catch (error) {
    /* sessionStorage may be unavailable. */
  }
}

loadWorkSession();

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
    if (halEvidencePacket) sessionStorage.setItem("halEvidencePacket", JSON.stringify(halEvidencePacket));
    else sessionStorage.removeItem("halEvidencePacket");
  } catch (error) {
    /* sessionStorage may be unavailable. */
  }
}

loadEvidencePacket();

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
    if (halReadinessDiagnostics) sessionStorage.setItem("halDiagnostics", JSON.stringify(halReadinessDiagnostics));
    else sessionStorage.removeItem("halDiagnostics");
  } catch (error) {
    /* sessionStorage may be unavailable. */
  }
}

loadReadinessDiagnostics();

function collectReadinessRuntime() {
  const halPage = PAGES.find((page) => page.id === "hal");
  let sessionStorageOk = true;
  try {
    sessionStorage.setItem("halDiagProbe", "1");
    sessionStorage.removeItem("halDiagProbe");
  } catch (error) {
    sessionStorageOk = false;
  }
  return {
    halImage: halPage ? halPage.image : "",
    hotspotCount: HOTSPOTS.length,
    sessionStorageOk,
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
    if (halOperatorReport) sessionStorage.setItem("halOperatorReport", JSON.stringify(halOperatorReport));
    else sessionStorage.removeItem("halOperatorReport");
  } catch (error) {
    /* sessionStorage may be unavailable. */
  }
}

loadOperatorReport();

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

async function runModel(runtime, systemPrompt, userText, draftLabel) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), runtime.timeoutMs || 60000);
  const payload = {
    model: runtime.model,
    stream: false,
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
    const data = await response.json();
    const raw = data && data.message && data.message.content ? data.message.content : "";
    const text = HalCore.cleanModelText(raw);
    if (!text) throw new Error("empty model response");
    return text + "\n\n(" + draftLabel + " · read-only · verify before acting)";
  } finally {
    clearTimeout(timer);
  }
}

function callLocalModel(userText) {
  return runModel(localModelConfig(), HalCore.buildSystemPrompt(halData), userText, "Local 14B draft");
}

function callReasoningModel(userText) {
  return runModel(reasoningModelConfig(), HalCore.buildReasoningPrompt(halData), userText, "Local reasoning draft");
}

function callEscalationModel(userText) {
  return runModel(escalationModelConfig(), HalCore.buildEscalationPrompt(halData), userText, "Local escalation draft");
}

function routeHalCommand(rawQuery) {
  return HalCore.routeHalCommand(halData, halModels, PAGES, rawQuery);
}

function logAudit(query, intent) {
  halAudit.push({ time: new Date().toLocaleTimeString(), query, intent });
  try {
    sessionStorage.setItem("halAudit", JSON.stringify(halAudit));
  } catch (error) {
    /* sessionStorage may be unavailable. */
  }
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

async function handleHalSubmit(query) {
  const trimmed = String(query).trim();
  if (!trimmed) return;
  halChatHistory.push({ role: "user", text: trimmed, actions: [] });
  saveChatHistory();

  const result = routeHalCommand(trimmed);

  if (result.useSessionStart && result.sessionId) {
    startWorkSession(result.sessionId);
    halChatHistory.push({
      role: "hal",
      text: result.text + "\n\n" + workSessionStatusText(),
      lane: "session",
      actions: normalizeActions(result.actions),
    });
    logAudit(trimmed, result.intent);
    saveChatHistory();
    renderChatLog();
    renderAuditLog();
    if (currentDrawerKey) renderPanel(currentDrawerKey);
    return;
  }

  if (result.useSessionReset) {
    resetWorkSession();
    halChatHistory.push({ role: "hal", text: result.text, lane: "session", actions: [] });
    logAudit(trimmed, result.intent);
    saveChatHistory();
    renderChatLog();
    renderAuditLog();
    if (currentDrawerKey) renderPanel(currentDrawerKey);
    return;
  }

  if (result.useSessionShow) {
    const text = halWorkSession
      ? workSessionStatusText() + "\n\nUse the Work Session panel to mark checks complete or draft a handoff note."
      : "No active work session. Say \"Start claims review\" or use the Work Session panel.";
    halChatHistory.push({ role: "hal", text, lane: "session", actions: [] });
    logAudit(trimmed, result.intent);
    saveChatHistory();
    renderChatLog();
    renderAuditLog();
    return;
  }

  if (result.useSessionHandoff) {
    if (!halWorkSession) {
      halChatHistory.push({ role: "hal", text: "No active work session to draft a handoff note from.", lane: "session", actions: [] });
    } else {
      halWorkSession.handoffNote = HalCore.draftHandoffNote(halWorkSession, halData);
      saveWorkSession();
      halChatHistory.push({ role: "hal", text: halWorkSession.handoffNote, lane: "session", actions: [] });
    }
    logAudit(trimmed, result.intent);
    saveChatHistory();
    renderChatLog();
    renderAuditLog();
    if (currentDrawerKey) renderPanel(currentDrawerKey);
    return;
  }

  if (result.usePacketBuild) {
    if (!halWorkSession) {
      halChatHistory.push({
        role: "hal",
        text: "No active work session. Start a session first (for example, \"Start claims review\"), then build an evidence packet.",
        lane: "packet",
        actions: [],
      });
    } else {
      const packet = buildEvidencePacketFromSession();
      halChatHistory.push({
        role: "hal",
        text: packet ? packet.text : "Could not build evidence packet.",
        lane: "packet",
        actions: [],
      });
    }
    logAudit(trimmed, result.intent);
    saveChatHistory();
    renderChatLog();
    renderAuditLog();
    if (currentDrawerKey) renderPanel(currentDrawerKey);
    return;
  }

  if (result.usePacketShow) {
    const text = halEvidencePacket
      ? halEvidencePacket.text
      : "No evidence packet built yet. Start a work session and say \"Build evidence packet\".";
    halChatHistory.push({ role: "hal", text, lane: "packet", actions: [] });
    logAudit(trimmed, result.intent);
    saveChatHistory();
    renderChatLog();
    renderAuditLog();
    return;
  }

  if (result.usePacketClear) {
    clearEvidencePacket();
    halChatHistory.push({ role: "hal", text: result.text, lane: "packet", actions: [] });
    logAudit(trimmed, result.intent);
    saveChatHistory();
    renderChatLog();
    renderAuditLog();
    if (currentDrawerKey) renderPanel(currentDrawerKey);
    return;
  }

  if (result.useReadinessRun) {
    const report = runReadinessDiagnostics();
    halChatHistory.push({
      role: "hal",
      text: HalCore.formatReadinessSummary(report),
      lane: "readiness",
      actions: [],
    });
    logAudit(trimmed, result.intent);
    saveChatHistory();
    renderChatLog();
    renderAuditLog();
    if (currentDrawerKey) renderPanel(currentDrawerKey);
    return;
  }

  if (result.useReadinessGate) {
    if (!halReadinessDiagnostics) runReadinessDiagnostics();
    halChatHistory.push({ role: "hal", text: staffUseGateText(), lane: "readiness", actions: [] });
    logAudit(trimmed, result.intent);
    saveChatHistory();
    renderChatLog();
    renderAuditLog();
    if (currentDrawerKey) renderPanel(currentDrawerKey);
    return;
  }

  if (result.useReadinessShow) {
    const text = halReadinessDiagnostics
      ? HalCore.formatReadinessSummary(halReadinessDiagnostics)
      : "No diagnostics available yet. Say \"Run readiness check\" or use the Readiness panel.";
    halChatHistory.push({ role: "hal", text, lane: "readiness", actions: [] });
    logAudit(trimmed, result.intent);
    saveChatHistory();
    renderChatLog();
    renderAuditLog();
    return;
  }

  if (result.useReadinessClear) {
    clearReadinessDiagnostics();
    halChatHistory.push({ role: "hal", text: result.text, lane: "readiness", actions: [] });
    logAudit(trimmed, result.intent);
    saveChatHistory();
    renderChatLog();
    renderAuditLog();
    if (currentDrawerKey) renderPanel(currentDrawerKey);
    return;
  }

  if (result.useSmokeTest) {
    const report = runOperatorSmokeTest();
    halChatHistory.push({ role: "hal", text: HalCore.formatSmokeTestSummary(report), lane: "operator", actions: [] });
    logAudit(trimmed, result.intent);
    saveChatHistory();
    renderChatLog();
    renderAuditLog();
    if (currentDrawerKey) renderPanel(currentDrawerKey);
    return;
  }

  if (result.useHandoffSummary) {
    halChatHistory.push({ role: "hal", text: staffHandoffSummaryText(), lane: "operator", actions: [] });
    logAudit(trimmed, result.intent);
    saveChatHistory();
    renderChatLog();
    renderAuditLog();
    return;
  }

  if (result.useEscalation) {
    if (!escalationModelReady()) {
      halChatHistory.push({ role: "hal", text: offlineModelMessage("escalate30b"), lane: "escalate30b · offline", actions: [] });
      logAudit(trimmed, "escalation: offline");
      saveChatHistory();
      renderChatLog();
      renderAuditLog();
      return;
    }
    const em = escalationModelConfig();
    const placeholder = { role: "hal", text: "Escalating locally to " + (em.model || "escalation lane") + "…", lane: "escalate30b", actions: [] };
    halChatHistory.push(placeholder);
    logAudit(trimmed, "escalation: review");
    saveChatHistory();
    renderChatLog();
    renderAuditLog();
    try {
      placeholder.text = await callEscalationModel(trimmed);
    } catch (error) {
      placeholder.text = offlineModelMessage("escalate30b");
      placeholder.lane = "escalate30b · offline";
    }
    saveChatHistory();
    renderChatLog();
    return;
  }

  if (result.useReasoning) {
    if (!reasoningModelReady()) {
      halChatHistory.push({ role: "hal", text: offlineModelMessage("reason21b"), lane: "reason21b · offline", actions: [] });
      logAudit(trimmed, "reasoning: offline");
      saveChatHistory();
      renderChatLog();
      renderAuditLog();
      return;
    }
    const rm = reasoningModelConfig();
    const placeholder = { role: "hal", text: "Reasoning locally with " + (rm.model || "reasoning lane") + "…", lane: "reason21b", actions: [] };
    halChatHistory.push(placeholder);
    logAudit(trimmed, "reasoning: plan");
    saveChatHistory();
    renderChatLog();
    renderAuditLog();
    try {
      placeholder.text = await callReasoningModel(trimmed);
    } catch (error) {
      placeholder.text = offlineModelMessage("reason21b");
      placeholder.lane = "reason21b · offline";
    }
    saveChatHistory();
    renderChatLog();
    return;
  }

  if (result.useModel) {
    if (!localModelReady()) {
      halChatHistory.push({ role: "hal", text: offlineModelMessage("chat14b"), lane: "chat14b · offline", actions: [] });
      logAudit(trimmed, "model: offline");
      saveChatHistory();
      renderChatLog();
      renderAuditLog();
      return;
    }
    const lm = localModelConfig();
    const placeholder = { role: "hal", text: "Thinking locally with " + (lm.model || "14B") + "…", lane: "chat14b", actions: [] };
    halChatHistory.push(placeholder);
    logAudit(trimmed, "model: query");
    saveChatHistory();
    renderChatLog();
    renderAuditLog();
    try {
      placeholder.text = await callLocalModel(trimmed);
    } catch (error) {
      placeholder.text = offlineModelMessage("chat14b");
      placeholder.lane = "chat14b · offline";
    }
    saveChatHistory();
    renderChatLog();
    return;
  }

  halChatHistory.push({
    role: "hal",
    text: result.text,
    lane: result.lane || "local",
    actions: normalizeActions(result.actions),
  });
  logAudit(trimmed, result.intent);
  saveChatHistory();
  renderChatLog();
  renderAuditLog();
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

function renderHotspots(pageId) {
  hotspotLayer.innerHTML = "";
  hotspotLayer.classList.toggle("active", pageId === "hal");
  if (pageId !== "hal") return;

  for (const hotspot of HOTSPOTS) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "hotspot";
    button.setAttribute("aria-label", hotspot.label);
    button.style.left = `${hotspot.left}%`;
    button.style.top = `${hotspot.top}%`;
    button.style.width = `${hotspot.width}%`;
    button.style.height = `${hotspot.height}%`;
    button.addEventListener("click", () => openDrawer(hotspot.key));
    hotspotLayer.appendChild(button);
  }
}

function select(id) {
  const page = PAGES.find((p) => p.id === id) || PAGES[0];
  img.src = page.image;
  img.alt = page.title;
  pageTitle.textContent = page.title;
  renderHotspots(page.id);
  closeDrawer();
  for (const key of Object.keys(buttons)) {
    buttons[key].classList.toggle("active", key === page.id);
  }
  if (window.location.hash !== "#" + page.id) {
    window.location.hash = page.id;
  }
}

for (const page of PAGES) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.textContent = page.label;
  btn.addEventListener("click", () => select(page.id));
  nav.appendChild(btn);
  buttons[page.id] = btn;
}

drawerClose.addEventListener("click", closeDrawer);
document.addEventListener("click", (event) => {
  if (!currentDrawerKey) return;
  const panel = drawer.querySelector(".drawer__panel");
  if (panel && panel.contains(event.target)) return;
  if (event.target.closest && (event.target.closest(".hotspot") || event.target.closest("#nav"))) return;
  closeDrawer();
});
window.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeDrawer();
});
window.addEventListener("hashchange", () => {
  const id = window.location.hash.replace("#", "");
  if (id) select(id);
});

fetch("data/hal-manager.json", { cache: "no-store" })
  .then((response) => {
    if (!response.ok) throw new Error("HAL data unavailable");
    return response.json();
  })
  .then((data) => {
    halData = data;
    if (currentDrawerKey) renderPanel(currentDrawerKey);
  })
  .catch(() => {
    halData = FALLBACK_HAL;
  });

fetch("data/hal-models.json", { cache: "no-store" })
  .then((response) => {
    if (!response.ok) throw new Error("HAL models unavailable");
    return response.json();
  })
  .then((data) => {
    halModels = data;
    if (currentDrawerKey) renderPanel(currentDrawerKey);
  })
  .catch(() => {
    halModels = FALLBACK_MODELS;
  });

const initial = window.location.hash.replace("#", "") || PAGES[0].id;
select(initial);
