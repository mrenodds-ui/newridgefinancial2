# Moonshot AI — Complete High-Tech Redesign Plan (CONSULT ONLY)

**Date:** 2026-07-10  
**Model:** kimi-k2.5  
**Key name:** OPENROUTER_API_KEY (value not stored in docs)  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Script:** `scripts/run_moonshot_complete_redesign_consult.py`  
**Apply:** DO NOT APPLY until operator validates.

## Operator request (verbatim)

> i dont want a mock up but a complete high tech redesign of the entire program wilf smal widgets of graphs charts and icon like print buttons, to remove current layout and a detailed plan from start to fish on how to do it.  i want it to look highly high tech professional with a detailed futuristic presentation wih anything animated and automated.  problem is i dont want overlays, old legacry rearrangement.  i want that wiped out before laying down a new design.  i believe past inknown programs were interfereing.  if i need a backend do it and replace it with functions that help the frontend.  plsease have him give code, report and dont proceed until validated.  do not rewrite what i want.

---

# Verdict

**CONSULT ONLY — DO NOT APPLY.**  
Awaiting operator validation before any file system changes, code deployment, or service restarts.

---

## 0. Operator Intent (Quoted)

> *"i dont want a mock up but a complete high tech redesign of the entire program wilf smal widgets of graphs charts and icon like print buttons, to remove current layout and a detailed plan from start to fish on how to do it. i want it to look highly high tech professional with a detailed futuristic presentation wih anything animated and automated. problem is i dont want overlays, old legacry rearrangement. i want that wiped out before laying down a new design. i believe past inknown programs were interfereing. if i need a backend do it and replace it with functions that help the frontend. plsease have him give code, report and dont proceed until validated. do not rewrite what i want."*

**Confirmation:** This is a **scorched-earth rebuild**, not a rearrangement of existing mockup panels. All "moonshot-mockup", "live-wire-pilot", and overlay systems will be **terminated and deleted** before the new high-tech widget-dense UI is laid down.

---

## 1. Wipe Plan — Remove Current Layout / Overlays / Legacy Interference

