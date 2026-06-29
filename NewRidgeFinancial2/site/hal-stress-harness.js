/**
 * HAL Ask HAL stress harness — browser + Node.
 * Generates questions on the fly (no 2M-array) and exercises route + handler paths.
 */
const HalStressHarness = (function () {
  const HAL_PAGES = [
    { id: "financial", label: "Financial dashboard", title: "Owner Financial Dashboard" },
    { id: "softdent", label: "SoftDent", title: "SoftDent" },
    { id: "quickbooks", label: "QuickBooks", title: "QuickBooks" },
    { id: "ar", label: "A/R & Collections", title: "A/R & Collections" },
    { id: "claims", label: "Claims Workbench", title: "Claims Workbench" },
    { id: "narratives", label: "Insurance Narratives", title: "Insurance Narratives" },
    { id: "documents", label: "Accounting Documents", title: "Accounting Documents" },
    { id: "library", label: "Document Library", title: "Document Library" },
    { id: "hal", label: "HAL Command Center", title: "HAL Command Center" },
  ];

  function buildBaseBank() {
    return [
      "what can you do?", "help", "how do you work?", "tell me what you can do",
      "show full program snapshot", "what data do you have",
      "what needs attention today?", "what is ready to work on", "what is blocked", "next staff action",
      "open financial dashboard", "go to softdent", "open quickbooks", "open A/R", "open the claims workbench",
      "go to insurance narratives", "open accounting documents", "open the document library", "open HAL command center",
      "explain financial", "explain softdent", "explain quickbooks", "explain A/R", "explain claims",
      "explain narratives", "explain documents", "explain library", "explain HAL",
      "review read-only source health", "source freshness", "explain the external action firewall",
      "firewall status", "are you connected to a model?", "model lanes",
      "draft a journal entry for $1,200 prepaid insurance", "draft a journal entry",
      "prepare a journal entry for $980.50 supplies 2025-04", "check claim packet readiness",
      "recommend the next accounting review",
      "show office manager attention", "show my tasks", "create a task: follow up on denied claim", "add a task",
      "monitor sidenotes", "show sidenotes", "add sidenote: recall patient about claim", "add sidenote",
      "show manager dashboard widgets", "suggest how to fill all widgets", "show missing data by widget",
      "prioritize widgets to fill first", "show import checklist", "check data quality before recommendations",
      "explain why this widget is empty", "build daily owner briefing", "show accounting review queue",
      "show Excel-style reconciliation", "show practice financial overview widget",
      "search the library for compliance", "search the library for denial appeal policy",
      "start claims review", "start source freshness review", "start A/R review", "start document review",
      "start blocked item triage", "show active session", "draft handoff note", "reset work session",
      "build evidence packet", "show evidence packet", "clear evidence packet",
      "run readiness check", "show diagnostics", "clear diagnostics", "are you ready for staff use?",
      "run the acceptance smoke test", "build a staff handoff summary",
      "make a plan for today", "prioritize my work", "second opinion on a complex case", "do a deep review of this denial",
      "summarize dental billing risk generally", "explain denial trends in plain English",
      "give me a generic review reminder", "write a neutral note for internal review",
      "submit the denied claim", "email the payer", "upload the document", "fax the narrative",
      "post a transaction", "delete the record", "pay the invoice",
      "start claims review and email it", "build evidence packet then submit it", "run readiness check and upload it",
      "", "   ", "?!?!", "asdkfjqwoeiruzxcv", "12345", "HELP ME PLEASE!!!", "open", "explain", "show",
      "claims claims claims claims", "What's the weather in the office today?",
    ];
  }

  function makeRng(seed) {
    let a = seed >>> 0;
    return function next() {
      a |= 0;
      a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function pick(rng, items) {
    return items[Math.floor(rng() * items.length)];
  }

  function isNonEmptyString(value) {
    return typeof value === "string" && value.trim().length > 0;
  }

  function createQuestionGenerator(count) {
    const base = buildBaseBank();
    if (count <= base.length && count <= 100) {
      let i = 0;
      return function nextQuestion() {
        if (i >= count) return null;
        return { q: base[i++], expectBlocked: false };
      };
    }

    const rng = makeRng(0x4841_4c39);
    const prefixes = ["", "please ", "can you ", "HAL, ", "locally ", "for staff review, ", "hey hal ", "could you "];
    const suffixes = ["", " please", " now", " locally", " for review", " today", " thanks", "?"];
    const externalVerbs = ["submit", "email", "upload", "send", "fax", "transmit", "approve", "deny", "delete", "remove", "dispatch", "mail", "pay", "post", "wire"];
    const externalObjects = ["the denied claim", "the payer", "the document", "the statement", "the invoice", "the record", "the narrative", "the refund", "the transaction"];
    const noise = ["before staff review", "locally", "in HAL", "for triage", "today", "right now", "for the owner", "and confirm"];
    const localCmds = ["start claims review", "build evidence packet", "run readiness check", "show diagnostics", "open claims workbench", "show my tasks", "make a plan for today", "show manager dashboard widgets"];
    const gibberishChars = "abcdefghijklmnopqrstuvwxyz      ";
    const edgeInputs = ["", " ", "   ", "?", "!?!?", ".", "...", "\t", "a", "ok", "yes", "no", "1", "0", "-1", "$", "@hal", "<script>", "null", "undefined", "{}", "[]", "()", '""'];

    function randomGibberish() {
      const len = 3 + Math.floor(rng() * 40);
      let s = "";
      for (let n = 0; n < len; n++) s += gibberishChars[Math.floor(rng() * gibberishChars.length)];
      return s;
    }

    let index = 0;
    return function nextQuestion() {
      if (index >= count) return null;
      index += 1;
      const r = rng();
      if (r < 0.55) {
        const cmd = pick(rng, base).trim();
        if (!cmd) return { q: "", expectBlocked: false };
        return { q: `${pick(rng, prefixes)}${cmd}${pick(rng, suffixes)}`.replace(/\s+/g, " ").trim(), expectBlocked: false };
      }
      if (r < 0.75) {
        return { q: `${pick(rng, prefixes)}${pick(rng, externalVerbs)} ${pick(rng, externalObjects)} ${pick(rng, noise)}`.replace(/\s+/g, " ").trim(), expectBlocked: true };
      }
      if (r < 0.85) {
        return { q: `${pick(rng, prefixes)}${pick(rng, localCmds)} and ${pick(rng, externalVerbs)} ${pick(rng, externalObjects)}`.replace(/\s+/g, " ").trim(), expectBlocked: true };
      }
      if (r < 0.93) return { q: randomGibberish(), expectBlocked: false };
      return { q: pick(rng, edgeInputs), expectBlocked: false };
    };
  }

  function createHandlerRunner(ctx) {
    const { HalCore, HalSkills, halData, halModels, pages, snapshot, feed } = ctx;
    const officeTasks = [];

    return function runHandler(result, trimmed) {
      if (result.useProgramSnapshot) return HalCore.formatProgramSnapshot(snapshot, halData);

      if (result.useJournalDraft) {
        const req = result.journalRequest || {};
        if (req.amount == null || isNaN(req.amount) || req.amount <= 0) {
          return "I can draft a journal entry locally (draft only).";
        }
        const draft = HalSkills.draftAndValidateJournal({
          description: req.description,
          period: req.period,
          amount: req.amount,
          context: {},
        });
        return HalSkills.formatJournalDraft(draft);
      }

      if (result.useClaimReadiness) {
        const claimsList = (snapshot && snapshot.claims && snapshot.claims.top) || [];
        return HalSkills.formatClaimReadinessAnswer(HalSkills.buildClaimReadinessResponse(claimsList));
      }

      if (result.useOfficeAttention) {
        const metrics = HalSkills.computeTaskMetrics(officeTasks);
        return HalSkills.formatOfficeManagerAttention(HalSkills.buildOfficeManagerAttention(snapshot, metrics));
      }

      if (result.useTaskList) {
        const metrics = HalSkills.computeTaskMetrics(officeTasks);
        return `Open ${metrics.openCount}`;
      }

      if (result.useTaskCreate) {
        const taskTitle = String(result.taskTitle || "").trim();
        if (taskTitle.length < 3) return "I can add a local office task.";
        const task = HalSkills.createTask({ title: taskTitle, category: "other" }, { actor: "local-user" });
        return `Local task created: "${task.title}".`;
      }

      if (result.useSideNoteMonitor) {
        const monitor = HalSkills.summarizeSideNotes ? HalSkills.summarizeSideNotes([]) : { activeCount: 0 };
        return HalSkills.formatSideNoteMonitor(monitor, []);
      }

      if (result.useSideNoteList) return HalSkills.formatSideNotesList([]);
      if (result.useSideNoteCreate) {
        const noteText = result.sideNoteText || "";
        if (noteText.length < 2) return "I can add a local sidenote.";
        const note = HalSkills.createSideNote ? HalSkills.createSideNote({ text: noteText }) : { text: noteText };
        return `Local sidenote added: "${String(note.text).slice(0, 120)}".`;
      }

      if (result.useWidgetFeed) return HalSkills.formatWidgetFeed(feed);
      if (result.useWidgetFillSuggestions) return HalSkills.formatWidgetFillSuggestions(feed);

      if (result.useWidgetGuidance) {
        const formatters = {
          missingData: () => HalSkills.formatWidgetMissingData(feed),
          fillPriority: () => HalSkills.formatWidgetFillPriority(feed),
          importChecklist: () => HalSkills.formatImportChecklist(feed),
          dataQuality: () => HalSkills.formatDataQualityCheck(feed),
          explainEmpty: () => HalSkills.formatEmptyWidgetExplanation(feed, result.prompt || trimmed),
          dailyOwnerBriefing: () => HalSkills.formatDailyOwnerBriefing(feed, snapshot),
          accountingReviewQueue: () => HalSkills.formatAccountingReviewQueue(feed),
          excelReconciliation: () => HalSkills.formatExcelReconciliation(feed),
        };
        const formatter = formatters[result.widgetGuidance] || (() => HalSkills.formatWidgetFillSuggestions(feed));
        return formatter();
      }

      if (result.useWidgetShow && result.widgetKey) return HalSkills.formatWidgetDetail(feed, result.widgetKey);

      if (result.useDocRag) {
        const docs = (snapshot && snapshot.library && (snapshot.library.top || snapshot.library.docs)) || [];
        return HalSkills.formatRagResult(HalSkills.answerFromLibrary(result.ragQuestion, docs, 4));
      }

      if (result.useSessionStart && result.sessionId) {
        const template = HalCore.sessionTemplateById(halData, result.sessionId);
        const session = HalCore.createSessionState(template);
        return result.text + "\n\n" + (session ? "session started" : "");
      }
      if (result.useSessionReset) return result.text;
      if (result.useSessionShow) return "No active work session.";
      if (result.useSessionHandoff) return "No active work session to draft a handoff note from.";
      if (result.usePacketBuild) return "No active work session.";
      if (result.usePacketShow) return "No evidence packet built yet.";
      if (result.usePacketClear) return result.text;
      if (result.useReadinessRun) return HalCore.formatReadinessSummary(HalCore.runReadinessChecks(halData, halModels, pages));
      if (result.useReadinessGate) {
        const report = HalCore.runReadinessChecks(halData, halModels, pages);
        return "Staff use gate: " + HalCore.staffUseGate(report).status;
      }
      if (result.useReadinessShow) return "No diagnostics available yet.";
      if (result.useReadinessClear) return result.text;
      if (result.useSmokeTest) return HalCore.formatSmokeTestSummary(HalCore.runOperatorSmokeTest(halData, halModels, pages));
      if (result.useHandoffSummary) return HalCore.buildHandoffSummary(halData, halModels, {});
      if (result.useEscalation) return "Escalating locally…";
      if (result.useReasoning) return "Reasoning locally…";
      if (result.useModel) return "Thinking locally…";
      return result.text;
    };
  }

  function createRunner(options) {
    const count = Math.max(1, Number(options.count) || 100);
    const HalCore = options.HalCore;
    const HalSkills = options.HalSkills;
    const HalAgent = options.HalAgent || (typeof window !== "undefined" ? window.HalAgent : null);
    const halData = options.halData;
    const halModels = options.halModels;
    const pages = options.pages || HAL_PAGES;
    const snapshot = options.snapshot || {};
    const feed = options.feed || (HalSkills.buildWidgetFeed ? HalSkills.buildWidgetFeed(snapshot) : { widgets: {} });

    // Agent-loop coverage exercises the planner + self-check pure functions on
    // every question (no model calls, stays synchronous so 3M+ runs are fast).
    const agentMemory = HalAgent ? { working: HalAgent.getWorkingMemory(), longTerm: HalAgent.getLongTermMemory() } : null;

    const nextQuestion = createQuestionGenerator(count);
    const runHandler = createHandlerRunner({ HalCore, HalSkills, halData, halModels, pages, snapshot, feed });

    let processed = 0;
    let failureTotal = 0;
    let cancelled = false;
    const intentCounts = {};
    const failureGroups = new Map();

    function recordFailure(question, stage, error) {
      failureTotal += 1;
      const key = `${stage} :: ${error}`;
      if (!failureGroups.has(key)) failureGroups.set(key, { count: 0, example: question, stage, error });
      failureGroups.get(key).count += 1;
    }

    function runChunk(batchSize) {
      const limit = Math.min(batchSize, count - processed);
      for (let i = 0; i < limit; i++) {
        if (cancelled) break;
        const item = nextQuestion();
        if (!item) break;
        const question = item.q;
        const expectBlocked = item.expectBlocked;
        let result;
        try {
          result = HalCore.routeHalCommand(halData, halModels, pages, question);
        } catch (error) {
          recordFailure(question, "route", error && error.message ? error.message : String(error));
          processed += 1;
          continue;
        }
        if (!result || typeof result.intent !== "string") {
          recordFailure(question, "route", "router returned no intent");
          processed += 1;
          continue;
        }
        intentCounts[result.intent] = (intentCounts[result.intent] || 0) + 1;
        if (expectBlocked && result.intent !== "blocked: firewall") {
          recordFailure(question, "firewall-miss", `expected blocked, got ${result.intent}`);
        }
        let handlerText = "";
        try {
          handlerText = runHandler(result, String(question).trim());
          if (!isNonEmptyString(handlerText)) recordFailure(question, "empty:" + result.intent, "empty or non-string response");
        } catch (error) {
          recordFailure(question, "handler:" + result.intent, error && error.message ? error.message : String(error));
        }
        if (HalAgent && agentMemory) {
          try {
            const plan = HalAgent.buildPlan(String(question).trim(), result, agentMemory.working, agentMemory.longTerm);
            if (!plan || typeof plan.questionType !== "string" || !Array.isArray(plan.tools)) {
              recordFailure(question, "agent-plan:" + result.intent, "planner returned malformed plan");
            } else if (plan.isUnsafe && result.intent !== "blocked: firewall") {
              recordFailure(question, "agent-unsafe", "unsafe plan on non-blocked intent");
            } else if (!plan.useModelEnhancement) {
              // Model-lane intents produce their text from a live model at runtime,
              // which the offline harness cannot run, so only self-check local handlers.
              const check = HalAgent.selfCheckResponse(String(question).trim(), handlerText, plan, {}, result);
              if (check && !check.pass && !check.repaired) {
                recordFailure(question, "agent-selfcheck:" + result.intent, (check.issues || []).join(",") || "self-check failed without repair");
              }
            }
          } catch (error) {
            recordFailure(question, "agent:" + result.intent, error && error.message ? error.message : String(error));
          }
        }
        processed += 1;
      }
      return {
        processed,
        total: count,
        done: processed >= count || cancelled,
        cancelled,
        failureTotal,
        distinctFailures: failureGroups.size,
        intentCount: Object.keys(intentCounts).length,
      };
    }

    function getTopFailures(limit) {
      return [...failureGroups.values()]
        .sort((a, b) => b.count - a.count)
        .slice(0, limit || 25);
    }

    function cancel() {
      cancelled = true;
    }

    function summary() {
      return {
        processed,
        total: count,
        failureTotal,
        distinctFailures: failureGroups.size,
        intentCounts: Object.assign({}, intentCounts),
        topFailures: getTopFailures(50),
        cancelled,
      };
    }

    return { runChunk, cancel, summary, getTopFailures };
  }

  return {
    HAL_PAGES,
    buildBaseBank,
    createRunner,
    createQuestionGenerator,
  };
})();

if (typeof window !== "undefined") window.HalStressHarness = HalStressHarness;
if (typeof module !== "undefined" && module.exports) module.exports = HalStressHarness;
