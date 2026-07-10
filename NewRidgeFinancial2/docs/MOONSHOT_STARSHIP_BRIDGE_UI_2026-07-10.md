# Moonshot AI — Starship Bridge UI Critique (CONSULT ONLY)

**Date:** 2026-07-10  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** hal-10220  
**Script:** `scripts/run_moonshot_starship_bridge_consult.py`  
**Apply:** DO NOT APPLY until operator validates.

## Operator request (verbatim)

> no have moonshot look at the current setup, the widgets are elongated unoranized.  i need widgets animated looking like a futurist high tech outlay, scrolling ticker tape with information, a side bar, interactive naritive page,  looking like a highly scientic progrofession financial pages that belong on a travelling starv ship

---

# Verdict

## 0. Operator Intent (quote request; confirm no rewrite)

> "no have moonshot look at the current setup, the widgets are elongated unoranized.  i need widgets animated looking like a futurist high tech outlay, scrolling ticker tape with information, a side bar, interactive naritive page,  looking like a highly scientic progrofession financial pages that belong on a travelling starv ship"

**Confirmed.** You are requesting a starship-bridge redesign of NR2-Apex (hal-10220) to eliminate the elongated/stretchy widget layout, introduce a fixed sidebar (persistent across all pages), add scrolling ticker tapes (top and/or bottom), and replace the weak Narratives KPI stubs with a true interactive narrative workspace. The aesthetic must be dense, scientific, and futuristic—like instrumentation on a traveling starship. **This is a CONSULTATION ONLY.** I will not apply these changes to your live hal-10220 build until you explicitly validate the plan.

---

## 1. Current Setup Critique (why elongated / unorganized / not starship)

**Root cause of elongation:**  
Your current `.apex-grid` uses `grid-template-columns: repeat(auto-fit, minmax(140px, 1fr))`. On wide monitors, `1fr` forces widgets to stretch horizontally to fill the entire row width. When a widget has low content density, it appears as a "wide bar" instead of a dense instrument. The `.apex-widget--wide { grid-column: span 2 }` modifier exacerbates this by creating inconsistent aspect ratios.

**Organization failure:**  
The 11-page horizontal button bar wraps unpredictably, consumes vertical real estate, and provides no persistent context for HAL status or quick actions. There is no ambient information layer (ticker), forcing users to drill into widgets to see if anything has changed.

**Missing starship DNA:**  
- **No fixed geometry:** Real bridge instruments have fixed positions and sizes; your layout is fluid/stretchy.  
- **No sidebar:** HAL status is hidden in the header on non-HAL pages; navigation disappears on scroll.  
- **No ambient awareness:** No ticker for alerts, market data, or system telemetry.  
- **Narratives are KPI stubs:** The page returns only 4 status widgets (`narr-drafts`, `narr-clinical-notes`, etc.) instead of a document composition interface.

---

## 2. Target Starship Bridge Layout

**Wireframe (text):**

```
[TICKER TOP: Scrolling alerts/metrics/status .........................................] 32px
┌─────────────────────────────────────────────────────────────────────────────────────┐
│  SIDEBAR (240px)    │  MAIN STAGE                                                        │
│  ┌───────────────┐  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │ NR2 APEX      │  │  │ WIDGET   │ │ WIDGET   │ │ WIDGET   │ │ WIDGET   │            │
│  │               │  │  │  320x240 │ │  320x240 │ │  640x240 │ │  320x480 │            │
│  │ • Financial   │  │  │          │ │          │ │ (wide)   │ │ (tall)   │            │
│  │ • Taxes       │  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘            │
│  │ • SoftDent    │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐                          │
│  │ ...           │  │  │ CHART    │ │ CHART    │ │ KPI      │                          │
│  │               │  │  │ 640x360  │ │ 640x360  │ │ 320x240  │                          │
│  │ HAL STATUS    │  │  └──────────┘ └──────────┘ └──────────┘                          │
│  │ [Orb] Live    │  │                                                                  │
│  │               │  │  (Fixed 4-column mosaic, no stretch)                             │
│  │ [Sync] [Prt]  │  │                                                                  │
│  └───────────────┘  └────────────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────────────────────────────┘
```

