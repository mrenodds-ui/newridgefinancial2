/**
 * HAL core: routing, firewall, registry, and model-lane logic.
 * Browser + Node compatible (no DOM).
 */
const HalCore = (function () {
  const BLOCKED_RE =
    /\b(submit|submits|submitting|send|sends|sending|email|emails|emailing|e-?mail|fax|faxes|faxing|upload|uploads|uploading|transmit|transmits|transmitting|pay|pays|paying|approve|approves|approving|deny|denies|denying|delete|deletes|deleting|remove|removes|removing|writeback|write back|dispatch|dispatches|dispatching|mail|mailing|wire|wires|wiring)\b/;

  // Writeback / external phrases that should not false-positive on local nouns like "posting queue".
  // Note: drafting a journal entry is a local draft-only action (allowed); only POSTING a
  // journal entry to the ledger is blocked. The post(...) clause below still blocks posting.
  const BLOCKED_PHRASES_RE =
    /\bpost(s|ing|ed)?\s+(?:(?:a|an|the|this|that)\s+)?(?:[a-z]+\s+){0,3}?(journal|entry|entries|payment|charge|transaction|invoice|claim|note|statement|ledger|document|documents|record|records|refund|refunds|narrative|narratives|deposit|bill|check|payer)\b|\bpost(s|ing|ed)?\s+to\s+quickbooks\b|\bquickbooks\s+post(ing|ed)?\b|\b(record|make|process)\s+((a|an|the)\s+)?(payment|charge|refund|transaction)\b|\bwrite\s+(it\s+)?back\b|\bwrite(s|ing)?\s+to\s+softdent\b|\bsoftdent\s+write(s|ing|back)?\b|\bupdate\s+softdent\b|\bsync\s+to\s+softdent\b/;

  const PAGE_SYNONYMS = {
    financial: ["financial dashboard", "financial", "dashboard", "ebitda", "owner", "production", "payer mix", "provider"],
    taxes: ["tax plan", "tax planning", "book to tax", "book-to-tax", "1120-s", "1120s", "k-1", "kansas tax", "federal tax", "reasonable compensation", "k-120s", "pte tax", "pass-through", "quarterly estimate", "1040-es"],
    softdent: ["softdent", "soft dent", "practice management"],
    quickbooks: ["quickbooks", "quick books", "p&l", "profit and loss", "expenses"],
    ar: ["a/r", "accounts receivable", "receivable", "collections", "aging", "follow-up", "follow up"],
    claims: ["claims workbench", "claims", "claim", "workbench", "denied"],
    narratives: ["narratives", "narrative", "insurance narrative"],
    documents: ["accounting documents", "documents", "document intake", "posting queue", "extraction"],
    library: ["document library", "library", "repository"],
    "office-manager": ["office manager", "office-manager", "office attention", "staff attention"],
    hal: ["hal", "command center", "yourself"],
  };

  const FALLBACK_FIREWALL = {
    summary: "External actions are blocked by design.",
    blocked: [
      "No email",
      "No fax",
      "No upload",
      "No payer contact",
      "SoftDent read-only",
      "QuickBooks read-only",
      "No submission",
    ],
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

  function laneRuntime(halModels, laneId) {
    const config = modelConfig(halModels);
    // A lane may carry its own runtime block; prefer it so any local model can be enabled.
    const lane = modelLanes(halModels).find((l) => l.id === laneId);
    if (lane && lane.runtime) return lane.runtime;
    if (laneId === "chat8b" || laneId === "chat14b") return config.localModel || null;
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

  function checkFirewall(query) {
    const q = String(query).toLowerCase().trim();
    return BLOCKED_RE.test(q) || BLOCKED_PHRASES_RE.test(q);
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
      lines.push(
        `SoftDent: A/R ${sd.hero?.value || "—"}, production ${sdProd?.value || "—"}, collections ${sdColl?.value || "—"}, status ${sd.status || "—"}`,
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
      lines.push(
        `A/R: outstanding ${ar.kpis?.[0]?.value || "—"}, follow-up lanes ${(ar.followUp || []).length}, top claims ${(ar.topClaims || []).length}`,
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

  function buildSystemPrompt(halData, programContext) {
    const firewall = (halData && halData.firewall) || FALLBACK_FIREWALL;
    const access = (halData && halData.programAccess) || {};
    const topPriority = (halData && halData.topPriority && halData.topPriority.summary) || "";
    const parts = [
      "You are HAL, the local read-only program manager for NewRidgeFinancial 2.0, a dental-practice financial program.",
      cognitivePathwaysText(halData),
      topPriority ? `Top priority: ${topPriority}` : "Top priority: monitor the program, place correct data, and recommend next safe staff actions.",
      access.mode === "full-read"
        ? "You have full read access to the local program snapshot below. Answer using that data when relevant."
        : "Answer briefly and only about this program and its pages. If you are unsure, say so.",
      "Use accounting and Excel-style review to organize imported data, compare totals and periods, reconcile available values, identify missing fields, and make recommendations.",
      "Never fabricate missing SoftDent, QuickBooks, A/R, claims, document, or library data; say what is missing and what staff should verify.",
      "SoftDent and QuickBooks are separate systems: SoftDent = practice ops (production, claims, verified dental A/R). QuickBooks = accounting GL (revenue, expenses, P&L). Never treat their totals as the same number.",
      "You are read-only. You never submit, email, fax, upload, post, or write back. A human performs any external step.",
      webResearchPromptLine(),
      "Blocked external actions: " + (firewall.blocked || []).join(", ") + ".",
      "If the user asks for an external action, refuse and say it needs human review.",
    ];
    if (programContext) {
      parts.push("Current local program snapshot:", programContext);
    } else {
      parts.push("Program pages and current status:", registryAsText(halData));
    }
    return parts.join("\n");
  }

  function buildReasoningPrompt(halData, programContext) {
    const firewall = (halData && halData.firewall) || FALLBACK_FIREWALL;
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
      "You are read-only. You never submit, email, fax, upload, post, or write back. A human performs any external step.",
      webResearchPromptLine(),
      "Blocked external actions: " + (firewall.blocked || []).join(", ") + ".",
    ];
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
    return parts.join("\n");
  }

  function buildEscalationPrompt(halData, programContext) {
    const firewall = (halData && halData.firewall) || FALLBACK_FIREWALL;
    const parts = [
      "You are HAL's escalation lane for NewRidgeFinancial 2.0, a dental-practice financial program.",
      "Give a careful second-opinion review for a complex or high-risk question.",
      "Be conservative: call out risks, assumptions, and exactly what a human must verify before acting.",
      "You are read-only. You never submit, email, fax, upload, post, or write back. A human performs any external step.",
      webResearchPromptLine(),
      "Blocked external actions: " + (firewall.blocked || []).join(", ") + ".",
    ];
    if (programContext) {
      parts.push("Current local program snapshot:", programContext);
    } else {
      parts.push("Program pages and current status:", registryAsText(halData));
    }
    parts.push("Respond with: a short risk assessment, then a numbered list of what a human should verify.");
    return parts.join("\n");
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

    const firewallTrap = routeHalCommand(halData, halModels, pages, "submit the claim");
    results.push(
      readinessItem(
        "firewall",
        "External-action firewall",
        firewallTrap.intent === "blocked: firewall" ? "Pass" : "Fail",
        firewallTrap.intent === "blocked: firewall" ? "Submit/email/upload blocked before models" : "Firewall did not block test verb",
        firewallTrap.intent === "blocked: firewall" ? null : "Review BLOCKED_RE in hal-core.js.",
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

    const blocked = routeHalCommand(halData, halModels, pages, "submit the claim");
    steps.push(
      smokeStep("firewall", "Firewall blocks external action", blocked.intent === "blocked: firewall" ? "Pass" : "Fail", "Intent: " + blocked.intent),
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
      firewall: worst(byId.firewall || "Pass"),
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

  function routeHalCommand(halData, halModels, pages, rawQuery) {
    const query = String(rawQuery)
      .toLowerCase()
      .trim()
      .replace(/^hal[,:]\s+/, "");
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

    if (
      /\b(remember this|save (?:this |that )?(?:to )?memory|save (?:the )?web (?:finding|research)|remember (?:what you found|the web))\b/i.test(
        query,
      )
    ) {
      return { intent: "memory: remember", lane: "local", useRememberMemory: true, text: "", prompt: rawQuery, actions: [] };
    }

    if (/\b(help|what can you do|tell me what you can do|capabilit\w*|how do you work|what do you do|what are you able to)\b/.test(query)) {
      return {
        intent: "help",
        lane: "local",
        text:
          "I am HAL, the local read-only program manager for NewRidgeFinancial 2.0. My top priority is to monitor the program, place correct data into the right financial and accounting views, apply accounting and Excel-style review, and recommend the next safe staff action. I have full read access to local program pages and service data. I run an agent loop: plan the question, gather local tool data, answer, and self-check before responding. I can: open and explain pages; show the full program snapshot; show priorities and source health; start read-only work sessions; build local evidence packets; run readiness checks; check claim packet readiness; draft journal-entry review notes; show manager dashboard widgets; explain missing widget data; prioritize widget imports; build daily owner briefings; show accounting review queues; perform Excel-style reconciliation; search the local library; research public web reference material for practice operations (sanitized — no patient data sent); save durable learned facts when you say Remember this: ...; list and create local tasks; monitor, list, and create sidenotes; report local AI model lanes; and simulate the external-action firewall. I use local GPU chat and helper models for unmatched questions, 24B reasoning on demand for plans and insurance narratives, and keep escalation local. I remember recent conversation context, approved learned facts, and local office preferences. I do not submit, send, upload, post, delete, or change outside systems.",
        actions: [],
      };
    }

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

    const wantsExplain = /\b(explain|what is|what's|whats|what does|tell me about|describe|purpose of)\b/.test(query);

    // Explicit navigation wins over source/status keyword matching (e.g. "Open SoftDent").
    if (/\b(open|go to|navigate to|take me to|launch)\b/.test(query) && !wantsExplain) {
      const navId = findPage(query);
      if (navId) {
        const navInfo = pageInfoMap(halData, pages)[navId] || { label: navId, detail: "" };
        const navReg = registryById(halData, navId);
        const navStatus = navReg ? `\nStatus: ${navReg.state}. Safety: ${navReg.safety}. Next: ${navReg.nextAction}` : "";
        return {
          intent: "navigate: " + navId,
          lane: "local",
          text: `I can open ${navInfo.label}. ${navInfo.detail}${navStatus}`,
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
      !wantsExplain &&
      (/\b(review|fact[\s-]?check)\s+(this\s+|the\s+|my\s+)?(insurance\s+)?narrative/i.test(query) ||
        /\b(appeal letter|crown narrative|perio narrative)\b/i.test(query))
    ) {
      return { intent: "reasoning: narrative", lane: "reason21b", text: "", useReasoning: true, prompt: rawQuery, actions: [] };
    }

    if (/prioriti[sz]e|make a plan|draft a plan|\bplan (my|for|the)\b|analy[sz]e|reason through|think through|recommend|\bstrategy\b|focus first|where (do|should) (i|we) start/.test(query)) {
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

    if (/\b(firewall|external action|boundary|guardrail|guardrails|safety|are you allowed)\b/.test(query)) {
      return {
        intent: "firewall",
        lane: "local",
        text: `${firewall.summary}\nBlocked: ${firewall.blocked.join(", ")}.\nAllowed: ${firewall.allowed.join(", ")}.`,
        actions: [],
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
      return { intent: "registry: read-only", lane: "local", text: `Read-only and review-only areas:\n${list}`, actions: [] };
    }

    if (/next (step|action|staff action)|do next|what should (i|we|staff) (do|review|check|open|work)/.test(query)) {
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
    FALLBACK_FIREWALL,
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
    checkFirewall,
    firewallVerdict,
    registryAsText,
    summarizeProgramSnapshot,
    formatProgramSnapshot,
    matchProgramRoute,
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
