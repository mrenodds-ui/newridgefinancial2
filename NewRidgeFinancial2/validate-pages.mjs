#!/usr/bin/env node
/**
 * Validate approved mockup pages have been converted into real functional pages.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const siteDir = join(__dirname, "site");
const require = createRequire(import.meta.url);

process.env.NR2_LOAD_IMPORTS = "1";

const appJs = readFileSync(join(siteDir, "app.js"), "utf8");
const indexHtml = readFileSync(join(siteDir, "index.html"), "utf8");
const stylesCss = readFileSync(join(siteDir, "styles.css"), "utf8");

require(join(siteDir, "empty-states.js"));
require(join(siteDir, "import-diagnostics.js"));
require(join(siteDir, "import-loader.js"));
require(join(siteDir, "runtime-issues.js"));
require(join(siteDir, "snapshot-store.js"));
require(join(siteDir, "import-coordinator.js"));
require(join(siteDir, "office-task-store.js"));
require(join(siteDir, "hal-proactive.js"));
require(join(siteDir, "hal-office-manager.js"));
require(join(siteDir, "widget-contract.js"));
require(join(siteDir, "hal-skills.js"));
const PageViews = require(join(siteDir, "page-views.js"));
const halData = JSON.parse(readFileSync(join(siteDir, "data", "hal-manager.json"), "utf8"));

const FUNCTIONAL_PAGES = [
  { id: "financial", checks: ["pv-fin-top", "pv-bento--financial", "Production MTD"] },
  { id: "softdent", checks: ["pv-bento--softdent", "DAYSHEET A/R"] },
  { id: "quickbooks", checks: ["pv-bento--quickbooks", "P&amp;L Summary"] },
  { id: "ar", checks: ["pv-bento--ar", "Aging Buckets"] },
  { id: "claims", checks: ["pv-claims-layout", "Claims pipeline"] },
  { id: "narratives", checks: ["pv-two-pane--narratives", "Narrative Composer", "Draft Narrative Preview"] },
  { id: "documents", checks: ["pv-bento--documents", "Document Intake", "Selected Document Preview"] },
  { id: "library", checks: ["pv-library-layout", "Document Library"] },
  { id: "office-manager", checks: ["pv--app", "Office Manager", "HAL priorities", "HAL did", "Human must approve"] },
];

for (const page of FUNCTIONAL_PAGES) {
  assert.ok(PageViews.hasPage(page.id), `${page.id} page must be routable`);
  const html = await PageViews.previewPageHtml(halData, page.id);
  assert.ok(!html.includes("pv--mock-image"), `${page.id} must NOT render a mockup image`);
  assert.ok(html.includes("pv--app"), `${page.id} must render the functional app surface`);
  assert.ok(html.includes("pv__header"), `${page.id} must use the shared page header`);
  if (page.id !== "office-manager") {
    assert.ok(
      html.includes("pv-badge--import") ||
        html.includes("Partial import") ||
        html.includes("No data loaded") ||
        html.includes("Import data"),
      `${page.id} must label import or empty data honestly`,
    );
  }
  for (const check of page.checks) {
    assert.ok(html.includes(check), `${page.id} must include ${check}`);
  }
  if (page.id === "financial") {
    assert.ok(!html.includes("Dr. Adams"), "financial page must not render sample provider names");
    assert.ok(!html.includes("Hygiene Team"), "financial page must not render sample provider names");
    assert.ok(
      html.includes("Awaiting import data") || html.includes("pv-badge--import") || html.includes("Partial import"),
      "financial page must show honest import state",
    );
  }
}

assert.equal(PageViews.hasPage("hal"), false, "HAL must route to the real HAL command-center renderer");

assert.ok(!appJs.includes("/api/"), "app.js must not reference backend API routes");
assert.ok(indexHtml.includes('id="appPage"'), "index must have app page container");
assert.ok(indexHtml.includes('id="halPageRoot"'), "index must have HAL root container");
assert.ok(!indexHtml.includes("page-sample-data.js"), "index must not load mock sample data");
assert.ok(!appJs.includes("Kiera Serrano"), "must not use fake operator name");
assert.ok(appJs.includes("renderRuntimeModeBanner"), "app must render an explicit browser/degraded-mode banner");
assert.ok(appJs.includes("desktopRequiredMessage(\"Full NR2 data access\")"), "browser banner must explain full data access requires desktop mode");
assert.ok(stylesCss.includes(".runtime-banner"), "styles must include runtime/degraded-mode banner styling");
assert.ok(indexHtml.includes("import-coordinator.js"), "index must load ImportCoordinator");
assert.ok(indexHtml.includes("import-diagnostics.js"), "index must load ImportDiagnostics");
assert.ok(indexHtml.includes("hal-proactive.js"), "index must load HalProactive");
assert.ok(indexHtml.includes("hal-office-manager.js"), "index must load HalOfficeManager");
assert.ok(indexHtml.includes("widget-contract.js"), "index must load WidgetContract");
assert.ok(indexHtml.includes("snapshot-store.js"), "index must load SnapshotStore");
assert.ok(indexHtml.includes("runtime-issues.js"), "index must load RuntimeIssues");
assert.ok(indexHtml.includes("office-task-store.js"), "index must load OfficeTaskStore");
assert.ok(!appJs.includes("await refreshHalWidgetFeed()") || appJs.includes("scheduleHalWidgetRefresh"), "side-note monitor must not poll full widget refresh");
const pageViewsJs = readFileSync(join(siteDir, "page-views.js"), "utf8");
assert.ok(pageViewsJs.includes("mountGeneration"), "page mount must use generation tokens to ignore stale renders");
assert.ok(pageViewsJs.includes("mountStillCurrent"), "page mount must verify current page before committing async HTML");

const ServicesMod = require(join(siteDir, "services.js"));
const SnapshotStorePage = require(join(siteDir, "snapshot-store.js"));
global.SnapshotStore = SnapshotStorePage;
SnapshotStorePage.invalidate("pages");
await SnapshotStorePage.get(() => ServicesMod.buildProgramSnapshotCore());
const dash = await ServicesMod.readDashboard("financial");
assert.ok(dash && dash.productionMtd, "readDashboard must return financial dashboard shape from snapshot");

const ImportDiagnostics = require(join(siteDir, "import-diagnostics.js"));
const ImportLoaderPage = require(join(siteDir, "import-loader.js"));
const manifest = JSON.parse(readFileSync(join(__dirname, "import-manifest.json"), "utf8"));
assert.ok(manifest.datasets["softdent.ar"].requiredFields.includes("Bucket"), "manifest must declare A/R required fields");
const diagBundle = {
  loadedAt: new Date().toISOString(),
  softdent: {
    dashboard: {
      sourceFile: "softdent_dashboard_data.json",
      modifiedAt: new Date().toISOString(),
      rows: [{ production: 500, collections: 400, period: "2026-06" }],
    },
  },
  quickbooks: {},
};
const diagnostics = ImportDiagnostics.evaluateBundle(diagBundle, manifest);
assert.ok(diagnostics.datasets.length === 11, "diagnostics must evaluate all manifest datasets");
["softdent.newPatients", "softdent.treatmentPlans", "softdent.caseAcceptance"].forEach((datasetKey) => {
  const item = diagnostics.datasets.find((row) => row.datasetKey === datasetKey);
  assert.ok(item && item.status === "not_configured", `${datasetKey} must report not_configured until exports exist`);
});
const importStatus = ImportLoaderPage.formatImportStatus(Object.assign({}, diagBundle, { diagnostics }));
assert.ok(importStatus.includes("Dataset health:"), "import status text must include dataset health block");

console.log("page validation passed");