### Immediate Termination (Before File Deletion)
```powershell
# Stop all NR2 processes and ghost listeners
Get-Process | Where-Object {$_.ProcessName -match "python|pywebview|chrome|edge"} | Stop-Process -Force
# Kill orphaned ports 8765/8766
Get-NetTCPConnection -LocalPort 8765,8766 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

### Files to DELETE (Mockup/Moonshot/Legacy Era)
**CSS (Theme/Overlay/Glass):**
- `NewRidgeFinancial2/site/nr2-moonshot-mockup-theme.css`
- `NewRidgeFinancial2/site/hal-mockup-overrides.css`
- `NewRidgeFinancial2/site/nr2-mockup-page-vocabulary.css`
- `NewRidgeFinancial2/site/nr2-moonshot-glow.css`
- `NewRidgeFinancial2/site/nr2-mission-control-glass.css`
- `NewRidgeFinancial2/site/nr2-mission-control-extreme.css`
- `NewRidgeFinancial2/site/workstation-moonshot-bridge.css`

**JS (Layout Engines/Chrome/Canvas):**
- `NewRidgeFinancial2/site/nr2-moonshot-mockup-chrome.js` — *MoonshotMockupChrome engine*
- `NewRidgeFinancial2/site/moonshot-page-registry.js` — *Legacy registry*
- `NewRidgeFinancial2/site/page-canvas.js` — *PageCanvas layout engine*
- `NewRidgeFinancial2/site/hal-page-canvas.js` — *HAL canvas overlays*
- `NewRidgeFinancial2/site/page-views.js` — *Old view mount layer*
- `NewRidgeFinancial2/site/hal-page.js` — *Legacy HAL renderer*

**HTML/Index Modifications:**
- Remove all `<link rel="stylesheet" href="...mockup...css"...>` from `index.html`
- Remove `data-nr2-epoch="moonshot-mockup"` attributes
- Remove `window.__NR2_REQUIRED_EPOCH` checks
- Remove `NR2_STAFF_MOCK_ONLY` flag and all mock-embed logic

### Registry & Storage Wipe
```javascript
// Execute in browser console before shutdown
Object.keys(localStorage).forEach(k => { if(k.includes('nr2') || k.includes('moonshot') || k.includes('hal')) localStorage.removeItem(k); });
Object.keys(sessionStorage).forEach(k => { if(k.includes('nr2') || k.includes('moonshot')) sessionStorage.removeItem(k); });
// Unregister service workers
navigator.serviceWorker.getRegistrations().then(regs => regs.forEach(r => r.unregister()));
```

### Backend Retirements
- Remove `MoonshotLayoutEngine` references from `browser_app.py` if present
- Disable `/api/mockup/*` routes in `nr2_http_server.py`
- Clear `app_data/nr2/cache/` directory (widget cache, schema cache)

---

## 2. Interference & Unknown Program Risks

| Risk | Source | Wipe Mitigation |
|------|--------|-----------------|
| **Ghost Python processes** | Previous `browser_app.py` instances holding port 8765 | Process kill + port release before new launch |
| **Dual layout engines** | `PageCanvas` vs `MoonshotMockupChrome` conflicting DOM writes | Delete both engines; new system uses single `NexusLayout` |
| **CSS specificity wars** | `nr2-mission-control-extreme.css` overriding with `!important` | Delete file; new design tokens use CSS variables only |
| **Service worker cache** | Old `sw.js` serving cached `moonshot-mockup` assets | Force unregister + cache delete before new shell loads |
| **Stale widget data** | `page-canvas-data.js` holding deprecated schemas | Delete file; new backend feeds fresh JSON only |
| **Workstation bridge** | Port 8766 pywebview still injecting old CSS | Verify process termination; new bridge uses WebSocket only |

---

## 3. Target Design System (Futuristic High-Tech)

**Codename:** NR2-Apex  
**Philosophy:** Orbital Command — dense data, zero chrome, instant action.

### Visual Tokens
```css
/* Apex Design Tokens */
--apex-bg-void: #050508;           /* Deep space black */
--apex-bg-surface: #0a0b10;        /* Elevated panels */
--apex-bg-elevated: #12141c;       /* Widget backgrounds */
--apex-accent-cyan: #00f0ff;       /* Primary action/data */
--apex-accent-amber: #ffb800;      /* Financial highlights */
--apex-accent-magenta: #ff0066;    /* Alerts/urgent */
--apex-grid-gap: 8px;              /* Tight widget packing */
--apex-widget-min: 140px;          /* Small widget base */
--apex-anim-fast: 120ms;           /* Micro-interactions */
--apex-anim-medium: 240ms;         /* Layout shifts */
```

### Typography
- **Primary:** `Inter` (weights 400, 500, 600) — compact, legible at small sizes
- **Monospace:** `JetBrains Mono` — financial figures, timestamps
- **Scale:** 11px labels, 13px data, 18px headers, 24px hero KPIs

### Widget Specs (Small, Dense)
- **KPI Tile:** 140×100px — large number, sparkline, delta indicator, icon button row
- **Chart Tile:** 280×180px — mini time-series, no legend (hover for details)
- **Action Chip:** 32×32px icon button — print, export, refresh, expand
- **Status Orb:** 8px LED-style indicator — pulsing for live data

### Motion & Automation
- **Entrance:** Staggered fade-up (50ms delay per widget)
- **Live Data:** Subtle "breathing" glow on updating cells (opacity 0.7→1.0, 2s loop)
- **Hover:** 120ms scale(1.02) + elevation shadow
- **Auto-refresh:** 30s interval with silent background fetch (no full page reload)
- **HAL Pulse:** Cyan border shimmer when AI is processing

---

## 4. End-to-End Plan (Start → Finish)

### P0: Scorched Earth (VALIDATION GATE 1)
**Goal:** Absolute clean slate  
**Actions:**
1. Execute Wipe Plan (Section 1)
2. Verify no `moonshot` strings remain in `site/` directory
3. Confirm ports 8765/8766 are free (`netstat -ano | findstr 8765`)
4. Backup `app_data/nr2/` to `app_data/nr2-backup-P0/`

**Acceptance:** `grep -r "moonshot\|mockup\|live-wire" site/` returns zero results.

### P1: Foundation Shell (VALIDATION GATE 2)
**Goal:** New CSS tokens + base HTML structure  
**Files:** `apex-tokens.css`, `index.html` (new shell), `apex-core.js`

**Acceptance:** Load `https://127.0.0.1:8765/` → see dark void background with cyan grid lines, no widgets yet, no console errors.

