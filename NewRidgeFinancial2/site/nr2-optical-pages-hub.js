/* Pages Hub — LIVE/STALE from lasers + period-close OPS (never hide stalled close) */
(function () {
  const W = window.NR2OpticalWire;
  if (!W) return;

  const CARD_MATCHERS = [
    { id: "hub-main", prefixes: ["softdent.", "quickbooks."] },
    { id: "hub-softdent", prefixes: ["softdent."] },
    { id: "hub-quickbooks", prefixes: ["quickbooks."] },
    { id: "hub-hal", prefixes: ["softdent.", "quickbooks."] },
    { id: "hub-claims", prefixes: ["softdent.claims"] },
    { id: "hub-taxes", prefixes: ["taxes.", "tax."] },
    { id: "hub-ar", prefixes: ["softdent.ar"] },
    { id: "hub-om", prefixes: ["softdent.", "quickbooks."] },
    { id: "hub-docs", prefixes: ["documents.", "softdent."] },
  ];

  function keysHit(keys, prefixes) {
    return (keys || []).some(function (k) {
      const key = String(k || "");
      return prefixes.some(function (p) {
        return key === p || key.indexOf(p) === 0;
      });
    });
  }

  function setVal(id, label, cls) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = label;
    el.classList.remove("empty", "bad", "stale", "sd", "qb", "hal");
    if (cls) el.classList.add(cls);
  }

  function wireForceClose(readyData, readyOk) {
    const btn = document.getElementById("btn-force-close");
    if (!btn || btn._nr2ForceBound) return;
    btn._nr2ForceBound = true;
    const available = readyOk && W.forceCloseAvailable && W.forceCloseAvailable(readyData);
    btn.disabled = !available;
    btn.addEventListener("click", async function () {
      if (btn.disabled || btn.classList.contains("busy")) return;
      btn.classList.add("busy");
      btn.disabled = true;
      btn.textContent = "CLOSING…";
      W.setBanner("partial", "FORCE CLOSE · SoftDent pull if lasers red / stalled · empty ≠ $0");
      try {
        await W.ensureSession();
        const res = await W.forcePeriodClose({ actor: "optical-hub" });
        const data = res && res.data ? res.data : {};
        const ok = !!(res && res.ok && data.ok);
        const status = String(data.status || (ok ? "completed" : "failed")).toUpperCase();
        const pull =
          data.pullSoftdentDecided === true
            ? " · SoftDent pull"
            : data.pullSoftdentDecided === false
              ? " · attest-only"
              : "";
        const hash = data.beamHash ? " · hash " + String(data.beamHash).slice(0, 8) : "";
        const fallback = data.fallback ? " · " + String(data.fallback) : "";
        W.setBanner(
          ok ? "live" : "partial",
          "FORCE CLOSE · " +
            status +
            pull +
            fallback +
            hash +
            (ok ? "" : " · " + String(data.error || "failed")) +
            " · empty ≠ $0"
        );
        if (ok) {
          setVal("hub-close", status, "hal");
        } else if (String(data.status || "").toLowerCase() === "blocked") {
          setVal("hub-close", "BLOCKED", "stale");
        }
      } catch (err) {
        W.setBanner(
          "partial",
          "FORCE CLOSE fault · " + String(err && err.message ? err.message : err)
        );
      } finally {
        btn.classList.remove("busy");
        btn.textContent = "FORCE CLOSE";
        setTimeout(function () {
          boot();
        }, 400);
      }
    });
  }

  async function boot() {
    const [info, ready] = await Promise.all([
      W.getJson("/api/app-info", 8000),
      W.getJson("/api/import-readiness", 12000),
    ]);

    const stamp =
      (info.ok && info.data && (info.data.buildId || info.data.BUILD_ID || info.data.assetVersion)) ||
      "nr2-optical";
    const readyData = ready.ok ? ready.data : null;
    const lasers = (readyData && readyData.alignmentLasers) || {};
    const blocking =
      readyData && Array.isArray(readyData.blocking) ? readyData.blocking : [];
    const datasetKeys = Array.isArray(lasers.datasetKeys)
      ? lasers.datasetKeys
      : blocking
          .map(function (b) {
            return b && b.datasetKey;
          })
          .filter(Boolean);
    const red = lasers.red === true || blocking.length > 0;
    const closeTrouble = W.periodCloseIsTrouble ? W.periodCloseIsTrouble(readyData) : false;
    const closeBit = W.periodCloseBannerBit
      ? W.periodCloseBannerBit(readyData)
      : "CLOSE · UNKNOWN";
    const pc = W.periodCloseStatus ? W.periodCloseStatus(readyData) : null;
    const level =
      readyData ? String(readyData.level || "unknown").toUpperCase() : "NO SIGNAL";

    const hubUnhappy = !ready.ok || red || closeTrouble;
    W.setBanner(
      hubUnhappy ? "partial" : "live",
      closeBit +
        " · " +
        (red ? "Lasers RED" : "Lasers green-path") +
        " · blocking " +
        blocking.length +
        " · " +
        level +
        " · stamp " +
        stamp
    );

    const title = document.querySelector("title");
    if (title) title.textContent = "NR2 Optical Pages Hub — " + stamp;

    const closeChip = document.getElementById("hub-close");
    if (closeChip) {
      if (!ready.ok || !pc) {
        setVal("hub-close", "NO SIGNAL", "stale");
      } else if (closeTrouble) {
        setVal("hub-close", String(pc.status || "trouble").toUpperCase(), "stale");
      } else {
        setVal("hub-close", String(pc.status || "idle").toUpperCase(), "hal");
      }
      const closeHint = document.getElementById("hint-close");
      if (closeHint) {
        closeHint.textContent =
          closeBit +
          " · FORCE CLOSE pulls SoftDent when lasers red / stalled · empty ≠ $0";
      }
    }

    wireForceClose(readyData, ready.ok);
    const btn = document.getElementById("btn-force-close");
    if (btn && !btn.classList.contains("busy")) {
      const available = W.forceCloseAvailable
        ? W.forceCloseAvailable(readyData)
        : false;
      btn.disabled = !ready.ok || !available;
    }

    CARD_MATCHERS.forEach(function (card) {
      const hit = keysHit(datasetKeys, card.prefixes);
      const opsCard =
        card.id === "hub-main" || card.id === "hub-hal" || card.id === "hub-om";
      if (!ready.ok) {
        setVal(card.id, "NO SIGNAL", "stale");
        return;
      }
      if (closeTrouble && opsCard) {
        setVal(card.id, "CLOSE " + String((pc && pc.status) || "STALL").toUpperCase(), "stale");
        return;
      }
      if (hit || (red && opsCard)) {
        setVal(card.id, "STALE", "stale");
        return;
      }
      const tone =
        card.id.indexOf("qb") >= 0 || card.id === "hub-quickbooks" || card.id === "hub-taxes"
          ? "qb"
          : card.id === "hub-hal" || card.id === "hub-main"
            ? "hal"
            : "sd";
      setVal(card.id, "LIVE", tone);
    });

    setVal("hub-narratives", "UNAVAILABLE", "stale");
  }

  boot();
})();
