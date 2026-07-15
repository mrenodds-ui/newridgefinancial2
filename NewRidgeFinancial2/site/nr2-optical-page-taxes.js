/* Tax Prism subpage — live calculate-planning (planning only, empty ≠ $0) */
(function () {
  const W = window.NR2OpticalWire;
  if (!W) return;

  async function runPlan() {
    W.setText("val-rate", "…");
    W.setBanner("partial", "Tax planning · posting calculate-planning …");
    const okSession = await W.ensureSession();
    if (!okSession) {
      W.setText("val-rate", "SESSION?");
      W.setBanner("partial", "Session weak — mutations may 403");
      return;
    }
    const r = await W.postJson("/api/apex/tax/calculate-planning", {}, 25000);
    if (!r.ok || !r.data) {
      W.setText("val-rate", "ERR");
      W.setText("val-period", null, "—");
      W.setText("val-book", null, "—");
      W.setBanner(
        "partial",
        "Tax planning failed · " + ((r.data && r.data.error) || r.status || "no signal")
      );
      return;
    }
    const plan = r.data;
    let rateLabel = null;
    if (plan.effective_rate != null && Number.isFinite(Number(plan.effective_rate))) {
      rateLabel = (Number(plan.effective_rate) * 100).toFixed(1) + "% EFF";
    } else if (plan.ok === false) {
      rateLabel = "UNAVAILABLE";
    } else {
      rateLabel = "PLAN OK";
    }
    W.setText("val-rate", rateLabel);

    const periodBits = [];
    if (plan.periodLabel) periodBits.push(String(plan.periodLabel));
    if (plan.taxYear != null) periodBits.push("TY " + plan.taxYear);
    if (plan.entity) periodBits.push(String(plan.entity));
    if (plan.state) periodBits.push(String(plan.state));
    W.setText("val-period", periodBits.length ? periodBits.join(" · ") : null, "∅");

    const book = W.fmtMoney(plan.taxable_income != null ? plan.taxable_income : plan.bookNetIncome);
    W.setText("val-book", book, "∅");

    const disc = document.getElementById("hint-disc");
    if (disc) {
      disc.textContent = String(plan.disclaimer || "PLANNING ONLY — REQUIRES CPA REVIEW");
    }
    const rateHint = document.getElementById("hint-rate");
    if (rateHint) {
      rateHint.textContent =
        (plan.memoAiTopics != null ? plan.memoAiTopics + " memo topics · " : "") + "never posted to QB";
    }
    W.setBanner("live", "Tax planning LIVE · PLANNING ONLY — CPA REVIEW · empty ≠ $0");
  }

  const btn = document.getElementById("btn-plan");
  if (btn) btn.onclick = () => void runPlan();
  runPlan().catch((err) => {
    W.setBanner("partial", "Tax wire fault · " + String(err && err.message ? err.message : err));
  });
})();
