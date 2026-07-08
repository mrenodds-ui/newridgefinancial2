# Plan Comparison — Cursor Mockup/Widget Fix vs Moonshot AI

**Date:** 2026-07-08  
**Model:** kimi-k2.6 via OPENROUTER_API_KEY  
**Script:** `scripts/run_moonshot_mockup_fix_comparison.py`

---

# Moonshot Verdict

The Cursor agent correctly diagnosed the root cause (data pipeline gaps + canvas vocabulary mismatches) but undervalued QuickBooks structural collapse and mischaracterized the widget-empty problem as a “status honesty” issue rather than a renderer data-resolution failure. I agree with the inventory of fixes; I disagree with the P0/P1 split and the sequencing of B vs C.

---

## Agreement with Cursor Plan

- **Phase A (data pipeline)** is correctly ranked P0. Without `softdent.procedures` and `softdent.claimStatus`, the SoftDent page cannot reach `SUCCESS`, and QuickBooks stale datasets (`expenseCategories`, `ar`) poison downstream KPI accuracy.
- **Phases D–F (panels, vocabulary, chart mount)** are the correct mechanical sequence: create DOM containers → apply mockup class vocabulary → mount charts into those containers.
- **Phase G (API refresh / build bump)** is correctly deferred to P2.

---

## Disagreements / Reorder

1. **QuickBooks layout collapse should be P0, not P1.** The audit shows 5 empty placeholders and a `dashboard-grid` count of 10 live vs 4 mockup, meaning the page is visually unusable even though the data feed is technically present. Flattening nested `dashboardHost` wrappers is as urgent as unblocking data.
2. **Widget “status honesty” is a P1 renderer fix, not a P0 status-badge change.** The feed audit reports **50/50 widgets with data, 0 empty/missing**. The bodies are empty because `page-canvas.js` renderers receive partial `data` bags and fall back to `.empty-placeholder` even when HAL bus datasets exist. The fix is data-resolution in the renderer, not a new `hasRenderableData()` badge function.
3. **Chart mount wiring (Phase F) should immediately follow panel insertion (Phase D).** Vocabulary (Phase E) can be parallel, but panels without mount logic remain empty after F5 until `enhancePage` is fixed.

---

## Priority Reconciliation Table

| Rank | Cursor phase | Moonshot rank | Note |
|------|--------------|---------------|------|
| 1 | A — Unblock data | **1** | Agree. SoftDent procedures/claimStatus collectors + QB stale guard are critical path. |
| 2 | C — QB layout collapse | **2** | **Promoted to P0.** Nested wrappers break the grid; 5 empty markers block users even when data is present. |
| 3 | B — Widget status honesty | **3** | **Demoted to P1 / reframed.** Root cause is canvas renderer blind to HAL data, not badge honesty. |
| 4 | D — Missing chart panels | **4** | Agree on P1. DOM must exist before charts can mount. |
| 5 | E — Page vocabulary | **5** | Agree on P1. CSS class parity (kpi-card, composer-grid, etc.). |
| 6 | F — Chart mount wiring | **6** | Agree on P1, but sequenced strictly after D. |
| 7 | G — Keys / build bump | **7** | Agree on P2. Sign-off only after parity passes. |

---

## Issue 1: Data Pipeline (SoftDent procedures, QB stale) — CODE

### `import_sync.py` (Python)

