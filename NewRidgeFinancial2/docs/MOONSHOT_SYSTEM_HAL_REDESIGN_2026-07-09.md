# Moonshot AI — System Interference, Program Deep Dive & HAL Redesign

**Date:** 2026-07-09  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Script:** `scripts/run_moonshot_system_hal_redesign_consult.py`

---

# Verdict
Your NR2 deployment suffers from three critical issues: (1) **Network layer failures**—the financial HAL backend (8765) is dropping connections and the workstation API (8766) is rejecting requests with 403, indicating auth/CORS misconfiguration or stale session middleware; (2) **Resource contention**—Ollama is pinned to 58MB RAM (deceptively low because the 30B/27B models are likely swapped/out) while 2GB+ of browser WebView2/Chrome processes compete for VRAM, creating GPU memory pressure that destabilizes local LLM inference; (3) **HAL UI bloat**—the current canvas appends chat below the dashboard creating vertical sprawl, widgets render at 260px minimum width with excessive diagnostic chrome (HCI scores, stress tests, agent loops) permanently visible, and the 51-widget registration (vs. 6 expected) indicates feed pollution. The redesign moves chat to a persistent right rail, compacts the mosaic to 160px tiles, collapses all runtime diagnostics under `<details>` drawers, and establishes a high-density "mission control" grid.

## 1. Workstation / System Interference Audit

**Port & Process Health**
- **8765 (NR2 Financial+HAL)**: `Connection closed: unexpected error on receive` — PID 4748 (python.exe) is listening but the HTTP server is terminating sockets prematurely. Likely causes: uncaught exception in `nr2_hal_gateway.py` request handler, SQLite lock contention, or CORS preflight failure.
- **8766 (Workstation)**: `403 Forbidden` — PID 12532 (pythonw.exe) is rejecting requests. This is authentication middleware blocking localhost origins or a missing bearer token in the health probe.
- **11434 (Ollama)**: Healthy, owned by PID 1696 (ollama.exe). However, with 30B/27B/24B/14B/8B models listed, VRAM exhaustion is likely causing model unloading/reloading latency.

**Memory & GPU Contention**
- **Browser saturation**: 15+ Chrome/Edge WebView2 processes consuming ~1.8GB RAM. When combined with Ollama’s hybrid GPU layout (pinning `hal-escalate:30b` + `hal-chat:8b`), VRAM is oversubscribed.
- **QuickBooks interference**: QBW.exe (154MB) and QBDBMgrN (116MB) hold file locks on practice data; ensure SoftDent/Schick imports run outside QB maintenance windows.

**Immediate Fixes**
```powershell
# 1. Kill stale Python processes and restart
Stop-Process -Id 4748,12532 -Force; Start-Sleep 2
cd NewRidgeFinancial2
python nr2_hal_gateway.py  # in one terminal (port 8765)
python workstation_api.py  # in another (port 8766) - verify no 403 handler in main()

# 2. Verify Ollama VRAM headroom (30B model needs ~20GB; unload heavy models if GPU has <24GB)
ollama ps  # check which models are currently loaded in VRAM
ollama stop falcon:180b  # definitely unload 180B if present
ollama stop qwen3:235b   # unload 235B
```

## 2. Program Deep Dive — Functional Errors

**P0 — Data Pipeline**
- **Widget feed pollution**: `validate-pages` reports HAL page has **51 widgets** vs. 6 expected in PageSchema. The `halWidgetFeed` is aggregating stale keys. **Fix**: Filter feed to PageSchema whitelist in `app.js` before passing to `HalPageCanvas.render()`.

**P1 — Connectivity**
- **8765 socket drops**: Add error handling in `nr2_hal_gateway.py` around the `classify_financial_query` call; uncaught exceptions there will close the HTTP connection without response.
- **8766 CORS/Auth**: The 403 suggests `NR2_WORKSTATION_ONLY` flag or bearer token validation is failing health checks. Add localhost exemption for `127.0.0.1` in auth middleware.

**P2 — HAL Wiring**
- **Missing stress test aggregation**: `renderSession` calls `H.stressTestHtml(ctx.halStressTest)` but `ctx.halStressTest` is never populated in `app.js` (only `halAgentHealth`, `halModels`, `halSideNotesInbox` are passed).

## 3. Program Deep Dive — Visual / UX Problems

**Layout Architecture**
- **Chat placement**: Current `render()` concatenates dashboard + chat vertically. This forces excessive scrolling on 1080p displays.
- **Widget scale**: CSS uses `minmax(260px, 1fr)` creating 8 massive tiles that dominate the viewport.
- **Diagnostic overload**: Session panel displays 3-column grid with "HCI score", "HAL 9000 ops", "Outbound executors", and "Runtime diagnostics" all expanded by default.

