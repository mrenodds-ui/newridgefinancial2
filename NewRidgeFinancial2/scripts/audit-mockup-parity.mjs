#!/usr/bin/env node
/**
 * Assert staff pages embed elite mock HTML and that elite mockups avoid legacy bridge classes.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");
const site = join(root, "site");
const mockupsElite = join(root, "..", ".local_logs", "moonshot_financial_eval", "page_mockups_elite");
const require = createRequire(import.meta.url);

process.env.NR2_LOAD_IMPORTS = "1";
globalThis.NR2_STAFF_MOCK_ONLY = true;
for (const f of [
  "empty-states.js",
  "import-diagnostics.js",
  "import-loader.js",
  "runtime-issues.js",
  "snapshot-store.js",
  "import-coordinator.js",
  "office-task-store.js",
  "hal-proactive.js",
  "hal-office-manager.js",
  "widget-contract.js",
  "hal-skills.js",
  "hal-widget-master-chart.js",
  "hal-page-widgets.js",
  "hal-live-widget-bridge.js",
  "data/mockup-elite-pages.js",
  "moonshot-page-registry.js",
  "nr2-moonshot-mockup-chrome.js",
  "tax-engine.js",
  "nr2-moonshot-mockup-chrome.js",
  "page-canvas-data.js",
  "page-canvas.js",
  "components.js",
]) {
  if (f === "hal-skills.js" && !globalThis.HAL) {
    globalThis.HAL = { skills: { defineSource() {} } };
  }
  require(join(site, f));
}

const Services = require(join(site, "services.js"));
const PageViews = require(join(site, "page-views.js"));
const SnapshotStore = require(join(site, "snapshot-store.js"));
global.SnapshotStore = SnapshotStore;
SnapshotStore.invalidate("mockup-parity");

const halData = JSON.parse(readFileSync(join(site, "data", "hal-manager.json"), "utf8"));
const snap = await SnapshotStore.get(() => Services.buildProgramSnapshotCore());
const feed = require(join(site, "hal-skills.js")).buildWidgetFeed(snap);

const FORBIDDEN_BODY = [
  /\bms-hbar/,
  /\bms-heatmap/,
  /\bms-queue/,
  /\bms-table/,
  /\bms-editor/,
  /\bms-composer/,
  /\bms-sidebar/,
  /\bms-doc-grid/,
  /\bwidget-kanban/,
  /\bms-funnel/,
  /\bms-gauge/,
  /\bms-vbars/,
  /\bms-hbars/,
];

const ELITE_PAGE_REQUIRED = {
  financial: ["widget-grid", "alert-ticker", "kpi-hero-row", "ms-panel", "data-hal-widget-key"],
  ar: ["widget-grid", "kpi-hero", "ms-panel", "kanban-wrap", "data-hal-widget-key"],
  claims: ["kanban", "data-hal-widget-key"],
  narratives: ["kanban", "data-hal-widget-key"],
  "office-manager": ["dashboard-grid", "kpi-hero", "data-hal-widget-key"],
  library: ["search-box", "glass-panel", "data-hal-widget-key"],
  documents: ["widget-grid", "ms-panel", "data-table", "preview-panel"],
  softdent: ["funnel", "data-hal-widget-key"],
  quickbooks: ["dashboard-grid", "glass-panel", "data-hal-widget-key"],
  taxes: ["widget-grid", "ms-panel", "data-hal-widget-key"],
};

let failures = 0;
for (const pageId of PageSchema.STAFF_PAGE_IDS || []) {
  const html = await PageViews.previewPageHtml(halData, pageId, feed, snap);
  if (!html.includes("ms-mockup-preview-frame")) {
    console.error(`FAIL ${pageId}: staff page must use elite mock embed gate`);
    failures += 1;
    continue;
  }
  if (!html.includes(`/mockup-elite-embed/${pageId}`)) {
    console.error(`FAIL ${pageId}: missing mockup-elite-embed iframe src`);
    failures += 1;
  }

  const mockupPath = join(mockupsElite, `${pageId}.html`);
  let mockHtml = "";
  try {
    mockHtml = readFileSync(mockupPath, "utf8");
  } catch {
    console.warn(`WARN ${pageId}: no elite mockup html at ${mockupPath}`);
    continue;
  }

  for (const re of FORBIDDEN_BODY) {
    if (re.test(mockHtml)) {
      console.error(`FAIL ${pageId}: forbidden legacy class in elite mock ${re}`);
      failures += 1;
    }
  }

  const required = ELITE_PAGE_REQUIRED[pageId] || ["ms-panel", "data-hal-widget-key"];
  for (const cls of required) {
    if (!mockHtml.includes(cls)) {
      console.error(`FAIL ${pageId}: elite mock missing class ${cls}`);
      failures += 1;
    }
  }

  if (pageId === "softdent") {
    const funnelSteps = (mockHtml.match(/class="funnel-step(?:[^"]*)"/g) || mockHtml.match(/class="funnel(?:[^"]*)"/g) || []).length;
    if (funnelSteps < 1) {
      console.error(`FAIL softdent: expected funnel markup, got ${funnelSteps}`);
      failures += 1;
    }
  }
}

assert.equal(failures, 0, `${failures} mockup parity violation(s)`);
console.log(`mockup parity OK — ${(PageSchema.STAFF_PAGE_IDS || []).length} staff pages`);