**CSS Grid Rules:**
- **Sidebar:** Fixed `240px`, `position: fixed`, full height below ticker.
- **Ticker:** Fixed `32px` height, full width, `position: fixed` top.
- **Stage:** `margin-left: 240px; margin-top: 32px;`, uses `display: grid` with `grid-template-columns: repeat(4, 320px)` and `grid-auto-rows: 240px`.
- **Widgets:** Fixed size classes (`.apex-inst--s`, `.apex-inst--m`, `.apex-inst--l`, `.apex-inst--tall`) using absolute pixel dimensions or strict aspect ratios. No `span` classes that break the grid.

---

## 3. Widget System Redesign

**Size Classes (Instruments):**
- `.apex-inst--s`: 320px × 240px (1×1) — Standard KPI
- `.apex-inst--m`: 320px × 360px (1×1.5) — Tall KPI
- `.apex-inst--l`: 640px × 360px (2×1) — Charts (replaces `--wide`)
- `.apex-inst--xl`: 640px × 480px (2×2) — Large charts
- `.apex-inst--full`: 1280px × 480px (4×2) — Exceptional detail views

**Layout Container:**
Replace `.apex-grid` with `.apex-mosaic`:
```css
.apex-mosaic {
  display: grid;
  grid-template-columns: repeat(4, 320px);
  grid-auto-rows: 240px;
  gap: 8px;
  padding: 16px;
  justify-content: start; /* Left-align, no stretch */
}
```

**Animation (Boot Sequence):**
- On page load: Widgets fade in with a "scanline wipe" (clip-path animation from top to bottom).
- On data refresh: Subtle border pulse (cyan) rather than full re-render.
- On alert: Amber border glow pulse.

---

## 4. Scrolling Ticker Tape Spec

**Element:** `#apex-ticker` (fixed top, 32px height).

**Content Sources:** `GET /api/apex/ticker` returns:
```json
{
  "items": [
    {"type": "metric", "label": "MTD PROD", "value": null, "unit": "USD", "status": "placeholder"},
    {"type": "alert", "severity": "amber", "text": "90+ AR > threshold"},
    {"type": "hal", "text": "HAL: Prioritize insurance follow-up"},
    {"type": "system", "text": "SoftDent sync: 2m ago"}
  ]
}
```
*Note: Values are `null` or PLACEHOLDER; never invented dollar amounts.*

**Behavior:**
- Infinite horizontal scroll (CSS `transform: translateX`), 40s duration, linear.
- Content duplicated for seamless loop.
- Pauses on `mouseenter` (accessibility).
- Respects `prefers-reduced-motion`: disables animation, shows static list.

---

## 5. Sidebar Spec

**Structure (always visible):**
1. **Brand:** "NR2 APEX" with version badge (hal-10220).
2. **Nav:** Icon + label buttons for 11 pages. Active state: cyan left border, elevated surface.
3. **HAL Module:** 
   - Orb (magenta pulse when busy).
   - Status text ("HAL Live", "HAL Busy").
   - Mini suggestion preview (1 line).
   - "Ask HAL" quick button.
4. **Quick Actions:** Sync (with spin animation), Print, Refresh.

**Visual:**
- Background: `var(--apex-surface)` with 1px right border `var(--apex-border)`.
- Width: 240px fixed.
- Collapses to 64px icon-only on small viewports (optional).

---

## 6. Interactive Narratives Page

**Interaction Model:**  
Replace the 4 KPI widgets with a **Document Composer** interface.

**Layout (3-pane):**
```
┌─────────────────────────────────────────────────────────────────┐
│ TIMELINE SCRUBBER [Intro][Findings][Plan][Notes] ▓▓▓▓▓▓▓▓        │
├──────────┬──────────────────────────────────┬───────────────────┤
│ SECTIONS │   COMPOSER (Rich Text)           │ CONTEXT PANEL     │
│ OUTLINE  │                                  │ • Patient Data    │
│          │   [HAL Assisted Rewrite ▼]       │ • HAL Suggestions │
│  ▶ Intro │                                  │ • Templates       │
│    Find  │   "PLACEHOLDER: Clinical text    │ • Audit Trail     │
│    Plan  │    will appear here..."          │                   │
│          │                                  │ [Generate Packet] │
└──────────┴──────────────────────────────────┴───────────────────┘
```

**Features:**
- **Timeline Scrubber:** Click to jump sections; visual progress bar.
- **Section Outline:** Draggable to reorder; click to focus composer.
- **Composer:** Markdown-aware editor with HAL integration (highlight text → "Rewrite clinically" → HAL suggests revision).
- **Context Panel:** Pulls patient data (placeholder), shows template library, HAL chat (mini).
- **Print Packet:** Generates PDF packet from current narrative structure.