**Density Failures**
- Font sizes are 13-14px for body text with 16-20px padding—too spacious for financial trading-floor aesthetic.
- Status rail uses large "ring" visualizations (60px+ height) for simple percentages.
- Empty states show verbose explanations instead of compact "—" dashes.

## 4. HAL Page Redesign Spec (chat RIGHT, compact, professional)

**Layout ASCII**
```
+-------------------------------------------------------------+------------------+
|  [Situational Hero - compact, 1 line alerts]                |  [Ask HAL]       |
|  [Status Rail - horizontal, compressed]                     |  Chat History    |
|                                                             |  [Textarea]      |
|  [Widget Mosaic - 4-6 cols compact tiles]                   |  [Suggestions]   |
|  [Work Surfaces - single row, icons only]                   |                  |
|  [Session - collapsed diagnostics, small controls]          |  (Sticky, 360px) |
+-------------------------------------------------------------+------------------+
```

**Demoted to Drawers/Details**
- HCI Capability Index scorecard → `<details>` under System Controls
- HAL 9000 autonomous ops status → `<details>` 
- Agent health telemetry (GPU temps, load) → `<details>`
- Stress test results → `<details>`
- Full consent category list → Drawer on click, show only "3 active" summary on surface
- Import diagnostic JSON → Collapsed under "Import & Source Health" header

**Density Targets**
- Mosaic tile: 160px min-width, 10px padding, 11px font, 24px metric height
- Grid gap: 8px (not 12-16px)
- Chat rail: Fixed 360px width, sticky top: 16px, height: calc(100vh - 32px)
- Hero height: Max 120px (currently unbounded)

## 5. Moonshot Code Deliverables

