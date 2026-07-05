/**
 * HAL chat 10000 — transcendent chat tier above chat 9000.
 */
const HalChat10000 = (function () {
  function config(halModels) {
    return (halModels && halModels.config && halModels.config.chat10000) || {};
  }

  function isEnabled(halModels) {
    const c = config(halModels);
    if (c.enabled === false) return false;
    const base = typeof HalChat9000 !== "undefined" && HalChat9000.isEnabled(halModels);
    const ver =
      typeof window !== "undefined" && window.NR2_BUILD
        ? String(window.NR2_BUILD.schemaVersion || "")
        : "";
    const m = /^hal-(\d+)$/.exec(ver);
    return base && ((m && Number(m[1]) >= 10000) || c.enabled === true);
  }

  function personaLines(halModels) {
    const base =
      typeof HalChat9000 !== "undefined" && HalChat9000.personaLines
        ? HalChat9000.personaLines(halModels)
        : "HAL operational intelligence.";
    return (
      base +
      "\n\nCHAT 10000: Practice director voice — executive summary first, delegate domains to billing/accounting/claims/compliance/ops, cite predictive alerts and employee tier status when relevant."
    );
  }

  function buildSystemPrompt(halData, halModels) {
    const parts = [personaLines(halModels)];
    if (typeof HalChat9000 !== "undefined" && HalChat9000.buildSystemPrompt) {
      parts.unshift(HalChat9000.buildSystemPrompt(halData, halModels));
    }
    const A = typeof HalAscension10000 !== "undefined" ? HalAscension10000 : null;
    if (A && A.isEnabled(halModels)) {
      parts.push("Ascension 10000 active — you operate as practice director with standing consent on routine back-office execution.");
    }
    return parts.filter(Boolean).join("\n\n");
  }

  function enrichPrompt(base, ctx) {
    let out = base;
    if (typeof HalChat9000 !== "undefined" && HalChat9000.enrichPrompt) {
      out = HalChat9000.enrichPrompt(out, ctx);
    }
    const DIR = typeof HalDirector !== "undefined" ? HalDirector : null;
    if (DIR && DIR.getExecutiveSummary && ctx) {
      const exec = DIR.getExecutiveSummary(ctx);
      if (exec) out += "\n\n" + exec;
    }
    return out;
  }

  function chatScoreEstimate(halModels, ctx) {
    let s = typeof HalChat9000 !== "undefined" && HalChat9000.chatScoreEstimate ? HalChat9000.chatScoreEstimate(halModels, ctx) : 3500;
    if (!isEnabled(halModels)) return Math.min(9000, s);
    s += 600;
    if (config(halModels).executivePersona !== false) s += 500;
    if (typeof HalDirector !== "undefined" && HalDirector.isRunning && HalDirector.isRunning()) s += 400;
    if (typeof HalEmployee !== "undefined" && HalEmployee.getTargetLevel(halModels) >= 7) s += 500;
    return Math.min(10000, s);
  }

  function shouldAlwaysAgentLoop(halModels, route, query) {
    if (
      typeof HalIndependentThought !== "undefined" &&
      HalIndependentThought.cursorParityFastPath &&
      HalIndependentThought.cursorParityFastPath(halModels, query, route)
    ) {
      return false;
    }
    if (typeof HalCursorParity !== "undefined" && HalCursorParity.isSimpleChatQuery(query, route)) return false;
    if (!isEnabled(halModels)) {
      return typeof HalChat9000 !== "undefined" && HalChat9000.shouldAlwaysAgentLoop(halModels, route, query);
    }
    if (config(halModels).alwaysAgentLoop === false) return false;
    return true;
  }

  return {
    isEnabled,
    config,
    personaLines,
    buildSystemPrompt,
    enrichPrompt,
    chatScoreEstimate,
    shouldAlwaysAgentLoop,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalChat10000;
}
if (typeof globalThis !== "undefined") {
  globalThis.HalChat10000 = HalChat10000;
}
if (typeof window !== "undefined") {
  window.HalChat10000 = HalChat10000;
}