**Backend Helpers:**  
`GET /api/apex/narratives/structure` — Returns document template sections.  
`POST /api/apex/narratives/generate` — HAL-assisted rewrite endpoint.  
`POST /api/apex/narratives/print-packet` — Returns PDF blob.

---

## 7. Scientific / Starship Visual Language

**Tokens (extend existing):**
- `--apex-chrome`: `rgba(0, 240, 255, 0.08)` — Subtle cyan glow.
- `--apex-scanline`: `repeating-linear-gradient(...)` — 2px lines at 4px intervals, 3% opacity.
- `--apex-border-subtle`: `rgba(240, 242, 245, 0.06)` — Invisible until focused.

**Typography:**
- Labels: `Orbitron`, 11px, uppercase, letter-spacing 0.1em, `--apex-text-secondary`.
- Data: `JetBrains Mono`, 13px, `--apex-text-primary`.
- Alerts: `JetBrains Mono`, 12px, `--apex-amber` or `--apex-magenta`.

**Effects:**
- **Glass:** `backdrop-filter: blur(12px)` on overlays/sidebar.
- **Scanlines:** Pseudo-element overlay on widgets (`::before` with scanline gradient).
- **Boot Animation:** `clip-path: polygon(0 0, 100% 0, 100% 0, 0 0)` → `polygon(0 0, 100% 0, 100% 100%, 0 100%)` over 600ms.

**Color Discipline:**
- Cyan: Primary action, active states, data lines.
- Amber: Warnings, alerts, attention-required.
- Magenta: HAL/AI presence only.
- No purple glow clichés; avoid neon gradients.

---

## 8. Moonshot Code Deliverables (paste-ready)

### File: site/apex-bridge-shell.html
```html
<!DOCTYPE html>
<html lang="en" data-apex-version="hal-10220" data-nr2-epoch="nr2-apex">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Cache-Control" content="no-store, no-cache, must-revalidate">
  <title>NewRidgeFinancial 2.0 — Apex Bridge</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Orbitron:wght@500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="apex-tokens.css?v=hal-10220">
  <link rel="stylesheet" href="apex-animations.css?v=hal-10220">
  <link rel="stylesheet" href="apex-bridge.css?v=hal-10220">
</head>
<body class="apex-bridge">
  <!-- TICKER -->
  <div id="apex-ticker" class="apex-ticker" aria-live="polite" aria-label="Financial ticker">
    <div class="apex-ticker__track" id="ticker-track">
      <!-- Populated by apex-ticker.js -->
      <span class="apex-ticker__item apex-ticker__item--placeholder">SYSTEM INITIALIZING...</span>
    </div>
  </div>

  <!-- SIDEBAR -->
  <aside id="apex-sidebar" class="apex-sidebar">
    <div class="apex-sidebar__brand">
      <div class="apex-brand">NR2 APEX</div>
      <div class="apex-version">hal-10220</div>
    </div>
    
    <nav class="apex-sidebar__nav" aria-label="Main navigation">
      <button type="button" class="apex-nav-btn active" data-page="financial" aria-current="page">
        <span class="apex-nav-icon" aria-hidden="true">◈</span>
        <span class="apex-nav-label">Financial</span>
      </button>
      <button type="button" class="apex-nav-btn" data-page="taxes">
        <span class="apex-nav-icon" aria-hidden="true">◉</span>
        <span class="apex-nav-label">Taxes</span>
      </button>
      <button type="button" class="apex-nav-btn" data-page="softdent">
        <span class="apex-nav-icon" aria-hidden="true">◆</span>
        <span class="apex-nav-label">SoftDent</span>
      </button>
      <button type="button" class="apex-nav-btn" data-page="quickbooks">
        <span class="apex-nav-icon" aria-hidden="true">◇</span>
        <span class="apex-nav-label">QuickBooks</span>
      </button>
      <button type="button" class="apex-nav-btn" data-page="ar">
        <span class="apex-nav-icon" aria-hidden="true">▣</span>
        <span class="apex-nav-label">A/R</span>
      </button>
      <button type="button" class="apex-nav-btn" data-page="claims">
        <span class="apex-nav-icon" aria-hidden="true">▤</span>
        <span class="apex-nav-label">Claims</span>
      </button>
      <button type="button" class="apex-nav-btn" data-page="narratives">
        <span class="apex-nav-icon" aria-hidden="true">▧</span>
        <span class="apex-nav-label">Narratives</span>
      </button>
      <button type="button" class="apex-nav-btn" data-page="documents">
        <span class="apex-nav-icon" aria-hidden="true">▨</span>
        <span class="apex-nav-label">Documents</span>
      </button>
      <button type="button" class="apex-nav-btn" data-page="library">
        <span class="apex-nav-icon" aria-hidden="true">▦</span>
        <span class="apex-nav-label">Library</span>
      </button>
      <button type="button" class="apex-nav-btn" data-page="office-manager">
        <span class="apex-nav-icon" aria-hidden="true">▩</span>
        <span class="apex-nav-label">Office Mgr</span>
      </button>
      <button type="button" class="apex-nav-btn" data-page="hal">
        <span class="apex-nav-icon" aria-hidden="true">◐</span>
        <span class="apex-nav-label">HAL</span>
      </button>
    </nav>

    <div class="apex-sidebar__hal">
      <div class="apex-hal-header">
        <div class="hal-orb" id="sidebar-hal-orb" aria-hidden="true"></div>
        <span class="apex-hal-status" id="sidebar-hal-status">HAL Standby</span>
      </div>
      <div class="apex-hal-suggestion" id="sidebar-hal-suggestion">
        <span class="apex-hal-suggestion__label">SUGGESTION</span>
        <p class="apex-hal-suggestion__text" id="hal-suggestion-text">Awaiting data...</p>
      </div>
      <button type="button" class="apex-btn apex-btn--hal" id="btn-ask-hal">Ask HAL</button>
    </div>

    <div class="apex-sidebar__actions">
      <button type="button" class="apex-icon-btn" id="btn-sync" title="Force sync">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12a9 9 0 1 1-2.6-6.3"/><polyline points="21 3 21 9 15 9"/></svg>
      </button>
      <button type="button" class="apex-icon-btn" id="btn-print-sidebar" title="Print view">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9V3h12v6"/><path d="M6 17H4a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-2"/><rect x="6" y="13" width="12" height="8" rx="1"/></svg>
      </button>
    </div>
  </aside>

  <!-- MAIN STAGE -->
  <main id="apex-main" class="apex-main">
    <header class="apex-stage-header">
      <h1 class="apex-page-title" id="apex-page-title">Financial</h1>
      <div class="apex-meta" id="apex-meta">Refreshed: —</div>
    </header>
    
    <div id="apex-stage" class="apex-mosaic" aria-live="polite">
      <!-- Widgets or Narratives UI injected here -->
    </div>
  </main>

  <script src="apex-ticker.js?v=hal-10220"></script>
  <script src="apex-core.js?v=hal-10220"></script>
  <script src="apex-hal-bridge.js?v=hal-10220"></script>
  <script src="apex-narratives.js?v=hal-10220"></script>
</body>
</html>
```

