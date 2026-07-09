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
const buildManifest = JSON.parse(readFileSync(join(root, "nr2-build.json"), "utf8"));
const mockEmbedMode = buildManifest.staffRenderMode === "mock-embed";
const pilotMode = buildManifest.staffRenderMode === "live-wire-pilot";
const liveWirePages =
  pilotMode && Array.isArray(buildManifest.liveWirePages) ? buildManifest.liveWirePages : [];
globalThis.NR2_STAFF_MOCK_ONLY = mockEmbedMode;
globalThis.NR2_STAFF_RENDER_MODE = buildManifest.staffRenderMode || (mockEmbedMode ? "mock-embed" : "live-wire-pilot");
globalThis.NR2_BUILD = buildManifest;
globalThis.NR2_LIVE_WIRE_PAGES = liveWirePages;
if (typeof document === "undefined") {
  globalThis.document = {
    documentElement: {
      _attrs: Object.create(null),
      setAttribute(k, v) {
        this._attrs[k] = String(v);
      },
      getAttribute(k) {
        return Object.prototype.hasOwnProperty.call(this._attrs, k) ? this._attrs[k] : null;
      },
    },
  };
}
try {
  document.documentElement.setAttribute(
    "data-nr2-staff-render",
    mockEmbedMode ? "mock-embed" : "live-wire-pilot",
  );
} catch (_e) {
  /* ignore */
}
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
  ...(pilotMode
    ? [
        "deferred-live-wire/moonshot-page-layouts.js",
        "deferred-live-wire/moonshot-layout-engine.js",
      ]
    : []),
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
  hal: ["ms-panel", "data-hal-widget-key", "data-hal-cmd"],
};

let failures = 0;
const staffIds = PageSchema.STAFF_PAGE_IDS || liveWirePages || [];
for (const pageId of staffIds) {
  const html = await PageViews.previewPageHtml(halData, pageId, feed, snap);
  const livePage = pilotMode && liveWirePages.includes(pageId);
  if (livePage) {
    // Moonshot VAL-001 / full-program audit: live-wire must NOT use iframe elite embed gate
    if (html.includes("ms-mockup-preview-iframe") || html.includes("ms-mockup-preview-frame")) {
      console.error(`FAIL ${pageId}: live-wire must not use elite mock embed iframe`);
      failures += 1;
      continue;
    }
    if (!html.includes("ms-mission-control") && !html.includes(`${pageId}-moonshot`)) {
      console.error(`FAIL ${pageId}: live-wire must render layout engine shell`);
      failures += 1;
    }
    if (!html.includes("ms-page-header") && !html.includes("ms-page-title")) {
      console.error(`FAIL ${pageId}: live-wire must render page header from layout spec`);
      failures += 1;
    }
  } else {
    if (!html.includes("ms-mockup-preview-frame")) {
      console.error(`FAIL ${pageId}: staff page must use elite mock embed gate`);
      failures += 1;
      continue;
    }
    if (!html.includes(`/mockup-elite-embed/${pageId}`)) {
      console.error(`FAIL ${pageId}: missing mockup-elite-embed iframe src`);
      failures += 1;
    }
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

  const widgetKeyRe = /data-hal-widget-key="([^"]+)"/g;
  const eliteKeys = [...mockHtml.matchAll(widgetKeyRe)].map((m) => m[1]);
  const registrySrc = readFileSync(join(root, "site/moonshot-page-registry.js"), "utf8");
  const metaBlock = registrySrc.match(new RegExp(`\\b${pageId}:\\s*\\{[\\s\\S]*?widgets:\\s*\\[([\\s\\S]*?)\\]`, "m"));
  if (metaBlock) {
    const expectedKeys = [...metaBlock[1].matchAll(/key:\s*"([^"]+)"/g)].map((m) => m[1]);
    if (expectedKeys.length) {
      const missing = expectedKeys.filter((k) => !eliteKeys.includes(k));
      const dupes = eliteKeys.filter((k, i) => eliteKeys.indexOf(k) !== i);
      if (missing.length) {
        console.error(`FAIL ${pageId}: elite mock missing widget keys ${missing.join(", ")}`);
        failures += 1;
      }
      if (dupes.length) {
        console.error(`FAIL ${pageId}: duplicate widget keys ${[...new Set(dupes)].join(", ")}`);
        failures += 1;
      }
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
console.log(`mockup parity OK — ${staffIds.length} staff pages`);
