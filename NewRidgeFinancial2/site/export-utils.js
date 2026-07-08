/**
 * Export helpers — CSV download and text export for the current page view.
 */
const ExportUtils = (function () {
  function esc(value) {
    return String(value == null ? "" : value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function csvEscape(value) {
    const text = String(value == null ? "" : value);
    if (/[",\n\r]/.test(text)) return `"${text.replace(/"/g, '""')}"`;
    return text;
  }

  function downloadText(filename, text, mime) {
    if (typeof document === "undefined") return { ok: false, error: "no document" };
    const blob = new Blob([text], { type: mime || "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename || "export.txt";
    link.rel = "noopener";
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 500);
    return { ok: true };
  }

  function rowsToCsv(rows) {
    return (rows || [])
      .map((row) => (Array.isArray(row) ? row : Object.values(row)).map(csvEscape).join(","))
      .join("\n");
  }

  function pageExportRows(pageId, snapshot, feed) {
    const D = typeof PageCanvasData !== "undefined" ? PageCanvasData : null;
    if (!D) return { title: pageId || "page", rows: [] };
    if (typeof D.bind === "function") D.bind(snapshot, feed);

    const map = {
      financial: () => ({
        title: "Financial dashboard",
        rows: [
          ["Section", "Metric", "Value"],
          ...(D.financialKpis ? D.financialKpis().map((k) => ["KPI", k.label, k.value]) : []),
          ...(D.financialCompare ? D.financialCompare().map((k) => ["Compare", k.label, k.value]) : []),
        ],
      }),
      softdent: () => ({
        title: "SoftDent",
        rows: [
          ["Metric", "Value"],
          ...(D.softdentGlanceStats ? D.softdentGlanceStats().map((k) => [k.label, k.value]) : []),
        ],
      }),
      quickbooks: () => ({
        title: "QuickBooks",
        rows: [["Account", "Amount"], ...(D.quickbooksPlRows ? D.quickbooksPlRows() : [])],
      }),
      ar: () => ({
        title: "A/R and collections",
        rows: [
          ["Metric", "Value"],
          ...(D.arKpis ? D.arKpis().map((k) => [k.label, k.value]) : []),
          ...(D.arTopClaimsTable ? D.arTopClaimsTable().slice(0, 25) : []),
        ],
      }),
      claims: () => ({
        title: "Claims workbench",
        rows: [
          ["Metric", "Value"],
          ...(D.claimsKpis ? D.claimsKpis().map((k) => [k.label, k.value]) : []),
        ],
      }),
      documents: () => ({
        title: "Accounting documents",
        rows: [
          ["Document", "Category", "Amount", "Date"],
          ...(D.documentsQueueRows ? D.documentsQueueRows() : []),
          ...(D.journalQueueItems ? D.journalQueueItems().map((item) => [
            item.title || item.id || "Entry",
            item.status || "—",
            item.amount != null ? item.amount : "—",
            item.period || item.createdAt || "—",
          ]) : []),
        ],
      }),
      library: () => ({
        title: "Document library",
        rows: [["Document", "Category", "Updated", "Expires"], ...(D.libraryRows ? D.libraryRows() : [])],
      }),
      hal: () => ({
        title: "HAL widget feed",
        rows: [["Widget", "Status", "Summary"], ...widgetFeedRows(feed)],
      }),
    };

    const builder = map[pageId] || map.financial;
    return builder ? builder() : { title: pageId, rows: [] };
  }

  function widgetFeedRows(feed) {
    const widgets = (feed && feed.widgets) || {};
    return Object.keys(widgets)
      .sort()
      .map((key) => {
        const w = widgets[key] || {};
        return [w.title || key, w.status || "—", w.summary || ""];
      });
  }

  function exportCurrentPageCsv(opts) {
    const o = opts || {};
    const pageId =
      o.pageId ||
      String(typeof window !== "undefined" ? window.location.hash : "")
        .replace(/^#/, "")
        .trim() ||
      "financial";
    const payload = pageExportRows(pageId, o.snapshot, o.feed);
    const stamp = new Date().toISOString().slice(0, 10);
    const csv = rowsToCsv(payload.rows);
    return downloadText(`${pageId}-${stamp}.csv`, csv, "text/csv;charset=utf-8");
  }

  function exportWidgetFeedCsv(feed) {
    const rows = [["Widget", "Status", "Summary"], ...widgetFeedRows(feed)];
    const stamp = new Date().toISOString().slice(0, 10);
    return downloadText(`widget-feed-${stamp}.csv`, rowsToCsv(rows), "text/csv;charset=utf-8");
  }

  function exportText(filename, text) {
    return downloadText(filename, text, "text/plain;charset=utf-8");
  }

  function exportCurrentPage(opts) {
    const halVisible =
      opts && opts.halPageVisible != null
        ? opts.halPageVisible
        : !!(typeof document !== "undefined" && document.querySelector("#appPage .ms-page--hal"));
    if (halVisible) return exportWidgetFeedCsv(opts && opts.feed);
    return exportCurrentPageCsv(opts);
  }

  return {
    esc,
    csvEscape,
    rowsToCsv,
    downloadText,
    pageExportRows,
    exportCurrentPageCsv,
    exportWidgetFeedCsv,
    exportCurrentPage,
    exportText,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = ExportUtils;
}
if (typeof globalThis !== "undefined") {
  globalThis.ExportUtils = ExportUtils;
}
if (typeof window !== "undefined") {
  window.ExportUtils = ExportUtils;
}
