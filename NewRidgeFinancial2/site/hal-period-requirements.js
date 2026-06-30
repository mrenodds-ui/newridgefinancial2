/* global globalThis, window */
(function initHalPeriodRequirements(root) {
  "use strict";

  function relevantPeriodLabels(reference) {
    const now = reference || new Date();
    const current = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
    let y = now.getFullYear();
    let m = now.getMonth();
    if (m === 0) {
      m = 12;
      y -= 1;
    }
    const prior = `${y}-${String(m).padStart(2, "0")}`;
    return [current, prior];
  }

  function periodsFromRows(rows, fieldNames) {
    const found = new Set();
    (rows || []).forEach((row) => {
      if (!row || typeof row !== "object") return;
      fieldNames.forEach((name) => {
        const raw = row[name];
        if (raw) found.add(String(raw).trim().slice(0, 7));
      });
    });
    return Array.from(found).sort();
  }

  const WIDGET_PERIOD_RULES = {
    financialProductionTrend: {
      label: "Production Trend & YTD",
      needs: "current + prior calendar month in SoftDent dashboard",
      datasets: ["softdent.dashboard"],
    },
    financialPayerMix: {
      label: "Payer Mix & Collections",
      needs: "current + prior month SoftDent dashboard with collections/payer fields",
      datasets: ["softdent.dashboard"],
    },
    practiceFinancialOverview: {
      label: "Practice Financial Overview",
      needs: "current month QuickBooks revenue + SoftDent dashboard",
      datasets: ["quickbooks.revenue", "softdent.dashboard"],
    },
    quickbooksPlDetail: {
      label: "QuickBooks P&L Detail",
      needs: "current month QuickBooks revenue and expenses",
      datasets: ["quickbooks.revenue", "quickbooks.expenses"],
    },
    periodCloseAndPosting: {
      label: "Period Close & Posting",
      needs: "active document queue period (from document dates, not import CSV)",
      datasets: ["local.documents"],
    },
    claimsPipeline: {
      label: "Claims Pipeline",
      needs: "claim service dates (not monthly period labels)",
      datasets: ["softdent.claims"],
    },
  };

  function analyzeWidgetPeriods(snapshot) {
    const bundle = (snapshot && snapshot.importBundle) || {};
    const required = relevantPeriodLabels();
    const sd = bundle.softdent || {};
    const qb = bundle.quickbooks || {};
    const loaded = {
      "softdent.dashboard": periodsFromRows((sd.dashboard && sd.dashboard.rows) || [], ["period", "Period"]),
      "quickbooks.revenue": periodsFromRows((qb.revenue && qb.revenue.rows) || [], ["Period", "period"]),
      "quickbooks.expenses": periodsFromRows((qb.expenses && qb.expenses.rows) || [], ["Period", "period"]),
    };
    const widgets = Object.entries(WIDGET_PERIOD_RULES).map(([widgetKey, rule]) => {
      const datasetKeys = rule.datasets || [];
      let ok = true;
      let missing = [];
      if (datasetKeys.includes("local.documents")) {
        ok = Boolean(snapshot && snapshot.documents && snapshot.documents.queueCount);
      } else if (datasetKeys.includes("softdent.claims")) {
        ok = Boolean((sd.claims && sd.claims.rows && sd.claims.rows.length) || (snapshot && snapshot.claims && snapshot.claims.total));
        if (!ok) missing = ["claims export rows"];
      } else {
        datasetKeys.forEach((ds) => {
          const have = new Set(loaded[ds] || []);
          required.forEach((period) => {
            if (!have.has(period)) missing.push(`${ds} missing ${period}`);
          });
        });
        ok = missing.length === 0;
      }
      return {
        widgetKey,
        label: rule.label,
        requirement: rule.needs,
        ok,
        missing,
        loadedPeriods: Object.fromEntries(datasetKeys.filter((ds) => loaded[ds]).map((ds) => [ds, loaded[ds]])),
      };
    });
    return {
      requiredPeriods: required,
      loadedPeriods: loaded,
      widgets,
      policy: "Import cache keeps current + prior calendar month only (relevant-periods-only).",
    };
  }

  function formatWidgetPeriodRequirements(snapshot) {
    const analysis = analyzeWidgetPeriods(snapshot || {});
    const lines = [
      "Widget period requirements (local import cache only):",
      "",
      `Policy: ${analysis.policy}`,
      `Required calendar months: ${analysis.requiredPeriods.join(", ")}`,
      "",
      "Loaded periods by dataset:",
      `- SoftDent dashboard: ${(analysis.loadedPeriods["softdent.dashboard"] || []).join(", ") || "none"}`,
      `- QuickBooks revenue: ${(analysis.loadedPeriods["quickbooks.revenue"] || []).join(", ") || "none"}`,
      `- QuickBooks expenses: ${(analysis.loadedPeriods["quickbooks.expenses"] || []).join(", ") || "none"}`,
      "",
      "Widget coverage:",
    ];
    analysis.widgets.forEach((w) => {
      lines.push(`- [${w.ok ? "OK" : "GAP"}] ${w.label}: ${w.requirement}`);
      if (w.missing && w.missing.length) lines.push(`  Missing: ${w.missing.join("; ")}`);
    });
    lines.push("", "HAL uses mental time travel here: compare required months to loaded exports before recommending trend or close work.");
    return lines.join("\n");
  }

  const api = { relevantPeriodLabels, analyzeWidgetPeriods, formatWidgetPeriodRequirements };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.HalPeriodRequirements = api;
})(typeof globalThis !== "undefined" ? globalThis : typeof window !== "undefined" ? window : {});