### File: NewRidgeFinancial2/site/hal-page-canvas.js
```javascript
/**
 * HAL Command Center canvas — Moonshot compact layout (chat-right rail).
 * Changes: render() produces split layout; renderAskHal optimized for rail;
 * renderSession diagnostics collapsed; renderWidgetMonitor compact tiles.
 */
const HalPageCanvas = (function () {
  function widgetsApi() {
    if (typeof HalPageWidgets !== "undefined") return HalPageWidgets;
    if (typeof globalThis !== "undefined" && globalThis.HalPageWidgets) return globalThis.HalPageWidgets;
    return null;
  }

  function widgetFromFeed(feed, key) {
    const api = widgetsApi();
    if (api && api.widgetFromFeed) return api.widgetFromFeed(feed, key);
    return feed && feed.widgets ? feed.widgets[key] : null;
  }

  function formatMetrics(widget) {
    const api = widgetsApi();
    if (api && api.formatMetrics) return api.formatMetrics(widget);
    if (typeof HalSkills !== "undefined" && HalSkills.formatWidgetMetrics) return HalSkills.formatWidgetMetrics(widget);
    return "";
  }

  function sparkBarsFromMetrics(widget) {
    const metrics = (widget && widget.metrics) || {};
    const nums = Object.values(metrics)
      .map((v) => {
        const n = Number(String(v == null ? "" : v).replace(/[^0-9.-]/g, ""));
        return Number.isFinite(n) ? Math.abs(n) : null;
      })
      .filter((n) => n != null)
      .slice(0, 8);
    if (!nums.length) {
      return `<div class="widget-sparkline compact" aria-hidden="true"><span class="kpi-spark-bar" style="height:6px"></span><span class="kpi-spark-bar" style="height:10px"></span><span class="kpi-spark-bar" style="height:8px"></span><span class="kpi-spark-bar" style="height:12px"></span></div>`;
    }
    const max = Math.max(...nums, 1);
    return `<div class="widget-sparkline compact" aria-hidden="true">${nums
      .map((n) => `<span class="kpi-spark-bar" style="height:${Math.max(3, Math.round((n / max) * 16))}px"></span>`)
      .join("")}</div>`;
  }

  function mosaicNavTarget(key) {
    if (typeof HalSkills !== "undefined" && HalSkills.WIDGET_NAV && HalSkills.WIDGET_NAV[key]) {
      return HalSkills.WIDGET_NAV[key];
    }
    return "financial";
  }

  function renderWidgetMonitor(ctx, H) {
    const feed = ctx.halWidgetFeed || {};
    // Compact metric specs - same keys, denser presentation
    const metricSpecs = [
      { key: "practiceFinancialOverview", label: "Production" },
      { key: "careDeliveryPerformance", label: "Collections" },
      { key: "quickbooksProfitLossDetail", label: "Net Income" },
      { key: "arAgingAndCollections", label: "A/R Aging" },
      { key: "claimsPipeline", label: "Claims" },
      { key: "caseAcceptance", label: "Case Acc." },
      { key: "documentIntakeQueue", label: "Documents" },
      { key: "officeManagerPriorities", label: "Tasks" },
    ];
    let readyTotal = 0;
    const missionTiles = metricSpecs
      .map((spec) => {
        const w = widgetFromFeed(feed, spec.key);
        const ok = w && String(w.status).toUpperCase() === "SUCCESS";
        if (ok) readyTotal += 1;
        const metrics = formatMetrics(w);
        const status = (w && w.status) || "FAILED";
        const cmd = `Explain ${spec.label}`;
        const page = mosaicNavTarget(spec.key);
        // Compact tile: no heavy glow, smaller text
        return `<article class="widget-card widget-mosaic-tile widget-mosaic-tile--compact" data-hal-widget-key="${H.esc(spec.key)}" data-panel="mosaic-${H.esc(spec.key)}" data-hal-cmd="${H.esc(cmd)}" data-open-page="${H.esc(page)}" data-hal-scroll-widget="${H.esc(spec.key)}" role="button" tabindex="0" aria-label="${H.esc(spec.label)} — ${H.esc(status)}">
          <div class="widget-header compact"><span class="widget-title">${H.esc(spec.label)}</span><span class="widget-status ${ok ? 'ok' : 'warn'}">${H.esc(status)}</span></div>
          <div class="metric-compact">${H.esc(metrics || '—')}</div>
          <div class="widget-canvas compact" data-nr2-spark-host="${H.esc(spec.key)}" aria-hidden="true">${sparkBarsFromMetrics(w)}</div>
        </article>`;
      })
      .join("");
    const widgetTotal = metricSpecs.length;
    return `<section class="hal-panel--widgets hal-widget-mosaic hal-widget-mosaic--compact" data-panel="widgetMosaic">
      ${missionTiles}
      <p class="widget-meta widget-meta--hal compact">${readyTotal}/${widgetTotal} ready · ${H.esc((feed && feed.importMode) || "direct-first")}</p>
    </section>`;
  }

  function registryStats(ctx) {
    const registry = (ctx.halData && ctx.halData.registry) || [];
    const tally = (pred) => registry.filter((e) => pred(String(e.state || "").toLowerCase())).length;
    return {
      registry,
      readyCount: tally((s) => s === "ready"),
      blockedCount: tally((s) => s === "blocked"),
      needsReviewCount: tally((s) => s.includes("review")),
      halLoaded: registry.length > 0,
    };
  }

  // Right-rail optimized chat (taller, sticky behavior via CSS)
  function renderAskHal(ctx, H) {
    const { halAskDraft, halAskLoading, halChatHistory, halData } = ctx;
    const suggestions = (halData && halData.askHal && halData.askHal.suggestions ? halData.askHal.suggestions : []).slice(0, 6);
    const messages = (halChatHistory || []).slice(-30); // deeper history for rail
    const chatHtml = messages.length
      ? `<div class="chat-history chat-history--rail">${messages
          .map((m) => {
            const followups =
              m.role === "hal" && m.followUpChips && m.followUpChips.length
                ? `<div class="prompt-chips prompt-chips--live compact">${m.followUpChips
                    .map((c) => H.actionChip(c.label, `data-hal-followup="${H.esc(c.query)}"`))
                    .join("")}</div>`
                : "";
            const roleClass = m.role === "user" ? "message message-user" : "message message-hal";
            // Compact: no agent loop visualization in rail (move to drawer)
            return `<div class="${roleClass} compact">
                <div class="message-head compact"><span class="msg-sender">${m.role === "user" ? "You" : "HAL"}</span>${m.role === "hal" ? `<button type="button" class="message-copy" data-hal-copy-response title="Copy">${H.uiIcon("copy")}</button>` : ""}</div>
                <p>${H.esc(m.text)}</p>
                ${followups}
              </div>`;
          })
          .join("")}</div>`
      : "";
    const modeLabel = ctx.halModels && ctx.halModels.config && ctx.halModels.config.mode === "online" ? "Auto" : "Local";
    return `<div class="chat-rail-panel chat-rail-panel--right" data-panel="askHal">
      <div class="chat-header compact">
        <div class="chat-title compact"><span class="hal-presence-orb hal-presence-orb--idle" data-hal-presence-orb aria-hidden="true"></span><span>Ask HAL</span></div>
        <div class="chat-status compact"><span class="status-dot"></span>${H.esc(modeLabel)}</div>
      </div>
      <div class="chat-messages chat-messages--rail">${chatHtml || '<p class="chat-placeholder compact">Ask about imports, widgets, or today\'s plan…</p>'}</div>
      <form class="chat-form chat-input compact" id="hpAskForm">
        <textarea class="chat-textarea compact" id="hpAskInput" rows="3" enterkeyhint="send" placeholder="Ask HAL… (Enter to send)" aria-label="Ask HAL">${H.esc(halAskDraft || "")}</textarea>
        <div class="chat-input-row compact">
          <button class="chat-send compact" type="submit" ${halAskLoading ? "disabled" : ""}>${halAskLoading ? "…" : "Send"}</button>
        </div>
      </form>
      <div class="chat-suggestions prompt-chips prompt-chips--live compact">${suggestions.map((s) => H.actionChip(s, `data-hal-suggest="${H.esc(s)}"`)).join("")}</div>
    </div>`;
  }

  function renderStatusRail(ctx, H) {
    const stats = registryStats(ctx);
    const snap = ctx.halProgramSnapshot || {};
    const bundle = snap.importBundle || {};
    const feed = ctx.halWidgetFeed || {};
    const health = feed.sourceHealth || {};
    const diag = bundle.diagnostics && bundle.diagnostics.summary ? bundle.diagnostics.summary : {};
    const importMode = bundle.importMode || (bundle.directFirst ? "direct-first" : "cache");
    const connected = diag.connected != null ? diag.connected : health.connected || 0;
    const missing = diag.missing != null ? diag.missing : health.missing || 0;
    const partial = diag.partial != null ? diag.partial : health.partial || 0;
    const healthTotal = Math.max(1, connected + partial + missing);
    const healthPct = Math.round((connected / healthTotal) * 100);
    const lastSync = (bundle && bundle.lastSyncAt) || (health && health.lastSyncAt) || "";
    const staleImport = lastSync && Number.isFinite(Date.parse(lastSync)) && Date.now() - Date.parse(lastSync) > 3600000;
    
    // Compact horizontal status rail (not vertical stack)
    return `<div class="hal-status-rail--compact" data-panel="statusRail">
      <div class="status-pill"><span class="status-label">Posture</span><span class="status-value">${stats.readyCount} READY</span></div>
      <div class="status-pill"><span class="status-label">Blocked</span><span class="status-value warn">${stats.blockedCount}</span></div>
      <div class="status-pill ${staleImport ? 'stale' : ''}"><span class="status-label">Health</span><span class="status-value">${healthPct}%</span></div>
      <div class="status-pill"><span class="status-label">Mode</span><span class="status-value">${H.esc(importMode)}</span></div>
      <div class="status-actions">
        <button type="button" class="prompt-chip compact" data-hal-cmd="Import status">Status</button>
        <button type="button" class="prompt-chip compact" data-hal-cmd="Refresh imports">Refresh</button>
      </div>
    </div>`;
  }

  function renderSurfaces(ctx, H) {
    const { halData } = ctx;
    const allSurfaces = (halData && halData.workSurfaces && halData.workSurfaces.items) || [];
    // Compact: only first 4, icon-only presentation
    const compactSurfaces = allSurfaces.filter((item) => item.target !== "sidenotes").slice(0, 4);
    const surfaces = compactSurfaces
      .map((item) => {
        const surfOpen = H.surfNavTarget(item);
        const surfCmd = `Open ${item.label}`;
        return `<button type="button" class="surface-chip" data-hal-surf-nav="${H.esc(surfOpen)}" data-hal-cmd="${H.esc(surfCmd)}" title="${H.esc(item.label)}">
          <span class="surface-icon">${H.surfNavIcon(item)}</span>
          <span class="surface-label">${H.esc(item.label)}</span>
        </button>`;
      })
      .join("");
    return `<section class="hal-panel--nav hal-panel--nav--compact" data-panel="workSurfaces">
      <div class="surface-chips-row">${surfaces || H.emptyNote("No surfaces")}</div>
    </section>`;
  }

  function renderSession(ctx, H) {
    const stats = registryStats(ctx);
    const { halData, halInlineFirewallResult } = ctx;
    const consent = (halData && halData.consent) || {};
    const localAlways = (consent.localAlways || []).slice(0, 2).join(" · ") || "Open pages · Explain status";
    
    // Compact controls only; all diagnostics hidden in details
    return `<section class="widget-card hal-panel--session hal-panel--session--compact" data-panel="session">
      <div class="session-compact-grid">
        <div class="session-col">
          <div class="compact-header">Controls</div>
          <div class="control-row">
            <button type="button" class="control-btn compact" data-hal-cmd="Run readiness check" title="Ready">${H.uiIcon("check")}</button>
            <button type="button" class="control-btn compact" data-hal-cmd="Run operator smoke test" title="Smoke">${H.uiIcon("smoke")}</button>
            <button type="button" class="control-btn compact" data-hal-cmd="Staff handoff summary" title="Handoff">${H.uiIcon("handoff")}</button>
            <button type="button" class="control-btn compact" data-hal-about-me title="About">${H.uiIcon("voice")}</button>
            <button type="button" class="control-btn compact" data-hal-drawer="status" title="Audit">${H.uiIcon("audit")}</button>
          </div>
          <p class="widget-footer compact">Registry: ${stats.readyCount} ready · ${stats.blockedCount} blocked</p>
        </div>
        <div class="session-col">
          <div class="compact-header">Trust</div>
          <p class="session-note compact">Local only: ${H.esc(localAlways)}</p>
          ${halInlineFirewallResult ? `<p class="session-note compact">${H.esc(halInlineFirewallResult.text || "")}</p>` : ""}
          <details class="details-panel compact">
            <summary>Diagnostics</summary>
            <div class="diagnostics-drawer">
              ${H.agentHealthHtml ? H.agentHealthHtml(ctx.halAgentHealth, ctx.halModels, ctx.halSideNotesInbox) : ""}
              ${H.stressTestHtml ? H.stressTestHtml(ctx.halStressTest) : ""}
            </div>
          </details>
        </div>
      </div>
    </section>`;
  }

  function renderSituationalHero(ctx, H) {
    const briefing = ctx.halMorningBriefing || (ctx.halProactiveBriefing && ctx.halProactiveBriefing.morningBriefing) || null;
    const sentence = (briefing && briefing.sentence) || "HAL is monitoring SoftDent and QuickBooks imports locally.";
    const feed = ctx.halWidgetFeed || {};
    const alertItems = [];
    const ticker = feed.widgets && feed.widgets.nr2AlertTicker;
    if (ticker && ticker.metrics && ticker.metrics.topAlert) {
      alertItems.push({ text: ticker.metrics.topAlert, level: "warn" });
    }
    const lag = feed.widgets && feed.widgets.nr2CollectionLag;
    if (lag && String(lag.status || "").toUpperCase() !== "SUCCESS") {
      alertItems.push({ text: "Collection lag", level: "warn" });
    }
    // Ultra-compact hero: one line sentence + inline alerts
    const alertsHtml = alertItems.slice(0, 2).map((item) => 
      `<span class="hero-alert ${H.esc(item.level)}" data-hal-cmd="${H.esc(item.text)}">${H.esc(item.text)}</span>`
    ).join("");
    
    return `<section class="hal-situational-hero hal-situational-hero--compact" data-panel="situationalHero">
      <div class="hero-main compact">
        <span class="hero-sentence">${H.esc(sentence)}</span>
        <span class="hero-alerts-inline">${alertsHtml}</span>
      </div>
      <div class="hero-actions compact">
        <button type="button" class="prompt-chip compact" data-hal-cmd="Summarize MTD production">Variance</button>
        <button type="button" class="prompt-chip compact" data-hal-cmd="Show import health">Imports</button>
        <button type="button" class="prompt-chip compact" data-hal-voice-ptt="1">Voice</button>
      </div>
    </section>`;
  }

  function renderDashboard(ctx, H) {
    // Left surface only (chat is separate rail)
    return [
      renderSituationalHero(ctx, H),
      renderStatusRail(ctx, H),
      renderWidgetMonitor(ctx, H),
      renderSurfaces(ctx, H),
      renderSession(ctx, H),
    ].join("");
  }

  function render(ctx, H) {
    // Split layout: left command surface | right chat rail
    return `<div class="hal-command-layout">
      <div class="hal-left-surface">${renderDashboard(ctx, H)}</div>
      <div class="hal-right-rail">${renderAskHal(ctx, H)}</div>
    </div>`;
  }

  function gridClassName() {
    return "hal-command-layout";
  }

  return { render, renderDashboard, renderAskHal, gridClassName };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalPageCanvas;
}
if (typeof globalThis !== "undefined") {
  globalThis.HalPageCanvas = HalPageCanvas;
}
```

