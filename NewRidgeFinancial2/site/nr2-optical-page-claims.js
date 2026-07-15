/* Claims optical bench — live SoftDent claims + aging summary */
(function () {
  const W = window.NR2OpticalWire;
  if (!W) return;

  async function boot() {
    W.setText("val-snap", null, "—");
    W.setText("val-era", "RO");
    W.setText("val-denials", null, "—");
    W.setText("val-over30", null, "—");
    W.setBanner("partial", "Wiring claims feed · empty ≠ $0 · no SoftDent write-back");

    const claims = await W.getJson("/api/softdent/claims-outstanding", 12000);
    const aging = await W.getJson("/api/claims/aging-summary", 12000);

    let live = false;
    if (claims.ok && claims.data && claims.data.hasData) {
      const list = Array.isArray(claims.data.claims) ? claims.data.claims : [];
      const total =
        W.money(claims.data.totalOutstanding) != null
          ? W.money(claims.data.totalOutstanding)
          : list.reduce((s, c) => s + (W.money(c.amount) || 0), 0);
      const shown = W.fmtMoney(total);
      if (shown) {
        W.setText("val-snap", shown + " · " + list.length);
        live = true;
      } else {
        W.setText("val-snap", null, "∅");
      }
      const pending = list.filter((c) => /pending|denial|denied/i.test(String(c.status || "")));
      if (pending.length) {
        W.setText("val-denials", String(pending.length) + " flagged");
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

    W.setText("val-era", "UNAVAILABLE");
    const eraHint = document.getElementById("hint-era");
    if (eraHint) eraHint.textContent = "ERA ingest pack removed · READ-ONLY path UNAVAILABLE";

    W.setBanner(live ? "live" : "partial", "Claims outstanding LIVE · ERA UNAVAILABLE · empty ≠ $0");
  }

  boot();
})();
