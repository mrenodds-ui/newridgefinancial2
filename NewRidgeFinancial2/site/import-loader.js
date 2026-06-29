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
      const hasPayer = Array.isArray(patch.payerMix?.segments) && patch.payerMix.segments.length > 0;
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
      const hasTrend = Array.isArray(patch.collectionsTrend?.values) && patch.collectionsTrend.values.length > 0;
      const hasTopClaims = Array.isArray(patch.topClaims) && patch.topClaims.length > 0;
      if (!hasTrend || !hasTopClaims) return "partial";
      return "complete";
    }
    return "complete";
  }

  function readCsvRows(text) {
    const lines = String(text || "")
      .replace(/\r\n/g, "\n")
      .split("\n")
      .filter((line) => line.trim());
    if (!lines.length) return [];
    const headers = lines[0].split(",").map((h) => h.trim());
    return lines.slice(1).map((line) => {
      const cells = line.split(",");
      const row = {};
      headers.forEach((header, index) => {
        row[header] = (cells[index] || "").trim();
      });
      return row;
    });
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
    return readCsvRows(raw);
  }

  function firstExisting(dir, names, fs) {
    for (const name of names) {
      const candidate = require("node:path").join(dir, name);
      if (fs.existsSync(candidate)) return candidate;
    }
    return null;
  }

  function loadDatasetNode(dir, names, fs) {
    if (!dir || !fs.existsSync(dir)) return null;
    const path = firstExisting(dir, names, fs);
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
    return {
      loadedAt: new Date().toISOString(),
      softdent: {
        dir: REPO_IMPORT_SOFTDENT,
        dashboard: loadDatasetNode(REPO_IMPORT_SOFTDENT, SOFTDENT_DASHBOARD_NAMES, fs),
        claims: loadDatasetNode(REPO_IMPORT_SOFTDENT, SOFTDENT_CLAIMS_NAMES, fs),
        clinicalNotes: loadDatasetNode(REPO_IMPORT_SOFTDENT, SOFTDENT_CLINICAL_NAMES, fs),
        ar: loadDatasetNode(REPO_IMPORT_SOFTDENT, SOFTDENT_AR_NAMES, fs),
      },
      quickbooks: {
        dir: REPO_IMPORT_QUICKBOOKS,
        revenue: loadDatasetNode(REPO_IMPORT_QUICKBOOKS, QB_REVENUE_NAMES, fs),
        expenses: loadDatasetNode(REPO_IMPORT_QUICKBOOKS, QB_EXPENSE_NAMES, fs),
        expenseCategories: loadDatasetNode(REPO_IMPORT_QUICKBOOKS, QB_EXPENSE_CATEGORY_NAMES, fs),
        ar: loadDatasetNode(REPO_IMPORT_QUICKBOOKS, QB_AR_NAMES, fs),
      },
    };
  }

  async function loadBundle(force) {
    const br = bridge();
    if (br) {
      if (force && br.refreshImports) return br.refreshImports();
      if (br.getImportBundle) return br.getImportBundle();
    }
    if (isNode && process.env.NR2_LOAD_IMPORTS === "1") return loadBundleNode();
    return null;
  }

  function hasSoftdentImport(bundle) {
    const sd = bundle && bundle.softdent;
    return Boolean(
      (sd && sd.dashboard && sd.dashboard.rows && sd.dashboard.rows.length) ||
        (sd && sd.claims && sd.claims.rows && sd.claims.rows.length),
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
        { label: "Claims Export", value: sd.claims ? sd.claims.sourceFile : "Missing", ok: Boolean(sd.claims && sd.claims.rows && sd.claims.rows.length) },
        { label: "A/R Export", value: hasAr ? sd.ar.sourceFile : "Not loaded", ok: hasAr },
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
    return assignPatch(emptyDashboard("quickbooks"), {
      pageId: "quickbooks",
      dataSource: "import",
      importedAt: totals.modifiedAt,
      syncStatus: "Connected",
      lastSync: formatFreshness(totals.modifiedAt),
      revenue: totals.revenue,
      expenses: totals.expenses,
      ...(expenseCategoryDonut ? { expenseCategories: expenseCategoryDonut } : {}),
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
    const aggregate = aggregateDashboard(normalizeDashboardRows(((bundle.softdent && bundle.softdent.dashboard) || {}).rows || []));
    const qb = quickbooksTotals(bundle);
    const production = aggregate.totals.production || null;
    const collections = aggregate.totals.collections || null;
    const collectionRate = production && collections !== null ? `${((collections / production) * 100).toFixed(1)}%` : "—";
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
        chart: { yLabels: ["$0", "$50k", "$100k"], xLabels: ["Import"], values: [production || 0] },
      },
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

  function buildDashboard(pageId, bundle) {
    const empty = emptyDashboard(pageId);
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
        const aging = softdent.aging || [];
        const total = coerceFloat(softdent.hero.value);
        const ninetyPlus = aging.find((a) => /^\s*(90\+|90\s*\+)/i.test(String(a.bucket || "")));
        const ninetyPlusPct = ninetyPlus && ninetyPlus.pct != null ? `${ninetyPlus.pct}%` : "—";
        return assignPatch(emptyDashboard("ar"), {
          pageId: "ar",
          dataSource: "import",
          importedAt: bundle.loadedAt,
          total: softdent.hero.value,
          buckets: aging,
          aging,
          kpis: [
            { label: "Total Outstanding", value: softdent.hero.value, tone: "gold" },
            { label: "vs. Prior 30 Days", value: "Imported", tone: "muted" },
            { label: "90+ Days %", value: ninetyPlusPct, tone: "warn" },
            { label: "Collections This 30 Days", value: formatMoney(((softdent.collections || 0) * 30) / 30), tone: "green" },
          ],
        });
      }
      return empty;
    }
    return empty;
  }

  function formatImportStatus(bundle) {
    if (!bundle) return "No import bundle loaded.";
    const lines = [`Import bundle loaded ${formatFreshness(bundle.loadedAt)}.`];
    const sync = bundle.syncStatus || {};
    if (sync.attempted) {
      lines.push(`Sync: ${sync.ok ? "OK" : "FAILED"}${sync.error ? ` (${sync.error})` : ""}`);
    }
    const sd = bundle.softdent || {};
    const qb = bundle.quickbooks || {};
    lines.push(
      `SoftDent dir: ${sd.dir || "—"}`,
      `  dashboard: ${sd.dashboard ? `${sd.dashboard.sourceFile} (${(sd.dashboard.rows || []).length} rows)` : "missing"}`,
      `  claims: ${sd.claims ? `${sd.claims.sourceFile} (${(sd.claims.rows || []).length} rows)` : "missing"}`,
      `  clinical notes: ${sd.clinicalNotes ? `${sd.clinicalNotes.sourceFile} (${(sd.clinicalNotes.rows || []).length} rows)` : "missing"}`,
      `  ar: ${sd.ar ? `${sd.ar.sourceFile} (${(sd.ar.rows || []).length} rows)` : "missing"}`,
      `QuickBooks dir: ${qb.dir || "—"}`,
      `  revenue: ${qb.revenue ? `${qb.revenue.sourceFile} (${(qb.revenue.rows || []).length} rows)` : "missing"}`,
      `  expenses: ${qb.expenses ? `${qb.expenses.sourceFile} (${(qb.expenses.rows || []).length} rows)` : "missing"}`,
      `  ar: ${qb.ar ? `${qb.ar.sourceFile} (${(qb.ar.rows || []).length} rows)` : "missing"}`,
      "",
      "HAL reads SoftDent and QuickBooks only. Nothing is posted or written back.",
    );
    if (sync.attempted && !sync.ok && sync.error) {
      lines.push("", `Last sync error: ${sync.error}`);
    }
    return lines.join("\n");
  }

  return {
    shouldLoadImports,
    PRIMARY_PROVIDER,
    loadBundle,
    hasImportData,
    hasSoftdentImport,
    hasQuickbooksImport,
    buildDashboard,
    emptyDashboard,
    mergeClaimsState,
    formatImportStatus,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = ImportLoader;
}
if (typeof window !== "undefined") {
  window.ImportLoader = ImportLoader;
}
