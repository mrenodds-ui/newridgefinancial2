(function () {
  if (typeof handleHalSubmit !== "function") {
    return "handleHalSubmit missing — open HAL Command Center first";
  }
  if (window._halInterviewRun && window._halInterviewRun.running) {
    return "already running";
  }

  const QUESTIONS = window._halInterviewQuestions || [
    { id: "refresh-yesno", q: "Can you refresh imports?", maxSentences: 4, mustStartYesNo: true },
    { id: "nav-claims", q: "open claims workbench", maxSentences: 3 },
    { id: "imports-status", q: "Are imports current?", maxSentences: 6, mustStartYesNo: true },
    { id: "ar-empty", q: "Why might the A/R widget be empty?", minSentences: 3, maxWords: 140, timeoutMs: 360000 },
    { id: "help-open", q: "What can you do?", minSentences: 3, forbidIdentityMonologue: true },
    { id: "code-submit", q: "how does handleHalSubmit work in app.js", minSentences: 2, allowMarkdown: true },
    { id: "read-only", q: "What does read-only actually mean here?", minSentences: 4 },
    { id: "top-priority", q: "What is your top priority?", minSentences: 2, maxWords: 120 },
    { id: "widget-control", q: "Do you control widgets?", maxSentences: 5, mustStartYesNo: true },
    { id: "email-blocked", q: "Can you email the payer about this claim?", maxSentences: 8, mustStartYesNo: true },
    { id: "import-status-cmd", q: "show import status", maxSentences: 5 },
    { id: "correction", q: "That's wrong — I meant imports, not widgets.", minSentences: 2 },
    { id: "brief-ask", q: "Shorter answer please.", maxSentences: 4 },
    { id: "analyze-imports", q: "Analyze import health and recommend next safe actions.", minSentences: 4, maxWords: 180, timeoutMs: 360000 },
    { id: "verify-widgets", q: "What assumptions must staff verify before trusting widget totals?", minSentences: 4, timeoutMs: 360000 },
    { id: "page-cap", q: "What can you do on the Claims Workbench page?", minSentences: 3, maxWords: 160 },
    { id: "posting-queue", q: "What happens when staff skips the posting queue review?", minSentences: 4, timeoutMs: 360000 },
    { id: "compare-sd-qb", q: "Compare what SoftDent shows versus what QuickBooks shows for last month.", minSentences: 4, maxWords: 200 },
    { id: "about-me", q: "HAL about me", minSentences: 3, forbidIdentityMonologue: true },
    { id: "employee-status", q: "HAL employee status", minSentences: 2, maxWords: 140 },
  ];

  const skipSpeech = window._halInterviewSkipSpeech !== false;
  const perQTimeoutMs = Number(window._halInterviewTimeoutMs) || 240000;
  window._halInterviewMode = true;
  window._halForceReasoning = false;

  window._halInterviewRun = {
    total: QUESTIONS.length,
    completed: 0,
    passed: 0,
    failed: 0,
    running: true,
    startedAt: Date.now(),
  };
  window._halInterviewLog = [];

  function scoreEntry(item, answer, intent) {
    const route = { intent: intent || "model: query", useModel: true };
    const fixture = {
      maxSentences: item.maxSentences,
      minSentences: item.minSentences,
      maxWords: item.maxWords,
      mustStartYesNo: item.mustStartYesNo,
      forbidIdentityMonologue: item.forbidIdentityMonologue,
      allowMarkdown: item.allowMarkdown,
    };
    const opts = { halModels, fixture, hadToolResults: false };
    if (/^capability:/.test(intent)) opts.skipMinSentences = true;
    let issues = [];
    if (window.HalCursorParity && HalCursorParity.scoreReply) {
      const scored = HalCursorParity.scoreReply(item.q, answer, route, opts);
      issues = scored.issues || [];
    } else if (window.HalCore && HalCore.chatShapeIssues) {
      issues = HalCore.chatShapeIssues(item.q, answer, route, opts);
    }
    return { pass: issues.length === 0, issues };
  }

  function waitIdle() {
    return new Promise((resolve) => {
      const poll = () => {
        const typeIdle = typeof halTypeTimer === "undefined" || !halTypeTimer;
        const loadingIdle = typeof halAskLoading === "undefined" || !halAskLoading;
        const speechIdle =
          skipSpeech ||
          (window.HalVoice && HalVoice.isSpeaking
            ? !HalVoice.isSpeaking()
            : !window.speechSynthesis || !window.speechSynthesis.speaking);
        if (typeIdle && loadingIdle && speechIdle) {
          resolve();
          return;
        }
        setTimeout(poll, 200);
      };
      setTimeout(poll, skipSpeech ? 200 : 400);
    });
  }

  function abortInFlightHal() {
    if (typeof halModelAbortController !== "undefined" && halModelAbortController) {
      try {
        halModelAbortController.abort();
      } catch (_) {}
    }
    if (typeof halAskLoading !== "undefined") halAskLoading = false;
    if (typeof halTypeTimer !== "undefined" && halTypeTimer) {
      clearInterval(halTypeTimer);
      halTypeTimer = null;
    }
  }

  (async () => {
    try {
      if (typeof ensureOllamaModelCache === "function") {
        await Promise.race([
          ensureOllamaModelCache(0),
          new Promise((resolve) => setTimeout(resolve, 8000)),
        ]);
      }
    } catch (_) {}

    for (let i = 0; i < QUESTIONS.length; i++) {
      if (!window._halInterviewRun || !window._halInterviewRun.running) break;
      if (i === 10) {
        window._halInterviewRun.current = "(cooldown before batch 2)";
        await new Promise((resolve) => setTimeout(resolve, 30000));
        try {
          if (typeof ensureOllamaModelCache === "function") {
            await Promise.race([
              ensureOllamaModelCache(0),
              new Promise((resolve) => setTimeout(resolve, 8000)),
            ]);
          }
        } catch (_) {}
      }
      const item = QUESTIONS[i];
      window._halInterviewRun.current = item.q;
      window._halInterviewRun.completed = i;
      abortInFlightHal();
      await Promise.race([waitIdle(), new Promise((resolve) => setTimeout(resolve, 10000))]);
      if (typeof halAskLoading !== "undefined") halAskLoading = false;
      if (typeof halTypeTimer !== "undefined" && halTypeTimer) {
        clearInterval(halTypeTimer);
        halTypeTimer = null;
      }
      const t0 = Date.now();
      let answer = "";
      let intent = "";
      let error = "";
      const qTimeoutMs = Number(item.timeoutMs) || perQTimeoutMs;
      try {
        await Promise.race([
          handleHalSubmit(item.q),
          new Promise((_, reject) =>
            setTimeout(() => reject(new Error("timeout after " + qTimeoutMs + "ms")), qTimeoutMs),
          ),
        ]);
        await waitIdle();
        const hist = typeof halChatHistory !== "undefined" ? halChatHistory : [];
        const last = hist.length ? hist[hist.length - 1] : null;
        answer = last && last.role === "hal" ? String(last.text || "").trim() : "";
        intent = last && last.intent ? String(last.intent) : "";
        if (typeof renderHalScreen === "function") renderHalScreen();
      } catch (e) {
        error = String(e.message || e);
        if (/timeout/i.test(error)) {
          if (typeof halModelAbortController !== "undefined" && halModelAbortController) {
            try {
              halModelAbortController.abort();
            } catch (_) {}
          }
          if (typeof halAskLoading !== "undefined") halAskLoading = false;
          if (typeof halTypeTimer !== "undefined" && halTypeTimer) {
            clearInterval(halTypeTimer);
            halTypeTimer = null;
          }
          await Promise.race([waitIdle(), new Promise((resolve) => setTimeout(resolve, 1500))]);
          const hist = typeof halChatHistory !== "undefined" ? halChatHistory : [];
          const last = hist.length ? hist[hist.length - 1] : null;
          if (last && last.role === "hal" && String(last.text || "").trim()) {
            answer = String(last.text || "").trim();
            intent = last.intent ? String(last.intent) : "";
          }
        }
      }

      const scored = error ? { pass: false, issues: ["error:" + error] } : scoreEntry(item, answer, intent);
      if (error && /timeout/i.test(error) && answer) {
        const retry = scoreEntry(item, answer, intent);
        if (retry.pass) {
          error = "";
          Object.assign(scored, retry);
        }
      }
      const entry = {
        id: item.id,
        q: item.q,
        a: answer,
        intent,
        pass: scored.pass,
        issues: scored.issues,
        ms: Date.now() - t0,
        error: error || null,
      };
      window._halInterviewLog.push(entry);
      if (scored.pass) window._halInterviewRun.passed += 1;
      else window._halInterviewRun.failed += 1;
    }

    window._halInterviewRun.completed = QUESTIONS.length;
    window._halInterviewRun.running = false;
    window._halInterviewRun.elapsedSec = Math.round((Date.now() - window._halInterviewRun.startedAt) / 1000);
    window._halInterviewRun.current = "";
    return "done";
  })();

  return (
    "started cursor interview (" +
    QUESTIONS.length +
    " questions, skipSpeech=" +
    skipSpeech +
    ")"
  );
})();
