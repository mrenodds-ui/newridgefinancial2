# Moonshot AI — High-Tech Visual Polish Consult
**Date:** 2026-07-09
**Model:** kimi-k2.5 via OPENROUTER_API_KEY
**Status:** REVIEW ONLY — do not apply until operator validates
**Script:** `scripts/run_moonshot_hightech_visual_consult.py`
**Scope:** Existing live-wire widgets only; CSS/chrome polish to mission-control look

---

# Verdict
Yes. By injecting **Terminal Glass** aesthetics—obsidian chrome (`#0a0a0c`), backdrop-filter blur panels, monospace figures (JetBrains Mono), cyan/gold signal glows, and severity-coded micro-indicators—the live pages will look like a Bloomberg terminal crossed with SpaceX mission control. The delta is purely CSS and class-injection; all data bindings and honest-empty CTAs remain untouched.

---

## 1. Why pages still look like the old schema
| Root Cause | Evidence in Current Build | Fix |
|------------|---------------------------|-----|
| **Flat gray panels** | `var(--bg-elevated)` too light; no `backdrop-filter` | Switch to `rgba(16,16,20,0.72)` + `blur(12px)` |
| **Friendly sans-serif figures** | KPI values render in Inter/System UI | Force `font-family: 'JetBrains Mono'` on all numerics |
| **Loose padding** | 16–20px gaps waste space; looks like a blog | Tight 10–12px grid, 8px internal padding |
| **Missing severity semantics** | No visual "heat" on high A/R or old claims | Left-border color codes + pulsing dots |
| **Static charts** | SVG charts lack scan-line animation | CSS `@keyframes scan` overlay |
| **No accent glow** | Borders stay static on hover | `box-shadow: var(--ms-glow-cyan)` on hover |
| **Kanban looks like a todo list** | Lanes lack header dots & compact density | `.kanban-lane-mission` styling |

---

## 2. Visual Design System (tokens + rules)
```css
/* Core Surface */
--mc-bg: #0a0a0c;
--mc-surface: rgba(16, 16, 20, 0.72);
--mc-border: rgba(255, 255, 255, 0.06);
--mc-border-hover: rgba(255, 255, 255, 0.12);

/* Signal Accents */
--mc-cyan: #22d3ee;
--mc-cyan-glow: 0 0 8px rgba(34, 211, 238, 0.35);
--mc-gold: #d6b15e;
--mc-gold-glow: 0 0 8px rgba(214, 177, 94, 0.35);
--mc-amber: #fbbf24;
--mc-red: #f87171;

/* Typography */
--font-mono: 'JetBrains Mono', 'SF Mono', Consolas, monospace;
--font-ui: Inter, system-ui, sans-serif;

/* Motion Budget (4 rules only) */
1. Scan-line sweep across charts (6s infinite linear)
2. Pulse on "LIVE" indicators (2s infinite)
3. Panel lift on hover (transform 0.2s)
4. Severity dot blink for critical items (1.5s infinite)
```

**Hard Rules**
- All currency/integers use `font-variant-numeric: tabular-nums`.
- No border-radius > 8px (sharp instruments, not pillows).
- Empty states render as "AWAITING IMPORT" monospace badge, never fake $0.00.
- Emoji banned in titles; use CSS `::before` dots for status.

---

## 3. Page-by-page polish plan
Uses **existing widget keys only**; changes are CSS class injections or markup wrappers.

