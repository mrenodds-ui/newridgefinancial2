/* A/R optical bench — SoftDent claims + readiness honesty (no invented buckets) */
(function () {
  const W = window.NR2OpticalWire;
  if (!W) return;

  async function boot() {
    W.setText("val-total", null);
    W.setText("val-buckets", null, "—");
    W.setText("val-collect", null, "—");
    W.setText("val-status", null, "—");
    W.setBanner("partial", "Wiring AR from SoftDent claims + readiness · no invented buckets");

    const claims = await W.getJson("/api/softdent/claims-outstanding", 12000);
    const ready = await W.getJson("/api/import-readiness", 12000);
    const aging = await W.getJson("/api/claims/aging-summary", 12000);

    let live = false;
    let stale = false;

    if (ready.ok && ready.data) {
      const gaps = (ready.data.datasetGaps || []).concat(
        (ready.data.completeness && ready.data.completeness.softGaps) || []
      );
      const arGap = gaps.find(
        (g) => g && /softdent\.ar/i.test(String(g.datasetKey || "")) && String(g.severity || "") === "critical"
      );
      if (arGap) {
        stale = /stale|missing/i.test(String(arGap.status || ""));
        W.setText("val-status", stale ? "STALE · " + (arGap.status || "gap") : String(arGap.status || "GAP"));
      } else {
        W.setText("val-status", "READY");
      }
    } else {
      W.setText("val-status", "NO SIGNAL");
    }

    if (claims.ok && claims.data && claims.data.hasData) {
      const list = Array.isArray(claims.data.claims) ? claims.data.claims : [];
      const total =
        W.money(claims.data.totalOutstanding) != null
          ? W.money(claims.data.totalOutstanding)
          : list.reduce((s, c) => s + (W.money(c.amount) || 0), 0);
      const shown = W.fmtMoney(total);
      if (shown) {
        W.setText("val-total", shown);
        live = true;
      } else {
        W.setText("val-total", null, "∅");
      }
      W.setText("val-collect", String(list.length) + " open claims");
    } else {
      W.setText("val-total", null, stale ? "STALE / ∅" : "NO SIGNAL");
      W.setText("val-collect", null, "∅");
    }

    if (aging.ok && aging.data && aging.data.hasData) {
      W.setText(
        "val-buckets",
        "over30: " + aging.data.over30 + " · n=" + aging.data.count + " (counts only)"
      );
      live = true;
    } else {
      W.setText("val-buckets", null, "NO BUCKET API · counts vacuum");
    }

    if (stale) {
      const el = document.getElementById("val-total");
      if (el) el.classList.add("stale");
      W.setBanner("partial", "softdent.ar STALE · claims may still show · empty ≠ $0 · no invent buckets");
    } else {
      W.setBanner(live ? "live" : "partial", "AR from claims outstanding · no SoftDent write-back");
    }
  }

  boot();
})();
