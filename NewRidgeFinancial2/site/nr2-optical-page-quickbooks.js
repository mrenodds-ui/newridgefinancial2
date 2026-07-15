/* QuickBooks optical bench — live APIs, no mock dollars */
(function () {
  const W = window.NR2OpticalWire;
  if (!W) return;

  async function boot() {
    W.setText("val-pl", null);
    W.setText("val-payroll", null, "UNAVAILABLE");
    W.setText("val-ar", null, "—");
    W.setText("val-ap", null, "—");
    W.setBanner("partial", "Wiring QB revenue + aging · empty ≠ $0");

    const rev = await W.getJson("/api/qb/monthly-revenue", 12000);
    const ar = await W.getJson("/api/qb/ar-aging", 12000);
    const ap = await W.getJson("/api/qb/ap-aging", 12000);

    let live = false;
    if (rev.ok && rev.data && rev.data.hasData && Array.isArray(rev.data.values) && rev.data.values.length) {
      const last = rev.data.values[rev.data.values.length - 1];
      const shown = W.fmtMoney(last);
      const lbl = Array.isArray(rev.data.labels) ? rev.data.labels[rev.data.labels.length - 1] : "";
      if (shown) {
        W.setText("val-pl", shown);
        const hint = document.getElementById("hint-pl");
        if (hint) hint.textContent = "monthly revenue" + (lbl ? " · " + lbl : "") + " · empty ≠ $0";
        live = true;
      } else {
        W.setText("val-pl", null, "∅");
      }
    } else {
      W.setText("val-pl", null, "NO SIGNAL");
    }

    function agingLabel(data) {
      if (!data) return null;
      if (data.hasData === false) return null;
      const total = data.total != null ? data.total : data.totalBalance != null ? data.totalBalance : data.sum;
      const shown = W.fmtMoney(total);
      if (shown) return shown;
      if (Array.isArray(data.buckets) && data.buckets.length) {
        const s = data.buckets.reduce((n, b) => n + (W.money(b.amount || b.balance || b.value) || 0), 0);
        return W.fmtMoney(s);
      }
      return data.hasData ? "LIVE" : null;
    }

    if (ar.ok && ar.data) {
      const shown = agingLabel(ar.data);
      W.setText("val-ar", shown, ar.data.hasData === false ? "∅" : "—");
      if (shown) live = true;
    }
    if (ap.ok && ap.data) {
      const shown = agingLabel(ap.data);
      W.setText("val-ap", shown, ap.data.hasData === false ? "∅" : "—");
      if (shown) live = true;
    }

    W.setText("val-payroll", "UNAVAILABLE");
    const payHint = document.getElementById("hint-payroll");
    if (payHint) payHint.textContent = "Payroll/AP export pack removed · UNAVAILABLE (clean-slate)";

    W.setBanner(live ? "live" : "partial", "QB revenue + aging · payroll export UNAVAILABLE · empty ≠ $0");
  }

  boot();
})();
