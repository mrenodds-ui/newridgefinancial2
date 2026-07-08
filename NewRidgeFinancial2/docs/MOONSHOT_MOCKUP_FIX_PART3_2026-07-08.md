# Moonshot Part 3

**Model:** kimi-k2.6 via OPENROUTER_API_KEY

---

## Issue 4 (continued): AR, Claims, Office Manager, Documents — CODE

```js
// page-canvas.js — page renderers for mockup parity

function renderARPage(container, data = {}) {
  const kpi = (i) => `
    <div class="kpi-card">
      <h4>${['0-30 Days','31-60 Days','61-90 Days'][i]}</h4>
      <div class="metric" data-widget="ar.age${i+1}">$0</div>
    </div>`;
  const chart = (i) => `
    <div class="chart-container" data-chart-type="bar" data-widget="ar.chart${i+1}">
      <canvas></canvas>
    </div>`;

  container.innerHTML = `
    <section class="page-ar">
      <header class="page-header"><h2>Accounts Receivable</h2></header>
      <div class="kpi-grid">${[0,1,2].map(kpi).join('')}</div>
      <div class="chart-row">${[0,1,2].map(chart).join('')}</div>
    </section>`;
}

function renderClaimsPage(container, data = {}) {
  const chart = (i) => `
    <div class="chart-container" data-chart-type="doughnut" data-widget="claims.chart${i+1}">
      <canvas></canvas>
    </div>`;
  const claim = (i) => `
    <article class="claim-card" data-widget="claims.claim${i+1}">
      <span class="claim-id">CLM-${1000+i}</span>
      <span class="claim-status badge">Pending</span>
    </article>`;

  container.innerHTML = `
    <section class="page-claims">
      <header class="page-header"><h2>Claims</h2></header>
      <div class="chart-row">${[0,1,2,3].map(chart).join('')}</div>
      <div class="claims-grid">${Array.from({length:23},(_,i)=>claim(i)).join('')}</div>
    </section>`;
}

function renderOfficeManagerPage(container, data = {}) {
  const panel = (i) => `
    <div class="dashboard-panel" data-widget="office.panel${i+1}">
      <h4>Office Panel ${i+1}</h4>
    </div>`;
  const chart = (i) => `
    <div class="chart-container" data-chart-type="line" data-widget="office.chart${i+1}">
      <canvas></canvas>
    </div>`;

  container.innerHTML = `
    <section class="page-office-manager">
      <header class="page-header"><h2>Office Manager</h2></header>
      <div class="dashboard-grid">${[0,1,2].map(panel).join('')}</div>
      <div class="chart-row">${[0,1].map(chart).join('')}</div>
    </section>`;
}

function renderDocumentsPage(container, data = {}) {
  const widget = (i) => `
    <div class="widget-card" data-widget="docs.widget${i+1}">
      <h4>Doc Set ${i+1}</h4>
      <div class="doc-count">0</div>
    </div>`;

  container.innerHTML = `
    <section class="page-documents">
      <header class="page-header"><h2>Documents</h2></header>
      <div class="widget-grid">${[0,1,2].map(widget).join('')}</div>
    </section>`;
}
```

## Issue 5: Page Vocabulary — CODE

```css
/* nr2-mockup-page-vocabulary.css */

/* --- Taxes: kpi-card / kpi-grid --- */
.taxes-kpi-section .kpi-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
  margin-bottom: 1.5rem;
}
.kpi-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  padding: 1rem;
  box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.04);
}
.kpi-card h4 {
  margin: 0 0 0.5rem;
  font-size: 0.875rem;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.kpi-card .metric {
  font-size: 1.5rem;
  font-weight: 700;
  color: #0f172a;
}

/* --- Narratives: composer-grid x4 --- */
.composer-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
}
.composer-grid > .composer-panel {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  padding: 1rem;
  min-height: 12rem;
}

/* --- Documents: widget-grid x3 --- */
.widget-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
}
.widget-grid > .widget-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  padding: 1rem;
  min-height: 8rem;
}

/* --- Shared layout helpers --- */
.chart-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
  gap: 1rem;
  margin-top: 1rem;
}
.chart-container {
  position: relative;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  padding: 1rem;
  min-height: 16rem;
}
.chart-container canvas {
  width: 100% !important;
  height: 100% !important;
}
.claims-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(14rem, 1fr));
  gap: 0.75rem;
  margin-top: 1rem;
}
.claim-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 0.375rem;
  padding: 0.75rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
  margin-bottom: 1.5rem;
}
.dashboard-panel {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  padding: 1rem;
  min-height: 6rem;
}
```

## Issue 6: Chart Mount / enhancePage — CODE

