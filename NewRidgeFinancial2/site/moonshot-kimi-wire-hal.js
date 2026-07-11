/**
 * Moonshot wiring — HAL namespace stub (load before hal-skills.js Moonshot append).
 */
(function () {
  window.HAL = window.HAL || {};
  window.HAL.skills = window.HAL.skills || {};
  window.HAL.bus = window.HAL.bus || { snapshot: { datasets: {} } };
  const _sources = Object.create(null);
  if (typeof window.HAL.skills.defineSource !== "function") {
    window.HAL.skills.defineSource = function (name, cfg) {
      _sources[name] = cfg;
    };
  }
  if (typeof window.HAL.skills.sourceHealth !== "function") {
    window.HAL.skills.sourceHealth = function (name) {
      const cfg = _sources[name];
      return cfg && typeof cfg.healthCheck === "function"
        ? cfg.healthCheck()
        : { status: "UNKNOWN", detail: "No health check registered." };
    };
  }
})();