| Page | Current Weak Spot | Target Look | Existing Widgets Emphasized | CSS/Class Changes |
|------|-------------------|-------------|------------------------------|-------------------|
| **financial** | Generic KPI row, loose padding | Trading-floor density; 5 KPIs with sparklines | `heroKpiRow` (5 tiles), `nr2MonthlyTrendCombo` (dual chart), `nr2CollectionLag` (gauge) | `.kpi-mono` on values; `.ms-panel-obsidian` on panels; sparkline CSS animation |
| **softdent** | Plain operatory table | Heat-map "war room" | `softdentOperatoryGrid` (heatmap), `softdentProviderProduction` (table) | `.heatmap-cell` severity colors (hot/warm/cool); `.operatory-mission` compact grid |
| **quickbooks** | White table backgrounds | IRS Terminal—glass with blue left-border | `quickbooksProfitLossDetail` (table), `quickbooksNetIncomeSummary` (stat-grid), `ebitdaNormalization` | `.glass-qb` accent class; monospace figures in tables; EBITDA waterfall bars via stat-grid styling |
| **ar** | Static aging list | Severity-coded rows; red glow >90 days | `quickbooksArAging`, `softdentClaimsOutstanding` | Row `.severity-high` border-left; `.glow-red` on aged balances |
| **taxes** | Form-like spacing | "Tax Terminal" amber accents | `quickbooksCashFlowTrend` (dual chart), `accountsPayableAutomation` (table) | `.tax-terminal` amber theme; compact `.compact-table` density |
| **claims** | 6-lane kanban looks like Trello | SpaceX pipeline—lanes with dot headers, severity cards | `claimsPipeline` (kanban), `claimsFunnel` | `.kanban-lane-mission` headers; `.severity-dot` (high/med/low) on cards; lane-specific glow |
| **narratives** | Draft list looks like email | Clinical Composer—pink glass, print-ready | `narrativeWorkflow` (kanban), `narrativeTemplates` | `.narrative-glass` pink accent; print icon CSS; status dots via `::before` |
| **documents** | File explorer aesthetic | Secure Vault—gold borders on "classified" docs | `documentVault` (table/grid) | `.doc-vault` gold left-border; monospace doc IDs |
| **library** | Card grid | Archive Terminal—cyan active states | `libraryResources` (stat-grid/table) | `.library-terminal` cyan hover glow |
| **office-manager** | Ops dashboard generic | Command Center—live pulse indicators | `opsDataPanel`, `officeKpis` (stats bar) | `.command-center`; `.live-pulse` dot animation |
| **hal** | Chat interface | HAL 9000 logs—red glow, monospace transcript | `halConversation`, `halLogs` | `.hal-interface` red accent glow; transcript glass panels |

---

## 4. Moonshot Code Deliverables

