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
        return `<article class="widget-card widget-mosaic-tile widget-mount-glow span-1" data-hal-widget-key="${H.esc(spec.key)}" data-panel="${H.esc(spec.key)}" data-hal-cmd="${H.esc(cmd)}" role="button" tabindex="0" aria-label="${H.esc(spec.label)} widget — ${H.esc(status)}">
          <div class="widget-header"><span class="widget-title">${H.esc(spec.label)}</span></div>
          <div class="metric-large text-glow">${H.esc(metrics || status)}</div>
          <div class="metric-delta ${deltaClass}"><span>${H.esc(status)}</span></div>
          <div class="widget-sparkline" aria-hidden="true"></div>
          <div class="widget-footer"><span>HAL widget</span><span>${H.esc(status)}</span></div>
        </article>`;
      })
      .join("");
    const widgetTotal = metricSpecs.length;
    return `<section class="hal-panel--widgets hal-widget-mosaic" data-panel="widgetMosaic">${missionTiles}<p class="widget-meta widget-meta--hal">${readyTotal}/${widgetTotal} ready · click a tile to ask HAL · ${H.esc((feed && feed.importMode) || "direct-first")}</p></section>`;
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
    const messages = (halChatHistory || []).slice(-1);
    const chatHtml = messages.length
      ? messages
          .map((m) => {
            const followups =
              m.role === "hal" && m.followUpChips && m.followUpChips.length
                ? `<div class="prompt-chips prompt-chips--live">${m.followUpChips
                    .map((c) => H.actionChip(c.label, `data-hal-followup="${H.esc(c.query)}"`))
                    .join("")}</div>`
                : "";
            const roleClass = m.role === "user" ? "message message-user" : "message message-hal";
            return `<div class="${roleClass}">
                <div class="message-head">
                  <span>${m.role === "user" ? "You" : "HAL"}${m.lane ? ` · ${H.esc(m.lane)}` : ""}</span>
                  ${m.role === "hal" ? `<button type="button" class="message-copy" data-hal-copy-response title="Copy response">${H.uiIcon("copy")}</button>` : ""}
                </div>
                <p>${H.esc(m.text)}</p>
                ${followups}
              </div>`;
          })
          .join("")
      : "";
    const modeLabel =
      ctx.halModels && ctx.halModels.config && ctx.halModels.config.mode === "online" ? "Auto" : "Registry only";
    return `<div class="chat-rail-panel" data-panel="askHal">
      <div class="chat-header">
        <div class="chat-title"><span class="chat-avatar" aria-hidden="true">AI</span> Ask HAL</div>
        <div class="chat-status"><span class="status-dot" aria-hidden="true"></span>${H.esc(modeLabel)} · Local only</div>
      </div>
      <div class="chat-messages">${chatHtml || '<p class="chat-placeholder">Ask about imports, widgets, or today\'s plan…</p>'}</div>
      <form class="chat-form chat-input" id="hpAskForm">
        <textarea class="chat-textarea" id="hpAskInput" rows="2" enterkeyhint="send" placeholder="Ask HAL anything…  (Enter to send)" aria-label="Ask HAL">${H.esc(halAskDraft || "")}</textarea>
        <div class="chat-input-row">
          <button class="chat-send-btn" type="submit" ${halAskLoading ? "disabled" : ""}>${halAskLoading ? "…" : `${H.uiIcon("send")} SEND`}</button>
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
    return postureBlock + importBlock;
  }

  function renderSurfaces(ctx, H) {
    const { halData, halWidgetFeed } = ctx;
    const liveSurfaces = (halWidgetFeed && halWidgetFeed.surfaceCounts) || {};
    const surfaces = ((halData && halData.workSurfaces && halData.workSurfaces.items) || [])
      .map((item) => {
        const reg = ((halData && halData.registry) || []).find((e) => e.id === item.target);
        const live = liveSurfaces[item.target];
        const state = live ? H.mapSurfaceState(live.status) : reg ? reg.state : "unknown";
        const surfOpen = H.surfNavTarget(item);
        const surfCmd = `Explain the ${item.label} work surface and what staff should do next`;
        return `<li class="surface-item surface-item" data-hal-surf-nav="${H.esc(surfOpen)}" data-hal-cmd="${H.esc(surfCmd)}" role="button" tabindex="0">
          <span class="surface-icon">${H.surfNavIcon(item)}</span>
          <div class="surface-main"><strong>${H.esc(item.label)}</strong></div>
          <span class="status-badge status-badge ${state === "Ready" ? "status-badge status-badge--ok" : state === "Needs review" ? "status-badge status-badge--warn" : "status-badge status-badge--off"}">${H.esc(state)}</span>
          <button type="button" class="surface-open-btn" data-hal-surf-open="${H.esc(surfOpen)}" title="Open">${H.uiIcon("chevronRight")}</button>
        </li>`;
      })
      .join("");
    return `<section class="widget-card hal-panel--nav surface-grid" data-panel="workSurfaces">
      ${H.cardHead("STAFF WORK SURFACES", "workSurfaces", "Jump to staff pages", H.cardIconRaw("ui", "surface"))}
      <ul class="surface-list surface-list">${surfaces || H.emptyNote("No work surfaces configured.")}</ul>
    </section>`;
  }

  function renderSession(ctx, H) {
    const stats = registryStats(ctx);
    const { halData, halInlineFirewallResult, halAudit } = ctx;
    const consent = (halData && halData.consent) || {};
    const categories = (consent.categories || []).slice(0, 4);
    const consentList = categories
      .map((item) => {
        const cmd = `Explain staff consent for ${item}`;
        return `<li class="checklist-item" data-hal-cmd="${H.esc(cmd)}" role="button" tabindex="0"><span>${H.esc(item)}</span><b>CONSENT</b></li>`;
      })
      .join("");
    const localAlways = (consent.localAlways || []).slice(0, 5);
    const activity = (halAudit || []).slice(-5).reverse();
    const activityHtml = activity.length
      ? activity
          .map(
            (row) =>
              `<li class="activity-item" data-hal-activity-cmd="${H.esc(row.query || row.label || "")}" role="button" tabindex="0"><i class="activity-dot activity-dot activity-dot--gold"></i><span>${H.esc(row.query || row.label || "")}</span><time>${H.esc(row.time || "")}</time></li>`,
          )
          .join("")
      : H.emptyNote("No HAL activity in this session yet.");
    const auditList = halAudit || [];
    const lastReceipt = auditList.length ? auditList[auditList.length - 1] : null;
    const lastReceiptText = lastReceipt
      ? `${lastReceipt.time || ""} · ${lastReceipt.intent || lastReceipt.query || "local action"}`.trim()
      : "No local receipt this session";

    const outboundExecutors = [
      "Email (SMTP)",
      "QuickBooks IIF export",
      "QuickBooks Online post",
      "Claim submission packet",
      "Narrative portal prep",
      "Payer portal RPA prep",
      "SoftDent writeback queue",
    ];
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
      .map((item) => `<li class="checklist-item" data-hal-cmd="Explain staff consent for ${H.esc(item)}" role="button" tabindex="0"><span>${H.esc(item)}</span><b>LIVE</b></li>`)
      .join("");
    return `<section class="widget-card hal-panel--session" data-panel="session">
      <div class="session-grid">
        <div class="session-col" data-panel="consent">
          ${H.cardHead("TRUST & CONSENT", "consent", "Staff consent policy", H.cardIconRaw("ui", "shield"))}
          <button type="button" class="consent-btn consent-btn" data-hal-cmd="Explain staff consent policy">${H.uiIcon("check")} CONSENT</button>
          <ul class="checklist checklist">${consentList}</ul>
          <p class="session-note"><b>Executors (consent):</b></p>
          <ul class="checklist checklist">${outboundList}</ul>
          ${hciHtml}
          ${aoHtml}
          <p class="session-note"><b>Always local:</b> ${localAlways.length ? localAlways.slice(0, 5).map(H.esc).join(" · ") : "Open pages · Explain status"}</p>
          <button type="button" class="prompt-chip prompt-chip--action" data-hal-cmd="Show outbound audit log">Outbound audit</button>
          ${halInlineFirewallResult ? `<p class="session-note">${H.esc(halInlineFirewallResult.text || "")}</p>` : ""}
        </div>
        <div class="session-col" data-panel="status">
          ${H.cardHead("RECENT ACTIVITY", "status", "Session audit log", H.cardIconRaw("ui", "activity"))}
          <ul class="activity-log activity-log">${activityHtml}</ul>
        </div>
        <div class="session-col" data-panel="controls">
          ${H.cardHead("SYSTEM CONTROLS", "controls", "Readiness and diagnostics", H.cardIconRaw("ui", "check"))}
          <div class="control-grid control-grid">
            <button type="button" class="control-btn" data-hal-cmd="Run readiness check"><span class="control-icon">${H.uiIcon("check")}</span><strong>Readiness</strong></button>
            <button type="button" class="control-btn" data-hal-cmd="Run operator smoke test"><span class="control-icon">${H.uiIcon("smoke")}</span><strong>Smoke</strong></button>
            <button type="button" class="control-btn" data-hal-cmd="Staff handoff summary"><span class="control-icon">${H.uiIcon("handoff")}</span><strong>Handoff</strong></button>
            <button type="button" class="control-btn" data-hal-about-me><span class="control-icon">${H.uiIcon("voice")}</span><strong>About me</strong></button>
            <button type="button" class="control-btn" data-hal-cmd="Monitor sidenotes"><span class="control-icon">${H.navIcon("sidenotes")}</span><strong>Staff notes</strong></button>
            <button type="button" class="control-btn" data-hal-drawer="status"><span class="control-icon">${H.uiIcon("audit")}</span><strong>Audit</strong></button>
          </div>
          <p class="widget-footer">Registry: ${H.esc(stats.readyCount)} ready · ${H.esc(stats.blockedCount)} blocked · Last receipt: ${H.esc(lastReceiptText)}</p>
          <details class="details-panel">
            <summary>Runtime diagnostics</summary>
            ${H.agentHealthHtml(ctx.halAgentHealth, ctx.halModels, ctx.halSideNotesInbox)}
            ${H.stressTestHtml(ctx.halStressTest)}
          </details>
        </div>
      </div>
    </section>`;
  }

  function renderSidenotes(ctx, H) {
    return H.sideNotesProgramCardHtml(ctx.halSideNotes, ctx.halSideNoteMonitor, ctx.halSideNotesInbox, ctx.sidenotesHubPath);
  }

  function renderMorningBriefing(ctx, H) {
    const card =
      ctx.halMorningBriefing ||
      (ctx.halProactiveBriefing && ctx.halProactiveBriefing.morningBriefing) ||
      null;
    if (!card || !card.sentence) return "";
    const domainChips = (card.domains || [])
      .map((d) => `<span class="status-chip status-chip--ok">${H.esc(d)}</span>`)
      .join(" ");
    const kpiHtml = (card.kpiTiles || [])
      .slice(0, 4)
      .map(
        (tile) =>
          `<div class="kpi-ribbon-tile kpi-ribbon-tile--${H.esc(tile.tone || "neutral")}" data-hal-widget-key="${H.esc(tile.widgetKey || "nr2KpiRibbon")}"><span>${H.esc(tile.label)}</span><strong>${H.esc(tile.value)}</strong></div>`,
      )
      .join("");
    const actuatorHtml = (card.actuators || [])
      .map((act) => {
        const id = H.esc(act.actionId || "refresh-imports");
        const label = H.esc(act.label || "Proceed");
        if (act.actionId === "navigate" && act.target) {
          return `<button type="button" class="prompt-chip prompt-chip--action" data-hal-actuator="${id}" data-hal-action="openPage" data-open-page="${H.esc(act.target)}" data-hal-consent="1">${label}</button>`;
        }
        return `<button type="button" class="prompt-chip prompt-chip--action" data-hal-actuator="${id}" data-hal-action="refreshImports" data-hal-consent="1">${label}</button>`;
      })
      .join("");
    return `<section class="widget-card hal-panel--morning-briefing span-2" data-panel="morningBriefing" data-hal-widget-key="halMorningBriefing">
      ${H.cardHead("MORNING BRIEFING", "morningBriefing", "Cross-domain synthesis · operator consent required for actions", H.cardIconRaw("widget", "nr2KpiRibbon"))}
      <p class="hal-morning-briefing__sentence text-glow">${H.esc(card.sentence)}</p>
      <div class="hal-morning-briefing__domains">${domainChips || H.emptyNote("Awaiting import data.")}</div>
      ${kpiHtml ? `<div class="kpi-ribbon hal-morning-briefing__kpi">${kpiHtml}</div>` : ""}
      <p class="widget-footer">${H.esc(card.importHealthSummary || "Import health included in synthesis.")}</p>
      ${actuatorHtml ? `<div class="prompt-chips prompt-chips--live hal-morning-briefing__actuators">${actuatorHtml}</div>` : ""}
    </section>`;
  }

  function renderDashboard(ctx, H) {
    return [
      renderMorningBriefing(ctx, H),
      renderStatusRail(ctx, H),
      renderWidgetMonitor(ctx, H),
      renderSurfaces(ctx, H),
      renderSidenotes(ctx, H),
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
