/* Pages Hub — Alignment Bench money face + OPS mech locks (nr2-12039) */
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

  function setFaceTone(faceId, stale) {
    const face = document.getElementById(faceId);
    if (!face) return;
    face.classList.toggle("stale-border", !!stale);
    face.classList.toggle("fresh", !stale);
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

  function paintMoneyFaces(beams, readyData) {
    if (W.applyBeamHeadline) {
      const sd = W.applyBeamHeadline({
        id: "hub-sd-amt",
        hintId: "hint-sd-amt",
        beams: beams,
        ready: readyData,
        side: "softdent",
      });
      const qb = W.applyBeamHeadline({
        id: "hub-qb-amt",
        hintId: "hint-qb-amt",
        beams: beams,
        ready: readyData,
        side: "quickbooks",
      });
      const sdEl = document.getElementById("hub-sd-amt");
      const qbEl = document.getElementById("hub-qb-amt");
      if (sdEl) {
        sdEl.classList.remove("sd", "qb", "hal", "stale", "empty");
        sdEl.classList.add(sd && sd.live ? "sd" : "stale");
      }
      if (qbEl) {
        qbEl.classList.remove("sd", "qb", "hal", "stale", "empty");
        qbEl.classList.add(qb && qb.live ? "qb" : "stale");
      }
      setFaceTone("face-sd", !(sd && sd.live));
      setFaceTone("face-qb", !(qb && qb.live));
      return;
    }
    setVal("hub-sd-amt", "NO SIGNAL", "stale");
    setVal("hub-qb-amt", "NO SIGNAL", "stale");
  }

  async function boot() {
    const [info, ready, beamsRes] = await Promise.all([
      W.getJson("/api/app-info", 8000),
      W.getJson("/api/import-readiness", 12000),
      W.getMoneyBeams ? W.getMoneyBeams(12000) : W.getJson("/api/hal/tools/money-beams", 12000),
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
    if (title) title.textContent = "NR2 Alignment Bench — " + stamp;

    const closeChip = document.getElementById("hub-close");
    if (closeChip) {
      if (!ready.ok || !pc) {
        setVal("hub-close", "NO SIGNAL", "stale");
        setFaceTone("face-hal", true);
      } else if (closeTrouble) {
        setVal("hub-close", String(pc.status || "trouble").toUpperCase(), "stale");
        setFaceTone("face-hal", true);
      } else {
        setVal("hub-close", String(pc.status || "idle").toUpperCase(), "hal");
        setFaceTone("face-hal", false);
      }
      const closeHint = document.getElementById("hint-close");
      if (closeHint) {
        closeHint.textContent =
          closeBit +
          " · FORCE CLOSE pulls SoftDent when lasers red / stalled · empty ≠ $0";
      }
    }

    const beams = beamsRes && beamsRes.ok ? beamsRes.data : null;
    paintMoneyFaces(beams, readyData);
    if (beams && W.beamProvenanceLine) {
      const hint = document.getElementById("hint-beam-proof");
      if (hint && (!hint.textContent || hint.textContent.indexOf("GET /api") === 0)) {
        hint.textContent = W.beamProvenanceLine(beams, readyData) + " · empty ≠ $0";
      }
    }

    wireForceClose(readyData, ready.ok);
    if (W.bindVerifyBeamButton) {
      W.bindVerifyBeamButton("btn-verify-beam", {
        hintId: "hint-beam-proof",
        valId: "hub-beam-proof",
      });
    }
    if (W.bindDeskSmokeButton) {
      W.bindDeskSmokeButton("btn-desk-smoke", {
        hintId: "hint-desk-smoke",
        valId: "hub-desk-smoke",
      });
    }
    W.getJson("/api/health/desk-smoke?run=0", 8000).then(function (res) {
      if (!res || !res.ok || !res.data) return;
      const st = String(res.data.status || "NO SIGNAL").toUpperCase();
      setVal("hub-desk-smoke", st, st === "GREEN" ? "hal" : "stale");
      const hint = document.getElementById("hint-desk-smoke");
      if (hint && res.data.at) {
        hint.textContent =
          "last " +
          String(res.data.at).slice(0, 19) +
          (res.data.deskProof ? " · proof " + res.data.deskProof : "") +
          " · empty ≠ $0";
      }
    });
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