### P2: Widget Engine (VALIDATION GATE 3)
**Goal:** Render small widgets from JSON feed  
**Files:** `apex-widget.js`, `apex-layout.js`

**Acceptance:** Static test payload renders 12 KPI tiles in responsive grid; print icons visible and clickable (console.log only).

### P3: Data Backend (VALIDATION GATE 4)
**Goal:** Python routes serve live data  
**Files:** Modify `nr2_http_server.py`, new `apex_routes.py`

**Acceptance:** `GET /api/apex/widgets/financial` returns JSON with production numbers; frontend auto-refreshes every 30s.

### P4: Page Migration (VALIDATION GATE 5)
**Goal:** Convert all 11 pages to Apex grid  
**Sequence:** financial → taxes → softdent → quickbooks → ar → claims → narratives → documents → library → office-manager → hal

**Acceptance:** Each page loads < 500ms, widget density > 8 per viewport, print buttons functional.

### P5: Automation & HAL (VALIDATION GATE 6)
**Goal:** Animated transitions, HAL integration, background sync  
**Files:** `apex-animations.css`, `apex-hal-bridge.js`

**Acceptance:** Widgets animate on load; HAL suggestions appear in side panel; data updates without page flash.

### P6: Production Hardening (FINAL VALIDATION)
**Goal:** Performance, rollback capability, documentation  
**Deliverable:** Full report, rollback script, operator sign-off.

---

## 5. Backend Functions That Help the Frontend

New module: `NewRidgeFinancial2/apex_backend.py` (imported into `nr2_http_server.py`)

### Route: `/api/apex/widgets/<page_id>`
**Purpose:** Feed all widget data for a page in single request  
**Returns:**
```json
{
  "page": "financial",
  "refreshedAt": "2026-07-09T22:30:00Z",
  "widgets": [
    {"id": "prod-mtd", "type": "kpi", "value": 124500, "delta": 0.12, "sparkline": [120,122,121,124,125,124,125]},
    {"id": "collections-chart", "type": "bar", "series": [{"label": "Insurance", "value": 45000}, {"label": "Patient", "value": 32000}]}
  ]
}
```

### Route: `/api/apex/print/<packet_type>`
**Purpose:** Generate print-ready HTML packet  
**Payload:** `{"page": "financial", "widgets": ["prod-mtd", "collections-chart"], "format": "pdf"}`  
**Returns:** `{"jobId": "abc123", "status": "queued", "url": "/print/abc123"}`

### Route: `/api/apex/hal/status`
**Purpose:** HAL operational state + suggestions  
**Returns:** `{"status": "idle", "suggestion": "Review 3 claims approaching deadline", "confidence": 0.94}`

### Route: `/api/apex/sync/trigger`
**Purpose:** Force immediate data refresh (SoftDent/QB)  
**Returns:** `{"startedAt": "...", "estimatedComplete": "..."}`

---

## 6. Moonshot Code Deliverables (Paste-Ready Foundations)

**FOUNDATION ONLY** — These are starting blocks, not the full rewrite.

