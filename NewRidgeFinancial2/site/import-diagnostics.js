/**
 * Dataset-level import diagnostics for NR2 financial automation.
 * Browser + Node compatible.
 */
const ImportDiagnostics = (function () {
  const STATUS = {
    CONNECTED: "connected",
    PARTIAL: "partial",
    STALE: "stale",
    NOT_CONFIGURED: "not_configured",
    MISSING: "missing",
  };

  const FALLBACK_DATASET_KEYS = [
    "softdent.dashboard",
    "softdent.claims",
    "softdent.clinicalNotes",
    "softdent.ar",
    "softdent.newPatients",
    "softdent.treatmentPlans",
    "softdent.caseAcceptance",
    "softdent.hygieneRecall",
    "quickbooks.revenue",
    "quickbooks.profitAndLoss",
    "quickbooks.expenses",
    "quickbooks.expenseCategories",
    "quickbooks.ar",
  ];

  function isNode() {
    return typeof window === "undefined";
  }

  function loadManifest() {
    if (!isNode()) return null;
    try {
      const fs = require("node:fs");
      const pathMod = require("node:path");
      const manifestPath = pathMod.join(__dirname, "..", "import-manifest.json");
      const payload = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
      return payload.version === 1 ? payload : null;
    } catch {
      return null;
    }
  }

  function parseIso(value) {
    if (!value) return null;
    const then = Date.parse(value);
    return Number.isFinite(then) ? then : null;
  }

  function ageMinutes(modifiedAt) {
    const then = parseIso(modifiedAt);
    if (then === null) return null;
    return Math.max(0, Math.round((Date.now() - then) / 60000));
  }

  function pickField(row, names) {
    if (!row || typeof row !== "object") return null;
    for (const name of names) {
      if (row[name] !== undefined && row[name] !== "") return row[name];
      const match = Object.keys(row).find((key) => key.toLowerCase() === String(name).toLowerCase());
      if (match && row[match] !== undefined && row[match] !== "") return row[match];
    }
    return null;
  }

  function aliasesForField(contract, fieldName) {
    const aliases = (contract && contract.fieldAliases) || {};
    const configured = aliases[fieldName];
    if (Array.isArray(configured) && configured.length) return configured;
    return [fieldName];
  }

  function validateRowsForContract(contract, rows) {
    const required = (contract && contract.requiredFields) || [];
    if (!required.length) return { ok: true, requiredFieldFailures: [] };
    if (!rows || !rows.length) return { ok: false, requiredFieldFailures: required.slice() };
    const failures = required.filter((fieldName) => {
      const aliases = aliasesForField(contract, fieldName);
      return !rows.some((row) => pickField(row, aliases) !== null && pickField(row, aliases) !== "");
    });
    return { ok: failures.length === 0, requiredFieldFailures: failures };
  }

  function collectorHint(manifest, contract) {
    const system = contract && contract.system;
    const upstream = manifest && manifest.upstreamRoots && manifest.upstreamRoots[system];
    const hints = (upstream && upstream.collectorHints) || {};
    const generatedBy = (contract && contract.generatedBy) || [];
    for (const key of generatedBy) {
      if (hints[key]) return hints[key];
    }
    if (contract && contract.sourceOwner && hints[contract.sourceOwner]) return hints[contract.sourceOwner];
    if (contract && contract.note) return contract.note;
    if (contract && Array.isArray(contract.filenames) && contract.filenames.length) {
      return `Expected export file: ${contract.filenames[0]}`;
    }
    return null;
  }

  function resolveUpstreamRoots(system, manifest) {
    if (!isNode() || !manifest || !manifest.upstreamRoots || !manifest.upstreamRoots[system]) return [];
    const fs = require("node:fs");
    const pathMod = require("node:path");
    const upstream = manifest.upstreamRoots[system];
    const roots = [];
    const addRoot = (candidate) => {
      try {
        if (fs.existsSync(candidate) && fs.statSync(candidate).isDirectory() && !roots.includes(candidate)) {
          roots.push(candidate);
        }
      } catch {
        /* ignore */
      }
    };
    (upstream.envVars || []).forEach((envName) => {
      const configured = process.env[envName];
      if (configured && String(configured).trim()) {
        let candidate = pathMod.resolve(String(configured).trim());
        addRoot(candidate);
      }
    });
    (upstream.defaultPaths || []).forEach((raw) => addRoot(String(raw)));
    return roots;
  }

  function findNewestUpstream(roots, filenames) {
    if (!isNode() || !roots.length || !filenames.length) return null;
    const fs = require("node:fs");
    const pathMod = require("node:path");
    const nameSet = new Set(filenames.map((name) => String(name).toLowerCase()));
    let best = null;
    let bestMtime = -1;
    const walk = (dir) => {
      let entries = [];
      try {
        entries = fs.readdirSync(dir, { withFileTypes: true });
      } catch {
        return;
      }
      for (const entry of entries) {
        const full = pathMod.join(dir, entry.name);
        if (entry.isDirectory()) walk(full);
        else if (entry.isFile() && nameSet.has(entry.name.toLowerCase()) && fs.statSync(full).mtimeMs > bestMtime) {
          best = full;
          bestMtime = fs.statSync(full).mtimeMs;
        }
      }
    };
    roots.forEach((root) => walk(root));
    if (!best) return null;
    const modifiedAt = new Date(bestMtime).toISOString();
    return { path: best, sourceFile: require("node:path").basename(best), modifiedAt, ageMinutes: ageMinutes(modifiedAt) };
  }

  function evaluateDataset(datasetKey, contract, datasetPayload, manifest, upstreamRoots, previousChecksums) {
    const automated = contract && contract.automated !== false;
    const severity = (contract && contract.severity) || "warning";
    const freshnessMax = Number((contract && contract.freshnessMaxMinutes) || 1440);
    const hint = collectorHint(manifest, contract);
    const note = contract && contract.note;

    if (!automated) {
      return {
        datasetKey,
        system: contract && contract.system,
        bundleKey: contract && contract.bundleKey,
        status: STATUS.NOT_CONFIGURED,
        severity,
        automated: false,
        found: false,
        rowCount: 0,
        sourceFile: null,
        modifiedAt: null,
        ageMinutes: null,
        freshnessMaxMinutes: freshnessMax,
        requiredFieldFailures: [],
        collectorHint: hint,
        upstreamFile: null,
        detail: note || "No automated collector configured for this dataset.",
      };
    }

    if (!datasetPayload || !datasetPayload.sourceFile) {
      const upstreamFile =
        upstreamRoots && contract && contract.filenames ? findNewestUpstream(upstreamRoots, contract.filenames) : null;
      let detail = "Dataset file not found in import cache.";
      if (upstreamFile) detail = "Import cache missing file; upstream export exists but was not copied.";
      else if (hint) detail = `Dataset file not found. Check collector: ${hint}.`;
      return {
        datasetKey,
        system: contract && contract.system,
        bundleKey: contract && contract.bundleKey,
        status: STATUS.MISSING,
        severity,
        automated: true,
        found: false,
        rowCount: 0,
        sourceFile: null,
        modifiedAt: null,
        ageMinutes: null,
        freshnessMaxMinutes: freshnessMax,
        requiredFieldFailures: [],
        collectorHint: hint,
        upstreamFile,
        detail,
      };
    }

    const rows = datasetPayload.rows || [];
    const rowCount = Array.isArray(rows) ? rows.length : 0;
    const modifiedAt = datasetPayload.modifiedAt || null;
    const datasetAge = ageMinutes(modifiedAt);
    const validation = validateRowsForContract(contract, rows);
    const requiredFieldFailures = validation.requiredFieldFailures || [];
    const upstreamFile =
      upstreamRoots && contract && contract.filenames ? findNewestUpstream(upstreamRoots, contract.filenames) : null;

    let status = STATUS.CONNECTED;
    let detail = "Dataset loaded and required fields pass.";
    if (datasetAge !== null && datasetAge > freshnessMax) {
      status = STATUS.STALE;
      detail = `Dataset is stale (${datasetAge} min old; max ${freshnessMax} min).`;
    } else if (requiredFieldFailures.length) {
      status = STATUS.PARTIAL;
      detail = `Dataset loaded but required fields missing: ${requiredFieldFailures.join(", ")}.`;
    } else if (!rowCount) {
      status = STATUS.PARTIAL;
      detail = "Dataset file present but contains no rows.";
    }
    if (upstreamFile && upstreamFile.ageMinutes !== null && upstreamFile.ageMinutes > freshnessMax && status === STATUS.CONNECTED) {
      const localFresh = datasetAge !== null && datasetAge <= freshnessMax;
      if (localFresh) {
        detail = `Local cache is fresh; upstream source is ${upstreamFile.ageMinutes} min old. ${detail}`;
      } else {
        status = STATUS.STALE;
        detail = `Upstream export is stale (${upstreamFile.ageMinutes} min old). ${detail}`;
      }
    }

    const currentSha = datasetPayload && datasetPayload.sha256 ? String(datasetPayload.sha256) : "";
    const previous = previousChecksums && previousChecksums[datasetKey];
    let checksumChanged = false;
    if (previous && currentSha) {
      const previousSha = previous.sha256 ? String(previous.sha256) : "";
      const previousFile = previous.sourceFile ? String(previous.sourceFile) : "";
      const currentFile = datasetPayload.sourceFile ? String(datasetPayload.sourceFile) : "";
      if (previousSha && previousSha !== currentSha) checksumChanged = true;
      else if (previousFile && currentFile && previousFile !== currentFile) checksumChanged = true;
    }
    if (checksumChanged && status === STATUS.CONNECTED) {
      status = STATUS.PARTIAL;
      detail = `Dataset changed since last sync (checksum). ${detail}`;
    }

    const readSource = String((datasetPayload && datasetPayload.readSource) || "").toLowerCase();
    if (datasetKey === "softdent.dashboard" && readSource === "bridge-fallback") {
      if (status === STATUS.CONNECTED) status = STATUS.PARTIAL;
      const bridgeValidation =
        datasetPayload && typeof datasetPayload.bridgeValidation === "object" ? datasetPayload.bridgeValidation : {};
      const bridgeIssues = Array.isArray(bridgeValidation.issues) ? bridgeValidation.issues : [];
      let bridgeNote = "Dashboard loaded from bridge fallback (not daysheet export).";
      if (bridgeIssues.length) bridgeNote = `${bridgeNote} ${bridgeIssues.join("; ")}.`;
      detail = `${bridgeNote} ${detail}`.trim();
    } else if (datasetKey === "softdent.dashboard" && rowCount === 1 && status === STATUS.CONNECTED) {
      status = STATUS.PARTIAL;
      detail = "Current month only; prior month export missing for trend/YTD widgets.";
    }

    return {
      datasetKey,
      system: contract && contract.system,
      bundleKey: contract && contract.bundleKey,
      status,
      severity,
      automated: true,
      found: true,
      rowCount,
      sourceFile: datasetPayload.sourceFile,
      modifiedAt,
      ageMinutes: datasetAge,
      freshnessMaxMinutes: freshnessMax,
      requiredFieldFailures,
      collectorHint: hint,
      upstreamFile,
      sha256: currentSha || null,
      checksumChanged,
      detail,
    };
  }

  function evaluateBundle(bundle, manifest, previousChecksums) {
    const resolvedManifest = manifest || loadManifest() || { datasets: {}, upstreamRoots: {} };
    const datasetsManifest = resolvedManifest.datasets || {};
    const checksums = previousChecksums || resolvedManifest.datasetChecksums || {};
    const items = [];
    const summary = { total: 0, connected: 0, partial: 0, stale: 0, missing: 0, notConfigured: 0 };
    const softdentRoots = resolveUpstreamRoots("softdent", resolvedManifest);
    const quickbooksRoots = resolveUpstreamRoots("quickbooks", resolvedManifest);

    FALLBACK_DATASET_KEYS.forEach((datasetKey) => {
      const contract = datasetsManifest[datasetKey] || {};
      const system = contract.system || datasetKey.split(".")[0];
      const bundleKey = contract.bundleKey || datasetKey.split(".")[1];
      const systemPayload = (bundle && bundle[system]) || {};
      const datasetPayload = systemPayload[bundleKey] || null;
      const roots = system === "softdent" ? softdentRoots : quickbooksRoots;
      const item = evaluateDataset(datasetKey, contract, datasetPayload, resolvedManifest, roots, checksums);
      items.push(item);
      summary.total += 1;
      if (item.status === STATUS.CONNECTED) summary.connected += 1;
      else if (item.status === STATUS.PARTIAL) summary.partial += 1;
      else if (item.status === STATUS.STALE) summary.stale += 1;
      else if (item.status === STATUS.MISSING) summary.missing += 1;
      else if (item.status === STATUS.NOT_CONFIGURED) summary.notConfigured += 1;
    });

    return {
      evaluatedAt: new Date().toISOString(),
      datasets: items,
      summary,
    };
  }

  function checkUpstreamHealth(manifest) {
    const resolvedManifest = manifest || loadManifest() || { datasets: {}, upstreamRoots: {} };
    const datasetsManifest = resolvedManifest.datasets || {};
    const systems = {};
    ["softdent", "quickbooks"].forEach((system) => {
      const roots = resolveUpstreamRoots(system, resolvedManifest);
      const datasetReports = [];
      Object.keys(datasetsManifest).forEach((datasetKey) => {
        const contract = datasetsManifest[datasetKey];
        if (!contract || contract.system !== system || contract.automated === false) return;
        const newest = findNewestUpstream(roots, contract.filenames || []);
        const freshnessMax = Number(contract.freshnessMaxMinutes || 1440);
        const stale = Boolean(newest && newest.ageMinutes !== null && newest.ageMinutes > freshnessMax);
        datasetReports.push({
          datasetKey,
          newestFile: newest,
          stale,
          collectorHint: collectorHint(resolvedManifest, contract),
        });
      });
      systems[system] = {
        roots: roots.map((path) => ({ path, exists: true })),
        configuredRootCount: roots.length,
        datasets: datasetReports,
      };
    });
    return { checkedAt: new Date().toISOString(), systems };
  }

  function statusLabel(status) {
    const labels = {
      connected: "Connected",
      partial: "Partial",
      stale: "Stale",
      not_configured: "Not Configured",
      missing: "Missing",
    };
    return labels[status] || status;
  }

  function formatDatasetLines(diagnostics) {
    if (!diagnostics || !Array.isArray(diagnostics.datasets)) return [];
    return diagnostics.datasets.map((item) => {
      const label = statusLabel(item.status);
      const file = item.sourceFile ? ` file=${item.sourceFile}` : "";
      const rows = item.found ? ` rows=${item.rowCount}` : "";
      const hint = item.collectorHint ? ` collector=${item.collectorHint}` : "";
      const checksum = item.checksumChanged ? " checksum-changed" : "";
      return `- ${item.datasetKey}: ${label}${file}${rows}${checksum}. ${item.detail || ""}${hint}`;
    });
  }

  function systemSummary(diagnostics, system) {
    const items = (diagnostics && diagnostics.datasets || []).filter((item) => item.system === system);
    if (!items.length) return { status: STATUS.MISSING, detail: "No datasets configured." };
    const priority = [STATUS.MISSING, STATUS.STALE, STATUS.PARTIAL, STATUS.NOT_CONFIGURED, STATUS.CONNECTED];
    let worst = STATUS.CONNECTED;
    for (const state of priority) {
      if (items.some((item) => item.status === state)) {
        worst = state;
        break;
      }
    }
    const connected = items.filter((item) => item.status === STATUS.CONNECTED).length;
    const detail = `${connected}/${items.length} datasets connected.`;
    return { status: worst, detail, items };
  }

  return {
    STATUS,
    loadManifest,
    pickField,
    validateRowsForContract,
    evaluateDataset,
    evaluateBundle,
    checkUpstreamHealth,
    statusLabel,
    formatDatasetLines,
    systemSummary,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = ImportDiagnostics;
}
if (typeof window !== "undefined") {
  window.ImportDiagnostics = ImportDiagnostics;
}
