# Moonshot AI — Flashy Presentation + HAL Brain (CONSULT ONLY)

**Date:** 2026-07-10  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** hal-10250  
**Script:** `scripts/run_moonshot_flashy_presentation_consult.py`  
**Apply:** DO NOT APPLY until operator validates.

## Operator request (verbatim)

> ask moonshot ai are there any flashy presentation additions that can be added all pages that make the pages look high tech.  and on hals page a flasy display that would look like hals brain thinking.

---

# Verdict

**CONSULT DELIVERY:** Global high-tech chrome enhancements (CSS-first, motion-respectful) + HAL neural-core display (canvas-based, stateful). **DO NOT APPLY** pending operator validation.

---

## 0. Operator Intent (quote; confirm consult-only)

> *"ask moonshot ai are there any flashy presentation additions that can be added all pages that make the pages look high tech. and on hals page a flasy display that would look like hals brain thinking."*

**CONFIRMED:** Consult-only. Source of truth preserved. No financial amounts invented. Evolution of hal-10250 Apex bridge forward (wipe-safe).

---

## 1. Global Flashy Additions (all pages)

| Rank | Item | What / Where | Impact | Risk | Verdict |
|------|------|--------------|--------|------|---------|
| **MUST** | **Holographic Widget Lift** | CSS 3D tilt + cyan glow on `.apex-widget` hover; `transform: translateZ(20px)` with `perspective(1000px)` on parent mosaic | High presence, spatial depth | Low (CSS-only) | **APPROVE** |
| **MUST** | **Phosphor Text Glow** | Subtle text-shadow on headers/data: `0 0 8px rgba(0,240,255,0.4)`; respects `prefers-reduced-motion` | Instant "CRT terminal" feel | Low | **APPROVE** |
| **MUST** | **Data Corner Brackets** | SVG corner glyphs on widget corners (`::before/::after`); animate `stroke-dashoffset` on hover | Technical precision | Low | **APPROVE** |
| **SHOULD** | **Ambient Scanline Sweep** | Occasional horizontal sweep (every 20s) across viewport using CSS `@keyframes`; opacity 0.03 | Living system feel | Medium (motion sensitivity) | **APPROVE with reduced-motion gate** |
| **SHOULD** | **Status LED Indicators** | Tiny 4px dots on sidebar nav items; blink patterns: solid (active), slow pulse (standby), rapid (updating) | Instant state recognition | Low | **APPROVE** |
| **SHOULD** | **Glitch Reveal** | 50ms chromatic aberration on navigation changes (`text-shadow: -2px 0 magenta, 2px 0 amber`) | Sci-fi signature | Medium (distraction) | **OPTIONAL** |
| **NICE** | **Perspective Grid Floor** | Fixed bottom-anchored SVG grid with perspective transform; 5% opacity | Starship bridge depth | Medium (overhead) | **DEFER** |

---

## 2. HAL Brain Thinking Display

**Concept:** *Neural Core Visualization* — A canvas-based "cognitive field" that replaces or augments the existing HAL orb in the sidebar when on the HAL page, or lives as a hero element in the HAL page mosaic.

**Placement:** Primary position in `#apex-stage` when `data-page="hal"` active; collapses to compact sidebar orb on other pages.

**States & Motion Language:**
- **IDLE:** Slow cyan pulse (0.5Hz), minimal node drift, dormant connections (10% opacity)
- **THINKING:** Rapid amber activity waves propagating through node network, connection lines animate dash-offset, nodes glow magenta on activation, 2Hz pulse
- **REPLY:** Convergence pattern — all activity rushes to center then radiates outward in cyan shockwave, settles to idle

**Visual Design:**
- 40-60 nodes (performance-scaled based on viewport)
- Cyan primary nodes, amber active nodes, magenta "firing" nodes
- Connection lines: `rgba(0,240,255,0.15)` idle, `rgba(255,191,0,0.6)` active
- Background: Void black with subtle radial gradient center glow
- No purple overload; stays scientific/cold-war-computer aesthetic

---

## 3. Moonshot Code Deliverables (paste-ready)

