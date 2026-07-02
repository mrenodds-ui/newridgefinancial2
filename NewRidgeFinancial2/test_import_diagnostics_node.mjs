/**
 * Node parity tests for import-diagnostics checksum detection.
 */
import assert from "node:assert/strict";
import ImportDiagnostics from "./site/import-diagnostics.js";

const { evaluateDataset, STATUS } = ImportDiagnostics;

const contract = {
  system: "softdent",
  bundleKey: "dashboard",
  automated: true,
  severity: "critical",
  freshnessMaxMinutes: 1440,
  requiredFields: ["production"],
  fieldAliases: { production: ["production"] },
};

const rows = [
  { production: 100, period: "2026-06" },
  { production: 90, period: "2026-05" },
];
const freshModifiedAt = new Date().toISOString();

const changed = evaluateDataset(
  "softdent.dashboard",
  contract,
  {
    sourceFile: "softdent_dashboard_data.json",
    modifiedAt: freshModifiedAt,
    sha256: "bbbb",
    rows,
  },
  { datasets: { "softdent.dashboard": contract } },
  [],
  {
    "softdent.dashboard": {
      sourceFile: "softdent_dashboard_data.json",
      sha256: "aaaa",
    },
  },
);
assert.equal(changed.status, STATUS.PARTIAL);
assert.equal(changed.checksumChanged, true);
assert.match(changed.detail, /checksum/i);

const stable = evaluateDataset(
  "softdent.dashboard",
  contract,
  {
    sourceFile: "softdent_dashboard_data.json",
    modifiedAt: freshModifiedAt,
    sha256: "same-hash",
    rows,
  },
  { datasets: { "softdent.dashboard": contract } },
  [],
  {
    "softdent.dashboard": {
      sourceFile: "softdent_dashboard_data.json",
      sha256: "same-hash",
    },
  },
);
assert.equal(stable.status, STATUS.CONNECTED);
assert.equal(stable.checksumChanged, false);

const bridgeFallback = evaluateDataset(
  "softdent.dashboard",
  contract,
  {
    sourceFile: "softdent_dashboard_data.json",
    modifiedAt: freshModifiedAt,
    readSource: "bridge-fallback",
    bridgeValidation: { ok: true, rowCount: 1, issues: [] },
    rows: [{ production: 120000, period: "2026-06", collectionsReported: false }],
  },
  { datasets: { "softdent.dashboard": contract } },
  [],
  {},
);
assert.equal(bridgeFallback.status, STATUS.PARTIAL);
assert.match(bridgeFallback.detail, /bridge fallback/i);

console.log("test_import_diagnostics_node.mjs: ok");
