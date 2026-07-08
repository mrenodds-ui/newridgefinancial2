/**
 * Universal print helpers — open a clean print preview for pages, text, HTML, widgets, and snapshots.
 */
const PrintUtils = (function () {
  const PRINT_CSS = `
    @page { margin: 0.75in; }
    * { box-sizing: border-box; }
    html, body { margin: 0; padding: 0; font-family: "Segoe UI", system-ui, sans-serif; color: #111; background: #fff; font-size: 11pt; line-height: 1.45; }
    .nr2-print-header { border-bottom: 2px solid #1a5276; padding-bottom: 8px; margin-bottom: 16px; }
    .nr2-print-header h1 { margin: 0 0 4px; font-size: 16pt; color: #1a5276; }
    .nr2-print-header .meta { margin: 0; color: #555; font-size: 9pt; }
    .nr2-print-body pre { white-space: pre-wrap; word-break: break-word; font-family: Consolas, "Courier New", monospace; font-size: 9pt; margin: 0; }
    .nr2-print-body table { width: 100%; border-collapse: collapse; margin: 8px 0; }
    .nr2-print-body th, .nr2-print-body td { border: 1px solid #ccc; padding: 4px 8px; text-align: left; vertical-align: top; }
    .nr2-print-body th { background: #f0f4f8; }
    .nr2-print-widget { margin-bottom: 12px; padding: 8px; border: 1px solid #ddd; page-break-inside: avoid; }
    .nr2-print-widget h3 { margin: 0 0 4px; font-size: 11pt; }
    .nr2-print-widget p { margin: 0 0 6px; }
    @media print { body { -webkit-print-color-adjust: exact; print-color-adjust: exact; } }
  `;

  function esc(value) {
    return String(value == null ? "" : value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function buildDocument(title, bodyHtml) {
    const safeTitle = esc(title || "Print");
    const stamp = esc(new Date().toLocaleString());
    return `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${safeTitle}</title><style>${PRINT_CSS}</style></head><body>
      <div class="nr2-print-doc">
        <header class="nr2-print-header"><h1>${safeTitle}</h1><p class="meta">NewRidgeFinancial 2.0 · ${stamp}</p></header>
        <div class="nr2-print-body">${bodyHtml || ""}</div>
      </div>
    </body></html>`;
  }

  function triggerPrint(docWindow) {
    if (!docWindow) return;
    docWindow.focus();
    setTimeout(() => {
      try {
        docWindow.print();
      } catch (_err) {
        /* print may be blocked in some embedded hosts */
      }
    }, 250);
  }

  function printViaIframe(title, bodyHtml) {
    let frame = document.getElementById("nr2PrintFrame");
    if (!frame) {
      frame = document.createElement("iframe");
      frame.id = "nr2PrintFrame";
      frame.title = "Print preview";
      frame.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0;opacity:0;pointer-events:none";
      frame.setAttribute("aria-hidden", "true");
      document.body.appendChild(frame);
    }
    const doc = frame.contentDocument || (frame.contentWindow && frame.contentWindow.document);
    if (!doc) return { ok: false, method: "iframe", error: "iframe unavailable" };
    doc.open();
    doc.write(buildDocument(title, bodyHtml));
    doc.close();
    triggerPrint(frame.contentWindow);
    return { ok: true, method: "iframe" };
  }

  function openPrintWindow(title, bodyHtml) {
    if (typeof window === "undefined" || typeof document === "undefined") {
      return { ok: false, method: "none", error: "no document" };
    }
    return printViaIframe(title, bodyHtml);
  }

  function sanitizeClone(root) {
    if (!root) return null;
    const clone = root.cloneNode(true);
    clone
      .querySelectorAll(
        "script, style, button, input, select, textarea, [hidden], .drawer__close, .drawer__print, [data-nr2-print], nav, #sidebar, #nav, .hal-chat__form, .hp-inline-chat__form",
      )
      .forEach((el) => el.remove());
    clone.querySelectorAll("details").forEach((el) => el.setAttribute("open", ""));
    clone.querySelectorAll("[aria-hidden='true']").forEach((el) => el.removeAttribute("aria-hidden"));
    return clone;
  }

  function printHtml(title, html) {
    return openPrintWindow(title, html || "");
  }

  function printText(title, text) {
    return printHtml(title, `<pre>${esc(text || "")}</pre>`);
  }

  function printJson(title, value) {
    let body = "";
    try {
      body = JSON.stringify(value, null, 2);
    } catch (_err) {
      body = String(value);
    }
    return printText(title || "JSON", body);
  }

  function printElement(target, title) {
    const element = typeof target === "string" ? document.querySelector(target) : target;
    if (!element) return { ok: false, method: "none", error: "element not found" };
    const clone = sanitizeClone(element);
    return printHtml(title || "Print", clone ? clone.outerHTML : "");
  }

  function printDrawer() {
    const panel = document.querySelector("#drawer .drawer__panel");
    const titleEl = document.getElementById("drawerTitle");
    const title = titleEl ? titleEl.textContent.replace(/\s+/g, " ").trim() : "HAL panel";
    return printElement(panel, title || "HAL panel");
  }

  function printCurrentView(opts) {
    const o = opts || {};
    const drawerEl = document.getElementById("drawer");
    const halVisible = o.halPageVisible != null ? o.halPageVisible : !!document.querySelector("#appPage .ms-page--hal");
    const drawerOpen = o.drawerOpen != null ? o.drawerOpen : drawerEl && drawerEl.classList.contains("open");

    if (drawerOpen) return printDrawer();
    if (halVisible) {
      const root =
        document.querySelector("#appPage .ms-page--hal") ||
        document.querySelector(".ms-page--hal") ||
        document.getElementById("appPage");
      return printElement(root, o.title || "HAL Command Center");
    }

    const pageId =
      o.pageId ||
      String(window.location.hash || "")
        .replace(/^#/, "")
        .trim() ||
      "financial";
    const scoped = document.querySelector(`[data-pv-page="${pageId}"]`) || document.getElementById("appPage");
    return printElement(scoped, o.title || pageId);
  }

  function formatWidgetBlock(key, widget) {
    const w = widget || {};
    const metrics = Array.isArray(w.metrics)
      ? w.metrics
          .map((m) => `<tr><td>${esc(m && m.label)}</td><td>${esc(m && m.value)}</td></tr>`)
          .join("")
      : "";
    return `<div class="nr2-print-widget">
      <h3>${esc(w.title || key)} <span style="font-weight:normal;color:#666">(${esc(w.status || "")})</span></h3>
      <p>${esc(w.summary || "")}</p>
      ${metrics ? `<table><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>${metrics}</tbody></table>` : ""}
    </div>`;
  }

  function printWidgetFeed(feed, title) {
    const widgets = (feed && feed.widgets) || {};
    const keys = Object.keys(widgets).sort();
    const body = keys.map((key) => formatWidgetBlock(key, widgets[key])).join("");
    return printHtml(title || "Widget feed", body || "<p>No widgets available.</p>");
  }

  function printWidget(feed, widgetKey, title) {
    const w = feed && feed.widgets && feed.widgets[widgetKey];
    if (!w) return printText(title || widgetKey, `Widget "${widgetKey}" was not found in the current feed.`);
    const text =
      typeof HalSkills !== "undefined" && HalSkills.formatWidgetDetail
        ? HalSkills.formatWidgetDetail(feed, widgetKey)
        : JSON.stringify(w, null, 2);
    return printText(title || w.title || widgetKey, text);
  }

  function printSnapshot(snapshot, halData, title) {
    const text =
      typeof HalCore !== "undefined" && HalCore.formatProgramSnapshot
        ? HalCore.formatProgramSnapshot(snapshot, halData)
        : JSON.stringify(snapshot, null, 2);
    return printText(title || "Program snapshot", text);
  }

  function printHalReply(history, title) {
    const hist = Array.isArray(history) ? history : [];
    const lastHal = [...hist].reverse().find((entry) => entry && entry.role === "hal");
    const text = lastHal && lastHal.text ? lastHal.text : "No HAL reply is available to print yet.";
    return printText(title || "HAL reply", text);
  }

  function printAnything(payload) {
    if (payload == null) return printCurrentView();
    if (typeof payload === "string") return printText("Print", payload);
    const p = payload;
    if (p.html != null) return printHtml(p.title, p.html);
    if (p.text != null) return printText(p.title, p.text);
    if (p.json != null) return printJson(p.title, p.json);
    if (p.element) return printElement(p.element, p.title);
    if (p.scope === "drawer") return printDrawer();
    if (p.scope === "widget-feed") return printWidgetFeed(p.feed, p.title);
    if (p.scope === "widget") return printWidget(p.feed, p.widgetKey, p.title);
    if (p.scope === "snapshot") return printSnapshot(p.snapshot, p.halData, p.title);
    if (p.scope === "hal-reply") return printHalReply(p.history, p.title);
    if (p.scope === "page" || p.scope === "auto") return printCurrentView(p);
    return printCurrentView(p);
  }

  return {
    esc,
    printHtml,
    printText,
    printJson,
    printElement,
    printDrawer,
    printCurrentView,
    printWidgetFeed,
    printWidget,
    printSnapshot,
    printHalReply,
    printAnything,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = PrintUtils;
}
if (typeof globalThis !== "undefined") {
  globalThis.PrintUtils = PrintUtils;
}
if (typeof window !== "undefined") {
  window.PrintUtils = PrintUtils;
}