### File: `site/apex-tokens.css`
```css
/* NR2-Apex Design Tokens — Foundation P1 */
:root {
  --apex-void: #050508;
  --apex-surface: #0a0b10;
  --apex-elevated: #12141c;
  --apex-border: #1e2029;
  --apex-cyan: #00f0ff;
  --apex-cyan-dim: rgba(0, 240, 255, 0.15);
  --apex-amber: #ffb800;
  --apex-amber-dim: rgba(255, 184, 0, 0.15);
  --apex-magenta: #ff0066;
  --apex-text-primary: #f0f2f5;
  --apex-text-secondary: #8b9098;
  --apex-grid-gap: 8px;
  --apex-radius: 6px;
  --apex-anim-fast: 120ms;
  --apex-anim-medium: 240ms;
  --apex-widget-shadow: 0 2px 8px rgba(0,0,0,0.4);
}

* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--apex-void);
  color: var(--apex-text-primary);
  font-family: 'Inter', system-ui, sans-serif;
  font-size: 13px;
  line-height: 1.4;
  overflow-x: hidden;
}

.apex-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: var(--apex-grid-gap);
  padding: var(--apex-grid-gap);
  max-width: 1920px;
  margin: 0 auto;
}

.apex-widget {
  background: var(--apex-elevated);
  border: 1px solid var(--apex-border);
  border-radius: var(--apex-radius);
  padding: 12px;
  position: relative;
  transition: transform var(--apex-anim-fast), box-shadow var(--apex-anim-fast);
  animation: apexEnter var(--apex-anim-medium) ease-out backwards;
}

.apex-widget:hover {
  transform: translateY(-2px);
  box-shadow: var(--apex-widget-shadow), 0 0 0 1px var(--apex-cyan-dim);
}

@keyframes apexEnter {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.apex-kpi-value {
  font-size: 24px;
  font-weight: 600;
  color: var(--apex-amber);
  font-family: 'JetBrains Mono', monospace;
}

.apex-kpi-delta {
  font-size: 11px;
  color: var(--apex-cyan);
}

.apex-sparkline {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 24px;
  margin-top: 8px;
}

.apex-spark-bar {
  flex: 1;
  background: var(--apex-cyan-dim);
  border-radius: 1px;
  transition: height var(--apex-anim-fast);
}

.apex-icon-btn {
  width: 28px;
  height: 28px;
  border: 1px solid var(--apex-border);
  background: var(--apex-surface);
  color: var(--apex-text-secondary);
  border-radius: var(--apex-radius);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all var(--apex-anim-fast);
}

.apex-icon-btn:hover {
  border-color: var(--apex-cyan);
  color: var(--apex-cyan);
  background: var(--apex-cyan-dim);
}
```

### File: `site/apex-shell.html` (New index.html core)
```html
<!DOCTYPE html>
<html lang="en" data-apex-version="hal-10170-apex">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Cache-Control" content="no-store">
  <title>NewRidgeFinancial 2.0 — Apex</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="apex-tokens.css">
  <style>
    #apex-header {
      position: sticky;
      top: 0;
      z-index: 100;
      background: rgba(5,5,8,0.9);
      backdrop-filter: blur(8px);
      border-bottom: 1px solid var(--apex-border);
      padding: 8px 16px;
      display: flex;
      align-items: center;
      gap: 16px;
    }
    #apex-nav { display: flex; gap: 8px; flex: 1; }
    .apex-nav-btn {
      padding: 6px 12px;
      background: transparent;
      border: 1px solid transparent;
      color: var(--apex-text-secondary);
      cursor: pointer;
      border-radius: var(--apex-radius);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      transition: all var(--apex-anim-fast);
    }
    .apex-nav-btn:hover, .apex-nav-btn.active {
      color: var(--apex-cyan);
      border-color: var(--apex-cyan-dim);
      background: var(--apex-cyan-dim);
    }
    #apex-hal-status {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 11px;
      color: var(--apex-text-secondary);
    }
    .hal-orb {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--apex-magenta);
      animation: halPulse 2s infinite;
    }
    @keyframes halPulse {
      0%, 100% { opacity: 0.4; }
      50% { opacity: 1; box-shadow: 0 0 8px var(--apex-magenta); }
    }
    #apex-stage { min-height: calc(100vh - 60px); }
  </style>
</head>
<body>
  <header id="apex-header">
    <div style="font-weight:600; color:var(--apex-cyan);">NR2 APEX</div>
    <nav id="apex-nav">
      <button class="apex-nav-btn active" data-page="financial">Financial</button>
      <button class="apex-nav-btn" data-page="taxes">Taxes</button>
      <button class="apex-nav-btn" data-page="softdent">SoftDent</button>
      <button class="apex-nav-btn" data-page="quickbooks">QuickBooks</button>
      <button class="apex-nav-btn" data-page="ar">A/R</button>
      <button class="apex-nav-btn" data-page="claims">Claims</button>
      <button class="apex-nav-btn" data-page="hal">HAL</button>
    </nav>
    <div id="apex-hal-status">
      <div class="hal-orb"></div>
      <span>HAL Standby</span>
    </div>
    <button class="apex-icon-btn" id="btn-print" title="Print Current View">🖨️</button>
    <button class="apex-icon-btn" id="btn-refresh" title="Force Refresh">↻</button>
  </header>
  
  <main id="apex-stage" class="apex-grid">
    <!-- Widgets injected here -->
  </main>

  <script src="apex-core.js"></script>
</body>
</html>
```

