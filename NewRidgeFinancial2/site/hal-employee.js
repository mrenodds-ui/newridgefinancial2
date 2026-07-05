/**
 * HAL employee tiers (levels 1–7) — profile, standing consent, work log.
 */
const HalEmployee = (function () {
  const STORAGE_POLICIES = "halEmployeeStandingPolicies";
  const STORAGE_TARGET = "halEmployeeTargetLevel";
  const MAX_LEVEL = 7;

  const LEVELS = {
    1: {
      id: 1,
      name: "Digital clerk",
      summary: "Read imports, draft work, briefings, consent-gated prep.",
    },
    2: {
      id: 2,
      name: "Bookkeeping assistant",
      summary: "QBO/IIF posting under standing consent, employee work log.",
    },
    3: {
      id: 3,
      name: "Billing / ops coordinator",
      summary: "Claim packets, payer email, denied-claim task loops, role matrix.",
    },
    4: {
      id: 4,
      name: "Back-office employee",
      summary: "SoftDent writeback execution, scheduled posting, cross-system tasks.",
    },
    5: {
      id: 5,
      name: "Full peer employee",
      summary: "Broad standing consent with audit — HAL owns routine back-office work.",
    },
    6: {
      id: 6,
      name: "Practice director",
      summary: "Predictive ops, executive digest, director delegation to domain agents.",
    },
    7: {
      id: 7,
      name: "Executive partner",
      summary: "Maximum standing consent — auto payer prep, continuous shift, director loop.",
    },
  };

  const DEFAULT_POLICIES = {
    1: { email: false, "qb-export": false, "qbo-post": false, "qbo-post-max-usd": 0, "claim-submit": false, "payer-portal-rpa": false, "softdent-writeback": false, "narrative-portal": false },
    2: { email: false, "qb-export": true, "qbo-post": true, "qbo-post-max-usd": 5000, "claim-submit": false, "payer-portal-rpa": false, "softdent-writeback": false, "narrative-portal": false },
    3: { email: true, "qb-export": true, "qbo-post": true, "qbo-post-max-usd": 10000, "claim-submit": true, "payer-portal-rpa": true, "softdent-writeback": false, "narrative-portal": true },
    4: { email: true, "qb-export": true, "qbo-post": true, "qbo-post-max-usd": 25000, "claim-submit": true, "payer-portal-rpa": true, "softdent-writeback": true, "narrative-portal": true, "scheduled-posting": true, "execute-softdent-queue": true },
    5: { email: true, "qb-export": true, "qbo-post": true, "qbo-post-max-usd": 100000, "claim-submit": true, "payer-portal-rpa": true, "softdent-writeback": true, "narrative-portal": true, "scheduled-posting": true, "execute-softdent-queue": true, "cross-system-sync": true, "auto-task-ownership": true },
    6: { email: true, "qb-export": true, "qbo-post": true, "qbo-post-max-usd": 250000, "claim-submit": true, "payer-portal-rpa": true, "softdent-writeback": true, "narrative-portal": true, "scheduled-posting": true, "execute-softdent-queue": true, "cross-system-sync": true, "auto-task-ownership": true, "director-delegation": true, "predictive-alerts": true, "executive-briefing": true },
    7: { email: true, "qb-export": true, "qbo-post": true, "qbo-post-max-usd": 0, "claim-submit": true, "payer-portal-rpa": true, "softdent-writeback": true, "narrative-portal": true, "scheduled-posting": true, "execute-softdent-queue": true, "cross-system-sync": true, "auto-task-ownership": true, "director-delegation": true, "predictive-alerts": true, "executive-briefing": true, "continuous-shift": true, "executive-partner-rpa": true },
  };

  function bridge() {
    if (typeof DesktopBridge !== "undefined") return DesktopBridge;
    if (typeof window !== "undefined" && window.DesktopBridge) return window.DesktopBridge;
    return null;
  }

  function config(halModels) {
    const cfg = (halModels && halModels.config && halModels.config.employee) || {};
    return Object.assign({ enabled: true, targetLevel: MAX_LEVEL, profile: { name: "HAL", title: "Office Operations Specialist" } }, cfg);
  }

  function ensureTargetLevel(halModels, level) {
    const cfg = config(halModels);
    if (cfg.enabled === false) return getTargetLevel(halModels);
    const want = Math.max(1, Math.min(MAX_LEVEL, Number(level != null ? level : cfg.targetLevel) || MAX_LEVEL));
    return setTargetLevel(want);
  }

  function getTargetLevel(halModels) {
    const cfg = config(halModels);
    if (typeof localStorage !== "undefined") {
      const saved = Number(localStorage.getItem(STORAGE_TARGET));
      if (saved >= 1 && saved <= MAX_LEVEL) return saved;
    }
    return Math.max(1, Math.min(MAX_LEVEL, Number(cfg.targetLevel) || MAX_LEVEL));
  }

  function setTargetLevel(level) {
    const n = Math.max(1, Math.min(MAX_LEVEL, Number(level) || 1));
    if (typeof localStorage !== "undefined") localStorage.setItem(STORAGE_TARGET, String(n));
    return n;
  }

  function policiesForLevel(level) {
    const n = Math.max(1, Math.min(MAX_LEVEL, Number(level) || 1));
    return Object.assign({}, DEFAULT_POLICIES[n] || DEFAULT_POLICIES[1]);
  }

  async function fetchRemoteStatus(halModels) {
    const db = bridge();
    const target = getTargetLevel(halModels);
    if (db && typeof db.employeeStatus === "function") {
      try {
        return await db.employeeStatus(target);
      } catch {
        /* fall through */
      }
    }
    return null;
  }

  async function computeAchievedLevel(ctx, halModels) {
    const target = getTargetLevel(halModels);
    const remote = await fetchRemoteStatus(halModels);
    if (remote && remote.achievedLevel) return Math.min(target, remote.achievedLevel);
    let achieved = 1;
    const db = bridge();
    if (db && (db.hasRuntimeAccess?.() || db.hasDesktopApi?.() || db.hasLoopbackApi?.())) achieved = Math.max(achieved, 1);
    if (typeof HalOutbound !== "undefined") achieved = Math.max(achieved, 2);
    if (typeof HalOrchestrator !== "undefined" && typeof OfficeTaskStore !== "undefined") achieved = Math.max(achieved, 3);
    if (db && typeof db.queueSoftdentWritebackWithConsent === "function") {
      try {
        const sd = db.softdentWritebackStatus && (await db.softdentWritebackStatus());
        if (sd && sd.configured) achieved = Math.max(achieved, 4);
      } catch {
        /* optional */
      }
    }
    if (target >= 5 && typeof HalAutonomousOps !== "undefined") achieved = Math.max(achieved, 5);
    if (target >= 6 && typeof HalDirector !== "undefined") achieved = Math.max(achieved, 6);
    if (target >= 7 && typeof HalAscension10000 !== "undefined" && HalAscension10000.isEnabled(halModels)) {
      achieved = Math.max(achieved, 7);
    } else if (target >= 7 && typeof HalDirector !== "undefined" && typeof HalEmployeeRunner !== "undefined") {
      achieved = Math.max(achieved, 6);
    }
    return Math.min(target, achieved);
  }

  async function status(ctx, halModels) {
    const target = getTargetLevel(halModels);
    const achieved = await computeAchievedLevel(ctx, halModels);
    const remote = await fetchRemoteStatus(halModels);
    const pol = policiesForLevel(target);
    const cfg = config(halModels);
    return {
      ok: true,
      name: (cfg.profile && cfg.profile.name) || "HAL",
      title: (cfg.profile && cfg.profile.title) || "Office Operations Specialist",
      targetLevel: target,
      targetLevelName: LEVELS[target].name,
      achievedLevel: achieved,
      achievedLevelName: LEVELS[achieved].name,
      standingPolicies: (remote && remote.standingPolicies) || pol,
      levels: LEVELS,
      remote,
    };
  }

  function standingAllows(kind, halModels) {
    const target = getTargetLevel(halModels);
    const pol = policiesForLevel(target);
    const key = String(kind || "").toLowerCase();
    if (Object.prototype.hasOwnProperty.call(pol, key)) return Boolean(pol[key]);
    return false;
  }

  function standingConsentText(halModels) {
    const target = getTargetLevel(halModels);
    return `Standing policy employee level ${target}`;
  }

  async function fetchWorkLog(limit) {
    const db = bridge();
    if (db && typeof db.listEmployeeWorkLog === "function") {
      return db.listEmployeeWorkLog(Number(limit || 15));
    }
    return { ok: true, items: [], count: 0 };
  }

  async function recordWork(action, summary, halModels, result) {
    const db = bridge();
    const target = getTargetLevel(halModels);
    if (db && typeof db.appendEmployeeWorkLog === "function") {
      return db.appendEmployeeWorkLog({ action, summary, level: target, actor: "HAL", result: result || {} });
    }
    return { ok: false };
  }

  function formatStatus(st) {
    const s = st || {};
    const lines = [
      `HAL employee: Level ${s.achievedLevel || 1}/5 — ${s.achievedLevelName || "Digital clerk"}.`,
      `Target tier: ${s.targetLevel || 7} (${s.targetLevelName || ""}).`,
      `${s.name || "HAL"} · ${s.title || "Office Operations Specialist"}.`,
      "",
      "Employee tiers:",
    ];
    Object.keys(LEVELS).forEach((k) => {
      const lv = LEVELS[k];
      const mark = Number(k) <= (s.achievedLevel || 1) ? "✓" : Number(k) === (s.targetLevel || 7) ? "→" : "·";
      lines.push(`${mark} ${k}. ${lv.name} — ${lv.summary}`);
    });
    if (s.targetLevel >= 6) {
      lines.push("");
      lines.push("Director mode: predictive alerts and executive digest active at level 6+.");
    }
    if (s.standingPolicies) {
      lines.push("");
      lines.push("Standing consent (target level):");
      Object.keys(s.standingPolicies).forEach((key) => {
        if (key.startsWith("_")) return;
        lines.push(`- ${key}: ${s.standingPolicies[key]}`);
      });
    }
    return lines.join("\n");
  }

  async function formatWorkLog(limit) {
    const log = await fetchWorkLog(limit || 12);
    const items = (log && log.items) || [];
    if (!items.length) {
      return "HAL work log is empty. Standing-consent shift actions and outbound work appear here after HAL runs a shift.";
    }
    const lines = ["HAL work log (employee timesheet):"];
    items.forEach((entry) => {
      const ok = entry.result && entry.result.ok === false ? "FAIL" : "OK";
      lines.push(`- [${ok}] ${entry.at || ""} · L${entry.level || "?"} · ${entry.action || "work"} — ${entry.summary || ""}`);
    });
    return lines.join("\n");
  }

  return {
    MAX_LEVEL,
    LEVELS,
    config,
    ensureTargetLevel,
    getTargetLevel,
    setTargetLevel,
    policiesForLevel,
    status,
    standingAllows,
    standingConsentText,
    fetchWorkLog,
    recordWork,
    formatStatus,
    formatWorkLog,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = HalEmployee;
}
if (typeof globalThis !== "undefined") {
  globalThis.HalEmployee = HalEmployee;
}
if (typeof window !== "undefined") {
  window.HalEmployee = HalEmployee;
}