```python
# import_sync.py — append to collector registry
COLLECTOR_MAP.update({
    "softdent.procedures": {
        "source": "softdent",
        "endpoint": "/export/procedures",
        "query": """
            SELECT procedure_code, procedure_description, fee, provider_id,
                   procedure_date, tooth_number, surface, status
            FROM procedures
            WHERE procedure_date >= :rolling_90d
            ORDER BY procedure_date DESC
        """,
        "schedule": "0 6,14 * * *",   # 06:00 + 14:00 daily
        "fallback_csv": "softdent_procedures.csv",
        "required_for": ["softdent", "narratives", "claims"],
    },
    "softdent.claimStatus": {
        "source": "softdent",
        "endpoint": "/export/claim_status",
        "query": """
            SELECT claim_id, patient_id, payer_name, claim_status,
                   billed_amount, paid_amount, date_submitted, date_resolved,
                   denial_reason, narrative_needed
            FROM claim_status
            WHERE date_submitted >= :rolling_90d
            ORDER BY date_submitted DESC
        """,
        "schedule": "0 7 * * *",      # 07:00 daily
        "fallback_csv": "softdent_claim_status.csv",
        "required_for": ["softdent", "claims"],
    }
})

# ------------------------------------------------------------------
# QuickBooks stale-force refresh
# ------------------------------------------------------------------
def ensure_quickbooks_fresh(max_age_minutes: int = 1440):
    qb_sets = [
        "quickbooks.revenue",
        "quickbooks.profitAndLoss",
        "quickbooks.expenses",
        "quickbooks.expenseCategories",
        "quickbooks.ar",
    ]
    for ds_key in qb_sets:
        meta = get_dataset_meta(ds_key)
        age = meta.get("age_minutes", 999999) if meta else 999999
        if age > max_age_minutes:
            logging.warning(f"[SYNC] QB dataset {ds_key} stale ({age}m). Queuing priority sync.")
            queue_priority_sync(ds_key, source="quickbooks", reason="stale_refresh")

# Invoke inside the main scheduler loop before widget-feed generation:
# ensure_quickbooks_fresh()
```

### `page-canvas-data.js` (JavaScript)

```javascript
/**
 * page-canvas-data.js — append these binders to PageCanvasData
 */

PageCanvasData.softdentProcedures = function() {
  const snap = window.HAL?.bus?.snapshot?.datasets || {};
  const ds = snap['softdent.procedures'];
  if (!ds) return [];
  return Array.isArray(ds) ? ds : (ds.rows || []);
};

PageCanvasData.softdentClaimStatus = function() {
  const snap = window.HAL?.bus?.snapshot?.datasets || {};
  const ds = snap['softdent.claimStatus'];
  if (!ds) return [];
  return Array.isArray(ds) ? ds : (ds.rows || []);
};

PageCanvasData.quickbooksExpenseCategories = function() {
  const snap = window.HAL?.bus?.snapshot?.datasets || {};
  const ds = snap['quickbooks.expenseCategories'];
  if (!ds) return { rows: [], stale: true, ageMin: Infinity };
  const rows = Array.isArray(ds) ? ds : (ds.rows || []);
  const ageMin = ds.freshnessMinutes || ds.ageMinutes || 0;
  return { rows, stale: ageMin > 1440, ageMin };
};

PageCanvasData.quickbooksAr = function() {
  const snap = window.HAL?.bus?.snapshot?.datasets || {};
  const ds = snap['quickbooks.ar'];
  if (!ds) return { rows: [], stale: true, ageMin: Infinity };
  const rows = Array.isArray(ds) ? ds : (ds.rows || []);
  const ageMin = ds.freshnessMinutes || ds.ageMinutes || 0;
  return { rows, stale: ageMin > 1440, ageMin };
};
```

### `hal-skills.js` (JavaScript)