### File: NewRidgeFinancial2/site/hal-mockup-overrides.css
```css
/**
 * Moonshot HAL Compact Layout Overrides
 * Chat-right rail, compact mosaic, collapsed diagnostics
 */

/* Split layout foundation */
.app--moonshot-mockup .ms-page--hal .hal-command-layout {
  display: grid;
  grid-template-columns: 1fr 360px;
  gap: 12px;
  align-items: start;
  padding: 12px 16px;
  max-width: 1920px;
  margin: 0 auto;
}

.app--moonshot-mockup .ms-page--hal .hal-left-surface {
  min-width: 0; /* allow truncation */
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.app--moonshot-mockup .ms-page--hal .hal-right-rail {
  position: sticky;
  top: 12px;
  height: calc(100vh - 24px);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* Right rail chat styling */
.app--moonshot-mockup .ms-page--hal .chat-rail-panel--right {
  background: rgba(30,30,30,0.95);
  border: 1px solid var(--border-subtle, #333);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  height: 100%;
  box-shadow: 0 4px 20px rgba(0,0,0,0.4);
}

.app--moonshot-mockup .ms-page--hal .chat-header.compact {
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-subtle, #333);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.app--moonshot-mockup .ms-page--hal .chat-title.compact {
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.app--moonshot-mockup .ms-page--hal .chat-status.compact {
  font-size: 11px;
  color: var(--text-secondary, #a3a3a3);
}

.app--moonshot-mockup .ms-page--hal .chat-messages--rail {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.app--moonshot-mockup .ms-page--hal .chat-history--rail {
  max-height: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.app--moonshot-mockup .ms-page--hal .message.compact {
  padding: 8px 10px;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.35;
  background: rgba(255,255,255,0.03);
  border: 1px solid transparent;
}

.app--moonshot-mockup .ms-page--hal .message-user.compact {
  background: rgba(0,212,255,0.08);
  border-color: rgba(0,212,255,0.25);
  align-self: flex-end;
  max-width: 90%;
}

.app--moonshot-mockup .ms-page--hal .message-hal.compact {
  background: rgba(124,184,138,0.08);
  border-color: rgba(124,184,138,0.25);
  align-self: flex-start;
  max-width: 95%;
}

.app--moonshot-mockup .ms-page--hal .message-head.compact {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
  font-size: 11px;
  color: var(--text-secondary, #888);
}

.app--moonshot-mockup .ms-page--hal .msg-sender {
  font-weight: 600;
  color: var(--accent-cyan, #22d3ee);
}

.app--moonshot-mockup .ms-page--hal .chat-form.compact {
  padding: 10px;
  border-top: 1px solid var(--border-subtle, #333);
}

.app--moonshot-mockup .ms-page--hal .chat-textarea.compact {
  width: 100%;
  background: rgba(0,0,0,0.3);
  border: 1px solid var(--border-subtle, #333);
  border-radius: 6px;
  padding: 8px;
  color: var(--text-primary, #f5f5f5);
  font-size: 12px;
  resize: none;
  min-height: 60px;
  font-family: inherit;
}

.app--moonshot-mockup .ms-page--hal .chat-input-row.compact {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}

.app--moonshot-mockup .ms-page--hal .chat-send.compact {
  padding: 6px 14px;
  background: var(--accent-cyan, #22d3ee);
  color: #000;
  border: none;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.app--moonshot-mockup .ms-page--hal .chat-send.compact:disabled {
  opacity: 0.5;
}

.app--moonshot-mockup .ms-page--hal .prompt-chips.compact {
  padding: 8px 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  border-top: 1px solid var(--border-subtle, #333);
}

/* Compact mosaic widgets */
.app--moonshot-mockup .ms-page--hal .hal-widget-mosaic--compact {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 8px;
}

.app--moonshot-mockup .ms-page--hal .widget-mosaic-tile--compact {
  padding: 10px;
  min-height: 90px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  background: rgba(255,255,255,0.02);
  border: 1px solid var(--border-subtle, #333);
  border-radius: 6px;
  cursor: pointer;
  transition: border-color 0.15s ease, transform 0.15s ease;
}

.app--moonshot-mockup .ms-page--hal .widget-mosaic-tile--compact:hover {
  border-color: rgba(0,212,255,0.4);
  transform: translateY(-1px);
}

.app--moonshot-mockup .ms-page--hal .widget-header.compact {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  color: var(--text-secondary, #a3a3a3);
  margin-bottom: 4px;
}

.app--moonshot-mockup .ms-page--hal .widget-status {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 999px;
  background: rgba(255,255,255,0.08);
}

.app--moonshot-mockup .ms-page--hal .widget-status.ok {
  background: rgba(0,230,118,0.15);
  color: #00e676;
}

.app--moonshot-mockup .ms-page--hal .widget-status.warn {
  background: rgba(255,152,0,0.15);
  color: #ff9800;
}

.app--moonshot-mockup .ms-page--hal .metric-compact {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary, #f5f5f5);
  line-height: 1.2;
}

.app--moonshot-mockup .ms-page--hal .widget-sparkline.compact {
  height: 20px;
  margin-top: 6px;
  display: flex;
  align-items: flex-end;
  gap: 2px;
  opacity: 0.7;
}

.app--moonshot-mockup .ms-page--hal .widget-sparkline.compact .kpi-spark-bar {
  flex: 1;
  min-width: 2px;
  background: linear-gradient(180deg, rgba(0,212,255,0.7), rgba(0,230,118,0.4));
  border-radius: 1px 1px 0 0;
}

.app--moonshot-mockup .ms-page--hal .widget-meta.compact {
  grid-column: 1 / -1;
  font-size: 10px;
  color: var(--text-secondary, #666);
  margin: 2px 0 0 4px;
}

/* Compact status rail */
.app--moonshot-mockup .ms-page--hal .hal-status-rail--compact {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: rgba(255,255,255,0.02);
  border: 1px solid var(--border-subtle, #333);
  border-radius: 6px;
}

.app--moonshot-mockup .ms-page--hal .status-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background: rgba(0,0,0,0.2);
  border-radius: 999px;
  font-size: 11px;
  border: 1px solid rgba(255,255,255,0.06);
}

.app--moonshot-mockup .ms-page--hal .status-pill.stale {
  border-color: rgba(255,152,0,0.3);
}

.app--moonshot-mockup .ms-page--hal .status-label {
  color: var(--text-secondary, #888);
  text-transform: uppercase;
  font-size: 10px;
  letter-spacing: 0.05em;
}

.app--moonshot-mockup .ms-page--hal .status-value {
  font-weight: 700;
  color: var(--text-primary, #f5f5f5);
}

.app--moonshot-mockup .ms-page--hal .status-value.warn {
  color: #ff9800;
}

.app--moonshot-mockup .ms-page--hal .status-actions {
  margin-left: auto;
  display: flex;
  gap: 6px;
}

/* Compact hero */
.app--moonshot-mockup .ms-page--hal .hal-situational-hero--compact {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  background: rgba(0,0,0,0.2);
  border: 1px solid var(--border-subtle, #333);
  border-radius: 6px;
}

.app--moonshot-mockup .ms-page--hal .hero-main.compact {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 12px;
}

.app--moonshot-mockup .ms-page--hal .hero-sentence {
  color: var(--text-primary, #f5f5f5);
  font-weight: 500;
}

.app--moonshot-mockup .ms-page--hal .hero-alerts-inline {
  display: flex;
  gap: 6px;
}

.app--moonshot-mockup .ms-page--hal .hero-alert {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(255,152,0,0.15);
  color: #ff9800;
  border: 1px solid rgba(255,152,0,0.3);
  cursor: pointer;
}

.app--moonshot-mockup .ms-page--hal .hero-actions.compact {
  display: flex;
  gap: 6px;
}

/* Compact surfaces */
.app--moonshot-mockup .ms-page--hal .hal-panel--nav--compact {
  padding: 8px;
  background: rgba(255,255,255,0.02);
  border: 1px solid var(--border-subtle, #333);
  border-radius: 6px;
}

.app--moonshot-mockup .ms-page--hal .surface-chips-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.app--moonshot-mockup .ms-page--hal .surface-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: rgba(0,0,0,0.3);
  border: 1px solid var(--border-subtle, #333);
  border-radius: 999px;
  color: var(--text-secondary, #a3a3a3);
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.app--moonshot-mockup .ms-page--hal .surface-chip:hover {
  border-color: rgba(0,212,255,0.4);
  color: var(--text-primary, #f5f5f5);
}

/* Compact session */
.app--moonshot-mockup .ms-page--hal .hal-panel--session--compact {
  padding: 10px;
  background: rgba(255,255,255,0.02);
  border: 1px solid var(--border-subtle, #333);
  border-radius: 6px;
}

.app--moonshot-mockup .ms-page--hal .session-compact-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

@media (max-width: 1200px) {
  .app--moonshot-mockup .ms-page--hal .session-compact-grid {
    grid-template-columns: 1fr;
  }
}

.app--moonshot-mockup .ms-page--hal .compact-header {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-secondary, #888);
  margin-bottom: 8px;
}

.app--moonshot-mockup .ms-page--hal .control-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.app--moonshot-mockup .ms-page--hal .control-btn.compact {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(255,255,255,0.05);
  border: 1px solid var(--border-subtle, #333);
  border-radius: 6px;
  color: var(--text-secondary, #a3a3a3);
  cursor: pointer;
  padding: 0;
}

.app--moonshot-mockup .ms-page--hal .control-btn.compact:hover {
  border-color: rgba(0,212,255,0.4);
  color: var(--text-primary, #f5f5f5);
}

.app--moonshot-mockup .ms-page--hal .session-note.compact {
  font-size: 11px;
  color: var(--text-secondary, #a3a3a3);
  margin: 4px 0;
}

.app--moonshot-mockup .ms-page--hal .details-panel.compact {
  margin-top: 8px;
  font-size: 11px;
}

.app--moonshot-mockup .ms-page--hal .details-panel.compact summary {
  cursor: pointer;
  color: var(--accent-cyan, #22d3ee);
  user-select: none;
}

.app--moonshot-mockup .ms-page--hal .diagnostics-drawer {
  padding: 8px;
  background: rgba(0,0,0,0.2);
  border-radius: 4px;
  margin-top: 6px;
}

/* Compact prompt chips */
.app--moonshot-mockup .ms-page--hal .prompt-chip.compact {
  padding: 4px 10px;
  font-size: 11px;
  background: rgba(255,255,255,0.05);
  border: 1px solid var(--border-subtle, #333);
  border-radius: 999px;
  color: var(--text-secondary, #a3a3a3);
  cursor: pointer;
}

.app--moonshot-mockup .ms-page--hal .prompt-chip.compact:hover {
  border-color: rgba(0,212,255,0.4);
  color: var(--text-primary, #f5f5f5);
}

/* Responsive rail collapse on small screens */
@media (max-width: 1280px) {
  .app--moonshot-mockup .ms-page--hal .hal-command-layout {
    grid-template-columns: 1fr 320px;
  }
}

@media (max-width: 1024px) {
  .app--moonshot-mockup .ms-page--hal .hal-command-layout {
    grid-template-columns: 1fr;
  }
  .app--moonshot-mockup .ms-page--hal .hal-right-rail {
    position: relative;
    height: 500px;
    top: 0;
  }
}
```

