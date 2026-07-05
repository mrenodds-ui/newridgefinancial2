/**
 * HAL Command Center canvas — hal-102 compact layout.
 */
const HalPageCanvas = (function () {
  function schemaApi() {
    if (typeof HalPageSchema !== "undefined") return HalPageSchema;
    if (typeof globalThis !== "undefined" && globalThis.HalPageSchema) return globalThis.HalPageSchema;
    return null;
  }

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

  function statusClass(status) {
    const s = String(status || "").toUpperCase();
    if (s === "SUCCESS") return "hp-wg-badge--ok";
    if (s === "DEGRADED") return "hp-wg-badge--warn";
    return "hp-wg-badge--off";
  }

  function zoneIcon(zone, H) {
    const spec = zone.icon || { type: "hal" };
    if (spec.type === "nav") return H.cardIconRaw("nav", spec.key);
    if (spec.type === "widget") return H.cardIconRaw("widget", spec.key);
    if (spec.type === "ui") return H.cardIconRaw("ui", spec.key);
    return H.cardIconRaw("hal");
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

  function widgetRow(spec, feed, H) {
    const key = spec.key;
    const w = widgetFromFeed(feed, key);
    const nav = spec.nav || (w && w.navTarget) || "";
    if (!w) {
      return `<div class="hp-wg-row hp-wg-row--empty" data-hal-widget-key="${H.esc(key)}">
        <span class="hp-wg-ico">${H.widgetIcon(key)}</span>
        <span class="hp-wg-row__title">${H.esc(key)}</span>
        <span class="hp-wg-badge hp-wg-badge--off">NO FEED</span>
      </div>`;
    }
    const widgetCmd = `Explain why the ${w.title} widget shows its current status and what data is missing`;
    const metrics = formatMetrics(w);
    const configure =
      w.status === "FAILED" && widgetsApi() && widgetsApi().canConfigureWidget && widgetsApi().canConfigureWidget(w)
        ? `<button type="button" class="hp-wg-configure" data-hal-configure-export="${H.esc(key)}">Fix</button>`
        : "";
    return `<div class="hp-wg-row hp-wg-card--active" data-hal-widget-key="${H.esc(key)}" data-hal-cmd="${H.esc(widgetCmd)}" title="${H.esc(widgetCmd)}">
      <span class="hp-wg-ico">${H.widgetIcon(key)}</span>
      <div class="hp-wg-row__body">
        <strong class="hp-wg-row__title">${H.esc(w.title || key)}</strong>
        ${metrics ? `<span class="hp-wg-row__metrics">${H.esc(metrics)}</span>` : ""}
      </div>
      <span class="hp-wg-badge ${statusClass(w.status)}">${H.esc(w.status || "FAILED")}</span>
      <button type="button" class="hp-wg-open hp-wg-open--compact" data-hal-widget-nav="${H.esc(nav)}">${H.uiIcon("externalLink")}</button>
      ${configure}
    </div>`;
  }

  function groupNeedsAttention(group, feed) {
    return (group.widgets || []).some((spec) => {
      const w = widgetFromFeed(feed, spec.key);
      const s = String((w && w.status) || "FAILED").toUpperCase();
      return s !== "SUCCESS";
    });
  }

  function renderWidgetMonitor(ctx, H) {
    const schema = schemaApi();
    const groups = schema ? schema.widgetGroupZones() : [];
    const feed = ctx.halWidgetFeed;
    let readyTotal = 0;
    let widgetTotal = 0;
    const sections = groups
      .map((group) => {
        const rows = (group.widgets || []).map((spec) => widgetRow(spec, feed, H)).join("");
        widgetTotal += (group.widgets || []).length;
        readyTotal += (group.widgets || []).filter((s) => {
          const w = widgetFromFeed(feed, s.key);
          return w && String(w.status).toUpperCase() === "SUCCESS";
        }).length;
        const open = groupNeedsAttention(group, feed);
        return `<details class="hp-wg-section hp-wg-section--${H.esc(group.accent || "gold")}" ${open ? "open" : ""}>
          <summary class="hp-wg-section__head">
            <span class="hp-wg-section__ico">${zoneIcon({ icon: group.icon }, H)}</span>
            <span class="hp-wg-section__title">${H.esc(group.title)}</span>
            <span class="hp-wg-section__count">${(group.widgets || []).filter((s) => {
              const w = widgetFromFeed(feed, s.key);
              return w && String(w.status).toUpperCase() === "SUCCESS";
            }).length}/${(group.widgets || []).length}</span>
          </summary>
          <div class="hp-wg-list">${rows}</div>
        </details>`;
      })
      .join("");
    return `<section class="hp-card hp-card--widgets" data-panel="widgets" style="grid-area:widgets;">
      ${H.cardHead("MANAGER WIDGETS", "widgets", "Widget feed grouped by staff page", H.cardIconRaw("widget", "officeManagerPriorities"))}
      <p class="hp-zone-meta">${readyTotal}/${widgetTotal} ready · click a row to ask HAL · ${H.esc((feed && feed.importMode) || "direct-first")}</p>
      <div class="hp-wg-monitor">${sections || H.emptyNote("Widget feed not loaded.")}</div>
    </section>`;
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
                ? `<div class="hp-chips hp-live-actions">${m.followUpChips
                    .map((c) => H.actionChip(c.label, `data-hal-followup="${H.esc(c.query)}"`))
                    .join("")}</div>`
                : "";
            return `<div class="hp-chat-row hp-chat-row--${m.role === "user" ? "user" : "hal"}">
                <div class="hp-chat-row__head">
                  <span>${m.role === "user" ? "You" : "HAL"}${m.lane ? ` · ${H.esc(m.lane)}` : ""}</span>
                  ${m.role === "hal" ? `<button type="button" class="hp-chat-copy" data-hal-copy-response title="Copy response">${H.uiIcon("copy")}</button>` : ""}
                </div>
                <p>${H.esc(m.text)}</p>
                ${followups}
              </div>`;
          })
          .join("")
      : "";
    return `<section class="hp-card hp-card--ask" data-panel="askHal" style="grid-area:command;">
      ${H.cardHead("ASK HAL", "askHal", "Ask HAL and view the latest response", H.cardIconRaw("hal"))}
      <form class="hp-ask__box hp-live-form" id="hpAskForm">
        <textarea class="hp-live-input hp-live-textarea" id="hpAskInput" rows="2" enterkeyhint="send" placeholder="Ask HAL anything…  (Enter to send)" aria-label="Ask HAL">${H.esc(halAskDraft || "")}</textarea>
        <div class="hp-ask__bar">
          <span class="hp-ask__mode">MODE</span>
          <span class="hp-ask__sel">${H.esc(ctx.halModels && ctx.halModels.config && ctx.halModels.config.mode === "online" ? "Auto" : "Registry only")}</span>
          <button class="hp-ask__send hp-live-send" type="submit" ${halAskLoading ? "disabled" : ""}>${halAskLoading ? "…" : `${H.uiIcon("send")} SEND`}</button>
        </div>
      </form>
      ${chatHtml ? `<div class="hp-inline-chat hp-inline-chat--compact">${chatHtml}</div>` : ""}
      <div class="hp-chips hp-live-actions">${suggestions.map((s) => H.actionChip(s, `data-hal-suggest="${H.esc(s)}"`)).join("")}</div>
    </section>`;
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

    return `<section class="hp-card hp-card--status" data-panel="statusRail" style="grid-area:status;">
      <div class="hp-status-rail">
        <div class="hp-status-rail__block" data-panel="reasoning">
          ${H.cardHead("PROGRAM POSTURE", "reasoning", "Registry and reasoning detail", H.cardIconRaw("widget", "halProgramPosture"))}
          <dl class="hp-stats hp-stats--compact">
            <div><dt>STATUS</dt><dd class="${stats.halLoaded ? "hp-ok" : ""}">${H.esc(stats.halLoaded ? "Active" : "Idle")}</dd></div>
            <div><dt>READY</dt><dd class="hp-ok">${H.esc(stats.readyCount)}</dd></div>
            <div><dt>BLOCKED</dt><dd>${H.esc(stats.blockedCount)}</dd></div>
            <div><dt>MODE</dt><dd>${H.esc(modeLabel)}</dd></div>
            <div><dt>PUBLISH</dt><dd>${H.esc(publish)}</dd></div>
          </dl>
          <p class="hp-card__foot hp-muted">Next: ${H.esc(topAction)}</p>
          <details class="hp-details">
            <summary>Local AI readiness</summary>
            ${H.aiReadinessHtml(ctx.halModels)}
          </details>
        </div>
        <div class="hp-status-rail__block" data-panel="importHealth">
          ${H.cardHead("IMPORT & SOURCE HEALTH", "importHealth", "Import mode and dataset health", H.cardIconRaw("widget", "halImportHealth"))}
          <dl class="hp-stats hp-stats--compact">
            <div><dt>MODE</dt><dd class="hp-ok">${H.esc(importMode)}</dd></div>
            <div><dt>CONNECTED</dt><dd class="hp-ok">${H.esc(connected)}</dd></div>
            <div><dt>PARTIAL</dt><dd>${H.esc(partial)}</dd></div>
            <div><dt>MISSING</dt><dd>${H.esc(missing)}</dd></div>
          </dl>
          <div class="hp-chips hp-chips--tight">
            ${H.actionChip("Import status", 'data-hal-cmd="Import status"')}
            ${H.actionChip("Refresh imports", 'data-hal-cmd="Refresh imports"')}
          </div>
        </div>
      </div>
    </section>`;
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
        return `<li class="hp-surf__row hp-surf__row--compact" data-hal-surf-nav="${H.esc(surfOpen)}" data-hal-cmd="${H.esc(surfCmd)}" role="button" tabindex="0">
          <span class="hp-surf__ico">${H.surfNavIcon(item)}</span>
          <div class="hp-surf__main"><strong>${H.esc(item.label)}</strong></div>
          <span class="hp-surf__state hp-wg-badge ${state === "Ready" ? "hp-wg-badge--ok" : state === "Needs review" ? "hp-wg-badge--warn" : "hp-wg-badge--off"}">${H.esc(state)}</span>
          <button type="button" class="hp-surf__chev" data-hal-surf-open="${H.esc(surfOpen)}" title="Open">${H.uiIcon("chevronRight")}</button>
        </li>`;
      })
      .join("");
    return `<section class="hp-card hp-card--nav" data-panel="workSurfaces" style="grid-area:nav;">
      ${H.cardHead("STAFF WORK SURFACES", "workSurfaces", "Jump to staff pages", H.cardIconRaw("ui", "surface"))}
      <ul class="hp-surf hp-surf--compact">${surfaces || H.emptyNote("No work surfaces configured.")}</ul>
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
        return `<li class="hp-fw__row--active" data-hal-cmd="${H.esc(cmd)}" role="button" tabindex="0"><span>${H.esc(item)}</span><b>CONSENT</b></li>`;
      })
      .join("");
    const localAlways = (consent.localAlways || []).slice(0, 5);
    const activity = (halAudit || []).slice(-5).reverse();
    const activityHtml = activity.length
      ? activity
          .map(
            (row) =>
              `<li class="hp-log__row--active" data-hal-activity-cmd="${H.esc(row.query || row.label || "")}" role="button" tabindex="0"><i class="hp-log__dot hp-log__dot--gold"></i><span>${H.esc(row.query || row.label || "")}</span><time>${H.esc(row.time || "")}</time></li>`,
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
      ? `<p class="hp-fw__score"><b>HCI:</b> ${H.esc(String(hci.score))}/${H.esc(String(hci.max))} (${H.esc(String(hci.percent))}%) · ${H.esc(hci.band)}</p>
          <button type="button" class="hp-chip hp-chip--action" data-hal-cmd="Show HAL capability index">Scorecard</button>
          <button type="button" class="hp-chip hp-chip--action" data-hal-cmd="Run orchestrator triage">Orchestrator</button>`
      : "";
    const aoHtml = ao
      ? `<p class="hp-fw__allowed"><b>HAL 9000 ops:</b> ${ao.running && !ao.paused ? "running" : ao.paused ? "paused" : "stopped"}</p>`
      : "";
    const outboundList = outboundExecutors
      .map((item) => `<li class="hp-fw__row--active" data-hal-cmd="Explain staff consent for ${H.esc(item)}" role="button" tabindex="0"><span>${H.esc(item)}</span><b>LIVE</b></li>`)
      .join("");
    return `<section class="hp-card hp-card--session" data-panel="session" style="grid-area:session;">
      <div class="hp-session-grid">
        <div class="hp-session-col" data-panel="consent">
          ${H.cardHead("TRUST & CONSENT", "consent", "Staff consent policy", H.cardIconRaw("ui", "shield"))}
          <button type="button" class="hp-fw__active hp-fw__active--btn" data-hal-cmd="Explain staff consent policy">${H.uiIcon("check")} CONSENT</button>
          <ul class="hp-fw__list hp-fw__list--compact">${consentList}</ul>
          <p class="hp-fw__allowed"><b>Executors (consent):</b></p>
          <ul class="hp-fw__list hp-fw__list--compact">${outboundList}</ul>
          ${hciHtml}
          ${aoHtml}
          <p class="hp-fw__allowed"><b>Always local:</b> ${localAlways.length ? localAlways.slice(0, 5).map(H.esc).join(" · ") : "Open pages · Explain status"}</p>
          <button type="button" class="hp-chip hp-chip--action" data-hal-cmd="Show outbound audit log">Outbound audit</button>
          ${halInlineFirewallResult ? `<p class="hp-live-note">${H.esc(halInlineFirewallResult.text || "")}</p>` : ""}
        </div>
        <div class="hp-session-col" data-panel="status">
          ${H.cardHead("RECENT ACTIVITY", "status", "Session audit log", H.cardIconRaw("ui", "activity"))}
          <ul class="hp-log hp-log--compact">${activityHtml}</ul>
        </div>
        <div class="hp-session-col" data-panel="controls">
          ${H.cardHead("SYSTEM CONTROLS", "controls", "Readiness and diagnostics", H.cardIconRaw("ui", "check"))}
          <div class="hp-ctrl hp-ctrl--compact">
            <button type="button" class="hp-ctrl__btn" data-hal-cmd="Run readiness check"><span class="hp-ctrl__ico">${H.uiIcon("check")}</span><strong>Readiness</strong></button>
            <button type="button" class="hp-ctrl__btn" data-hal-cmd="Run operator smoke test"><span class="hp-ctrl__ico">${H.uiIcon("smoke")}</span><strong>Smoke</strong></button>
            <button type="button" class="hp-ctrl__btn" data-hal-cmd="Staff handoff summary"><span class="hp-ctrl__ico">${H.uiIcon("handoff")}</span><strong>Handoff</strong></button>
            <button type="button" class="hp-ctrl__btn" data-hal-about-me><span class="hp-ctrl__ico">${H.uiIcon("voice")}</span><strong>About me</strong></button>
            <button type="button" class="hp-ctrl__btn" data-hal-cmd="Monitor sidenotes"><span class="hp-ctrl__ico">${H.navIcon("sidenotes")}</span><strong>SideNotes</strong></button>
            <button type="button" class="hp-ctrl__btn" data-hal-drawer="status"><span class="hp-ctrl__ico">${H.uiIcon("audit")}</span><strong>Audit</strong></button>
          </div>
          <p class="hp-card__foot">Registry: ${H.esc(stats.readyCount)} ready · ${H.esc(stats.blockedCount)} blocked · Last receipt: ${H.esc(lastReceiptText)}</p>
          <details class="hp-details">
            <summary>Runtime diagnostics</summary>
            ${H.agentHealthHtml(ctx.halAgentHealth, ctx.halModels, ctx.halSideNotesInbox)}
            ${H.stressTestHtml(ctx.halStressTest)}
          </details>
        </div>
      </div>
    </section>`;
  }

  function renderSidenotes(ctx, H) {
    return H.sideNotesProgramCardHtml(ctx.halSideNotes, ctx.halSideNoteMonitor, ctx.halSideNotesInbox, ctx.sidenotesHubPath).replace(
      'style="grid-area:sidenotes;"',
      'style="grid-area:sidenotes;"',
    );
  }

  function render(ctx, H) {
    return [
      renderAskHal(ctx, H),
      renderStatusRail(ctx, H),
      renderWidgetMonitor(ctx, H),
      renderSurfaces(ctx, H),
      renderSidenotes(ctx, H),
      renderSession(ctx, H),
    ].join("");
  }

  function gridClassName() {
    const schema = schemaApi();
    return schema && schema.GRID ? schema.GRID.className : "hp-grid hp-grid--hal-102";
  }

  return { render, gridClassName, widgetRow, renderAskHal };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalPageCanvas;
}
if (typeof globalThis !== "undefined") {
  globalThis.HalPageCanvas = HalPageCanvas;
}
