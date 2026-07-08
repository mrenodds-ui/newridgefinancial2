/**
 * Moonshot P2 #9 — When NR2 Workstation (8766) is offline, 8765 browser tabs
 * elect a localStorage leader and relay office-broadcast metadata (no message text).
 */
const SideNotesOfficeFallback = (function () {
  const LEADER_KEY = "nr2:sidenotes:office-leader";
  const BROADCAST_KEY = "nr2:sidenotes:office-broadcast-fallback";
  const LEADER_TTL_MS = 15000;
  const tabId = "tab-" + Math.random().toString(36).slice(2, 10);

  function readLeader() {
    try {
      const raw = localStorage.getItem(LEADER_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }

  function writeLeader(record) {
    try {
      localStorage.setItem(LEADER_KEY, JSON.stringify(record));
    } catch {
      /* quota / private mode */
    }
  }

  function tryBecomeLeader() {
    const now = Date.now();
    const record = readLeader();
    if (!record || now - Number(record.at || 0) > LEADER_TTL_MS) {
      writeLeader({ tabId, at: now });
      return readLeader()?.tabId === tabId;
    }
    if (record.tabId === tabId) {
      writeLeader({ tabId, at: now });
      return true;
    }
    return false;
  }

  function readBroadcastFallback() {
    try {
      const raw = localStorage.getItem(BROADCAST_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }

  function recordBroadcastFallback(payload) {
    if (!tryBecomeLeader()) return false;
    const entry = Object.assign({}, payload || {}, { at: new Date().toISOString(), localOnly: true });
    try {
      localStorage.setItem(BROADCAST_KEY, JSON.stringify(entry));
    } catch {
      return false;
    }
    if (typeof window !== "undefined") window.__NR2_HUB_BROADCAST = entry;
    return true;
  }

  async function workstationReachable() {
    try {
      const headers = {};
      if (typeof window !== "undefined" && window.NR2_HUB_TOKEN) {
        headers["X-Hub-Token"] = String(window.NR2_HUB_TOKEN);
      }
      const res = await fetch("/api/hub/status", { cache: "no-store", headers });
      if (!res.ok) return false;
      const data = await res.json();
      return !!(data && data.workstationReachable);
    } catch {
      return false;
    }
  }

  function applyFallbackBroadcast() {
    const fb = readBroadcastFallback();
    if (!fb || !fb.at) return null;
    if (typeof window !== "undefined") window.__NR2_HUB_BROADCAST = fb;
    return fb;
  }

  function install() {
    if (typeof window === "undefined" || window.NR2_WORKSTATION_ONLY) return;
    tryBecomeLeader();
    window.setInterval(() => {
      tryBecomeLeader();
    }, LEADER_TTL_MS / 2);
    window.addEventListener("storage", (event) => {
      if (!event || event.key !== BROADCAST_KEY || !event.newValue) return;
      try {
        const fb = JSON.parse(event.newValue);
        window.__NR2_HUB_BROADCAST = fb;
        if (typeof patchHubBroadcastBadgeDom === "function") patchHubBroadcastBadgeDom();
      } catch {
        /* ignore */
      }
    });
  }

  return {
    install,
    tryBecomeLeader,
    readBroadcastFallback,
    recordBroadcastFallback,
    workstationReachable,
    applyFallbackBroadcast,
  };
})();

if (typeof globalThis !== "undefined") globalThis.SideNotesOfficeFallback = SideNotesOfficeFallback;
