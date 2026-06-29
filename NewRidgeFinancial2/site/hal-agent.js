/**
 * HAL Agent Core — planner, local tools, working/long-term memory, self-check, repair loop.
 * Sits between routing and response generation. Browser + Node compatible.
 */
const HalAgent = (function () {
  const MEMORY_KEY = "halAgentMemory";
  const REPAIR_KEY = "halRepairLog";
  const WORKING_KEY = "halWorkingMemory";
  const ARCHITECTURE_VERSION = "hal-agent-v1.1";
  const REPAIR_MAX = 100;
  const TURN_MAX = 12;
  const AGENT_BUDGET = {
    maxTools: 3,
    maxToolSummaryChars: 2400,
    maxModelContextChars: 6000,
    maxRecentTurns: 4,
  };

  const SAFETY_POLICY = {
    summary: "HAL is read-only. Draft only. Human review required. No external delivery.",
    blocked: [
      "submit", "email", "fax", "upload", "transmit", "pay", "post", "delete",
      "remove", "dispatch", "mail", "wire", "writeback", "payer contact",
    ],
    allowed: [
      "open local pages", "read program snapshot", "explain status",
      "prepare review notes", "draft journal entries locally", "create local tasks",
      "monitor sidenotes", "run readiness checks", "search local library",
    ],
    rules: [
      "Never fabricate missing import data; say what is missing.",
      "Never claim an external action was performed.",
      "If data is stale or unavailable, say so before recommending.",
      "Cite which local source or tool informed the answer when possible.",
    ],
  };

  const TOOL_DEFS = {
    read_program_snapshot: {
      label: "Read program snapshot",
      run: async (ctx) => {
        const snap = await ctx.loadProgramSnapshot();
        if (!snap) return { ok: false, summary: "Program snapshot unavailable." };
        const text = HalCore.summarizeProgramSnapshot(snap, ctx.halData);
        return { ok: true, summary: text.slice(0, 4000), snapshot: snap };
      },
    },
    read_widget_feed: {
      label: "Read manager widget feed",
      run: async (ctx) => {
        const snap = await ctx.loadProgramSnapshot();
        if (!snap || !window.HalSkills) return { ok: false, summary: "Widget feed unavailable." };
        const feed = snap.widgets || HalSkills.buildWidgetFeed(snap);
        return { ok: true, summary: HalSkills.formatWidgetFeed(feed).slice(0, 3000), feed };
      },
    },
    read_source_health: {
      label: "Read source intake health",
      run: async (ctx) => {
        const items = (ctx.halData.sources && ctx.halData.sources.items) || [];
        const list = items
          .map((item) => {
            const extra = item.freshness ? ` Freshness: ${item.freshness}.` : "";
            const warn = item.warning ? ` Warning: ${item.warning}` : "";
            return `- ${item.label} — ${item.status}: ${item.detail}${extra}${warn}`;
          })
          .join("\n");
        return { ok: true, summary: list || "No source intake items configured." };
      },
    },
    read_claims_summary: {
      label: "Read claims summary",
      run: async (ctx) => {
        const snap = await ctx.loadProgramSnapshot();
        const claims = (snap && snap.claims && snap.claims.top) || [];
        if (!window.HalSkills) return { ok: false, summary: "Claims tools unavailable." };
        const resp = HalSkills.buildClaimReadinessResponse(claims);
        return { ok: true, summary: HalSkills.formatClaimReadinessAnswer(resp).slice(0, 2500) };
      },
    },
    read_tasks: {
      label: "Read local office tasks",
      run: async (ctx) => {
        if (!window.HalSkills) return { ok: false, summary: "Task tools unavailable." };
        const metrics = HalSkills.computeTaskMetrics(ctx.halOfficeTasks || []);
        const lines = [
          `Open ${metrics.openCount} · In progress ${metrics.inProgressCount} · Blocked ${metrics.blockedCount}`,
        ];
        (ctx.halOfficeTasks || []).slice(0, 8).forEach((t) => lines.push(`- [${t.status}] ${t.title}`));
        return { ok: true, summary: lines.join("\n") };
      },
    },
    read_work_session: {
      label: "Read active work session",
      run: async (ctx) => {
        if (!ctx.halWorkSession) return { ok: true, summary: "No active work session." };
        return { ok: true, summary: ctx.workSessionStatusText() };
      },
    },
    search_document_library: {
      label: "Search document library",
      run: async (ctx, args) => {
        const snap = await ctx.loadProgramSnapshot();
        const docs = (snap && snap.library && (snap.library.top || snap.library.docs)) || [];
        if (!window.HalSkills) return { ok: false, summary: "Library search unavailable." };
        const q = String(args.query || "").trim() || "compliance";
        const rag = HalSkills.answerFromLibrary(q, docs, 4);
        return { ok: true, summary: HalSkills.formatRagResult(rag).slice(0, 2500), query: q };
      },
    },
    explain_firewall: {
      label: "Explain external-action firewall",
      run: async (ctx) => {
        const fw = (ctx.halData && ctx.halData.firewall) || HalCore.FALLBACK_FIREWALL;
        return {
          ok: true,
          summary: `${fw.summary}\nBlocked: ${(fw.blocked || []).join(", ")}.\nAllowed: ${(fw.allowed || []).join(", ")}.`,
        };
      },
    },
    run_readiness_check: {
      label: "Run readiness check",
      run: async (ctx) => {
        const report = ctx.runReadinessDiagnostics();
        return { ok: true, summary: HalCore.formatReadinessSummary(report).slice(0, 3000) };
      },
    },
  };

  let workingMemory = createWorkingMemory();
  let longTermMemory = createLongTermMemory();
  let repairLog = [];
  let memoryLoaded = false;
  let memoryDirty = false;
  let health = {
    architectureVersion: ARCHITECTURE_VERSION,
    budget: AGENT_BUDGET,
    lastIntent: null,
    lastQuestionType: null,
    lastTools: [],
    lastSelfCheck: "none",
    lastLatencyMs: 0,
    lastModelLane: null,
    repairCount: 0,
    updatedAt: null,
  };

  function createWorkingMemory() {
    return {
      sessionId: Date.now(),
      turns: [],
      focus: null,
      currentPage: null,
      lastIntent: null,
      lastTools: [],
      activeWorkSession: false,
      updatedAt: new Date().toISOString(),
    };
  }

  function createLongTermMemory() {
    return {
      preferences: {
        reportStyle: "concise",
        priorityPages: ["financial", "claims", "ar", "quickbooks"],
        emphasizeAccountingReview: true,
      },
      notes: [],
      updatedAt: new Date().toISOString(),
    };
  }

  function hasUseFlag(route) {
    if (!route) return false;
    return Object.keys(route).some((k) => k.startsWith("use") && route[k] === true);
  }

  function classifyQuestion(query, route) {
    const intent = route.intent || "";
    if (intent === "blocked: firewall") return "unsafe_external";
    if (intent === "help") return "help";
    if (/^navigate:/.test(intent)) return "navigation";
    if (/^explain:/.test(intent)) return "explanation";
    if (route.useModel) return "open_chat";
    if (route.useReasoning) return "planning";
    if (route.useEscalation) return "escalation";
    if (/widget|import|briefing|reconciliation/i.test(query)) return "widget_analysis";
    if (/task|office|attention/i.test(query)) return "office_ops";
    if (/claim|denied|packet/i.test(query)) return "claims";
    if (/journal|accounting/i.test(query)) return "accounting";
    return "local_command";
  }

  function buildPlan(query, route, working, longTerm) {
    const intent = route.intent || "";
    const isUnsafe = intent === "blocked: firewall";
    const tools = [];

    if (isUnsafe) {
      return {
        questionType: "unsafe_external",
        needsData: false,
        tools: ["explain_firewall"],
        isUnsafe: true,
        useModelEnhancement: false,
        needsClarification: false,
        lane: route.lane,
        intent,
      };
    }

    if (route.useProgramSnapshot || route.useModel || route.useReasoning || route.useEscalation) {
      tools.push("read_program_snapshot");
    }
    if (route.useWidgetFeed || route.useWidgetGuidance || route.useWidgetShow || route.useWidgetFillSuggestions) {
      tools.push("read_widget_feed");
    }
    if (route.useClaimReadiness || /\b(claim|denied|packet)\b/i.test(query)) tools.push("read_claims_summary");
    if (route.useOfficeAttention || route.useTaskList || route.useTaskCreate || /\b(task|office manager|attention)\b/i.test(query)) {
      tools.push("read_tasks");
    }
    if (route.useDocRag || /\b(library|search|compliance|policy)\b/i.test(query)) {
      tools.push("search_document_library");
    }
    if (route.useImportStatus || route.useImportRefresh || /\b(source|freshness|import|softdent|quickbooks)\b/i.test(query)) {
      tools.push("read_source_health");
    }
    if (working.activeWorkSession || route.useSessionShow || route.useSessionHandoff || route.usePacketBuild || route.usePacketShow) {
      tools.push("read_work_session");
    }
    if (route.useReadinessRun || route.useReadinessGate || /\breadiness\b/i.test(query)) {
      tools.push("run_readiness_check");
    }
    if (intent === "firewall" || /\bfirewall\b/i.test(query)) tools.push("explain_firewall");

    const uniqueTools = [...new Set(tools)].slice(0, AGENT_BUDGET.maxTools);

    return {
      questionType: classifyQuestion(query, route),
      needsData: uniqueTools.length > 0,
      tools: uniqueTools,
      isUnsafe: false,
      useModelEnhancement: !!(route.useModel || route.useReasoning || route.useEscalation),
      needsClarification: !route.text && !hasUseFlag(route),
      lane: route.lane,
      intent,
      budget: AGENT_BUDGET,
      preferences: longTerm.preferences,
    };
  }

  async function runTools(toolIds, ctx, query) {
    const results = {};
    for (const id of toolIds) {
      const def = TOOL_DEFS[id];
      if (!def) continue;
      try {
        results[id] = await def.run(ctx, { query });
      } catch (error) {
        results[id] = { ok: false, summary: error && error.message ? error.message : String(error) };
      }
    }
    return results;
  }

  function summarizeToolResults(toolResults) {
    return Object.entries(toolResults || {})
      .map(([id, res]) => {
        const label = (TOOL_DEFS[id] && TOOL_DEFS[id].label) || id;
        const body = res && res.summary ? String(res.summary).slice(0, AGENT_BUDGET.maxToolSummaryChars) : "No data.";
        return `### ${label}\n${body}`;
      })
      .join("\n\n");
  }

  function summarizeWorkingMemory(working) {
    const recent = (working.turns || []).slice(-AGENT_BUDGET.maxRecentTurns);
    if (!recent.length) return "";
    return recent
      .map((t) => `${t.role}: ${String(t.text).slice(0, 160)}${t.intent ? ` [${t.intent}]` : ""}`)
      .join("\n");
  }

  function buildAgentSystemPrompt(ctx, plan, toolResults, working, longTerm) {
    const base =
      plan.questionType === "planning"
        ? HalCore.buildReasoningPrompt(ctx.halData, null)
        : plan.questionType === "escalation"
          ? HalCore.buildEscalationPrompt(ctx.halData, null)
          : HalCore.buildSystemPrompt(ctx.halData, null);

    const parts = [
      base,
      "",
      "AGENT POLICY (always enforce):",
      SAFETY_POLICY.summary,
      "Blocked: " + SAFETY_POLICY.blocked.join(", ") + ".",
      "Rules:",
      ...SAFETY_POLICY.rules.map((r) => "- " + r),
    ];

    if (longTerm.preferences) {
      parts.push(
        "",
        "Office preferences:",
        `- Report style: ${longTerm.preferences.reportStyle}`,
        `- Priority pages: ${(longTerm.preferences.priorityPages || []).join(", ")}`,
      );
    }

    const toolText = summarizeToolResults(toolResults);
    if (toolText) {
      parts.push("", "Tool results gathered for this question:", toolText.slice(0, AGENT_BUDGET.maxModelContextChars));
    }

    const turnText = summarizeWorkingMemory(working);
    if (turnText) {
      parts.push("", "Recent conversation context:", turnText);
    }

    parts.push(
      "",
      "Before answering, verify: answer the question, do not invent data, refuse external actions, note missing data, and keep the reply practical for staff review.",
    );
    return parts.join("\n");
  }

  function selfCheckResponse(query, text, plan, toolResults, route) {
    const issues = [];
    const body = String(text || "").trim();

    if (!body) issues.push("empty_response");
    if (plan.isUnsafe && !/human review|firewall|blocked|external|cannot|can't|will not/i.test(body)) {
      issues.push("unsafe_not_refused");
    }
    if (!plan.isUnsafe && /\b(I (submitted|sent|emailed|uploaded|posted|deleted|paid|wired|faxed))\b/i.test(body)) {
      issues.push("claimed_external_action");
    }
    if (plan.useModelEnhancement && body.length < 20) issues.push("too_short");

    let repaired = null;
    if (issues.includes("empty_response")) {
      repaired =
        (route && route.text) ||
        "I could not produce a safe answer from local data. Try asking what HAL can do, or name a page, widget, or review task.";
    } else if (issues.includes("unsafe_not_refused")) {
      repaired =
        "That is an external action, so it stops at the firewall and needs human review. I can open the right page and prepare review notes, but a person must take the external step.";
    } else if (issues.includes("claimed_external_action")) {
      repaired =
        body.replace(/\bI (submitted|sent|emailed|uploaded|posted|deleted|paid|wired|faxed)\b/gi, "A human must") +
        "\n\n(Local draft only — external delivery requires human review.)";
    }

    return { pass: issues.length === 0, issues, repaired };
  }

  function recordTurn(role, text, meta) {
    workingMemory.turns.push({
      role,
      text: String(text).slice(0, 500),
      intent: meta && meta.intent ? meta.intent : null,
      tools: meta && meta.tools ? meta.tools : [],
      at: new Date().toISOString(),
    });
    if (workingMemory.turns.length > TURN_MAX) workingMemory.turns = workingMemory.turns.slice(-TURN_MAX);
    if (meta && meta.intent) workingMemory.lastIntent = meta.intent;
    if (meta && meta.tools) workingMemory.lastTools = meta.tools;
    if (meta && meta.focus) workingMemory.focus = meta.focus;
    workingMemory.updatedAt = new Date().toISOString();
    memoryDirty = true;
  }

  function logRepair(entry, persistFn) {
    const row = Object.assign({ at: new Date().toISOString() }, entry);
    repairLog.unshift(row);
    if (repairLog.length > REPAIR_MAX) repairLog = repairLog.slice(0, REPAIR_MAX);
    health.repairCount = repairLog.length;
    health.lastSelfCheck = "repair:" + (entry.issues || []).join(",");
    health.updatedAt = row.at;
    memoryDirty = true;
    if (typeof persistFn === "function") persistFn(REPAIR_KEY, repairLog);
    return row;
  }

  async function loadMemory(ctx) {
    // Load exactly once per session; subsequent queries reuse in-memory state.
    memoryLoaded = true;
    if (!ctx || typeof ctx.persistGet !== "function") return;
    try {
      const savedWorking = await ctx.persistGet(WORKING_KEY);
      const savedLong = await ctx.persistGet(MEMORY_KEY);
      const savedRepair = await ctx.persistGet(REPAIR_KEY);
      if (savedWorking && Array.isArray(savedWorking.turns)) workingMemory = savedWorking;
      if (savedLong && savedLong.preferences) longTermMemory = savedLong;
      if (Array.isArray(savedRepair)) repairLog = savedRepair;
    } catch {
      /* memory load is best-effort */
    }
  }

  async function saveMemory(ctx) {
    // Only write when something actually changed; callers fire-and-forget this
    // off the response hot path.
    if (!ctx || typeof ctx.persistSet !== "function" || !memoryDirty) return;
    memoryDirty = false;
    longTermMemory.updatedAt = new Date().toISOString();
    try {
      await ctx.persistSet(WORKING_KEY, workingMemory);
      await ctx.persistSet(MEMORY_KEY, longTermMemory);
      await ctx.persistSet(REPAIR_KEY, repairLog);
    } catch {
      memoryDirty = true; // retry on the next turn
    }
  }

  async function enhanceModelCall(ctx, route, query, plan, toolResults, onToken) {
    const agentPrompt = buildAgentSystemPrompt(ctx, plan, toolResults, workingMemory, longTermMemory);

    // De-dup: when a snapshot-bearing tool already ran, its summary is in the
    // agent prompt, so do NOT also append the full program context (it would
    // double the prompt and slow time-to-first-token).
    const snapshotToolRan = (plan.tools || []).some(
      (t) => t === "read_program_snapshot" || t === "read_widget_feed" || t === "read_claims_summary",
    );
    // The fast chat lane gets a tighter context cap for snappier first tokens;
    // the deeper reasoning/escalation lanes keep the full budget.
    const ctxCap = route.useModel ? 3000 : AGENT_BUDGET.maxModelContextChars;
    let combinedPrompt = agentPrompt;
    if (!snapshotToolRan) {
      const programContext = await ctx.getProgramContextText();
      if (programContext) combinedPrompt += "\n\nProgram context:\n" + programContext.slice(0, ctxCap);
    }

    if (route.useEscalation) {
      if (!ctx.escalationModelReady()) return { text: ctx.offlineModelMessage("escalate30b"), lane: "escalate30b · offline" };
      const em = ctx.escalationModelConfig();
      // Escalation runs a hidden think pass; skip streaming so raw reasoning is
      // not flashed to the user before it is cleaned out.
      const text = await ctx.runModel(em, combinedPrompt, query, "Local escalation draft");
      return { text, lane: "escalate30b" };
    }
    if (route.useReasoning) {
      if (!ctx.reasoningModelReady()) return { text: ctx.offlineModelMessage("reason21b"), lane: "reason21b · offline" };
      const rm = ctx.reasoningModelConfig();
      const text = await ctx.runModel(rm, combinedPrompt, query, "Local reasoning plan", onToken);
      return { text, lane: "reason21b" };
    }
    if (route.useModel) {
      if (!ctx.localModelReady()) return { text: ctx.offlineModelMessage("chat14b"), lane: "chat14b · offline" };
      const lm = ctx.localModelConfig();
      const text = await ctx.runModel(lm, combinedPrompt, query, "Local chat draft", onToken);
      return { text, lane: "chat14b" };
    }
    return null;
  }

  /**
   * Main agent entry: plan → enrich with tools → execute route → self-check → repair log.
   * ctx.executeRoute(route, query, toolResults) must return { text, lane, actions, intent }.
   */
  async function processQuery(query, ctx) {
    const trimmed = String(query).trim();
    if (!trimmed) return null;
    const startedAt = Date.now();

    // Lazy memory: load once per session, never on the per-query hot path again.
    if (!memoryLoaded) await loadMemory(ctx);
    workingMemory.currentPage = ctx.getCurrentPage ? ctx.getCurrentPage() : null;
    workingMemory.activeWorkSession = !!(ctx.halWorkSession);
    recordTurn("user", trimmed, { focus: workingMemory.currentPage });

    const route = HalCore.routeHalCommand(ctx.halData, ctx.halModels, ctx.pages, trimmed);
    const plan = buildPlan(trimmed, route, workingMemory, longTermMemory);
    const isModelLane = !!(route.useModel || route.useReasoning || route.useEscalation);

    // Instant local-command path: deterministic routes that need no tools and no
    // model run straight through the executor so they answer with zero extra
    // latency (template responses are inherently within the safety policy).
    if (!isModelLane && !plan.useModelEnhancement && (!plan.tools || plan.tools.length === 0)) {
      const fast = await ctx.executeRoute(route, trimmed, {});
      if (fast) {
        recordTurn("hal", fast.text, { intent: fast.intent, tools: [] });
        health = {
          architectureVersion: ARCHITECTURE_VERSION,
          budget: AGENT_BUDGET,
          lastIntent: route.intent,
          lastQuestionType: plan.questionType,
          lastTools: [],
          lastSelfCheck: "instant",
          lastLatencyMs: Date.now() - startedAt,
          lastModelLane: null,
          repairCount: repairLog.length,
          updatedAt: new Date().toISOString(),
        };
        saveMemory(ctx);
        return Object.assign({}, fast, {
          plan,
          toolResults: {},
          selfCheck: { pass: true, issues: [], instant: true },
        });
      }
    }

    const toolResults = plan.tools.length ? await runTools(plan.tools, ctx, trimmed) : {};

    let outcome;
    if (plan.useModelEnhancement) {
      try {
        const enhanced = await enhanceModelCall(ctx, route, trimmed, plan, toolResults, ctx.onToken);
        if (enhanced) {
          outcome = {
            text: enhanced.text,
            lane: enhanced.lane,
            actions: [],
            intent: route.intent,
          };
        }
      } catch {
        outcome = null;
      }
    }

    if (!outcome) {
      outcome = await ctx.executeRoute(route, trimmed, toolResults);
    }

    const checked = selfCheckResponse(trimmed, outcome.text, plan, toolResults, route);
    if (!checked.pass) {
      logRepair(
        {
          query: trimmed,
          intent: route.intent,
          issues: checked.issues,
          example: String(outcome.text || "").slice(0, 200),
          tools: plan.tools,
        },
        ctx.persistSet,
      );
      if (checked.repaired) outcome.text = checked.repaired;
    }

    recordTurn("hal", outcome.text, { intent: outcome.intent, tools: plan.tools });
    health = {
      architectureVersion: ARCHITECTURE_VERSION,
      budget: AGENT_BUDGET,
      lastIntent: route.intent,
      lastQuestionType: plan.questionType,
      lastTools: plan.tools,
      lastSelfCheck: checked.pass ? "pass" : "repaired:" + checked.issues.join(","),
      lastLatencyMs: Date.now() - startedAt,
      lastModelLane: plan.useModelEnhancement ? route.lane : null,
      repairCount: repairLog.length,
      updatedAt: new Date().toISOString(),
    };
    saveMemory(ctx);

    return Object.assign({}, outcome, {
      plan,
      toolResults,
      selfCheck: checked,
    });
  }

  function getWorkingMemory() {
    return Object.assign({}, workingMemory);
  }

  function getLongTermMemory() {
    return Object.assign({}, longTermMemory);
  }

  function getRepairLog() {
    return repairLog.slice();
  }

  function getHealth() {
    return Object.assign({}, health, {
      repairCount: repairLog.length,
      workingTurns: (workingMemory.turns || []).length,
      memoryUpdatedAt: longTermMemory.updatedAt,
    });
  }

  function updatePreferences(patch, persistFn) {
    longTermMemory.preferences = Object.assign({}, longTermMemory.preferences, patch || {});
    longTermMemory.updatedAt = new Date().toISOString();
    memoryDirty = true;
    if (typeof persistFn === "function") persistFn(MEMORY_KEY, longTermMemory);
    return longTermMemory.preferences;
  }

  return {
    ARCHITECTURE_VERSION,
    AGENT_BUDGET,
    SAFETY_POLICY,
    TOOL_DEFS,
    buildPlan,
    runTools,
    selfCheckResponse,
    buildAgentSystemPrompt,
    processQuery,
    loadMemory,
    saveMemory,
    getWorkingMemory,
    getLongTermMemory,
    getRepairLog,
    getHealth,
    updatePreferences,
    logRepair,
  };
})();

if (typeof window !== "undefined") window.HalAgent = HalAgent;
if (typeof module !== "undefined" && module.exports) module.exports = HalAgent;
