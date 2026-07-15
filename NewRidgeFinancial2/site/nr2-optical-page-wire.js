/* Shared optical subpage wire helpers — empty ≠ $0 (CSP script-src 'self') */
(function (global) {
  function money(n) {
    if (n == null || !Number.isFinite(Number(n))) return null;
    return Number(n);
  }
  function fmtMoney(n) {
    const v = money(n);
    if (v == null) return null;
    return "$" + v.toLocaleString("en-US", { maximumFractionDigits: 0 });
  }
  function setText(id, value, emptyLabel) {
    const el = document.getElementById(id);
    if (!el) return;
    if (value == null || value === "") {
      el.textContent = emptyLabel || "—";
      el.classList.add("empty");
      return;
    }
    el.textContent = value;
    el.classList.remove("empty");
  }
  async function getJson(path, timeoutMs) {
    const ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
    const timer = ctrl && timeoutMs ? setTimeout(() => ctrl.abort(), timeoutMs) : null;
    try {
      const res = await fetch(path, {
        cache: "no-store",
        headers: { Accept: "application/json" },
        signal: ctrl ? ctrl.signal : undefined,
      });
      let data = null;
      try {
        data = await res.json();
      } catch (_) {
        data = null;
      }
      return { ok: res.ok, status: res.status, data: data };
    } catch (err) {
      return { ok: false, status: 0, data: { error: String(err && err.message ? err.message : err) } };
    } finally {
      if (timer) clearTimeout(timer);
    }
  }
  let sessionToken = "";
  async function ensureSession() {
    const r = await getJson("/api/browser-session", 8000);
    if (r.ok && r.data && r.data.sessionToken) {
      sessionToken = String(r.data.sessionToken);
      return true;
    }
    return false;
  }
  async function postJson(path, body, timeoutMs) {
    if (!sessionToken) await ensureSession();
    const ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
    const timer = ctrl && timeoutMs ? setTimeout(() => ctrl.abort(), timeoutMs) : null;
    try {
      const res = await fetch(path, {
        method: "POST",
        cache: "no-store",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          ...(sessionToken ? { "X-NR2-Session-Token": sessionToken } : {}),
        },
        body: JSON.stringify(body || {}),
        signal: ctrl ? ctrl.signal : undefined,
      });
      let data = null;
      try {
        data = await res.json();
      } catch (_) {
        data = null;
      }
      return { ok: res.ok, status: res.status, data: data };
    } catch (err) {
      return { ok: false, status: 0, data: { error: String(err && err.message ? err.message : err) } };
    } finally {
      if (timer) clearTimeout(timer);
    }
  }
  let cachedBuildId = "";
  async function resolveBuildId() {
    if (cachedBuildId) return cachedBuildId;
    const r = await getJson("/api/app-info", 6000);
    const id =
      r.ok && r.data
        ? String(r.data.buildId || r.data.BUILD_ID || r.data.assetVersion || "").trim()
        : "";
    cachedBuildId = id || "nr2-optical";
    return cachedBuildId;
  }
  function setBanner(mode, detail) {
    const banner = document.querySelector(".banner");
    if (!banner) return;
    const label =
      mode === "live" ? "LIVE" : mode === "partial" ? "PARTIAL" : mode === "unavailable" ? "UNAVAILABLE" : "WIRE";
    const stamp = cachedBuildId || "nr2-optical";
    banner.childNodes[0] && banner.childNodes[0].nodeType === 3
      ? (banner.childNodes[0].textContent =
          label + " · optical · " + stamp + " · empty ≠ $0 · no SoftDent write-back ")
      : null;
    const bind = banner.querySelector(".bind");
    if (bind && detail) bind.textContent = detail;
    if (!cachedBuildId) {
      resolveBuildId().then(function (id) {
        if (!banner.childNodes[0] || banner.childNodes[0].nodeType !== 3) return;
        banner.childNodes[0].textContent =
          label + " · optical · " + id + " · empty ≠ $0 · no SoftDent write-back ";
      });
    }
  }
  global.NR2OpticalWire = {
    money: money,
    fmtMoney: fmtMoney,
    setText: setText,
    getJson: getJson,
    postJson: postJson,
    ensureSession: ensureSession,
    setBanner: setBanner,
    resolveBuildId: resolveBuildId,
  };
})(window);