```js
// nr2-moonshot-ui.js — Chart lifecycle (replace-not-stack)

window.NR2UI = window.NR2UI || {};

(function (NS) {
  const _charts = new WeakMap(); // canvas -> Chart instance

  /**
   * Mount a Chart.js instance on a <canvas>.
   * Replace-not-stack: destroys any existing chart on the exact canvas first.
   */
  NS.mountChart = function (canvas, type = 'bar', data = {}, options = {}) {
    if (!canvas || !(canvas instanceof HTMLCanvasElement)) {
      console.warn('[NR2UI] mountChart requires a <canvas> element');
      return null;
    }

    // Clear Chart.js global registry
    if (window.Chart && Chart.getChart) {
      const existing = Chart.getChart(canvas);
      if (existing) existing.destroy();
    }

    // Clear local WeakMap
    if (_charts.has(canvas)) {
      _charts.get(canvas).destroy();
      _charts.delete(canvas);
    }

    const ctx = canvas.getContext('2d');
    const chart = new Chart(ctx, {
      type,
      data: data.labels ? data : { labels: [], datasets: [] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom' } },
        ...options,
      },
    });

    _charts.set(canvas, chart);
    return chart;
  };

  /**
   * enhancePage — idempotent scan for chart placeholders.
   */
  NS.enhancePage = function () {
    if (!window.Chart) {
      console.warn('[NR2UI] Chart.js not loaded');
      return;
    }

    document.querySelectorAll('.chart-container[data-chart-type]').forEach((container) => {
      let canvas = container.querySelector('canvas');
      if (!canvas) {
        canvas = document.createElement('canvas');
        container.innerHTML = '';
        container.appendChild(canvas);
      }

      // Skip if already mounted
      if (Chart.getChart && Chart.getChart(canvas)) return;

      const type = container.dataset.chartType || 'bar';
      const widgetKey = container.dataset.widget;
      const payload = window.NR2Data?.[widgetKey] || { labels: ['A','B','C'], datasets: [{ label: 'Dataset', data: [3,1,4] }] };

      NS.mountChart(canvas, type, payload);
    });
  };
})(window.NR2UI);
```

```js
// app.js — renderPageView tail hook

async function renderPageView(pageName, data = {}) {
  const canvas = document.getElementById('page-canvas');
  if (!canvas) return;

  // Clear previous view to prevent ghost DOM/charts
  canvas.innerHTML = '';

  const renderers = {
    financial: renderFinancialPage,
    taxes: renderTaxesPage,
    softdent: renderSoftdentPage,
    narratives: renderNarrativesPage,
    claims: renderClaimsPage,
    ar: renderARPage,
    'office-manager': renderOfficeManagerPage,
    documents: renderDocumentsPage,
    quickbooks: renderQuickbooksPage,
    library: renderLibraryPage,
  };

  const renderer = renderers[pageName];
  if (typeof renderer === 'function') {
    renderer(canvas, data);
  } else {
    canvas.innerHTML = `<div class="empty-state">Page <code>${pageName}</code> not found.</div>`;
  }

  // Moonshot hook: mount charts after DOM flush
  if (window.NR2UI?.enhancePage) {
    requestAnimationFrame(() => window.NR2UI.enhancePage());
  }
}
```

## Moonshot Independent Roadmap (next 5 commits)

1. **P1 — Data bind AR/Claims charts**  
   Replace static `NR2Data` fallbacks in `enhancePage` with live HAL widget feeds for `ar.chart1-3` and `claims.chart1-4`.

2. **P2 — QuickBooks layout parity**  
   Align `dashboard-grid`, `chart-large`, and `chart-medium` counts to mockup specs (4/3/3) and add responsive collapse rules.

3. **P3 — Narratives composer wiring**  
   Populate the 4-column `composer-grid` with live note-section bindings (`narratives.section0-3`) and section persistence.

4. **P4 — Softdent collector recovery**  
   Restore `softdent.procedures` and `softdent.claimStatus` dataset exports; update `sourceHealth` to 11/11 connected.

5. **P5 — Lazy mount + debounce**  
   Add `IntersectionObserver` for off-screen chart containers and debounce `enhancePage` to block redundant renders on rapid navigation.

## Operator Smoke Test

- [ ] Navigate to **AR** → verify 3 `.kpi-card` elements and 3 `.chart-container` canvases mount without error.
- [ ] Navigate to **Claims** → verify 4 `.chart-container` doughnut/bar charts and exactly 23 `.claim-card` rows render.
- [ ] Navigate to **Office Manager** → verify 3 `.dashboard-panel` grids and 2 `.chart-container` line charts appear.
- [ ] Navigate to **Documents** → verify 3 `.widget-card` columns in `.widget-grid`.
- [ ] Navigate to **Taxes** → verify `.kpi-grid` 2-column layout and `.kpi-card` styling load from `nr2-mockup-page-vocabulary.css`.
- [ ] Navigate to **Narratives** → verify `.composer-grid` renders 4 columns.
- [ ] Rapid-switch between pages → confirm charts are replaced, not stacked (no canvas count growth in DevTools).
- [ ] Verify `app.js` calls `NR2UI.enhancePage()` once per route inside `requestAnimationFrame`.
- [ ] Confirm no placeholder text remains in AR, Claims, Office Manager, Documents markup.