```javascript
/**
 * hal-skills.js — register missing datasets and health checks
 */

HAL.skills.defineSource('softdent', {
  datasets: [
    'softdent.dashboard','softdent.claims','softdent.clinicalNotes',
    'softdent.ar','softdent.newPatients','softdent.treatmentPlans',
    'softdent.caseAcceptance','softdent.hygieneRecall','softdent.operatory',
    'softdent.procedures',        // NEW
    'softdent.claimStatus'        // NEW
  ],
  healthCheck() {
    const critical = ['softdent.dashboard','softdent.claims','softdent.procedures','softdent.claimStatus'];
    const present = critical.filter(k => HAL.bus?.snapshot?.datasets?.[k]);
    const ok = present.length === critical.length;
    return {
      status: ok ? 'SUCCESS' : 'DEGRADED',
      detail: ok ? 'All critical SoftDent datasets present' : `${present.length}/${critical.length} critical datasets present`
    };
  }
});

HAL.skills.defineSource('quickbooks', {
  datasets: [
    'quickbooks.revenue','quickbooks.profitAndLoss','quickbooks.expenses',
    'quickbooks.expenseCategories','quickbooks.ar'
  ],
  healthCheck() {
    const staleThreshold = 1440;
    const sets = [
      'quickbooks.revenue','quickbooks.profitAndLoss','quickbooks.expenses',
      'quickbooks.expenseCategories','quickbooks.ar'
    ];
    let staleCount = 0;
    sets.forEach(k => {
      const ds = HAL.bus?.snapshot?.datasets?.[k];
      if (!ds) return;
      const age = ds.freshnessMinutes || ds.ageMinutes || 0;
      if (age > staleThreshold) staleCount++;
    });
    return {
      status: staleCount === 0 ? 'SUCCESS' : (staleCount >= 2 ? 'DEGRADED' : 'WARNING'),
      detail: staleCount > 0 ? `${staleCount} QB dataset(s) stale (>24h)` : 'All QB datasets fresh'
    };
  }
});
```

---

## Issue 2: Widget Feed vs Canvas Empty — CODE

### `page-canvas.js` (JavaScript)

```javascript
/**
 * page-canvas.js — data-resolution + empty-state guard
 */

// 1. Shared honesty / resolution helpers
PageCanvas.hasRenderableData = function(datasetKey, minRows = 1) {
  const snap = (window.HAL?.bus?.snapshot?.datasets) || {};
  const ds = snap[datasetKey];
  if (!ds) return false;
  const rows = Array.isArray(ds) ? ds : (ds.rows || ds.data);
  if (Array.isArray(rows)) return rows.length >= minRows;
  if (typeof ds === 'object' && Object.keys(ds).length > 0) return true;
  return false;
};

// Resolve passed page data against live HAL bus datasets when renderer bag is empty
PageCanvas.resolveData = function(pageId, passedData) {
  if (passedData && Object.keys(passedData).length > 0) return passedData;
  const snap = window.HAL?.bus?.snapshot?.datasets || {};
  const out = { ...(passedData || {}) };
  Object.keys(snap).forEach(dsKey => {
    if (dsKey.startsWith(pageId + '.')) {
      const short = dsKey.split('.').pop();
      out[short] = snap[dsKey];
    }
  });
  return out;
};

// 2. Example: patch renderSoftdent so it NEVER shows global empty placeholder
//    when HAL has ANY softdent dataset (including the new ones).
PageCanvas.renderSoftdent = function(pageId, data) {
  const root = document.getElementById('appPage');
  if (!root) return;

  data = this.resolveData('softdent', data || {});

  const hasAny = [
    'softdent.dashboard','softdent.claims','softdent.clinicalNotes',
    'softdent.ar','softdent.newPatients','softdent.treatmentPlans',
    'softdent.caseAcceptance','softdent.hygieneRecall','softdent.operatory',
    'softdent.procedures','softdent.claimStatus'
  ].some(k => PageCanvas.hasRenderableData(k));

  if (!hasAny) {
    root.innerHTML = `<div class="empty-placeholder">No SoftDent data connected</div>`;
    return;
  }

  root.innerHTML = `
    <div class="softdent-page">
      <div class="widget-grid" data-hal-widget-key="softdentOverview">
        ${this.canvasMetricTile({ title: 'Production', value: data.dashboard?.production })}
        ${this.canvasMetricTile({ title: 'Collections', value: data.dashboard?.collections })}
      </div>

      <div class="widget-grid" data-hal-widget-key="softdentFunnel">
        ${this.canvasFunnel(data.funnel || {})}
      </div>

      <div class="widget-grid" data-hal-widget-key="softdentOperatory">
        ${this.operatoryGrid?.(data.operatory) || '<div class="empty-state">Operatory timeline not configured</div>'}
      </div>

      <div class="widget-grid" data-hal-widget-key="softdentRecall">
        ${this.recallTable?.(data.hygieneRecall) || ''}
      </div>

      <div class="chart-panel-grid">
        <div class="chart-container" data-hal-widget-key="softdentProduction">
          ${PageCanvas.hasRenderableData('softdent.procedures')
            ? this.proceduresTable(PageCanvasData.softdentProcedures())
            : '<div class="empty-state">Procedures loading…</div>'}
        </div>
        <div class="chart-container" data-hal-widget-key="softdentClaimStatus">
          ${PageCanvas.hasRenderableData('softdent.claimStatus')
            ? this.claimStatusPanel(PageCanvasData.softdentClaimStatus())
            : '<div class="empty-state">Claim status loading…</div>'}
        </div>
        <div class="chart-container" data-hal-widget-key="softdentCollections"></div>
        <div class="chart-container" data-hal-widget-key="softdentAging"></div>
      </div>
    </div>
  `;
};
```

