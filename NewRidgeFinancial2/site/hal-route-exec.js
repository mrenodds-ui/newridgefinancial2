/**
 * HAL route executor — runs routed intents into local outcomes (no chat UI).
 * Used by HalAgent after planning and tool enrichment.
 */
const HalRouteExec = (function () {
  function resolveImportCoordinator() {
    if (typeof globalThis !== "undefined" && globalThis.ImportCoordinator) return globalThis.ImportCoordinator;
    if (typeof ImportCoordinator !== "undefined") return ImportCoordinator;
    return null;
  }

  async function resolveOfficeTasks(ctx) {
    if (ctx && typeof ctx.getOfficeTasks === "function") return ctx.getOfficeTasks();
    const snapshot = ctx && typeof ctx.loadProgramSnapshot === "function" ? await ctx.loadProgramSnapshot() : null;
    return (snapshot && snapshot.officeTasks) || (ctx && ctx.halOfficeTasks) || [];
  }

  function outcome(text, lane, intent, actions, extra) {
    return Object.assign(
      {
        text: text || "",
        lane: lane || "local",
        intent: intent || "unknown",
        actions: actions || [],
      },
      extra || {},
    );
  }

  async function execute(result, trimmed, toolResults, ctx) {
    if (result.useEscalation || result.useReasoning || result.useModel) return null;

    if (result.useProgramSnapshot) {
      const snapshot = await ctx.loadProgramSnapshot();
      const text = snapshot
        ? HalCore.formatProgramSnapshot(snapshot, ctx.halData)
        : "Program snapshot unavailable. Services layer is not loaded.";
      return outcome(text, "program", result.intent);
    }

    if (result.useProactiveBriefing) {
      const Proactive = typeof HalProactive !== "undefined" ? HalProactive : window.HalProactive;
      if (!Proactive) return outcome("Proactive HAL manager is not loaded.", "hal", result.intent);
      const briefing =
        (ctx.runProactiveCycle && (await ctx.runProactiveCycle())) ||
        Proactive.getLastBriefing() ||
        (await Proactive.runCycle(ctx));
      const text = briefing ? Proactive.formatProactiveBriefing(briefing) : "Proactive briefing unavailable.";
      return outcome(text, "hal", result.intent, [], { refreshHal: true });
    }

    if (result.useImportRefresh || result.useImportStatus) {
      const desktop = typeof DesktopBridge !== "undefined" ? DesktopBridge : window.DesktopBridge;
      if (!desktop || !desktop.hasDesktopApi || !desktop.hasDesktopApi()) {
        const message =
          desktop && desktop.desktopRequiredMessage
            ? desktop.desktopRequiredMessage("Import status and refresh")
            : "Import status and refresh require the NR2 desktop app. Browser mode is a UI preview only.";
        return outcome(message, "imports", result.intent, [], { refreshHal: false });
      }
      const Svc = ctx.Services;
      let text = "Import loader is not available in this runtime.";
      if (Svc && ctx.ImportLoader) {
        let bundle = null;
        let refreshError = null;
        if (result.useImportRefresh) {
          const coord = resolveImportCoordinator();
          try {
            if (coord) {
              bundle = await coord.refresh({ reason: "hal-route" });
            } else if (typeof Svc.refreshImports === "function") {
              bundle = await Svc.refreshImports();
            }
          } catch (err) {
            refreshError = err;
            if (typeof Svc.loadImportBundle === "function") {
              bundle = await Svc.loadImportBundle();
            }
          }
          if (bundle) {
            if (typeof Svc.invalidateSnapshot === "function") Svc.invalidateSnapshot();
            ctx.clearProgramContextCache();
            await ctx.refreshHalWidgetFeed(await ctx.loadProgramSnapshot());
          }
        } else if (typeof Svc.loadImportBundle === "function") {
          bundle = await Svc.loadImportBundle();
        }
        text = ctx.ImportLoader.formatImportStatus(bundle);
        if (result.useImportRefresh && bundle) {
          text += "\n\nImport cache refreshed. Widgets and dashboards now use the latest local export files.";
        }
        if (refreshError) {
          text += `\n\nRefresh error: ${refreshError.message || refreshError}`;
        }
      }
      return outcome(text, "imports", result.intent, [], { refreshHal: true });
    }

    if (result.useSourceHealth) {
      const snapshot = await ctx.loadProgramSnapshot();
      const feed =
        (snapshot && snapshot.widgets) || (window.HalSkills && HalSkills.buildWidgetFeed(snapshot)) || ctx.halWidgetFeed || {};
      const staticItems = (ctx.halData.sources && ctx.halData.sources.items) || [];
      let text = HalSkills.formatSourceHealthText(feed.sourceHealth, staticItems);
      const issues = snapshot && snapshot.runtimeIssues;
      if (issues && issues.length) {
        text += "\n\nRuntime issues:\n" + issues.map((item) => `- ${item.source}: ${item.message}`).join("\n");
      }
      return outcome(text, "sources", result.intent, [], { refreshHal: false });
    }

    if (result.useJournalDraft) {
      const req = result.journalRequest || {};
      let text;
      if (req.amount == null || isNaN(req.amount) || req.amount <= 0) {
        text =
          "I can draft a journal entry locally (draft only — never posted). Tell me the amount and the type, e.g. " +
          '"Draft a journal entry for $1,200 prepaid insurance" or include a period like 2025-05.';
      } else {
        const draft = HalSkills.draftAndValidateJournal({
          description: req.description,
          period: req.period,
          amount: req.amount,
          context: {},
        });
        text = HalSkills.formatJournalDraft(draft);
      }
      return outcome(text, "accounting", result.intent);
    }

    if (result.useClaimReadiness) {
      const tool = toolResults && toolResults.read_claims_summary;
      const text = tool && tool.ok ? tool.summary : null;
      if (text) return outcome(text, "claims", result.intent);
      const snapshot = await ctx.loadProgramSnapshot();
      const claimsList = (snapshot && snapshot.claims && snapshot.claims.top) || [];
      const resp = HalSkills.buildClaimReadinessResponse(claimsList);
      return outcome(HalSkills.formatClaimReadinessAnswer(resp), "claims", result.intent);
    }

    if (result.useOfficeAttention) {
      const snapshot = await ctx.loadProgramSnapshot();
      const tasks = await resolveOfficeTasks(ctx);
      const metrics = HalSkills.computeTaskMetrics(tasks);
      const resp = HalSkills.buildOfficeManagerAttention(snapshot, metrics);
      return outcome(HalSkills.formatOfficeManagerAttention(resp), "office", result.intent);
    }

    if (result.useOfficeBriefing) {
      const officeApi =
        typeof HalOfficeManager !== "undefined"
          ? HalOfficeManager
          : typeof window !== "undefined" && window.HalOfficeManager
            ? window.HalOfficeManager
            : null;
      if (!officeApi) return outcome("Office manager briefing unavailable.", "office", result.intent);
      const tool = toolResults && toolResults.read_office_briefing;
      if (tool && tool.summary) return outcome(tool.summary, "office", result.intent, [], { refreshHal: true });
      const snapshot = await ctx.loadProgramSnapshot();
      const briefing = window.HalProactive && HalProactive.getLastBriefing ? HalProactive.getLastBriefing() : null;
      const state =
        (briefing && briefing.officeManager) ||
        officeApi.buildOfficeManagerState(snapshot, ctx, briefing || { officePriorities: officeApi.buildOfficePriorities(snapshot, ctx) });
      return outcome(officeApi.formatDailyOfficeBriefing(state, snapshot), "office", result.intent, [], { refreshHal: true });
    }

    if (result.useTaskList) {
      const tasks = await resolveOfficeTasks(ctx);
      const metrics = HalSkills.computeTaskMetrics(tasks);
      const lines = [
        `Local office tasks (${tasks.length}) — local only; HAL reads SoftDent and QuickBooks only:`,
        `Open ${metrics.openCount} · In progress ${metrics.inProgressCount} · Blocked ${metrics.blockedCount} · Completed ${metrics.completedCount}`,
      ];
      if (!tasks.length) {
        lines.push("", 'No tasks yet. Say "Create a task: follow up on denied claim" to add one.');
      } else {
        lines.push("");
        tasks.slice(0, 12).forEach((t) => lines.push(`- [${t.status}] (${t.priority}) ${t.title}`));
      }
      return outcome(lines.join("\n"), "office", result.intent);
    }

    if (result.useSideNoteMonitor) {
      ctx.refreshSideNoteMonitor();
      return outcome(
        HalSkills.formatSideNoteMonitor(ctx.halSideNoteMonitor, ctx.halSideNotes || []),
        "sidenotes",
        result.intent,
        [],
        { refreshHal: true },
      );
    }

    if (result.useSideNoteList) {
      return outcome(HalSkills.formatSideNotesList(ctx.halSideNotes || []), "sidenotes", result.intent);
    }

    if (result.useSideNoteCreate) {
      let text = "";
      const noteText = result.sideNoteText || "";
      if (noteText.length < 2) {
        text =
          'I can add a local sidenote (local only; HAL reads SoftDent and QuickBooks only). Say "Add sidenote: recall patient about claim" or type in the sidenotes panel below.';
      } else {
        try {
          const note = ctx.addSideNote(noteText);
          text =
            `Local sidenote added (local only, not_submitted): "${note.text.slice(0, 120)}".\n` +
            `HAL is monitoring ${(ctx.halSideNotes || []).filter((n) => n.status !== "archived").length} active sidenote(s).`;
        } catch (err) {
          text = `Could not add sidenote: ${err.message || err}`;
        }
      }
      return outcome(text, "sidenotes", result.intent, [], { refreshHal: true });
    }

    async function widgetFeed() {
      const tool = toolResults && toolResults.read_widget_feed;
      if (tool && tool.feed) return tool.feed;
      const snapshot = await ctx.loadProgramSnapshot();
      return (snapshot && snapshot.widgets) || HalSkills.buildWidgetFeed(snapshot);
    }

    if (result.useWidgetFeed) {
      const feed = await widgetFeed();
      ctx.setHalWidgetFeed(feed);
      return outcome(HalSkills.formatWidgetFeed(feed), "widgets", result.intent, [], { refreshHal: true });
    }

    if (result.useWidgetContract) {
      const contract =
        typeof WidgetContract !== "undefined"
          ? WidgetContract
          : typeof window !== "undefined" && window.WidgetContract
            ? window.WidgetContract
            : null;
      const text =
        contract && typeof contract.formatAllContractsForHal === "function"
          ? contract.formatAllContractsForHal()
          : "Widget contract unavailable.";
      return outcome(text, "widgets", result.intent, [], { refreshHal: true });
    }

    if (result.useWidgetFillSuggestions) {
      const feed = await widgetFeed();
      ctx.setHalWidgetFeed(feed);
      return outcome(HalSkills.formatWidgetFillSuggestions(feed), "widgets", result.intent, [], { refreshHal: true });
    }

    if (result.useWidgetGuidance) {
      const snapshot = await ctx.loadProgramSnapshot();
      const feed = await widgetFeed();
      ctx.setHalWidgetFeed(feed);
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
      return outcome(formatter(), "widgets", result.intent, [], { refreshHal: true });
    }

    if (result.useWidgetShow && result.widgetKey) {
      const feed = await widgetFeed();
      ctx.setHalWidgetFeed(feed);
      return outcome(
        HalSkills.formatWidgetDetail(feed, result.widgetKey),
        "widgets",
        result.intent,
        [{ label: "Open related page", page: feed.widgets[result.widgetKey]?.navTarget || "" }],
        { refreshHal: true },
      );
    }

    if (result.useDocRag) {
      const tool = toolResults && toolResults.search_document_library;
      if (tool && tool.ok && tool.summary) return outcome(tool.summary, "library", result.intent);
      const snapshot = await ctx.loadProgramSnapshot();
      const docs = (snapshot && snapshot.library && (snapshot.library.top || snapshot.library.docs)) || [];
      const rag = HalSkills.answerFromLibrary(result.ragQuestion, docs, 4);
      return outcome(HalSkills.formatRagResult(rag), "library", result.intent);
    }

    if (result.useTaskCreate) {
      let text;
      const taskTitle = String(result.taskTitle || "").trim();
      if (taskTitle.length < 3) {
        text =
          'I can add a local office task (local only; HAL reads SoftDent and QuickBooks only). Tell me the task title, e.g. "Create a task: follow up on denied claim" or use the Tasks panel below.';
      } else {
        try {
          const task = HalSkills.createTask({ title: taskTitle, category: "other" }, { actor: "local-user" });
          ctx.addOfficeTask(task);
          text =
            `Local task created (local only, not_submitted): "${task.title}".\n` +
            `Status: ${task.status} · Priority: ${task.priority}. Local only; HAL reads SoftDent and QuickBooks only.`;
        } catch (error) {
          text = "Could not create the task: " + (error && error.message ? error.message : "invalid task.");
        }
      }
      return outcome(text, "office", result.intent, [], { refreshPanel: true });
    }

    if (result.useSessionStart && result.sessionId) {
      ctx.startWorkSession(result.sessionId);
      return outcome(
        result.text + "\n\n" + ctx.workSessionStatusText(),
        "session",
        result.intent,
        ctx.normalizeActions(result.actions),
        { refreshPanel: true },
      );
    }

    if (result.useSessionReset) {
      ctx.resetWorkSession();
      return outcome(result.text, "session", result.intent, [], { refreshPanel: true });
    }

    if (result.useSessionShow) {
      const text = ctx.halWorkSession
        ? ctx.workSessionStatusText() + "\n\nUse the Work Session panel to mark checks complete or draft a handoff note."
        : 'No active work session. Say "Start claims review" or use the Work Session panel.';
      return outcome(text, "session", result.intent);
    }

    if (result.useSessionHandoff) {
      if (!ctx.halWorkSession) {
        return outcome("No active work session to draft a handoff note from.", "session", result.intent, [], { refreshPanel: true });
      }
      ctx.draftSessionHandoff();
      return outcome(ctx.halWorkSession.handoffNote, "session", result.intent, [], { refreshPanel: true });
    }

    if (result.usePacketBuild) {
      if (!ctx.halWorkSession) {
        return outcome(
          'No active work session. Start a session first (for example, "Start claims review"), then build an evidence packet.',
          "packet",
          result.intent,
          [],
          { refreshPanel: true },
        );
      }
      const packet = ctx.buildEvidencePacketFromSession();
      return outcome(packet ? packet.text : "Could not build evidence packet.", "packet", result.intent, [], { refreshPanel: true });
    }

    if (result.usePacketShow) {
      const text = ctx.halEvidencePacket
        ? ctx.halEvidencePacket.text
        : 'No evidence packet built yet. Start a work session and say "Build evidence packet".';
      return outcome(text, "packet", result.intent);
    }

    if (result.usePacketClear) {
      ctx.clearEvidencePacket();
      return outcome(result.text, "packet", result.intent, [], { refreshPanel: true });
    }

    if (result.useReadinessRun) {
      const report = ctx.runReadinessDiagnostics();
      return outcome(HalCore.formatReadinessSummary(report), "readiness", result.intent, [], { refreshPanel: true });
    }

    if (result.useReadinessGate) {
      if (!ctx.halReadinessDiagnostics) ctx.runReadinessDiagnostics();
      return outcome(ctx.staffUseGateText(), "readiness", result.intent, [], { refreshPanel: true });
    }

    if (result.useReadinessShow) {
      const text = ctx.halReadinessDiagnostics
        ? HalCore.formatReadinessSummary(ctx.halReadinessDiagnostics)
        : 'No diagnostics available yet. Say "Run readiness check" or use the Readiness panel.';
      return outcome(text, "readiness", result.intent);
    }

    if (result.useReadinessClear) {
      ctx.clearReadinessDiagnostics();
      return outcome(result.text, "readiness", result.intent, [], { refreshPanel: true });
    }

    if (result.useSmokeTest) {
      const report = ctx.runOperatorSmokeTest();
      return outcome(HalCore.formatSmokeTestSummary(report), "operator", result.intent, [], { refreshPanel: true });
    }

    if (result.useHandoffSummary) {
      return outcome(ctx.staffHandoffSummaryText(), "operator", result.intent);
    }

    if (result.intent === "firewall" && toolResults && toolResults.explain_firewall && toolResults.explain_firewall.summary) {
      return outcome(toolResults.explain_firewall.summary, result.lane, result.intent, result.actions);
    }

    return outcome(result.text, result.lane, result.intent, result.actions);
  }

  return { execute };
})();

if (typeof window !== "undefined") window.HalRouteExec = HalRouteExec;
if (typeof module !== "undefined" && module.exports) module.exports = HalRouteExec;