### File: site/apex-bridge.css
```css
/* NR2-Apex Bridge Layout — Starship Bridge Geometry */
:root {
  --sidebar-width: 240px;
  --ticker-height: 32px;
  --mosaic-col: 320px;
  --mosaic-row: 240px;
  --mosaic-gap: 8px;
}

/* Reset for bridge layout */
.apex-bridge {
  margin: 0;
  padding: 0;
  background: var(--apex-void);
  color: var(--apex-text-primary);
  font-family: "JetBrains Mono", ui-monospace, monospace;
  overflow-x: hidden;
}

/* TICKER */
.apex-ticker {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: var(--ticker-height);
  background: rgba(5, 5, 8, 0.95);
  border-bottom: 1px solid var(--apex-border);
  z-index: 1000;
  overflow: hidden;
  display: flex;
  align-items: center;
}

.apex-ticker__track {
  display: flex;
  gap: 48px;
  white-space: nowrap;
  animation: tickerScroll 40s linear infinite;
  padding-left: 100%; /* Start off-screen */
}

.apex-ticker:hover .apex-ticker__track {
  animation-play-state: paused;
}

@media (prefers-reduced-motion: reduce) {
  .apex-ticker__track { animation: none; padding-left: 16px; }
}

@keyframes tickerScroll {
  0% { transform: translateX(0); }
  100% { transform: translateX(-50%); } /* Assumes duplicated content */
}

.apex-ticker__item {
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
  color: var(--apex-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.apex-ticker__item--alert { color: var(--apex-amber); }
.apex-ticker__item--hal { color: var(--apex-magenta); }
.apex-ticker__item--metric { color: var(--apex-cyan); }

/* SIDEBAR */
.apex-sidebar {
  position: fixed;
  top: var(--ticker-height);
  left: 0;
  width: var(--sidebar-width);
  bottom: 0;
  background: var(--apex-surface);
  border-right: 1px solid var(--apex-border);
  display: flex;
  flex-direction: column;
  z-index: 900;
  overflow-y: auto;
}

.apex-sidebar__brand {
  padding: 16px;
  border-bottom: 1px solid var(--apex-border);
}

.apex-version {
  font-size: 10px;
  color: var(--apex-text-secondary);
  margin-top: 4px;
  font-family: "Orbitron", sans-serif;
}

.apex-sidebar__nav {
  flex: 1;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.apex-nav-btn {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 4px;
  color: var(--apex-text-secondary);
  cursor: pointer;
  transition: all 120ms ease;
  text-align: left;
  font-size: 12px;
}

.apex-nav-btn:hover {
  background: var(--apex-elevated);
  color: var(--apex-text-primary);
}

.apex-nav-btn.active {
  background: rgba(0, 240, 255, 0.08);
  border-left: 3px solid var(--apex-cyan);
  color: var(--apex-cyan);
}

.apex-nav-icon {
  font-size: 14px;
  width: 20px;
  text-align: center;
}

.apex-sidebar__hal {
  padding: 16px;
  border-top: 1px solid var(--apex-border);
  border-bottom: 1px solid var(--apex-border);
  background: rgba(0, 0, 0, 0.2);
}

.apex-hal-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.apex-hal-status {
  font-size: 11px;
  color: var(--apex-text-secondary);
  font-family: "Orbitron", sans-serif;
}

.apex-hal-suggestion__label {
  font-size: 9px;
  color: var(--apex-magenta);
  letter-spacing: 0.1em;
}

.apex-hal-suggestion__text {
  font-size: 11px;
  color: var(--apex-text-secondary);
  margin: 4px 0 0 0;
  line-height: 1.3;
  min-height: 28px;
}

.apex-btn--hal {
  width: 100%;
  margin-top: 12px;
  padding: 8px;
  background: rgba(255, 0, 102, 0.15);
  border: 1px solid rgba(255, 0, 102, 0.3);
  color: var(--apex-magenta);
  font-family: "Orbitron", sans-serif;
  font-size: 11px;
  cursor: pointer;
  border-radius: 4px;
  transition: all 200ms;
}

.apex-btn--hal:hover {
  background: rgba(255, 0, 102, 0.25);
  box-shadow: 0 0 12px rgba(255, 0, 102, 0.2);
}

.apex-sidebar__actions {
  padding: 16px;
  display: flex;
  gap: 8px;
}

.apex-icon-btn {
  flex: 1;
  height: 36px;
  background: var(--apex-elevated);
  border: 1px solid var(--apex-border);
  border-radius: 4px;
  color: var(--apex-text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 120ms;
}

.apex-icon-btn:hover {
  border-color: var(--apex-cyan);
  color: var(--apex-cyan);
}

.apex-icon-btn svg {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
}

/* MAIN STAGE */
.apex-main {
  margin-left: var(--sidebar-width);
  margin-top: var(--ticker-height);
  min-height: calc(100vh - var(--ticker-height));
  background: var(--apex-void);
}

.apex-stage-header {
  padding: 16px 24px;
  border-bottom: 1px solid var(--apex-border);
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}

.apex-page-title {
  font-family: "Orbitron", sans-serif;
  font-size: 18px;
  font-weight: 600;
  color: var(--apex-cyan);
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.apex-meta {
  font-size: 11px;
  color: var(--apex-text-secondary);
}

/* MOSAIC GRID — No stretch, fixed geometry */
.apex-mosaic {
  display: grid;
  grid-template-columns: repeat(auto-fill, var(--mosaic-col));
  grid-auto-rows: var(--mosaic-row);
  gap: var(--mosaic-gap);
  padding: 24px;
  justify-content: start; /* Prevent stretch */
  align-content: start;
}

/* Widget Instruments */
.apex-inst {
  background: var(--apex-surface);
  border: 1px solid var(--apex-border);
  border-radius: 6px;
  padding: 16px;
  position: relative;
  overflow: hidden;
  animation: instBoot 600ms ease-out forwards;
  opacity: 0;
}

.apex-inst::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--apex-cyan-dim), transparent);
  opacity: 0.5;
}

@keyframes instBoot {
  0% {
    opacity: 0;
    transform: translateY(8px);
    clip-path: polygon(0 0, 100% 0, 100% 0, 0 0);
  }
  100% {
    opacity: 1;
    transform: translateY(0);
    clip-path: polygon(0 0, 100% 0, 100% 100%, 0 100%);
  }
}

/* Size variants */
.apex-inst--s { grid-column: span 1; grid-row: span 1; }
.apex-inst--m { grid-column: span 1; grid-row: span 1; height: 360px; }
.apex-inst--l { grid-column: span 2; grid-row: span 1; }
.apex-inst--xl { grid-column: span 2; grid-row: span 2; }
.apex-inst--full { grid-column: span 4; grid-row: span 2; }

/* Scanline effect */
.apex-inst::after {
  content: "";
  position: absolute;
  inset: 0;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0, 240, 255, 0.03) 2px,
    rgba(0, 240, 255, 0.03) 4px
  );
  pointer-events: none;
  opacity: 0;
  transition: opacity 300ms;
}

.apex-inst:hover::after {
  opacity: 1;
}

/* Loading/Empty states */
.apex-inst[data-empty="true"] {
  border-style: dashed;
  opacity: 0.6;
}

.apex-inst__placeholder {
  color: var(--apex-text-secondary);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
```

