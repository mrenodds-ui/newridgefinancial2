/* SoftDent optical bench — live APIs + money-beams SoftDent headline */
(function () {
  const W = window.NR2OpticalWire;
  if (!W) return;

  function lastProduction(data) {
    if (!data) return { amount: null, label: "" };
    if (Array.isArray(data.points) && data.points.length) {
      const tip = data.points[data.points.length - 1];
      return {
        amount: W.money(tip && (tip.production != null ? tip.production : tip.value)),
        label: tip && tip.date ? String(tip.date) : "",
      };
    }
    const vals = data.values || data.series || data.daily;
    if (Array.isArray(vals) && vals.length) {
      const tip = vals[vals.length - 1];
      const amount =
        typeof tip === "number"
          ? tip
          : tip && (tip.value != null ? tip.value : tip.amount != null ? tip.amount : tip.production);
      const labels = data.labels;
      const label =
        Array.isArray(labels) && labels.length ? String(labels[labels.length - 1]) : "";
      return { amount: W.money(amount), label: label };
    }
    if (data.total != null) return { amount: W.money(data.total), label: "" };
    return { amount: null, label: "" };
  }

  async function boot() {
    W.setText("val-ar", null);
    W.setText("val-period", "60d");
    W.setText("val-prod", null, "—");
    W.setText("val-claims", null, "—");
    W.setBanner("partial", "Wiring SoftDent + money-beams · empty ≠ $0");

    let live = false;
    let arFromBeam = false;

    const arAging = await W.getJson("/api/softdent/ar-aging", 12000);
    const claims = await W.getJson("/api/softdent/claims-outstanding?limit=50", 12000);
    const ready = await W.getJson("/api/import-readiness", 12000);
    const beamsRes = await W.getMoneyBeams(12000);
    const readyData = ready.ok ? ready.data : null;
    const beams = beamsRes.ok ? beamsRes.data : null;

    const beamHit = W.applyBeamHeadline({
      id: "val-ar",
      hintId: null,
      beams: beams,
      ready: readyData,
      side: "softdent",
    });
    if (beamHit.applied && beamHit.live) {
      arFromBeam = true;
      live = true;
      const arCard = document.getElementById("val-ar");
      const arHint = arCard && arCard.parentElement && arCard.parentElement.querySelector(".hint");
      if (arHint) {
        arHint.textContent =
          "money-beams SoftDent · hash " +
          String((beams && beams.beamHash) || "n/a") +
          " · empty ≠ $0";
      }
    } else if (!beamHit.applied && arAging.ok && arAging.data && arAging.data.hasData) {
      const shown = W.fmtMoney(arAging.data.total);
      if (shown) {
        W.setText("val-ar", shown);
        live = true;
      } else {
        W.setText("val-ar", null, "∅");
      }
    }

    if (claims.ok && claims.data && claims.data.hasData) {
      const list = Array.isArray(claims.data.claims) ? claims.data.claims : [];
      const count = claims.data.count != null ? Number(claims.data.count) : list.length;
      // Prefer same SoftDent beam total for claims card when beam live
      let shown = null;
      if (beams && beams.softdent && beams.softdent.hasData && !W.lasersRed(readyData) && !beams.importStale) {
        const h = W.honestyMoney(true, beams.softdent.display);
        shown = h.empty ? null : h.text;
      }
      if (!shown) shown = W.fmtMoney(W.money(claims.data.totalOutstanding));
      if (shown) {
        W.setText("val-claims", shown + (count ? " · " + count : ""));
        if (!arFromBeam && !beamHit.blocked) W.setText("val-ar", shown);
        live = true;
      } else {
        W.setText("val-claims", null, "∅");
        if (!arFromBeam && !beamHit.applied) W.setText("val-ar", null, "∅");
      }
    } else {
      W.setText("val-claims", null, "NO SIGNAL");
      if (!arFromBeam && !beamHit.applied) W.setText("val-ar", null, "NO SIGNAL");
    }

    const prod = await W.getJson("/api/softdent/production-daily", 12000);
    if (prod.ok && prod.data) {
      const last = lastProduction(prod.data);
      const shown = W.fmtMoney(last.amount);
      const empty = Array.isArray(prod.data.points)
        ? prod.data.points.length === 0
        : prod.data.hasData === false;
      W.setText("val-prod", shown, empty ? "∅" : "—");
      const hint = document.getElementById("hint-prod");
      if (hint && shown) {
        hint.textContent =
          "Production" + (last.label ? " · " + last.label : "") + " · empty ≠ $0";
      }
      if (shown) live = true;
    } else {
      W.setText("val-prod", null, "NO SIGNAL");
    }

    const coll = await W.getJson("/api/softdent/collections-daily", 12000);
    if (coll.ok && coll.data && coll.data.hasData && Array.isArray(coll.data.values) && coll.data.values.length) {
      const lastColl = W.fmtMoney(coll.data.values[coll.data.values.length - 1]);
      const lbl = Array.isArray(coll.data.labels)
        ? coll.data.labels[coll.data.labels.length - 1]
        : "";
      const periodEl = document.getElementById("val-period");
      if (periodEl && lastColl) {
        W.setText("val-period", lastColl);
        const periodHint = periodEl.parentElement && periodEl.parentElement.querySelector(".hint");
        if (periodHint) {
          periodHint.textContent =
            "collections latest" + (lbl ? " · " + lbl : "") + " · period refresh on main";
        }
      }
      live = true;
    }

    const util = await W.getJson("/api/softdent/provider-utilization-7d", 10000);
    if (util.ok && util.data && util.data.hasData && Array.isArray(util.data.providers) && util.data.providers.length) {
      const top = util.data.providers[0];
      const appts = top && top.appointments != null ? Number(top.appointments) : null;
      const code = top && top.providerCode != null ? String(top.providerCode) : "?";
      const ch = document.getElementById("hint-claims");
      if (ch && appts != null) {
        ch.textContent =
          (ch.textContent || "claims") +
          " · 7d util P" +
          code +
          " " +
          appts +
          " appts";
      }
      live = true;
    }

    let stale = !!(arAging.ok && arAging.data && arAging.data.stale);
    if (readyData) {
      stale = stale || W.keysHit(W.laserKeys(readyData), ["softdent."]) || W.lasersRed(readyData);
    }
    const provenance = W.beamProvenanceLine(beams, readyData);
    if (stale || (beams && beams.importStale)) {
      const ar = document.getElementById("val-ar");
      if (ar) ar.classList.add("stale");
      W.setBanner(
        "partial",
        "SoftDent lasers STALE · " + provenance + " · empty ≠ $0 · no write-back"
      );
    } else {
      W.setBanner(
        live ? "live" : "partial",
        "SoftDent · money-beams · " + provenance + " · no write-back"
      );
    }
  }

  boot().catch((err) => {
    W.setBanner("partial", "Wire fault · " + String(err && err.message ? err.message : err));
  });
})();