### File: `site/apex-core.js` (Foundation Widget Engine)
```javascript
/**
 * NR2-Apex Core — Widget Engine Foundation P2
 * No legacy dependencies. Self-contained.
 */
const Apex = (function() {
  'use strict';
  
  const config = {
    refreshInterval: 30000,
    apiBase: '/api/apex',
    animStagger: 50
  };

  const stage = document.getElementById('apex-stage');
  let currentPage = 'financial';
  let refreshTimer = null;

  // Widget Registry
  const widgets = new Map();

  class Widget {
    constructor(id, type, data) {
      this.id = id;
      this.type = type;
      this.data = data;
      this.element = null;
    }
    
    render() {
      const el = document.createElement('article');
      el.className = 'apex-widget';
      el.style.animationDelay = `${widgets.size * config.animStagger}ms`;
      el.innerHTML = this.getTemplate();
      this.element = el;
      this.attachEvents();
      return el;
    }
    
    getTemplate() {
      if (this.type === 'kpi') {
        const spark = (this.data.sparkline || []).map(h => 
          `<div class="apex-spark-bar" style="height:${Math.max(20, h)}%"></div>`
        ).join('');
        return `
          <header style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <span style="font-size:11px; color:var(--apex-text-secondary); text-transform:uppercase;">${this.data.label}</span>
            <button class="apex-icon-btn" data-action="print" title="Print">🖨️</button>
          </header>
          <div class="apex-kpi-value">${this.formatNumber(this.data.value)}</div>
          <div class="apex-kpi-delta">${this.data.delta > 0 ? '▲' : '▼'} ${Math.abs(this.data.delta * 100).toFixed(1)}%</div>
          <div class="apex-sparkline">${spark}</div>
        `;
      }
      return `<div>Unknown widget type</div>`;
    }
    
    formatNumber(n) {
      return new Intl.NumberFormat('en-US', {style: 'currency', currency: 'USD', maximumFractionDigits: 0}).format(n);
    }
    
    attachEvents() {
      this.element.querySelector('[data-action="print"]')?.addEventListener('click', () => {
        console.log(`Print requested for ${this.id}`);
        // P4: Connect to /api/apex/print/
      });
    }
  }

  async function loadPage(pageId) {
    currentPage = pageId;
    stage.innerHTML = '<div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--apex-text-secondary);">Loading...</div>';
    
    try {
      const res = await fetch(`${config.apiBase}/widgets/${pageId}`);
      const payload = await res.json();
      renderWidgets(payload.widgets);
      startAutoRefresh();
    } catch(e) {
      stage.innerHTML = `<div style="color:var(--apex-magenta); grid-column:1/-1;">Error loading data: ${e.message}</div>`;
    }
  }

  function renderWidgets(data) {
    stage.innerHTML = '';
    widgets.clear();
    data.forEach((w, idx) => {
      const widget = new Widget(w.id, w.type, w);
      widgets.set(w.id, widget);
      stage.appendChild(widget.render());
    });
  }

  function startAutoRefresh() {
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = setInterval(() => loadPage(currentPage), config.refreshInterval);
  }

  // Navigation
  document.querySelectorAll('[data-page]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.apex-nav-btn').forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      loadPage(e.target.dataset.page);
    });
  });

  // Global actions
  document.getElementById('btn-refresh')?.addEventListener('click', () => loadPage(currentPage));
  document.getElementById('btn-print')?.addEventListener('click', () => {
    window.print(); // P5: Enhanced print packet
  });

  // Init
  loadPage('financial');

  return { loadPage, config };
})();
```