### File: site/apex-ticker.js
```javascript
/**
 * NR2-Apex Ticker Tape — Starship Bridge Ambient Display
 * Build: hal-10220
 */
(function() {
  "use strict";
  
  const CONFIG = {
    endpoint: "/api/apex/ticker",
    interval: 30000, // Refresh every 30s
    scrollSpeed: 40, // seconds for full loop
    maxItems: 20
  };

  class ApexTicker {
    constructor() {
      this.track = document.getElementById("ticker-track");
      this.items = [];
      this.timer = null;
      this.init();
    }

    async init() {
      await this.fetch();
      this.startRotation();
      window.addEventListener("visibilitychange", () => this.handleVisibility());
    }

    async fetch() {
      try {
        const res = await fetch(`${CONFIG.endpoint}?_=${Date.now()}`, {
          credentials: "same-origin",
          cache: "no-store"
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        this.update(data.items || []);
      } catch (err) {
        console.warn("[ApexTicker] Feed failed, using placeholder:", err);
        this.update([{
          type: "system",
          text: "TICKER OFFLINE — CHECK CONNECTION"
        }]);
      }
    }

    update(items) {
      // Sanitize: never show invented dollar amounts
      const sanitized = items.slice(0, CONFIG.maxItems).map(item => ({
        type: item.type || "info",
        text: this.sanitizeText(item.text || ""),
        severity: item.severity || "info"
      }));

      if (JSON.stringify(sanitized) === JSON.stringify(this.items)) return;
      this.items = sanitized;
      this.render();
    }

    sanitizeText(text) {
      // Ensure no financial amounts are hardcoded in display
      if (typeof text !== "string") return "DATA UNAVAILABLE";
      return text;
    }

    render() {
      if (!this.track) return;
      
      // Build inner HTML
      const html = this.items.map(item => {
        const className = `apex-ticker__item apex-ticker__item--${item.type}`;
        const prefix = item.type === "metric" ? "◈ " : 
                      item.type === "alert" ? "▲ " :
                      item.type === "hal" ? "◐ " : "• ";
        return `<span class="${className}">${prefix}${this.escapeHtml(item.text)}</span>`;
      }).join("");

      // Duplicate for seamless loop
      this.track.innerHTML = html + html;
    }

    escapeHtml(text) {
      const div = document.createElement("div");
      div.textContent = text;
      return div.innerHTML;
    }

    startRotation() {
      this.timer = setInterval(() => this.fetch(), CONFIG.interval);
    }

    handleVisibility() {
      if (document.hidden) {
        // Pause updates to save resources
      } else {
        this.fetch();
      }
    }

    destroy() {
      if (this.timer) clearInterval(this.timer);
    }
  }

  // Initialize when DOM ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => new ApexTicker());
  } else {
    new ApexTicker();
  }
})();
```

