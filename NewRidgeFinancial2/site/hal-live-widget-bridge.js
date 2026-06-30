/**
 * HAL live widget bridge
 *
 * Small event bus for interactive widgets. Third-party widgets (ECharts,
 * Tabulator, Tiptap, Mermaid) can report row/cell/chart events here; app.js
 * records them into HAL runtime state and the widget flashes locally.
 */
const HalLiveWidgetBridge = (function () {
  const MAX_EVENTS = 40;
  const events = [];

  function nowIso() {
    try {
      return new Date().toISOString();
    } catch {
      return "";
    }
  }

  function normalizeEvent(input) {
    const event = input || {};
    return {
      eventId: event.eventId || `hal-widget-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      at: event.at || nowIso(),
      widgetKey: event.widgetKey || "unknown",
      pageId: event.pageId || "unknown",
      library: event.library || "custom",
      eventType: event.eventType || "interaction",
      payload: event.payload || {},
      halAction: event.halAction || "Record widget interaction",
      flash: event.flash || "gold",
    };
  }

  function report(input) {
    const event = normalizeEvent(input);
    events.unshift(event);
    if (events.length > MAX_EVENTS) events.length = MAX_EVENTS;
    if (typeof window !== "undefined" && typeof window.CustomEvent === "function") {
      window.dispatchEvent(new CustomEvent("hal-live-widget-event", { detail: event }));
    }
    return event;
  }

  function recent(limit) {
    return events.slice(0, limit || MAX_EVENTS);
  }

  function clear() {
    events.length = 0;
  }

  function flashElement(element, tone) {
    if (!element || !element.classList) return;
    const cls = tone === "red" ? "pv-hal-live-flash--red" : tone === "cyan" ? "pv-hal-live-flash--cyan" : "pv-hal-live-flash--gold";
    element.classList.remove("pv-hal-live-flash", "pv-hal-live-flash--gold", "pv-hal-live-flash--cyan", "pv-hal-live-flash--red");
    // Reflow so repeated clicks replay the animation.
    void element.offsetWidth;
    element.classList.add("pv-hal-live-flash", cls);
    window.setTimeout(() => {
      element.classList.remove("pv-hal-live-flash", cls);
    }, 1400);
  }

  return {
    report,
    recent,
    clear,
    flashElement,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalLiveWidgetBridge;
}
if (typeof window !== "undefined") {
  window.HalLiveWidgetBridge = HalLiveWidgetBridge;
}
