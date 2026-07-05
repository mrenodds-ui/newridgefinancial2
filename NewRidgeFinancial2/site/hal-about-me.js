/**
 * HAL about me — spoken intro for the practice owner in the HAL UI.
 */
const HalAboutMe = (function () {
  const PRACTICE_NAME = "New Ridge Family Dental";

  async function loadMemories(limit) {
    const db =
      typeof DesktopBridge !== "undefined"
        ? DesktopBridge
        : typeof window !== "undefined"
          ? window.DesktopBridge
          : null;
    if (!db || typeof db.listHalMemories !== "function") return [];
    try {
      const resp = await db.listHalMemories();
      const items = (resp && resp.items) || [];
      return items.slice(0, Math.max(1, limit || 2));
    } catch {
      return [];
    }
  }

  function buildScript(ctx, halModels, halData) {
    const parts = [];
    const practice = PRACTICE_NAME;
    const emp =
      typeof HalEmployee !== "undefined"
        ? HalEmployee.getTargetLevel(halModels)
        : (halModels && halModels.config && halModels.config.employee && halModels.config.employee.targetLevel) || 7;
    const empName =
      typeof HalEmployee !== "undefined" && HalEmployee.LEVELS[emp]
        ? HalEmployee.LEVELS[emp].name
        : "Executive partner";

    parts.push(`Good afternoon. I am HAL, your ${empName.toLowerCase()} at ${practice}.`);

    if (typeof HalCapabilityIndex !== "undefined" && HalCapabilityIndex.compute) {
      try {
        const hci = HalCapabilityIndex.compute(ctx || {}, halModels);
        if (hci && hci.score) {
          parts.push(`My capability index is ${hci.score} out of ${hci.max}.`);
        }
      } catch {
        /* optional */
      }
    }

    parts.push(
      "You lead this office. I monitor SoftDent and QuickBooks imports, triage billing and accounting work, and execute routine back-office actions under standing consent and audit.",
    );
    parts.push(
      "I do not replace your clinical judgment or payer submit without your confirmation. Ask me in chat, or tap About Me anytime you want this briefing again.",
    );

    return parts.join(" ");
  }

  async function buildScriptWithMemories(ctx, halModels, halData) {
    let script = buildScript(ctx, halModels, halData);
    const memories = await loadMemories(2);
    if (memories.length) {
      const note = memories
        .map((m) => (m && (m.text || m.body || m.fact)) || "")
        .filter(Boolean)
        .slice(0, 1)
        .join("");
      if (note) {
        script += ` I also remember locally: ${String(note).slice(0, 120)}.`;
      }
    }
    return script;
  }

  async function speak(ctx, halModels, halData) {
    const script = await buildScriptWithMemories(ctx, halModels, halData);
    if (typeof HalVoice === "undefined" || !HalVoice) {
      return { ok: false, script, message: "Voice module not loaded." };
    }
    if (HalVoice.speakHal9000Briefing) {
      const r = await HalVoice.speakHal9000Briefing(script, { interrupt: true, kind: "about-me" });
      return Object.assign({ ok: true, script }, r || {});
    }
    if (HalVoice.speakMirandaBriefing) {
      const r = await HalVoice.speakMirandaBriefing(script, { interrupt: true, kind: "about-me" });
      return Object.assign({ ok: true, script }, r || {});
    }
    if (HalVoice.speakHalReply) {
      HalVoice.speakHalReply(script, { interrupt: true });
      return { ok: true, script, started: true };
    }
    return { ok: false, script, message: "No TTS engine available." };
  }

  return {
    buildScript,
    buildScriptWithMemories,
    speak,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalAboutMe;
}
if (typeof globalThis !== "undefined") {
  globalThis.HalAboutMe = HalAboutMe;
}
if (typeof window !== "undefined") {
  window.HalAboutMe = HalAboutMe;
}