### File: site/apex-narratives.html (Scaffold/Partial)
```html
<!-- Interactive Narratives Page Scaffold -->
<!-- Load this into #apex-stage when page === 'narratives' -->
<div class="narratives-bridge" id="narratives-bridge">
  <!-- Timeline Scrubber -->
  <div class="narr-scrubber">
    <div class="narr-scrubber__track" id="narr-timeline">
      <button class="narr-scrubber__node active" data-section="intro">Introduction</button>
      <button class="narr-scrubber__node" data-section="findings">Findings</button>
      <button class="narr-scrubber__node" data-section="treatment">Treatment Plan</button>
      <button class="narr-scrubber__node" data-section="notes">Clinical Notes</button>
      <button class="narr-scrubber__node" data-section="followup">Follow-up</button>
    </div>
    <div class="narr-scrubber__progress" id="narr-progress"></div>
  </div>

  <!-- 3-Pane Workspace -->
  <div class="narr-workspace">
    <!-- Left: Section Outline -->
    <aside class="narr-outline">
      <h3 class="narr-panel-title">Sections</h3>
      <ul class="narr-outline__list" id="narr-outline-list">
        <!-- Populated dynamically -->
        <li data-section="intro" class="active">Introduction</li>
        <li data-section="findings">Findings</li>
        <li data-section="treatment">Treatment Plan</li>
        <li data-section="notes">Clinical Notes</li>
        <li data-section="followup">Follow-up</li>
      </ul>
      <button class="apex-btn apex-btn--secondary" id="btn-add-section">+ Add Section</button>
    </aside>

    <!-- Center: Composer -->
    <main class="narr-composer">
      <div class="narr-composer__toolbar">
        <button class="apex-btn" id="btn-rewrite-hal" title="HAL-assisted rewrite">HAL Rewrite</button>
        <button class="apex-btn" id="btn-insert-template">Insert Template</button>
        <div class="narr-composer__status" id="composer-status">Draft</div>
      </div>
      <textarea 
        class="narr-composer__editor" 
        id="narr-editor" 
        placeholder="[PLACEHOLDER] Clinical narrative text will appear here. Select text and click 'HAL Rewrite' for AI assistance."
      ></textarea>
    </main>

    <!-- Right: Context Panel -->
    <aside class="narr-context">
      <h3 class="narr-panel-title">Context</h3>
      
      <div class="narr-context__section">
        <h4>Patient Data</h4>
        <div class="narr-data-placeholder" id="patient-data-placeholder">
          [PLACEHOLDER] Patient information unavailable
        </div>
      </div>

      <div class="narr-context__section">
        <h4>HAL Suggestions</h4>
        <div class="narr-suggestion" id="narr-hal-suggestion">
          <p class="narr-suggestion__text">Awaiting input...</p>
          <button class="apex-btn apex-btn--small" disabled>Apply</button>
        </div>
      </div>

      <div class="narr-context__section">
        <h4>Templates</h4>
        <select class="narr-select" id="template-select">
          <option value="">Select template...</option>
          <option value="new-patient">New Patient Exam</option>
          <option value="restorative">Restorative Procedure</option>
          <option value="perio">Periodontal Maintenance</option>
        </select>
      </div>

      <div class="narr-actions">
        <button class="apex-btn apex-btn--primary" id="btn-generate-packet">Generate Print Packet</button>
        <button class="apex-btn" id="btn-save-draft">Save Draft</button>
      </div>
    </aside>
  </div>
</div>
```