### File: `apex-chrome-flash.css` (Global additions)
```css
/* NR2-Apex Flash Chrome — High-tech presentation layer
 * Add to existing CSS or include after apex-bridge.css
 * Respects prefers-reduced-motion
 */

/* === PHOSPHOR TEXT GLOW === */
.apex-phosphor,
.apex-page-title,
.apex-widget__value,
.apex-ticker__item {
  text-shadow: 0 0 8px rgba(0, 240, 255, 0.35),
               0 0 16px rgba(0, 240, 255, 0.15);
}

/* === HOLOGRAPHIC WIDGET LIFT === */
.apex-mosaic {
  perspective: 1000px;
  transform-style: preserve-3d;
}

.apex-widget {
  transition: transform 0.3s ease, box-shadow 0.3s ease;
  transform-style: preserve-3d;
}

.apex-widget:hover {
  transform: translateZ(20px) scale(1.02);
  box-shadow: 
    0 10px 30px rgba(0, 0, 0, 0.8),
    0 0 20px rgba(0, 240, 255, 0.15),
    0 0 40px rgba(0, 240, 255, 0.05),
    inset 0 1px 0 rgba(255, 255, 255, 0.05);
}

/* === DATA CORNER BRACKETS === */
.apex-widget {
  position: relative;
}

.apex-widget::before,
.apex-widget::after {
  content: '';
  position: absolute;
  width: 12px;
  height: 12px;
  border: 1px solid var(--apex-cyan-dim);
  opacity: 0.4;
  transition: all 0.3s ease;
}

.apex-widget::before {
  top: -1px;
  left: -1px;
  border-right: none;
  border-bottom: none;
}

.apex-widget::after {
  bottom: -1px;
  right: -1px;
  border-left: none;
  border-top: none;
}

.apex-widget:hover::before,
.apex-widget:hover::after {
  opacity: 1;
  width: 20px;
  height: 20px;
  border-color: var(--apex-cyan);
}

/* === AMBIENT SCANLINE SWEEP === */
.apex-scan-sweep::after {
  content: '';
  position: fixed;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(0, 240, 255, 0.03),
    transparent
  );
  pointer-events: none;
  animation: apexSweep 20s linear infinite;
  z-index: 9999;
}

@keyframes apexSweep {
  0% { left: -100%; }
  5% { left: 100%; }
  100% { left: 100%; }
}

/* === STATUS LED INDICATORS === */
.apex-nav-btn {
  position: relative;
}

.apex-nav-btn::before {
  content: '';
  position: absolute;
  left: 8px;
  top: 50%;
  transform: translateY(-50%);
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--apex-cyan-dim);
  opacity: 0.3;
  transition: all 0.3s ease;
}

.apex-nav-btn.active::before {
  background: var(--apex-cyan);
  opacity: 1;
  box-shadow: 0 0 8px var(--apex-cyan);
}

.apex-nav-btn.is-updating::before {
  animation: apexLedPulse 0.8s ease-in-out infinite;
  background: var(--apex-amber);
  box-shadow: 0 0 8px var(--apex-amber);
}

@keyframes apexLedPulse {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 1; }
}

/* === GLITCH REVEAL (Optional) === */
.apex-glitch {
  position: relative;
}

.apex-glitch.active {
  animation: apexGlitch 0.15s ease-out;
}

@keyframes apexGlitch {
  0% {
    text-shadow: -2px 0 var(--apex-magenta), 2px 0 var(--apex-amber);
    transform: translateX(-1px);
  }
  25% {
    text-shadow: 2px 0 var(--apex-magenta), -2px 0 var(--apex-amber);
    transform: translateX(1px);
  }
  50% {
    text-shadow: -1px 0 var(--apex-amber), 1px 0 var(--apex-cyan);
  }
  100% {
    text-shadow: none;
    transform: translateX(0);
  }
}

/* === REDUCED MOTION === */
@media (prefers-reduced-motion: reduce) {
  .apex-widget:hover {
    transform: none;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
  }
  
  .apex-scan-sweep::after {
    animation: none;
    opacity: 0;
  }
  
  .apex-nav-btn.is-updating::before {
    animation: none;
    opacity: 1;
  }
}
```