### File: NewRidgeFinancial2/site/app.js (Patch)
Apply this patch to `renderHal()` to ensure `halStressTest` is passed to canvas context:
```javascript
// In renderHal() function, locate the ctx object and add:
const ctx = {
  // ... existing fields ...
  halAgentHealth: (window.NR2HalAgent && window.NR2HalAgent.health) ? window.NR2HalAgent.health() : null,
  halStressTest: (window.NR2HalStress && window.NR2HalStress.latest) ? window.NR2HalStress.latest() : null, // ADD THIS
  halSideNotesInbox: window.sidenotesInbox || null,
  // ...
};
```

## 6. Staff Pages Compaction Recommendations

Apply these density rules to all staff pages (`financial`, `taxes`, `softdent`, `quickbooks`, `ar`, `claims`, `narratives`, `documents`, `library`, `office-manager`):

**Grid & Sizing**
- Change widget grid from `minmax(280px, 1fr)` to `repeat(auto-fill, minmax(200px, 1fr))` for standard pages, `160px` for HAL.
- Reduce section padding from `24px` to `12-16px`.
- Use `gap: 10px` instead of `16-20px`.

**Typography**
- Widget headers: 12-13px uppercase (from 14-16px).
- Metric values: 20-24px (from 32-40px).
- Body/labels: 11px (from 13px).

