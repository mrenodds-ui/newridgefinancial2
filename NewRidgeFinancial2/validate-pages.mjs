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
require(join(siteDir, "hal-widget-master-chart.js"));
require(join(siteDir, "hal-page-widgets.js"));
require(join(siteDir, "hal-live-widget-bridge.js"));
const HalPilotWidgets = require(join(siteDir, "hal-pilot-widgets.js"));
require(join(siteDir, "components.js"));
const ServicesMod = require(join(siteDir, "services.js"));
const PageViews = require(join(siteDir, "page-views.js"));
const HalSkills = require(join(siteDir, "hal-skills.js"));
const halData = JSON.parse(readFileSync(join(siteDir, "data", "hal-manager.json"), "utf8"));

const SnapshotStorePage = require(join(siteDir, "snapshot-store.js"));
global.SnapshotStore = SnapshotStorePage;
SnapshotStorePage.invalidate("pages-preview");
const previewSnapshot = await SnapshotStorePage.get(() => ServicesMod.buildProgramSnapshotCore());
const previewWidgetFeed = HalSkills.buildWidgetFeed(previewSnapshot);

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

const HIGH_TECH_SURFACES = {
  financial: ["pv-hal-echart", "pv-hal-tabulator", "pv-hal-command"],
  softdent: ["pv-hal-grid", "pv-hal-command"],
  quickbooks: ["pv-hal-grid", "pv-hal-command"],
  ar: ["pv-hal-grid", "pv-hal-kanban", "pv-hal-command"],
  claims: ["pv-hal-kanban"],
  narratives: ["pv-hal-editor"],
  documents: ["pv-hal-grid", "pv-hal-pdf"],
  library: ["pv-hal-pdf"],
  "office-manager": ["pv-hal-kanban", "pv-hal-timeline", "pv-hal-command"],
};