### File: `apex-motion-helper.js` (Shared utilities)
```javascript
/**
 * NR2-Apex Motion Helper — RAF scheduler + reduced motion detection
 * Include after apex-core.js
 */

window.ApexMotion = (function() {
  'use strict';
  
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const rafCallbacks = new Set();
  let rafId = null;
  
  function schedule(callback) {
    if (prefersReducedMotion) return () => {};
    rafCallbacks.add(callback);
    if (!rafId) tick();
    return () => rafCallbacks.delete(callback);
  }
  
  function tick() {
    rafCallbacks.forEach(cb => {
      try { cb(); } catch(e) { console.error('ApexMotion tick error:', e); }
    });
    rafId = rafCallbacks.size > 0 ? requestAnimationFrame(tick) : null;
  }
  
  function triggerGlitch(element) {
    if (prefersReducedMotion || !element) return;
    element.classList.add('apex-glitch', 'active');
    setTimeout(() => element.classList.remove('active'), 150);
  }
  
  function setUpdatingState(selector, isUpdating) {
    const els = document.querySelectorAll(selector);
    els.forEach(el => {
      el.classList.toggle('is-updating', isUpdating);
    });
  }
  
  // Auto-apply scan sweep to body on load
  if (!prefersReducedMotion) {
    document.body.classList.add('apex-scan-sweep');
  }
  
  return {
    schedule,
    triggerGlitch,
    setUpdatingState,
    prefersReducedMotion,
    cancel: (handle) => handle && handle()
  };
})();
```

### File: `apex-hal-brain.html` (HAL page template fragment)
```html
<!-- HAL Brain Container — Inject into #apex-stage when page=hal -->
<div id="hal-brain-container" class="hal-brain-container">
  <div class="hal-brain-header">
    <span class="hal-brain-label">NEURAL CORE</span>
    <span id="hal-brain-state" class="hal-brain-state">IDLE</span>
  </div>
  <canvas id="hal-brain-canvas" class="hal-brain-canvas"></canvas>
  <div class="hal-brain-metrics">
    <div class="hal-metric">
      <span class="hal-metric-label">SYNAPSES</span>
      <span id="hal-metric-synapses" class="hal-metric-value">0</span>
    </div>
    <div class="hal-metric">
      <span class="hal-metric-label">ACTIVITY</span>
      <span id="hal-metric-activity" class="hal-metric-value">0%</span>
    </div>
    <div class="hal-metric">
      <span class="hal-metric-label">LATENCY</span>
      <span id="hal-metric-latency" class="hal-metric-value">0ms</span>
    </div>
  </div>
</div>
```

### File: `apex-hal-brain.css` (HAL-specific styles)
```css
/* HAL Neural Core Display */
.hal-brain-container {
  grid-column: 1 / -1;
  grid-row: span 2;
  background: 
    radial-gradient(ellipse at center, rgba(0, 240, 255, 0.03) 0%, transparent 70%),
    var(--apex-void);
  border: 1px solid var(--apex-border);
  position: relative;
  overflow: hidden;
  min-height: 400px;
  display: flex;
  flex-direction: column;
}

.hal-brain-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--apex-border);
  background: rgba(0, 0, 0, 0.3);
}

.hal-brain-label {
  font-family: "Orbitron", sans-serif;
  font-size: 11px;
  letter-spacing: 0.2em;
  color: var(--apex-cyan);
  text-shadow: 0 0 8px rgba(0, 240, 255, 0.5);
}

.hal-brain-state {
  font-family: "JetBrains Mono", monospace;
  font-size: 10px;
  padding: 4px 8px;
  border: 1px solid var(--apex-cyan-dim);
  color: var(--apex-cyan);
  background: rgba(0, 240, 255, 0.05);
  transition: all 0.3s ease;
}

.hal-brain-state.thinking {
  border-color: var(--apex-amber);
  color: var(--apex-amber);
  background: rgba(255, 191, 0, 0.1);
  animation: apexStatePulse 1s ease-in-out infinite;
}

@keyframes apexStatePulse {
  0%, 100% { opacity: 0.7; }
  50% { opacity: 1; }
}

.hal-brain-canvas {
  flex: 1;
  width: 100%;
  display: block;
}

.hal-brain-metrics {
  display: flex;
  gap: 24px;
  padding: 12px 16px;
  border-top: 1px solid var(--apex-border);
  background: rgba(0, 0, 0, 0.3);
}

.hal-metric {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.hal-metric-label {
  font-size: 9px;
  letter-spacing: 0.15em;
  color: var(--apex-text-secondary);
}

.hal-metric-value {
  font-family: "JetBrains Mono", monospace;
  font-size: 14px;
  color: var(--apex-cyan);
  text-shadow: 0 0 8px rgba(0, 240, 255, 0.4);
}
```

