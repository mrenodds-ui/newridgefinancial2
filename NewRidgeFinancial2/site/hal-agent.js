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
    summary: "HAL is the internal office manager. Local coordination only. External firewall locked. Human review required for outbound actions.",
    blocked: [
      "submit", "email", "fax", "upload", "transmit", "pay", "post", "delete",
      "remove", "dispatch", "mail", "wire", "writeback", "payer contact",
    ],
    allowed: [
      "open local pages", "read program snapshot", "explain status",
      "prepare review notes", "draft journal entries locally", "create local tasks",
      "monitor sidenotes", "run readiness checks", "search local library",
      "refresh local imports", "place verified data into local dashboards/widgets",
      "prioritize office work", "publish daily office briefings",
      "research public web docs for practice reference (no PHI sent)",
    ],
    rules: [
      "Apply metacognition: self-check every answer against tool results and missing-data rules before responding.",
      "Use mental time travel: compare required calendar months (current + prior) to loaded SoftDent/QuickBooks exports for trend and close widgets.",
      "HAL is the internal office manager; external writeback and outbound actions remain blocked.",
      "Sound like a steady office teammate: short plain paragraphs, no bullet lists unless the user asks, no chatbot closings.",
      "Never fabricate missing import data; say what is missing.",
      "Never claim an external action was performed.",
      "If data is stale or unavailable, say so before recommending.",
      "Cite which local source or tool informed the answer when possible.",
      "When web research tool results are present, use them for public reference context and say they are not verified against this practice's live data.",
      "When planning or prioritizing, prefer the proactive office manager assessment over generic advice.",
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
    read_widget_contract: {
      label: "Read enforced widget contract",
      run: async () => {
        const contract =
          typeof WidgetContract !== "undefined"
            ? WidgetContract
            : typeof window !== "undefined" && window.WidgetContract
              ? window.WidgetContract
              : null;
        if (!contract || typeof contract.formatAllContractsForHal !== "function") {
          return { ok: false, summary: "Widget contract unavailable." };
        }
        return { ok: true, summary: contract.formatAllContractsForHal().slice(0, 4000) };
      },
    },
    read_widget_master_chart: {
      label: "Read widget master chart",
      run: async (ctx) => {
        const snap = ctx && typeof ctx.loadProgramSnapshot === "function" ? await ctx.loadProgramSnapshot() : null;
        const chart =
          typeof HalWidgetMasterChart !== "undefined"
            ? HalWidgetMasterChart
            : typeof window !== "undefined" && window.HalWidgetMasterChart
              ? window.HalWidgetMasterChart
              : (() => {
                  try {
                    return require("./hal-widget-master-chart.js");
                  } catch {
                    return null;
                  }
                })();
        if (!chart || typeof chart.formatForHal !== "function") {
          return { ok: false, summary: "Widget master chart unavailable." };
        }
        const feed =
          (snap && snap.widgets) || (window.HalSkills && HalSkills.buildWidgetFeed(snap)) || ctx.halWidgetFeed || null;
        return {
          ok: true,
          summary: chart.formatForHal(feed).slice(0, 6000),
          chart: chart.all ? chart.all(feed) : null,
        };
      },
    },
    read_source_health: {
      label: "Read source intake health",
      run: async (ctx) => {
        const snap = await ctx.loadProgramSnapshot();
        const feed =
          (snap && snap.widgets) || (window.HalSkills && HalSkills.buildWidgetFeed(snap)) || ctx.halWidgetFeed || {};
        const staticItems = (ctx.halData.sources && ctx.halData.sources.items) || [];
        let summary = HalSkills.formatSourceHealthText(feed.sourceHealth, staticItems);
        const issues = snap && snap.runtimeIssues;
        if (issues && issues.length) {
          summary += "\n\nRuntime issues:\n" + issues.map((item) => `- ${item.source}: ${item.message}`).join("\n");
        }
        return { ok: true, summary };
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
        const tasks =
          typeof ctx.getOfficeTasks === "function"
            ? await ctx.getOfficeTasks()
            : (await ctx.loadProgramSnapshot())?.officeTasks || ctx.halOfficeTasks || [];
        const metrics = HalSkills.computeTaskMetrics(tasks);
        const lines = [
          `Open ${metrics.openCount} · In progress ${metrics.inProgressCount} · Blocked ${metrics.blockedCount}`,
        ];
        tasks.slice(0, 8).forEach((t) => lines.push(`- [${t.status}] ${t.title}`));
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
    research_web: {
      label: "Research public web (practice reference)",
      run: async (ctx, args) => {
        const cfg = ctx.halModels && ctx.halModels.config && ctx.halModels.config.webResearch;
        if (!cfg || cfg.enabled !== true) {
          return { ok: false, summary: "Web research is disabled in HAL config." };
        }
        const bridge =
          typeof DesktopBridge !== "undefined"
            ? DesktopBridge
            : typeof window !== "undefined" && window.DesktopBridge
              ? window.DesktopBridge
              : null;
        if (!bridge || typeof bridge.webResearch !== "function") {
          return { ok: false, summary: "Web research requires the NR2 desktop app." };
        }
        const q = String(args.query || "").trim();
        if (!q) return { ok: false, summary: "No query for web research." };
        const payload = await bridge.webResearch(q, { maxResults: cfg.maxResults || 5, enrich: true });
        if (!payload || payload.ok === false) {
          const err = (payload && (payload.error || payload.policy)) || "lookup failed";
          return { ok: false, summary: `Web research unavailable: ${err}` };
        }
        const lines = (payload.results || []).map((row, idx) => {
          const title = row.title || "Result";
          const snippet = row.snippet || "";
          const url = row.url || "";
          return `${idx + 1}. ${title}\n   ${snippet}${url ? `\n   ${url}` : ""}`;
        });
        const header = `Public web research for: ${payload.query || q}`;
        const warning = payload.warnings && payload.warnings.length ? `\nSanitization: ${payload.warnings.join(" ")}` : "";
        lastWebResearch = payload;
        return {
          ok: true,
          summary: `${header}${warning}\n\n${lines.join("\n\n")}`.slice(0, 3500),
          research: payload,
        };
      },
    },
    remember_fact: {
      label: "Save learned fact to durable memory",
      run: async (ctx, args) => {
        const bridge =
          typeof DesktopBridge !== "undefined"
            ? DesktopBridge
            : typeof window !== "undefined" && window.DesktopBridge
              ? window.DesktopBridge
              : null;
        if (!bridge || typeof bridge.rememberHalFact !== "function") {
          return { ok: false, summary: "Learning requires the NR2 desktop app." };
        }
        const text = String(args.text || args.query || "").trim();
        if (!text) return { ok: false, summary: "No fact text to remember." };
        try {
          const saved = await bridge.rememberHalFact(text, { source: args.source || "staff:remember" });
          approvedMemories = ((saved && (await bridge.listHalMemories())) || {}).items || approvedMemories;
          return {
            ok: true,
            summary: `Saved to durable HAL memory (${saved.memory && saved.memory.id ? saved.memory.id : "learned"}). Future answers may use this as guidance.`,
            memory: saved.memory,
          };
        } catch (error) {
          return { ok: false, summary: error && error.message ? error.message : String(error) };
        }
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
    read_proactive_briefing: {
      label: "Read proactive program assessment",
      run: async (ctx) => {
        if (!window.HalProactive) return { ok: false, summary: "Proactive manager unavailable." };
        const briefing =
          (ctx.runProactiveCycle && (await ctx.runProactiveCycle())) ||
          HalProactive.getLastBriefing() ||
          (await HalProactive.runCycle(ctx));
        if (!briefing) return { ok: false, summary: "Proactive briefing unavailable." };
        return { ok: true, summary: HalProactive.formatProactiveBriefing(briefing).slice(0, 4000), briefing };
      },
    },
    read_office_briefing: {
      label: "Read daily office manager briefing",
      run: async (ctx) => {
        const officeApi =
          typeof HalOfficeManager !== "undefined"
            ? HalOfficeManager
            : typeof window !== "undefined" && window.HalOfficeManager
              ? window.HalOfficeManager
              : null;
        if (!officeApi) return { ok: false, summary: "Office manager briefing unavailable." };
        let briefing =
          (ctx.runProactiveCycle && (await ctx.runProactiveCycle())) ||
          (window.HalProactive && HalProactive.getLastBriefing()) ||
          null;
        const snap = (await ctx.loadProgramSnapshot()) || {};
        const state =
          (briefing && briefing.officeManager) ||
          officeApi.buildOfficeManagerState(snap, ctx, briefing || { officePriorities: officeApi.buildOfficePriorities(snap, ctx) });
        return {
          ok: true,
          summary: officeApi.formatDailyOfficeBriefing(state, snap).slice(0, 4000),
          officeManager: state,
        };
      },
    },
  };

  let workingMemory = createWorkingMemory();
  let longTermMemory = createLongTermMemory();
  let repairLog = [];
  let approvedMemories = [];
  let memoriesLoaded = false;
  let lastWebResearch = null;
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
    if (route.useOss) return "oss_review";
    if (/widget|import|briefing|reconciliation/i.test(query)) return "widget_analysis";
    if (/task|office|attention/i.test(query)) return "office_ops";
    if (/claim|denied|packet/i.test(query)) return "claims";
    if (/journal|accounting/i.test(query)) return "accounting";
    return "local_command";
  }

  const WEB_RESEARCH_PRACTICE_RE =
    /\b(accounting|softdent|quickbooks|reconcil|production|collections|daysheet|ebitda|p&l|profit|ledger|month.?end|close|a\/r|receivable|claim|insurance|payer|denial|narrative|eob|era|credential|prior auth|compliance|hipaa|osha|cdt|coding|fee schedule|hygien|staff|schedul|front desk|carestream|sensei|dentrix|eaglesoft|treatment plan|case acceptance|vendor|documentation|best practice|regulation|billing|reimbursement|write.?off|adjustment)\b/i;

  const WEB_RESEARCH_EXPLICIT_RE =
    /\b(search the web|look up online|web research|research online|find (?:out|info) (?:about|on)|what does .+ say about|latest (?:on|about)|public documentation|vendor docs?)\b/i;

  function webResearchEnabled(ctx, query, route) {
    const cfg = ctx && ctx.halModels && ctx.halModels.config && ctx.halModels.config.webResearch;
    if (!cfg || cfg.enabled !== true) return false;
    const r = route || {};
    if (r.intent === "blocked: firewall" || r.text) return false;
    if (r.useWebResearch === true) return true;
    if (WEB_RESEARCH_EXPLICIT_RE.test(query)) return true;

    const mode = String(cfg.mode || "broad").toLowerCase();
    if (mode === "accounting") {
      return /\b(accounting|softdent|quickbooks|reconcil|production|collections|daysheet|ebitda|p&l|profit|ledger|month.?end|close|a\/r|receivable|cash basis|accrual)\b/i.test(
        query,
      );
    }

    // broad: no automatic web fetch on casual chat — too slow.
    if (r.useReasoning || r.useEscalation || r.useOss) {
      return WEB_RESEARCH_PRACTICE_RE.test(query) && String(query).trim().length >= 16;
    }
    return false;
  }

  function buildPlan(query, route, working, longTerm, ctx) {
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

    if (route.useProgramSnapshot || route.useReasoning || route.useEscalation || route.useOss) {
      tools.push("read_program_snapshot");
    }
    if (route.useWidgetFeed || route.useWidgetGuidance || route.useWidgetShow || route.useWidgetFillSuggestions) {
      tools.push("read_widget_feed");
    }
    if (route.useWidgetContract || /\b(widget contract|what does .*widget need|which dataset|which field|data source for .*widget)\b/i.test(query)) {
      tools.push("read_widget_contract");
    }
    if (route.useWidgetMasterChart || /\b(widget master chart|master widget chart|widget map|widget guide|all widgets chart)\b/i.test(query)) {
      tools.push("read_widget_master_chart");
    }
    if (route.useClaimReadiness || (/\b(claim|denied|packet)\b/i.test(query) && !route.text)) {
      tools.push("read_claims_summary");
    }
    if (
      (route.useOfficeAttention || route.useTaskList || route.useTaskCreate) &&
      /\b(task|office manager|attention)\b/i.test(query) &&
      !route.text
    ) {
      tools.push("read_tasks");
    }
    if (route.useDocRag || (/\b(library|search|compliance|policy)\b/i.test(query) && !route.text)) {
      tools.push("search_document_library");
    }
    if (
      !route.useSourceHealth &&
      !route.useImportStatus &&
      !route.useImportRefresh &&
      /\b(source|freshness|import|softdent|quickbooks)\b/i.test(query) &&
      !route.text
    ) {
      tools.push("read_source_health");
    }
    if (working.activeWorkSession || route.useSessionShow || route.useSessionHandoff || route.usePacketBuild || route.usePacketShow) {
      tools.push("read_work_session");
    }
    if (route.useReadinessRun || route.useReadinessGate || /\breadiness\b/i.test(query)) {
      tools.push("run_readiness_check");
    }
    if (route.useProactiveBriefing || route.useReasoning) {
      tools.push("read_proactive_briefing");
    }
    if (
      route.useOfficeBriefing ||
      /\b(daily office briefing|office manager briefing|office briefing|what should staff do today)\b/i.test(query)
    ) {
      tools.push("read_office_briefing");
    }
    if (intent === "firewall" || /\bfirewall\b/i.test(query)) tools.push("explain_firewall");
    if (ctx && webResearchEnabled(ctx, query, route)) tools.push("research_web");

    const toolBudget = tools.includes("research_web") ? 4 : AGENT_BUDGET.maxTools;
    const uniqueTools = [...new Set(tools)].slice(0, toolBudget);

    return {
      questionType: classifyQuestion(query, route),
      needsData: uniqueTools.length > 0,
      tools: uniqueTools,
      isUnsafe: false,
      useModelEnhancement: !!(route.useModel || route.useReasoning || route.useEscalation || route.useOss),
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

    const webCfg = ctx.halModels && ctx.halModels.config && ctx.halModels.config.webResearch;
    if (webCfg && webCfg.enabled === true) {
      parts.push(
        "",
        "Local tools you may rely on when results are provided:",
        "- research_web: sanitized public web reference (practice ops, vendors, insurance, compliance)",
        "- read_program_snapshot, read_widget_feed, read_source_health, and other local-only tools",
      );
    }

    if (window.HalSkills && approvedMemories.length) {
      const guidance = HalSkills.memoryGuidanceText(approvedMemories);
      if (guidance) parts.push("", guidance);
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

  function buildFastChatAgentPrompt(ctx, plan, toolResults, working, longTerm) {
    const toolText = summarizeToolResults(toolResults);
    const parts = [HalCore.buildFastChatSystemPrompt(ctx.halData, null)];
    if (toolText) {
      parts.push("", "Tool results:", toolText.slice(0, 1200));
    }
    const turnText = summarizeWorkingMemory(working);
    if (turnText) {
      parts.push("", "Recent turns:", turnText.slice(0, 400));
    }
    parts.push("", "Answer the user directly in 1–2 short paragraphs. No bullet lists unless asked.");
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

  async function loadApprovedMemories(ctx) {
    const bridge =
      typeof DesktopBridge !== "undefined"
        ? DesktopBridge
        : typeof window !== "undefined" && window.DesktopBridge
          ? window.DesktopBridge
          : null;
    if (!bridge || typeof bridge.listHalMemories !== "function") return;
    try {
      const payload = await bridge.listHalMemories();
      approvedMemories = (payload && payload.items) || [];
      memoriesLoaded = true;
    } catch {
      /* memory load is best-effort */
    }
  }

  async function loadMemory(ctx) {
    // Load exactly once per session; subsequent queries reuse in-memory state.
    memoryLoaded = true;
    if (!ctx || typeof ctx.persistGet !== "function") {
      await loadApprovedMemories(ctx);
      return;
    }
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
    await loadApprovedMemories(ctx);
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

  function isFastChatRoute(route) {
    return !!(route.useModel && !route.useReasoning && !route.useEscalation && !route.useOss);
  }

  function fastChatSkipsProgramContext(route) {
    // Speed-first chat: tool summaries and route handlers cover office data.
    return isFastChatRoute(route);
  }

  async function enhanceModelCall(ctx, route, query, plan, toolResults, onToken) {
    const isFastChat = isFastChatRoute(route);
    const agentPrompt = isFastChat
      ? buildFastChatAgentPrompt(ctx, plan, toolResults, workingMemory, longTermMemory)
      : buildAgentSystemPrompt(ctx, plan, toolResults, workingMemory, longTermMemory);

    const snapshotToolRan = (plan.tools || []).some(
      (t) => t === "read_program_snapshot" || t === "read_widget_feed" || t === "read_claims_summary",
    );
    const ctxCap = isFastChat ? 900 : route.useModel ? 3000 : AGENT_BUDGET.maxModelContextChars;
    let combinedPrompt = agentPrompt;
    if (!fastChatSkipsProgramContext(route) && !snapshotToolRan) {
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
    if (route.useOss) {
      if (!ctx.ossModelReady()) return { text: ctx.offlineModelMessage("oss120b"), lane: "oss120b · offline" };
      const om = ctx.ossModelConfig();
      const text = await ctx.runModel(om, combinedPrompt, query, "Local OSS draft", onToken);
      return { text, lane: "oss120b" };
    }
    if (route.useReasoning) {
      if (!ctx.reasoningModelReady()) return { text: ctx.offlineModelMessage("reason21b"), lane: "reason21b · offline" };
      const rm = ctx.reasoningModelConfig();
      const text = await ctx.runModel(rm, combinedPrompt, query, "Local reasoning plan", onToken);
      return { text, lane: "reason21b" };
    }
    if (route.useModel) {
      if (!ctx.localModelReady()) return { text: ctx.offlineModelMessage("chat8b"), lane: "chat8b · offline" };
      const lm = Object.assign({ fastChat: true }, ctx.localModelConfig());
      const text = await ctx.runModel(lm, combinedPrompt, query, "Local chat draft", onToken);
      return { text, lane: "chat8b" };
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
    const plan = buildPlan(trimmed, route, workingMemory, longTermMemory, ctx);
    const isModelLane = !!(route.useModel || route.useReasoning || route.useEscalation || route.useOss);

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
      } catch (error) {
        if (typeof RuntimeIssues !== "undefined") {
          RuntimeIssues.record("hal-agent.model", error, { lane: route.lane, intent: route.intent });
        }
        outcome = null;
      }
    }

    if (!outcome) {
      try {
        outcome = await ctx.executeRoute(route, trimmed, toolResults);
      } catch (error) {
        if (typeof RuntimeIssues !== "undefined") {
          RuntimeIssues.record("hal-agent.route", error, { lane: route.lane, intent: route.intent });
        }
        outcome = null;
      }
    }

    if (!outcome) {
      const lane = route.lane || "local";
      const offline =
        typeof ctx.offlineModelMessage === "function" && plan.useModelEnhancement
          ? ctx.offlineModelMessage(lane)
          : null;
      outcome = {
        text:
          offline ||
          "I could not complete that request. Check that Ollama is running at 127.0.0.1:11434, then try again.",
        lane: plan.useModelEnhancement ? lane + " · offline" : lane,
        actions: [],
        intent: route.intent || "error",
      };
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

  function getLastWebResearch() {
    return lastWebResearch ? Object.assign({}, lastWebResearch) : null;
  }

  function getApprovedMemories() {
    return approvedMemories.slice();
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
    isFastChatRoute,
    fastChatSkipsProgramContext,
    processQuery,
    loadMemory,
    saveMemory,
    getWorkingMemory,
    getLongTermMemory,
    getRepairLog,
    getHealth,
    getLastWebResearch,
    getApprovedMemories,
    updatePreferences,
    logRepair,
  };
})();

if (typeof window !== "undefined") window.HalAgent = HalAgent;
if (typeof module !== "undefined" && module.exports) module.exports = HalAgent;
