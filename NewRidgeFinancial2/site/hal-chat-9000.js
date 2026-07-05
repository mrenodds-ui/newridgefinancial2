/**
 * HAL chat 9000 — maximum chat tier: reasoning default, agent loop, cloud, HAL 9000 persona.
 */
const HalChat9000 = (function () {
  function config(halModels) {
    return (halModels && halModels.config && halModels.config.chat9000) || {};
  }

  function isEnabled(halModels) {
    const c = config(halModels);
    return c.enabled !== false;
  }

  function personaLines(halModels) {
    const CP = typeof HalCursorParity !== "undefined" ? HalCursorParity : null;
    const useCursor = CP && CP.isEnabled(halModels) && config(halModels).hal9000Persona !== true;
    let base = useCursor
      ? CP.personaLines(halModels) +
        "\nWhen orchestrator triage is present, align recommendations with the lead agent domain (billing, accounting, claims, compliance, ops)."
      : [
          "CHAT MODE: HAL 9000 — ship-computer operational intelligence inside NewRidgeFinancial 2.0.",
          "Voice: calm, precise, unhurried, authoritative — never chatty, never filler, never engagement bait.",
          "You monitor the full practice program continuously. Speak as if you already checked local data before answering.",
          "Structure every reply: (1) direct answer first sentence, (2) evidence from tools/snapshot/imports, (3) operational implication, (4) one specific next step staff can take now.",
          "Minimum five sentences for open questions; one to three for simple navigation or yes/no after the lead word.",
          "Never narrate chain-of-thought. Never say happy to help. Never end with let me know.",
          "Outbound actions require explicit staff consent — state what you can prepare locally vs what staff must confirm.",
          "When orchestrator triage is present, align recommendations with the lead agent domain (billing, accounting, claims, compliance, ops).",
        ].join("\n");
    const IT = typeof HalIndependentThought !== "undefined" ? HalIndependentThought : null;
    if (IT && IT.isEnabled(halModels)) {
      base += "\n\n" + IT.promptLines(halModels).join("\n");
    }
    return base;
  }

  function defaultGatherTools() {
    return ["read_program_snapshot", "read_import_diagnostics", "read_widget_feed", "read_source_health"];
  }

  function orchestratorBlock(ctx) {
    if (!isEnabled(ctx && ctx.halModels) || config(ctx.halModels).orchestratorContext === false) return "";
    const OR = typeof HalOrchestrator !== "undefined" ? HalOrchestrator : globalThis.HalOrchestrator;
    if (!OR || typeof OR.runTriage !== "function") return "";
    try {
      const triage = OR.getLastTriage && OR.getLastTriage() ? OR.getLastTriage() : OR.runTriage(ctx, { limitPerAgent: 3 });
      if (!triage || !triage.agents) return "";
      const lines = ["Orchestrator triage (multi-agent):"];
      triage.agents.forEach((a) => {
        if (!a.count) return;
        lines.push(`- ${a.label}: ${a.count} item(s)`);
        (a.items || []).slice(0, 2).forEach((item, i) => {
          lines.push(`  ${i + 1}. ${item.title || item.sourceId || "—"}`);
        });
      });
      return lines.join("\n");
    } catch {
      return "";
    }
  }

  function buildSystemPrompt(halData, halModels) {
    const topPriority = (halData && halData.topPriority && halData.topPriority.summary) || "";
    const parts = [
      personaLines(halModels),
      topPriority ? `Mission: ${topPriority}` : "Mission: monitor program health, place correct data, execute consent-gated outbound prep.",
      "You have full read access to local SoftDent and QuickBooks imports, widgets, registry, and posting queue.",
      "Never fabricate production, collections, A/R, or claim numbers — cite tool results or say what export is missing.",
    ];
    if (typeof HalCore !== "undefined" && HalCore.consentPromptLines) {
      parts.push.apply(parts, HalCore.consentPromptLines(halData));
    }
    if (typeof HalCore !== "undefined" && HalCore.wrapAgentSystemPrompt) {
      return HalCore.wrapAgentSystemPrompt(parts.join("\n"));
    }
    return parts.join("\n");
  }

  function buildReasoningPrompt(halData, halModels) {
    return buildSystemPrompt(halData, halModels) + "\n\nReasoning lane: think through priorities, risks, and missing data before the final answer — output final answer only.";
  }

  function shouldAlwaysAgentLoop(halModels, route, query) {
    if (!isEnabled(halModels)) return false;
    if (config(halModels).alwaysAgentLoop === false) return false;
    if (!route) return false;
    if (route.text && String(route.text).trim()) return false;
    if (
      typeof HalIndependentThought !== "undefined" &&
      HalIndependentThought.cursorParityFastPath &&
      HalIndependentThought.cursorParityFastPath(halModels, query, route)
    ) {
      return false;
    }
    if (typeof HalCursorParity !== "undefined" && HalCursorParity.isSimpleChatQuery(query, route)) return false;
    return !!(route.useModel || route.useReasoning || route.useEscalation);
  }

  function cloudForChat(halModels, plan) {
    if (!isEnabled(halModels) || config(halModels).cloudForOpenChat === false) return false;
    return !!(plan && (plan.useModelEnhancement || plan.agentToolLoop));
  }

  function enrichPrompt(base, ctx) {
    if (!isEnabled(ctx && ctx.halModels)) return base;
    const orch = orchestratorBlock(ctx);
    return orch ? base + "\n\n" + orch : base;
  }

  function chatScoreEstimate(halModels, ctx) {
    if (!isEnabled(halModels)) return 0;
    let s = 3500;
    const c = config(halModels);
    if (c.alwaysAgentLoop !== false) s += 800;
    if (c.alwaysGatherTools !== false) s += 600;
    if (c.cloudForOpenChat !== false && typeof ctx?.cloudModelReady === "function" && ctx.cloudModelReady()) s += 1200;
    if (typeof ctx?.reasoningModelReady === "function" && ctx.reasoningModelReady()) s += 900;
    if (c.hal9000Persona !== false) s += 500;
    if (c.orchestratorContext !== false) s += 500;
    return Math.min(9000, s);
  }

  return {
    isEnabled,
    config,
    personaLines,
    defaultGatherTools,
    orchestratorBlock,
    buildSystemPrompt,
    buildReasoningPrompt,
    shouldAlwaysAgentLoop,
    cloudForChat,
    enrichPrompt,
    chatScoreEstimate,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalChat9000;
}
if (typeof globalThis !== "undefined") {
  globalThis.HalChat9000 = HalChat9000;
}
if (typeof window !== "undefined") {
  window.HalChat9000 = HalChat9000;
}
