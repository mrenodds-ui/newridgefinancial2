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
  status: {
    title: "HAL Command Center",
    summary: "Local program manager for NewRidgeFinancial 2.0.",
    posture: ["Local-only", "Read-only", "Human review required", "Not submitted"],
    modelLanes: [
      { name: "14B chat lane", role: "Staff-facing conversation", state: "Planned" },
      { name: "21B reasoning lane", role: "Program review and prioritization", state: "Planned" },
      { name: "30B escalation lane", role: "Second-opinion review", state: "Planned" },
    ],
  },
  askHal: {
    title: "Ask HAL",
    summary: "HAL is currently operating as a local program manager.",
    suggestions: ["Show priorities", "Open claims", "Review source health"],
    response: "I can navigate pages, explain local status, and keep work inside the read-only boundary.",
  },
  sources: { title: "Read-only source intake", summary: "Source pages are read-only.", items: [] },
  reasoning: { title: "Local reasoning core", summary: "Organizes work into Ready, Needs review, and Blocked lanes.", lanes: [] },
  workSurfaces: { title: "Staff work surfaces", summary: "Open and explain each program surface.", items: [] },
  firewall: { title: "External action firewall", summary: "External actions are blocked by design.", blocked: [], allowed: [] },
  priorities: { title: "Today’s operator priorities", items: [] },
  registry: [
    { id: "financial", name: "Financial Dashboard", purpose: "Owner-level financial view.", safety: "Read-only view", state: "Ready", nextAction: "Review production and collections.", blocked: [], related: [] },
    { id: "claims", name: "Claims Workbench", purpose: "Claim review lanes.", safety: "Review-only", state: "Needs review", nextAction: "Work the Needs Review lane.", blocked: [], related: [] },
    { id: "hal", name: "HAL Command Center", purpose: "Local program manager.", safety: "Local manager", state: "Ready", nextAction: "Ask HAL to open a page or show priorities.", blocked: [], related: [] },
  ],
};

const FALLBACK_MODELS = {
  config: { mode: "offline", localFirst: true, externalCallsEnabled: false, activeLane: null },
  lanes: [
    { id: "chat14b", name: "14B chat lane", model: "queen3:14b", role: "Staff-facing conversation", state: "Offline", willAllow: ["Explain pages in plain language", "Summarize local status"], stillBlocked: ["No external actions", "No data writeback"] },
    { id: "reason21b", name: "21B reasoning lane", model: "planned", role: "Program review and prioritization", state: "Planned", willAllow: ["Prioritize work across pages"], stillBlocked: ["No external actions"] },
    { id: "escalate30b", name: "30B escalation lane", model: "planned", role: "Second-opinion review", state: "Planned", willAllow: ["Second-opinion review"], stillBlocked: ["No external actions"] },
  ],
};

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

// Ask HAL local manager: chat transcript + session audit log (local-only, no AI model).
let halChatHistory = [];
let halAudit = [];
try {
  const savedAudit = sessionStorage.getItem("halAudit");
  if (savedAudit) halAudit = JSON.parse(savedAudit);
} catch (error) {
  halAudit = [];
}

// External-action verbs always stop at the firewall and require human review.
// Includes common -ing/-s forms so "submitting", "emailing", etc. are also caught.
const BLOCKED_RE = /\b(submit|submits|submitting|send|sends|sending|email|emails|emailing|e-?mail|fax|faxes|faxing|upload|uploads|uploading|transmit|transmits|transmitting|pay|paying|approve|approves|approving|deny|denies|denying|delete|deletes|deleting|remove|removes|removing|writeback|write back|dispatch|dispatches|dispatching|mail|mailing)\b/;

