/**
 * Maps HAL widget feed + program snapshot into canvas page view models.
 * No mock/demo values — empty states when imports are missing.
 */
const PageCanvasData = (function () {
  let feed = null;
  let snapshot = null;
  let liveIntegrationHealth = null;
  let selectedClaimId = null;

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
      const prior = latestReportedCollections();
      if (prior && prior.value > 0) {
        return {
          value: fmtMoney(prior.value),
          hint: `Latest SoftDent collections · ${prior.period} (current period export pending)`,
          tone: "warning",
          period: prior.period,
          pendingCurrent: true,
        };
      }
      return {
        value: "Pending export",
        hint: "Comparable period export not loaded",
        tone: "warning",
        pendingCurrent: true,
      };
    }
    if (fin && (fin.collectionsMissing || fin.collectionsZeroWithProduction)) {
      const prior = latestReportedCollections();
      if (prior && prior.value > 0) {
        return {
          value: fmtMoney(prior.value),
          hint: `Latest SoftDent collections · ${prior.period}`,
          tone: "warning",
          period: prior.period,
        };
      }
      return {
        value: "—",
        hint: fin.collectionsMissing
          ? "Collections not reported"
          : "Verify final daysheet export",
        tone: "warning",
      };
    }
    if (value != null && value !== "" && value !== "—") {
      return {
        value: fmt(value),
        hint: fmt(fallbackHint),
        tone: undefined,
      };
    }
    const prior = latestReportedCollections();
    if (prior && prior.value > 0) {
      return {
        value: fmtMoney(prior.value),
        hint: `SoftDent collections · ${prior.period}`,
        tone: undefined,
        period: prior.period,
      };
    }
    return {
      value: fmt(value),
      hint: fmt(fallbackHint),
      tone: undefined,
    };
  }

  function fmtMoney(amount) {
    const n = Number(amount);
    if (!Number.isFinite(n)) return "—";
    return `$${Math.round(n).toLocaleString()}`;
  }

  function latestReportedCollections() {
    const series = softdentCollectionsDailySeries();
    if (!series || !series.hasData || !Array.isArray(series.labels) || !Array.isArray(series.values)) {
      return null;
    }
    for (let i = series.labels.length - 1; i >= 0; i -= 1) {
      const value = Number(series.values[i]);
      if (Number.isFinite(value) && value > 0) {
        return { period: String(series.labels[i] || ""), value };
      }
    }
    return null;
  }

  function verifiedArWidgetReady(key) {
    const w = widget(key);
    const status = String((w && w.status) || "").toUpperCase();
    if (status === "SUCCESS") return true;
    if (status !== "DEGRADED") return false;
    // SoftDent can stay DEGRADED while collections are pending, but still have
    // verified A/R metrics. Policy-nullified metrics mean the source is withheld.
    const m = (w && w.metrics) || {};
    const present = (value) => value != null && value !== "" && value !== "—";
    if (key === "softdentArAging") return present(m.totalAr) || present(m.currentBucket);
    if (key === "softdentResponsibility") {
      return present(m.insuranceAmount) || present(m.patientAmount);
    }
    if (key === "arAgingAndCollections") return present(m.totalOutstanding);
    if (key === "arOutstandingClaims") return present(m.topClaimOutstanding) || present(m.openClaimCount);
    return true;
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
    const ribbon = nr2KpiRibbonTiles();
    const goal = nr2GoalScorecard();
    const lag = nr2CollectionLag();
    const prodSpark = sparkSeries(fin.productionTrend && fin.productionTrend.production);
    const collections = collectionsDisplay(
      fin,
      ov.collectionsTotal,
      payer.collectionRate ? `Rate ${payer.collectionRate}` : null,
    );
    const dsoTile = (ribbon.tiles || []).find((t) => /dso|days|ar/i.test(String(t.label || "")));
    const dsoValue = lag.hasData && lag.avgLagDays != null ? String(lag.avgLagDays) : dsoTile ? dsoTile.value : "—";
    return [
      {
        label: "Production MTD",
        value: fmt(ov.productionTotal || trend.productionMtd || (fin.productionMtd && fin.productionMtd.value)),
        hint: fin.productionMtd && fin.productionMtd.vs ? fin.productionMtd.vs : fmt(trend.trailingCollectionRate),
        tone: widgetTone("practiceFinancialOverview"),
        spark: prodSpark,
        widgetKey: "practiceFinancialOverview",
      },
      {
        label: collections.period ? `Collections (${collections.period})` : "Collections MTD",
        value: collections.value,
        hint: collections.hint,
        tone: collections.tone || widgetTone("softdentCollectionsDaily"),
        // SoftDent collections series / overview — not production-trend.
        widgetKey: "softdentCollectionsDaily",
      },
      {
        label: (() => {
          const net = quickbooksNetIncomeSummary();
          if (net && net.hasData && net.ytdNetIncome != null) return "Net Income YTD";
          if (net && net.latestMonth) return `Net Income (${net.latestMonth})`;
          return "Net Income YTD";
        })(),
        value: (() => {
          const net = quickbooksNetIncomeSummary();
          if (net && net.hasData && net.ytdNetIncome != null) return fmt(net.ytdNetIncome);
          return fmt(ov.monthlyNetIncome);
        })(),
        hint: (() => {
          const net = quickbooksNetIncomeSummary();
          if (net && net.hasData && net.monthCount != null) return `${net.monthCount} QB month${net.monthCount === 1 ? "" : "s"}`;
          return fmt(ov.monthlyRevenue ? `Revenue ${ov.monthlyRevenue}` : null);
        })(),
        tone: widgetTone("quickbooksNetIncomeSummary"),
        // QuickBooks net income — not payer-mix.
        widgetKey: "quickbooksNetIncomeSummary",
      },
      {
        label: "A/R Days",
        value: dsoValue,
        hint: lag.dsoProxy
          ? "Weighted DSO"
          : lag.priorPeriodProxy
            ? lag.caption || `Proxy from ${lag.period}`
            : lag.hasData
              ? "Monthly proxy"
              : "Cross-analytics",
        tone: widgetTone("nr2CollectionLag"),
        // Collection lag / DSO — not the KPI ribbon container.
        widgetKey: "nr2CollectionLag",
      },
      {
        label: "Goal Attainment",
        value: goal.hasData && goal.pctOfGoal != null ? `${goal.pctOfGoal}%` : goal.hasData && goal.needsGoal ? "Set goal" : "—",
        hint: goal.hasData && goal.pctOfGoal != null
          ? "YTD production vs goal"
          : goal.needsGoal
            ? "Set NR2_GOAL_PRODUCTION_YTD"
            : "—",
        tone: goal.tone || widgetTone("nr2GoalScorecard"),
        widgetKey: "nr2GoalScorecard",
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
        label: collections.period ? `Collections (${collections.period})` : "Collections",
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
        value: (() => {
          const rate = ca.acceptanceRate != null ? ca.acceptanceRate : practice.caseRate;
          if (rate == null || rate === "" || rate === "—" || /not\s*configured/i.test(String(rate))) return "—";
          return fmt(rate);
        })(),
        hint: practice.treatmentPresented ? `${practice.treatmentPresented} presented` : fmt(ca.plansPresented),
        tone: widgetTone("caseAcceptance"),
        widgetKey: "caseAcceptance",
      },
    ];
  }

  function softdentHeroKpis() {
    const care = metrics("careDeliveryPerformance");
    const ov = metrics("practiceFinancialOverview");
    const trend = metrics("financialProductionTrend");
    const fin = dash("financial") || {};
    const np = softdentNewPatientsMtdData();
    const coll = softdentCollectionsDailySeries();
    const co = softdentClaimsOutstandingData();
    const collTotal =
      coll.hasData && coll.values.length ? coll.values.reduce((s, v) => s + (Number(v) || 0), 0) : null;
    const production =
      care.productionTotal ||
      care.productionMtd ||
      ov.productionTotal ||
      trend.productionMtd ||
      (fin.productionMtd && fin.productionMtd.value);
    return [
      {
        label: "Production MTD",
        value: fmt(production || "—"),
        hint: (fin.productionMtd && fin.productionMtd.vs) || care.vsPrior || "SoftDent dashboard",
        widgetKey: "careDeliveryPerformance",
        tone: widgetTone("careDeliveryPerformance"),
      },
      {
        label: np.period ? `New Patients (${np.period})` : "New Patients",
        value: np.hasData ? fmt(np.count) : "—",
        hint: np.period ? String(np.period) : "SoftDent export",
        widgetKey: "softdentNewPatientsMTD",
        tone: widgetTone("softdentNewPatientsMTD"),
      },
      {
        label: "Collections Trend",
        value: collTotal != null ? `$${Math.round(collTotal).toLocaleString()}` : "—",
        hint: coll.hasData ? "Daily series" : "—",
        widgetKey: "softdentCollectionsDaily",
        tone: widgetTone("softdentCollectionsDaily"),
      },
      {
        label: "Outstanding Claims",
        value: co.claims && co.claims.length ? String(co.claims.length) : "—",
        hint:
          co.claims && co.claims.length
            ? `$${Math.round(co.claims.reduce((s, c) => s + (parseAmount(c.balance || c.amount) || 0), 0)).toLocaleString()}`
            : "—",
        widgetKey: "softdentClaimsOutstanding",
        tone: widgetTone("softdentClaimsOutstanding"),
      },
    ];
  }

  function softdentAppointmentStats() {
    const appt = softdentAppointmentsSnapshotData();
    if (!appt.hasData || !appt.appointments.length) {
      return [];
    }
    const counts = { checkedIn: 0, inProgress: 0, completed: 0, noShows: 0 };
    appt.appointments.forEach((a) => {
      const st = String(a.status || "").toLowerCase();
      if (st.includes("complete")) counts.completed += 1;
      else if (st.includes("progress") || st.includes("seated")) counts.inProgress += 1;
      else if (st.includes("no") && st.includes("show")) counts.noShows += 1;
      else counts.checkedIn += 1;
    });
    return [
      { value: fmt(counts.checkedIn), label: "Checked in" },
      { value: fmt(counts.inProgress), label: "In progress" },
      { value: fmt(counts.completed), label: "Completed" },
      { value: fmt(counts.noShows), label: "No-shows" },
    ];
  }

  function softdentArAgingHeatmap() {
    const aging = softdentAgingBars();
    if (!aging || !aging.labels || !aging.labels.length) return null;
    return {
      rowLabels: ["Practice"],
      colLabels: aging.labels,
      matrix: [aging.values.map((v) => Math.round(Number(v) || 0))],
    };
  }

  function treatmentPlanFunnel() {
    const practice = practiceStats();
    const ca = metrics("caseAcceptance");
    return [
      { label: "Presented", value: fmt(ca.plansPresented || practice.treatmentPresented) },
      { label: "Accepted", value: fmt(ca.plansAccepted || practice.caseAccepted) },
      { label: "Scheduled", value: fmt(ca.plansScheduled || practice.treatmentScheduled) },
      { label: "Completed", value: fmt(ca.plansCompleted || practice.treatmentCompleted) },
    ];
  }

  function hygieneRecallGauge() {
    const practice = practiceStats();
    const hr = metrics("hygieneRecall");
    let rate = hr.recallRate != null && hr.recallRate !== "" && hr.recallRate !== "—" ? hr.recallRate : null;
    if (rate == null) {
      const completed = Number(
        hr.hygieneCompleted != null
          ? hr.hygieneCompleted
          : practice.hygieneCompleted != null && practice.hygieneCompleted !== "—"
            ? practice.hygieneCompleted
            : NaN,
      );
      const dueRaw = hr.recallDue != null ? hr.recallDue : practice.recallDueCount;
      const due = Number(dueRaw);
      if (Number.isFinite(completed) && Number.isFinite(due) && completed + due > 0) {
        rate = Math.round((completed / (completed + due)) * 1000) / 10;
      }
    }
    if (typeof rate === "string" && rate.trim()) {
      const parsed = Number(String(rate).replace(/%/g, "").trim());
      rate = Number.isFinite(parsed) ? parsed : null;
    }
    if (rate == null || !Number.isFinite(Number(rate))) {
      return { rate: null, hasData: false };
    }
    return { rate: Number(rate), hasData: true };
  }

  function claimsPipelineSummary() {
    const m = metrics("claimsPipeline");
    const claims = allClaims();
    const totalValue = claims.reduce((s, c) => s + (parseAmount(c.amount || c.balance) || 0), 0);
    const denied = claims.filter((c) => String(c.status || "").toLowerCase().includes("denied")).length;
    const denialRate = claims.length ? Math.round((denied / claims.length) * 1000) / 10 : 0;
    const pendingAttachments = claims.filter((c) => String(c.status || "").toLowerCase().includes("attachment")).length;
    const ages = claims.map((c) => parseAmount(c.ageDays || c.age)).filter((n) => typeof n === "number" && !Number.isNaN(n));
    const avgAge = ages.length ? Math.round(ages.reduce((s, n) => s + n, 0) / ages.length) : "—";
    return [
      {
        label: "Total Open Value",
        value: totalValue ? `$${Math.round(totalValue).toLocaleString()}` : fmt(m.totalValue || "—"),
        halSubpanel: "claimsKpiTotal",
      },
      {
        label: "Average Age",
        value: avgAge !== "—" ? `${avgAge}d` : "—",
        halSubpanel: "claimsKpiAge",
      },
      {
        label: "Denial Rate",
        value: claims.length ? `${denialRate}%` : fmt(m.denialRate || "—"),
        halSubpanel: "claimsKpiDenied",
      },
      {
        label: "Pending Attachments",
        value: fmt(pendingAttachments || m.pendingAttachments || "—"),
        halSubpanel: "claimsKpiAttachments",
      },
    ];
  }

  function narrativeKanban() {
    const nar = snapshot && snapshot.narratives;
    const lanes = ["Draft", "Pending Review", "Approved", "Sent to Payer"];
    const buckets = Object.fromEntries(lanes.map((lane) => [lane, []]));
    const laneFor = (status) => {
      const s = String(status || "").toLowerCase();
      if (/sent|submitted|payer/.test(s)) return "Sent to Payer";
      if (/approv/.test(s)) return "Approved";
      if (/pending|review/.test(s)) return "Pending Review";
      return "Draft";
    };
    const pushDraft = (d, fallbackTitle) => {
      if (!d) return;
      const lane = laneFor(d.status || d.lane || d.stage);
      buckets[lane].push({
        patient: d.patient || d.title || fallbackTitle || "Draft",
        procedureCode: d.procedureCode || d.code || "—",
        payer: d.payer || "—",
        amount: d.amount || "",
        title: d.title,
      });
    };
    const drafts = Array.isArray(nar?.drafts) ? nar.drafts : [];
    // Never invent progress by index — only use an explicit draft status when present.
    if (drafts.length) {
      drafts.forEach((d, i) => pushDraft(d, `Draft ${i + 1}`));
    } else if (nar && nar.latest) {
      pushDraft(nar.latest, "Latest draft");
    }
    // Do not synthesize kanban cards from claims — claims are not narrative drafts.
    return lanes.map((lane) => ({ lane, tone: "muted", items: buckets[lane] }));
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
        value: (() => {
          const docsInPeriod = Number(String(period.documentsInPeriod != null ? period.documentsInPeriod : "").replace(/[^\d.-]/g, ""));
          const postedNum = Number(String(period.postedPct != null ? period.postedPct : "").replace(/[^\d.-]/g, ""));
          if ((!Number.isFinite(docsInPeriod) || docsInPeriod <= 0) && (!Number.isFinite(postedNum) || postedNum === 0)) {
            return "—";
          }
          return fmt(period.postedPct);
        })(),
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
    const labels = trend.labels || [];
    let production = (trend.production || []).map(parseAmount);
    const average = (trend.average || []).map(parseAmount);
    if (!production.length) return null;
    const filters =
      typeof NR2PageFilters !== "undefined" && NR2PageFilters.filterContext
        ? NR2PageFilters.filterContext("financial")
        : {};
    const sliced =
      typeof NR2PageFilters !== "undefined" && NR2PageFilters.applyPeriodSlice
        ? NR2PageFilters.applyPeriodSlice(labels, production, filters)
        : { labels, values: production };
    production = sliced.values;
    const slicedLabels = sliced.labels;
    const avgSlice =
      average.length && slicedLabels.length
        ? average.slice(-slicedLabels.length)
        : null;
    return {
      production,
      average: avgSlice && avgSlice.length ? avgSlice : null,
      max: Math.max(...production, 1) * 1.1,
      labels: slicedLabels,
    };
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
    const center = mix.rate
      ? `<strong>${escHtml(mix.rate)}</strong><span>Collections</span>${mix.hint ? `<span class="donut-hint">${escHtml(mix.hint)}</span>` : ""}`
      : mix.hint
        ? `<span class="donut-hint">${escHtml(mix.hint)}</span>`
        : "";
    return { slices, center, hint: mix.hint || null };
  }

  function providerBars() {
    const fin = dash("financial") || {};
    if (fin.dataSource === "empty") return null;
    const rows = ((fin.providers && fin.providers.rows) || []).filter((r) => {
      const amount = parseAmount(r && r.amount);
      const name = String((r && r.name) || "").trim();
      return name && amount > 0;
    });
    if (!rows.length) return null;
    return {
      items: rows.map((r) => ({ name: r.name, amount: r.amount, pct: parseAmount(r.pct) })),
      total: (fin.providers.total && fin.providers.total.amount) || fmt(metrics("providerPerformance").providerTotal),
    };
  }

  function softdentGlanceStats() {
    const care = metrics("careDeliveryPerformance");
    const payer = metrics("payerMixAndCollections");
    const patients = activePatientCensus();
    return [
      { value: fmt(care.patientBalanceTotal), label: "Patient A/R", tone: widgetTone("careDeliveryPerformance") || "warning", widgetKey: "softdentArAging" },
      { value: fmt(payer.collectionRate), label: "Collection rate", tone: widgetTone("payerMixAndCollections"), widgetKey: "payerMixAndCollections" },
      {
        value: fmt(patients.count),
        label: patients.label,
        hint: patients.hint,
        widgetKey: "careDeliveryPerformance",
      },
      { value: fmt(care.providerCount), label: "Providers loaded", widgetKey: "careDeliveryPerformance" },
    ];
  }

  function glanceValue(sd, label) {
    const row = ((sd && sd.glance) || []).find((g) => g.label === label);
    return row ? row.value : null;
  }

  function activePatientCensus() {
    const care = metrics("careDeliveryPerformance");
    const sd = dash("softdent") || {};
    const fromCare = care.patientCount;
    if (fromCare != null && fromCare !== "" && fromCare !== "—") {
      return { count: fromCare, label: "Active patients", hint: "SoftDent dashboard", source: "care" };
    }
    const fromGlance =
      glanceValue(sd, "Total Patients") ||
      glanceValue(sd, "Active Patients") ||
      glanceValue(sd, "Patients Today");
    if (fromGlance != null && fromGlance !== "" && fromGlance !== "—") {
      return { count: fromGlance, label: "Active patients", hint: "SoftDent glance", source: "glance" };
    }
    const names = new Set();
    const rooms = softdentOperatoryGrid() || [];
    rooms.forEach((room) => {
      (room.slots || []).forEach((slot) => {
        const name = slot.patient || slot.patientName;
        if (name) names.add(String(name).trim());
      });
    });
    if (!names.size) {
      const appt = softdentAppointmentsSnapshotData();
      (appt.appointments || []).forEach((row) => {
        const name = row.patientId || row.patient || row.patientName;
        if (name && name !== "—") names.add(String(name).trim());
      });
    }
    if (names.size) {
      return {
        count: names.size,
        label: "Patients today",
        hint: "Unique patients on today's operatory schedule",
        source: "schedule",
      };
    }
    return { count: null, label: "Active patients", hint: null, source: null };
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

  function outstandingClaimsAmount() {
    const claims = (snapshot && snapshot.claims && snapshot.claims.claims) || [];
    if (claims.length) {
      return claims.reduce((sum, row) => sum + parseAmount(row.amount || row.outstanding || row.balance), 0);
    }
    const bundle = snapshot && snapshot.importBundle;
    const rows = (bundle && bundle.softdent && bundle.softdent.claims && bundle.softdent.claims.rows) || [];
    return rows.reduce((sum, row) => {
      const amount =
        parseAmount(row.ClaimAmount) ||
        parseAmount(row.Outstanding) ||
        parseAmount(row.Balance) ||
        parseAmount(row.amount);
      return sum + amount;
    }, 0);
  }

  function softdentResponsibilityDonut() {
    if (!verifiedArWidgetReady("softdentResponsibility")) return null;
    const sd = dash("softdent") || {};
    const resp = sd.responsibility || {};
    let ins = parseAmount(resp.insurance && resp.insurance.amount);
    let pat = parseAmount(resp.patient && resp.patient.amount);
    // Dashboard "patient" often mirrors collections attribution, not A/R. Require
    // a real two-sided split before trusting those fields.
    if (!(ins > 0 && pat > 0)) {
      const aging = softdentAgingBars();
      const arTotal = aging
        ? aging.values.reduce((sum, value) => sum + (Number(value) || 0), 0)
        : parseAmount(sd.hero && sd.hero.value) || parseAmount(resp.total);
      const claimTotal = outstandingClaimsAmount();
      if (arTotal > 0 && claimTotal > 0) {
        ins = Math.min(claimTotal, arTotal);
        pat = Math.max(0, arTotal - ins);
      } else {
        return null;
      }
    }
    const total = ins + pat;
    if (!total) return null;
    const usedClaimsProxy = !(parseAmount(resp.insurance && resp.insurance.amount) > 0 && parseAmount(resp.patient && resp.patient.amount) > 0);
    return {
      slices: [
        { label: "Insurance", pct: Math.round((ins / total) * 1000) / 10, color: "#60a5fa" },
        { label: "Patient portion", pct: Math.round((pat / total) * 1000) / 10, color: "#d6b15e" },
      ],
      hint: resp.source === "claims-vs-ar" || usedClaimsProxy ? "Open SoftDent claims vs daysheet A/R" : resp.hint || null,
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
      recallDueCount: hr.recallDue != null ? hr.recallDue : pr.hygieneRecall?.due != null ? pr.hygieneRecall.due : null,
      recallRate: hr.recallRate != null ? hr.recallRate : pr.hygieneRecall?.recallRate != null ? pr.hygieneRecall.recallRate : null,
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
    const S = softdentDailyApi();
    if (S && typeof S.operatoryGrid === "function") {
      const chairs = S.operatoryGrid(snapshot);
      if (Array.isArray(chairs) && chairs.length) return chairs;
    }
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

  function arAgingBars() {
    if (!verifiedArWidgetReady("arAgingAndCollections")) return null;
    const ar = dash("ar") || {};
    const aging = ar.aging || ar.buckets || [];
    if (aging.length) {
      return {
        labels: aging.map((a) => a.bucket || a.label),
        values: aging.map((a) => parseAmount(a.amount || a.pct)),
      };
    }
    if (verifiedArWidgetReady("softdentArAging")) return softdentAgingBars();
    return null;
  }

  function arEliteKpis() {
    const ar = dash("ar") || {};
    const wm = metrics("arAgingAndCollections");
    const lag = nr2CollectionLag();
    const dsoTile = (nr2KpiRibbonTiles().tiles || []).find((t) => /dso|days|ar/i.test(String(t.label || "")));
    const dsoValue = lag.hasData && lag.avgLagDays != null ? String(lag.avgLagDays) : dsoTile ? dsoTile.value : "—";
    const buckets = ar.aging || ar.buckets || [];
    const findBucket = (re) => {
      const row = buckets.find((a) => re.test(String(a.bucket || a.label || "")));
      return row ? fmt(row.amount || row.pct) : "—";
    };
    return [
      {
        label: "Total A/R",
        value: fmt(wm.totalOutstanding),
        halSubpanel: "arKpiTotal",
        tone: widgetTone("arAgingAndCollections") || "warning",
      },
      { label: "Current (0–30)", value: findBucket(/0-30|current/i), halSubpanel: "arKpiCurrent" },
      { label: "31–60 Days", value: findBucket(/31-60|31\s*to\s*60/i), halSubpanel: "arKpi3160" },
      { label: "61–90 Days", value: findBucket(/61-90|61\s*to\s*90/i), halSubpanel: "arKpi6190" },
      { label: "90+ Days", value: findBucket(/90\+|^\s*90/i), halSubpanel: "arKpi90plus", tone: "warning" },
      {
        label: "DSO",
        value: dsoValue,
        hint: lag.caption || (lag.dsoProxy ? "Weighted DSO" : lag.hasData ? "Monthly proxy" : null),
        halSubpanel: "arKpiDso",
      },
    ];
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

  function allClaims() {
    const claims = snapshot && snapshot.claims && snapshot.claims.claims;
    return Array.isArray(claims) ? claims : [];
  }

  function setSelectedClaimId(claimId) {
    selectedClaimId = claimId ? String(claimId) : null;
  }

  function selectedClaim() {
    const claims = allClaims();
    if (!claims.length) return null;
    if (selectedClaimId) {
      const match = claims.find((c) => String(c.id || "") === selectedClaimId);
      if (match) return match;
    }
    return claims[0];
  }

  function firstClaim() {
    return selectedClaim();
  }

  function narrativeComposerOptions() {
    const lib = typeof HalNarrativeLibrary !== "undefined" ? HalNarrativeLibrary : null;
    const nar = snapshot && snapshot.narratives;
    return {
      focuses: (lib && lib.FOCUSES) || ["Medical Necessity", "Denial Appeal"],
      tones: (lib && lib.TONES) || ["Professional", "Clinical-Detailed"],
      lengths: (lib && lib.LENGTHS) || ["Standard", "Brief"],
      focus: (nar && nar.composer && nar.composer.focus) || (nar && nar.focus) || "Medical Necessity",
      tone: (nar && nar.composer && nar.composer.tone) || "Professional",
      length: (nar && nar.composer && nar.composer.length) || "Standard",
    };
  }

  function narrativeCitationWidgets() {
    const latest = snapshot && snapshot.narratives && snapshot.narratives.latest;
    if (latest && latest.citationWidgets && latest.citationWidgets.length) return latest.citationWidgets;
    return ["narrativeWorkflow", "claimsPipeline"];
  }

  function narrativeDraft() {
    const nar = snapshot && snapshot.narratives;
    const latest = nar && nar.latest;
    if (latest && latest.body) return latest.body;
    if (latest && latest.text) return latest.text;
    return "";
  }

  function narrativeCdtCodes() {
    const claim = firstClaim();
    const codes = [];
    const seen = new Set();
    const push = (code, desc) => {
      const cdt = String(code || "").trim().toUpperCase();
      if (!cdt || seen.has(cdt)) return;
      seen.add(cdt);
      codes.push(desc ? `${cdt} ${desc}` : cdt);
    };
    if (claim) {
      if (claim.procedure) push(String(claim.procedure).split(/\s+/)[0], String(claim.procedure).replace(/^\S+\s*/, ""));
      const procs = claim.procedures || claim.procedureCodes || claim.cdtCodes || [];
      (Array.isArray(procs) ? procs : []).forEach((p) => {
        if (typeof p === "string") push(p.split(/\s+/)[0], p.replace(/^\S+\s*/, ""));
        else if (p && typeof p === "object") push(p.code || p.cdt || p.procedure, p.desc || p.description || p.label);
      });
    }
    const fee = snapshot && (snapshot.feeSchedule || snapshot.fee_schedule);
    const feeRows = (fee && (fee.rows || fee.codes || fee.items)) || [];
    (Array.isArray(feeRows) ? feeRows : []).slice(0, 12).forEach((row) => {
      push(row.code || row.cdt || row.CdtCode || row.procedure, row.desc || row.description || row.label);
    });
    return codes.slice(0, 20);
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
        return `<article class="ms-ops-stat ms-ops-data__stat" data-hal-kpi-ref="${escHtml(row.widgetKey)}" data-hal-cmd="Explain ${escHtml(row.label)}" role="button" tabindex="0">
          <span class="ms-ops-stat__ico">${icon}</span>
          <strong>${escHtml(row.value)}</strong>
          <span>${escHtml(row.label)}</span>
        </article>`;
      })
      .join("");
    return `<section class="widget-card col-12 ms-ops-data" data-hal-subpanel="officeOpsData">
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

  function documentsPeriodLabel() {
    const docs = snapshot && snapshot.documents;
    const fromDocs = docs && docs.period && docs.period.label;
    const fromMetrics = metrics("periodCloseAndPosting").periodLabel;
    return String(fromDocs || fromMetrics || "").trim();
  }

  function documentsPeriodStats() {
    const docs = snapshot && snapshot.documents;
    const period = metrics("periodCloseAndPosting");
    const ap = metrics("accountsPayableAutomation");
    const label = documentsPeriodLabel();
    const docCountRaw = period.documentsInPeriod != null ? period.documentsInPeriod : docs && docs.period && docs.period.documents;
    const docCount = Number(String(docCountRaw != null ? docCountRaw : "").replace(/[^\d.-]/g, ""));
    const hasDocs = Number.isFinite(docCount) && docCount > 0;
    const postedRaw = period.postedPct;
    const postedNum = Number(String(postedRaw != null ? postedRaw : "").replace(/[^\d.-]/g, ""));
    // 0% Posted with no documents is empty-state noise, not a real close metric.
    if (!label && !hasDocs && (postedRaw == null || postedRaw === "" || postedRaw === "—" || postedNum === 0)) {
      return [];
    }
    const postedDisplay =
      !hasDocs && (postedRaw == null || postedRaw === "" || postedRaw === "—" || postedNum === 0)
        ? "—"
        : fmt(postedRaw);
    return [
      ...(label ? [{ value: label, label: "Period", tone: "info", widgetKey: "periodCloseAndPosting" }] : []),
      { value: hasDocs ? fmt(docCountRaw) : "—", label: "Documents in period", tone: widgetTone("periodCloseAndPosting"), widgetKey: "periodCloseAndPosting" },
      { value: postedDisplay, label: "Posted", tone: postedDisplay === "—" ? "neutral" : "success", widgetKey: "periodCloseAndPosting" },
      { value: fmt(period.pendingAmount || ap.postingQueuePendingCount), label: "Pending review", tone: "warning", widgetKey: "journalPostingQueue" },
      { value: fmt(ap.expenseTotal), label: "Expense total", tone: "warning", widgetKey: "accountsPayableAutomation" },
    ];
  }

  function journalRows() {
    const m = metrics("journalPostingQueue");
    const count = Number(String(m.queueCount || "").replace(/[^\d.-]/g, ""));
    if (!Number.isFinite(count) || count <= 0) return [];
    return [
      ["Pending review", fmt(m.pendingReview), "Journal queue", "Local"],
      ["Ready to export", fmt(m.readyToExport), "Journal queue", "Local"],
    ];
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

  function halImportHealthStats() {
    const w = widget("halImportHealth");
    const m = (w && w.metrics) || {};
    const bundle = snapshot && snapshot.importBundle;
    const diag = (bundle && bundle.diagnostics && bundle.diagnostics.summary) || {};
    const health = (feed && feed.sourceHealth) || {};
    const connected = m.connectedDatasets != null ? m.connectedDatasets : diag.connected != null ? diag.connected : health.connected;
    const partial = m.partialDatasets != null ? m.partialDatasets : diag.partial != null ? diag.partial : health.partial;
    const missing = m.missingDatasets != null ? m.missingDatasets : diag.missing != null ? diag.missing : health.missing;
    const hasData = connected != null || partial != null || missing != null || Boolean(w);
    const c = Number(connected) || 0;
    const p = Number(partial) || 0;
    const miss = Number(missing) || 0;
    const total = Math.max(1, c + p + miss);
    const pct = Math.round((c / total) * 100);
    return {
      hasData,
      status: (w && w.status) || "—",
      importMode: (bundle && bundle.importMode) || (feed && feed.importMode) || "cache",
      pct,
      stats: [
        { label: "Connected", value: fmt(connected), tone: "success", widgetKey: "halImportHealth" },
        { label: "Partial", value: fmt(partial), tone: "warning", widgetKey: "halImportHealth" },
        { label: "Missing", value: fmt(missing), tone: miss > 0 ? "warning" : undefined, widgetKey: "halImportHealth" },
        { label: "Health", value: hasData ? `${pct}%` : "—", tone: pct >= 70 ? "success" : "warning", widgetKey: "halImportHealth" },
      ],
    };
  }

  function halPracticeOverviewStats() {
    const ov = metrics("practiceFinancialOverview");
    const fin = dash("financial") || {};
    const collections = collectionsDisplay(fin, ov.collectionsTotal);
    const hasData =
      ov.productionTotal != null ||
      ov.collectionsTotal != null ||
      collections.value !== "—" ||
      ov.monthlyNetIncome != null ||
      (fin.productionMtd && fin.productionMtd.value != null);
    return {
      hasData,
      stats: [
        {
          label: "Production MTD",
          value: fmt(ov.productionTotal || (fin.productionMtd && fin.productionMtd.value)),
          tone: widgetTone("practiceFinancialOverview"),
          widgetKey: "practiceFinancialOverview",
        },
        {
          label: collections.period ? `Collections (${collections.period})` : "Collections",
          value: collections.value,
          tone: collections.tone || widgetTone("practiceFinancialOverview"),
          widgetKey: "practiceFinancialOverview",
        },
        {
          label: "Open A/R",
          value: fmt(ov.arTotal || metrics("arAgingAndCollections").totalOutstanding),
          tone: "warning",
          widgetKey: "practiceFinancialOverview",
        },
        {
          label: "Book net",
          value: fmt(ov.monthlyNetIncome || metrics("quickbooksProfitLossDetail").netIncome),
          tone: widgetTone("quickbooksProfitLossDetail"),
          widgetKey: "practiceFinancialOverview",
        },
      ],
    };
  }

  function halCareDeliveryStats() {
    const care = metrics("careDeliveryPerformance");
    const practice = practiceStats();
    const patients = activePatientCensus();
    const production = care.productionTotal || metrics("financialProductionTrend").productionMtd;
    const newPatients = metrics("newPatients").newPatientCount || practice.newPatients;
    const hasData =
      (production != null && production !== "") ||
      (patients.count != null && patients.count !== "") ||
      (care.providerCount != null && care.providerCount !== "") ||
      (newPatients != null && newPatients !== "");
    return {
      hasData,
      stats: [
        {
          label: "Production MTD",
          value: fmt(production),
          tone: widgetTone("careDeliveryPerformance"),
          widgetKey: "careDeliveryPerformance",
        },
        {
          label: patients.label,
          value: fmt(patients.count),
          hint: patients.hint,
          widgetKey: "careDeliveryPerformance",
        },
        {
          label: "Providers",
          value: fmt(care.providerCount),
          widgetKey: "careDeliveryPerformance",
        },
        {
          label: "New patients",
          value: fmt(newPatients),
          tone: widgetTone("newPatients"),
          widgetKey: "careDeliveryPerformance",
        },
      ],
    };
  }

  function halAskHalSuggestions() {
    const ask = (typeof globalThis !== "undefined" && globalThis.halData && globalThis.halData.askHal) || null;
    const suggestions = (ask && ask.suggestions) || [
      "Show import health",
      "Summarize MTD production",
      "List open claims",
      "Explain QuickBooks net income",
    ];
    return suggestions.slice(0, 6);
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

  function financialPriorCompare() {
    const fin = dash("financial") || {};
    const trend = fin.productionTrend || {};
    const labels = trend.labels || [];
    const prod = (trend.production || []).map(parseAmount);
    if (labels.length < 2 || prod.length < 2) return [];
    const cur = prod[prod.length - 1];
    const prev = prod[prod.length - 2];
    const deltaPct = prev ? Math.round(((cur - prev) / prev) * 100) : null;
    return [
      {
        label: `Current (${labels[labels.length - 1] || "period"})`,
        value: fmt(cur),
        delta: deltaPct != null ? `${deltaPct >= 0 ? "+" : ""}${deltaPct}% vs prior` : "—",
        tone: deltaPct != null && deltaPct >= 0 ? "success" : "warning",
      },
      {
        label: `Prior (${labels[labels.length - 2] || "period"})`,
        value: fmt(prev),
        delta: "baseline",
        tone: "neutral",
      },
    ];
  }

  function taxPlan() {
    if (typeof TaxEngine !== "undefined" && TaxEngine.buildTaxPlanFromSnapshot) {
      const inputs =
        typeof TaxEngine.collectInputsFromSnapshot === "function"
          ? TaxEngine.collectInputsFromSnapshot(snapshot, feed)
          : {};
      const filters =
        typeof NR2PageFilters !== "undefined" && NR2PageFilters.filterContext
          ? NR2PageFilters.filterContext("taxes")
          : {};
      if (filters.revenueAdjPct) {
        const base = inputs.bookNetIncome || 0;
        inputs.bookNetIncome = Math.round(base * (1 + (filters.revenueAdjPct || 0) / 100));
      }
      if (filters.modeledW2 != null) inputs.modeledOfficerW2 = filters.modeledW2;
      return TaxEngine.buildTaxPlan(inputs);
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

  function nr2GoalScorecard() {
    const A = analyticsApi();
    return A ? A.goalScorecard(snapshot) : { hasData: false };
  }

  function nr2AlertTicker() {
    const A = analyticsApi();
    return A ? A.alertTicker(snapshot) : { items: [], hasData: false };
  }

  function nr2ProviderCompensation() {
    const A = analyticsApi();
    return A ? A.providerCompensation(snapshot) : { providers: [], hasData: false };
  }

  function nr2MonthlyTrendCombo() {
    const A = analyticsApi();
    const combo = A ? A.monthlyTrendCombo(snapshot) : { labels: [], hasData: false };
    if (!combo.labels || !combo.labels.length) return combo;
    const filters =
      typeof NR2PageFilters !== "undefined" && NR2PageFilters.filterContext
        ? NR2PageFilters.filterContext("financial")
        : {};
    const PF = typeof NR2PageFilters !== "undefined" ? NR2PageFilters : null;
    if (!PF || !PF.applyPeriodSlice) return combo;
    const prodSlice = PF.applyPeriodSlice(combo.labels, combo.production || [], filters);
    const collSlice = PF.applyPeriodSlice(combo.labels, combo.collections || [], filters);
    const revSlice = PF.applyPeriodSlice(combo.labels, combo.revenue || [], filters);
    return Object.assign({}, combo, {
      labels: prodSlice.labels,
      production: prodSlice.values,
      collections: collSlice.values,
      revenue: revSlice.values,
      hasData: prodSlice.labels.length > 0,
    });
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

  function shortPeriodLabel(period) {
    const raw = String(period || "").trim();
    const match = raw.match(/^(\d{4})-(\d{2})/);
    if (!match) return raw || "";
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    const idx = Number(match[2]) - 1;
    return months[idx] ? `${months[idx]} ${match[1].slice(2)}` : raw;
  }

  function newPatientsFlowSeries() {
    const bundle = snapshot && snapshot.importBundle;
    const rows = (bundle && bundle.softdent && bundle.softdent.newPatients && bundle.softdent.newPatients.rows) || [];
    const byPeriod = {};
    rows.forEach((row) => {
      const period = String(
        (row && (row.Period || row.period || row.Month || row.month)) || "",
      ).trim();
      if (!period) return;
      const key = period.length >= 7 ? period.slice(0, 7) : period;
      const count = Number(
        String(row.Count || row.count || row.NewPatients || row.newPatients || row.Total || "0").replace(/,/g, ""),
      );
      if (!Number.isFinite(count)) return;
      byPeriod[key] = (byPeriod[key] || 0) + count;
    });
    const labels = Object.keys(byPeriod).sort();
    if (labels.length) {
      return {
        labels: labels.map(shortPeriodLabel),
        values: labels.map((key) => byPeriod[key]),
        periods: labels,
        hasData: true,
        singlePeriod: labels.length === 1,
      };
    }
    const mtd = softdentNewPatientsMtdData();
    const metricsNp = metrics("newPatients");
    const count =
      mtd && mtd.hasData && mtd.count != null
        ? Number(mtd.count)
        : metricsNp && metricsNp.newPatientCount != null
          ? Number(metricsNp.newPatientCount)
          : null;
    const period = (mtd && mtd.period) || (metricsNp && metricsNp.period) || "";
    if (count == null || !Number.isFinite(count)) {
      return { labels: [], values: [], periods: [], hasData: false, singlePeriod: false };
    }
    return {
      labels: [shortPeriodLabel(period) || "Latest"],
      values: [count],
      periods: period ? [String(period).slice(0, 7)] : [],
      hasData: true,
      singlePeriod: true,
    };
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

  function softdentOdbcStatus() {
    if (typeof window !== "undefined" && window.__NR2_SOFTDENT_ODBC_STATUS) {
      return window.__NR2_SOFTDENT_ODBC_STATUS;
    }
    const bundle = snapshot && snapshot.importBundle;
    const lane = bundle && bundle.softdent && bundle.softdent.odbcExtract;
    if (!lane) return null;
    return {
      lastMode: lane.mode || null,
      lastExtractAt: lane.refreshedAt || null,
      populatedTables: lane.populatedTables != null ? lane.populatedTables : null,
      odbcConfigured: null,
      tableCounts: {},
    };
  }

  function softdentProcedures() {
    const bundle = snapshot && snapshot.importBundle;
    const ds = bundle && bundle.softdent && bundle.softdent.procedures;
    if (!ds) return [];
    return Array.isArray(ds) ? ds : (ds.rows || []);
  }

  function softdentClaimStatus() {
    const bundle = snapshot && snapshot.importBundle;
    const ds = bundle && bundle.softdent && bundle.softdent.claimStatus;
    if (!ds) return [];
    return Array.isArray(ds) ? ds : (ds.rows || []);
  }

  function quickbooksExpenseCategories() {
    const bundle = snapshot && snapshot.importBundle;
    const ds = bundle && bundle.quickbooks && bundle.quickbooks.expenseCategories;
    const diag = bundle && bundle.diagnostics && bundle.diagnostics["quickbooks.expenseCategories"];
    const ageMin = diag && diag.ageMinutes != null ? diag.ageMinutes : Infinity;
    if (!ds) return { rows: [], stale: true, ageMin };
    const rows = Array.isArray(ds) ? ds : (ds.rows || []);
    return { rows, stale: ageMin > 1440, ageMin };
  }

  function quickbooksAr() {
    const bundle = snapshot && snapshot.importBundle;
    const ds = bundle && bundle.quickbooks && bundle.quickbooks.ar;
    const diag = bundle && bundle.diagnostics && bundle.diagnostics["quickbooks.ar"];
    const ageMin = diag && diag.ageMinutes != null ? diag.ageMinutes : Infinity;
    if (!ds) return { rows: [], stale: true, ageMin };
    const rows = Array.isArray(ds) ? ds : (ds.rows || []);
    return { rows, stale: ageMin > 1440, ageMin };
  }

  return {
    bind,
    setLiveIntegrationHealth,
    getLiveIntegrationHealth,
    periodSubtitle,
    financialKpis,
    softdentKpis,
    softdentHeroKpis,
    softdentAppointmentStats,
    softdentArAgingHeatmap,
    treatmentPlanFunnel,
    hygieneRecallGauge,
    claimsPipelineSummary,
    narrativeKanban,
    documentsKpis,
    financialCompare,
    financialPriorCompare,
    financialWeeklyBars,
    financialYtdBars,
    productionTrendSeries,
    payerDonut,
    providerBars,
    softdentGlanceStats,
    softdentAgingBars,
    softdentResponsibilityDonut,
    practiceStats,
    activePatientCensus,
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
    arEliteKpis,
    arAgingBars,
    arCollectionsChart,
    arTopClaimsTable,
    arFollowUpKanban,
    claimsKpis,
    claimsKanban,
    allClaims,
    setSelectedClaimId,
    selectedClaim,
    firstClaim,
    narrativeDraft,
    narrativeCdtCodes,
    narrativeComposerOptions,
    narrativeCitationWidgets,
    narrativeHistoryRows,
    narrativeKpis,
    documentsQueueRows,
    firstDocument,
    documentsPeriodLabel,
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
    halImportHealthStats,
    halPracticeOverviewStats,
    halCareDeliveryStats,
    halAskHalSuggestions,
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
    nr2GoalScorecard,
    nr2AlertTicker,
    nr2ProviderCompensation,
    nr2MonthlyTrendCombo,
    quickbooksBalanceSheetSummary,
    quickbooksCashFlowTrend,
    quickbooksNetIncomeSummary,
    quickbooksRevenueByService,
    quickbooksQbArAging,
    softdentCollectionsDailySeries,
    softdentNewPatientsMtdData,
    newPatientsFlowSeries,
    softdentClaimsOutstandingData,
    softdentProviderProductionData,
    softdentAppointmentsSnapshotData,
    softdentOdbcStatus,
    softdentProcedures,
    softdentClaimStatus,
    quickbooksExpenseCategories,
    quickbooksAr,
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
