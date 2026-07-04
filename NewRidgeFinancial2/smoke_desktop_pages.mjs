/**
 * Staff page smoke — financial, documents, and office-manager surfaces (no HAL chat).
 * Uses the same Node import path as NR2 desktop (NR2_LOAD_IMPORTS=1).
 */
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const siteDir = join(__dirname, "site");

process.env.NR2_LOAD_IMPORTS = "1";

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

require(join(siteDir, "empty-states.js"));
require(join(siteDir, "import-diagnostics.js"));
require(join(siteDir, "import-loader.js"));
require(join(siteDir, "runtime-issues.js"));
require(join(siteDir, "snapshot-store.js"));
require(join(siteDir, "month-end-close.js"));
require(join(siteDir, "portal-ops.js"));
require(join(siteDir, "hal-skills.js"));
require(join(siteDir, "page-schema.js"));
require(join(siteDir, "page-chrome.js"));
require(join(siteDir, "page-canvas-data.js"));
require(join(siteDir, "page-canvas.js"));
require(join(siteDir, "components.js"));
const Services = require(join(siteDir, "services.js"));
const PageViews = require(join(siteDir, "page-views.js"));
const HalSkills = require(join(siteDir, "hal-skills.js"));
const PageCanvasData = require(join(siteDir, "page-canvas-data.js"));
const PortalOps = require(join(siteDir, "portal-ops.js"));
const MonthEndClose = require(join(siteDir, "month-end-close.js"));
const halData = JSON.parse(readFileSync(join(siteDir, "data", "hal-manager.json"), "utf8"));

const snap = await Services.readProgramSnapshot();
assertOk("program snapshot loads", Boolean(snap && snap.dashboards), "dashboards present");

const feed = HalSkills.buildWidgetFeed(snap);
PageCanvasData.bind(feed, snap);

const pageIds = ["financial", "documents", "office-manager"];
for (const pageId of pageIds) {
  const html = await PageViews.previewPageHtml(halData, pageId, feed, snap);
  assertOk(`${pageId} page renders`, html.includes("pv--app"), "functional app surface");
  assertOk(`${pageId} no mock shell`, !html.includes("pv--mock-image"), "no mock image");
}

const finHtml = await PageViews.previewPageHtml(halData, "financial", feed, snap);
assertOk(
  "financial month-end surface",
  finHtml.includes("pv-month-end-blocker") || finHtml.includes("Month-End Close Checklist"),
  finHtml.includes("pv-month-end-blocker") ? "blocker strip" : "checklist panel",
);

const payload = MonthEndClose.buildReconciliationPayload(snap);
assertOk("month-end payload builds", Boolean(payload && payload.checklist), `period=${payload?.period || "?"}`);

const docsHtml = await PageViews.previewPageHtml(halData, "documents", feed, snap);
assertOk("documents source breakdown", docsHtml.includes("Source breakdown"), "source panel present");
const breakdown = PageCanvasData.documentsSourceBreakdown();
assertOk("documents source stats", Array.isArray(breakdown) && breakdown.length === 4, breakdown.map((r) => r.label).join(", "));

const omHtml = await PageViews.previewPageHtml(halData, "office-manager", feed, snap);
assertOk("office-manager ops health", omHtml.includes("Integration health"), "ops health panel");
assertOk("ops health refresh wired", omHtml.includes("data-ops-refresh-health"), "refresh button");
assertOk("ops support bundle wired", omHtml.includes("data-ops-support-bundle"), "support bundle button");

const opsText = PortalOps.formatOpsHealthFromSnapshot(snap);
assertOk("ops health formatter", opsText.includes("Import bundle") || opsText.includes("Journal queue"), opsText.split("\n")[0]);

const report = {
  ok: failures.length === 0,
  pages: pageIds,
  monthEndBlockers: payload?.checklist?.blockers ?? null,
  documentsQueue: snap.documents?.queueCount ?? null,
  failures,
  checks,
};

console.log(JSON.stringify(report, null, 2));
process.exit(failures.length ? 1 : 0);