**Diagnostic Hiding**
- Move "Data provenance", "Last sync", "Source health" from widget footers into tooltips or `<details>` elements.
- Remove "Mockup parity" badges from production UI (keep in devtools only).

**HAL Keys Preservation**
Ensure these keys remain in all renders per PageSchema:
- `halAskHal`, `halImportHealth`, `practiceFinancialOverview`, `careDeliveryPerformance`, `quickbooksProfitLossDetail`, `officeManagerSurfaces`

## 7. Prioritized Fix Roadmap (next 5 commits + acceptance criteria)

**Commit 1: Layout Infrastructure (P0)**
- Replace `hal-page-canvas.js` with split-layout version provided above.
- Add `hal-mockup-overrides.css` compact styles.
- **Acceptance**: Chat rail renders on right side at 360px width, sticky positioning holds on scroll, no horizontal scrollbars at 1280px+ width.

**Commit 2: Diagnostic Demotion (P0)**
- Wrap HCI, Agent Health, Stress Test, detailed consent lists in `<details>` elements with `compact` class.
- **Acceptance**: Initial HAL page load shows <800px height for session panel; diagnostics revealed only on explicit expand.

**Commit 3: Network Stabilization (P1)**
- Fix 8765 connection drops: Add try/except around `classify_financial_query` in `nr2_hal_gateway.py` to return JSON error instead of closing socket.
- Fix 8766 403: Add `if request.remote_addr == '127.0.0.1': allow` bypass in auth middleware.
- **Acceptance**: Health checks return HTTP 200 with JSON body, no more "connection closed" or 403 errors in logs.