const PAGE_SYNONYMS = {
  financial: ["financial dashboard", "financial", "dashboard", "ebitda", "owner", "production", "payer mix", "provider"],
  softdent: ["softdent", "soft dent", "practice management"],
  quickbooks: ["quickbooks", "quick books", "p&l", "profit and loss", "expenses"],
  ar: ["a/r", "accounts receivable", "receivable", "collections", "aging", "follow-up", "follow up"],
  claims: ["claims workbench", "claims", "claim", "workbench", "denied"],
  narratives: ["narratives", "narrative", "insurance narrative"],
  documents: ["accounting documents", "document intake", "posting queue", "extraction"],
  library: ["document library", "library", "repository"],
  hal: ["hal", "command center", "yourself"],
};

function pageInfoMap() {
  const map = {};
  const items = (halData.workSurfaces && halData.workSurfaces.items) || [];
  for (const item of items) map[item.target] = { label: item.label, detail: item.detail };
  for (const page of PAGES) if (!map[page.id]) map[page.id] = { label: page.label, detail: page.title };
  return map;
}

function registryList() {
  return (halData.registry && halData.registry.length ? halData.registry : FALLBACK_HAL.registry) || [];
}

function registryById(id) {
  return registryList().find((entry) => entry.id === id) || null;
}

function modelConfig() {
  return (halModels && halModels.config) || FALLBACK_MODELS.config;
}

function modelLanes() {
  return (halModels && halModels.lanes && halModels.lanes.length ? halModels.lanes : FALLBACK_MODELS.lanes) || [];
}

function localModelConfig() {
  const config = modelConfig();
  return config && config.localModel ? config.localModel : null;
}

function reasoningModelConfig() {
  const config = modelConfig();
  return config && config.reasoningModel ? config.reasoningModel : null;
}

function escalationModelConfig() {
  const config = modelConfig();
  return config && config.escalationModel ? config.escalationModel : null;
}

function runtimeReady(runtime) {
  const config = modelConfig();
  return config.mode === "online" && runtime && runtime.enabled === true && !!runtime.endpoint && !!runtime.model;
}

function localModelReady() {
  return runtimeReady(localModelConfig());
}

function reasoningModelReady() {
  return runtimeReady(reasoningModelConfig());
}

function escalationModelReady() {
  return runtimeReady(escalationModelConfig());
}

// Message shown when a local lane is not reachable or not enabled.
function offlineModelMessage(laneId) {
  const lane = modelLanes().find((entry) => entry.id === laneId) || modelLanes().find((entry) => entry.id === "chat14b");
  const name = lane && lane.name ? lane.name : "local chat lane";
  const model = lane && lane.model ? lane.model : "queen3:14b";
  return (
    "I could not reach the " +
    name +
    " (" +
    model +
    ") on this machine, so I can only answer from the local program registry right now. " +
    "Make sure the local model service is running, then try again."
  );
}

function registryAsText() {
  return registryList()
    .map((entry) => `- ${entry.name} [${entry.state}; ${entry.safety}]: ${entry.purpose} Next: ${entry.nextAction}`)
    .join("\n");
}

// Read-only system grounding for the local 14B chat lane. The model drafts text only.
function buildSystemPrompt() {
  const firewall = halData.firewall || FALLBACK_HAL.firewall;
  return [
    "You are HAL, the local read-only program manager for NewRidgeFinancial 2.0, a dental-practice financial program.",
    "Answer briefly and only about this program and its pages. If you are unsure, say so.",
    "You are read-only. You never submit, email, fax, upload, post, or write back. A human performs any external step.",
    "Blocked external actions: " + (firewall.blocked || []).join(", ") + ".",
    "If the user asks for an external action, refuse and say it needs human review.",
    "Program pages and current status:",
    registryAsText(),
  ].join("\n");
}

// Read-only grounding for the reasoning lane: prioritize across program state.
function buildReasoningPrompt() {
  const firewall = halData.firewall || FALLBACK_HAL.firewall;
  const priorities = (halData.priorities && halData.priorities.items) || [];
  return [
    "You are HAL's reasoning lane for NewRidgeFinancial 2.0, a dental-practice financial program.",
    "Produce a short, structured, prioritized plan based only on the local program state below.",
    "Order work by readiness and risk: handle Needs Review and Blocked items carefully, and never advance payer-facing work without human review.",
    "You are read-only. You never submit, email, fax, upload, post, or write back. A human performs any external step.",
    "Blocked external actions: " + (firewall.blocked || []).join(", ") + ".",
    "Program pages and current status:",
    registryAsText(),
    "Known operator priorities:",
    priorities.map((item, index) => `${index + 1}. ${item}`).join("\n"),
    "Respond with a brief numbered plan. Keep it under 8 steps.",
  ].join("\n");
}

