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
    if (/blocked item|blocked triage/.test(q)) return sessionTemplateById(halData, "blocked-triage");
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
    const firewall = (halData && halData.firewall) || FALLBACK_FIREWALL;
    const cfg = packetConfig(halData);
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
      firewallReminder: "Blocked external actions: " + (firewall.blocked || []).join(", "),
      handoffNote: session.handoffNote || null,
      modelNote: halModels ? "Local model lanes only; firewall runs before every lane." : null,
      disclaimer: cfg.disclaimer || "Draft only · read-only · human review required before any external action",
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
    if (!packet.firewallReminder) errors.push("missing firewallReminder");
    if (!packet.disclaimer || !/human review/i.test(packet.disclaimer)) {
      errors.push("disclaimer must mention human review");
    }
    if (!packet.text || !packet.text.includes(packet.sessionLabel)) {
      errors.push("packet text must include session label");
    }
    return errors;
  }

  function matchPacketRoute(query) {
    const q = String(query).toLowerCase().trim();
    if (/clear evidence packet|clear packet/.test(q)) return { type: "clear" };
    if (/show evidence packet|show packet/.test(q)) return { type: "show" };
    if (/build evidence packet|build packet|create evidence packet/.test(q)) return { type: "build" };
    return null;
  }

  function matchSessionRoute(query) {
    const q = String(query).toLowerCase().trim();
    if (/show (active|current) session|active session|work session status|current work session/.test(q)) {
      return { type: "show" };
    }
    if (/reset (work )?session|clear session|end session/.test(q)) {
      return { type: "reset" };
    }
    if (/draft handoff|handoff note|draft session note/.test(q)) {
      return { type: "handoff" };
    }
    if (/\bstart\b/.test(q) || /begin review/.test(q)) {
      return { type: "start" };
    }
    return null;
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
          "I am the local program manager. I can open any program page, explain what each page is for, show today's priorities, start read-only work sessions, build local evidence packets, report source health, simulate the firewall, and explain model lanes. I do not submit, send, or change anything.",
        actions: [],
      };
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
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalCore;
}
if (typeof window !== "undefined") {
  window.HalCore = HalCore;
}
