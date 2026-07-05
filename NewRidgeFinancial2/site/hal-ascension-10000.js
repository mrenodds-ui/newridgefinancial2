/**
 * HAL ascension 10000 — transcendent program tier above hal-9000 + employee level 5.
 */
const HalAscension10000 = (function () {
  const MAX = 10000;
  const BASE_MAX = 9000;

  function config(halModels) {
    return (halModels && halModels.config && halModels.config.ascension10000) || {};
  }

  function isEnabled(halModels) {
    const c = config(halModels);
    if (c.enabled === false) return false;
    const ver =
      typeof window !== "undefined" && window.NR2_BUILD
        ? String(window.NR2_BUILD.schemaVersion || "")
        : "";
    const m = /^hal-(\d+)$/.exec(ver);
    return (m && Number(m[1]) >= 10000) || c.enabled === true;
  }

  function buildVersion(ctx) {
    const snap = ctx && ctx.halData && ctx.halData.build;
    return snap && (snap.schemaVersion || snap.assetVersion) ? String(snap.schemaVersion || snap.assetVersion) : "";
  }

  function directorEnabled(halModels) {
    return isEnabled(halModels) && config(halModels).directorMode !== false;
  }

  function executiveBlock(ctx) {
    if (!directorEnabled(ctx && ctx.halModels)) return "";
    const DIR = typeof HalDirector !== "undefined" ? HalDirector : globalThis.HalDirector;
    if (!DIR || typeof DIR.getExecutiveSummary !== "function") return "";
    try {
      return DIR.getExecutiveSummary(ctx);
    } catch {
      return "";
    }
  }

  function ascensionScoreBonus(halModels, ctx) {
    if (!isEnabled(halModels)) return 0;
    let bonus = 400;
    if (directorEnabled(halModels)) bonus += 350;
    if (typeof HalEmployee !== "undefined" && HalEmployee.getTargetLevel(halModels) >= 7) bonus += 250;
    if (typeof HalDirector !== "undefined" && HalDirector.isRunning && HalDirector.isRunning()) bonus += 200;
    return Math.min(1000, bonus);
  }

  function formatStatus(halModels, ctx) {
    const c = config(halModels);
    const emp = typeof HalEmployee !== "undefined" ? HalEmployee.getTargetLevel(halModels) : 0;
    return [
      `HAL 10000 ascension: ${isEnabled(halModels) ? "active" : "inactive"}.`,
      `Director mode: ${directorEnabled(halModels) ? "on" : "off"}.`,
      `Employee target: level ${emp}/7.`,
      c.policy || "Transcendent tier — predictive director loop, executive digest, levels 6–7 employee autonomy.",
    ].join("\n");
  }

  return {
    MAX,
    BASE_MAX,
    config,
    isEnabled,
    directorEnabled,
    executiveBlock,
    ascensionScoreBonus,
    formatStatus,
    buildVersion,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalAscension10000;
}
if (typeof globalThis !== "undefined") {
  globalThis.HalAscension10000 = HalAscension10000;
}
if (typeof window !== "undefined") {
  window.HalAscension10000 = HalAscension10000;
}
