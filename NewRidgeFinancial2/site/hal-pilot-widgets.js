/**
 * HAL pilot widgets — interactive event wiring for canvas page surfaces.
 * Kanban cards, chart bars, and other [data-hal-action] elements dispatch through HalLiveWidgetBridge.
 */
const HalPilotWidgets = (function () {
  const LEGACY_WIDGET_SCHEMA = {
    mode: "canvas-feed",
    note: "Staff pages render through PageCanvas with halWidgetFeed badges and HAL command wiring.",
    eventContract: ["pageId", "widgetKey", "library", "eventType", "payload", "halAction", "flash"],
  };

  function emit(card, detail) {
    const bridge =
      typeof HalLiveWidgetBridge !== "undefined"
        ? HalLiveWidgetBridge
        : typeof window !== "undefined"
          ? window.HalLiveWidgetBridge
          : null;
    if (!bridge || typeof bridge.report !== "function") return;
    const event = bridge.report(detail);
    if (typeof bridge.flashElement === "function") bridge.flashElement(card, event.flash);
  }

  function init(root) {
    if (!root) return;
    root.querySelectorAll("[data-hal-pilot-initialized]").forEach((el) => el.removeAttribute("data-hal-pilot-initialized"));

    root.querySelectorAll("[data-hal-action]:not([data-hal-pilot-initialized])").forEach((el) => {
      el.setAttribute("data-hal-pilot-initialized", "1");
      el.addEventListener("click", () => {
        const widget = el.closest("[data-hal-pilot]") || el;
        const card = el.closest("[data-hal-widget-key]") || widget;
        if (widget && widget.querySelectorAll) {
          widget.querySelectorAll(".is-selected").forEach((selected) => selected.classList.remove("is-selected"));
        }
        el.classList.add("is-selected");
        emit(card, {
          pageId: el.getAttribute("data-hal-page") || "unknown",
          widgetKey: el.getAttribute("data-hal-widget") || "unknown",
          library: el.getAttribute("data-hal-library") || "canvas widget",
          eventType: el.getAttribute("data-hal-event") || "interaction",
          payload: {
            label: el.getAttribute("data-hal-payload-label") || "",
            value: el.getAttribute("data-hal-payload-value") || "",
          },
          halAction: el.getAttribute("data-hal-next") || "Review selected widget item",
          flash: el.getAttribute("data-hal-flash") || "gold",
        });
      });
    });

    root.querySelectorAll("[data-hal-force-place]:not([data-hal-force-bound])").forEach((btn) => {
      btn.setAttribute("data-hal-force-bound", "1");
      btn.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (typeof window !== "undefined" && typeof window.CustomEvent === "function") {
          window.dispatchEvent(
            new CustomEvent("hal-force-widget-placement", {
              detail: {
                pageId: btn.getAttribute("data-hal-page") || "financial",
                reason: "ui-force",
              },
            }),
          );
        }
      });
    });

    root.querySelectorAll("[data-hal-chart-bar]:not([data-hal-pilot-initialized])").forEach((bar) => {
      bar.setAttribute("data-hal-pilot-initialized", "1");
      bar.addEventListener("click", () => {
        const card = bar.closest("[data-hal-widget-key]") || bar.closest(".pv-canvas-panel") || bar;
        const metric = bar.getAttribute("data-hal-chart-bar") || "metric";
        const value = Number(bar.getAttribute("data-hal-value"));
        const pageId = bar.getAttribute("data-hal-page") || card.getAttribute("data-hal-widget-key") ? "financial" : "unknown";
        const widgetKey = card.getAttribute ? card.getAttribute("data-hal-widget-key") || "practiceFinancialOverview" : "practiceFinancialOverview";
        emit(card, {
          pageId,
          widgetKey,
          library: "canvas chart",
          eventType: "click",
          payload: { metric, value: Number.isFinite(value) ? value : null },
          halAction: `Explain ${metric} in the financial overview`,
          flash: "gold",
        });
      });
    });
  }

  return {
    LEGACY_WIDGET_SCHEMA,
    init,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalPilotWidgets;
}
if (typeof globalThis !== "undefined") {
  globalThis.HalPilotWidgets = HalPilotWidgets;
}
if (typeof window !== "undefined") {
  window.HalPilotWidgets = HalPilotWidgets;
}
