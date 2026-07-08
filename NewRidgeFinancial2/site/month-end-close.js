/**
 * Month-end close checklist and reconciliation export (computed from live imports + documents).
 */
const MonthEndClose = (function () {
  function postingApi() {
    if (typeof DocumentPosting !== "undefined") return DocumentPosting;
    if (typeof window !== "undefined" && window.DocumentPosting) return window.DocumentPosting;
    try {
      return require("./document-posting.js");
    } catch {
      return null;
    }
  }

  function item(id, label, status, detail) {
    return { id, label, status, detail: detail || "" };
  }

  function dashboardRowCount(bundle) {
    const rows = bundle?.softdent?.dashboard?.rows;
    return Array.isArray(rows) ? rows.length : 0;
  }

  function criticalDiagnostics(bundle) {
    const diag = bundle?.diagnostics;
    if (!diag) return [];
    const items = Array.isArray(diag.datasets) ? diag.datasets : [];
    return items.filter((row) => row.severity === "critical" && row.status !== "connected");
  }

  function buildMonthEndChecklist({ financial, documents, importBundle } = {}) {
    const fin = financial || {};
    const docs = documents || {};
    const bundle = importBundle || null;
    const period =
      fin.periodAlignment?.softdentPeriod ||
      fin.periodAlignment?.quickbooksPeriod ||
      docs.period?.label ||
      new Date().toISOString().slice(0, 7);

    const items = [];

    const aligned = fin.periodAlignment?.aligned !== false;
    items.push(
      item(
        "period-alignment",
        "Cross-source period alignment",
        aligned ? "ok" : "fail",
        aligned
          ? `SoftDent and QuickBooks both report ${period}.`
          : fin.periodAlignment?.message || "Period mismatch between SoftDent and QuickBooks.",
      ),
    );

    const collectionsOk = !fin.collectionsMissing && !fin.collectionsZeroWithProduction;
    const collectionsPending = Boolean(fin.collectionsPending);
    items.push(
      item(
        "collections",
        "SoftDent collections reported",
        collectionsPending ? "warn" : collectionsOk ? "ok" : "fail",
        collectionsPending
          ? "Collections export pending for the comparable period — production may load before collections."
          : collectionsOk
            ? "Collections field present for the current period."
            : fin.collectionsMissing
              ? "Collections not reported — verify daysheet export before close."
              : "Production without collections — run final daysheet export.",
      ),
    );

    const overallPass = fin.quality && fin.quality.overallPass;
    const qualityScore = Number(fin.quality?.score || 0);
    const qualityOk = overallPass !== false && qualityScore >= 70;
    items.push(
      item(
        "data-quality",
        "Financial data quality",
        overallPass === false ? "fail" : qualityScore <= 0 ? "warn" : qualityOk ? "ok" : "warn",
        overallPass === false
          ? "Overall quality gate failed — review collections, period alignment, freshness, and QuickBooks reconcile."
          : qualityScore > 0
            ? `Score ${qualityScore}/100.`
            : "No quality score — imports may be missing.",
      ),
    );

    const qbCategory = (fin.quality?.categories || []).find((row) => row.label === "QB P&L reconcile");
    const qbOk = qbCategory ? Number(qbCategory.score) >= 20 : false;
    items.push(
      item(
        "qb-reconcile",
        "QuickBooks P&L reconcile",
        qbOk ? "ok" : "warn",
        qbOk ? "Revenue, expenses, and net income reconcile." : "P&L variance detected — review QuickBooks exports.",
      ),
    );

    const critical = criticalDiagnostics(bundle);
    items.push(
      item(
        "import-freshness",
        "Critical import datasets",
        critical.length ? "fail" : bundle ? "ok" : "warn",
        critical.length
          ? `${critical.length} critical dataset(s) missing or stale: ${critical.map((row) => row.datasetKey).join(", ")}.`
          : bundle
            ? "All critical imports connected."
            : "Import bundle unavailable.",
      ),
    );

    const pending = (docs.posting || []).find((row) => /pending review/i.test(row.label || ""));
    const pendingCount = Number(pending?.count || 0);
    items.push(
      item(
        "document-review",
        "Documents pending review",
        pendingCount === 0 ? "ok" : "warn",
        pendingCount === 0 ? "No documents waiting in Pending Review." : `${pendingCount} document(s) still Pending Review.`,
      ),
    );

    const depth = dashboardRowCount(bundle);
    const dashboardSource = bundle?.softdent?.dashboard?.readSource;
    items.push(
      item(
        "dashboard-depth",
        "SoftDent dashboard depth",
        depth >= 2 ? "ok" : depth === 1 ? "warn" : "warn",
        depth >= 2 ? "Current and prior month loaded for trend/YTD." : "Single-month dashboard — prior month export missing.",
      ),
    );
    if (dashboardSource === "bridge-fallback") {
      items.push(
        item(
          "dashboard-source",
          "SoftDent dashboard source",
          "warn",
          "Dashboard row(s) sourced from bridge snapshot — export daysheet for authoritative collections.",
        ),
      );
    }

    const blockers = items.filter((row) => row.status === "fail").length;
    const warnings = items.filter((row) => row.status === "warn").length;
    const ready = blockers === 0;
    const summary = ready
      ? warnings
        ? `No blockers; ${warnings} advisory item(s) remain.`
        : "All checklist items pass."
      : `${blockers} blocker(s) and ${warnings} advisory item(s).`;

    return { period, items, ready, blockers, warnings, summary };
  }

  function buildReconciliationPayload(snapshot) {
    const fin = snapshot?.dashboards?.financial || {};
    const docs = snapshot?.documents || {};
    const bundle = snapshot?.importBundle || null;
    const checklist = buildMonthEndChecklist({ financial: fin, documents: docs, importBundle: bundle });
    return {
      generatedAt: new Date().toISOString(),
      period: checklist.period,
      checklist,
      financial: {
        productionMtd: fin.productionMtd?.value || null,
        qualityScore: fin.quality?.score || null,
        overallPass: fin.quality?.overallPass ?? null,
        periodAlignment: fin.periodAlignment || null,
        collectionsMissing: Boolean(fin.collectionsMissing),
        collectionsPending: Boolean(fin.collectionsPending),
      },
      documents: {
        queueCount: docs.queueCount || 0,
        period: docs.period || null,
        posting: docs.posting || [],
        postingAudit: docs.postingAudit || [],
      },
      imports: {
        loadedAt: bundle?.loadedAt || null,
        softdentDir: bundle?.softdentDir || null,
        quickbooksDir: bundle?.quickbooksDir || null,
      },
    };
  }

  function csvEscape(value) {
    const raw = String(value == null ? "" : value);
    if (/[",\n]/.test(raw)) return `"${raw.replace(/"/g, '""')}"`;
    return raw;
  }

  function formatReconciliationExport(payload) {
    const lines = [
      "New Ridge Financial — Month-End Reconciliation Summary",
      `Generated: ${payload.generatedAt}`,
      `Period: ${payload.period}`,
      "",
      `Checklist: ${payload.checklist.summary}`,
    ];
    payload.checklist.items.forEach((row) => {
      lines.push(`- [${row.status.toUpperCase()}] ${row.label}: ${row.detail}`);
    });
    lines.push(
      "",
      "Financial snapshot:",
      `- Production MTD: ${payload.financial.productionMtd || "—"}`,
      `- Data quality: ${payload.financial.qualityScore != null ? `${payload.financial.qualityScore}/100` : "—"}`,
      `- Period alignment: ${payload.financial.periodAlignment?.aligned === false ? payload.financial.periodAlignment.message : "Aligned"}`,
      "",
      "Documents:",
      `- Queue: ${payload.documents.queueCount}`,
      `- Posted amount: ${payload.documents.period?.postedAmount || "—"}`,
      `- Pending amount: ${payload.documents.period?.pendingAmount || "—"}`,
    );
    const audit = payload.documents.postingAudit || [];
    if (audit.length) {
      lines.push("", "Recent posting audit (newest first):");
      audit.slice(0, 15).forEach((entry) => {
        lines.push(
          `- ${entry.at} · ${entry.docId} · ${entry.fromStatus || "—"} → ${entry.toStatus}${entry.reviewedBy ? ` · ${entry.reviewedBy}` : ""}`,
        );
      });
    }
    lines.push("", "Posting to QuickBooks remains human-reviewed only. NR2 does not post to external systems.");
    return lines.join("\n");
  }

  function formatReconciliationCsv(payload) {
    const rows = [
      ["section", "key", "status", "detail"],
      ["checklist", "summary", payload.checklist.ready ? "ready" : "gaps", payload.checklist.summary],
    ];
    payload.checklist.items.forEach((row) => {
      rows.push(["checklist", row.id, row.status, row.detail]);
    });
    rows.push(["financial", "productionMtd", "", payload.financial.productionMtd || ""]);
    rows.push(["financial", "qualityScore", "", payload.financial.qualityScore != null ? String(payload.financial.qualityScore) : ""]);
    rows.push(["documents", "queueCount", "", String(payload.documents.queueCount || 0)]);
    rows.push(["documents", "postedAmount", "", payload.documents.period?.postedAmount || ""]);
    rows.push(["documents", "pendingAmount", "", payload.documents.period?.pendingAmount || ""]);
    (payload.documents.postingAudit || []).slice(0, 25).forEach((entry) => {
      rows.push([
        "postingAudit",
        entry.docId,
        entry.toStatus,
        `${entry.at}; ${entry.fromStatus || "—"} → ${entry.toStatus}; ${entry.reviewedBy || ""}`,
      ]);
    });
    return rows.map((cols) => cols.map(csvEscape).join(",")).join("\n");
  }

  function renderChecklistHtml(checklist, esc) {
    const escape = typeof esc === "function" ? esc : (value) => String(value || "");
    const badgeClass = checklist.ready ? "ok" : checklist.blockers ? "fail" : "warn";
    const badgeLabel = checklist.ready ? "Ready for review" : checklist.blockers ? "Blockers remain" : "Advisory gaps";
    const rows = (checklist.items || [])
      .map(
        (row) => `<li class="ms-month-end__item ms-month-end__item--${escape(row.status)}">
        <span class="ms-month-end__mark" aria-hidden="true">${row.status === "ok" ? "✓" : row.status === "warn" ? "!" : "✗"}</span>
        <div><strong>${escape(row.label)}</strong><p>${escape(row.detail)}</p></div>
      </li>`,
      )
      .join("");
    return `<section class="widget-card ms-month-end" data-hal-widget-key="periodCloseAndPosting">
      <div class="widget-card__head ms-month-end__head">
        <h3>Month-End Close Checklist</h3>
        <span class="ms-month-end__badge ms-month-end__badge--${badgeClass}">${escape(badgeLabel)}</span>
      </div>
      <p class="ms-muted ms-month-end__meta">Period ${escape(checklist.period)} · ${escape(checklist.summary)}</p>
      <ul class="ms-month-end__list">${rows}</ul>
      <div class="ms-month-end__actions">
        <button type="button" class="ms-button" data-recon-export="text">Export reconciliation summary</button>
        <button type="button" class="ms-button" data-recon-export="csv">Download CSV</button>
        <button type="button" class="ms-button ms-button--primary" data-recon-copy="1">Copy checklist</button>
      </div>
      <p class="ms-lock-note">Local review only — NR2 does not post to QuickBooks or SoftDent.</p>
    </section>`;
  }

  function renderPostingAuditHtml(audit, esc) {
    const escape = typeof esc === "function" ? esc : (value) => String(value || "");
    const rows = Array.isArray(audit) ? audit : [];
    if (!rows.length) {
      return `<section class="widget-card ms-posting-audit"><div class="widget-card__head"><h3>Posting Audit Trail</h3></div><p class="ms-muted">Status changes will appear here when staff updates document posting states.</p></section>`;
    }
    const body = rows
      .slice(0, 12)
      .map(
        (entry) => `<tr>
        <td>${escape((entry.at || "").replace("T", " ").slice(0, 19))}</td>
        <td>${escape(entry.docId)}</td>
        <td>${escape(entry.vendor || "—")}</td>
        <td>${escape(entry.fromStatus || "—")} → ${escape(entry.toStatus)}</td>
        <td>${escape(entry.reviewedBy || "—")}</td>
      </tr>`,
      )
      .join("");
    return `<section class="widget-card ms-posting-audit"><div class="widget-card__head"><h3>Posting Audit Trail</h3></div>
      <div class="ms-table-wrap"><table class="ms-table ms-table--compact"><thead><tr><th>When (UTC)</th><th>Document</th><th>Vendor</th><th>Transition</th><th>Reviewer</th></tr></thead><tbody>${body}</tbody></table></div>
    </section>`;
  }

  function renderBlockerStripHtml(checklist, esc) {
    const escape = typeof esc === "function" ? esc : (value) => String(value || "");
    if (!checklist || !checklist.blockers) return "";
    const fails = (checklist.items || []).filter((row) => row.status === "fail").slice(0, 3);
    const warns = (checklist.items || []).filter((row) => row.status === "warn").slice(0, 2);
    const chips = fails.concat(warns);
    if (!chips.length) return "";
    const list = chips
      .map((row) => `<li><strong>${escape(row.label)}</strong> — ${escape(row.detail)}</li>`)
      .join("");
    return `<div class="ms-month-end-blocker" role="status">
      <div class="ms-month-end-blocker__head">
        <strong>Month-end blockers</strong>
        <span class="ms-month-end__badge ms-month-end__badge--fail">${escape(checklist.blockers)} blocker(s)</span>
      </div>
      <ul class="ms-month-end-blocker__list">${list}</ul>
      <p class="ms-muted">Resolve imports and data quality before period close. Full checklist is below.</p>
    </div>`;
  }

  return {
    buildMonthEndChecklist,
    buildReconciliationPayload,
    formatReconciliationExport,
    formatReconciliationCsv,
    renderChecklistHtml,
    renderBlockerStripHtml,
    renderPostingAuditHtml,
    postingApi,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = MonthEndClose;
}
if (typeof window !== "undefined") {
  window.MonthEndClose = MonthEndClose;
}
if (typeof globalThis !== "undefined") {
  globalThis.MonthEndClose = MonthEndClose;
}
