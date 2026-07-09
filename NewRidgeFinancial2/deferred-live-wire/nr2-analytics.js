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

  function currentMonthPeriod() {
    const now = new Date();
    return `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, "0")}`;
  }

  function dashboardRows(snapshot) {
    const fin = snapshot && snapshot.dashboards && snapshot.dashboards.financial;
    const pendingPeriod = fin && fin.collectionsPending
      ? normalizePeriod(
          (fin.periodAlignment && fin.periodAlignment.comparablePeriod) ||
            fin.comparablePeriod ||
            (fin.collectionRateMetrics && fin.collectionRateMetrics.latestMonthPeriod) ||
            "",
        )
      : "";
    if (fin && fin.productionTrend && Array.isArray(fin.productionTrend.labels) && fin.productionTrend.labels.length) {
      const labels = fin.productionTrend.labels;
      const production = fin.productionTrend.production || [];
      const collectionsSeries = fin.productionTrend.collections || [];
      return labels.map((period, i) => {
        const key = normalizePeriod(period);
        return {
          period: key,
          production: parseMoney(production[i]),
          collections: parseMoney(collectionsSeries[i]),
          collectionsPending: Boolean(pendingPeriod && key === pendingPeriod),
        };
      });
    }
    const bundle = bundleFromSnapshot(snapshot);
    const dashboard = bundle && bundle.softdent && bundle.softdent.dashboard;
    let rows = [];
    if (Array.isArray(dashboard)) rows = dashboard;
    else if (dashboard && Array.isArray(dashboard.rows)) rows = dashboard.rows;
    return rows
      .map((row) => {
        const period = normalizePeriod(pickField(row, ["period", "Period", "year_month"]));
        const collectionsPending =
          row.collectionsPending === true ||
          row.CollectionsPending === true ||
          Boolean(pendingPeriod && period === pendingPeriod);
        const collectionsReported =
          !collectionsPending &&
          row.collectionsReported !== false &&
          row.CollectionsReported !== false;
        return {
          period,
          production: parseMoney(pickField(row, ["production", "Production"])),
          collections: collectionsReported
            ? parseMoney(pickField(row, ["collections", "Collections"]))
            : 0,
          collectionsPending,
          collectionsReported,
        };
      })
      .filter((row) => row.period)
      .sort((a, b) => a.period.localeCompare(b.period));
  }

  function periodIncomplete(row) {
    if (!row) return false;
    if (row.collectionsPending) return true;
    if (row.collectionsReported === false) return true;
    // Current calendar month with production but no reported collections is still open.
    if (row.period === currentMonthPeriod() && row.production > 0 && !(row.collections > 0)) return true;
    return false;
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
        const incomplete = periodIncomplete(sd);
        let variancePct = null;
        let tone = "neutral";
        if (sd.production > 0 && qbRevenue != null) {
          variancePct = Math.round(((qbRevenue - sd.production) / sd.production) * 1000) / 10;
          const abs = Math.abs(variancePct);
          // Incomplete months (collections export pending) are informational — cash-basis
          // deposits lag production by design until SoftDent closes the month.
          tone = incomplete ? "neutral" : abs <= 3 ? "ok" : abs <= 10 ? "warn" : "alert";
        }
        return {
          period: sd.period,
          softdentProduction: sd.production,
          quickbooksRevenue: qbRevenue != null ? qbRevenue : null,
          variancePct,
          tone,
          incomplete,
          collectionsPending: Boolean(sd.collectionsPending),
        };
      })
      .filter((row) => row.softdentProduction > 0 || row.quickbooksRevenue != null);
    const latest = rows.length ? rows[rows.length - 1] : null;
    const latestComplete = [...rows].reverse().find((row) => !row.incomplete && row.variancePct != null) || null;
    const review = latest && latest.incomplete && latestComplete ? latestComplete : latest;
    return {
      rows: rows.slice(-12),
      latest,
      latestComplete,
      review,
      hasData: rows.length > 0,
      summary:
        latest && latest.incomplete
          ? `Current period ${latest.period} still open (collections export pending); review ${review && review.period ? review.period : "prior"} variance when available.`
          : latest && latest.variancePct != null
            ? `Latest ${latest.period}: ${latest.variancePct}% variance`
            : "",
    };
  }

  function collectionLag(snapshot) {
    const dso = arWeightedDso(snapshot);
    if (dso != null) {
      return {
        avgLagDays: dso,
        dsoProxy: true,
        priorPeriodProxy: false,
        period: null,
        incompleteCurrent: false,
        hasData: true,
        caption: "",
        summary: `Collection lag (A/R weighted DSO): ${dso} days`,
      };
    }
    const sdRows = dashboardRows(snapshot);
    const latest = sdRows.length ? sdRows[sdRows.length - 1] : null;
    const incompleteCurrent = Boolean(latest && periodIncomplete(latest));
    // Open months (collections export pending) blank the latest row — use last complete month.
    const complete =
      [...sdRows]
        .reverse()
        .find((row) => !periodIncomplete(row) && row.production > 0 && row.collections > 0) || null;
    let avg = null;
    let period = null;
    if (complete) {
      avg =
        Math.round(
          Math.max(0, Math.min(90, 30 * (1 - Math.min(1, complete.collections / complete.production)))) * 10,
        ) / 10;
      period = complete.period;
    }
    const priorPeriodProxy = Boolean(incompleteCurrent && period && latest && period !== latest.period);
    let summary = "";
    let caption = "";
    if (avg != null) {
      if (priorPeriodProxy) {
        summary = `Collection lag proxy from ${period}: ${avg} days (current month collections export pending).`;
        caption = `Proxy from ${period} · ${latest.period} export pending`;
      } else {
        summary = `Collection lag (monthly proxy): ${avg} days`;
        caption = period ? `From ${period}` : "";
      }
    }
    return {
      avgLagDays: avg,
      dsoProxy: false,
      priorPeriodProxy,
      period,
      incompleteCurrent,
      hasData: avg != null,
      caption,
      summary,
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

  function qbDepositsForPeriod(snapshot, period) {
    const bundle = bundleFromSnapshot(snapshot);
    const qb = (bundle && bundle.quickbooks) || {};
    const summary = qb.depositsSummary || qb.deposits_summary;
    if (summary) {
      const dep = parseMoney(summary.totalDeposits || summary.total_deposits);
      if (dep > 0) return { amount: dep, source: "quickbooks.depositsSummary" };
    }
    const probe =
      (typeof NR2QbReports !== "undefined" && NR2QbReports.probeFromSnapshot
        ? NR2QbReports.probeFromSnapshot(snapshot)
        : null) || {};
    const dep = parseMoney(probe.total_deposits || probe.deposits_total || probe.bank_deposits);
    if (dep > 0) return { amount: dep, source: "quickbooksProbe" };
    const byPeriod = probe.deposits_by_period || probe.monthly_deposits;
    if (Array.isArray(byPeriod) && byPeriod.length) {
      const match = byPeriod.find((row) => normalizePeriod(row.period || row.Period) === period) || byPeriod[byPeriod.length - 1];
      const amount = parseMoney(match && (match.amount || match.total || match.Deposits));
      if (amount > 0) return { amount, source: "quickbooksProbe.period" };
    }
    const payments = parseMoney(probe.payments_received || probe.total_payments_received);
    if (payments > 0) return { amount: payments, source: "quickbooksProbe.payments" };
    return { amount: 0, source: "" };
  }

  function collectionDepositVariance(snapshot) {
    const sdRows = dashboardRows(snapshot);
    if (!sdRows.length) {
      return {
        hasData: false,
        variancePct: null,
        summary: "Collection vs deposit variance populates when SoftDent dashboard and QuickBooks deposit exports share a period.",
      };
    }
    const latest = sdRows[sdRows.length - 1];
    const collections = latest.collections || 0;
    const dep = qbDepositsForPeriod(snapshot, latest.period);
    if (collections <= 0 || !dep.amount) {
      return { hasData: false, period: latest.period, variancePct: null, summary: "" };
    }
    const variancePct = Math.round(((dep.amount - collections) / collections) * 1000) / 10;
    const threshold =
      typeof window !== "undefined" && window.NR2_DEPOSIT_VARIANCE_THRESHOLD_PCT
        ? parseMoney(window.NR2_DEPOSIT_VARIANCE_THRESHOLD_PCT)
        : 8;
    const tone = Math.abs(variancePct) <= threshold ? "ok" : Math.abs(variancePct) <= threshold * 1.5 ? "warn" : "alert";
    return {
      hasData: true,
      period: latest.period,
      softdentCollections: collections,
      quickbooksDeposits: dep.amount,
      variancePct,
      thresholdPct: threshold,
      tone,
      source: dep.source,
      summary: `${latest.period}: QuickBooks deposits are ${variancePct > 0 ? "+" : ""}${variancePct}% vs SoftDent collections.`,
    };
  }

  function kpiRibbon(snapshot) {
    const recon = productionReconciliation(snapshot);
    const lag = collectionLag(snapshot);
    const revenue = quickbooksMonthlyRevenue(snapshot);
    const daily = softdentProductionDaily(snapshot);
    const tiles = [];
    const varianceRow = recon.review || recon.latest;
    if (varianceRow && varianceRow.variancePct != null) {
      tiles.push({
        label: varianceRow.incomplete ? "Prod vs QB (open month)" : "Prod vs QB variance",
        value: `${varianceRow.variancePct}%`,
        tone: varianceRow.tone,
        widgetKey: "nr2ProductionReconciliation",
      });
    }
    if (lag.avgLagDays != null) {
      tiles.push({
        label: lag.priorPeriodProxy ? `Collection lag (${lag.period})` : "Collection lag (DSO)",
        value: `${lag.avgLagDays}d`,
        tone: lag.avgLagDays > 45 ? "warn" : "ok",
        widgetKey: "nr2CollectionLag",
        hint: lag.caption || "",
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
    const sdRows = dashboardRows(snapshot);
    const qbRows = qbMonthlyRows(snapshot);
    if (sdRows.length && qbRows.length) {
      const latestSd = sdRows[sdRows.length - 1];
      const qbMatch = qbRows.find((row) => row.period === latestSd.period) || qbRows[qbRows.length - 1];
      if (latestSd.collections > 0 && qbMatch.revenue > 0) {
        const variancePct = Math.round(((qbMatch.revenue - latestSd.collections) / latestSd.collections) * 1000) / 10;
        const tone = Math.abs(variancePct) <= 5 ? "ok" : Math.abs(variancePct) <= 12 ? "warn" : "alert";
        tiles.push({
          label: "Collections vs QB",
          value: `${variancePct > 0 ? "+" : ""}${variancePct}%`,
          tone,
          widgetKey: "nr2CollectionLag",
        });
      }
    }
    const depVar = collectionDepositVariance(snapshot);
    if (depVar.hasData && depVar.variancePct != null) {
      tiles.push({
        label: "Collections vs deposits",
        value: `${depVar.variancePct > 0 ? "+" : ""}${depVar.variancePct}%`,
        tone: depVar.tone || "neutral",
        widgetKey: "nr2ProductionReconciliation",
      });
    }
    return { tiles: tiles.slice(0, 6), hasData: tiles.length > 0 };
  }

  function goalScorecard(snapshot) {
    const sdRows = dashboardRows(snapshot);
    const ytdProd = sdRows.reduce((sum, row) => sum + (row.production || 0), 0);
    let target = 0;
    if (typeof window !== "undefined" && window.NR2_GOAL_PRODUCTION_YTD) {
      target = parseMoney(window.NR2_GOAL_PRODUCTION_YTD);
    }
    if (target <= 0 && ytdProd > 0) target = Math.round(ytdProd * 1.05);
    const pct = target > 0 ? Math.round((ytdProd / target) * 1000) / 10 : null;
    const tone = pct == null ? "neutral" : pct >= 95 ? "ok" : pct >= 80 ? "warn" : "alert";
    return { ytdProduction: ytdProd, targetProduction: target || null, pctOfGoal: pct, tone, hasData: ytdProd > 0 };
  }

  function alertTicker(snapshot) {
    const alerts = [];
    const recon = productionReconciliation(snapshot);
    const latest = recon.latest || {};
    const review = recon.review || latest;
    if (latest.incomplete) {
      alerts.push({
        level: "info",
        text: `SoftDent collections export pending for ${latest.period || "current month"} — production vs QuickBooks variance is informational until month close`,
        widgetKey: "softdentCollectionsDaily",
      });
      if (review && !review.incomplete && review.variancePct != null && Math.abs(review.variancePct) > 10) {
        alerts.push({
          level: "warn",
          text: `Production vs QuickBooks variance ${review.variancePct}% (${review.period})`,
          widgetKey: "nr2ProductionReconciliation",
        });
      }
    } else if (latest.variancePct != null && Math.abs(latest.variancePct) > 10) {
      alerts.push({
        level: "warn",
        text: `Production vs QuickBooks variance ${latest.variancePct}% (${latest.period || "latest"})`,
        widgetKey: "nr2ProductionReconciliation",
      });
    }
    const lag = collectionLag(snapshot);
    if (lag.priorPeriodProxy && lag.period) {
      alerts.push({
        level: "info",
        text: `Collection lag proxy from ${lag.period} (${lag.avgLagDays}d) — current month SoftDent collections export still pending`,
        widgetKey: "nr2CollectionLag",
      });
    } else if (lag.avgLagDays != null && lag.avgLagDays > 45) {
      alerts.push({
        level: "warn",
        text: `Collection lag ${lag.avgLagDays} days exceeds 45-day review threshold`,
        widgetKey: "nr2CollectionLag",
      });
    }
    const depVar = collectionDepositVariance(snapshot);
    if (depVar.hasData && depVar.variancePct != null && Math.abs(depVar.variancePct) > (depVar.thresholdPct || 8)) {
      alerts.push({
        level: Math.abs(depVar.variancePct) > (depVar.thresholdPct || 8) * 1.5 ? "alert" : "warn",
        text: `Collections vs QB deposits variance ${depVar.variancePct}% (${depVar.period || "latest"})`,
        widgetKey: "nr2ProductionReconciliation",
      });
    }
    if (!alerts.length) {
      alerts.push({
        level: "ok",
        text: "Cross-analytics within normal review thresholds for imported snapshot",
        widgetKey: "nr2KpiRibbon",
      });
    }
    return { items: alerts.slice(0, 8), hasData: true };
  }

  function providerCompensation(snapshot) {
    const fin = snapshot && snapshot.dashboards && snapshot.dashboards.financial;
    const rows = (fin && fin.providers && fin.providers.rows) || [];
    const mapped = (Array.isArray(rows) ? rows : []).slice(0, 8).map((row) => ({
      name: String(row.name || row.provider || "Provider"),
      production: parseMoney(row.production || row.amount),
    }));
    const total = mapped.reduce((sum, row) => sum + row.production, 0);
    return {
      providers: mapped.map((row) => ({
        name: row.name,
        production: row.production,
        pct: total > 0 ? Math.round((row.production / total) * 1000) / 10 : 0,
      })),
      totalProduction: total,
      hasData: mapped.length > 0,
    };
  }

  function monthlyTrendCombo(snapshot) {
    const sdRows = dashboardRows(snapshot);
    const qbRows = qbMonthlyRows(snapshot);
    const qbBy = {};
    qbRows.forEach((row) => {
      qbBy[row.period] = row.revenue;
    });
    const periods = Array.from(new Set(sdRows.map((row) => row.period).concat(Object.keys(qbBy)))).sort().slice(-12);
    return {
      labels: periods,
      production: periods.map((period) => {
        const row = sdRows.find((item) => item.period === period);
        return row ? row.production : 0;
      }),
      collections: periods.map((period) => {
        const row = sdRows.find((item) => item.period === period);
        return row ? row.collections : 0;
      }),
      revenue: periods.map((period) => qbBy[period] || 0),
      hasData: periods.length > 0,
    };
  }

  return {
    productionReconciliation,
    collectionLag,
    quickbooksMonthlyRevenue,
    softdentProductionDaily,
    kpiRibbon,
    collectionDepositVariance,
    goalScorecard,
    alertTicker,
    providerCompensation,
    monthlyTrendCombo,
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
