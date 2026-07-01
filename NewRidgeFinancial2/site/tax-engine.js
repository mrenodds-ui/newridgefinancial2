/**
 * Deterministic S corp tax planning — mirrors tax_engine.py for UI + validators.
 */
const TaxEngine = (function () {
  const TAX_YEAR = 2025;
  const ENTITY = "S corporation";
  const STATE = "Kansas";
  const MEMOAI_TAX_TOPICS = 19;
  const FEDERAL_PLANNING_RATE = 0.32;
  const KANSAS_PLANNING_RATE = 0.057;
  const EMPLOYER_FICA_RATE = 0.0765;
  const SOCIAL_SECURITY_WAGE_BASE = 174900;
  const COMP_SCENARIO_SALARIES = [180000, 220000, 260000];
  const DEFAULT_COMP_RATIO = 0.32;
  const COMP_MIN = 180000;
  const COMP_MAX = 280000;

  function roundMoney(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return 0;
    return Math.round(n);
  }

  function clamp(value, low, high) {
    return Math.max(low, Math.min(high, value));
  }

  function employerFica(wages) {
    const taxable = Math.min(Math.max(Number(wages) || 0, 0), SOCIAL_SECURITY_WAGE_BASE);
    return roundMoney(taxable * EMPLOYER_FICA_RATE);
  }

  function defaultModeledW2(bookNetIncome) {
    if (!bookNetIncome || bookNetIncome <= 0) return COMP_SCENARIO_SALARIES[1];
    return roundMoney(clamp(bookNetIncome * DEFAULT_COMP_RATIO, COMP_MIN, COMP_MAX));
  }

  function formatMoney(value) {
    const n = roundMoney(value);
    const abs = Math.abs(n).toLocaleString("en-US");
    return n < 0 ? `($${abs})` : `$${abs}`;
  }

  function buildTaxPlan(opts) {
    const o = opts || {};
    const book = roundMoney(o.bookNetIncome || 0);
    const addBacks = roundMoney(Math.max(o.ebitdaAddBacks || 0, 0));
    const mealsAdj = book ? roundMoney(book * 0.005) : 0;
    const healthAdj = book ? roundMoney(Math.min(12000, book * 0.01)) : 0;

    const bridgeLines = [
      { line: "Net income per books", amount: book, kind: "book" },
      { line: "Add: depreciation / §179 timing", amount: addBacks, kind: "add" },
      { line: "Less: meals & nondeductible (est.)", amount: -mealsAdj, kind: "less" },
      { line: "Less: owner health adj. (review)", amount: -healthAdj, kind: "less" },
    ];
    const taxableOrdinary = book + addBacks - mealsAdj - healthAdj;
    bridgeLines.push({ line: "Estimated ordinary business income", amount: taxableOrdinary, kind: "result" });
    bridgeLines.push({ line: "Owner share (100%)", amount: taxableOrdinary, kind: "result" });

    const selectedW2 = o.modeledOfficerW2 != null ? roundMoney(o.modeledOfficerW2) : defaultModeledW2(book);
    const k1Ordinary = taxableOrdinary;
    bridgeLines.push({ line: "Modeled officer W-2 (already in books)", amount: selectedW2, kind: "neutral" });
    bridgeLines.push({ line: "Est. K-1 ordinary (planning)", amount: k1Ordinary, kind: "result" });

    const federalTax = roundMoney(Math.max(k1Ordinary, 0) * FEDERAL_PLANNING_RATE);
    const kansasTax = roundMoney(Math.max(k1Ordinary, 0) * KANSAS_PLANNING_RATE);
    const totalOwnerTax = federalTax + kansasTax;

    const scenarios = COMP_SCENARIO_SALARIES.map((salary) => {
      let note = "Balanced · document with BLS/MGMA";
      if (salary === COMP_SCENARIO_SALARIES[0]) note = "Lower payroll · higher audit risk if too low";
      if (salary === COMP_SCENARIO_SALARIES[2]) note = "Higher payroll · lower distribution room";
      return {
        salary,
        k1Ordinary,
        employerFica: employerFica(salary),
        note,
        selected: salary === selectedW2,
      };
    });

    const quarterFed = roundMoney(federalTax / 4);
    const quarterKs = roundMoney(kansasTax / 4);
    const quarterly = ["Q1", "Q2", "Q3", "Q4"].map((period, i) => ({
      period,
      federal: quarterFed,
      kansas: quarterKs,
      due: ["Apr 15", "Jun 15", "Sep 15", "Jan 15"][i],
      status: "planned",
    }));

    const periodLabel = o.periodLabel || "QuickBooks import";
    const kpis = [
      { label: "Book net income", value: formatMoney(book), tone: "info", hint: periodLabel },
      { label: "Modeled officer W-2", value: formatMoney(selectedW2), tone: "info", hint: "Planning scenario" },
      { label: "Est. K-1 ordinary", value: formatMoney(k1Ordinary), tone: "success", hint: "After book-to-tax adj." },
      { label: "Est. owner tax", value: formatMoney(totalOwnerTax), tone: "warning", hint: "Federal + Kansas · CPA review" },
    ];

    return {
      taxYear: o.taxYear || TAX_YEAR,
      entity: ENTITY,
      state: STATE,
      periodLabel,
      memoAiTopics: MEMOAI_TAX_TOPICS,
      disclaimer: "Planning estimate only — not a filed return. CPA review required.",
      bookNetIncome: book,
      modeledOfficerW2: selectedW2,
      k1Ordinary,
      federalTaxEstimate: federalTax,
      kansasTaxEstimate: kansasTax,
      totalOwnerTaxEstimate: totalOwnerTax,
      federalRateLabel: `${Math.round(FEDERAL_PLANNING_RATE * 100)}% planning`,
      kansasRateLabel: `${(KANSAS_PLANNING_RATE * 100).toFixed(1)}% planning`,
      bridgeLines,
      compScenarios: scenarios,
      taxSplit: [
        { id: "federal", label: "Federal income (est.)", amount: federalTax },
        { id: "kansas", label: "Kansas income (est.)", amount: kansasTax },
      ],
      quarterlyEstimates: quarterly,
      memoCitations: [
        "scorp-reasonable-compensation-dental",
        "scorp-section-199a-qbi",
        "kansas-pte-tax-election",
        "scorp-quickbooks-readonly-prep",
      ],
      kpis,
      hasBookData: book > 0,
    };
  }

  function parseMoneyString(value) {
    const raw = String(value == null ? "" : value).trim();
    if (!raw || raw === "—") return null;
    const negative = raw.startsWith("(") && raw.endsWith(")");
    const n = Number(raw.replace(/[$,\s()]/g, ""));
    if (!Number.isFinite(n)) return null;
    return negative ? -n : n;
  }

  function collectInputsFromSnapshot(snapshot, feed) {
    const qb = (snapshot && snapshot.dashboards && snapshot.dashboards.quickbooks) || {};
    let netIncome = null;
    let periodLabel = "";

    if (qb.revenue != null && qb.expenses != null) {
      const rev = Number(qb.revenue);
      const exp = Number(qb.expenses);
      if (Number.isFinite(rev) && Number.isFinite(exp)) netIncome = rev - exp;
    }

    const plRows = (qb.pl && qb.pl.rows) || [];
    const netRow = plRows.find((r) => /net income/i.test(String(r.category || r.label || "")));
    if (netRow && netRow.amount) {
      const parsed = parseMoneyString(netRow.amount);
      if (parsed != null) netIncome = parsed;
    }

    if (qb.importedAt) periodLabel = `Imported ${new Date(qb.importedAt).toLocaleDateString()}`;
    if (qb.pl && qb.pl.range) periodLabel = qb.pl.range;

    let ebitdaAddBacks = 0;
    const candidates = qb.ebitdaCandidates || [];
    candidates.forEach((c) => {
      const amt = Number(String(c.amount || "").replace(/[$,]/g, ""));
      if (Number.isFinite(amt)) ebitdaAddBacks += amt;
    });
    if (!ebitdaAddBacks && feed && feed.widgets && feed.widgets.ebitdaNormalization) {
      const m = feed.widgets.ebitdaNormalization.metrics || {};
      const total = Number(String(m.ebitdaAddBackTotal || "").replace(/[$,]/g, ""));
      if (Number.isFinite(total)) ebitdaAddBacks = total;
    }

    return { bookNetIncome: netIncome, ebitdaAddBacks, periodLabel };
  }

  function buildTaxPlanFromSnapshot(snapshot, feed) {
    return buildTaxPlan(collectInputsFromSnapshot(snapshot, feed));
  }

  return {
    buildTaxPlan,
    buildTaxPlanFromSnapshot,
    collectInputsFromSnapshot,
    formatMoney,
    employerFica,
  };
})();

if (typeof module !== "undefined" && module.exports) {
  module.exports = TaxEngine;
}
if (typeof globalThis !== "undefined") {
  globalThis.TaxEngine = TaxEngine;
}
if (typeof window !== "undefined") {
  window.TaxEngine = TaxEngine;
}
