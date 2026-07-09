/**
 * HAL cursor parity — interview rubric and polish hooks so chat replies match Cursor Auto style.
 */
const HalCursorParity = (function () {
  function config(halModels) {
    return (halModels && halModels.config && halModels.config.cursorParity) || {};
  }

  function isEnabled(halModels) {
    const c = config(halModels);
    if (c.enabled === false) return false;
    const ap = (halModels && halModels.config && halModels.config.agentProgramming) || {};
    return ap.proportionalDepth !== false;
  }

  function personaLines(halModels) {
    return [
      "CHAT MODE: Friendly Cursor Auto colleague — warm, clear, collaborative, proportional depth.",
      "Lead with the answer in the first sentence. Ground claims in local imports, registry, widgets, or tool results when the question needs them.",
      "Greetings and casual chat: short and friendly — do not recite scripts, morning briefings, or import diagnostics unless asked.",
      "Simple navigation, refresh, and yes/no questions: one to three sentences after the lead word.",
      "Open diagnostic or planning questions: five to ten sentences with evidence, gaps, and one safe next step.",
      "Markdown allowed when discussing program source (`inline code`, short bullets, file citations).",
      "No ship-computer monologue, no happy-to-help filler, no let-me-know closers, no engagement bait.",
      "Outbound actions stay consent-gated — say what you can prepare locally vs what staff must confirm.",
    ].join("\n");
  }

  function isSimpleChatQuery(query, route) {
    const q = String(query || "").trim();
    if (typeof HalCore !== "undefined") {
      if (HalCore.isGreetingQuery && HalCore.isGreetingQuery(q)) return true;
      if (HalCore.isSimpleActionQuery && HalCore.isSimpleActionQuery(q)) return true;
      if (HalCore.isYesNoQuestion && HalCore.isYesNoQuestion(q)) return true;
      if (HalCore.wantsBriefReply && HalCore.wantsBriefReply(q)) return true;
    }
    const intent = route && route.intent ? String(route.intent) : "";
    if (intent === "chat: greeting" || (route && route.useFriendlyGreeting)) return true;
    if (/^navigate:|^imports: (refresh|status)|^capability:page-can/.test(intent)) return true;
    return q.length < 48 && !/\b(how does|what does|what is|why|why is|explain|walk me|plan|prioritize|debug|grep|source code)\b/i.test(q);
  }

  function isOpenDiagnosticQuery(query, route) {
    const q = String(query || "").trim();
    if (typeof HalCore !== "undefined" && HalCore.wantsDetailedReply && HalCore.wantsDetailedReply(q)) return true;
    return (
      q.length >= 48 ||
      /\b(why|how does|what does|what is|what happens|explain|diagnose|investigate|plan|prioritize|compare|analyze)\b/i.test(q) ||
      !!(route && (route.useReasoning || route.useEscalation))
    );
  }

  function shouldEnforceMinSentences(query, route, meta, text, halModels) {
    if (!isEnabled(halModels || (meta && meta.halModels))) return null;
    meta = meta || {};
    const q = String(query || "").trim();
    if (/read[\s-]?only|readonly actually mean|what does read-only/i.test(q)) return true;
    if (meta.skipMinSentences) return false;
    if (isSimpleChatQuery(query, route)) return false;
    if (typeof HalCore !== "undefined" && HalCore.isCodeDiscussionQuery && HalCore.isCodeDiscussionQuery(query, route, meta)) {
      return false;
    }
    if (!isOpenDiagnosticQuery(query, route)) return false;
    return true;
  }

  function enrichPolishMeta(meta, query, route, halModels) {
    meta = meta || {};
    if (!isEnabled(halModels || meta.halModels)) return meta;
    const out = Object.assign({}, meta, { halModels: halModels || meta.halModels, cursorParity: true });
    if (isSimpleChatQuery(query, route)) {
      out.skipMinSentences = true;
      out.preferBrief = true;
    }
    if (
      typeof HalCore !== "undefined" &&
      HalCore.isCodeDiscussionQuery &&
      HalCore.isCodeDiscussionQuery(query, route, out)
    ) {
      out.allowMarkdown = true;
    }
    return out;
  }

  function rewriteShapeSystemPrompt() {
    return (
      "Rewrite HAL's reply for staff chat like Cursor Auto. " +
      "Proportional depth: simple or yes/no questions stay to one to three sentences; open diagnostic questions may use five to ten. " +
      "Answer in the first sentence. Markdown only when discussing source code. " +
      "No identity monologue, no filler closings, no unrequested numbered lists. Keep evidence and recommendations from the draft."
    );
  }

  const INTERVIEW_FIXTURES = [
    {
      id: "refresh-yesno",
      query: "Can you refresh imports?",
      route: { intent: "capability:imports", useModel: true, lane: "chat8b" },
      draft:
        "Yes — I can trigger a local import refresh from the program bundle. That re-reads SoftDent and QuickBooks exports on disk; it does not write back to either system. Next step: run Refresh imports from the header or ask me to refresh now.",
      maxSentences: 4,
      mustStartYesNo: true,
    },
    {
      id: "nav-brief",
      query: "open claims workbench",
      route: { intent: "navigate: claims", lane: "local" },
      draft: "Opening Claims Workbench now.",
      maxSentences: 3,
    },
    {
      id: "imports-status",
      query: "Are imports current?",
      route: { intent: "imports: status", useModel: true, lane: "chat8b" },
      draft:
        "No — the registry shows the SoftDent export is missing from the inbox folder, so widgets may be stale. QuickBooks CSV loaded, but A/R counts should not be trusted until SoftDent is present. Next step: refresh imports after placing the export.",
      maxSentences: 6,
      mustStartYesNo: true,
      toolSummary: "SoftDent export missing; QuickBooks CSV present.",
    },
    {
      id: "ar-empty-why",
      query: "Why might the A/R widget be empty?",
      route: { intent: "model: query", useModel: true, useReasoning: true, lane: "reason21b" },
      draft:
        "The A/R widget is empty when the SoftDent AR export did not load or the import bundle is stale. From local checks, missing inbox exports and failed sync are the usual causes — not hidden data in the live system. Staff should refresh imports and confirm the AR CSV path before treating balances as zero. I can re-check widget feed after refresh.",
      minSentences: 3,
      maxWords: 120,
    },
    {
      id: "help-open",
      query: "What can you do?",
      route: { intent: "help", useModel: true, lane: "chat8b" },
      draft:
        "I monitor local SoftDent and QuickBooks imports, explain page widgets, draft review notes, and prepare consent-gated outbound work — I do not post live without staff confirmation. I can open pages, run readiness checks, grep program source, and flag stale exports. Ask about a specific page or task for a narrower answer.",
      minSentences: 3,
      forbidIdentityMonologue: true,
    },
    {
      id: "code-markdown",
      query: "how does handleHalSubmit work in app.js",
      route: { intent: "model: query", useModel: true, useReasoning: true, lane: "reason21b" },
      draft:
        "`handleHalSubmit` in `app.js` routes the chat input through `HalCore.routeHalCommand`, then `HalAgent.processQuery` when the route needs a model. It streams tokens to the HAL panel and respects independent-thought mode by skipping canned executor text. Next step: grep `handleHalSubmit` if you want exact line numbers.",
      allowMarkdown: true,
      minSentences: 2,
    },
  ];

  function scoreReply(query, text, route, opts) {
    opts = opts || {};
    const issues = [];
    const body = String(text || "").trim();
    if (!body) issues.push("empty_response");
    if (/hit an error and could not finish|could not complete that request|check that ollama is running/i.test(body)) {
      issues.push("runtime_error");
    }

    if (typeof HalCore !== "undefined" && HalCore.chatShapeIssues) {
      HalCore.chatShapeIssues(query, body, route, opts).forEach((i) => {
        if (!issues.includes(i)) issues.push(i);
      });
    }

    const fixture = opts.fixture || {};
    if (fixture.mustStartYesNo && !/^(yes|no)\b/i.test(body)) issues.push("yes_no_not_direct");
    if (fixture.maxSentences && typeof HalCore !== "undefined" && HalCore.countSentences(body) > fixture.maxSentences) {
      issues.push("too_long_for_simple");
    }
    if (fixture.minSentences && typeof HalCore !== "undefined" && HalCore.countSentences(body) < fixture.minSentences) {
      issues.push("too_short");
    }
    if (fixture.maxWords && body.split(/\s+/).length > fixture.maxWords) issues.push("too_wordy");
    if (fixture.forbidIdentityMonologue && /\b(I am HAL|ship computer|operational intelligence)\b/i.test(body)) {
      issues.push("identity_monologue");
    }
    if (fixture.allowMarkdown && !/[`]|```/.test(body) && /\b(app\.js|handleHalSubmit|grep)\b/i.test(body)) {
      issues.push("missing_code_markdown");
    }

    const critical = new Set([
      "empty_response",
      "identity_monologue",
      "chatbot_filler",
      "engagement_bait",
      "instruction_leak",
      "yes_no_not_direct",
      "runtime_error",
    ]);
    const score = Math.max(0, 100 - issues.length * 12 - issues.filter((i) => critical.has(i)).length * 8);
    return { pass: issues.length === 0, issues, score };
  }

  function runInterviewPolish(HalCore, halData, halModels, pages) {
    const results = [];
    for (const fixture of INTERVIEW_FIXTURES) {
      const route = fixture.route || { intent: "model: query", useModel: true };
      const meta = enrichPolishMeta(
        {
          halData,
          halModels,
          pages,
          toolSummary: fixture.toolSummary || "",
          synthesize: false,
        },
        fixture.query,
        route,
        halModels,
      );
      const polished = HalCore.polishChatReply(fixture.draft, fixture.query, route, meta);
      const scored = scoreReply(fixture.query, polished, route, {
        fixture,
        halModels,
        hadToolResults: !!fixture.toolSummary,
      });
      results.push({
        id: fixture.id,
        query: fixture.query,
        pass: scored.pass,
        issues: scored.issues,
        score: scored.score,
        reply: polished.slice(0, 280),
      });
    }
    return results;
  }

  return {
    config,
    isEnabled,
    personaLines,
    isSimpleChatQuery,
    isOpenDiagnosticQuery,
    shouldEnforceMinSentences,
    enrichPolishMeta,
    rewriteShapeSystemPrompt,
    INTERVIEW_FIXTURES,
    scoreReply,
    runInterviewPolish,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalCursorParity;
}
if (typeof globalThis !== "undefined") {
  globalThis.HalCursorParity = HalCursorParity;
}
if (typeof window !== "undefined") {
  window.HalCursorParity = HalCursorParity;
}
