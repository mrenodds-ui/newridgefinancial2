/* A/R optical bench — SoftDent AR buckets + live money-beams headline */
(function () {
  const W = window.NR2OpticalWire;
  if (!W) return;

  function bucketLine(buckets) {
    if (!Array.isArray(buckets) || !buckets.length) return null;
    return buckets
      .map(function (b) {
        const amt = W.fmtMoney(W.money(b.amount != null ? b.amount : b.balance));
        return String(b.bucket || "?") + " " + (amt || "∅");
      })
      .join(" · ");
  }

  async function boot() {
    W.setText("val-total", null);
    W.setText("val-buckets", null, "—");
    W.setText("val-collect", null, "—");
    W.setText("val-status", null, "—");
    W.setBanner("partial", "Wiring SoftDent AR + money-beams · empty ≠ $0 · no invent $");

    const aging = await W.getJson("/api/softdent/ar-aging", 12000);
    const claims = await W.getJson("/api/softdent/claims-outstanding", 12000);
    const ready = await W.getJson("/api/import-readiness", 12000);
    const beamsRes = await W.getMoneyBeams(12000);

    let live = false;
    let stale = false;
    const readyData = ready.ok ? ready.data : null;
    const beams = beamsRes.ok ? beamsRes.data : null;

    if (readyData) {
      const keys = W.laserKeys(readyData);
      const arHit = W.keysHit(keys, ["softdent.ar"]);
      stale = arHit || W.lasersRed(readyData);
      W.setText("val-status", arHit || W.lasersRed(readyData) ? "STALE · lasers" : "READY");
    } else {
      W.setText("val-status", "NO SIGNAL");
    }

    const beamHit = W.applyBeamHeadline({
      id: "val-total",
      hintId: "hint-total",
      beams: beams,
      ready: readyData,
      side: "softdent",
    });
    if (beamHit.applied && beamHit.live) {
      live = true;
    } else if (!beamHit.applied) {
      // Fallback to domain APIs only when money-beams unavailable
      if (aging.ok && aging.data && aging.data.hasData) {
        const shown = W.fmtMoney(aging.data.total);
        if (shown) {
          W.setText("val-total", shown);
          live = true;
        } else {
          W.setText("val-total", null, "∅");
        }
        if (aging.data.stale) stale = true;
      } else if (claims.ok && claims.data && claims.data.hasData) {
        const list = Array.isArray(claims.data.claims) ? claims.data.claims : [];
        const total =
          W.money(claims.data.totalOutstanding) != null
            ? W.money(claims.data.totalOutstanding)
            : list.reduce((s, c) => s + (W.money(c.amount) || 0), 0);
        const shown = W.fmtMoney(total);
        W.setText("val-total", shown, shown ? null : "∅");
        if (shown) live = true;
        const totalHint = document.getElementById("hint-total");
        if (totalHint) totalHint.textContent = "claims proxy · money-beams UNAVAILABLE";
      } else {
        W.setText("val-total", null, stale ? "STALE / ∅" : "NO SIGNAL");
      }
    }

    if (aging.ok && aging.data && aging.data.hasData) {
      const line = bucketLine(aging.data.buckets);
      W.setText("val-buckets", line, "∅");
      if (aging.data.stale) stale = true;
      const ageHint = document.getElementById("hint-buckets");
      if (ageHint) {
        ageHint.textContent =
          "SoftDent AR buckets" +
          (aging.data.ageHours != null ? " · age " + aging.data.ageHours + "h" : "") +
          " · empty ≠ $0";
      }
    } else {
      W.setText("val-buckets", null, aging.ok ? "∅" : "NO SIGNAL");
    }

    if (claims.ok && claims.data && claims.data.hasData) {
      const list = Array.isArray(claims.data.claims) ? claims.data.claims : [];
      W.setText("val-collect", String(list.length) + " open claims");
    } else {
      W.setText("val-collect", null, "∅");
    }

    const provenance = W.beamProvenanceLine(beams, readyData);
    if (stale || (beams && beams.importStale) || W.lasersRed(readyData)) {
      const el = document.getElementById("val-total");
      if (el) el.classList.add("stale");
      W.setBanner(
        "partial",
        "SoftDent lasers STALE · " + provenance + " · empty ≠ $0 · no SoftDent write-back"
      );
    } else {
      W.setBanner(
        W.bannerModeFromReady(readyData, live),
        "SoftDent A/R · money-beams · " + provenance + " · empty ≠ $0"
      );
    }
  }

  boot();
})();
