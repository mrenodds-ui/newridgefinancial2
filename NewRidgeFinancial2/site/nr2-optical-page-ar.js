/* A/R optical bench — SoftDent AR buckets first, claims proxy fallback */
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
    W.setBanner("partial", "Wiring SoftDent AR buckets · empty ≠ $0 · no invent $");

    const aging = await W.getJson("/api/softdent/ar-aging", 12000);
    const claims = await W.getJson("/api/softdent/claims-outstanding", 12000);
    const ready = await W.getJson("/api/import-readiness", 12000);

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

    if (aging.ok && aging.data && aging.data.hasData) {
      const shown = W.fmtMoney(aging.data.total);
      const line = bucketLine(aging.data.buckets);
      if (shown) {
        W.setText("val-total", shown);
        live = true;
      } else {
        W.setText("val-total", null, "∅");
      }
      W.setText("val-buckets", line, "∅");
      if (aging.data.stale) stale = true;
      const ageHint = document.getElementById("hint-buckets");
      if (ageHint) {
        ageHint.textContent =
          "GET softdent/ar-aging" +
          (aging.data.ageHours != null ? " · age " + aging.data.ageHours + "h" : "") +
          " · empty ≠ $0";
      }
    } else {
      W.setText("val-buckets", null, aging.ok ? "∅" : "NO SIGNAL");
      // Claims proxy for total only — never invent SoftDent bucket dollars.
      if (claims.ok && claims.data && claims.data.hasData) {
        const list = Array.isArray(claims.data.claims) ? claims.data.claims : [];
        const total =
          W.money(claims.data.totalOutstanding) != null
            ? W.money(claims.data.totalOutstanding)
            : list.reduce((s, c) => s + (W.money(c.amount) || 0), 0);
        const shown = W.fmtMoney(total);
        W.setText("val-total", shown, shown ? null : "∅");
        if (shown) live = true;
        const totalHint = document.getElementById("hint-total");
        if (totalHint) totalHint.textContent = "claims proxy · SoftDent AR file empty/missing";
      } else {
        W.setText("val-total", null, stale ? "STALE / ∅" : "NO SIGNAL");
      }
    }

    if (claims.ok && claims.data && claims.data.hasData) {
      const list = Array.isArray(claims.data.claims) ? claims.data.claims : [];
      W.setText("val-collect", String(list.length) + " open claims");
    } else {
      W.setText("val-collect", null, "∅");
    }

    if (stale) {
      const el = document.getElementById("val-total");
      if (el) el.classList.add("stale");
      W.setBanner(
        "partial",
        "softdent.ar STALE · re-export SoftDent Account Aging Report · empty ≠ $0 · no SoftDent write-back"
      );
    } else {
      W.setBanner(
        live ? "live" : "partial",
        "SoftDent A/R buckets · no SoftDent write-back · empty ≠ $0"
      );
    }
  }

  boot();
})();
