# Moonshot AI — Issues 4-6 Continuation

**Date:** 2026-07-08  
**Model:** kimi-k2.6 via OPENROUTER_API_KEY  
**Script:** `scripts/run_moonshot_issues_4_6.py`

---

## Issue 4: Missing Chart Panels (per page) — CODE

### `page-canvas.js` (JavaScript)

```javascript
/**
 * page-canvas.js — Issue 4: Panel-count parity renderers
 * Covers: financial, softdent, ar, claims, office-manager, documents
 * Depends on Issue 2 helpers: PageCanvas.resolveData, PageCanvas.hasRenderableData
 */

PageCanvas.renderFinancial = function(pageId, data) {
  const root = document.getElementById('appPage');
  if (!root) return;
  data = this.resolveData('financial', data || {});
  const hasAny = this.hasRenderableData('quickbooks.revenue')
              || this.hasRenderableData('quickbooks.profitAndLoss')
              || this.hasRenderableData('quickbooks.expenses');
  if (!hasAny) {
    root.innerHTML = `<div class="empty-placeholder">No financial data connected</div>`;
    return;
  }
  root.innerHTML = `
    <div class="financial-page">
      <div class="kpi-grid">
        ${this.canvasMetricTile({ title: 'Revenue', value: data.revenue })}
        ${this.canvasMetricTile({ title: 'Expenses', value: data.expenses })}
        ${this.canvasMetricTile({ title: 'Net Income', value: data.netIncome })}
      </div>
      <div class="chart-panel-grid">
        <div class="chart-container" data-hal-widget-key="financialRevenueTrend"></div>
        <div class="chart-container" data-hal-widget-key="financialExpenseBreakdown"></div>
        <div class="chart-container" data-hal-widget-key="financialProfitLoss"></div>
        <div class="chart-container" data-hal-widget-key="financialAging"></div>
      </div>
    </div>
  `;
};

PageCanvas.renderSoftdent = function(pageId, data) {
  const root = document.getElementById('appPage');
  if (!root) return;
  data = this.resolveData('softdent', data || {});
  const hasAny = [
    'softdent.dashboard','softdent.claims','softdent.clinicalNotes',
    'softdent.ar','softdent.newPatients','softdent.treatmentPlans',
    'softdent.caseAcceptance','softdent.hygieneRecall','softdent.operatory',
    'softdent.procedures','softdent.claimStatus'
  ].some(k => this.hasRenderableData(k));
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
        ${this.canvasFunnel?.(data.funnel) || '<div class="empty-state">Funnel data unavailable</div>'}
      </div>
      <div class="widget-grid" data-hal-widget-key="softdentOperatory">
        ${this.operatoryGrid?.(data.operatory) || '<div class="empty-state">Operatory timeline not configured</div>'}
      </div>
      <div class="widget-grid" data-hal-widget-key="softdentRecall">
        ${this.recallTable?.(data.hygieneRecall) || ''}
      </div>
      <div class="chart-panel-grid">
        <div class="chart-container" data-hal-widget-key="softdentProduction">
          ${this.hasRenderableData('softdent.procedures')
            ? this.proceduresTable?.(PageCanvasData.softdentProcedures()) || ''
            : '<div class="empty-state">Procedures loading…</div>'}
        </div>
        <div class="chart-container" data-hal-widget-key="softdentClaimStatus">
          ${this.hasRenderableData('softdent.claimStatus')
            ? this.claimStatusPanel?.(PageCanvasData.softdentClaimStatus()) || ''
            : '<div class="empty-state">Claim status loading…</div>'}
        </div>
        <div class="chart-container" data-hal-widget-key="softdentCollections"></div>
        <div class="chart-container" data-hal-widget-key="softdentAging"></div>
      </div>
    </div>
  `;
};

PageCanvas.renderAr = function(pageId,