### File: `site/apex-chart-widget.js` (Chart Widget Extension)
```javascript
/**
 * Apex Chart Widget — Foundation P2 Extension
 * Lightweight canvas-based sparkline/bar charts, no external libs
 */
class ChartWidget {
  constructor(canvas, data, type = 'line') {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.data = data;
    this.type = type;
    this.resize();
    window.addEventListener('resize', () => this.resize());
    this.draw();
  }
  
  resize() {
    const rect = this.canvas.parentElement.getBoundingClientRect();
    this.canvas.width = rect.width * window.devicePixelRatio;
    this.canvas.height = 60 * window.devicePixelRatio;
    this.canvas.style.width = rect.width + 'px';
    this.canvas.style.height = '60px';
    this.ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
  }
  
  draw() {
    const ctx = this.ctx;
    const w = this.canvas.width / window.devicePixelRatio;
    const h = 60;
    const values = this.data.values || this.data;
    const max = Math.max(...values, 1);
    const min = Math.min(...values, 0);
    const range = max - min;
    
    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = '#00f0ff';
    ctx.lineWidth = 2;
    ctx.beginPath();
    
    values.forEach((v, i) => {
      const x = (i / (values.length - 1)) * w;
      const y = h - ((v - min) / range) * (h - 10) - 5;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    
    ctx.stroke();
    
    // Fill gradient
    ctx.lineTo(w, h);
    ctx.lineTo(0, h);
    ctx.closePath();
    const grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, 'rgba(0, 240, 255, 0.2)');
    grad.addColorStop(1, 'rgba(0, 240, 255, 0)');
    ctx.fillStyle = grad;
    ctx.fill();
  }
}

// Usage: new ChartWidget(document.getElementById('canvas'), [10,20,15,30,25]);
```

### File: `NewRidgeFinancial2/apex_routes.py` (Backend Foundation P3)
```python
"""
Apex API Routes — Foundation P3
Add to nr2_http_server.py or import as module
"""
import json
import random
from datetime import datetime, timezone
from bottle import route, response, request

def apex_routes():
    @route('/api/apex/widgets/<page_id>')
    def apex_widget_feed(page_id):
        """Foundation widget feed — returns dummy data for P3 testing"""
        response.content_type = 'application/json'
        
        widgets = []
        if page_id == 'financial':
            widgets = [
                {
                    "id": "prod-mtd",
                    "type": "kpi",
                    "label": "Production MTD",
                    "value": 124500 + random.randint(-5000, 5000),
                    "delta": 0.12,
                    "sparkline": [80, 82, 81, 84, 85, 84, 87]
                },
                {
                    "id": "collections-mtd",
                    "type": "kpi",
                    "label": "Collections",
                    "value": 98000,
                    "delta": -0.03,
                    "sparkline": [90, 88, 89, 87, 85, 86, 88]
                },
                {
                    "id": "ar-aging",
                    "type": "chart",
                    "label": "A/R Aging",
                    "chartType": "bar",
                    "series": [
                        {"label": "Current", "value": 45000},
                        {"label": "31-60", "value": 12000},
                        {"label": "60+", "value": 5000}
                    ]
                }
            ]
        
        return json.dumps({
            "page": page_id,
            "refreshedAt": datetime.now(timezone.utc).isoformat(),
            "widgets": widgets
        })

    @route('/api/apex/print/<packet_type>', method='POST')
    def apex_print_trigger(packet_type):
        """Foundation print endpoint — queues print job"""
        data = request.json
        job_id = f"prt_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(1000,9999)}"
        return json.dumps({
            "jobId": job_id,
            "status": "queued",
            "estimatedReady": "30s",
            "url": f"/print/{job_id}"
        })

    @route('/api/apex/sync/trigger', method='POST')
    def apex_sync_trigger():
        """Trigger background sync"""
        return json.dumps({
            "startedAt": datetime.now(timezone.utc).isoformat(),
            "status": "syncing",
            "sources": ["softdent", "quickbooks"]
        })

# Initialize: apex_routes()
```

---

## 7. Full Program Page Map (Apex Transformation)