### File: `NewRidgeFinancial2/site/nr2-mission-control-glass.css`
```css
/**
 * Moonshot Mission Control — Terminal Glass Aesthetic
 * Scope: .app--moonshot-mockup .ms-page.ms-mission-control
 * P0: Paste after nr2-moonshot-glow.css
 */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap');

.app--moonshot-mockup .ms-page.ms-mission-control {
  --mc-bg: #0a0a0c;
  --mc-surface: rgba(16, 16, 20, 0.72);
  --mc-border: rgba(255, 255, 255, 0.06);
  --mc-border-hover: rgba(255, 255, 255, 0.12);
  --mc-cyan: #22d3ee;
  --mc-cyan-glow: 0 0 8px rgba(34, 211, 238, 0.35);
  --mc-gold: #d6b15e;
  --mc-gold-glow: 0 0 8px rgba(214, 177, 94, 0.35);
  --mc-amber: #fbbf24;
  --mc-red: #f87171;
  --mc-green: #34d399;
  --font-mono: 'JetBrains Mono', 'SF Mono', Consolas, monospace;
  
  background: var(--mc-bg);
  color: #e5e7eb;
  font-family: Inter, system-ui, sans-serif;
}

/* Shell Density */
.app--moonshot-mockup .ms-page.ms-mission-control .widget-grid {
  gap: 12px;
  padding: 16px;
}

/* Obsidian Glass Panel (replaces .card, .panel) */
.app--moonshot-mockup .ms-page.ms-mission-control .ms-panel-obsidian,
.app--moonshot-mockup .ms-page.ms-mission-control .canvas-panel,
.app--moonshot-mockup .ms-page.ms-mission-control .kpi-tile {
  background: var(--mc-surface);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--mc-border);
  border-radius: 8px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.35);
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}
.app--moonshot-mockup .ms-page.ms-mission-control .ms-panel-obsidian:hover,
.app--moonshot-mockup .ms-page.ms-mission-control .canvas-panel:hover,
.app--moonshot-mockup .ms-page.ms-mission-control .kpi-tile:hover {
  border-color: var(--mc-border-hover);
  box-shadow: var(--mc-cyan-glow);
  transform: translateY(-1px);
}

/* Monospace Figures (KPIs, Tables, Charts) */
.app--moonshot-mockup .ms-page.ms-mission-control .kpi-mono,
.app--moonshot-mockup .ms-page.ms-mission-control .kpi-value,
.app--moonshot-mission-control .figure,
.app--moonshot-mockup .ms-page.ms-mission-control td.numeric,
.app--moonshot-mockup .ms-page.ms-mission-control .chart-value {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.01em;
}

/* KPI Hero Density */
.app--moonshot-mockup .ms-page.ms-mission-control .kpi-hero-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 10px;
  margin-bottom: 12px;
}
.app--moonshot-mockup .ms-page.ms-mission-control .kpi-hero-tile {
  padding: 12px;
  position: relative;
  overflow: hidden;
}
.app--moonshot-mockup .ms-page.ms-mission-control .kpi-hero-tile::before {
  content: "";
  position: absolute;
  top: 0; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, transparent, var(--mc-cyan), transparent);
  opacity: 0.6;
}
.app--moonshot-mockup .ms-page.ms-mission-control .kpi-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #94a3b8;
  margin-bottom: 4px;
}
.app--moonshot-mockup .ms-page.ms-mission-control .kpi-value {
  font-size: 24px;
  font-weight: 600;
  color: #f0f0f2;
}

/* Severity Indicators */
.app--moonshot-mockup .ms-page.ms-mission-control .severity-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  display: inline-block;
  margin-right: 6px;
}
.app--moonshot-mockup .ms-page.ms-mission-control .severity-dot.high { background: var(--mc-red); box-shadow: 0 0 6px var(--mc-red); }
.app--moonshot-mockup .ms-page.ms-mission-control .severity-dot.med { background: var(--mc-amber); }
.app--moonshot-mockup .ms-page.ms-mission-control .severity-dot.low { background: var(--mc-green); }

/* Row Severity Borders (Tables) */
.app--moonshot-mockup .ms-page.ms-mission-control tr.severity-high td:first-child { border-left: 3px solid var(--mc-red); }
.app--moonshot-mockup .ms-page.ms-mission-control tr.severity-med td:first-child { border-left: 3px solid var(--mc-amber); }
.app--moonshot-mockup .ms-page.ms-mission-control tr.severity-low td:first-child { border-left: 3px solid var(--mc-green); }

/* Mission Kanban (Claims, Narratives) */
.app--moonshot-mockup .ms-page.ms-mission-control .kanban-mission {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 10px;
  height: calc(100vh - 260px);
}
.app--moonshot-mockup .ms-page.ms-mission-control .kanban-lane-mission {
  background: var(--mc-surface);
  border: 1px solid var(--mc-border);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.app--moonshot-mockup .ms-page.ms-mission-control .kanban-lane-mission .lane-header {
  padding: 10px 12px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #94a3b8;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.app--moonshot-mockup .ms-page.ms-mission-control .kanban-lane-mission .lane-header::before {
  content: "";
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--mc-cyan);
  margin-right: 8px;
  box-shadow: 0 0 6px var(--mc-cyan);
}
.app--moonshot-mockup .ms-page.ms-mission-control .kanban-lane-mission:nth-child(1) .lane-header::before { background: #a78bfa; box-shadow: 0 0 6px #a78bfa; } /* Draft */
.app--moonshot-mockup .ms-page.ms-mission-control .kanban-lane-mission:nth-child(2) .lane-header::before { background: var(--mc-cyan); }
.app--moonshot-mockup .ms-page.ms-mission-control .kanban-lane-mission:nth-child(3) .lane-header::before { background: var(--mc-green); }
.app--moonshot-mockup .ms-page.ms-mission-control .kanban-lane-mission .lane-body {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.app--moonshot-mockup .ms-page.ms-mission-control .kanban-card-mission {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 6px;
  padding: 10px;
  font-size: 12px;
  position: relative;
  cursor: pointer;
  transition: border-color 0.15s, transform 0.15s;
}
.app--moonshot-mockup .ms-page.ms-mission-control .kanban-card-mission:hover {
  border-color: rgba(34,211,238,0.3);
  transform: translateY(-2px);
}

/* Chart Scanline Animation */
@keyframes scan {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}
.app--moonshot-mockup .ms-page.ms-mission-control .chart-container {
  position: relative;
  overflow: hidden;
}
.app--moonshot-mockup .ms-page.ms-mission-control .chart-container::after {
  content: "";
  position: absolute;
  top: 0; left: 0; width: 100%; height: 100%;
  background: linear-gradient(90deg, transparent, rgba(34,211,238,0.04), transparent);
  animation: scan 6s linear infinite;
  pointer-events: none;
}

/* Live Pulse Indicator */
@keyframes live-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.app--moonshot-mockup .ms-page.ms-mission-control .live-indicator::before {
  content: "";
  display: inline-block;
  width: 6px; height: 6px;
  background: var(--mc-green);
  border-radius: 50%;
  margin-right: 6px;
  animation: live-pulse 2s infinite;
  box-shadow: 0 0 6px var(--mc-green);
}

/* Honest Empty State (Terminal Style) */
.app--moonshot-mockup .ms-page.ms-mission-control .empty-terminal {
  font-family: var(--font-mono);
  font-size: 12px;
  color: #64748b;
  border: 1px dashed rgba(255,255,255,0.1);
  padding: 20px;
  text-align: center;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

/* Accent Overrides per Page */
.app--moonshot-mockup .ms-page.ms-mission-control.quickbooks-moonshot .ms-panel-obsidian:hover { box-shadow: 0 0 8px rgba(96,165,250,0.35); }
.app--moonshot-mockup .ms-page.ms-mission-control.narratives-moonshot .ms-panel-obsidian:hover { box-shadow: 0 0 8px rgba(244,114,182,0.35); }
.app--moonshot-mockup .ms-page.ms-mission-control.taxes-moonshot .ms-panel-obsidian:hover { box-shadow: 0 0 8px rgba(251,191,36,0.35); }
.app--moonshot-mockup .ms-page.ms-mission-control.hal-moonshot .ms-panel-obsidian:hover { box-shadow: 0 0 8px rgba(248,113,113,0.35); }
```

