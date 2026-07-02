import assert from "node:assert/strict";
import ImportLoader from "./site/import-loader.js";
import WidgetContract from "./site/widget-contract.js";

const {
  normalizePeriodKey,
  comparePeriodAlignment,
  buildFinancialDataQuality,
  assessCollectionHealth,
  scopeExpenseCategoryRows,
  compareArCrossSource,
  buildCollectionRateMetrics,
  quickbooksTotals,
} = ImportLoader;

assert.equal(normalizePeriodKey("2026-06"), "2026-06");
assert.equal(normalizePeriodKey("06/30/2026"), "2026-06");
assert.equal(normalizePeriodKey("2026/6"), "2026-06");

const aligned = comparePeriodAlignment("2026-06", "2026-06", true, true);
assert.equal(aligned.aligned, true);

const mismatch = comparePeriodAlignment("2026-06", "2026-05", true, true);
assert.equal(mismatch.aligned, false);
assert.match(mismatch.message, /Period mismatch/);

const ahead = comparePeriodAlignment("2026-07", "2026-06", true, true, new Date("2026-07-01T12:00:00Z"));
assert.equal(ahead.aligned, true);
assert.equal(ahead.comparablePeriod, "2026-06");

const pendingHealth = assessCollectionHealth(
  [{ period: "2026-06", production: 171796.9, collectionsPending: true }],
  "2026-06",
);
assert.equal(pendingHealth.pending, true);
assert.equal(pendingHealth.healthy, true);

const aggregateMissing = {
  totals: { production: 168790, collections: 0, collectionsReported: false, insurance: 0, patient: 0 },
};
const qb = {
  revenue: 109907.52,
  expenses: 77066.11,
  netIncome: 32841.41,
  plReconcile: { matches: true, derivedNetIncome: 32841.41, plNetIncome: 32841.41 },
};
const qualityMissing = buildFinancialDataQuality(
  { diagnostics: { critical: [] } },
  aggregateMissing,
  qb,
  mismatch,
  assessCollectionHealth([]),
);
assert.ok(qualityMissing.score < 88, "quality score should reflect missing collections and period mismatch");
assert.equal(qualityMissing.overallPass, false, "period mismatch should fail overallPass");
assert.equal(qualityMissing.categories.find((c) => c.label === "Collections field").score, 0);
assert.equal(qualityMissing.categories.find((c) => c.label === "Collection health").score, 0);

const zeroHealth = assessCollectionHealth([
  { period: "2026-05", production: 130295.6, collections: 71414.88 },
  { period: "2026-06", production: 169318.9, collections: 0 },
]);
assert.equal(zeroHealth.latestZeroWithProduction, true);
assert.equal(zeroHealth.healthy, false);

const aggregateZero = {
  totals: { production: 299614.5, collections: 71414.88, collectionsReported: true, insurance: 0, patient: 71414.88 },
};
const qualityZero = buildFinancialDataQuality(
  { diagnostics: { critical: [] } },
  aggregateZero,
  qb,
  aligned,
  zeroHealth,
);
assert.ok(qualityZero.score < 100, "quality score should penalize zero collections on latest period");
assert.equal(qualityZero.categories.find((c) => c.label === "Collection health").score, 0);

const unlabeledScope = scopeExpenseCategoryRows(
  [{ Category: "Rent", Amount: "1000" }, { Category: "Lab", Amount: "500" }],
  "2026-06",
);
assert.equal(unlabeledScope.scope, "unlabeled");
assert.match(unlabeledScope.scopeLabel, /unlabeled/i);

const labeledScope = scopeExpenseCategoryRows(
  [
    { Category: "Rent", Amount: "1000", Period: "2026-06" },
    { Category: "Lab", Amount: "500", Period: "2026-05" },
  ],
  "2026-06",
);
assert.equal(labeledScope.scope, "period");
assert.equal(labeledScope.rows.length, 1);

assert.equal(labeledScope.rows.length, 1);

const ytdLabeled = scopeExpenseCategoryRows(
  [{ Category: "Rent", Amount: "1000", Scope: "YTD" }],
  "2026-06",
  77066.11,
);
assert.equal(ytdLabeled.scope, "ytd");
assert.match(ytdLabeled.scopeLabel, /YTD cumulative/i);

const ytdInferred = scopeExpenseCategoryRows(
  [{ Category: "Rent", Amount: "2215801" }],
  "2026-06",
  77066.11,
);
assert.equal(ytdInferred.scope, "ytd_inferred");

const arOk = compareArCrossSource(49111.03, 48800.5);
assert.equal(arOk.comparable, true);
assert.equal(arOk.withinTolerance, true);

const arReview = compareArCrossSource(49111.03, 40000);
assert.equal(arReview.withinTolerance, false);

const arMissingQb = compareArCrossSource(49111.03, null);
assert.equal(arMissingQb.comparable, false);
assert.match(arMissingQb.message, /QuickBooks A\/R not loaded/i);

const trailing = buildCollectionRateMetrics(
  [
    { period: "2026-05", production: 130295.6, collections: 71414.88 },
    { period: "2026-06", production: 169318.9, collections: 0 },
  ],
  { evaluated: true, reported: true, latestZeroWithProduction: true },
);
assert.equal(trailing.trailingRate, "54.8%");
assert.equal(trailing.trailingPeriods, "2026-05");
assert.equal(trailing.latestMonthIncomplete, true);
assert.equal(trailing.latestMonthRate, "0.0%");
assert.match(trailing.displayLabel, /Trailing collection rate/i);

const plTotals = quickbooksTotals({
  quickbooks: {
    revenue: { rows: [{ Period: "2026-06", TotalIncome: "1000" }] },
    expenses: { rows: [{ Period: "2026-06", TotalExpense: "400" }] },
    profitAndLoss: { rows: [{ Period: "2026-06", TotalIncome: "1000", TotalExpense: "400", NetIncome: "650" }] },
  },
  loadedAt: new Date().toISOString(),
});
assert.equal(plTotals.netIncome, 650);
assert.equal(plTotals.plReconcile.matches, false);

const pendingContract = WidgetContract.resolveMetric(
  { path: "collections", dataset: "softdent.dashboard", dashboard: "financial" },
  { dashboards: { financial: { dataSource: "import", collectionsPending: true } }, diagnostics: { datasets: [] } },
);
assert.equal(pendingContract.state, "pending");
assert.equal(pendingContract.value, WidgetContract.MISSING);

console.log("test_import_loader_accounting.mjs: ok");