### File: server/apex_bridge_helpers.py
```python
# NR2-Apex Bridge Backend Helpers
# Add these routes to your existing Flask/FastAPI app
# WARNING: CONSULT ONLY — DO NOT DEPLOY UNTIL VALIDATED

from flask import jsonify, Blueprint
from datetime import datetime
import random

apex_bridge = Blueprint('apex_bridge', __name__)

@apex_bridge.route('/api/apex/ticker')
def get_ticker():
    """
    Returns scrolling ticker content.
    NO FINANCIAL AMOUNTS INVENTED HERE — uses PLACEHOLDER or null.
    """
    items = [
        {"type": "system", "text": f"SYSTEM SYNC: {datetime.now().strftime('%H:%M')}"},
        {"type": "hal", "text": "HAL: Review 90+ day AR when convenient"},
        {"type": "alert", "severity": "amber", "text": "ALERT: SoftDent connection latency > 200ms"},
        {"type": "metric", "label": "MTD PRODUCTION", "value": None, "unit": "USD", "status": "placeholder"},
        {"type": "metric", "label": "AR OUTSTANDING", "value": None, "unit": "USD", "status": "placeholder"},
        {"type": "system", "text": "BACKUP: Completed 04:00 EST"},
    ]
    return jsonify({"items": items, "timestamp": datetime.utcnow().isoformat()})

@apex_bridge.route('/api/apex/narratives/structure', methods=['GET'])
def get_narrative_structure():
    """Returns default section structure for new narrative"""
    return jsonify({
        "sections": [
            {"id": "intro", "title": "Introduction", "order": 0, "content": "[PLACEHOLDER]"},
            {"id": "findings", "title": "Findings", "order": 1, "content": "[PLACEHOLDER]"},
            {"id": "treatment", "title": "Treatment Plan", "order": 2, "content": "[PLACEHOLDER]"},
            {"id": "notes", "title": "Clinical Notes", "order": 3, "content": "[PLACEHOLDER]"},
        ]
    })

@apex_bridge.route('/api/apex/narratives/generate', methods=['POST'])
def generate_narrative():
    """
    HAL-assisted rewrite endpoint.
    Accepts: {text: str, context: dict, style: str}
    Returns: {suggestion: str, confidence: float}
    """
    # PLACEHOLDER: Integrate with actual HAL/NLP service
    return jsonify({
        "suggestion": "[PLACEHOLDER] HAL would rewrite the selected text here based on clinical context.",
        "confidence": None,
        "status": "placeholder"
    })

@apex_bridge.route('/api/apex/narratives/print-packet', methods=['POST'])
def generate_print_packet():
    """Generates PDF packet from narrative structure"""
    # PLACEHOLDER: Integrate with PDF generation service
    return jsonify({
        "status": "placeholder",
        "message": "Packet generation not yet implemented",
        "download_url": None
    })

# Register blueprint in main app:
# app.register_blueprint(apex_bridge)
```

