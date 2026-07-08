/**
 * HAL hub client — workstations POST inbound messages to the financial app hub (port 8765).
 *
 * Configure hub URL via NR2_HAL_HUB_URL (Python env) or window.NR2_HAL_HUB_URL after boot.
 */
const HalHubClient = (function () {
  const DEFAULT_HUB = "http://127.0.0.1:8765";

  function getHalHubUrl() {
    if (typeof window !== "undefined" && window.NR2_HAL_HUB_URL) {
      return String(window.NR2_HAL_HUB_URL).replace(/\/+$/, "");
    }
    return DEFAULT_HUB;
  }

  function hubAuthHeaders(extra) {
    const headers = Object.assign({}, extra || {});
    const token =
      (typeof window !== "undefined" && window.NR2_HUB_TOKEN) ||
      (typeof window !== "undefined" && window.NR2_BUILD && window.NR2_BUILD.hubToken) ||
      "";
    if (token) headers["X-Hub-Token"] = String(token);
    return headers;
  }

  async function hubFetch(path, options) {
    const url = `${getHalHubUrl()}${path}`;
    const opts = Object.assign({ cache: "no-store", mode: "cors" }, options || {});
    opts.headers = hubAuthHeaders(opts.headers);
    const res = await fetch(url, opts);
    if (!res.ok) {
      const err = new Error(`hal-hub ${res.status} ${path}`);
      err.status = res.status;
      throw err;
    }
    return res.json();
  }

  async function submitToHalHub(partial) {
    const text = String((partial && partial.text) || "").trim();
    if (!text) throw new Error("empty message");
    const rawTargets = partial && partial.targets;
    const targets = Array.isArray(rawTargets)
      ? rawTargets.map((t) => String(t).trim()).filter(Boolean)
      : partial && partial.target
        ? String(partial.target)
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean)
        : ["all"];
    const payload = {
      from: (partial && partial.from) || "Workstation",
      targets: targets.length ? targets : ["all"],
      text,
      speak: partial && partial.speak != null ? !!partial.speak : true,
      role: (partial && partial.role) || "staff",
      type: (partial && partial.type) || "announce",
    };
    return hubFetch("/api/hal-hub/inbound", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }

  async function sendHalPopupMessage(text, targets, options) {
    const body = String(text || "").trim();
    if (!body) throw new Error("empty message");
    const list = Array.isArray(targets) ? targets.map((t) => String(t).trim()).filter(Boolean) : ["all"];
    return submitToHalHub({
      from: "HAL",
      role: "hal",
      targets: list.length ? list : ["all"],
      text: body,
      speak: !!(options && options.speak),
      type: (options && options.type) || "announce",
    });
  }

  async function processPending() {
    return hubFetch("/api/hal-hub/process", { method: "POST" });
  }

  async function getStatus() {
    return hubFetch("/api/hal-hub/status");
  }

  async function announce(text, options) {
    const opts = options || {};
    return hubFetch("/api/hal-hub/announce", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: String(text || ""),
        from: opts.from || opts.sender || "",
        broadcast: !!opts.broadcast,
      }),
    });
  }

  async function fetchOfficeChannel() {
    return hubFetch("/api/office-channel");
  }

  async function fetchStations() {
    return hubFetch("/api/hal-hub/stations");
  }

  async function sendHeartbeat(partial) {
    const station = String((partial && partial.station) || "").trim();
    if (!station) throw new Error("empty station");
    const payload = {
      station,
      host:
        (partial && partial.host) ||
        (typeof window !== "undefined" && window.location && window.location.hostname) ||
        "",
      port:
        partial && partial.port != null
          ? partial.port
          : typeof window !== "undefined" && window.location && window.location.port
            ? parseInt(window.location.port, 10)
            : 8766,
      source: (partial && partial.source) || "nr2-workstation",
      programId: (partial && partial.programId) || "nr2-workstation",
    };
    return hubFetch("/api/hal-hub/stations/heartbeat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }

  async function fetchLastBroadcast() {
    return hubFetch("/api/hub/last-broadcast", { method: "GET" });
  }

  async function notifyHubBroadcast(partial) {
    const payload = partial || {};
    return hubFetch("/api/hub/notify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        from: payload.from || payload.fromStation || "Workstation",
        target: payload.target || "all",
        channel: payload.channel || "office",
        at: payload.at,
      }),
    });
  }

  async function pushMorningBriefingToWorkstation(briefing) {
    if (!briefing || !briefing.sentence) return null;
    const domains = Array.isArray(briefing.domains) ? briefing.domains.slice(0, 4) : [];
    const text = `[HAL Morning Briefing] ${String(briefing.sentence).slice(0, 280)}${
      domains.length ? ` (${domains.join(" + ")})` : ""
    }`;
    return submitToHalHub({
      from: "HAL",
      role: "hal",
      targets: ["workstation", "sidenotes"],
      text,
      speak: false,
      type: "briefing",
    });
  }

  return {
    getHalHubUrl,
    submitToHalHub,
    sendHalPopupMessage,
    processPending,
    getStatus,
    announce,
    fetchOfficeChannel,
    fetchStations,
    sendHeartbeat,
    notifyHubBroadcast,
    fetchLastBroadcast,
    pushMorningBriefingToWorkstation,
  };
})();

if (typeof globalThis !== "undefined") globalThis.HalHubClient = HalHubClient;
if (typeof module !== "undefined" && module.exports) {
  module.exports = HalHubClient;
}