// Read-only grounding for the escalation lane: careful second-opinion review.
function buildEscalationPrompt() {
  const firewall = halData.firewall || FALLBACK_HAL.firewall;
  return [
    "You are HAL's escalation lane for NewRidgeFinancial 2.0, a dental-practice financial program.",
    "Give a careful second-opinion review for a complex or high-risk question.",
    "Be conservative: call out risks, assumptions, and exactly what a human must verify before acting.",
    "You are read-only. You never submit, email, fax, upload, post, or write back. A human performs any external step.",
    "Blocked external actions: " + (firewall.blocked || []).join(", ") + ".",
    "Program pages and current status:",
    registryAsText(),
    "Respond with: a short risk assessment, then a numbered list of what a human should verify.",
  ].join("\n");
}

// Strip optional <think> reasoning blocks some local models emit.
function cleanModelText(text) {
  return String(text)
    .replace(/<think>[\s\S]*?<\/think>/gi, "")
    .replace(/<\/?think>/gi, "")
    .trim();
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
    const text = cleanModelText(raw);
    if (!text) throw new Error("empty model response");
    return text + "\n\n(" + draftLabel + " · read-only · verify before acting)";
  } finally {
    clearTimeout(timer);
  }
}

function callLocalModel(userText) {
  return runModel(localModelConfig(), buildSystemPrompt(), userText, "Local 14B draft");
}

function callReasoningModel(userText) {
  return runModel(reasoningModelConfig(), buildReasoningPrompt(), userText, "Local reasoning draft");
}

function callEscalationModel(userText) {
  return runModel(escalationModelConfig(), buildEscalationPrompt(), userText, "Local escalation draft");
}

function findPage(query) {
  let best = null;
  let bestLen = 0;
  for (const [id, synonyms] of Object.entries(PAGE_SYNONYMS)) {
    for (const synonym of synonyms) {
      if (query.includes(synonym) && synonym.length > bestLen) {
        best = id;
        bestLen = synonym.length;
      }
    }
  }
  return best;
}

