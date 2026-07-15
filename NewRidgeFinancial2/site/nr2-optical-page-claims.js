/* Claims optical bench — full SoftDent outstanding total + aging counts */
(function () {
  const W = window.NR2OpticalWire;
  if (!W) return;

  async function boot() {
    W.setText("val-snap", null, "—");
    W.setText("val-era", "UNAVAILABLE");
    W.setText("val-denials", null, "—");
    W.setText("val-over30", null, "—");
    W.setBanner("partial", "Wiring claims feed · empty ≠ $0 · no SoftDent write-back");

    const claims = await W.getJson("/api/softdent/claims-outstanding?limit=50", 12000);
    const aging = await W.getJson("/api/claims/aging-summary", 12000);
    const adj = await W.getJson("/api/softdent/adjustment-log", 12000);
    const ready = await W.getJson("/api/import-readiness", 12000);
    const readyData = ready.ok ? ready.data : null;
    const claimsStale = readyData
      ? W.keysHit(W.laserKeys(readyData), ["softdent.claims", "softdent."])
      : false;

    let live = false;
    if (claims.ok && claims.data && claims.data.hasData) {
      const list = Array.isArray(claims.data.claims) ? claims.data.claims : [];
      const count =
        claims.data.count != null ? Number(claims.data.count) : list.length;
      const total = W.money(claims.data.totalOutstanding);
      const shown = W.fmtMoney(total);
      if (shown) {
        W.setText("val-snap", shown + " · " + count);
        live = true;
      } else {
        W.setText("val-snap", null, "∅");
      }
      const pending = list.filter((c) => /pending|denial|denied|review/i.test(String(c.status || "")));
      if (pending.length) {
        W.setText("val-denials", String(pending.length) + " in sample");
        const dh = document.getElementById("hint-denials");
        if (dh) {
          dh.textContent =
            "status flags in top sample · full open count " + count + " · empty ≠ $0";
        }
      } else {
        W.setText("val-denials", null, "∅");
      }
    } else {
      W.setText("val-snap", null, "NO SIGNAL");
      W.setText("val-denials", null, "NO SIGNAL");
    }

    if (aging.ok && aging.data && aging.data.hasData) {
      W.setText("val-over30", String(aging.data.over30) + " / " + String(aging.data.count));
      live = true;
    } else if (aging.ok && aging.data && aging.data.hasData === false) {
      W.setText("val-over30", null, "∅");
    }

    // ERA pack removed — surface SoftDent adjustment log (read-only) instead of fake ERA $.
    if (adj.ok && adj.data && adj.data.hasData && Array.isArray(adj.data.adjustments) && adj.data.adjustments.length) {
      const tip = adj.data.adjustments[0];
      const amt = W.fmtMoney(W.money(tip && tip.amount));
      W.setText("val-era", amt ? "ADJ LOG " + amt : "ADJ LOG");
      const eraHint = document.getElementById("hint-era");
      if (eraHint) {
        eraHint.textContent =
          "ERA UNAVAILABLE · SoftDent adjustment-log" +
          (tip && tip.date ? " · " + tip.date : "") +
          " · read-only";
      }
      live = true;
    } else {
      W.setText("val-era", "UNAVAILABLE");
      const eraHint = document.getElementById("hint-era");
      if (eraHint) eraHint.textContent = "ERA ingest pack removed · no SoftDent write-back";
    }

    W.setBanner(
      claimsStale ? "partial" : live ? "live" : "partial",
      claimsStale
        ? "Claims STALE · lasers red on softdent · ERA UNAVAILABLE · empty ≠ $0"
        : "Claims full total LIVE · ERA UNAVAILABLE · empty ≠ $0"
    );
  }

  boot().catch((err) => {
    W.setBanner("partial", "Claims wire fault · " + String(err && err.message ? err.message : err));
  });
})();
