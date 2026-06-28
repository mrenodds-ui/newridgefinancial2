/**
 * HAL core: routing, firewall, registry, and model-lane logic.
 * Browser + Node compatible (no DOM).
 */
const HalCore = (function () {
  const BLOCKED_RE =
    /\b(submit|submits|submitting|send|sends|sending|email|emails|emailing|e-?mail|fax|faxes|faxing|upload|uploads|uploading|transmit|transmits|transmitting|pay|paying|approve|approves|approving|deny|denies|denying|delete|deletes|deleting|remove|removes|removing|writeback|write back|dispatch|dispatches|dispatching|mail|mailing)\b/;

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

  const FALLBACK_FIREWALL = {
    summary: "External actions are blocked by design.",
    blocked: ["No email", "No fax", "No upload", "No payer contact", "No writeback", "No submission"],
    allowed: ["Open local program pages", "Explain local status", "Prepare review notes", "Flag missing information"],
  };

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

  function modelLanes(halModels) {
    return (halModels && halModels.lanes) || [];
  }

  function runtimeReady(halModels, runtime) {
    const config = modelConfig(halModels);
    return config.mode === "online" && runtime && runtime.enabled === true && !!runtime.endpoint && !!runtime.model;
  }

  function laneRuntime(halModels, laneId) {
    const config = modelConfig(halModels);
    if (laneId === "chat14b") return config.localModel || null;
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

  function checkFirewall(query) {
    return BLOCKED_RE.test(String(query).toLowerCase().trim());
  }

  function firewallVerdict(query, firewall) {
    const fw = firewall || FALLBACK_FIREWALL;
    if (checkFirewall(query)) {
      return {
        allowed: false,
        intent: "blocked: firewall",
        text:
          "Blocked — external action. " +
          fw.summary +
          " A human must perform this step outside HAL.",
      };
    }
    return {
      allowed: true,
      intent: "firewall: allowed",
      text: "Allowed — local/read-only action. HAL can navigate, explain, or draft review notes only.",
    };
  }

  function registryAsText(halData) {
    return registryList(halData)
      .map((entry) => `- ${entry.name} [${entry.state}; ${entry.safety}]: ${entry.purpose} Next: ${entry.nextAction}`)
      .join("\n");
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

  function buildSystemPrompt(halData) {
    const firewall = (halData && halData.firewall) || FALLBACK_FIREWALL;
    return [
      "You are HAL, the local read-only program manager for NewRidgeFinancial 2.0, a dental-practice financial program.",
      "Answer briefly and only about this program and its pages. If you are unsure, say so.",
      "You are read-only. You never submit, email, fax, upload, post, or write back. A human performs any external step.",
      "Blocked external actions: " + (firewall.blocked || []).join(", ") + ".",
      "If the user asks for an external action, refuse and say it needs human review.",
      "Program pages and current status:",
      registryAsText(halData),
    ].join("\n");
  }

  function buildReasoningPrompt(halData) {
    const firewall = (halData && halData.firewall) || FALLBACK_FIREWALL;
    const priorities = (halData.priorities && halData.priorities.items) || [];
    return [
      "You are HAL's reasoning lane for NewRidgeFinancial 2.0, a dental-practice financial program.",
      "Produce a short, structured, prioritized plan based only on the local program state below.",
      "Order work by readiness and risk: handle Needs Review and Blocked items carefully, and never advance payer-facing work without human review.",
      "You are read-only. You never submit, email, fax, upload, post, or write back. A human performs any external step.",
      "Blocked external actions: " + (firewall.blocked || []).join(", ") + ".",
      "Program pages and current status:",
      registryAsText(halData),
      "Known operator priorities:",
      priorities.map((item, index) => `${index + 1}. ${item}`).join("\n"),
      "Respond with a brief numbered plan. Keep it under 8 steps.",
    ].join("\n");
  }

  function buildEscalationPrompt(halData) {
    const firewall = (halData && halData.firewall) || FALLBACK_FIREWALL;
    return [
      "You are HAL's escalation lane for NewRidgeFinancial 2.0, a dental-practice financial program.",
      "Give a careful second-opinion review for a complex or high-risk question.",
      "Be conservative: call out risks, assumptions, and exactly what a human must verify before acting.",
      "You are read-only. You never submit, email, fax, upload, post, or write back. A human performs any external step.",
      "Blocked external actions: " + (firewall.blocked || []).join(", ") + ".",
      "Program pages and current status:",
      registryAsText(halData),
      "Respond with: a short risk assessment, then a numbered list of what a human should verify.",
    ].join("\n");
  }

  function cleanModelText(text) {
    let out = String(text);
    out = out.replace(/<think>[\s\S]*?<\/think>/gi, "");
    out = out.replace(/<\/?think>/gi, "");
    out = out.replace(/\*[^*]+\*/g, "");
    const monologueStart = /^(Okay|Hmm|Let me|Wait|Pauses|Nods|Double-checks|Starts structuring)/i;
    if (monologueStart.test(out.trim())) {
      const riskIdx = out.search(/\*\*Risk Assessment\*\*|Risk Assessment|Human Verification|DO NOT PROCEED/i);
      if (riskIdx > 0) out = out.slice(riskIdx);
    }
    return out.trim();
  }

  function routeHalCommand(halData, halModels, pages, rawQuery) {
    const query = String(rawQuery).toLowerCase().trim();
    const firewall = (halData && halData.firewall) || FALLBACK_FIREWALL;

    if (checkFirewall(query)) {
      return {
        intent: "blocked: firewall",
        lane: "firewall",
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
        lane: "local",
        text:
          "I am the local program manager. I can open any program page, explain what each page is for, show today's priorities, report read-only source health, simulate the firewall, and explain model lanes. I do not submit, send, or change anything.",
        actions: [],
      };
    }

    const wantsExplain = /\b(explain|what is|what's|whats|what does|tell me about|describe|purpose of)\b/.test(query);

    if (/second opinion|escalat|double[\s-]?check|high[\s-]?risk|complex case|deep review|review carefully|sanity check|scrutin/.test(query)) {
      return { intent: "escalation", lane: "escalate30b", text: "", useEscalation: true, prompt: rawQuery, actions: [] };
    }

    if (/prioriti[sz]e|make a plan|draft a plan|\bplan (my|for|the)\b|analy[sz]e|reason through|think through|recommend|\bstrategy\b|focus first|where (do|should) (i|we) start/.test(query)) {
      return { intent: "reasoning", lane: "reason21b", text: "", useReasoning: true, prompt: rawQuery, actions: [] };
    }

    if (/\bpriorit|needs attention|attention today|what needs|to-?do|\btoday\b/.test(query)) {
      const items = (halData.priorities && halData.priorities.items) || [];
      const list = items.map((item, index) => `${index + 1}. ${item}`).join("\n");
      return { intent: "priorities", lane: "local", text: `Today's operator priorities:\n${list}`, actions: [] };
    }

    if (/\b(firewall|external action|boundary|guardrail|safety|are you allowed)\b/.test(query)) {
      return {
        intent: "firewall",
        lane: "local",
        text: `${firewall.summary}\nBlocked: ${firewall.blocked.join(", ")}.\nAllowed: ${firewall.allowed.join(", ")}.`,
        actions: [],
      };
    }

    if (/\b(source|softdent|quickbooks|freshness|sync|intake|source health)\b/.test(query) && !wantsExplain) {
      const items = (halData.sources && halData.sources.items) || [];
      const list = items
        .map((item) => {
          const extra = item.freshness ? ` Freshness: ${item.freshness}.` : "";
          const warn = item.warning ? ` Warning: ${item.warning}` : "";
          return `- ${item.label} — ${item.status}: ${item.detail}${extra}${warn}`;
        })
        .join("\n");
      return { intent: "sources", lane: "local", text: `Read-only source intake status:\n${list}`, actions: [] };
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

    if (/\bblocked\b|needs review|waiting on/.test(query)) {
      const waiting = registryList(halData).filter((entry) => /blocked|needs review/i.test(entry.state));
      const list = waiting.map((entry) => `- ${entry.name} (${entry.state}): ${entry.nextAction}`).join("\n");
      return {
        intent: "registry: blocked",
        lane: "local",
        text: waiting.length ? `Waiting or needs review:\n${list}` : "Nothing is blocked right now.",
        actions: waiting.map((entry) => ({ type: "openPage", label: "Open " + entry.name, page: entry.id })),
      };
    }

    if (/read[\s-]?only|readonly/.test(query)) {
      const readOnly = registryList(halData).filter((entry) =>
        /read[\s-]?only|indexed|reference|review-only|local review|manager/i.test(entry.safety),
      );
      const list = readOnly.map((entry) => `- ${entry.name}: ${entry.safety}`).join("\n");
      return { intent: "registry: read-only", lane: "local", text: `Read-only and review-only areas:\n${list}`, actions: [] };
    }

    if (/next (step|action)|do next|what should/.test(query)) {
      const list = registryList(halData).map((entry) => `- ${entry.name}: ${entry.nextAction}`).join("\n");
      return { intent: "registry: next actions", lane: "local", text: `Suggested next staff actions:\n${list}`, actions: [] };
    }

    const pageId = findPage(query);
    if (pageId) {
      const info = pageInfoMap(halData, pages)[pageId] || { label: pageId, detail: "" };
      const reg = registryById(halData, pageId);
      const status = reg ? `\nStatus: ${reg.state}. Safety: ${reg.safety}. Next: ${reg.nextAction}` : "";
      if (pageId === "hal" && !wantsExplain) {
        const halStatus = halData.status || {};
        return { intent: "status", lane: "local", text: (halStatus.summary || "") + status, actions: [] };
      }
      if (wantsExplain) {
        return {
          intent: "explain: " + pageId,
          lane: "local",
          text: `${info.label}: ${info.detail}${status}`,
          actions: pageId === "hal" ? [] : [{ type: "openPage", label: "Open " + info.label, page: pageId }],
        };
      }
      return {
        intent: "navigate: " + pageId,
        lane: "local",
        text: `I can open ${info.label}. ${info.detail}${status}`,
        actions: [{ type: "openPage", label: "Open " + info.label, page: pageId }],
      };
    }

    return {
      intent: "model: query",
      lane: "chat14b",
      text: "",
      useModel: true,
      prompt: rawQuery,
      actions: [],
    };
  }

  return {
    BLOCKED_RE,
    PAGE_SYNONYMS,
    FALLBACK_FIREWALL,
    registryList,
    registryById,
    registryByState,
    modelConfig,
    modelLanes,
    runtimeReady,
    laneRuntime,
    laneReady,
    deriveModelLaneCards,
    deriveReasoningLanes,
    derivePriorityGroups,
    pageInfoMap,
    findPage,
    checkFirewall,
    firewallVerdict,
    registryAsText,
    modelLanesText,
    buildSystemPrompt,
    buildReasoningPrompt,
    buildEscalationPrompt,
    cleanModelText,
    routeHalCommand,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalCore;
}
if (typeof window !== "undefined") {
  window.HalCore = HalCore;
}