**Commit 4: Widget Feed Cleanup (P1)**
- Filter `halWidgetFeed` to whitelist only PageSchema-registered keys before passing to canvas.
- **Acceptance**: `validate-pages` shows HAL widgets actual <= expected (6), not 51.

**Commit 5: VRAM Optimization (P2)**
- Unload oversized models (`falcon:180b`, `qwen3:235b`, `gpt-oss:120b`) from Ollama on startup.
- Implement model rotation in `hal_hub.py` to keep only `hal-chat:8b` + `hal-escalate:30b` pinned per hybrid policy.
- **Acceptance**: `ollama ps` shows max 2 models loaded; GPU VRAM usage <80% during normal operation.

## 8. Operator Smoke Test Checklist

**Browser Checks**
- [ ] Open `http://127.0.0.1:8765` → JSON health response appears (not connection reset).
- [ ] Open `http://127.0.0.1:8766` → Returns 200 OK (not 403).
- [ ] Load HAL page → Chat rail visible on right, sticky on scroll.
- [ ] Resize window to 1024px → Chat rail moves below dashboard (responsive collapse).

**Functional Checks**
- [ ] Click mosaic tile "Production" → Navigates to Financial page.
- [ ] Type "Import status" in chat → Response appears in right rail history.
- [ ] Click "Diagnostics" expander in Session panel → Agent health details revealed.
- [ ] Verify no "51 widgets" warning in console → Feed filtered correctly.

**System Checks**
- [ ] Run `Get-Process python*,ollama* | Select Name,Id,PM` → 8765/8766 processes stable, memory <200MB each.
- [ ] Run `ollama ps` → Only 2 models loaded (8b + 30b).
- [ ] Import SoftDent sample → Import health pill updates to >90% without stale warning.