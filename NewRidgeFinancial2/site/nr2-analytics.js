/**
 * NR2 cross-analytics (browser) — mirrors nr2_analytics.py using program snapshot / import bundle.
 */
const NR2Analytics = (function () {
  function parseMoney(value) {
    const raw = String(value == null ? "" : value)
      .replace(/[$,]/g, "")
      .trim();
    if (!raw || raw === "—" || raw === "-") return 0;
    const n = Number(raw);
    return Number.isFinite(n) ? n : 0;
  }

  function normalizePeriod(raw) {
    const text = String(raw || "").trim();
    if (!text) return "";
    const iso = text.match(/^(\d{4})-(\d{2})/);
    if (iso) return `${iso[1]}-${iso[2]}`;
    const ym = text.match(/^(\d{4})[-/](\d{1,2})$/);
    if (ym) return `${ym[1]}-${String(ym[2]).padStart(2, "0")}`;
    return text.slice(0, 7);
  }

  function pickField(row, names) {
    if (!row) return null;
    for (let i = 0; i < names.length; i++) {
      const val = row[names[i]];
      if (val != null && val !== "") return val;
    }
    return null;
  }

  function bundleFromSnapshot(snapshot) {
    return (snapshot && snapshot.importBundle) || null;
  }

  function dashboardRows(snapshot) {
    const fin = snapshot && snapshot.dashboards && snapshot.dashboards.financial;
    if (fin && fin.productionTrend && Array.isArray(fin.productionTrend.labels) && fin.productionTrend.labels.length) {
      const labels = fin.productionTrend.labels;
      const production = fin.productionTrend.production || [];
      return labels.map((period, i) => ({
        period: normalizePeriod(period),
        production: parseMoney(production[i]),
        collections: 0,
      }));
    }
    const bundle = bundleFromSnapshot(snapshot);
    const dashboard = bundle && bundle.softdent && bundle.softdent.dashboard;
    let rows = [];
    if (Array.isArray(dashboard)) rows = dashboard;
    else if (dashboard && Array.isArray(dashboard.rows)) rows = dashboard.rows;
    return rows
      .map((row) => ({
        period: normalizePeriod(pickField(row, ["period", "Period", "year_month"])),
        production: parseMoney(pickField(row, ["production", "Production"])),
        collections: parseMoney(pickField(row, ["collections", "Collections"])),
      }))
      .filter((row) => row.period)
      .sort((a, b) => a.period.localeCompare(b.period));
  }

  function qbMonthlyRows(snapshot) {
    const bundle = bundleFromSnapshot(snapshot);
    if (!bundle || !bundle.quickbooks) return [];
    const plRows = ((bundle.quickbooks.profitAndLoss || {}).rows || []).concat((bundle.quickbooks.revenue || {}).rows || []);
    const byPeriod = {};
    plRows.forEach((row) => {
      const period = normalizePeriod(pickField(row, ["Period", "period", "Month", "month"]));
      const income = parseMoney(pickField(row, ["TotalIncome", "Income", "Revenue", "total_income", "Amount"]));
      if (!period || income <= 0) return;
      byPeriod[period] = { period, revenue: income };
    });
    return Object.keys(byPeriod)
      .sort()
      .map((key) => byPeriod[key]);
  }

  function arWeightedDso(snapshot) {
    const bundle = bundleFromSnapshot(snapshot);
    const arRows = (bundle && bundle.softdent && bundle.softdent.ar && bundle.softdent.ar.rows) || [];
    const mids = { "0-30": 15, "31-60": 45, "61-90": 75, "90+": 105 };
    let weighted = 0;
    let total = 0;
    arRows.forEach((row) => {
      const amount = parseMoney(pickField(row, ["Balance", "Outstanding", "Amount", "Total"]));
      if (amount <= 0) return;
      const bucket = String(pickField(row, ["Aging", "Bucket", "AgeBucket", "bucket"]) || "");
      let days = null;
      Object.keys(mids).forEach((key) => {
        if (bucket.indexOf(key) >= 0) days = mids[key];
      });
      if (days == null) days = 45;
      weighted += amount * days;
      total += amount;
    });
    return total > 0 ? Math.round((weighted / total) * 10) / 10 : null;
  }

  function productionReconciliation(snapshot) {
    const sdRows = dashboardRows(snapshot);
    const qbRows = qbMonthlyRows(snapshot);
    const qbBy = {};
    qbRows.forEach((row) => {
      qbBy[row.period] = row.revenue;
    });
    const rows = sdRows
      .map((sd) => {
        const qbRevenue = qbBy[sd.period];
        let variancePct = null;
        let tone = "neutral";
        if (sd.production > 0 && qbRevenue != null) {
          variancePct = Math.round(((qbRevenue - sd.production) / sd.production) * 1000) / 10;
          const abs = Math.abs(variancePct);
          tone = abs <= 3 ? "ok" : abs <= 10 ? "warn" : "alert";
        }
        return {
          period: sd.period,
          softdentProduction: sd.production,
          quickbooksRevenue: qbRevenue != null ? qbRevenue : null,
          variancePct,
          tone,
        };
      })
      .filter((row) => row.softdentProduction > 0 || row.quickbooksRevenue != null);
    const latest = rows.length ? rows[rows.length - 1] : null;
    return {
      rows: rows.slice(-12),
      latest,
      hasData: rows.length > 0,
      summary: latest && latest.variancePct != null ? `Latest ${latest.period}: ${latest.variancePct}% variance` : "",
    };
  }

  function collectionLag(snapshot) {
    const dso = arWeightedDso(snapshot);
    let avg = dso;
    if (avg == null) {
      const sdRows = dashboardRows(snapshot);
      const latest = sdRows.length ? sdRows[sdRows.length - 1] : null;
      if (latest && latest.production > 0 && latest.collections > 0) {
        avg = Math.round(Math.max(0, Math.min(90, 30 * (1 - Math.min(1, latest.collections / latest.production)))) * 10) / 10;
      }
    }
    return {
      avgLagDays: avg,
      dsoProxy: dso != null,
      hasData: avg != null,
      summary: avg != null ? `Collection lag (DSO proxy): ${avg} days` : "",
    };
  }

  function quickbooksMonthlyRevenue(snapshot) {
    const rows = qbMonthlyRows(snapshot).slice(-12);
    return {
      labels: rows.map((row) => row.period),
      values: rows.map((row) => row.revenue),
      hasData: rows.length > 0,
    };
  }

  function softdentProductionDaily(snapshot) {
    const rows = dashboardRows(snapshot).slice(-30);
    return {
      granularity: rows.length ? "monthly" : "none",
      points: rows.map((row) => ({ date: row.period, production: row.production })),
      hasData: rows.length > 0,
    };
  }

  function kpiRibbon(snapshot) {
    const recon = productionReconciliation(snapshot);
    const lag = collectionLag(snapshot);
    const revenue = quickbooksMonthlyRevenue(snapshot);
    const daily = softdentProductionDaily(snapshot);
    const tiles = [];
    if (recon.latest && recon.latest.variancePct != null) {
      tiles.push({
        label: "Prod vs QB variance",
        value: `${recon.latest.variancePct}%`,
        tone: recon.latest.tone,
        widgetKey: "nr2ProductionReconciliation",
      });
    }
    if (lag.avgLagDays != null) {
      tiles.push({
        label: "Collection lag (DSO)",
        value: `${lag.avgLagDays}d`,
        tone: lag.avgLagDays > 45 ? "warn" : "ok",
        widgetKey: "nr2CollectionLag",
      });
    }
    if (revenue.values && revenue.values.length) {
      tiles.push({
        label: "QB revenue (latest month)",
        value: `$${Math.round(revenue.values[revenue.values.length - 1]).toLocaleString()}`,
        tone: "neutral",
        widgetKey: "quickbooksMonthlyRevenue",
      });
    }
    if (daily.points && daily.points.length) {
      const last = daily.points[daily.points.length - 1];
      tiles.push({
        label: "SoftDent production (latest)",
        value: `$${Math.round(last.production).toLocaleString()}`,
        tone: "neutral",
        widgetKey: "softdentProductionDaily",
      });
    }
    return { tiles: tiles.slice(0, 6), hasData: tiles.length > 0 };
  }

  return {
    productionReconciliation,
    collectionLag,
    quickbooksMonthlyRevenue,
    softdentProductionDaily,
    kpiRibbon,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = NR2Analytics;
}
if (typeof globalThis !== "undefined") {
  globalThis.NR2Analytics = NR2Analytics;
}
if (typeof window !== "undefined") {
  window.NR2Analytics = NR2Analytics;
}
