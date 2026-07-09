/**
 * HAL Command Center canvas — moonshot mockup layout only.
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
      return `<div class="widget-sparkline" aria-hidden="true"><span class="kpi-spark-bar" style="height:8px"></span><span class="kpi-spark-bar" style="height:14px"></span><span class="kpi-spark-bar" style="height:10px"></span><span class="kpi-spark-bar" style="height:18px"></span></div>`;
    }
    const max = Math.max(...nums, 1);
    return `<div class="widget-sparkline" aria-hidden="true">${nums
      .map((n) => `<span class="kpi-spark-bar" style="height:${Math.max(4, Math.round((n / max) * 28))}px"></span>`)
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
    const metricSpecs = [
      { key: "practiceFinancialOverview", label: "Production MTD" },
      { key: "careDeliveryPerformance", label: "Collections" },
      { key: "quickbooksProfitLossDetail", label: "Net income" },
      { key: "arAgingAndCollections", label: "Outstanding A/R" },
      { key: "claimsPipeline", label: "Open claims" },
      { key: "caseAcceptance", label: "Case acceptance" },
      { key: "documentIntakeQueue", label: "Documents" },
      { key: "officeManagerPriorities", label: "Office tasks" },
    ];
    let readyTotal = 0;
    const missionTiles = metricSpecs
      .map((spec) => {
        const w = widgetFromFeed(feed, spec.key);
        const ok = w && String(w.status).toUpperCase() === "SUCCESS";
        if (ok) readyTotal += 1;
        const metrics = formatMetrics(w);
        const status = (w && w.status) || "FAILED";
        const cmd = `Explain the ${spec.label} widget status`;
        const deltaClass = ok ? "delta-positive" : "delta-negative";
        const page = mosaicNavTarget(spec.key);
        return `<article class="widget-card widget-mosaic-tile widget-mount-glow span-1" data-hal-widget-key="${H.esc(spec.key)}" data-panel="mosaic-${H.esc(spec.key)}" data-hal-cmd="${H.esc(cmd)}" data-open-page="${H.esc(page)}" data-hal-scroll-widget="${H.esc(spec.key)}" role="button" tabindex="0" aria-label="${H.esc(spec.label)} widget — ${H.esc(status)}">
          <div class="widget-header"><span class="widget-title">${H.esc(spec.label)}</span></div>
          <div class="metric-large text-glow">${H.esc(metrics || status)}</div>
          <div class="metric-delta ${deltaClass}"><span>${H.esc(status)}</span></div>
          <div class="widget-canvas" data-nr2-spark-host="${H.esc(spec.key)}" aria-hidden="true">${sparkBarsFromMetrics(w)}</div>
        </article>`;
      })
      .join("");
    const widgetTotal = metricSpecs.length;
    return `<section class="hal-panel--widgets hal-widget-mosaic dashboard-grid" data-panel="widgetMosaic">${missionTiles}<p class="widget-meta widget-meta--hal col-12">${readyTotal}/${widgetTotal} ready · local only · click a tile to open page + ask HAL · ${H.esc((feed && feed.importMode) || "direct-first")}</p></section>`;
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

  function renderAskHal(ctx, H) {
    const { halAskDraft, halAskLoading, halChatHistory, halData } = ctx;
    const suggestions = (halData && halData.askHal && halData.askHal.suggestions ? halData.askHal.suggestions : []).slice(0, 6);
    const messages = (halChatHistory || []).slice(-20);
    const chatHtml = messages.length
      ? `<div class="chat-history">${messages
          .map((m) => {
            const followups =
              m.role === "hal" && m.followUpChips && m.followUpChips.length
                ? `<div class="prompt-chips prompt-chips--live">${m.followUpChips
                    .map((c) => H.actionChip(c.label, `data-hal-followup="${H.esc(c.query)}"`))
                    .join("")}</div>`
                : "";
            const loop =
              m.role === "hal" && Array.isArray(m.agentLoop) && m.agentLoop.length
                ? `<div class="hal-agent-loop" aria-label="HAL agent loop">${m.agentLoop
                    .map(
                      (step) =>
                        `<div class="hal-agent-loop__step"><strong>${H.esc(step.phase || step.title || "Step")}</strong>${H.esc(step.detail || step.text || "")}</div>`,
                    )
                    .join("")}</div>`
                : m.role === "hal" && Array.isArray(m.tools) && m.tools.length
                  ? `<div class="hal-agent-loop" aria-label="HAL tool plan">${m.tools
                      .slice(0, 4)
                      .map((t) => `<div class="hal-agent-loop__step"><strong>Tool</strong>${H.esc(t)}</div>`)
                      .join("")}</div>`
                  : "";
            const citations =
              m.role === "hal" && ((m.tools && m.tools.length) || (m.citationWidgets && m.citationWidgets.length))
                ? typeof NR2Tier3 !== "undefined" && NR2Tier3.renderCitationChipsHtml
                  ? NR2Tier3.renderCitationChipsHtml(m.tools, m.citationWidgets)
                  : ""
                : "";
            const roleClass = m.role === "user" ? "message message-user" : "message message-hal";
            return `<div class="${roleClass}">
                <div class="message-head">
                  <span>${m.role === "user" ? "You" : "HAL"}${m.lane ? ` · ${H.esc(m.lane)}` : ""}</span>
                  ${m.role === "hal" ? `<button type="button" class="message-copy" data-hal-copy-response title="Copy response">${H.uiIcon("copy")}</button>` : ""}
                </div>
                ${citations}
                <p>${H.esc(m.text)}</p>
                ${loop}
                ${followups}
              </div>`;
          })
          .join("")}</div>`
      : "";
    const modeLabel =
      ctx.halModels && ctx.halModels.config && ctx.halModels.config.mode === "online" ? "Auto" : "Registry only";
    return `<div class="chat-rail-panel" data-panel="askHal">
      <div class="chat-header">
        <div class="chat-title"><span class="hal-presence-orb hal-presence-orb--idle" data-hal-presence-orb aria-hidden="true"></span><span class="chat-avatar" aria-hidden="true">AI</span> Ask HAL</div>
        <div class="chat-status"><span class="status-dot" data-hal-presence-dot aria-hidden="true"></span>${H.esc(modeLabel)} · Local only</div>
      </div>
      <div class="chat-messages">${chatHtml || '<p class="chat-placeholder">Ask about imports, widgets, or today\'s plan…</p>'}</div>
      <form class="chat-form chat-input" id="hpAskForm">
        <textarea class="chat-textarea" id="hpAskInput" rows="2" enterkeyhint="send" placeholder="Ask HAL anything…  (Enter to send)" aria-label="Ask HAL">${H.esc(halAskDraft || "")}</textarea>
        <div class="chat-input-row">
          <button class="chat-send" type="submit" ${halAskLoading ? "disabled" : ""}>${halAskLoading ? "…" : `${H.uiIcon("send")} SEND`}</button>
        </div>
      </form>
      <div class="chat-suggestions prompt-chips prompt-chips--live">${suggestions.map((s) => H.actionChip(s, `data-hal-suggest="${H.esc(s)}"`)).join("")}</div>
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
    const modeLabel = ctx.halModels && ctx.halModels.config && ctx.halModels.config.mode === "online" ? "Auto" : "Registry-only";
    const publish =
      (feed.jobs && feed.jobs.widgetPublish && feed.jobs.widgetPublish.status) || "—";
    const topAction =
      (ctx.halProactiveBriefing && ctx.halProactiveBriefing.topAction && ctx.halProactiveBriefing.topAction.title) ||
      "Review registry posture";

    const healthTotal = Math.max(1, connected + partial + missing);
    const healthPct = Math.round((connected / healthTotal) * 100);
    const lastSync =
      (bundle && bundle.lastSyncAt) ||
      (health && health.lastSyncAt) ||
      (diag && diag.lastSyncAt) ||
      "";
    const staleImport =
      lastSync && Number.isFinite(Date.parse(lastSync)) && Date.now() - Date.parse(lastSync) > 3600000;
    const importStaleClass = staleImport ? " hal-health-ring--stale" : "";
    const postureValue = stats.halLoaded ? `${stats.readyCount} READY` : "IDLE";
    const postureBlock = `<div class="lane-badge hal-panel--posture" data-panel="statusRail">
      <div class="lane-header">
        <div>
          <div class="lane-label">PROGRAM POSTURE</div>
          <div class="lane-value">${H.esc(postureValue)}</div>
        </div>
        <div class="lane-status">
          <span class="status-dot" aria-hidden="true"></span>
          <span>${H.esc(stats.halLoaded ? "ACTIVE" : "STANDBY")}</span>
        </div>
      </div>
      <div class="lane-sub">
        <div class="lane-metric"><span>BLOCKED</span> <strong>${H.esc(stats.blockedCount)}</strong></div>
        <div class="lane-metric"><span>Mode:</span> <strong>${H.esc(modeLabel)}</strong></div>
        <div class="lane-metric"><span>Publish:</span> <strong>${H.esc(publish)}</strong></div>
      </div>
      <p class="widget-footer">Next: ${H.esc(topAction)}</p>
      <details class="details-panel" data-panel="reasoning">
        <summary>Local AI readiness</summary>
        ${H.aiReadinessHtml(ctx.halModels)}
      </details>
    </div>`;
    const importBlock = `<div class="import-health hal-panel--import hal-health-ring${importStaleClass}" data-panel="importHealth" data-health-score="${healthPct}" data-last-sync="${H.esc(lastSync || "")}">
      ${H.cardHead("IMPORT & SOURCE HEALTH", "importHealth", "Import mode and dataset health", H.cardIconRaw("widget", "halImportHealth"))}
      <span class="health-score text-glow">${H.esc(healthPct)}%</span>
      <div class="health-bar" aria-hidden="true"><div class="health-fill" style="width:${healthPct}%"></div></div>
      <div class="health-details">
        <div class="health-item"><span class="health-item-value">${H.esc(connected)}</span><div class="health-item-label">Connected</div></div>
        <div class="health-item"><span class="health-item-value">${H.esc(partial)}</span><div class="health-item-label">Partial</div></div>
        <div class="health-item"><span class="health-item-value">${H.esc(missing)}</span><div class="health-item-label">Missing</div></div>
      </div>
      <p class="widget-footer">Mode: ${H.esc(importMode)}</p>
      <div class="prompt-chips prompt-chips--tight">
        ${H.actionChip("Import status", 'data-hal-cmd="Import status"')}
        ${H.actionChip("Refresh imports", 'data-hal-cmd="Refresh imports"')}
      </div>
    </div>`;
    return `<div class="hal-status-stack">${postureBlock}${importBlock}</div>`;
  }

  function renderSurfaces(ctx, H) {
    const { halData, halWidgetFeed } = ctx;
    const liveSurfaces = (halWidgetFeed && halWidgetFeed.surfaceCounts) || {};
    const allSurfaces = (halData && halData.workSurfaces && halData.workSurfaces.items) || [];
    const compactSurfaces = allSurfaces.filter((item) => item.target !== "sidenotes").slice(0, 5);
    const surfaces = compactSurfaces
      .map((item) => {
        const reg = ((halData && halData.registry) || []).find((e) => e.id === item.target);
        const live = liveSurfaces[item.target];
        const state = live ? H.mapSurfaceState(live.status) : reg ? reg.state : "unknown";
        const surfOpen = H.surfNavTarget(item);
        const surfCmd = `Explain the ${item.label} work surface and what staff should do next`;
        const badgeTone =
          state === "Ready" ? "status-badge--ok" : state === "Needs review" ? "status-badge--warn" : "status-badge--off";
        return `<li class="surface-row" data-hal-surf-nav="${H.esc(surfOpen)}" data-hal-cmd="${H.esc(surfCmd)}" role="button" tabindex="0">
          <span class="surface-icon">${H.surfNavIcon(item)}</span>
          <div class="surface-main"><strong>${H.esc(item.label)}</strong></div>
          <span class="status-badge ${badgeTone}">${H.esc(state)}</span>
          <button type="button" class="surface-chev" data-hal-surf-open="${H.esc(surfOpen)}" title="Open">${H.uiIcon("chevronRight")}</button>
        </li>`;
      })
      .join("");
    return `<section class="widget-card hal-panel--nav surface-grid" data-panel="workSurfaces">
      ${H.cardHead("STAFF WORK SURFACES", "workSurfaces", "Jump to staff pages", H.cardIconRaw("ui", "surface"))}
      <ul class="surface-list">${surfaces || H.emptyNote("No work surfaces configured.")}</ul>
    </section>`;
  }

  function renderSession(ctx, H) {
    const stats = registryStats(ctx);
    const { halData, halInlineFirewallResult, halAudit } = ctx;
    const consent = (halData && halData.consent) || {};
    const categories = (consent.categories || []).slice(0, 3);
    const consentList = categories
      .map((item) => {
        const cmd = `Explain staff consent for ${item}`;
        return `<li class="checklist-row--active" data-hal-cmd="${H.esc(cmd)}" role="button" tabindex="0"><span>${H.esc(item)}</span><b>CONSENT</b></li>`;
      })
      .join("");
    const localAlways = (consent.localAlways || []).slice(0, 3);
    const activity = (halAudit || []).slice(-3).reverse();
    const activityHtml = activity.length
      ? activity
          .map(
            (row) =>
              `<li class="activity-row--active" data-hal-activity-cmd="${H.esc(row.query || row.label || "")}" role="button" tabindex="0"><i class="activity-dot activity-dot--gold"></i><span>${H.esc(row.query || row.label || "")}</span><time>${H.esc(row.time || "")}</time></li>`,
          )
          .join("")
      : H.emptyNote("No HAL activity in this session yet.");
    const auditList = halAudit || [];
    const lastReceipt = auditList.length ? auditList[auditList.length - 1] : null;
    const lastReceiptText = lastReceipt
      ? `${lastReceipt.time || ""} · ${lastReceipt.intent || lastReceipt.query || "local action"}`.trim()
      : "No local receipt this session";

    const outboundExecutors = ["Email (SMTP)", "QuickBooks IIF export", "Claim submission packet", "SoftDent writeback queue"];
    const hci =
      typeof HalCapabilityIndex !== "undefined" && HalCapabilityIndex.compute
        ? HalCapabilityIndex.compute(ctx, ctx.halModels)
        : null;
    const ao =
      typeof HalAutonomousOps !== "undefined" && HalAutonomousOps.status ? HalAutonomousOps.status() : null;
    const hciHtml = hci
      ? `<p class="session-note"><b>HCI:</b> ${H.esc(String(hci.score))}/${H.esc(String(hci.max))} (${H.esc(String(hci.percent))}%) · ${H.esc(hci.band)}</p>
          <button type="button" class="prompt-chip prompt-chip--action" data-hal-cmd="Show HAL capability index">Scorecard</button>
          <button type="button" class="prompt-chip prompt-chip--action" data-hal-cmd="Run orchestrator triage">Orchestrator</button>`
      : "";
    const aoHtml = ao
      ? `<p class="session-note"><b>HAL 9000 ops:</b> ${ao.running && !ao.paused ? "running" : ao.paused ? "paused" : "stopped"}</p>`
      : "";
    const outboundList = outboundExecutors
      .map((item) => `<li class="checklist-row--active" data-hal-cmd="Explain staff consent for ${H.esc(item)}" role="button" tabindex="0"><span>${H.esc(item)}</span><b>LIVE</b></li>`)
      .join("");
    return `<section class="widget-card hal-panel--session" data-panel="session">
      <div class="session-grid">
        <div class="session-col" data-panel="consent">
          ${H.cardHead("TRUST & CONSENT", "consent", "Staff consent policy", H.cardIconRaw("ui", "shield"))}
          <button type="button" class="checklist-active--btn" data-hal-cmd="Explain staff consent policy">${H.uiIcon("check")} CONSENT</button>
          <p class="session-note session-note--compact"><b>Always local:</b> ${localAlways.length ? localAlways.map(H.esc).join(" · ") : "Open pages · Explain status"}</p>
          ${halInlineFirewallResult ? `<p class="session-note session-note--compact">${H.esc(halInlineFirewallResult.text || "")}</p>` : ""}
          <details class="details-panel details-panel--compact">
            <summary>Consent categories &amp; executors</summary>
            <ul class="checklist-list">${consentList}</ul>
            <p class="session-note"><b>Executors (consent):</b></p>
            <ul class="checklist-list">${outboundList}</ul>
          </details>
        </div>
        <div class="session-col" data-panel="status">
          ${H.cardHead("RECENT ACTIVITY", "status", "Session audit log", H.cardIconRaw("ui", "activity"))}
          <ul class="activity-log">${activityHtml}</ul>
        </div>
        <div class="session-col" data-panel="controls">
          ${H.cardHead("SYSTEM CONTROLS", "controls", "Readiness and diagnostics", H.cardIconRaw("ui", "check"))}
          <div class="control-grid control-grid--compact">
            <button type="button" class="control-btn" data-hal-cmd="Run readiness check"><span class="control-icon">${H.uiIcon("check")}</span><strong>Ready</strong></button>
            <button type="button" class="control-btn" data-hal-cmd="Run operator smoke test"><span class="control-icon">${H.uiIcon("smoke")}</span><strong>Smoke</strong></button>
            <button type="button" class="control-btn" data-hal-cmd="Staff handoff summary"><span class="control-icon">${H.uiIcon("handoff")}</span><strong>Handoff</strong></button>
            <button type="button" class="control-btn" data-hal-about-me><span class="control-icon">${H.uiIcon("voice")}</span><strong>About</strong></button>
            <button type="button" class="control-btn" data-hal-drawer="status"><span class="control-icon">${H.uiIcon("audit")}</span><strong>Audit</strong></button>
          </div>
          <p class="widget-footer widget-footer--compact">Registry: ${H.esc(stats.readyCount)} ready · ${H.esc(stats.blockedCount)} blocked · Last receipt: ${H.esc(lastReceiptText)}</p>
          <details class="details-panel details-panel--compact">
            <summary>Runtime diagnostics</summary>
            ${hciHtml}
            ${aoHtml}
            ${H.agentHealthHtml(ctx.halAgentHealth, ctx.halModels, ctx.halSideNotesInbox)}
            ${H.stressTestHtml(ctx.halStressTest)}
          </details>
        </div>
      </div>
    </section>`;
  }

  function renderSituationalHero(ctx, H) {
    const briefing =
      ctx.halMorningBriefing ||
      (ctx.halProactiveBriefing && ctx.halProactiveBriefing.morningBriefing) ||
      null;
    const sentence =
      (briefing && briefing.sentence) ||
      (ctx.halProactiveBriefing && ctx.halProactiveBriefing.headline) ||
      "HAL is monitoring SoftDent and QuickBooks imports locally.";
    const feed = ctx.halWidgetFeed || {};
    const alertItems = [];
    const ticker = feed.widgets && feed.widgets.nr2AlertTicker;
    if (ticker && ticker.metrics && ticker.metrics.topAlert) {
      alertItems.push({ text: ticker.metrics.topAlert, level: "warn" });
    }
    const lag = feed.widgets && feed.widgets.nr2CollectionLag;
    if (lag && String(lag.status || "").toUpperCase() !== "SUCCESS") {
      alertItems.push({ text: lag.summary || "Collection lag needs review", level: "warn" });
    }
    const recon = feed.widgets && feed.widgets.nr2ProductionReconciliation;
    if (recon && String(recon.status || "").toUpperCase() === "DEGRADED") {
      alertItems.push({ text: recon.summary || "Production vs QuickBooks variance elevated", level: "warn" });
    }
    // Do not invent green "all clear" filler — only show real exceptions.
    const alertsHtml = alertItems
      .slice(0, 2)
      .map(
        (item) =>
          `<button type="button" class="prompt-chip prompt-chip--action nr2-alert-ticker__item nr2-alert-ticker__item--${H.esc(item.level)}" data-hal-cmd="${H.esc(item.text)}">${H.esc(item.text)}</button>`,
      )
      .join("");
    const kpiHtml =
      briefing && briefing.kpiTiles && briefing.kpiTiles.length
        ? `<div class="kpi-ribbon hal-hero-kpi" data-panel="morningBriefing" data-hal-widget-key="halMorningBriefing">${briefing.kpiTiles
            .slice(0, 3)
            .map(
              (tile, index) =>
                `<div class="kpi-ribbon-tile kpi-ribbon-tile--${H.esc(tile.tone || "neutral")}" data-hal-kpi-tile="${index}"><span>${H.esc(tile.label)}</span><strong>${H.esc(tile.value)}</strong></div>`,
            )
            .join("")}</div>`
        : "";
    const actuatorHtml =
      briefing && briefing.actuators && briefing.actuators.length
        ? `<div class="prompt-chips prompt-chips--live hal-hero-actuators">${briefing.actuators
            .slice(0, 2)
            .map((act) => {
              const id = H.esc(act.actionId || "refresh-imports");
              const label = H.esc(act.label || "Proceed");
              if (act.actionId === "navigate" && act.target) {
                return `<button type="button" class="prompt-chip prompt-chip--action" data-hal-actuator="${id}" data-hal-action="openPage" data-open-page="${H.esc(act.target)}" data-hal-consent="1">${label}</button>`;
              }
              return `<button type="button" class="prompt-chip prompt-chip--action" data-hal-actuator="${id}" data-hal-action="refreshImports" data-hal-consent="1">${label}</button>`;
            })
            .join("")}</div>`
        : "";
    return `<section class="widget-card hal-situational-hero hal-situational-hero--compact" data-panel="situationalHero" data-hal-widget-key="halSituationalHero">
      <div class="hal-situational-hero__main">
        ${H.cardHead("SITUATIONAL HERO", "situationalHero", "Living command posture", H.cardIconRaw("widget", "nr2KpiRibbon"))}
        <p class="hal-morning-briefing__sentence text-glow">${H.esc(sentence)}</p>
        ${kpiHtml}
        <div class="prompt-chips prompt-chips--live hal-situational-hero__actions">
          <button type="button" class="prompt-chip prompt-chip--action" data-hal-cmd="Summarize MTD production">Variance</button>
          <button type="button" class="prompt-chip prompt-chip--action" data-hal-cmd="Show import health">Imports</button>
          <button type="button" class="prompt-chip prompt-chip--action" data-hal-voice-ptt="1">Voice</button>
        </div>
        ${actuatorHtml}
      </div>
      <div class="hal-situational-hero__alerts" aria-label="HAL exceptions">${alertsHtml}</div>
    </section>`;
  }

  function renderDashboard(ctx, H) {
    return [
      `<div class="dashboard-grid hal-dashboard-top">${renderSituationalHero(ctx, H)}${renderStatusRail(ctx, H)}</div>`,
      renderWidgetMonitor(ctx, H),
      `<div class="hal-compact-mid">${renderSurfaces(ctx, H)}</div>`,
      renderSession(ctx, H),
    ].join("");
  }

  function render(ctx, H) {
    return renderDashboard(ctx, H) + renderAskHal(ctx, H);
  }

  function gridClassName() {
    return "dashboard-grid";
  }

  return { render, renderDashboard, renderAskHal, gridClassName };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalPageCanvas;
}
if (typeof globalThis !== "undefined") {
  globalThis.HalPageCanvas = HalPageCanvas;
}
