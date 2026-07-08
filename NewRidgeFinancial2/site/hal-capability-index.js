/**
 * HAL Capability Index (HCI) — 0–10000 ascension scale (hal-10000).
 * 0–250: office-manager core · 251–10000: autonomous + director transcendent tier.
 */
const HalCapabilityIndex = (function () {
  const MAX_SCORE = 10000;
  const OFFICE_MAX = 250;

  function buildVersion(ctx) {
    const snap = ctx && ctx.halData && ctx.halData.build;
    const fromSnap = snap && (snap.schemaVersion || snap.assetVersion);
    if (fromSnap) return String(fromSnap);
    if (typeof window !== "undefined" && window.NR2_BUILD) {
      return String(window.NR2_BUILD.schemaVersion || window.NR2_BUILD.assetVersion || "");
    }
    return "";
  }

  function widgetRatio(ctx) {
    const feed = ctx && ctx.halWidgetFeed;
    const widgets = (feed && feed.widgets) || {};
    const order =
      typeof HalSkills !== "undefined" && HalSkills.WIDGET_ORDER ? HalSkills.WIDGET_ORDER : Object.keys(widgets);
    if (!order.length) return 0;
    const ready = order.filter((key) => {
      const w = widgets[key];
      const status = w && String(w.status || "").toUpperCase();
      return status === "SUCCESS" || status === "READY";
    }).length;
    return ready / order.length;
  }

  function computeOfficeCore(ctx, halModels) {
    let platform = 0;
    const db =
      typeof DesktopBridge !== "undefined"
        ? DesktopBridge
        : typeof window !== "undefined"
          ? window.DesktopBridge
          : null;
    if (db && db.hasRuntimeAccess && db.hasRuntimeAccess()) platform += 15;
    else if (db && db.hasDesktopApi && db.hasDesktopApi()) platform += 12;
    else platform += 6;
    const verMatch = /^hal-(\d+)$/.exec(buildVersion(ctx));
    if (verMatch) {
      const n = Number(verMatch[1] || 0);
      if (n >= 10000) platform += 20;
      else if (n >= 9000) platform += 15;
      else if (n >= 250) platform += 12;
      else if (n >= 200) platform += 8;
    }
    if (typeof HalAgent !== "undefined") platform += 3;
    if (typeof HalAgentLoop !== "undefined") platform += 2;

    const cfg = (halModels && halModels.config) || {};
    const prog = cfg.agentProgramming || {};
    let agent = 0;
    if (prog.agentLoop) agent += 8;
    if (prog.agentAutoTools) agent += 6;
    if (prog.autoEscalate) agent += 6;
    if (cfg.preferReasoning) agent += 5;
    const cloud = cfg.cloudReasoning || {};
    if (cloud.enabled || cloud.autoEnableWhenKeySet) agent += 5;
    agent = Math.min(40, agent);

    let outbound = 0;
    if (db && typeof db.sendEmailWithConsent === "function") outbound += 6;
    if (db && typeof db.exportPostingQueueIifWithConsent === "function") outbound += 6;
    if (db && typeof db.buildClaimPacketWithConsent === "function") outbound += 6;
    if (db && typeof db.exportNarrativePortalPrepWithConsent === "function") outbound += 5;
    if (db && typeof db.postQboJournalWithConsent === "function") outbound += 8;
    if (db && typeof db.buildPayerPortalRpaWithConsent === "function") outbound += 8;
    if (db && typeof db.queueSoftdentWritebackWithConsent === "function") outbound += 6;
    if (typeof HalOutbound !== "undefined") outbound += 3;
    if (typeof HalConsent !== "undefined") outbound += 2;
    outbound = Math.min(50, outbound);

    const diag = ctx && ctx.importDiagnostics;
    let data = 8;
    if (diag && Array.isArray(diag.datasets)) {
      const automated = diag.datasets.filter((d) => d.automated !== false);
      if (automated.length) {
        const ok = automated.filter((d) => d.status === "ok" || d.status === "current").length;
        data = Math.round(25 * (ok / automated.length));
      }
    }

    let proactive = 0;
    if (typeof HalProactive !== "undefined") {
      if (HalProactive.runCycle) proactive += 10;
      if (HalProactive.startBriefingScheduler) proactive += 8;
    }
    if (typeof ProgramStrength !== "undefined" && ProgramStrength.runAutonomousHealLoop) proactive += 7;
    proactive = Math.min(25, proactive);

    let voice = 0;
    if (typeof HalVoice !== "undefined") {
      voice += 10;
      if (HalVoice.checkNeuralTts) voice += 5;
      if (HalVoice.speakHalBriefing || HalVoice.speakHal9000Briefing) voice += 5;
    }
    voice = Math.min(20, voice);

    const consent = typeof HalConsent !== "undefined" ? 10 : 0;
    const widgets = Math.round(45 * widgetRatio(ctx));

    const score = Math.min(
      OFFICE_MAX,
      platform + widgets + agent + outbound + data + proactive + voice + consent,
    );
    return {
      score,
      max: OFFICE_MAX,
      parts: { platform, widgets, agent, outbound, data, proactive, voice, consent },
    };
  }

  function computeAscension(ctx, halModels) {
    let autonomous = 0;
    if (typeof HalAutonomousOps !== "undefined") {
      if (HalAutonomousOps.start) autonomous += 400;
      if (HalAutonomousOps.runTick) autonomous += 350;
      const st = HalAutonomousOps.status && HalAutonomousOps.status();
      if (st && st.running && !st.paused) autonomous += 500;
    }
    autonomous = Math.min(1250, autonomous);

    let orchestrator = 0;
    if (typeof HalOrchestrator !== "undefined") {
      orchestrator += 400;
      const triage = HalOrchestrator.getLastTriage && HalOrchestrator.getLastTriage();
      if (triage && triage.agentCount >= 5) orchestrator += 450;
      if (triage && triage.totalItems >= 0) orchestrator += 400;
    }
    orchestrator = Math.min(1250, orchestrator);

    let external = 0;
    const db =
      typeof DesktopBridge !== "undefined"
        ? DesktopBridge
        : typeof window !== "undefined"
          ? window.DesktopBridge
          : null;
    if (db) {
      if (typeof db.postQboJournalWithConsent === "function") external += 350;
      if (typeof db.buildPayerPortalRpaWithConsent === "function") external += 400;
      if (typeof db.queueSoftdentWritebackWithConsent === "function") external += 350;
      if (typeof db.buildClaimPacketWithConsent === "function") external += 300;
      if (typeof db.sendEmailWithConsent === "function") external += 300;
      if (typeof db.exportPostingQueueIifWithConsent === "function") external += 300;
    }
    external = Math.min(2000, external);

    let governance = 0;
    if (typeof HalConsent !== "undefined") {
      governance += 400;
      if (HalConsent.getRolePolicy || HalConsent.outboundKind) governance += 350;
    }
    if (db && typeof db.listOutboundAudit === "function") governance += 500;
    governance = Math.min(1250, governance);

    let monitoring = 0;
    if (typeof HalProactive !== "undefined" && HalProactive.startBriefingScheduler) monitoring += 450;
    if (typeof ProgramStrength !== "undefined") monitoring += 400;
    if (typeof HalAutonomousOps !== "undefined" && HalAutonomousOps.status) monitoring += 400;
    monitoring = Math.min(1250, monitoring);

    let voice9000 = 0;
    const auto = (halModels && halModels.config && halModels.config.autonomousOps) || {};
    const chat9000 = (halModels && halModels.config && halModels.config.chat9000) || {};
    if (auto.hal9000Voice) voice9000 += 300;
    if (chat9000.enabled !== false && chat9000.hal9000Persona !== false) voice9000 += 450;
    if (typeof HalVoice !== "undefined" && HalVoice.speakHalBriefing) voice9000 += 350;
    voice9000 = Math.min(750, voice9000);

    let integration = 0;
    const verMatch = /^hal-(\d+)$/.exec(buildVersion(ctx));
    if (verMatch && Number(verMatch[1] || 0) >= 9000) integration += 400;
    if (typeof HalOrchestrator !== "undefined") integration += 350;
    if (typeof HalChat9000 !== "undefined" && HalChat9000.isEnabled(halModels)) integration += 400;
    if (typeof HalEmployee !== "undefined" && HalEmployee.getTargetLevel(halModels) >= 5) integration += 200;
    integration = Math.min(750, integration);

    let employee = 0;
    if (typeof HalEmployee !== "undefined") {
      const lvl = HalEmployee.getTargetLevel(halModels);
      employee += Math.min(250, lvl * 50);
    }
    if (typeof HalEmployeeRunner !== "undefined") employee += 50;
    employee = Math.min(350, employee);

    let director = 0;
    if (typeof HalAscension10000 !== "undefined" && HalAscension10000.isEnabled(halModels)) director += 350;
    if (typeof HalDirector !== "undefined") {
      director += 200;
      if (HalDirector.isRunning && HalDirector.isRunning()) director += 150;
    }
    if (typeof HalChat10000 !== "undefined" && HalChat10000.isEnabled(halModels)) director += 200;
    director = Math.min(700, director);

    const bonus =
      typeof HalAscension10000 !== "undefined" && HalAscension10000.ascensionScoreBonus
        ? HalAscension10000.ascensionScoreBonus(halModels, ctx)
        : 0;

    const score = autonomous + orchestrator + external + governance + monitoring + voice9000 + integration + employee + director + bonus;
    return {
      score,
      max: MAX_SCORE - OFFICE_MAX,
      parts: { autonomous, orchestrator, external, governance, monitoring, voice9000, integration, employee, director, bonus },
    };
  }

  function bandFor(score) {
    if (score >= 9500) return "hal-10000";
    if (score >= 8500) return "hal-9000";
    if (score >= 7000) return "ascended";
    if (score >= 5000) return "autonomous";
    if (score >= 3000) return "advanced";
    if (score >= 2000) return "strong";
    if (score >= 1000) return "capable";
    if (score >= 500) return "building";
    return "developing";
  }

  function compute(ctx, halModels) {
    const office = computeOfficeCore(ctx, halModels);
    const ascension = computeAscension(ctx, halModels);
    const total = Math.min(MAX_SCORE, office.score + ascension.score);
    const pct = Math.round((total / MAX_SCORE) * 100);
    const band = bandFor(total);
    const dimensions = [
      { id: "office", label: "Office manager core", max: OFFICE_MAX, score: office.score },
      { id: "autonomous", label: "Autonomous ops daemon", max: 1250, score: ascension.parts.autonomous },
      { id: "orchestrator", label: "Multi-agent orchestrator", max: 1250, score: ascension.parts.orchestrator },
      { id: "external", label: "External execution readiness", max: 2000, score: ascension.parts.external },
      { id: "governance", label: "Governance & audit", max: 1250, score: ascension.parts.governance },
      { id: "monitoring", label: "Always-on monitoring", max: 1250, score: ascension.parts.monitoring },
      { id: "voice9000", label: "HAL 9000 presence", max: 750, score: ascension.parts.voice9000 },
      { id: "integration", label: "Integration depth", max: 750, score: ascension.parts.integration },
      { id: "employee", label: "Employee tier (1–7)", max: 350, score: ascension.parts.employee || 0 },
      { id: "director", label: "Director / transcendent", max: 700, score: (ascension.parts.director || 0) + (ascension.parts.bonus || 0) },
    ];
    const empLevel = typeof HalEmployee !== "undefined" ? HalEmployee.getTargetLevel(halModels) : 0;
    const headline =
      band === "hal-10000"
        ? "HAL 10000 transcendent — practice director loop, levels 6–7 employee autonomy, executive digest, and standing consent at peak. Staff confirm payer submit and clinical charting."
        : band === "hal-9000" && empLevel >= 7
          ? "HAL 9000 + Level 7 executive partner — autonomous ops and director delegation active."
        : band === "hal-9000" && empLevel >= 5
        ? "HAL 9000 + Level 5 employee — autonomous ops, standing consent writeback, and full audit. Staff confirm payer submit and clinical actions."
        : band === "hal-9000"
        ? "HAL 9000 tier — autonomous ops, multi-agent orchestrator, and consent-gated external executors are live. Staff confirm irreversible payer and clinical actions."
        : band === "ascended"
          ? "HAL is ascended — autonomous loop and orchestrator active; configure QBO/SMTP/SoftDent writeback for peak tier."
          : total >= 2500
            ? "HAL is in autonomous mode — always-on heal and triage running; wire remaining integrations to climb toward 9000."
            : total >= 1000
              ? "HAL is advanced — office core solid; enable hal-9000 autonomous ops and outbound env vars."
              : "HAL is building — run Start Program on desktop, refresh imports, ask for capability index.";
    return {
      score: total,
      max: MAX_SCORE,
      officeScore: office.score,
      ascensionScore: ascension.score,
      percent: pct,
      band,
      tier: band === "hal-10000" ? 10000 : band === "hal-9000" ? 9000 : total,
      build: buildVersion(ctx),
      dimensions,
      headline,
    };
  }

  function formatReport(report) {
    if (!report) return "Capability index unavailable.";
    const lines = [
      `HAL Capability Index: ${report.score}/${report.max} (${report.percent}%) — ${report.band}.`,
      `Office core: ${report.officeScore}/250 · Ascension: ${report.ascensionScore}/${report.max - 250}.`,
      report.headline,
      "",
      "Dimensions:",
    ];
    (report.dimensions || []).forEach((d) => {
      lines.push(`- ${d.label}: ${d.score}/${d.max}`);
    });
    if (report.score < report.max) {
      lines.push("");
      lines.push(
        "Next toward 10000: NR2_QBO_* · NR2_SMTP_* · NR2_SOFTDENT_* · director loop on desktop · employee level 7 · keep autonomous ops running.",
      );
    }
    return lines.join("\n");
  }

  return {
    MAX_SCORE,
    OFFICE_MAX,
    compute,
    formatReport,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalCapabilityIndex;
}
if (typeof globalThis !== "undefined") {
  globalThis.HalCapabilityIndex = HalCapabilityIndex;
}
if (typeof window !== "undefined") {
  window.HalCapabilityIndex = HalCapabilityIndex;
}
