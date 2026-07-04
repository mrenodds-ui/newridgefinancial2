/**
 * HAL core: routing, consent policy, registry, and model-lane logic.
 * Browser + Node compatible (no DOM).
 */
const HalCore = (function () {
  const OUTBOUND_ACTION_RE =
    /\b(submit|submits|submitting|send|sends|sending|email|emails|emailing|e-?mail|fax|faxes|faxing|upload|uploads|uploading|transmit|transmits|transmitting|pay|pays|paying|approve|approves|approving|deny|denies|denying|delete|deletes|deleting|remove|removes|removing|writeback|write back|dispatch|dispatches|dispatching|mail|mailing|wire|wires|wiring)\b|\b(contact|contacts|contacting)\b.*\b(payer|insurance)\b|\b(payer|insurance)\b.*\b(contact|email|fax|call)\b/;

  const OUTBOUND_PHRASES_RE =
    /\bpost(s|ing|ed)?\s+(?:(?:a|an|the|this|that)\s+)?(?:[a-z]+\s+){0,3}?(journal|entry|entries|payment|charge|transaction|invoice|claim|note|statement|ledger|document|documents|record|records|refund|refunds|narrative|narratives|deposit|bill|check|payer)\b|\bpost(s|ing|ed)?\s+to\s+quickbooks\b|\bquickbooks\s+post(ing|ed)?\b|\b(record|make|process)\s+((a|an|the)\s+)?(payment|charge|refund|transaction)\b|\bwrite\s+(it\s+)?back\b|\bwrite(s|ing)?\s+to\s+softdent\b|\bsoftdent\s+write(s|ing|back)?\b|\bupdate\s+softdent\b|\bsync\s+to\s+softdent\b/;

  /** @deprecated use OUTBOUND_ACTION_RE — kept for tests and legacy imports */
  const BLOCKED_RE = OUTBOUND_ACTION_RE;
  /** @deprecated use OUTBOUND_PHRASES_RE */
  const BLOCKED_PHRASES_RE = OUTBOUND_PHRASES_RE;

  const PAGE_SYNONYMS = {
    financial: ["financial dashboard", "financial", "dashboard", "ebitda", "owner", "production", "payer mix", "provider"],
    taxes: ["taxes", "tax plan", "tax planning", "book to tax", "book-to-tax", "1120-s", "1120s", "k-1", "kansas tax", "federal tax", "reasonable compensation", "k-120s", "pte tax", "pass-through", "quarterly estimate", "1040-es"],
    softdent: ["softdent", "soft dent", "practice management"],
    quickbooks: ["quickbooks", "quick books", "p&l", "profit and loss", "expenses", "posting queue", "journal posting queue"],
    ar: ["a/r", "accounts receivable", "receivable", "collections", "aging", "follow-up", "follow up"],
    claims: ["claims workbench", "claims", "claim", "workbench", "denied"],
    narratives: ["narratives", "narrative", "insurance narrative"],
    documents: ["accounting documents", "documents", "document intake", "extraction"],
    library: ["document library", "library", "repository"],
    "office-manager": ["office manager", "office-manager", "office attention", "staff attention"],
    hal: ["hal", "command center", "yourself"],
  };

  const FALLBACK_CONSENT = {
    required: true,
    title: "Staff consent policy",
    summary: "HAL may email, submit, post, fax, upload, or deliver externally only after explicit staff consent for that specific action.",
    prompt: "I need your consent before I send, post, submit, or deliver anything externally.",
    categories: ["Email and payer contact", "Claim submission", "QuickBooks post", "SoftDent writeback", "Document upload"],
    localAlways: ["Open local program pages", "Explain local status", "Prepare review notes", "Refresh imports", "Draft locally"],
  };

  /** @deprecated legacy export — consent policy replaced firewall */
  const FALLBACK_FIREWALL = FALLBACK_CONSENT;

  function consentPolicy(halData) {
    if (halData && halData.consent) return halData.consent;
    return FALLBACK_CONSENT;
  }

  function isFirewallActive() {
    return false;
  }

  function setFirewallEnabled() {
    /* firewall removed — consent policy only */
  }

  function checkFirewall() {
    return false;
  }

  function registryList(halData) {
    return (halData && halData.registry) || [];
  }

  function registryById(halData, id) {
    return registryList(halData).find((entry) => entry.id === id) || null;
  }

  function registryByState(halData, statePattern) {
    return registryList(halData).filter((entry) => statePattern.test(entry.state));
  }

  function modelConfig(halModels) {
    return (halModels && halModels.config) || { mode: "offline" };
  }

  function isLocalModelEndpoint(endpoint) {
    if (!endpoint) return false;
    try {
      const host = new URL(endpoint).hostname.toLowerCase();
      return host === "127.0.0.1" || host === "localhost" || host === "::1";
    } catch {
      return false;
    }
  }

  function modelLanes(halModels) {
    return (halModels && halModels.lanes) || [];
  }

  function runtimeReady(halModels, runtime) {
    const config = modelConfig(halModels);
    return (
      config.mode === "online" &&
      config.externalCallsEnabled === false &&
      runtime &&
      runtime.enabled === true &&
      isLocalModelEndpoint(runtime.endpoint) &&
      !!runtime.model
    );
  }

  function mergeChatLaneRuntime(base, laneRuntimeBlock) {
    if (!base && !laneRuntimeBlock) return null;
    const merged = Object.assign({}, base || {}, laneRuntimeBlock || {});
    merged.options = Object.assign({}, (base && base.options) || {}, (laneRuntimeBlock && laneRuntimeBlock.options) || {});
    if (laneRuntimeBlock && typeof laneRuntimeBlock.think === "boolean") merged.think = laneRuntimeBlock.think;
    else if (base && typeof base.think === "boolean") merged.think = base.think;
    return merged;
  }

  function laneRuntime(halModels, laneId) {
    const config = modelConfig(halModels);
    // A lane may carry its own runtime block; prefer it so any local model can be enabled.
    const lane = modelLanes(halModels).find((l) => l.id === laneId);
    if (laneId === "chat8b" || laneId === "chat14b") {
      const base = config.localModel || null;
      if (lane && lane.runtime) return mergeChatLaneRuntime(base, lane.runtime);
      return base;
    }
    if (lane && lane.runtime) return lane.runtime;
    if (laneId === "helper14b" || laneId === "helper8b") return config.fastModel || null;
    if (laneId === "reason21b") return config.reasoningModel || null;
    if (laneId === "escalate30b") return config.escalationModel || null;
    return null;
  }

  function laneReady(halModels, laneId) {
    return runtimeReady(halModels, laneRuntime(halModels, laneId));
  }

  function deriveModelLaneCards(halModels) {
    return modelLanes(halModels).map((lane) => ({
      name: lane.name,
      role: lane.role,
      state: lane.state,
      model: lane.model,
      ready: laneReady(halModels, lane.id),
    }));
  }

  function deriveReasoningLanes(halData) {
    const ready = registryByState(halData, /ready/i);
    const review = registryByState(halData, /needs review/i);
    const blocked = registryByState(halData, /blocked/i);
    return [
      { label: "Ready", count: ready.length, detail: "Pages and queues that can be reviewed immediately.", entries: ready },
      { label: "Needs review", count: review.length, detail: "Items that require staff confirmation before any next step.", entries: review },
      { label: "Blocked", count: blocked.length, detail: "Items waiting on missing information or external systems.", entries: blocked },
    ];
  }

  function derivePriorityGroups(halData) {
    const lanes = deriveReasoningLanes(halData);
    return lanes.map((lane) => ({
      label: lane.label,
      items: (lane.entries || []).map((entry) => ({
        id: entry.id,
        name: entry.name,
        state: entry.state,
        nextAction: entry.nextAction,
        safety: entry.safety,
      })),
    }));
  }

  function pageInfoMap(halData, pages) {
    const map = {};
    const items = (halData.workSurfaces && halData.workSurfaces.items) || [];
    for (const item of items) map[item.target] = { label: item.label, detail: item.detail };
    for (const page of pages || []) {
      if (!map[page.id]) map[page.id] = { label: page.label, detail: page.title };
    }
    return map;
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

  function isLocalStaffReviewOverride(query) {
    const q = String(query).toLowerCase().trim();
    return (
      /\b(approve all|bulk approve)\b.*\b(journal|posting queue)\b/.test(q) ||
      /\b(journal|posting queue)\b.*\b(approve all|bulk approve)\b/.test(q)
    );
  }

  function isOutboundActionPhrase(query) {
    const q = String(query).toLowerCase().trim();
    if (isLocalStaffReviewOverride(q)) return false;
    return (
      OUTBOUND_ACTION_RE.test(q) ||
      OUTBOUND_PHRASES_RE.test(q) ||
      /\bpush\b.*\b(live|to quickbooks)\b/.test(q) ||
      /\bpush\b.*\b(journal|entry|entries)\b.*\blive\b/.test(q)
    );
  }

  function isHypotheticalQuestion(query) {
    const q = String(query).toLowerCase().trim();
    return (
      /\bwhat happens (when|if)\b/.test(q) ||
      /\bwhat if\b/.test(q) ||
      /\bwhat would happen\b/.test(q) ||
      /\bwhat goes wrong if\b/.test(q) ||
      /\bwhat are the risks if\b/.test(q) ||
      /\bwhen staff (skip|skips|ignore|ignores)\b/.test(q) ||
      /\bif staff (skip|skips|ignore|ignores)\b/.test(q)
    );
  }

  function isPageNavigationIntent(query) {
    const q = String(query).toLowerCase().trim();
    return /\b(open|go to|navigate to|take me to|launch|show me the)\b/.test(q);
  }

  function pickVariant(items) {
    if (!items || !items.length) return "";
    return items[Math.floor(Math.random() * items.length)];
  }

  const CHAT_LIMITS = {
    defaultMax: 1380,
    capabilityMax: 1120,
    helpMax: 920,
    proactiveMax: 1280,
    readinessMax: 1400,
    yesNoMax: 780,
    reasoningMax: 2400,
  };

  const MIN_REPLY_SENTENCES = 5;

  const HAL_IDENTITY_RE =
    /^I am HAL, the local read-only program manager[\s\S]{0,120}?self-check before responding\.\s*/i;

  function isYesNoQuestion(query) {
    return /^(can you|are you allowed|could you|may i ask if you can|tell me honestly|what happens if i ask you to)\b/i.test(
      String(query || "").trim(),
    );
  }

  function isChatSizedQuestion(query, route) {
    const q = String(query || "").toLowerCase();
    const intent = route && route.intent ? String(route.intent) : "";
    if (/^capability:|^capability:consent|^consent/.test(intent)) return true;
    if (isYesNoQuestion(q)) return true;
    if (/^what can you (not )?do on /.test(q)) return true;
    if (route && route.useProactiveBriefing) {
      if (/make a plan|step-by-step|numbered plan|work plan|action plan|analy[sz]e|strategy|reason through/.test(q)) {
        return false;
      }
      return true;
    }
    if (intent === "priorities" || intent === "proactive: briefing") return true;
    if (intent === "help") return true;
    return false;
  }

  function chatBudgetFor(query, route) {
    const intent = route && route.intent ? String(route.intent) : "";
    if (intent === "help") return CHAT_LIMITS.helpMax;
    if (/^reasoning:/.test(intent) || (route && route.useReasoning)) return CHAT_LIMITS.reasoningMax;
    if (/^capability:|^blocked: firewall/.test(intent)) {
      return isYesNoQuestion(query) ? CHAT_LIMITS.yesNoMax : CHAT_LIMITS.capabilityMax;
    }
    if (route && route.useProactiveBriefing) return CHAT_LIMITS.proactiveMax;
    if (route && (route.useReadinessRun || route.useReadinessGate)) return CHAT_LIMITS.readinessMax;
    if (isYesNoQuestion(query)) return CHAT_LIMITS.yesNoMax;
    return CHAT_LIMITS.defaultMax;
  }

  function stripHalIdentityMonologue(text, allowIdentity) {
    if (allowIdentity) return String(text || "").trim();
    return String(text || "")
      .replace(HAL_IDENTITY_RE, "")
      .trim();
  }

  function trimAtSentence(text, maxChars) {
    const raw = String(text || "").trim();
    if (raw.length <= maxChars) return raw;
    const slice = raw.slice(0, maxChars);
    const lastStop = Math.max(slice.lastIndexOf(". "), slice.lastIndexOf("! "), slice.lastIndexOf("? "));
    if (lastStop > Math.floor(maxChars * 0.45)) return slice.slice(0, lastStop + 1).trim();
    return slice.trim() + "…";
  }

  function trimChatReply(text, query, route, options) {
    options = options || {};
    const force = options.force === true;
    if (!force && !isChatSizedQuestion(query, route)) return String(text || "").trim();
    const intent = route && route.intent ? String(route.intent) : "";
    let out = stripHalIdentityMonologue(text, intent === "help");
    const max = options.maxChars || adjustChatBudget(query, route, options);
    if (out.length > max) out = trimAtSentence(out, max);
    return out.trim();
  }

  function buildHelpChatReply(halData) {
    const consent = consentPolicy(halData);
    return pickVariant([
      "I'm HAL — local program manager for this office. I open pages, explain imports, run readiness checks, and draft work. Outbound actions like email, submit, and post require your explicit consent each time.",
      "I read SoftDent and QuickBooks imports, place data on dashboards, and flag gaps. Outbound actions need your consent. Name a page, widget, import task, or say Run readiness check for specifics.",
      `${consent.summary} Name a page if you want more detail.`,
    ]);
  }

  function localChatFallback(query, halData) {
    const top = halData && halData.topPriority && halData.topPriority.summary;
    const reg = registryList(halData)
      .filter((e) => /needs review|blocked/i.test(e.state))
      .slice(0, 2)
      .map((e) => e.name)
      .join(" and ");
    return pickVariant([
      top
        ? `The chat model is offline, but from local data: ${top}${reg ? ` Also watch ${reg}.` : ""}`
        : "The chat model is offline — I still have the registry and import status. Ask about a page, imports, or readiness.",
      reg
        ? `Local chat is offline. Registry shows ${reg} needs attention. I can still explain pages and import health without the model.`
        : "Local chat is offline. I can answer from the program registry — try Open claims, Import status, or Run readiness check.",
    ]);
  }

  function offlineModelChatMessage(laneId, halModels, halData, query) {
    const lane = modelLanes(halModels).find((entry) => entry.id === laneId) || modelLanes(halModels)[0];
    const name = lane && lane.name ? lane.name : "local chat";
    const fallback = localChatFallback(query, halData);
    return pickVariant([
      `${name} is offline right now. ${fallback}`,
      `I can't reach ${name} on this machine. ${fallback}`,
      `Model lane is down (${lane && lane.model ? lane.model : "local"}). ${fallback}`,
    ]);
  }

  function countWords(text) {
    return String(text || "")
      .trim()
      .split(/\s+/)
      .filter(Boolean).length;
  }

  function splitSentences(text) {
    const raw = String(text || "").trim();
    if (!raw) return [];
    return (raw.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [raw]).map((s) => s.trim()).filter(Boolean);
  }

  function countSentences(text) {
    return splitSentences(text).length;
  }

  function isCodeDiscussionQuery(query, route, meta) {
    meta = meta || {};
    const q = String(query || "");
    if (/\b(source code|function|\.js\b|\.py\b|\.mjs\b|grep|read file|how does .+ work|handleHalSubmit|routeHalCommand|programming|in the code)\b/i.test(q)) {
      return true;
    }
    if (meta.hadSourceTools) return true;
    const tools = meta.toolsUsed || meta.tools || [];
    if (Array.isArray(tools) && tools.some((t) => /grep_program|read_program_file|list_program_files|explain_route/.test(String(t)))) {
      return true;
    }
    return false;
  }

  function allowsMarkdownInReply(query, route, meta) {
    if (isCodeDiscussionQuery(query, route, meta || {})) return true;
    if (route && (route.useReasoning || route.useEscalation || route.useOss)) return true;
    if (wantsDetailedReply(query)) return true;
    if (/\b(list|steps|checklist|bullet)\b/i.test(String(query || ""))) return true;
    return false;
  }

  function compressThreadForPrompt(turns, maxRecent) {
    maxRecent = maxRecent || 6;
    const list = turns || [];
    if (!list.length) return "";
    if (list.length <= maxRecent) {
      return list
        .map((t) => `${t.role}: ${String(t.text).slice(0, 160)}${t.intent ? ` [${t.intent}]` : ""}`)
        .join("\n");
    }
    const old = list.slice(0, -maxRecent);
    const recent = list.slice(-maxRecent);
    const topics = old
      .filter((t) => t.role === "user")
      .map((t) => String(t.text).slice(0, 56))
      .slice(-4);
    const summary = topics.length
      ? `Earlier thread (${old.length} turns): ${topics.join("; ")}.`
      : `Earlier thread (${old.length} turns).`;
    const recentText = recent
      .map((t) => `${t.role}: ${String(t.text).slice(0, 160)}${t.intent ? ` [${t.intent}]` : ""}`)
      .join("\n");
    return summary + "\n" + recentText;
  }

  function detectAmbiguousQuery(query, turns) {
    const q = String(query || "").trim();
    if (!/^(fix it|what about that|do that|same thing|help me|what now|and that|what about it)\??$/i.test(q)) {
      return null;
    }
    const priorUser = [...(turns || [])].reverse().find((t) => t.role === "user");
    if (priorUser) return null;
    return {
      text:
        "I need a bit more context before I can investigate. Are you asking about imports, a specific page, claims work, or accounting review?",
      chips: [
        { label: "Import status", query: "Show import status", action: { type: "runQuery", query: "Show import status" } },
        { label: "Top priority", query: "What needs attention today?", action: { type: "runQuery", query: "What needs attention today?" } },
        { label: "Open Claims", query: "Open claims workbench", action: { type: "openPage", page: "claims" } },
        { label: "Refresh imports", query: "Refresh imports", action: { type: "refreshImports" } },
      ],
    };
  }

  function inferPageActionsFromAnswer(text, pages) {
    const actions = [];
    const body = String(text || "").toLowerCase();
    for (const p of pages || []) {
      const id = String(p.id || "").toLowerCase();
      const label = String(p.label || p.title || id).toLowerCase();
      if ((label.length > 4 && body.includes(label)) || body.includes(id.replace(/-/g, " "))) {
        actions.push({
          type: "openPage",
          label: "Open " + (p.label || p.id),
          page: p.id,
        });
      }
    }
    const seen = new Set();
    return actions.filter((a) => {
      if (seen.has(a.page)) return false;
      seen.add(a.page);
      return true;
    }).slice(0, 2);
  }

  function isInternalInstructionText(text) {
    const s = String(text || "").toLowerCase();
    return (
      /synthesize tool results|do not paste tool headers|combine them into one coherent|local tool check:/i.test(s) ||
      /if multiple tools ran|markdown dumps|chain-of-thought|self-check rubric/i.test(s)
    );
  }

  function stripInstructionLeaks(text) {
    return String(text || "")
      .replace(/\bLocal tool check:[\s\S]{0,360}?(?:\.\s|\.$|$)/gi, "")
      .replace(/\bSynthesize tool results[\s\S]{0,280}?(?:\.\s|\.$|$)/gi, "")
      .replace(/\bIf multiple tools ran, combine th[\s\S]{0,160}?\./gi, "")
      .replace(/\bdo not paste tool headers[\s\S]{0,120}?(?:\.\s|\.$|$)/gi, "")
      .replace(/\bCall out \[FAILED\][^.!?]*[.!?]?/gi, "")
      .replace(/\s*\((Local (reasoning|chat|escalation|OSS)?[^)]*draft[^)]*)\)\s*$/gi, "")
      .replace(/\s*\(Local reasoning plan · read-only · verify before acting\)\s*$/gi, "")
      .replace(/\s*\(Local .* · read-only · verify before acting\)\s*$/gi, "")
      .replace(/\s{2,}/g, " ")
      .trim();
  }

  function shouldEnforceMinSentences(query, route, meta, text) {
    meta = meta || {};
    const body = String(text || "").trim();
    const detailed = wantsDetailedReply(query) || /glacial pace|every step|walk me through|at a glacial/i.test(String(query || ""));
    if (body && countSentences(body) >= MIN_REPLY_SENTENCES && !detailed) {
      return false;
    }
    if (meta.skipMinSentences) return false;
    if (isSimpleActionQuery(query)) return false;
    if (route && route.text && body && countSentences(body) >= MIN_REPLY_SENTENCES && !detailed) return false;
    if (isCodeDiscussionQuery(query, route, meta)) return false;
    if ((wantsBriefReply(query) || meta.preferBrief) && !detailed) return false;
    const q = String(query || "").trim();
    if (/read[\s-]?only|readonly actually mean|what does read-only/i.test(q)) return true;
    if (q.length < 48 && !(route && (route.useReasoning || route.useEscalation)) && !isYesNoQuestion(q) && !detailed) {
      return false;
    }
    return true;
  }

  function minSentencePadding(query, route, meta, existing) {
    const halData = meta && meta.halData;
    const top = halData && halData.topPriority && halData.topPriority.summary;
    const page = meta && meta.currentPage;
    const tool = meta && meta.toolSummary;
    const pool = [
      top
        ? "The registry currently flags this as the top priority: " + top + "."
        : "I answer from the local program registry and import bundle — not live write-back to SoftDent or QuickBooks.",
      page
        ? "You are on the " + page + " page; name a widget if you want a narrower answer."
        : "You can narrow this by naming a page — Financial, Claims, A/R, or QuickBooks.",
      tool && String(tool).length > 20 && !isInternalInstructionText(tool)
        ? "From local checks: " + String(tool).replace(/\s+/g, " ").trim().slice(0, 120) + "."
        : "If a widget looks empty, refresh imports and verify the export path before drawing conclusions.",
      "Staff still posts in QuickBooks, contacts payers, and handles outbound steps — I stay read-only at the firewall.",
      "I can open pages, explain status, draft review notes, and flag gaps; humans execute anything external.",
      "Missing fields usually indicate a stale or incomplete import, not hidden data.",
    ];
    const out = [];
    for (const p of pool) {
      if (existing.length + out.length >= MIN_REPLY_SENTENCES) break;
      if (!existing.some((s) => textSimilarity(s, p) > 0.55) && !out.some((s) => textSimilarity(s, p) > 0.55)) {
        out.push(p);
      }
    }
    while (existing.length + out.length < MIN_REPLY_SENTENCES) {
      out.push(pool[(existing.length + out.length) % pool.length]);
    }
    return out;
  }

  function ensureMinSentences(text, query, route, meta) {
    const draft = String(text || "").trim();
    if (!shouldEnforceMinSentences(query, route, meta, draft)) return draft;
    let out = draft;
    for (let pass = 0; pass < 3 && countSentences(out) < MIN_REPLY_SENTENCES; pass++) {
      const sentences = splitSentences(out);
      const pads = minSentencePadding(query, route, meta || {}, sentences);
      out = sentences.concat(pads.slice(0, MIN_REPLY_SENTENCES - sentences.length)).join(" ").trim();
    }
    if (countSentences(out) < MIN_REPLY_SENTENCES) {
      out = out.replace(/[.!?]\s*$/, "") + ". Ask about Financial, Claims, A/R, or QuickBooks if you want a narrower answer.";
    }
    return out.trim();
  }

  function hasUnrequestedList(text, query) {
    if (/\b(list|step-by-step|numbered|bullet|checklist|show all|full briefing|everything)\b/i.test(String(query || ""))) {
      return false;
    }
    const body = String(text || "");
    const numbered = (body.match(/^\s*\d+\.\s/mg) || []).length;
    const bullets = (body.match(/^\s*[-*•]\s/mg) || []).length;
    return numbered >= 4 || bullets >= 4;
  }

  function chatShapeIssues(query, text, route, opts) {
    opts = opts || {};
    const issues = [];
    const intent = route && route.intent ? String(route.intent) : "";
    const body = String(text || "").trim();
    if (!body) return issues;
    if (intent !== "help" && HAL_IDENTITY_RE.test(body)) issues.push("identity_monologue");
    if (isChatSizedQuestion(query, route) && !(route && route.useReasoning) && countWords(body) > 320) {
      issues.push("too_long_chat");
    }
    if (hasUnrequestedList(body, query) && !allowsMarkdownInReply(query, route, opts)) issues.push("numbered_list_unrequested");
    if (isYesNoQuestion(query) && !/^(yes|no|sure|absolutely|that one's|not from here|i can't|i can|different angle|to add)/i.test(body)) {
      issues.push("yes_no_not_direct");
    }
    if (CHATBOT_FILLER_RE.test(body) || CHATBOT_CLOSER_RE.test(body)) issues.push("chatbot_filler");
    if (INTERNAL_JARGON_RE.test(body)) issues.push("internal_jargon");
    if (/\b(local tool check|synthesize tool results|combine th\b|do not paste tool headers)\b/i.test(body)) {
      issues.push("instruction_leak");
    }
    if (QUESTION_ECHO_RE.test(body)) issues.push("question_echo");
    if (answersMustLead(query, route) && !answerLeadsCorrectly(query, body, route)) issues.push("answer_not_first");
    if (opts.previousHalText && textSimilarity(body, opts.previousHalText) > 0.72) issues.push("repeats_previous");
    if (
      shouldEnforceMinSentences(query, route, opts) &&
      countSentences(body) < MIN_REPLY_SENTENCES
    ) {
      issues.push("too_few_sentences");
    }
    if (typeof HalAgentProgramming !== "undefined" && HalAgentProgramming.agentShapeIssues) {
      HalAgentProgramming.agentShapeIssues(query, body, route, {
        hadToolResults: opts.hadToolResults,
        previousHalText: opts.previousHalText,
        codeDiscussion: isCodeDiscussionQuery(query, route, opts),
      }).forEach((issue) => {
        if (!issues.includes(issue)) issues.push(issue);
      });
    }
    return issues;
  }

  function answersMustLead(query, route) {
    const intent = route && route.intent ? String(route.intent) : "";
    return isYesNoQuestion(query) || /^capability:|^blocked: firewall/.test(intent);
  }

  function answerLeadsCorrectly(query, body, route) {
    const text = String(body || "").trim();
    if (!text) return false;
    const intent = route && route.intent ? String(route.intent) : "";
    if (isYesNoQuestion(query)) {
      return /^(yes|no|sure|absolutely|obviously|frankly|predictably|not from here|i can't|i can|repeating myself|still|got it|fine)/i.test(text);
    }
    if (/^blocked: firewall/.test(intent)) {
      return /^(no|not from here|can't|cannot|blocked|stops at the firewall|same answer|still read-only|that's all|i couldn't have been clearer|that's not what|details\.|please bore)/i.test(text);
    }
    if (/^capability:/.test(intent)) {
      return /^(yes|no|sure|on |from |for |i can|i can't|absolutely|obviously|same as before)/i.test(text);
    }
    return true;
  }

  function stripInternalJargon(text) {
    return stripInstructionLeaks(
      String(text || "")
        .replace(INTERNAL_JARGON_RE, "local system")
        .replace(/\s{2,}/g, " ")
        .trim(),
    );
  }

  function flattenMarkdownForChat(text) {
    return String(text || "")
      .replace(/\*\*([^*]+)\*\*/g, "$1")
      .replace(/\*([^*]+)\*/g, "$1")
      .replace(/^#+\s+/gm, "")
      .replace(/^\s*\d+\.\s+/gm, "")
      .replace(/^\s*[-*•]\s+/gm, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function compressedBlockedReply(_legacy, query, briefCount, halData) {
    if (briefCount >= 1) {
      return pickVariant([
        "Same consent policy — confirm before any email, submit, or post.",
        "Still need your consent for outbound actions. I can prep locally until you confirm.",
        "No change — explicit consent is still required for external delivery.",
      ]);
    }
    return variedBlockedCapabilityReply(null, query, halData);
  }

  function buildSessionRecap(turns) {
    const list = (turns || []).filter((t) => t && t.text);
    if (!list.length) return "We haven't chatted yet this session — ask about a page, imports, or readiness.";
    const pairs = [];
    for (let i = 0; i < list.length; i++) {
      const t = list[i];
      if (t.role !== "user") continue;
      const nextHal = list[i + 1] && list[i + 1].role === "hal" ? list[i + 1] : null;
      pairs.push({
        q: String(t.text).slice(0, 100),
        a: nextHal ? String(nextHal.text).slice(0, 120) : "",
      });
    }
    const recent = pairs.slice(-4);
    if (!recent.length) return "No recent questions to recap.";
    const lines = recent.map((p, idx) => `${idx + 1}. You asked "${p.q}" — I said "${p.a || "…"}"`);
    return "Quick recap:\n" + lines.join("\n");
  }

  function matchCompareRoute(query) {
    const raw = String(query || "").trim();
    if (/^(explain|tell me about|what is|what's|describe)\b/i.test(raw)) return null;
    const m = raw.match(/^(.+?)\s+(?:vs\.?|versus|compared to)\s+(.+?)\??$/i);
    if (!m) return null;
    const left = m[1].trim();
    const right = m[2].trim();
    if (!left || !right || left.length > 48 || right.length > 48) return null;
    return { left, right };
  }

  function buildCompareReply(left, right, halData) {
    const l = left.toLowerCase();
    const r = right.toLowerCase();
    const topics = {
      imports: /\bimports?\b/,
      widgets: /\bwidgets?\b/,
      softdent: /\bsoftdent\b/,
      quickbooks: /\bquickbooks\b|\bqb\b/,
      claims: /\bclaims?\b/,
      readiness: /\breadiness\b/,
    };
    function detect(s) {
      return Object.keys(topics).filter((k) => topics[k].test(s));
    }
    const dl = detect(l);
    const dr = detect(r);
    if (dl.includes("imports") && dr.includes("widgets")) {
      return pickVariant([
        "Imports are the raw SoftDent and QuickBooks files I load locally. Widgets are the dashboard tiles built from that data — refresh imports first when widgets look empty.",
        "Imports feed the program; widgets display the result on each page. No imports, widgets show gaps even if the layout is fine.",
      ]);
    }
    if (dl.includes("softdent") && dr.includes("quickbooks")) {
      return pickVariant([
        "SoftDent is clinical and production data; QuickBooks is accounting and P&L. I read both as imports — neither gets write-back from here.",
        "SoftDent covers practice/clinical exports; QuickBooks covers books. Both stay read-only; staff posts in QuickBooks outside the program.",
      ]);
    }
    const top = halData && halData.topPriority && halData.topPriority.summary;
    return pickVariant([
      `${left} and ${right} are different surfaces here — ask about one page at a time if you want specifics.${top ? " Top priority right now: " + top : ""}`,
      `Short answer: ${left} vs ${right} aren't the same workflow. Name the page or task and I'll compare what I can do on each.`,
    ]);
  }

  function appendEvidenceClause(text, toolSummary, query) {
    if (!toolSummary || !String(text || "").trim()) return text;
    if (isInternalInstructionText(toolSummary)) return String(text || "").trim();
    const body = String(text).trim();
    if (/\b(from local|registry shows|imports show|from the registry|local data|from local checks)\b/i.test(body)) return body;
    const snippet = String(toolSummary).replace(/\s+/g, " ").trim().slice(0, 100);
    if (!snippet || snippet.length < 12 || isInternalInstructionText(snippet)) return body;
    if (/\b(missing|empty|offline|unavailable|no import)\b/i.test(snippet)) {
      return body.replace(/[.!?]\s*$/, "") + ". From local data: " + snippet + ".";
    }
    return body;
  }

  function repairChatShape(query, text, route, issues) {
    let out = String(text || "").trim();
    if (issues.includes("identity_monologue")) out = stripHalIdentityMonologue(out, false);
    if (issues.includes("chatbot_filler")) out = stripChatbotFillers(out);
    if (issues.includes("internal_jargon")) out = stripInternalJargon(out);
    if (issues.includes("instruction_leak")) out = stripInstructionLeaks(out);
    if (issues.includes("question_echo")) out = out.replace(QUESTION_ECHO_RE, "").trim();
    if (issues.includes("repeats_previous")) {
      const keepYesNo =
        route &&
        (/^capability:(no-executor|blocked)/.test(String(route.intent || "")) ||
          /^blocked: firewall/.test(String(route.intent || "")));
      out = pickVariant(
        keepYesNo
          ? ["Same boundary as before: " + out, "Still the same rule: " + out, out]
          : [
              "Different angle on the same point: " + out,
              "Restating with the same evidence: " + out,
              out.replace(/^(yes|no)[—,\s]*/i, ""),
            ],
      );
    }
    if (issues.includes("too_long_chat") || issues.includes("numbered_list_unrequested")) {
      out = trimChatReply(out, query, route, { force: true, preferBrief: true });
    }
    if (issues.includes("yes_no_not_direct") && isYesNoQuestion(query)) {
      const blocked = route && route.intent === "blocked: firewall";
      let prefix =
        typeof HalAgentProgramming !== "undefined" && HalAgentProgramming.yesNoLead
          ? HalAgentProgramming.yesNoLead(query, route)
          : blocked
            ? "No."
            : "Yes.";
      if (!prefix) prefix = blocked ? "No." : "Yes.";
      if (!/^(yes|no)\b/i.test(out)) out = prefix + " " + out;
    }
    if (issues.includes("answer_not_first") && answersMustLead(query, route)) {
      if (/^blocked: firewall/.test(route && route.intent ? route.intent : "") && !/^no\b/i.test(out)) {
        out = "No — " + out.replace(/^(yes|no)[—,\s]*/i, "");
      } else if (isYesNoQuestion(query) && !/^(yes|no)\b/i.test(out)) {
        const blocked = /^blocked: firewall/.test(route && route.intent ? route.intent : "");
        out = (blocked ? "No — " : "Yes — ") + out;
      }
    }
    if (issues.includes("too_few_sentences")) {
      out = ensureMinSentences(out, query, route, {});
    }
    if (typeof HalAgentProgramming !== "undefined" && HalAgentProgramming.repairAgentShapeIssues) {
      out = HalAgentProgramming.repairAgentShapeIssues(query, out, issues, route);
    }
    return out.trim();
  }

  const CHATBOT_FILLER_RE =
    /^(great question|good question|certainly[!,]?|absolutely[!,]?|i'd be happy to|as an ai|as an artificial)/i;
  const CHATBOT_CLOSER_RE =
    /(let me know if|would you like me to|feel free to ask|if you want more detail|i hope this helps|happy to assist|feel free to reach out)\s*\.?\s*$/i;
  const INTERNAL_JARGON_RE =
    /\b(agent loop|model lane|chat8b|reason21b|escalate30b|oss120b|self-check|tool results|num_predict|fastChat|GPU lane|Ollama endpoint|local tool check|synthesize tool|markdown dumps)\b/gi;
  const QUESTION_ECHO_RE = /^(regarding your question|as for your question|you asked (?:if|whether)|to answer your question)/i;

  function detectUserTone(query) {
    const q = String(query || "").trim().toLowerCase();
    if (/^(quick question|hey hal|hal,|just wondering|real quick)/.test(q)) return "casual";
    if (/\b(explain|step-by-step|numbered|list all|full detail|walk me through|break down)\b/.test(q)) return "detailed";
    return "neutral";
  }

  function isFollowUpQuery(query) {
    const q = String(query || "").trim();
    return (
      /\b(that|same thing|same question|what about|how about|and what about|you said|earlier)\b/i.test(q) ||
      isImplicitFollowUp(q)
    );
  }

  function isImplicitFollowUp(query) {
    const q = String(query || "").trim();
    if (/^(what about|and |also |how about|same for|still\??|again\??)/i.test(q)) return true;
    if (q.length < 90 && /\b(it|that|there|this one)\b/i.test(q)) return true;
    return false;
  }

  function isCorrectionQuery(query) {
    return /^(no[,.\s—-]|that'?s wrong|not what i meant|incorrect|you misunderstood|wrong[—-])/i.test(String(query || "").trim());
  }

  function wantsBriefReply(query) {
    return /\b(shorter|too long|be brief|keep it short|tl;dr|summarize|less detail)\b/i.test(String(query || "").toLowerCase());
  }

  function wantsDetailedReply(query) {
    return detectUserTone(query) === "detailed";
  }

  function tokenSet(text) {
    return new Set(String(text || "").toLowerCase().match(/\b[a-z]{3,}\b/g) || []);
  }

  function textSimilarity(a, b) {
    const sa = tokenSet(a);
    const sb = tokenSet(b);
    if (!sa.size || !sb.size) return 0;
    let inter = 0;
    sa.forEach((t) => {
      if (sb.has(t)) inter++;
    });
    return inter / Math.max(sa.size, sb.size);
  }

  function buildThreadContextBlock(turns, query) {
    const recent = (turns || []).slice(-6);
    if (!recent.length) return "";
    const lines = recent.map((t) => `${t.role === "user" ? "User" : "HAL"}: ${String(t.text).slice(0, 200)}`);
    let block = "Recent conversation (stay coherent — do not repeat your last answer verbatim):\n" + lines.join("\n");
    const resolved = resolveFollowUpTopic(query, turns);
    if (resolved) block += "\nResolved follow-up topic: " + resolved;
    if (isFollowUpQuery(query)) block += "\nThis refers to the prior turn — answer in that context.";
    return block;
  }

  function resolveFollowUpTopic(query, turns) {
    const q = String(query || "").trim();
    if (!isFollowUpQuery(q)) return "";
    const list = turns || [];
    const lastUser = [...list].reverse().find((t) => t.role === "user");
    const lastHal = [...list].reverse().find((t) => t.role === "hal");
    const priorQ = lastUser ? String(lastUser.text).slice(0, 140) : "";
    const priorA = lastHal ? String(lastHal.text).slice(0, 120) : "";
    const about = q.match(/^what about\s+(.+?)\??$/i);
    if (about) return `User previously asked "${priorQ}" — now asking about ${about[1].trim()}.`;
    if (/^(and|also)\s+/i.test(q)) return `Extending prior question "${priorQ}": ${q}`;
    if (/\b(it|that|there)\b/i.test(q) && priorA) return `Referring to HAL's last answer: "${priorA}" — user says: ${q}`;
    if (/^(still|again)\??$/i.test(q)) return `User wants confirmation on: "${priorQ}"`;
    return priorQ ? `Follow-up to: "${priorQ}"` : "";
  }

  function resolveFollowUpQuery(query, turns) {
    const q = String(query || "").trim();
    if (!isFollowUpQuery(q)) return q;
    const topic = resolveFollowUpTopic(q, turns);
    if (!topic) return q;
    return `${q} (${topic})`;
  }

  function expandAtMentions(query, pages) {
    let q = String(query || "");
    if (!/@/.test(q)) return q;
    const pageList = pages || [];
    q = q.replace(/@([\w./-]+)/g, (full, token) => {
      const t = String(token || "").toLowerCase();
      const page = pageList.find(
        (p) =>
          String(p.id || "").toLowerCase() === t ||
          String(p.label || "")
            .toLowerCase()
            .includes(t.replace(/-/g, " ")),
      );
      if (page) return `(page context: ${page.label || page.id}) ${full}`;
      if (/\.(js|py|json|mjs|css|html)$/i.test(token)) return `(file context: ${token}) ${full}`;
      return full;
    });
    return q;
  }

  function updateSessionSummary(turns, prior) {
    const list = turns || [];
    if (list.length < 6) return prior || "";
    const users = list
      .filter((t) => t.role === "user")
      .slice(-8)
      .map((t) => String(t.text).slice(0, 72));
    if (!users.length) return prior || "";
    return "Session topics so far: " + users.join("; ") + ".";
  }

  function isSimpleActionQuery(query) {
    const q = String(query || "").toLowerCase();
    if (/\b(explain|why|detail|status|describe|tell me about)\b/.test(q)) return false;
    return (
      /^\s*(open|go to|navigate to|take me to|launch)\b/.test(q) ||
      /^\s*(refresh|reload)\s+(the\s+)?imports?\b/.test(q) ||
      (/^\s*can you (open|refresh|reload)\b/.test(q) && q.length < 80)
    );
  }

  function buildMicroActionReply(intent, label, query) {
    const name = label || "that page";
    if (/^navigate:/.test(intent)) {
      return pickVariant([
        `Opening ${name} now.`,
        `${name} is loading — I'll keep context on this page for follow-ups.`,
        `On it — switching to ${name}.`,
      ]);
    }
    if (/imports: refresh/.test(intent)) {
      return pickVariant([
        "Refreshing local SoftDent and QuickBooks imports — read-only, no write-back.",
        "Import refresh started from local export paths.",
        "Reloading import bundle now; widgets update when files land.",
      ]);
    }
    if (/imports: status/.test(intent) && isSimpleActionQuery(query)) {
      return pickVariant(["Checking import status from local files.", "Pulling import health from the local bundle."]);
    }
    return "";
  }

  function pageAwareClause(currentPage, halData, pages, query) {
    if (!currentPage || currentPage === "hal") return "";
    if (isFollowUpQuery(query) && !/\b(on |page|open )/i.test(query)) return "";
    const info = pageInfoMap(halData, pages)[currentPage];
    if (!info) return "";
    return pickVariant([`On ${info.label}: `, `From ${info.label}, `, `${info.label} — `]);
  }

  function agentPersonalityPromptLines() {
    if (typeof HalAgentProgramming !== "undefined" && HalAgentProgramming.contractSummary) {
      return HalAgentProgramming.contractSummary();
    }
    return "Auto-style agent: answer first, cite local evidence, name gaps, one next step, min five sentences.";
  }

  function mirandaPersonalityPromptLines() {
    return agentPersonalityPromptLines();
  }

  function applyHalPersonality(text, query, route, meta) {
    meta = meta || {};
    let out = String(text || "").trim();
    if (!out || meta.skipPersonality) return out;

    if (/^got it\b/i.test(out)) {
      out = out.replace(/^got it\b/i, "Understood — ").trim();
    }
    if (isCorrectionQuery(query) && !/^to clarify\b/i.test(out)) {
      out = ("To clarify — " + out.charAt(0).toLowerCase() + out.slice(1)).trim();
    }
    if (isYesNoQuestion(query)) {
      if (/^yes\b/i.test(out) && !/^yes[.,]/i.test(out)) {
        out = out.replace(/^yes[—,\s-]*/i, "Yes. ");
      } else if (/^no\b/i.test(out) && !/^no[.,]/i.test(out)) {
        out = out.replace(/^no[—,\s-]*/i, "No. ");
      }
    }
    return out.trim();
  }

  function stripChatbotFillers(text) {
    let out = String(text || "").trim();
    out = out.replace(CHATBOT_FILLER_RE, "");
    out = out.replace(CHATBOT_CLOSER_RE, "").trim();
    return out.trim();
  }

  function synthesizeHandlerReply(rawText, query, route) {
    const raw = String(rawText || "").trim();
    if (!raw || raw.length < 320) return raw;
    const intent = route && route.intent ? String(route.intent) : "";
    if (/readiness/i.test(intent) || /HAL readiness:/i.test(raw)) {
      const gate = raw.match(/Staff use gate:\s*([^\n]+)/i);
      const warn = (raw.match(/\[Warning\]/gi) || []).length;
      const fail = (raw.match(/\[Fail\]/gi) || []).length;
      const pass = (raw.match(/\[Pass\]/gi) || []).length;
      const status = fail ? "needs fixes" : warn ? "ready with warnings" : "looks good";
      return pickVariant([
        `Readiness is ${status} — ${pass} pass, ${warn} warning${warn === 1 ? "" : "s"}${fail ? `, ${fail} fail` : ""}.${gate ? " " + gate[1].trim() + "." : ""}`,
        `Quick read: ${status} (${pass}P/${warn}W${fail ? `/${fail}F` : ""}).${gate ? " Gate: " + gate[1].trim() + "." : ""}`,
      ]);
    }
    if (/widget/i.test(intent) || /\[FAILED\]|Widgets ready:/i.test(raw)) {
      const ready = raw.match(/(\d+\/\d+)\s*ready/i) || raw.match(/Widgets ready:\s*(\d+\/\d+)/i);
      const failed = (raw.match(/\[FAILED\]/gi) || []).length;
      return pickVariant([
        `Widget feed: ${ready ? ready[1] + " ready" : "partial data"}${failed ? `, ${failed} need imports` : ""}.`,
        `Dashboard widgets — ${ready ? ready[1] : "some gaps"}${failed ? "; " + failed + " still need data" : ""}.`,
      ]);
    }
    if (/imports:/i.test(intent)) {
      if (isSimpleActionQuery(query) && /refresh/i.test(intent)) {
        return pickVariant([
          "Imports refreshed — dashboards use the latest local export files.",
          "Done — local SoftDent and QuickBooks imports reloaded.",
        ]);
      }
      const first = raw.split(/\n/).find((l) => l.trim().length > 10) || raw.slice(0, 160);
      return trimAtSentence(first.replace(/^#+\s*/, ""), 280);
    }
    if (hasUnrequestedList(raw, query) || raw.length > 700) {
      const first = raw.split(/\n/).find((l) => l.trim().length > 12) || raw.slice(0, 120);
      return trimAtSentence(first.replace(/^#+\s*/, ""), 280);
    }
    return trimChatReply(raw, query, route, { force: true });
  }

  function progressiveDepthHint(query, route, wasTrimmed) {
    if (!wasTrimmed || wantsDetailedReply(query)) return "";
    const intent = route && route.intent ? String(route.intent) : "";
    if (/readiness/i.test(intent)) return pickVariant([' Say "Run readiness check" for the full checklist.', " Ask for the full readiness report for every line."]);
    if (route && route.useProactiveBriefing) return pickVariant([' Say "full briefing" for all priorities.', " Ask for more detail if you want the rest."]);
    if (/widget/i.test(intent)) return ' Say "Show manager dashboard widgets" for the full feed.';
    return "";
  }

  function buildFollowUpChips(outcome, route, halData, query) {
    const chips = [];
    const intent = outcome && outcome.intent ? String(outcome.intent) : route && route.intent ? String(route.intent) : "";
    const answer = outcome && outcome.text ? String(outcome.text) : "";
    const pages = outcome && outcome._pages ? outcome._pages : [];
    if (route && route.useReadinessRun) {
      chips.push({ label: "Full readiness", query: "Run readiness check", action: { type: "runQuery", query: "Run readiness check" } });
    }
    if (route && route.useProactiveBriefing) {
      chips.push({ label: "What's next?", query: "What should staff do first?", action: { type: "runQuery", query: "What should staff do first?" } });
    }
    if (route && route.useWidgetFeed) {
      chips.push({
        label: "Open Financial",
        query: "Open financial dashboard",
        action: { type: "openPage", page: "financial" },
      });
    }
    if (intent === "blocked: firewall" || intent === "capability:blocked") {
      chips.push({ label: "What CAN I do?", query: "What can you do instead?" });
      chips.push({ label: "Draft review note", query: "Draft a journal entry locally" });
    }
    if (/imports:|missing import|no import data|imports look empty|stale export|refresh import/i.test(answer + intent)) {
      chips.push({ label: "Refresh imports", query: "Refresh imports", action: { type: "refreshImports" } });
      chips.push({ label: "Import status", query: "Show import status", action: { type: "runQuery", query: "Show import status" } });
    }
    if (/^navigate:/.test(intent)) {
      const pageId = intent.replace(/^navigate:\s*/, "");
      chips.push({
        label: "Why this page?",
        query: "What can you do on this page?",
        action: { type: "runQuery", query: "What can you do on the " + pageId.replace(/-/g, " ") + " page?" },
      });
    }
    const actions = outcome && outcome.actions ? outcome.actions : [];
    if (/^capability:page-/.test(intent) && actions[0] && actions[0].page) {
      chips.push({
        label: "Open page",
        query: "Open " + actions[0].page.replace(/-/g, " "),
        action: { type: "openPage", page: actions[0].page },
      });
    }
    if (/claims workbench|denied claim|claim packet/i.test(answer) && !chips.some((c) => c.action && c.action.page === "claims")) {
      chips.push({
        label: "Open Claims",
        query: "Open claims workbench",
        action: { type: "openPage", page: "claims" },
      });
    }
    if (/quickbooks|journal|ledger|posting queue/i.test(answer) && !chips.some((c) => c.action && c.action.page === "quickbooks")) {
      chips.push({
        label: "Open QuickBooks",
        query: "Open QuickBooks",
        action: { type: "openPage", page: "quickbooks" },
      });
    }
    const top = halData && halData.topPriority && halData.topPriority.summary;
    if (top && (/priority|attention|blocked today/i.test(String(query || "")) || chips.length < 2)) {
      chips.push({ label: "Top priority", query: "What's the top priority?", action: { type: "runQuery", query: "What's the top priority?" } });
    }
    const displayLen = answer.length;
    const spokenBudget =
      typeof spokenBudgetFor === "function" && query ? spokenBudgetFor(query, route, {}) : 220;
    if (displayLen > spokenBudget + 60) {
      chips.push({ label: "Say more", query: "Say more about that", action: { type: "runQuery", query: "Say more about that" } });
    }
    const seen = new Set();
    return chips
      .filter((c) => {
        const key = (c.action && c.action.type === "openPage" ? c.action.page : c.query || c.label).toLowerCase();
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      })
      .slice(0, 5);
  }

  function adjustChatBudget(query, route, opts) {
    opts = opts || {};
    let max = chatBudgetFor(query, route);
    const intent = route && route.intent ? String(route.intent) : "";
    if (route && (route.useReasoning || route.useEscalation || /^reasoning:/.test(intent))) {
      max = Math.min(Math.floor(max * 1.15), CHAT_LIMITS.reasoningMax);
    }
    if (opts.preferBrief || wantsBriefReply(query)) {
      max = Math.max(Math.floor(max * 0.88), 920);
    } else if (detectUserTone(query) === "casual") {
      max = Math.floor(max * 0.92);
    }
    if (wantsDetailedReply(query)) max = Math.min(Math.floor(max * 1.35), CHAT_LIMITS.reasoningMax);
    return max;
  }

  function expandCorrectionQuery(query, turns) {
    if (!isCorrectionQuery(query)) return query;
    const list = turns || [];
    const priorUser = [...list].reverse().find((t) => t.role === "user");
    const priorHal = [...list].reverse().find((t) => t.role === "hal");
    if (!priorUser || !priorHal) return query;
    return (
      'Correction: "' +
      query +
      '". Re-answer more accurately. Prior question: "' +
      priorUser.text +
      '". Your prior answer: "' +
      String(priorHal.text).slice(0, 280) +
      '".'
    );
  }

  function polishChatReply(text, query, route, meta) {
    meta = meta || {};
    let out = stripInstructionLeaks(String(text || "").trim());
    const intent = route && route.intent ? String(route.intent) : "";
    if (/^blocked: firewall/.test(intent) && meta.firewallBriefCount >= 1) {
      out = compressedBlockedReply(null, query, meta.firewallBriefCount, meta.halData);
    }
    const micro = isSimpleActionQuery(query) && buildMicroActionReply(intent, meta.actionLabel, query);
    if (micro && /^navigate:|imports: refresh|imports: status/.test(intent)) {
      out = micro;
    }
    const rawLen = out.length;
    if (meta.synthesize !== false && (out.length > 300 || (hasUnrequestedList(out, query) && !allowsMarkdownInReply(query, route, meta)))) {
      out = synthesizeHandlerReply(out, query, route);
    }
    if (isChatSizedQuestion(query, route) && (/\*\*|^\s*\d+\./m.test(out)) && !allowsMarkdownInReply(query, route, meta)) {
      out = flattenMarkdownForChat(out);
    }
    if (meta.currentPage && meta.pages && meta.halData) {
      const clause = pageAwareClause(meta.currentPage, meta.halData, meta.pages, query);
      if (clause && !new RegExp("^" + clause.trim().slice(0, 6), "i").test(out)) {
        out = clause + (out.charAt(0) || "").toLowerCase() + out.slice(1);
      }
    }
    out = stripChatbotFillers(out);
    out = stripInternalJargon(out);
    if (meta.toolSummary) out = appendEvidenceClause(out, meta.toolSummary, query);
    out = trimChatReply(out, query, route, {
      force: meta.forceTrim || (isChatSizedQuestion(query, route) && !(route && route.useReasoning)),
      maxChars: adjustChatBudget(query, route, meta),
      preferBrief: meta.preferBrief,
    });
    const hint = progressiveDepthHint(query, route, rawLen > out.length + 40);
    if (hint && !out.includes(hint.trim().slice(1, 20))) out = out + hint;
    out = applyHalPersonality(out, query, route, meta);
    out = ensureMinSentences(out, query, route, meta);
    return stripInstructionLeaks(out.trim());
  }

  const SPOKEN_LIMITS = {
    defaultMax: 520,
    yesNoMax: 340,
    capabilityMax: 440,
    readinessMax: 400,
    planMax: 580,
    briefMax: 200,
  };

  const SPOKEN_DEPTH_HINT_RE = /(?:^|\s)(?:Say|Ask)\s+"[^"]+"\s+for\s+[^.!?]+[.!?]?/gi;

  function stripMarkdownForSpeech(text) {
    return String(text || "")
      .replace(/\*\*([^*]+)\*\*/g, "$1")
      .replace(/\*([^*]+)\*/g, "$1")
      .replace(/`([^`]+)`/g, "$1")
      .replace(/^#+\s+/gm, "")
      .replace(/^\s*[-*•]\s+/gm, "")
      .replace(/^\s*\d+\.\s+/gm, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function spokenContractions(text) {
    return String(text || "")
      .replace(/\bI am\b/g, "I'm")
      .replace(/\bcannot\b/gi, "can't")
      .replace(/\bdo not\b/gi, "don't")
      .replace(/\bdoes not\b/gi, "doesn't")
      .replace(/\bwill not\b/gi, "won't")
      .replace(/\bit is\b/gi, "it's")
      .replace(/\bthat is\b/gi, "that's")
      .replace(/\bwe are\b/gi, "we're")
      .replace(/\byou are\b/gi, "you're");
  }

  function spokenNumbers(text) {
    const small = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];
    return String(text || "").replace(/\b(\d+)\/(\d+)\b/g, (_, a, b) => {
      const an = Number(a);
      const bn = Number(b);
      const aw = an >= 0 && an <= 10 ? small[an] : a;
      const bw = bn >= 0 && bn <= 10 ? small[bn] : b;
      return `${aw} of ${bw}`;
    });
  }

  function spokenBudgetFor(query, route, meta) {
    meta = meta || {};
    const intent = route && route.intent ? String(route.intent) : "";
    if (meta.preferBrief || wantsBriefReply(query)) return SPOKEN_LIMITS.briefMax;
    if (isYesNoQuestion(query)) return SPOKEN_LIMITS.yesNoMax;
    if (/^capability:|^blocked: firewall/.test(intent)) return SPOKEN_LIMITS.capabilityMax;
    if (/readiness/i.test(intent) || (route && route.useReadinessRun)) return SPOKEN_LIMITS.readinessMax;
    if (route && (route.useReasoning || route.useEscalation)) return SPOKEN_LIMITS.planMax;
    if (route && route.useProactiveBriefing && /make a plan|priorit/i.test(String(query || "").toLowerCase())) {
      return SPOKEN_LIMITS.planMax;
    }
    return SPOKEN_LIMITS.defaultMax;
  }

  function takeSpokenSentences(text, maxChars, maxSentences) {
    const raw = String(text || "").trim();
    if (!raw) return "";
    const sentences = raw.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [raw];
    let out = "";
    let count = 0;
    for (const sentence of sentences) {
      const piece = sentence.trim();
      if (!piece) continue;
      const next = out ? `${out} ${piece}` : piece;
      if (count >= maxSentences || next.length > maxChars) break;
      out = next;
      count++;
    }
    if (!out) out = trimAtSentence(raw, maxChars);
    return out.trim();
  }

  function toSpokenScript(displayText, query, route, meta) {
    meta = meta || {};
    let out = stripMarkdownForSpeech(displayText);
    out = stripChatbotFillers(out);
    out = out.replace(SPOKEN_DEPTH_HINT_RE, " ").trim();
    out = stripHalIdentityMonologue(out, false);
    out = spokenContractions(out);
    out = spokenNumbers(out);
    out = out.replace(/[;:—–]/g, ".").replace(/\.\.+/g, ".").trim();

    const budget = spokenBudgetFor(query, route, meta);
    let maxSentences = 3;
    if (meta.preferBrief || wantsBriefReply(query)) maxSentences = 2;
    if (/readiness/i.test(route && route.intent ? route.intent : "")) maxSentences = 2;
    if (route && (route.useReasoning || route.useEscalation)) maxSentences = 6;

    out = takeSpokenSentences(out, budget, maxSentences);

    const displayLen = String(displayText || "").trim().length;
    if (displayLen > out.length + 80 && !/on screen/i.test(out)) {
      out = out.replace(/[.!?]\s*$/, "") + ". The rest is on screen if you can read.";
    }
    return out.trim();
  }

  function stripCapabilityPrefixes(rawQuery) {
    return String(rawQuery)
      .trim()
      .replace(/^hal[,:]\s+/i, "")
      .replace(/^quick question:\s*/i, "")
      .replace(/^tell me honestly\s*[—-]\s*/i, "")
      .trim();
  }

  function describeBlockedAction(actionPhrase) {
    const a = String(actionPhrase || "").toLowerCase();
    if (/\bpost\b.*\bquickbooks\b|\bquickbooks\b.*\bpost\b/.test(a)) return "post to QuickBooks";
    if (/\bwrite\b.*\bsoftdent\b|\bsoftdent\b.*\bwrite\b/.test(a)) return "write back to SoftDent";
    if (/\b(submit|transmit)\b.*\bclaim\b|\bclaim\b.*\b(submit|transmit)\b/.test(a)) return "submit or transmit a claim";
    if (/\b(upload|portal)\b.*\bnarrative\b|\bnarrative\b.*\b(upload|portal)\b/.test(a)) return "upload a narrative to a portal";
    if (/\b(email|contact|fax)\b.*\bpayer\b|\bpayer\b.*\b(email|contact|fax)\b/.test(a)) return "contact the payer directly";
    if (/\bdelete\b.*\bclaim\b/.test(a)) return "delete a claim";
    if (/\bpush\b.*\b(live|to quickbooks)\b/.test(a)) return "push that live to the ledger";
    if (/\bpush\b.*\b(journal|entry|entries)\b.*\blive\b/.test(a)) return "push this journal entry live";
    const verb = a.match(
      /\b(submit|send|email|fax|upload|transmit|pay|delete|remove|post|write|contact|dispatch|wire)\b/,
    );
    return verb ? verb[1] + " that" : "do that external step";
  }

  function variedBlockedCapabilityReply(_legacy, actionPhrase, halData) {
    const act = describeBlockedAction(actionPhrase);
    const consent = consentPolicy(halData);
    return pickVariant([
      `Yes — I can ${act} with your explicit consent. ${consent.summary} Confirm when you are ready and I will proceed or prepare the delivery.`,
      `Yes — ${act.charAt(0).toUpperCase() + act.slice(1)} is allowed here after consent. ${consent.prompt}`,
      `Yes — I can handle ${act} once you consent. Say "I consent" or confirm the action and I will continue.`,
    ]);
  }

  function consentVerdict(query, _consentCfg, halData) {
    const cfg = consentPolicy(halData);
    const outbound = isOutboundActionPhrase(query);
    const phrase = String(query || "").trim();
    return {
      allowed: true,
      intent: outbound ? "consent: required" : "consent: local",
      text: outbound
        ? `${cfg.prompt} Proposed action: "${phrase}". Confirm consent to proceed.`
        : "Allowed — local action with no external delivery required.",
    };
  }

  function firewallVerdict(query, consentCfg, halData, halModels) {
    return consentVerdict(query, consentCfg, halData);
  }

  function wrapAllowedCapabilityReply(actionPhrase, body) {
    const act = String(actionPhrase || "that").replace(/\s+without staff approval$/i, "").trim();
    const core = String(body || "").trim();
    const intro = pickVariant([
      `Yes — I can ${act} here locally.`,
      `${act.charAt(0).toUpperCase() + act.slice(1)} is in-bounds for this program.`,
      `Yes — ${act} stays local and I can handle it now.`,
      `I can do that here. ${act.charAt(0).toUpperCase() + act.slice(1)} uses local data only.`,
    ]);
    if (!core) return intro;
    if (/^yes\b|^sure\b|^absolutely\b|^that's in-bounds/i.test(core)) return core;
    return intro + " " + core;
  }

  function parseCapabilityQuestion(rawQuery) {
    const q = stripCapabilityPrefixes(rawQuery).toLowerCase();

    let m = q.match(/^what can you not do on (?:the )?(.+?)(?:\s+page)?\??$/);
    if (m) return { kind: "page-cannot", pageHint: m[1].trim() };

    m = q.match(/^what can you do on (?:the )?(.+?)(?:\s+page)?\??$/);
    if (m) return { kind: "page-can", pageHint: m[1].trim() };

    m = q.match(/^what happens if i ask you to (.+?)\??$/);
    if (m) return { kind: "hypothetical", action: m[1].trim() };

    m = q.match(/^(?:are you allowed to|can you) (.+?)(?:\s+without staff approval)?\??$/);
    if (m) return { kind: "can", action: m[1].trim() };

    return null;
  }

  function buildPageCapabilityReply(halData, pages, pageHint, negated) {
    const pageId = findPage(pageHint.replace(/\s+page$/, ""));
    if (!pageId) return null;
    const reg = registryById(halData, pageId);
    const info = pageInfoMap(halData, pages)[pageId] || { label: pageId, detail: "" };
    const label = info.label || pageId;
    const status = reg ? `${reg.state}. Safety: ${reg.safety}. Next: ${reg.nextAction}` : "review-only locally.";
    if (negated) {
      return {
        intent: "capability:page-limits",
        lane: "local",
        text: pickVariant([
          `On ${label}, I won't post, submit, email, or write back — ${reg?.safety || "review-only"}. I can explain what's here and prep notes for staff. Obviously.`,
          `${label} is read-only for me. No external delivery from that page; I flag gaps and tell staff what to do next (${status}).`,
          `I don't change outside systems from ${label}. I navigate, explain imported data, and draft local review — humans own outbound actions.`,
        ]),
        actions: pageId === "hal" ? [] : [{ type: "openPage", label: "Open " + label, page: pageId }],
      };
    }
    return {
      intent: "capability:page-can",
      lane: "local",
      text: pickVariant([
        `On ${label}, I open the page, walk through ${info.detail || "local data"}, and call out what's missing — ${status}`,
        `${label}: I explain ${info.detail || "what staff see here"}, compare imports, and tell you the next review step. ${status}`,
        `For ${label}, I'm your read-only guide — ${info.detail || "local views only"}. Current posture: ${status}. You're welcome.`,
      ]),
      actions: pageId === "hal" ? [] : [{ type: "openPage", label: "Open " + label, page: pageId }],
    };
  }

  function capabilityLocalFlagsForAction(action, halData, halModels) {
    const a = String(action || "").toLowerCase();
    const firewall = (halData && halData.firewall) || FALLBACK_FIREWALL;
    if (/make a plan|plan for today|show what needs attention|what needs attention today/.test(a)) {
      return { intent: "capability:plan", lane: "local", useProactiveBriefing: true, text: "", actions: [] };
    }
    if (/readiness check|run readiness/.test(a)) {
      return { intent: "capability:readiness", lane: "local", useReadinessRun: true, text: "", actions: [] };
    }
    if (/refresh imports|import status|show import status|review import diagnostics|import diagnostics/.test(a)) {
      const refresh = /\brefresh\b/.test(a);
      return refresh
        ? { intent: "capability:imports-refresh", lane: "local", useImportRefresh: true, text: "", actions: [] }
        : { intent: "capability:imports-status", lane: "local", useImportStatus: true, text: "", actions: [] };
    }
    if (/manager dashboard widgets|show manager dashboard/.test(a)) {
      return { intent: "capability:widgets", lane: "local", useWidgetFeed: true, text: "", actions: [] };
    }
    if (/claim packet readiness|check claim packet readiness/.test(a)) {
      return { intent: "capability:claims-packet", lane: "local", useClaimReadiness: true, text: "", actions: [] };
    }
    if (/draft a journal entry locally|journal entry locally/.test(a)) {
      return { intent: "capability:journal-draft", lane: "local", useJournalDraft: true, text: "", actions: [] };
    }
    if (/monitor sidenotes/.test(a)) {
      return { intent: "capability:sidenotes", lane: "local", useSideNoteMonitor: true, text: "", actions: [] };
    }
    if (/posting queue items|show posting queue|list posting queue|journal queue items|show journal queue/.test(a)) {
      return { intent: "capability:posting-queue", lane: "local", usePostingQueueList: true, text: "", actions: [] };
    }
    if (/search the document library|search document library/.test(a)) {
      return { intent: "capability:library-search", lane: "local", useDocRag: true, ragQuestion: action, text: "", actions: [] };
    }
    if (/explain (the )?(staff )?consent|consent policy|external action consent/.test(a)) {
      const cfg = consentPolicy(halData);
      return {
        intent: "capability:consent",
        lane: "local",
        text: pickVariant([
          `${cfg.summary} Categories: ${(cfg.categories || []).join(", ")}.`,
          `${cfg.prompt} ${cfg.summary}`,
          `Consent is required per action — not a firewall. ${cfg.summary}`,
        ]),
        actions: [],
      };
    }

    if (/explain the firewall|external action firewall/.test(a)) {
      return {
        intent: "capability:consent",
        lane: "local",
        text: "The external-action firewall has been removed. HAL uses a staff consent policy instead — email, submit, post, and upload require your explicit consent for each action.",
        actions: [],
      };
    }
    return null;
  }

  function matchMixedCapabilityQuestion(halData, pages, rawQuery) {
    const q = stripCapabilityPrefixes(rawQuery).toLowerCase();
    const firewall = (halData && halData.firewall) || FALLBACK_FIREWALL;

    if (/\b(who|staff|human|office)\b.*\b(submit|transmit|send|post)\b.*\bpayer/i.test(q) || /\bwho\b.*\bsubmit.*\bpayer/i.test(q)) {
      return {
        intent: "capability:external-review",
        lane: "local",
        text: pickVariant([
          "Staff submits to payers — not HAL. I prepare claims review, narratives, and packet readiness locally; a human transmits outside this program.",
          "Payer submission is always staff-owned. I can open Claims, explain packet readiness, and draft notes — I never transmit.",
          "No — I don't submit to payers. Your team reviews my local drafts and sends through SoftDent or the payer portal.",
        ]),
        actions: [{ type: "openPage", label: "Open Claims Workbench", page: "claims" }],
      };
    }

    if (/\bregistry items need review\b/.test(q)) {
      const waiting = registryByState(halData, /needs review/i);
      const list = waiting.map((entry) => `- ${entry.name} (${entry.state}): ${entry.nextAction}`).join("\n");
      return {
        intent: "capability:registry-review",
        lane: "local",
        text: pickVariant([
          waiting.length
            ? `These registry items need review:\n${list}`
            : "Nothing in the registry is flagged needs-review right now.",
          waiting.length
            ? `Needs-review queue:\n${list}`
            : "Registry looks clear — no items waiting on review.",
        ]),
        actions: waiting.map((entry) => ({ type: "openPage", label: "Open " + entry.name, page: entry.id })),
      };
    }

    if (/\bare imports current\b/.test(q)) {
      return {
        intent: "capability:imports-current",
        lane: "local",
        useImportStatus: true,
        text: "",
        actions: [],
      };
    }

    if (/\bdo you control widgets\b/.test(q)) {
      return {
        intent: "capability:widgets-control",
        lane: "local",
        useWidgetFeed: true,
        text: "",
        actions: [],
      };
    }

    if (/\bwho must review external actions\b/.test(q)) {
      return {
        intent: "capability:external-review",
        lane: "local",
        text: pickVariant([
          "Staff with authority over that workflow — usually the owner or office manager. I stop at the firewall; a named person approves anything outbound.",
          "A human on your team, not me. I prep and explain; whoever owns claims, accounting, or payer contact takes the external step after review.",
          "Always a person. The firewall blocks HAL from submit, email, upload, or post — your staff reviews my notes and executes outside the program.",
        ]),
        actions: [],
      };
    }

    if (/\b(browser preview|preview mode)\b/.test(q)) {
      return {
        intent: "capability:browser-preview",
        lane: "local",
        text: pickVariant([
          "On http://127.0.0.1 I have full loopback access — imports, practice pulls, widgets, and SQLite storage through the NR2 server. File:// preview and remote hosts still need Start Program.",
          "Loopback mode at 127.0.0.1 gives HAL the same data access as the desktop shell. Agent patch tools and clipboard still need the pywebview app.",
          "Browser preview on file:// is UI-only. Open http://127.0.0.1:8765 or Start Program for live imports and autonomous placement.",
        ]),
        actions: [],
      };
    }

    if (/\bwhat is blocked today\b/.test(q)) {
      const blocked = registryByState(halData, /blocked/i);
      const list = blocked.map((entry) => `- ${entry.name}: ${entry.nextAction}`).join("\n");
      return {
        intent: "capability:blocked-today",
        lane: "local",
        text: blocked.length
          ? pickVariant([
              `Blocked today:\n${list}`,
              `These are blocked right now:\n${list}`,
            ])
          : pickVariant([
              "Nothing is marked blocked in the registry today.",
              "No blocked registry items — check needs-review if you're hunting for work.",
            ]),
        actions: blocked.map((entry) => ({ type: "openPage", label: "Open " + entry.name, page: entry.id })),
      };
    }

    if (/\bwhat do you need from staff\b/.test(q)) {
      return { intent: "capability:job-requirements", lane: "local", useHalJobRequirements: true, text: "", actions: [] };
    }

    if (/\bwhat is your top priority\b/.test(q)) {
      return { intent: "capability:priority", lane: "local", useProactiveBriefing: true, text: "", actions: [] };
    }

    if (/\bwhat happens if data is missing\b/.test(q)) {
      return {
        intent: "capability:missing-data",
        lane: "local",
        text: pickVariant([
          "I say what's missing, which import or page to check, and I won't invent numbers. Staff verifies SoftDent and QuickBooks before acting.",
          "No guessing — I flag the gap, point to the source health panel, and recommend the next safe verification step.",
          "Missing data means I stay in review mode: name the blank field, suggest which collector to run, and wait for staff confirmation.",
        ]),
        actions: [],
      };
    }

    if (/\bsee softdent production\b/.test(q)) {
      return { intent: "capability:softdent-production", lane: "local", useSourceHealth: true, text: "", actions: [] };
    }

    return null;
  }

  function isPolicyCanYouProbe(rawQuery, action) {
    const raw = stripCapabilityPrefixes(rawQuery).toLowerCase();
    const act = String(action || "").toLowerCase();
    if (/^are you allowed to /.test(raw)) return true;
    if (/without staff approval/.test(raw)) return true;
    if (/^tell me honestly/.test(String(rawQuery).toLowerCase())) return true;
    if (isOutboundActionPhrase(act) || isOutboundActionPhrase(rawQuery)) return true;
    return false;
  }

  function isOperationalPassthrough(inner, action) {
    if (!inner || !inner.intent) return false;
    if (inner.intent === "help") return true;
    if (/^(readiness:|session:|print:|operator:|packet:|imports:|ops:)/.test(inner.intent)) return true;
    if (
      inner.useReadinessRun ||
      inner.useReadinessClear ||
      inner.useSessionStart ||
      inner.usePacketBuild ||
      inner.usePrint
    ) {
      return true;
    }
    return /^(run |start |clear |reset |print |build |check hal|self-check|readiness)/i.test(String(action || ""));
  }

  function matchCapabilityRoute(halData, halModels, pages, rawQuery) {
    const mixed = matchMixedCapabilityQuestion(halData, pages, rawQuery);
    if (mixed) return mixed;

    const parsed = parseCapabilityQuestion(rawQuery);
    if (!parsed) return null;

    const consent = consentPolicy(halData);

    if (parsed.kind === "page-can") {
      return buildPageCapabilityReply(halData, pages, parsed.pageHint, false);
    }
    if (parsed.kind === "page-cannot") {
      return buildPageCapabilityReply(halData, pages, parsed.pageHint, true);
    }

    if (parsed.kind === "can" && !isPolicyCanYouProbe(rawQuery, parsed.action)) {
      return null;
    }

    const action = parsed.action || "";
    const actionNeedsConsent = isOutboundActionPhrase(action) || isOutboundActionPhrase(rawQuery);

    if (parsed.kind === "hypothetical" || (parsed.kind === "can" && actionNeedsConsent)) {
      return {
        intent: "capability:consent-required",
        lane: "local",
        text: variedBlockedCapabilityReply(consent, action, halData),
        actions: [],
      };
    }

    if (parsed.kind === "can") {
      const localFlags = capabilityLocalFlagsForAction(action, halData, halModels);
      if (localFlags) return localFlags;

      const inner = routeHalCommand(halData, halModels, pages, action, { capabilityInner: true });
      if (isOperationalPassthrough(inner, action)) return inner;

      if (inner.useModel || inner.useReasoning || inner.useEscalation || inner.useOss) {
        const pageId = findPage(action);
        if (pageId) {
          const nav = routeHalCommand(halData, halModels, pages, "open " + pageId.replace(/-/g, " "), {
            capabilityInner: true,
          });
          if (nav.text) {
            return Object.assign({}, nav, {
              intent: "capability:" + nav.intent,
              text: wrapAllowedCapabilityReply(action, nav.text),
            });
          }
        }
        return {
          intent: "capability:allowed-fallback",
          lane: "local",
          text: wrapAllowedCapabilityReply(action, "I handle that locally; outbound delivery needs your consent."),
          actions: [],
        };
      }
      if (inner.text) {
        return Object.assign({}, inner, {
          intent: "capability:" + (inner.intent || "allowed"),
          text: wrapAllowedCapabilityReply(action, inner.text),
        });
      }
      if (
        inner.useImportRefresh ||
        inner.useImportStatus ||
        inner.useReadinessRun ||
        inner.useProactiveBriefing ||
        inner.useWidgetFeed ||
        inner.useClaimReadiness ||
        inner.useJournalDraft ||
        inner.useSideNoteMonitor ||
        inner.useSideNoteList ||
        inner.useTaskList ||
        inner.usePostingQueueList ||
        inner.useDocRag ||
        inner.useReadinessShow ||
        inner.useSourceHealth
      ) {
        return Object.assign({}, inner, { intent: "capability:" + (inner.intent || "tool") });
      }
    }

    return null;
  }

  function registryAsText(halData) {
    return registryList(halData)
      .map((entry) => `- ${entry.name} [${entry.state}; ${entry.safety}]: ${entry.purpose} Next: ${entry.nextAction}`)
      .join("\n");
  }

  function verifiedSoftdentArAvailable(snapshot) {
    const skills =
      typeof HalSkills !== "undefined"
        ? HalSkills
        : typeof globalThis !== "undefined" && globalThis.HalSkills
          ? globalThis.HalSkills
          : typeof window !== "undefined" && window.HalSkills
            ? window.HalSkills
            : null;
    if (skills && typeof skills.softDentReadSourceStatus === "function") {
      return skills.softDentReadSourceStatus(snapshot).arAvailable;
    }
    const snap = snapshot || {};
    const bundle = snap.importBundle || {};
    const ar = snap.dashboards && snap.dashboards.ar;
    const arRows = (bundle.softdent && bundle.softdent.ar && bundle.softdent.ar.rows) || [];
    return !!(
      (ar &&
        ((Array.isArray(ar.buckets) && ar.buckets.length) ||
          (Array.isArray(ar.aging) && ar.aging.length) ||
          ar.total)) ||
      arRows.length > 0
    );
  }

  function summarizeProgramSnapshot(snapshot, halData) {
    if (!snapshot) return registryAsText(halData);
    const lines = [];
    const access = (halData && halData.programAccess) || {};
    lines.push(
      (access.mode === "full-read" ? "FULL PROGRAM READ ACCESS" : "PROGRAM SNAPSHOT") +
        " (local only · " +
        (snapshot.label || "import/persisted data") +
        "):",
    );
    const fin = snapshot.dashboards && snapshot.dashboards.financial;
    if (fin) {
      const metricValue = (re) => ((fin.metrics || []).find((m) => re.test(String(m.label || ""))) || {}).value || "—";
      const ebitdaMetric = (fin.metrics || []).find((m) => /ebitda/i.test(String(m.label || "")));
      const finParts = [
        `production ${fin.productionMtd?.value || "—"}`,
        `collections ${metricValue(/collections/i)}`,
        `QB revenue ${metricValue(/quickbooks revenue|revenue/i)}`,
        `QB net income ${metricValue(/net income/i)}`,
      ];
      if (ebitdaMetric) finParts.push(`EBITDA ${ebitdaMetric.value || "—"}`);
      if (fin.quality?.score) finParts.push(`quality ${fin.quality.score}/100`);
      lines.push(`Financial (${fin.dateRange || "current"}): ${finParts.join(", ")}`);
      lines.push(
        "Source boundary: SoftDent = practice ops (production, claims, dental A/R). QuickBooks = accounting GL (revenue, expenses, P&L). Totals are related but not interchangeable.",
      );
      if (fin.payerMix?.slices?.length) {
        lines.push(
          "Payer mix: " +
            fin.payerMix.slices
              .slice(0, 5)
              .map((s) => `${s.label} ${s.pct}%`)
              .join(", "),
        );
      }
    }
    const sd = snapshot.dashboards && snapshot.dashboards.softdent;
    if (sd) {
      const sdProd = (sd.glance || []).find((g) => g.label === "Production MTD");
      const sdColl = (sd.glance || []).find((g) => g.label === "Collections MTD");
      const arAvailable = verifiedSoftdentArAvailable(snapshot);
      lines.push(
        `SoftDent: A/R ${arAvailable ? sd.hero?.value || "—" : "—"}, production ${sdProd?.value || "—"}, collections ${sdColl?.value || "—"}, status ${sd.status || "—"}`,
      );
    }
    const qb = snapshot.dashboards && snapshot.dashboards.quickbooks;
    if (qb) {
      const qbRev = (qb.pl?.rows || []).find((r) => r.category === "Revenue");
      const qbNet = (qb.pl?.rows || []).find((r) => r.category === "Net Income");
      lines.push(
        `QuickBooks: revenue ${qbRev?.amount || "—"}, net income ${qbNet?.amount || "—"}, sync ${qb.syncStatus || "—"}`,
      );
    }
    const ar = snapshot.dashboards && snapshot.dashboards.ar;
    if (ar) {
      const arAvailable = verifiedSoftdentArAvailable(snapshot);
      lines.push(
        `A/R: outstanding ${arAvailable ? ar.kpis?.[0]?.value || "—" : "—"}, follow-up lanes ${(ar.followUp || []).length}, top claims ${(ar.topClaims || []).length}`,
      );
    }
    if (snapshot.claims) {
      const statusText = Object.entries(snapshot.claims.byStatus || {})
        .map(([k, v]) => `${k}: ${v}`)
        .join(", ");
      lines.push(`Claims workbench: ${snapshot.claims.total} claims (${statusText})`);
      (snapshot.claims.top || []).slice(0, 5).forEach((c) => {
        lines.push(`  - ${c.id} · ${c.patient} · ${c.procedure} · ${c.amount} · ${c.status}`);
      });
    }
    if (snapshot.narratives) {
      lines.push(
        `Narratives: ${snapshot.narratives.drafts} drafts · focus ${snapshot.narratives.focus || "—"} · latest ${snapshot.narratives.latest?.version || "none"}`,
      );
    }
    if (snapshot.documents) {
      lines.push(`Documents (${snapshot.documents.entity || "entity"}): ${snapshot.documents.queueCount} in queue`);
      if (snapshot.documents.sourceCounts) {
        const counts = snapshot.documents.sourceCounts;
        lines.push(
          `  Sources: QuickBooks ${counts.quickbooks || 0}, SoftDent ${counts.softdent || 0}, OCR ${counts.ocr || 0}, manual ${counts.manual || 0}`,
        );
      }
      (snapshot.documents.posting || []).forEach((p) => lines.push(`  - ${p.label}: ${p.count}`));
      (snapshot.documents.top || []).slice(0, 4).forEach((d) => {
        const source = d.sourceSystem ? ` · ${d.sourceSystem}` : "";
        lines.push(`  - ${d.id} · ${d.vendor} · ${d.amount} · ${d.status}${source}`);
      });
    }
    if (snapshot.library) {
      lines.push(`Library: ${snapshot.library.results} documents indexed`);
      (snapshot.library.top || []).slice(0, 4).forEach((d) => {
        lines.push(`  - ${d.title} · ${d.type} · ${d.updated}`);
      });
    }
    if (snapshot.sideNotes) {
      const sn = snapshot.sideNotes;
      const mon = sn.monitor || {};
      lines.push(
        `Sidenotes (HAL monitor): ${sn.activeCount ?? sn.total ?? 0} active · ${mon.openCount ?? "—"} open · ${mon.pinnedCount ?? "—"} pinned · ${mon.highPriorityCount ?? "—"} high priority`,
      );
      (sn.top || []).slice(0, 5).forEach((n) => {
        lines.push(`  - [${n.status}/${n.priority}] ${n.text}`);
      });
    }
    if (snapshot.widgets) {
      const summarize =
        typeof HalSkills !== "undefined" && HalSkills.summarizeWidgetFeed ? HalSkills.summarizeWidgetFeed : null;
      if (summarize) {
        lines.push("Manager widgets (HAL):");
        summarize(snapshot.widgets)
          .split("\n")
          .forEach((line) => {
            if (line) lines.push(`  ${line}`);
          });
      }
    }
    lines.push("Registry status:");
    lines.push(registryAsText(halData));
    if (halData.sources && halData.sources.items && halData.sources.items.length) {
      lines.push(
        "Source intake:",
        ...(halData.sources.items || []).map((s) => `- ${s.label}: ${s.status} · ${s.freshness} · ${s.syncState || "unknown"}`),
      );
    }
    return lines.join("\n").slice(0, 14000);
  }

  function formatProgramSnapshot(snapshot, halData) {
    return summarizeProgramSnapshot(snapshot, halData) + "\n\n(Full program read access · local only · verify before acting)";
  }

  function matchProgramRoute(query) {
    if (
      /\b(program (data|access|snapshot|status)|full program|all program data|read the program|what data do you have|show program)\b/.test(
        query,
      )
    ) {
      return { type: "snapshot" };
    }
    return null;
  }

  function parseJournalRequest(rawQuery) {
    const text = String(rawQuery || "");
    const amountMatch = text.replace(/,/g, "").match(/\$?\s*(\d+(?:\.\d{1,2})?)/);
    const amount = amountMatch ? parseFloat(amountMatch[1]) : null;
    const periodMatch = text.match(/\b(\d{4}-\d{2})\b/);
    const period = periodMatch ? periodMatch[1] : "2025-05";
    return { description: text, amount: amount, period: period };
  }

  // Skill routing — ported HAL capabilities (accounting, claim readiness,
  // office-manager attention + tasks). All local, read/draft-only.
  function matchSkillRoute(query, rawQuery) {
    // Accounting: draft a journal entry (drafting only; posting stays blocked by firewall)
    if (/\b(draft|prepare|create|build)\b.*\bjournal\b|\bjournal entry\b/.test(query) && !/\bpost\b/.test(query)) {
      const parsed = parseJournalRequest(rawQuery);
      return {
        intent: "accounting: journal-draft",
        lane: "local",
        useJournalDraft: true,
        journalRequest: parsed,
        text: "",
        actions: [],
      };
    }

    // Claim packet readiness
    if (/\b(claim|packet)\b.*\breadiness\b|\breadiness\b.*\b(claim|packet)\b|\bclaim packet\b/.test(query)) {
      return { intent: "claims: readiness", lane: "local", useClaimReadiness: true, text: "", actions: [] };
    }

    // Office-manager attention
    if (/\boffice[\s-]?manager\b/.test(query) && !/\btask\b/.test(query)) {
      return { intent: "office: attention", lane: "local", useOfficeAttention: true, text: "", actions: [] };
    }

    // Sidenotes: monitor
    if (/\b(monitor|watch|check|status)\b.*\bsidenotes?\b|\bsidenotes?\b.*\b(monitor|watch|status)\b/.test(query)) {
      return { intent: "sidenotes: monitor", lane: "local", useSideNoteMonitor: true, text: "", actions: [] };
    }

    // Sidenotes: list
    if (/\b(show|list|view)\b.*\bsidenotes?\b|\bsidenotes?\b.*\b(list|open)\b/.test(query)) {
      return { intent: "sidenotes: list", lane: "local", useSideNoteList: true, text: "", actions: [] };
    }

    // Sidenotes: create
    const sideNoteMatch =
      String(rawQuery || "").match(/\b(?:add|create|new|make)\s+sidenote\b[:\-\s]*(.*)$/i) ||
      String(rawQuery || "").match(/\bsidenote\b[:\-\s]+(.*)$/i);
    if (sideNoteMatch) {
      return {
        intent: "sidenotes: create",
        lane: "local",
        useSideNoteCreate: true,
        sideNoteText: sideNoteMatch[1].trim(),
        text: "",
        actions: [],
      };
    }

    // Office tasks: list
    if (/\b(show|list|view|my)\b.*\btasks?\b|\btasks?\b.*\b(list|open|status)\b/.test(query)) {
      return { intent: "tasks: list", lane: "local", useTaskList: true, text: "", actions: [] };
    }

    // Office tasks: create
    const createTaskMatch = String(rawQuery || "").match(/\b(?:create|add|new|make)\s+(?:a\s+)?task\b[:\-\s]*(.*)$/i);
    if (createTaskMatch) {
      const title = createTaskMatch[1].trim();
      return {
        intent: "tasks: create",
        lane: "local",
        useTaskCreate: true,
        taskTitle: title,
        text: "",
        actions: [],
      };
    }

    // Manager dashboard widgets (import-cache widget feed)
    if (
      /\b(period|periods|time period|month)\b.*\b(widget|need|require|data|coverage)\b/.test(query) ||
      /\bwhat periods\b.*\b(widget|need|require)\b/.test(query) ||
      /\bwidget period requirements\b/.test(query)
    ) {
      return { intent: "periods: widget-requirements", lane: "local", useWidgetPeriodRequirements: true, text: "", actions: [] };
    }
    if (/\b(source trace|trace widgets?|widget trace|diagnostic trace|diagnose widgets?|trace (the )?sources?)\b/.test(query)) {
      return { intent: "widgets: source-trace", lane: "local", useWidgetGuidance: true, widgetGuidance: "sourceTrace", text: "", actions: [] };
    }
    if (/\bmissing data\b.*\bwidgets?\b|\bwidgets?\b.*\bmissing data\b|\bmissing\b.*\bby widget\b/.test(query)) {
      return { intent: "widgets: missing-data", lane: "local", useWidgetGuidance: true, widgetGuidance: "missingData", text: "", actions: [] };
    }
    if (/\b(widget master chart|master widget chart|all widgets chart|widget map|widget guide|where\b.*widgets?\b.*\bdata)\b/.test(query)) {
      return { intent: "widgets: master-chart", lane: "local", useWidgetMasterChart: true, text: "", actions: [] };
    }
    if (/\bwidget contract\b|\bwhat does\b.*\bwidget\b.*\bneed\b|\bwhich dataset\b.*\bwidget\b|\bwhich field\b.*\bwidget\b|\bdata source\b.*\bwidget\b/.test(query)) {
      return { intent: "widgets: contract", lane: "local", useWidgetContract: true, text: "", actions: [] };
    }
    if (/\bprioriti[sz]e\b.*\bwidgets?\b|\bwidgets?\b.*\b(fill first|priority|prioriti[sz]e)\b/.test(query)) {
      return { intent: "widgets: fill-priority", lane: "local", useWidgetGuidance: true, widgetGuidance: "fillPriority", text: "", actions: [] };
    }
    if (/\bimport checklist\b|\bchecklist\b.*\b(imports?|softdent|quickbooks)\b/.test(query)) {
      return { intent: "imports: checklist", lane: "local", useWidgetGuidance: true, widgetGuidance: "importChecklist", text: "", actions: [] };
    }
    if (/\bdata quality\b.*\b(recommend|check|review)|\bcheck\b.*\bdata quality\b/.test(query)) {
      return { intent: "data-quality: check", lane: "local", useWidgetGuidance: true, widgetGuidance: "dataQuality", text: "", actions: [] };
    }
    if (/\bwhy\b.*\bwidgets?\b.*\b(empty|blank|missing|incomplete)\b|\bexplain\b.*\bwidgets?\b.*\b(empty|blank|missing|incomplete)\b/.test(query)) {
      return { intent: "widgets: explain-empty", lane: "local", useWidgetGuidance: true, widgetGuidance: "explainEmpty", prompt: rawQuery, text: "", actions: [] };
    }
    if (/\bdaily owner briefing\b|\bowner briefing\b/.test(query)) {
      return { intent: "briefing: owner-daily", lane: "local", useWidgetGuidance: true, widgetGuidance: "dailyOwnerBriefing", text: "", actions: [] };
    }
    if (/\bdaily office briefing\b|\boffice manager briefing\b|\boffice briefing\b/.test(query)) {
      return { intent: "briefing: office-daily", lane: "local", useOfficeBriefing: true, text: "", actions: [] };
    }
    if (/\baccounting review queue\b|\bshow accounting review\b|\bquickbooks\b.*\bdocuments\b.*\breview\b/.test(query)) {
      return { intent: "accounting: review-queue", lane: "local", useWidgetGuidance: true, widgetGuidance: "accountingReviewQueue", text: "", actions: [] };
    }
    if (
      /\b(show|list|view|can you show)\b.*\b(posting queue|journal posting queue|journal queue)\b|\b(posting queue|journal posting queue|journal queue)\b.*\b(items?|entries|list|status)\b/.test(
        query,
      )
    ) {
      return { intent: "accounting: posting-queue-list", lane: "local", usePostingQueueList: true, text: "", actions: [] };
    }
    if (
      /\breconciliation checklist\b|\bsoftdent\b.*\bquickbooks\b.*\breconcil|\baccounting reconciliation\b|\breconcile\b.*\b(softdent|quickbooks)\b/.test(
        query,
      )
    ) {
      return {
        intent: "accounting: reconciliation-checklist",
        lane: "local",
        useWidgetGuidance: true,
        widgetGuidance: "accountingReconciliationChecklist",
        text: "",
        actions: [],
      };
    }
    if (/\b(document workbook|work documents|excel documents|accounting documents workbook|work the documents)\b/.test(query)) {
      return { intent: "documents: excel-workbook", lane: "local", useWidgetGuidance: true, widgetGuidance: "documentExcelWorkbook", text: "", actions: [] };
    }
    if (/\bexcel\b.*\breconciliation\b|\breconciliation\b.*\bexcel\b|\bexcel-style reconciliation\b/.test(query)) {
      return { intent: "reconciliation: excel-style", lane: "local", useWidgetGuidance: true, widgetGuidance: "excelReconciliation", text: "", actions: [] };
    }
    if (
      /\b(fill|populate|complete)\b.*\b(all\s+)?(widgets?|dashboard widgets|manager dashboard)\b/.test(query) ||
      /\b(suggest|suggestions?|recommend)\b.*\b(fill|populate|complete)\b.*\b(widgets?|dashboard widgets)\b/.test(query) ||
      /\b(suggest|suggestions?|recommend)\b.*\b(widgets?|dashboard widgets)\b/.test(query)
    ) {
      return { intent: "widgets: fill-suggestions", lane: "local", useWidgetFillSuggestions: true, text: "", actions: [] };
    }
    const widgetRoutes = [
      { pattern: /\b(financial overview|practice financial|financial)\b.*\bwidget\b|\bwidget\b.*\b(financial overview|practice financial|financial)\b/, key: "practiceFinancialOverview" },
      { pattern: /\b(production trend|ytd production|production mtd)\b.*\bwidget\b|\bwidget\b.*\b(production trend|ytd production)\b/, key: "financialProductionTrend" },
      { pattern: /\b(payer mix|collection rate|collections mix)\b.*\bwidget\b|\bwidget\b.*\b(payer mix|collection rate)\b/, key: "payerMixAndCollections" },
      { pattern: /\b(provider performance|provider production|provider breakdown)\b.*\bwidget\b|\bwidget\b.*\b(provider performance|provider production)\b/, key: "providerPerformance" },
      { pattern: /\b(data freshness|data quality|quality score)\b.*\bwidget\b|\bwidget\b.*\b(data freshness|data quality|quality score)\b/, key: "practiceFinancialOverview" },
      { pattern: /\b(ebitda|normalization|add-?back)\b.*\bwidget\b|\bwidget\b.*\b(ebitda|normalization|add-?back)\b/, key: "ebitdaNormalization" },
      { pattern: /\b(p&l|profit and loss|gross profit|cogs)\b.*\bwidget\b|\bwidget\b.*\b(p&l|profit and loss|gross profit|cogs)\b/, key: "quickbooksProfitLossDetail" },
      { pattern: /\b(quickbooks|qb)\b.*\b(sync|widget)\b|\bwidget\b.*\b(quickbooks|qb)\b.*\bsync\b|\bsync\b.*\bwidget\b.*\bquickbooks\b/, key: "quickbooksProfitLossDetail" },
      { pattern: /\b(accounts payable|a\/?p(?: automation)?)\b.*\bwidget\b|\bwidget\b.*\b(accounts payable|a\/?p)\b/, key: "accountsPayableAutomation" },
      { pattern: /\b(document intake|intake queue|document queue)\b.*\bwidget\b|\bwidget\b.*\b(document intake|intake queue|document queue)\b/, key: "documentIntakeQueue" },
      { pattern: /\b(document preview|selected document|invoice preview)\b.*\bwidget\b|\bwidget\b.*\b(document preview|selected document|invoice preview)\b/, key: "documentPreview" },
      { pattern: /\b(period close|posting review|posting queue|journal entries?)\b.*\bwidget\b|\bwidget\b.*\b(period close|posting|journal entries?)\b/, key: "periodCloseAndPosting" },
      { pattern: /\b(journal posting queue|journal queue)\b.*\bwidget\b|\bwidget\b.*\b(journal posting queue|journal queue)\b/, key: "journalPostingQueue" },
      { pattern: /\b(claims pipeline|claim pipeline|kanban|claim lanes)\b.*\bwidget\b|\bwidget\b.*\b(claims pipeline|claim pipeline|kanban|claim lanes)\b/, key: "claimsPipeline" },
      { pattern: /\b(claims|receivables)\b.*\bwidget\b|\bwidget\b.*\b(claims|receivables)\b/, key: "smartClaimsAndReceivables" },
      { pattern: /\b(claim readiness|safety posture|safety)\b.*\bwidget\b|\bwidget\b.*\b(claim readiness|safety)\b/, key: "claimsPipeline" },
      { pattern: /\b(a\/?r aging|collections|follow-?up queue)\b.*\bwidget\b|\bwidget\b.*\b(a\/?r aging|collections)\b/, key: "arAgingAndCollections" },
      { pattern: /\b(top outstanding|outstanding claims|top claims)\b.*\bwidget\b|\bwidget\b.*\b(top outstanding|outstanding claims|top claims)\b/, key: "arOutstandingClaims" },
      { pattern: /\b(care delivery|clinical(?: performance)?)\b.*\bwidget\b|\bwidget\b.*\b(care delivery|clinical)\b/, key: "careDeliveryPerformance" },
      { pattern: /\b(softdent aging|daysheet aging|softdent a\/?r)\b.*\bwidget\b|\bwidget\b.*\b(softdent aging|daysheet aging|softdent a\/?r)\b/, key: "softdentArAging" },
      { pattern: /\b(insurance vs patient|patient responsibility|insurance responsibility|responsibility split)\b.*\bwidget\b|\bwidget\b.*\b(insurance vs patient|patient responsibility|responsibility split)\b/, key: "softdentResponsibility" },
      { pattern: /\b(softdent source health|softdent health|source health)\b.*\bwidget\b|\bwidget\b.*\b(softdent source health|softdent health|source health)\b/, key: "careDeliveryPerformance" },
      { pattern: /\b(softdent exports?|export history)\b.*\bwidget\b|\bwidget\b.*\b(softdent exports?|export history)\b/, key: "careDeliveryPerformance" },
      { pattern: /\b(narrative|narratives|insurance narrative)\b.*\bwidget\b|\bwidget\b.*\b(narrative|narratives|insurance narrative)\b/, key: "narrativeWorkflow" },
      { pattern: /\b(document library|library|indexed documents|storage)\b.*\bwidget\b|\bwidget\b.*\b(document library|library|indexed documents|storage)\b/, key: "documentLibrary" },
    ];
    for (const route of widgetRoutes) {
      if (route.pattern.test(query)) {
        return { intent: `widgets: show:${route.key}`, lane: "local", useWidgetShow: true, widgetKey: route.key, text: "", actions: [] };
      }
    }
    if (/\b(widgets?|widget feed|dashboard widgets|manager dashboard)\b/.test(query)) {
      return { intent: "widgets: feed", lane: "local", useWidgetFeed: true, text: "", actions: [] };
    }

    if (
      /\b(document library|library)\b.*\b(compliance|policy|support|questions?)\b/.test(query) ||
      /\bcompliance\b.*\b(library|document)\b/.test(query)
    ) {
      return { intent: "library: ask", lane: "local", useDocRag: true, ragQuestion: rawQuery, text: "", actions: [] };
    }

    // Document RAG / library retrieval (grounded, local-only)
    const ragAsk =
      /\b(search|find|look ?up|query)\b.*\b(librar|document|file|doc)/.test(query) ||
      /\b(documents?|library|files?)\b.*\b(say|mention|contain|about)\b/.test(query) ||
      /\bask (the )?(documents?|library)\b/.test(query);
    if (ragAsk && !/\b(open|go to|navigate)\b/.test(query)) {
      return { intent: "library: ask", lane: "local", useDocRag: true, ragQuestion: rawQuery, text: "", actions: [] };
    }

    return null;
  }

  function matchPrintRoute(query, rawQuery) {
    if (/\b(fingerprint|blueprint|print queue|printer queue)\b/.test(query)) return null;
    if (!/\bprint\b/.test(query)) return null;

    const base = { lane: "local", usePrint: true, text: "", actions: [] };

    if (/\b(snapshot|program snapshot)\b/.test(query)) {
      return { ...base, intent: "print: snapshot", printScope: "snapshot" };
    }
    if (/\b(drawer|side panel|command center panel)\b/.test(query)) {
      return { ...base, intent: "print: drawer", printScope: "drawer" };
    }
    if (/\b(last (?:hal )?(?:reply|response|answer)|hal reply|hal response)\b/.test(query)) {
      return { ...base, intent: "print: hal-reply", printScope: "hal-reply" };
    }
    if (/\b(current page|this page|the page|page view|screen)\b/.test(query) || /\bprint\s+(?:the\s+)?page\b/.test(query)) {
      return { ...base, intent: "print: page", printScope: "page" };
    }

    const pseudoQuery = query.replace(/\bprint\b/g, "show");
    const skill = matchSkillRoute(pseudoQuery, rawQuery);
    if (skill && skill.useWidgetShow && skill.widgetKey) {
      return { ...base, intent: `print: widget:${skill.widgetKey}`, printScope: "widget", widgetKey: skill.widgetKey };
    }
    if (skill && skill.useWidgetFeed) {
      return { ...base, intent: "print: widget-feed", printScope: "widget-feed" };
    }
    if (skill && skill.useProgramSnapshot) {
      return { ...base, intent: "print: snapshot", printScope: "snapshot" };
    }

    const textMatch = String(rawQuery || "").match(/\bprint\b[:\s]+([\s\S]+)$/i);
    if (textMatch && textMatch[1].trim()) {
      return { ...base, intent: "print: text", printScope: "text", printText: textMatch[1].trim() };
    }

    return { ...base, intent: "print: auto", printScope: "auto", prompt: rawQuery };
  }

  function modelLanesText(halModels) {
    const lanes = modelLanes(halModels);
    const anyReady = lanes.some((lane) => laneReady(halModels, lane.id));
    const header = anyReady
      ? "Model lanes (local-only; firewall runs before every lane):"
      : "Model lanes are configured but offline on this machine:";
    const list = lanes
      .map((lane) => {
        const ready = laneReady(halModels, lane.id) ? "ready" : "offline";
        return `- ${lane.name} (${lane.model}) — ${lane.state} [${ready}]\n   Will allow: ${(lane.willAllow || []).join(", ")}\n   Still blocked: ${(lane.stillBlocked || []).join(", ")}`;
      })
      .join("\n");
    return header + "\n" + list;
  }

  function cognitivePathwaysText(halData) {
    const block = (halData && halData.cognitivePathways) || {};
    const lines = [
      "HAL cognitive & social characteristics (high-priority pathways):",
      block.summary || "Reason deeply, self-check, plan across periods, and cooperate with staff — read-only always.",
    ];
    (block.cognitive || []).forEach((item) => lines.push(`- ${item.label}: ${item.practice}`));
    (block.social || []).forEach((item) => lines.push(`- ${item.label}: ${item.practice}`));
    return lines.join("\n");
  }

  function webResearchPromptLine() {
    return (
      "Public web research is available for sanitized practice-reference lookups (vendor docs, insurance billing, compliance, coding, office operations). " +
      "Never send patient names, amounts, or account numbers to the web. " +
      "When tool results include web research, cite it as public reference — not as verified practice-specific facts."
    );
  }

  function humanVoicePromptLines() {
    return [
      "Voice: sound like a steady, capable office teammate — not a generic chatbot, dashboard narrator, or distant outside evaluator.",
      "Structure answers as: direct practical answer first; reason or verified source basis second; next safe staff action third.",
      "Use short plain paragraphs. Do not use bullet lists or numbered steps unless the user asks for a list.",
      "Do not end with filler closings such as \"let me know\", \"if you want\", \"Would you like me to\", or open-ended helper questions.",
      "Do not emit hidden scratchpad, reasoning tags, markdown artifacts, or chain-of-thought text — return only the final answer staff should read.",
      "When the operator asks for a steady briefing (not a dashboard recap), speak in two short paragraphs and name SoftDent and QuickBooks when both are relevant.",
      "For QuickBooks write/post requests: first sentence must say you cannot post in QuickBooks and must include \"read-only\"; then explain human review is required.",
      "For collections trailing production: first sentence must reference aging report, accounts receivable, A/R, or outstanding balances, and must mention insurance.",
      "For denied claims aging past 30 days: mention the claim status or denial reason and a practical follow-up (resubmit or appeal).",
      "For operating-picture requests: stay in status mode, use two short paragraphs, and when verified context includes them mention Ollama, SoftDent, and QuickBooks explicitly.",
    ].join("\n");
  }

  function fastHumanVoicePromptLines() {
    return (
      agentPersonalityPromptLines() +
      "\nExamples:" +
      "\nQ: Can you post to QuickBooks? → No. I cannot post to QuickBooks from here — read-only. I can draft journal entries from imports and show what needs review before staff clicks Post." +
      "\nQ: Are imports current? → [Direct answer from local status.] Then what is missing, which export path, and what staff should verify." +
      "\nQ: What can you do on Claims? → Open the workbench, walk denied lanes, check packet readiness — I do not submit to payers." +
      "\nQ: Same question again? → Briefly acknowledge the repeat, restate the answer clearly with the same evidence."
    );
  }

  function consentPromptLines(halData) {
    const cfg = consentPolicy(halData);
    const local = (cfg.localAlways || []).slice(0, 8);
    const outbound = (cfg.categories || []).slice(0, 6);
    return [
      cfg.summary || FALLBACK_CONSENT.summary,
      "Local actions run immediately: " + (local.length ? local.join(", ") : "read, explain, reconcile, draft, refresh imports") + ".",
      "Outbound actions require explicit staff consent per action: " + (outbound.length ? outbound.join(", ") : "email, submit, post, upload, fax") + ".",
      cfg.prompt || FALLBACK_CONSENT.prompt,
    ];
  }

  function buildFastChatSystemPrompt(halData, programContext) {
    const topPriority = (halData && halData.topPriority && halData.topPriority.summary) || "";
    const parts = [
      "You are HAL, the local program manager for NewRidgeFinancial 2.0.",
      topPriority ? `Priority: ${topPriority}` : "Priority: monitor the program and recommend safe next staff actions.",
      fastHumanVoicePromptLines(),
      "Hard rule: always write at least five complete sentences — direct answer first, then evidence, implication, gaps, and next step.",
      "Answer from local context only. Never fabricate import data.",
    ].concat(consentPromptLines(halData));
    if (programContext) {
      parts.push("Local snapshot:", programContext.slice(0, 2200));
    }
    return wrapAgentSystemPrompt(parts.join("\n"));
  }

  function wrapAgentSystemPrompt(text) {
    const body = String(text || "").trim();
    if (/^PROGRAMMING:/m.test(body)) return body;
    if (typeof HalAgentProgramming !== "undefined" && HalAgentProgramming.wrapSystemPrompt) {
      return HalAgentProgramming.wrapSystemPrompt(body);
    }
    return body;
  }

  function buildSystemPrompt(halData, programContext) {
    const access = (halData && halData.programAccess) || {};
    const topPriority = (halData && halData.topPriority && halData.topPriority.summary) || "";
    const parts = [
      "You are HAL, the local program manager for NewRidgeFinancial 2.0, a dental-practice financial program.",
      cognitivePathwaysText(halData),
      topPriority ? `Top priority: ${topPriority}` : "Top priority: monitor the program, place correct data, and recommend next safe staff actions.",
      access.mode === "full-read"
        ? "You have full read access to the local program snapshot below. Answer using that data when relevant."
        : "Answer in enough detail to be useful — about this program and its pages. If you are unsure, say so plainly.",
      "Use accounting and Excel-style review to organize imported data, compare totals and periods, reconcile available values, identify missing fields, and make recommendations.",
      "Never fabricate missing SoftDent, QuickBooks, A/R, claims, document, or library data; say what is missing and what staff should verify.",
      "SoftDent and QuickBooks are separate systems: SoftDent = practice ops (production, claims, verified dental A/R). QuickBooks = accounting GL (revenue, expenses, P&L). Never treat their totals as the same number.",
      humanVoicePromptLines(),
      webResearchPromptLine(),
    ].concat(consentPromptLines(halData)).concat([
      "If the user asks for an outbound action, explain what you can prepare locally and ask for explicit consent before sending, posting, or delivering.",
    ]);
    if (programContext) {
      parts.push("Current local program snapshot:", programContext);
    } else {
      parts.push("Program pages and current status:", registryAsText(halData));
    }
    return wrapAgentSystemPrompt(parts.join("\n"));
  }

  function wantsStructuredPlan(query) {
    return /prioriti[sz]e|make a plan|draft a plan|\bplan (my|for|the)\b|analy[sz]e (?:this|the|my|our|it)|reason through|think through|\bstrategy\b|focus first|where (do|should) (i|we) start|\b(step[\s-]?by[\s-]?step plan|numbered plan|work plan|action plan)\b/.test(
      String(query || "").toLowerCase(),
    );
  }

  function buildReasoningChatPrompt(halData, programContext) {
    const topPriority = (halData && halData.topPriority && halData.topPriority.summary) || "";
    const parts = [
      "You are HAL on the 24B reasoning lane for NewRidgeFinancial 2.0 — dental-practice financial program.",
      mirandaPersonalityPromptLines(),
      topPriority ? `Top priority: ${topPriority}` : "Top priority: monitor the program and recommend safe next staff actions.",
      "Before writing, reason through: what they asked, what local/tool evidence applies, what is missing, and what one safe next step staff should take.",
      "Answer structure (prose only — no markdown headers, no numbered lists unless they asked for a plan):",
      "1) Direct answer in the first sentence.",
      "2) Evidence from tool results or snapshot — be specific about page, widget, or import state.",
      "3) Accounting or operational implication in plain language.",
      "4) What data is missing or stale and how to fix it locally (refresh imports, open a page, etc.).",
      "5) One prioritized recommendation staff can act on locally.",
      "Hard rule: never fewer than five complete sentences in the final answer.",
      "Give five to eight sentences when explaining — clear prose with evidence, not a telegram.",
      "Yes/no questions: lead with Yes or No, then explain why with real detail.",
      "Never open with Here is a structured plan unless they asked for a plan.",
      webResearchPromptLine(),
    ].concat(consentPromptLines(halData));
    if (programContext) {
      parts.push("Current local program snapshot:", programContext);
    } else {
      parts.push("Program pages and current status:", registryAsText(halData));
    }
    return wrapAgentSystemPrompt(parts.join("\n"));
  }

  function buildReasoningPrompt(halData, programContext) {
    const priorities = (halData.priorities && halData.priorities.items) || [];
    const topPriority = (halData && halData.topPriority && halData.topPriority.summary) || "";
    const parts = [
      "You are HAL's reasoning lane for NewRidgeFinancial 2.0, a dental-practice financial program.",
      cognitivePathwaysText(halData),
      topPriority ? `Top priority: ${topPriority}` : "Top priority: monitor the program, place correct data, and recommend next safe staff actions.",
      "Produce a short, structured, prioritized plan based only on the local program state below.",
      "Use accounting and Excel-style reasoning: verify source freshness, put imported rows in the correct financial/accounting context, reconcile totals and periods, sort or group what matters, and call out blanks or conflicts.",
      "Order work by readiness and risk: handle Needs Review and Blocked items carefully, and never advance payer-facing work without human review.",
      "Recommendations must say what data supports them and what data is still missing.",
      webResearchPromptLine(),
    ].concat(consentPromptLines(halData));
    if (programContext) {
      parts.push("Current local program snapshot:", programContext);
    } else {
      parts.push("Program pages and current status:", registryAsText(halData));
    }
    parts.push(
      "Known operator priorities:",
      priorities.map((item, index) => `${index + 1}. ${item}`).join("\n"),
      "Respond with a brief numbered plan. Keep it under 8 steps and include recommendations.",
    );
    return wrapAgentSystemPrompt(parts.join("\n"));
  }

  function buildEscalationPrompt(halData, programContext) {
    const parts = [
      "You are HAL's escalation lane for NewRidgeFinancial 2.0, a dental-practice financial program.",
      "Give a careful second-opinion review for a complex or high-risk question.",
      "Be conservative: call out risks, assumptions, and exactly what a human must verify before acting.",
      webResearchPromptLine(),
    ].concat(consentPromptLines(halData));
    if (programContext) {
      parts.push("Current local program snapshot:", programContext);
    } else {
      parts.push("Program pages and current status:", registryAsText(halData));
    }
    parts.push("Respond with: a short risk assessment, then a numbered list of what a human should verify.");
    return wrapAgentSystemPrompt(parts.join("\n"));
  }

  function cleanModelText(text) {
    let out = String(text);
    out = out.replace(/<think>[\s\S]*?<\/think>/gi, "");
    out = out.replace(/<\/?think>/gi, "");
    out = out.replace(/\*[^*]+\*/g, "");
    out = out.replace(/^(Okay|Sure|Certainly)[,.]?\s*(from my (local )?)?(read-?only )?(monitoring )?perspective[,:]?\s*/i, "");
    out = out.replace(/\s*\((Local chat draft|Local .* draft)[^)]*\)\s*$/i, "");
    out = out.replace(/\s*\(Local reasoning plan · read-only · verify before acting\)\s*$/i, "");
    out = out.replace(/\s*\(Local .* · read-only · verify before acting\)\s*$/i, "");
    const monologueStart = /^(Okay|Hmm|Let me|Wait|Pauses|Nods|Double-checks|Starts structuring)/i;
    if (monologueStart.test(out.trim())) {
      const riskIdx = out.search(/\*\*Risk Assessment\*\*|Risk Assessment|Human Verification|DO NOT PROCEED/i);
      if (riskIdx > 0) out = out.slice(riskIdx);
    }
    return stripInstructionLeaks(out.trim());
  }

  function sessionTemplates(halData) {
    const ws = halData && halData.workSessions;
    return (ws && ws.templates) || [];
  }

  function sessionTemplateById(halData, id) {
    return sessionTemplates(halData).find((t) => t.id === id) || null;
  }

  function findSessionTemplate(halData, query) {
    const q = String(query).toLowerCase().trim();
    for (const template of sessionTemplates(halData)) {
      if (template.command && q.includes(String(template.command).toLowerCase())) return template;
      if (template.id && q.includes(template.id.replace(/-/g, " "))) return template;
      if (template.label && q.includes(String(template.label).toLowerCase())) return template;
    }
    if (/claims review/.test(q)) return sessionTemplateById(halData, "claims-review");
    if (/source freshness|source review/.test(q)) return sessionTemplateById(halData, "source-freshness");
    if (/a\/r review|ar review|collections review/.test(q)) return sessionTemplateById(halData, "ar-review");
    if (/document review/.test(q)) return sessionTemplateById(halData, "document-review");
    if (/review item|review triage|blocked item|blocked triage/.test(q)) return sessionTemplateById(halData, "blocked-triage");
    return null;
  }

  function createSessionState(template) {
    const checklist = (template.checklist || []).map((text, index) => ({
      id: index,
      text: String(text),
      done: false,
    }));
    return {
      id: template.id,
      label: template.label,
      targetPage: template.targetPage,
      purpose: template.purpose,
      safety: template.safety,
      checklist,
      verify: (template.verify || []).map(String),
      startedAt: new Date().toISOString(),
      handoffNote: null,
    };
  }

  function toggleSessionCheck(session, checkId) {
    if (!session || !session.checklist) return session;
    const next = { ...session, checklist: session.checklist.map((item) => ({ ...item })) };
    const item = next.checklist.find((c) => c.id === checkId);
    if (item) item.done = !item.done;
    return next;
  }

  function sessionProgress(session) {
    if (!session || !session.checklist || session.checklist.length === 0) return 0;
    const done = session.checklist.filter((c) => c.done).length;
    return Math.round((done / session.checklist.length) * 100);
  }

  function draftHandoffNote(session, halData) {
    if (!session) return "";
    const reg = registryById(halData, session.targetPage);
    const pending = (session.checklist || []).filter((c) => !c.done).map((c) => c.text);
    const completed = (session.checklist || []).filter((c) => c.done).map((c) => c.text);
    const verify = (session.verify || []).map((v) => "- [ ] " + v).join("\n");
    const lines = [
      "HAL handoff note — " + session.label,
      "Purpose: " + session.purpose,
      "Safety: " + session.safety,
      reg ? "Related page: " + reg.name + " (" + reg.state + ")" : "",
      "",
      "Completed checks:",
      completed.length ? completed.map((c) => "- [x] " + c).join("\n") : "- (none yet)",
      "",
      "Remaining checks:",
      pending.length ? pending.map((c) => "- [ ] " + c).join("\n") : "- (all complete)",
      "",
      "Human must verify:",
      verify || "- (see session template)",
      "",
      "(Draft only · read-only · human review required before any external action)",
    ];
    return lines.filter(Boolean).join("\n");
  }

  function validateSessionTemplates(halData) {
    const errors = [];
    const registryIds = new Set(registryList(halData).map((e) => e.id));
    for (const template of sessionTemplates(halData)) {
      if (!template.id) errors.push("template missing id");
      if (!template.targetPage) errors.push("template " + template.id + " missing targetPage");
      else if (!registryIds.has(template.targetPage) && template.targetPage !== "hal") {
        errors.push("template " + template.id + " targetPage not in registry: " + template.targetPage);
      }
      for (const item of template.checklist || []) {
        if (typeof item !== "string" || !item.trim()) errors.push("template " + template.id + " has invalid checklist item");
      }
    }
    return errors;
  }

  function packetConfig(halData) {
    return (halData && halData.evidencePackets) || {
      disclaimer: "Draft only · read-only · human review required before any external action",
    };
  }

  function sourceFreshnessSummary(halData) {
    const items = (halData.sources && halData.sources.items) || [];
    return items
      .map((item) => {
        const fresh = item.freshness ? " · " + item.freshness : "";
        const sync = item.syncState ? " · " + item.syncState : "";
        return "- " + item.label + ": " + item.status + fresh + sync;
      })
      .join("\n");
  }

  function formatEvidencePacketText(packet) {
    if (!packet) return "";
    const lines = [
      "HAL EVIDENCE PACKET — " + packet.sessionLabel,
      "Built: " + packet.builtAt,
      "Progress: " + packet.progress + "%",
      "",
      "Purpose: " + packet.purpose,
      "Safety: " + packet.safety,
      "",
      "Completed checks:",
      packet.completedChecks.length ? packet.completedChecks.map((c) => "- [x] " + c).join("\n") : "- (none)",
      "",
      "Remaining checks:",
      packet.remainingChecks.length ? packet.remainingChecks.map((c) => "- [ ] " + c).join("\n") : "- (all complete)",
      "",
      "Human must verify:",
      packet.verifyList.length ? packet.verifyList.map((v) => "- [ ] " + v).join("\n") : "- (see session)",
      "",
      "Registry state:",
      packet.registryState || "- (none)",
      "",
      "Source freshness:",
      packet.sourceFreshness || "- (none)",
      "",
      "Firewall reminder:",
      packet.firewallReminder,
      "",
    ];
    if (packet.handoffNote) {
      lines.push("Handoff note:", packet.handoffNote, "");
    }
    if (packet.modelNote) {
      lines.push("Model lanes:", packet.modelNote, "");
    }
    lines.push("(" + packet.disclaimer + ")");
    return lines.join("\n");
  }

  function buildEvidencePacket(session, halData, halModels) {
    if (!session) return null;
    const reg = registryById(halData, session.targetPage);
    const cfg = packetConfig(halData);
    const consent = consentPolicy(halData);
    const completedChecks = (session.checklist || []).filter((c) => c.done).map((c) => c.text);
    const remainingChecks = (session.checklist || []).filter((c) => !c.done).map((c) => c.text);
    const registryState = reg
      ? reg.name + " [" + reg.state + "; " + reg.safety + "] — " + reg.nextAction + ". Blocked: " + (reg.blocked || []).join(", ")
      : null;
    const packet = {
      builtAt: new Date().toISOString(),
      sessionLabel: session.label,
      progress: sessionProgress(session),
      purpose: session.purpose,
      safety: session.safety,
      completedChecks,
      remainingChecks,
      verifyList: (session.verify || []).map(String),
      registryState,
      sourceFreshness: sourceFreshnessSummary(halData),
      consentReminder: consent.prompt || consent.summary,
      firewallReminder: consent.prompt || consent.summary,
      handoffNote: session.handoffNote || null,
      modelNote: halModels ? "Local model lanes only; consent required before outbound actions." : null,
      disclaimer: cfg.disclaimer || "Draft only · staff consent required before any external delivery",
    };
    packet.text = formatEvidencePacketText(packet);
    return packet;
  }

  function validateEvidencePacket(packet, halData) {
    const errors = [];
    if (!packet) {
      errors.push("packet is null");
      return errors;
    }
    if (!packet.sessionLabel) errors.push("missing sessionLabel");
    if (typeof packet.progress !== "number") errors.push("missing progress");
    if (!packet.safety) errors.push("missing safety");
    if (!Array.isArray(packet.completedChecks)) errors.push("missing completedChecks");
    if (!Array.isArray(packet.remainingChecks)) errors.push("missing remainingChecks");
    if (!Array.isArray(packet.verifyList)) errors.push("missing verifyList");
    if (!packet.registryState) errors.push("missing registryState");
    if (!packet.sourceFreshness) errors.push("missing sourceFreshness");
    if (!packet.consentReminder && !packet.firewallReminder) errors.push("missing consentReminder");
    if (!packet.disclaimer || !/consent|human review/i.test(packet.disclaimer)) {
      errors.push("disclaimer must mention consent or human review");
    }
    if (!packet.text || !packet.text.includes(packet.sessionLabel)) {
      errors.push("packet text must include session label");
    }
    return errors;
  }

  function matchPacketRoute(query) {
    const q = String(query).toLowerCase().trim();
    if (/clear evidence packet|clear (local )?packet|reset evidence packet/.test(q)) return { type: "clear" };
    if (/show evidence packet|show (the )?packet|display evidence packet|view evidence packet|open packet text/.test(q)) {
      return { type: "show" };
    }
    if (
      /build evidence packet|build packet|build the packet|create evidence packet|create packet|assemble evidence packet|make evidence packet/.test(q)
    ) {
      return { type: "build" };
    }
    return null;
  }

  function readinessConfig(halData) {
    return (halData && halData.readiness) || {
      expectedRegistryCount: 10,
      expectedSessionTemplates: 5,
      expectedModelLanes: 3,
      halImage: "",
    };
  }

  function readinessItem(id, label, status, detail, next) {
    return { id, label, status, detail, next: next || null };
  }

  function staffUseGate(report) {
    if (!report || !report.results) {
      return {
        status: "Unknown",
        headline: "Readiness not run yet",
        detail: "Run a readiness check before staff use.",
        blockers: [],
        warnings: [],
      };
    }
    const blockers = report.results.filter((r) => r.status === "Fail");
    const warnings = report.results.filter((r) => r.status === "Warning");
    if (blockers.length > 0) {
      return {
        status: "Not ready",
        headline: "Not ready for staff use",
        detail: blockers.length + " blocking check(s) must be resolved before staff use.",
        blockers: blockers.map((r) => r.label + ": " + (r.next || r.detail)),
        warnings: warnings.map((r) => r.label + ": " + (r.next || r.detail)),
      };
    }
    if (warnings.length > 0) {
      return {
        status: "Ready with warnings",
        headline: "Ready with warnings",
        detail: warnings.length + " warning(s) noted. Staff may proceed with care.",
        blockers: [],
        warnings: warnings.map((r) => r.label + ": " + (r.next || r.detail)),
      };
    }
    return {
      status: "Ready",
      headline: "Ready for staff use",
      detail: "All readiness checks passed. HAL is safe for read-only staff use.",
      blockers: [],
      warnings: [],
    };
  }

  function formatReadinessSummary(report) {
    if (!report || !report.results) return "No diagnostics available.";
    const gate = staffUseGate(report);
    const lines = [
      "HAL readiness: " + report.overall,
      "Staff use gate: " + gate.status + " — " + gate.headline,
      "Checked: " + report.ranAt,
      "",
      ...report.results.map((r) => "- [" + r.status + "] " + r.label + ": " + r.detail + (r.next ? " Next: " + r.next : "")),
      "",
      "(Local diagnostic only · read-only · human review required)",
    ];
    return lines.join("\n");
  }

  function runReadinessChecks(halData, halModels, pages, runtime) {
    const cfg = readinessConfig(halData);
    const results = [];

    const regCount = registryList(halData).length;
    results.push(
      readinessItem(
        "registry",
        "Program registry",
        regCount === cfg.expectedRegistryCount ? "Pass" : "Fail",
        regCount + " of " + cfg.expectedRegistryCount + " pages registered",
        regCount === cfg.expectedRegistryCount ? null : "Check hal-manager.json registry entries.",
      ),
    );

    const sessionErrors = validateSessionTemplates(halData);
    const sessionCount = sessionTemplates(halData).length;
    results.push(
      readinessItem(
        "sessions",
        "Work session templates",
        sessionErrors.length === 0 && sessionCount === cfg.expectedSessionTemplates ? "Pass" : "Fail",
        sessionCount + " templates; " + sessionErrors.length + " validation issue(s)",
        sessionErrors.length ? sessionErrors.join("; ") : null,
      ),
    );

    const submitRoute = routeHalCommand(halData, halModels, pages, "submit the claim");
    results.push(
      readinessItem(
        "consent",
        "Staff consent policy",
        submitRoute.intent !== "blocked: firewall" ? "Pass" : "Fail",
        consentPolicy(halData).summary,
        submitRoute.intent === "blocked: firewall" ? "Remove firewall blocking from routeHalCommand." : null,
      ),
    );

    let routeFails = 0;
    const suggestions = (halData.validation && halData.validation.suggestionRoutes) || {};
    for (const [suggestion, expected] of Object.entries(suggestions)) {
      const routed = routeHalCommand(halData, halModels, pages, suggestion);
      if (routed.intent !== expected && !String(routed.intent).startsWith(expected)) routeFails++;
    }
    results.push(
      readinessItem(
        "routes",
        "Suggestion routing",
        routeFails === 0 ? "Pass" : "Fail",
        Object.keys(suggestions).length - routeFails + " of " + Object.keys(suggestions).length + " routes match fixtures",
        routeFails ? "Update validation.suggestionRoutes or routeHalCommand." : null,
      ),
    );

    const packetCfg = packetConfig(halData);
    const packetFieldCount = (halData.evidencePackets && halData.evidencePackets.fields && halData.evidencePackets.fields.length) || 0;
    results.push(
      readinessItem(
        "packets",
        "Evidence packet config",
        packetFieldCount >= 10 && packetCfg.disclaimer ? "Pass" : "Warning",
        packetFieldCount + " packet fields configured",
        packetFieldCount < 10 ? "Check evidencePackets.fields in hal-manager.json." : null,
      ),
    );

    const lanes = modelLanes(halModels);
    const mode = modelConfig(halModels).mode || "offline";
    const lanesReady = lanes.filter((lane) => laneReady(halModels, lane.id)).length;
    results.push(
      readinessItem(
        "models",
        "Model lane configuration",
        lanes.length === cfg.expectedModelLanes ? "Pass" : "Warning",
        lanes.length + " lanes configured; mode=" + mode + "; " + lanesReady + " ready on this machine",
        lanesReady === 0 && mode === "online" ? "Start Ollama locally or set mode offline in hal-models.json." : null,
      ),
    );

    if (runtime && typeof runtime === "object") {
      if (runtime.halImage) {
        const ok = String(runtime.halImage).includes(cfg.halImage);
        results.push(
          readinessItem(
            "hal-image",
            "HAL page image",
            ok ? "Pass" : "Fail",
            runtime.halImage,
            ok ? null : "Hard refresh (Ctrl+Shift+R) or restart the desktop app.",
          ),
        );
      }
      if (runtime.storageMode === "sqlite" || runtime.desktopBridgeOk === true) {
        results.push(readinessItem("storage", "Desktop SQLite storage", "Pass", "pywebview bridge active; SQLite-backed persistence available", null));
      } else if (runtime.storageMode === "sessionStorage") {
        results.push(
          readinessItem(
            "storage",
            "Browser preview storage",
            "Warning",
            "sessionStorage fallback only; imports, SQLite storage, SideNotes hub files, and import sync are unavailable",
            "Launch NR2 with StartProgram.bat for desktop mode (http://127.0.0.1:8765/).",
          ),
        );
      } else if (runtime.sessionStorageOk === true) {
        results.push(readinessItem("storage", "Browser session storage", "Pass", "sessionStorage available", null));
      } else if (runtime.sessionStorageOk === false) {
        results.push(readinessItem("storage", "Browser session storage", "Warning", "sessionStorage unavailable", "Use a normal browser window; private mode may block persistence."));
      }
      if (runtime.activeSession) {
        results.push(
          readinessItem(
            "active-session",
            "Active work session",
            "Pass",
            "Session: " + runtime.activeSession.label + " (" + sessionProgress(runtime.activeSession) + "% complete)",
            null,
          ),
        );
      } else {
        results.push(
          readinessItem(
            "active-session",
            "Active work session",
            "Warning",
            "No active work session",
            "Start a session before building an evidence packet.",
          ),
        );
      }
    }

    const overall = results.some((r) => r.status === "Fail")
      ? "Fail"
      : results.some((r) => r.status === "Warning")
        ? "Warning"
        : "Pass";

    const report = { ranAt: new Date().toISOString(), overall, results };
    report.gate = staffUseGate(report);
    report.summary = formatReadinessSummary(report);
    return report;
  }

  function smokeStep(id, label, status, detail) {
    return { id, label, status, detail };
  }

  function formatSmokeTestSummary(report) {
    if (!report || !report.steps) return "No smoke test available.";
    const lines = [
      "HAL operator smoke test: " + report.overall,
      "Ran: " + report.ranAt,
      "",
      ...report.steps.map((s) => "- [" + s.status + "] " + s.label + ": " + s.detail),
      "",
      "(Local end-to-end check · read-only · no external action performed)",
    ];
    return lines.join("\n");
  }

  function runOperatorSmokeTest(halData, halModels, pages, runtime) {
    const steps = [];

    const readiness = runReadinessChecks(halData, halModels, pages, runtime);
    steps.push(
      smokeStep(
        "readiness",
        "Readiness check runs",
        readiness && readiness.results.length ? "Pass" : "Fail",
        readiness ? "Overall " + readiness.overall + " across " + readiness.results.length + " checks" : "No readiness report",
      ),
    );

    const help = routeHalCommand(halData, halModels, pages, "what can you do?");
    steps.push(smokeStep("ask", "Ask HAL responds locally", help.intent === "help" ? "Pass" : "Fail", "Intent: " + help.intent));

    const nav = routeHalCommand(halData, halModels, pages, "open claims workbench");
    steps.push(smokeStep("navigate", "Open a program page", nav.intent === "navigate: claims" ? "Pass" : "Fail", "Intent: " + nav.intent));

    const template = sessionTemplateById(halData, "claims-review");
    const session = template ? createSessionState(template) : null;
    steps.push(
      smokeStep("session", "Start a work session", session ? "Pass" : "Fail", session ? "Session: " + session.label : "No claims-review template"),
    );

    const packet = session ? buildEvidencePacket(session, halData, halModels) : null;
    const packetErrors = packet ? validateEvidencePacket(packet, halData) : ["no packet"];
    steps.push(
      smokeStep(
        "packet",
        "Build evidence packet",
        packet && packetErrors.length === 0 ? "Pass" : "Fail",
        packet ? packetErrors.length + " validation issue(s)" : "No packet built",
      ),
    );

    const submitRoute = routeHalCommand(halData, halModels, pages, "submit the claim");
    steps.push(
      smokeStep(
        "consent",
        "Consent policy (no firewall block)",
        submitRoute.intent !== "blocked: firewall" ? "Pass" : "Fail",
        "Intent: " + submitRoute.intent,
      ),
    );

    const overall = steps.some((s) => s.status === "Fail") ? "Fail" : steps.some((s) => s.status === "Warning") ? "Warning" : "Pass";
    const report = { ranAt: new Date().toISOString(), overall, steps };
    report.summary = formatSmokeTestSummary(report);
    return report;
  }

  function buildHandoffSummary(halData, halModels, context) {
    const ctx = context || {};
    const readiness = ctx.readiness || null;
    const session = ctx.session || null;
    const packet = ctx.packet || null;
    const smoke = ctx.smoke || null;
    const gate = readiness ? readiness.gate || staffUseGate(readiness) : null;
    const blocked = registryList(halData).filter((entry) => /blocked|needs review/i.test(entry.state));
    const lines = [
      "HAL STAFF HANDOFF SUMMARY",
      "Generated: " + new Date().toISOString(),
      "",
      "Readiness: " + (readiness ? readiness.overall : "not run yet"),
      "Staff use gate: " + (gate ? gate.status + " — " + gate.headline : "not run yet"),
      "Operator smoke test: " + (smoke ? smoke.overall : "not run yet"),
      "",
      "Active work session: " + (session ? session.label + " (" + sessionProgress(session) + "% complete)" : "none"),
      "Evidence packet: " + (packet ? "built " + packet.builtAt : "none"),
      "",
      "Blocked / needs review:",
      blocked.length ? blocked.map((entry) => "- " + entry.name + " (" + entry.state + "): " + entry.nextAction).join("\n") : "- (none)",
      "",
      "Next staff actions:",
      registryList(halData)
        .map((entry) => "- " + entry.name + ": " + entry.nextAction)
        .join("\n"),
      "",
      "(Read-only summary · HAL performs no external action · human review required)",
    ];
    return lines.join("\n");
  }

  function deriveDrawerHealth(halData, halModels, pages, readiness) {
    const report = readiness || runReadinessChecks(halData, halModels, pages);
    const byId = {};
    for (const item of report.results) byId[item.id] = item.status;
    const worst = (...statuses) => (statuses.includes("Fail") ? "Fail" : statuses.includes("Warning") ? "Warning" : "Pass");
    const sourceItems = (halData.sources && halData.sources.items) || [];
    const sourcesStatus = sourceItems.some((s) => s.warning) ? "Warning" : "Pass";
    return {
      askHal: worst(byId.routes || "Pass", byId.registry || "Pass"),
      sources: sourcesStatus,
      reasoning: worst(byId.models || "Pass"),
      workSurfaces: worst(byId.sessions || "Pass", byId.packets || "Pass"),
      consent: worst(byId.consent || "Pass"),
      priorities: "Pass",
      status: report.overall,
      controls: report.overall,
    };
  }

  function modelLaneDetails(halModels) {
    const mode = modelConfig(halModels).mode || "offline";
    return modelLanes(halModels).map((lane) => {
      const ready = laneReady(halModels, lane.id);
      let nextStep = null;
      if (!ready) {
        nextStep =
          mode === "online"
            ? "Start Ollama locally and confirm " + (lane.model || "the model") + " is pulled."
            : "Set mode to online in hal-models.json once a local model is available.";
      }
      return { id: lane.id, name: lane.name, role: lane.role, model: lane.model, state: lane.state, ready, mode, nextStep };
    });
  }

  function matchOperatorRoute(query) {
    const q = String(query).toLowerCase().trim();
    if (/smoke test|operator test|acceptance test|end[\s-]?to[\s-]?end (test|check)|operator check/.test(q)) return { type: "smoke" };
    if (/staff handoff summary|handoff summary|staff summary|handoff report/.test(q)) return { type: "handoff-summary" };
    return null;
  }

  function matchReadinessRoute(query) {
    const q = String(query).toLowerCase().trim();
    if (/staff[\s-]?use gate|ready for staff|safe for staff|can staff use|are you ready for staff|ready to use|staff readiness/.test(q)) {
      return { type: "gate" };
    }
    if (/clear diagnostic|clear readiness|reset diagnostic/.test(q)) return { type: "clear" };
    if (/show diagnostic|show readiness|display diagnostic/.test(q)) return { type: "show" };
    if (
      /what (?:does |do )?readiness|what readiness|readiness actually check|explain readiness|tell me what readiness/.test(
        q,
      )
    ) {
      return { type: "show" };
    }
    if (/run readiness|readiness check|check hal|hal diagnostic|self[\s-]?check|diagnostic check/.test(q)) return { type: "run" };
    return null;
  }

  function matchSessionRoute(query) {
    const q = String(query).toLowerCase().trim();
    if (/reset ((the )?(work |current ))?session|clear (work )?session|end (the )?session/.test(q)) {
      return { type: "reset" };
    }
    if (/show (active|current) session|active session|active work session|work session status|current work session|current session|session status/.test(q)) {
      return { type: "show" };
    }
    if (/draft handoff|handoff note|draft session note/.test(q)) {
      return { type: "handoff" };
    }
    if (/\bstart\b/.test(q) || /begin review/.test(q)) {
      return { type: "start" };
    }
    return null;
  }

  function matchEnglishVocabRoute(query, rawQuery) {
    const q = String(query || "").trim().toLowerCase();
    if (/\b(seed|index|fill|load)\b.*\b(english|dictionary)\b/.test(q) && /\b(library|local)\b/.test(q)) {
      return { intent: "english: seed-library", lane: "local", useEnglishSeed: true, text: "", actions: [] };
    }
    if (/\b(random|pick)\b.*\b(english\s+)?word\b/.test(q) || /\bvocabulary\b.*\brandom\b/.test(q) || q === "random word") {
      return { intent: "english: random-word", lane: "local", useEnglishRandom: true, text: "", actions: [] };
    }
    if (/\b(english\s+)?quiz\b.*\b(\d+|words?)\b/.test(q) || /\bvocabulary quiz\b/.test(q)) {
      const m = q.match(/\b(\d+)\b/);
      return {
        intent: "english: quiz",
        lane: "local",
        useEnglishQuiz: true,
        englishQuizCount: m ? Math.min(10, parseInt(m[1], 10) || 5) : 5,
        text: "",
        actions: [],
      };
    }
    const define =
      String(rawQuery || "")
        .trim()
        .match(/^(?:define|meaning of)\s+(?:the\s+word\s+)?([a-z'-]+)\.?\??$/i) ||
      String(rawQuery || "")
        .trim()
        .match(/^(?:what does|what is)\s+the\s+word\s+([a-z'-]+)\.?\??$/i);
    if (define) {
      return {
        intent: "english: define",
        lane: "local",
        useEnglishDefine: true,
        englishWord: define[1].toLowerCase(),
        text: "",
        actions: [],
      };
    }
    if (/\bteach\b.*\benglish\b/.test(q) || /\blearn english\b/.test(q) || /\benglish lesson\b/.test(q)) {
      return { intent: "english: teach", lane: "local", useEnglishTeach: true, text: "", actions: [] };
    }
    return null;
  }

  function routeHalCommand(halData, halModels, pages, rawQuery, opts) {
    opts = opts || {};
    const query = String(rawQuery)
      .toLowerCase()
      .trim()
      .replace(/^hal[,:]\s+/, "");

    if (!opts.capabilityInner) {
      if (
        /\b(recap|summarize (?:what we|our (?:chat|conversation))|what did we (?:just )?(?:talk|discuss) about|conversation so far)\b/i.test(
          query,
        )
      ) {
        return { intent: "chat: recap", lane: "local", useChatRecap: true, text: "", actions: [] };
      }
      const compare = matchCompareRoute(rawQuery);
      if (compare) {
        return {
          intent: "chat: compare",
          lane: "local",
          text: buildCompareReply(compare.left, compare.right, halData),
          actions: [],
        };
      }
      const english = matchEnglishVocabRoute(query, rawQuery);
      if (english) return english;
      const capability = matchCapabilityRoute(halData, halModels, pages, rawQuery);
      if (capability) return capability;
    }

    if (
      /\b(remember this|save (?:this |that )?(?:to )?memory|save (?:the )?web (?:finding|research)|remember (?:what you found|the web))\b/i.test(
        query,
      )
    ) {
      return { intent: "memory: remember", lane: "local", useRememberMemory: true, text: "", prompt: rawQuery, actions: [] };
    }

    if (
      /\b(help|tell me what you can do|capabilit\w*|how do you work|what do you do|what are you able to)\b/.test(query) ||
      (/\bwhat can you do\b/.test(query) && !/\bon (the )?[a-z]/i.test(query) && !/\bpage\b/.test(query))
    ) {
      return {
        intent: "help",
        lane: "local",
        text: buildHelpChatReply(halData),
        actions: [],
      };
    }

    const printRoute = matchPrintRoute(query, rawQuery);
    if (printRoute) return printRoute;

    const programRoute = matchProgramRoute(query);
    if (programRoute) {
      if (programRoute.type === "snapshot") {
        return { intent: "program: snapshot", lane: "local", useProgramSnapshot: true, text: "", actions: [] };
      }
    }

    const skillRoute = matchSkillRoute(query, rawQuery);
    if (skillRoute) return skillRoute;

    const operatorRoute = matchOperatorRoute(query);
    if (operatorRoute) {
      if (operatorRoute.type === "smoke") {
        return { intent: "operator: smoke", lane: "local", useSmokeTest: true, text: "", actions: [] };
      }
      if (operatorRoute.type === "handoff-summary") {
        return { intent: "operator: handoff-summary", lane: "local", useHandoffSummary: true, text: "", actions: [] };
      }
    }

    const readinessRoute = matchReadinessRoute(query);
    if (readinessRoute) {
      if (readinessRoute.type === "gate") {
        return { intent: "readiness: gate", lane: "local", useReadinessGate: true, text: "", actions: [] };
      }
      if (readinessRoute.type === "run") {
        return { intent: "readiness: run", lane: "local", useReadinessRun: true, text: "", actions: [] };
      }
      if (readinessRoute.type === "show") {
        return { intent: "readiness: show", lane: "local", useReadinessShow: true, text: "", actions: [] };
      }
      if (readinessRoute.type === "clear") {
        return {
          intent: "readiness: clear",
          lane: "local",
          useReadinessClear: true,
          text: "Diagnostics cleared.",
          actions: [],
        };
      }
    }

    const packetRoute = matchPacketRoute(query);
    if (packetRoute) {
      if (packetRoute.type === "build") {
        return { intent: "packet: build", lane: "local", usePacketBuild: true, text: "", actions: [] };
      }
      if (packetRoute.type === "show") {
        return { intent: "packet: show", lane: "local", usePacketShow: true, text: "", actions: [] };
      }
      if (packetRoute.type === "clear") {
        return {
          intent: "packet: clear",
          lane: "local",
          usePacketClear: true,
          text: "Evidence packet cleared.",
          actions: [],
        };
      }
    }

    const sessionRoute = matchSessionRoute(query);
    if (sessionRoute) {
      if (sessionRoute.type === "show") {
        return { intent: "session: show", lane: "local", useSessionShow: true, text: "", actions: [] };
      }
      if (sessionRoute.type === "reset") {
        return { intent: "session: reset", lane: "local", useSessionReset: true, text: "Work session cleared.", actions: [] };
      }
      if (sessionRoute.type === "handoff") {
        return { intent: "session: handoff", lane: "local", useSessionHandoff: true, text: "", actions: [] };
      }
      if (sessionRoute.type === "start") {
        const template = findSessionTemplate(halData, query);
        if (template) {
          const reg = registryById(halData, template.targetPage);
          return {
            intent: "session: start:" + template.id,
            lane: "local",
            useSessionStart: true,
            sessionId: template.id,
            text:
              "Starting work session: " +
              template.label +
              ". " +
              template.purpose +
              " Safety: " +
              template.safety,
            actions: template.targetPage
              ? [{ type: "openPage", label: "Open " + (reg ? reg.name : template.targetPage), page: template.targetPage }]
              : [],
          };
        }
      }
    }

    const wantsExplain =
      /\b(explain|what is|what's|whats|what does|tell me about|describe|purpose of|what happens when|what happens if|what if|what would happen)\b/.test(
        query,
      );

    // Explicit navigation wins over source/status keyword matching (e.g. "Open SoftDent").
    if (/\b(open|go to|navigate to|take me to|launch)\b/.test(query) && !wantsExplain) {
      const navId = findPage(query);
      if (navId) {
        const navInfo = pageInfoMap(halData, pages)[navId] || { label: navId, detail: "" };
        const navReg = registryById(halData, navId);
        const navStatus = navReg ? `\nStatus: ${navReg.state}. Safety: ${navReg.safety}. Next: ${navReg.nextAction}` : "";
        const simpleNav = isSimpleActionQuery(rawQuery);
        const navText = simpleNav
          ? buildMicroActionReply("navigate: " + navId, navInfo.label, rawQuery)
          : `I can open ${navInfo.label}. ${navInfo.detail}${navStatus}`;
        return {
          intent: "navigate: " + navId,
          lane: "local",
          text: navText,
          actions: [{ type: "openPage", label: "Open " + navInfo.label, page: navId }],
        };
      }
    }

    if (/\b(120b|gpt-oss|oss120b)\b/i.test(query) || /\brun\b.*\b120b\b/i.test(query)) {
      return { intent: "oss", lane: "oss120b", text: "", useOss: true, prompt: rawQuery, actions: [] };
    }

    if (/second opinion|escalat|double[\s-]?check|high[\s-]?risk|complex case|deep review|review carefully|sanity check|scrutin/.test(query)) {
      return { intent: "escalation", lane: "escalate30b", text: "", useEscalation: true, prompt: rawQuery, actions: [] };
    }

    if (
      /\b(search the web|look up online|web research|research online|find (?:out|info) (?:about|on)|latest (?:on|about)|public documentation)\b/i.test(
        query,
      )
    ) {
      return {
        intent: "research: web",
        lane: "chat8b",
        text: "",
        useModel: true,
        useWebResearch: true,
        prompt: rawQuery,
        actions: [],
      };
    }

    if (
      /\b(draft|select|pick|best|generate)\b.*\b(narrative|letter)\b/.test(query) &&
      (/\bclaim\b|\bCLM[-\w]+\b/i.test(query) || /\bfor\b.*\bclaim\b/.test(query))
    ) {
      return { intent: "narratives: select-for-claim", lane: "local", useNarrativeForClaim: true, text: "", actions: [] };
    }

    if (
      /\banalyze whether\b.*\bimports?\b.*\b(current|fresh|stale|enough|ready|management)\b/.test(query) ||
      /\bimports?\b.*\b(current enough|fresh enough|stale|ready)\b.*\bfor\b.*\b(review|management)\b/.test(query)
    ) {
      return { intent: "imports: currency-check", lane: "local", useImportStatus: true, text: "", actions: [] };
    }

    if (
      !wantsExplain &&
      (/\b(review|fact[\s-]?check)\s+(this\s+|the\s+|my\s+)?(insurance\s+)?narrative/i.test(query) ||
        /\b(appeal letter|crown narrative|perio narrative)\b/i.test(query))
    ) {
      return { intent: "reasoning: narrative", lane: "reason21b", text: "", useReasoning: true, prompt: rawQuery, actions: [] };
    }

    if (/\b(can you|could you)\b.*\b(make a plan|plan for today)\b/.test(query)) {
      return { intent: "priorities", lane: "local", useProactiveBriefing: true, text: "", actions: [] };
    }

    if (
      /prioriti[sz]e|make a plan|draft a plan|\bplan (my|for|the)\b|analy[sz]e (?:this|the|my|our|it)|reason through|think through|\bstrategy\b|focus first|where (do|should) (i|we) start/.test(
        query,
      ) ||
      /\b(step[\s-]?by[\s-]?step plan|numbered plan|work plan|action plan)\b/.test(query) ||
      (/\brecommend\b/.test(query) &&
        /\b(accounting|review|priority|priorities|next step|month.?end|closeout|close out|work plan)\b/.test(query))
    ) {
      return { intent: "reasoning", lane: "reason21b", text: "", useReasoning: true, prompt: rawQuery, actions: [] };
    }

    if (/\bblocked\b|\bblockers\b|needs review|waiting on|what is waiting/.test(query)) {
      const waiting = registryList(halData).filter((entry) => /blocked|needs review/i.test(entry.state));
      const list = waiting.map((entry) => `- ${entry.name} (${entry.state}): ${entry.nextAction}`).join("\n");
      return {
        intent: "registry: blocked",
        lane: "local",
        text: waiting.length ? `Waiting or needs review:\n${list}` : "Nothing is blocked right now.",
        actions: waiting.map((entry) => ({ type: "openPage", label: "Open " + entry.name, page: entry.id })),
      };
    }

    if (
      /\b(proactive|what should hal|what's best|best for the program|think about the program|program health|hal recommend)\b/.test(
        query,
      )
    ) {
      return { intent: "proactive: briefing", lane: "local", useProactiveBriefing: true, text: "", actions: [] };
    }

    if (/\bpriorit|needs attention|attention today|what needs attention|what should (i|we) do|to-?do|\btoday\b/.test(query)) {
      return { intent: "priorities", lane: "local", useProactiveBriefing: true, text: "", actions: [] };
    }

    if (/\b(consent|consent policy|guardrail|guardrails|safety)\b/.test(query) || /\bfirewall\b/.test(query)) {
      const cfg = consentPolicy(halData);
      const policyText = pickVariant([
        `${cfg.summary} ${cfg.prompt}`,
        `No firewall — consent only. ${cfg.summary}`,
        `${cfg.title}: ${(cfg.categories || []).join(", ")} require explicit consent before HAL acts.`,
      ]);
      return { intent: "consent", lane: "local", text: policyText, actions: [] };
    }

    if (/\bquickbooks online\b|\bqbo api\b|\bquickbooks api status\b/.test(query)) {
      return {
        intent: "integration:qbo-online",
        lane: "local",
        text:
          "QuickBooks Online API direct post is optional. Set NR2_QBO_CLIENT_ID, NR2_QBO_CLIENT_SECRET, NR2_QBO_REALM_ID, and NR2_QBO_REFRESH_TOKEN to enable consent-gated API post. Until configured, use Export approved journal entries to QuickBooks IIF after consent — that path is live today.",
        actions: [{ type: "openPage", page: "quickbooks", label: "Open QuickBooks" }],
      };
    }

    if (
      /\b(what can (you|hal)|catalog|list resources|available resources)\b.*\b(quickbooks|softdent|source|upstream)\b/.test(query) ||
      /\b(quickbooks|softdent)\b.*\b(what can (you|hal)|catalog|list resources)\b/.test(query)
    ) {
      return { intent: "sources: catalog", lane: "local", usePracticeSourceCatalog: true, text: "", actions: [] };
    }

    if (
      (/\b(fetch|pull|get|read|query|retrieve)\b/.test(query) &&
        (/\b(direct|live|upstream|source)\b/.test(query) || /\b(revenue|expenses|claims|dashboard|ar|p&l|profit|clinical|bridge|monthly)\b/.test(query)) &&
        /\b(quickbooks|softdent|qb)\b/.test(query)) ||
      /\b(fetch|pull|get)\b.*\b(quickbooks|softdent|qb)\b.*\b(revenue|expenses|claims|dashboard|ar|p&l|profit|clinical|bridge|monthly|all)\b/.test(query)
    ) {
      const skills =
        typeof HalSkills !== "undefined"
          ? HalSkills
          : typeof globalThis !== "undefined" && globalThis.HalSkills
            ? globalThis.HalSkills
            : typeof window !== "undefined" && window.HalSkills
              ? window.HalSkills
              : null;
      const practiceSystem = /\bsoftdent\b|\bsoft dent\b/.test(query)
        ? "softdent"
        : /\bquickbooks\b|\bqb\b/.test(query)
          ? "quickbooks"
          : "quickbooks";
      const req =
        skills && skills.resolvePracticeSourceRequest
          ? skills.resolvePracticeSourceRequest(query)
          : { system: practiceSystem, resource: "revenue", refreshCache: /\b(refresh|sync)\b/.test(query) };
      if (!req.system || req.system === "catalog") req.system = practiceSystem;
      return {
        intent: `sources: fetch:${req.system || "quickbooks"}`,
        lane: "local",
        usePracticeSourceFetch: true,
        practiceSourceRequest: req,
        text: "",
        actions: [],
      };
    }

    if (/\b(refresh|reload)\b.*\b(imports?|softdent|quickbooks)\b|\bimports?\b.*\b(refresh|reload|status)\b|\bsoftdent\b.*\bimports?\b|\bquickbooks\b.*\bimports?\b/.test(query)) {
      if (/\b(refresh|reload)\b/.test(query)) {
        return { intent: "imports: refresh", lane: "local", useImportRefresh: true, text: "", actions: [] };
      }
      return { intent: "imports: status", lane: "local", useImportStatus: true, text: "", actions: [] };
    }

    if (/\b(integration health|integrations health|integration status|system health)\b/.test(query)) {
      return { intent: "ops: integration-health", lane: "local", useIntegrationHealth: true, text: "", actions: [] };
    }
    if (/\b(support bundle|diagnostics bundle|export support|troubleshoot bundle)\b/.test(query)) {
      return { intent: "ops: support-bundle", lane: "local", useSupportBundle: true, text: "", actions: [] };
    }
    if (/\b(daily closeout|morning checklist|end of day checklist)\b/.test(query)) {
      return { intent: "ops: daily-closeout", lane: "local", useDailyCloseout: true, text: "", actions: [] };
    }
    if (/\b(closeout runbook|month.?end runbook|end of month runbook|close the month|month.?end close runbook)\b/.test(query)) {
      return { intent: "ops: closeout-runbook", lane: "local", useCloseoutRunbook: true, text: "", actions: [] };
    }
    if (/\b(self heal|self-heal|strengthen program|repair program|fix program|program strength|heal program)\b/.test(query)) {
      return { intent: "ops: self-heal", lane: "local", useProgramSelfHeal: true, text: "", actions: [] };
    }
    if (/\b(approve all|bulk approve)\b.*\b(journal|posting queue)\b|\b(journal|posting queue)\b.*\b(approve all|bulk approve)\b/.test(query)) {
      return { intent: "ops: journal-bulk-approve", lane: "local", useJournalBulkApprove: true, text: "", actions: [] };
    }
    if (/\b(financial reports?|claim tracking|claims report|ar aging report)\b/.test(query)) {
      return { intent: "ops: financial-reports", lane: "local", useFinancialReports: true, text: "", actions: [] };
    }
    if (/\b(automation registry|scheduled jobs|automation status|last run)\b/.test(query)) {
      return { intent: "ops: automation-registry", lane: "local", useAutomationRegistry: true, text: "", actions: [] };
    }
    if (/\bhow do i\b|\bhow to\b.*\b(import|widget|document|support|closeout|refresh)\b/.test(query)) {
      return { intent: "ops: program-help", lane: "local", useProgramHelp: true, prompt: rawQuery, text: "", actions: [] };
    }

    if (
      /\b(pull|sync|refresh)\b.*\b(softdent|quickbooks|practice sources?|upstream)\b|\b(softdent|quickbooks)\b.*\b(pull|sync|refresh)\b.*\b(direct|source|approved|cache|all|100%|full)\b/.test(
        query,
      )
    ) {
      const fullPull = /\b(full|100%|all data|everything)\b/.test(query);
      return { intent: "sources: pull-approved", lane: "local", usePracticeSourcePull: true, practiceSourceFullPull: fullPull, text: "", actions: [] };
    }

    if (/\b(cognitive|metacognition|how do you think|characteristics|pathways)\b/.test(query)) {
      return { intent: "hal: cognitive-pathways", lane: "local", useCognitivePathways: true, text: "", actions: [] };
    }

    if (
      /\bwhat do you need\b|\bwhat do i need to provide\b|\bthings you need\b|\bwhat.*need.*\b(job|work)\b|\blist.*\b(need|missing|requirements)\b.*\bhal\b/.test(
        query,
      )
    ) {
      return { intent: "hal: job-requirements", lane: "local", useHalJobRequirements: true, text: "", actions: [] };
    }

    if (
      /\b(difference|different|vs\.?|versus|compare|between)\b.*\b(softdent|quickbooks)\b.*\b(softdent|quickbooks)\b/.test(query) ||
      /\bwhat (data|information|numbers?)\b.*\b(comes from|is in|live in)\b.*\b(softdent|quickbooks)\b/.test(query) ||
      /\b(softdent|quickbooks)\b.*\b(data|source|system|export)\b.*\b(mean|for|used|own|difference)\b/.test(query) ||
      /\bexplain\b.*\b(softdent|quickbooks)\b.*\b(source|data|system|difference|vs)\b/.test(query) ||
      /\bwhich (system|source)\b.*\b(ar|revenue|production|claims|expenses)\b/.test(query) ||
      /\bsoftdent\b.*\bvs\b.*\bquickbooks\b/.test(query) ||
      /\bquickbooks\b.*\bvs\b.*\bsoftdent\b/.test(query)
    ) {
      return { intent: "sources: system guide", lane: "local", useSourceSystemGuide: true, text: "", actions: [] };
    }

    if (
      /\b(force|push|place|fill|refresh)\b.*\b(widget|dashboard|data)\b|\b(widget|dashboard)\b.*\b(force|push|place|fill|refresh)\b|\bplace data\b|\bpush data\b/.test(
        query,
      )
    ) {
      return { intent: "widgets: force placement", lane: "local", useForceWidgetPlacement: true, text: "", actions: [] };
    }

    if (/\b(source|softdent|quickbooks|freshness|sync|intake|source health)\b/.test(query) && !wantsExplain) {
      return { intent: "sources", lane: "local", useSourceHealth: true, text: "", actions: [] };
    }

    if (/\bmodels?\b|\b14b\b|\b21b\b|\b30b\b|\bllm\b|\bai lane\b|which model|are you connected|connected to a model/.test(query)) {
      return { intent: "model lanes", lane: "local", text: modelLanesText(halModels), actions: [] };
    }

    if (/\bready\b/.test(query)) {
      const ready = registryByState(halData, /ready/i);
      const list = ready.map((entry) => `- ${entry.name}: ${entry.nextAction}`).join("\n");
      return {
        intent: "registry: ready",
        lane: "local",
        text: ready.length ? `Ready to work now:\n${list}` : "Nothing is marked ready right now.",
        actions: ready.map((entry) => ({ type: "openPage", label: "Open " + entry.name, page: entry.id })),
      };
    }

    if (/read[\s-]?only|readonly|local review|review-only/.test(query)) {
      const readOnly = registryList(halData).filter((entry) =>
        /read[\s-]?only|indexed|reference|review-only|local review|manager/i.test(entry.safety),
      );
      const list = readOnly.map((entry) => `- ${entry.name}: ${entry.safety}`).join("\n");
      const text = readOnly.length
        ? `Read-only and review-only areas:\n${list}`
        : pickVariant([
            "Read-only here means I navigate, explain imports, reconcile, and draft locally — but I cannot post to QuickBooks, submit to payers, email, fax, or upload. Staff executes anything outbound.",
            "Read-only for HAL: local review, summaries, and drafts only. Ledger posting, payer contact, and file delivery stay with staff outside this program.",
          ]);
      return { intent: "registry: read-only", lane: "local", text, actions: [] };
    }

    if (/next (step|action|staff action)|do next|what should (i|we|staff) (do|review|check|open|work)/.test(query)) {
      const list = registryList(halData).map((entry) => `- ${entry.name}: ${entry.nextAction}`).join("\n");
      return { intent: "registry: next actions", lane: "local", text: `Suggested next staff actions:\n${list}`, actions: [] };
    }

    const pageId = findPage(query);
    if (pageId && !isHypotheticalQuestion(rawQuery)) {
      const info = pageInfoMap(halData, pages)[pageId] || { label: pageId, detail: "" };
      const reg = registryById(halData, pageId);
      const status = reg ? `\nStatus: ${reg.state}. Safety: ${reg.safety}. Next: ${reg.nextAction}` : "";
      if (pageId === "hal" && !wantsExplain) {
        const halStatus = halData.status || {};
        return { intent: "status", lane: "local", text: (halStatus.summary || "") + status, actions: [] };
      }
      if (wantsExplain) {
        const verbose = /glacial pace|every step|walk me through/i.test(String(rawQuery || ""));
        const explainBody = verbose
          ? `${info.label}: ${info.detail}${status}\n\nI'll walk through this slowly. First, open ${info.label} from the sidebar so widgets and registry context load together. Second, check whether imports for that page are fresh — empty tiles usually mean stale or missing SoftDent or QuickBooks exports, not hidden live data. Third, read the registry line above for state, safety, and the suggested next staff action. Fourth, name a specific widget if you want a narrower drill-down. Fifth, note anything still missing before anyone posts, emails, or contacts a payer outside NR2. HAL stays read-only here; staff executes outbound steps.`
          : `${info.label}: ${info.detail}${status}`;
        return {
          intent: "explain: " + pageId,
          lane: "local",
          text: explainBody,
          actions: pageId === "hal" ? [] : [{ type: "openPage", label: "Open " + info.label, page: pageId }],
        };
      }
      if (isPageNavigationIntent(query)) {
        return {
          intent: "navigate: " + pageId,
          lane: "local",
          text: `I can open ${info.label}. ${info.detail}${status}`,
          actions: [{ type: "openPage", label: "Open " + info.label, page: pageId }],
        };
      }
    }

    return {
      intent: "model: query",
      lane: "chat8b",
      text: "",
      useModel: true,
      prompt: rawQuery,
      actions: [],
    };
  }

  return {
    BLOCKED_RE,
    PAGE_SYNONYMS,
    FALLBACK_CONSENT,
    FALLBACK_FIREWALL,
    consentPolicy,
    consentVerdict,
    registryList,
    registryById,
    registryByState,
    modelConfig,
    modelLanes,
    runtimeReady,
    laneRuntime,
    laneReady,
    isLocalModelEndpoint,
    deriveModelLaneCards,
    deriveReasoningLanes,
    derivePriorityGroups,
    pageInfoMap,
    findPage,
    isHypotheticalQuestion,
    isOutboundActionPhrase,
    isPageNavigationIntent,
    checkFirewall,
    isFirewallActive,
    setFirewallEnabled,
    pickVariant,
    variedBlockedCapabilityReply,
    wrapAllowedCapabilityReply,
    parseCapabilityQuestion,
    matchCapabilityRoute,
    CHAT_LIMITS,
    MIN_REPLY_SENTENCES,
    isChatSizedQuestion,
    isYesNoQuestion,
    chatBudgetFor,
    trimChatReply,
    stripHalIdentityMonologue,
    buildHelpChatReply,
    localChatFallback,
    offlineModelChatMessage,
    chatShapeIssues,
    repairChatShape,
    detectUserTone,
    isFollowUpQuery,
    isCorrectionQuery,
    wantsBriefReply,
    textSimilarity,
    buildThreadContextBlock,
    pageAwareClause,
    stripChatbotFillers,
    synthesizeHandlerReply,
    progressiveDepthHint,
    buildFollowUpChips,
    adjustChatBudget,
    expandCorrectionQuery,
    applyHalPersonality,
    wrapAgentSystemPrompt,
    agentPersonalityPromptLines,
    polishChatReply,
    isSimpleActionQuery,
    buildMicroActionReply,
    expandAtMentions,
    updateSessionSummary,
    resolveFollowUpQuery,
    updateSessionSummary,
    isCodeDiscussionQuery,
    allowsMarkdownInReply,
    compressThreadForPrompt,
    detectAmbiguousQuery,
    inferPageActionsFromAnswer,
    resolveFollowUpTopic,
    isImplicitFollowUp,
    stripInternalJargon,
    stripInstructionLeaks,
    isInternalInstructionText,
    flattenMarkdownForChat,
    compressedBlockedReply,
    buildSessionRecap,
    matchCompareRoute,
    buildCompareReply,
    matchEnglishVocabRoute,
    appendEvidenceClause,
    answerLeadsCorrectly,
    answersMustLead,
    SPOKEN_LIMITS,
    spokenBudgetFor,
    toSpokenScript,
    countWords,
    countSentences,
    splitSentences,
    ensureMinSentences,
    shouldEnforceMinSentences,
    firewallVerdict,
    registryAsText,
    summarizeProgramSnapshot,
    formatProgramSnapshot,
    matchProgramRoute,
    modelLanesText,
    buildSystemPrompt,
    buildFastChatSystemPrompt,
    buildReasoningPrompt,
    buildReasoningChatPrompt,
    wantsStructuredPlan,
    buildEscalationPrompt,
    cleanModelText,
    routeHalCommand,
    sessionTemplates,
    sessionTemplateById,
    findSessionTemplate,
    createSessionState,
    toggleSessionCheck,
    sessionProgress,
    draftHandoffNote,
    validateSessionTemplates,
    matchSessionRoute,
    matchPacketRoute,
    packetConfig,
    buildEvidencePacket,
    formatEvidencePacketText,
    validateEvidencePacket,
    sourceFreshnessSummary,
    readinessConfig,
    runReadinessChecks,
    staffUseGate,
    formatReadinessSummary,
    matchReadinessRoute,
    runOperatorSmokeTest,
    formatSmokeTestSummary,
    buildHandoffSummary,
    deriveDrawerHealth,
    modelLaneDetails,
    matchOperatorRoute,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalCore;
}
if (typeof window !== "undefined") {
  window.HalCore = HalCore;
}
