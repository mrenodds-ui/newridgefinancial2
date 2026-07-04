/**
 * HAL Agent Core — planner, local tools, working/long-term memory, self-check, repair loop.
 * Sits between routing and response generation. Browser + Node compatible.
 */
const HalAgent = (function () {
  const MEMORY_KEY = "halAgentMemory";
  const REPAIR_KEY = "halRepairLog";
  const WORKING_KEY = "halWorkingMemory";
  const ARCHITECTURE_VERSION = "hal-agent-v12-cursor";
  const REPAIR_MAX = 100;
  const TURN_MAX = 16;
  const AGENT_BUDGET = {
    maxTools: 10,
    maxGatherRounds: 3,
    maxTaskCompletionRounds: 2,
    maxToolSummaryChars: 5200,
    maxModelContextChars: 14000,
    maxRecentTurns: 12,
  };

  function syncAgentBudgetFromModels(halModels) {
    const ap = (halModels && halModels.config && halModels.config.agentProgramming) || {};
    if (typeof ap.maxToolsPerTurn === "number" && ap.maxToolsPerTurn > 0) {
      AGENT_BUDGET.maxTools = Math.min(20, ap.maxToolsPerTurn);
    }
    if (typeof ap.multiGatherRounds === "number" && ap.multiGatherRounds > 0) {
      AGENT_BUDGET.maxGatherRounds = Math.min(6, ap.multiGatherRounds);
    }
    if (typeof HalAgentLoop !== "undefined" && HalAgentLoop.configureFromAgentProgramming) {
      HalAgentLoop.configureFromAgentProgramming(ap);
    }
  }

  function buildCloudToolSchemas(toolIds) {
    const ids = [...new Set((toolIds || []).filter((id) => TOOL_DEFS[id]))].slice(0, 12);
    return ids.map((id) => ({
      type: "function",
      function: {
        name: id,
        description: (TOOL_DEFS[id] && TOOL_DEFS[id].label) || id,
        parameters: {
          type: "object",
          properties: {
            query: { type: "string", description: "Search terms, file path, or allowlisted command id" },
          },
        },
      },
    }));
  }

  function agentLoopToolIds(plan) {
    return (plan.tools || []).concat([
      "grep_program_source",
      "read_program_file",
      "semantic_search_program",
      "run_hal_validation",
      "run_command",
      "read_program_snapshot",
      "spawn_investigation",
    ]);
  }

  function attachOllamaNativeTools(runtime, plan, agentCfg) {
    if (!runtime || !plan || !plan.agentToolLoop) return runtime;
    if (agentCfg.localOllamaTools === false) return runtime;
    const schemas = buildCloudToolSchemas(agentLoopToolIds(plan));
    if (!schemas.length) return runtime;
    return Object.assign({}, runtime, { structuredAgent: true, ollamaTools: schemas });
  }

  function cloudAgentEligible(plan, ctx) {
    if (typeof ctx.cloudAgentEligible === "function") return ctx.cloudAgentEligible(plan);
    if (typeof ctx.cloudModelReady !== "function" || !ctx.cloudModelReady()) return false;
    const cfg = (ctx.halModels && ctx.halModels.config && ctx.halModels.config.cloudReasoning) || {};
    if (cfg.enabled === true) return !!(plan && plan.agentToolLoop);
    if (cfg.autoEnableWhenKeySet === false) return false;
    if (!plan || !plan.agentToolLoop) return false;
    if (cfg.preferForTaskCompletion === false) return false;
    return !!(plan.isTaskCompletionQuery || plan.isInvestigateQuery || plan.isComplexInvestigationQuery);
  }

  function parsePatchFromQuery(query) {
    const block = String(query || "").match(/<<<patch\s+([\s\S]*?)>>>/i);
    if (!block) return null;
    const body = block[1];
    const fileMatch = body.match(/^\s*file:\s*(.+)$/im);
    const oldMatch = body.match(/^\s*old:\s*\n([\s\S]*?)(?=^\s*new:\s*\n)/im);
    const newMatch = body.match(/^\s*new:\s*\n([\s\S]*)$/im);
    if (!fileMatch || !oldMatch || !newMatch) return null;
    return {
      file: fileMatch[1].trim(),
      old: oldMatch[1].replace(/\r\n/g, "\n"),
      new: newMatch[1].replace(/\r\n/g, "\n"),
    };
  }

  function isTaskCompletionQuery(query) {
    return /\b(fix|patch|change|update|edit|implement|modify|correct|validate|validation|syntax check|run validation|self-heal|strengthen program|repair program|make it pass)\b/i.test(
      String(query || ""),
    );
  }

  function shouldRunPostValidation(query, toolResults) {
    if (!isTaskCompletionQuery(query)) return false;
    if (/\bvalidate|validation|syntax check|make sure.*pass\b/i.test(query)) return true;
    if (toolResults && toolResults.apply_program_patch && toolResults.apply_program_patch.ok) return true;
    return false;
  }

  function bridgeFromCtx(ctx) {
    if (ctx && ctx.desktopBridge) return ctx.desktopBridge;
    if (typeof DesktopBridge !== "undefined") return DesktopBridge;
    if (typeof window !== "undefined" && window.DesktopBridge) return window.DesktopBridge;
    return null;
  }

  const SAFETY_POLICY = {
    summary: "HAL is the internal office manager. Local coordination; external-action firewall disabled.",
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
      "HAL is the internal office manager; outbound executors are not wired — do not claim email, post, or writeback was performed.",
      "Sound like a capable Cursor-style agent: answer first, cite local evidence, name gaps, recommend one safe next step. At least five complete sentences. Accurate on missing data and read-only limits — helpful, never sarcastic.",
      "Never fabricate missing import data; say what is missing.",
      "Never claim an external action was performed.",
      "If data is stale or unavailable, say so before recommending.",
      "Cite which local source or tool informed the answer when possible.",
      "When web research tool results are present, use them for public reference context and say they are not verified against this practice's live data.",
      "When planning or prioritizing, prefer the proactive office manager assessment over generic advice.",
      "Follow HalAgentProgramming contract when present: answer first, synthesize tools, min five sentences, one next step.",
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
    read_registry: {
      label: "Read HAL capability registry",
      run: async (ctx) => {
        if (!HalCore || typeof HalCore.registryAsText !== "function") {
          return { ok: false, summary: "Registry unavailable." };
        }
        return { ok: true, summary: HalCore.registryAsText(ctx.halData).slice(0, 4500) };
      },
    },
    read_current_context: {
      label: "Read current page and session context",
      run: async (ctx) => {
        const pageId = ctx.getCurrentPage ? ctx.getCurrentPage() : "unknown";
        const info =
          HalCore && ctx.pages ? HalCore.pageInfoMap(ctx.halData, ctx.pages)[pageId] : null;
        const hist = ctx.getWorkingTurns ? ctx.getWorkingTurns() : ctx.getChatHistory ? ctx.getChatHistory() : [];
        const recent = (hist || [])
          .slice(-4)
          .map((t) => `${t.role}: ${String(t.text || "").slice(0, 100)}`)
          .join("\n");
        const events = Array.isArray(ctx.halLiveWidgetEvents) ? ctx.halLiveWidgetEvents.length : 0;
        const session = ctx.halWorkSession && ctx.halWorkSession.templateId ? ctx.halWorkSession.templateId : "none";
        const lines = [
          `Current page: ${info ? info.label : pageId}`,
          info && info.detail ? `Page focus: ${info.detail}` : "",
          `Active work session: ${session}`,
          `Live widget events this session: ${events}`,
          recent ? `Recent turns:\n${recent}` : "Recent turns: none",
        ].filter(Boolean);
        return { ok: true, summary: lines.join("\n") };
      },
    },
    search_program: {
      label: "Search program pages and registry",
      run: async (ctx, args) => {
        const raw = String(args.query || "").trim();
        const terms = raw
          .toLowerCase()
          .split(/\s+/)
          .filter((w) => w.length > 2);
        if (!terms.length) return { ok: false, summary: "No search terms." };
        const hits = [];
        (ctx.pages || []).forEach((page) => {
          const hay = `${page.id} ${page.label || ""} ${page.title || ""}`.toLowerCase();
          if (terms.some((t) => hay.includes(t))) hits.push(`Page: ${page.label || page.id} (#${page.id})`);
        });
        (HalCore.registryList(ctx.halData) || []).forEach((entry) => {
          const hay = `${entry.id} ${entry.label || ""} ${entry.state || ""} ${entry.detail || ""} ${entry.nextAction || ""}`.toLowerCase();
          if (terms.some((t) => hay.includes(t))) {
            hits.push(`Registry: ${entry.label || entry.id} — ${entry.state || "unknown"}`);
          }
        });
        const firewall = ctx.halData && ctx.halData.firewall;
        if (firewall && terms.some((t) => "firewall blocked allowed".includes(t))) {
          hits.push(`Firewall: ${firewall.summary || "external actions blocked"}`);
        }
        return {
          ok: true,
          summary: hits.length
            ? hits.slice(0, 24).join("\n")
            : `No program matches for "${raw}". Try page names (claims, A/R, QuickBooks) or registry topics (imports, widgets).`,
          query: raw,
        };
      },
    },
    read_import_diagnostics: {
      label: "Read import diagnostics detail",
      run: async (ctx) => {
        const snap = await ctx.loadProgramSnapshot();
        const diagnostics = snap && snap.importBundle && snap.importBundle.diagnostics;
        const api =
          typeof ImportDiagnostics !== "undefined"
            ? ImportDiagnostics
            : typeof window !== "undefined" && window.ImportDiagnostics
              ? window.ImportDiagnostics
              : null;
        if (!diagnostics || !api || typeof api.formatDatasetLines !== "function") {
          return { ok: false, summary: "Import diagnostics unavailable — try refresh imports first." };
        }
        const lines = api.formatDatasetLines(diagnostics);
        return { ok: true, summary: (lines.length ? lines.join("\n") : "No import datasets evaluated.").slice(0, 4000) };
      },
    },
    lookup_english_word: {
      label: "Look up English dictionary word",
      run: async (ctx, args) => {
        const api =
          typeof HalEnglishVocab !== "undefined"
            ? HalEnglishVocab
            : typeof window !== "undefined" && window.HalEnglishVocab
              ? window.HalEnglishVocab
              : null;
        if (!api || typeof api.lookupWord !== "function") {
          return { ok: false, summary: "English dictionary unavailable." };
        }
        const raw = String(args.query || "").trim().replace(/^define\s+/i, "");
        const word = raw.match(/\b([a-z'-]{3,})\b/i);
        const term = word ? word[1] : raw.split(/\s+/).pop();
        if (!term) return { ok: false, summary: "No word to look up." };
        const entry = await api.lookupWord(term);
        if (!entry) return { ok: false, summary: `No dictionary entry for "${term}".` };
        const text =
          typeof api.formatWordLesson === "function" ? api.formatWordLesson(entry) : JSON.stringify(entry);
        return { ok: true, summary: String(text).slice(0, 2500), word: term };
      },
    },
    read_program_help: {
      label: "Read in-app program help",
      run: async (ctx, args) => {
        const bridge =
          typeof DesktopBridge !== "undefined"
            ? DesktopBridge
            : typeof window !== "undefined" && window.DesktopBridge
              ? window.DesktopBridge
              : null;
        if (!bridge || typeof bridge.getProgramHelp !== "function") {
          return { ok: false, summary: "Program help requires the NR2 desktop app." };
        }
        const payload = await bridge.getProgramHelp(String(args.query || ""));
        const text = payload && payload.text ? String(payload.text) : "No help topic matched.";
        return { ok: true, summary: text.slice(0, 3000), match: payload && payload.match ? payload.match : null };
      },
    },
    grep_program_source: {
      label: "Search NR2 program source (read-only)",
      run: async (ctx, args) => {
        const bridge =
          typeof DesktopBridge !== "undefined"
            ? DesktopBridge
            : typeof window !== "undefined" && window.DesktopBridge
              ? window.DesktopBridge
              : null;
        if (!bridge || typeof bridge.grepProgramSource !== "function") {
          return { ok: false, summary: "Program source search requires the NR2 desktop app." };
        }
        const raw = String(args.query || "").trim();
        const term =
          raw.match(/\b(handleHalSubmit|HalAgent|routeHalCommand|buildPlan|grep|function\s+(\w+))\b/i)?.[0] ||
          raw.replace(/^(how does|how do|where is|find|grep|search)\s+/i, "").trim() ||
          raw;
        const payload = await bridge.grepProgramSource(term, 20);
        const text = payload && payload.text ? String(payload.text) : "No source matches.";
        return { ok: !!(payload && payload.count), summary: text.slice(0, 4500), hits: payload && payload.hits ? payload.hits : [] };
      },
    },
    search_hal_memories: {
      label: "Search durable HAL memories",
      run: async (ctx, args) => {
        const bridge =
          typeof DesktopBridge !== "undefined"
            ? DesktopBridge
            : typeof window !== "undefined" && window.DesktopBridge
              ? window.DesktopBridge
              : null;
        if (!bridge || typeof bridge.searchHalMemories !== "function") {
          return { ok: false, summary: "Memory search requires the NR2 desktop app." };
        }
        const payload = await bridge.searchHalMemories(String(args.query || ""), 6);
        const text = payload && payload.text ? String(payload.text) : "No matching memories.";
        return {
          ok: !!(payload && payload.count),
          summary: text.slice(0, 2500) || "No matching memories.",
          count: payload && payload.count ? payload.count : 0,
        };
      },
    },
    read_program_file: {
      label: "Read NR2 program source file",
      run: async (ctx, args) => {
        const bridge =
          typeof DesktopBridge !== "undefined"
            ? DesktopBridge
            : typeof window !== "undefined" && window.DesktopBridge
              ? window.DesktopBridge
              : null;
        if (!bridge || typeof bridge.readProgramFile !== "function") {
          return { ok: false, summary: "Program file read requires the NR2 desktop app." };
        }
        const raw = String(args.query || "");
        const pathMatch =
          raw.match(/(?:NewRidgeFinancial2\/)?(site\/[\w./-]+\.\w+)/i) ||
          raw.match(/\b(hal-[\w.-]+\.(?:js|json|py|html|css|mjs))\b/i) ||
          raw.match(/\b([\w.-]+\.(?:js|json|py))\b/i);
        const rel = pathMatch ? pathMatch[1] : raw.replace(/^read\s+/i, "").trim();
        if (!rel) return { ok: false, summary: "No file path to read." };
        const payload = await bridge.readProgramFile(rel, 10000);
        const text = payload && payload.text ? String(payload.text) : "File unavailable.";
        return {
          ok: !!(payload && payload.ok !== false),
          summary: (payload && payload.file ? payload.file + ":\n" : "") + text.slice(0, 4500),
          file: payload && payload.file ? payload.file : rel,
        };
      },
    },
    list_program_files: {
      label: "List NR2 program source files",
      run: async (ctx, args) => {
        const bridge = bridgeFromCtx(ctx);
        if (!bridge || typeof bridge.listProgramFiles !== "function") {
          return { ok: false, summary: "Program file list requires the NR2 desktop app." };
        }
        const payload = await bridge.listProgramFiles("site", 60);
        return {
          ok: !!(payload && payload.count),
          summary: (payload && payload.text ? payload.text : "No files.").slice(0, 3500),
          files: payload && payload.files ? payload.files : [],
        };
      },
    },
    apply_program_patch: {
      label: "Apply safe program source patch",
      run: async (ctx, args) => {
        const bridge = bridgeFromCtx(ctx);
        const spec = (ctx && ctx.pendingPatch) || parsePatchFromQuery(String(args.query || ""));
        if (!spec || !spec.file || !spec.old) {
          return {
            ok: false,
            summary:
              "No patch spec. Use <<<patch\\nfile: site/example.js\\nold:\\n...\\nnew:\\n...\\n>>> in your message, or ask HAL to validate only.",
          };
        }
        if (!bridge || typeof bridge.applyProgramPatch !== "function") {
          return { ok: false, summary: "Program patch requires the NR2 desktop app." };
        }
        const payload = await bridge.applyProgramPatch(spec.file, spec.old, spec.new, false);
        const text = payload && payload.text ? String(payload.text) : "Patch failed.";
        return { ok: !!(payload && payload.ok), summary: text.slice(0, 2000), file: payload && payload.file ? payload.file : spec.file };
      },
    },
    run_hal_validation: {
      label: "Run validate-hal.mjs",
      run: async (ctx, args) => {
        const bridge = bridgeFromCtx(ctx);
        if (bridge && typeof bridge.runHalValidation === "function") {
          const payload = await bridge.runHalValidation(120);
          const text = payload && payload.text ? String(payload.text) : "Validation unavailable.";
          return {
            ok: !!(payload && payload.ok),
            summary: text.slice(0, 5000),
            exitCode: payload && payload.exitCode != null ? payload.exitCode : -1,
          };
        }
        if (typeof process !== "undefined" && process.versions && process.versions.node) {
          try {
            const { execSync } = require("node:child_process");
            const { join } = require("node:path");
            let nr2 = ctx && ctx.nr2Root ? ctx.nr2Root : null;
            if (!nr2) {
              const cwd = process.cwd();
              nr2 = /NewRidgeFinancial2/i.test(cwd) ? cwd : join(cwd, "NewRidgeFinancial2");
            }
            const out = execSync("node validate-hal.mjs", {
              cwd: nr2,
              encoding: "utf8",
              env: Object.assign({}, process.env, { NR2_LOAD_IMPORTS: "1" }),
              stdio: ["ignore", "pipe", "pipe"],
              timeout: 120000,
            });
            return { ok: true, summary: String(out).slice(-5000), exitCode: 0 };
          } catch (err) {
            const msg = (err.stdout || "") + (err.stderr || "") + (err.message || "");
            return { ok: false, summary: msg.slice(-5000), exitCode: err.status || 1 };
          }
        }
        return { ok: false, summary: "HAL validation requires the NR2 desktop app or Node runtime." };
      },
    },
    run_node_syntax_check: {
      label: "Run node --check on program files",
      run: async (ctx, args) => {
        const bridge = bridgeFromCtx(ctx);
        const raw = String(args.query || "");
        const paths = [];
        const re = /(?:NewRidgeFinancial2\/)?(site\/[\w./-]+\.(?:js|mjs))/gi;
        let m;
        while ((m = re.exec(raw)) !== null) paths.push(m[1]);
        if (!paths.length) {
          paths.push("site/hal-core.js", "site/hal-agent.js", "site/app.js");
        }
        if (!bridge || typeof bridge.runNodeSyntaxCheck !== "function") {
          return { ok: false, summary: "Syntax check requires the NR2 desktop app." };
        }
        const payload = await bridge.runNodeSyntaxCheck(paths);
        const text = payload && payload.text ? String(payload.text) : "Syntax check failed.";
        return { ok: !!(payload && payload.ok), summary: text.slice(0, 3000), results: payload && payload.results ? payload.results : [] };
      },
    },
    semantic_search_program: {
      label: "Semantic search program source",
      run: async (ctx, args) => {
        const bridge = bridgeFromCtx(ctx);
        const q = String(args.query || "");
        if (bridge && typeof bridge.semanticSearchProgram === "function") {
          const payload = await bridge.semanticSearchProgram(q, 15);
          const text = payload && payload.text ? String(payload.text) : "No semantic matches.";
          return { ok: !!(payload && payload.count), summary: text.slice(0, 4500), hits: payload && payload.hits ? payload.hits : [] };
        }
        const grepDef = TOOL_DEFS.grep_program_source;
        if (grepDef) {
          const fallback = await grepDef.run(ctx, { query: q });
          const summary = fallback && fallback.summary ? String(fallback.summary) : "No matches.";
          return {
            ok: !!(fallback && fallback.ok),
            summary: ("Source search (browser fallback):\n" + summary).slice(0, 4500),
            hits: fallback && fallback.matches ? fallback.matches : [],
          };
        }
        return { ok: false, summary: "Semantic search requires the NR2 desktop app or grep fallback." };
      },
    },
    run_git_readonly: {
      label: "Git status/diff (read-only)",
      run: async (ctx, args) => {
        const bridge = bridgeFromCtx(ctx);
        const raw = String(args.query || "").toLowerCase();
        let cmd = "status";
        if (/diff-stat|diff stat/.test(raw)) cmd = "diff-stat";
        else if (/diff-names|diff names|changed files/.test(raw)) cmd = "diff-names";
        else if (/log|history/.test(raw)) cmd = "log";
        if (!bridge || typeof bridge.runGitReadonly !== "function") {
          return { ok: false, summary: "Git read requires the NR2 desktop app." };
        }
        const payload = await bridge.runGitReadonly(cmd);
        const text = payload && payload.text ? String(payload.text) : "Git unavailable.";
        return { ok: !!(payload && payload.ok), summary: text.slice(0, 4000), command: cmd };
      },
    },
    run_command: {
      label: "Run allowlisted repo command",
      run: async (ctx, args) => {
        const bridge = bridgeFromCtx(ctx);
        const raw = String(args.query || "").trim().toLowerCase();
        let cmdId = "validate-hal";
        if (/node-check-agent|check agent|hal-agent/.test(raw)) cmdId = "node-check-agent";
        else if (/node-check-app|check app/.test(raw)) cmdId = "node-check-app";
        else if (/node-check-core|check core/.test(raw)) cmdId = "node-check-core";
        else if (/node-check-loop|agent-loop/.test(raw)) cmdId = "node-check-loop";
        else if (/node-check-all|check all|syntax all/.test(raw)) cmdId = "node-check-all";
        else if (/git-diff-stat|diff stat/.test(raw)) cmdId = "git-diff-stat";
        else if (/git-diff-names|diff names|changed files/.test(raw)) cmdId = "git-diff-names";
        else if (/git-log|git log/.test(raw)) cmdId = "git-log";
        else if (/git-status|git status/.test(raw)) cmdId = "git-status";
        else if (/validate|validation/.test(raw)) cmdId = "validate-hal";
        else if (/^[a-z0-9-]+$/.test(raw)) cmdId = raw;
        if (!bridge || typeof bridge.runAllowlistedCommand !== "function") {
          return { ok: false, summary: "Allowlisted commands require the NR2 desktop app." };
        }
        const payload = await bridge.runAllowlistedCommand(cmdId);
        const text = payload && payload.text ? String(payload.text) : "Command unavailable.";
        return {
          ok: !!(payload && payload.ok),
          summary: text.slice(0, 5000),
          command: cmdId,
          exitCode: payload && payload.exitCode != null ? payload.exitCode : -1,
        };
      },
    },
    explain_route: {
      label: "Explain HAL routing for this question",
      run: async (ctx, args) => {
        const q = String(args.query || "").trim();
        if (!HalCore || typeof HalCore.routeHalCommand !== "function") {
          return { ok: false, summary: "Routing unavailable." };
        }
        const r = HalCore.routeHalCommand(ctx.halData, ctx.halModels, ctx.pages, q);
        const miniPlan = buildPlan(q, r, workingMemory, longTermMemory, ctx);
        const flags = [
          r.useModel ? "useModel" : null,
          r.useReasoning ? "useReasoning" : null,
          r.useEscalation ? "useEscalation" : null,
          r.useImportRefresh ? "useImportRefresh" : null,
        ]
          .filter(Boolean)
          .join(", ");
        return {
          ok: true,
          summary: [
            `Question: ${q}`,
            `Intent: ${r.intent || "unknown"}`,
            `Lane: ${r.lane || "local"}`,
            `Flags: ${flags || "none"}`,
            `Tools planned: ${miniPlan.tools.join(", ") || "none"}`,
            r.text ? `Template text: ${String(r.text).slice(0, 200)}` : "No pre-baked template — model or executor will answer.",
          ].join("\n"),
        };
      },
    },
    search_chat_history: {
      label: "Search recent HAL chat turns",
      run: async (ctx, args) => {
        const raw = String(args.query || "").toLowerCase();
        const terms = raw.split(/\s+/).filter((w) => w.length > 2);
        const hist = ctx.getChatHistory ? ctx.getChatHistory() : ctx.getWorkingTurns ? ctx.getWorkingTurns() : [];
        const hits = (hist || []).filter((m) => {
          const hay = `${m.role || ""} ${m.text || ""}`.toLowerCase();
          return terms.length ? terms.some((t) => hay.includes(t)) : hay.length > 0;
        });
        const recent = hits.slice(-8);
        if (!recent.length) {
          return { ok: true, summary: "No matching turns in recent chat history." };
        }
        const lines = recent.map((m) => `${m.role === "user" ? "You" : "HAL"}: ${String(m.text || "").slice(0, 160)}`);
        return { ok: true, summary: lines.join("\n") };
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
      preferBrief: false,
      firewallBriefCount: 0,
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

  function isInvestigateQuery(query, route) {
    return (
      /\b(what'?s wrong|why is|why are|investigate|debug|diagnose|root cause|figure out|what happened|broken|not working|empty widget)\b/i.test(
        query,
      ) ||
      /\b(how does|where is .+ handled|grep|source code)\b/i.test(query) ||
      !!(route && route.useReasoning && /\b(import|widget|source|missing|failed)\b/i.test(query))
    );
  }

  function isComplexInvestigationQuery(query, route) {
    const q = String(query || "");
    if (!isInvestigateQuery(q, route)) return false;
    return (
      q.length > 140 ||
      (q.match(/\?/g) || []).length > 1 ||
      /\b(and also|additionally|step by step|trace through|deep dive|multiple|both .+ and| and how| and why| as well as)\b/i.test(q)
    );
  }

  function extractSubInvestigationFocus(query) {
    const q = String(query || "").trim();
    const parts = q.split(/\?\s+/).filter(Boolean);
    if (parts.length > 1) return parts[0].trim() + "?";
    const codeFocus = q.match(/\b(how does|where is|why is|what handles)\s+[^?.!]+/i);
    if (codeFocus) return codeFocus[0].trim();
    return q.slice(0, 180);
  }

  function extractToolEvidenceLines(toolResults, maxLines) {
    const lines = [];
    for (const [id, res] of Object.entries(toolResults || {})) {
      if (!res || !res.summary) continue;
      const summary = String(res.summary).trim();
      const chunks = summary
        .split(/\n+/)
        .map((s) => s.trim())
        .filter(Boolean);
      for (const chunk of chunks) {
        if (/^(no data|error|unknown tool|#+\s)/i.test(chunk)) continue;
        if (chunk.length < 16) continue;
        lines.push(chunk.replace(/\s+/g, " ").slice(0, 420));
        break;
      }
      if (lines.length >= maxLines) break;
    }
    return lines;
  }

  function synthesizeAnswerFromTools(query, plan, toolResults, route, ctx) {
    const ap = (ctx && ctx.halModels && ctx.halModels.config && ctx.halModels.config.agentProgramming) || {};
    if (ap.synthesizeTools === false) return null;
    const lines = extractToolEvidenceLines(toolResults, 5);
    if (!lines.length) return null;

    const q = String(query || "");
    let lead;
    if (/\breadiness\b/i.test(q)) lead = "Readiness checks from local tools show:";
    else if (/\bimport|fresh|stale|missing|softdent|quickbooks\b/i.test(q)) lead = "Import and source status from local checks:";
    else if (isInvestigateQuery(q, route)) lead = "Local diagnostics for this question:";
    else if (/\bprioriti|attention|blocked\b/i.test(q)) lead = "From local office data:";
    else lead = "From local program evidence:";

    let next = "Next step: refresh imports or name a specific page if you want a narrower check.";
    if (/\breadiness\b/i.test(q)) next = "Next step: run readiness from HAL or open the page named in the findings.";
    else if (route && route.intent === "imports: refresh") next = "Next step: verify export paths, then refresh imports if files are missing.";
    else if (/\bdenied|claim\b/i.test(q)) next = "Next step: open Claims Workbench and work the Needs Review lane first.";

    const evidenceTag = "This is based on the local program data gathered for this question.";
    const body = lines.join(" ");
    return `${lead} ${body} ${next} ${evidenceTag}`.replace(/\s{2,}/g, " ").trim();
  }

  function isGenericOfflineText(text) {
    return /\b(local chat is offline|can't reach local chat|model lane is down|chat model is offline)\b/i.test(
      String(text || ""),
    );
  }

  function buildToolSynthesisOutcome(query, plan, toolResults, route, ctx) {
    const text = synthesizeAnswerFromTools(query, plan, toolResults, route, ctx);
    if (!text) return null;
    return {
      text,
      lane: "local",
      actions: [],
      intent: (route && route.intent) || "tools:synthesis",
    };
  }

  function expandGatherToolsForRound(query, route, toolResults, round, existingIds) {
    const had = new Set(existingIds || []);
    const add = [];
    const blob = Object.values(toolResults || {})
      .map((r) => (r && r.summary ? String(r.summary) : ""))
      .join(" ");
    if (round >= 1) {
      if (!had.has("read_import_diagnostics") && /\b(import|missing|empty|stale|dataset|export)\b/i.test(query + blob)) {
        add.push("read_import_diagnostics");
      }
      if (!had.has("read_widget_feed") && /\b(widget|dashboard|feed|empty|tile)\b/i.test(query + blob)) {
        add.push("read_widget_feed");
      }
      if (!had.has("grep_program_source") && /\b(how|why|bug|code|function|broken|error)\b/i.test(query)) {
        add.push("grep_program_source");
      }
    }
    if (round >= 2) {
      if (!had.has("read_program_help")) add.push("read_program_help");
      if (!had.has("search_program")) add.push("search_program");
      if (!had.has("read_source_health")) add.push("read_source_health");
    }
    if (round >= 1 && /\bvalidate|validation|syntax\b/i.test(query)) {
      if (!had.has("run_hal_validation")) add.push("run_hal_validation");
      if (!had.has("run_node_syntax_check") && /\bsyntax\b/i.test(query)) add.push("run_node_syntax_check");
    }
    return add.filter((id) => !had.has(id)).slice(0, Math.max(0, AGENT_BUDGET.maxTools - had.size));
  }

  function needsMoreGather(checked, toolResults, plan, round) {
    if (!plan || !plan.useModelEnhancement) return false;
    if (round >= AGENT_BUDGET.maxGatherRounds - 1) return false;
    if (checked && checked.pass) return false;
    const issues = (checked && checked.issues) || [];
    if (issues.includes("missing_evidence_when_tools") || issues.includes("empty_response")) return true;
    const blob = Object.values(toolResults || {})
      .map((r) => (r && r.summary ? String(r.summary) : ""))
      .join(" ");
    if (/FAILED|missing|empty|no data|error|unavailable/i.test(blob)) return true;
    return false;
  }

  function cursorGatherTools(query, route) {
    if (!(route.useModel || route.useReasoning || route.useEscalation || route.useOss)) return [];
    const gather = ["read_current_context"];
    if (!route.text) {
      gather.push("read_program_snapshot", "read_source_health");
    }
    if (/\b(registry|capabilit|what can you|what can't|blocked|allowed)\b/i.test(query)) {
      gather.push("read_registry");
    }
    if (/\bwidget|dashboard|feed|manager|tile|monitor\b/i.test(query)) {
      gather.push("read_widget_feed");
    }
    if (/\b(import|diagnostic|export|fresh|stale|inbox|dataset)\b/i.test(query)) {
      gather.push("read_import_diagnostics");
    }
    if (/\bdefine\b|english word|vocabulary|dictionary|random english\b/i.test(query)) {
      gather.push("lookup_english_word");
    }
    if (/\b(search|find|where is|look for|grep)\b/i.test(query)) {
      gather.push("search_program");
      gather.push("semantic_search_program");
    }
    if (/\b(how does|how do|source code|in the code|function|programming|hal-agent|handleHalSubmit|routeHalCommand)\b/i.test(query)) {
      gather.push("grep_program_source");
    }
    if (/\b(deep dive|trace through|step by step|sub-investigation|spawn)\b/i.test(query)) {
      gather.push("spawn_investigation");
    }
    if (/\b(read file|open file|show file|\.js\b|\.py\b|hal-agent\.js|app\.js)\b/i.test(query)) {
      gather.push("read_program_file");
    }
    if (/\b(list files|what files|source tree|program files)\b/i.test(query)) {
      gather.push("list_program_files");
    }
    if (/\b(route|routing|which lane|what intent|how do you route)\b/i.test(query)) {
      gather.push("explain_route");
    }
    if (/\b(earlier|before|you said|last time|chat history|we discussed)\b/i.test(query)) {
      gather.push("search_chat_history");
    }
    if (/\b(how do i|help with|troubleshoot|why is my|operator help)\b/i.test(query)) {
      gather.push("read_program_help");
    }
    if (/\b(remember|recall|you said|last time|memory)\b/i.test(query)) {
      gather.push("search_hal_memories");
    }
    if (/\blearn this|save this|note that\b/i.test(query)) {
      gather.push("remember_fact");
    }
    if (isTaskCompletionQuery(query)) {
      if (!gather.includes("grep_program_source")) gather.push("grep_program_source");
      if (/\bvalidate|validation\b/i.test(query)) gather.push("run_hal_validation");
      if (/\bsyntax\b/i.test(query)) gather.push("run_node_syntax_check");
      if (/<<<patch/i.test(query)) gather.push("apply_program_patch");
      if (/\bgit\b/i.test(query)) gather.push("run_git_readonly");
      if (/\bcommand|shell|run validate\b/i.test(query)) gather.push("run_command");
    }
    return gather;
  }

  function buildPlan(query, route, working, longTerm, ctx) {
    if (ctx && ctx.halModels) syncAgentBudgetFromModels(ctx.halModels);
    const agentCfg = (ctx && ctx.halModels && ctx.halModels.config && ctx.halModels.config.agentProgramming) || {};
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

    if (agentCfg.cursorGather !== false) {
      cursorGatherTools(query, route).forEach((id) => tools.push(id));
    }

    if (parsePatchFromQuery(query)) tools.push("apply_program_patch");
    if (isTaskCompletionQuery(query)) {
      if (/\bvalidate|validation|make.*pass\b/i.test(query)) tools.push("run_hal_validation");
      if (/\bsyntax\b/i.test(query)) tools.push("run_node_syntax_check");
    }

    const uniqueTools = [...new Set(tools)].slice(0, AGENT_BUDGET.maxTools);
    const planOnly = typeof HalAgentLoop !== "undefined" && HalAgentLoop.isPlanOnlyQuery(query);

    return {
      questionType: classifyQuestion(query, route),
      originalQuery: query,
      needsData: uniqueTools.length > 0,
      tools: uniqueTools,
      isUnsafe: false,
      useModelEnhancement: !!(route.useModel || route.useReasoning || route.useEscalation || route.useOss),
      needsClarification: !route.text && !hasUseFlag(route),
      agentToolLoop: !planOnly && !!(route.useModel || route.useReasoning || route.useEscalation),
      planOnly,
      isTaskCompletionQuery: isTaskCompletionQuery(query),
      isInvestigateQuery: isInvestigateQuery(query, route),
      isComplexInvestigationQuery: isComplexInvestigationQuery(query, route),
      lane: route.lane,
      intent,
      budget: AGENT_BUDGET,
      preferences: longTerm.preferences,
    };
  }

  async function runTools(toolIds, ctx, query) {
    const notify = ctx && typeof ctx.onToolProgress === "function" ? ctx.onToolProgress : null;
    const jobs = toolIds.map(async (id) => {
      const def = TOOL_DEFS[id];
      if (!def) return [id, null];
      if (notify) notify({ phase: "start", tool: id, label: def.label || id });
      try {
        const res = await def.run(ctx, { query });
        if (notify) {
          notify({
            phase: "done",
            tool: id,
            label: def.label || id,
            ok: !(res && res.ok === false),
          });
        }
        return [id, res];
      } catch (error) {
        if (notify) notify({ phase: "done", tool: id, label: def.label || id, ok: false });
        return [id, { ok: false, summary: error && error.message ? error.message : String(error) }];
      }
    });
    const pairs = await Promise.all(jobs);
    const results = {};
    pairs.forEach(([id, res]) => {
      if (res) results[id] = res;
    });
    return results;
  }

  function escalateRouteForRetry(route, query) {
    const r = Object.assign({}, route || {});
    r.useReasoning = true;
    r.useModel = false;
    r.useEscalation = false;
    r.useOss = false;
    r.lane = "reason21b";
    r.text = "";
    r.prompt = query;
    if (!/^reasoning:/.test(String(r.intent || ""))) {
      r.intent = "reasoning: auto-escalate";
    }
    return r;
  }

  function shouldAutoEscalate(checked, route, agentCfg) {
    if (agentCfg && agentCfg.autoEscalate === false) return false;
    if (!checked || checked.pass) return false;
    if (!route || route.useReasoning || route.useEscalation || route.useOss) return false;
    if (!route.useModel) return false;
    return checked.issues.some((issue) => MODEL_SHAPE_ISSUES.has(issue) || issue === "too_short" || issue === "empty_response");
  }

  function summarizeToolEvidenceOnly(toolResults) {
    const parts = [];
    for (const [id, res] of Object.entries(toolResults || {})) {
      if (!res || !res.summary) continue;
      const label = (TOOL_DEFS[id] && TOOL_DEFS[id].label) || id.replace(/_L\d+$/, "");
      const body = String(res.summary)
        .replace(/^#+\s+/gm, "")
        .replace(/\bSynthesize tool results[^.]*\.?/gi, "")
        .trim()
        .slice(0, 180);
      if (body.length < 16 || /^(no data|error|unknown tool)/i.test(body)) continue;
      parts.push(`${label}: ${body}`);
    }
    return parts.join(" ").slice(0, 220);
  }

  function summarizeToolResults(toolResults) {
    const header =
      typeof HalAgentProgramming !== "undefined" && HalAgentProgramming.toolSynthesisGuide
        ? HalAgentProgramming.toolSynthesisGuide() + "\n\n"
        : "Synthesize these tool results into your answer (do not paste raw dumps):\n\n";
    return (
      header +
      Object.entries(toolResults || {})
        .map(([id, res]) => {
          const label = (TOOL_DEFS[id] && TOOL_DEFS[id].label) || id;
          const body = res && res.summary ? String(res.summary).slice(0, AGENT_BUDGET.maxToolSummaryChars) : "No data.";
          return `### ${label}\n${body}`;
        })
        .join("\n\n")
    );
  }

  function summarizeWorkingMemory(working) {
    const turns = working.turns || [];
    if (typeof HalCore !== "undefined" && HalCore.compressThreadForPrompt) {
      return HalCore.compressThreadForPrompt(turns, AGENT_BUDGET.maxRecentTurns);
    }
    const recent = turns.slice(-AGENT_BUDGET.maxRecentTurns);
    if (!recent.length) return "";
    return recent
      .map((t) => `${t.role}: ${String(t.text).slice(0, 160)}${t.intent ? ` [${t.intent}]` : ""}`)
      .join("\n");
  }

  function buildAgentSystemPrompt(ctx, plan, toolResults, working, longTerm) {
    const query = plan && plan.originalQuery ? plan.originalQuery : "";
    const usePlanStyle =
      plan.questionType === "planning" &&
      (HalCore.wantsStructuredPlan ? HalCore.wantsStructuredPlan(query) : /make a plan|prioriti/i.test(query));
    const base =
      plan.questionType === "planning" && !usePlanStyle
        ? HalCore.buildReasoningChatPrompt(ctx.halData, null)
        : plan.questionType === "planning"
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
    if (working.sessionSummary) {
      parts.push("", working.sessionSummary);
    }
    if (plan.agentToolLoop && typeof HalAgentLoop !== "undefined") {
      parts.push("", HalAgentLoop.TOOL_LOOP_GUIDE);
      if (plan.loopSuffix) parts.push("", "Prior tool loop results:", String(plan.loopSuffix).slice(0, 6000));
    }
    if (plan.planOnly) {
      parts.push("", "PLAN ONLY: propose steps and patches but do not claim changes were applied.");
    }

    parts.push(
      "",
      plan.questionType === "planning" && !usePlanStyle
        ? "Answer clearly: cite local evidence and one safe next step for staff. Use five+ sentences for planning questions."
        : "Verify: answer the question, do not invent data, do not claim external actions, note missing data. Proportional depth — simple questions stay concise; reasoning and code questions get full detail. Markdown allowed for source citations.",
    );
    return parts.join("\n");
  }

  function buildFastChatAgentPrompt(ctx, plan, toolResults, working, longTerm) {
    const toolText = summarizeToolResults(toolResults);
    const parts = [HalCore.buildFastChatSystemPrompt(ctx.halData, null)];
    const thread = HalCore.buildThreadContextBlock(working.turns, plan && plan.originalQuery ? plan.originalQuery : "");
    if (thread) parts.push("", thread);
    if (working.preferBrief) parts.push("", "User prefers brief answers this session — keep replies short.");
    if (toolText) {
      parts.push("", "Tool results:", toolText.slice(0, 1200));
    }
    const turnText = summarizeWorkingMemory(working);
    if (turnText) {
      parts.push("", "Recent turns:", turnText.slice(0, 400));
    }
    parts.push(
      "",
      "Write like a Cursor Auto-style agent: direct answer first, then evidence and implications. Proportional depth — simple questions can be short; complex or diagnostic questions need detail. Markdown and code citations allowed when discussing program source.",
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
    if (plan.useModelEnhancement && body.length < 28) issues.push("too_short");
    if (
      plan.useModelEnhancement &&
      route &&
      route.useReasoning &&
      typeof HalCore !== "undefined" &&
      HalCore.countSentences &&
      HalCore.countSentences(body) < (HalCore.MIN_REPLY_SENTENCES || 5)
    ) {
      issues.push("too_few_sentences");
    } else if (
      plan.useModelEnhancement &&
      route &&
      route.useReasoning &&
      typeof HalCore !== "undefined" &&
      HalCore.countWords &&
      HalCore.countWords(body) < 42
    ) {
      issues.push("too_short");
    }

    if (typeof HalCore !== "undefined" && HalCore.chatShapeIssues) {
      const prevHal = (workingMemory.turns || []).filter((t) => t.role === "hal").slice(-1)[0];
      const shapeIssues = HalCore.chatShapeIssues(query, body, route, {
        previousHalText: prevHal ? prevHal.text : "",
        hadToolResults: !!(toolResults && Object.keys(toolResults).length),
        toolsUsed: plan && plan.tools ? plan.tools : [],
        hadSourceTools: !!(plan && plan.tools && plan.tools.some((t) => /grep_program|read_program_file|list_program_files|explain_route/.test(t))),
      });
      shapeIssues.forEach((issue) => {
        if (!issues.includes(issue)) issues.push(issue);
      });
    }

    let repaired = null;
    if (issues.includes("empty_response")) {
      repaired =
        (route && route.text) ||
        "I could not produce a safe answer from local data. Try asking what HAL can do, or name a page, widget, or review task.";
    } else if (issues.includes("unsafe_not_refused")) {
      const fw = typeof HalCore !== "undefined" ? HalCore.FALLBACK_FIREWALL : null;
      repaired =
        typeof HalCore !== "undefined" && HalCore.variedBlockedCapabilityReply
          ? HalCore.variedBlockedCapabilityReply(fw, query)
          : "That is an external action, so it stops at the firewall and needs human review. I can open the right page and prepare review notes, but a person must take the external step.";
    } else if (issues.includes("claimed_external_action")) {
      repaired =
        body.replace(/\bI (submitted|sent|emailed|uploaded|posted|deleted|paid|wired|faxed)\b/gi, "A human must") +
        "\n\n(Local draft only — external delivery requires human review.)";
    } else if (
      issues.some((i) =>
        i === "too_long_chat" ||
        i === "identity_monologue" ||
        i === "numbered_list_unrequested" ||
        i === "yes_no_not_direct" ||
        i === "chatbot_filler" ||
        i === "repeats_previous" ||
        i === "internal_jargon" ||
        i === "question_echo" ||
        i === "answer_not_first" ||
        i === "too_few_sentences" ||
        i === "missing_evidence_when_tools" ||
        i === "no_next_step" ||
        i === "sarcasm_or_dismissal" ||
        i === "engagement_bait",
      )
    ) {
      repaired =
        typeof HalCore !== "undefined" && HalCore.repairChatShape
          ? HalCore.repairChatShape(query, body, route, issues)
          : body;
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
    if (role === "user" && HalCore.wantsBriefReply && HalCore.wantsBriefReply(text)) workingMemory.preferBrief = true;
    if (role === "hal" && meta && meta.intent && /blocked: firewall|capability:blocked/.test(meta.intent)) {
      workingMemory.firewallBriefCount = (workingMemory.firewallBriefCount || 0) + 1;
    }
    workingMemory.updatedAt = new Date().toISOString();
    if (typeof HalCore !== "undefined" && HalCore.updateSessionSummary) {
      workingMemory.sessionSummary = HalCore.updateSessionSummary(workingMemory.turns, workingMemory.sessionSummary);
    }
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

  function preferHigherReasoning(ctx) {
    if (typeof globalThis !== "undefined" && globalThis._halForceReasoning === false) return false;
    if (typeof globalThis !== "undefined" && (globalThis._halRandomQaUseReasoning || globalThis._halForceReasoning)) {
      return true;
    }
    const cfg = ctx && ctx.halModels && ctx.halModels.config;
    return !!(cfg && cfg.preferReasoning);
  }

  function routeIsOperational(route) {
    if (!route) return false;
    return Object.keys(route).some((k) => k.startsWith("use") && route[k] === true && k !== "useModel" && k !== "useReasoning" && k !== "useEscalation" && k !== "useOss");
  }

  function reason21bAvailable(ctx) {
    if (typeof ctx.reason21bAvailable === "function") return ctx.reason21bAvailable();
    if (typeof ctx.reasoningModelConfig === "function") {
      const rc = ctx.reasoningModelConfig();
      return !!(rc && !rc.reasonFallback);
    }
    return false;
  }

  function downgradeRouteIfReasoningOffline(route, ctx) {
    if (!route || !route.useReasoning) return route;
    if (reason21bAvailable(ctx)) return route;
    if (typeof ctx.localModelReady === "function" && ctx.localModelReady()) {
      const r = Object.assign({}, route);
      r.useReasoning = false;
      r.useModel = true;
      r.useEscalation = false;
      r.useOss = false;
      r.lane = "chat8b";
      if (/^reasoning:/.test(String(r.intent || ""))) r.intent = "model: query";
      return r;
    }
    return route;
  }

  function applyHigherReasoningRoute(route, query, ctx) {
    if (!route) return route;
    // Template/instant routes already have staff-facing text — keep fast path.
    if (route.text && String(route.text).trim()) return route;
    if (routeIsOperational(route)) return route;
    const ap = (ctx && ctx.halModels && ctx.halModels.config && ctx.halModels.config.agentProgramming) || {};
    const agentLoopQuery =
      ap.agentToolLoop !== false &&
      ap.agentLoopUseReasoning !== false &&
      (/(how does|why is|fix|debug|investigate|validate|patch|source code|grep|where is .* handled|implement|make.*pass)/i.test(
        String(query || ""),
      ) ||
        /<<<tool/i.test(String(query || "")));
    if (
      agentLoopQuery &&
      typeof ctx.reasoningModelReady === "function" &&
      ctx.reasoningModelReady()
    ) {
      const r = Object.assign({}, route);
      if (reason21bAvailable(ctx)) {
        r.useReasoning = true;
        r.useModel = false;
        r.lane = "reason21b";
      } else {
        r.useReasoning = false;
        r.useModel = true;
        r.lane = "chat8b";
      }
      r.useEscalation = false;
      r.useOss = false;
      r.text = "";
      r.prompt = r.prompt || query;
      if (!/^reasoning:/.test(String(r.intent || ""))) {
        r.intent = reason21bAvailable(ctx) ? "reasoning: agent-loop" : "model: query";
      }
      return r;
    }
    if (!preferHigherReasoning(ctx)) return route;
    if (typeof ctx.reasoningModelReady === "function" && !ctx.reasoningModelReady()) {
      return downgradeRouteIfReasoningOffline(Object.assign({}, route, { useReasoning: true, useModel: false, lane: "reason21b" }), ctx);
    }
    const intent = String(route.intent || "");
    if (
      /^navigate:/.test(intent) &&
      route.actions &&
      route.actions.length &&
      typeof HalCore !== "undefined" &&
      HalCore.isSimpleActionQuery &&
      HalCore.isSimpleActionQuery(query)
    ) {
      return route;
    }
    if (intent === "imports: refresh" && route.useImportRefresh) return route;
    const r = Object.assign({}, route);
    if (reason21bAvailable(ctx)) {
      r.useReasoning = true;
      r.useModel = false;
      r.lane = "reason21b";
    } else {
      r.useReasoning = false;
      r.useModel = true;
      r.lane = "chat8b";
    }
    r.useEscalation = false;
    r.useOss = false;
    r.prompt = r.prompt || query;
    if (!/^reasoning:/.test(intent)) {
      r.intent = reason21bAvailable(ctx)
        ? globalThis._halRandomQaUseReasoning
          ? "reasoning: qa"
          : "reasoning: chat"
        : "model: query";
    }
    return r;
  }

  function isFastChatRoute(route) {
    return !!(route.useModel && !route.useReasoning && !route.useEscalation && !route.useOss);
  }

  function fastChatSkipsProgramContext(route) {
    // Speed-first chat: tool summaries and route handlers cover office data.
    return isFastChatRoute(route);
  }

  async function enhanceModelCall(ctx, route, query, plan, toolResults, onToken) {
    const agentCfg = (ctx && ctx.halModels && ctx.halModels.config && ctx.halModels.config.agentProgramming) || {};
    const isFastChat = isFastChatRoute(route) && !(plan && plan.agentToolLoop);
    const agentPrompt = isFastChat
      ? buildFastChatAgentPrompt(ctx, plan, toolResults, workingMemory, longTermMemory)
      : buildAgentSystemPrompt(ctx, plan, toolResults, workingMemory, longTermMemory);

    const userText = (function () {
      const thread = HalCore.buildThreadContextBlock(workingMemory.turns, query);
      if (typeof HalAgentProgramming !== "undefined" && HalAgentProgramming.formatUserTurn) {
        return HalAgentProgramming.formatUserTurn(query, thread);
      }
      return thread ? thread + "\n\n" + query : query;
    })();

    const snapshotToolRan = (plan.tools || []).some(
      (t) => t === "read_program_snapshot" || t === "read_widget_feed" || t === "read_claims_summary",
    );
    const ctxCap = isFastChat
      ? 1200
      : route.useReasoning || route.useEscalation
        ? AGENT_BUDGET.maxModelContextChars
        : route.useModel
          ? 3500
          : AGENT_BUDGET.maxModelContextChars;
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
      const text = await ctx.runModel(em, combinedPrompt, userText, "Local escalation draft");
      return { text, lane: "escalate30b" };
    }
    if (route.useOss) {
      if (!ctx.ossModelReady()) return { text: ctx.offlineModelMessage("oss120b"), lane: "oss120b · offline" };
      const om = ctx.ossModelConfig();
      const text = await ctx.runModel(om, combinedPrompt, userText, "Local OSS draft", onToken);
      return { text, lane: "oss120b" };
    }
    const useCloudAgent = plan && plan.agentToolLoop && cloudAgentEligible(plan, ctx);
    if (useCloudAgent) {
      const cloudPolicy = (ctx.halModels && ctx.halModels.config && ctx.halModels.config.cloudReasoning) || {};
      const shouldSanitize = cloudPolicy.sanitizeBeforeCloud !== false;
      let sysPrompt = combinedPrompt;
      let usrText = userText;
      if (shouldSanitize && typeof ctx.sanitizeForCloud === "function") {
        sysPrompt = ctx.sanitizeForCloud(sysPrompt);
        usrText = ctx.sanitizeForCloud(usrText);
      }
      const cm = Object.assign({ cloud: true, agentLoop: true, structuredAgent: true }, ctx.cloudModelConfig());
      cm.options = Object.assign({}, cm.options || {}, { max_tokens: 2048, temperature: 0.2 });
      cm.cloudTools = buildCloudToolSchemas(agentLoopToolIds(plan));
      const raw = await ctx.runModel(cm, sysPrompt, usrText, "Cloud agent", onToken);
      if (raw && typeof raw === "object" && (raw.toolCalls || raw.text != null)) {
        return {
          text: String(raw.text || ""),
          toolCalls: raw.toolCalls || [],
          lane: "cloud",
        };
      }
      const text = typeof raw === "string" ? raw : String((raw && raw.text) || "");
      return { text, lane: "cloud" };
    }
    const wantAgentReasoning =
      plan &&
      plan.agentToolLoop &&
      agentCfg.agentLoopUseReasoning !== false &&
      route.useModel &&
      !route.useReasoning &&
      !route.useEscalation &&
      typeof ctx.reasoningModelReady === "function" &&
      ctx.reasoningModelReady();
    if (wantAgentReasoning) {
      let rm = Object.assign({ reasoningLane: true, agentLoop: true }, ctx.reasoningModelConfig());
      rm.options = Object.assign({}, rm.options || {}, { num_predict: 1800 });
      rm = attachOllamaNativeTools(rm, plan, agentCfg);
      const raw = await ctx.runModel(rm, combinedPrompt, userText, "Agent loop reasoning", onToken);
      if (raw && typeof raw === "object" && (raw.toolCalls || raw.text != null)) {
        return {
          text: String(raw.text || ""),
          toolCalls: raw.toolCalls || [],
          lane: "reason21b",
        };
      }
      const text = typeof raw === "string" ? raw : String((raw && raw.text) || "");
      return { text, lane: "reason21b" };
    }
    if (route.useReasoning) {
      if (!ctx.reasoningModelReady()) {
        if (ctx.localModelReady && ctx.localModelReady()) {
          const lm = Object.assign({ fastChat: true, reasonFallback: true }, ctx.localModelConfig());
          const text = await ctx.runModel(lm, combinedPrompt, userText, "Local chat fallback", onToken);
          return { text, lane: "chat8b" };
        }
        return { text: ctx.offlineModelMessage("reason21b"), lane: "reason21b · offline" };
      }
      const rm = Object.assign({ reasoningLane: true }, ctx.reasoningModelConfig());
      const rmTools = plan && plan.agentToolLoop ? attachOllamaNativeTools(rm, plan, agentCfg) : rm;
      try {
        const raw = await ctx.runModel(rmTools, combinedPrompt, userText, "Local reasoning plan", onToken);
        const text = typeof raw === "string" ? raw : String((raw && raw.text) || "");
        const toolCalls = raw && typeof raw === "object" ? raw.toolCalls : null;
        if (String(text || "").trim() || (toolCalls && toolCalls.length)) {
          return {
            text,
            toolCalls: toolCalls || [],
            lane: rm.reasonFallback ? "chat8b" : "reason21b",
          };
        }
      } catch (error) {
        if (typeof RuntimeIssues !== "undefined") {
          RuntimeIssues.record("hal-agent.reasoning", error, { lane: route.lane, intent: route.intent });
        }
      }
      if (ctx.localModelReady && ctx.localModelReady()) {
        const lm = Object.assign({ fastChat: true, reasonFallback: true }, ctx.localModelConfig());
        const text = await ctx.runModel(lm, combinedPrompt, userText, "Local chat fallback", onToken);
        return { text, lane: "chat8b" };
      }
      return { text: ctx.offlineModelMessage("reason21b"), lane: "reason21b · offline" };
    }
    if (route.useModel) {
      if (!ctx.localModelReady()) {
        if (typeof HalCore !== "undefined" && HalCore.offlineModelChatMessage) {
          return {
            text: HalCore.offlineModelChatMessage("chat8b", ctx.halModels, ctx.halData, query),
            lane: "local",
          };
        }
        return { text: ctx.offlineModelMessage("chat8b"), lane: "chat8b · offline" };
      }
      const lm = Object.assign({ fastChat: true }, ctx.localModelConfig());
      if (HalCore.isChatSizedQuestion && HalCore.isChatSizedQuestion(query, route)) {
        lm.options = Object.assign({}, lm.options || {}, { temperature: 0.42 });
      }
      const text = await ctx.runModel(lm, combinedPrompt, userText, "Local chat draft", onToken);
      return { text, lane: "chat8b" };
    }
    return null;
  }

  async function spawnInvestigationSubtask(ctx, focusQuery, parentQuery) {
    const focus = String(focusQuery || "").trim();
    if (!focus) return { ok: false, summary: "Sub-investigation needs a focused question." };
    const agentCfg = (ctx.halModels && ctx.halModels.config && ctx.halModels.config.agentProgramming) || {};
    const maxDepth = typeof agentCfg.subtaskMaxDepth === "number" ? agentCfg.subtaskMaxDepth : 1;
    const depth = Number(ctx.subtaskDepth || 0);
    if (depth >= maxDepth) {
      return { ok: false, summary: "Sub-investigation depth limit reached — answer from prior context." };
    }
    if (typeof HalAgentLoop === "undefined" || !HalAgentLoop.runModelWithLoop) {
      return { ok: false, summary: "Agent loop unavailable for sub-investigation." };
    }
    ctx.subtaskDepth = depth + 1;
    let subRoute = HalCore.routeHalCommand(ctx.halData, ctx.halModels, ctx.pages, focus);
    subRoute = escalateRouteForRetry(subRoute, focus);
    const subPlan = buildPlan(focus, subRoute, workingMemory, longTermMemory, ctx);
    const loopSuffix =
      "\n[Sub-investigation" +
      (parentQuery ? " for: " + String(parentQuery).slice(0, 160) : "") +
      "]\nAnswer this focused slice only; cite file paths and line evidence.\n";
    const activeSubPlan = Object.assign({}, subPlan, {
      agentToolLoop: true,
      isInvestigateQuery: true,
      loopSuffix,
    });
    const runToolFn = (id, c, q) => {
      const def = TOOL_DEFS[id];
      return def ? def.run(c, { query: q, parentQuery: parentQuery || focus }) : Promise.resolve({ ok: false, summary: "Unknown tool: " + id });
    };
    try {
      const result = await HalAgentLoop.runModelWithLoop({
        enhanceModelCall,
        runTool: runToolFn,
        ctx,
        route: subRoute,
        query: focus,
        plan: activeSubPlan,
        initialToolResults: {},
        onToken: undefined,
        toolIds: new Set(Object.keys(TOOL_DEFS).filter((id) => id !== "spawn_investigation")),
        maxTurnsOverride: 3,
      });
      const text = result && result.text ? String(result.text).trim() : "";
      if (!text) return { ok: false, summary: "Sub-investigation completed without a usable answer." };
      return {
        ok: true,
        summary: ("Sub-investigation (" + (result.loopTurns || 0) + " turns):\n" + text).slice(0, 2800),
        loopTurns: result.loopTurns || 0,
      };
    } catch (error) {
      if (typeof RuntimeIssues !== "undefined") {
        RuntimeIssues.record("hal-agent.spawn-investigation", error, { focus: focus.slice(0, 80) });
      }
      return { ok: false, summary: "Sub-investigation failed: " + String(error && error.message ? error.message : error) };
    } finally {
      ctx.subtaskDepth = depth;
    }
  }

  TOOL_DEFS.spawn_investigation = {
    label: "Run focused sub-investigation (subagent)",
    run: async (ctx, args) =>
      spawnInvestigationSubtask(
        ctx,
        String(args.query || "").trim(),
        String(args.parentQuery || args.query || "").trim(),
      ),
  };

  /**
   * Main agent entry: plan → enrich with tools → execute route → self-check → repair log.
   * ctx.executeRoute(route, query, toolResults) must return { text, lane, actions, intent }.
   */
  const MODEL_SHAPE_ISSUES = new Set([
    "too_long_chat",
    "numbered_list_unrequested",
    "yes_no_not_direct",
    "repeats_previous",
    "answer_not_first",
    "question_echo",
    "internal_jargon",
    "instruction_leak",
    "too_few_sentences",
    "missing_evidence_when_tools",
    "no_next_step",
  ]);

  async function rewriteShapeViaModel(ctx, query, draftText, route) {
    if (!ctx || typeof ctx.runModel !== "function") return null;
    const useReason =
      route && route.useReasoning && typeof ctx.reasoningModelReady === "function" && ctx.reasoningModelReady();
    if (!useReason && (!ctx.localModelReady || !ctx.localModelReady())) return null;
    const lm = useReason
      ? Object.assign({ reasoningLane: true }, ctx.reasoningModelConfig())
      : Object.assign({ fastChat: true }, ctx.localModelConfig());
    const system =
      "Rewrite HAL's reply for staff chat. Clear, direct, collaborative — like a strong coding agent explaining to a colleague. At least five complete sentences with real detail. Answer in the first sentence. No markdown, no numbered lists unless they asked for a plan, no internal jargon, no echoing the question, no filler closings. Keep evidence and recommendations from the draft.";
    const user = `Question: ${query}\n\nDraft to rewrite:\n${String(draftText || "").slice(0, 1400)}`;
    try {
      const text = await ctx.runModel(lm, system, user, "Shape repair");
      return typeof HalCore !== "undefined" && HalCore.cleanModelText ? HalCore.cleanModelText(text) : text;
    } catch {
      return null;
    }
  }

  function finalizeOutcome(outcome, trimmed, route, plan, ctx, toolResults) {
    if (!outcome || !outcome.text || !HalCore.polishChatReply) return outcome;
    const toolSummary = summarizeToolEvidenceOnly(toolResults || {});
    let actionLabel = "";
    const navMatch = route && route.intent ? String(route.intent).match(/^navigate:\s*(.+)$/) : null;
    if (navMatch && ctx.pages) {
      const info = HalCore.pageInfoMap(ctx.halData, ctx.pages)[navMatch[1]];
      actionLabel = info && info.label ? info.label : navMatch[1];
    }
    outcome.text = HalCore.polishChatReply(outcome.text, trimmed, route, {
      halData: ctx.halData,
      halModels: ctx.halModels,
      pages: ctx.pages,
      currentPage: workingMemory.currentPage,
      preferBrief: workingMemory.preferBrief,
      synthesize: !plan.useModelEnhancement,
      firewallBriefCount: workingMemory.firewallBriefCount || 0,
      toolSummary,
      actionLabel,
      toolsUsed: plan && plan.tools ? plan.tools : [],
      hadSourceTools: !!(plan && plan.tools && plan.tools.some((t) => /grep_program|read_program_file|list_program_files|explain_route/.test(t))),
    });
    outcome.followUpChips = HalCore.buildFollowUpChips(
      Object.assign({}, outcome, { _pages: ctx.pages }),
      route,
      ctx.halData,
      trimmed,
    );
    if (HalCore.inferPageActionsFromAnswer && ctx.pages) {
      const inferred = HalCore.inferPageActionsFromAnswer(outcome.text, ctx.pages);
      if (inferred.length && (!outcome.actions || !outcome.actions.length)) {
        outcome.actions = inferred;
      }
    }
    if (navMatch && (!outcome.actions || !outcome.actions.length)) {
      const pageId = navMatch[1];
      const info = HalCore.pageInfoMap(ctx.halData, ctx.pages)[pageId];
      outcome.actions = [
        {
          type: "openPage",
          label: "Open " + (info && info.label ? info.label : pageId),
          page: pageId,
        },
      ];
    }
    if (HalCore.toSpokenScript) {
      outcome.spokenScript = HalCore.toSpokenScript(outcome.text, trimmed, route, {
        preferBrief: workingMemory.preferBrief,
      });
    }
    return outcome;
  }

  function isOfflineModelLane(lane) {
    return /\boffline\b/i.test(String(lane || ""));
  }

  async function ensureOfflineToolGather(trimmed, route, plan, toolResults, ctx, runToolFn) {
    if (Object.keys(toolResults || {}).length >= 2) return toolResults;
    if (typeof HalAgentLoop === "undefined" || !HalAgentLoop.suggestAutoTools) return toolResults;
    const toolIds = new Set(Object.keys(TOOL_DEFS));
    const agentCfg = (ctx.halModels && ctx.halModels.config && ctx.halModels.config.agentProgramming) || {};
    const auto = HalAgentLoop.suggestAutoTools(trimmed, plan, toolResults, toolIds, agentCfg).slice(0, 3);
    for (const req of auto) {
      const def = TOOL_DEFS[req.name];
      if (!def) continue;
      toolResults[req.name + "_offline"] = await def.run(ctx, { query: req.query || trimmed });
    }
    return toolResults;
  }

  async function processQuery(query, ctx) {
    const trimmed = String(query).trim();
    if (!trimmed) return null;
    const startedAt = Date.now();

    // Lazy memory: load once per session, never on the per-query hot path again.
    if (!memoryLoaded) await loadMemory(ctx);
    workingMemory.currentPage = ctx.getCurrentPage ? ctx.getCurrentPage() : null;
    workingMemory.activeWorkSession = !!(ctx.halWorkSession);
    recordTurn("user", trimmed, { focus: workingMemory.currentPage });

    let route = downgradeRouteIfReasoningOffline(
      applyHigherReasoningRoute(HalCore.routeHalCommand(ctx.halData, ctx.halModels, ctx.pages, trimmed), trimmed, ctx),
      ctx,
    );
    const plan = buildPlan(trimmed, route, workingMemory, longTermMemory, ctx);
    const isModelLane = !!(route.useModel || route.useReasoning || route.useEscalation || route.useOss);

    if (typeof HalCore.detectAmbiguousQuery === "function") {
      const clarify = HalCore.detectAmbiguousQuery(trimmed, workingMemory.turns);
      if (clarify) {
        const clarifyOutcome = {
          text: clarify.text,
          lane: "local",
          actions: [],
          intent: "clarify:ambiguous",
          followUpChips: clarify.chips,
        };
        finalizeOutcome(clarifyOutcome, trimmed, route, plan, ctx, {});
        recordTurn("hal", clarifyOutcome.text, { intent: clarifyOutcome.intent, tools: [] });
        saveMemory(ctx);
        return Object.assign({}, clarifyOutcome, { plan, toolResults: {}, selfCheck: { pass: true, issues: [], clarify: true } });
      }
    }

    // Instant local-command path:
    // model run straight through the executor so they answer with zero extra
    // latency (template responses are inherently within the safety policy).
    if (!isModelLane && !plan.useModelEnhancement && (!plan.tools || plan.tools.length === 0)) {
      const fast = await ctx.executeRoute(route, trimmed, {});
      if (fast) {
        let checked = selfCheckResponse(trimmed, fast.text, plan, {}, route);
        if (!checked.pass && checked.repaired) fast.text = checked.repaired;
        finalizeOutcome(fast, trimmed, route, plan, ctx, {});
        recordTurn("hal", fast.text, { intent: fast.intent || route.intent, tools: [] });
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

    const patchSpec = parsePatchFromQuery(trimmed);
    if (patchSpec) ctx.pendingPatch = patchSpec;

    let toolResults = plan.tools.length ? await runTools(plan.tools, ctx, trimmed) : {};
    let activePlan = plan;
    const agentCfg = (ctx.halModels && ctx.halModels.config && ctx.halModels.config.agentProgramming) || {};

    if (plan.useModelEnhancement && isInvestigateQuery(trimmed, route)) {
      const extra = expandGatherToolsForRound(trimmed, route, toolResults, 1, Object.keys(toolResults));
      if (extra.length) {
        const more = await runTools(extra, ctx, trimmed);
        Object.assign(toolResults, more);
        activePlan = Object.assign({}, plan, { tools: [...new Set([...plan.tools, ...extra])] });
      }
    }

    if (
      plan.useModelEnhancement &&
      agentCfg.spawnSubtasks !== false &&
      isComplexInvestigationQuery(trimmed, route) &&
      !toolResults.spawn_investigation
    ) {
      const focus = extractSubInvestigationFocus(trimmed);
      if (ctx.onToolProgress) {
        ctx.onToolProgress({ phase: "start", tool: "spawn_investigation", label: "Sub-investigation" });
      }
      toolResults.spawn_investigation = await spawnInvestigationSubtask(ctx, focus, trimmed);
      if (ctx.onToolProgress) {
        ctx.onToolProgress({
          phase: "done",
          tool: "spawn_investigation",
          ok: !!(toolResults.spawn_investigation && toolResults.spawn_investigation.ok),
        });
      }
      activePlan = Object.assign({}, activePlan, {
        loopSuffix:
          (activePlan.loopSuffix || "") +
          "\n\nPrior sub-investigation:\n" +
          String((toolResults.spawn_investigation && toolResults.spawn_investigation.summary) || "").slice(0, 2200),
      });
    }

    let outcome;
    const runToolFn = (id, c, q) => {
      const def = TOOL_DEFS[id];
      return def ? def.run(c, { query: q }) : Promise.resolve({ ok: false, summary: "Unknown tool: " + id });
    };
    const toolIdSet = new Set(Object.keys(TOOL_DEFS));

    if (plan.useModelEnhancement) {
      try {
        let enhanced;
        if (typeof HalAgentLoop !== "undefined" && HalAgentLoop.runModelWithLoop) {
          enhanced = await HalAgentLoop.runModelWithLoop({
            enhanceModelCall,
            runTool: runToolFn,
            ctx,
            route,
            query: trimmed,
            plan: activePlan,
            initialToolResults: toolResults,
            onToken: ctx.onToken,
            toolIds: toolIdSet,
          });
        } else {
          enhanced = await enhanceModelCall(ctx, route, trimmed, activePlan, toolResults, ctx.onToken);
          enhanced = Object.assign({}, enhanced, { toolResults, loopTurns: 0, loopLog: [] });
        }
        if (enhanced && enhanced.text && !isOfflineModelLane(enhanced.lane)) {
          if (enhanced.toolResults) Object.assign(toolResults, enhanced.toolResults);
          outcome = {
            text: enhanced.text,
            lane: enhanced.lane,
            actions: [],
            intent: route.intent,
            agentLoopTurns: enhanced.loopTurns || 0,
            agentLoopLog: enhanced.loopLog || [],
          };
        } else if (enhanced && isOfflineModelLane(enhanced.lane)) {
          if (enhanced.toolResults) Object.assign(toolResults, enhanced.toolResults);
          await ensureOfflineToolGather(trimmed, route, activePlan, toolResults, ctx, runToolFn);
          const synth = buildToolSynthesisOutcome(trimmed, activePlan, toolResults, route, ctx);
          if (synth) outcome = synth;
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

    if ((!outcome || isGenericOfflineText(outcome.text)) && plan.useModelEnhancement) {
      await ensureOfflineToolGather(trimmed, route, activePlan, toolResults, ctx, runToolFn);
      const synth = buildToolSynthesisOutcome(trimmed, activePlan, toolResults, route, ctx);
      if (synth) outcome = synth;
    }

    if (outcome && isGenericOfflineText(outcome.text)) {
      await ensureOfflineToolGather(trimmed, route, activePlan, toolResults, ctx, runToolFn);
      const synth = buildToolSynthesisOutcome(trimmed, activePlan, toolResults, route, ctx);
      if (synth) outcome = synth;
    }

    if (!outcome) {
      const lane = route.lane || "local";
      let offline = null;
      if (plan.useModelEnhancement) {
        if (typeof HalCore !== "undefined" && HalCore.offlineModelChatMessage) {
          offline = HalCore.offlineModelChatMessage(lane.replace(/\s·\soffline$/i, ""), ctx.halModels, ctx.halData, trimmed);
        } else if (typeof ctx.offlineModelMessage === "function") {
          offline = ctx.offlineModelMessage(lane);
        }
      }
      outcome = {
        text:
          offline ||
          "I could not complete that request. Check that Ollama is running at 127.0.0.1:11434, then try again.",
        lane: plan.useModelEnhancement ? "local" : lane,
        actions: [],
        intent: route.intent || "error",
      };
    }

    let checked = selfCheckResponse(trimmed, outcome.text, activePlan, toolResults, route);

    if (!checked.pass && needsMoreGather(checked, toolResults, plan, 1)) {
      const extra = expandGatherToolsForRound(trimmed, route, toolResults, 2, Object.keys(toolResults));
      if (extra.length) {
        const more = await runTools(extra, ctx, trimmed);
        Object.assign(toolResults, more);
        activePlan = Object.assign({}, plan, { tools: [...new Set([...plan.tools, ...extra])] });
        if (ctx.onToolProgress) {
          extra.forEach((toolId) => ctx.onToolProgress({ phase: "start", tool: toolId, label: toolId }));
        }
        try {
          const retry = await enhanceModelCall(ctx, route, trimmed, activePlan, toolResults, ctx.onToken);
          if (retry && String(retry.text || "").trim()) {
            outcome = {
              text: retry.text,
              lane: retry.lane || outcome.lane,
              actions: outcome.actions || [],
              intent: route.intent,
            };
            checked = selfCheckResponse(trimmed, outcome.text, activePlan, toolResults, route);
            logRepair(
              {
                query: trimmed,
                intent: route.intent,
                issues: ["multi_gather_round_2"],
                example: String(outcome.text || "").slice(0, 200),
                tools: activePlan.tools,
              },
              ctx.persistSet,
            );
          }
        } catch (error) {
          if (typeof RuntimeIssues !== "undefined") {
            RuntimeIssues.record("hal-agent.multi-gather", error, { intent: route.intent });
          }
        }
      }
    }

    if (
      !checked.pass &&
      shouldAutoEscalate(checked, route, agentCfg) &&
      typeof ctx.reasoningModelReady === "function" &&
      ctx.reasoningModelReady()
    ) {
      route = escalateRouteForRetry(route, trimmed);
      try {
        const retry = await enhanceModelCall(ctx, route, trimmed, plan, toolResults, ctx.onToken);
        if (retry && String(retry.text || "").trim()) {
          outcome = {
            text: retry.text,
            lane: retry.lane || "reason21b",
            actions: [],
            intent: route.intent,
          };
          checked = selfCheckResponse(trimmed, outcome.text, activePlan, toolResults, route);
          logRepair(
            {
              query: trimmed,
              intent: route.intent,
              issues: ["auto_escalate_reason21b"],
              example: String(outcome.text || "").slice(0, 200),
              tools: plan.tools,
            },
            ctx.persistSet,
          );
        }
      } catch (error) {
        if (typeof RuntimeIssues !== "undefined") {
          RuntimeIssues.record("hal-agent.auto-escalate", error, { intent: route.intent });
        }
      }
    }

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
      const recheck = selfCheckResponse(trimmed, outcome.text, plan, toolResults, route);
      const needsModel = recheck.issues.some((issue) => MODEL_SHAPE_ISSUES.has(issue));
      if (!recheck.pass && needsModel && plan.useModelEnhancement) {
        const rewritten = await rewriteShapeViaModel(ctx, trimmed, outcome.text, route);
        if (rewritten && String(rewritten).trim().length > 8) {
          outcome.text = String(rewritten).trim();
          logRepair(
            {
              query: trimmed,
              intent: route.intent,
              issues: recheck.issues.concat(["model_rewrite"]),
              example: String(outcome.text || "").slice(0, 200),
              tools: plan.tools,
            },
            ctx.persistSet,
          );
        }
      } else if (!recheck.pass && recheck.repaired) {
        outcome.text = recheck.repaired;
      }
    }

    if (shouldRunPostValidation(trimmed, toolResults) || (typeof HalAgentLoop !== "undefined" && HalAgentLoop.parseAllPatches(outcome.text).length)) {
      if (typeof HalAgentLoop !== "undefined" && HalAgentLoop.runValidateRetryLoop) {
        outcome = await HalAgentLoop.runValidateRetryLoop({
          ctx,
          query: trimmed,
          outcome,
          toolResults,
          route,
          activePlan,
          onToken: ctx.onToken,
          shouldValidate: shouldRunPostValidation(trimmed, toolResults),
          planOnly: activePlan.planOnly,
          runTool: runToolFn,
          enhanceModelCall,
          escalateRoute: escalateRouteForRetry,
          toolIds: toolIdSet,
          runModelWithLoopFn: HalAgentLoop.runModelWithLoop,
        });
      } else if (!toolResults.run_hal_validation) {
        toolResults.run_hal_validation = await TOOL_DEFS.run_hal_validation.run(ctx, { query: trimmed });
        const val = toolResults.run_hal_validation;
        if (val && outcome && outcome.text) {
          const tag = val.ok ? "Validation passed" : "Validation failed";
          outcome.text =
            String(outcome.text).replace(/\s+$/, "") +
            `\n\n${tag} (validate-hal.mjs):\n${String(val.summary || "").slice(0, 1600)}`;
        }
      }
    }

    finalizeOutcome(outcome, trimmed, route, activePlan, ctx, toolResults);

    const finalCheck = selfCheckResponse(trimmed, outcome.text, activePlan, toolResults, route);
    recordTurn("hal", outcome.text, { intent: outcome.intent, tools: activePlan.tools });
    health = {
      architectureVersion: ARCHITECTURE_VERSION,
      budget: AGENT_BUDGET,
      lastIntent: route.intent,
      lastQuestionType: activePlan.questionType,
      lastTools: activePlan.tools,
      lastSelfCheck: finalCheck.pass ? "pass" : "repaired:" + finalCheck.issues.join(","),
      lastLatencyMs: Date.now() - startedAt,
      lastModelLane: plan.useModelEnhancement ? route.lane : null,
      repairCount: repairLog.length,
      updatedAt: new Date().toISOString(),
    };
    saveMemory(ctx);

    return Object.assign({}, outcome, {
      plan: activePlan,
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
    syncAgentBudgetFromModels,
    buildCloudToolSchemas,
    attachOllamaNativeTools,
    cloudAgentEligible,
    agentLoopToolIds,
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
    parsePatchFromQuery,
    isTaskCompletionQuery,
    shouldRunPostValidation,
    synthesizeAnswerFromTools,
    isInvestigateQuery,
    isComplexInvestigationQuery,
    spawnInvestigationSubtask,
  };
})();

if (typeof window !== "undefined") window.HalAgent = HalAgent;
if (typeof module !== "undefined" && module.exports) module.exports = HalAgent;
