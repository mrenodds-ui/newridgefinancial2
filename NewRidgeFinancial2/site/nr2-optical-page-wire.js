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
  function lasersRed(ready) {
    if (!ready || typeof ready !== "object") return false;
    const lasers = ready.alignmentLasers || {};
    const blocking = Array.isArray(ready.blocking) ? ready.blocking : [];
    if (lasers.red === true) return true;
    if (lasers.red === false) return false;
    return blocking.length > 0 || ready.ok === false;
  }
  function laserKeys(ready) {
    const lasers = ready && ready.alignmentLasers;
    if (lasers && Array.isArray(lasers.datasetKeys) && lasers.datasetKeys.length) {
      return lasers.datasetKeys.map(String);
    }
    return (ready && Array.isArray(ready.blocking) ? ready.blocking : [])
      .map(function (b) {
        return b && b.datasetKey ? String(b.datasetKey) : "";
      })
      .filter(Boolean);
  }
  function keysHit(keys, prefixes) {
    return (keys || []).some(function (k) {
      return prefixes.some(function (p) {
        return k === p || k.indexOf(p) === 0;
      });
    });
  }
  function bannerModeFromReady(ready, hasLiveSignal) {
    if (lasersRed(ready)) return "partial";
    return hasLiveSignal ? "live" : "partial";
  }
  /** HAL-shaped SoftDent/QB money honesty — never treat $0 as live data. */
  function honestyMoney(hasData, display) {
    if (!hasData) return { text: "NO SIGNAL", empty: true };
    const d = String(display || "").trim();
    if (!d || /^[∅⊘]|no signal|unavailable/i.test(d)) {
      return { text: "NO SIGNAL", empty: true };
    }
    if (/^\$?\s*0(\.0+)?$/.test(d)) {
      return { text: "empty (not zero)", empty: true };
    }
    return { text: d, empty: false };
  }
  async function getMoneyBeams(timeoutMs) {
    return getJson("/api/hal/tools/money-beams", timeoutMs || 12000);
  }
  /**
   * Apply SoftDent or QB attested headline from money-beams.
   * When lasers red / importStale: suppress dollars (empty ≠ $0).
   */
  function applyBeamHeadline(opts) {
    const id = opts && opts.id;
    const hintId = opts && opts.hintId;
    const beams = opts && opts.beams;
    const ready = opts && opts.ready;
    const side = opts && opts.side; // "softdent" | "quickbooks"
    const el = id ? document.getElementById(id) : null;
    if (!el) return { applied: false, live: false };

    const lasers = lasersRed(ready);
    const staleBeam = !!(beams && beams.importStale);
    const block = lasers || staleBeam;
    const sideObj =
      beams && side === "quickbooks"
        ? beams.quickbooks
        : beams && beams.softdent
          ? beams.softdent
          : null;

    if (block) {
      setText(id, null, lasers ? "STALE / ∅" : "NO SIGNAL");
      el.classList.add("stale");
      if (hintId) {
        const hint = document.getElementById(hintId);
        if (hint) {
          hint.textContent =
            "money-beams gated · lasers/import STALE · empty ≠ $0 · hash " +
            String((beams && beams.beamHash) || "n/a");
        }
      }
      return { applied: true, live: false, blocked: true };
    }

    if (!beams || !sideObj) {
      return { applied: false, live: false };
    }

    const h = honestyMoney(!!sideObj.hasData, sideObj.display);
    if (h.empty) {
      setText(id, null, h.text);
      return { applied: true, live: false };
    }
    setText(id, h.text);
    el.classList.remove("stale");
    if (hintId) {
      const hint = document.getElementById(hintId);
      if (hint) {
        const ts = String(beams.beamTimestamp || beams.at || "").slice(0, 19);
        hint.textContent =
          "money-beams · " +
          side +
          (ts ? " · " + ts : "") +
          " · hash " +
          String(beams.beamHash || "n/a") +
          " · empty ≠ $0";
      }
    }
    return { applied: true, live: true, beamHash: beams.beamHash };
  }
  function beamProvenanceLine(beams, ready) {
    if (!beams) return "money-beams · NO SIGNAL";
    const close = ready && ready.periodClose;
    const parts = [
      "beamHash " + String(beams.beamHash || "n/a"),
      beams.beamTimestamp ? "at " + String(beams.beamTimestamp).slice(0, 19) : "",
      close && close.completedAt ? "close " + String(close.completedAt).slice(0, 19) : "",
    ].filter(Boolean);
    return parts.join(" · ");
  }
  function periodCloseStatus(ready) {
    const close = ready && ready.periodClose;
    if (!close || typeof close !== "object") {
      const op = ready && ready.operationContext;
      if (op && op.activeOperation) {
        return { status: String(op.activeOperation), completedAt: null, lastBeamHash: null };
      }
      return null;
    }
    return {
      status: String(close.status || "unknown").toLowerCase(),
      completedAt: close.completedAt || null,
      lastBeamHash: close.lastBeamHash || null,
    };
  }
  function periodCloseIsTrouble(ready) {
    const pc = periodCloseStatus(ready);
    if (!pc) return false;
    return /^(stalled|blocked|running|daily_close)$/i.test(pc.status);
  }
  function periodCloseBannerBit(ready) {
    const pc = periodCloseStatus(ready);
    if (!pc) return "CLOSE · NO SIGNAL";
    const stamp = pc.completedAt ? String(pc.completedAt).slice(0, 16).replace("T", " ") : "";
    const hash = pc.lastBeamHash ? " · hash " + String(pc.lastBeamHash).slice(0, 8) : "";
    return (
      "CLOSE · " +
      String(pc.status || "unknown").toUpperCase() +
      (stamp ? " · " + stamp : "") +
      hash
    );
  }
  function forceCloseAvailable(ready) {
    const pc = periodCloseStatus(ready);
    const status = pc ? String(pc.status || "").toLowerCase() : "";
    if (status === "running" || status === "daily_close") return false;
    if (status === "stalled" || status === "blocked") return true;
    return lasersRed(ready);
  }
  async function forcePeriodClose(opts) {
    const o = opts || {};
    const body = {
      actor: o.actor || "optical-force-close",
    };
    if (typeof o.pullSoftdent === "boolean") body.pullSoftdent = o.pullSoftdent;
    return postJson("/api/period-close/force", body, o.timeoutMs || 180000);
  }
  function bindForceCloseButton(btnId, opts) {
    const btn = document.getElementById(btnId || "btn-force-close");
    if (!btn) return null;
    const o = opts || {};
    const ready = o.ready || null;
    const available = forceCloseAvailable(ready);
    btn.disabled = !available;
    btn.title = available
      ? "FORCE CLOSE · SoftDent pull when lasers red or close stalled; else attest-only · empty ≠ $0"
      : "FORCE CLOSE · available when lasers red or period-close stalled/blocked";
    if (btn._nr2ForceBound) return btn;
    btn._nr2ForceBound = true;
    btn.addEventListener("click", function () {
      if (btn.disabled || btn.classList.contains("busy")) return;
      btn.classList.add("busy");
      btn.disabled = true;
      const label = btn.textContent;
      btn.textContent = "CLOSING…";
      forcePeriodClose({ actor: o.actor || "optical-force-close" })
        .then(function (res) {
          const data = (res && res.data) || {};
          const hash = data.beamHash ? String(data.beamHash).slice(0, 12) : "n/a";
          const ok = !!(res && res.ok && data.ok);
          const bit =
            (ok ? "FORCE CLOSE · OK · hash " : "FORCE CLOSE · FAIL · ") +
            hash +
            (data.laserOverride ? " · laserOverride" : "") +
            " · empty ≠ $0";
          if (typeof o.onDone === "function") {
            o.onDone({ ok: ok, res: res, bit: bit, data: data });
          } else if (typeof setBanner === "function") {
            setBanner(ok ? "live" : "partial", bit);
          }
          if (o.hintId) {
            const hint = document.getElementById(o.hintId);
            if (hint) hint.textContent = bit;
          }
        })
        .catch(function (err) {
          if (typeof setBanner === "function") {
            setBanner("partial", "FORCE CLOSE · fault · " + String(err && err.message ? err.message : err));
          }
        })
        .finally(function () {
          btn.classList.remove("busy");
          btn.textContent = label || "FORCE CLOSE";
          // Re-enable only if still available after refresh callers handle re-boot.
          if (typeof o.onFinally === "function") o.onFinally();
          else btn.disabled = !forceCloseAvailable(o.ready);
        });
    });
    return btn;
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
    lasersRed: lasersRed,
    laserKeys: laserKeys,
    keysHit: keysHit,
    bannerModeFromReady: bannerModeFromReady,
    honestyMoney: honestyMoney,
    getMoneyBeams: getMoneyBeams,
    applyBeamHeadline: applyBeamHeadline,
    beamProvenanceLine: beamProvenanceLine,
    periodCloseStatus: periodCloseStatus,
    periodCloseIsTrouble: periodCloseIsTrouble,
    periodCloseBannerBit: periodCloseBannerBit,
    forceCloseAvailable: forceCloseAvailable,
    forcePeriodClose: forcePeriodClose,
    bindForceCloseButton: bindForceCloseButton,
  };
})(window);
