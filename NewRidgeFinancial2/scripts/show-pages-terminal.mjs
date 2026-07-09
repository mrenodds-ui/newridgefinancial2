#!/usr/bin/env node
/**
 * Render all staff + HAL pages and print a terminal summary.
 */
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const site = join(__dirname, "..", "site");
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
  "page-canvas-data.js",
  "moonshot-layout-engine.js",
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
SnapshotStore.invalidate("terminal-pages");

const halData = JSON.parse(readFileSync(join(site, "data", "hal-manager.json"), "utf8"));
const snap = await SnapshotStore.get(() => Services.buildProgramSnapshotCore());
const feed = require(join(site, "hal-skills.js")).buildWidgetFeed(snap);

require(join(site, "hal-page.js"));
require(join(site, "hal-page-canvas.js"));
const HalPage = require(join(site, "hal-page.js"));

const halModels = JSON.parse(readFileSync(join(site, "data", "hal-models.json"), "utf8"));

function mockHalRoot() {
  const store = { innerHTML: "" };
  return {
    innerHTML: "",
    set innerHTML(v) {
      store.innerHTML = String(v == null ? "" : v);
    },
    get innerHTML() {
      return store.innerHTML;
    },
    querySelector() {
      return null;
    },
    querySelectorAll() {
      return [];
    },
  };
}

const pages = [...PageSchema.STAFF_PAGE_IDS, "hal"];
const W = 72;
const line = (c = "─") => c.repeat(W);
const pad = (s, n) => String(s).slice(0, n).padEnd(n);

console.log("");
console.log(" NR2 Moonshot Pages — renderBody preview (terminal)");
console.log(" " + line());
console.log(" Snapshot:", snap?.label || "(no label)");
console.log(" Render path: PageCanvas.renderBody → PageViews.previewPageHtml");
console.log(" " + line());

for (const pageId of pages) {
  let html = "";
  const title = PageSchema.byId(pageId)?.title || pageId;
  if (pageId === "hal") {
    const root = mockHalRoot();
    HalPage.render({
      root,
      halData,
      halModels,
      halWidgetFeed: feed,
      halProgramSnapshot: snap,
      halChatHistory: [],
      halAskDraft: "",
      halAskLoading: false,
      halSideNotes: [],
      halSideNoteMonitor: { activeCount: 0, openCount: 0, pinnedCount: 0, highPriorityCount: 0 },
    });
    html = root.innerHTML;
  } else {
    html = await PageViews.previewPageHtml(halData, pageId, feed, snap);
  }

  const widgets = (html.match(/class="widget-card[^"]*"/g) || []).length;
  const kpiCards = (html.match(/class="[^"]*kpi-card[^"]*"/g) || []).length;
  const charts = (html.match(/class="[^"]*chart-container[^"]*"/g) || []).length;
  const legacy = [
    ["financial-page", /financial-page/],
    ["page-header stub", /class="page-header"/],
    ["pv-canvas", /pv-canvas/],
    ["pv-hal-", /pv-hal-/],
  ]
    .filter(([, re]) => re.test(html))
    .map(([n]) => n);

  const titles = [...html.matchAll(/class="widget-title"[^>]*>(?:<[^>]+>)*([^<]{4,80})/g)]
    .map((m) => m[1].replace(/&amp;/g, "&").trim())
    .slice(0, 6);

  const markers = [
    html.includes("widget-grid") && "widget-grid",
    html.includes("dashboard-grid") && "dashboard-grid",
    html.includes("composer-grid") && "composer-grid",
    html.includes("kanban-board") && "kanban-board",
    html.includes("sync-badge") && "sync-badge",
    html.includes("data-ms-page") && "data-ms-page",
  ].filter(Boolean);

  console.log("");
  console.log(" ▶ " + title.toUpperCase() + "  (" + pageId + ")");
  console.log("   HTML bytes:", html.length.toLocaleString());
  console.log(
    "   Layout:",
    pad(markers.join(", ") || "(none)", 40),
    "| widgets:",
    widgets,
    "| kpi-cards:",
    kpiCards,
    "| charts:",
    charts,
  );
  console.log("   Panels:", titles.length ? titles.join(" · ") : "(no widget-title found)");
  if (legacy.length) console.log("   ⚠ legacy markers:", legacy.join(", "));
  else console.log("   ✓ no legacy stub markers");
}

console.log("");
console.log(" " + line());
console.log(" Done — " + pages.length + " pages rendered");
console.log("");
