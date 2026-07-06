/**
 * NR2 office channel — LAN-shared workflow feed (replaces SideNotesIM for in-app messaging).
 */
const OfficeHub = (function () {
  const SCHEMA = "nr2-office-channel-v1";
  const MAX_MESSAGES = 200;

  function stationLabel() {
    if (typeof globalThis !== "undefined" && globalThis._nr2WorkstationStation) {
      return String(globalThis._nr2WorkstationStation);
    }
    return "Workstation";
  }

  async function loopback(path, options) {
    if (typeof DesktopBridge === "undefined" || !DesktopBridge.hasLoopbackApi || !DesktopBridge.hasLoopbackApi()) {
      return null;
    }
    const port = (typeof window !== "undefined" && window.location && window.location.port) || "8765";
    const host = (typeof window !== "undefined" && window.location && window.location.hostname) || "127.0.0.1";
    const protocol = (typeof window !== "undefined" && window.location && window.location.protocol) || "http:";
    const url = `${protocol}//${host}:${port}${path}`;
    const res = await fetch(url, Object.assign({ cache: "no-store" }, options || {}));
    if (!res.ok) throw new Error(`office-channel ${res.status}`);
    return res.json();
  }

  async function fetchChannel() {
    const useHub =
      (typeof globalThis !== "undefined" && globalThis.NR2_WORKSTATION_ONLY) ||
      (typeof globalThis !== "undefined" && globalThis.NR2_HAL_HUB_URL);
    if (useHub && typeof HalHubClient !== "undefined" && HalHubClient.fetchOfficeChannel) {
      try {
        const live = await HalHubClient.fetchOfficeChannel();
        if (live && Array.isArray(live.messages)) return live;
      } catch (_) {}
    }
    try {
      const live = await loopback("/api/office-channel");
      if (live && Array.isArray(live.messages)) return live;
    } catch (_) {}
    try {
      if (typeof DesktopBridge !== "undefined" && DesktopBridge.readDataFile) {
        const data = await DesktopBridge.readDataFile("office-channel.json");
        if (data && Array.isArray(data.messages)) return data;
      }
    } catch (_) {}
    return { schema: SCHEMA, messages: [], station: stationLabel() };
  }

  function normalizeTargets(partial) {
    const raw = partial && partial.targets;
    if (Array.isArray(raw) && raw.length) {
      const list = raw.map((s) => String(s).trim()).filter(Boolean);
      const all = list.some((t) => /^(all|everyone)$/i.test(t));
      if (all) return { target: "all", targets: ["all"] };
      return { target: list.join(", "), targets: list };
    }
    const single = String((partial && partial.target) || "all").trim();
    if (!single || /^(all|everyone)$/i.test(single)) return { target: "all", targets: ["all"] };
    if (single.includes(",")) {
      const list = single.split(",").map((s) => s.trim()).filter(Boolean);
      return { target: single, targets: list.length ? list : ["all"] };
    }
    return { target: single, targets: [single] };
  }

  function messageTargetsForStation(message, stationLabel) {
    const station = String(stationLabel || "").trim().toLowerCase();
    const { targets } = normalizeTargets(message || {});
    if (targets.some((t) => /^(all|everyone)$/i.test(String(t)))) return true;
    if (!station) return true;
    return targets.some((t) => String(t).trim().toLowerCase() === station);
  }

  async function appendMessage(partial) {
    const text = String((partial && partial.text) || "").trim();
    if (!text) throw new Error("empty message");
    const role = String((partial && partial.role) || "staff").toLowerCase();
    const routing = normalizeTargets(partial || {});
    const payload = {
      from: (partial && partial.from) || (role === "hal" ? "HAL" : stationLabel()),
      role: role === "hal" ? "hal" : "staff",
      text,
      speak: partial && partial.speak != null ? !!partial.speak : role === "hal" || partial.type === "announce",
      target: routing.target,
      targets: routing.targets,
      type: (partial && partial.type) || (role === "hal" ? "workflow" : "announce"),
    };
    try {
      const res = await loopback("/api/office-channel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: payload }),
      });
      if (res && res.message) return res;
    } catch (_) {}
    const local = (await fetchChannel()) || { schema: SCHEMA, messages: [] };
    const entry = Object.assign(
      {
        id: "local-" + Date.now() + "-" + Math.random().toString(36).slice(2, 8),
        at: new Date().toISOString(),
      },
      payload,
    );
    local.messages = (local.messages || []).concat(entry).slice(-MAX_MESSAGES);
    if (typeof DesktopBridge !== "undefined" && DesktopBridge.storageSet) {
      await DesktopBridge.storageSet("officeChannelFallback", local);
    }
    return { ok: true, message: entry, channel: local, localOnly: true };
  }

  async function loadFallback() {
    if (typeof DesktopBridge === "undefined" || !DesktopBridge.storageGet) return null;
    return DesktopBridge.storageGet("officeChannelFallback");
  }

  function mergeChannels(primary, fallback) {
    const a = (primary && primary.messages) || [];
    const b = (fallback && fallback.messages) || [];
    const byId = new Map();
    a.concat(b).forEach((m) => {
      if (m && m.id) byId.set(m.id, m);
    });
    return {
      schema: SCHEMA,
      messages: Array.from(byId.values()).sort((x, y) => String(x.at || "").localeCompare(String(y.at || ""))),
      updatedAt: (primary && primary.updatedAt) || (fallback && fallback.updatedAt) || null,
    };
  }

  return {
    SCHEMA,
    stationLabel,
    fetchChannel,
    appendMessage,
    loadFallback,
    mergeChannels,
    normalizeTargets,
    messageTargetsForStation,
  };
})();

if (typeof globalThis !== "undefined") globalThis.OfficeHub = OfficeHub;
