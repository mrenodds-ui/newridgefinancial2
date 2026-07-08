#!/usr/bin/env node
/**
 * Assert staff page bodies use mockup vocabulary from page_mockups/*.html
 * instead of legacy ms-* bridge / widget-kanban classes.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");
const site = join(root, "site");
const mockups = join(root, "..", ".local_logs", "moonshot_financial_eval", "page_mockups");
const require = createRequire(import.meta.url);

process.env.NR2_LOAD_IMPORTS = "1";
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
  "page-schema.js",
  "nr2-moonshot-mockup-chrome.js",
  "tax-engine.js",
  "page-chrome.js",
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

const PAGE_REQUIRED = {
  financial: ["provider-list", "chart-container", "widget-card", "nr2-alert-ticker", "kpi-ribbon"],
  ar: ["kpi-grid", "kpi-tile", "heatmap-grid", "queue-list", "queue-item"],
  claims: ["kanban-board", "kanban-column", "claim-card", "side-panel"],
  narratives: ["composer-grid", "panel", "composer-textarea", "cdt-list"],
  "office-manager": ["stats-bar", "stat-item", "focus-list"],
  library: ["search-container", "search-box", "document-grid", "doc-card"],
  documents: ["data-table", "doc-preview"],
  softdent: ["widget-card", "funnel-chart", "funnel-label", "operatory-grid"],
  quickbooks: ["dashboard-grid", "kpi-card", "sync-badge"],
  taxes: ["widget-card", "tax-split-chart"],
};

let failures = 0;
for (const pageId of PageSchema.STAFF_PAGE_IDS || []) {
  const html = await PageViews.previewPageHtml(halData, pageId, feed, snap);
  const bodyStart = html.indexOf("widget-grid") >= 0 ? html.indexOf("widget-grid") : html.indexOf("composer-grid");
  const body = bodyStart >= 0 ? html.slice(bodyStart) : html;

  for (const re of FORBIDDEN_BODY) {
    if (re.test(body)) {
      console.error(`FAIL ${pageId}: forbidden legacy class ${re}`);
      failures += 1;
    }
  }

  const required = PAGE_REQUIRED[pageId] || ["widget-card"];
  for (const cls of required) {
    if (!html.includes(cls)) {
      console.error(`FAIL ${pageId}: missing mockup class ${cls}`);
      failures += 1;
    }
  }

  if (pageId === "softdent") {
    const funnelSteps = (html.match(/class="funnel-step(?:[^"]*)"/g) || []).length;
    if (funnelSteps < 4) {
      console.error(`FAIL softdent: expected 4 funnel-step rows, got ${funnelSteps}`);
      failures += 1;
    }
  }

  const mockupPath = join(mockups, `${pageId}.html`);
  const SIGNATURE_BY_PAGE = {
    financial: ["provider-list", "chart-container", "nr2-alert-ticker", "kpi-ribbon"],
    quickbooks: ["dashboard-grid", "kpi-card", "sync-badge"],
    ar: ["kpi-grid", "heatmap-grid", "queue-list"],
    claims: ["kanban-board", "claim-card", "side-panel"],
    narratives: ["composer-grid", "composer-textarea"],
    "office-manager": ["stats-bar"],
  };
  const signature = SIGNATURE_BY_PAGE[pageId];
  if (signature) {
    for (const cls of signature) {
      if (!html.includes(cls)) {
        console.error(`FAIL ${pageId}: expected mockup signature class ${cls}`);
        failures += 1;
      }
    }
  } else {
    try {
      readFileSync(mockupPath, "utf8");
    } catch {
      console.warn(`WARN ${pageId}: no mockup html at ${mockupPath}`);
    }
  }
}

assert.equal(failures, 0, `${failures} mockup parity violation(s)`);
console.log(`mockup parity OK — ${(PageSchema.STAFF_PAGE_IDS || []).length} staff pages`);
