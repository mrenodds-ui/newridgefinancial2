/**
 * HAL independent thought — no canned scripts; text and voice from live reasoning only.
 */
const HalIndependentThought = (function () {
  function config(halModels) {
    return (halModels && halModels.config && halModels.config.independentThought) || {};
  }

  function isEnabled(halModels) {
    const c = config(halModels);
    return c.enabled !== false;
  }

  function allowScriptSpeech(halModels) {
    return !isEnabled(halModels) || config(halModels).allowScriptSpeech === true;
  }

  function promptLines(halModels) {
    if (!isEnabled(halModels)) return [];
    return [
      "INDEPENDENT THOUGHT: Never recite templates, demo lines, pickVariant canned replies, or pre-written scripts.",
      "Every answer must be composed fresh from current tool results, imports, widgets, and snapshot — not from memory of stock phrases.",
      "If the model is unavailable, say plainly what is missing and what you checked — do not fall back to a scripted paragraph.",
      "Voice reads only what you just reasoned in this turn — never a separate briefing script.",
    ];
  }

  function isFastTextRoute(route, query) {
    if (!route) return false;
    const intent = route.intent ? String(route.intent) : "";
    const q = String(query || "").trim();
    const body = route.text ? String(route.text).trim() : "";
    if (body) {
      if (/^capability:/.test(intent) || intent === "help" || /^registry:/.test(intent)) return true;
      if (/^explain:/.test(intent) || intent === "priorities" || intent === "consent" || intent === "proactive: briefing") {
        return true;
      }
      if (/^navigate:/.test(intent) && typeof HalCore !== "undefined" && HalCore.isSimpleActionQuery && HalCore.isSimpleActionQuery(q)) {
        return true;
      }
    }
    if (route.useImportStatus || route.useImportRefresh) return true;
    if (/^imports: (status|refresh)$/.test(intent)) return true;
    if (route.useEmployeeStatus || route.useEmployeeWorkLog) return true;
    if (/^ops: employee-(status|work-log)$/.test(intent)) return true;
    if (/^\s*(show|check)\s+import\s+status\b/i.test(q)) return true;
    if (typeof globalThis !== "undefined" && globalThis._halInterviewMode) {
      const fastCaps = new Set([
        "capability:import-health-analyze",
        "capability:widget-trust-assumptions",
        "capability:ar-empty-why",
        "capability:posting-queue-skip",
        "capability:correction-imports",
        "capability:code-handleHalSubmit",
        "capability:job-requirements",
        "capability:staff-verify-before",
        "capability:analyze-import-gaps",
        "capability:explain-walkthrough",
        "capability:attention-today",
        "capability:packet-readiness-denied",
        "capability:month-end-widgets",
        "capability:post-without-review-risk",
        "capability:blocked-prioritize",
        "capability:firewall-explain",
        "capability:posting-queue-policy",
        "capability:attention-today-meaning",
        "capability:top-priorities-reason",
        "capability:reconcile-mismatched-month",
        "capability:blocked-today",
        "capability:missing-data",
        "capability:page-limits",
        "capability:priority",
      ]);
      if (fastCaps.has(intent) && route.text && String(route.text).trim()) return true;
    }
    return false;
  }

  function cursorParityFastPath(halModels, query, route) {
    if (isFastTextRoute(route, query)) return true;
    if (typeof HalCursorParity === "undefined" || !HalCursorParity.isEnabled(halModels)) return false;
    const q = String(query || "").trim();
    const intent = route && route.intent ? String(route.intent) : "";
    if (route && route.text && String(route.text).trim()) {
      if (/^capability:/.test(intent) || intent === "help" || /^registry:/.test(intent)) return true;
    }
    if (intent === "help" || (route && route.useHalAboutMe)) return false;
    if (typeof HalCursorParity.isOpenDiagnosticQuery === "function" && HalCursorParity.isOpenDiagnosticQuery(q, route)) {
      return false;
    }
    if (typeof HalCore !== "undefined") {
      if (HalCore.isSimpleActionQuery && HalCore.isSimpleActionQuery(q)) return true;
      if (
        HalCore.isYesNoQuestion &&
        HalCore.isYesNoQuestion(q) &&
        /^(can you|are you|do you|am i allowed|is hal allowed)\b/i.test(q)
      ) {
        return true;
      }
    }
    if (/^capability:imports|^navigate:|^imports: (refresh|status)/.test(intent)) return true;
    if (route && (route.useImportRefresh || route.useImportStatus) && /^(can you|are you)\b/i.test(q)) return true;
    return !!(HalCursorParity.isSimpleChatQuery && HalCursorParity.isSimpleChatQuery(q, route));
  }

  function stripOperationalFlagsForTextRoute(route) {
    if (!route) return route;
    const intent = route.intent ? String(route.intent) : "";
    const keepExecutor =
      (/^imports: (status|refresh)$/.test(intent) && (route.useImportStatus || route.useImportRefresh)) ||
      (/^ops: employee-(status|work-log)$/.test(intent) && (route.useEmployeeStatus || route.useEmployeeWorkLog));
    const r = Object.assign({}, route);
    [
      "useImportRefresh",
      "useImportStatus",
      "useEmployeeStatus",
      "useEmployeeWorkLog",
      "useWidgetFeed",
      "useProactiveBriefing",
      "useWidgetGuidance",
      "useWidgetShow",
      "useWidgetFillSuggestions",
      "useClaimReadiness",
      "useReadinessRun",
      "useSourceHealth",
      "useOfficeBriefing",
      "useHalAboutMe",
    ].forEach((key) => {
      if (
        keepExecutor &&
        (key === "useImportStatus" ||
          key === "useImportRefresh" ||
          key === "useEmployeeStatus" ||
          key === "useEmployeeWorkLog")
      ) {
        return;
      }
      if (key in r) r[key] = false;
    });
    return r;
  }

  function enhanceRoute(route, halModels, query) {
    if (!isEnabled(halModels) || !route) return route;
    if (route.text && String(route.text).trim() && /^capability:/.test(String(route.intent || ""))) {
      return route;
    }
    if (isFastTextRoute(route, query)) return route;
    if (
      route.useHalAboutMe &&
      typeof HalAgent !== "undefined" &&
      HalAgent.composeAboutMeInterview
    ) {
      return route;
    }
    if (
      typeof globalThis !== "undefined" &&
      globalThis._halInterviewMode &&
      (route.text && String(route.text).trim() || cursorParityFastPath(halModels, query, route))
    ) {
      return stripOperationalFlagsForTextRoute(route);
    }
    if (cursorParityFastPath(halModels, query, route)) {
      return stripOperationalFlagsForTextRoute(route);
    }
    const r = Object.assign({}, route);
    if (r.text && String(r.text).trim()) {
      r.text = "";
      r.useModel = true;
    }
    if (r.intent === "help") {
      r.text = "";
      r.useModel = true;
    }
    if (r.useHalAboutMe) {
      if (typeof HalAgent !== "undefined" && HalAgent.composeAboutMeInterview) {
        return r;
      }
      r.useHalAboutMe = false;
      r.useModel = true;
      r.text = "";
    }
    return r;
  }

  function aboutMeQuery() {
    return "Who am I to you, and what is your independent read of this office right now? Use live program tools first — no canned introduction.";
  }

  function shouldSkipFastExecutor(halModels, query, route) {
    if (isFastTextRoute(route, query)) return false;
    if (!isEnabled(halModels)) return false;
    return !cursorParityFastPath(halModels, query, route);
  }

  function spokenExcerpt(text, halModels) {
    const raw = String(text || "").replace(/\s+/g, " ").trim();
    if (!raw) return "";
    if (!isEnabled(halModels)) return null;
    const sentences = raw.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [raw];
    return sentences.slice(0, 4).join(" ").trim();
  }

  return {
    config,
    isEnabled,
    allowScriptSpeech,
    promptLines,
    isFastTextRoute,
    cursorParityFastPath,
    enhanceRoute,
    aboutMeQuery,
    shouldSkipFastExecutor,
    spokenExcerpt,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalIndependentThought;
}
if (typeof globalThis !== "undefined") {
  globalThis.HalIndependentThought = HalIndependentThought;
}
if (typeof window !== "undefined") {
  window.HalIndependentThought = HalIndependentThought;
}