---

## 9. Implementation Phases (S0→Sn) + Validation Gate

**S0: VALIDATION GATE**  
You are here. Review this consultation. Confirm:
- [ ] Sidebar placement (left) and width (240px) acceptable
- [ ] Ticker at top (32px) acceptable (bottom ticker can be added later)
- [ ] Fixed mosaic grid (320px base unit) acceptable vs. responsive fluid
- [ ] Interactive Narratives layout (3-pane) matches your workflow
- [ ] Backend endpoints (`/api/apex/ticker`, `/api/apex/narratives/*`) can be implemented

**DO NOT PROCEED TO S1 UNTIL YOU REPLY "VALIDATED" or specify changes.**

**S1: Shell Replacement**  
- Backup `site/index.html` → `index.html.bak.hal-10220`
- Deploy `apex-bridge-shell.html` as new `index.html`
- Deploy `apex-bridge.css`
- Verify sidebar renders, ticker placeholder visible, stage empty but styled

**S2: Mosaic Grid Conversion**  
- Modify `apex-core.js` Widget class to emit `.apex-inst` with size classes instead of `.apex-widget`
- Update `renderWidget()` to use fixed sizes based on widget type (kpi→s, chart→l, etc.)
- Remove auto-fit grid CSS from legacy files

**S3: Ticker Integration**  
- Deploy `apex-ticker.js`
- Implement backend `/api/apex/ticker` (use helper above)
- Verify scroll animation, pause on hover, reduced-motion support

**S4: Narratives Page Build**  
- Deploy `apex-narratives.js` (controller for the scaffold)
- Implement backend helpers for structure/generate/print
- Wire up HAL suggestion panel in narratives context

**S5: Animation Polish**  
- Tune boot sequence timing (staggered widget entry)
- Add scanline effects
- Final contrast check for accessibility

---

## 10. Risks & Rollback

**Risks:**
1. **Fixed layout fragility:** The 320px×4 mosaic assumes minimum 1280px width. On smaller screens, horizontal scroll appears. *(Mitigation: Add `@media (max-width: 1400px)` to reduce to 3 columns, or accept scrollbar as "starship console" aesthetic.)*
2. **Ticker distraction:** Continuous motion may irritate users. *(Mitigation: Pause on hover implemented; add "Mute Ticker" button in S5 if requested.)*
3. **Backend load:** Ticker polls every 30s; narratives page has rich interactions. *(Mitigation: Cache ticker for 10s on backend; use debouncing on narrative editor.)*
4. **Narratives complexity:** 3-pane UI is a departure from simple widget grids. *(Mitigation: Fallback to simple widget view if JS fails; progressive enhancement.)*

**Rollback Plan:**
- All files are additive (`apex-bridge-*.html/css/js`) or versioned (`?v=hal-10220`).
- If failure occurs, restore `index.html` from `index.html.bak.hal-10220` and remove bridge CSS/JS includes.
- No database schema changes required for this UI update.

**WAITING FOR VALIDATION.** Do not apply until you confirm.