### File: `NewRidgeFinancial2/site/deferred-live-wire/moonshot-layout-engine.js` (Patch)
**P1: Inject mission-control class and monospace wrappers**
Replace the `pageClass` construction in the `render` function (~line 90):

```javascript
  // REPLACE existing pageClass ternary block with:
  const baseClass = `${pageId}-moonshot`;
  const missionClass = "ms-mission-control";
  const pageClass = `${baseClass} ${missionClass}`;
```

**Add KPI mono wrapper in heroKpi rendering** (~line 180, inside `renderWidgetGridPanel` where `kpi` objects are rendered):

```javascript
  // When rendering KPI value strings, ensure they wrap with <span class="kpi-mono">
  // Example modification inside the hero-kpi block:
  const valueHtml = `<span class="kpi-mono">${H.esc(kpi.value || "—")}</span>`;
  // Use valueHtml instead of direct escape in the template
```

**Kanban lane class injection** (~line 350, in `canvasKanbanLanes` or equivalent):

```javascript
  // Ensure kanban containers get .kanban-mission and lanes get .kanban-lane-mission
  // When constructing lane HTML:
  const laneClass = `kanban-lane-mission ${lane.accent ? 'accent-'+lane.accent : ''}`;
```

### File: `NewRidgeFinancial2/site/page-canvas.js` (Patch)
**P2: Honest empty state styling and table row severity**

In `canvasEmptyFor` (~line 50), wrap output:

```javascript
  return `<div class="empty-terminal">${ctaText}</div>`;
```

In `canvasTable` row generation (~line 400), add severity class mapping:

```javascript
  // Map row.severity ('high'|'med'|'low') to CSS class
  const severityClass = row.severity ? `severity-${row.severity}` : '';
  return `<tr class="${severityClass}">...</tr>`;
```

In `canvasKanbanLanes` (~line 600), emit mission markup:

```javascript
  // Use kanban-mission wrapper and kanban-lane-mission per lane
  // Add severity dot if item.severity exists:
  const dot = item.severity ? `<span class="severity-dot ${item.severity}"></span>` : '';
```

---

## 5. Diff vs Jul 8 elite mockups
| Elite Mockup (Static) | This Live-Wire Change |
|-----------------------|----------------------|
| Hardcoded fake data in HTML | **Honest CTAs** when imports missing; real data inherits glass styling |
| Static SVG charts | **CSS-animated** charts (scanline) with live data hooks |
| Fixed color themes per page | **Dynamic accent injection** via `accentFor(pageId)` mapped to CSS variables |
| Perfect dummy kanban cards | **Empty-terminal states** naming exact export files (e.g., "Load `softdent_production.csv`") |
| No HAL integration | HAL widget chrome respects `.hal-moonshot` red glow |

---

## 6. Operator Validation Gate
Before approving merge, verify in browser:

- [ ] **Financial**: Hero row shows 5 KPI tiles with monospace values; hovering any tile lifts it with cyan glow.
- [ ] **Claims**: 6 kanban lanes visible; lane headers have colored dots; claim cards with `severity: 'high'` show red left border and pulsing red dot.
- [ ] **QuickBooks**: Profit & Loss table numbers are right-aligned monospace; rows have no extra padding (compact density).
- [ ] **Narratives**: Pink glow on hover; print button present in toolbar (existing hal-10164 feature); kanban cards show status dots.
- [ ] **Empty State Test**: Rename import to break data bind → page shows "AWAITING IMPORT" terminal badge (not $0.00).
- [ ] **No Emoji**: Confirm zero emoji characters in panel titles (e.g., "Claims" not "Claims 📋").

---

## 7. Prioritized apply order (max 4 commits) — WAIT for operator "proceed"
1. **P0 — `nr2-mission-control-glass.css`**: Paste into site root; link in `index.html` after `nr2-moonshot-glow.css`. *Pure CSS, zero risk to data.*
2. **P1 — `moonshot-layout-engine.js` patch**: Inject `ms-mission-control` class to all staff pages. *Enables CSS scoping.*
3. **P2 — `page-canvas.js` polish**: Add `kpi-mono` wrappers, `empty-terminal` class, severity row classes. *Completes the wiring.*
4. **P3 — Spot fixes**: Per-page accent verification (e.g., ensure `quickbooks-moonshot` gets blue hover glow). *Visual QA only.*

**Do not proceed past P0 without operator confirmation that CSS loads without 404.**
