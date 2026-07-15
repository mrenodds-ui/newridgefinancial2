/* SoftDent optical bench — live APIs, no mock dollars */
(function () {
  const W = window.NR2OpticalWire;
  if (!W) return;

  async function boot() {
    W.setText("val-ar", null);
    W.setText("val-period", "60d");
    W.setText("val-prod", null, "—");
    W.setText("val-claims", null, "—");
    W.setBanner("partial", "Wiring SoftDent claims + production · empty ≠ $0");

    let live = false;

    const claims = await W.getJson("/api/softdent/claims-outstanding", 12000);
    if (claims.ok && claims.data && claims.data.hasData) {
      const total =
        W.money(claims.data.totalOutstanding) != null
          ? W.money(claims.data.totalOutstanding)
          : (claims.data.claims || []).reduce((s, c) => s + (W.money(c.amount) || 0), 0);
      const shown = W.fmtMoney(total);
      if (shown) {
        W.setText("val-claims", shown);
        W.setText("val-ar", shown);
        live = true;
      } else {
        W.setText("val-claims", null, "∅");
        W.setText("val-ar", null, "∅");
      }
    } else {
      W.setText("val-claims", null, "NO SIGNAL");
      W.setText("val-ar", null, "NO SIGNAL");
    }

    const prod = await W.getJson("/api/softdent/production-daily", 12000);
    if (prod.ok && prod.data) {
      const vals = prod.data.values || prod.data.series || prod.data.daily;
      let last = null;
      if (Array.isArray(vals) && vals.length) {
        const tip = vals[vals.length - 1];
        last = typeof tip === "number" ? tip : tip && (tip.value != null ? tip.value : tip.amount);
      } else if (prod.data.total != null) {
        last = prod.data.total;
      }
      const shown = W.fmtMoney(last);
      W.setText("val-prod", shown, prod.data.hasData === false ? "∅" : "—");
      if (shown) live = true;
    } else {
      W.setText("val-prod", null, "NO SIGNAL");
    }

    const coll = await W.getJson("/api/softdent/collections-daily", 12000);
    if (coll.ok && coll.data && coll.data.hasData) {
      const hint = document.getElementById("hint-coll");
      if (hint) hint.textContent = "Collections daily · LIVE signal";
      live = true;
    }

    let stale = false;
    const ready = await W.getJson("/api/import-readiness", 12000);
    if (ready.ok && ready.data) {
      const gaps = (ready.data.datasetGaps || []).concat(
        (ready.data.completeness && ready.data.completeness.softGaps) || []
      );
      stale = gaps.some(
        (g) =>
          g &&
          String(g.severity || "") === "critical" &&
          /softdent\.ar|softdent/i.test(String(g.datasetKey || "")) &&
          /stale/i.test(String(g.status || ""))
      );
    }
    if (stale) {
      const ar = document.getElementById("val-ar");
      if (ar) ar.classList.add("stale");
      W.setBanner("partial", "SoftDent AR stale · claims may still be live · empty ≠ $0");
    } else {
      W.setBanner(live ? "live" : "partial", "SoftDent read-only · claims + production · no write-back");
    }
  }

  boot().catch((err) => {
    W.setBanner("partial", "Wire fault · " + String(err && err.message ? err.message : err));
  });
})();