---

## Issue 3: QuickBooks Layout Collapse — CODE

### `page-canvas.js` (JavaScript)

```javascript
/**
 * page-canvas.js — replace renderQuickbooks to remove nested wrappers
 */

PageCanvas.renderQuickbooks = function(pageId, data) {
  const root = document.getElementById('appPage');
  if (!root) return;

  // Detect stale from HAL if not provided in data bag
  const qbExp = PageCanvasData.quickbooksExpenseCategories?.();
  const qbAr  = PageCanvasData.quickbooksAr?.();
  const isStale = qbExp?.stale || qbAr?.stale || data?.qbStale;

  root.innerHTML = `
    <div class="dashboard-grid" data-page="quickbooks" data-hal-widget-key="qbDashboard">
      <div class="dashboard-grid__header">
        <h2 class="dashboard-grid__title">QuickBooks Overview</h2>
        <span class="sync-badge ${isStale ? 'sync-badge--stale' : ''}" data-qb-sync-status>
          ${isStale ? 'Stale — refresh needed' : 'Synced'}
        </span>
      </div>

      <div class="kpi-grid">
        <div class="kpi-card" data-hal-widget-key="qbRevenue">
          <div class="kpi-value">${data?.revenueYtd ?? '—'}</div>
          <div class="kpi-label">Revenue YTD</div>
        </div>
        <div class="kpi-card" data-hal-widget-key="qbExpenses">
          <div class="kpi-value">${data?.expensesYtd ?? '—'}</div>
          <div class="kpi-label">Expenses YTD</div>
        </div>
        <div class="kpi-card" data-hal-widget-key="qbNetIncome">
          <div class="kpi-value">${data?.netIncome ?? '—'}</div>
          <div class="kpi-label">Net Income</div>
        </div>
        <div class="kpi-card" data-hal-widget-key="qbAr">
          <div class="kpi-value">${data?.arOutstanding ?? '—'}</div>
          <div class="kpi-label">AR Outstanding</div>
        </div>
      </div>

      <div class="dashboard-grid__charts">
        <div class="chart-large chart-container" data-hal-widget-key="qbRevenueTrend"></div>
        <div class="chart-medium chart-container" data-hal-widget-key="qbProfitLoss"></div>
        <div class="chart-medium chart-container" data-hal-widget-key="qbExpenseCategories"></div>
        <div class="chart-large chart-container" data-hal-widget-key="qbCashFlow"></div>
        <div class="chart-medium chart-container" data-hal-widget-key="qbAging"></div>
        <div class="chart-medium chart-container" data-hal-widget-key="qbVendorSpend"></div>
      </div>
    </div>
  `;
};
```

---

## Issue 4: Missing Chart Panels (per page) — CODE

### `page-canvas.js` (JavaScript)

```javascript
/**
 * page-canvas.js — inject missing chart-container panels