for (const page of FUNCTIONAL_PAGES) {
  assert.ok(PageViews.hasPage(page.id), `${page.id} page must be routable`);
  const html = await PageViews.previewPageHtml(halData, page.id, previewWidgetFeed);
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
  if (page.id !== "office-manager") {
    assert.ok(html.includes("data-hal-widget-key"), `${page.id} must wire HAL into page widgets`);
    assert.ok(html.includes("pv-hal-strip") || html.includes("pv-hal-widget__badge"), `${page.id} must show HAL placement chrome`);
  }
  if (page.id === "financial") {
    assert.ok(!html.includes("Dr. Adams"), "financial page must not render sample provider names");
    assert.ok(!html.includes("Hygiene Team"), "financial page must not render sample provider names");
    assert.ok(html.includes("pv-hal-echart"), "financial page must include HAL ECharts pilot");
    assert.ok(html.includes("pv-hal-tabulator"), "financial page must include HAL Tabulator pilot");
    assert.ok(
      html.includes("Awaiting import data") || html.includes("pv-badge--import") || html.includes("Partial import"),
      "financial page must show honest import state",
    );
  }
  for (const cls of HIGH_TECH_SURFACES[page.id] || []) {
    assert.ok(html.includes(cls), `${page.id} must render high-tech HAL surface ${cls}`);
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
assert.ok(indexHtml.includes("hal-page-widgets.js"), "index must load HalPageWidgets");
assert.ok(indexHtml.includes("hal-widget-master-chart.js"), "index must load HalWidgetMasterChart");
assert.ok(indexHtml.includes("hal-live-widget-bridge.js"), "index must load HalLiveWidgetBridge");
assert.ok(indexHtml.includes("hal-pilot-widgets.js"), "index must load HalPilotWidgets");
assert.equal(HalPilotWidgets.LEGACY_WIDGET_SCHEMA.mode, "preserve-existing-page-data", "plain widgets must preserve the old page data schema");
assert.ok(stylesCss.includes(".pv-hal-grid"), "styles must include AG Grid plain styling");
assert.ok(stylesCss.includes(".pv-hal-kanban"), "styles must include Kanban plain styling");
assert.ok(stylesCss.includes(".pv-hal-pdf"), "styles must include PDF plain styling");
assert.ok(indexHtml.includes("widget-contract.js"), "index must load WidgetContract");
assert.ok(indexHtml.includes("snapshot-store.js"), "index must load SnapshotStore");
assert.ok(indexHtml.includes("runtime-issues.js"), "index must load RuntimeIssues");
assert.ok(indexHtml.includes("office-task-store.js"), "index must load OfficeTaskStore");
assert.ok(!appJs.includes("await refreshHalWidgetFeed()") || appJs.includes("scheduleHalWidgetRefresh"), "side-note monitor must not poll full widget refresh");
const pageViewsJs = readFileSync(join(siteDir, "page-views.js"), "utf8");
assert.ok(pageViewsJs.includes("mountGeneration"), "page mount must use generation tokens to ignore stale renders");
assert.ok(pageViewsJs.includes("mountStillCurrent"), "page mount must verify current page before committing async HTML");
assert.ok(pageViewsJs.includes("sourceExpired"), "documents preview must handle expired source files");
assert.ok(pageViewsJs.includes("fileUnavailable"), "documents preview must show unavailable source message");

const ServicesModValidate = ServicesMod;
const SnapshotStorePageValidate = SnapshotStorePage;
global.SnapshotStore = SnapshotStorePageValidate;
SnapshotStorePageValidate.invalidate("pages");
await SnapshotStorePageValidate.get(() => ServicesModValidate.buildProgramSnapshotCore());
const dash = await ServicesModValidate.readDashboard("financial");
assert.ok(dash && dash.productionMtd, "readDashboard must return financial dashboard shape from snapshot");

const ImportDiagnostics = require(join(siteDir, "import-diagnostics.js"));
const ImportLoaderPage = require(join(siteDir, "import-loader.js"));
const qbBundle = await ImportLoaderPage.loadBundle(false);
assert.ok(qbBundle && qbBundle.quickbooks && qbBundle.quickbooks.profitAndLoss, "import bundle must expose quickbooks.profitAndLoss");
assert.ok((qbBundle.quickbooks.profitAndLoss.rows || []).length >= 1, "profitAndLoss dataset must load rows from CSV");
const plNet = (qbBundle.quickbooks.profitAndLoss.rows[0] || {}).NetIncome;
if (plNet != null && plNet !== "") {
  assert.ok(!String(plNet).includes("00000000000"), "profitAndLoss NetIncome must be rounded");
}
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
assert.ok(diagnostics.datasets.length === Object.keys(manifest.datasets).length, "diagnostics must evaluate all manifest datasets");
["softdent.newPatients", "softdent.treatmentPlans", "softdent.caseAcceptance"].forEach((datasetKey) => {
  const item = diagnostics.datasets.find((row) => row.datasetKey === datasetKey);
  assert.ok(item && item.status === "not_configured", `${datasetKey} must report not_configured until exports exist`);
});
const importStatus = ImportLoaderPage.formatImportStatus(Object.assign({}, diagBundle, { diagnostics }));
assert.ok(importStatus.includes("Dataset health:"), "import status text must include dataset health block");

// Documents page must render synced document rows. Inject a fake desktop bridge
// whose document sync returns a populated queue, then confirm the service exposes
// those rows so the Accounting Documents page can render them.
const priorBridge = global.DesktopBridge;
global.DesktopBridge = {
  hasDesktopApi: () => true,
  async storageGet() {
    return null;
  },
  async storageSet() {},
  async syncAccountingDocuments() {
    return {
      syncedAt: new Date().toISOString(),
      queueCount: 1,
      state: {
        entity: "New Ridge Family Financial",
        queue: [
          { id: "GL-2026-0616", type: "Invoice", vendor: "Glidewell", date: "2026-06-16", amount: "$221.40", status: "Pending Review", statusTone: "warn", age: 14, autoImported: true },
        ],
        previewById: {},
        period: { label: "2026-06", documents: 1 },
      },
    };
  },
};
const docList = await ServicesMod.documents.list();
assert.ok(Array.isArray(docList.queue) && docList.queue.length === 1, "documents.list must expose synced document rows");
assert.ok(docList.queue[0].vendor === "Glidewell", "synced document row must carry vendor from sync state");
if (priorBridge === undefined) {
  delete global.DesktopBridge;
} else {
  global.DesktopBridge = priorBridge;
}

console.log("page validation passed");
