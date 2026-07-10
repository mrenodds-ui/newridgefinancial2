# Moonshot AI — More Financial Widgets + Flashy Pro Items (CONSULT ONLY)

**Date:** 2026-07-10  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** hal-10280  
**Script:** `scripts/run_moonshot_more_widgets_flash_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> ask moonshot ai are there any more financial widgets like bar graphs that can be placed in the pages as well as any other flashy highly professional items then report dont code until i approve

---

# Verdict

## 0. Operator Intent (quote; confirm consult-only / no code until approve)

> "ask moonshot ai are there any more financial widgets like bar graphs that can be placed in the pages as well as any other flashy highly professional items then report dont code until i approve"

**CONFIRMED:** This response is **CONSULT ONLY**. No code will be applied to hal-10280 until explicit operator approval (proceed / validated / approve) is received. All deliverables below are speculative specifications for review.

---

## 1. More Financial Widgets (bar graphs and kin)

| Name | Chart/Widget Type | Page(s) | Import Data Source | Priority | Honesty Notes |
|------|-------------------|---------|-------------------|----------|---------------|
| **Provider Production Horizontal Bars** | Horizontal bar (canvas) | Financial, SoftDent | `softdent/provider_production` rows (Provider/Amount) | **MUST** | Shows top providers by volume; empty when no provider breakdown available; anonymized if only practice totals |
| **Payer Mix Donut** | Donut/Pie (SVG) | Financial, Office-Manager | `softdent/payer_summary` or `qb/customer_income` | **SHOULD** | Distribution by carrier; honest "No payer classification" slice if unclassified; never fabricates percentages |
| **A/R Aging Waterfall** | Waterfall (canvas) | A/R | `softdent/ar_aging` buckets (Current→120+) + adjustments | **MUST** | Walks from Gross Charges → Net Collectible; negative steps shown in amber; empty if aging report unavailable |
| **Collection Efficiency Bullet** | Bullet chart (SVG) | A/R, Financial | Calculated: `collections / (production - adjustments)` from `financial_reports` | **SHOULD** | Compares actual ratio to benchmark line; no benchmark = grayed target zone |
| **Expense Treemap** | Treemap (canvas) | QuickBooks, Financial | `qb/expenseCategories` hierarchical (Category/Amount) | **NICE** | Hierarchical spending view; leaf nodes only; honest empty if flat expense list |
| **YoY Sparkline Strip** | Sparkline (mini canvas) | Financial, Taxes | Comparative period columns from `financial_reports` | **SHOULD** | Tiny trendline embedded in KPI header; flat line if single period only |
| **Procedure Velocity Area** | Stacked area (canvas) | Financial, Claims | `softdent/procedure_log` date-aggregated count | **NICE** | Cumulative procedures over time; gap handling for non-business days |
| **Daily Production Range** | Candlestick/Range (canvas) | Financial | `softdent/daily_journals` (Min/Max/Avg per day) | **NICE** | Shows volatility; requires daily granularity; falls back to simple bar if only monthlies |
| **Insurance vs Patient Split** | Stacked horizontal bar | Financial, Office-Manager | `softdent/transaction_types` (Insurance Payment vs Patient Payment) | **MUST** | Composition view; handles partial payments; unallocated payments shown as "Pending" |

---

## 2. Other Flashy Highly Professional Items

**Already Present at hal-10280 (do not duplicate):**
- Phosphor glow, holographic hover lift, corner brackets, ambient scan sweep, sidebar nav LEDs, page-title glitch, grid floor, dual tickers (TELEMETRY + OPS), HAL neural core canvas.

| Instrument | Type | Scope | Priority | Notes |
|------------|------|-------|----------|-------|
| **KPI Numeric Rollup** | Motion | All pages | **MUST** | Count-up animation on value change (0→target); respects `prefers-reduced-motion` (instant snap) |
| **Threshold Alert Pulse** | Chrome/Motion | Financial, A/R, Claims | **MUST** | Subtle amber/red edge-glow on widgets exceeding danger thresholds (A/R >90 days >20%, Denial rate >15%); 3-pulse then steady |
| **Holographic Card Tilt** | Chrome | All mosaic cards | **SHOULD** | 3D perspective tilt following mouse position (max 5deg); disabled for reduced-motion; maintains phosphor glow |
| **Typing Decoder Effect** | Motion | HAL, Narratives | **SHOULD** | Text scrambles through charset before resolving to final value (like satellite decode); 40ms char interval |
| **Timeline Date Scrubber** | Instrument | Financial, Taxes | **MUST** | Horizontal range slider with snap-to-month; updates all widgets on stage via silent refresh; cyan track, amber handle |
| **Focus Mode Expansion** | Chrome | Chart widgets (L/XL) | **SHOULD** | Click-to-expand widget to 90vw with backdrop blur (`backdrop-filter`); ESC to collapse; print-optimized layout |
| **Data Refresh Ripple** | Motion | All pages | **NICE** | Concentric cyan ring emanates from refresh button on data update; 600ms duration; single ripple only |
| **Crosshair Laser Cursor** | Chrome | Chart canvases | **NICE** | Vertical/horizontal hairlines following mouse on hover (cyan 1px); snaps to nearest data point; fades on exit |
| **Sync Breathing Indicator** | Motion | Top TELEMETRY ticker | **NICE** | Subtle 4s opacity pulse on "LIVE" indicator when socket polling active; pauses on error state |

---

## 3. Per-Page Placement Map

**Financial:**  
*Saturated with core instruments.* Add **Provider Production Horizontal Bars** (top of stage), **Payer Mix Donut** (sidebar gap), **YoY Sparklines** (embedded in Morning Brief KPI headers), **Collection Efficiency Bullet** (below liquidity pulse). Enable **Threshold Alert Pulse** on A/R KPI if >90 days exceeds practice threshold.

**Taxes:**  
Add **Timeline Date Scrubber** (stage header, spanning Q1-Q4), **YoY Sparklines** on estimated tax liability cards. Consider watermarked "ESTIMATE" backdrop on empty quarters.

**SoftDent:**  
Add **Procedure Velocity Area** (production trending), **Daily Production Range** (volatility view). Keep existing categorize assist.

**QuickBooks:**  
Add **Expense Treemap** (XL slot) utilizing the new `expenseCategories` hierarchy from 10280 fix. **Horizontal bar** for top vendors by spend.

**A/R:**  
Add **A/R Aging Waterfall** (central XL slot) replacing or augmenting remainder widget. **Threshold Alert Pulse** mandatory on >90 days bucket.

**Claims:**  
Add **Insurance vs Patient Split** (stacked bar showing claim composition). **Crosshair Laser Cursor** on velocity funnel for precise date targeting.

**Narratives:**  
Add **Typing Decoder Effect** for generated narrative text reveals. Saturated otherwise.

**Documents:**  
Saturated — skip or add **Holographic Card Tilt** to file cards only.

**Library:**  
Saturated — skip.

**Office-Manager:**  
Add **Payer Mix Donut** (patient responsibility context), **Insurance vs Patient Split**. **Calculator** remains primary.

**HAL:**  
Saturated with neural core. Add **Typing Decoder Effect** for HAL response text (scramble→resolve).

---

## 4. Moonshot Spec Deliverables (paste-ready, CONSULT ONLY)

### 4.1 Instrument JSON Shapes

```json
{
  "instrument": "horizontal-bar",
  "type": "horizontal-bar",
  "title": "Provider Production",
  "size": "l",
  "dataSource": "softdent/provider_production",
  "config": {
    "barColor": "var(--apex-cyan)",
    "alternateColor": "var(--apex-magenta)",
    "labelKey": "provider",
    "valueKey": "production",
    "maxBars": 8,
    "showValues": true,
    "format": "currency",
    "sort": "desc"
  },
  "emptyState": {
    "message": "No provider breakdown available",
    "icon": "users"
  }
}
```

```json
{
  "instrument": "waterfall",
  "type": "waterfall",
  "title": "A/R Aging Flow",
  "size": "xl",
  "dataSource": "softdent/ar_aging",
  "config": {
    "positiveColor": "var(--apex-cyan)",
    "negativeColor": "var(--apex-amber)",
    "totalColor": "var(--apex-magenta)",
    "steps": [
      {"label": "Gross Charges", "key": "gross", "type": "start"},
      {"label": "Adjustments", "key": "adjustments", "type": "negative"},
      {"label": "Current", "key": "current", "type": "positive"},
      {"label": "31-60", "key": "bucket_31_60", "type": "positive"},
      {"label": "61-90", "key": "bucket_61_90", "type": "positive"},
      {"label": ">90", "key": "bucket_90_plus", "type": "positive"},
      {"label": "Net Collectible", "key": "net", "type": "total"}
    ]
  }
}
```

```json
{
  "instrument": "bullet-chart",
  "type": "bullet",
  "title": "Collection Efficiency",
  "size": "s",
  "dataSource": "calculated/collection_ratio",
  "config": {
    "targetValue": 0.98,
    "ranges": [
      {"max": 0.85, "color": "var(--apex-red)"},
      {"max": 0.95, "color": "var(--apex-amber)"},
      {"max": 1.0, "color": "var(--apex-cyan)"}
    ],
    "unit": "percent"
  }
}
```

```json
{
  "instrument": "sparkline",
  "type": "sparkline",
  "title": "YoY Trend",
  "size": "inline",
  "dataSource": "financial_reports/comparative",
  "config": {
    "lineColor": "var(--apex-cyan)",
    "fillColor": "rgba(0,255,255,0.1)",
    "height": 24,
    "width": 80,
    "periods": 12
  }
}
```

### 4.2 CSS Stubs (Chrome/Motion)

```css
/* CONSULT ONLY - Threshold Alert Pulse */
@keyframes alert-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(255, 160, 0, 0); }
  50% { box-shadow: 0 0 0 4px rgba(255, 160, 0, 0.3); }
}
.apex-alert-pulse {
  animation: alert-pulse 2s ease-in-out 3;
  border: 1px solid var(--apex-amber);
}
@media (prefers-reduced-motion: reduce) {
  .apex-alert-pulse { animation: none; border-width: 2px; }
}

