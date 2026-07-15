/* QuickBooks optical bench — live revenue / cash / NI · empty ≠ $0 */
(function () {
  const W = window.NR2OpticalWire;
  if (!W) return;

  function agingLabel(data) {
    if (!data || data.hasData === false) return null;
    const total = data.total != null ? data.total : data.totalBalance != null ? data.totalBalance : data.sum;
    const shown = W.fmtMoney(total);
    if (shown) return shown;
    if (Array.isArray(data.buckets) && data.buckets.length) {
      const s = data.buckets.reduce((n, b) => n + (W.money(b.amount || b.balance || b.value) || 0), 0);
      return W.fmtMoney(s);
    }
    return null;
  }

  async function boot() {
    W.setText("val-pl", null);
    W.setText("val-cash", null, "—");
    W.setText("val-ni", null, "—");
    W.setText("val-aging", null, "—");
    W.setBanner("partial", "Wiring QB revenue + cash + net income · empty ≠ $0");

    const rev = await W.getJson("/api/qb/monthly-revenue", 12000);
    const cash = await W.getJson("/api/qb/cash-flow", 12000);
    const ni = await W.getJson("/api/qb/net-income", 12000);
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

    if (cash.ok && cash.data && cash.data.hasData && Array.isArray(cash.data.net) && cash.data.net.length) {
      const tip = cash.data.net[cash.data.net.length - 1];
      const shown = W.fmtMoney(tip);
      const lbl = Array.isArray(cash.data.labels) ? cash.data.labels[cash.data.labels.length - 1] : "";
      if (shown) {
        W.setText("val-cash", shown);
        const hint = document.getElementById("hint-cash");
        if (hint) {
          const inflow = Array.isArray(cash.data.inflows) ? W.fmtMoney(cash.data.inflows[cash.data.inflows.length - 1]) : "";
          const outflow = Array.isArray(cash.data.outflows) ? W.fmtMoney(cash.data.outflows[cash.data.outflows.length - 1]) : "";
          hint.textContent =
            "cash net" +
            (lbl ? " · " + lbl : "") +
            (inflow ? " · in " + inflow : "") +
            (outflow ? " · out " + outflow : "");
        }
        live = true;
      } else {
        W.setText("val-cash", null, "∅");
      }
    } else {
      W.setText("val-cash", null, cash.ok ? "∅" : "NO SIGNAL");
    }

    if (ni.ok && ni.data && ni.data.hasData) {
      const ytd = W.fmtMoney(ni.data.ytdNetIncome);
      const latest = W.fmtMoney(ni.data.latestNetIncome);
      const shown = ytd || latest;
      if (shown) {
        W.setText("val-ni", shown);
        const hint = document.getElementById("hint-ni");
        if (hint) {
          hint.textContent =
            (ytd ? "YTD " + ytd : "latest " + latest) +
            (ni.data.latestMonth ? " · " + ni.data.latestMonth : "") +
            " · empty ≠ $0";
        }
        live = true;
      } else {
        W.setText("val-ni", null, "∅");
      }
    } else {
      W.setText("val-ni", null, ni.ok ? "∅" : "NO SIGNAL");
    }

    const arShown = ar.ok && ar.data ? agingLabel(ar.data) : null;
    const apShown = ap.ok && ap.data ? agingLabel(ap.data) : null;
    if (arShown || apShown) {
      const parts = [];
      if (arShown) parts.push("AR " + arShown);
      else parts.push("AR ∅");
      if (apShown) parts.push("AP " + apShown);
      else parts.push("AP ∅");
      W.setText("val-aging", parts.join(" · "));
      live = true;
    } else {
      const empty =
        (ar.ok && ar.data && ar.data.hasData === false) ||
        (ap.ok && ap.data && ap.data.hasData === false);
      W.setText("val-aging", null, empty || ar.ok || ap.ok ? "AR ∅ · AP ∅" : "NO SIGNAL");
      const hint = document.getElementById("hint-aging");
      if (hint) hint.textContent = "QB AR/AP aging empty · payroll export UNAVAILABLE · empty ≠ $0";
    }

    W.setBanner(
      live ? "live" : "partial",
      "QB revenue + cash + net income · aging vacuum if empty · empty ≠ $0"
    );
  }

  boot().catch((err) => {
    W.setBanner("partial", "QB wire fault · " + String(err && err.message ? err.message : err));
  });
})();
