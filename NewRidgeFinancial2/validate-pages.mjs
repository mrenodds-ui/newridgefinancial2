#!/usr/bin/env node
/**
 * Validate approved mockup pages have been converted into real functional pages.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import { execSync } from "node:child_process";

const __dirname = dirname(fileURLToPath(import.meta.url));
const siteDir = join(__dirname, "site");
const require = createRequire(import.meta.url);

process.env.NR2_LOAD_IMPORTS = "1";

const appJs = readFileSync(join(siteDir, "app.js"), "utf8");
const indexHtml = readFileSync(join(siteDir, "index.html"), "utf8");
const buildManifest = JSON.parse(readFileSync(join(__dirname, "nr2-build.json"), "utf8"));
const expectedAssetVersion = buildManifest.assetVersion;
const mockEmbedMode = buildManifest.staffRenderMode === "mock-embed";
const pilotMode = buildManifest.staffRenderMode === "live-wire-pilot";
const liveWirePages = pilotMode && Array.isArray(buildManifest.liveWirePages) ? buildManifest.liveWirePages : [];
const stylesCss = readFileSync(join(siteDir, "styles.css"), "utf8");
const themeCss = readFileSync(join(siteDir, "nr2-moonshot-mockup-theme.css"), "utf8");
const vocabCss = readFileSync(join(siteDir, "nr2-mockup-page-vocabulary.css"), "utf8");

globalThis.NR2_STAFF_MOCK_ONLY = true;
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
if (!globalThis.HAL) {
  globalThis.HAL = { skills: { defineSource() {} } };
}
require(join(siteDir, "hal-skills.js"));
require(join(siteDir, "hal-widget-master-chart.js"));
require(join(siteDir, "hal-page-widgets.js"));
require(join(siteDir, "hal-live-widget-bridge.js"));
const HalPilotWidgets = require(join(siteDir, "hal-pilot-widgets.js"));
globalThis.__NR2_MOCKUP_ELITE_PAGES = undefined;
require(join(siteDir, "data/mockup-elite-pages.js"));
require(join(siteDir, "moonshot-page-registry.js"));
require(join(siteDir, "nr2-moonshot-mockup-chrome.js"));
require(join(siteDir, "tax-engine.js"));
require(join(siteDir, "nr2-moonshot-mockup-chrome.js"));
require(join(siteDir, "month-end-close.js"));
require(join(siteDir, "portal-ops.js"));
require(join(siteDir, "page-canvas-data.js"));
if (pilotMode) {
  globalThis.NR2_BUILD = buildManifest;
  globalThis.NR2_LIVE_WIRE_PAGES = liveWirePages;
  require(join(siteDir, "deferred-live-wire/moonshot-page-layouts.js"));
  require(join(siteDir, "deferred-live-wire/moonshot-layout-engine.js"));
}
require(join(siteDir, "page-canvas.js"));
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

const MOCKUP_EPOCH = PageSchema.LAYOUT_EPOCH === "moonshot-mockup";

const MOCK_PREVIEW_CHECKS = ["ms-mockup-preview-frame", "mockup-elite-embed", "ms-mockup-preview-iframe"];

const FUNCTIONAL_PAGES = [
  { id: "financial", checks: MOCK_PREVIEW_CHECKS },
  { id: "taxes", checks: MOCK_PREVIEW_CHECKS },
  { id: "softdent", checks: MOCK_PREVIEW_CHECKS },
  { id: "quickbooks", checks: MOCK_PREVIEW_CHECKS },
  { id: "ar", checks: MOCK_PREVIEW_CHECKS },
  { id: "claims", checks: MOCK_PREVIEW_CHECKS },
  { id: "narratives", checks: MOCK_PREVIEW_CHECKS },
  { id: "documents", checks: MOCK_PREVIEW_CHECKS },
  { id: "library", checks: MOCK_PREVIEW_CHECKS },
  { id: "office-manager", checks: MOCK_PREVIEW_CHECKS },
  { id: "hal", checks: MOCK_PREVIEW_CHECKS },
];

const HIGH_TECH_SURFACES = {};

for (const page of FUNCTIONAL_PAGES) {
  assert.ok(PageViews.hasPage(page.id), `${page.id} page must be routable`);
  const html = await PageViews.previewPageHtml(halData, page.id, previewWidgetFeed, previewSnapshot);
  assert.ok(!html.includes("pv--mock-image"), `${page.id} must NOT render a mockup image`);
  assert.ok(html.includes("ms-page"), `${page.id} must render mockup ms-page surface`);
  assert.ok(
    html.includes("ms-page-chrome--mock-embed") || html.includes("ms-page-chrome") || html.includes("hero"),
    `${page.id} must use mockup page chrome`,
  );
  if (mockEmbedMode || (pilotMode && !liveWirePages.includes(page.id))) {
    assert.ok(html.includes("ms-page-chrome--mock-embed"), `${page.id} must use compact mock-embed chrome`);
    assert.ok(html.includes("mock-embed-nav"), `${page.id} must render top mock-embed page nav`);
    assert.ok(!html.includes("sync-badge"), `${page.id} mock-embed must not show live sync badges`);
    assert.ok(!html.includes("ms-import-notice"), `${page.id} mock-embed must not show import notices`);
    assert.ok(!html.includes("storyboard-export-btn"), `${page.id} mock-embed must not show storyboard export chrome`);
    assert.ok(!html.includes("ms-hal-readiness-strip"), `${page.id} mock-embed must not show HAL readiness strip`);
    assert.ok(!html.includes("nr2-hal-readiness"), `${page.id} mock-embed must not show HAL readiness id`);
    assert.ok(!html.includes("page-header-tools"), `${page.id} mock-embed must not show page header tools`);
    assert.ok(!html.includes("filter-bar"), `${page.id} mock-embed must not show filter bar`);
    assert.ok(!html.includes("hal-insight"), `${page.id} mock-embed must not show HAL insight banner`);
    assert.ok(!html.includes('class="hero"'), `${page.id} mock-embed must not show page hero`);
    assert.ok(!html.includes("ms-mockup-preview-banner"), `${page.id} mock-embed must not show elite preview banner`);
  } else if (pilotMode && liveWirePages.includes(page.id)) {
    assert.ok(html.includes("ms-live-wire-pilot-banner"), `${page.id} live-wire pilot must show pilot banner`);
    assert.ok(!html.includes("ms-mockup-preview-iframe"), `${page.id} live-wire pilot must not use mock iframe`);
    assert.ok(html.includes(`${page.id}-moonshot`) || html.includes("widget-grid"), `${page.id} live-wire pilot must render layout engine body`);
  } else {
    assert.ok(html.includes("hal-insight") || html.includes("filter-bar") || page.id === "hal", `${page.id} must use mockup insight or filter bar`);
  }
  const pilotLivePage = pilotMode && liveWirePages.includes(page.id);
  const pilotMockPage = pilotMode && !liveWirePages.includes(page.id);
  if ((!mockEmbedMode && !pilotMode) || pilotLivePage) {
    if (page.id !== "office-manager" && page.id !== "hal") {
      assert.ok(
        html.includes("hal-insight") || html.includes("filter-bar"),
        `${page.id} must use insight or filter toolbar`,
      );
    }
  }
  for (const check of page.checks) {
    if (pilotMode && liveWirePages.includes(page.id)) continue;
    assert.ok(html.includes(check), `${page.id} must include ${check}`);
  }
  assert.ok(!html.includes("pv-canvas-hero"), `${page.id} must not render legacy pv-canvas hero`);
  assert.ok(!html.includes("pv-canvas-body"), `${page.id} must not render legacy pv-canvas body`);
  assert.ok(!html.includes("pv-canvas-grid-split"), `${page.id} must not render legacy pv-canvas grid split`);
  assert.ok(!html.includes("pv-card"), `${page.id} must not use legacy pv-card panels`);
  assert.ok(!html.includes("pv-table"), `${page.id} must not use legacy pv-table markup`);
  assert.ok(!html.includes("pv-ms-"), `${page.id} must not use legacy pv-ms chart classes`);
  assert.ok(!html.includes("pv-canvas-"), `${page.id} must not use legacy pv-canvas internals`);
  assert.ok(!html.includes("pv-badge"), `${page.id} must not use legacy pv-badge`);
  assert.ok(!html.match(/\bclass="[^"]*\bpv-/), `${page.id} must not use legacy pv-* class prefix in markup`);
  assert.ok(!html.match(/\bhp-[a-z]/), `${page.id} must not use legacy hp-* class prefix`);
  assert.ok(!html.includes("data-nr2-chart-host"), `${page.id} must not mount chart overlay hosts`);
  if (page.id === "financial") {
    if (pilotMode && liveWirePages.includes("financial")) {
      assert.ok(html.includes("financial-moonshot"), "financial live-wire pilot must render layout engine shell");
      assert.ok(!html.includes("ms-mockup-preview-iframe"), "financial live-wire pilot must not use mock iframe");
    } else {
      assert.ok(html.includes("ms-mockup-preview-frame"), "financial page must embed elite mock preview");
    }
    if (!mockEmbedMode && !(pilotMode && liveWirePages.includes("financial"))) {
      assert.ok(
        html.includes("hal-insight") || html.includes("HAL Insight"),
        "financial page must show HAL insight banner",
      );
    }
  }
  for (const cls of HIGH_TECH_SURFACES[page.id] || []) {
    assert.ok(html.includes(cls), `${page.id} must render high-tech HAL surface ${cls}`);
  }
}

assert.equal(PageViews.hasPage("hal"), true, "HAL must use elite mock embed in staff mock-only mode");

assert.ok(!appJs.includes("127.0.0.1:8765/api") && !appJs.includes('"/api/hal'), "app.js must not reference NR2 desktop backend API routes");
assert.ok(indexHtml.includes('id="appPage"'), "index must have app page container");
assert.ok(!indexHtml.includes('id="halPageRoot"'), "index must not use legacy HAL root container");
assert.ok(!indexHtml.includes('id="halPage"'), "index must not use legacy HAL page shell");
assert.ok(!indexHtml.includes("page-sample-data.js"), "index must not load mock sample data");
assert.ok(!appJs.includes("Kiera Serrano"), "must not use fake operator name");
assert.ok(appJs.includes("renderRuntimeModeBanner"), "app must render an explicit browser/degraded-mode banner");
assert.ok(appJs.includes("serverRequiredMessage(\"Full NR2 data access\")"), "offline banner must explain full data access requires NR2 server");
assert.ok(stylesCss.includes(".runtime-banner"), "styles must include runtime/degraded-mode banner styling");
assert.ok(indexHtml.includes("import-coordinator.js"), "index must load ImportCoordinator");
assert.ok(indexHtml.includes("import-diagnostics.js"), "index must load ImportDiagnostics");
assert.ok(indexHtml.includes("hal-proactive.js"), "index must load HalProactive");
assert.ok(indexHtml.includes("hal-office-manager.js"), "index must load HalOfficeManager");
assert.ok(indexHtml.includes("hal-page-widgets.js"), "index must load HalPageWidgets");
assert.ok(indexHtml.includes("hal-widget-master-chart.js"), "index must load HalWidgetMasterChart");
assert.ok(indexHtml.includes("hal-live-widget-bridge.js"), "index must load HalLiveWidgetBridge");
assert.ok(indexHtml.includes("NR2_FINANCIAL_ONLY"), "financial index must declare NR2_FINANCIAL_ONLY");
assert.ok(indexHtml.includes("nr2-moonshot-mockup-chrome.js"), "financial index must load mockup chrome");
const navRailHtml =
  typeof MoonshotMockupChrome !== "undefined" && MoonshotMockupChrome.renderNavRail
    ? MoonshotMockupChrome.renderNavRail("financial")
    : "";
assert.ok(navRailHtml.includes("nav-section"), "mockup nav must render grouped sections");
assert.ok(navRailHtml.includes("nav-practice"), "mockup nav must render practice block");
assert.ok(navRailHtml.includes('data-nav="hal"'), "mockup nav must include HAL");
if (mockEmbedMode || pilotMode) {
  assert.ok(!navRailHtml.includes("nav-sublist"), "mock-embed nav must hide widget subpages");
  assert.ok(
    indexHtml.includes('data-nr2-staff-render="mock-embed"') ||
      indexHtml.includes("setAttribute('data-nr2-staff-render','mock-embed'"),
    "index must tag mock-embed staff render mode",
  );
  assert.ok(indexHtml.includes("app--mock-embed-solo"), "mock-embed index must use solo layout without left rail");
  assert.ok(!indexHtml.includes('id="sidebar"'), "mock-embed index must not include left sidebar element");
}
if (pilotMode) {
  assert.ok(indexHtml.includes("deferred-live-wire/moonshot-page-layouts.js"), "pilot must load layout manifest");
  assert.ok(indexHtml.includes("deferred-live-wire/moonshot-layout-engine.js"), "pilot must load layout engine");
  assert.ok(indexHtml.includes("NR2_LIVE_WIRE_PAGES"), "pilot index must declare live-wire pages");
} else if (!mockEmbedMode) {
  assert.ok(indexHtml.includes('class="nav-rail"'), "financial index must use mockup nav-rail");
  assert.ok(navRailHtml.includes("nav-sublist"), "active page nav must render widget subpages");
  assert.ok(navRailHtml.includes("Practice Financial Overview"), "financial nav must list widget subpages");
}
assert.ok(indexHtml.includes("nr2-moonshot-mockup-theme.css"), "financial index must load moonshot mockup theme");
assert.ok(indexHtml.includes("nr2-mockup-page-vocabulary.css"), "financial index must load mockup page vocabulary CSS");
assert.ok(indexHtml.includes("data-nr2-program"), "financial index must tag html as financial program");
assert.equal(
  typeof PageSchema !== "undefined" ? PageSchema.LAYOUT_EPOCH : null,
  "moonshot-mockup",
  "PageSchema.LAYOUT_EPOCH must be moonshot-mockup",
);
assert.equal(buildManifest.REQUIRED_EPOCH, "moonshot-mockup", "nr2-build.json must require moonshot-mockup epoch");
assert.ok(
  pilotMode || mockEmbedMode,
  "nr2-build.json staffRenderMode must be mock-embed or live-wire-pilot",
);
if (pilotMode) {
  assert.ok(
    Array.isArray(buildManifest.liveWirePages) && buildManifest.liveWirePages.includes("financial"),
    "live-wire-pilot must include financial in liveWirePages",
  );
} else {
  assert.ok(!indexHtml.includes("moonshot-page-layouts.js"), "index must not load layout manifest in mock-embed mode");
  assert.ok(!indexHtml.includes("moonshot-layout-engine.js"), "index must not load layout engine until mock pages are wired");
}
assert.ok(indexHtml.includes("NR2_STAFF_MOCK_ONLY"), "index must enable staff mock-only mode");
assert.ok(indexHtml.includes("data/mockup-elite-pages.js"), "index must load mockup elite page manifest");
assert.ok(!indexHtml.includes("moonshot-page-layouts.json"), "index must not load external layout JSON");
assert.ok(!indexHtml.includes("charts/"), "index must not load chart overlay scripts in mock-embed mode");
assert.ok(!indexHtml.includes("nr2-tier3.js"), "index must not load tier-3 bundle in mock-embed mode");
assert.ok(indexHtml.includes("moonshot-page-registry.js"), "index must load Moonshot page registry");
assert.ok(indexHtml.includes("nr2-moonshot-mockup-chrome.js"), "index must load Moonshot mockup chrome");
assert.ok(!indexHtml.includes("page-chrome.js"), "index must not load legacy page-chrome.js");
assert.ok(!indexHtml.includes("page-schema.js"), "index must not load legacy page-schema.js");
assert.ok(!indexHtml.includes("hal-page-schema.js"), "index must not load legacy hal-page-schema.js");
assert.ok(indexHtml.includes("desktop-boot.js"), "index must load desktop boot gate");
const scriptVersions = [...indexHtml.matchAll(/\.js\?v=([^"&]+)/g)].map((match) => match[1]);
assert.ok(scriptVersions.length >= 1, "index must load versioned scripts");
for (const version of new Set(scriptVersions)) {
  assert.equal(version, expectedAssetVersion, `all index scripts must use asset version ${expectedAssetVersion}`);
}
assert.ok(
  indexHtml.includes(`styles.css?v=${expectedAssetVersion}`),
  `index styles.css must use asset version ${expectedAssetVersion}`,
);
assert.ok(!stylesCss.includes(".pv--mock-image"), "styles must not include legacy mock-image shell rules");
assert.ok(!stylesCss.includes(".pv__header"), "styles must not include legacy pv__header rules");
assert.equal(
  typeof PageSchema !== "undefined" ? PageSchema.SCHEMA_VERSION : null,
  expectedAssetVersion,
  "PageSchema.SCHEMA_VERSION must match nr2-build.json",
);
assert.equal(HalPilotWidgets.CANVAS_WIDGET_SCHEMA.mode, "canvas-feed", "staff pages must use canvas feed HAL wiring");
assert.ok(!stylesCss.includes(".pv-bento"), "styles must not include legacy bento layout rules");
assert.ok(!stylesCss.includes(".pv-canvas-hero"), "styles must not include legacy pv-canvas hero");
assert.ok(!stylesCss.includes(".pv-fin-"), "styles must not include legacy financial pv-* blocks");
assert.ok(themeCss.includes(".ms-page-chrome"), "moonshot theme must include ms-page-chrome");
assert.ok(themeCss.includes(".widget-card"), "moonshot theme must include widget-card");
assert.ok(vocabCss.includes(".ms-boot-error"), "mockup vocabulary must include ms-boot-error");
assert.ok(indexHtml.includes("widget-contract.js"), "index must load WidgetContract");
assert.ok(indexHtml.includes("snapshot-store.js"), "index must load SnapshotStore");
assert.ok(indexHtml.includes("runtime-issues.js"), "index must load RuntimeIssues");
assert.ok(indexHtml.includes("office-task-store.js"), "index must load OfficeTaskStore");
assert.ok(!appJs.includes("await refreshHalWidgetFeed()") || appJs.includes("scheduleHalWidgetRefresh"), "side-note monitor must not poll full widget refresh");
assert.ok(!indexHtml.includes('class="topbar"'), "index must not include legacy topbar shell");
assert.ok(appJs.includes("PageSchema.navPages") || appJs.includes("appPages"), "app must derive navigation from PageSchema");
assert.ok(indexHtml.includes("tax-engine.js"), "index must load TaxEngine");
assert.ok(indexHtml.includes("page-canvas-data.js"), "index must load PageCanvasData");
assert.ok(indexHtml.includes("page-canvas.js"), "index must load PageCanvas");
const pageViewsJs = readFileSync(join(siteDir, "page-views.js"), "utf8");
const pageCanvasJs = readFileSync(join(siteDir, "page-canvas.js"), "utf8");
assert.ok(!pageViewsJs.includes("PAGE_OUTLINES"), "page-views must not use legacy PAGE_OUTLINES");
assert.ok(!pageViewsJs.includes("MOCK_IMAGES"), "page-views must not use mock image routing");
assert.ok(!pageViewsJs.includes("readDashboard"), "page-views must not fetch legacy dashboard renderers");
assert.ok(pageViewsJs.includes("stripMockEmbedLiveChrome"), "page-views must strip live chrome in mock-embed mode");
assert.ok(pageViewsJs.includes("ms-hal-readiness-strip"), "page-views strip must remove HAL readiness strips");
const mockupChromeJs = readFileSync(join(siteDir, "nr2-moonshot-mockup-chrome.js"), "utf8");
assert.ok(mockupChromeJs.includes("pageChromeMockEmbed"), "mockup chrome must expose mock-embed page chrome");
assert.ok(
  mockupChromeJs.includes("if (staffMockEmbedMode()) return pageChromeMockEmbed") ||
    mockupChromeJs.includes("if (staffMockEmbedMode()) return pageChromeMockEmbed(state, schema, opts)") ||
    mockupChromeJs.includes("if (schema && staffMockEmbedPage(schema.id)) return pageChromeMockEmbed"),
  "pageChrome must redirect to mock-embed chrome",
);
  assert.ok(
    mockupChromeJs.includes("staffMockEmbedPage") && mockupChromeJs.includes("refreshHalReadinessStrip"),
    "refreshHalReadinessStrip must use staffMockEmbedPage in mock-embed / pilot mode",
  );
assert.ok(pageCanvasJs.includes("PageCanvasData") || pageCanvasJs.includes("dataApi"), "page-canvas must render from HAL program snapshot data");
assert.ok(pageCanvasJs.includes("ms-mockup-preview-frame"), "page-canvas must embed elite mock previews");
if (pilotMode) {
  assert.ok(
    pageCanvasJs.includes("shouldLiveWire") &&
      (pageCanvasJs.includes("MoonshotLayoutEngine.render") || pageCanvasJs.includes("LE.render")),
    "page-canvas must wire MoonshotLayoutEngine for pilot",
  );
} else {
  assert.ok(!pageCanvasJs.includes("MoonshotLayoutEngine.render"), "page-canvas must not wire MoonshotLayoutEngine in mock-embed mode");
}
assert.ok(Object.keys(PageSchema.PAGES || {}).length >= 10, "PageSchema must build pages from registry metadata");
assert.ok(!pageCanvasJs.includes("renderFinancial"), "page-canvas must not use legacy renderFinancial");
assert.ok(!pageCanvasJs.includes("renderQuickbooksLegacy"), "page-canvas must not use legacy QuickBooks renderer");
const pageCanvasDataJs = readFileSync(join(siteDir, "page-canvas-data.js"), "utf8");
assert.ok(pageCanvasDataJs.includes("financialImportNotice"), "page canvas data must expose financial import notice");
assert.ok(pageCanvasDataJs.includes("claimsImportNotice"), "page canvas data must expose claims import notice");
assert.ok(pageCanvasDataJs.includes("documentsImportNotice"), "page canvas data must expose documents import notice");
assert.ok(pageCanvasDataJs.includes("libraryImportNotice"), "page canvas data must expose library import notice");
assert.ok(pageCanvasDataJs.includes("officeManagerImportNotice"), "page canvas data must expose office manager import notice");
assert.ok(pageCanvasDataJs.includes("narrativesImportNotice"), "page canvas data must expose narratives import notice");
assert.ok(pageCanvasDataJs.includes("taxesImportNotice"), "page canvas data must expose taxes import notice");
assert.ok(pageCanvasDataJs.includes("monthEndBlockerStripHtml"), "page canvas data must expose month-end blocker strip");
assert.ok(pageCanvasDataJs.includes("documentsSourceBreakdown"), "page canvas data must expose documents source breakdown");
assert.ok(pageCanvasDataJs.includes("opsHealthPanelHtml"), "page canvas data must expose ops health panel");
assert.ok(pageViewsJs.includes("data-ops-refresh-health"), "page-views must wire ops health refresh button");
assert.ok(pageViewsJs.includes("data-ops-support-bundle"), "page-views must wire support bundle button");
assert.ok(pageCanvasJs.includes("canvasImportNotice"), "page-canvas must render import notices on staff pages");

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
["softdent.newPatients", "softdent.treatmentPlans", "softdent.caseAcceptance", "softdent.hygieneRecall", "softdent.operatory", "softdent.procedures", "softdent.claimStatus"].forEach((datasetKey) => {
  const item = diagnostics.datasets.find((row) => row.datasetKey === datasetKey);
  assert.ok(item && item.status === "missing", `${datasetKey} must report missing until exports exist`);
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

execSync("node scripts/audit-mockup-parity.mjs", { cwd: __dirname, stdio: "inherit" });
execSync("node scripts/compare-mockup-elite-embed.mjs", { cwd: __dirname, stdio: "inherit" });
execSync("node scripts/rebuild-moonshot-site.mjs --dry-run", { cwd: __dirname, stdio: "pipe" });

console.log("page validation passed");
