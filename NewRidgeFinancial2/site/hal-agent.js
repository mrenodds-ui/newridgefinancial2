/**
 * HAL Agent Core — planner, local tools, working/long-term memory, self-check, repair loop.
 * Sits between routing and response generation. Browser + Node compatible.
 */
const HalAgent = (function () {
  const MEMORY_KEY = "halAgentMemory";
  const REPAIR_KEY = "halRepairLog";
  const WORKING_KEY = "halWorkingMemory";
  const ARCHITECTURE_VERSION = "hal-agent-v13-cursor";
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

  function workstationFastHalActive() {
    if (typeof globalThis === "undefined") return false;
    if (globalThis._halWorkstationFastMode === false) return false;
    if (globalThis._halWorkstationFastMode === true) return true;
    if (globalThis.NR2_WORKSTATION_FAST_HAL === false) return false;
    if (globalThis.NR2_WORKSTATION_FAST_HAL === true) return true;
    if (globalThis.NR2_WORKSTATION_ONLY && globalThis.NR2_WORKSTATION_FAST_HAL !== false) return true;
    return false;
  }

  function syncAgentBudgetFromModels(halModels) {
    const ap = (halModels && halModels.config && halModels.config.agentProgramming) || {};
    if (typeof ap.maxToolsPerTurn === "number" && ap.maxToolsPerTurn > 0) {
      AGENT_BUDGET.maxTools = Math.min(20, ap.maxToolsPerTurn);
    }
    if (typeof ap.multiGatherRounds === "number" && ap.multiGatherRounds > 0) {
      AGENT_BUDGET.maxGatherRounds = Math.min(6, ap.multiGatherRounds);
    }
    const c9000 = halModels && halModels.config && halModels.config.chat9000;
    if (c9000 && c9000.enabled !== false) {
      AGENT_BUDGET.maxModelContextChars = 18000;
      AGENT_BUDGET.maxToolSummaryChars = 6200;
      AGENT_BUDGET.maxRecentTurns = 16;
    }
    const c10000 = halModels && halModels.config && halModels.config.chat10000;
    if (c10000 && c10000.enabled !== false) {
      AGENT_BUDGET.maxModelContextChars = 22000;
      AGENT_BUDGET.maxToolSummaryChars = 7500;
      AGENT_BUDGET.maxRecentTurns = 18;
      if (typeof ap.maxToolsPerTurn === "number") {
        AGENT_BUDGET.maxTools = Math.min(24, Math.max(AGENT_BUDGET.maxTools, ap.maxToolsPerTurn));
      }
    }
    if (typeof HalAgentLoop !== "undefined" && HalAgentLoop.configureFromAgentProgramming) {
      HalAgentLoop.configureFromAgentProgramming(ap);
    }
    if (typeof globalThis !== "undefined" && globalThis._halInterviewMode) {
      AGENT_BUDGET.maxGatherRounds = 1;
      AGENT_BUDGET.maxTools = Math.min(AGENT_BUDGET.maxTools, 6);
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

  function shouldUseAgentToolLoop(query, route, agentCfg) {
    if (agentCfg && agentCfg.agentToolLoop === false) return false;
    if (/<<<tool/i.test(String(query || ""))) return true;
    if (isTaskCompletionQuery(query)) return true;
    if (isInvestigateQuery(query, route)) return true;
    if (route && (route.useEscalation || route.useOss)) return true;
    if (route && route.text && hasUseFlag(route) && !/\b(code|source|grep|fix|patch|debug|investigate)\b/i.test(query)) {
      return false;
    }
    if (
      /\b(show|list|open|refresh|monitor|run a readiness|check claim|explain .+ widget|can you (show|list|open|refresh|monitor|run|check|explain)|posting queue items?)\b/i.test(
        query,
      ) &&
      !/\b(code|source|grep|fix|patch|debug|investigate|why is|how does)\b/i.test(query)
    ) {
      return false;
    }
    if (/\b(make a plan|prioriti|reason through|think through|analyze .+ and tell)\b/i.test(query) && route && route.useReasoning) {
      return false;
    }
    return false;
  }

  function wantsOllamaNativeTools(plan, query, agentCfg) {
    if (!plan || !plan.agentToolLoop || agentCfg.localOllamaTools === false) return false;
    return !!(
      plan.isTaskCompletionQuery ||
      plan.isInvestigateQuery ||
      /\b(code|source|grep|patch|function|handled|hal-agent|debug|implement)\b/i.test(String(query || ""))
    );
  }

  function attachOllamaNativeTools(runtime, plan, query, agentCfg) {
    if (!wantsOllamaNativeTools(plan, query, agentCfg)) return runtime;
    const schemas = buildCloudToolSchemas(agentLoopToolIds(plan));
    if (!schemas.length) return runtime;
    return Object.assign({}, runtime, { structuredAgent: true, ollamaTools: schemas });
  }

  function browserCloudHalBlocked() {
    if (typeof window === "undefined" || !window.location) return false;
    if (typeof globalThis !== "undefined" && globalThis.NR2_WORKSTATION_ONLY) return false;
    const host = String(window.location.hostname || "").toLowerCase();
    const isLoopback = host === "127.0.0.1" || host === "localhost" || host === "::1";
    if (!isLoopback) return false;
    const db = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
    if (db && typeof db.getCachedCloudHalSettings === "function" && db.getCachedCloudHalSettings()?.enabled) return false;
    if (db && db.cloudHalSettingsCache && db.cloudHalSettingsCache.enabled) return false;
    return true;
  }

  async function cloudHalEnabledAsync(ctx) {
    const db = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
    if (db && typeof db.getCloudHalSettings === "function") {
      const settings = await db.getCloudHalSettings();
      return !!(settings && settings.enabled);
    }
    return false;
  }

  function cloudAgentEligible(plan, ctx) {
    if (typeof ctx.cloudAgentEligible === "function") return ctx.cloudAgentEligible(plan);
    if (ctx && ctx.cloudHalEnabled === true && plan && plan.agentToolLoop) return true;
    if (typeof ctx.cloudModelReady !== "function" || !ctx.cloudModelReady()) return false;
    const cfg = (ctx.halModels && ctx.halModels.config && ctx.halModels.config.cloudReasoning) || {};
    if (cfg.enabled !== true) return false;
    if (cfg.autoEnableWhenKeySet === false) return false;
    if (!plan || !plan.agentToolLoop) return false;
    if (cfg.preferForAllAgentLoops === true) return true;
    if (cfg.preferForTaskCompletion === false && !plan.isInvestigateQuery) return false;
    return !!(
      plan.isTaskCompletionQuery ||
      plan.isInvestigateQuery ||
      plan.isComplexInvestigationQuery ||
      isMultiAnalyzeQuery(plan.originalQuery || "")
    );
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
      "HAL is the internal office manager. Outbound actions (email, IIF export, claim packets) run only after staff consent — do not claim they were performed without consent and audit logging.",
      "Sound like a capable, friendly Cursor-style teammate: answer first, cite local evidence, name gaps, recommend one safe next step. At least five complete sentences on open work questions. Greetings and casual questions stay short and warm — no script or diagnostics dump. Accurate on missing data and consent limits — helpful, never sarcastic.",
      "Never fabricate missing import data; say what is missing.",
      "Never claim an external action was performed.",
      "If data is stale or unavailable, say so before recommending.",
      "Cite which local source or tool informed the answer when possible.",
      "When web research tool results are present, use them for public reference context and say they are not verified against this practice's live data.",
      "When planning or prioritizing, prefer the proactive office manager assessment over generic advice.",
      "Follow HalAgentProgramming contract when present: answer first, synthesize tools, min five sentences, one next step.",
    ],
  };

  // OM / HAL patient context (ephemeral per tab) — Moonshot Mon–Thu + dossier consults
  let omPatientContext = null;
  let omPatientContextSetAt = 0;
  const OM_PATIENT_CONTEXT_TTL_MS = 15 * 60 * 1000;

  function getOMPatientContext() {
    if (!omPatientContext) return null;
    if (Date.now() - omPatientContextSetAt > OM_PATIENT_CONTEXT_TTL_MS) {
      omPatientContext = null;
      return null;
    }
    return omPatientContext;
  }

  function setOMPatientContext(patientId) {
    const pid = String(patientId || "").trim();
    omPatientContext = pid || null;
    omPatientContextSetAt = pid ? Date.now() : 0;
    const bridge =
      typeof DesktopBridge !== "undefined"
        ? DesktopBridge
        : typeof window !== "undefined" && window.DesktopBridge
          ? window.DesktopBridge
          : null;
    if (bridge && typeof bridge.auditHalPatientContext === "function" && pid) {
      const hash = pid.length === 4 ? pid.toUpperCase() : String(pid).slice(0, 4);
      try {
        bridge.auditHalPatientContext({
          patientHash: hash,
          action: "set_context",
          timestamp: new Date().toISOString(),
        });
      } catch (_e) {
        /* audit best-effort */
      }
    }
    if (typeof window !== "undefined") {
      window.NR2_OM_PATIENT_CONTEXT = omPatientContext;
      try {
        window.dispatchEvent(
          new CustomEvent("nr2-om-patient-context", { detail: { patientId: omPatientContext } })
        );
      } catch (_e2) {
        /* ignore */
      }
    }
    return omPatientContext;
  }

  async function hasPatientDossierCapability() {
    const bridge =
      typeof DesktopBridge !== "undefined"
        ? DesktopBridge
        : typeof window !== "undefined" && window.DesktopBridge
          ? window.DesktopBridge
          : null;
    if (!bridge || typeof bridge.getAppInfo !== "function") {
      // Default OM role on workstation — allow; server still enforces
      return true;
    }
    try {
      const info = await bridge.getAppInfo();
      const caps = (info && info.capabilities) || [];
      if (!Array.isArray(caps)) return true;
      return (
        caps.includes("*") ||
        caps.includes("read_all") ||
        caps.includes("read_patient_dossier")
      );
    } catch (_e) {
      return true;
    }
  }

  function cloudHalBlockedForPatientTools() {
    const bridge =
      typeof DesktopBridge !== "undefined"
        ? DesktopBridge
        : typeof window !== "undefined" && window.DesktopBridge
          ? window.DesktopBridge
          : null;
    const settings = bridge && typeof bridge.getCachedCloudHalSettings === "function"
      ? bridge.getCachedCloudHalSettings()
      : null;
    // Patient PHI tools must stay local — reject when cloud HAL explicitly enabled for routing
    if (settings && settings.enabled === true && settings.forceCloudForPatient === true) {
      return true;
    }
    return false;
  }

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
        const claims =
          (snap && snap.claims && (snap.claims.top || snap.claims.claims)) || [];
        if (!window.HalSkills) return { ok: false, summary: "Claims tools unavailable." };
        const resp = HalSkills.buildClaimReadinessResponse(claims);
        let summary = HalSkills.formatClaimReadinessAnswer(resp);
        const bridge =
          typeof DesktopBridge !== "undefined"
            ? DesktopBridge
            : typeof window !== "undefined" && window.DesktopBridge
              ? window.DesktopBridge
              : null;
        if (bridge && typeof bridge.joinClaimPayers === "function" && claims.length) {
          try {
            const joined = await bridge.joinClaimPayers(claims.slice(0, 12));
            if (joined && joined.text) summary += "\n\n" + String(joined.text);
          } catch {
            /* optional join */
          }
        }
        return { ok: true, summary: summary.slice(0, 3500) };
      },
    },
    join_claim_payers: {
      label: "Join claim Payer labels to office payer reference",
      run: async (ctx, args) => {
        const bridge =
          typeof DesktopBridge !== "undefined"
            ? DesktopBridge
            : typeof window !== "undefined" && window.DesktopBridge
              ? window.DesktopBridge
              : null;
        if (!bridge || typeof bridge.joinClaimPayers !== "function") {
          return { ok: false, summary: "Claim payer join requires the NR2 server." };
        }
        let claims = [];
        const q = String((args && (args.query || args.payer)) || "").trim();
        if (q && !/\bclaim\b/i.test(q)) {
          // Single payer label lookup via join helper
          claims = [{ id: "query", payer: q, status: "" }];
        } else {
          const snap = await ctx.loadProgramSnapshot();
          claims = (snap && snap.claims && (snap.claims.top || snap.claims.claims)) || [];
        }
        const payload = await bridge.joinClaimPayers(claims.slice(0, 20));
        const text = payload && payload.text ? String(payload.text) : "No claim↔payer joins.";
        return {
          ok: !!(payload && payload.count),
          summary: text.slice(0, 2500) || "No claim↔payer joins.",
          count: payload && payload.count ? payload.count : 0,
        };
      },
    },
    build_appeal_packet: {
      label: "Build local denial/appeal packet (preflight + denial risk + payer)",
      run: async (ctx, args) => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "Appeal packet requires loopback server." };
        }
        const q = String((args && (args.query || args.claimId)) || "");
        let claimId = args.claimId || args.id || "";
        if (!claimId) {
          const idMatch = q.match(/\b(DS-[\w-]+|CLM[-\w]+|\d{4,})\b/i);
          if (idMatch) claimId = idMatch[1];
        }
        const data = await bridge.loopbackJson("/api/claims/appeal-packet", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            claimId,
            payer: args.payer || "",
            procedure: args.procedure || "",
            narrative: args.narrative || "",
            denialReason: args.denialReason || "",
            cdt: args.cdt || args.cdtCode || "",
            query: q,
          }),
        });
        const clinical =
          data && data.clinicalNotesAttached
            ? `\nClinical notes attached: ${(data.clinicalNotes || []).length} SoftDent note(s) — staff must verify.`
            : "";
        let pending = null;
        if (
          data &&
          data.ok &&
          data.claimId &&
          typeof HalConsent !== "undefined" &&
          typeof HalConsent.createPendingClaimPacket === "function"
        ) {
          pending = HalConsent.createPendingClaimPacket({
            claimId: data.claimId,
            narrative: data.narrative || "",
            payer: (data.claim && data.claim.payer) || args.payer || "",
            gaps: data.gaps || [],
            query: `Build claim packet zip for ${data.claimId} with consent`,
          });
        }
        const finish =
          data && data.finishLine && data.finishLine.zipNeedsConsent
            ? pending
              ? `\n\nFinish line: claim packet for ${data.claimId} is staged — say "I consent" to build the local zip (portal upload stays manual).`
              : "\n\nFinish line: narrative draft ready — staff consent required for claim packet zip (portal upload is manual)."
            : "";
        return {
          ok: Boolean(data && data.ok),
          summary: String((data && data.summary) || "Appeal packet unavailable.").slice(0, 3200) + clinical + finish,
          packet: data,
          narrative: data && data.narrative,
          clinicalNotesAttached: Boolean(data && data.clinicalNotesAttached),
          pendingConsent: pending,
        };
      },
    },
    list_posting_queue: {
      label: "List accounting posting queue (pending review)",
      run: async (ctx, args) => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "Posting queue requires loopback server." };
        }
        const status = (args && (args.status || args.filter)) || "pending_review";
        const limit = Number((args && args.limit) || 25) || 25;
        const qs = `?limit=${encodeURIComponent(String(limit))}&status=${encodeURIComponent(String(status))}`;
        const data = await bridge.loopbackJson(`/api/posting-queue${qs}`, { method: "GET" });
        const items = (data && data.items) || [];
        if (!items.length) {
          return { ok: true, summary: "Posting queue empty for this filter — nothing pending review.", count: 0, items: [] };
        }
        const lines = [`Posting queue (${status}): ${items.length}`, ""];
        items.slice(0, 12).forEach((item, idx) => {
          lines.push(
            `${idx + 1}. ${item.queue_id || item.queueId || item.id || "?"} · $${item.amount ?? "?"} · ${item.description || "journal"} · ${item.status || "?"}`,
          );
        });
        lines.push("", "Ask HAL: batch approve postings (consent-gated) — does not post live to QuickBooks.");
        return { ok: true, summary: lines.join("\n"), count: items.length, items, metrics: data && data.metrics };
      },
    },
    list_pending_era_matches: {
      label: "List ERA/EOB matches pending staff review",
      run: async () => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "ERA pending list requires loopback server." };
        }
        const data = await bridge.loopbackJson("/api/era/pending-matches?limit=25", { method: "GET" });
        const items = (data && data.items) || [];
        if (!items.length) {
          return { ok: true, summary: "No ERA/EOB matches pending review.", count: 0, items: [] };
        }
        const lines = [`ERA/EOB pending review: ${items.length}`, ""];
        items.slice(0, 10).forEach((item, idx) => {
          lines.push(
            `${idx + 1}. id ${item.id} · ${item.referenceId || "?"} → claim ${item.predictedClaimId || "?"} · ${item.status} · confidence ${item.confidenceBadge || item.confidence || "?"}` +
              (item.paidAmount != null ? ` · paid $${item.paidAmount}` : ""),
          );
        });
        lines.push("", "Ask HAL: confirm ERA match <id> to claim <ClaimId> — queues posting for review, does not post live.");
        return { ok: true, summary: lines.join("\n"), count: items.length, items };
      },
    },
    confirm_era_match: {
      label: "Confirm pending ERA/EOB match and queue posting for review",
      run: async (ctx, args) => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "ERA confirm requires loopback server." };
        }
        const q = String((args && (args.query || "")) || "");
        let matchId = args.matchId || args.id || args.eraLineId || "";
        let claimId = args.claimId || args.correctedClaimId || "";
        if (!matchId) {
          const m = q.match(/\b(?:match|era|eob)\s+([A-Za-z0-9-]{6,})\b/i) || q.match(/\bid\s+([A-Za-z0-9-]{6,})\b/i);
          if (m) matchId = m[1];
        }
        if (!claimId) {
          const c = q.match(/\b(?:claim|to)\s+(DS-[\w-]+|CLM[-\w]+|\d{4,})\b/i);
          if (c) claimId = c[1];
        }
        const data = await bridge.loopbackJson("/api/era/confirm-match", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            matchId,
            claimId,
            paidAmount: args.paidAmount,
            cdt: args.cdt || args.cdtCode || "",
            payer: args.payer || "",
            procedure: args.procedure || "",
            actor: "Staff",
          }),
        });
        return {
          ok: Boolean(data && data.ok),
          summary: String((data && data.summary) || data.error || "ERA confirm failed.").slice(0, 2500),
          result: data,
        };
      },
    },
    list_claims_aging_followup: {
      label: "List claims aging follow-up queue (60+ days)",
      run: async (ctx, args) => {
        const snap = await ctx.loadProgramSnapshot();
        let claims = (snap && snap.claims && (snap.claims.top || snap.claims.claims)) || [];
        if (!window.HalSkills || typeof HalSkills.buildClaimsAgingFollowUp !== "function") {
          return { ok: false, summary: "Claims aging tools unavailable." };
        }
        const bridge =
          typeof DesktopBridge !== "undefined"
            ? DesktopBridge
            : typeof window !== "undefined"
              ? window.DesktopBridge
              : null;
        if (bridge && typeof bridge.joinClaimPayers === "function" && claims.length) {
          try {
            const joined = await bridge.joinClaimPayers(claims.slice(0, 40));
            const enriched = (joined && joined.items) || [];
            if (enriched.length) {
              const byId = new Map(
                enriched.map((c) => [String((c && (c.id || c.claimId || c.ClaimId)) || "").toLowerCase(), c]),
              );
              claims = claims.map((c) => {
                const key = String((c && (c.id || c.claimId || c.ClaimId)) || "").toLowerCase();
                const hit = byId.get(key);
                if (hit && hit.payerMatch) return Object.assign({}, c, { payerMatch: hit.payerMatch });
                return c;
              });
            }
          } catch {
            /* optional join */
          }
        }
        const minDays = Number(args.minDays || args.min_days || 60) || 60;
        const resp = HalSkills.buildClaimsAgingFollowUp(claims, { minDays });
        const top = (resp.items || [])[0];
        let dialHint = "";
        if (top && !top.genericPayer) {
          dialHint =
            `\n\nNext: schedule call task claims_aging for ${top.claimRef}` +
            (top.payerPhone ? ` / dial ${top.payerPhone}` : "") +
            " — or build appeal packet if denied.";
        }
        return {
          ok: true,
          summary: HalSkills.formatClaimsAgingFollowUp(resp).slice(0, 3500) + dialHint,
          aging: resp,
        };
      },
    },
    draft_insurance_narrative: {
      label: "Draft insurance narrative for claim",
      run: async (ctx, args) => {
        const snap = await ctx.loadProgramSnapshot();
        if (!window.HalSkills || typeof HalSkills.buildDraftInsuranceNarrative !== "function") {
          return { ok: false, summary: "Narrative drafting unavailable." };
        }
        const q = String((args && args.query) || "");
        let params = {};
        const jsonMatch = q.match(/\{[\s\S]*\}/);
        if (jsonMatch) {
          try {
            params = JSON.parse(jsonMatch[0]);
          } catch {
            params = {};
          }
        }
        if (!params.claimId) {
          const idMatch = q.match(/\b(CLM[-\w]+|\d{4,})\b/i);
          if (idMatch) params.claimId = idMatch[1];
        }
        if (!params.focus) {
          const focusMatch = q.match(/\bfocus[:\s]+([A-Za-z][\w\s-]+)/i);
          if (focusMatch) params.focus = focusMatch[1].trim();
        }
        if (!params.tone) {
          const toneMatch = q.match(/\btone[:\s]+([A-Za-z][\w-]+)/i);
          if (toneMatch) params.tone = toneMatch[1].trim();
        }
        if (/\bappeal\b|\bdenial\b/i.test(q) && !params.focus) params.focus = "Denial Appeal";
        // Join payer themes when claim has a named carrier
        try {
          const claim = HalSkills.resolveClaimById
            ? HalSkills.resolveClaimById(snap, params.claimId)
            : null;
          const payerLabel = (claim && (claim.payer || claim.Payer || claim.tag)) || args.payer || "";
          const bridge =
            typeof DesktopBridge !== "undefined"
              ? DesktopBridge
              : typeof window !== "undefined"
                ? window.DesktopBridge
                : null;
          if (payerLabel && bridge && typeof bridge.joinClaimPayers === "function") {
            const joined = await bridge.joinClaimPayers([{ id: params.claimId || "draft", payer: payerLabel }]);
            const row = ((joined && joined.items) || [])[0];
            if (row && row.payerMatch) {
              params.payerMatch = row.payerMatch;
              if (claim) claim.payerMatch = row.payerMatch;
            }
          }
        } catch {
          /* optional */
        }
        const result = HalSkills.buildDraftInsuranceNarrative(snap, params);
        return {
          ok: result.ok !== false,
          summary: HalSkills.formatDraftInsuranceNarrativeResult(result).slice(0, 3500),
          draft: result,
          citationWidgets: result.citationWidgets || ["narrativeWorkflow", "claimsPipeline"],
        };
      },
    },
    softdent_extract_status: {
      label: "SoftDent ODBC extract status",
      run: async (ctx) => {
        let status = null;
        if (typeof Services !== "undefined" && typeof Services.fetchSoftdentOdbcStatus === "function") {
          try {
            status = await Services.fetchSoftdentOdbcStatus();
          } catch {
            status = null;
          }
        }
        if (!status && window.HalSkills && typeof HalSkills.buildSoftdentExtractStatus === "function") {
          status = HalSkills.buildSoftdentExtractStatus(await ctx.loadProgramSnapshot());
        }
        if (!window.HalSkills || typeof HalSkills.formatSoftdentExtractStatus !== "function") {
          return { ok: false, summary: "SoftDent extract diagnostics unavailable." };
        }
        const resp = status || HalSkills.buildSoftdentExtractStatus(null);
        return { ok: true, summary: HalSkills.formatSoftdentExtractStatus(resp).slice(0, 2800), status: resp };
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
    read_shift_context: {
      label: "Read HAL employee shift and tier",
      run: async () => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        const state =
          (typeof window !== "undefined" && window.nr2ShiftState) ||
          (bridge && typeof bridge.pollShiftState === "function" ? await bridge.pollShiftState() : null);
        if (!state) return { ok: false, summary: "Shift context unavailable." };
        const lines = [
          `Tier ${state.tier} (${state.levelName || "Unknown"})`,
          state.active ? `On shift since ${state.clockedInAt || "unknown"}` : "Off shift",
          `Employee: ${state.employeeId || "HAL"}`,
        ];
        return { ok: true, summary: lines.join("\n"), shift: state };
      },
    },
    read_model_lane_history: {
      label: "Read recent HAL model lane routing history",
      run: async () => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "Lane history requires loopback server." };
        }
        const data = await bridge.loopbackJson("/api/hal/lane-history?limit=10");
        const items = (data && data.items) || [];
        if (!items.length) return { ok: true, summary: "No lane history recorded yet." };
        const lines = items.map(
          (it, idx) => `${idx + 1}. ${it.lane || "?"} · ${it.intent || ""} · ${String(it.queryPreview || "").slice(0, 80)}`,
        );
        return { ok: true, summary: lines.join("\n"), items };
      },
    },
    read_clinical_summary: {
      label: "Read clinical summary context (read-only)",
      run: async (ctx, args) => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.fetchClinicalContext !== "function") {
          return { ok: false, summary: "Clinical context requires loopback server." };
        }
        let patientId = String(args.patientId || args.query || "").trim();
        if (!patientId && getOMPatientContext()) patientId = getOMPatientContext();
        const data = await bridge.fetchClinicalContext({ limit: 5, patientId: patientId || undefined });
        const items = (data && data.items) || [];
        if (!items.length) return { ok: true, summary: "No clinical summaries on file." };
        const lines = items.map((it, idx) => `${idx + 1}. ${String(it.summary || it.text || "").slice(0, 240)}`);
        return { ok: true, summary: lines.join("\n\n"), readOnly: true };
      },
    },
    summarize_patient_dossier: {
      label: "Summarize patient dossier (data + tx + notes + claims)",
      run: async (ctx, args) => {
        if (cloudHalBlockedForPatientTools()) {
          return { ok: false, summary: "Patient dossier is local-only — cloud HAL blocked for PHI." };
        }
        const bridge =
          typeof DesktopBridge !== "undefined"
            ? DesktopBridge
            : typeof window !== "undefined" && window.DesktopBridge
              ? window.DesktopBridge
              : null;
        if (!bridge || typeof bridge.fetchPatientDossier !== "function") {
          return { ok: false, summary: "Patient dossier requires NR2 loopback server." };
        }
        if (!(await hasPatientDossierCapability())) {
          return {
            ok: false,
            summary: "You do not have permission to request patient dossiers. Contact office manager.",
          };
        }
        let patientId = String(args.patientId || args.patient_id || "").trim();
        if (!patientId) {
          const q = String(args.query || "").trim();
          const m = q.match(
            /\b(?:patient|dossier|summarize)\s+([A-Za-z0-9_-]{3,64})\b/i
          );
          patientId = m ? m[1] : "";
        }
        if (!patientId && getOMPatientContext()) patientId = getOMPatientContext();
        if (!patientId) {
          return {
            ok: false,
            summary: "Provide a patient id (or select a patient on the Mon–Thu schedule).",
          };
        }
        const data = await bridge.fetchPatientDossier(patientId, {
          summarize: true,
          memberId: args.memberId || args.member_id,
          payerId: args.payerId || args.payer_id,
          payerName: args.payerName || args.payer_name,
          providerNpi: args.providerNpi || args.provider_npi,
          fetchEligibility: args.fetchEligibility || args.fetch_eligibility,
        });
        if (!data || data.ok === false) {
          return {
            ok: false,
            summary: (data && (data.error || data.summary)) || "Dossier unavailable.",
          };
        }
        const text =
          (data.summary && String(data.summary)) ||
          (data.summaryMarkdown && String(data.summaryMarkdown)) ||
          "Dossier loaded but summary empty.";
        // Honesty guard
        if (/\$0\.00|\b\$0\b/.test(text) && data.dossier) {
          const md = data.summaryMarkdown || text;
          return { ok: true, summary: String(md).slice(0, 4000), patientId, source: "honesty_guard" };
        }
        return {
          ok: true,
          summary: text.slice(0, 4000),
          patientId,
          source: data.summarySource || "dossier",
          dossier: data.dossier || null,
        };
      },
    },
    read_patient_summary: {
      label: "Read patient demographics/insurance mini-summary (OM context)",
      run: async (ctx, args) => {
        if (cloudHalBlockedForPatientTools()) {
          return { ok: false, summary: "Patient tools are local-only." };
        }
        const bridge =
          typeof DesktopBridge !== "undefined"
            ? DesktopBridge
            : typeof window !== "undefined" && window.DesktopBridge
              ? window.DesktopBridge
              : null;
        if (!bridge || typeof bridge.fetchPatientDossierMini !== "function") {
          return { ok: false, summary: "Patient summary requires NR2 loopback server." };
        }
        let patientId = String(args.patientId || args.patient_id || "").trim();
        if (!patientId && getOMPatientContext()) patientId = getOMPatientContext();
        if (!patientId) {
          return { ok: false, summary: "No patient selected in OM — click a hash on Mon–Thu schedule." };
        }
        const data = await bridge.fetchPatientDossierMini(patientId);
        if (!data || !data.ok) {
          return { ok: false, summary: (data && data.error) || "Patient not found." };
        }
        const lines = [
          `Patient ${data.patientHash || "——"} (${data.initials || "P—"})`,
          `Carrier: ${data.primaryCarrier || "unknown"}`,
          `Open claims: ${data.openClaims != null ? data.openClaims : "unknown"}`,
          `Last visit: ${data.lastVisit || "unknown"}`,
          `Account balance: ${data.accountBalance || "unavailable"} (empty ≠ $0)`,
          `Clinical notes: ${data.hasClinicalNotes ? "yes" : "none on file"}`,
        ];
        if (data.schemaGap) lines.push(`Schema note: ${data.schemaGap}`);
        return { ok: true, summary: lines.join("\n"), patientId, mini: data };
      },
    },
    clear_patient_context: {
      label: "Clear OM patient context for HAL",
      run: async () => {
        setOMPatientContext(null);
        return { ok: true, summary: "Patient context cleared.", status: "cleared" };
      },
    },
    set_patient_context: {
      label: "Set OM patient context for HAL (staff-gated)",
      run: async (ctx, args) => {
        const patientId = String(args.patientId || args.patient_id || args.query || "").trim();
        if (!patientId) return { ok: false, summary: "Provide patientId." };
        setOMPatientContext(patientId);
        return {
          ok: true,
          summary: `HAL patient context set to ${patientId.length === 4 ? patientId.toUpperCase() : "selected patient"} (15 min TTL).`,
          patientId,
        };
      },
    },
    build_collections_queue: {
      label: "Generate A/R collections follow-up queue",
      run: async () => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "Collections queue requires loopback server." };
        }
        const data = await bridge.loopbackJson("/api/collections/generate-queue", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ limit: 25 }),
        });
        const items = (data && data.items) || [];
        if (!items.length) {
          return { ok: true, summary: data.summary || "No balances flagged for collections.", count: 0 };
        }
        const lines = [
          data.summary || `${items.length} account(s) queued:`,
          "",
          ...items.map((it) => {
            let line =
              `- [${it.priority}] ${it.patientName}: $${Number(it.balance || 0).toFixed(2)}` +
              (it.bucket ? ` · ${it.bucket}` : "") +
              (it.phone ? ` · ${it.phone}` : "");
            if (it.callScript) line += `\n  Script: ${String(it.callScript).slice(0, 220)}`;
            return line;
          }),
          "",
          "Staff owns patient contact. Ask HAL to schedule a call task or click-to-dial with consent.",
        ];
        return { ok: true, summary: lines.join("\n"), count: items.length, items, queue: data };
      },
    },
    generate_collection_letter: {
      label: "Draft patient collection letter (approval queue)",
      run: async (ctx, args) => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "Collection letter requires loopback server." };
        }
        const data = await bridge.loopbackJson("/api/collections/letter", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            patientName: args.patientName || args.patient_name,
            balance: args.balance,
            patientId: args.patientId,
          }),
        });
        return {
          ok: true,
          summary: data.requiresApproval
            ? `Letter drafted (requires email consent approval):\n${data.letter}`
            : `Letter ready:\n${data.letter}`,
        };
      },
    },
    schedule_call_task: {
      label: "Schedule A/R collection call with script",
      run: async (ctx, args) => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "Call scheduling requires loopback server." };
        }
        const data = await bridge.loopbackJson("/api/collections/schedule-call", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            patientName: args.patientName || args.patient_name,
            balance: args.balance,
            priority: args.priority || "high",
            scenario: args.scenario || args.scriptScenario || "",
            phone: args.phone || args.phoneNumber || "",
            claimId: args.claimId || "",
            payer: args.payer || "",
            patientId: args.patientId || "",
            notes: args.notes || "",
          }),
        });
        return {
          ok: true,
          summary: data.summary || `Call scheduled.\nScript: ${data.callScript || ""}`,
          queueId: data.id,
          scenario: data.scenario,
          phone: data.phone,
        };
      },
    },
    heal_import_pipeline: {
      label: "Predictive import heal (retry sync)",
      run: async () => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "Import heal requires loopback server." };
        }
        const data = await bridge.loopbackJson("/api/import/heal", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ force: false }),
        });
        const hints = (data.hints || []).map((h) => `- ${h}`).join("\n");
        return { ok: true, summary: `${data.message || "Heal complete."}${hints ? `\n${hints}` : ""}` };
      },
    },
    parse_era_835: {
      label: "Parse ERA/835 and fuzzy-match claims",
      run: async (ctx, args) => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "ERA parse requires loopback server." };
        }
        const data = await bridge.loopbackJson("/api/era/parse", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: args.content || args.era835 || args.query || "" }),
        });
        const count = (data.matches || []).length;
        return { ok: true, summary: `ERA parsed: ${count} segment(s) matched/reviewed.` };
      },
    },
    draft_deposit_reconciliation: {
      label: "Draft bank deposit reconciliation",
      run: async (ctx, args) => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "Deposit recon requires loopback server." };
        }
        const body = { depositDate: args.depositDate || args.period || "" };
        if (args.bankAmount != null || args.bank_amount != null) {
          body.bankAmount = Number(args.bankAmount || args.bank_amount);
        }
        if (args.ledgerAmount != null || args.ledger_amount != null) {
          body.ledgerAmount = Number(args.ledgerAmount || args.ledger_amount);
        }
        // Omit zero placeholders so the server can seed from collection↔deposit analytics.
        const data = await bridge.loopbackJson("/api/deposits/draft-recon", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        const draft = (data && data.draft) || {};
        const actions = (draft.suggestedActions || []).map((a) => `- ${a}`).join("\n");
        const seeded = data.seededFromAnalytics || draft.seededFromAnalytics
          ? " Seeded from SoftDent collections vs QB deposits."
          : "";
        const pct =
          draft.variancePct != null && Number.isFinite(Number(draft.variancePct))
            ? ` (${Number(draft.variancePct) >= 0 ? "+" : ""}${draft.variancePct}%)`
            : "";
        return {
          ok: true,
          summary: `Variance $${data.variance}${pct}.${seeded} ${actions || "Balanced."}`.trim(),
          draft,
        };
      },
    },
    stage_claim_preflight: {
      label: "Stage claim submission preflight checklist",
      run: async (ctx, args) => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "Claim preflight requires loopback server." };
        }
        const data = await bridge.loopbackJson("/api/claims/preflight", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            claimId: args.claimId || args.query || "",
            patientId: args.patientId || "",
            payer: args.payer || args.Payer || "",
            procedure: args.procedure || args.Procedure || "",
            cdt: args.cdt || args.cdtCode || "",
            narrative: args.narrative || args.clinicalNote || "",
            clinicalNote: args.clinicalNote || "",
            narrativePresent: args.narrativePresent,
            attachmentsReady: args.attachmentsReady,
            feeScheduleVerified: args.feeScheduleVerified,
            insuranceVerified: args.insuranceVerified,
            clinicalSummaryLinked: args.clinicalSummaryLinked,
          }),
        });
        const checklist = (data && data.checklist) || {};
        const lines = Object.entries(checklist).map(([k, v]) => `- ${k}: ${v ? "yes" : "no"}`);
        const gaps = Array.isArray(data.gaps) && data.gaps.length ? `\nGaps:\n${data.gaps.map((g) => `- ${g}`).join("\n")}` : "";
        const elig = data && data.eligibilityHit;
        const eligLine = elig
          ? `\nEligibility cache: ${elig.payerName || "?"}` +
            (elig.deductibleRemaining != null ? ` · ded rem $${elig.deductibleRemaining}` : "") +
            (elig.annualMaxRemaining != null ? ` · max rem $${elig.annualMaxRemaining}` : "")
          : "";
        return {
          ok: true,
          summary: `Status ${data.status}.${gaps}${eligLine}\n${lines.join("\n")}`,
          checklist,
          gaps: data.gaps || [],
          feeDetail: data.feeDetail || null,
          eligibilityHit: elig || null,
        };
      },
    },
    match_eob_era: {
      label: "Match EOB or ERA payment to claim",
      run: async (ctx, args) => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "EOB/ERA match requires loopback server." };
        }
        const data = await bridge.loopbackJson("/api/eob/match", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            referenceId: args.referenceId || args.query || "",
            claimId: args.claimId || "",
            sourceType: args.sourceType || "eob",
            paidAmount: args.paidAmount,
            cdt: args.cdt || args.cdtCode || "",
            payer: args.payer || "",
            procedure: args.procedure || "",
            billedAmount: args.billedAmount || args.billed,
            remark: args.remark || args.carc || "",
          }),
        });
        const scrub =
          data.feeScrub && data.feeScrub.ok
            ? ` Fee scrub: ${data.feeScrub.classification} (paid $${data.feeScrub.paidAmount} vs allowed $${data.feeScrub.allowedAmount}).`
            : "";
        return {
          ok: true,
          summary:
            (data.summary ||
              `Match ${data.status}: ref ${(data.detail && data.detail.referenceId) || ""} → claim ${(data.detail && data.detail.claimId) || ""}`) +
            scrub,
          detail: data.detail,
          feeScrub: data.feeScrub || null,
        };
      },
    },
    batch_approve_postings: {
      label: "Batch approve posting queue entries (consent-gated)",
      run: async (ctx, args) => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "Batch approve requires loopback server." };
        }
        const data = await bridge.loopbackJson("/api/posting/batch-approve", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ queueIds: args.queueIds || [], reviewerActor: "HAL" }),
        });
        if (data.error === "consent_denied") {
          return { ok: false, summary: `Consent denied at tier ${(data.consent && data.consent.tier) || "?"}.` };
        }
        return { ok: true, summary: "Batch approval completed.", result: data };
      },
    },
    generate_month_end_tasks: {
      label: "Generate month-end close task list",
      run: async (ctx, args) => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "Month-end tasks require loopback server." };
        }
        const data = await bridge.loopbackJson("/api/close/generate-tasks", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ period: (args && args.period) || "" }),
        });
        const tasks = (data && data.tasks) || [];
        const lines = [
          data.summary || `Period ${data.period}:`,
          "",
          ...tasks.map(
            (t) =>
              `- [${t.priority}] ${t.title}` +
              (t.detail ? ` — ${String(t.detail).slice(0, 120)}` : ""),
          ),
        ];
        if (data.analyticsGrounded) {
          lines.push("", "Tasks grounded in live SoftDent/QB analytics where available.");
        }
        return { ok: true, summary: lines.join("\n"), tasks, period: data.period };
      },
    },
    scrub_fee_vs_paid: {
      label: "Scrub fee-schedule allowed vs EOB/ERA paid (CO-45 vs underpay)",
      run: async (ctx, args) => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "Fee vs paid scrub requires loopback server." };
        }
        const q = String((args && (args.query || args.cdt || "")) || "");
        const cdtMatch = q.match(/\b(D\d{4})\b/i);
        const paidRaw = args.paidAmount != null ? args.paidAmount : args.paid;
        const data = await bridge.loopbackJson("/api/fee/scrub-paid", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            cdt: args.cdt || args.cdtCode || (cdtMatch ? cdtMatch[1] : ""),
            payer: args.payer || args.schedule || "",
            paidAmount: paidRaw,
            billedAmount: args.billedAmount || args.billed,
            remark: args.remark || args.remarkCode || args.carc || "",
            procedure: args.procedure || "",
            query: q,
          }),
        });
        return {
          ok: Boolean(data && data.ok),
          summary: String((data && data.summary) || data.error || "Fee vs paid scrub unavailable.").slice(0, 2500),
          scrub: data,
        };
      },
    },
    record_era_match_feedback: {
      label: "Record ERA match correction for ML training",
      run: async (ctx, args) => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "ERA feedback requires loopback server." };
        }
        await bridge.loopbackJson("/api/era/match-feedback", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            eraLineId: args.eraLineId || args.era_transaction_id,
            predictedClaimId: args.predictedClaimId || args.claim_id,
            correctedClaimId: args.correctedClaimId || args.correction_claim_id,
            approved: args.is_correct !== false,
            confidence: args.confidence,
          }),
        });
        return { ok: true, summary: "ERA match feedback recorded for training." };
      },
    },
    clock_out_shift: {
      label: "Clock out and generate shift handoff report",
      run: async (ctx, args, options = {}) => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "Clock-out requires loopback server." };
        }
        const data = await bridge.loopbackJson("/api/employee/clock-out", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
        });

        // Generate spoken excerpt (1-2 sentences) — Moonshot voice+report Phase 1
        const openCount = data.openItemCount || 0;
        const spoken = `Handoff ${data.handoffId || "ready"}: ${openCount} open item${
          openCount !== 1 ? "s" : ""
        }. Shift closed.`;

        if (options.speak !== false && typeof HalVoice !== "undefined" && HalVoice.speakHalBriefing) {
          HalVoice.speakHalBriefing(spoken, { interrupt: true });
        }

        return {
          ok: true,
          summary: data.reportMarkdown || `Handoff ${data.handoffId}: ${openCount} open item(s).`,
          spokenExcerpt: spoken,
          handoff: data,
        };
      },
    },
    get_last_handoff_report: {
      label: "Retrieve prior shift handoff report",
      run: async (ctx, args, options = {}) => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "Handoff retrieval requires loopback server." };
        }
        const id = args.shiftId || args.handoffId;
        if (!id) return { ok: false, summary: "handoffId required." };
        const data = await bridge.loopbackJson(`/api/shift/handoff/${encodeURIComponent(String(id))}`);
        const md = (data.handoff && data.handoff.reportMarkdown) || "";
        const openCount =
          (data.handoff && (data.handoff.openItemCount || data.handoff.open_item_count)) || 0;
        const spoken = `Handoff ${id}: ${openCount} open item${openCount !== 1 ? "s" : ""}.`;
        if (options.speak !== false && typeof HalVoice !== "undefined" && HalVoice.speakHalBriefing) {
          HalVoice.speakHalBriefing(spoken, { interrupt: true });
        }
        return { ok: true, summary: md || "Empty handoff.", spokenExcerpt: spoken, handoff: data.handoff };
      },
    },
    readiness_diagnostics: {
      label: "Run HAL readiness / system health diagnostics",
      run: async (ctx, args, options = {}) => {
        let report = null;
        if (ctx && typeof ctx.runReadinessDiagnostics === "function") {
          report = ctx.runReadinessDiagnostics();
        } else if (typeof HalCore !== "undefined" && typeof HalCore.runReadinessDiagnostics === "function") {
          report = HalCore.runReadinessDiagnostics();
        }
        if (!report) {
          return { ok: false, summary: "Readiness diagnostics unavailable." };
        }
        const summary =
          typeof HalCore !== "undefined" && HalCore.formatReadinessSummary
            ? HalCore.formatReadinessSummary(report)
            : String(report.summary || report.overall || "Readiness complete.");
        const overall = report.overall || "unknown";
        const n = (report.results && report.results.length) || 0;
        const spoken = `Readiness ${overall} across ${n} check${n !== 1 ? "s" : ""}.`;
        if (options.speak !== false && typeof HalVoice !== "undefined" && HalVoice.speakHalBriefing) {
          HalVoice.speakHalBriefing(spoken, { interrupt: true });
        }
        return { ok: true, summary: summary.slice(0, 3000), spokenExcerpt: spoken, report };
      },
    },
    daily_ops_briefing: {
      label: "Generate daily operations briefing",
      run: async (ctx, args, options = {}) => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "Bridge required." };
        }

        // Parallel READ-ONLY queries (SoftDent + employee status) — Moonshot Phase 4
        const [schedule, claims, staff] = await Promise.all([
          bridge.loopbackJson("/api/softdent/today-schedule").catch(() => ({})),
          bridge.loopbackJson("/api/claims/aging-summary").catch(() => ({})),
          bridge.loopbackJson("/api/employee/on-duty").catch(() => ({})),
        ]);

        const patientCount = schedule && schedule.count != null ? Number(schedule.count) : 0;
        const agingCount = claims && claims.over30 != null ? Number(claims.over30) : 0;
        const staffNames = (staff && Array.isArray(staff.names) ? staff.names : []).filter(Boolean);
        const staffList = staffNames.join(", ");

        const markdown = `## Daily Ops Briefing - ${new Date().toLocaleDateString()}
- **Schedule**: ${patientCount} patients
- **Claims >30d**: ${agingCount}
- **Staff**: ${staffList || "None logged"}
`;
        const spoken = `Today: ${patientCount} patients scheduled. ${agingCount} claims over 30 days. ${staffNames.length} staff on duty.`;

        if (options.speak !== false && typeof HalVoice !== "undefined" && HalVoice.speakHalBriefing) {
          HalVoice.speakHalBriefing(spoken, { interrupt: true });
        }

        return { ok: true, summary: markdown, spokenExcerpt: spoken };
      },
    },
    click_to_dial: {
      label: "Initiate patient phone call with script",
      run: async (ctx, args) => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "VoIP dial requires loopback server." };
        }
        const data = await bridge.loopbackJson("/api/voip/dial", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            patientId: args.patientId || args.patient_id,
            phoneNumber: args.phoneNumber || args.phone_number || args.phone,
            scriptScenario: args.scriptScenario || args.scenario || args.context || "collections",
            patientName: args.patientName,
            balance: args.balance,
            queueId: args.queueId || args.queue_id || "",
            claimId: args.claimId || "",
          }),
        });
        if (data.telUri && typeof window !== "undefined") {
          try {
            window.location.href = data.telUri;
          } catch {
            /* softphone may handle via bridge */
          }
        }
        return {
          ok: Boolean(data && data.ok !== false),
          summary:
            `Call ${data.callId || "?"} initiated` +
            (data.queueId ? ` · queue ${data.queueId}` : "") +
            `.\nScript:\n${data.script || ""}` +
            `\nAfter the call: log outcome (promised / no_answer / closed) to update collections queue.`,
          callId: data.callId,
          queueId: data.queueId || args.queueId || "",
        };
      },
    },
    log_call_outcome: {
      label: "Log VoIP call outcome (updates collections queue)",
      run: async (ctx, args) => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "Call logging requires loopback server." };
        }
        const data = await bridge.loopbackJson("/api/voip/log", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            callId: args.callId || args.call_reference,
            outcome: args.outcome || "unknown",
            notes: args.notes || "",
            durationSec: args.duration_sec || args.durationSec,
            queueId: args.queueId || args.queue_id || "",
          }),
        });
        const q = data && data.queueUpdate && data.queueUpdate.ok
          ? ` Collections queue → ${data.queueStatus || data.queueUpdate.status}.`
          : "";
        return {
          ok: Boolean(data && data.ok !== false),
          summary: `Call ${args.callId || data.callId || ""} logged as ${args.outcome || data.outcome || "unknown"}.${q}`,
          queueUpdate: data && data.queueUpdate,
        };
      },
    },
    send_billing_sms: {
      label: "Send billing reminder SMS",
      run: async (ctx, args) => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "SMS requires loopback server." };
        }
        const data = await bridge.loopbackJson("/api/sms/send", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            patientId: args.patientId || args.patient_id,
            phoneNumber: args.phoneNumber || args.phone,
            templateKey: args.templateKey || args.template || "reminder",
            variables: args.variables,
          }),
        });
        return { ok: data.ok !== false, summary: `SMS ${data.messageId || ""} status: ${data.status || "queued"}.` };
      },
    },
    get_sms_thread: {
      label: "Read SMS conversation thread",
      run: async (ctx, args) => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "SMS thread requires loopback server." };
        }
        const pid = args.patientId || args.patient_id;
        const data = await bridge.loopbackJson(`/api/sms/thread/${encodeURIComponent(String(pid || ""))}`);
        const lines = (data.thread || []).map((m) => `[${m.direction}] ${m.body}`);
        return { ok: true, summary: lines.join("\n") || "No SMS history." };
      },
    },
    sync_qb_customers: {
      label: "Sync QuickBooks read-only status",
      run: async () => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "QB sync requires loopback server." };
        }
        const data = await bridge.loopbackJson("/api/qb/sync", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
        return { ok: true, summary: JSON.stringify(data.status || data).slice(0, 1500) };
      },
    },
    push_journal_entry_to_qb: {
      label: "Post journal entry to QuickBooks (consent-gated)",
      run: async (ctx, args) => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "QB post requires loopback server." };
        }
        const data = await bridge.loopbackJson("/api/qb/push", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ entries: args.entries, memo: args.memo, amount: args.amount }),
        });
        if (data.error === "consent_denied") return { ok: false, summary: "QB post consent denied at current tier." };
        return { ok: true, summary: "Journal entry submitted to QB connector.", result: data };
      },
    },
    get_qb_reconciliation_status: {
      label: "Check QB vs ledger reconciliation",
      run: async () => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "QB reconciliation requires loopback server." };
        }
        const data = await bridge.loopbackJson("/api/qb/reconciliation");
        return { ok: true, summary: JSON.stringify(data).slice(0, 1200) };
      },
    },
    classify_incoming_document: {
      label: "Classify scanned mail/document type",
      run: async (ctx, args) => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "Document classify requires loopback server." };
        }
        const data = await bridge.loopbackJson("/api/documents/classify", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: args.text || args.content, path: args.path || args.document_id }),
        });
        return {
          ok: true,
          summary: `${data.category} (${Math.round((data.confidence || 0) * 100)}%) → route ${data.suggestedRoute || "human_inbox"}`,
          classification: data,
        };
      },
    },
    acknowledge_alert: {
      label: "Acknowledge proactive HAL alert",
      run: async (ctx, args) => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "Alerts require loopback server." };
        }
        await bridge.loopbackJson(`/api/alerts/${encodeURIComponent(String(args.alertId || args.alert_id || ""))}/ack`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: "{}",
        });
        return { ok: true, summary: "Alert acknowledged." };
      },
    },
    run_morning_routine: {
      label: "Trigger autonomous morning routine (admin)",
      run: async (ctx, args) => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "Scheduler requires loopback server." };
        }
        const data = await bridge.loopbackJson("/api/scheduler/morning-run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ force: Boolean(args && args.force) }),
        });
        if (data.skipped) return { ok: true, summary: `Morning routine skipped: ${data.reason}.` };
        return { ok: true, summary: `Morning routine ${data.runId}: ${(data.actions || []).length} action(s).` };
      },
    },
    list_autonomous_work: {
      label: "List HAL autonomous work ledger (local staged work)",
      run: async (ctx, args) => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "Autonomous work list requires loopback server." };
        }
        const openOnly = args && args.openOnly === false ? "0" : "1";
        const limit = Number((args && args.limit) || 40) || 40;
        const kind = (args && args.kind) || "";
        const qs =
          `?openOnly=${encodeURIComponent(openOnly)}&limit=${encodeURIComponent(String(limit))}` +
          (kind ? `&kind=${encodeURIComponent(String(kind))}` : "");
        const data = await bridge.loopbackJson(`/api/scheduler/work${qs}`, { method: "GET" });
        const items = (data && data.items) || [];
        if (!items.length) {
          return { ok: true, summary: "No open autonomous work — morning tick may not have run yet.", count: 0, items: [] };
        }
        const lines = [`HAL autonomous work (open): ${items.length}`, ""];
        items.slice(0, 15).forEach((row, idx) => {
          lines.push(
            `${idx + 1}. [${row.kind}] ${row.title}` +
              (row.priority && row.priority !== "normal" ? ` · ${row.priority}` : ""),
          );
          if (row.detail) lines.push(`   ${String(row.detail).slice(0, 160)}`);
        });
        lines.push("", "Local only — dial, zip, email, and live post stay staff-gated.");
        return { ok: true, summary: lines.join("\n"), count: items.length, items };
      },
    },
    undo_scheduler_run: {
      label: "Undo autonomous morning run within 4-hour window",
      run: async (ctx, args) => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "Scheduler undo requires loopback server." };
        }
        const runId = String(args.runId || args.run_id || "").trim();
        if (!runId) return { ok: false, summary: "runId required for undo." };
        const data = await bridge.loopbackJson("/api/scheduler/undo", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ runId }),
        });
        if (!data.ok) return { ok: false, summary: data.detail || data.error || "Undo failed.", result: data };
        return { ok: true, summary: `Undid autonomous run ${runId}.`, result: data };
      },
    },
    predict_claim_denial_risk: {
      label: "Predict pre-submit claim denial risk (local rules stub)",
      run: async (ctx, args) => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "Denial predict requires loopback server." };
        }
        const codes = args.cdtCodes || args.cdt_codes || args.codes || [];
        const claim = args.claim && typeof args.claim === "object" ? args.claim : null;
        const data = await bridge.loopbackJson("/api/era/denial-predict", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            cdtCodes: Array.isArray(codes) ? codes : String(codes || "").split(/[\s,]+/).filter(Boolean),
            payerId: args.payerId || args.payer_id || args.payer || "",
            hasNarrative: args.hasNarrative !== false && args.hasNarrative !== "false",
            priorDenials: Number(args.priorDenials || args.prior_denials || 0),
            procedure: args.procedure || "",
            claimStatus: args.status || args.claimStatus || "",
            denialReason: args.denialReason || "",
            claim: claim || {
              id: args.claimId || args.id || "",
              payer: args.payer || args.Payer || "",
              procedure: args.procedure || "",
              narrative: args.narrative || args.clinicalNote || "",
              status: args.status || "",
              cdt: args.cdt || args.cdtCode || "",
            },
          }),
        });
        const pct = Math.round(Number(data.riskScore || 0) * 100);
        const flags = Array.isArray(data.flags) && data.flags.length ? ` Flags: ${data.flags.join(", ")}.` : "";
        return {
          ok: Boolean(data.ok),
          summary: `Denial risk ${pct}%${data.highRisk ? " — review before submit" : ""}.${data.genericPayer ? " Generic payer." : ""}${flags}`,
          prediction: data,
        };
      },
    },
    pull_qb_payments: {
      label: "Pull QuickBooks payments read-only for reconciliation",
      run: async () => {
        const bridge = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
        if (!bridge || typeof bridge.loopbackJson !== "function") {
          return { ok: false, summary: "QB pull requires loopback server." };
        }
        const data = await bridge.loopbackJson("/api/qb/pull", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: "{}",
        });
        return {
          ok: Boolean(data.ok),
          summary: `QB pull (${data.mode || "unknown"}): ${data.paymentCount ?? (data.payments || []).length} payment(s).`,
          result: data,
        };
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
          return { ok: false, summary: "Web research requires the NR2 server." };
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
          return { ok: false, summary: "Learning requires the NR2 server." };
        }
        let text = String(args.text || args.query || "").trim();
        if (!text) {
          const raw = String(args.query || ctx.lastQuery || "");
          const m = raw.match(/(?:remember|save|learn|note)\s+(?:this|that)\s*:?\s*(.+)/i);
          if (m && m[1]) text = m[1].trim();
        }
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
    explain_consent: {
      label: "Explain staff consent policy",
      run: async (ctx) => {
        const cfg = HalCore.consentPolicy(ctx.halData);
        return {
          ok: true,
          summary: `${cfg.summary}\nCategories: ${(cfg.categories || []).join(", ")}.`,
        };
      },
    },
    explain_firewall: {
      label: "Explain staff consent policy (legacy alias)",
      run: async (ctx) => {
        const cfg = HalCore.consentPolicy(ctx.halData);
        return { ok: true, summary: cfg.summary };
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
    send_office_message: {
      label: "Send desktop popup to office room or Everyone",
      run: async (_ctx, args) => {
        const text = String((args && (args.text || args.message)) || "").trim();
        const rawTargets = args && (args.targets || args.stations || args.target);
        let targets = ["all"];
        if (Array.isArray(rawTargets) && rawTargets.length) {
          targets = rawTargets.map((t) => String(t).trim()).filter(Boolean);
        } else if (rawTargets) {
          targets = String(rawTargets)
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean);
        }
        if (!text) return { ok: false, summary: "Message text is required." };
        const send =
          typeof globalThis.sendHalOfficePopupMessage === "function"
            ? globalThis.sendHalOfficePopupMessage
            : typeof HalHubClient !== "undefined" && HalHubClient.sendHalPopupMessage
              ? (body, t) => HalHubClient.sendHalPopupMessage(body, t)
              : null;
        if (!send) return { ok: false, summary: "Office popup messaging requires the NR2 desktop HAL hub." };
        await send(text, targets);
        const routeLabel =
          typeof HalCore !== "undefined" && HalCore.formatOfficeMessageTargets
            ? HalCore.formatOfficeMessageTargets(targets)
            : targets.join(", ");
        return {
          ok: true,
          summary: `Sent popup message to ${routeLabel}: ${text.slice(0, 240)}`,
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
        const lines = api.formatDatasetLines(diagnostics) || [];
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
          return { ok: false, summary: "Program help requires the NR2 server." };
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
          return { ok: false, summary: "Program source search requires the NR2 server." };
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
          return { ok: false, summary: "Memory search requires the NR2 server." };
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
    search_payer_reference: {
      label: "Search dental payer reference (routing + narrative hints)",
      run: async (ctx, args) => {
        const bridge =
          typeof DesktopBridge !== "undefined"
            ? DesktopBridge
            : typeof window !== "undefined" && window.DesktopBridge
              ? window.DesktopBridge
              : null;
        if (!bridge || typeof bridge.searchPayerReference !== "function") {
          return { ok: false, summary: "Payer reference search requires the NR2 server." };
        }
        const payload = await bridge.searchPayerReference(String(args.query || args.payer || ""), 4);
        const text = payload && payload.text ? String(payload.text) : "No payer reference matches.";
        return {
          ok: !!(payload && payload.count),
          summary: text.slice(0, 2500) || "No payer reference matches.",
          count: payload && payload.count ? payload.count : 0,
        };
      },
    },
    search_dental_carrier_catalog: {
      label: "Search US dental carrier catalog (carriers + plan families)",
      run: async (ctx, args) => {
        const bridge =
          typeof DesktopBridge !== "undefined"
            ? DesktopBridge
            : typeof window !== "undefined" && window.DesktopBridge
              ? window.DesktopBridge
              : null;
        if (!bridge || typeof bridge.searchDentalCarrierCatalog !== "function") {
          return { ok: false, summary: "Dental carrier catalog search requires the NR2 server." };
        }
        const payload = await bridge.searchDentalCarrierCatalog(
          String(args.query || args.carrier || args.payer || ""),
          8
        );
        const text = payload && payload.text ? String(payload.text) : "No carrier catalog matches.";
        return {
          ok: !!(payload && payload.count),
          summary: text.slice(0, 3000) || "No carrier catalog matches.",
          count: payload && payload.count ? payload.count : 0,
        };
      },
    },
    search_tesia_payers: {
      label: "Search Desktop Tesia / Vyne payer IDs (clearinghouse routing)",
      run: async (ctx, args) => {
        const bridge =
          typeof DesktopBridge !== "undefined"
            ? DesktopBridge
            : typeof window !== "undefined" && window.DesktopBridge
              ? window.DesktopBridge
              : null;
        if (!bridge || typeof bridge.searchTesiaPayers !== "function") {
          return { ok: false, summary: "Tesia payer search requires the NR2 server." };
        }
        const q = String(args.query || args.payer || args.payerId || "");
        const kansasOnly = /\bkansas\b|\bks\b/i.test(q) || !!args.kansas;
        const payload = await bridge.searchTesiaPayers(q, 8, kansasOnly);
        const text = payload && payload.text ? String(payload.text) : "No Tesia/Vyne payer matches.";
        return {
          ok: !!(payload && payload.count),
          summary: text.slice(0, 3000) || "No Tesia/Vyne payer matches.",
          count: payload && payload.count ? payload.count : 0,
        };
      },
    },
    join_softdent_tesia: {
      label: "Join SoftDent InsCo ECS IDs to Desktop Tesia/Vyne payer list (exact IDs only)",
      run: async (ctx, args) => {
        const bridge =
          typeof DesktopBridge !== "undefined"
            ? DesktopBridge
            : typeof window !== "undefined" && window.DesktopBridge
              ? window.DesktopBridge
              : null;
        if (!bridge || typeof bridge.joinSoftDentTesia !== "function") {
          return { ok: false, summary: "SoftDent↔Tesia join requires the NR2 server." };
        }
        const dry = !!(args.dryRun || args.dry_run || args.preview);
        const payload = await bridge.joinSoftDentTesia(dry);
        const text =
          payload && payload.text
            ? String(payload.text)
            : payload && payload.ok
              ? JSON.stringify(payload.counts || payload)
              : "SoftDent↔Tesia join failed.";
        return {
          ok: !!(payload && payload.ok),
          summary: text.slice(0, 3000),
          counts: payload && payload.counts ? payload.counts : null,
        };
      },
    },
    lookup_fee_schedule: {
      label: "Look up office fee schedule amounts by CDT / carrier",
      run: async (ctx, args) => {
        const bridge =
          typeof DesktopBridge !== "undefined"
            ? DesktopBridge
            : typeof window !== "undefined" && window.DesktopBridge
              ? window.DesktopBridge
              : null;
        if (!bridge || typeof bridge.lookupFeeSchedule !== "function") {
          return { ok: false, summary: "Fee schedule lookup requires the NR2 server." };
        }
        const q = String(args.query || args.code || args.cdt || "");
        const payer = String(args.payer || args.schedule || "").trim();
        const payload = await bridge.lookupFeeSchedule(payer ? `${q} ${payer}` : q, 3);
        const text = payload && payload.text ? String(payload.text) : "No fee schedule matches.";
        return {
          ok: !!(payload && payload.count),
          summary: text.slice(0, 2500) || "No fee schedule matches.",
          count: payload && payload.count ? payload.count : 0,
        };
      },
    },
    lookup_treatment_estimate: {
      label: "Look up SoftDent-derived insurance estimate for ADA code × payer",
      run: async (ctx, args) => {
        const bridge =
          typeof DesktopBridge !== "undefined"
            ? DesktopBridge
            : typeof window !== "undefined" && window.DesktopBridge
              ? window.DesktopBridge
              : null;
        if (!bridge || typeof bridge.lookupTreatmentEstimate !== "function") {
          return { ok: false, summary: "Treatment estimate lookup requires the NR2 server." };
        }
        const ada = String(args.ada_code || args.ada || args.code || args.cdt || "").trim();
        const payer = String(args.payer_name || args.payer || args.query || "").trim();
        const payload = await bridge.lookupTreatmentEstimate(payer, ada);
        const text =
          (payload && (payload.reply || payload.text)) ||
          "No treatment estimate available for that payer × ADA (empty ≠ $0).";
        return {
          ok: !!(payload && payload.ok),
          summary: String(text).slice(0, 2500),
          result: payload && payload.result ? payload.result : null,
        };
      },
    },
    list_eligibility_cache: {
      label: "List cached eligibility snapshots (PHI-redacted)",
      run: async (ctx, args) => {
        const bridge =
          typeof DesktopBridge !== "undefined"
            ? DesktopBridge
            : typeof window !== "undefined" && window.DesktopBridge
              ? window.DesktopBridge
              : null;
        if (!bridge || typeof bridge.listEligibilityCache !== "function") {
          return { ok: false, summary: "Eligibility cache requires the NR2 server." };
        }
        const payload = await bridge.listEligibilityCache(Number(args.limit || 8));
        const text = payload && payload.text ? String(payload.text) : "No fresh eligibility cache entries.";
        return {
          ok: !!(payload && payload.count),
          summary: text.slice(0, 2500) || "No fresh eligibility cache entries.",
          count: payload && payload.count ? payload.count : 0,
        };
      },
    },
    fetch_eligibility_271: {
      label: "Fetch eligibility via Availity/clearinghouse 271 (or report status / use cache)",
      run: async (ctx, args) => {
        const bridge =
          typeof DesktopBridge !== "undefined"
            ? DesktopBridge
            : typeof window !== "undefined" && window.DesktopBridge
              ? window.DesktopBridge
              : null;
        if (!bridge || typeof bridge.fetchEligibility271 !== "function") {
          return { ok: false, summary: "271 fetch requires the NR2 server." };
        }
        let payerName = String(args.payerName || args.payer || args.query || "").trim();
        let payerId = String(args.payerId || args.payer_id || "").trim();
        // Resolve payerId from Tesia/Vyne list first, then office payer reference
        if (payerName && !payerId && typeof bridge.searchTesiaPayers === "function") {
          try {
            const tesia = await bridge.searchTesiaPayers(payerName, 1, false);
            const hit = tesia && tesia.items && tesia.items[0];
            if (hit && hit.payerId) payerId = String(hit.payerId);
            if (hit && hit.name && !payerName) payerName = String(hit.name);
          } catch {
            /* optional */
          }
        }
        if (payerName && !payerId && typeof bridge.searchPayerReference === "function") {
          try {
            const pref = await bridge.searchPayerReference(payerName, 1);
            const hit = pref && pref.items && pref.items[0];
            if (hit) {
              const ids = hit.payerIds || [];
              if (ids.length) payerId = String(ids[0]);
              if (!payerName) payerName = String(hit.name || "");
            }
          } catch {
            /* optional */
          }
        }
        const vendorArg = String(args.vendor || "auto").trim().toLowerCase();
        let vendor = vendorArg || "auto";
        if (vendor === "tesia" || vendor === "vyne") vendor = "vyne_tesia";
        if (vendor === "availity_demo" || vendor === "availity-coverages") vendor = "availity";
        // Prefer Availity when the user/query mentions it
        if (
          vendor === "auto" &&
          /\bavaility\b/i.test(String(args.query || args.payerName || args.payer || ""))
        ) {
          vendor = "availity";
        }
        const payload = await bridge.fetchEligibility271({
          payerName,
          payerId,
          memberId: String(args.memberId || args.member_id || ""),
          providerNpi: String(args.providerNpi || args.npi || ""),
          subscriberLastName: String(args.subscriberLastName || args.lastName || ""),
          subscriberDob: String(args.subscriberDob || args.dateOfBirth || ""),
          vendor,
        });
        const parts = [];
        if (payload && payload.message) parts.push(String(payload.message));
        else if (payload && payload.error) parts.push(String(payload.error));
        if (payload && payload.demo) parts.push("(Availity demo mock — not live patient data.)");
        if (payload && payload.entry) {
          const e = payload.entry;
          const bits = [];
          if (e.payerName) bits.push(String(e.payerName));
          if (e.deductibleRemaining != null) bits.push("deductible remaining " + e.deductibleRemaining);
          if (e.annualMaxRemaining != null) bits.push("annual max remaining " + e.annualMaxRemaining);
          if (bits.length) parts.push("Cached: " + bits.join("; ") + ".");
        }
        if (payload && payload.hint) parts.push("Hint: " + String(payload.hint));
        if (payload && payload.status) {
          const st = payload.status;
          const live = st.liveReady ? "live credentials present" : "live credentials missing";
          const mock = st.mockEnabled ? "mock ON" : "mock OFF";
          parts.push(`Clearinghouse status: ${live}; ${mock}.`);
          if (st.vendors && st.vendors.availity) {
            const av = st.vendors.availity;
            parts.push(
              `Availity: ${av.configured ? "configured" : "not configured"}${av.demo ? " (demo)" : ""}.`
            );
          }
          if (st.requiredLiveFields && st.requiredLiveFields.length) {
            parts.push("Live 271 needs: " + st.requiredLiveFields.join(", ") + ".");
          }
        }
        if (payload && payload.ok === false && typeof bridge.listEligibilityCache === "function") {
          try {
            const cache = await bridge.listEligibilityCache(4);
            if (cache && cache.count) {
              parts.push("Fresh local eligibility cache still available — use list_eligibility_cache or POST /api/eligibility-cache to add a redacted snapshot.");
            } else {
              parts.push("No fresh eligibility cache. Staff can paste a PHI-redacted snapshot via POST /api/eligibility-cache.");
            }
          } catch {
            /* optional */
          }
        }
        const summary = parts.join(" ") || "271 fetch complete.";
        return { ok: !!(payload && payload.ok), summary: summary.slice(0, 2500) };
      },
    },
    fetch_availity_eligibility: {
      label: "Fetch dental eligibility/benefits via Availity Coverages (demo or live)",
      run: async (ctx, args) => {
        const def = TOOL_DEFS.fetch_eligibility_271;
        return def.run(ctx, Object.assign({}, args, { vendor: "availity" }));
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
          return { ok: false, summary: "Program file read requires the NR2 server." };
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
          return { ok: false, summary: "Program file list requires the NR2 server." };
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
          return { ok: false, summary: "Program patch requires the NR2 server." };
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
        return { ok: false, summary: "HAL validation requires the NR2 server or Node runtime." };
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
          return { ok: false, summary: "Syntax check requires the NR2 server." };
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
        return { ok: false, summary: "Semantic search requires the NR2 server or grep fallback." };
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
          return { ok: false, summary: "Git read requires the NR2 server." };
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
        else if (/rebuild-search|search index|reindex/.test(raw)) cmdId = "rebuild-search-index";
        else if (/git-status|git status/.test(raw)) cmdId = "git-status";
        else if (/validate|validation/.test(raw)) cmdId = "validate-hal";
        else if (/^[a-z0-9-]+$/.test(raw)) cmdId = raw;
        if (!bridge || typeof bridge.runAllowlistedCommand !== "function") {
          return { ok: false, summary: "Allowlisted commands require the NR2 server." };
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

  function extractAnalyzeTargets(query) {
    const q = String(query || "");
    const m = q.match(/\banalyze\s+(.+?)\s+and\s+(.+?)(?:\s+and tell me|\s*$)/i);
    if (!m) return null;
    const left = m[1].trim();
    const right = m[2].replace(/\s+and tell me.*$/i, "").trim();
    if (!left || !right || left.length < 2 || right.length < 2) return null;
    return [left, right];
  }

  function isMultiAnalyzeQuery(query) {
    return extractAnalyzeTargets(query) !== null;
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
    else if (route && (route.useFriendlyGreeting || route.intent === "chat: greeting")) lead = "Friendly note:";
    else if (/\bprioriti|attention|blocked|what should i\b/i.test(q) || (route && route.useOfficeAttention))
      lead = "What needs attention today:";
    else lead = "From local program evidence:";

    let next = "Next step: refresh imports or name a specific page if you want a narrower check.";
    if (/\breadiness\b/i.test(q)) next = "Next step: run readiness from HAL or open the page named in the findings.";
    else if (route && route.intent === "imports: refresh") next = "Next step: verify export paths, then refresh imports if files are missing.";
    else if (route && (route.useFriendlyGreeting || route.intent === "chat: greeting"))
      next = "Next step: ask me anything about the practice when you're ready.";
    else if (route && route.useOfficeAttention) next = "Next step: work the top attention item locally; outbound stays staff-gated.";
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

  function toolResultLooksEmpty(result) {
    if (!result) return true;
    if (result.ok === false) return true;
    if (typeof result.count === "number" && result.count <= 0) return true;
    const summary = String(result.summary || "").toLowerCase();
    if (!summary.trim()) return true;
    return /\b(no (?:matching|fee schedule|payer reference|fresh eligibility)|no matches|not found|requires the nr2 server)\b/i.test(
      summary
    );
  }

  function wantsInsuranceOpsTools(query) {
    const q = String(query || "");
    return (
      /\bD\d{4}\b/i.test(q) ||
      /\b(fee\s*schedule|allowed\s*amount|allowed\s*fee|contracted\s*fee|practice\s*amount|co-?45|underpay(?:ment)?|ucr)\b/i.test(
        q
      ) ||
      /\b(payer reference|payer id|routing id|denial theme|common denial|elig(?:ibility|ible)?\s*(?:phone|tel|number|website|portal|contact)|claim\s*phone)\b/i.test(
        q
      ) ||
      (/\b(delta dental|metlife|cigna|guardian|aetna|uhc|united concordia|humana|medicaid|bcbs|blue cross|careington|geha|dentemax|dentaquest)\b/i.test(
        q
      ) &&
        /\b(payer|insurance|denial|narrative|eob|claim|phone|fee|allowed|elig)\b/i.test(q)) ||
      /\b(eligibility cache|deductible remaining|annual max remaining|benefit check|270|271|coinsurance)\b/i.test(q) ||
      /\b(denial|appeal|eob|insurance claim)\b/i.test(q) ||
      /\b(claim preflight|preflight|packet readiness|denial risk|pre-?submit scrub|before submit)\b/i.test(q) ||
      /\b(claims? aging|aging follow-?up|over (30|60|90) days|60\+ days|90\+ days)\b/i.test(q) ||
      (/\bclaims?\b/i.test(q) && /\b(denied|denial|payer|carrier|readiness|scrub|submit|appeal|aging|follow-?up)\b/i.test(q))
    );
  }

  function expandGatherToolsForRound(query, route, toolResults, round, existingIds) {
    const had = new Set(existingIds || []);
    const add = [];
    const blob = Object.values(toolResults || {})
      .map((r) => (r && r.summary ? String(r.summary) : ""))
      .join(" ");
    const results = toolResults || {};
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
      // Insurance recovery: if first pass skipped or emptied payer/fee/eligibility tools, add them.
      if (wantsInsuranceOpsTools(query)) {
        if (!had.has("search_payer_reference")) add.push("search_payer_reference");
        else if (toolResultLooksEmpty(results.search_payer_reference) && !had.has("search_hal_memories")) {
          add.push("search_hal_memories");
        }
        if (
          /\b(dental\s*carrier\s*catalog|us\s*dental\s*(carriers?|insurers?)|plan\s*families|carriers?\s*offered)\b/i.test(
            query
          ) &&
          !had.has("search_dental_carrier_catalog")
        ) {
          add.push("search_dental_carrier_catalog");
        }
        if (
          /\bD\d{4}\b/i.test(query) ||
          /\b(fee\s*schedule|allowed|co-?45|underpay|practice\s*amount|ucr)\b/i.test(query)
        ) {
          if (!had.has("lookup_fee_schedule")) add.push("lookup_fee_schedule");
          else if (toolResultLooksEmpty(results.lookup_fee_schedule) && !had.has("search_hal_memories")) {
            add.push("search_hal_memories");
          }
        }
        if (
          /\b(deductible|annual max|benefit check|270|271|coinsurance|eligibility cache)\b/i.test(query) &&
          !had.has("list_eligibility_cache")
        ) {
          add.push("list_eligibility_cache");
        }
        if (
          /\b(draft|write|prepare|generate)\b.*\bnarrative\b|\bdraft with hal\b/i.test(query) &&
          !had.has("draft_insurance_narrative")
        ) {
          add.push("draft_insurance_narrative");
        }
        // Claim scrub: readiness / preflight / denial when the ask is claim-scoped.
        if (/\b(claims?|denied|denial|appeal|pre-?submit|packet|readiness|aging)\b/i.test(query)) {
          if (!had.has("read_claims_summary")) add.push("read_claims_summary");
          if (
            /\b(preflight|before submit|ready to submit|scrub|packet)\b/i.test(query) &&
            !had.has("stage_claim_preflight")
          ) {
            add.push("stage_claim_preflight");
            if (!had.has("list_eligibility_cache")) add.push("list_eligibility_cache");
          }
          if (
            /\b(denial risk|deny|predict denial|pre-?submit|scrub)\b/i.test(query) &&
            !had.has("predict_claim_denial_risk")
          ) {
            add.push("predict_claim_denial_risk");
          }
          if (
            /\b(appeal|appeal packet|denial packet|build (an? )?appeal)\b/i.test(query) &&
            !had.has("build_appeal_packet")
          ) {
            add.push("build_appeal_packet");
            if (!had.has("read_clinical_summary")) add.push("read_clinical_summary");
          }
          if (
            /\b(payer|carrier|insurance|join)\b/i.test(query) &&
            !had.has("join_claim_payers")
          ) {
            add.push("join_claim_payers");
          }
          if (
            /\b(aging|over \d+ days|60\+?|90\+?|follow-?up queue|oldest claim)\b/i.test(query) &&
            !had.has("list_claims_aging_followup")
          ) {
            add.push("list_claims_aging_followup");
          }
        }
        if (
          /\b(era|eob|835)\b/i.test(query) &&
          /\b(pending|review|match|queue)\b/i.test(query) &&
          !had.has("list_pending_era_matches")
        ) {
          add.push("list_pending_era_matches");
        }
        if (
          /\bconfirm\b/i.test(query) &&
          /\b(era|eob|match)\b/i.test(query) &&
          !had.has("confirm_era_match")
        ) {
          add.push("confirm_era_match");
        }
        if (
          /\b(collections?|who do i call|call list|past due)\b/i.test(query) &&
          !had.has("build_collections_queue")
        ) {
          add.push("build_collections_queue");
          if (!had.has("schedule_call_task")) add.push("schedule_call_task");
          if (!had.has("click_to_dial")) add.push("click_to_dial");
        }
        if (
          /\b(log (call|outcome)|call outcome|no.?answer|promised to pay)\b/i.test(query) &&
          !had.has("log_call_outcome")
        ) {
          add.push("log_call_outcome");
        }
        if (
          /\b(aging|over \d+ days|60\+?|90\+?).*\b(call|dial|follow)\b|\bfollow.?up claim\b/i.test(query) &&
          !had.has("schedule_call_task")
        ) {
          add.push("schedule_call_task");
          if (!had.has("list_claims_aging_followup")) add.push("list_claims_aging_followup");
        }
        if (
          /\b(denial|narrative|appeal).*\b(tips?|theme|draft)\b|\bdraft.*\b(denial|narrative|appeal)\b/i.test(query) &&
          !had.has("search_payer_reference")
        ) {
          add.push("search_payer_reference");
          if (!had.has("draft_insurance_narrative")) add.push("draft_insurance_narrative");
        }
        if (
          /\b(month.?end|close the month|close tasks)\b/i.test(query) &&
          !had.has("generate_month_end_tasks")
        ) {
          add.push("generate_month_end_tasks");
        }
        if (
          /\b(underpay|underpaid|fee vs paid|allowed vs paid|co-?45)\b/i.test(query) &&
          !had.has("scrub_fee_vs_paid")
        ) {
          add.push("scrub_fee_vs_paid");
        }
        if (
          /\b(posting queue|journal queue|pending postings?)\b/i.test(query) &&
          !had.has("list_posting_queue")
        ) {
          add.push("list_posting_queue");
        }
        if (
          /\b(softdent|odbc|named payer|carrier gap|sd_claims)\b/i.test(query) &&
          !had.has("softdent_extract_status")
        ) {
          add.push("softdent_extract_status");
        }
      }
    }
    if (round >= 2) {
      if (!had.has("read_program_help")) add.push("read_program_help");
      if (!had.has("search_program")) add.push("search_program");
      if (!had.has("read_source_health")) add.push("read_source_health");
      if (wantsInsuranceOpsTools(query)) {
        if (!had.has("search_payer_reference")) add.push("search_payer_reference");
        if (!had.has("lookup_fee_schedule") && /\bD\d{4}\b|fee|allowed|co-?45|underpay/i.test(query)) {
          add.push("lookup_fee_schedule");
        }
        if (
          !had.has("lookup_treatment_estimate") &&
          /\b(estimate|treatment\s*plan|how much.*(pay|cover)|insurance\s*pay)/i.test(query) &&
          /\bD\d{4}\b/i.test(query)
        ) {
          add.push("lookup_treatment_estimate");
        }
        if (!had.has("search_hal_memories")) add.push("search_hal_memories");
        if (/\b(claim|denied|denial|appeal)\b/i.test(query)) {
          if (!had.has("read_claims_summary")) add.push("read_claims_summary");
          if (!had.has("join_claim_payers")) add.push("join_claim_payers");
        }
      }
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
    const q = String((plan && plan.originalQuery) || "");
    if (wantsInsuranceOpsTools(q)) {
      const results = toolResults || {};
      if (
        toolResultLooksEmpty(results.search_payer_reference) ||
        toolResultLooksEmpty(results.lookup_fee_schedule) ||
        toolResultLooksEmpty(results.list_eligibility_cache) ||
        toolResultLooksEmpty(results.read_claims_summary)
      ) {
        return true;
      }
      // Planned insurance tools never ran
      const planned = new Set((plan && plan.tools) || []);
      if (
        (planned.has("search_payer_reference") && !results.search_payer_reference) ||
        (planned.has("lookup_fee_schedule") && !results.lookup_fee_schedule) ||
        (planned.has("read_claims_summary") && !results.read_claims_summary) ||
        (planned.has("stage_claim_preflight") && !results.stage_claim_preflight) ||
        (planned.has("predict_claim_denial_risk") && !results.predict_claim_denial_risk)
      ) {
        return true;
      }
    }
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
    if (
      typeof HalCore !== "undefined" &&
      HalCore.isGreetingQuery &&
      HalCore.isGreetingQuery(query)
    ) {
      /* Friendly hello — no diagnostic gather. */
    } else if (
      /\bwhat (needs|requires) attention\b|\bwhat should i (do|work on)\b|\b(start of day|morning (brief|check))\b/i.test(
        query,
      )
    ) {
      gather.push("list_autonomous_work", "read_import_diagnostics", "read_claims_summary");
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
    if (/\banalyze .+ and .+/i.test(query) && /\bmissing\b/i.test(query)) {
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
    if (/\b(remember|recall|you said|last time|memory|memoai|learned)\b/i.test(query)) {
      gather.push("search_hal_memories");
    }
    if (
      /\b(claim|denied|denial|appeal|narrative|cdt|crown|srp|prophy|implant|endo|payer|insurance|eob|era|d2740|d4341|d6010|d3330)\b/i.test(
        query,
      )
    ) {
      gather.push("search_hal_memories");
    }
    if (/\b(tax|1120|k-1|scorp|quickbooks|softdent|import|a\/r|ar aging|hipaa|schedule|hygiene|closeout|osha)\b/i.test(query)) {
      gather.push("search_hal_memories");
    }
    if (
      /\b(payer reference|payer id|routing id|denial theme|common denial|elig(?:ibility|ible)?\s*(?:phone|tel|number|website|portal|contact)|claim\s*phone)\b/i.test(
        query
      ) ||
      (/\b(delta dental|metlife|cigna|guardian|aetna|uhc|united concordia|humana|medicaid|bcbs|blue cross|careington|geha|dentemax|dentaquest)\b/i.test(
        query
      ) &&
        /\b(payer|insurance|denial|narrative|eob|claim|phone|fee|allowed|elig)\b/i.test(query))
    ) {
      gather.push("search_payer_reference");
    }
    if (
      /\b(dental\s*carrier\s*catalog|us\s*dental\s*(carriers?|insurers?)|plan\s*families|what\s*plans\s*(does|do)|carriers?\s*offered|insurance\s*companies\s*list)\b/i.test(
        query
      ) ||
      (/\b(carrier|insurer|insurance\s*compan(?:y|ies))\b/i.test(query) &&
        /\b(plan|policy|policies|ppo|dhmo|marketplace|individual)\b/i.test(query))
    ) {
      gather.push("search_dental_carrier_catalog");
    }
    if (
      /\b(tesia|vyne|payer\s*id|payor\s*id|e-?claim\s*id|clearinghouse\s*payer)\b/i.test(query)
    ) {
      gather.push("search_tesia_payers");
    }
    if (
      /\b(softdent\s*[↔\-–]?\s*tesia|join\s+(softdent|tesia)|tesia\s+join|ecs\s*(payer\s*)?id)\b/i.test(
        query
      )
    ) {
      gather.push("join_softdent_tesia");
    }
    if (
      /\bD\d{4}\b/i.test(query) ||
      /\b(fee\s*schedule|allowed\s*amount|allowed\s*fee|contracted\s*fee|practice\s*amount|co-?45|underpay(?:ment)?)\b/i.test(
        query
      )
    ) {
      gather.push("lookup_fee_schedule");
    }
    if (/\b(eligibility cache|deductible remaining|annual max remaining|benefit check|270|271|coinsurance)\b/i.test(query)) {
      gather.push("list_eligibility_cache");
    }
    if (
      /\b(fetch 271|270\/271|clearinghouse eligibility|run eligibility|availity|fetch availity|check (?:eligibility|benefits) (?:with |via )?availity)\b/i.test(
        query
      )
    ) {
      gather.push("fetch_eligibility_271");
      if (/\bavaility\b/i.test(query)) gather.push("fetch_availity_eligibility");
    }
    if (/\b(claim|denied|denial|appeal|packet|readiness|pre-?submit)\b/i.test(query) && wantsInsuranceOpsTools(query)) {
      gather.push("read_claims_summary");
      if (/\b(preflight|before submit|scrub|packet readiness)\b/i.test(query)) {
        gather.push("stage_claim_preflight");
      }
      if (/\b(denial risk|predict denial|pre-?submit scrub)\b/i.test(query)) {
        gather.push("predict_claim_denial_risk");
      }
      if (/\b(payer|carrier|join)\b/i.test(query)) {
        gather.push("join_claim_payers");
      }
    }
    if (/\blearn this|save this|note that|remember this|remember that|our office always|from now on\b/i.test(query)) {
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
    const interviewMode = typeof globalThis !== "undefined" && globalThis._halInterviewMode;
    const workstationFast = workstationFastHalActive();
    const intent = route.intent || "";
    const isUnsafe = false;
    const tools = [];

    if (routeIsOperational(route)) {
      return {
        questionType: classifyQuestion(query, route),
        originalQuery: query,
        needsData: false,
        tools: [],
        isUnsafe: false,
        useModelEnhancement: false,
        needsClarification: false,
        agentToolLoop: false,
        planOnly: false,
        isTaskCompletionQuery: false,
        isInvestigateQuery: false,
        isComplexInvestigationQuery: false,
        lane: route.lane,
        intent,
        budget: AGENT_BUDGET,
        preferences: longTerm.preferences,
      };
    }

    if (
      route.text &&
      String(route.text).trim() &&
      typeof HalIndependentThought !== "undefined" &&
      HalIndependentThought.cursorParityFastPath &&
      HalIndependentThought.cursorParityFastPath(ctx.halModels, query, route)
    ) {
      return {
        questionType: classifyQuestion(query, route),
        originalQuery: query,
        needsData: false,
        tools: [],
        isUnsafe: false,
        useModelEnhancement: false,
        needsClarification: false,
        agentToolLoop: false,
        planOnly: false,
        isTaskCompletionQuery: false,
        isInvestigateQuery: false,
        isComplexInvestigationQuery: false,
        lane: route.lane,
        intent,
        budget: AGENT_BUDGET,
        preferences: longTerm.preferences,
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
    if (
      route.useClaimReadiness ||
      (/\b(claim|denied|packet|readiness)\b/i.test(query) && !route.text) ||
      (wantsInsuranceOpsTools(query) && /\b(claim|denied|denial|appeal)\b/i.test(query))
    ) {
      tools.push("read_claims_summary");
    }
    if (
      /\b(claim.*(payer|insurance|insco)|payer.*(claim|join)|which payer|carrier on (the )?claim)\b/i.test(query) ||
      (/\bclaim\b/i.test(query) && /\b(metlife|delta|cigna|guardian|aetna|payer|insurance)\b/i.test(query)) ||
      (wantsInsuranceOpsTools(query) && /\b(claim|denied)\b/i.test(query) && /\b(payer|carrier)\b/i.test(query))
    ) {
      tools.push("join_claim_payers");
    }
    if (
      /\b(draft|write|prepare|generate)\b.*\b(insurance\s+)?narrative\b/i.test(query) ||
      /\bnarrative\b.*\b(for|on)\b.*\bclaim\b/i.test(query) ||
      /\bdraft with hal\b/i.test(query)
    ) {
      tools.push("draft_insurance_narrative");
    }
    if (
      /\b(denial|narrative|eob|payer|insurance claim|appeal|elig(?:ibility|ible)?\s*(?:phone|tel|number|website|portal|contact)|claim\s*phone)\b/i.test(
        query
      ) ||
      (/\b(delta dental|metlife|cigna|guardian|aetna|humana|bcbs|blue cross)\b/i.test(query) &&
        /\b(phone|fee|allowed|insurance|elig)\b/i.test(query))
    ) {
      tools.push("search_payer_reference");
    }
    if (
      /\b(dental\s*carrier\s*catalog|us\s*dental\s*(carriers?|insurers?)|plan\s*families|carriers?\s*offered)\b/i.test(
        query
      ) ||
      (/\b(carrier|insurer|insurance\s*compan(?:y|ies))\b/i.test(query) &&
        /\b(plan|policy|policies|ppo|dhmo|marketplace)\b/i.test(query))
    ) {
      tools.push("search_dental_carrier_catalog");
    }
    if (/\b(tesia|vyne|payer\s*id|payor\s*id|e-?claim\s*id|clearinghouse\s*payer)\b/i.test(query)) {
      tools.push("search_tesia_payers");
    }
    if (
      /\b(softdent\s*[↔\-–]?\s*tesia|join\s+(softdent|tesia)|tesia\s+join|ecs\s*(payer\s*)?id)\b/i.test(
        query
      )
    ) {
      tools.push("join_softdent_tesia");
    }
    if (
      /\bD\d{4}\b/i.test(query) ||
      /\b(fee\s*schedule|allowed\s*amount|allowed\s*fee|contracted\s*fee|practice\s*amount|co-?45|underpay(?:ment)?)\b/i.test(
        query
      )
    ) {
      tools.push("lookup_fee_schedule");
    }
    if (/\b(eligibility|deductible|annual max|copay|benefit remaining|270|271)\b/i.test(query)) {
      tools.push("list_eligibility_cache");
    }
    if (/\b(availity|fetch 271|270\/271|clearinghouse eligibility|run eligibility)\b/i.test(query)) {
      if (!tools.includes("fetch_eligibility_271")) tools.push("fetch_eligibility_271");
      if (/\bavaility\b/i.test(query) && !tools.includes("fetch_availity_eligibility")) {
        tools.push("fetch_availity_eligibility");
      }
    }
    if (
      /\bsoftdent\b.*\b(odbc|extract|sd_|sqlite)\b|\bodbc\b.*\bsoftdent\b|\bsd_\w+\b|\bextract status\b/i.test(query)
    ) {
      tools.push("softdent_extract_status");
    }
    if (/\b(shift|tier|employee level|standing consent)\b/i.test(query)) {
      tools.push("read_shift_context");
    }
    if (/\b(lane history|model lane|which model|escalat)\b/i.test(query)) {
      tools.push("read_model_lane_history");
    }
    if (/\b(clinical summary|clinical context|sidenotes|procedure narrative)\b/i.test(query)) {
      tools.push("read_clinical_summary");
    }
    if (
      /\b(summarize\s+patient|patient\s+dossier|mega[- ]?dossier|full\s+summary\s+of\s+patient|dossier\s+for\s+patient)\b/i.test(
        query
      ) ||
      /\bsummarize\s+[A-Za-z0-9]{4}\b/i.test(query)
    ) {
      if (!tools.includes("summarize_patient_dossier")) tools.push("summarize_patient_dossier");
    }
    if (
      /\b(about\s+this\s+patient|patient\s+summary|selected\s+patient|ask\s+hal\s+about)\b/i.test(query)
    ) {
      if (!tools.includes("read_patient_summary")) tools.push("read_patient_summary");
      if (!tools.includes("summarize_patient_dossier")) tools.push("summarize_patient_dossier");
    }
    if (/\b(clear\s+patient\s+context|forget\s+patient)\b/i.test(query)) {
      if (!tools.includes("clear_patient_context")) tools.push("clear_patient_context");
    }
    if (/\b(collection letter|collection call|schedule call)\b/i.test(query)) {
      tools.push("generate_collection_letter", "schedule_call_task");
    }
    if (/\b(heal import|import heal|refresh import|fix import)\b/i.test(query)) {
      tools.push("heal_import_pipeline");
    }
    if (/\b(era|835|eob match|parse era)\b/i.test(query)) {
      tools.push("parse_era_835", "match_eob_era");
    }
    if (
      /\b(collections queue|collect from|past due|follow.?up queue|who do i call|call list|collections call)\b/i.test(
        query
      ) ||
      (/\b(collections?|a\/?r|aging)\b/i.test(query) && /\b(call|queue|today|follow)\b/i.test(query))
    ) {
      tools.push("build_collections_queue");
    }
    if (
      /\b(deposit reconc|bank deposit|deposit variance|collections?\s+vs\s+deposit|why is (the )?deposit|deposit off)\b/i.test(
        query
      ) ||
      (/\b(deposit|deposits)\b/i.test(query) && /\b(variance|reconcil|mismatch|off|short|over)\b/i.test(query))
    ) {
      tools.push("draft_deposit_reconciliation");
    }
    if (
      /\b(claim preflight|preflight|before submit|scrub (the )?claim|packet readiness)\b/i.test(query) ||
      (wantsInsuranceOpsTools(query) && /\b(pre-?submit|ready to submit)\b/i.test(query))
    ) {
      tools.push("stage_claim_preflight");
      if (!tools.includes("list_eligibility_cache")) tools.push("list_eligibility_cache");
    }
    if (/\b(eob|era|835|auto.?match)\b/i.test(query)) {
      tools.push("match_eob_era");
    }
    if (
      /\b(posting queue|journal posting queue|journal queue|list postings?|pending postings?)\b/i.test(query) ||
      (/\bposting\b/i.test(query) && /\b(queue|pending|review|list|show)\b/i.test(query))
    ) {
      tools.push("list_posting_queue");
    }
    if (/\b(batch approve|approve postings|approve queue)\b/i.test(query)) {
      tools.push("batch_approve_postings");
    }
    if (/\b(month.?end|close tasks|month end tasks|month end close|close the month)\b/i.test(query)) {
      tools.push("generate_month_end_tasks");
    }
    if (
      /\b(underpay|underpaid|fee vs paid|allowed vs paid|co-?45 scrub|scrub (the )?eob)\b/i.test(query) ||
      (/\b(co-?45|underpay)\b/i.test(query) && /\b(D\d{4}|paid|eob|era|allowed)\b/i.test(query))
    ) {
      tools.push("scrub_fee_vs_paid");
      if (!tools.includes("lookup_fee_schedule")) tools.push("lookup_fee_schedule");
    }
    if (/\b(clock out|shift handoff|end shift|handoff report)\b/i.test(query)) {
      tools.push("clock_out_shift", "get_last_handoff_report");
    }
    if (/\b(readiness|system check|health check|smoke test)\b/i.test(query)) {
      if (!tools.includes("readiness_diagnostics")) tools.push("readiness_diagnostics");
    }
    if (/\b(briefing|morning brief|daily ops|status update)\b/i.test(query)) {
      if (!tools.includes("daily_ops_briefing")) tools.push("daily_ops_briefing");
    }
    if (/\b(click.?to.?dial|call patient|phone script|voip)\b/i.test(query)) {
      tools.push("click_to_dial", "log_call_outcome");
    }
    if (/\b(sms|text reminder|billing text)\b/i.test(query)) {
      tools.push("send_billing_sms", "get_sms_thread");
    }
    if (/\b(quickbooks|qbo|qb sync|journal entry)\b/i.test(query)) {
      tools.push("sync_qb_customers", "push_journal_entry_to_qb", "get_qb_reconciliation_status");
    }
    if (/\b(classify document|mail sort|scan document|incoming mail)\b/i.test(query)) {
      tools.push("classify_incoming_document");
    }
    if (/\b(era feedback|match confidence|wrong match)\b/i.test(query)) {
      tools.push("record_era_match_feedback");
    }
    if (/\b(morning routine|autonomous|scheduler|proactive alert)\b/i.test(query)) {
      tools.push("run_morning_routine", "acknowledge_alert", "undo_scheduler_run", "list_autonomous_work");
    }
    if (
      /\b(autonomous work|staged appeal|work ledger|what did hal (do|stage)|hal staged)\b/i.test(query)
    ) {
      tools.push("list_autonomous_work");
    }
    if (/\b(undo morning|undo scheduler|undo autonomous)\b/i.test(query)) {
      tools.push("undo_scheduler_run");
    }
    if (/\b(eod handoff|end of day handoff|compile handoff)\b/i.test(query)) {
      tools.push("get_last_handoff_report");
    }
    if (
      /\b(denial risk|deny before submit|predict denial|pre.?submit scrub)\b/i.test(query) ||
      (wantsInsuranceOpsTools(query) && /\b(denial|appeal)\b/i.test(query) && /\b(risk|scrub|before submit|predict)\b/i.test(query))
    ) {
      tools.push("predict_claim_denial_risk");
    }
    if (
      /\b(appeal packet|denial packet|build (an? )?appeal|prepare (an? )?appeal)\b/i.test(query) ||
      (/\bappeal\b/i.test(query) && /\b(denied|denial|claim)\b/i.test(query))
    ) {
      tools.push("build_appeal_packet");
      if (!tools.includes("draft_insurance_narrative")) tools.push("draft_insurance_narrative");
      if (!tools.includes("read_clinical_summary")) tools.push("read_clinical_summary");
    }
    if (
      /\b(named payer|carrier gap|softdent (claims|odbc)|sd_claims|odbc status)\b/i.test(query) ||
      (/\bsoftdent\b/i.test(query) && /\b(payer|carrier|claims export)\b/i.test(query))
    ) {
      if (!tools.includes("softdent_extract_status")) tools.push("softdent_extract_status");
    }
    if (/\b(era|eob).*(pending|review|queue)|pending (era|eob|matches)\b/i.test(query)) {
      tools.push("list_pending_era_matches");
    }
    if (
      /\b(confirm (era|eob|match)|approve (era|eob) match|era match (is )?correct)\b/i.test(query) ||
      (/\bconfirm\b/i.test(query) && /\b(era|eob|match)\b/i.test(query) && /\bclaim\b/i.test(query))
    ) {
      tools.push("confirm_era_match");
    }
    if (
      /\b(claims? aging|aging follow-?up|over (30|60|90) days|60\+ days|90\+ days|oldest claims?|follow-?up queue)\b/i.test(
        query
      )
    ) {
      tools.push("list_claims_aging_followup");
      if (/\b(call|dial|phone|follow.?up)\b/i.test(query)) {
        if (!tools.includes("schedule_call_task")) tools.push("schedule_call_task");
        if (!tools.includes("click_to_dial")) tools.push("click_to_dial");
      }
    }
    if (/\b(log (call|outcome)|call outcome|no.?answer|promised)\b/i.test(query)) {
      if (!tools.includes("log_call_outcome")) tools.push("log_call_outcome");
    }
    if (/\b(pull qb|pull quickbooks|qb payments|qb pull)\b/i.test(query)) {
      tools.push("pull_qb_payments", "get_qb_reconciliation_status");
    }
    if (/\b(pilot phase|cutover|shadow mode|system of record)\b/i.test(query)) {
      tools.push("read_current_context");
    }
    if (
      route.useOfficeMessageSend ||
      (/\b(message|tell|notify|alert|ping|send)\b/i.test(query) &&
        /\b(room|frontdesk|front desk|everyone|office manager|server|darkroom|everyone)\b/i.test(query))
    ) {
      tools.push("send_office_message");
    }
    if (
      (route.useOfficeAttention || route.useTaskList || route.useTaskCreate) &&
      /\b(task|office manager|attention)\b/i.test(query) &&
      !route.text
    ) {
      tools.push("read_tasks");
    }
    if (route.useFriendlyGreeting || route.intent === "chat: greeting") {
      /* Friendly hello — skip diagnostics / briefing tools. */
    } else if (route.useOfficeAttention) {
      tools.push(
        "list_autonomous_work",
        "read_import_diagnostics",
        "read_claims_summary",
        "read_office_briefing",
      );
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
    if (
      /\bwhat (needs|requires) attention\b|\bwhat should i (do|work on|focus on)\b|\b(start of day|start my day)\b/i.test(
        query,
      )
    ) {
      tools.push("list_autonomous_work", "read_import_diagnostics", "read_claims_summary", "read_office_briefing");
    }
    if (intent === "consent" || /\bconsent\b/i.test(query)) tools.push("explain_consent");
    if (intent === "firewall" || /\bfirewall\b/i.test(query)) tools.push("explain_consent");
    if (ctx && webResearchEnabled(ctx, query, route)) tools.push("research_web");

    if (agentCfg.cursorGather !== false) {
      cursorGatherTools(query, route).forEach((id) => tools.push(id));
    }

    if (parsePatchFromQuery(query)) tools.push("apply_program_patch");
    if (isTaskCompletionQuery(query)) {
      if (/\bvalidate|validation|make.*pass\b/i.test(query)) tools.push("run_hal_validation");
      if (/\bsyntax\b/i.test(query)) tools.push("run_node_syntax_check");
    }

    if (
      !interviewMode &&
      !workstationFast &&
      !(route.useFriendlyGreeting || route.intent === "chat: greeting") &&
      !(typeof HalCore !== "undefined" && HalCore.isGreetingQuery && HalCore.isGreetingQuery(query)) &&
      typeof HalChat9000 !== "undefined" &&
      HalChat9000.isEnabled(ctx.halModels) &&
      HalChat9000.config(ctx.halModels).alwaysGatherTools !== false
    ) {
      HalChat9000.defaultGatherTools().forEach((id) => tools.push(id));
    }

    if (interviewMode) {
      const essential = new Set([
        "read_current_context",
        "read_program_snapshot",
        "read_source_health",
        "read_import_diagnostics",
        "read_widget_feed",
        "read_registry",
      ]);
      const filtered = [...new Set(tools)].filter((id) => essential.has(id));
      tools.length = 0;
      filtered.forEach((id) => tools.push(id));
    }

    if (workstationFast) {
      const essential = new Set(["read_current_context", "search_document_library", "read_registry"]);
      const filtered = [...new Set(tools)].filter((id) => essential.has(id));
      tools.length = 0;
      filtered.forEach((id) => tools.push(id));
    }

    const uniqueTools = [...new Set(tools)].slice(0, AGENT_BUDGET.maxTools);
    const planOnly = typeof HalAgentLoop !== "undefined" && HalAgentLoop.isPlanOnlyQuery(query);

    let agentToolLoop = !planOnly && shouldUseAgentToolLoop(query, route, agentCfg);
    if (workstationFast) {
      agentToolLoop = false;
    } else if (
      !interviewMode &&
      typeof HalChat10000 !== "undefined" &&
      HalChat10000.shouldAlwaysAgentLoop(ctx.halModels, route, query)
    ) {
      agentToolLoop = !planOnly;
    } else if (
      !interviewMode &&
      typeof HalChat9000 !== "undefined" &&
      HalChat9000.shouldAlwaysAgentLoop(ctx.halModels, route, query)
    ) {
      agentToolLoop = !planOnly;
    }

    return {
      questionType: classifyQuestion(query, route),
      originalQuery: query,
      needsData: uniqueTools.length > 0,
      tools: uniqueTools,
      isUnsafe: false,
      useModelEnhancement: !!(route.useModel || route.useReasoning || route.useEscalation || route.useOss),
      needsClarification: !route.text && !hasUseFlag(route),
      agentToolLoop,
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
    if (workstationFastHalActive()) return false;
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

  function shiftContextBlock() {
    const state = typeof window !== "undefined" ? window.nr2ShiftState : null;
    if (!state) return "";
    const lines = [
      "[SHIFT_CONTEXT]",
      `Tier: ${state.tier} (${state.levelName || "Unknown"})`,
      `Active: ${state.active ? "yes" : "no"}`,
      `Employee: ${state.employeeId || "HAL"}`,
      "Respect standing consent policies for outbound and posting actions at this tier.",
      "[END_SHIFT_CONTEXT]",
    ];
    return lines.join("\n");
  }

  function buildAgentSystemPrompt(ctx, plan, toolResults, working, longTerm) {
    const query = plan && plan.originalQuery ? plan.originalQuery : "";
    const usePlanStyle =
      plan.questionType === "planning" &&
      (HalCore.wantsStructuredPlan ? HalCore.wantsStructuredPlan(query) : /make a plan|prioriti/i.test(query));
    const chat10000 = typeof HalChat10000 !== "undefined" && HalChat10000.isEnabled(ctx.halModels);
    const chat9000 = typeof HalChat9000 !== "undefined" && HalChat9000.isEnabled(ctx.halModels);
    let base;
    if ((chat10000 || chat9000) && plan.questionType !== "escalation") {
      const Chat = chat10000 ? HalChat10000 : HalChat9000;
      base =
        plan.questionType === "planning" && usePlanStyle
          ? HalCore.buildReasoningPrompt(ctx.halData, null)
          : plan.questionType === "planning" && Chat.buildReasoningPrompt
            ? HalChat9000.buildReasoningPrompt(ctx.halData, ctx.halModels)
            : Chat.buildSystemPrompt(ctx.halData, ctx.halModels);
      base = Chat.enrichPrompt(base, ctx);
    } else {
      base =
        plan.questionType === "planning" && !usePlanStyle
          ? HalCore.buildReasoningChatPrompt(ctx.halData, null)
          : plan.questionType === "planning"
            ? HalCore.buildReasoningPrompt(ctx.halData, null)
            : plan.questionType === "escalation"
              ? HalCore.buildEscalationPrompt(ctx.halData, null)
              : HalCore.buildSystemPrompt(ctx.halData, null);
    }

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

    const shiftBlock = shiftContextBlock();
    if (shiftBlock) parts.push("", shiftBlock);

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
    if (plan.isUnsafe && !/consent|human review|confirmed|with your approval/i.test(body)) {
      issues.push("unsafe_not_refused");
    }
    if (!plan.isUnsafe && /\b(I (submitted|sent|emailed|uploaded|posted|deleted|paid|wired|faxed))\b/i.test(body) && !/consent|confirmed|with your approval/i.test(body)) {
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
          : "That outbound action needs your explicit consent first. I can open the right page and prepare the delivery — confirm when you are ready.";
    } else if (issues.includes("claimed_external_action")) {
      repaired =
        body.replace(/\bI (submitted|sent|emailed|uploaded|posted|deleted|paid|wired|faxed)\b/gi, "A human must") +
        "\n\n(Local draft only — external delivery requires your consent.)";
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
    if (meta && (meta.claimId || meta.narrativeId || meta.payer || meta.topic)) {
      const bridge =
        typeof DesktopBridge !== "undefined"
          ? DesktopBridge
          : typeof window !== "undefined" && window.DesktopBridge
            ? window.DesktopBridge
            : null;
      if (bridge && typeof bridge.updateHalSessionContext === "function") {
        bridge
          .updateHalSessionContext({
            claimId: meta.claimId || "",
            narrativeId: meta.narrativeId || "",
            payer: meta.payer || "",
            page: meta.focus || workingMemory.currentPage || "",
            topic: meta.topic || (meta.intent ? String(meta.intent) : ""),
          })
          .catch(() => {});
      }
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
    if (workstationFastHalActive()) return false;
    if (typeof globalThis !== "undefined" && globalThis._halForceReasoning === false) return false;
    if (typeof globalThis !== "undefined" && (globalThis._halRandomQaUseReasoning || globalThis._halForceReasoning)) {
      return true;
    }
    const cfg = ctx && ctx.halModels && ctx.halModels.config;
    const c9000 = cfg && cfg.chat9000;
    if (c9000 && c9000.enabled !== false && c9000.defaultReasoning !== false) return true;
    return !!(cfg && cfg.preferReasoning);
  }

  function routeIsOperational(route) {
    if (!route) return false;
    if (
      route.useEnglishDefine ||
      route.useEnglishRandom ||
      route.useEnglishQuiz ||
      route.useEnglishTeach ||
      route.useEnglishSeed
    ) {
      return true;
    }
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
    if (workstationFastHalActive()) {
      if (route.text && String(route.text).trim()) return route;
      if (routeIsOperational(route)) return route;
      const r = Object.assign({}, route);
      r.useReasoning = false;
      r.useEscalation = false;
      r.useOss = false;
      r.useModel = true;
      r.lane = "chat8b";
      if (/^reasoning:/.test(String(r.intent || ""))) r.intent = "model: query";
      if (!r.text) r.prompt = r.prompt || query;
      return r;
    }
    if (typeof globalThis !== "undefined" && globalThis._halInterviewMode) {
      if (route.useReasoning || route.useEscalation || route.useOss) {
        const r = Object.assign({}, route);
        r.useReasoning = false;
        r.useEscalation = false;
        r.useOss = false;
        r.useModel = true;
        r.lane = "chat8b";
        if (!r.text) r.prompt = r.prompt || query;
        return r;
      }
      return route;
    }
    // Template/instant routes already have staff-facing text — keep fast path.
    if (route.text && String(route.text).trim()) return route;
    if (route.useProactiveBriefing) return route;
    const intentEarly = String(route.intent || "");
    if (/^(capability:|registry:|help$|priorities$|navigate:|imports:)/.test(intentEarly)) return route;
    if (
      typeof HalIndependentThought !== "undefined" &&
      HalIndependentThought.isFastTextRoute &&
      HalIndependentThought.isFastTextRoute(route, query)
    ) {
      return route;
    }
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
      // Hybrid: prefer on-demand coder32b for agent/programming; fall back to reason21b.
      const preferCoder = ap.preferCoderForAgentLoop !== false;
      const coderReady = typeof ctx.coderModelReady === "function" && ctx.coderModelReady();
      if (preferCoder && coderReady) {
        r.useReasoning = true;
        r.useModel = false;
        r.useCoder = true;
        r.lane = ap.coderLane || "coder32b";
        r.intent = "reasoning: agent-loop-coder";
      } else if (reason21bAvailable(ctx)) {
        r.useReasoning = true;
        r.useModel = false;
        r.useCoder = false;
        r.lane = "reason21b";
        r.intent = "reasoning: agent-loop";
      } else {
        r.useReasoning = false;
        r.useModel = true;
        r.useCoder = false;
        r.lane = "chat8b";
        r.intent = "model: query";
      }
      r.useEscalation = false;
      r.useOss = false;
      r.text = "";
      r.prompt = r.prompt || query;
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
    if (intent === "imports: status" && route.useImportStatus) return route;
    if (route.useEmployeeStatus || route.useEmployeeWorkLog) return route;
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

  function fastChatSkipsProgramContext(route, ctx) {
    if (workstationFastHalActive()) return true;
    if (typeof HalChat9000 !== "undefined" && ctx && HalChat9000.isEnabled(ctx.halModels) && HalChat9000.config(ctx.halModels).alwaysGatherTools !== false) {
      return false;
    }
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
    ctx.cloudHalEnabled = await cloudHalEnabledAsync(ctx);
    let combinedPrompt = agentPrompt;
    if (!fastChatSkipsProgramContext(route, ctx) && !snapshotToolRan) {
      const programContext = await ctx.getProgramContextText();
      if (programContext) combinedPrompt += "\n\nProgram context:\n" + programContext.slice(0, ctxCap);
    }
    if (typeof HalImportReadiness !== "undefined" && HalImportReadiness.buildImportReadinessContext) {
      const db = typeof DesktopBridge !== "undefined" ? DesktopBridge : null;
      if (db && typeof db.getImportReadiness === "function") {
        const readiness = await db.getImportReadiness();
        const block = HalImportReadiness.buildImportReadinessContext(readiness);
        if (block) combinedPrompt = block + "\n\n" + combinedPrompt;
      }
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
    const useCloudAgent =
      plan &&
      plan.agentToolLoop &&
      cloudAgentEligible(plan, ctx) &&
      (!browserCloudHalBlocked() || (await cloudHalEnabledAsync(ctx)));
    if (useCloudAgent && browserCloudHalBlocked() && !(await cloudHalEnabledAsync(ctx))) {
      return {
        text: "Cloud HAL is disabled. Enable it from server settings with operator confirmation (ENABLE CLOUD HAL).",
        lane: "cloud · blocked",
      };
    }
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
      const preferCoder = agentCfg.preferCoderForAgentLoop !== false;
      const coderReady = typeof ctx.coderModelReady === "function" && ctx.coderModelReady();
      let rm;
      let laneLabel = "reason21b";
      if (preferCoder && coderReady && typeof ctx.coderModelConfig === "function") {
        rm = Object.assign({ reasoningLane: true, agentLoop: true, coderLane: true }, ctx.coderModelConfig());
        laneLabel = agentCfg.coderLane || "coder32b";
      } else {
        rm = Object.assign({ reasoningLane: true, agentLoop: true }, ctx.reasoningModelConfig());
      }
      rm.options = Object.assign({}, rm.options || {}, { num_predict: 1800 });
      rm = attachOllamaNativeTools(rm, plan, query, agentCfg);
      const raw = await ctx.runModel(rm, combinedPrompt, userText, "Agent loop reasoning", onToken);
      if (raw && typeof raw === "object" && (raw.toolCalls || raw.text != null)) {
        return {
          text: String(raw.text || ""),
          toolCalls: raw.toolCalls || [],
          lane: laneLabel,
        };
      }
      const text = typeof raw === "string" ? raw : String((raw && raw.text) || "");
      return { text, lane: laneLabel };
    }
    if (route.useReasoning) {
      // Hybrid agent-loop-coder: use on-demand coder32b when route.useCoder is set.
      if (route.useCoder && typeof ctx.coderModelReady === "function" && ctx.coderModelReady() && typeof ctx.coderModelConfig === "function") {
        const cm = Object.assign({ reasoningLane: true, coderLane: true }, ctx.coderModelConfig());
        const cmTools = plan && plan.agentToolLoop ? attachOllamaNativeTools(cm, plan, query, agentCfg) : cm;
        try {
          const raw = await ctx.runModel(cmTools, combinedPrompt, userText, "Local coder agent", onToken);
          const text = typeof raw === "string" ? raw : String((raw && raw.text) || "");
          const toolCalls = raw && typeof raw === "object" ? raw.toolCalls : null;
          if (String(text || "").trim() || (toolCalls && toolCalls.length)) {
            return {
              text,
              toolCalls: toolCalls || [],
              lane: agentCfg.coderLane || "coder32b",
            };
          }
        } catch (error) {
          if (typeof RuntimeIssues !== "undefined") {
            RuntimeIssues.record("hal-agent.coder", error, { lane: route.lane, intent: route.intent });
          }
        }
        // Fall through to reason21b if coder fails.
      }
      if (!ctx.reasoningModelReady()) {
        if (ctx.localModelReady && ctx.localModelReady()) {
          const lm = Object.assign({ fastChat: true, reasonFallback: true }, ctx.localModelConfig());
          const text = await ctx.runModel(lm, combinedPrompt, userText, "Local chat fallback", onToken);
          return { text, lane: "chat8b" };
        }
        return { text: ctx.offlineModelMessage("reason21b"), lane: "reason21b · offline" };
      }
      const rm = Object.assign({ reasoningLane: true }, ctx.reasoningModelConfig());
      const rmTools = plan && plan.agentToolLoop ? attachOllamaNativeTools(rm, plan, query, agentCfg) : rm;
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

  async function spawnParallelInvestigations(ctx, focuses, parentQuery) {
    const list = (focuses || []).filter(Boolean).slice(0, 2);
    if (!list.length) return null;
    const results = await Promise.all(
      list.map((focus) =>
        spawnInvestigationSubtask(
          ctx,
          /\banalyze\b/i.test(focus) ? focus : "Analyze " + focus + " and tell me what's missing from imports.",
          parentQuery,
        ),
      ),
    );
    const ok = results.filter((r) => r && r.ok);
    if (!ok.length) {
      return { ok: false, summary: "Parallel sub-investigations did not return usable answers." };
    }
    const summary = ok
      .map((r, i) => "### Focus " + (i + 1) + "\n" + String(r.summary || "").slice(0, 1400))
      .join("\n\n");
    return {
      ok: true,
      summary: summary.slice(0, 2800),
      parallel: list.length,
      loopTurns: ok.reduce((n, r) => n + (Number(r.loopTurns) || 0), 0),
    };
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
    const useCoder =
      route &&
      route.useCoder &&
      typeof ctx.coderModelReady === "function" &&
      ctx.coderModelReady() &&
      typeof ctx.coderModelConfig === "function";
    const useReason =
      !useCoder &&
      route &&
      route.useReasoning &&
      typeof ctx.reasoningModelReady === "function" &&
      ctx.reasoningModelReady();
    if (!useCoder && !useReason && (!ctx.localModelReady || !ctx.localModelReady())) return null;
    const lm = useCoder
      ? Object.assign({ reasoningLane: true, coderLane: true }, ctx.coderModelConfig())
      : useReason
        ? Object.assign({ reasoningLane: true }, ctx.reasoningModelConfig())
        : Object.assign({ fastChat: true }, ctx.localModelConfig());
    const system =
      typeof HalCursorParity !== "undefined" && HalCursorParity.rewriteShapeSystemPrompt
        ? HalCursorParity.rewriteShapeSystemPrompt()
        : "Rewrite HAL's reply for staff chat. Clear, direct, collaborative — like a strong coding agent explaining to a colleague. Proportional depth. Answer in the first sentence. No markdown unless discussing source code, no numbered lists unless they asked for a plan, no internal jargon, no echoing the question, no filler closings. Keep evidence and recommendations from the draft.";
    const user = `Question: ${query}\n\nDraft to rewrite:\n${String(draftText || "").slice(0, 1400)}`;
    try {
      const text = await ctx.runModel(lm, system, user, "Shape repair");
      return typeof HalCore !== "undefined" && HalCore.cleanModelText ? HalCore.cleanModelText(text) : text;
    } catch {
      return null;
    }
  }

  function attachPendingConsentChips(outcome, toolResults) {
    if (!outcome || typeof HalConsent === "undefined") return outcome;
    let pending = null;
    if (typeof HalConsent.getPending === "function") {
      try {
        pending = HalConsent.getPending();
      } catch {
        pending = null;
      }
    }
    if (!pending && toolResults) {
      for (const res of Object.values(toolResults)) {
        if (res && res.pendingConsent) {
          pending = res.pendingConsent;
          break;
        }
      }
    }
    if (pending && typeof HalConsent.followUpChips === "function") {
      outcome.followUpChips = HalConsent.followUpChips(pending);
      if (typeof HalConsent.wrapReplyWithConsent === "function" && outcome.text) {
        outcome.text = HalConsent.wrapReplyWithConsent(outcome.text, pending);
      }
    }
    return outcome;
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
    attachPendingConsentChips(outcome, toolResults);
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

  async function composeAboutMeInterview(ctx) {
    const interviewMode = typeof globalThis !== "undefined" && globalThis._halInterviewMode;
    const aboutQuery =
      typeof HalAboutMe !== "undefined" && HalAboutMe.queryText ? HalAboutMe.queryText() : aboutMeQueryFallback();
    const route = { intent: "ops: hal-about-me", lane: "chat8b", useHalAboutMe: true, text: "", actions: [] };
    const toolIds = interviewMode
      ? ["read_current_context", "read_registry"]
      : ["read_current_context", "read_program_snapshot", "read_registry", "read_source_health"];
    const toolResults = await runTools(toolIds, ctx, aboutQuery);
    const plan = {
      questionType: "about",
      originalQuery: aboutQuery,
      tools: toolIds,
      useModelEnhancement: false,
      agentToolLoop: false,
      lane: "local",
      intent: route.intent,
      budget: AGENT_BUDGET,
    };
    let text = "";
    const synth = buildToolSynthesisOutcome(aboutQuery, plan, toolResults, route, ctx);
    text = synth && synth.text ? synth.text : "";
    if (!text) {
      text =
        "I read the local registry and import bundle — staff drive outbound steps while I stay read-only. " +
        "Ask about a specific page or import status for a narrower read on this office. " +
        "Nothing external runs without your consent on each action.";
    }
    if (typeof HalCore !== "undefined" && HalCore.countSentences && HalCore.countSentences(text) < 3) {
      text = HalCore.ensureMinSentences(text, aboutQuery, route, { halModels: ctx.halModels, skipMinSentences: false });
    }
    return { text, lane: "local", actions: [], intent: route.intent };
  }

  function aboutMeQueryFallback() {
    if (typeof HalIndependentThought !== "undefined" && HalIndependentThought.aboutMeQuery) {
      return HalIndependentThought.aboutMeQuery();
    }
    return "Who am I to you, and what is your independent read of this office right now?";
  }

  async function processQuery(query, ctx) {
    const trimmed = String(query).trim();
    if (!trimmed) return null;
    const routeQuery = ctx && ctx.routeQuery ? String(ctx.routeQuery).trim() : trimmed;
    const startedAt = Date.now();

    // Lazy memory: load once per session, never on the per-query hot path again.
    if (!memoryLoaded) await loadMemory(ctx);
    workingMemory.currentPage = ctx.getCurrentPage ? ctx.getCurrentPage() : null;
    workingMemory.activeWorkSession = !!(ctx.halWorkSession);
    recordTurn("user", trimmed, { focus: workingMemory.currentPage });

    if (typeof HalImportReadiness !== "undefined" && HalImportReadiness.guardBeforeModel) {
      const readinessBlock = await HalImportReadiness.guardBeforeModel(trimmed, ctx);
      if (readinessBlock) {
        recordTurn("hal", readinessBlock.text, { intent: readinessBlock.intent || "readiness:import-stale", tools: [] });
        saveMemory(ctx);
        return readinessBlock;
      }
    }

    let route = downgradeRouteIfReasoningOffline(
      applyHigherReasoningRoute(HalCore.routeHalCommand(ctx.halData, ctx.halModels, ctx.pages, routeQuery), routeQuery, ctx),
      ctx,
    );

    const fastTextRoute =
      typeof HalIndependentThought !== "undefined" &&
      HalIndependentThought.isFastTextRoute &&
      HalIndependentThought.isFastTextRoute(route, routeQuery);
    if (fastTextRoute) {
      const fastPlan = {
        questionType: classifyQuestion(trimmed, route),
        originalQuery: trimmed,
        tools: [],
        useModelEnhancement: false,
        lane: route.lane,
        intent: route.intent || "",
        budget: AGENT_BUDGET,
      };
      const fast = await ctx.executeRoute(route, trimmed, {});
      if (fast) {
        let checked = selfCheckResponse(trimmed, fast.text, fastPlan, {}, route);
        if (!checked.pass && checked.repaired) fast.text = checked.repaired;
        finalizeOutcome(fast, trimmed, route, fastPlan, ctx, {});
        recordTurn("hal", fast.text, { intent: fast.intent || route.intent, tools: [] });
        saveMemory(ctx);
        return Object.assign({}, fast, {
          plan: fastPlan,
          toolResults: {},
          selfCheck: { pass: true, issues: [], instant: true, fastText: true },
        });
      }
    }

    if (typeof HalIndependentThought !== "undefined" && HalIndependentThought.enhanceRoute) {
      route = HalIndependentThought.enhanceRoute(route, ctx.halModels, trimmed);
    }
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

    // Instant local-command path (disabled when independent thought — no canned script replies).
    const skipFast =
      typeof HalIndependentThought !== "undefined" &&
      HalIndependentThought.shouldSkipFastExecutor(ctx.halModels, trimmed, route);
    if (!skipFast && !isModelLane && !plan.useModelEnhancement && (!plan.tools || plan.tools.length === 0)) {
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

    let toolResults = plan.tools && plan.tools.length ? await runTools(plan.tools, ctx, trimmed) : {};
    let activePlan = plan;
    const agentCfg = (ctx.halModels && ctx.halModels.config && ctx.halModels.config.agentProgramming) || {};

    if (
      plan.useModelEnhancement &&
      (isInvestigateQuery(trimmed, route) || wantsInsuranceOpsTools(trimmed))
    ) {
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
      (isComplexInvestigationQuery(trimmed, route) || isMultiAnalyzeQuery(trimmed)) &&
      !toolResults.spawn_investigation
    ) {
      const analyzeTargets = extractAnalyzeTargets(trimmed);
      if (ctx.onToolProgress) {
        ctx.onToolProgress({
          phase: "start",
          tool: "spawn_investigation",
          label: analyzeTargets ? "Parallel sub-investigations" : "Sub-investigation",
        });
      }
      toolResults.spawn_investigation = analyzeTargets
        ? await spawnParallelInvestigations(ctx, analyzeTargets, trimmed)
        : await spawnInvestigationSubtask(ctx, extractSubInvestigationFocus(trimmed), trimmed);
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
    shouldUseAgentToolLoop,
    wantsOllamaNativeTools,
    attachOllamaNativeTools,
    cloudAgentEligible,
    agentLoopToolIds,
    buildPlan,
    runTools,
    selfCheckResponse,
    buildAgentSystemPrompt,
    isFastChatRoute,
    fastChatSkipsProgramContext,
    workstationFastHalActive,
    processQuery,
    composeAboutMeInterview,
    loadMemory,
    saveMemory,
    getWorkingMemory,
    getLongTermMemory,
    getRepairLog,
    getHealth,
    getLastWebResearch,
    getApprovedMemories,
    updatePreferences,
    setOMPatientContext,
    getOMPatientContext,
    logRepair,
    parsePatchFromQuery,
    isTaskCompletionQuery,
    shouldRunPostValidation,
    synthesizeAnswerFromTools,
    isInvestigateQuery,
    isComplexInvestigationQuery,
    isMultiAnalyzeQuery,
    extractAnalyzeTargets,
    spawnInvestigationSubtask,
    spawnParallelInvestigations,
    wantsInsuranceOpsTools,
    expandGatherToolsForRound,
    toolResultLooksEmpty,
    needsMoreGather,
  };
})();

if (typeof window !== "undefined") window.HalAgent = HalAgent;
if (typeof module !== "undefined" && module.exports) module.exports = HalAgent;
