#!/usr/bin/env node
import { writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(__dirname, "..");
const outputPath = join(repoRoot, "data", "import_document_honesty_slice_validation.json");
const require = createRequire(import.meta.url);

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function buildImportedDoc(id) {
  return {
    id,
    type: "Statement",
    vendor: "QuickBooks Revenue",
    amount: "$1,000",
    status: "Ready to Post",
    autoImported: true,
    sourceSystem: "quickbooks",
    sourceKind: "monthlyRevenue",
    date: "2026-06-30",
  };
}

async function main() {
  const startedAt = Date.now();
  const payload = { ok: false, checks: [], errors: [], durationSec: 0 };
  const priorImportLoader = global.ImportLoader;
  const priorDesktopBridge = global.DesktopBridge;
  try {
    process.env.NR2_LOAD_IMPORTS = "1";
    delete global.DesktopBridge;
    const Services = require(join(repoRoot, "site", "services.js"));

    await Services.resetAll();
    global.ImportLoader = {
      shouldLoadImports: () => true,
      hasImportData: () => true,
      loadBundle: async () => ({
        loadedAt: new Date().toISOString(),
        syncStatus: { attempted: true, ok: false, status: "failed", error: "sync failed" },
        diagnostics: {
          datasets: [
            { datasetKey: "softdent.dashboard", status: "stale" },
            { datasetKey: "softdent.ar", status: "connected" },
            { datasetKey: "quickbooks.revenue", status: "connected" },
            { datasetKey: "quickbooks.expenses", status: "connected" },
          ],
        },
      }),
      buildDocumentStateFromImportBundle: () => ({
        queue: [buildImportedDoc("QB-REV-FAILED")],
        previewById: {},
      }),
    };
    const blocked = await Services.documents.list({});
    assert((blocked.queue || []).length === 0, "failed or stale imports must not hydrate documents");
    payload.checks.push({ name: "stale-or-failed-bundle-blocked", ok: true });

    await Services.resetAll();
    global.ImportLoader = {
      shouldLoadImports: () => true,
      hasImportData: () => true,
      loadBundle: async () => ({
        loadedAt: new Date().toISOString(),
        syncStatus: { attempted: true, ok: true, status: "success" },
        diagnostics: {
          datasets: [
            { datasetKey: "softdent.dashboard", status: "connected" },
            { datasetKey: "softdent.ar", status: "connected" },
            { datasetKey: "quickbooks.revenue", status: "connected" },
            { datasetKey: "quickbooks.expenses", status: "connected" },
          ],
        },
      }),
      buildDocumentStateFromImportBundle: () => ({
        queue: [buildImportedDoc("QB-REV-HEALTHY")],
        previewById: { "QB-REV-HEALTHY": { vendor: "QUICKBOOKS REVENUE" } },
      }),
    };
    const hydrated = await Services.documents.list({});
    assert((hydrated.queue || []).length === 1, "healthy import bundles should hydrate documents when persisted queue is empty");
    assert((hydrated.queue || [])[0].id === "QB-REV-HEALTHY", "hydrated queue must come from the import bundle");
    payload.checks.push({ name: "healthy-bundle-hydrates", ok: true });

    payload.ok = true;
  } catch (error) {
    payload.errors.push({ message: error && error.message ? error.message : String(error) });
  } finally {
    global.ImportLoader = priorImportLoader;
    if (priorDesktopBridge === undefined) delete global.DesktopBridge;
    else global.DesktopBridge = priorDesktopBridge;
    payload.durationSec = Math.round((Date.now() - startedAt) / 10) / 100;
    writeFileSync(outputPath, JSON.stringify(payload, null, 2), "utf8");
  }
  return payload.ok ? 0 : 1;
}

main().then((code) => {
  process.exitCode = code;
});
