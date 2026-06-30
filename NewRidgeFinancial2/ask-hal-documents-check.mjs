#!/usr/bin/env node
/**
 * Ask HAL (local route path) whether documents-page data is visible in widgets.
 * Usage: node ask-hal-documents-check.mjs
 */
import { readFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import { execSync } from "node:child_process";

const __dirname = dirname(fileURLToPath(import.meta.url));
const siteDir = join(__dirname, "site");
const require = createRequire(import.meta.url);

const pullCheck = execSync(
  'python -c "from practice_source_access import verify_claims_in_cache; import json; print(json.dumps(verify_claims_in_cache()))"',
  { cwd: __dirname, encoding: "utf8" },
);
const claimsReady = JSON.parse(pullCheck);
if (!claimsReady.ok) {
  execSync(
    "python -c \"import os; os.environ['NR2_HAL_FULL_PULL']='1'; from practice_source_access import pull_all_practice_sources; pull_all_practice_sources(full=True, scan_resources=False)\"",
    { cwd: __dirname, stdio: "pipe", encoding: "utf8" },
  );
} else {
  process.env.NR2_HAL_FULL_PULL = "1";
  execSync("python sync_document_sources.py", { cwd: __dirname, stdio: "pipe" });
}

process.env.NR2_LOAD_IMPORTS = "1";

const storeJson = execSync(
  `python -c "import json; from local_store import LocalStore; from document_sync import NR2_DATA_DIR, DOCUMENTS_KEY; raw=LocalStore(NR2_DATA_DIR).get(DOCUMENTS_KEY); print(raw or '{}')"`,
  { cwd: __dirname, encoding: "utf8" },
);
const documentsState = JSON.parse(storeJson);

require(join(siteDir, "empty-states.js"));
require(join(siteDir, "import-diagnostics.js"));
require(join(siteDir, "import-loader.js"));
require(join(siteDir, "widget-contract.js"));
require(join(siteDir, "runtime-issues.js"));
require(join(siteDir, "snapshot-store.js"));
require(join(siteDir, "hal-narrative-library.js"));
require(join(siteDir, "hal-skills.js"));
require(join(siteDir, "hal-core.js"));
require(join(siteDir, "hal-route-exec.js"));
require(join(siteDir, "hal-widget-master-chart.js"));
require(join(siteDir, "desktop-bridge.js"));
require(join(siteDir, "services.js"));
const HalCore = require(join(siteDir, "hal-core.js"));
const HalSkills = require(join(siteDir, "hal-skills.js"));
const HalRouteExec = require(join(siteDir, "hal-route-exec.js"));
const Services = require(join(siteDir, "services.js"));
const ImportLoader = require(join(siteDir, "import-loader.js"));
const SnapshotStore = require(join(siteDir, "snapshot-store.js"));

globalThis.HalCore = HalCore;
globalThis.HalSkills = HalSkills;
globalThis.Services = Services;
globalThis.ImportLoader = ImportLoader;
globalThis.SnapshotStore = SnapshotStore;

const halData = JSON.parse(readFileSync(join(siteDir, "data", "hal-manager.json"), "utf8"));
const halModels = JSON.parse(readFileSync(join(siteDir, "data", "hal-models.json"), "utf8"));
const pages = [
  { id: "financial", name: "Financial" },
  { id: "softdent", name: "SoftDent" },
  { id: "quickbooks", name: "QuickBooks" },
  { id: "ar", name: "A/R" },
  { id: "claims", name: "Claims" },
  { id: "narratives", name: "Narratives" },
  { id: "documents", name: "Documents" },
  { id: "library", name: "Library" },
  { id: "hal", name: "HAL" },
];

globalThis.DesktopBridge = {
  hasDesktopApi: () => true,
  storageGet: async (key) => {
    if (key === "nr2:v2:documents") return documentsState;
    return null;
  },
  storageSet: async () => documentsState,
  syncAccountingDocuments: async () => ({
    queueCount: (documentsState.queue || []).length,
    sourceImport: { counts: { quickbooks: 0, softdent: 0 } },
    state: documentsState,
  }),
  refreshImports: async () => ImportLoader.loadBundle(false),
  pullPracticeSources: async () => {
    const { execSync: exec } = await import("node:child_process");
    return JSON.parse(
      exec(`python -c "from practice_source_access import pull_all_practice_sources; import json; print(json.dumps(pull_all_practice_sources()))"`, {
        cwd: __dirname.replace(/\\site$/, "").replace(/\/site$/, "") || __dirname,
        encoding: "utf8",
      }),
    );
  },
  getImportSyncStatus: async () => ({ status: "idle" }),
};

SnapshotStore.invalidate("ask-hal-documents");
const snapshot = await SnapshotStore.get(() => Services.buildProgramSnapshotCore());
const feed = HalSkills.buildWidgetFeed(snapshot);

const ctx = {
  halData,
  halModels,
  pages,
  halOfficeTasks: [],
  halWorkSession: null,
  halEvidencePacket: null,
  halReadinessDiagnostics: null,
  halSideNotes: [],
  halWidgetFeed: feed,
  loadProgramSnapshot: async () => Object.assign({}, snapshot, { widgets: feed }),
  refreshHalWidgetFeed: async (snap) => {
    const next = snap || (await ctx.loadProgramSnapshot());
    ctx.halWidgetFeed = next.widgets || HalSkills.buildWidgetFeed(next);
    return ctx.halWidgetFeed;
  },
  workSessionStatusText: () => "No session",
  runReadinessDiagnostics: () => HalCore.runReadinessChecks(halData, halModels, pages),
  staffUseGateText: () => "gate",
  staffHandoffSummaryText: () => "handoff",
  runOperatorSmokeTest: () => HalCore.runOperatorSmokeTest(halData, halModels, pages),
  refreshSideNoteMonitor: () => null,
  addSideNote: (t) => ({ text: t }),
  addOfficeTask: () => null,
  startWorkSession: () => null,
  resetWorkSession: () => null,
  draftSessionHandoff: () => null,
  buildEvidencePacketFromSession: () => null,
  clearEvidencePacket: () => null,
  clearReadinessDiagnostics: () => null,
  normalizeActions: (a) => a || [],
  clearProgramContextCache: () => null,
  setHalWidgetFeed: (f) => {
    ctx.halWidgetFeed = f;
  },
  Services,
  ImportLoader,
  halData,
  getOfficeTasks: async () => [],
};

async function ask(question) {
  const route = HalCore.routeHalCommand(halData, halModels, pages, question);
  const exec = await HalRouteExec.execute(route, question, {}, ctx);
  return {
    question,
    intent: route.intent,
    lane: exec?.lane || route.lane,
    text: exec?.text || route.text || "(no local response — would use model lane)",
  };
}

const questions = [
  "Pull all SoftDent and QuickBooks data",
  "Show manager dashboard widgets",
  "What do you need to do your job",
  "Draft narrative for claim CLM-2026-1001",
  "Work document workbook",
];

const docWidgets = ["documentIntakeQueue", "documentPreview", "accountsPayableAutomation", "periodCloseAndPosting"];
const widgetReport = docWidgets.map((key) => {
  const w = feed.widgets[key];
  return {
    key,
    status: w?.status,
    metrics: w?.metrics,
  };
});

const answers = [];
for (const q of questions) {
  answers.push(await ask(q));
}

const summary = {
  documentsQueueCount: snapshot.documents?.queueCount || 0,
  sourceCounts: snapshot.documents?.sourceCounts || {},
  documentWidgets: widgetReport,
  accountingExcelValidation: feed.accountingExcelValidation?.status,
  halAnswers: answers,
};

console.log(JSON.stringify(summary, null, 2));
