/**
 * Live desktop smoke — import bundle, widget feed, and staff-page import notices.
 * Uses the same Node import path as NR2 desktop (NR2_LOAD_IMPORTS=1).
 */
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);

process.env.NR2_LOAD_IMPORTS = "1";

const HalSkills = require(join(__dirname, "site", "hal-skills.js"));
const Services = require(join(__dirname, "site", "services.js"));
const PageCanvasData = require(join(__dirname, "site", "page-canvas-data.js"));
const PageSchema = require(join(__dirname, "site", "moonshot-page-registry.js"));

const failures = [];
const checks = [];

function pass(name, detail) {
  checks.push({ name, ok: true, detail: detail || null });
}

function fail(name, detail) {
  failures.push({ name, detail });
  checks.push({ name, ok: false, detail });
}

function assertOk(name, ok, detail) {
  if (ok) pass(name, detail);
  else fail(name, detail);
}

const manifest = JSON.parse(readFileSync(join(__dirname, "nr2-build.json"), "utf8"));
const schemaVersion = String(manifest.schemaVersion || manifest.assetVersion || "");
assertOk(
  "build manifest schemaVersion",
  schemaVersion.length > 0,
  schemaVersion || "missing",
);
assertOk(
  "page registry matches build manifest",
  String(PageSchema.SCHEMA_VERSION) === schemaVersion,
  `registry=${PageSchema.SCHEMA_VERSION} manifest=${schemaVersion}`,
);

const snap = await Services.readProgramSnapshot();
assertOk("program snapshot loads", Boolean(snap && snap.dashboards), "dashboards present");

const bundle = snap.importBundle || {};
const feed = HalSkills.buildWidgetFeed(snap);
PageCanvasData.bind(feed, snap);

const overview = feed.widgets.practiceFinancialOverview;
assertOk(
  "financial overview widget",
  overview && overview.status !== "FAILED",
  overview ? `${overview.status}: ${overview.summary || "ok"}` : "missing widget",
);

const fin = snap.dashboards?.financial || {};
if (fin.collectionsPending) {
  pass("collections pending surfaced", "financial.collectionsPending=true (info banner expected)");
} else if (fin.collectionsMissing || fin.collectionsZeroWithProduction) {
  pass("collections gap surfaced", "collections missing/zero with production");
} else {
  pass("collections state", "not pending or missing");
}

const noticeFns = [
  ["financial", "financialImportNotice"],
  ["softdent", "softdentImportNotice"],
  ["quickbooks", "quickbooksImportNotice"],
  ["ar", "arImportNotice"],
  ["claims", "claimsImportNotice"],
  ["documents", "documentsImportNotice"],
  ["library", "libraryImportNotice"],
  ["officeManager", "officeManagerImportNotice"],
  ["narratives", "narrativesImportNotice"],
  ["taxes", "taxesImportNotice"],
];
for (const [pageId, fnName] of noticeFns) {
  const fn = PageCanvasData[fnName];
  assertOk(`${pageId} import notice callable`, typeof fn === "function", fnName);
  if (typeof fn !== "function") continue;
  let notice = null;
  try {
    notice = fn();
  } catch (err) {
    fail(`${pageId} import notice`, String(err.message || err));
    continue;
  }
  checks.push({
    name: `${pageId} notice`,
    ok: true,
    detail: notice ? `${notice.tone || "info"}: ${notice.message}` : "none (healthy or silent)",
  });
}

const arStatus = HalSkills.softDentReadSourceStatus(snap);
const arWidget = feed.widgets.arAgingAndCollections;
if (!arStatus.arAvailable) {
  assertOk(
    "A/R withheld without verified export",
    arWidget?.status !== "SUCCESS",
    arWidget?.status || "no widget",
  );
  const kpis = PageCanvasData.arKpis();
  assertOk(
    "A/R KPIs do not leak stale totals",
    !kpis.some((row) => /\$\d/.test(String(row.value || ""))),
    kpis.map((row) => `${row.label}=${row.value}`).join("; ") || "empty",
  );
} else {
  pass("verified A/R available", "arAgingAndCollections may show SUCCESS");
}

const claimsRows = (bundle.softdent?.claims?.rows || []).length;
const claimsSnap = snap.claims?.total || 0;
pass("claims data", `export rows=${claimsRows} snapshot total=${claimsSnap}`);

const report = {
  ok: failures.length === 0,
  schemaVersion,
  importMode: bundle.importMode || null,
  directFirst: process.env.NR2_DIRECT_FIRST_IMPORTS === "1",
  overview: overview?.status || null,
  accountingValidation: feed.accountingExcelValidation?.status || null,
  arCrossCheck: fin.arCrossCheck || null,
  arAvailable: arStatus.arAvailable,
  collectionsPending: Boolean(fin.collectionsPending),
  failures,
  checks,
};

console.log(JSON.stringify(report, null, 2));
process.exit(failures.length ? 1 : 0);
