/**
 * Moonshot-only page renderer — sole layout path from moonshot-page-layouts.js.
 * No legacy merge, no chart overlay. Page metadata from MoonshotPageRegistry.
 */
const MoonshotLayoutEngine = (function () {
  let MANIFEST = null;

  function loadManifest() {
    if (MANIFEST) return MANIFEST;
    if (typeof MOONSHOT_PAGE_LAYOUTS !== "undefined") {
      MANIFEST = MOONSHOT_PAGE_LAYOUTS;
      return MANIFEST;
    }
    try {
      if (typeof require !== "undefined") {
        MANIFEST = require("./moonshot-page-layouts.js");
        return MANIFEST;
      }
    } catch (_e) {
      /* browser without script tag */
    }
    return MANIFEST;
  }

  function pageSpec(pageId) {
    const m = loadManifest();
    return m && m.pages && m.pages[pageId] ? m.pages[pageId] : null;
  }

  function hasPage(pageId) {
    return Boolean(pageSpec(pageId));
  }

  function accentFor(pageId) {
    const R = typeof MoonshotPageRegistry !== "undefined" ? MoonshotPageRegistry : PageSchema;
    const p = R && R.byId ? R.byId(pageId) : null;
    return (p && p.accent) || "green";
  }

  /** Empty CTA naming exact export file(s) via HalSkills.widgetImportCta. */
  function emptyFor(H, widgetKey, subject) {
    if (H && typeof H.canvasEmptyFor === "function") return H.canvasEmptyFor(widgetKey, subject);
    const Skills = typeof HalSkills !== "undefined" ? HalSkills : null;
    if (Skills && typeof Skills.widgetImportCta === "function" && H && H.canvasEmpty) {
      return H.canvasEmpty(Skills.widgetImportCta(widgetKey, subject));
    }
    return H.canvasEmpty(
      subject
        ? `${subject} appears when the required import is loaded — then run refresh imports.`
        : "Add the required export into the import inbox, then run refresh imports.",
    );
  }

  function render(pageId, H) {
    const spec = pageSpec(pageId);
    if (!spec || !H) return "";
    const D = H.dataApi ? H.dataApi() : null;
    const accent = accentFor(pageId);
    const panels = spec.panels || [];
    const shell = spec.shell || "widget-grid";

    if (shell === "dashboard-grid") {
      let inner = "";
      if (pageId === "office-manager") {
        if (D && D.opsDataPanelHtml) inner += D.opsDataPanelHtml();
        if (H.canvasStatsBar && D && D.officeKpis) inner += H.canvasStatsBar(D.officeKpis());
      }
      if (pageId === "quickbooks") {
        inner += renderQuickbooksDashboard(panels, D, H, accent);
      } else {
        inner += `<div class="dashboard-grid">${panels.map((p) => renderDashboardTile(p, D, H, pageId, accent)).join("")}</div>`;
      }
      return `${H.dashboardPageOpen(`${pageId}-moonshot`)}<div class="widget-grid">${inner}</div></div>`;
    }

    let body = panels.map((p) => H.gridCol(p.colSpan || 12, renderWidgetGridPanel(p, D, H, pageId, accent))).join("");
    if (pageId === "softdent" && H.renderSoftdentOdbcStrip && D && D.softdentOdbcStatus) {
      body += H.renderSoftdentOdbcStrip(D.softdentOdbcStatus());
    }
    const pageClass =
      pageId === "claims"
        ? "claims-moonshot"
        : pageId === "narratives"
          ? "narratives-moonshot"
          : pageId === "taxes"
            ? "taxes-moonshot"
            : `${pageId}-moonshot`;
    return `${H.stackOpen(pageClass)}${body}</div>`;
  }

  function monthNameFromPeriod(label) {
    const raw = String(label || "").trim();
    const match = raw.match(/^(\d{4})-(\d{2})/);
    if (!match) return "";
    const months = [
      "January",
      "February",
      "March",
      "April",
      "May",
      "June",
      "July",
      "August",
      "September",
      "October",
      "November",
      "December",
    ];
    const idx = Number(match[2]) - 1;
    return months[idx] || "";
  }

  function resolvePanelTitle(panel, D) {
    const key = panel && panel.widgetKey;
    const fallback = (panel && panel.title) || "";
    if (key !== "periodCloseAndPosting" && key !== "journalPostingQueue") return fallback;
    let periodLabel = "";
    try {
      if (D && typeof D.documentsPeriodLabel === "function") {
        periodLabel = D.documentsPeriodLabel() || "";
      }
      if (!periodLabel && D && typeof D.metrics === "function") {
        const metrics = D.metrics("periodCloseAndPosting") || {};
        periodLabel = metrics.periodLabel || "";
      }
      if (!periodLabel && D && typeof D.documentsPeriodStats === "function") {
        const stats = D.documentsPeriodStats() || [];
        const periodStat = stats.find((row) => String(row.label || "").toLowerCase() === "period");
        periodLabel = (periodStat && periodStat.value) || periodLabel;
      }
    } catch (_e) {
      /* keep fallback */
    }
    const month = monthNameFromPeriod(periodLabel);
    if (!month) {
      if (/^june\s+/i.test(fallback)) {
        return key === "journalPostingQueue" ? "Journal Entries" : "Period Close";
      }
      return fallback;
    }
    return key === "journalPostingQueue" ? `${month} Journal Entries` : `${month} Period Close`;
  }

  function renderWidgetGridPanel(panel, D, H, pageId, accent) {
    const panelTitle = resolvePanelTitle(panel, D);
    if (panel.type === "hero-kpi" && panel.colSpan && panel.colSpan < 12) {
      const kpis = resolveHeroKpis(panel, D, H, pageId);
      const kpi = Array.isArray(kpis) ? kpis[0] : kpis;
      if (panel.halSubpanel && H.canvasPanel) {
        return H.canvasPanel({
          title: panelTitle || (kpi && kpi.label) || "",
          accent,
          halSubpanel: panel.halSubpanel,
          body: kpi
            ? `<div class="kpi-value">${H.esc(kpi.value || "—")}</div>${kpi.hint ? `<span class="trend">${H.esc(kpi.hint)}</span>` : ""}`
            : emptyFor(H, "claimsPipeline", "Claims metrics"),
        });
      }
      if (kpi && H.canvasMetricTile) {
        const tile = { ...kpi, label: panelTitle || kpi.label };
        return H.canvasMetricTile(tile, panel.colSpan);
      }
    }
    if (panel.type === "hero-kpi" && (!panel.colSpan || panel.colSpan >= 12)) {
      const kpis = resolveHeroKpis(panel, D, H, pageId);
      if (pageId === "ar" && kpis && kpis.length) {
        return kpis.length >= 5 ? H.heroKpiRow(kpis, 6) : H.canvasKpiGrid(kpis);
      }
      const maxKpis = pageId === "financial" ? 5 : pageId === "ar" ? 6 : pageId === "claims" ? 4 : 4;
      return kpis && kpis.length ? H.heroKpiRow(kpis, maxKpis) : "";
    }
    return H.canvasPanel({
      title: panelTitle || "",
      accent,
      widgetKey: panel.widgetKey,
      halSubpanel: panel.halSubpanel,
      chartHost: false,
      colSpan: panel.colSpan,
      body: renderPanelBody(panel, D, H, pageId, accent),
    });
  }

  function renderDashboardTile(panel, D, H, pageId, accent) {
    if (panel.type === "hero-kpi") {
      const kpis = resolveHeroKpis(panel, D, H, pageId);
      return (kpis || [])
        .slice(0, 4)
        .map((k) => {
          const wk = k.widgetKey || panel.widgetKey || "";
          const delta = k.delta ? `<span class="trend">${H.esc(k.delta)}</span>` : "";
          return `<div class="card kpi-card kpi-glow-card"${H.kpiRefOnly ? H.kpiRefOnly(wk, k.label || panel.title) : ""}>
            <div class="card-header"><span class="card-title">${H.esc(k.label || panel.title)}</span>${delta}</div>
            <div class="card-value">${H.esc(k.value || "—")}</div>
          </div>`;
        })
        .join("");
    }
    const wk = panel.widgetKey || "";
    const body = renderPanelBody(panel, D, H, pageId, accent);
    const chartCls = panel.type === "chart" ? " chart-large" : panel.type === "gauge" ? " kpi-card" : " chart-medium";
    const attrs = panel.halSubpanel
      ? ` data-hal-subpanel="${H.esc(panel.halSubpanel)}"`
      : wk
        ? ` data-hal-widget-key="${H.esc(wk)}"`
        : "";
    return `<div class="card widget-glow-border${chartCls}"${attrs}>
      <div class="card-header"><span class="card-title">${H.esc(panel.title || "")}</span></div>
      ${body}
    </div>`;
  }

  /** Elite Jul 8 QB mockup — single 12-col dashboard-grid with colSpan spans. */
  function renderQuickbooksDashboard(panels, D, H, accent) {
    const tiles = panels
      .map((p) => {
        const span = Math.min(12, Math.max(1, Number(p.colSpan) || 6));
        return `<div class="qb-span qb-span-${span}">${renderDashboardTile(p, D, H, "quickbooks", accent)}</div>`;
      })
      .join("");
    return `<div class="dashboard-grid qb-dashboard-grid">${tiles}</div>`;
  }

  function resolveHeroKpis(panel, D, H, pageId) {
    if (!D) return [];
    if (pageId === "financial") {
      const built = D.financialKpis ? D.financialKpis() : [];
      if (panel.kpis && panel.kpis.length) {
        const byKey = Object.fromEntries(built.map((k) => [k.widgetKey, k]));
        return panel.kpis.map((spec) => {
          const base = byKey[spec.widgetKey] || { label: spec.label || spec.widgetKey, value: "—", widgetKey: spec.widgetKey };
          // Prefer live period-aware labels (e.g. Collections (2026-06)) over static layout MTD titles.
          return { ...base, label: base.label || spec.label || spec.widgetKey, widgetKey: spec.widgetKey };
        });
      }
      return built;
    }
    if (pageId === "softdent" && panel.kpis && panel.kpis.length) {
      const built = D.softdentHeroKpis ? D.softdentHeroKpis() : D.softdentKpis ? D.softdentKpis() : [];
      const byKey = Object.fromEntries(built.map((k) => [k.widgetKey, k]));
      return panel.kpis.map((spec) => {
        const base = byKey[spec.widgetKey] || { label: spec.label || spec.widgetKey, value: "—", widgetKey: spec.widgetKey };
        return { ...base, label: base.label || spec.label || spec.widgetKey, widgetKey: spec.widgetKey };
      });
    }
    if (pageId === "softdent" && panel.widgetKey) {
      const all = D.softdentKpis ? D.softdentKpis() : [];
      if (panel.widgetKey === "careDeliveryPerformance") {
        const base = all.find((k) => k.widgetKey === "careDeliveryPerformance") || { value: "—", widgetKey: "careDeliveryPerformance" };
        return [{ ...base, label: panel.title || "Production MTD", widgetKey: "careDeliveryPerformance" }];
      }
      if (panel.widgetKey === "softdentNewPatientsMTD") {
        const np = D.softdentNewPatientsMtdData ? D.softdentNewPatientsMtdData() : { count: 0, hasData: false };
        const value = np.hasData ? String(np.count ?? "—") : "—";
        const label = np.hasData && np.period ? `New Patients (${np.period})` : panel.title || "New Patients";
        return [{ label, value, widgetKey: "softdentNewPatientsMTD" }];
      }
      if (panel.widgetKey === "caseAcceptance") {
        const base = all.find((k) => k.widgetKey === "caseAcceptance") || { value: "—", widgetKey: "caseAcceptance" };
        return [{ ...base, label: panel.title || "Case Acceptance Rate", widgetKey: "caseAcceptance" }];
      }
      if (panel.widgetKey === "softdentClaimsOutstanding") {
        const co = D.softdentClaimsOutstandingData ? D.softdentClaimsOutstandingData() : { claims: [] };
        return [{ label: panel.title || "Outstanding Claims", value: String((co.claims && co.claims.length) || 0), widgetKey: "softdentClaimsOutstanding" }];
      }
    }
    if (pageId === "claims" && panel.kpis && panel.kpis.length) {
      return D.claimsPipelineSummary ? D.claimsPipelineSummary() : D.claimsKpis ? D.claimsKpis() : [];
    }
    if (pageId === "ar" && panel.kpis && panel.kpis.length) {
      const built = D.arEliteKpis ? D.arEliteKpis() : D.arKpis ? D.arKpis() : [];
      const bySub = Object.fromEntries(built.filter((k) => k.halSubpanel).map((k) => [k.halSubpanel, k]));
      return panel.kpis.map((spec) => {
        const base = bySub[spec.halSubpanel] || { label: spec.label, value: "—", halSubpanel: spec.halSubpanel };
        return { ...base, label: spec.label || base.label, halSubpanel: spec.halSubpanel };
      });
    }
    if (pageId === "claims" && panel.halSubpanel) {
      const all = D.claimsKpis ? D.claimsKpis() : [];
      const idx = { claimsKpiTotal: 0, claimsKpiValue: 1, claimsKpiDenied: 2 }[panel.halSubpanel];
      return idx != null && all[idx] ? [all[idx]] : [];
    }
    if (pageId === "ar") return D.arKpis ? D.arKpis() : [];
    if (pageId === "quickbooks") return D.quickbooksKpis ? D.quickbooksKpis() : [];
    return [];
  }

  function renderPanelBody(panel, D, H, pageId, accent) {
    const wk = panel.widgetKey;
    if (panel.type === "kanban" && wk && WIDGET_BODY[wk]) return WIDGET_BODY[wk](D, H, panel, pageId, accent);
    if (wk && WIDGET_BODY[wk]) return WIDGET_BODY[wk](D, H, panel, pageId, accent);
    if (panel.type === "hero-kpi") return "";
    if (panel.halSubpanel && SUBPANEL_BODY[panel.halSubpanel]) {
      return SUBPANEL_BODY[panel.halSubpanel](D, H, panel, pageId, accent);
    }
    return emptyFor(H, wk || null, panel.title || "Widget");
  }

  const WIDGET_BODY = {
    nr2AlertTicker(D, H) {
      const alerts = D && D.nr2AlertTicker ? D.nr2AlertTicker() : { items: [] };
      if (alerts.items && alerts.items.length) {
        return H.canvasAlertTicker(alerts.items);
      }
      return H.canvasEmpty("No cross-analytics exceptions for the imported snapshot — thresholds evaluate SoftDent vs QuickBooks variance, collection lag, and A/R 90+.");
    },
    nr2MonthlyTrendCombo(D, H) {
      const combo = D && D.nr2MonthlyTrendCombo ? D.nr2MonthlyTrendCombo() : {};
      return H.canvasMonthlyTrendCombo(combo);
    },
    nr2KpiRibbon(D, H) {
      const ribbon = D && D.nr2KpiRibbonTiles ? D.nr2KpiRibbonTiles() : { tiles: [] };
      return H.canvasKpiRibbon(ribbon.tiles || []);
    },
    nr2GoalScorecard(D, H) {
      return H.canvasGoalScorecard(D && D.nr2GoalScorecard ? D.nr2GoalScorecard() : {});
    },
    nr2ProductionReconciliation(D, H) {
      return H.canvasReconciliationTable(D && D.nr2ProductionReconciliation ? D.nr2ProductionReconciliation() : { rows: [] });
    },
    softdentProductionDaily(D, H) {
      const prodDaily = D && D.softdentProductionDailySeries ? D.softdentProductionDailySeries() : { points: [] };
      return H.chartContainer(
        prodDaily.points && prodDaily.points.length
          ? H.vBarChart(
              prodDaily.points.map((p) => p.date),
              prodDaily.points.map((p) => p.production),
              "#60a5fa",
            )
          : emptyFor(H, "softdentProductionDaily", "Production trend"),
      );
    },
    nr2CollectionLag(D, H) {
      const lag = D && D.nr2CollectionLag ? D.nr2CollectionLag() : {};
      if (!lag.hasData) {
        return emptyFor(H, "nr2CollectionLag", "Collection lag");
      }
      const days = lag.avgLagDays != null ? lag.avgLagDays : "—";
      const arcPct = typeof days === "number" ? Math.min(100, Math.round((days / 60) * 100)) : 0;
      const caption = lag.caption
        ? `<div class="gauge-caption ms-elite-gauge-caption">${H.esc(String(lag.caption))}</div>`
        : "";
      const aria = lag.caption ? `Collection lag ${days} days · ${lag.caption}` : `Collection lag ${days} days`;
      return `<div class="ms-elite-dso-gauge gauge-container" role="img" aria-label="${H.esc(aria)}">
        <svg viewBox="0 0 120 70" class="gauge-svg ms-elite-gauge-svg" aria-hidden="true">
          <path d="M 10 65 A 50 50 0 0 1 110 65" fill="none" stroke="var(--line-subtle)" stroke-width="8"/>
          <path d="M 10 65 A 50 50 0 0 1 110 65" fill="none" stroke="var(--gold)" stroke-width="8" stroke-dasharray="${(arcPct * 1.57).toFixed(1)} 157" stroke-linecap="round" class="ms-elite-gauge-arc"/>
        </svg>
        <div class="gauge-center"><strong class="gauge-value">${H.esc(String(days))}</strong><span class="gauge-label">Days</span></div>
        ${caption}
      </div>`;
    },
    providerPerformance(D, H) {
      const providers = D && D.providerBars ? D.providerBars() : null;
      if (!providers || !providers.items.length) {
        return emptyFor(H, "providerPerformance", "Provider performance");
      }
      return H.hBarChart(
        providers.items.map((item) => ({ name: item.name, amount: item.amount, pct: item.pct })),
        "amount",
        "name",
        "pct",
      );
    },
    softdentNewPatientsMTD(D, H) {
      const np = D && D.softdentNewPatientsMtdData ? D.softdentNewPatientsMtdData() : { count: 0, hasData: false };
      const flow = D && D.newPatientsFlowSeries ? D.newPatientsFlowSeries() : { hasData: false, values: [] };
      const val = np.hasData ? String(np.count) : "—";
      const periodHint = np.period ? String(np.period) : "MTD";
      const sparkValues =
        flow.hasData && flow.values && flow.values.length
          ? flow.values
          : np.hasData && np.count != null
            ? [Number(np.count) || 0]
            : [];
      const spark =
        sparkValues.length && typeof H.barSparkline === "function"
          ? H.barSparkline(sparkValues, "success")
          : "";
      return `<div class="ms-elite-stat-tile">
        <div class="kpi-value">${H.esc(val)}</div>
        <div class="trend-indicator"><span>${H.esc(periodHint)}</span></div>
        ${spark}
      </div>`;
    },
    softdentClaimsOutstanding(D, H) {
      const co = D && D.softdentClaimsOutstandingData ? D.softdentClaimsOutstandingData() : { claims: [] };
      const count = co.claims && co.claims.length ? co.claims.length : 0;
      const total = co.claims && co.claims.length
        ? co.claims.reduce((sum, row) => sum + (H.parseAmount(row.balance || row.amount) || 0), 0)
        : 0;
      return `<div class="ms-elite-stat-tile">
        <div class="kpi-value">${H.esc(String(count || "—"))}</div>
        <div class="trend-indicator ms-elite-stat-hint">${total ? H.esc(`$${Math.round(total).toLocaleString()}`) : "—"}</div>
      </div>`;
    },
    newPatients(D, H) {
      const flow = D && D.newPatientsFlowSeries ? D.newPatientsFlowSeries() : { hasData: false };
      if (!flow.hasData || !flow.labels || !flow.labels.length) {
        return emptyFor(H, "newPatients", "New patient flow");
      }
      if (flow.singlePeriod && flow.values.length === 1) {
        const period = flow.labels[0];
        const count = flow.values[0];
        return `<div class="ms-elite-stat-tile">
          <div class="kpi-value">${H.esc(String(count))}</div>
          <div class="trend-indicator"><span>${H.esc(period || "Latest period")}</span> · single exported period</div>
        </div>`;
      }
      return H.chartContainer(H.vBarChart(flow.labels, flow.values, "#34d399"));
    },
    nr2ProviderCompensationWidget(D, H) {
      const provComp = D && D.nr2ProviderCompensation ? D.nr2ProviderCompensation() : { providers: [], hasData: false };
      if (provComp.hasData && provComp.providers && provComp.providers.length) {
        return H.canvasProviderCompShare(provComp);
      }
      const providers = D && D.providerBars ? D.providerBars() : null;
      if (!providers || !providers.items || !providers.items.length) {
        return emptyFor(H, "nr2ProviderCompensationWidget", "Provider production share");
      }
      const payload = {
        providers: providers.items.map((item) => ({
          name: item.name,
          production: H.parseAmount(item.amount),
          pct: item.pct,
        })),
        totalProduction: H.parseAmount(providers.total),
        hasData: true,
      };
      return H.canvasProviderCompShare(payload);
    },
    quickbooksProfitLossDetail(D, H) {
      const rows = D && D.quickbooksPlRows ? D.quickbooksPlRows() : [];
      return rows.length
        ? H.canvasTable(["Account", "Amount", "Notes"], rows.slice(0, 12), true)
        : emptyFor(H, "quickbooksProfitLossDetail", "QuickBooks P&L rows");
    },
    ebitdaNormalization(D, H) {
      const rows = D && D.ebitdaRows ? D.ebitdaRows() : [];
      return rows.length
        ? H.canvasTable(["Adjustment", "Amount", "Reviewer", "Notes"], rows, true)
        : emptyFor(H, "ebitdaNormalization", "EBITDA normalization");
    },
    taxBookToTaxBridge(D, H) {
      const bridge = D && D.taxBridgeRows ? D.taxBridgeRows() : [];
      return bridge.length
        ? H.canvasTable(["Line item", "Amount"], bridge, true)
        : emptyFor(H, "quickbooksProfitLossDetail", "Book-to-tax bridge");
    },
    taxReasonableComp(D, H) {
      const scenarios = D && D.taxCompScenarioRows ? D.taxCompScenarioRows() : [];
      return scenarios.length
        ? H.canvasTable(["W-2 salary", "Est. K-1", "Employer FICA", "Note"], scenarios, true)
        : emptyFor(H, "quickbooksProfitLossDetail", "Compensation scenarios");
    },
    taxQuarterlyEstimates(D, H) {
      const quarterly = D && D.taxQuarterlyRows ? D.taxQuarterlyRows() : [];
      return quarterly.length
        ? H.canvasTable(["Period", "Federal", "Kansas", "Due", "Amount"], quarterly, true)
        : H.canvasEmpty("Quarterly estimates appear when tax engine runs.");
    },
    taxFederalStateSplit(D, H) {
      const split = D && D.taxSplit ? D.taxSplit() : [];
      if (!split.length) return H.canvasEmpty("Federal/state split appears when tax plan is loaded.");
      const total = split.reduce((s, row) => s + H.parseAmount(row[1]), 0) || 1;
      const slices = split.map((row, i) => ({
        label: row[0],
        pct: Math.round((H.parseAmount(row[1]) / total) * 100),
        color: i ? "#a855f7" : "#60a5fa",
      }));
      return `<div class="tax-split-chart">${H.conicDonut(slices, "")}</div>`;
    },
    softdentCollectionsDaily(D, H) {
      const coll = D && D.softdentCollectionsDailySeries ? D.softdentCollectionsDailySeries() : { labels: [], values: [] };
      return H.chartContainer(
        coll.hasData ? H.vBarChart(coll.labels, coll.values, "#34d399") : emptyFor(H, "softdentCollectionsDaily", "Collections trend"),
      );
    },
    softdentProviderProduction(D, H) {
      const prov = D && D.softdentProviderProductionData ? D.softdentProviderProductionData() : { providers: [] };
      return H.chartContainer(
        prov.hasData
          ? H.hBarChart(
              prov.providers.map((p) => ({
                name: p.providerCode,
                amount: `$${Math.round(p.production).toLocaleString()}`,
                pct: prov.total ? Math.round((p.production / prov.total) * 100) : 0,
              })),
              "amount",
              "name",
              "pct",
            )
          : emptyFor(H, "softdentProviderProduction", "Provider production"),
      );
    },
    softdentArAging(D, H, panel) {
      if (panel && panel.type === "heatmap") {
        const heat = D && D.softdentArAgingHeatmap ? D.softdentArAgingHeatmap() : null;
        if (heat && heat.matrix) return H.canvasHeatmap(heat.rowLabels, heat.colLabels, heat.matrix);
        const aging = D && D.softdentAgingBars ? D.softdentAgingBars() : null;
        const fallback = H.arHeatmapFromAging ? H.arHeatmapFromAging(aging) : null;
        return fallback
          ? H.canvasHeatmap(fallback.rowLabels, fallback.colLabels, fallback.matrix)
          : emptyFor(H, "softdentArAging", "A/R aging heatmap");
      }
      const aging = D && D.softdentAgingBars ? D.softdentAgingBars() : null;
      return H.chartContainer(
        aging ? H.vBarChart(aging.labels, aging.values, "#60a5fa") : emptyFor(H, "softdentArAging", "A/R aging"),
      );
    },
    caseAcceptance(D, H, panel) {
      const ca = H.metricsFromWidget("caseAcceptance");
      const practice = D && D.practiceStats ? D.practiceStats() : {};
      const raw = ca.acceptanceRate != null && ca.acceptanceRate !== "" && ca.acceptanceRate !== "—"
        ? ca.acceptanceRate
        : ca.rate != null && ca.rate !== "" && ca.rate !== "—"
          ? ca.rate
          : practice.caseRate != null && practice.caseRate !== "" && practice.caseRate !== "—"
            ? practice.caseRate
            : null;
      if (raw == null || /not\s*configured/i.test(String(raw))) {
        return emptyFor(H, "caseAcceptance", "Case acceptance");
      }
      const pct = typeof raw === "number" ? raw : H.parsePct(raw);
      if (!Number.isFinite(pct)) {
        return emptyFor(H, "caseAcceptance", "Case acceptance");
      }
      return H.canvasGauge(Math.min(100, Math.max(0, pct)), "Acceptance", "var(--accent-cyan, #22d3ee)");
    },
    hygieneRecall(D, H, panel) {
      if (panel && panel.type === "gauge") {
        const gauge = D && D.hygieneRecallGauge ? D.hygieneRecallGauge() : { hasData: false };
        if (!gauge || !gauge.hasData || gauge.rate == null) {
          return emptyFor(H, "hygieneRecall", "Hygiene recall");
        }
        const pct = typeof gauge.rate === "number" ? gauge.rate : H.parsePct(gauge.rate);
        return H.canvasGauge(Math.min(100, Math.max(0, pct)), "Recall", "var(--accent-cyan, #22d3ee)");
      }
      const practice = D && D.practiceStats ? D.practiceStats() : {};
      const completed = practice.hygieneCompleted && practice.hygieneCompleted !== "—" ? practice.hygieneCompleted : "—";
      const dueNote = practice.recallDue ? `<p class="widget-note">${H.esc(practice.recallDue)}</p>` : "";
      return `${H.canvasStat(completed, "Hygiene completed", undefined, "hygieneRecall")}${dueNote}`;
    },
    softdentResponsibility(D, H) {
      const resp = D && D.softdentResponsibilityDonut ? D.softdentResponsibilityDonut() : null;
      if (!resp) return emptyFor(H, "softdentResponsibility", "Insurance vs patient split");
      const center = resp.hint ? `<span class="donut-hint">${H.esc(resp.hint)}</span>` : "";
      return H.conicDonut(resp.slices, center);
    },
    treatmentPlanSummary(D, H, panel) {
      const practice = D && D.practiceStats ? D.practiceStats() : {};
      const ca = H.metricsFromWidget("caseAcceptance");
      if (panel && panel.type === "funnel") {
        const steps = [
          { label: "Presented", value: ca.plansPresented || practice.treatmentPresented },
          { label: "Accepted", value: ca.plansAccepted || practice.caseAccepted },
          { label: "Scheduled", value: ca.plansScheduled || practice.treatmentScheduled },
          { label: "Completed", value: ca.plansCompleted || practice.treatmentCompleted },
        ];
        const hasAny = steps.some((s) => s.value != null && s.value !== "" && s.value !== "—" && !/not\s*configured/i.test(String(s.value)));
        if (!hasAny) {
          return emptyFor(H, "treatmentPlanSummary", "Treatment-plan funnel");
        }
        return H.canvasFunnel(steps.map((s) => ({ label: s.label, value: H.fmtClaim(s.value != null && s.value !== "" ? s.value : "—") })));
      }
      return H.canvasStat(practice.treatmentPresented || "—", "Treatment presented", undefined, "treatmentPlanSummary");
    },
    softdentAppointmentsSnapshot(D, H, panel) {
      if (panel && panel.type === "stat-grid") {
        const stats = D && D.softdentAppointmentStats ? D.softdentAppointmentStats() : [];
        if (stats.length) {
          return H.canvasStatGrid(stats.map((s) => ({ ...s, widgetKey: "softdentAppointmentsSnapshot" })));
        }
      }
      const appt = D && D.softdentAppointmentsSnapshotData ? D.softdentAppointmentsSnapshotData() : { appointments: [] };
      if (appt.hasData && appt.appointments && appt.appointments.length) {
        return H.canvasTable(
          ["Time", "Patient", "Operatory", "Status"],
          appt.appointments.map((a) => [a.date, a.patientId, a.provider, a.status]),
          true,
        );
      }
      return emptyFor(H, "softdentAppointmentsSnapshot", "Appointment snapshot");
    },
    softdentOperatoryGrid(D, H) {
      return H.canvasOperatoryGrid(D && D.softdentOperatoryGrid ? D.softdentOperatoryGrid() : null);
    },
    claimsPipeline(D, H) {
      const lanes = D && D.claimsKanban ? D.claimsKanban() : [];
      const hasCards = lanes.some((lane) => lane.items && lane.items.length);
      if (!lanes.length) {
        return emptyFor(H, "claimsPipeline", "Claims pipeline");
      }
      const board = H.canvasKanbanLanes(lanes, "claimsPipeline", { claims: true });
      if (hasCards) return board;
      return `${board}${emptyFor(H, "claimsPipeline", "Claim cards")}`;
    },
    arAgingAndCollections(D, H, panel) {
      const aging = D && D.arAgingBars ? D.arAgingBars() : D && D.softdentAgingBars ? D.softdentAgingBars() : null;
      const heat = H.arHeatmapFromAging ? H.arHeatmapFromAging(aging) : null;
      if (!aging || !aging.labels || !aging.values) {
        return emptyFor(H, "arAgingAndCollections", "A/R aging");
      }
      const waterfall = `<div class="ms-elite-waterfall">${aging.labels
        .map((label, i) => {
          const max = Math.max(...aging.values, 1);
          const pct = Math.round(((aging.values[i] || 0) / max) * 100);
          return `<div class="ms-elite-waterfall-row"><span class="ms-elite-waterfall-label">${H.esc(label)}</span><div class="ms-elite-waterfall-track"><div class="ms-elite-waterfall-fill" style="--w:${pct}%"></div></div><span class="ms-elite-stat-num">$${Math.round(aging.values[i] || 0).toLocaleString()}</span></div>`;
        })
        .join("")}</div>`;
      const heatHtml = heat
        ? H.canvasHeatmap(heat.rowLabels, heat.colLabels, heat.matrix)
        : emptyFor(H, "arAgingAndCollections", "A/R aging heatmap");
      return `${waterfall}${heatHtml}`;
    },
    smartClaimsAndReceivables(D, H) {
      const kanban = D && D.arFollowUpKanban ? D.arFollowUpKanban() : [];
      const kanbanLanes =
        kanban.length > 0
          ? kanban
          : [
              { lane: "Needs call", tone: "orange", items: [] },
              { lane: "Awaiting payer", tone: "blue", items: [] },
              { lane: "Ready to close", tone: "green", items: [] },
            ];
      return H.canvasPriorityQueue(kanbanLanes, "smartClaimsAndReceivables");
    },
    arOutstandingClaims(D, H) {
      const claims = D && D.arTopClaimsTable ? D.arTopClaimsTable() : [];
      return claims.length
        ? H.canvasTable(["Patient", "Procedure", "Payer", "Balance", "Age"], claims, true)
        : emptyFor(H, "arOutstandingClaims", "Outstanding claim detail");
    },
    quickbooksMonthlyRevenue(D, H) {
      const moRev = D && D.quickbooksMonthlyRevenueSeries ? D.quickbooksMonthlyRevenueSeries() : { labels: [], values: [] };
      const plTrend = D && D.quickbooksPlTrend ? D.quickbooksPlTrend() : null;
      if (plTrend && plTrend.labels) {
        return H.chartContainer(H.dualLineChart(plTrend.labels, plTrend.series), true);
      }
      return moRev.hasData
        ? H.chartContainer(H.vBarChart(moRev.labels, moRev.values, "#00d4ff"))
        : emptyFor(H, "quickbooksMonthlyRevenue", "Monthly revenue trend");
    },
    quickbooksRevenueByService(D, H) {
      const revSvc = D && D.quickbooksRevenueByService ? D.quickbooksRevenueByService() : { slices: [] };
      if (!revSvc.hasData) return emptyFor(H, "quickbooksRevenueByService", "Revenue-by-service");
      const slices = revSvc.slices.map((s, i) => ({
        label: s.label,
        pct: s.pct || Math.round((s.amount / (revSvc.total || 1)) * 100),
        color: ["#60a5fa", "#34d399", "#f59e0b", "#a855f7"][i % 4],
      }));
      return H.conicDonut(slices, "");
    },
    quickbooksNetIncomeSummary(D, H) {
      const netInc = D && D.quickbooksNetIncomeSummary ? D.quickbooksNetIncomeSummary() : {};
      const ytd = netInc.hasData && netInc.ytdNetIncome != null ? `$${Math.round(netInc.ytdNetIncome).toLocaleString()}` : "—";
      const margin = netInc.marginPct != null ? `${netInc.marginPct}%` : "—";
      const qoq = netInc.qoqGrowthPct != null ? `${netInc.qoqGrowthPct}%` : "—";
      return H.canvasStatGrid([
        { value: ytd, label: "YTD Net Income", widgetKey: "quickbooksNetIncomeSummary" },
        { value: margin, label: "Margin", widgetKey: "quickbooksNetIncomeSummary" },
        { value: qoq, label: "QOQ Growth", widgetKey: "quickbooksNetIncomeSummary" },
      ]);
    },
    quickbooksBalanceSheetSummary(D, H) {
      const bs = D && D.quickbooksBalanceSheetSummary ? D.quickbooksBalanceSheetSummary() : { assets: [] };
      return bs.hasData
        ? H.canvasTable(
            ["Asset", "Amount"],
            (bs.assets || []).map((row) => [row.label, `$${Math.round(row.amount).toLocaleString()}`]),
            true,
          )
        : emptyFor(H, "quickbooksBalanceSheetSummary", "Balance sheet summary");
    },
    quickbooksCashFlowTrend(D, H) {
      const cf = D && D.quickbooksCashFlowTrend ? D.quickbooksCashFlowTrend() : { labels: [], net: [] };
      return cf.hasData
        ? H.chartContainer(H.dualLineChart(cf.labels, [{ label: "Net", tone: "success", data: cf.net }]), true)
        : emptyFor(H, "quickbooksCashFlowTrend", "Cash flow trend");
    },
    quickbooksExpenseBreakdown(D, H) {
      const expenseBars = D && D.quickbooksExpenseBars ? D.quickbooksExpenseBars() : null;
      if (!expenseBars || !expenseBars.labels.length) {
        return emptyFor(H, "quickbooksExpenseBreakdown", "Expense breakdown");
      }
      const max = Math.max(...expenseBars.values, 1);
      return `<div class="ms-elite-stat-grid">${expenseBars.labels
        .map((label, i) => {
          const val = expenseBars.values[i] || 0;
          const pct = Math.round((val / max) * 100);
          return `<div class="ms-elite-stat-row"><span class="ms-elite-stat-label">${H.esc(label)}</span><div class="ms-elite-stat-bar-bg"><div class="ms-elite-stat-bar-fill" style="--w:${pct}%"></div></div><span class="ms-elite-stat-num">$${Math.round(val).toLocaleString()}</span></div>`;
        })
        .join("")}</div>`;
    },
    quickbooksArAging(D, H) {
      const qbAr = D && D.quickbooksQbArAging ? D.quickbooksQbArAging() : { buckets: [] };
      return qbAr.hasData
        ? H.canvasTable(
            ["Bucket", "Balance"],
            qbAr.buckets.map((b) => [b.bucket, `$${Math.round(b.balance).toLocaleString()}`]),
            true,
          )
        : emptyFor(H, "quickbooksArAging", "QuickBooks A/R aging");
    },
    documentIntakeQueue(D, H) {
      const queue = D && D.documentsQueueRows ? D.documentsQueueRows() : [];
      return queue.length
        ? H.canvasTable(["Document", "Category", "Amount", "Date"], queue, true)
        : emptyFor(H, "documentIntakeQueue", "Accounting documents");
    },
    documentPreview(D, H) {
      const doc = D && D.firstDocument ? D.firstDocument() : null;
      return `${H.canvasDocPreview(doc ? doc.vendor || doc.id || "Document" : "Document preview", doc && doc.pages ? doc.pages : 1)}${doc ? "" : emptyFor(H, "documentPreview", "Document preview")}`;
    },
    accountsPayableAutomation(D, H) {
      const apRows = D && D.accountsPayableRows ? D.accountsPayableRows() : [];
      if (apRows.length) {
        return H.canvasTable(["Vendor", "Amount", "Due", "Status"], apRows, true);
      }
      const ap = H.metricsFromWidget("accountsPayableAutomation");
      const postedRaw = ap.postedPct;
      const posted =
        postedRaw == null || postedRaw === "" || postedRaw === "—" || /not\s*configured/i.test(String(postedRaw))
          ? "—"
          : `${H.parsePct(postedRaw)}%`;
      if ((ap.expenseTotal == null || ap.expenseTotal === "" || ap.expenseTotal === "—") && posted === "—") {
        return emptyFor(H, "accountsPayableAutomation", "Accounts payable");
      }
      return H.canvasTable(
        ["Metric", "Value"],
        [
          ["Expense total", H.fmtClaim(ap.expenseTotal)],
          ["Posted", posted],
        ],
        true,
      );
    },
    periodCloseAndPosting(D, H) {
      const periodStats = D && D.documentsPeriodStats ? D.documentsPeriodStats() : [];
      if (periodStats.length) {
        return H.canvasStatGrid(periodStats.map((s) => ({ ...s, widgetKey: "periodCloseAndPosting" })));
      }
      return emptyFor(H, "periodCloseAndPosting", "Period close metrics");
    },
    journalPostingQueue(D, H) {
      const journalItems = D && D.journalQueueItems ? D.journalQueueItems() : [];
      if (journalItems.length) return H.renderJournalQueuePanel(journalItems);
      const rows = D && D.journalRows ? D.journalRows() : [];
      if (rows.length) {
        return H.canvasTable(["Entry", "Amount", "Category", "Source"], rows, true);
      }
      return H.canvasEmpty("No journal entries in queue — reviewed accruals appear here when staff stages them for export.");
    },
    documentLibrary(D, H) {
      const rows = D && D.libraryRows ? D.libraryRows() : [];
      const doc = D && D.firstLibraryDoc ? D.firstLibraryDoc() : null;
      return `${rows.length ? H.canvasTable(["Document", "Category", "Updated", "Expires"], rows, true) : emptyFor(H, "documentLibrary", "Library documents")}${doc ? H.canvasDocPreview(doc.title || "Preview", doc.pages || 1) : ""}`;
    },
    officeManagerPriorities(D, H) {
      const kanban = D && D.officeKanban ? D.officeKanban() : [];
      if (!kanban.length) {
        return H.canvasEmpty("Office priorities appear when HAL office tasks or degraded widgets need staff attention.");
      }
      return H.canvasKanbanLanes(kanban, "officeManagerPriorities");
    },
    officeManagerSurfaces(D, H) {
      const staffPages =
        typeof PageSchema !== "undefined" && PageSchema.NAV_GROUPS
          ? PageSchema.NAV_GROUPS.flatMap((g) => g.pages).filter((id) => id !== "hal" && id !== "office-manager")
          : [];
      return H.canvasNavPills(staffPages);
    },
    halAskHal(D, H) {
      const RT = typeof globalThis !== "undefined" ? globalThis : typeof window !== "undefined" ? window : {};
      const history =
        (typeof halChatHistory !== "undefined" && Array.isArray(halChatHistory) && halChatHistory) ||
        RT.halChatHistory ||
        [];
      const loading =
        (typeof halAskLoading !== "undefined" && !!halAskLoading) || !!RT.halAskLoading;
      const draft =
        (typeof halAskDraft !== "undefined" && halAskDraft) || RT.halAskDraft || "";
      const messages = history.slice(-12);
      const chatHtml = messages.length
        ? `<div class="chat-history">${messages
            .map((m) => {
              const roleClass = m.role === "user" ? "message message-user" : "message message-hal";
              const who = m.role === "user" ? "You" : "HAL";
              return `<div class="${roleClass}"><div class="message-head"><span>${H.esc(who)}</span></div><p>${H.esc(m.text || "")}</p></div>`;
            })
            .join("")}</div>`
        : `<p class="chat-placeholder">Ask about imports, widgets, or today's plan…</p>`;
      const suggestions = D && D.halAskHalSuggestions ? D.halAskHalSuggestions() : [];
      const chips = suggestions
        .map(
          (s) =>
            `<button type="button" class="prompt-chip" data-hal-suggest="${H.esc(s)}">${H.esc(s)}</button>`,
        )
        .join("");
      return `<div class="chat-rail-panel" data-panel="askHal" data-hal-widget-key="halAskHal">
        <div class="chat-header">
          <div class="chat-title"><span class="chat-avatar" aria-hidden="true">AI</span> Ask HAL</div>
          <div class="chat-status">Local only</div>
        </div>
        <div class="chat-messages">${chatHtml}</div>
        <form class="chat-form chat-input" id="hpAskForm">
          <textarea class="chat-textarea" id="hpAskInput" rows="2" enterkeyhint="send" placeholder="Ask HAL anything…  (Enter to send)" aria-label="Ask HAL">${H.esc(draft)}</textarea>
          <div class="chat-input-row">
            <button class="chat-send" type="submit" ${loading ? "disabled" : ""}>${loading ? "…" : "SEND"}</button>
          </div>
        </form>
        <div class="chat-suggestions prompt-chips prompt-chips--live">${chips}</div>
      </div>`;
    },
    halImportHealth(D, H) {
      const health = D && D.halImportHealthStats ? D.halImportHealthStats() : { hasData: false, stats: [] };
      if (!health.hasData) {
        return emptyFor(H, "halImportHealth", "Import & Source Health");
      }
      const mode = health.importMode
        ? `<p class="widget-footer">Mode: ${H.esc(String(health.importMode))} · ${H.esc(String(health.status || ""))}</p>`
        : "";
      return `${H.canvasStatGrid(health.stats || [])}${mode}`;
    },
    practiceFinancialOverview(D, H) {
      const pack = D && D.halPracticeOverviewStats ? D.halPracticeOverviewStats() : { hasData: false, stats: [] };
      if (!pack.hasData) {
        return emptyFor(H, "practiceFinancialOverview", "Practice Financial Overview");
      }
      return H.canvasStatGrid(pack.stats || []);
    },
    careDeliveryPerformance(D, H) {
      const pack = D && D.halCareDeliveryStats ? D.halCareDeliveryStats() : { hasData: false, stats: [] };
      if (!pack.hasData) {
        return emptyFor(H, "careDeliveryPerformance", "Care Delivery Performance");
      }
      return H.canvasStatGrid(pack.stats || []);
    },
    narrativeWorkflow(D, H, panel) {
      const printBar = `<div class="composer-toolbar narrative-print-bar">
        <button type="button" class="chip nr2-print-btn" data-nr2-print="narrative" aria-label="Print narrative draft">Print draft</button>
        <button type="button" class="chip chip--ghost nr2-print-btn" data-nr2-print="page" aria-label="Print narratives page">Print page</button>
      </div>`;
      if (panel && panel.type === "kanban") {
        const lanes = D && D.narrativeKanban ? D.narrativeKanban() : [];
        const board = H.canvasKanbanLanes(lanes, "narrativeWorkflow", { narratives: true });
        const hasCards = lanes.some((lane) => lane.items && lane.items.length);
        if (hasCards) return `${printBar}${board}`;
        return `${printBar}${board}${emptyFor(H, "narrativeWorkflow", "Narrative drafts")}`;
      }
      return `${printBar}${emptyFor(H, "narrativeWorkflow", "Narrative drafts")}`;
    },
  };

  const SUBPANEL_BODY = {
    claimsVolumeTrend(D, H) {
      const claims = D && D.allClaims ? D.allClaims() : [];
      if (!claims.length) {
        return emptyFor(H, "claimsVolumeTrend", "Claims volume");
      }
      // Honest open-claims count until dated weekly submission history exists — never invent Week 1–4 bars.
      return H.canvasStat(String(claims.length), "Open claims", undefined, "claimsPipeline");
    },
    claimsPayerBreakdown(D, H) {
      const claims = D && D.allClaims ? D.allClaims() : [];
      const payerMap = {};
      claims.forEach((c) => {
        const p = String(c.payer || "Other").slice(0, 20);
        payerMap[p] = (payerMap[p] || 0) + 1;
      });
      const entries = Object.entries(payerMap).sort((a, b) => b[1] - a[1]).slice(0, 5);
      if (!entries.length) return emptyFor(H, "claimsPayerBreakdown", "Payer breakdown");
      return H.chartContainer(H.vBarChart(entries.map((e) => e[0]), entries.map((e) => e[1]), "#f59e0b"));
    },
    arDistribution(D, H) {
      const payer = D && D.payerDonut ? D.payerDonut() : null;
      return payer ? H.conicDonut(payer.slices, payer.center, 96) : emptyFor(H, "arDistribution", "Payer mix");
    },
    categoryFacets(D, H) {
      return `<input class="search-box" type="search" placeholder="Search library…" aria-label="Search library" /><div class="document-grid"><span class="text-muted">Contracts · Compliance · Insurance</span></div>`;
    },
    taxMemoEvidence(D, H) {
      const citations = D && D.taxMemoCitations ? D.taxMemoCitations() : [];
      const topics = D && D.taxMemoTopics ? D.taxMemoTopics() : [];
      const disclaimer = D && D.taxDisclaimer ? D.taxDisclaimer() : "Read-only planning — CPA review required before filing.";
      const memoItems = citations.length
        ? citations.map((c) => `<li><strong>${H.esc(c.title || c.source || "Citation")}</strong><span>${H.esc(c.detail || c.excerpt || "")}</span></li>`).join("")
        : topics.length
          ? topics.map((t) => `<li><strong>${H.esc(t.title || t.topic || "Topic")}</strong><span>${H.esc(t.summary || t.detail || "")}</span></li>`).join("")
          : `<li><strong>MemoAI evidence</strong><span>Load QuickBooks P&amp;L and run the tax engine to attach IRS and Kansas guidance citations.</span></li>`;
      return `<p class="text-muted">${H.esc(disclaimer)}</p><ul class="ms-tax-memo">${memoItems}</ul>`;
    },
    caseAcceptanceFunnel(D, H) {
      const practice = D && D.practiceStats ? D.practiceStats() : {};
      const ca = H.metricsFromWidget("caseAcceptance");
      const funnelSteps = [
        { label: "Presented", value: ca.plansPresented || practice.treatmentPresented },
        { label: "Accepted", value: ca.plansAccepted || practice.caseAccepted },
        { label: "Scheduled", value: ca.plansScheduled || practice.treatmentScheduled },
        { label: "Completed", value: ca.plansCompleted || practice.treatmentCompleted },
      ];
      const hasAny = funnelSteps.some((s) => s.value != null && s.value !== "" && s.value !== "—" && !/not\s*configured/i.test(String(s.value)));
      if (!hasAny) {
        return emptyFor(H, "treatmentPlanSummary", "Treatment-plan funnel");
      }
      return H.canvasFunnel(funnelSteps.map((s) => ({ label: s.label, value: H.fmtClaim(s.value != null && s.value !== "" ? s.value : "—") })));
    },
    ebitdaFunnel(D, H) {
      const rows = D && D.ebitdaRows ? D.ebitdaRows() : [];
      return rows.length
        ? H.canvasTable(["Adjustment", "Amount", "Reviewer", "Notes"], rows, true)
        : emptyFor(H, "ebitdaNormalization", "EBITDA normalization");
    },
    claimsSidebar(D, H) {
      const claim = D && D.firstClaim ? D.firstClaim() : null;
      return H.canvasClaimSidebar(claim, "claimsPipeline");
    },
    documentsSourceBreakdown(D, H) {
      const stats = D && D.documentsSourceBreakdown ? D.documentsSourceBreakdown() : [];
      return stats.length
        ? H.canvasStatGrid(stats.map((s) => ({ ...s, widgetKey: undefined })))
        : emptyFor(H, "documentsSourceBreakdown", "Source breakdown");
    },
    officeTaskQueue(D, H) {
      const tasks = D && D.officeTaskRows ? D.officeTaskRows() : [];
      return tasks.length
        ? H.canvasTable(["Due", "Category", "Task", "Status"], tasks, true)
        : H.canvasEmpty("Local office tasks will appear when HAL or staff create them.");
    },
  };

  return { render, hasPage, loadManifest, pageSpec };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = MoonshotLayoutEngine;
}
if (typeof globalThis !== "undefined") {
  globalThis.MoonshotLayoutEngine = MoonshotLayoutEngine;
}
