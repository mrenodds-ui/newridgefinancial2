#!/usr/bin/env node
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..", "..");
const mockDir = join(root, ".local_logs/moonshot_financial_eval/page_mockups");
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
  "tax-engine.js",
  "nr2-moonshot-mockup-chrome.js",
  "page-canvas-data.js",
  "moonshot-layout-engine.js",
  "page-canvas.js",
  "components.js",
]) {
  if (f === "hal-skills.js" && !globalThis.HAL) globalThis.HAL = { skills: { defineSource() {} } };
  require(join(site, f));
}

const Services = require(join(site, "services.js"));
const PageViews = require(join(site, "page-views.js"));
const SnapshotStore = require(join(site, "snapshot-store.js"));
global.SnapshotStore = SnapshotStore;
SnapshotStore.invalidate("mockup-cmp");
const halData = JSON.parse(readFileSync(join(site, "data/hal-manager.json"), "utf8"));
const snap = await SnapshotStore.get(() => Services.buildProgramSnapshotCore());
const feed = require(join(site, "hal-skills.js")).buildWidgetFeed(snap);
require(join(site, "hal-page.js"));
require(join(site, "hal-page-canvas.js"));
const HalPage = require(join(site, "hal-page.js"));

const SIG = [
  "widget-grid",
  "widget-card",
  "dashboard-grid",
  "kpi-card",
  "composer-grid",
  "kanban-board",
  "chart-container",
  "stat-grid",
  "kpi-grid",
  "heatmap-grid",
  "search-box",
  "document-grid",
  "funnel-chart",
  "operatory-grid",
  "hal-situational-hero",
  "hal-widget-mosaic",
  "kpi-large",
  "sync-badge",
];

function titles(html, cls) {
  const re = new RegExp(`class="${cls}"[^>]*>(?:<[^>]+>)*([^<]{3,80})`, "g");
  return [...html.matchAll(re)].map((m) => m[1].replace(/&amp;/g, "&").trim());
}

function firstBlock(html, pattern) {
  const m = html.match(pattern);
  return m ? m[0].replace(/\s+/g, " ").trim().slice(0, 400) : "";
}

function extractMockupBody(html) {
  const markers = ["<div class=\"widget-grid\"", "<div class=\"dashboard-grid\"", "<div class=\"composer-grid\"", "<div class=\"content-wrapper\""];
  let start = -1;
  for (const m of markers) {
    const i = html.indexOf(m);
    if (i >= 0 && (start < 0 || i < start)) start = i;
  }
  return start >= 0 ? html.slice(start, start + 12000) : html;
}

function extractLiveBody(html) {
  const i = html.indexOf("widget-grid");
  const j = html.indexOf("dashboard-grid");
  const k = html.indexOf("composer-grid");
  const starts = [i, j, k].filter((n) => n >= 0);
  const start = starts.length ? Math.min(...starts) : 0;
  return html.slice(start, start + 12000);
}

const pages = [...PageSchema.STAFF_PAGE_IDS, "hal"];
const report = [];

for (const id of pages) {
  const mockFull = readFileSync(join(mockDir, `${id}.html`), "utf8");
  let liveFull = "";
  if (id === "hal") {
    const store = { v: "" };
    const mockRoot = {
      get innerHTML() {
        return store.v;
      },
      set innerHTML(x) {
        store.v = String(x || "");
      },
      querySelector() {
        return null;
      },
      querySelectorAll() {
        return [];
      },
    };
    HalPage.render({
      root: mockRoot,
      halData,
      halModels: {},
      halWidgetFeed: feed,
      halProgramSnapshot: snap,
      halChatHistory: [],
      halAskDraft: "",
      halAskLoading: false,
      halSideNotes: [],
      halSideNoteMonitor: { activeCount: 0, openCount: 0, pinnedCount: 0, highPriorityCount: 0 },
    });
    liveFull = store.v;
  } else {
    liveFull = await PageViews.previewPageHtml(halData, id, feed, snap);
  }

  const mockBody = extractMockupBody(mockFull);
  const liveBody = extractLiveBody(liveFull);

  const mockSig = SIG.filter((s) => mockFull.includes(s));
  const liveSig = SIG.filter((s) => liveFull.includes(s));
  const missing = mockSig.filter((s) => !liveSig.includes(s));
  const extra = liveSig.filter((s) => !mockSig.includes(s));

  const mockWidgetTitles = titles(mockFull, "widget-title");
  const liveWidgetTitles = titles(liveFull, "widget-title");
  const mockCardTitles = titles(mockFull, "card-title");
  const liveCardTitles = titles(liveFull, "card-title");

  const mockSnippet = firstBlock(
    mockBody,
    /<div class="widget-card[^"]*"[^>]*>[\s\S]{0,500}/,
  ) || firstBlock(mockBody, /<div class="card kpi-card"[\s\S]{0,500}/);

  const fix =
    missing.length > 0
      ? `Add mockup classes/structure: ${missing.join(", ")}`
      : mockCardTitles.length && !liveCardTitles.length && id === "quickbooks"
        ? "QuickBooks uses card-title in mockup; live uses card-title but not widget-card — align dashboard-grid spans"
        : extra.includes("nr2-alert-ticker") && !mockSig.includes("nr2-alert-ticker")
          ? "Live adds NR2-only panels (alert ticker, reconciliation) — decide keep vs mockup trim"
          : "Structure largely aligned — verify spacing/col-spans visually";

  report.push({
    id,
    title: PageSchema.byId(id)?.title || id,
    mockSig,
    liveSig,
    missing,
    extra,
    mockPanels: [...mockWidgetTitles, ...mockCardTitles].slice(0, 10),
    livePanels: [...liveWidgetTitles, ...liveCardTitles].slice(0, 10),
    mockSnippet,
    fix,
    mockupPath: `.local_logs/moonshot_financial_eval/page_mockups/${id}.html`,
    renderer:
      id === "hal" ? "site/hal-page-canvas.js" : `site/page-canvas.js → render${id === "office-manager" ? "OfficeManager" : id.charAt(0).toUpperCase() + id.slice(1)}()`,
  });
}

const outDir = join(__dirname, "..", ".tmp");
mkdirSync(outDir, { recursive: true });
const outPath = join(outDir, "mockup-live-report.json");
writeFileSync(outPath, JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
