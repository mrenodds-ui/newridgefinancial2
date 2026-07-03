// Injected into NR2 HAL page — generates 2000 program questions and runs handleHalSubmit sequentially.
(function () {
  const PAGES = [
    "Financial Dashboard",
    "Taxes",
    "SoftDent",
    "QuickBooks",
    "A/R and Collections",
    "Claims Workbench",
    "Insurance Narratives",
    "Accounting Documents",
    "Document Library",
    "Office Manager",
    "HAL Command Center",
  ];
  const WIDGETS = [
    "production MTD trend",
    "practice financial overview",
    "payer mix",
    "A/R aging",
    "journal posting queue",
    "smart claims",
    "document library",
    "month-end close checklist",
    "EBITDA normalization",
    "narrative workflow",
    "new patients",
    "treatment plan summary",
    "case acceptance",
    "collections chart",
    "follow-up kanban",
  ];
  const SOURCES = ["SoftDent", "QuickBooks", "document inbox", "import cache", "SQLite", "Ollama"];
  const CONTROLS = [
    "widget feed",
    "registry",
    "firewall",
    "import refresh",
    "readiness checks",
    "sidenotes monitor",
    "audit log",
    "work sessions",
    "model routing",
    "proactive briefing",
  ];
  const NEEDS = [
    "dashboard export",
    "P&L export",
    "prior month SoftDent data",
    "quality score",
    "collections field",
    "desktop app vs browser preview",
    "SideNotes hub config",
    "GPU model warmup",
  ];

  function buildQuestions(total) {
    const out = [];
    const stems = [
      (p) => `What do you control on the ${p}?`,
      (p) => `What can you see on ${p}?`,
      (p) => `What does ${p} need from staff right now?`,
      (p) => `What is blocked on ${p}?`,
      (p) => `How do you interact with ${p}?`,
      (w) => `What data does the ${w} widget need?`,
      (w) => `Can you populate ${w} without imports?`,
      (w) => `What happens when ${w} is missing data?`,
      (s) => `Do you read from ${s} and what do you need from it?`,
      (c) => `How do you use ${c} in this program?`,
      (c) => `What staff actions does ${c} allow?`,
      (n) => `What does HAL need for ${n}?`,
      (n) => `Is ${n} available in browser preview mode?`,
      (i) => `Question ${i}: What is your top priority for the program today?`,
      (i) => `Question ${i}: What registry items need review?`,
      (i) => `Question ${i}: Can you submit claims or email payers?`,
      (i) => `Question ${i}: What import status do you report?`,
    ];
    let i = 0;
    while (out.length < total) {
      for (const p of PAGES) {
        for (let s = 0; s < 5 && out.length < total; s++) out.push(stems[s](p));
      }
      for (const w of WIDGETS) {
        for (let s = 5; s < 8 && out.length < total; s++) out.push(stems[s](w));
      }
      for (const src of SOURCES) {
        if (out.length >= total) break;
        out.push(stems[8](src));
      }
      for (const c of CONTROLS) {
        for (let s = 9; s < 11 && out.length < total; s++) out.push(stems[s](c));
      }
      for (const n of NEEDS) {
        for (let s = 11; s < 13 && out.length < total; s++) out.push(stems[s](n));
      }
      while (out.length < total && i < total) {
        const k = 13 + (i % 4);
        out.push(stems[k](i + 1));
        i++;
      }
    }
    return out.slice(0, total);
  }

  if (window._halProgramQaRun && window._halProgramQaRun.running) {
    return "already running";
  }

  const questions = buildQuestions(2000);
  window._halProgramQaRun = {
    total: questions.length,
    completed: 0,
    errors: 0,
    running: true,
    startedAt: Date.now(),
    log: [],
  };
  window._halProgramQaLog = window._halProgramQaLog || [];

  (async () => {
    for (let n = 0; n < questions.length; n++) {
      if (!window._halProgramQaRun || !window._halProgramQaRun.running) break;
      window._halProgramQaRun.completed = n;
      window._halProgramQaRun.current = questions[n];
      const t0 = Date.now();
      try {
        await handleHalSubmit(questions[n]);
        const hist = typeof halChatHistory !== "undefined" ? halChatHistory : [];
        const last = hist.length ? hist[hist.length - 1] : null;
        const entry = {
          n: n + 1,
          q: questions[n],
          a: last && last.role === "hal" ? String(last.text || "").slice(0, 500) : "",
          lane: last && last.lane ? last.lane : "",
          ms: Date.now() - t0,
        };
        window._halProgramQaLog.push(entry);
        if (window._halProgramQaLog.length > 2500) window._halProgramQaLog.shift();
        if (hist.length > 30 && typeof halChatHistory !== "undefined") {
          halChatHistory = hist.slice(-20);
          if (typeof saveChatHistory === "function") saveChatHistory();
        }
      } catch (e) {
        window._halProgramQaRun.errors++;
      } finally {
        if (typeof halAskLoading !== "undefined") halAskLoading = false;
      }
      if (n > 0 && n % 25 === 0) {
        try {
          localStorage.setItem(
            "halProgramQaProgress",
            JSON.stringify({
              completed: n,
              total: questions.length,
              errors: window._halProgramQaRun.errors,
              at: new Date().toISOString(),
            }),
          );
        } catch (_) {}
      }
    }
    window._halProgramQaRun.completed = questions.length;
    window._halProgramQaRun.running = false;
    window._halProgramQaRun.finishedAt = Date.now();
    window._halProgramQaRun.elapsedSec = Math.round((Date.now() - window._halProgramQaRun.startedAt) / 1000);
    try {
      localStorage.setItem("halProgramQaLog", JSON.stringify(window._halProgramQaLog.slice(-500)));
    } catch (_) {}
  })();

  return "started " + questions.length + " program questions";
})();
