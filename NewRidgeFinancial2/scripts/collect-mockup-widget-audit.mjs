#!/usr/bin/env node
/** Collect mockup-vs-live parity + widget feed audit for Moonshot consultation. */
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");
const site = join(root, "site");
const mockups = join(root, "..", ".local_logs", "moonshot_financial_eval", "page_mockups");
const outDir = join(root, "..", ".local_logs", "moonshot_financial_eval");
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
  "moonshot-page-layouts.js",
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
const HalSkills = require(join(site, "hal-skills.js"));
global.SnapshotStore = SnapshotStore;
SnapshotStore.invalidate("moonshot-audit");

const MOCKUP_CLASSES = [
  "widget-grid",
  "dashboard-grid",
  "kpi-card",
  "kpi-grid",
  "kpi-tile",
  "provider-list",
  "chart-container",
  "heatmap-grid",
  "queue-list",
  "kanban-board",
  "claim-card",
  "composer-grid",
  "stats-bar",
  "funnel-chart",
  "operatory-grid",
  "tax-split-chart",
  "document-grid",
  "data-table",
  "sync-badge",
  "kpi-ribbon",
  "nr2-alert-ticker",
  "side-panel",
  "search-container",
  "widget-card",
  "chart-large",
  "chart-medium",
  "chart-full",
];

function countClass(html, cls) {
  return (html.match(new RegExp(`\\b${cls}\\b`, "g")) || []).length;
}

const halData = JSON.parse(readFileSync(join(site, "data", "hal-manager.json"), "utf8"));
const snap = await SnapshotStore.get(() => Services.buildProgramSnapshotCore());
const feed = HalSkills.buildWidgetFeed(snap);
const pages = PageSchema.STAFF_PAGE_IDS || [];

const lines = ["# NR2 Mockup Parity + Widget Data Audit", "", `Generated: ${new Date().toISOString()}`, ""];

lines.push("## Page-by-page mockup vs live HTML");
for (const pageId of pages) {
  const liveHtml = await PageViews.previewPageHtml(halData, pageId, feed, snap);
  let mockHtml = "";
  try {
    mockHtml = readFileSync(join(mockups, `${pageId}.html`), "utf8");
  } catch {
    lines.push(`### ${pageId}`, "- **NO MOCKUP FILE**", "");
    continue;
  }
  const diffs = [];
  for (const cls of MOCKUP_CLASSES) {
    const mockCount = countClass(mockHtml, cls);
    const liveCount = countClass(liveHtml, cls);
    if (mockCount > 0 && liveCount === 0) diffs.push(`MISSING \`${cls}\` (mock has ${mockCount})`);
    else if (mockCount > 0 && liveCount > 0 && Math.abs(mockCount - liveCount) > Math.max(1, mockCount * 0.4)) {
      diffs.push(`COUNT \`${cls}\`: mock=${mockCount} live=${liveCount}`);
    }
  }
  const emptyWidgets = (liveHtml.match(/widget-empty|No data yet|empty-state/gi) || []).length;
  const schema = PageSchema.byId(pageId);
  const widgetKeys = ((schema && schema.widgets) || []).map((w) => w.key);
  const wired = widgetKeys.filter((k) => liveHtml.includes(`data-hal-widget-key="${k}"`));
  const missingWire = widgetKeys.filter((k) => !liveHtml.includes(`data-hal-widget-key="${k}"`));

  lines.push(`### ${pageId}`);
  lines.push(`- Empty/placeholder markers in live HTML: **${emptyWidgets}**`);
  lines.push(`- HAL widget keys wired: **${wired.length}/${widgetKeys.length}**`);
  if (missingWire.length) lines.push(`- Unwired keys: ${missingWire.join(", ")}`);
  if (diffs.length) {
    lines.push("- Mockup class mismatches:");
    for (const d of diffs) lines.push(`  - ${d}`);
  } else {
    lines.push("- Mockup class counts: **aligned** (structural parity pass)");
  }
  lines.push("");
}

lines.push("## Widget feed readiness");
const widgets = feed && feed.widgets ? Object.entries(feed.widgets) : [];
let emptyCount = 0;
let dataCount = 0;
for (const [key, val] of widgets) {
  const status = val && (val.status || val.readiness || val.state || val.placement);
  const isEmpty =
    !val ||
    val.empty === true ||
    status === "empty" ||
    status === "missing" ||
    status === "no-data" ||
    status === "blocked";
  if (isEmpty) {
    emptyCount += 1;
    lines.push(`- **EMPTY** \`${key}\` status=${status || "unknown"}`);
  } else {
    dataCount += 1;
  }
}
lines.push("");
lines.push(`Summary: **${dataCount}** widgets with data, **${emptyCount}** empty/missing of **${widgets.length}** total.`);
if (feed && feed.sourceHealth) {
  lines.push("");
  lines.push("### sourceHealth");
  lines.push("```json");
  lines.push(JSON.stringify(feed.sourceHealth, null, 2).slice(0, 8000));
  lines.push("```");
}

if (snap && snap.importDiagnostics) {
  lines.push("");
  lines.push("### importDiagnostics (summary)");
  lines.push("```json");
  lines.push(JSON.stringify(snap.importDiagnostics, null, 2).slice(0, 6000));
  lines.push("```");
}

mkdirSync(outDir, { recursive: true });
const outPath = join(outDir, "MOCKUP_WIDGET_AUDIT_LATEST.md");
writeFileSync(outPath, lines.join("\n"), "utf8");
console.log(outPath);
console.log(lines.join("\n"));