function routeHalCommand(rawQuery) {
  const query = rawQuery.toLowerCase().trim();
  const firewall = halData.firewall || FALLBACK_HAL.firewall;

  if (BLOCKED_RE.test(query)) {
    return {
      intent: "blocked: firewall",
      text:
        "That is an external action, so it stops at the firewall and needs human review. " +
        firewall.summary +
        " I can open the right page and prepare review notes, but a person has to take the external step.",
      actions: [],
    };
  }

  if (/\b(help|what can you do|capabilit|how do you work|what do you do)\b/.test(query)) {
    return {
      intent: "help",
      text:
        "I am the local program manager. I can open any program page, explain what each page is for, show today's priorities, report read-only source health, and explain the external-action firewall. I do not submit, send, or change anything.",
      actions: [],
    };
  }

  const wantsExplain = /\b(explain|what is|what's|whats|what does|tell me about|describe|purpose of)\b/.test(query);

  if (/second opinion|escalat|double[\s-]?check|high[\s-]?risk|complex case|deep review|review carefully|sanity check|scrutin/.test(query)) {
    return { intent: "escalation", text: "", useEscalation: true, prompt: rawQuery, actions: [] };
  }

  if (/prioriti[sz]e|make a plan|draft a plan|\bplan (my|for|the)\b|analy[sz]e|reason through|think through|recommend|\bstrategy\b|focus first|where (do|should) (i|we) start/.test(query)) {
    return { intent: "reasoning", text: "", useReasoning: true, prompt: rawQuery, actions: [] };
  }

  if (/\bpriorit|needs attention|attention today|what needs|to-?do|\btoday\b/.test(query)) {
    const items = (halData.priorities && halData.priorities.items) || [];
    const list = items.map((item, index) => `${index + 1}. ${item}`).join("\n");
    return { intent: "priorities", text: `Today's operator priorities:\n${list}`, actions: [] };
  }

  if (/\b(firewall|external action|boundary|guardrail|safety|are you allowed)\b/.test(query)) {
    return {
      intent: "firewall",
      text: `${firewall.summary}\nBlocked: ${firewall.blocked.join(", ")}.\nAllowed: ${firewall.allowed.join(", ")}.`,
      actions: [],
    };
  }

  if (/\b(source|softdent|quickbooks|freshness|sync|intake)\b/.test(query) && !wantsExplain) {
    const items = (halData.sources && halData.sources.items) || [];
    const list = items.map((item) => `- ${item.label} - ${item.status}: ${item.detail}`).join("\n");
    return { intent: "sources", text: `Read-only source intake status:\n${list}`, actions: [] };
  }

  if (/\bmodels?\b|\b14b\b|\b21b\b|\b30b\b|\bllm\b|\bai lane\b|which model|are you connected|connected to a model/.test(query)) {
    const lanes = modelLanes();
    const list = lanes
      .map(
        (lane) =>
          `- ${lane.name} (${lane.model}) — ${lane.state}\n   Will allow: ${(lane.willAllow || []).join(", ")}\n   Still blocked: ${(lane.stillBlocked || []).join(", ")}`,
      )
      .join("\n");
    return {
      intent: "model lanes",
      text: `Model lanes are local-only and none are connected yet:\n${list}`,
      actions: [],
    };
  }

  if (/\bready\b/.test(query)) {
    const ready = registryList().filter((entry) => /ready/i.test(entry.state));
    const list = ready.map((entry) => `- ${entry.name}: ${entry.nextAction}`).join("\n");
    return {
      intent: "registry: ready",
      text: ready.length ? `Ready to work now:\n${list}` : "Nothing is marked ready right now.",
      actions: [],
    };
  }

  if (/\bblocked\b|needs review|waiting on/.test(query)) {
    const waiting = registryList().filter((entry) => /blocked|needs review/i.test(entry.state));
    const list = waiting.map((entry) => `- ${entry.name} (${entry.state}): ${entry.nextAction}`).join("\n");
    return {
      intent: "registry: blocked",
      text: waiting.length ? `Waiting or needs review:\n${list}` : "Nothing is blocked right now.",
      actions: [],
    };
  }

  if (/read[\s-]?only|readonly/.test(query)) {
    const readOnly = registryList().filter((entry) => /read[\s-]?only|indexed|reference|review-only|local review|manager/i.test(entry.safety));
    const list = readOnly.map((entry) => `- ${entry.name}: ${entry.safety}`).join("\n");
    return { intent: "registry: read-only", text: `Read-only and review-only areas:\n${list}`, actions: [] };
  }

  if (/next (step|action)|do next|what should/.test(query)) {
    const list = registryList().map((entry) => `- ${entry.name}: ${entry.nextAction}`).join("\n");
    return { intent: "registry: next actions", text: `Suggested next staff actions:\n${list}`, actions: [] };
  }

  const pageId = findPage(query);
  if (pageId) {
    const info = pageInfoMap()[pageId];
    const reg = registryById(pageId);
    const status = reg ? `\nStatus: ${reg.state}. Safety: ${reg.safety}. Next: ${reg.nextAction}` : "";
    if (pageId === "hal" && !wantsExplain) {
      const halStatus = halData.status || FALLBACK_HAL.status;
      return { intent: "status", text: halStatus.summary + status, actions: [] };
    }
    if (wantsExplain) {
      return {
        intent: "explain: " + pageId,
        text: `${info.label}: ${info.detail}${status}`,
        actions: pageId === "hal" ? [] : [{ label: "Open " + info.label, page: pageId }],
      };
    }
    return {
      intent: "navigate: " + pageId,
      text: `I can open ${info.label}. ${info.detail}${status}`,
      actions: [{ label: "Open " + info.label, page: pageId }],
    };
  }

  return {
    intent: "model: query",
    text: "",
    useModel: true,
    prompt: rawQuery,
    actions: [],
  };
}

function logAudit(query, intent) {
  halAudit.push({ time: new Date().toLocaleTimeString(), query, intent });
  try {
    sessionStorage.setItem("halAudit", JSON.stringify(halAudit));
  } catch (error) {
    /* sessionStorage may be unavailable; audit stays in memory. */
  }
}

function renderChatLog() {
  const log = document.getElementById("halChatLog");
  if (!log) return;
  log.innerHTML = halChatHistory
    .map((message) => {
      const actions = (message.actions || [])
        .map(
          (action) =>
            `<button class="hal-msg__action" type="button" data-open-page="${escapeHtml(action.page)}">${escapeHtml(
              action.label,
            )}</button>`,
        )
        .join("");
      return `<div class="hal-msg hal-msg--${message.role === "user" ? "user" : "hal"}">
        <span class="hal-msg__who">${message.role === "user" ? "You" : "HAL"}</span>
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
        `<div class="hal-audit__row"><span>${escapeHtml(entry.time)}</span><span>${escapeHtml(
          entry.intent,
        )}</span><span>${escapeHtml(entry.query)}</span></div>`,
    )
    .join("");
}

async function handleHalSubmit(query) {
  const trimmed = String(query).trim();
  if (!trimmed) return;
  halChatHistory.push({ role: "user", text: trimmed, actions: [] });

  const result = routeHalCommand(trimmed);

  if (result.useEscalation) {
    if (!escalationModelReady()) {
      halChatHistory.push({ role: "hal", text: offlineModelMessage("escalate30b"), actions: [] });
      logAudit(trimmed, "escalation: offline");
      renderChatLog();
      renderAuditLog();
      return;
    }
    const em = escalationModelConfig();
    const placeholder = { role: "hal", text: "Escalating locally to " + (em.model || "escalation lane") + "…", actions: [] };
    halChatHistory.push(placeholder);
    logAudit(trimmed, "escalation: review");
    renderChatLog();
    renderAuditLog();
    try {
      placeholder.text = await callEscalationModel(trimmed);
    } catch (error) {
      placeholder.text = offlineModelMessage("escalate30b");
    }
    renderChatLog();
    return;
  }

  if (result.useReasoning) {
    if (!reasoningModelReady()) {
      halChatHistory.push({ role: "hal", text: offlineModelMessage("reason21b"), actions: [] });
      logAudit(trimmed, "reasoning: offline");
      renderChatLog();
      renderAuditLog();
      return;
    }
    const rm = reasoningModelConfig();
    const placeholder = { role: "hal", text: "Reasoning locally with " + (rm.model || "reasoning lane") + "…", actions: [] };
    halChatHistory.push(placeholder);
    logAudit(trimmed, "reasoning: plan");
    renderChatLog();
    renderAuditLog();
    try {
      placeholder.text = await callReasoningModel(trimmed);
    } catch (error) {
      placeholder.text = offlineModelMessage("reason21b");
    }
    renderChatLog();
    return;
  }

  if (result.useModel) {
    if (!localModelReady()) {
      halChatHistory.push({ role: "hal", text: offlineModelMessage("chat14b"), actions: [] });
      logAudit(trimmed, "model: offline");
      renderChatLog();
      renderAuditLog();
      return;
    }
    const lm = localModelConfig();
    const placeholder = { role: "hal", text: "Thinking locally with " + (lm.model || "14B") + "…", actions: [] };
    halChatHistory.push(placeholder);
    logAudit(trimmed, "model: query");
    renderChatLog();
    renderAuditLog();
    try {
      placeholder.text = await callLocalModel(trimmed);
    } catch (error) {
      placeholder.text = offlineModelMessage("chat14b");
    }
    renderChatLog();
    return;
  }

  halChatHistory.push({ role: "hal", text: result.text, actions: result.actions || [] });
  logAudit(trimmed, result.intent);
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

function cards(items) {
  if (!items || items.length === 0) return "";
  return `<div class="drawer-grid">${items
    .map(
      (item) => `<div class="drawer-card"><strong>${escapeHtml(item.label || item.name)}</strong>${escapeHtml(
        item.detail || item.role || item.state || "",
      )}</div>`,
    )
    .join("")}</div>`;
}

function chips(items, blocked = false) {
  if (!items || items.length === 0) return "";
  return `<div>${items
    .map((item) => `<span class="status-chip${blocked ? " status-chip--blocked" : ""}">${escapeHtml(item)}</span>`)
    .join("")}</div>`;
}

function numbered(items) {
  if (!items || items.length === 0) return "";
  return `<div class="drawer-grid">${items.map((item) => `<div class="drawer-card">${escapeHtml(item)}</div>`).join("")}</div>`;
}

function surfaceActions(items) {
  if (!items || items.length === 0) return "";
  return `<div class="drawer-grid">${items
    .map(
      (item) =>
        `<button class="drawer-action" type="button" data-target-page="${escapeHtml(item.target)}"><strong>${escapeHtml(
          item.label,
        )}</strong>${escapeHtml(item.detail)}</button>`,
    )
    .join("")}</div>`;
}

function renderPanel(key) {
  const data = halData[key] || halData.status;
  drawerTitle.textContent = data.title || "HAL Command Center";

  if (key === "askHal") {
    if (halChatHistory.length === 0) {
      halChatHistory.push({ role: "hal", text: data.response, actions: [] });
    }
    drawerContent.innerHTML = `
      <p>${escapeHtml(data.summary)}</p>
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
    `;
    const suggest = document.getElementById("halSuggest");
    (data.suggestions || []).forEach((text) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "status-chip hal-suggest__chip";
      chip.textContent = text;
      chip.addEventListener("click", () => handleHalSubmit(text));
      suggest.appendChild(chip);
    });
    const form = document.getElementById("halChatForm");
    const input = document.getElementById("halChatInput");
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const value = input.value;
      input.value = "";
      handleHalSubmit(value);
    });
    renderChatLog();
    renderAuditLog();
    return;
  }

  if (key === "status") {
    drawerContent.innerHTML = `
      <p>${escapeHtml(data.summary)}</p>
      ${chips(data.posture)}
      ${cards(data.modelLanes)}
    `;
    return;
  }

  if (key === "reasoning") {
    drawerContent.innerHTML = `
      <p>${escapeHtml(data.summary)}</p>
      ${cards(data.lanes)}
    `;
    return;
  }

  if (key === "workSurfaces") {
    drawerContent.innerHTML = `
      <p>${escapeHtml(data.summary)}</p>
      ${surfaceActions(data.items)}
    `;
    drawerContent.querySelectorAll("[data-target-page]").forEach((button) => {
      button.addEventListener("click", () => {
        closeDrawer();
        select(button.dataset.targetPage);
      });
    });
    return;
  }

  if (key === "firewall") {
    drawerContent.innerHTML = `
      <p>${escapeHtml(data.summary)}</p>
      <div><strong>Blocked</strong>${chips(data.blocked, true)}</div>
      <div><strong>Allowed</strong>${chips(data.allowed)}</div>
    `;
    return;
  }

  if (key === "priorities") {
    drawerContent.innerHTML = numbered(data.items);
    return;
  }

  drawerContent.innerHTML = `
    <p>${escapeHtml(data.summary)}</p>
    ${cards(data.items)}
  `;
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
drawer.addEventListener("click", (event) => {
  if (event.target === drawer) closeDrawer();
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
  })
  .catch(() => {
    halModels = FALLBACK_MODELS;
  });

const initial = window.location.hash.replace("#", "") || PAGES[0].id;
select(initial);
