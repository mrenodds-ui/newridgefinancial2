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

  function extractRememberText(query) {
    const patterns = [
      /\bremember this[:.]?\s+(.+)$/i,
      /\bsave (?:this |that )?(?:to )?memory[:.]?\s+(.+)$/i,
      /\blearn(?:ing)?[:.]?\s+(.+)$/i,
    ];
    for (const pattern of patterns) {
      const match = String(query || "").match(pattern);
      if (match && match[1]) return match[1].trim();
    }
    return "";
  }

  async function execute(result, trimmed, toolResults, ctx) {
    if (result.useEscalation || result.useReasoning || result.useModel) return null;

    if (result.useChatRecap) {
      const turns =
        ctx.getWorkingTurns && typeof ctx.getWorkingTurns === "function"
          ? ctx.getWorkingTurns()
          : (ctx.getChatHistory || (() => []))().map((m) => ({ role: m.role, text: m.text }));
      const text =
        typeof HalCore !== "undefined" && HalCore.buildSessionRecap
          ? HalCore.buildSessionRecap(turns)
          : "Session recap is not available.";
      return outcome(text, "local", result.intent);
    }

    if (result.useProgramSnapshot) {
      const snapshot = await ctx.loadProgramSnapshot();
      const text = snapshot
        ? HalCore.formatProgramSnapshot(snapshot, ctx.halData)
        : "Program snapshot unavailable. Services layer is not loaded.";
      return outcome(text, "program", result.intent);
    }

    if (result.usePrint) {
      const PU = typeof PrintUtils !== "undefined" ? PrintUtils : typeof globalThis !== "undefined" ? globalThis.PrintUtils : null;
      if (!PU) return outcome("Print utilities are not loaded.", "print", result.intent);

      const scope = result.printScope || "auto";
      let printResult = { ok: false };

      if (scope === "snapshot") {
        const snapshot = await ctx.loadProgramSnapshot();
        printResult = PU.printSnapshot(snapshot, ctx.halData);
      } else if (scope === "widget-feed") {
        const feed = await widgetFeed();
        printResult = PU.printWidgetFeed(feed);
      } else if (scope === "widget" && result.widgetKey) {
        const feed = await widgetFeed();
        printResult = PU.printWidget(feed, result.widgetKey);
      } else if (scope === "drawer") {
        printResult = PU.printDrawer();
      } else if (scope === "hal-reply") {
        printResult = PU.printHalReply(ctx.halChatHistory || []);
      } else if (scope === "text") {
        printResult = PU.printText(result.printTitle || "Print", result.printText || trimmed);
      } else {
        printResult = PU.printCurrentView();
      }

      const label =
        scope === "text" && result.printText
          ? result.printText.slice(0, 48) + (result.printText.length > 48 ? "…" : "")
          : scope;
      const text =
        printResult && printResult.ok !== false
          ? `Print dialog opened for ${label}.`
          : "Could not open the print dialog. Allow pop-ups for this app or use the Print toolbar button.";
      return outcome(text, "print", result.intent, [], { refreshHal: false });
    }

    if (result.useProactiveBriefing) {
      const Proactive = typeof HalProactive !== "undefined" ? HalProactive : window.HalProactive;
      if (!Proactive) return outcome("Proactive HAL manager is not loaded.", "hal", result.intent);
      const briefing =
        (ctx.runProactiveCycle && (await ctx.runProactiveCycle())) ||
        Proactive.getLastBriefing() ||
        (await Proactive.runCycle(ctx));
      const chatMode =
        typeof HalCore !== "undefined" && HalCore.isChatSizedQuestion
          ? HalCore.isChatSizedQuestion(trimmed, result)
          : true;
      const text = briefing
        ? Proactive.formatProactiveBriefing(briefing, { chatMode })
        : "Proactive briefing unavailable.";
      const shaped =
        typeof HalCore !== "undefined" && HalCore.trimChatReply
          ? HalCore.trimChatReply(text, trimmed, result, { force: chatMode })
          : text;
      return outcome(shaped, "hal", result.intent, [], { refreshHal: true });
    }

    if (result.useForceWidgetPlacement) {
      if (ctx.forceWidgetPlacement) {
        const placement = await ctx.forceWidgetPlacement({ reason: "hal-chat" });
        const feed = ctx.halWidgetFeed || {};
        const widgets = feed.widgets || {};
        const ready = Object.keys(widgets).filter((key) => widgets[key] && widgets[key].status === "SUCCESS").length;
        const total = Object.keys(widgets).length;
        const text = [
          placement && placement.placementNote ? placement.placementNote : "HAL forced widget placement.",
          "",
          `Widgets ready: ${ready}/${total}`,
          window.HalSkills ? HalSkills.formatWidgetFeed(feed) : "",
        ]
          .filter(Boolean)
          .join("\n");
        return outcome(text, "widgets", result.intent, [], { refreshHal: true });
      }
      return outcome("Force widget placement is unavailable in this runtime.", "widgets", result.intent, [], { refreshHal: false });
    }

    if (result.usePracticeSourceCatalog) {
      const desktop = typeof DesktopBridge !== "undefined" ? DesktopBridge : window.DesktopBridge;
      if (!desktop || !desktop.hasDesktopApi || !desktop.hasDesktopApi()) {
        const message =
          desktop && desktop.desktopRequiredMessage
            ? desktop.desktopRequiredMessage("Direct QuickBooks and SoftDent source access")
            : "Direct source access requires the NR2 desktop app.";
        return outcome(message, "sources", result.intent, [], { refreshHal: false });
      }
      let catalog = null;
      if (typeof desktop.listPracticeSourceCatalog === "function") {
        catalog = await desktop.listPracticeSourceCatalog();
      }
      const text = HalSkills.formatPracticeSourceCatalog(catalog);
      return outcome(text, "sources", result.intent, [], { refreshHal: false });
    }

    if (result.usePracticeSourcePull) {
      const Svc = ctx.Services;
      if (!Svc || typeof Svc.pullPracticeSources !== "function") {
        return outcome("Practice source pull requires Services.pullPracticeSources in the desktop app.", "sources", result.intent, [], {
          refreshHal: false,
        });
      }
      try {
        const payload = await Svc.pullPracticeSources({ reason: "hal-route", fullPull: Boolean(result.practiceSourceFullPull) });
        if (typeof Svc.invalidateSnapshot === "function") Svc.invalidateSnapshot();
        ctx.clearProgramContextCache();
        await ctx.refreshHalWidgetFeed(await ctx.loadProgramSnapshot());
        const text = HalSkills.formatPracticeSourcePullResult(payload);
        return outcome(text, "sources", result.intent, [], { refreshHal: true });
      } catch (err) {
        return outcome(`Practice source pull failed: ${err.message || err}`, "sources", result.intent, [], { refreshHal: false });
      }
    }

    if (result.useNarrativeForClaim) {
      const snapshot = await ctx.loadProgramSnapshot();
      const text = HalSkills.formatNarrativeForClaim(snapshot, trimmed);
      return outcome(text, "narratives", result.intent, [], { refreshHal: false });
    }

    if (result.useHalJobRequirements) {
      const snapshot = await ctx.loadProgramSnapshot();
      const feed = (snapshot && snapshot.widgets) || HalSkills.buildWidgetFeed(snapshot);
      const text = HalSkills.formatHalJobRequirements(feed, snapshot);
      return outcome(text, "hal", result.intent, [], { refreshHal: false });
    }

    if (result.useWidgetPeriodRequirements) {
      const snapshot = await ctx.loadProgramSnapshot();
      const text = HalSkills.formatWidgetPeriodRequirements(snapshot);
      return outcome(text, "periods", result.intent, [], { refreshHal: false });
    }

    if (result.useCognitivePathways) {
      const text = HalSkills.formatCognitivePathways(ctx.halData);
      return outcome(text, "hal", result.intent, [], { refreshHal: false });
    }

    if (result.useSourceSystemGuide) {
      const snapshot = await ctx.loadProgramSnapshot();
      const text = HalSkills.formatSourceSystemGuide(snapshot);
      return outcome(text, "sources", result.intent, [], { refreshHal: false });
    }

    if (result.usePracticeSourceFetch) {
      const desktop = typeof DesktopBridge !== "undefined" ? DesktopBridge : window.DesktopBridge;
      if (!desktop || !desktop.hasDesktopApi || !desktop.hasDesktopApi()) {
        const message =
          desktop && desktop.desktopRequiredMessage
            ? desktop.desktopRequiredMessage("Direct QuickBooks and SoftDent source access")
            : "Direct source access requires the NR2 desktop app.";
        return outcome(message, "sources", result.intent, [], { refreshHal: false });
      }
      const request = result.practiceSourceRequest || (HalSkills.resolvePracticeSourceRequest ? HalSkills.resolvePracticeSourceRequest(trimmed) : {});
      let payload = null;
      if (typeof desktop.fetchPracticeSource === "function") {
        payload = await desktop.fetchPracticeSource(request.system, request.resource, {
          refreshCache: Boolean(request.refreshCache),
        });
      }
      const text = HalSkills.formatPracticeSourceFetch(payload, request);
      const refreshHal = Boolean(payload && payload.ok && request.refreshCache);
      if (refreshHal && ctx.Services && typeof ctx.Services.invalidateSnapshot === "function") {
        ctx.Services.invalidateSnapshot();
        ctx.clearProgramContextCache();
        await ctx.refreshHalWidgetFeed(await ctx.loadProgramSnapshot());
      }
      return outcome(text, "sources", result.intent, [], { refreshHal });
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
        try {
          const Ops = typeof PortalOps !== "undefined" ? PortalOps : window.PortalOps;
          if (Ops && typeof Ops.getIntegrationHealth === "function") {
            const health = await Ops.getIntegrationHealth();
            text += "\n\n" + Ops.formatIntegrationHealth(health);
          }
        } catch (_healthErr) {
          /* optional enrichment */
        }
      }
      return outcome(text, "imports", result.intent, [], { refreshHal: true });
    }

    if (result.useIntegrationHealth) {
      const Ops = typeof PortalOps !== "undefined" ? PortalOps : window.PortalOps;
      if (!Ops) return outcome("Portal ops module is not loaded.", "ops", result.intent);
      const health = await Ops.getIntegrationHealth();
      return outcome(Ops.formatIntegrationHealth(health), "ops", result.intent);
    }

    if (result.useSupportBundle) {
      const Ops = typeof PortalOps !== "undefined" ? PortalOps : window.PortalOps;
      if (!Ops) return outcome("Portal ops module is not loaded.", "ops", result.intent);
      const bundle = await Ops.buildSupportBundle(trimmed.slice(0, 200));
      const text = bundle && bundle.ok
        ? `Support bundle created: ${bundle.path}\nSize: ${bundle.sizeBytes || 0} bytes.\nIntegration status: ${bundle.integrationStatus || "unknown"}.`
        : "Support bundle could not be created.";
      return outcome(text, "ops", result.intent);
    }

    if (result.useDailyCloseout) {
      const Ops = typeof PortalOps !== "undefined" ? PortalOps : window.PortalOps;
      if (!Ops) return outcome("Portal ops module is not loaded.", "ops", result.intent);
      const payload = await Ops.getDailyCloseout();
      return outcome(Ops.formatDailyCloseout(payload), "ops", result.intent);
    }

    if (result.useCloseoutRunbook) {
      const Ops = typeof PortalOps !== "undefined" ? PortalOps : window.PortalOps;
      if (!Ops || typeof Ops.buildCloseoutRunbook !== "function") {
        return outcome("Closeout runbook requires PortalOps.", "ops", result.intent);
      }
      const snapshot = await ctx.loadProgramSnapshot();
      const payload = await Ops.buildCloseoutRunbook(snapshot);
      return outcome(Ops.formatCloseoutRunbook(payload), "ops", result.intent, [{ label: "Open documents", page: "documents" }]);
    }

    if (result.useProgramSelfHeal) {
      const PS = typeof ProgramStrength !== "undefined" ? ProgramStrength : window.ProgramStrength;
      if (!PS || typeof PS.runSelfHeal !== "function") {
        return outcome("Program self-heal is not loaded.", "ops", result.intent);
      }
      const fullPull = /\bfull\b|\b100%\b|\ball exports\b/.test(trimmed);
      const report = await PS.runSelfHeal({ reason: "hal", fullPull });
      ctx.clearProgramContextCache && ctx.clearProgramContextCache();
      if (ctx.refreshHalWidgetFeed) await ctx.refreshHalWidgetFeed(await ctx.loadProgramSnapshot());
      return outcome(PS.formatReport(report), "ops", result.intent, [], { refreshHal: true });
    }

    if (result.useJournalBulkApprove) {
      const db = typeof DesktopBridge !== "undefined" ? DesktopBridge : window.DesktopBridge;
      if (!db || typeof db.bulkReviewPostingQueue !== "function") {
        return outcome("Bulk journal review requires the NR2 desktop app.", "ops", result.intent);
      }
      const bulk = await db.bulkReviewPostingQueue(
        "approved",
        "hal-local-user",
        "Bulk approved via HAL (local review only; not posted to QuickBooks).",
      );
      ctx.clearProgramContextCache && ctx.clearProgramContextCache();
      if (ctx.refreshHalWidgetFeed) await ctx.refreshHalWidgetFeed(await ctx.loadProgramSnapshot());
      const count = bulk && bulk.reviewedCount != null ? bulk.reviewedCount : 0;
      return outcome(
        `Approved ${count} pending journal queue item(s). Export approved CSV from Accounting Documents when ready.`,
        "ops",
        result.intent,
        [{ label: "Open documents", page: "documents" }],
        { refreshHal: true },
      );
    }

    if (result.useFinancialReports) {
      const Ops = typeof PortalOps !== "undefined" ? PortalOps : window.PortalOps;
      if (!Ops) return outcome("Portal ops module is not loaded.", "ops", result.intent);
      const reports = await Ops.getFinancialReports(/\bsync exports\b/i.test(trimmed));
      const lines = [
        "Financial reports (import snapshot):",
        `- Claims: ${reports.claimTracking?.totalClaims || 0} total; ${reports.claimTracking?.deniedCount || 0} denied.`,
        `- A/R outstanding: $${Number(reports.arAging?.totalOutstanding || 0).toLocaleString()}.`,
        `- Treatment plans: ${reports.treatmentPlans?.available ? "loaded" : "missing"}.`,
        `- Case acceptance: ${reports.caseAcceptance?.available ? "loaded" : "missing"}.`,
        "",
        reports.claimTracking?.followUpHint || "",
        reports.arAging?.followUpHint || "",
      ].filter(Boolean);
      return outcome(lines.join("\n"), "ops", result.intent);
    }

    if (result.useAutomationRegistry) {
      const Ops = typeof PortalOps !== "undefined" ? PortalOps : window.PortalOps;
      if (!Ops) return outcome("Portal ops module is not loaded.", "ops", result.intent);
      const payload = await Ops.getAutomationRegistry();
      return outcome(Ops.formatAutomationRegistry(payload), "ops", result.intent);
    }

    if (result.useProgramHelp) {
      const Ops = typeof PortalOps !== "undefined" ? PortalOps : window.PortalOps;
      const db = typeof DesktopBridge !== "undefined" ? DesktopBridge : window.DesktopBridge;
      let text = "Program help is unavailable in this runtime.";
      if (Ops && typeof Ops.getProgramHelp === "function") {
        const help = await Ops.getProgramHelp(result.prompt || trimmed);
        text = (help && help.text) || text;
      } else if (db && typeof db.getProgramHelp === "function") {
        const help = await db.getProgramHelp(result.prompt || trimmed);
        text = (help && help.text) || text;
      }
      return outcome(text, "help", result.intent);
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
        const draft = await HalSkills.draftAndValidateJournalAsync({
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

    if (result.useRememberMemory) {
      const desktop = typeof DesktopBridge !== "undefined" ? DesktopBridge : window.DesktopBridge;
      if (!desktop || !desktop.hasDesktopApi || !desktop.hasDesktopApi()) {
        const message =
          desktop && desktop.desktopRequiredMessage
            ? desktop.desktopRequiredMessage("Saving durable HAL learned facts")
            : "Learning requires the NR2 desktop app.";
        return outcome(message, "memory", result.intent);
      }
      const wantsWeb = /\bweb\b/i.test(trimmed);
      if (wantsWeb && typeof HalAgent !== "undefined" && HalAgent.getLastWebResearch) {
        const last = HalAgent.getLastWebResearch();
        if (last && Array.isArray(last.results) && last.results.length) {
          try {
            const saved = await desktop.rememberHalWebFindings(last.query || last.originalQuery || trimmed, last.results);
            const memory = saved && saved.memory;
            return outcome(
              `Saved public web findings to durable HAL memory${memory && memory.id ? ` (${memory.id})` : ""}. I can use this as guidance in future answers.`,
              "memory",
              result.intent,
            );
          } catch (error) {
            return outcome(
              error && error.message ? error.message : "Could not save web findings to memory.",
              "memory",
              result.intent,
            );
          }
        }
        return outcome(
          "No recent web research is available to save. Ask a web research question first, then say Remember the web findings.",
          "memory",
          result.intent,
        );
      }
      const fact = extractRememberText(trimmed);
      if (!fact) {
        return outcome(
          'Tell me what to remember, for example: Remember this: SoftDent needs a final daysheet per date for accurate A/R.',
          "memory",
          result.intent,
        );
      }
      try {
        const saved = await desktop.rememberHalFact(fact);
        const memory = saved && saved.memory;
        return outcome(
          `Saved to durable HAL memory${memory && memory.id ? ` (${memory.id})` : ""}:\n- ${memory ? memory.text : fact}`,
          "memory",
          result.intent,
        );
      } catch (error) {
        return outcome(error && error.message ? error.message : "Could not save memory.", "memory", result.intent);
      }
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

    if (result.useWidgetMasterChart) {
      const feed = await widgetFeed();
      ctx.setHalWidgetFeed(feed);
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
      const text =
        chart && typeof chart.formatForHal === "function"
          ? chart.formatForHal(feed)
          : "Widget master chart unavailable.";
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
        sourceTrace: () => HalSkills.formatWidgetSourceTrace(feed, snapshot),
        fillPriority: () => HalSkills.formatWidgetFillPriority(feed),
        importChecklist: () => HalSkills.formatImportChecklist(feed, snapshot),
        dataQuality: () => HalSkills.formatDataQualityCheck(feed),
        explainEmpty: () => HalSkills.formatEmptyWidgetExplanation(feed, result.prompt || trimmed),
        dailyOwnerBriefing: () => HalSkills.formatDailyOwnerBriefing(feed, snapshot),
        accountingReviewQueue: () => HalSkills.formatAccountingReviewQueue(feed, snapshot),
        accountingReconciliationChecklist: () => HalSkills.formatAccountingReconciliationChecklist(feed, snapshot),
        documentExcelWorkbook: () => HalSkills.formatDocumentExcelWorkbook(feed, snapshot),
        excelReconciliation: () => HalSkills.formatExcelReconciliation(feed, snapshot),
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

    if (result.useEnglishSeed) {
      const Vocab = typeof HalEnglishVocab !== "undefined" ? HalEnglishVocab : globalThis.HalEnglishVocab;
      if (!Vocab || !Vocab.seedLibraryIntoServices) {
        return outcome("English vocabulary module is not loaded.", "english", result.intent);
      }
      const seeded = await Vocab.seedLibraryIntoServices(/\bforce\b/i.test(trimmed));
      ctx.clearProgramContextCache && ctx.clearProgramContextCache();
      const text = seeded.ok
        ? seeded.seeded
          ? `English dictionary indexed — ${seeded.volumes || seeded.docCount} volumes, ${seeded.wordCount || "370k+"} words in the local library. Ask for a random word or say define [word].`
          : `Library already has the dictionary (${seeded.docCount} volumes, ${seeded.wordCount || ""} words). Say "seed english dictionary force" to rebuild.`
        : `Could not seed dictionary: ${seeded.error || "unknown error"}`;
      return outcome(text, "english", result.intent, [], { refreshHal: result.useEnglishSeed });
    }

    if (result.useEnglishRandom || result.useEnglishTeach) {
      const Vocab = typeof HalEnglishVocab !== "undefined" ? HalEnglishVocab : globalThis.HalEnglishVocab;
      if (!Vocab) return outcome("English vocabulary module is not loaded.", "english", result.intent);
      const entry = await Vocab.randomWord({ minLen: 4, maxLen: 11 });
      const text = result.useEnglishTeach
        ? Vocab.formatWordLesson(entry, { prompt: true })
        : Vocab.buildRandomWordReply(entry);
      return outcome(text, "english", result.intent);
    }

    if (result.useEnglishDefine) {
      const Vocab = typeof HalEnglishVocab !== "undefined" ? HalEnglishVocab : globalThis.HalEnglishVocab;
      if (!Vocab) return outcome("English vocabulary module is not loaded.", "english", result.intent);
      const entry = await Vocab.lookupWord(result.englishWord);
      return outcome(Vocab.buildDefineReply(entry, result.englishWord), "english", result.intent);
    }

    if (result.useEnglishQuiz) {
      const Vocab = typeof HalEnglishVocab !== "undefined" ? HalEnglishVocab : globalThis.HalEnglishVocab;
      if (!Vocab) return outcome("English vocabulary module is not loaded.", "english", result.intent);
      const count = result.englishQuizCount || 5;
      const words = [];
      for (let i = 0; i < count; i++) {
        words.push(await Vocab.randomWord({ minLen: 4, maxLen: 10 }));
      }
      return outcome(Vocab.buildQuizPrompt(words), "english", result.intent);
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