| Page | Current State | Apex Transformation | Widget Examples |
|------|--------------|---------------------|-----------------|
| **financial** | Mockup panels | Executive Command Grid | Production KPI (large), Collection velocity sparkline, Payer mix donut (small), Reconciliation status orb, Provider performance bars |
| **taxes** | Text lists | Tax Compliance Deck | Quarterly estimate tiles, Book-to-tax bridge waterfall, S-corp reasonable comp gauge, Distribution vs W-2 balance |
| **softdent** | Clinical lists | Care Velocity Matrix | Daily production bars, Provider schedule density, New patient flow (mini line), Case acceptance rate (circular), Hygiene recall status |
| **quickbooks** | P&L tables | Financial Intelligence Grid | Net income trend, Expense category treemap (small), Cash position gauge, A/R aging horizontal bars, EBITDA walk |
| **ar** | Aging reports | Collections Operations | Aging buckets (color-coded tiles), Insurance vs Patient responsibility split, Collection lag indicator, Follow-up queue counter |
| **claims** | Pipeline list | Claims Funnel | Submission timeline, Outstanding by payer (pie), Denial rate trend, Appeals status chips |
| **narratives** | Document list | Narrative Forge | Template grid with preview thumbnails, Generation queue status, Recently generated list with print icons |
| **documents** | File browser | Document Vault | Grid view with metadata, Upload drop-zone widget, OCR status indicators, Quick actions (print/email) |
| **library** | Resource links | Knowledge Base | Category tiles with counts, Search-as-you-type bar, Recently accessed chips |
| **office-manager** | Task lists | Operations Center | System health monitors (CPU/DB), Task priority queue with progress bars, Staff assignment grid, Alert ticker |
| **hal** | Chat interface | AI Command Node | Input bar with suggestion chips, Context awareness panel (what HAL sees), Confidence meters, Recent commands history |

---

## 8. Validation Gate (Operator Must Approve Before Any Apply)

**STOP — DO NOT PROCEED WITHOUT OPERATOR VALIDATION**

Checklist for approval:
- [ ] **Wipe Scope Approved:** Confirm deletion of all `moonshot`, `mockup`, `live-wire` files listed in Section 1
- [ ] **Interference Check:** Confirm ports 8765/8766 are free of ghost processes
- [ ] **Backup Verified:** Confirm `app_data/nr2/` backed up to `nr2-backup-P0/`
- [ ] **Design Tokens Approved:** Review `apex-tokens.css` color palette (cyan/amber/void black)
- [ ] **Widget Density Approved:** Confirm 140px minimum widget size is acceptable
- [ ] **Automation Approved:** Confirm 30s auto-refresh interval is acceptable
- [ ] **Page Priority:** Confirm migration order (financial first, then taxes, etc.)
- [ ] **Rollback Plan:** Confirm Section 9 rollback procedure is acceptable

**Operator Action Required:**  
Reply with:  
`"VALIDATED — Proceed to P0 (Wipe)"` or  
`"MODIFY — [specific changes]"` or  
`"ABORT — Do not proceed"`

---

## 9. Risks & Rollback

### Risk Matrix
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Data loss during wipe | Low | Critical | P0 backup mandatory; verify backup before delete |
| Port conflict (8765) | Medium | High | P0 port check script; kill processes if needed |
| CSS not loading (new design) | Medium | Medium | Fallback to inline styles in HTML if external CSS fails |
| HAL integration failure | Medium | Medium | New HAL bridge is opt-in; old HAL chat can remain in separate file until P5 |
| Print functionality delay | Low | Low | Browser print (Ctrl+P) works immediately; enhanced packets in P4 |

### Rollback Procedure (Emergency)
If catastrophic failure at any phase:
1. Stop Python server (`Ctrl+C` or process kill)
2. Restore files from `app_data/nr2-backup-P0/` if database affected
3. Restore `site/` from Git or backup:
   ```powershell
   # If git available
   git checkout HEAD -- NewRidgeFinancial2/site/
   # If no git, restore from manual backup
   Copy-Item -Recurse -Force "backup/site/" "NewRidgeFinancial2/site/"
   ```
4. Restore `index.html` from backup (pre-apex version)
5. Restart with `StartProgram.bat`
6. Clear browser cache hard (`Ctrl+Shift+R`)

**Estimated Rollback Time:** 5 minutes if backups prepared.

---

**END OF CONSULTATION REPORT**  
**Status:** Awaiting operator validation. No files have been modified.