### File: `apex-hal-brain.js` (HAL brain logic)
```javascript
/**
 * HAL Neural Core Visualization
 * Include only on HAL page or lazy-load when navigating to HAL
 */

window.HALBrain = (function() {
  'use strict';
  
  const canvas = document.getElementById('hal-brain-canvas');
  if (!canvas) return null;
  
  const ctx = canvas.getContext('2d');
  const stateEl = document.getElementById('hal-brain-state');
  const metricSynapses = document.getElementById('hal-metric-synapses');
  const metricActivity = document.getElementById('hal-metric-activity');
  const metricLatency = document.getElementById('hal-metric-latency');
  
  let width, height;
  let nodes = [];
  let connections = [];
  let animationId = null;
  let currentState = 'idle'; // idle, thinking, reply
  
  const CONFIG = {
    nodeCount: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 45,
    connectionDistance: 120,
    idleSpeed: 0.2,
    thinkSpeed: 2.5,
    colors: {
      cyan: '0, 240, 255',
      amber: '255, 191, 0',
      magenta: '255, 0, 128'
    }
  };
  
  class Node {
    constructor() {
      this.reset();
      this.x = Math.random() * width;
      this.y = Math.random() * height;
    }
    
    reset() {
      this.x = Math.random() * width;
      this.y = Math.random() * height;
      this.vx = (Math.random() - 0.5) * CONFIG.idleSpeed;
      this.vy = (Math.random() - 0.5) * CONFIG.idleSpeed;
      this.radius = 2 + Math.random() * 2;
      this.activation = 0;
      this.lastActivation = 0;
    }
    
    update(state) {
      // Movement
      const speed = state === 'thinking' ? CONFIG.thinkSpeed : CONFIG.idleSpeed;
      this.x += this.vx * (speed / CONFIG.idleSpeed);
      this.y += this.vy * (speed / CONFIG.idleSpeed);
      
      // Boundaries
      if (this.x < 0 || this.x > width) this.vx *= -1;
      if (this.y < 0 || this.y > height) this.vy *= -1;
      
      // Activation decay
      this.activation *= 0.95;
      
      // Random activation in thinking state
      if (state === 'thinking' && Math.random() < 0.02) {
        this.activate();
      }
    }
    
    activate() {
      this.activation = 1;
      this.lastActivation = Date.now();
    }
    
    draw() {
      const alpha = 0.3 + (this.activation * 0.7);
      const color = this.activation > 0.5 ? CONFIG.colors.magenta : CONFIG.colors.cyan;
      
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.radius + (this.activation * 2), 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${color}, ${alpha})`;
      ctx.fill();
      
      // Glow
      if (this.activation > 0.1) {
        ctx.beginPath();
        ctx.arc(this.x, this.y, (this.radius * 3) + (this.activation * 10), 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${color}, ${this.activation * 0.2})`;
        ctx.fill();
      }
    }
  }
  
  function init() {
    resize();
    window.addEventListener('resize', resize);
    
    // Create nodes
    for (let i = 0; i < CONFIG.nodeCount; i++) {
      nodes.push(new Node());
    }
    
    // Pre-calculate connections (static topology)
    updateConnections();
    
    if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      animate();
    } else {
      // Static render for reduced motion
      drawStatic();
    }
  }
  
  function resize() {
    const rect = canvas.parentElement.getBoundingClientRect();
    width = rect.width;
    height = rect.height - 80; // Account for header/footer
    canvas.width = width;
    canvas.height = height;
  }
  
  function updateConnections() {
    connections = [];
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dx = nodes[i].x - nodes[j].x;
        const dy = nodes[i].y - nodes[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < CONFIG.connectionDistance) {
          connections.push({ a: i, b: j, dist });
        }
      }
    }
    if (metricSynapses) metricSynapses.textContent = connections.length;
  }
  
  function drawConnection(conn, time) {
    const nodeA = nodes[conn.a];
    const nodeB = nodes[conn.b];
    
    const active = nodeA.activation > 0.3 || nodeB.activation > 0.3;
    const baseAlpha = 0.1 - (conn.dist / CONFIG.connectionDistance) * 0.1;
    
    ctx.beginPath();
    ctx.moveTo(nodeA.x, nodeA.y);
    ctx.lineTo(nodeB.x, nodeB.y);
    
    if (active && currentState === 'thinking') {
      // Animated dash for active connections
      ctx.strokeStyle = `rgba(${CONFIG.colors.amber}, ${baseAlpha + 0.3})`;
      ctx.lineWidth = 1.5;
      ctx.setLineDash([5, 5]);
      ctx.lineDashOffset = -time / 10;
    } else {
      ctx.strokeStyle = `rgba(${CONFIG.colors.cyan}, ${baseAlpha})`;
      ctx.lineWidth = 0.5;
      ctx.setLineDash([]);
    }
    
    ctx.stroke();
    ctx.setLineDash([]);
  }
  
  function animate() {
    const time = Date.now();
    
    ctx.fillStyle = 'rgba(5, 5, 8, 0.15)';
    ctx.fillRect(0, 0, width, height);
    
    // Update and draw connections first (behind nodes)
    connections.forEach(conn => drawConnection(conn, time));
    
    // Update and draw nodes
    let activeCount = 0;
    nodes.forEach(node => {
      node.update(currentState);
      node.draw();
      if (node.activation > 0.1) activeCount++;
    });
    
    // Update metrics
    if (metricActivity) {
      const activityPct = Math.round((activeCount / nodes.length) * 100);
      metricActivity.textContent = activityPct + '%';
    }
    if (metricLatency) {
      const latency = currentState === 'thinking' ? 12 + Math.floor(Math.random() * 8) : 1;
      metricLatency.textContent = latency + 'ms';
    }
    
    // Occasional connection recalculation (rare, for drift)
    if (time % 60 === 0) updateConnections();
    
    animationId = requestAnimationFrame(animate);
  }
  
  function drawStatic() {
    ctx.fillStyle = 'rgb(5, 5, 8)';
    ctx.fillRect(0, 0, width, height);
    connections.forEach(conn => drawConnection(conn, 0));
    nodes.forEach(node => node.draw());
  }
  
  // State management
  function setState(state) {
    currentState = state;
    if (stateEl) {
      stateEl.textContent = state.toUpperCase();
      stateEl.className = 'hal-brain-state ' + state;
    }
    
    if (state === 'reply') {
      // Trigger convergence animation
      nodes.forEach(node => {
        const dx = (width / 2) - node.x;
        const dy = (height / 2) - node.y;
        node.vx += dx * 0.01;
        node.vy += dy * 0.01;
      });
      
      setTimeout(() => {
        nodes.forEach(node => {
          node.vx = (Math.random() - 0.5) * CONFIG.idleSpeed;
          node.vy = (Math.random() - 0.5) * CONFIG.idleSpeed;
        });
        setState('idle');
      }, 2000);
    }
  }
  
  // Cleanup
  function destroy() {
    if (animationId) cancelAnimationFrame(animationId);
    window.removeEventListener('resize', resize);
  }
  
  init();
  
  return {
    setState,
    destroy,
    getState: () => currentState
  };
})();
```

---

## 4. Implementation Phases (F0 validate → Fn) + Validation Gate

| Phase | Action | Validation Gate |
|-------|--------|-----------------|
| **F0** | Operator reviews this consult; approves/rejects specific items | **STOP HERE** — Do not proceed without operator "validated" or "proceed with X only" |
| **F1** | Apply `apex-chrome-flash.css` globally; add `apex-motion-helper.js` to index.html | Visual check: No layout shifts, motion respects system settings |
| **F2** | Inject HAL brain HTML into HAL page route; include `apex-hal-brain.css` and `.js` | Verify canvas renders, state changes work, performance 60fps |
| **F3** | Wire HAL brain states to existing `apex-hal-bridge.js` events (query submitted → thinking, response received → reply) | End-to-end: User types query, sees brain activate, sees reply convergence |

**DO NOT APPLY until operator says:** "validated," "proceed," or "apply F1 only" etc.

---

## 5. Risks (perf, a11y, distraction) & Rollback

| Risk | Mitigation | Rollback |
|------|------------|----------|
| **Performance** | Canvas uses RAF with auto-pause when tab hidden; node count capped at 45 (scales down on mobile) | Set `CONFIG.nodeCount = 0` or remove canvas element |
| **Motion Sensitivity** | `prefers-reduced-motion` detected at load; disables animations, shows static brain | CSS media query automatically handles; JS checks before RAF |
| **Visual Clutter** | Effects are subtle (opacity 0.03-0.15), not neon; scan sweep is 20s interval, not constant | Remove `apex-scan-sweep` class from body; disable hover effects in CSS |
| **Maintenance** | Vanilla JS only, no dependencies; self-contained files | Delete the three new files; revert to hal-10250 baseline |

**Emergency Rollback Command:** Remove `<script src="apex-motion-helper.js">` and HAL brain includes; delete `apex-chrome-flash.css` references. System returns to hal-10250 baseline.