/* CONSULT ONLY - Holographic Tilt */
.apex-holo-tilt {
  transform-style: preserve-3d;
  transition: transform 0.1s ease-out;
}
.apex-holo-tilt:hover {
  /* Transform applied via JS mousemove */
}

/* CONSULT ONLY - Typing Decoder */
.apex-decode-text {
  font-family: var(--apex-mono);
  color: var(--apex-cyan);
}
```

### 4.3 JS Stubs (Motion)

```javascript
// CONSULT ONLY - Numeric Rollup (Count-up)
function animateValue(el, start, end, duration, formatter) {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    el.textContent = formatter(end);
    return;
  }
  const startTime = performance.now();
  function update(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3); // easeOutCubic
    const current = start + (end - start) * eased;
    el.textContent = formatter(current);
    if (progress < 1) requestAnimationFrame(update);
  }
  requestAnimationFrame(update);
}

// CONSULT ONLY - Typing Decoder
function decodeText(element, finalText, charset = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    element.textContent = finalText;
    return;
  }
  let iterations = 0;
  const interval = setInterval(() => {
    element.textContent = finalText.split("").map((char, idx) => {
      if (idx < iterations) return finalText[idx];
      if (char === " ") return " ";
      return charset[Math.floor(Math.random() * charset.length)];
    }).join("");
    if (iterations >= finalText.length) clearInterval(interval);
    iterations += 1/3;
  }, 40);
}
```

---

## 5. Implementation Phases (W0 validate → Wn) + Validation Gate

**W0 — Validation (Pre-code)**  
- Audit current canvas performance on target hardware (dental office tablets/laptops)  
- Verify `expenseCategories` hierarchy depth for treemap viability  
- Confirm operator preference: horizontal bars vs. vertical for provider view  
- **Gate:** Operator approval required to proceed to W1

**W1 — Core Financial Charts (High Impact, Low Risk)**  
- Implement `horizontal-bar` (Provider Production)  
- Implement `donut` (Payer Mix)  
- Implement `bullet` (Collection Efficiency)  
- Add **Threshold Alert Pulse** chrome  
- **Gate:** Visual validation on Financial + A/R pages; verify honest empty states with live imports

**W2 — Advanced Visualization (Medium Impact, Medium Risk)**  
- Implement `waterfall` (A/R Aging Flow)  
- Implement `sparkline` (YoY trends)  
- Implement **Timeline Date Scrubber** instrument  
- **Gate:** Performance test with 12-month data; confirm reduced-motion fallbacks

**W3 — Motion Polish (Nice-to-have, Low Risk)**  
- Implement **Holographic Card Tilt**  
- Implement **Typing Decoder Effect** for HAL  
- Implement **Crosshair Laser Cursor** on charts  
- **Gate:** Accessibility audit; ensure no motion sickness triggers

**W4 — Integration (Optional)**  
- Combine Sparklines into existing KPI headers  
- Add Focus Mode expansion to all XL charts  
- **Final Gate:** Operator sign-off for production deployment

---

## 6. Risks & Rollback

| Risk | Impact | Mitigation | Rollback |
|------|--------|------------|----------|
| **Canvas Performance** | High | Limit to 8 bars, 12-month sparklines; use `will-change` sparingly | Remove `type: "canvas"` widgets from mosaic JSON; fallback to KPI numbers |
| **Motion Sickness** | Medium | Strict `prefers-reduced-motion` media queries; all animations < 600ms | CSS `animation: none !important` override class |
| **Data Misrepresentation** | Critical | Waterfall steps must handle negative values explicitly; no interpolation between import rows | Revert to simple `bar` type; display raw table |
| **Visual Distraction** | Medium | Threshold pulse limited to 3 cycles; no auto-playing animations | Toggle class `apex-flash-disabled` on body |
| **Treemap Complexity** | Low | Max 2 levels deep; honest "Other" aggregation for >10 leaves | Fallback to horizontal bar of top 8 categories |

**Rollback Procedure:**  
All new instruments are additive JSON configurations. To rollback any widget, delete or comment its entry in the page's `mosaic` array in `apex_backend.py`. CSS classes are namespaced `apex-*`; remove link to `apex-enhanced-widgets.css` if required. No database schema changes required.