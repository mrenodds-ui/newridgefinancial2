/**
 * SoftDent / QuickBooks import loader for NewRidgeFinancial 2.0.
 * Reads canonical export files and maps them into dashboard shapes HAL already uses.
 * Browser + Node compatible.
 */
const ImportLoader = (function () {
  const PRIMARY_PROVIDER = "Dr. Michael Reno";
  const isNode = typeof window === "undefined";
  const REPO_IMPORT_SOFTDENT = isNode
    ? require("node:path").join(__dirname, "..", "..", "app_data", "nr2", "document_inbox", "softdent")
    : null;
  const REPO_IMPORT_QUICKBOOKS = isNode
    ? require("node:path").join(__dirname, "..", "..", "app_data", "nr2", "document_inbox", "quickbooks")
    : null;

  const SOFTDENT_DASHBOARD_NAMES = [
    "softdent_dashboard_data.json",
    "softdent_dashboard_export.json",
    "softdent_dashboard_data.csv",
    "softdent_dashboard_export.csv",
  ];
  const SOFTDENT_CLAIMS_NAMES = [
    "softdent_claims_export.csv",
    "softdent_claims_data.csv",
    "softdent_claims_export.json",
    "softdent_claims_data.json",
  ];
  const SOFTDENT_CLINICAL_NAMES = ["softdent_clinical_notes_data.json", "softdent_clinical_notes_export.json"];
  const SOFTDENT_AR_NAMES = [
    "softdent_ar_aging.csv",
    "softdent_accounts_receivable.csv",
    "softdent_ar_aging.json",
    "patient_aging.csv",
    "ar_aging.csv",
  ];
  const QB_REVENUE_NAMES = [
    "quickbooks_revenue.csv",
    "quickbooks_revenue.json",
  ];
  const QB_PL_NAMES = [
    "quickbooks_profit_and_loss.csv",
    "quickbooks_profit_loss.csv",
  ];
  const QB_EXPENSE_NAMES = ["quickbooks_expenses.csv", "quickbooks_expense_detail.csv", "quickbooks_expenses.json"];
  const QB_EXPENSE_CATEGORY_NAMES = ["quickbooks_expense_categories.csv"];
  const QB_AR_NAMES = ["quickbooks_ar.csv", "quickbooks_accounts_receivable.csv", "quickbooks_aging.csv"];
  const SOFTDENT_NEW_PATIENTS_NAMES = ["softdent_new_patients.csv", "softdent_new_patients.json", "new_patients.csv"];
  const SOFTDENT_TREATMENT_PLANS_NAMES = [
    "treatment_plan_summary.csv",
    "softdent_treatment_plan_summary.csv",
    "treatment_plan_summary.json",
  ];
  const SOFTDENT_CASE_ACCEPTANCE_NAMES = ["case_acceptance.csv", "softdent_case_acceptance.csv", "case_acceptance.json"];
  const SOFTDENT_HYGIENE_RECALL_NAMES = [
    "hygiene_recall_summary.csv",
    "softdent_hygiene_recall.csv",
    "hygiene_recall_summary.json",
  ];

  function loadManifestDatasets() {
    if (!isNode) return null;
    try {
      const fs = require("node:fs");
      const pathMod = require("node:path");
      const manifestPath = pathMod.join(__dirname, "..", "import-manifest.json");
      const payload = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
      if (payload.version !== 1) return null;
      return payload.datasets || null;
    } catch {
      return null;
    }
  }

  function manifestFilenames(key, fallback) {
    const datasets = loadManifestDatasets();
    const entry = datasets && datasets[key];
    if (entry && Array.isArray(entry.filenames) && entry.filenames.length) return entry.filenames;
    return fallback;
  }

  const MANIFEST_SOFTDENT_DASHBOARD_NAMES = manifestFilenames("softdent.dashboard", SOFTDENT_DASHBOARD_NAMES);
  const MANIFEST_SOFTDENT_CLAIMS_NAMES = manifestFilenames("softdent.claims", SOFTDENT_CLAIMS_NAMES);
  const MANIFEST_SOFTDENT_CLINICAL_NAMES = manifestFilenames("softdent.clinicalNotes", SOFTDENT_CLINICAL_NAMES);
  const MANIFEST_SOFTDENT_AR_NAMES = manifestFilenames("softdent.ar", SOFTDENT_AR_NAMES);
  const MANIFEST_QB_REVENUE_NAMES = manifestFilenames("quickbooks.revenue", QB_REVENUE_NAMES);
  const MANIFEST_QB_PL_NAMES = manifestFilenames("quickbooks.profitAndLoss", QB_PL_NAMES);
  const MANIFEST_QB_EXPENSE_NAMES = manifestFilenames("quickbooks.expenses", QB_EXPENSE_NAMES);
  const MANIFEST_QB_EXPENSE_CATEGORY_NAMES = manifestFilenames("quickbooks.expenseCategories", QB_EXPENSE_CATEGORY_NAMES);
  const MANIFEST_QB_AR_NAMES = manifestFilenames("quickbooks.ar", QB_AR_NAMES);
  const MANIFEST_SOFTDENT_NEW_PATIENTS_NAMES = manifestFilenames("softdent.newPatients", SOFTDENT_NEW_PATIENTS_NAMES);
  const MANIFEST_SOFTDENT_TREATMENT_PLANS_NAMES = manifestFilenames("softdent.treatmentPlans", SOFTDENT_TREATMENT_PLANS_NAMES);
  const MANIFEST_SOFTDENT_CASE_ACCEPTANCE_NAMES = manifestFilenames("softdent.caseAcceptance", SOFTDENT_CASE_ACCEPTANCE_NAMES);
  const MANIFEST_SOFTDENT_HYGIENE_RECALL_NAMES = manifestFilenames("softdent.hygieneRecall", SOFTDENT_HYGIENE_RECALL_NAMES);

  function bridge() {
    if (typeof DesktopBridge !== "undefined") return DesktopBridge;
    if (typeof window !== "undefined" && window.DesktopBridge) return window.DesktopBridge;
    return null;
  }

  function shouldLoadImports() {
    const br = bridge();
    if (br && br.hasRuntimeAccess && br.hasRuntimeAccess()) return true;
    if (br && br.hasDesktopApi && br.hasDesktopApi()) return true;
    if (br && br.hasLoopbackApi && br.hasLoopbackApi()) return true;
    if (isNode && process.env.NR2_LOAD_IMPORTS === "1") return true;
    return false;
  }

  function coerceFloat(value) {
    if (value === null || value === undefined || value === "") return null;
    if (typeof value === "number" && Number.isFinite(value)) return value;
    const normalized = String(value).replace(/[$,]/g, "").trim();
    if (!normalized) return null;
    const parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function formatMoney(value) {
    const amount = coerceFloat(value);
    if (amount === null) return "—";
    return amount.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });
  }

  function formatCount(value) {
    const amount = coerceFloat(value);
    if (amount === null) return "—";
    return Math.round(amount).toLocaleString("en-US");
  }

  function formatFreshness(iso) {
    if (!iso) return "Unknown";
    const then = Date.parse(iso);
    if (!Number.isFinite(then)) return "Unknown";
    const mins = Math.max(0, Math.round((Date.now() - then) / 60000));
    if (mins < 1) return "Just now";
    if (mins < 60) return `${mins} min ago`;
    const hours = Math.round(mins / 60);
    if (hours < 48) return `${hours} hr ago`;
    return new Date(then).toLocaleString();
  }

  function deepClone(value) {
    return value == null ? value : JSON.parse(JSON.stringify(value));
  }

  function resolveEmptyStates() {
    if (typeof EmptyStates !== "undefined") return EmptyStates;
    if (typeof window !== "undefined" && window.EmptyStates) return window.EmptyStates;
    try {
      return require("./empty-states.js");
    } catch {
      return { dashboard: () => null, store: () => ({}) };
    }
  }

  function emptyDashboard(pageId) {
    const empty = resolveEmptyStates();
    return empty.dashboard(pageId) || { dataSource: "empty" };
  }

  function assignPatch(base, patch) {
    const merged = Object.assign(deepClone(base || {}), patch || {});
    if (merged.dataSource === "import" && !merged.importDepth) {
      const pageId = merged.pageId || (patch && patch.pageId) || "";
      merged.importDepth = dashboardImportDepth(pageId, merged);
    }
    return merged;
  }

  function dashboardImportDepth(pageId, patch) {
    if (pageId === "financial") {
      if (patch.collectionsMissing || patch.collectionsZeroWithProduction) return "degraded";
      if (patch.collectionsPending) return "partial";
      if (patch.periodAlignment && patch.periodAlignment.aligned === false && patch.bothSources) return "degraded";
      if (patch.singleSource) return "partial";
      const hasTrend = Array.isArray(patch.productionTrend?.production) && patch.productionTrend.production.length > 1;
      const hasPayer = Array.isArray(patch.payerMix?.slices) && patch.payerMix.slices.length > 0;
      const hasQuality = patch.quality && patch.quality.score > 0;
      if (!hasTrend || !hasPayer || !hasQuality) return "partial";
      return "complete";
    }
    if (pageId === "quickbooks") {
      if (patch.plReconcile && patch.plReconcile.matches === false) return "degraded";
      const hasCategories = Array.isArray(patch.expenseCategories?.slices) && patch.expenseCategories.slices.length > 0;
      const hasMonthly = Array.isArray(patch.monthlyExpenses) && patch.monthlyExpenses.length > 0;
      if (!hasCategories && !hasMonthly) return "partial";
      return "complete";
    }
    if (pageId === "softdent") {
      if (patch.collectionsMissing) return "degraded";
      const hasCollections = Number(patch.collections || 0) > 0 || patch.collectionsReported === false;
      const claimsOk = (patch.health || []).some((h) => /claims/i.test(String(h.label || "")) && h.ok);
      if (!hasCollections || !claimsOk) return "partial";
      return "complete";
    }
    if (pageId === "ar") {
      const hasTrend = Array.isArray(patch.collectionsTrend?.current) && patch.collectionsTrend.current.length > 0;
      const hasTopClaims = Array.isArray(patch.topClaims) && patch.topClaims.length > 0;
      const hasKpis = Array.isArray(patch.kpis) && patch.kpis.some((row) => row && row.value && row.value !== "—");
      if (hasTrend && hasTopClaims) return "complete";
      if (hasTopClaims && hasKpis) return "complete";
      if (!hasTrend && !hasTopClaims) return "partial";
      return "partial";
    }
    return "complete";
  }

  function importedTrendMeta() {
    return { trend: "Imported", trendDir: "flat" };
  }

  function parseCsvRfc(text) {
    const rows = [];
    let row = [];
    let field = "";
    let inQuotes = false;
    const src = String(text || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
    for (let i = 0; i < src.length; i += 1) {
      const ch = src[i];
      if (inQuotes) {
        if (ch === '"') {
          if (src[i + 1] === '"') {
            field += '"';
            i += 1;
          } else {
            inQuotes = false;
          }
        } else {
          field += ch;
        }
        continue;
      }
      if (ch === '"') {
        inQuotes = true;
      } else if (ch === ",") {
        row.push(field);
        field = "";
      } else if (ch === "\n") {
        row.push(field);
        field = "";
        if (row.some((cell) => String(cell).trim())) rows.push(row);
        row = [];
      } else {
        field += ch;
      }
    }
    row.push(field);
    if (row.some((cell) => String(cell).trim())) rows.push(row);
    if (!rows.length) return [];
    const headers = rows[0].map((h) => String(h).trim());
    return rows.slice(1).map((cells) => {
      const out = {};
      headers.forEach((header, index) => {
        out[header] = (cells[index] || "").trim();
      });
      return out;
    });
  }

  function readCsvRows(text) {
    return parseCsvRfc(text);
  }

  function extractJsonRows(payload) {
    if (Array.isArray(payload)) return payload.filter((row) => row && typeof row === "object");
    if (payload && typeof payload === "object") {
      for (const key of ["rows", "data", "items", "notes", "claims"]) {
        if (Array.isArray(payload[key])) return payload[key].filter((row) => row && typeof row === "object");
      }
    }
    return [];
  }

  function rowsFromJsonProbe(payload) {
    if (!payload || typeof payload !== "object") return [];
    const categories = payload.top_expense_categories;
    if (!Array.isArray(categories)) return [];
    const period = String(payload.period || payload.period_end || "").trim();
    return categories
      .filter((item) => item && typeof item === "object" && item.amount != null && item.amount !== "")
      .map((item) => {
        const row = {
          Category: String(item.category || ""),
          Amount: item.amount,
        };
        const itemPeriod = String(item.period || period || "").trim();
        if (itemPeriod) row.Period = itemPeriod;
        else row.Scope = "YTD";
        return row;
      });
  }

  function readTabularFile(path, fs) {
    const raw = fs.readFileSync(path, "utf8");
    if (path.toLowerCase().endsWith(".json")) {
      const payload = JSON.parse(raw);
      const probeRows = rowsFromJsonProbe(payload);
      if (probeRows.length) return probeRows;
      return extractJsonRows(payload);
    }
    const trimmed = raw.trimStart();
    if (trimmed.startsWith("{")) {
      try {
        const payload = JSON.parse(trimmed);
        const probeRows = rowsFromJsonProbe(payload);
        if (probeRows.length) return probeRows;
      } catch {
        /* fall through to CSV */
      }
    }
    const sidecar = path.replace(/\.csv$/i, ".json");
    if (sidecar !== path && fs.existsSync(sidecar)) {
      try {
        const sidecarStat = fs.statSync(sidecar);
        const csvStat = fs.statSync(path);
        if (sidecarStat.mtimeMs >= csvStat.mtimeMs) {
          return extractJsonRows(JSON.parse(fs.readFileSync(sidecar, "utf8")));
        }
      } catch {
        /* fall through to CSV */
      }
    }
    return readCsvRows(raw);
  }

  function newestExisting(dir, names, fs) {
    const pathMod = require("node:path");
    let best = null;
    let bestMtime = -1;
    for (const name of names) {
      const candidate = pathMod.join(dir, name);
      if (!fs.existsSync(candidate)) continue;
      const mtime = fs.statSync(candidate).mtimeMs;
      if (mtime > bestMtime) {
        best = candidate;
        bestMtime = mtime;
      }
    }
    return best;
  }

  function loadDatasetNode(dir, names, fs) {
    if (!dir || !fs.existsSync(dir)) return null;
    const path = newestExisting(dir, names, fs);
    if (!path) return null;
    const stat = fs.statSync(path);
    return {
      sourceFile: require("node:path").basename(path),
      modifiedAt: new Date(stat.mtimeMs).toISOString(),
      rows: readTabularFile(path, fs),
    };
  }

  async function loadBundleNode() {
    const fs = require("node:fs");
    return attachBundleDiagnostics({
      loadedAt: new Date().toISOString(),
      softdent: {
        dir: REPO_IMPORT_SOFTDENT,
        dashboard: loadDatasetNode(REPO_IMPORT_SOFTDENT, MANIFEST_SOFTDENT_DASHBOARD_NAMES, fs),
        claims: loadDatasetNode(REPO_IMPORT_SOFTDENT, MANIFEST_SOFTDENT_CLAIMS_NAMES, fs),
        clinicalNotes: loadDatasetNode(REPO_IMPORT_SOFTDENT, MANIFEST_SOFTDENT_CLINICAL_NAMES, fs),
        ar: loadDatasetNode(REPO_IMPORT_SOFTDENT, MANIFEST_SOFTDENT_AR_NAMES, fs),
        newPatients: loadDatasetNode(REPO_IMPORT_SOFTDENT, MANIFEST_SOFTDENT_NEW_PATIENTS_NAMES, fs),
        treatmentPlans: loadDatasetNode(REPO_IMPORT_SOFTDENT, MANIFEST_SOFTDENT_TREATMENT_PLANS_NAMES, fs),
        caseAcceptance: loadDatasetNode(REPO_IMPORT_SOFTDENT, MANIFEST_SOFTDENT_CASE_ACCEPTANCE_NAMES, fs),
        hygieneRecall: loadDatasetNode(REPO_IMPORT_SOFTDENT, MANIFEST_SOFTDENT_HYGIENE_RECALL_NAMES, fs),
      },
      quickbooks: {
        dir: REPO_IMPORT_QUICKBOOKS,
        revenue: loadDatasetNode(REPO_IMPORT_QUICKBOOKS, MANIFEST_QB_REVENUE_NAMES, fs),
        profitAndLoss: loadDatasetNode(REPO_IMPORT_QUICKBOOKS, MANIFEST_QB_PL_NAMES, fs),
        expenses: loadDatasetNode(REPO_IMPORT_QUICKBOOKS, MANIFEST_QB_EXPENSE_NAMES, fs),
        expenseCategories: loadDatasetNode(REPO_IMPORT_QUICKBOOKS, MANIFEST_QB_EXPENSE_CATEGORY_NAMES, fs),
        ar: loadDatasetNode(REPO_IMPORT_QUICKBOOKS, MANIFEST_QB_AR_NAMES, fs),
      },
    });
  }

  // Browser file:// without pywebview returns null — use the desktop bridge, loopback API, or Node (NR2_LOAD_IMPORTS=1).
  async function loadBundleFromHttpApi() {
    if (typeof window === "undefined" || typeof fetch !== "function") return null;
    const host = String(window.location.hostname || "").toLowerCase();
    if (host !== "127.0.0.1" && host !== "localhost") return null;
    try {
      const response = await fetch("/api/import-bundle", { cache: "no-store" });
      if (!response.ok) return null;
      const payload = await response.json();
      return payload && typeof payload === "object" ? payload : null;
    } catch {
      return null;
    }
  }

  async function loadBundle(force) {
    const br = bridge();
    let bundle = null;
    if (br) {
      if (force && br.refreshImports) bundle = await br.refreshImports();
      else if (br.getImportBundle) bundle = await br.getImportBundle();
    }
    if (!bundle) bundle = await loadBundleFromHttpApi();
    if (!bundle && isNode && process.env.NR2_LOAD_IMPORTS === "1") bundle = await loadBundleNode();
    return bundle ? attachBundleDiagnostics(bundle) : null;
  }

  function hasSoftdentImport(bundle) {
    const sd = bundle && bundle.softdent;
    return Boolean(
      (sd && sd.dashboard && sd.dashboard.rows && sd.dashboard.rows.length) ||
        (sd && sd.claims && sd.claims.rows && sd.claims.rows.length) ||
        (sd && sd.ar && sd.ar.rows && sd.ar.rows.length),
    );
  }

  function hasQuickbooksImport(bundle) {
    const qb = bundle && bundle.quickbooks;
    return Boolean(
      (qb && qb.revenue && qb.revenue.rows && qb.revenue.rows.length) ||
        (qb && qb.expenses && qb.expenses.rows && qb.expenses.rows.length),
    );
  }

  function hasImportData(bundle) {
    return hasSoftdentImport(bundle) || hasQuickbooksImport(bundle);
  }

  function normalizeDashboardRows(rows) {
    return (rows || []).map((row) => {
      const collectionsPending = row.collectionsPending === true || row.CollectionsPending === true;
      const collectionsReported =
        !collectionsPending && row.collectionsReported !== false && row.CollectionsReported !== false;
      const parsedCollections = coerceFloat(row.collections ?? row.Collections);
      return {
        provider: String(row.provider || row.Provider || row.providerName || row.ProviderName || PRIMARY_PROVIDER).trim() || PRIMARY_PROVIDER,
        period: String(row.period || row.Period || ""),
        production: coerceFloat(row.production || row.Production) || 0,
        collections: collectionsReported ? (parsedCollections ?? 0) : null,
        collectionsReported,
        collectionsPending,
        insurance: coerceFloat(row.insurance || row.Insurance) || 0,
        patient: coerceFloat(row.patient || row.Patient) || 0,
      };
    });
  }

  function isPriorCalendarMonth(laterPeriod, earlierPeriod) {
    const later = normalizePeriodKey(laterPeriod);
    const earlier = normalizePeriodKey(earlierPeriod);
    const matchLater = later.match(/^(\d{4})-(\d{2})$/);
    const matchEarlier = earlier.match(/^(\d{4})-(\d{2})$/);
    if (!matchLater || !matchEarlier) return false;
    let year = Number(matchEarlier[1]);
    let month = Number(matchEarlier[2]) + 1;
    if (month > 12) {
      month = 1;
      year += 1;
    }
    return `${year}-${String(month).padStart(2, "0")}` === `${matchLater[1]}-${matchLater[2]}`;
  }

  function resolveComparablePeriod(softdentPeriod, quickbooksPeriod, referenceDate) {
    const sd = normalizePeriodKey(softdentPeriod);
    const qb = normalizePeriodKey(quickbooksPeriod);
    if (!sd) return qb;
    if (!qb) return sd;
    if (sd === qb) return sd;
    const ref = referenceDate instanceof Date ? referenceDate : new Date(referenceDate || Date.now());
    const currentMonth = `${ref.getFullYear()}-${String(ref.getMonth() + 1).padStart(2, "0")}`;
    if (sd === currentMonth && isPriorCalendarMonth(sd, qb)) return qb;
    return sd;
  }

  function dashboardRowsForPeriod(rows, periodKey) {
    const target = normalizePeriodKey(periodKey);
    if (!target) return normalizeDashboardRows(rows || []);
    return normalizeDashboardRows(rows || []).filter((row) => normalizePeriodKey(row.period) === target);
  }

  function resolveDashboardPeriodContext(bundle) {
    const dashboardRows = normalizeDashboardRows(((bundle.softdent && bundle.softdent.dashboard) || {}).rows || []);
    const aggregate = aggregateDashboard(dashboardRows);
    const qbPeriod = latestQuickbooksPeriod(bundle);
    const sdLatestPeriod = aggregate.period;
    const comparablePeriod = resolveComparablePeriod(sdLatestPeriod, qbPeriod, bundle.loadedAt || Date.now());
    const comparableRows = comparablePeriod ? dashboardRowsForPeriod(dashboardRows, comparablePeriod) : dashboardRows;
    const comparableAggregate = comparableRows.length ? aggregateDashboard(comparableRows) : aggregate;
    return {
      dashboardRows,
      aggregate,
      qbPeriod,
      sdLatestPeriod,
      comparablePeriod,
      comparableRows,
      comparableAggregate,
    };
  }

  function aggregateCollections(rows) {
    if (!rows.length) return { total: 0, reported: true };
    const reportedRows = rows.filter((row) => row.collectionsReported !== false);
    if (!reportedRows.length || reportedRows.some((row) => row.collections === null)) {
      return { total: null, reported: false };
    }
    return {
      total: rows.reduce((acc, row) => acc + (row.collections || 0), 0),
      reported: true,
    };
  }

  function aggregateDashboard(rows) {
    const collectionRollup = aggregateCollections(rows);
    const totals = rows.reduce(
      (acc, row) => {
        acc.production += row.production;
        acc.insurance += row.insurance;
        acc.patient += row.patient;
        return acc;
      },
      { production: 0, collections: collectionRollup.total, insurance: 0, patient: 0 },
    );
    totals.collectionsReported = collectionRollup.reported;
    const periods = rows.map((row) => row.period).filter(Boolean);
    const period = periods.length ? periods.sort().slice(-1)[0] : "";
    const byProvider = {};
    rows.forEach((row) => {
      const provider = row.provider || PRIMARY_PROVIDER;
      if (!byProvider[provider]) {
        byProvider[provider] = {
          provider,
          period,
          production: 0,
          collections: 0,
          insurance: 0,
          patient: 0,
        };
      }
      byProvider[provider].production += row.production;
      if (row.collections !== null) {
        byProvider[provider].collections += row.collections;
      }
      byProvider[provider].insurance += row.insurance;
      byProvider[provider].patient += row.patient;
    });
    const providerRows = Object.values(byProvider).sort((a, b) => b.production - a.production);
    return { totals, period, rows: providerRows };
  }

  function comparableDisplayTotals(displayAggregate) {
    const totals = displayAggregate && displayAggregate.totals;
    return (
      totals || {
        production: 0,
        collections: null,
        insurance: 0,
        patient: 0,
        collectionsReported: false,
      }
    );
  }

  function pickField(row, names) {
    for (const name of names) {
      if (row[name] !== undefined && row[name] !== "") return row[name];
      const match = Object.keys(row).find((key) => key.toLowerCase() === name.toLowerCase());
      if (match && row[match] !== undefined && row[match] !== "") return row[match];
    }
    return null;
  }

  function normalizePeriodKey(value) {
    const raw = String(value || "").trim();
    if (!raw) return "";
    const iso = raw.match(/^(\d{4})-(\d{2})/);
    if (iso) return `${iso[1]}-${iso[2]}`;
    const slash = raw.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
    if (slash) return `${slash[3]}-${String(slash[1]).padStart(2, "0")}`;
    const monthYear = raw.match(/^(\d{4})[-/](\d{1,2})$/);
    if (monthYear) return `${monthYear[1]}-${String(monthYear[2]).padStart(2, "0")}`;
    return raw.slice(0, 7);
  }

  function latestQuickbooksPeriod(bundle) {
    const qb = (bundle && bundle.quickbooks) || {};
    const rows = []
      .concat(((qb.revenue && qb.revenue.rows) || []))
      .concat(((qb.expenses && qb.expenses.rows) || []))
      .concat(((qb.profitAndLoss && qb.profitAndLoss.rows) || []));
    const periods = rows
      .map((row) => normalizePeriodKey(pickField(row, ["Month", "month", "Period", "period", "Date", "date"])))
      .filter(Boolean)
      .sort()
      .reverse();
    return periods[0] || "";
  }

  function assessCollectionHealth(rows, comparablePeriod) {
    const normalized = normalizeDashboardRows(rows || []);
    if (!normalized.length) {
      return {
        evaluated: false,
        reported: true,
        healthy: true,
        pending: false,
        latestZeroWithProduction: false,
        message: "OK",
      };
    }
    const scoped = comparablePeriod
      ? normalized.filter((row) => normalizePeriodKey(row.period) === normalizePeriodKey(comparablePeriod))
      : normalized;
    const sorted = [...(scoped.length ? scoped : normalized)].sort((a, b) =>
      String(a.period || "").localeCompare(String(b.period || "")),
    );
    const latest = sorted[sorted.length - 1];
    if (latest.collectionsPending) {
      // Pending = incomplete export, not a hard failure. UI uses pending flag + widget state "pending".
      return {
        evaluated: true,
        reported: false,
        pending: true,
        healthy: true,
        latestZeroWithProduction: false,
        message: "Collections export pending for comparable period",
      };
    }
    if (latest.collectionsReported === false) {
      return {
        evaluated: true,
        reported: false,
        pending: false,
        healthy: false,
        latestZeroWithProduction: false,
        message: "Collections missing for comparable period",
      };
    }
    if (latest.production > 0 && (latest.collections === null || latest.collections === 0)) {
      return {
        evaluated: true,
        reported: true,
        pending: false,
        healthy: false,
        latestZeroWithProduction: true,
        message: "$0 collections with production — verify final SoftDent daysheet export",
      };
    }
    return {
      evaluated: true,
      reported: true,
      pending: false,
      healthy: true,
      latestZeroWithProduction: false,
      message: "OK",
    };
  }

  function collectionsPendingValue(aggregate, collectionHealth) {
    if (collectionHealth && collectionHealth.pending) return null;
    const totals = aggregate && aggregate.totals;
    return totals ? totals.collections ?? null : null;
  }

  function resolveCollectionHealth(collectionHealth, aggregate) {
    if (collectionHealth && collectionHealth.pending) {
      return {
        evaluated: true,
        reported: false,
        pending: true,
        healthy: true,
        latestZeroWithProduction: false,
        message: collectionHealth.message || "Collections export pending for comparable period",
      };
    }
    if (collectionHealth && collectionHealth.evaluated) return collectionHealth;
    const reported = aggregate.totals.collectionsReported !== false;
    const production = aggregate.totals.production || 0;
    const collections = aggregate.totals.collections;
    const latestZeroWithProduction = reported && production > 0 && (collections === 0 || collections === null);
    return {
      evaluated: true,
      reported,
      healthy: reported && !latestZeroWithProduction,
      latestZeroWithProduction,
      message: !reported
        ? "Collections missing for latest period"
        : latestZeroWithProduction
          ? "$0 collections with production — verify final SoftDent daysheet export"
          : "OK",
    };
  }

  function scopeExpenseCategoryRows(categoryRows, alignPeriod, monthlyExpensesLatest) {
    const rows = categoryRows || [];
    const labeledScope = rows
      .map((row) => String(pickField(row, ["Scope", "scope"]) || "").trim().toUpperCase())
      .find(Boolean);
    if (labeledScope && /YTD|CUMULATIVE|ANNUAL/.test(labeledScope)) {
      return {
        rows,
        scope: "ytd",
        scopeLabel: "YTD cumulative (export labeled)",
      };
    }
    const hasPeriod = rows.some((row) => normalizePeriodKey(pickField(row, ["Period", "period", "Month", "month"])));
    if (!hasPeriod) {
      const categoryTotal = rows.reduce((acc, row) => acc + (coerceFloat(pickField(row, ["Amount", "amount"])) || 0), 0);
      const monthly = coerceFloat(monthlyExpensesLatest);
      if (monthly !== null && monthly > 0 && categoryTotal > monthly * 1.5) {
        return {
          rows,
          scope: "ytd_inferred",
          scopeLabel: "YTD cumulative (inferred — category total exceeds monthly P&L expenses)",
        };
      }
      return {
        rows,
        scope: "unlabeled",
        scopeLabel: "Category pivot (export scope unlabeled — verify with accounting)",
      };
    }
    const period = normalizePeriodKey(alignPeriod);
    const filtered = period
      ? rows.filter((row) => normalizePeriodKey(pickField(row, ["Period", "period", "Month", "month"])) === period)
      : rows;
    const scopedRows = filtered.length ? filtered : rows;
    const scopedPeriod = period || normalizePeriodKey(pickField(scopedRows[0], ["Period", "period", "Month", "month"]));
    return {
      rows: scopedRows,
      scope: "period",
      scopeLabel: scopedPeriod ? `Period ${scopedPeriod}` : "Period unknown",
    };
  }

  function comparePeriodAlignment(softdentPeriod, quickbooksPeriod, hasSd, hasQb, referenceDate) {
    const sdLatest = normalizePeriodKey(softdentPeriod);
    const qb = normalizePeriodKey(quickbooksPeriod);
    const comparablePeriod = resolveComparablePeriod(sdLatest, qb, referenceDate);
    if (!hasSd || !hasQb) {
      return {
        aligned: true,
        softdentPeriod: sdLatest,
        quickbooksPeriod: qb,
        comparablePeriod,
        message: "",
      };
    }
    if (!sdLatest || !qb) {
      return {
        aligned: false,
        softdentPeriod: sdLatest,
        quickbooksPeriod: qb,
        comparablePeriod,
        message: "Period unknown for one or more sources; cross-source comparison not verified.",
      };
    }
    if (comparablePeriod === qb) {
      return {
        aligned: true,
        softdentPeriod: sdLatest,
        quickbooksPeriod: qb,
        comparablePeriod,
        message: "",
        note:
          sdLatest !== qb
            ? `Cross-source view uses ${qb}; SoftDent also includes ${sdLatest} in progress.`
            : "",
      };
    }
    return {
      aligned: false,
      softdentPeriod: sdLatest,
      quickbooksPeriod: qb,
      comparablePeriod,
      message: `Period mismatch: SoftDent ${comparablePeriod || sdLatest} vs QuickBooks ${qb}.`,
    };
  }

  function buildFinancialDataQuality(bundle, aggregate, qb, periodAlignment, collectionHealth) {
    let score = 0;
    const categories = [];
    const diag = bundle && bundle.diagnostics;
    const freshOk = !diag || !((diag.critical || []).length);
    categories.push({ label: "Import freshness", score: freshOk ? 25 : 10, value: freshOk ? "OK" : "Stale or missing" });
    score += freshOk ? 25 : 10;

    const health = resolveCollectionHealth(collectionHealth, aggregate);
    const fieldScore = health.pending ? 8 : health.reported ? 10 : 0;
    categories.push({
      label: "Collections field",
      score: fieldScore,
      value: health.pending ? "Pending export" : health.reported ? "Present" : "Missing for period",
    });
    score += fieldScore;
    const healthScore = health.pending ? 12 : !health.reported ? 0 : health.healthy ? 15 : 0;
    categories.push({
      label: "Collection health",
      score: healthScore,
      value: health.healthy ? "OK" : health.message,
    });
    score += healthScore;

    const periodOk = periodAlignment.aligned;
    categories.push({
      label: "Cross-source period",
      score: periodOk ? 25 : 5,
      value: periodOk ? "Aligned" : "Mismatch",
    });
    score += periodOk ? 25 : 5;

    const rev = qb.revenue;
    const exp = qb.expenses;
    const ni = qb.netIncome;
    const qbReconcile =
      qb.plReconcile && qb.plReconcile.matches !== false
        ? rev === null || exp === null || ni === null || Math.abs(rev - exp - ni) < 1
        : false;
    categories.push({
      label: "QB P&L reconcile",
      score: qbReconcile ? 25 : 10,
      value: qbReconcile ? "OK" : "Variance",
    });
    score += qbReconcile ? 25 : 10;

    const overallPass =
      freshOk &&
      (health.pending || (health.reported && health.healthy)) &&
      periodOk &&
      qbReconcile;
    return { score: Math.min(100, score), categories, overallPass };
  }

  function diagnosticsApi() {
    if (typeof ImportDiagnostics !== "undefined") return ImportDiagnostics;
    if (typeof window !== "undefined" && window.ImportDiagnostics) return window.ImportDiagnostics;
    try {
      return require("./import-diagnostics.js");
    } catch {
      return null;
    }
  }

  function attachBundleDiagnostics(bundle) {
    if (!bundle || bundle.diagnostics) return bundle;
    const diag = diagnosticsApi();
    if (diag && typeof diag.evaluateBundle === "function") {
      bundle.diagnostics = diag.evaluateBundle(bundle);
    }
    return bundle;
  }

  function buildCollectionRateMetrics(rows, collectionHealth) {
    const normalized = normalizeDashboardRows(rows || []).filter((row) => row.period);
    normalized.sort((a, b) => String(a.period).localeCompare(String(b.period)));
    const latest = normalized[normalized.length - 1];
    const latestIncomplete = Boolean(
      latest &&
        (latest.collectionsPending ||
          (latest.collectionsReported !== false &&
            latest.production > 0 &&
            (latest.collections === null || latest.collections === 0))),
    );
    const latestMonthRate =
      latest && latest.production > 0 && latest.collections !== null && latest.collectionsReported !== false
        ? `${((latest.collections / latest.production) * 100).toFixed(1)}%`
        : latestIncomplete
          ? "0.0%"
          : null;

    const trailingRows = latestIncomplete ? normalized.slice(0, -1) : normalized;
    const trailingProduction = trailingRows.reduce((acc, row) => acc + (row.production || 0), 0);
    const trailingCollections = trailingRows.reduce((acc, row) => {
      if (row.collections === null || row.collectionsReported === false) return acc;
      return acc + (row.collections || 0);
    }, 0);
    const trailingComplete =
      trailingRows.length > 0 &&
      trailingRows.every((row) => row.collectionsReported !== false && row.collections !== null);

    let trailingRate = null;
    let trailingPeriods = "";
    if (trailingRows.length && trailingComplete && trailingProduction > 0) {
      trailingRate = `${((trailingCollections / trailingProduction) * 100).toFixed(1)}%`;
      trailingPeriods =
        trailingRows.length === 1
          ? trailingRows[0].period
          : `${trailingRows[0].period} to ${trailingRows[trailingRows.length - 1].period}`;
    }

    const displayRate = trailingRate || (collectionHealth && !collectionHealth.reported ? "Not reported" : latestMonthRate || "—");
    const displayLabel = trailingRate
      ? `Trailing collection rate (${trailingPeriods})`
      : latestIncomplete
        ? "Latest month rate (incomplete — do not use for period close)"
        : "Collection rate";

    return {
      trailingRate,
      trailingPeriods,
      trailingMonthCount: trailingRows.length,
      latestMonthRate,
      latestMonthPeriod: latest?.period || "",
      latestMonthIncomplete: latestIncomplete,
      displayRate,
      displayLabel,
    };
  }

  function buildProductionTrendFromRows(rows, collectionRateMetrics) {
    const periods = (rows || [])
      .map((row) => ({
        period: String(row.period || "").trim(),
        production: Number(row.production) || 0,
        collections: Number(row.collections) || 0,
      }))
      .filter((row) => row.period);
    if (periods.length < 2) return null;
    periods.sort((a, b) => a.period.localeCompare(b.period));
    const production = periods.map((row) => row.production);
    const average = production.map((_, index) => {
      const slice = production.slice(0, index + 1);
      return slice.reduce((acc, value) => acc + value, 0) / slice.length;
    });
    const maxProd = Math.max(...production, 0);
    const yStep = maxProd > 0 ? Math.ceil(maxProd / 2 / 1000) * 1000 : 50000;
    const rateMetrics = collectionRateMetrics || buildCollectionRateMetrics(rows, { evaluated: false, reported: true });
    const rateEntry = {
      label: "Trailing Collection Rate",
      value: rateMetrics.trailingRate || rateMetrics.displayRate || "—",
      trendDir: "flat",
      note: rateMetrics.trailingPeriods ? `Imported months: ${rateMetrics.trailingPeriods}` : rateMetrics.displayLabel,
    };
    return {
      yLabels: [`$${Math.round(yStep / 1000)}k`, `$${Math.round((yStep * 2) / 1000)}k`],
      labels: periods.map((row) => row.period),
      production,
      average,
      ytd: [
        { label: "YTD Production", value: formatMoney(production.reduce((acc, value) => acc + value, 0)), trendDir: "flat" },
        rateEntry,
        Object.assign({}, rateEntry, { label: "YTD Collection Rate" }),
      ],
    };
  }

  function buildPayerMixFromAggregate(aggregate, collectionRateMetrics) {
    const insurance = aggregate.totals.insurance || 0;
    const patient = aggregate.totals.patient || 0;
    const total = insurance + patient;
    if (total <= 0) return null;
    const production = aggregate.totals.production || 0;
    const collections = aggregate.totals.collections || 0;
    const fallbackRate = production > 0 ? `${((collections / production) * 100).toFixed(1)}%` : "—";
    return {
      total: formatMoney(total),
      rate: collectionRateMetrics?.displayRate || fallbackRate,
      rateLabel: collectionRateMetrics?.displayLabel || "Collection rate",
      latestMonthRate: collectionRateMetrics?.latestMonthRate || null,
      latestMonthPeriod: collectionRateMetrics?.latestMonthPeriod || "",
      latestMonthIncomplete: Boolean(collectionRateMetrics?.latestMonthIncomplete),
      trailingPeriods: collectionRateMetrics?.trailingPeriods || "",
      rateTrend: collectionRateMetrics?.trailingPeriods
        ? `Trailing ${collectionRateMetrics.trailingPeriods}`
        : collectionRateMetrics?.latestMonthIncomplete
          ? "Latest month incomplete"
          : "Imported",
      rateTrendDir: "flat",
      slices: [
        { label: "Insurance", pct: Math.round((insurance / total) * 1000) / 10 },
        { label: "Patient", pct: Math.round((patient / total) * 1000) / 10 },
      ].filter((slice) => slice.pct > 0),
    };
  }

  function buildMonthlySeriesFromRows(rows, amountFields) {
    const monthly = (rows || [])
      .map((row) => ({
        label: String(pickField(row, ["Month", "month", "Period", "period", "Date", "date"]) || "").trim(),
        amount: coerceFloat(pickField(row, amountFields)),
      }))
      .filter((row) => row.label && row.amount !== null);
    if (monthly.length < 2) return null;
    monthly.sort((a, b) => a.label.localeCompare(b.label));
    return {
      labels: monthly.map((row) => row.label),
      values: monthly.map((row) => row.amount),
    };
  }

  function buildMonthlyExpensesFromRows(rows) {
    return buildMonthlySeriesFromRows(rows, ["Amount", "amount", "TotalExpense", "Expenses", "Expense"]);
  }

  function buildMonthlyRevenueFromRows(rows) {
    return buildMonthlySeriesFromRows(rows, ["Amount", "amount", "TotalIncome", "Income", "Revenue", "total_income"]);
  }

  function buildQuickbooksArSummary(arRows) {
    const buckets = (arRows || [])
      .map((row) => ({
        bucket: String(pickField(row, ["Bucket", "bucket", "AgingBucket", "Range", "range"]) || "Total"),
        amount: coerceFloat(pickField(row, ["Balance", "balance", "Amount", "amount", "AccountsReceivable"])),
      }))
      .filter((row) => row.amount !== null);
    if (!buckets.length) {
      const total = coerceFloat(pickField((arRows || [])[0] || {}, ["AccountsReceivable", "TotalAR", "total_ar"]));
      if (total === null) return null;
      return { total, buckets: [{ bucket: "Total", amount: total }] };
    }
    const total = buckets.reduce((acc, row) => acc + row.amount, 0);
    return { total, buckets };
  }

  function softdentArTotal(bundle) {
    const arRows = ((bundle.softdent && bundle.softdent.ar) || {}).rows || [];
    const buckets = arRows
      .map((row) => coerceFloat(pickField(row, ["Amount", "Balance", "amount", "total"])))
      .filter((amount) => amount !== null);
    if (!buckets.length) return null;
    return buckets.reduce((acc, amount) => acc + amount, 0);
  }

  function quickbooksArTotal(bundle) {
    const arRows = ((bundle.quickbooks && bundle.quickbooks.ar) || {}).rows || [];
    const summary = buildQuickbooksArSummary(arRows);
    return summary ? summary.total : null;
  }

  function compareArCrossSource(softdentTotal, quickbooksTotal) {
    if (softdentTotal === null || softdentTotal === undefined) {
      return {
        comparable: false,
        softdentTotal: null,
        quickbooksTotal: quickbooksTotal ?? null,
        variance: null,
        withinTolerance: null,
        message: "SoftDent A/R export not loaded.",
      };
    }
    if (quickbooksTotal === null || quickbooksTotal === undefined) {
      return {
        comparable: false,
        softdentTotal,
        quickbooksTotal: null,
        variance: null,
        withinTolerance: null,
        message: "QuickBooks A/R not loaded — drop quickbooks_ar.csv in the QuickBooks import folder.",
      };
    }
    const variance = Math.abs(softdentTotal - quickbooksTotal);
    return {
      comparable: false,
      softdentTotal,
      quickbooksTotal,
      variance,
      withinTolerance: null,
      message:
        `SoftDent operational A/R ($${softdentTotal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}) ` +
        `and QuickBooks ledger A/R ($${quickbooksTotal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}) ` +
        `use different scopes — variance $${variance.toFixed(2)} is informational only.`,
    };
  }

  function latestPeriodRow(rows) {
    const periodized = (rows || []).filter((row) =>
      String(pickField(row, ["Month", "month", "Period", "period", "Date", "date"]) || "").trim(),
    );
    if (!periodized.length) return (rows || [])[0] || null;
    return periodized
      .slice()
      .sort((a, b) =>
        String(pickField(b, ["Month", "month", "Period", "period", "Date", "date"]) || "").localeCompare(
          String(pickField(a, ["Month", "month", "Period", "period", "Date", "date"]) || ""),
        ),
      )[0];
  }

  function quickbooksTotals(bundle) {
    const revenueRows = ((bundle.quickbooks && bundle.quickbooks.revenue) || {}).rows || [];
    const expenseRows = ((bundle.quickbooks && bundle.quickbooks.expenses) || {}).rows || [];
    const plRows = ((bundle.quickbooks && bundle.quickbooks.profitAndLoss) || {}).rows || [];
    const totalFromRows = (rows, totalFields, amountFields) => {
      const latest = latestPeriodRow(rows);
      if (latest) {
        const explicit = coerceFloat(pickField(latest, totalFields));
        if (explicit !== null) return explicit;
        return coerceFloat(pickField(latest, amountFields));
      }
      const first = rows[0] || {};
      const explicitTotal = coerceFloat(pickField(first, totalFields));
      if (explicitTotal !== null) return explicitTotal;
      return rows.reduce((acc, row) => acc + (coerceFloat(pickField(row, amountFields)) || 0), 0);
    };
    let revenue = totalFromRows(revenueRows, ["TotalIncome", "Income", "Revenue", "total_income"], ["Amount", "amount", "Total"]);
    let expenses = totalFromRows(
      expenseRows,
      ["TotalExpense", "Expenses", "Expense", "total_expense"],
      ["Amount", "amount", "Total"],
    );
    const firstRevenue = revenueRows[0] || {};
    const firstExpense = expenseRows[0] || {};
    if (!revenue && expenseRows.length) {
      revenue = coerceFloat(pickField(firstExpense, ["TotalIncome", "Income", "Revenue"])) || revenue;
    }
    if (!expenses && revenueRows.length) {
      expenses = coerceFloat(pickField(firstRevenue, ["TotalExpense", "Expenses", "Expense"])) || expenses;
    }
    const plLatest = latestPeriodRow(plRows);
    const plNetIncome = plLatest ? coerceFloat(pickField(plLatest, ["NetIncome", "net_income", "Net Income"])) : null;
    const plRevenue = plLatest ? coerceFloat(pickField(plLatest, ["TotalIncome", "Income", "Revenue", "total_income"])) : null;
    const plExpenses = plLatest
      ? coerceFloat(pickField(plLatest, ["TotalExpense", "Expenses", "Expense", "total_expense"]))
      : null;
    const derivedNetIncome = revenue !== null && expenses !== null ? revenue - expenses : null;
    if (plRevenue !== null) revenue = plRevenue;
    if (plExpenses !== null) expenses = plExpenses;
    const netIncome = plNetIncome !== null ? plNetIncome : derivedNetIncome;
    const plReconcile = {
      derivedNetIncome,
      plNetIncome,
      matches:
        derivedNetIncome === null || plNetIncome === null || Math.abs(derivedNetIncome - plNetIncome) < 1,
    };
    const modifiedAt =
      (bundle.quickbooks.profitAndLoss && bundle.quickbooks.profitAndLoss.modifiedAt) ||
      (bundle.quickbooks.revenue && bundle.quickbooks.revenue.modifiedAt) ||
      (bundle.quickbooks.expenses && bundle.quickbooks.expenses.modifiedAt) ||
      bundle.loadedAt;
    return { revenue, expenses, netIncome, derivedNetIncome, plNetIncome, plReconcile, modifiedAt, revenueRows, expenseRows, plRows };
  }

  function buildSoftdentDashboard(bundle) {
    if (!hasSoftdentImport(bundle)) return null;
    const sd = bundle.softdent || {};
    const periodCtx = resolveDashboardPeriodContext(bundle);
    const dashboardRows = periodCtx.dashboardRows;
    const aggregate = periodCtx.aggregate;
    const displayAggregate = periodCtx.comparableAggregate;
    const displayTotals = comparableDisplayTotals(displayAggregate);
    const comparablePeriod = periodCtx.comparablePeriod;
    const collectionsPending = Boolean(
      periodCtx.comparableRows.some((row) => row.collectionsPending) &&
        !periodCtx.comparableRows.some((row) => row.collectionsReported !== false && !row.collectionsPending),
    );
    const arRows = (sd.ar && sd.ar.rows) || [];
    const arBuckets = arRows
      .map((row) => ({
        bucket: String(pickField(row, ["Bucket", "bucket", "AgingBucket", "Range", "range"]) || "Total"),
        amount: coerceFloat(pickField(row, ["Amount", "Balance", "amount", "total"])),
      }))
      .filter((row) => row.amount !== null);
    const arTotal = arBuckets.reduce((acc, row) => acc + row.amount, 0);
    const hasAr = arBuckets.length > 0 && arTotal > 0;
    const modifiedAt = (sd.dashboard && sd.dashboard.modifiedAt) || bundle.loadedAt;
    const exports = [];
    ["dashboard", "claims", "clinicalNotes", "ar"].forEach((key) => {
      const dataset = sd[key];
      if (!dataset || !dataset.sourceFile) return;
      exports.push({
        name: dataset.sourceFile,
        source: "SoftDent",
        dataset: key,
        status: dataset.rows && dataset.rows.length ? "SUCCESS" : "EMPTY",
        completed: formatFreshness(dataset.modifiedAt),
        records: String((dataset.rows || []).length),
        size: "—",
      });
    });

    const glance = [
      { label: "Providers Loaded", value: dashboardRows.length ? "1" : "0" },
      { label: "Import Period", value: comparablePeriod || aggregate.period || "—" },
      { label: "Claims Rows", value: formatCount(((sd.claims && sd.claims.rows) || []).length) },
      { label: "Clinical Notes", value: formatCount(((sd.clinicalNotes && sd.clinicalNotes.rows) || []).length) },
      { label: "Production MTD", value: formatMoney(displayTotals.production) },
      {
        label: "Collections MTD",
        value: collectionsPending ? "Pending export" : formatMoney(displayTotals.collections),
      },
    ];

    const patch = {
      dataSource: "import",
      importedAt: modifiedAt,
      date: comparablePeriod || aggregate.period || new Date(modifiedAt).toLocaleDateString(),
      source: "SoftDent",
      status: "Connected",
      production: displayTotals.production,
      collections: collectionsPending ? null : displayTotals.collections,
      collectionsPending,
      comparablePeriod,
      hero: hasAr
        ? {
            label: "DAYSHEET A/R",
            value: formatMoney(arTotal),
            subtitle: "Total A/R (imported)",
            ...importedTrendMeta(),
            spark: null,
            sparkNote: "No historical A/R trend in import",
          }
        : {
            label: "DAYSHEET A/R",
            value: "—",
            subtitle: "Awaiting verified SoftDent A/R export",
            trend: "Import only",
            trendDir: "flat",
            spark: null,
          },
      collectionsMissing: !collectionsPending && displayTotals.collectionsReported === false,
      collectionsReported: collectionsPending ? false : displayTotals.collectionsReported !== false,
      subMetrics: [
            { label: "Production", value: formatMoney(displayTotals.production) },
            {
              label: "Collections",
              value: collectionsPending ? "Pending export" : formatMoney(displayTotals.collections),
            },
            { label: "Insurance", value: formatMoney(displayTotals.insurance) },
            { label: "Patient", value: formatMoney(displayTotals.patient) },
          ],
      aging: arBuckets.map((bucket) => ({
        bucket: bucket.bucket,
        amount: formatMoney(bucket.amount),
        pct: arTotal ? Math.round((bucket.amount / arTotal) * 1000) / 10 : 0,
      })),
      responsibility: {
            total: hasAr ? formatMoney(arTotal) : "—",
            insurance: { amount: formatMoney(aggregate.totals.insurance), pct: 0 },
            patient: { amount: formatMoney(aggregate.totals.patient), pct: 0 },
            collectability: "—",
            collectable: "—",
          },
      health: [
        { label: "Connection", value: "Imported", ok: true },
        { label: "Data Freshness", value: formatFreshness(modifiedAt), ok: true },
        { label: "Dashboard Export", value: sd.dashboard ? sd.dashboard.sourceFile : "Missing", ok: Boolean(sd.dashboard) },
        {
          label: "Claims Export",
          value: sd.claims && sd.claims.rows && sd.claims.rows.length ? sd.claims.sourceFile : "Missing — awaiting SoftDent claims export",
          ok: Boolean(sd.claims && sd.claims.rows && sd.claims.rows.length),
        },
        {
          label: "Clinical Notes",
          value:
            sd.clinicalNotes && sd.clinicalNotes.rows && sd.clinicalNotes.rows.length
              ? sd.clinicalNotes.sourceFile
              : "Missing — awaiting SoftDent clinical notes export",
          ok: Boolean(sd.clinicalNotes && sd.clinicalNotes.rows && sd.clinicalNotes.rows.length),
        },
        { label: "A/R Export", value: hasAr ? sd.ar.sourceFile : "Not loaded", ok: hasAr },
        ...(collectionsPending
          ? [{ label: "Collections", value: "Awaiting daysheet export for comparable period", ok: true }]
          : displayTotals.production > 0 && displayTotals.collectionsReported === false
          ? [{ label: "Collections", value: "Not reported for this period — verify daysheet export", ok: false }]
          : displayTotals.production > 0 && displayTotals.collections === 0
            ? [{ label: "Collections", value: "Source reports $0 collections for this period", ok: false }]
            : []),
      ],
      glance,
      exports,
    };
    return assignPatch(emptyDashboard("softdent"), Object.assign({ pageId: "softdent" }, patch));
  }

  function buildQuickbooksDashboard(bundle) {
    if (!hasQuickbooksImport(bundle)) return null;
    const totals = quickbooksTotals(bundle);
    const grossProfit = totals.revenue !== null && totals.expenses !== null ? totals.revenue - totals.expenses : null;
    const margin = totals.revenue && grossProfit !== null ? `${((grossProfit / totals.revenue) * 100).toFixed(1)}% Margin` : "";
    const rows = [
      { category: "Revenue", amount: formatMoney(totals.revenue), change: "Imported", changeTone: "flat" },
      { category: "Operating Expenses", amount: formatMoney(totals.expenses), change: "Imported", changeTone: "flat" },
      {
        category: "Net Income",
        amount: formatMoney(totals.netIncome),
        change: "Imported",
        changeTone: "flat",
        sub: margin,
        highlight: true,
      },
    ];
    const categoryRows = ((bundle.quickbooks && bundle.quickbooks.expenseCategories) || {}).rows || [];
    const categoryScope = scopeExpenseCategoryRows(categoryRows, latestQuickbooksPeriod(bundle), totals.expenses);
    const scopedCategoryRows = categoryScope.rows;
    const expenseCategories = scopedCategoryRows
      .map((row) => ({
        label: String(pickField(row, ["Category", "category"]) || ""),
        amount: formatMoney(pickField(row, ["Amount", "amount"])),
        pct: 0,
      }))
      .filter((row) => row.label);
    const categoryTotal = scopedCategoryRows.reduce((acc, row) => acc + (coerceFloat(pickField(row, ["Amount", "amount"])) || 0), 0);
    expenseCategories.forEach((row) => {
      const amt = coerceFloat(row.amount);
      row.pct = categoryTotal && amt !== null ? Math.round((amt / categoryTotal) * 1000) / 10 : 0;
    });
    const donutColors = ["#d6b15e", "#64748b", "#94a3b8", "#cbd5e1", "#e2e8f0"];
    const expenseCategoryDonut = expenseCategories.length
      ? {
          total: formatMoney(categoryTotal || totals.expenses),
          scope: categoryScope.scope,
          scopeLabel: categoryScope.scopeLabel,
          monthlyExpensesLatest: formatMoney(totals.expenses),
          slices: expenseCategories.map((row, index) => ({
            label: row.label,
            pct: row.pct,
            color: donutColors[index % donutColors.length],
          })),
        }
      : undefined;
    const monthlyExpenses = buildMonthlyExpensesFromRows(totals.expenseRows);
    const monthlyRevenue = buildMonthlyRevenueFromRows(totals.revenueRows);
    const arRows = ((bundle.quickbooks && bundle.quickbooks.ar) || {}).rows || [];
    const arSummary = buildQuickbooksArSummary(arRows);
    return assignPatch(emptyDashboard("quickbooks"), {
      pageId: "quickbooks",
      dataSource: "import",
      importedAt: totals.modifiedAt,
      syncStatus: "Connected",
      lastSync: formatFreshness(totals.modifiedAt),
      revenue: totals.revenue,
      expenses: totals.expenses,
      plReconcile: totals.plReconcile,
      ...(expenseCategoryDonut ? { expenseCategories: expenseCategoryDonut } : {}),
      ...(monthlyExpenses ? { monthlyExpenses } : {}),
      ...(monthlyRevenue ? { monthlyRevenue } : {}),
      ...(arSummary
        ? {
            ar: {
              total: formatMoney(arSummary.total),
              buckets: arSummary.buckets.map((bucket) => ({
                bucket: bucket.bucket,
                amount: formatMoney(bucket.amount),
              })),
            },
          }
        : {}),
      pl: {
        range: `Imported ${formatFreshness(totals.modifiedAt)}`,
        rows,
      },
      sync: {
        connection: "QuickBooks import",
        access: "Read-Only",
        frequency: "On file refresh",
        lastSync: formatFreshness(totals.modifiedAt),
        status: "Connected",
      },
    });
  }

  function buildFinancialDashboard(bundle, softdent, quickbooks) {
    if (!hasSoftdentImport(bundle) && !hasQuickbooksImport(bundle)) return null;
    const periodCtx = resolveDashboardPeriodContext(bundle);
    const dashboardRows = periodCtx.dashboardRows;
    const aggregate = periodCtx.aggregate;
    const displayAggregate = periodCtx.comparableAggregate;
    const displayTotals = comparableDisplayTotals(displayAggregate);
    const qb = quickbooksTotals(bundle);
    const hasSd = hasSoftdentImport(bundle);
    const hasQb = hasQuickbooksImport(bundle);
    const qbPeriod = periodCtx.qbPeriod;
    const periodAlignment = comparePeriodAlignment(periodCtx.sdLatestPeriod, qbPeriod, hasSd, hasQb, bundle.loadedAt || Date.now());
    const collectionHealth = assessCollectionHealth(dashboardRows, periodCtx.comparablePeriod);
    const production = displayTotals.production || null;
    const collections = collectionsPendingValue(displayAggregate || { totals: displayTotals }, collectionHealth);
    const collectionsMissing = !collectionHealth.pending && production > 0 && !collectionHealth.reported;
    const collectionsZeroWithProduction = collectionHealth.latestZeroWithProduction;
    const collectionRateMetrics = buildCollectionRateMetrics(dashboardRows, collectionHealth);
    const collectionRate = collectionRateMetrics.displayRate;
    const productionTrend = buildProductionTrendFromRows(dashboardRows, collectionRateMetrics);
    const payerMix = buildPayerMixFromAggregate(aggregate, collectionRateMetrics);
    const quality = buildFinancialDataQuality(bundle, aggregate, qb, periodAlignment, collectionHealth);
    const arCrossCheck = compareArCrossSource(softdentArTotal(bundle), quickbooksArTotal(bundle));
    const periodLabel = periodAlignment.comparablePeriod || periodAlignment.softdentPeriod || aggregate.period || "";
    const dateRange = !periodAlignment.aligned && periodAlignment.message
      ? periodAlignment.message
      : periodLabel
        ? periodAlignment.note
          ? `Period ${periodLabel} · ${periodAlignment.note}`
          : `Period ${periodLabel}`
        : `Imported ${formatFreshness(bundle.loadedAt)}`;
    const prodTrend = importedTrendMeta();
    return assignPatch(emptyDashboard("financial"), {
      pageId: "financial",
      dataSource: "import",
      importedAt: bundle.loadedAt,
      periodAlignment,
      singleSource: (hasSd && !hasQb) || (!hasSd && hasQb),
      bothSources: hasSd && hasQb,
      collectionsMissing,
      collectionsZeroWithProduction,
      collectionsPending: Boolean(collectionHealth.pending),
      collectionHealth,
      collectionRateMetrics,
      arCrossCheck,
      dateRange,
      productionMtd: {
        label: "Production MTD",
        value: formatMoney(production),
        ...prodTrend,
        vs: softdent ? `SoftDent import · ${formatFreshness(softdent.importedAt)}` : "SoftDent import",
        chart: {
          yLabels: productionTrend ? productionTrend.yLabels : ["$0", "$50k", "$100k"],
          xLabels: productionTrend ? productionTrend.labels : ["Import"],
          values: productionTrend ? productionTrend.production : [production || 0],
        },
      },
      ...(productionTrend ? { productionTrend } : {}),
      ...(payerMix ? { payerMix } : {}),
      metrics: [
        {
          label: "Collections MTD",
          value: collectionHealth.pending ? "Pending export" : formatMoney(collections),
          tone: collectionHealth.pending || collectionsMissing ? "gold" : "green",
          ...(collectionsMissing
            ? { trend: "Not reported", trendDir: "down" }
            : collectionHealth.pending
              ? { trend: "Pending export", trendDir: "flat" }
              : importedTrendMeta()),
          vs: collectionHealth.pending
            ? "Comparable period export not loaded"
            : collectionsMissing
              ? "Verify daysheet export — not a true 0% rate"
              : "SoftDent import",
          subLabel: collectionRateMetrics.displayLabel,
          subValue: collectionRate,
          ...(collectionRateMetrics.latestMonthIncomplete
            ? {
                subTrend: `Latest month ${collectionRateMetrics.latestMonthPeriod}: ${collectionRateMetrics.latestMonthRate}`,
                subTrendDir: "down",
              }
            : collectionsMissing
              ? { subTrend: "Missing", subTrendDir: "down" }
              : { subTrend: collectionRateMetrics.trailingPeriods ? `Trailing ${collectionRateMetrics.trailingPeriods}` : "Imported", subTrendDir: "flat" }),
        },
        {
          label: "QuickBooks Revenue",
          value: formatMoney(qb.revenue),
          tone: "blue",
          ...(periodAlignment.aligned ? importedTrendMeta() : { trend: "Period check", trendDir: "down" }),
          vs: quickbooks
            ? `QuickBooks import · ${formatFreshness(quickbooks.importedAt)}${qbPeriod ? ` · ${qbPeriod}` : ""}`
            : "QuickBooks import",
        },
        {
          label: "QuickBooks Net Income",
          value: formatMoney(qb.netIncome),
          tone: "purple",
          ...(periodAlignment.aligned ? importedTrendMeta() : { trend: "Period check", trendDir: "down" }),
          vs: qbPeriod ? `QuickBooks · ${qbPeriod}` : "QuickBooks import",
        },
      ],
      providers: {
        rows: aggregate.rows.map((row) => ({
          name: row.provider,
          amount: formatMoney(row.production),
          pct: production ? Math.round((row.production / production) * 1000) / 10 : 0,
        })),
        total: { amount: formatMoney(production), pct: 100 },
      },
      freshness: [
        {
          system: "SoftDent",
          status: hasSoftdentImport(bundle) ? "Imported" : "Missing",
          date: formatFreshness((bundle.softdent.dashboard && bundle.softdent.dashboard.modifiedAt) || ""),
          time: "",
          freq: "Export",
        },
        {
          system: "QuickBooks",
          status: hasQuickbooksImport(bundle) ? "Imported" : "Missing",
          date: formatFreshness(qb.modifiedAt),
          time: "",
          freq: "Export",
        },
      ],
      footer: {
        disclaimer: "Imported from local SoftDent and QuickBooks export files. HAL reads only; nothing is written back.",
        refreshed: formatFreshness(bundle.loadedAt),
      },
      ...(productionTrend && payerMix ? { quality } : {}),
    });
  }

  function mapClaimStatus(status) {
    const normalized = String(status || "").toLowerCase();
    if (normalized.includes("denied")) return "Denied";
    if (normalized.includes("paid") || normalized.includes("closed")) return "Ready";
    if (normalized.includes("review") || normalized.includes("pending")) return "Needs Review";
    return "Draft";
  }

  function buildCollectionsTrendFromRows(rows) {
    const periods = normalizeDashboardRows(rows || [])
      .filter((row) => row.period && !row.collectionsPending && row.collectionsReported !== false)
      .map((row) => ({
        period: row.period,
        collections: Number(row.collections) || 0,
      }))
      .filter((row) => row.collections > 0);
    if (!periods.length) {
      return { labels: [], current: [], prior: [] };
    }
    periods.sort((a, b) => a.period.localeCompare(b.period));
    const current = periods.map((row) => row.collections);
    return {
      labels: periods.map((row) => row.period),
      current,
      prior: current.length > 1 ? current.slice(0, -1) : [],
    };
  }

  function claimAgeDays(value) {
    const raw = String(value || "").trim();
    if (!raw || raw === "—") return null;
    const parsed = Date.parse(raw.length >= 10 ? raw.slice(0, 10) : raw);
    if (!Number.isFinite(parsed)) return null;
    return Math.max(0, Math.floor((Date.now() - parsed) / 86400000));
  }

  function buildTopClaimsFromImport(rows) {
    return (rows || [])
      .map((row) => {
        const dos = String(pickField(row, ["ServiceDate", "serviceDate", "DOS", "dos"]) || "—");
        const ageDays = pickField(row, ["Days", "days", "Age", "age"]);
        const parsedAge = coerceFloat(ageDays);
        const days = parsedAge != null ? String(parsedAge) : claimAgeDays(dos) != null ? String(claimAgeDays(dos)) : "—";
        return {
          claim: String(pickField(row, ["ClaimId", "claimId", "id"]) || ""),
          patient: String(pickField(row, ["PatientName", "patient"]) || "Unknown"),
          insurance: String(pickField(row, ["Payer", "payer", "Insurance", "insurance"]) || "—"),
          dos,
          billed: formatMoney(pickField(row, ["ClaimAmount", "amount", "Billed", "billed"])),
          outstanding: formatMoney(pickField(row, ["Outstanding", "outstanding", "Balance", "balance", "ClaimAmount", "amount"])),
          days,
          status: mapClaimStatus(pickField(row, ["ClaimStatus", "status"])),
        };
      })
      .filter((row) => row.claim)
      .slice(0, 10);
  }

  function buildFollowUpFromImport(rows) {
    const lanes = { "Needs Review": [], Denied: [], Draft: [] };
    (rows || []).forEach((row) => {
      const status = mapClaimStatus(pickField(row, ["ClaimStatus", "status"]));
      if (!lanes[status]) return;
      lanes[status].push({
        label: `${String(pickField(row, ["PatientName", "patient"]) || "Unknown")} · ${String(pickField(row, ["ClaimId", "claimId", "id"]) || "")}`,
        count: 1,
      });
    });
    return Object.entries(lanes)
      .filter(([, items]) => items.length > 0)
      .map(([status, items]) => ({
        status,
        count: items.length,
        tone: status === "Denied" ? "red" : status === "Needs Review" ? "warn" : "muted",
        items: items.slice(0, 5),
      }));
  }

  function mapAgingForAr(aging) {
    return (aging || []).map((entry) => ({
      label: entry.label || entry.bucket || "—",
      bucket: entry.bucket || entry.label || "—",
      amount: entry.amount,
      pct: entry.pct,
    }));
  }

  function mergeClaimsState(state, bundle) {
    const rows = ((bundle.softdent && bundle.softdent.claims) || {}).rows || [];
    if (!rows.length) return state;
    const lanes = { Draft: { count: 0, cards: [], more: 0 }, "Needs Review": { count: 0, cards: [], more: 0 }, Ready: { count: 0, cards: [], more: 0 }, Denied: { count: 0, cards: [], more: 0 } };
    rows.forEach((row) => {
      const lane = mapClaimStatus(pickField(row, ["ClaimStatus", "status"]));
      const card = {
        id: String(pickField(row, ["ClaimId", "claimId", "id"]) || ""),
        patient: String(pickField(row, ["PatientName", "patient"]) || "Unknown"),
        dob: "—",
        procedure: String(pickField(row, ["Procedure", "procedure"]) || "—"),
        amount: formatMoney(pickField(row, ["ClaimAmount", "amount"])),
        age: String(pickField(row, ["ServiceDate", "serviceDate"]) || "Imported"),
        tag: String(pickField(row, ["Payer", "payer"]) || lane),
        tagTone: lane === "Denied" ? "red" : lane === "Needs Review" ? "warn" : "ok",
      };
      lanes[lane].cards.push(card);
      lanes[lane].count += 1;
    });
    Object.values(lanes).forEach((lane) => {
      lane.more = Math.max(0, lane.count - lane.cards.length);
    });
    const total = rows.length;
    return Object.assign({}, state, {
      dataSource: "import",
      importedAt: bundle.loadedAt,
      claims: rows.map((row) => ({
        id: String(pickField(row, ["ClaimId", "claimId", "id"]) || ""),
        patient: String(pickField(row, ["PatientName", "patient"]) || "Unknown"),
        status: mapClaimStatus(pickField(row, ["ClaimStatus", "status"])),
        payer: String(pickField(row, ["Payer", "payer"]) || ""),
        amount: formatMoney(pickField(row, ["ClaimAmount", "amount"])),
        procedure: String(pickField(row, ["Procedure", "procedure"]) || ""),
        serviceDate: String(pickField(row, ["ServiceDate", "serviceDate"]) || ""),
        denialReason: String(pickField(row, ["DenialReason", "denialReason"]) || ""),
      })),
      laneTotals: Object.fromEntries(Object.entries(lanes).map(([key, lane]) => [key, lane.count])),
      kpis: [
        { label: "Total Claims", value: formatCount(total), trend: "Imported from SoftDent" },
        { label: "Denied", value: formatCount(lanes.Denied.count), trend: "Imported" },
        { label: "Needs Review", value: formatCount(lanes["Needs Review"].count), trend: "Imported" },
        { label: "Ready / Paid", value: formatCount(lanes.Ready.count), trend: "Imported" },
      ],
      lanes,
      claimsMode: "import-readonly",
      safety: "Import read-only · payer submission locked.",
    });
  }

  function sumFieldRows(rows, fieldNames) {
    return (rows || []).reduce((acc, row) => acc + (coerceFloat(pickField(row, fieldNames)) || 0), 0);
  }

  function buildPracticeDashboard(bundle) {
    const sd = (bundle && bundle.softdent) || {};
    const npRows = (sd.newPatients && sd.newPatients.rows) || [];
    const tpRows = (sd.treatmentPlans && sd.treatmentPlans.rows) || [];
    const caRows = (sd.caseAcceptance && sd.caseAcceptance.rows) || [];
    const hrRows = (sd.hygieneRecall && sd.hygieneRecall.rows) || [];
    const hasNp = npRows.length > 0;
    const hasTp = tpRows.length > 0;
    const hasCa = caRows.length > 0;
    const hasHr = hrRows.length > 0;
    const emptyPractice = {
      pageId: "practice",
      dataSource: "empty",
      configured: { newPatients: false, treatmentPlans: false, caseAcceptance: false, hygieneRecall: false },
      newPatients: { count: null, period: null, status: "Not Configured" },
      treatmentPlans: { presented: null, accepted: null, presentedValue: null, status: "Not Configured" },
      caseAcceptance: { rate: null, presented: null, accepted: null, status: "Not Configured" },
      hygieneRecall: { completed: null, due: null, period: null, status: "Not Configured" },
    };
    if (!hasNp && !hasTp && !hasCa && !hasHr) {
      return assignPatch(emptyDashboard("practice"), emptyPractice);
    }
    const npCount = hasNp
      ? coerceFloat(pickField(npRows[0], ["Count", "count", "NewPatients", "newPatients", "Total"])) || sumFieldRows(npRows, ["Count", "count", "NewPatients"])
      : null;
    const npPeriod = hasNp ? String(pickField(npRows[0], ["Period", "period", "Month", "month"]) || "—") : null;
    const presented = hasTp ? sumFieldRows(tpRows, ["Presented", "presented", "PlansPresented", "TxPresented"]) : null;
    const accepted = hasTp ? sumFieldRows(tpRows, ["Accepted", "accepted", "PlansAccepted", "TxAccepted"]) : null;
    const presentedValue = hasTp ? sumFieldRows(tpRows, ["Amount", "amount", "PresentedValue", "TotalAmount"]) : null;
    let caRate = hasCa ? pickField(caRows[0], ["AcceptanceRate", "acceptanceRate", "Rate", "rate"]) : null;
    let caPresented = hasCa ? coerceFloat(pickField(caRows[0], ["Presented", "presented", "PlansPresented"])) : null;
    let caAccepted = hasCa ? coerceFloat(pickField(caRows[0], ["Accepted", "accepted", "PlansAccepted"])) : null;
    if (!hasCa && presented > 0 && accepted != null) {
      caPresented = presented;
      caAccepted = accepted;
      caRate = `${((accepted / presented) * 100).toFixed(1)}%`;
    }
    const hrCompleted = hasHr
      ? sumFieldRows(hrRows, ["HygieneCompleted", "hygieneCompleted", "Completed", "completed"])
      : null;
    const hrDue = hasHr ? sumFieldRows(hrRows, ["RecallDue", "recallDue", "Due", "due", "Overdue"]) : null;
    const hrPeriod = hasHr ? String(pickField(hrRows[0], ["Period", "period", "Month", "month"]) || "—") : null;
    return assignPatch(emptyDashboard("practice"), {
      pageId: "practice",
      dataSource: "import",
      importedAt: bundle.loadedAt,
      configured: { newPatients: hasNp, treatmentPlans: hasTp, caseAcceptance: hasCa || Boolean(caRate), hygieneRecall: hasHr },
      newPatients: hasNp
        ? { count: npCount, period: npPeriod, status: "Connected" }
        : { count: null, period: null, status: "Not Configured" },
      treatmentPlans: hasTp
        ? {
            presented,
            accepted,
            presentedValue: formatMoney(presentedValue),
            status: "Connected",
          }
        : { presented: null, accepted: null, presentedValue: null, status: "Not Configured" },
      caseAcceptance:
        hasCa || caRate
          ? {
              rate: caRate,
              presented: caPresented,
              accepted: caAccepted,
              status: hasCa ? "Connected" : "Derived",
            }
          : { rate: null, presented: null, accepted: null, status: "Not Configured" },
      hygieneRecall: hasHr
        ? {
            completed: hrCompleted,
            due: hrDue,
            period: hrPeriod,
            status: "Connected",
          }
        : { completed: null, due: null, period: null, status: "Not Configured" },
    });
  }

  function documentImportSlug(value, limit) {
    const cleaned = String(value || "")
      .replace(/[^A-Za-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .toUpperCase();
    return (cleaned || "ROW").slice(0, limit || 32);
  }

  function documentImportDate(period, fallback) {
    const raw = String(period || "").trim();
    if (/^\d{4}-\d{2}$/.test(raw)) return `${raw}-01`;
    if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) return raw;
    return fallback || new Date().toISOString().slice(0, 10);
  }

  function buildDocumentStateFromImportBundle(bundle) {
    const qb = (bundle && bundle.quickbooks) || {};
    const sd = (bundle && bundle.softdent) || {};
    const today = new Date().toISOString().slice(0, 10);
    const queue = [];
    const previewById = {};
    const counts = { quickbooks: 0, softdent: 0 };

    function addEntry(doc, preview) {
      queue.push(doc);
      previewById[doc.id] = preview;
    }

    (((qb.expenses || {}).rows) || []).forEach((row) => {
      const period = String(pickField(row, ["Period", "period", "Month", "month"]) || "unknown");
      const amount = coerceFloat(pickField(row, ["TotalExpense", "Amount", "amount", "total"]));
      const sourceFile = String((qb.expenses || {}).sourceFile || "quickbooks_expenses.csv");
      const docId = `QB-EXP-${documentImportSlug(period)}`;
      addEntry(
        {
          id: docId,
          type: "Statement",
          vendor: "QuickBooks Operating Expenses",
          date: documentImportDate(period, today),
          amount: formatMoney(amount),
          status: "Ready to Post",
          statusTone: "ok",
          age: 0,
          autoImported: true,
          sourceSystem: "quickbooks",
          sourceFile,
          sourceKind: "monthlyExpenses",
        },
        {
          vendor: "QUICKBOOKS OPERATING EXPENSES",
          invoice: docId,
          date: documentImportDate(period, today),
          total: formatMoney(amount),
          file: sourceFile,
          pages: "Import row",
          uploaded: today,
          textPreview: `QuickBooks monthly expense total · period ${period}`,
          sourceExpired: false,
          fileUnavailable: "Source export row — no PDF attached.",
          previewAvailable: false,
        },
      );
      counts.quickbooks += 1;
    });

    (((qb.revenue || {}).rows) || []).forEach((row) => {
      const period = String(pickField(row, ["Period", "period", "Month", "month"]) || "unknown");
      const amount = coerceFloat(pickField(row, ["TotalIncome", "Revenue", "Amount", "amount", "total"]));
      const sourceFile = String((qb.revenue || {}).sourceFile || "quickbooks_revenue.csv");
      const docId = `QB-REV-${documentImportSlug(period)}`;
      addEntry(
        {
          id: docId,
          type: "Statement",
          vendor: "QuickBooks Revenue",
          date: documentImportDate(period, today),
          amount: formatMoney(amount),
          status: "Ready to Post",
          statusTone: "ok",
          age: 0,
          autoImported: true,
          sourceSystem: "quickbooks",
          sourceFile,
          sourceKind: "monthlyRevenue",
        },
        {
          vendor: "QUICKBOOKS REVENUE",
          invoice: docId,
          date: documentImportDate(period, today),
          total: formatMoney(amount),
          file: sourceFile,
          pages: "Import row",
          uploaded: today,
          textPreview: `QuickBooks monthly revenue total · period ${period}`,
          sourceExpired: false,
          fileUnavailable: "Source export row — no PDF attached.",
          previewAvailable: false,
        },
      );
      counts.quickbooks += 1;
    });

    (((sd.ar || {}).rows) || []).forEach((row) => {
      const bucket = String(pickField(row, ["Bucket", "bucket", "AgingBucket", "Range"]) || "Total");
      const amount = coerceFloat(pickField(row, ["Balance", "Amount", "amount", "total"]));
      const sourceFile = String((sd.ar || {}).sourceFile || "softdent_ar_aging.csv");
      const docId = `SD-AR-${documentImportSlug(bucket)}`;
      addEntry(
        {
          id: docId,
          type: "A/R Aging",
          vendor: `SoftDent A/R · ${bucket}`,
          date: today,
          amount: formatMoney(amount),
          status: "Ready to Post",
          statusTone: "ok",
          age: 0,
          autoImported: true,
          sourceSystem: "softdent",
          sourceFile,
          sourceKind: "arAging",
        },
        {
          vendor: `SOFTDENT A/R · ${bucket}`.toUpperCase(),
          invoice: docId,
          date: today,
          total: formatMoney(amount),
          file: sourceFile,
          pages: "Import row",
          uploaded: today,
          textPreview: `SoftDent A/R aging bucket · ${bucket}`,
          sourceExpired: false,
          fileUnavailable: "Source export row — no PDF attached.",
          previewAvailable: false,
        },
      );
      counts.softdent += 1;
    });

    (((sd.dashboard || {}).rows) || []).slice(0, 12).forEach((row) => {
      const period = String(pickField(row, ["period", "Period", "Month", "month"]) || "current");
      const production = coerceFloat(pickField(row, ["production", "Production"]));
      const collections = coerceFloat(pickField(row, ["collections", "Collections"]));
      const provider = String(pickField(row, ["provider", "Provider", "providerName"]) || "New Ridge Family Dental");
      const sourceFile = String((sd.dashboard || {}).sourceFile || "softdent_dashboard_data.json");
      const docId = `SD-DASH-${documentImportSlug(period)}`;
      addEntry(
        {
          id: docId,
          type: "Production Summary",
          vendor: provider,
          date: documentImportDate(period, today),
          amount: formatMoney(production != null ? production : collections),
          status: "Ready to Post",
          statusTone: "ok",
          age: 0,
          autoImported: true,
          sourceSystem: "softdent",
          sourceFile,
          sourceKind: "dashboard",
        },
        {
          vendor: provider.toUpperCase(),
          invoice: docId,
          date: documentImportDate(period, today),
          total: formatMoney(production != null ? production : collections),
          file: sourceFile,
          pages: "Import row",
          uploaded: today,
          textPreview: `SoftDent dashboard import · production ${formatMoney(production)} · collections ${formatMoney(collections)}`,
          sourceExpired: false,
          fileUnavailable: "Source export row — no PDF attached.",
          previewAvailable: false,
        },
      );
      counts.softdent += 1;
    });

    return {
      importedAt: (bundle && bundle.loadedAt) || new Date().toISOString(),
      queue,
      previewById,
      counts,
      warnings: counts.quickbooks || counts.softdent ? [] : ["No SoftDent or QuickBooks rows found in the import cache for document intake."],
    };
  }

  function buildDashboard(pageId, bundle) {
    const empty = emptyDashboard(pageId);
    if (pageId === "practice") return buildPracticeDashboard(bundle || {});
    if (!bundle || !hasImportData(bundle)) return empty;
    const softdent = buildSoftdentDashboard(bundle);
    const quickbooks = buildQuickbooksDashboard(bundle);
    if (pageId === "softdent") return softdent || empty;
    if (pageId === "quickbooks") {
      return quickbooks || assignPatch(empty, { dataSource: "empty", syncStatus: "Awaiting QuickBooks export" });
    }
    if (pageId === "financial") return buildFinancialDashboard(bundle, softdent, quickbooks) || empty;
    if (pageId === "ar") {
      if (softdent && softdent.hero && softdent.hero.value !== "—") {
        const aging = mapAgingForAr(softdent.aging || []);
        const claimRows = ((bundle.softdent && bundle.softdent.claims) || {}).rows || [];
        const dashboardRows = ((bundle.softdent && bundle.softdent.dashboard) || {}).rows || [];
        const topClaims = buildTopClaimsFromImport(claimRows);
        const followUp = buildFollowUpFromImport(claimRows);
        const collectionsTrend = buildCollectionsTrendFromRows(dashboardRows);
        const collectionsMtd = softdent.collections;
        const ninetyPlus = aging.find((a) => /^\s*(90\+|90\s*\+)/i.test(String(a.bucket || a.label || "")));
        const ninetyPlusPct = ninetyPlus && ninetyPlus.pct != null ? `${ninetyPlus.pct}%` : "—";
        return assignPatch(emptyDashboard("ar"), {
          pageId: "ar",
          dataSource: "import",
          importedAt: bundle.loadedAt,
          total: softdent.hero.value,
          buckets: aging,
          aging,
          topClaims,
          followUp,
          collectionsTrend,
          collectionsTrendEmpty: collectionsTrend.current.length
            ? null
            : "Awaiting collections trend export.",
          topClaimsEmpty: topClaims.length
            ? null
            : "Awaiting SoftDent claims export for outstanding claim detail.",
          followUpEmpty: followUp.length ? null : "Awaiting SoftDent claims export for follow-up lanes.",
          kpis: [
            { label: "Total Outstanding", value: softdent.hero.value, tone: "gold" },
            { label: "vs. Prior 30 Days", value: "Imported", tone: "muted" },
            { label: "90+ Days %", value: ninetyPlusPct, tone: "warn" },
            {
              label: "Collections MTD",
              value: formatMoney(collectionsMtd),
              tone: collectionsMtd > 0 ? "green" : "muted",
            },
          ],
        });
      }
      return empty;
    }
    return empty;
  }

  function formatImportStatus(bundle) {
    if (!bundle) return "No import bundle loaded.";
    const diagApi = diagnosticsApi();
    const diagnostics = bundle.diagnostics || (diagApi ? diagApi.evaluateBundle(bundle) : null);
    const lines = [`Import bundle loaded ${formatFreshness(bundle.loadedAt)}.`];
    if (bundle.importMode) {
      lines.push(`Import mode: ${bundle.importMode}.`);
    }
    const sync = bundle.syncStatus || {};
    if (sync.attempted) {
      lines.push(`Sync: ${sync.ok ? "OK" : "FAILED"}${sync.error ? ` (${sync.error})` : ""}`);
    }
    if (diagnostics && diagnostics.summary) {
      const summary = diagnostics.summary;
      lines.push(
        `Dataset health: ${summary.connected} connected, ${summary.partial} partial, ${summary.stale} stale, ${summary.missing} missing, ${summary.notConfigured} not configured.`,
      );
      if (diagApi && typeof diagApi.formatDatasetLines === "function") {
        lines.push("", "Dataset diagnostics:");
        diagApi.formatDatasetLines(diagnostics).forEach((line) => lines.push(`  ${line.replace(/^- /, "")}`));
      }
    }
    const sd = bundle.softdent || {};
    const qb = bundle.quickbooks || {};
    lines.push(
      `SoftDent dir: ${sd.dir || "—"}`,
      `  dashboard: ${sd.dashboard ? `${sd.dashboard.sourceFile} (${(sd.dashboard.rows || []).length} rows)` : "missing"}`,
      `  claims: ${sd.claims ? `${sd.claims.sourceFile} (${(sd.claims.rows || []).length} rows)` : "missing — awaiting SoftDent claims export"}`,
      `  clinical notes: ${sd.clinicalNotes ? `${sd.clinicalNotes.sourceFile} (${(sd.clinicalNotes.rows || []).length} rows)` : "missing — awaiting SoftDent clinical notes export"}`,
      `  ar: ${sd.ar ? `${sd.ar.sourceFile} (${(sd.ar.rows || []).length} rows)` : "missing"}`,
      `QuickBooks dir: ${qb.dir || "—"}`,
      `  revenue: ${qb.revenue ? `${qb.revenue.sourceFile} (${(qb.revenue.rows || []).length} rows)` : "missing"}`,
      `  profit and loss: ${qb.profitAndLoss ? `${qb.profitAndLoss.sourceFile} (${(qb.profitAndLoss.rows || []).length} rows)` : "missing"}`,
      `  expenses: ${qb.expenses ? `${qb.expenses.sourceFile} (${(qb.expenses.rows || []).length} rows)` : "missing"}`,
      `  expense categories: ${qb.expenseCategories ? `${qb.expenseCategories.sourceFile} (${(qb.expenseCategories.rows || []).length} rows)` : "missing"}`,
      `  ar: ${qb.ar ? `${qb.ar.sourceFile} (${(qb.ar.rows || []).length} rows)` : "missing — run SDK summary sync or drop quickbooks_ar.csv"}`,
      "",
      "HAL reads SoftDent and QuickBooks only. Nothing is posted or written back.",
    );
    if (bundle.upstreamHealth && bundle.upstreamHealth.systems) {
      lines.push("", "Upstream automation:");
      Object.keys(bundle.upstreamHealth.systems).forEach((system) => {
        const report = bundle.upstreamHealth.systems[system];
        lines.push(`  ${system}: ${report.configuredRootCount || 0} export root(s) configured`);
        (report.datasets || []).forEach((item) => {
          if (item.stale) {
            lines.push(`    - ${item.datasetKey}: upstream stale${item.collectorHint ? ` (${item.collectorHint})` : ""}`);
          }
        });
      });
    }
    if (sync.attempted && !sync.ok && sync.error) {
      lines.push("", `Last sync error: ${sync.error}`);
    }
    const syncResult = sync.result || {};
    if (Array.isArray(syncResult.warnings) && syncResult.warnings.length) {
      lines.push("", "Sync warnings:");
      syncResult.warnings.forEach((warning) => lines.push(`  - ${warning}`));
    }
    const runtime = typeof globalThis !== "undefined" ? globalThis.RuntimeIssues : typeof RuntimeIssues !== "undefined" ? RuntimeIssues : null;
    if (runtime) {
      const importIssues = runtime.list().filter((item) => /import|sync|manifest/i.test(item.source));
      if (importIssues.length) {
        lines.push("", "Runtime import issues:");
        importIssues.slice(0, 5).forEach((item) => lines.push(`  - ${item.source}: ${item.message}`));
      }
    }
    return lines.join("\n");
  }

  return {
    shouldLoadImports,
    PRIMARY_PROVIDER,
    loadBundle,
    readCsvRows,
    parseCsvRfc,
    hasImportData,
    hasSoftdentImport,
    hasQuickbooksImport,
    buildDashboard,
    buildDocumentStateFromImportBundle,
    emptyDashboard,
    mergeClaimsState,
    formatImportStatus,
    attachBundleDiagnostics,
    normalizePeriodKey,
    latestQuickbooksPeriod,
    resolveComparablePeriod,
    resolveDashboardPeriodContext,
    comparePeriodAlignment,
    buildCollectionRateMetrics,
    compareArCrossSource,
    softdentArTotal,
    quickbooksArTotal,
    assessCollectionHealth,
    resolveCollectionHealth,
    scopeExpenseCategoryRows,
    buildFinancialDataQuality,
    quickbooksTotals,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = ImportLoader;
}
if (typeof window !== "undefined") {
  window.ImportLoader = ImportLoader;
}
