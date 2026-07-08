#!/usr/bin/env node
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");
const site = join(root, "site");
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
  "hal-page-schema.js",
  "hal-page-canvas.js",
  "hal-page.js",
]) {
  if (f === "hal-skills.js" && !globalThis.HAL) {
    globalThis.HAL = { skills: { defineSource() {} } };
  }
  require(join(site, f));
}

const Services = require(join(site, "services.js"));
const PageViews = require(join(site, "page-views.js"));
const HalPageMod = require(join(site, "hal-page.js"));
const SnapshotStore = require(join(site, "snapshot-store.js"));
global.SnapshotStore = SnapshotStore;
SnapshotStore.invalidate("schema-audit");

const halData = JSON.parse(readFileSync(join(site, "data", "hal-manager.json"), "utf8"));
const halModels = JSON.parse(readFileSync(join(site, "data", "hal-models.json"), "utf8"));

const LEGACY_PATTERNS = [
  { id: "pv-canvas", re: /pv-canvas-/i },
  { id: "pv-badge", re: /\bpv-badge\b/i },
  { id: "pv-chip", re: /\bpv-chip\b/i },
  { id: "pv-table", re: /\bpv-table\b/i },
  { id: "pv-canvas-insight", re: /\bpv-canvas-insight\b/i },
  { id: "pv-filter-pill", re: /\bpv-filter-pill\b/i },
  { id: "pv-hal-command", re: /\bpv-hal-command\b/i },
  { id: "pv-ms-", re: /pv-ms-/i },
  { id: "pv--canvas", re: /pv--canvas/i },
  { id: "hp-grid", re: /\bhp-grid\b/i },
  { id: "hp-card", re: /\bhp-card\b/i },
  { id: "hp-prefix", re: /\bhp-[a-z]/i },
  { id: "nav-group", re: /\bnav-group\b/i },
  { id: "brand-canvas", re: /\bbrand--canvas\b/i },
  { id: "class=hp", re: /class="hp"/i },
  { id: "pv-hal-widget", re: /\bpv-hal-widget\b/i },
  { id: "pv-filter", re: /pv-filter/i },
  { id: "canvasShell", re: /pv-canvas-shell/i },
];

function scan(label, html) {
  const found = LEGACY_PATTERNS.filter((p) => p.re.test(html)).map((p) => p.id);
  return { label, found, ok: found.length === 0 };
}

const snap = await SnapshotStore.get(() => Services.buildProgramSnapshotCore());
const feed = require(join(site, "hal-skills.js")).buildWidgetFeed(snap);
const pages = PageSchema.STAFF_PAGE_IDS || [];
const results = [];

for (const id of pages) {
  const html = await PageViews.previewPageHtml(halData, id, feed, snap);
  results.push(scan(id, html));
}

let halHtml = "";
const halRoot = {
  set innerHTML(value) {
    halHtml = value;
  },
  get innerHTML() {
    return halHtml;
  },
  querySelector() {
    return null;
  },
  querySelectorAll() {
    return [];
  },
};

HalPageMod.render({
  root: halRoot,
  halData,
  halModels,
  halWidgetFeed: feed,
  halProgramSnapshot: snap,
  halAskDraft: "",
  halAskLoading: false,
  halChatHistory: [],
  halAudit: [],
  halSideNotes: [],
  halSideNoteMonitor: {},
  halSideNotesInbox: {},
  sidenotesHubPath: "",
});

results.push(scan("hal", halHtml));

const bad = results.filter((r) => !r.ok);
console.log(JSON.stringify({ bad, all: results }, null, 2));
process.exit(bad.length ? 1 : 0);
