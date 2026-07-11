/**
 * HAL spoken-report viewer — Moonshot voice+report NICE.
 * Remembers last report excerpts and offers "Read Summary" re-speak.
 */
(function (global) {
  "use strict";

  const STORE_KEY = "nr2:hal:reports";
  const MAX = 20;
  let lastReport = null;

  function voiceReportsEnabled() {
    const cfg = global.NR2_CONFIG || {};
    return cfg.voiceReportsEnabled !== false;
  }

  function loadList() {
    try {
      const raw = global.localStorage && localStorage.getItem(STORE_KEY);
      const list = raw ? JSON.parse(raw) : [];
      return Array.isArray(list) ? list : [];
    } catch (_err) {
      return [];
    }
  }

  function saveList(list) {
    try {
      if (global.localStorage) localStorage.setItem(STORE_KEY, JSON.stringify(list.slice(0, MAX)));
    } catch (_err) {
      /* ignore */
    }
  }

  function remember(report) {
    if (!report || !voiceReportsEnabled()) return null;
    const entry = {
      at: new Date().toISOString(),
      tool: String(report.tool || report.intent || "report"),
      summary: String(report.summary || "").slice(0, 8000),
      spokenExcerpt: String(report.spokenExcerpt || report.summary || "").slice(0, 420),
    };
    lastReport = entry;
    const list = loadList();
    list.unshift(entry);
    saveList(list);
    return entry;
  }

  function getLast() {
    if (lastReport) return lastReport;
    const list = loadList();
    lastReport = list[0] || null;
    return lastReport;
  }

  function readSummary(excerpt) {
    const text = String(excerpt || (getLast() && getLast().spokenExcerpt) || "").trim();
    if (!text) return { ok: false, reason: "empty" };
    if (typeof HalVoice !== "undefined" && HalVoice.speakHalBriefing) {
      HalVoice.speakHalBriefing(text, { interrupt: true });
      return { ok: true, spoken: text };
    }
    if (global.speechSynthesis) {
      global.speechSynthesis.cancel();
      global.speechSynthesis.speak(new SpeechSynthesisUtterance(text));
      return { ok: true, spoken: text, engine: "speechSynthesis" };
    }
    return { ok: false, reason: "no-tts" };
  }

  function attachReadButton(metaRow, report) {
    if (!metaRow || !voiceReportsEnabled()) return null;
    const excerpt = String((report && report.spokenExcerpt) || (report && report.summary) || "").trim();
    if (!excerpt) return null;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "apex-hal-chat__copy apex-hal-chat__read-summary";
    btn.textContent = "Read Summary";
    btn.title = "Re-speak the short spoken excerpt";
    btn.dataset.halReadSummary = "1";
    btn.addEventListener("click", () => {
      const res = readSummary(excerpt);
      btn.textContent = res.ok ? "Reading…" : "Unavailable";
      setTimeout(() => {
        btn.textContent = "Read Summary";
      }, 1600);
    });
    metaRow.appendChild(btn);
    return btn;
  }

  function enhanceMessageRow(row, report) {
    if (!row || !report) return;
    remember(report);
    const meta = row.querySelector(".apex-hal-chat__meta-row");
    if (meta) attachReadButton(meta, report);
  }

  global.HalReports = {
    remember,
    getLast,
    readSummary,
    attachReadButton,
    enhanceMessageRow,
    loadList,
  };
})(typeof window !== "undefined" ? window : globalThis);
