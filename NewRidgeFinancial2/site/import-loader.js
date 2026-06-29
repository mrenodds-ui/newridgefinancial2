/**
 * SoftDent / QuickBooks import loader for NewRidgeFinancial 2.0.
 * Reads canonical export files and maps them into dashboard shapes HAL already uses.
 * Browser + Node compatible.
 */
const ImportLoader = (function () {
  const PRIMARY_PROVIDER = "Dr. Michael Reno";
  const isNode = typeof window === "undefined";
  const REPO_IMPORT_SOFTDENT = isNode
    ? require("node:path").join(__dirname, "..", "..", "app", "data", "imports", "softdent")
    : null;
  const REPO_IMPORT_QUICKBOOKS = isNode
    ? require("node:path").join(__dirname, "..", "..", "app", "data", "imports", "quickbooks")
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
  const MANIFEST_QB_EXPENSE_NAMES = manifestFilenames("quickbooks.expenses", QB_EXPENSE_NAMES);
  const MANIFEST_QB_EXPENSE_CATEGORY_NAMES = manifestFilenames("quickbooks.expenseCategories", QB_EXPENSE_CATEGORY_NAMES);
  const MANIFEST_QB_AR_NAMES = manifestFilenames("quickbooks.ar", QB_AR_NAMES);
  const MANIFEST_SOFTDENT_NEW_PATIENTS_NAMES = manifestFilenames("softdent.newPatients", SOFTDENT_NEW_PATIENTS_NAMES);
  const MANIFEST_SOFTDENT_TREATMENT_PLANS_NAMES = manifestFilenames("softdent.treatmentPlans", SOFTDENT_TREATMENT_PLANS_NAMES);
  const MANIFEST_SOFTDENT_CASE_ACCEPTANCE_NAMES = manifestFilenames("softdent.caseAcceptance", SOFTDENT_CASE_ACCEPTANCE_NAMES);

  function bridge() {
    if (typeof DesktopBridge !== "undefined") return DesktopBridge;
    if (typeof window !== "undefined" && window.DesktopBridge) return window.DesktopBridge;
    return null;
  }

  function shouldLoadImports() {
    if (bridge() && bridge().hasDesktopApi && bridge().hasDesktopApi()) return true;
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
      const hasTrend = Array.isArray(patch.productionTrend?.production) && patch.productionTrend.production.length > 1;
      const hasPayer = Array.isArray(patch.payerMix?.slices) && patch.payerMix.slices.length > 0;
      const hasQuality = patch.quality && patch.quality.score > 0;
      if (!hasTrend || !hasPayer || !hasQuality) return "partial";
      return "complete";
    }
    if (pageId === "quickbooks") {
      const hasCategories = Array.isArray(patch.expenseCategories?.slices) && patch.expenseCategories.slices.length > 0;
      const hasMonthly = Array.isArray(patch.monthlyExpenses) && patch.monthlyExpenses.length > 0;
      if (!hasCategories && !hasMonthly) return "partial";
      return "complete";
    }
    if (pageId === "softdent") {
      const hasCollections = Number(patch.collections || 0) > 0;
      const claimsOk = (patch.health || []).some((h) => /claims/i.test(String(h.label || "")) && h.ok);
      if (!hasCollections || !claimsOk) return "partial";
      return "complete";
    }
    if (pageId === "ar") {
      const hasTrend = Array.isArray(patch.collectionsTrend?.current) && patch.collectionsTrend.current.length > 0;
      const hasTopClaims = Array.isArray(patch.topClaims) && patch.topClaims.length > 0;
      if (!hasTrend || !hasTopClaims) return "partial";
      return "complete";
    }
    return "complete";
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

  function readTabularFile(path, fs) {
    const raw = fs.readFileSync(path, "utf8");
    if (path.toLowerCase().endsWith(".json")) return extractJsonRows(JSON.parse(raw));
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
      },
      quickbooks: {
        dir: REPO_IMPORT_QUICKBOOKS,
        revenue: loadDatasetNode(REPO_IMPORT_QUICKBOOKS, MANIFEST_QB_REVENUE_NAMES, fs),
        expenses: loadDatasetNode(REPO_IMPORT_QUICKBOOKS, MANIFEST_QB_EXPENSE_NAMES, fs),
        expenseCategories: loadDatasetNode(REPO_IMPORT_QUICKBOOKS, MANIFEST_QB_EXPENSE_CATEGORY_NAMES, fs),
        ar: loadDatasetNode(REPO_IMPORT_QUICKBOOKS, MANIFEST_QB_AR_NAMES, fs),
      },
    });
  }

  // Browser file:// without pywebview returns null — use the desktop bridge or Node (NR2_LOAD_IMPORTS=1).
  async function loadBundle(force) {
    const br = bridge();
    let bundle = null;
    if (br) {
      if (force && br.refreshImports) bundle = await br.refreshImports();
      else if (br.getImportBundle) bundle = await br.getImportBundle();
    }
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
    return (rows || []).map((row, index) => ({
      provider: String(row.provider || row.Provider || row.providerName || row.ProviderName || PRIMARY_PROVIDER).trim() || PRIMARY_PROVIDER,
      period: String(row.period || row.Period || ""),
      production: coerceFloat(row.production || row.Production) || 0,
      collections: coerceFloat(row.collections || row.Collections) || 0,
      insurance: coerceFloat(row.insurance || row.Insurance) || 0,
      patient: coerceFloat(row.patient || row.Patient) || 0,
    }));
  }

  function aggregateDashboard(rows) {
    const totals = rows.reduce(
      (acc, row) => {
        acc.production += row.production;
        acc.collections += row.collections;
        acc.insurance += row.insurance;
        acc.patient += row.patient;
        return acc;
      },
      { production: 0, collections: 0, insurance: 0, patient: 0 },
    );
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
      byProvider[provider].collections += row.collections;
      byProvider[provider].insurance += row.insurance;
      byProvider[provider].patient += row.patient;
    });
    const providerRows = Object.values(byProvider).sort((a, b) => b.production - a.production);
    return { totals, period, rows: providerRows };
  }

  function pickField(row, names) {
    for (const name of names) {
      if (row[name] !== undefined && row[name] !== "") return row[name];
      const match = Object.keys(row).find((key) => key.toLowerCase() === name.toLowerCase());
      if (match && row[match] !== undefined && row[match] !== "") return row[match];
    }
    return null;
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

  function buildProductionTrendFromRows(rows) {
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
    return {
      yLabels: [`$${Math.round(yStep / 1000)}k`, `$${Math.round((yStep * 2) / 1000)}k`],
      labels: periods.map((row) => row.period),
      production,
      average,
      ytd: [
        { label: "YTD Production", value: formatMoney(production.reduce((acc, value) => acc + value, 0)) },
        {
          label: "YTD Collection Rate",
          value: (() => {
            const prod = production.reduce((acc, value) => acc + value, 0);
            const coll = periods.reduce((acc, row) => acc + row.collections, 0);
            return prod > 0 ? `${((coll / prod) * 100).toFixed(1)}%` : "—";
          })(),
        },
      ],
    };
  }

  function buildPayerMixFromAggregate(aggregate) {
    const insurance = aggregate.totals.insurance || 0;
    const patient = aggregate.totals.patient || 0;
    const total = insurance + patient;
    if (total <= 0) return null;
    const production = aggregate.totals.production || 0;
    const collections = aggregate.totals.collections || 0;
    return {
      total: formatMoney(total),
      rate: production > 0 ? `${((collections / production) * 100).toFixed(1)}%` : "—",
      rateTrend: "Imported",
      slices: [
        { label: "Insurance", pct: Math.round((insurance / total) * 1000) / 10 },
        { label: "Patient", pct: Math.round((patient / total) * 1000) / 10 },
      ].filter((slice) => slice.pct > 0),
    };
  }

  function buildMonthlyExpensesFromRows(rows) {
    const monthly = (rows || [])
      .map((row) => ({
        label: String(pickField(row, ["Month", "month", "Period", "period", "Date", "date"]) || "").trim(),
        amount: coerceFloat(pickField(row, ["Amount", "amount", "TotalExpense", "Expenses", "Expense"])),
      }))
      .filter((row) => row.label && row.amount !== null);
    if (monthly.length < 2) return null;
    monthly.sort((a, b) => a.label.localeCompare(b.label));
    return {
      labels: monthly.map((row) => row.label),
      values: monthly.map((row) => row.amount),
    };
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

  function quickbooksTotals(bundle) {
    const revenueRows = ((bundle.quickbooks && bundle.quickbooks.revenue) || {}).rows || [];
    const expenseRows = ((bundle.quickbooks && bundle.quickbooks.expenses) || {}).rows || [];
    const totalFromRows = (rows, totalFields, amountFields) => {
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
    const netIncome = revenue !== null && expenses !== null ? revenue - expenses : null;
    const modifiedAt =
      (bundle.quickbooks.revenue && bundle.quickbooks.revenue.modifiedAt) ||
      (bundle.quickbooks.expenses && bundle.quickbooks.expenses.modifiedAt) ||
      bundle.loadedAt;
    return { revenue, expenses, netIncome, modifiedAt, revenueRows, expenseRows };
  }

  function buildSoftdentDashboard(bundle) {
    if (!hasSoftdentImport(bundle)) return null;
    const sd = bundle.softdent || {};
    const dashboardRows = normalizeDashboardRows((sd.dashboard && sd.dashboard.rows) || []);
    const aggregate = aggregateDashboard(dashboardRows);
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
      { label: "Import Period", value: aggregate.period || "—" },
      { label: "Claims Rows", value: formatCount(((sd.claims && sd.claims.rows) || []).length) },
      { label: "Clinical Notes", value: formatCount(((sd.clinicalNotes && sd.clinicalNotes.rows) || []).length) },
      { label: "Production MTD", value: formatMoney(aggregate.totals.production) },
      { label: "Collections MTD", value: formatMoney(aggregate.totals.collections) },
    ];

    const patch = {
      dataSource: "import",
      importedAt: modifiedAt,
      date: aggregate.period || new Date(modifiedAt).toLocaleDateString(),
      source: "SoftDent",
      status: "Connected",
      production: aggregate.totals.production,
      collections: aggregate.totals.collections,
      hero: hasAr
        ? {
            label: "DAYSHEET A/R",
            value: formatMoney(arTotal),
            subtitle: "Total A/R (imported)",
            trend: "Imported",
            trendDir: "up",
            spark: [arTotal * 0.8, arTotal * 0.9, arTotal],
          }
        : {
            label: "DAYSHEET A/R",
            value: "—",
            subtitle: "Awaiting verified SoftDent A/R export",
            trend: "Import only",
            trendDir: "down",
            spark: [1, 1, 1],
          },
      subMetrics: [
            { label: "Production", value: formatMoney(aggregate.totals.production) },
            { label: "Collections", value: formatMoney(aggregate.totals.collections) },
            { label: "Insurance", value: formatMoney(aggregate.totals.insurance) },
            { label: "Patient", value: formatMoney(aggregate.totals.patient) },
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
        ...(aggregate.totals.production > 0 && aggregate.totals.collections === 0
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
      { category: "Revenue", amount: formatMoney(totals.revenue), change: "Imported", changeTone: "up" },
      { category: "Operating Expenses", amount: formatMoney(totals.expenses), change: "Imported", changeTone: "down" },
      {
        category: "Net Income",
        amount: formatMoney(totals.netIncome),
        change: "Imported",
        changeTone: "up",
        sub: margin,
        highlight: true,
      },
    ];
    const categoryRows = ((bundle.quickbooks && bundle.quickbooks.expenseCategories) || {}).rows || [];
    const expenseCategories = categoryRows
      .map((row) => ({
        label: String(pickField(row, ["Category", "category"]) || ""),
        amount: formatMoney(pickField(row, ["Amount", "amount"])),
        pct: 0,
      }))
      .filter((row) => row.label);
    const categoryTotal = categoryRows.reduce((acc, row) => acc + (coerceFloat(pickField(row, ["Amount", "amount"])) || 0), 0);
    expenseCategories.forEach((row) => {
      const amt = coerceFloat(row.amount);
      row.pct = categoryTotal && amt !== null ? Math.round((amt / categoryTotal) * 1000) / 10 : 0;
    });
    const donutColors = ["#d6b15e", "#64748b", "#94a3b8", "#cbd5e1", "#e2e8f0"];
    const expenseCategoryDonut = expenseCategories.length
      ? {
          total: formatMoney(categoryTotal || totals.expenses),
          slices: expenseCategories.map((row, index) => ({
            label: row.label,
            pct: row.pct,
            color: donutColors[index % donutColors.length],
          })),
        }
      : undefined;
    const monthlyExpenses = buildMonthlyExpensesFromRows(totals.expenseRows);
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
      ...(expenseCategoryDonut ? { expenseCategories: expenseCategoryDonut } : {}),
      ...(monthlyExpenses ? { monthlyExpenses } : {}),
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
    const dashboardRows = normalizeDashboardRows(((bundle.softdent && bundle.softdent.dashboard) || {}).rows || []);
    const aggregate = aggregateDashboard(dashboardRows);
    const qb = quickbooksTotals(bundle);
    const production = aggregate.totals.production || null;
    const collections = aggregate.totals.collections || null;
    const collectionRate = production && collections !== null ? `${((collections / production) * 100).toFixed(1)}%` : "—";
    const productionTrend = buildProductionTrendFromRows(dashboardRows);
    const payerMix = buildPayerMixFromAggregate(aggregate);
    return assignPatch(emptyDashboard("financial"), {
      pageId: "financial",
      dataSource: "import",
      importedAt: bundle.loadedAt,
      dateRange: aggregate.period ? `Period ${aggregate.period}` : `Imported ${formatFreshness(bundle.loadedAt)}`,
      productionMtd: {
        label: "Production MTD",
        value: formatMoney(production),
        trend: "Imported",
        trendDir: "up",
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
          value: formatMoney(collections),
          tone: "green",
          trend: "Imported",
          trendDir: "up",
          vs: "SoftDent import",
          subLabel: "Collection Rate",
          subValue: collectionRate,
          subTrend: "Imported",
          subTrendDir: "up",
        },
        {
          label: "QuickBooks Revenue",
          value: formatMoney(qb.revenue),
          tone: "blue",
          trend: "Imported",
          trendDir: "up",
          vs: quickbooks ? `QuickBooks import · ${formatFreshness(quickbooks.importedAt)}` : "QuickBooks import",
        },
        {
          label: "QuickBooks Net Income",
          value: formatMoney(qb.netIncome),
          tone: "purple",
          trend: "Imported",
          trendDir: "up",
          vs: "QuickBooks import",
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
    });
  }

  function mapClaimStatus(status) {
    const normalized = String(status || "").toLowerCase();
    if (normalized.includes("denied")) return "Denied";
    if (normalized.includes("paid") || normalized.includes("closed")) return "Ready";
    if (normalized.includes("review") || normalized.includes("pending")) return "Needs Review";
    return "Draft";
  }

  function buildTopClaimsFromImport(rows) {
    return (rows || [])
      .map((row) => ({
        claim: String(pickField(row, ["ClaimId", "claimId", "id"]) || ""),
        patient: String(pickField(row, ["PatientName", "patient"]) || "Unknown"),
        insurance: String(pickField(row, ["Payer", "payer", "Insurance", "insurance"]) || "—"),
        dos: String(pickField(row, ["ServiceDate", "serviceDate", "DOS", "dos"]) || "—"),
        billed: formatMoney(pickField(row, ["ClaimAmount", "amount", "Billed", "billed"])),
        outstanding: formatMoney(pickField(row, ["Outstanding", "outstanding", "Balance", "balance", "ClaimAmount", "amount"])),
        days: String(pickField(row, ["Days", "days", "Age", "age"]) || "—"),
        status: mapClaimStatus(pickField(row, ["ClaimStatus", "status"])),
      }))
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
    const hasNp = npRows.length > 0;
    const hasTp = tpRows.length > 0;
    const hasCa = caRows.length > 0;
    const emptyPractice = {
      pageId: "practice",
      dataSource: "empty",
      configured: { newPatients: false, treatmentPlans: false, caseAcceptance: false },
      newPatients: { count: null, period: null, status: "Not Configured" },
      treatmentPlans: { presented: null, accepted: null, presentedValue: null, status: "Not Configured" },
      caseAcceptance: { rate: null, presented: null, accepted: null, status: "Not Configured" },
    };
    if (!hasNp && !hasTp && !hasCa) {
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
    return assignPatch(emptyDashboard("practice"), {
      pageId: "practice",
      dataSource: "import",
      importedAt: bundle.loadedAt,
      configured: { newPatients: hasNp, treatmentPlans: hasTp, caseAcceptance: hasCa || Boolean(caRate) },
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
    });
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
        const topClaims = buildTopClaimsFromImport(claimRows);
        const followUp = buildFollowUpFromImport(claimRows);
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
          collectionsTrend: { labels: [], current: [], prior: [] },
          collectionsTrendEmpty: "Awaiting collections trend export.",
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
      `  expenses: ${qb.expenses ? `${qb.expenses.sourceFile} (${(qb.expenses.rows || []).length} rows)` : "missing"}`,
      `  expense categories: ${qb.expenseCategories ? `${qb.expenseCategories.sourceFile} (${(qb.expenseCategories.rows || []).length} rows)` : "missing"}`,
      `  ar: ${qb.ar ? `${qb.ar.sourceFile} (${(qb.ar.rows || []).length} rows)` : "not configured — no automated QuickBooks A/R collector"}`,
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
    emptyDashboard,
    mergeClaimsState,
    formatImportStatus,
    attachBundleDiagnostics,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = ImportLoader;
}
if (typeof window !== "undefined") {
  window.ImportLoader = ImportLoader;
}
