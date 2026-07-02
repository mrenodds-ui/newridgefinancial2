import assert from "node:assert/strict";
import DocumentPosting from "./site/document-posting.js";
import MonthEndClose from "./site/month-end-close.js";

const { validateDocumentStatusTransition, buildPostingAuditEntry, appendPostingAudit } = DocumentPosting;

assert.equal(
  validateDocumentStatusTransition({ vendor: "", date: "2026-06-01", amount: "$10" }, "Ready to Post").ok,
  false,
);
assert.equal(
  validateDocumentStatusTransition({ vendor: "Acme", date: "2026-06-01", amount: "$10" }, "Ready to Post").ok,
  true,
);
assert.equal(
  validateDocumentStatusTransition({ vendor: "Acme", date: "2026-06-01", amount: "$10" }, "Posted", { reviewedBy: "" }).ok,
  false,
);
assert.equal(
  validateDocumentStatusTransition({ vendor: "Acme", date: "2026-06-01", amount: "$10" }, "Posted", { reviewedBy: "Controller" }).ok,
  true,
);

const entry = buildPostingAuditEntry({
  doc: { id: "DOC-1", vendor: "Acme", amount: "$100" },
  previousStatus: "Pending Review",
  nextStatus: "Posted",
  reviewedBy: "Controller",
});
assert.equal(entry.docId, "DOC-1");
assert.equal(entry.toStatus, "Posted");

const state = { postingAudit: [] };
appendPostingAudit(state, entry);
assert.equal(state.postingAudit.length, 1);

const checklist = MonthEndClose.buildMonthEndChecklist({
  financial: {
    periodAlignment: { aligned: true, softdentPeriod: "2026-06", quickbooksPeriod: "2026-06" },
    collectionsMissing: false,
    collectionsZeroWithProduction: false,
    quality: { score: 85, categories: [{ label: "QB P&L reconcile", score: 25 }] },
  },
  documents: { posting: [{ label: "Pending Review", count: 0 }], period: { label: "2026-06" } },
  importBundle: { diagnostics: { datasets: [] }, softdent: { dashboard: { rows: [{}, {}] } } },
});
assert.equal(checklist.ready, true);
assert.ok(checklist.items.some((item) => item.id === "period-alignment" && item.status === "ok"));

const pendingChecklist = MonthEndClose.buildMonthEndChecklist({
  financial: {
    periodAlignment: { aligned: true, softdentPeriod: "2026-06", quickbooksPeriod: "2026-06" },
    collectionsPending: true,
    collectionsMissing: false,
    collectionsZeroWithProduction: false,
    quality: { score: 85, overallPass: true, categories: [{ label: "QB P&L reconcile", score: 25 }] },
  },
  documents: { posting: [{ label: "Pending Review", count: 0 }], period: { label: "2026-06" } },
  importBundle: { diagnostics: { datasets: [] }, softdent: { dashboard: { rows: [{}, {}] } } },
});
assert.equal(pendingChecklist.ready, true);
assert.ok(pendingChecklist.items.some((item) => item.id === "collections" && item.status === "warn"));

const failedQualityChecklist = MonthEndClose.buildMonthEndChecklist({
  financial: {
    periodAlignment: { aligned: true, softdentPeriod: "2026-06", quickbooksPeriod: "2026-06" },
    collectionsMissing: false,
    collectionsZeroWithProduction: false,
    quality: { score: 55, overallPass: false, categories: [{ label: "QB P&L reconcile", score: 10 }] },
  },
  documents: { posting: [{ label: "Pending Review", count: 0 }], period: { label: "2026-06" } },
  importBundle: { diagnostics: { datasets: [] }, softdent: { dashboard: { rows: [{}, {}] } } },
});
assert.equal(failedQualityChecklist.ready, false);
assert.ok(failedQualityChecklist.items.some((item) => item.id === "data-quality" && item.status === "fail"));

const bridgeChecklist = MonthEndClose.buildMonthEndChecklist({
  financial: {
    periodAlignment: { aligned: true, softdentPeriod: "2026-06", quickbooksPeriod: "2026-06" },
    collectionsMissing: false,
    quality: { score: 85, overallPass: true, categories: [{ label: "QB P&L reconcile", score: 25 }] },
  },
  documents: { posting: [{ label: "Pending Review", count: 0 }], period: { label: "2026-06" } },
  importBundle: {
    diagnostics: { datasets: [] },
    softdent: { dashboard: { rows: [{}, {}], readSource: "bridge-fallback" } },
  },
});
assert.ok(bridgeChecklist.items.some((item) => item.id === "dashboard-source" && item.status === "warn"));

const payload = MonthEndClose.buildReconciliationPayload({
  dashboards: { financial: { productionMtd: { value: "$1" }, quality: { score: 80 } } },
  documents: { queueCount: 2, period: { postedAmount: "$1" }, postingAudit: [entry] },
  importBundle: { loadedAt: "2026-06-30T00:00:00.000Z" },
});
const text = MonthEndClose.formatReconciliationExport(payload);
assert.match(text, /Month-End Reconciliation Summary/);
assert.match(text, /Posting audit/i);
const csv = MonthEndClose.formatReconciliationCsv(payload);
assert.match(csv, /checklist,period-alignment/);

console.log("test_month_end_close.mjs: ok");
