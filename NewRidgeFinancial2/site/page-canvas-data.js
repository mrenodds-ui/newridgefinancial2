/**
 * Maps HAL widget feed + program snapshot into canvas page view models.
 * No mock/demo values — empty states when imports are missing.
 */
const PageCanvasData = (function () {
  let feed = null;
  let snapshot = null;
  let liveIntegrationHealth = null;

  const COLORS = ["#78a86b", "#60a5fa", "#c084fc", "#d6b15e", "#fb923c", "#f472b6"];
  const CLAIM_LANES = ["Draft", "Needs Review", "Ready", "Denied"];
  const TASK_LANE_MAP = {
    billing: "Billing",
    claims: "Billing",
    ar: "Billing",
    revenue: "Owner review",
    accounting: "Owner review",
    data_sources: "Owner review",
    scheduling: "Scheduling",
    sidenotes: "Scheduling",
    other: "General",
  };

  function bind(nextFeed, nextSnapshot) {
    feed = nextFeed || null;
    snapshot = nextSnapshot || null;
  }

  function setLiveIntegrationHealth(payload) {
    liveIntegrationHealth = payload || null;
  }

  function getLiveIntegrationHealth() {
    return liveIntegrationHealth;
  }

  function integrationMetric(id) {
    const health = liveIntegrationHealth;
    const row = health && Array.isArray(health.integrations) ? health.integrations.find((item) => item.id === id) : null;
    return row || null;
  }

  function widget(key) {
    if (!feed || !key) return null;
    return feed.widgets?.[key] || feed.officeWidgets?.[key] || null;
  }

  function dash(pageId) {
    return (snapshot && snapshot.dashboards && snapshot.dashboards[pageId]) || null;
  }

  function metrics(key) {
    const w = widget(key);
    return (w && w.metrics) || {};
  }

  function fmt(value) {
    if (value == null || value === "") return "—";
    if (typeof WidgetContract !== "undefined" && value === WidgetContract.MISSING) return "—";
    return String(value);
  }

  function parseAmount(value) {
    if (typeof value === "number" && Number.isFinite(value)) return value;
    const n = Number(String(value || "").replace(/[$,%]/g, "").replace(/,/g, ""));
    return Number.isFinite(n) ? n : 0;
  }

  function sparkSeries(values) {
    if (!Array.isArray(values) || !values.length) return null;
    const nums = values.map(parseAmount).filter((n) => Number.isFinite(n));
    return nums.length >= 2 ? nums.slice(-5) : null;
  }

  function widgetTone(key) {
    const status = String((widget(key) && widget(key).status) || "").toUpperCase();
    if (status === "SUCCESS") return "success";
    if (status === "DEGRADED") return "warning";
    return undefined;
  }

  function collectionsDisplay(fin, value, fallbackHint) {
    if (fin && fin.collectionsPending) {
      return {
        value: "Pending export",
        hint: "Comparable period export not loaded",
        tone: "warning",
      };
    }
    if (fin && (fin.collectionsMissing || fin.collectionsZeroWithProduction)) {
      return {
        value: "—",
        hint: fin.collectionsMissing
          ? "Collections not reported"
          : "Verify final daysheet export",
        tone: "warning",
      };
    }
    return {
      value: fmt(value),
      hint: fmt(fallbackHint),
      tone: undefined,
    };
  }

  function verifiedArWidgetReady(key) {
    const w = widget(key);
    return String((w && w.status) || "").toUpperCase() === "SUCCESS";
  }

  function periodSubtitle() {
    const fin = dash("financial");
    if (fin && fin.dateRange) return fin.dateRange;
    const sd = dash("softdent");
    if (sd && sd.date) return sd.date;
    if (snapshot && snapshot.label) return snapshot.label;
    return "Awaiting import data";
  }

  function financialKpis() {
    const fin = dash("financial") || {};
    const ov = metrics("practiceFinancialOverview");
    const trend = metrics("financialProductionTrend");
    const payer = metrics("payerMixAndCollections");
    const ar = metrics("arAgingAndCollections");
    const prodSpark = sparkSeries(fin.productionTrend && fin.productionTrend.production);
    const collections = collectionsDisplay(
      fin,
      ov.collectionsTotal,
      ar.aging90PlusPct ? `A/R 90+ ${ar.aging90PlusPct}` : null,
    );
    return [
      {
        label: "Production MTD",
        value: fmt(ov.productionTotal || trend.productionMtd || (fin.productionMtd && fin.productionMtd.value)),
        hint: fin.productionMtd && fin.productionMtd.vs ? fin.productionMtd.vs : fmt(trend.trailingCollectionRate),
        tone: widgetTone("financialProductionTrend"),
        spark: prodSpark,
        widgetKey: "financialProductionTrend",
      },
      {
        label: "Collection rate",
        value: fmt(payer.collectionRate || payer.latestMonthCollectionRate),
        hint: fin.collectionsPending ? "Collections export pending" : fmt(payer.trailingCollectionPeriods),
        tone: fin.collectionsPending ? "warning" : widgetTone("payerMixAndCollections"),
        widgetKey: "payerMixAndCollections",
      },
      {
        label: "QuickBooks net income",
        value: fmt(ov.monthlyNetIncome),
        hint: fmt(ov.monthlyRevenue ? `Revenue ${ov.monthlyRevenue}` : null),
        tone: widgetTone("practiceFinancialOverview"),
        widgetKey: "quickbooksProfitLossDetail",
      },
      {
        label: "SoftDent collections",
        value: collections.value,
        hint: collections.hint,
        tone: collections.tone || widgetTone("practiceFinancialOverview"),
        spark: sparkSeries(fin.productionTrend && fin.productionTrend.average),
        widgetKey: "practiceFinancialOverview",
      },
      {
        label: "SoftDent A/R",
        value: fmt(ar.totalOutstanding),
        hint: fmt(ar.aging90PlusPct ? `90+ ${ar.aging90PlusPct}` : "Outstanding balance"),
        tone: widgetTone("arAgingAndCollections") || "warning",
        widgetKey: "arAgingAndCollections",
      },
    ];
  }

  function softdentKpis() {
    const care = metrics("careDeliveryPerformance");
    const practice = practiceStats();
    const np = metrics("newPatients");
    const ca = metrics("caseAcceptance");
    const fin = dash("financial") || {};
    const prodSpark = sparkSeries(fin.productionTrend && fin.productionTrend.production);
    const collections = collectionsDisplay(fin, care.collectionsTotal, metrics("payerMixAndCollections").collectionRate);
    return [
      {
        label: "Production MTD",
        value: fmt(care.productionTotal || metrics("financialProductionTrend").productionMtd),
        hint: fin.productionMtd && fin.productionMtd.vs ? fin.productionMtd.vs : "SoftDent dashboard",
        tone: widgetTone("careDeliveryPerformance"),
        spark: prodSpark,
        widgetKey: "careDeliveryPerformance",
      },
      {
        label: "Collections",
        value: collections.value,
        hint: collections.hint,
        tone: collections.tone || widgetTone("payerMixAndCollections"),
        widgetKey: "payerMixAndCollections",
      },
      {
        label: "New patients",
        value: fmt(np.newPatientCount || practice.newPatients),
        hint: fmt(np.period || practice.newPatientsHint),
        tone: widgetTone("newPatients"),
        widgetKey: "newPatients",
      },
      {
        label: "Case acceptance",
        value: fmt(ca.acceptanceRate || practice.caseRate),
        hint: practice.treatmentPresented ? `${practice.treatmentPresented} presented` : fmt(ca.plansPresented),
        tone: widgetTone("caseAcceptance"),
        widgetKey: "caseAcceptance",
      },
    ];
  }

  function documentsKpis() {
    const period = metrics("periodCloseAndPosting");
    const ap = metrics("accountsPayableAutomation");
    const docs = snapshot && snapshot.documents;
    const docApi = integrationMetric("documents");
    const postingApi = integrationMetric("posting-queue");
    const queueCount = docs && docs.queueCount != null ? docs.queueCount : null;
    const docDetail = docApi && docApi.detail ? String(docApi.detail).replace(/[^\d]/g, "") : "";
    return [
      {
        label: "Documents in period",
        value: fmt(period.documentsInPeriod || queueCount || docDetail),
        hint: docs && docs.period ? fmt(docs.period) : "Accounting queue",
        tone: widgetTone("documentIntakeQueue"),
        widgetKey: "documentIntakeQueue",
      },
      {
        label: "Posted",
        value: fmt(period.postedPct),
        hint: "Period close",
        tone: "success",
        widgetKey: "periodCloseAndPosting",
      },
      {
        label: "Pending review",
        value: fmt(period.pendingAmount || ap.postingQueuePendingCount || metrics("journalPostingQueue").pendingReview),
        hint: postingApi && postingApi.detail ? postingApi.detail : "Journal queue",
        tone: "warning",
        widgetKey: "journalPostingQueue",
      },
      {
        label: "Expense total",
        value: fmt(ap.expenseTotal),
        hint: "Accounts payable",
        tone: widgetTone("accountsPayableAutomation"),
        widgetKey: "accountsPayableAutomation",
      },
    ];
  }

  function financialQualityTone(fin) {
    if (!fin || (fin.dataSource !== "import" && fin.dataSource !== "persisted")) return "warning";
    if (fin.collectionsMissing || fin.collectionsZeroWithProduction) return "warning";
    if (fin.collectionsPending) return "warning";
    if (fin.periodAlignment && fin.periodAlignment.aligned === false) return "warning";
    if (fin.quality && fin.quality.overallPass === false) return "warning";
    if (fin.quality && fin.quality.overallPass === true && Number(fin.quality.score) >= 70) return "success";
    return undefined;
  }

  function financialQualityDelta(fin) {
    if (fin.collectionsPending) return "Collections export pending";
    if (fin.quality && fin.quality.overallPass === false) return "Quality gate failed";
    if (fin.periodAlignment && fin.periodAlignment.aligned === false) {
      return fin.periodAlignment.message || "Period mismatch";
    }
    if (fin.footer && fin.footer.refreshed) return `Refreshed ${fin.footer.refreshed}`;
    return "Import snapshot";
  }

  function financialCompare() {
    const fin = dash("financial") || {};
    const payer = metrics("payerMixAndCollections");
    const prod = fin.productionMtd || {};
    return [
      { label: "Production MTD", value: fmt(prod.value), delta: fmt(prod.vs || prod.trend), tone: prod.trendDir === "down" ? "warning" : prod.trendDir === "up" ? "success" : undefined },
      { label: "Collection rate", value: fmt(payer.collectionRate), delta: fin.collectionsPending ? "Pending export" : fmt(payer.latestMonthCollectionRate), tone: fin.collectionsPending ? "warning" : widgetTone("payerMixAndCollections") },
      { label: "QuickBooks net", value: fmt(metrics("practiceFinancialOverview").monthlyNetIncome), delta: fmt(metrics("practiceFinancialOverview").monthlyRevenue), tone: widgetTone("quickbooksProfitLossDetail") },
    ];
  }

  function financialWeeklyBars() {
    const fin = dash("financial") || {};
    const trend = fin.productionTrend || {};
    const labels = trend.labels || [];
    const values = (trend.production || []).map(parseAmount);
    if (!labels.length || !values.length) return null;
    const tail = Math.min(4, labels.length);
    return {
      labels: labels.slice(-tail),
      values: values.slice(-tail),
      caption: "SoftDent production trend · trailing periods",
    };
  }

  function financialYtdBars() {
    const ov = metrics("practiceFinancialOverview");
    const qb = dash("quickbooks") || {};
    const pl = (qb.pl && qb.pl.rows) || [];
    const rowVal = (name) => {
      const row = pl.find((r) => String(r.category || "").toLowerCase() === name.toLowerCase());
      return row ? parseAmount(row.amount || row.value) : 0;
    };
    const labels = ["Revenue", "Expenses", "Net income"];
    const values = [
      parseAmount(ov.monthlyRevenue || rowVal("Revenue")),
      parseAmount(rowVal("Operating Expenses") || rowVal("Expenses") || qb.expenses),
      parseAmount(ov.monthlyNetIncome || rowVal("Net Income")),
    ];
    if (!values.some((v) => v > 0)) return null;
    return { labels, values, caption: qb.pl && qb.pl.range ? qb.pl.range : "QuickBooks YTD" };
  }

  function productionTrendSeries() {
    const fin = dash("financial") || {};
    const trend = fin.productionTrend || {};
    const production = (trend.production || []).map(parseAmount);
    const average = (trend.average || []).map(parseAmount);
    if (!production.length) return null;
    return { production, average: average.length ? average : null, max: Math.max(...production, 1) * 1.1 };
  }

  function payerDonut() {
    const fin = dash("financial") || {};
    const mix = fin.payerMix || {};
    const slices = (mix.slices || []).map((s, i) => ({
      label: s.label || "Payer",
      pct: parseAmount(s.pct),
      color: s.color || COLORS[i % COLORS.length],
    }));
    if (!slices.length) return null;
    const center = mix.rate ? `<strong>${escHtml(mix.rate)}</strong><span>Collections</span>` : "";
    return { slices, center };
  }

  function providerBars() {
    const fin = dash("financial") || {};
    const rows = (fin.providers && fin.providers.rows) || [];
    if (!rows.length) return null;
    return {
      items: rows.map((r) => ({ name: r.name, amount: r.amount, pct: parseAmount(r.pct) })),
      total: (fin.providers.total && fin.providers.total.amount) || fmt(metrics("providerPerformance").providerTotal),
    };
  }

  function softdentGlanceStats() {
    const care = metrics("careDeliveryPerformance");
    const payer = metrics("payerMixAndCollections");
    const sd = dash("softdent") || {};
    return [
      { value: fmt(care.patientBalanceTotal), label: "Patient A/R", tone: widgetTone("careDeliveryPerformance") || "warning", widgetKey: "softdentArAging" },
      { value: fmt(payer.collectionRate), label: "Collection rate", tone: widgetTone("payerMixAndCollections"), widgetKey: "payerMixAndCollections" },
      { value: fmt(care.patientCount || glanceValue(sd, "Total Patients")), label: "Active patients", widgetKey: "careDeliveryPerformance" },
      { value: fmt(care.providerCount), label: "Providers loaded", widgetKey: "careDeliveryPerformance" },
    ];
  }

  function glanceValue(sd, label) {
    const row = ((sd && sd.glance) || []).find((g) => g.label === label);
    return row ? row.value : null;
  }

  function softdentAgingBars() {
    if (!verifiedArWidgetReady("softdentArAging")) return null;
    const sd = dash("softdent") || {};
    const aging = sd.aging || [];
    if (!aging.length) return null;
    return {
      labels: aging.map((a) => a.bucket || a.label),
      values: aging.map((a) => parseAmount(a.amount || a.pct)),
    };
  }

  function softdentResponsibilityDonut() {
    if (!verifiedArWidgetReady("softdentResponsibility")) return null;
    const sd = dash("softdent") || {};
    const resp = sd.responsibility || {};
    const ins = parseAmount(resp.insurance && resp.insurance.amount);
    const pat = parseAmount(resp.patient && resp.patient.amount);
    const total = ins + pat;
    if (!total) return null;
    return {
      slices: [
        { label: "Insurance", pct: Math.round((ins / total) * 1000) / 10, color: "#60a5fa" },
        { label: "Patient portion", pct: Math.round((pat / total) * 1000) / 10, color: "#d6b15e" },
      ],
    };
  }

  function practiceStats() {
    const pr = dash("practice") || {};
    const np = metrics("newPatients");
    const tp = metrics("treatmentPlanSummary");
    const ca = metrics("caseAcceptance");
    const hr = metrics("hygieneRecall");
    return {
      newPatients: fmt(np.newPatientCount || pr.newPatients?.count),
      newPatientsHint: fmt(np.period || pr.newPatients?.period),
      treatmentPresented: fmt(tp.presentedValue || tp.plansPresented || pr.treatmentPlans?.presentedValue || pr.treatmentPlans?.presented),
      caseRate: fmt(ca.acceptanceRate || pr.caseAcceptance?.rate),
      caseAccepted:
        ca.acceptedCount != null && ca.presentedCount != null
          ? `${fmt(ca.acceptedCount)} / ${fmt(ca.presentedCount)}`
          : ca.plansAccepted != null && ca.plansPresented != null
            ? `${fmt(ca.plansAccepted)} / ${fmt(ca.plansPresented)}`
            : null,
      treatmentScheduled: fmt(ca.plansScheduled || tp.scheduledCount || pr.treatmentPlans?.scheduled),
      treatmentCompleted: fmt(ca.completedCount || tp.completedCount || pr.treatmentPlans?.completed),
      hygieneCompleted: fmt(hr.hygieneCompleted || pr.hygieneRecall?.completed),
      recallDue: hr.recallDue != null ? `${fmt(hr.recallDue)} recall due` : pr.hygieneRecall?.due != null ? `${fmt(pr.hygieneRecall.due)} recall due` : null,
      hygienePeriod: fmt(hr.period || pr.hygieneRecall?.period),
    };
  }

  function importHealthCards() {
    const sd = dash("softdent") || {};
    const exports = sd.exports || [];
    if (exports.length) {
      return exports.slice(0, 4).map((row, i) => ({
        op: row.dataset || "Export",
        patient: row.name || row.sourceFile || "SoftDent",
        procedure: `${row.records || "0"} records · ${row.status || "—"}`,
        provider: row.source || "SoftDent",
        tone: row.status === "SUCCESS" ? "green" : row.status === "EMPTY" ? "orange" : "blue",
      }));
    }
    const glance = sd.glance || [];
    if (glance.length) {
      return glance.slice(0, 4).map((g, i) => ({
        op: g.label,
        patient: fmt(g.value),
        procedure: sd.source || "SoftDent import",
        provider: sd.status || "Import",
        tone: ["green", "blue", "orange", "blue"][i % 4],
      }));
    }
    return [];
  }

  function importBundleDashboard() {
    const bundle = snapshot && snapshot.importBundle;
    return (bundle && bundle.softdent && bundle.softdent.dashboard) || null;
  }

  function importBundleAgeMinutes() {
    const bundle = snapshot && snapshot.importBundle;
    const syncStatus = bundle && bundle.syncStatus;
    const loadedAt =
      (bundle && bundle.loadedAt) ||
      (syncStatus && (syncStatus.syncedAt || syncStatus.finishedAt || syncStatus.updatedAt)) ||
      null;
    if (!loadedAt) return null;
    const t = Date.parse(String(loadedAt));
    if (!Number.isFinite(t)) return null;
    return Math.max(0, (Date.now() - t) / 60000);
  }

  function withStaleBadge(notice, options) {
    const opts = options || {};
    const maxAgeMinutes = Number(opts.maxAgeMinutes || 60);
    const qb = dash("quickbooks") || {};
    const ageMin = importBundleAgeMinutes();
    const datasetKeys = Array.isArray(opts.datasetKeys) ? opts.datasetKeys : [];
    const datasetStale =
      datasetKeys.length > 0 &&
      datasetIssuesForKeys(datasetKeys).some((item) => item.status === "stale" || item.status === "partial");
    const syncStale = /stale|blocked|pending/i.test(String(qb.syncStatus || qb.lastSync || ""));
    const ageStale = ageMin != null && ageMin > maxAgeMinutes;
    if (!datasetStale && !syncStale && !ageStale) return notice;
    const merged = notice ? Object.assign({}, notice) : {};
    merged.stale = true;
    if (!merged.staleLabel) {
      const ageLabel = ageMin != null ? `${Math.round(ageMin)}m ago` : "stale";
      merged.staleLabel = opts.staleLabel || `Last-known data — last sync ${ageLabel}`;
    }
    return merged;
  }

  function quickbooksSyncStale() {
    const qb = dash("quickbooks") || {};
    const issues = quickbooksDatasetIssues();
    const partial = issues.some((item) => item.status === "stale" || item.status === "partial");
    const ageMin = importBundleAgeMinutes();
    return (
      partial ||
      /stale|blocked|pending/i.test(String(qb.syncStatus || qb.lastSync || "")) ||
      (ageMin != null && ageMin > 60)
    );
  }

  function datasetIssuesForKeys(datasetKeys) {
    const bundle = snapshot && snapshot.importBundle;
    const diagnostics = bundle && bundle.diagnostics;
    const datasets = (diagnostics && diagnostics.datasets) || [];
    const keys = new Set(datasetKeys);
    return datasets.filter((item) => keys.has(item.datasetKey) && item.status !== "connected");
  }

  function financialImportNotice() {
    const fin = dash("financial") || {};
    const bundle = snapshot && snapshot.importBundle;
    const dashboard = importBundleDashboard();
    const readSource = dashboard && dashboard.readSource;
    if (bundle && bundle.directPipelineError) {
      return { tone: "error", message: `Import pipeline: ${bundle.directPipelineError}` };
    }
    if (readSource === "bridge-fallback") {
      const validation = (dashboard && dashboard.bridgeValidation) || {};
      const issues = validation.issues || [];
      return {
        tone: validation.ok ? "info" : "warning",
        message: issues.length
          ? `SoftDent dashboard is from bridge snapshot (not daysheet export): ${issues.join("; ")}`
          : "SoftDent dashboard is from bridge snapshot — export daysheet for authoritative collections.",
      };
    }
    if (fin.periodAlignment && fin.periodAlignment.aligned === false) {
      return {
        tone: "warning",
        message: fin.periodAlignment.message || "SoftDent and QuickBooks periods do not align.",
      };
    }
    if (fin.collectionsPending) {
      return {
        tone: "info",
        message:
          "Collections export is pending for the QuickBooks-comparable period — production is loaded; collection rate may be incomplete.",
      };
    }
    if (fin.collectionsMissing || fin.collectionsZeroWithProduction) {
      return {
        tone: "warning",
        message:
          "SoftDent collections are missing for a period with production — verify final daysheet export before period close.",
      };
    }
    if (fin.quality && fin.quality.overallPass === false) {
      return {
        tone: "warning",
        message:
          "Financial data quality gate failed — review import freshness, collections, period alignment, and QuickBooks P&L reconcile.",
      };
    }
    const overview = widget("practiceFinancialOverview");
    if (overview && overview.status === "FAILED") {
      return {
        tone: "warning",
        message: overview.summary || "Practice financial overview is missing required import data.",
      };
    }
    if (overview && overview.status === "DEGRADED" && overview.summary) {
      return withStaleBadge({ tone: "info", message: overview.summary }, { maxAgeMinutes: 1440, datasetKeys: ["softdent.dashboard", "quickbooks.profitAndLoss"] });
    }
    return withStaleBadge(null, {
      maxAgeMinutes: 1440,
      datasetKeys: ["softdent.dashboard", "quickbooks.profitAndLoss", "quickbooks.revenue"],
    });
  }

  function softdentImportNotice() {
    const dashboard = importBundleDashboard();
    const fin = dash("financial") || {};
    const readSource = dashboard && dashboard.readSource;
    if (readSource === "bridge-fallback") {
      const validation = (dashboard && dashboard.bridgeValidation) || {};
      const issues = validation.issues || [];
      return {
        tone: validation.ok ? "info" : "warning",
        message: issues.length
          ? `Dashboard sourced from bridge snapshot: ${issues.join("; ")}. Export daysheet for authoritative collections.`
          : "Dashboard sourced from bridge snapshot — daysheet export recommended for collections and trend widgets.",
      };
    }
    const issues = datasetIssuesForKeys(["softdent.dashboard", "softdent.claims", "softdent.ar"]);
    if (issues.length) {
      return {
        tone: issues.some((item) => item.status === "missing" || item.status === "not_configured") ? "warning" : "info",
        message: issues
          .slice(0, 3)
          .map((item) => item.detail || item.datasetKey)
          .join(" · "),
      };
    }
    if (fin.collectionsPending) {
      return {
        tone: "info",
        message:
          "Collections export pending for the comparable period — care delivery metrics may omit collections.",
      };
    }
    const care = widget("careDeliveryPerformance");
    if (care && care.status === "FAILED") {
      return withStaleBadge(
        { tone: "warning", message: care.summary || "SoftDent dashboard import not loaded." },
        { maxAgeMinutes: 1440, datasetKeys: ["softdent.dashboard", "softdent.clinical"] },
      );
    }
    return withStaleBadge(null, {
      maxAgeMinutes: 1440,
      datasetKeys: ["softdent.dashboard", "softdent.clinical", "softdent.ar"],
    });
  }

  function arImportNotice() {
    const fin = dash("financial") || {};
    const smart = widget("smartClaimsAndReceivables");
    const aging = widget("arAgingAndCollections");
    const outstanding = widget("arOutstandingClaims");
    const issues = datasetIssuesForKeys(["softdent.ar", "softdent.claims"]);
    if (issues.length) {
      return {
        tone: issues.some((item) => item.status === "missing" || item.status === "not_configured") ? "warning" : "info",
        message: issues
          .slice(0, 3)
          .map((item) => item.detail || item.datasetKey)
          .join(" · "),
      };
    }
    if (fin.arCrossCheck && fin.arCrossCheck.comparable && fin.arCrossCheck.withinTolerance === false) {
      return { tone: "warning", message: fin.arCrossCheck.message || "SoftDent and QuickBooks A/R totals differ beyond tolerance." };
    }
    if (smart && smart.status === "FAILED") {
      return {
        tone: "warning",
        message:
          smart.summary ||
          "Verified A/R source is not loaded — totals stay empty until SoftDent A/R aging export syncs.",
      };
    }
    if (aging && aging.status === "DEGRADED" && aging.summary) {
      return { tone: "info", message: aging.summary };
    }
    if (outstanding && outstanding.status === "FAILED" && !arTopClaimsTable().length) {
      return {
        tone: "warning",
        message:
          outstanding.summary ||
          "Outstanding claim detail will appear when SoftDent claims export includes balances or verified A/R.",
      };
    }
    const hasChart = Boolean(arCollectionsChart());
    const hasClaims = arTopClaimsTable().length > 0;
    if (smart && smart.status !== "SUCCESS" && !hasChart && !hasClaims) {
      return {
        tone: "warning",
        message: "A/R charts stay empty until verified SoftDent A/R aging and claims exports are loaded.",
      };
    }
    return null;
  }

  function claimsImportNotice() {
    const claimsSnap = snapshot && snapshot.claims;
    const pipeline = widget("claimsPipeline");
    const smart = widget("smartClaimsAndReceivables");
    const issues = datasetIssuesForKeys(["softdent.claims"]);
    if (issues.length) {
      return {
        tone: issues.some((item) => item.status === "missing" || item.status === "not_configured") ? "warning" : "info",
        message: issues
          .slice(0, 3)
          .map((item) => item.detail || item.datasetKey)
          .join(" · "),
      };
    }
    if (pipeline && pipeline.status === "FAILED") {
      return {
        tone: "warning",
        message:
          pipeline.summary || "SoftDent claims export not loaded — pipeline lanes stay empty until claims sync.",
      };
    }
    if (pipeline && pipeline.status === "DEGRADED" && pipeline.summary) {
      return { tone: "info", message: pipeline.summary };
    }
    if (smart && smart.status === "DEGRADED" && smart.summary && !(claimsSnap && claimsSnap.total > 0)) {
      return { tone: "info", message: smart.summary };
    }
    const hasKanban = claimsKanban().length > 0;
    const hasClaim = Boolean(firstClaim());
    if (pipeline && pipeline.status !== "SUCCESS" && !hasKanban && !hasClaim) {
      return {
        tone: "warning",
        message: "Claims workbench stays empty until SoftDent claims export is loaded and validated.",
      };
    }
    return null;
  }

  function documentsImportNotice() {
    const docs = snapshot && snapshot.documents;
    const intake = widget("documentIntakeQueue");
    const ap = widget("accountsPayableAutomation");
    const period = widget("periodCloseAndPosting");
    const journal = widget("journalPostingQueue");
    const pending = (docs && docs.posting || []).find((row) => /pending review/i.test(String(row.label || "")));
    const pendingCount = Number((pending && pending.count) || 0);
    if (intake && intake.status === "FAILED" && !(docs && docs.queueCount > 0)) {
      return {
        tone: "warning",
        message:
          intake.summary ||
          "Local document queue is empty — drop accounting documents in the inbox or run document sync.",
      };
    }
    if (pendingCount > 0) {
      return {
        tone: "info",
        message: `${pendingCount} document(s) still Pending Review before posting or period close.`,
      };
    }
    if (period && period.status === "DEGRADED" && period.summary) {
      return { tone: "info", message: period.summary };
    }
    if (journal && journal.status === "FAILED" && !journalRows().length) {
      return {
        tone: "info",
        message: journal.summary || "Journal posting queue is available when Start Program is running and accruals are reviewed.",
      };
    }
    if (ap && ap.status === "DEGRADED" && ap.summary && !(docs && docs.queueCount > 0)) {
      return { tone: "info", message: ap.summary };
    }
    return null;
  }

  function libraryImportNotice() {
    const lib = snapshot && snapshot.library;
    const libraryWidget = widget("documentLibrary");
    const rows = libraryRows();
    if (libraryWidget && libraryWidget.status === "FAILED" && !rows.length) {
      return {
        tone: "warning",
        message:
          libraryWidget.summary ||
          "Document library is empty — index local contracts and compliance files for HAL search.",
      };
    }
    if (libraryWidget && libraryWidget.status === "DEGRADED" && libraryWidget.summary) {
      return { tone: "info", message: libraryWidget.summary };
    }
    if (lib && lib.indexStatus && /error|stale/i.test(String(lib.indexStatus))) {
      return { tone: "warning", message: `Library index status: ${lib.indexStatus}` };
    }
    return null;
  }

  function narrativesImportNotice() {
    const nar = snapshot && snapshot.narratives;
    const workflow = widget("narrativeWorkflow");
    const draft = narrativeDraft();
    const draftCount = Array.isArray(nar && nar.drafts)
      ? nar.drafts.length
      : Number((nar && nar.drafts) || 0);
    if (workflow && workflow.status === "FAILED" && !draft && !draftCount) {
      return {
        tone: "info",
        message:
          workflow.summary ||
          "Narrative composer is local-only — drafts appear after staff capture claim facts from SoftDent.",
      };
    }
    if (workflow && workflow.status === "DEGRADED" && workflow.summary) {
      return { tone: "info", message: workflow.summary };
    }
    if (!draft && !draftCount && !(nar && nar.latest)) {
      return {
        tone: "info",
        message: "No local narrative drafts yet — HAL can help draft for review; nothing submits to payers from this page.",
      };
    }
    return null;
  }

  function taxesImportNotice() {
    const bundle = snapshot && snapshot.importBundle;
    const pipelineError = bundle && bundle.directPipelineError;
    if (pipelineError) {
      return { tone: "error", message: `Import pipeline: ${pipelineError}` };
    }
    const issues = quickbooksDatasetIssues();
    const missing = issues.filter((item) => item.status === "missing" || item.status === "not_configured");
    const hasBook = taxHasBookData();
    const bridge = taxBridgeRows();
    const plWidget = widget("quickbooksProfitLossDetail");
    const ebitdaWidget = widget("ebitdaNormalization");
    if (missing.length && !hasBook) {
      return {
        tone: "warning",
        message: `Book-to-tax bridge needs QuickBooks P&L — ${missing
          .slice(0, 2)
          .map((item) => item.detail || item.datasetKey)
          .join(" · ")}`,
      };
    }
    if (issues.length && !hasBook) {
      return {
        tone: "info",
        message: issues
          .slice(0, 3)
          .map((item) => item.detail || item.datasetKey)
          .join(" · "),
      };
    }
    const feedWidget = plWidget || ebitdaWidget;
    if (feedWidget && feedWidget.status === "FAILED" && !hasBook && !bridge.length) {
      return {
        tone: "warning",
        message:
          feedWidget.summary ||
          "Book-to-tax bridge stays empty until QuickBooks revenue and P&L exports sync.",
      };
    }
    if (feedWidget && feedWidget.status === "DEGRADED" && !hasBook) {
      return {
        tone: "info",
        message:
          feedWidget.summary ||
          "QuickBooks book data is partial — compensation scenarios and quarterly estimates may be placeholders.",
      };
    }
    if (!hasBook && !bridge.length) {
      return {
        tone: "info",
        message: "Tax planning uses QuickBooks book income when available — sync P&L exports for live bridge lines.",
      };
    }
    return null;
  }

  function officeManagerImportNotice() {
    const priorities = widget("officeManagerPriorities") || widget("officeManagerSurfaces");
    const tasks = (snapshot && snapshot.officeTasks) || [];
    const failedWidgets = Object.values((feed && feed.widgets) || {}).filter((w) => {
      const status = String(w.status || "").toUpperCase();
      return status === "FAILED" || status === "DEGRADED";
    });
    if (priorities && priorities.status === "FAILED" && !tasks.length && !failedWidgets.length) {
      return {
        tone: "warning",
        message: priorities.summary || "No HAL attention items yet — widgets may still be waiting on imports.",
      };
    }
    if (failedWidgets.length) {
      return {
        tone: failedWidgets.some((w) => w.status === "FAILED") ? "warning" : "info",
        message: `${failedWidgets.length} widget(s) need attention: ${failedWidgets
          .slice(0, 4)
          .map((w) => w.title || w.key)
          .join(", ")}.`,
      };
    }
    if (priorities && priorities.summary && priorities.status === "DEGRADED") {
      return { tone: "info", message: priorities.summary };
    }
    return null;
  }

  function quickbooksDatasetIssues() {
    const bundle = snapshot && snapshot.importBundle;
    const diagnostics = bundle && bundle.diagnostics;
    const datasets = (diagnostics && diagnostics.datasets) || [];
    const qbKeys = new Set([
      "quickbooks.revenue",
      "quickbooks.expenses",
      "quickbooks.profitAndLoss",
      "quickbooks.expenseCategories",
    ]);
    return datasets.filter((item) => qbKeys.has(item.datasetKey) && item.status !== "connected");
  }

  function quickbooksImportNotice() {
    const qb = dash("quickbooks") || {};
    const bundle = snapshot && snapshot.importBundle;
    const hasPl = quickbooksPlRows().length > 0;
    const hasExpenses = Boolean(quickbooksExpenseBars() || quickbooksExpenseDonut());
    const hasEbitda = ebitdaRows().length > 0;
    const hasAny = hasPl || hasExpenses || hasEbitda;
    const pipelineError = bundle && bundle.directPipelineError;
    if (pipelineError) {
      return { tone: "error", message: `QuickBooks import pipeline: ${pipelineError}` };
    }
    const issues = quickbooksDatasetIssues();
    if (issues.length) {
      const missing = issues.filter((item) => item.status === "missing" || item.status === "not_configured");
      const partial = issues.filter((item) => item.status === "partial" || item.status === "stale");
      const summary = [];
      if (missing.length) summary.push(`${missing.length} export(s) missing`);
      if (partial.length) summary.push(`${partial.length} stale or partial`);
      const detail = issues
        .slice(0, 3)
        .map((item) => item.detail || item.datasetKey)
        .join(" · ");
      return {
        tone: missing.length ? "warning" : "info",
        message: [summary.join("; "), detail].filter(Boolean).join(" — "),
      };
    }
    const plWidget = widget("quickbooksProfitLossDetail");
    const ebitdaWidget = widget("ebitdaNormalization");
    const feedWidget = plWidget || ebitdaWidget;
    if (feedWidget && feedWidget.status === "FAILED" && !hasAny) {
      return {
        tone: "warning",
        message:
          feedWidget.summary ||
          "QuickBooks import not loaded — charts stay empty until revenue, P&L, and expense exports sync.",
      };
    }
    if (feedWidget && feedWidget.status === "DEGRADED" && !hasAny) {
      return {
        tone: "info",
        message: feedWidget.summary || "QuickBooks data is partial — some panels may stay empty until all exports sync.",
      };
    }
    if (!hasAny && qb.dataSource !== "import" && qb.dataSource !== "persisted") {
      return {
        tone: "warning",
        message: "QuickBooks charts populate when revenue, P&L, and expense exports are synced to the import cache.",
      };
    }
    if (!hasAny && (qb.dataSource === "import" || qb.dataSource === "persisted")) {
      return {
        tone: "info",
        message: "QuickBooks import is connected, but P&L rows and expense series are not in the current cache yet.",
      };
    }
    if (/blocked|stale|pending/i.test(String(qb.syncStatus || qb.lastSync || ""))) {
      return withStaleBadge(
        {
          tone: "warning",
          message: `QuickBooks sync status: ${qb.syncStatus || qb.lastSync}. Charts may be incomplete until sync completes.`,
        },
        { maxAgeMinutes: 60, datasetKeys: ["quickbooks.profitAndLoss", "quickbooks.expenses"] },
      );
    }
    if (hasAny && quickbooksSyncStale()) {
      return withStaleBadge(
        {
          tone: "info",
          message: "QuickBooks charts show last-known export values while sync catches up.",
        },
        { maxAgeMinutes: 60, datasetKeys: ["quickbooks.profitAndLoss", "quickbooks.expenses", "quickbooks.expenseCategories"] },
      );
    }
    return withStaleBadge(null, {
      maxAgeMinutes: 60,
      datasetKeys: ["quickbooks.profitAndLoss", "quickbooks.expenses", "quickbooks.expenseCategories"],
    });
  }

  function quickbooksKpis() {
    const qb = dash("quickbooks") || {};
    const pl = metrics("quickbooksProfitLossDetail");
    const ebitda = metrics("ebitdaNormalization");
    const kpis = qb.kpis || [];
    if (kpis.length) {
      return kpis.map((k, i) =>
        Object.assign({}, k, {
          value: fmt(k.value),
          widgetKey: k.widgetKey || (i === kpis.length - 1 ? "ebitdaNormalization" : "quickbooksProfitLossDetail"),
        }),
      );
    }
    return [
      {
        label: "Net income YTD",
        value: fmt(pl.netIncome || qb.netIncomeYtd),
        hint: "QuickBooks P&L",
        tone: widgetTone("quickbooksProfitLossDetail"),
        widgetKey: "quickbooksProfitLossDetail",
      },
      {
        label: "Revenue YTD",
        value: fmt(pl.revenueTotal || pl.totalRevenue || qb.revenueYtd),
        widgetKey: "quickbooksProfitLossDetail",
      },
      {
        label: "Operating expenses",
        value: fmt(pl.operatingExpenses || pl.expenseTotal || qb.expenseYtd),
        tone: widgetTone("quickbooksProfitLossDetail"),
        widgetKey: "quickbooksProfitLossDetail",
      },
      {
        label: "EBITDA add-backs",
        value: fmt(ebitda.ebitdaAddBackTotal || ebitda.candidateTotal),
        hint: fmt(ebitda.expenseCategoriesScope),
        widgetKey: "ebitdaNormalization",
      },
    ];
  }

  function libraryKpis() {
    const lib = snapshot && snapshot.library;
    const m = metrics("documentLibrary");
    const docs = (lib && (lib.docs || lib.top)) || [];
    const contracts = docs.filter((d) => /contract|payer|agreement/i.test(String(d.category || d.type || ""))).length;
    const compliance = docs.filter((d) => /compliance|hipaa|osha|policy/i.test(String(d.category || d.type || ""))).length;
    return [
      {
        label: "Documents indexed",
        value: fmt(lib && lib.results != null ? lib.results : docs.length),
        hint: lib && lib.indexStatus ? String(lib.indexStatus) : "Local library",
        tone: widgetTone("documentLibrary"),
        widgetKey: "documentLibrary",
      },
      {
        label: "Contracts",
        value: fmt(contracts || m.contractCount),
        widgetKey: "documentLibrary",
      },
      {
        label: "Compliance files",
        value: fmt(compliance || m.complianceCount),
        widgetKey: "documentLibrary",
      },
      {
        label: "Expiring soon",
        value: fmt(m.expiringSoonCount || (lib && lib.expiringSoon) || "—"),
        tone: m.expiringSoonCount ? "warning" : undefined,
        widgetKey: "documentLibrary",
      },
    ];
  }

  function quickbooksPlTrend() {
    const qb = dash("quickbooks") || {};
    const monthly = qb.monthlyNetIncome || qb.monthlyPl || qb.monthlyRevenue;
    if (monthly && monthly.labels && monthly.values) {
      return {
        labels: monthly.labels,
        series: [{ name: "Net income", values: monthly.values.map(parseAmount) }],
      };
    }
    const expenseMonthly = qb.monthlyExpenses || {};
    if (expenseMonthly.labels && expenseMonthly.values && expenseMonthly.values.length) {
      return {
        labels: expenseMonthly.labels,
        series: [{ name: "Expenses", values: expenseMonthly.values.map(parseAmount) }],
      };
    }
    return null;
  }

  function softdentOperatoryGrid() {
    const sd = dash("softdent") || {};
    const chairs = sd.operatoryChairs;
    if (Array.isArray(chairs) && chairs.length) return chairs;
    return null;
  }

  function quickbooksPlRows() {
    const qb = dash("quickbooks") || {};
    const rows = (qb.pl && qb.pl.rows) || [];
    return rows.slice(0, 8).map((r) => [r.category || r.label || "—", fmt(r.amount || r.value), fmt(r.vs || r.note || "—")]);
  }

  function quickbooksExpenseBars() {
    const qb = dash("quickbooks") || {};
    const monthly = qb.monthlyExpenses || {};
    const labels = monthly.labels || [];
    const values = (monthly.values || []).map(parseAmount);
    if (!labels.length) return null;
    return { labels, values };
  }

  function quickbooksExpenseDonut() {
    const qb = dash("quickbooks") || {};
    const cats = qb.expenseCategories || {};
    const slices = (cats.slices || []).map((s, i) => ({
      label: s.label || "Category",
      pct: parseAmount(s.pct),
      color: s.color || COLORS[i % COLORS.length],
    }));
    return slices.length ? { slices } : null;
  }

  function ebitdaRows() {
    const qb = dash("quickbooks") || {};
    const candidates = qb.ebitdaCandidates || [];
    if (candidates.length) {
      return candidates.slice(0, 8).map((c) => [
        c.category || c.label || "Add-back",
        fmt(c.amount),
        fmt(c.reviewer || "—"),
        fmt(c.notes || c.status || "—"),
      ]);
    }
    const m = metrics("ebitdaNormalization");
    if (m.ebitdaAddBackTotal || m.ebitdaCandidateCount) {
      return [["EBITDA add-back total", fmt(m.ebitdaAddBackTotal), "HAL", fmt(m.expenseCategoriesScope)]];
    }
    return [];
  }

  function arKpis() {
    const ar = dash("ar") || {};
    const wm = metrics("arAgingAndCollections");
    const kpis = ar.kpis || [];
    if (verifiedArWidgetReady("arAgingAndCollections") && kpis.length) {
      return kpis.map((k, i) => ({
        label: k.label,
        value: fmt(k.value),
        hint: k.hint || "",
        tone: k.tone === "warn" || k.tone === "warning" ? "warning" : k.tone === "green" || k.tone === "success" ? "success" : undefined,
        spark: null,
        widgetKey: ["arAgingAndCollections", "arAgingAndCollections", "arAgingAndCollections", "smartClaimsAndReceivables"][i] || "arAgingAndCollections",
      }));
    }
    return [
      { label: "Total outstanding", value: fmt(wm.totalOutstanding), hint: "Verified A/R", tone: widgetTone("arAgingAndCollections") || "warning", widgetKey: "arAgingAndCollections" },
      { label: "90+ days", value: fmt(wm.aging90PlusPct), hint: "Aging bucket", tone: "warning", widgetKey: "arAgingAndCollections" },
      { label: "Collections MTD", value: fmt(wm.collectionsThisPeriod), hint: "This period", tone: widgetTone("arAgingAndCollections"), widgetKey: "arAgingAndCollections" },
      { label: "Follow-up queue", value: fmt(wm.followUpQueueCount), hint: "Claims needing action", widgetKey: "smartClaimsAndReceivables" },
    ];
  }

  function arCollectionsChart() {
    if (!verifiedArWidgetReady("arAgingAndCollections")) return null;
    const ar = dash("ar") || {};
    const trend = ar.collectionsTrend || {};
    const labels = trend.labels || [];
    const billed = (trend.current || trend.billed || []).map(parseAmount);
    const collected = (trend.prior || trend.collected || []).map(parseAmount);
    if (!labels.length && !billed.length) return null;
    const useLabels = labels.length ? labels : billed.map((_, i) => `P${i + 1}`);
    return {
      labels: useLabels,
      series: [
        { name: "Billed", data: billed.length ? billed : collected, tone: "info" },
        { name: "Collected", data: collected.length ? collected : billed, tone: "success" },
      ],
    };
  }

  function arTopClaimsTable() {
    const ar = dash("ar") || {};
    const rows = ar.topClaims || [];
    const showOutstanding = verifiedArWidgetReady("arOutstandingClaims");
    return rows.slice(0, 10).map((c) => [
      c.patient || "—",
      c.procedure || c.claim || "—",
      c.insurance || "—",
      showOutstanding ? fmt(c.outstanding || c.billed) : "—",
      fmt(c.days),
    ]);
  }

  function arFollowUpKanban() {
    const ar = dash("ar") || {};
    const followUp = ar.followUp || [];
    const showAmounts = verifiedArWidgetReady("arOutstandingClaims");
    if (followUp.length) {
      return followUp.map((lane) => ({
        lane: lane.status || lane.lane || "Follow-up",
        tone: lane.tone === "red" ? "orange" : lane.tone === "warn" ? "orange" : lane.tone || "blue",
        items: (lane.items || []).map((item) => {
          if (typeof item === "string") return item;
          if (!showAmounts) return item.label || item.patient || "—";
          return item.label || "—";
        }),
      }));
    }
    const claims = snapshot && snapshot.claims && snapshot.claims.claims;
    if (!claims || !claims.length) return [];
    const lanes = { "Needs call": [], "Awaiting payer": [], "Ready to close": [] };
    claims.slice(0, 12).forEach((c) => {
      const label = showAmounts
        ? `${c.patient || "Unknown"} · ${fmt(c.amount)}`
        : c.patient || "Unknown";
      if (c.status === "Denied") lanes["Needs call"].push(label);
      else if (c.status === "Ready") lanes["Ready to close"].push(label);
      else lanes["Awaiting payer"].push(label);
    });
    return Object.entries(lanes)
      .filter(([, items]) => items.length)
      .map(([lane, items]) => ({ lane, tone: "muted", items }));
  }

  function claimsKpis() {
    const m = metrics("claimsPipeline");
    const claims = snapshot && snapshot.claims;
    const pipelineTone = widgetTone("claimsPipeline");
    return [
      { label: "Open claims", value: fmt(m.totalClaims || (claims && claims.total)), tone: pipelineTone, spark: null, widgetKey: "claimsPipeline" },
      { label: "Needs review", value: fmt(m.needsReviewCount), tone: m.needsReviewCount ? "warning" : pipelineTone, widgetKey: "claimsPipeline" },
      { label: "Ready", value: fmt(m.readyCount), tone: m.readyCount ? "success" : pipelineTone, widgetKey: "claimsPipeline" },
      { label: "Denied", value: fmt(m.deniedCount), tone: m.deniedCount ? "warning" : pipelineTone, widgetKey: "claimsPipeline" },
    ];
  }

  function claimsKanban() {
    const claims = snapshot && snapshot.claims;
    if (!claims) return [];
    const byLane = claims.byStatus || claims.laneTotals || {};
    if (claims.claims && claims.claims.length) {
      const lanes = {};
      CLAIM_LANES.forEach((lane) => {
        lanes[lane] = claims.claims.filter((c) => c.status === lane).slice(0, 6);
      });
      return CLAIM_LANES.filter((lane) => lanes[lane].length).map((lane) => ({
        lane,
        tone: lane === "Ready" ? "green" : lane === "Denied" ? "orange" : "muted",
        items: lanes[lane],
      }));
    }
    return CLAIM_LANES.filter((lane) => byLane[lane]).map((lane) => ({
      lane,
      tone: "muted",
      items: [`${byLane[lane]} claim(s)`],
    }));
  }

  function firstClaim() {
    const claims = snapshot && snapshot.claims && snapshot.claims.claims;
    return (claims && claims[0]) || null;
  }

  function narrativeDraft() {
    const nar = snapshot && snapshot.narratives;
    const latest = nar && nar.latest;
    if (latest && latest.body) return latest.body;
    if (latest && latest.text) return latest.text;
    return "";
  }

  function narrativeHistoryRows() {
    const nar = snapshot && snapshot.narratives;
    const latest = nar && nar.latest;
    if (latest) {
      return [[fmt(latest.version || "v1"), fmt(latest.modified || latest.date), fmt(latest.focus || nar.focus), fmt(latest.by || "Local")]];
    }
    return [];
  }

  function narrativeKpis() {
    const nar = snapshot && snapshot.narratives;
    const w = widget("narrativeWorkflow");
    const draftCount = typeof nar?.drafts === "number" ? nar.drafts : Array.isArray(nar?.drafts) ? nar.drafts.length : 0;
    return [
      {
        label: "Drafts saved",
        value: fmt(draftCount),
        hint: "Local review only",
        widgetKey: "narrativeWorkflow",
        tone: draftCount ? "success" : undefined,
      },
      {
        label: "Focus mode",
        value: fmt(nar?.focus || (w && w.metrics && w.metrics.focus)),
        widgetKey: "narrativeWorkflow",
      },
      {
        label: "Latest version",
        value: fmt(latestVersionLabel(nar)),
        widgetKey: "narrativeWorkflow",
      },
      {
        label: "Claims source",
        value: fmt(metrics("claimsPipeline").totalClaims),
        hint: "For narrative facts",
        widgetKey: "claimsPipeline",
      },
    ];
  }

  function latestVersionLabel(nar) {
    const latest = nar && nar.latest;
    if (latest && latest.version) return latest.version;
    return draftCountLabel(nar) > 0 ? "Saved" : "—";
  }

  function draftCountLabel(nar) {
    return typeof nar?.drafts === "number" ? nar.drafts : Array.isArray(nar?.drafts) ? nar.drafts.length : 0;
  }

  function documentsSourceBreakdown() {
    const docs = snapshot && snapshot.documents;
    const counts = (docs && docs.sourceCounts) || {};
    return [
      { value: fmt(counts.quickbooks || 0), label: "QuickBooks rows", tone: "default", widgetKey: "documentIntakeQueue" },
      { value: fmt(counts.softdent || 0), label: "SoftDent rows", tone: "default", widgetKey: "documentIntakeQueue" },
      { value: fmt(counts.ocr || 0), label: "OCR inbox", tone: "default", widgetKey: "documentIntakeQueue" },
      { value: fmt(counts.manual || 0), label: "Manual", tone: "default", widgetKey: "documentIntakeQueue" },
    ];
  }

  function opsDataPanelHtml() {
    if (!snapshot) return "";
    const ov = metrics("practiceFinancialOverview");
    const ar = metrics("arAgingAndCollections");
    const claims = metrics("claimsPipeline");
    const docs = snapshot.documents || {};
    const docApi = integrationMetric("documents");
    const postingApi = integrationMetric("posting-queue");
    const docCount =
      docs.queueCount != null
        ? fmt(docs.queueCount)
        : docApi && docApi.detail
          ? fmt(String(docApi.detail).match(/\d+/)?.[0] || "—")
          : "—";
    const postingCount =
      metrics("journalPostingQueue").queueCount && metrics("journalPostingQueue").queueCount !== "—"
        ? metrics("journalPostingQueue").queueCount
        : postingApi && postingApi.detail
          ? fmt(String(postingApi.detail).match(/\d+/)?.[0] || "—")
          : "—";
    const rows = [
      { label: "Production MTD", value: fmt(ov.productionTotal), widgetKey: "practiceFinancialOverview" },
      { label: "Collections", value: fmt(ov.collectionsTotal), widgetKey: "payerMixAndCollections" },
      { label: "Open A/R", value: fmt(ar.totalOutstanding), widgetKey: "arAgingAndCollections" },
      { label: "Open claims", value: fmt(claims.totalClaims), widgetKey: "claimsPipeline" },
      { label: "Documents", value: docCount, widgetKey: "documentIntakeQueue" },
      { label: "Posting queue", value: fmt(postingCount), widgetKey: "journalPostingQueue" },
    ];
    const cards = rows
      .map((row) => {
        const icon = typeof AppIcons !== "undefined" ? AppIcons.widget(row.widgetKey) : "";
        return `<article class="ms-ops-stat ms-ops-data__stat" data-hal-widget-key="${escHtml(row.widgetKey)}" data-hal-cmd="Explain ${escHtml(row.label)}" role="button" tabindex="0">
          <span class="ms-ops-stat__ico">${icon}</span>
          <strong>${escHtml(row.value)}</strong>
          <span>${escHtml(row.label)}</span>
        </article>`;
      })
      .join("");
    return `<section class="widget-card col-12 ms-ops-data" data-hal-widget-key="officeManagerPriorities">
      <div class="widget-header"><span class="widget-title">Practice data</span><span class="ms-muted">Live snapshot · API-backed counts</span></div>
      <div class="ms-stat-grid ms-ops-data__grid">${cards}</div>
      <div class="ms-actions">
        <button type="button" class="ms-button" data-ops-refresh-health="1">Refresh data</button>
        <button type="button" class="ms-button ms-button--primary" data-ops-support-bundle="1">Export support bundle</button>
      </div>
    </section>`;
  }

  function opsHealthPanelHtml() {
    return opsDataPanelHtml();
  }

  function documentsQueueRows() {
    const docs = snapshot && snapshot.documents;
    const rows = (docs && (docs.workbookSample || docs.top)) || [];
    return rows.slice(0, 8).map((d) => [d.vendor || d.type || d.id || "Document", d.type || d.sourceSystem || "—", fmt(d.amount), fmt(d.date || d.status)]);
  }

  function firstDocument() {
    const docs = snapshot && snapshot.documents;
    const rows = (docs && (docs.top || docs.workbookSample)) || [];
    return rows[0] || null;
  }

  function documentsPeriodStats() {
    const docs = snapshot && snapshot.documents;
    const period = metrics("periodCloseAndPosting");
    const ap = metrics("accountsPayableAutomation");
    return [
      { value: fmt(period.documentsInPeriod), label: "Documents in period", tone: widgetTone("periodCloseAndPosting"), widgetKey: "periodCloseAndPosting" },
      { value: fmt(period.postedPct), label: "Posted", tone: "success", widgetKey: "periodCloseAndPosting" },
      { value: fmt(period.pendingAmount || ap.postingQueuePendingCount), label: "Pending review", tone: "warning", widgetKey: "journalPostingQueue" },
      { value: fmt(ap.expenseTotal), label: "Expense total", tone: "warning", widgetKey: "accountsPayableAutomation" },
    ];
  }

  function journalRows() {
    const m = metrics("journalPostingQueue");
    if (m.queueCount && m.queueCount !== "—") {
      return [
        ["Pending review", fmt(m.pendingReview), "Journal queue", "Local"],
        ["Ready to export", fmt(m.readyToExport), "Journal queue", "Local"],
      ];
    }
    return [];
  }

  function journalQueueItems() {
    const jq = snapshot && snapshot.journalPostingQueue;
    return Array.isArray(jq && jq.items) ? jq.items : [];
  }

  function monthEndBlockerStripHtml() {
    if (typeof MonthEndClose === "undefined" || !MonthEndClose.renderBlockerStripHtml || !snapshot) return "";
    const payload = MonthEndClose.buildReconciliationPayload(snapshot);
    return MonthEndClose.renderBlockerStripHtml(payload.checklist, escHtml);
  }

  function monthEndChecklistHtml() {
    if (typeof MonthEndClose === "undefined" || !MonthEndClose.renderChecklistHtml || !snapshot) return "";
    const payload = MonthEndClose.buildReconciliationPayload(snapshot);
    return MonthEndClose.renderChecklistHtml(payload.checklist, escHtml);
  }

  function monthEndReconciliationPayload() {
    if (typeof MonthEndClose === "undefined" || !MonthEndClose.buildReconciliationPayload || !snapshot) return null;
    return MonthEndClose.buildReconciliationPayload(snapshot);
  }

  function libraryRows() {
    const lib = snapshot && snapshot.library;
    const docs = (lib && (lib.docs || lib.top)) || [];
    return docs.slice(0, 10).map((d) => [d.title || d.name || d.id || "Document", d.category || d.type || "—", fmt(d.updated || d.date), fmt(d.expires || "—")]);
  }

  function firstLibraryDoc() {
    const lib = snapshot && snapshot.library;
    const docs = (lib && (lib.docs || lib.top)) || [];
    return docs[0] || null;
  }

  function officeKpis() {
    const ov = metrics("practiceFinancialOverview");
    const ar = metrics("arAgingAndCollections");
    const np = metrics("newPatients");
    return [
      { label: "Production MTD", value: fmt(ov.productionTotal), hint: "Owner dashboard", tone: widgetTone("practiceFinancialOverview"), widgetKey: "practiceFinancialOverview" },
      { label: "Open A/R", value: fmt(ar.totalOutstanding), hint: "Verified receivables", tone: "warning", widgetKey: "arAgingAndCollections" },
      { label: "Open claims", value: fmt(metrics("claimsPipeline").totalClaims), hint: "Claims workbench", tone: widgetTone("claimsPipeline"), widgetKey: "claimsPipeline" },
      { label: "New patients", value: fmt(np.newPatientCount), hint: "Practice performance", widgetKey: "newPatients" },
    ];
  }

  function officeKanban() {
    const tasks = (snapshot && snapshot.officeTasks) || [];
    if (tasks.length) {
      const lanes = {};
      tasks.slice(0, 20).forEach((task) => {
        const lane = TASK_LANE_MAP[task.category] || "General";
        if (!lanes[lane]) lanes[lane] = [];
        lanes[lane].push(task.title || "Task");
      });
      return Object.entries(lanes).map(([lane, items]) => ({
        lane,
        tone: lane === "Billing" ? "orange" : lane === "Scheduling" ? "blue" : "green",
        items: items.slice(0, 5),
      }));
    }
    const failed = Object.values((feed && feed.widgets) || {}).filter((w) => {
      const s = String(w.status || "").toUpperCase();
      return s === "FAILED" || s === "DEGRADED";
    });
    if (failed.length) {
      return [
        {
          lane: "Billing focus",
          tone: "orange",
          items: failed.slice(0, 6).map((w) => `${w.title || w.key}: ${formatMetricsLine(w)}`),
        },
      ];
    }
    return [];
  }

  function formatMetricsLine(widget) {
    if (!widget || !widget.metrics) return "Review";
    const entries = Object.entries(widget.metrics).filter(([, v]) => v != null && v !== "" && v !== "—");
    if (!entries.length) return "Review";
    return entries
      .slice(0, 2)
      .map(([k, v]) => `${k} ${v}`)
      .join(" · ");
  }

  function officeTaskRows() {
    const tasks = (snapshot && snapshot.officeTasks) || [];
    return tasks.slice(0, 8).map((t) => [
      fmt(t.dueHint || t.dueDate || "—"),
      fmt(t.patientLabel || t.category || "—"),
      t.title || "—",
      fmt(t.assignedTo || t.status || "open"),
    ]);
  }

  function taxPlan() {
    if (typeof TaxEngine !== "undefined" && TaxEngine.buildTaxPlanFromSnapshot) {
      return TaxEngine.buildTaxPlanFromSnapshot(snapshot, feed);
    }
    return null;
  }

  function fmtTaxMoney(value) {
    if (typeof TaxEngine !== "undefined" && TaxEngine.formatMoney) return TaxEngine.formatMoney(value);
    return fmt(value);
  }

  function taxKpis() {
    const plan = taxPlan();
    if (plan && plan.kpis && plan.kpis.length) {
      return plan.kpis.map((k) => Object.assign({}, k, { widgetKey: k.widgetKey || "quickbooksProfitLossDetail" }));
    }
    return [
      { label: "Book net income", value: fmt(metrics("quickbooksProfitLossDetail").netIncome || metrics("practiceFinancialOverview").monthlyNetIncome), tone: widgetTone("quickbooksProfitLossDetail"), hint: "QuickBooks P&L", widgetKey: "quickbooksProfitLossDetail" },
      { label: "Annualized book", value: fmtTaxMoney(parseAmount(metrics("practiceFinancialOverview").monthlyNetIncome) * 12), tone: "info", hint: "Planning estimate", widgetKey: "ebitdaNormalization" },
      { label: "Federal est.", value: "Planning", tone: "info", hint: "CPA review required", widgetKey: "quickbooksProfitLossDetail" },
      { label: "Kansas est.", value: "Planning", tone: "info", hint: "K-120S · K-40", widgetKey: "quickbooksProfitLossDetail" },
    ];
  }

  function taxBridgeRows() {
    const plan = taxPlan();
    if (!plan || !plan.bridgeLines) return [];
    return plan.bridgeLines.map((row) => [row.line, fmtTaxMoney(row.amount)]);
  }

  function taxCompScenarioRows() {
    const plan = taxPlan();
    if (!plan || !plan.compScenarios) return [];
    return plan.compScenarios.map((s) => [
      fmtTaxMoney(s.salary),
      fmtTaxMoney(s.k1Ordinary),
      fmtTaxMoney(s.employerFica),
      s.selected ? `${s.note} · selected` : s.note,
    ]);
  }

  function taxQuarterlyRows() {
    const plan = taxPlan();
    if (!plan || !plan.quarterlyEstimates) return [];
    return plan.quarterlyEstimates.map((q) => [
      q.period,
      fmtTaxMoney(q.federal),
      fmtTaxMoney(q.kansas),
      q.due,
      q.status,
    ]);
  }

  function taxSplit() {
    const plan = taxPlan();
    return (plan && plan.taxSplit) || [];
  }

  function taxMemoCitations() {
    const plan = taxPlan();
    return (plan && plan.memoCitations) || [];
  }

  function taxDisclaimer() {
    const plan = taxPlan();
    return (plan && plan.disclaimer) || "Read-only planning — CPA review required before filing.";
  }

  function taxHasBookData() {
    const plan = taxPlan();
    return Boolean(plan && plan.hasBookData);
  }

  function taxFederalRows() {
    return [
      ["Form 1120-S", "U.S. S corporation return", "Mar 15 (or extension)", "File with IRS; issue Schedule K-1 to shareholders"],
      ["Schedule K-1", "Shareholder income allocation", "With 1120-S", "Ordinary income, wages, distributions flow to owner 1040"],
      ["Reasonable compensation", "Owner-dentist W-2 wages", "Payroll ongoing", "IRS scrutinizes low salary / high distributions"],
      ["Payroll taxes", "FICA on officer wages", "Semi-weekly / quarterly", "S corp wages subject to FICA; distributions are not"],
      ["Section 199A (QBI)", "Qualified business income deduction", "Owner 1040", "W-2 wages and UBIA limit may apply to dental S corp"],
      ["Estimated tax (1040-ES)", "Owner tax on K-1 income", "Apr / Jun / Sep / Jan", "Pass-through income taxed on shareholder return"],
      ["Section 179 / bonus", "Equipment expensing", "With return", "Dental equipment and technology may qualify—verify with CPA"],
      ["Built-in gains / AAA", "Accumulated adjustments account", "With return", "Track AAA for distribution taxability"],
    ];
  }

  function taxKansasRows() {
    return [
      ["Form K-120S", "Kansas S corporation return", "Apr 15 (or extension)", "State counterpart to federal 1120-S"],
      ["K-1 (Kansas)", "Shareholder state allocation", "With K-120S", "Kansas ordinary income flows to owner Kansas return"],
      ["Kansas individual (K-40)", "Owner return on K-1 income", "Apr 15 (or extension)", "Report Kansas share of S corp income"],
      ["PTE tax election", "Pass-through entity tax", "Annual election", "Kansas allows PTE tax election—evaluate with CPA vs individual credit"],
      ["Kansas estimated tax", "Owner quarterly estimates", "Apr / Jun / Sep / Jan", "If Kansas tax owed after withholding/credits"],
      ["Withholding (if applicable)", "Non-resident shareholders", "Per KDOR rules", "Review if owners live outside Kansas"],
      ["Sales / use tax", "Taxable goods", "Monthly / quarterly", "Most dental professional services exempt; taxable supplies may apply"],
    ];
  }

  function taxCalendarRows() {
    return [
      ["Jan 31", "Federal", "W-2 / 1099 issuance to employees and vendors"],
      ["Mar 15", "Federal", "Form 1120-S due (or file extension Form 7004)"],
      ["Apr 15", "Federal / Kansas", "Owner 1040 and 1040-ES Q1; Kansas K-120S and K-40 if calendar year"],
      ["Jun 15", "Federal / Kansas", "1040-ES Q2 estimated payment"],
      ["Sep 15", "Federal / Kansas", "1040-ES Q3; extended 1120-S if on extension"],
      ["Oct 15", "Federal", "Extended individual 1040 if on extension"],
      ["Jan 15", "Federal / Kansas", "1040-ES Q4 estimated payment"],
    ];
  }

  function taxMemoTopics() {
    return [
      { topic: "Federal 1120-S & K-1", scope: "Federal S corp return and shareholder allocations" },
      { topic: "Reasonable compensation", scope: "Owner-dentist W-2 vs distributions" },
      { topic: "Section 199A QBI", scope: "Pass-through deduction limits for dental practices" },
      { topic: "Estimated taxes", scope: "1040-ES for shareholder K-1 income" },
      { topic: "Kansas K-120S", scope: "Kansas S corporation return" },
      { topic: "Kansas PTE tax", scope: "Pass-through entity tax election" },
      { topic: "Kansas owner K-40", scope: "Individual flow-through reporting" },
      { topic: "Equipment §179", scope: "Dental capex expensing review points" },
      { topic: "NR2 Taxes page", scope: "HAL read-only tax guidance boundary" },
    ];
  }

  function taxBookIncomeRows() {
    const plRows = quickbooksPlRows();
    if (!plRows.length) return [];
    return plRows.slice(0, 6);
  }

  function taxEbitdaRows() {
    return ebitdaRows().slice(0, 5);
  }

  function officeTimeline() {
    const tasks = (snapshot && snapshot.officeTasks) || [];
    return tasks.slice(0, 4).map((t, i) => ({
      time: fmt(t.category || "Task"),
      title: t.title || "—",
      detail: t.description || t.notes || fmt(t.status),
      active: i === 0,
    }));
  }

  function analyticsApi() {
    return typeof NR2Analytics !== "undefined" ? NR2Analytics : null;
  }

  function nr2ProductionReconciliation() {
    const A = analyticsApi();
    return A ? A.productionReconciliation(snapshot) : { rows: [], hasData: false };
  }

  function nr2CollectionLag() {
    const A = analyticsApi();
    return A ? A.collectionLag(snapshot) : { avgLagDays: null, hasData: false };
  }

  function quickbooksMonthlyRevenueSeries() {
    const A = analyticsApi();
    return A ? A.quickbooksMonthlyRevenue(snapshot) : { labels: [], values: [], hasData: false };
  }

  function softdentProductionDailySeries() {
    const A = analyticsApi();
    return A ? A.softdentProductionDaily(snapshot) : { points: [], hasData: false, granularity: "none" };
  }

  function nr2KpiRibbonTiles() {
    const A = analyticsApi();
    return A ? A.kpiRibbon(snapshot) : { tiles: [], hasData: false };
  }

  function qbReportsApi() {
    return typeof NR2QbReports !== "undefined" ? NR2QbReports : null;
  }

  function softdentDailyApi() {
    return typeof NR2SoftdentDaily !== "undefined" ? NR2SoftdentDaily : null;
  }

  function quickbooksBalanceSheetSummary() {
    const Q = qbReportsApi();
    return Q ? Q.balanceSheetSummary(snapshot) : { hasData: false, assets: [] };
  }

  function quickbooksCashFlowTrend() {
    const Q = qbReportsApi();
    return Q ? Q.cashFlowTrend(snapshot) : { hasData: false, labels: [], net: [] };
  }

  function quickbooksNetIncomeSummary() {
    const Q = qbReportsApi();
    return Q ? Q.netIncomeSummary(snapshot) : { hasData: false };
  }

  function quickbooksRevenueByService() {
    const Q = qbReportsApi();
    return Q ? Q.revenueByService(snapshot) : { hasData: false, slices: [] };
  }

  function quickbooksQbArAging() {
    const Q = qbReportsApi();
    return Q ? Q.arAging(snapshot) : { hasData: false, buckets: [] };
  }

  function softdentCollectionsDailySeries() {
    const S = softdentDailyApi();
    return S ? S.collectionsDaily(snapshot) : { hasData: false, labels: [], values: [] };
  }

  function softdentNewPatientsMtdData() {
    const S = softdentDailyApi();
    return S ? S.newPatientsMtd(snapshot) : { hasData: false, count: 0 };
  }

  function softdentClaimsOutstandingData() {
    const S = softdentDailyApi();
    return S ? S.claimsOutstanding(snapshot) : { hasData: false, claims: [] };
  }

  function softdentProviderProductionData() {
    const S = softdentDailyApi();
    return S ? S.providerProduction(snapshot) : { hasData: false, providers: [] };
  }

  function softdentAppointmentsSnapshotData() {
    const S = softdentDailyApi();
    return S ? S.appointmentsSnapshot(snapshot) : { hasData: false, appointments: [] };
  }

  function escHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  return {
    bind,
    setLiveIntegrationHealth,
    getLiveIntegrationHealth,
    periodSubtitle,
    financialKpis,
    softdentKpis,
    documentsKpis,
    financialCompare,
    financialWeeklyBars,
    financialYtdBars,
    productionTrendSeries,
    payerDonut,
    providerBars,
    softdentGlanceStats,
    softdentAgingBars,
    softdentResponsibilityDonut,
    practiceStats,
    importHealthCards,
    financialImportNotice,
    softdentImportNotice,
    arImportNotice,
    claimsImportNotice,
    documentsImportNotice,
    libraryImportNotice,
    officeManagerImportNotice,
    narrativesImportNotice,
    taxesImportNotice,
    quickbooksImportNotice,
    quickbooksSyncStale,
    withStaleBadge,
    importBundleAgeMinutes,
    quickbooksKpis,
    quickbooksPlTrend,
    softdentOperatoryGrid,
    libraryKpis,
    quickbooksPlRows,
    quickbooksExpenseBars,
    quickbooksExpenseDonut,
    ebitdaRows,
    arKpis,
    arCollectionsChart,
    arTopClaimsTable,
    arFollowUpKanban,
    claimsKpis,
    claimsKanban,
    firstClaim,
    narrativeDraft,
    narrativeHistoryRows,
    narrativeKpis,
    documentsQueueRows,
    firstDocument,
    documentsPeriodStats,
    journalRows,
    journalQueueItems,
    monthEndBlockerStripHtml,
    monthEndChecklistHtml,
    monthEndReconciliationPayload,
    documentsSourceBreakdown,
    opsHealthPanelHtml,
    opsDataPanelHtml,
    libraryRows,
    firstLibraryDoc,
    officeKpis,
    officeKanban,
    officeTaskRows,
    officeTimeline,
    taxKpis,
    taxPlan,
    taxBridgeRows,
    taxCompScenarioRows,
    taxQuarterlyRows,
    taxSplit,
    taxMemoCitations,
    taxDisclaimer,
    taxHasBookData,
    taxFederalRows,
    taxKansasRows,
    taxCalendarRows,
    taxMemoTopics,
    taxBookIncomeRows,
    taxEbitdaRows,
    nr2ProductionReconciliation,
    nr2CollectionLag,
    quickbooksMonthlyRevenueSeries,
    softdentProductionDailySeries,
    nr2KpiRibbonTiles,
    quickbooksBalanceSheetSummary,
    quickbooksCashFlowTrend,
    quickbooksNetIncomeSummary,
    quickbooksRevenueByService,
    quickbooksQbArAging,
    softdentCollectionsDailySeries,
    softdentNewPatientsMtdData,
    softdentClaimsOutstandingData,
    softdentProviderProductionData,
    softdentAppointmentsSnapshotData,
    fmt,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = PageCanvasData;
}
if (typeof globalThis !== "undefined") {
  globalThis.PageCanvasData = PageCanvasData;
}
if (typeof window !== "undefined") {
  window.PageCanvasData = PageCanvasData;
}
