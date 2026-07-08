/**
 * QuickBooks extended reports (browser) — mirrors nr2_qb_reports.py.
 */
const NR2QbReports = (function () {
  function parseMoney(value) {
    const raw = String(value == null ? "" : value)
      .replace(/[$,]/g, "")
      .trim();
    if (!raw || raw === "—" || raw === "-") return 0;
    const n = Number(raw);
    return Number.isFinite(n) ? n : 0;
  }

  function bundleFromSnapshot(snapshot) {
    return (snapshot && snapshot.importBundle) || null;
  }

  function qbSection(snapshot) {
    const bundle = bundleFromSnapshot(snapshot);
    return (bundle && bundle.quickbooks) || {};
  }

  function probeFromSnapshot(snapshot) {
    const bundle = bundleFromSnapshot(snapshot);
    const diag = bundle && bundle.diagnostics;
    if (diag && diag.quickbooksProbe) return diag.quickbooksProbe;
    return null;
  }

  function monthlyRows(snapshot) {
    const qb = qbSection(snapshot);
    const rows = [];
    ["profitAndLoss", "revenue"].forEach((key) => {
      const chunk = qb[key];
      if (chunk && Array.isArray(chunk.rows)) rows.push.apply(rows, chunk.rows);
    });
    const byPeriod = {};
    rows.forEach((row) => {
      const period = String(row.Period || row.period || "").trim();
      const income = parseMoney(row.TotalIncome || row.income_total || row.revenue);
      const expense = parseMoney(row.TotalExpense || row.expense_total || row.expenses);
      if (!period || income <= 0) return;
      byPeriod[period] = {
        Period: period,
        TotalIncome: income,
        TotalExpense: expense,
        NetIncome: parseMoney(row.NetIncome) || income - expense,
      };
    });
    return Object.keys(byPeriod)
      .sort()
      .map((key) => byPeriod[key]);
  }

  function balanceSheetSummary(snapshot) {
    const monthly = monthlyRows(snapshot);
    const qb = qbSection(snapshot);
    let arTotal = 0;
    const arRows = (qb.ar && qb.ar.rows) || [];
    arRows.forEach((row) => {
      arTotal += parseMoney(row.Balance || row.balance || row.Amount);
    });
    const income = monthly.length ? monthly[monthly.length - 1].TotalIncome : parseMoney(qb.revenue);
    const expenses = monthly.length ? monthly[monthly.length - 1].TotalExpense : parseMoney(qb.expenses);
    const assets = [];
    if (arTotal > 0) assets.push({ label: "Accounts Receivable", amount: Math.round(arTotal) });
    const cashProxy = Math.max(0, income - expenses);
    if (cashProxy > 0) assets.push({ label: "Cash & Deposits (proxy)", amount: Math.round(cashProxy) });
    return {
      hasData: assets.length > 0,
      assets,
      liabilities: [],
      equity: income || expenses ? Math.round(income - expenses) : null,
    };
  }

  function cashFlowTrend(snapshot) {
    const monthly = monthlyRows(snapshot).slice(-12);
    return {
      hasData: monthly.length > 0,
      labels: monthly.map((row) => row.Period),
      inflows: monthly.map((row) => row.TotalIncome),
      outflows: monthly.map((row) => row.TotalExpense),
      net: monthly.map((row) => row.NetIncome),
    };
  }

  function netIncomeSummary(snapshot) {
    const monthly = monthlyRows(snapshot);
    const ytd = monthly.reduce((acc, row) => acc + (row.NetIncome || 0), 0);
    const latest = monthly.length ? monthly[monthly.length - 1] : null;
    return {
      hasData: monthly.length > 0,
      ytdNetIncome: Math.round(ytd),
      latestMonth: latest ? latest.Period : null,
      latestNetIncome: latest ? Math.round(latest.NetIncome) : null,
      monthCount: monthly.length,
    };
  }

  function revenueByService(snapshot) {
    const qb = qbSection(snapshot);
    const slices = [];
    const categories = qb.expenseCategories;
    if (categories && Array.isArray(categories.slices)) {
      categories.slices.forEach((row) => {
        const amount = parseMoney(row.amount || row.Amount || row.pct);
        if (amount > 0) slices.push({ label: row.label || row.Category || "Category", amount });
      });
    }
    const income = parseMoney(qb.revenue);
    if (!slices.length && income > 0) {
      slices.push({ label: "Clinical Production (proxy)", amount: income });
    }
    const total = slices.reduce((acc, row) => acc + row.amount, 0);
    slices.forEach((row) => {
      row.pct = total > 0 ? Math.round((row.amount / total) * 1000) / 10 : 0;
    });
    return { hasData: slices.length > 0, slices: slices.slice(0, 8), total: Math.round(total) };
  }

  function arAging(snapshot) {
    const qb = qbSection(snapshot);
    const buckets = [];
    const arRows = (qb.ar && qb.ar.rows) || [];
    arRows.forEach((row) => {
      buckets.push({
        bucket: String(row.Bucket || row.bucket || ""),
        balance: parseMoney(row.Balance || row.balance),
      });
    });
    const total = buckets.reduce((acc, row) => acc + row.balance, 0);
    return { hasData: buckets.length > 0, buckets, total: Math.round(total) };
  }

  return {
    balanceSheetSummary,
    cashFlowTrend,
    netIncomeSummary,
    revenueByService,
    arAging,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = NR2QbReports;
}
if (typeof globalThis !== "undefined") {
  globalThis.NR2QbReports = NR2QbReports;
}
if (typeof window !== "undefined") {
  window.NR2QbReports = NR2QbReports;
}
