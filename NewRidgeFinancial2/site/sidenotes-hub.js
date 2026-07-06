/**
 * SideNotesIM bridge — read/send via local SideNotes history.vdb (workstation app).
 */
const SideNotesHub = (function () {
  async function loopback(path, options) {
    if (typeof DesktopBridge === "undefined" || !DesktopBridge.hasLoopbackApi || !DesktopBridge.hasLoopbackApi()) {
      return null;
    }
    const port = (typeof window !== "undefined" && window.location && window.location.port) || "8766";
    const host = (typeof window !== "undefined" && window.location && window.location.hostname) || "127.0.0.1";
    const protocol = (typeof window !== "undefined" && window.location && window.location.protocol) || "http:";
    const url = `${protocol}//${host}:${port}${path}`;
    const res = await fetch(url, Object.assign({ cache: "no-store" }, options || {}));
    if (!res.ok) throw new Error(`sidenotes ${res.status}`);
    return res.json();
  }

  async function status() {
    try {
      return await loopback("/api/sidenotes/status");
    } catch (_) {
      return { ok: false };
    }
  }

  async function fetchMessages(station) {
    try {
      const q = new URLSearchParams();
      if (station) q.set("station", String(station));
      q.set("limit", "48");
      const live = await loopback(`/api/sidenotes/messages?${q.toString()}`);
      if (live && Array.isArray(live.messages)) return live;
    } catch (_) {}
    return { ok: false, messages: [] };
  }

  function primaryTarget(targets) {
    if (!Array.isArray(targets) || !targets.length) return "Everyone";
    if (targets.some((t) => /^(all|everyone)$/i.test(String(t)))) return "Everyone";
    if (targets.length === 1) return targets[0];
    return targets.join(", ");
  }

  async function sendMessage(partial) {
    const text = String((partial && partial.text) || "").trim();
    if (!text) throw new Error("empty message");
    const from = String((partial && partial.from) || "").trim();
    const targets = partial && partial.targets;
    let to = "Everyone";
    if (Array.isArray(targets) && targets.length) {
      to = primaryTarget(targets);
    } else if (partial && partial.target) {
      to = String(partial.target);
    }
    const res = await loopback("/api/sidenotes/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ from, to, text }),
    });
    if (!res || !res.ok) {
      const err = (res && res.error) || "SideNotes send failed";
      throw new Error(err);
    }
    return res;
  }

  function messageTargetsForStation(message, stationLabel) {
    const station = String(stationLabel || "").trim().toLowerCase();
    const target = String((message && message.target) || "").trim();
    const targets = Array.isArray(message && message.targets) ? message.targets : [];
    if (targets.some((t) => /^(all|everyone)$/i.test(String(t)))) return true;
    if (/^(all|everyone)$/i.test(target)) return true;
    if (!station) return true;
    const from = String((message && message.from) || "").trim().toLowerCase();
    if (from === station) return true;
    if (target.toLowerCase() === station) return true;
    return targets.some((t) => String(t).trim().toLowerCase() === station);
  }

  return {
    status,
    fetchMessages,
    sendMessage,
    messageTargetsForStation,
    primaryTarget,
  };
})();

if (typeof globalThis !== "undefined") globalThis.SideNotesHub = SideNotesHub;
