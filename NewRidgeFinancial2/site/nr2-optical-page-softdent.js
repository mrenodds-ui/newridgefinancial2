/* SoftDent optical bench — live APIs, no mock dollars */
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
        typeof tip === "number" ? tip : tip && (tip.value != null ? tip.value : tip.amount != null ? tip.amount : tip.production);
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
    W.setBanner("partial", "Wiring SoftDent claims + production · empty ≠ $0");

    let live = false;
    let arFromAging = false;

    const arAging = await W.getJson("/api/softdent/ar-aging", 12000);
    if (arAging.ok && arAging.data && arAging.data.hasData) {
      const shown = W.fmtMoney(arAging.data.total);
      if (shown) {
        W.setText("val-ar", shown);
        arFromAging = true;
        live = true;
      } else {
        W.setText("val-ar", null, "∅");
      }
    }

    const claims = await W.getJson("/api/softdent/claims-outstanding?limit=50", 12000);
    if (claims.ok && claims.data && claims.data.hasData) {
      const list = Array.isArray(claims.data.claims) ? claims.data.claims : [];
      const count = claims.data.count != null ? Number(claims.data.count) : list.length;
      const total = W.money(claims.data.totalOutstanding);
      const shown = W.fmtMoney(total);
      if (shown) {
        W.setText("val-claims", shown + (count ? " · " + count : ""));
        if (!arFromAging) W.setText("val-ar", shown);
        live = true;
      } else {
        W.setText("val-claims", null, "∅");
        if (!arFromAging) W.setText("val-ar", null, "∅");
      }
    } else {
      W.setText("val-claims", null, "NO SIGNAL");
      if (!arFromAging) W.setText("val-ar", null, "NO SIGNAL");
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
          "GET softdent/production-daily" + (last.label ? " · " + last.label : "") + " · empty ≠ $0";
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
        // Keep period wheel hint in title; show latest collections under period card value.
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
    const ready = await W.getJson("/api/import-readiness", 12000);
    const readyData = ready.ok ? ready.data : null;
    if (readyData) {
      stale = stale || W.keysHit(W.laserKeys(readyData), ["softdent."]);
    }
    if (stale) {
      const ar = document.getElementById("val-ar");
      if (ar) ar.classList.add("stale");
      W.setBanner(
        "partial",
        "SoftDent lasers STALE · re-export Account Aging (keep SoftDent save folder) · empty ≠ $0"
      );
    } else {
      W.setBanner(
        live ? "live" : "partial",
        "SoftDent read-only · claims + production · no write-back"
      );
    }
  }

  boot().catch((err) => {
    W.setBanner("partial", "Wire fault · " + String(err && err.message ? err.message : err));
  });
})();
