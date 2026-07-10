"""Deterministic S corporation tax planning snapshot for NR2 (federal + Kansas)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from knowledge_memory_store import resolve_memory_citations

TAX_YEAR = 2025
ENTITY = "S corporation"
STATE = "Kansas"
MEMOAI_TAX_TOPICS = 19

FEDERAL_PLANNING_RATE = 0.32
KANSAS_PLANNING_RATE = 0.057
EMPLOYER_FICA_RATE = 0.0765
SOCIAL_SECURITY_WAGE_BASE = 174_900
COMP_SCENARIO_SALARIES = (180_000, 220_000, 260_000)
DEFAULT_COMP_RATIO = 0.32
COMP_MIN = 180_000
COMP_MAX = 280_000


def _round_money(value: float | int | None) -> int:
    if value is None:
        return 0
    return int(round(float(value)))


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def employer_fica(wages: float) -> int:
    taxable = min(max(wages, 0.0), SOCIAL_SECURITY_WAGE_BASE)
    return _round_money(taxable * EMPLOYER_FICA_RATE)


def default_modeled_w2(book_net_income: float) -> int:
    if book_net_income <= 0:
        return COMP_SCENARIO_SALARIES[1]
    return _round_money(_clamp(book_net_income * DEFAULT_COMP_RATIO, COMP_MIN, COMP_MAX))


def build_tax_plan(
    *,
    book_net_income: float | None,
    ebitda_add_backs: float = 0.0,
    modeled_officer_w2: int | None = None,
    period_label: str = "",
    tax_year: int = TAX_YEAR,
) -> dict[str, Any]:
    book = _round_money(book_net_income or 0)
    add_backs = _round_money(max(ebitda_add_backs, 0))
    meals_adj = _round_money(book * 0.005) if book else 0
    health_adj = _round_money(min(12_000, book * 0.01)) if book else 0

    bridge_lines = [
        {"line": "Net income per books", "amount": book, "kind": "book"},
        {"line": "Add: depreciation / §179 timing", "amount": add_backs, "kind": "add"},
        {"line": "Less: meals & nondeductible (est.)", "amount": -meals_adj, "kind": "less"},
        {"line": "Less: owner health adj. (review)", "amount": -health_adj, "kind": "less"},
    ]
    taxable_ordinary = book + add_backs - meals_adj - health_adj
    bridge_lines.append({"line": "Estimated ordinary business income", "amount": taxable_ordinary, "kind": "result"})
    bridge_lines.append({"line": "Owner share (100%)", "amount": taxable_ordinary, "kind": "result"})

    selected_w2 = modeled_officer_w2 if modeled_officer_w2 is not None else default_modeled_w2(float(book))
    k1_ordinary = taxable_ordinary
    bridge_lines.append({"line": "Modeled officer W-2 (already in books)", "amount": selected_w2, "kind": "neutral"})
    bridge_lines.append({"line": "Est. K-1 ordinary (planning)", "amount": k1_ordinary, "kind": "result"})

    federal_tax = _round_money(max(k1_ordinary, 0) * FEDERAL_PLANNING_RATE)
    kansas_tax = _round_money(max(k1_ordinary, 0) * KANSAS_PLANNING_RATE)
    total_owner_tax = federal_tax + kansas_tax

    scenarios = []
    for salary in COMP_SCENARIO_SALARIES:
        note = "Balanced · document with BLS/MGMA"
        if salary == min(COMP_SCENARIO_SALARIES):
            note = "Lower payroll · higher audit risk if too low"
        elif salary == max(COMP_SCENARIO_SALARIES):
            note = "Higher payroll · lower distribution room"
        scenarios.append(
            {
                "salary": salary,
                "k1Ordinary": k1_ordinary,
                "employerFica": employer_fica(float(salary)),
                "note": note,
                "selected": salary == selected_w2,
            }
        )

    quarter_amount_fed = _round_money(federal_tax / 4)
    quarter_amount_ks = _round_money(kansas_tax / 4)
    quarterly = [
        {"period": "Q1", "federal": quarter_amount_fed, "kansas": quarter_amount_ks, "due": "Apr 15", "status": "planned"},
        {"period": "Q2", "federal": quarter_amount_fed, "kansas": quarter_amount_ks, "due": "Jun 15", "status": "planned"},
        {"period": "Q3", "federal": quarter_amount_fed, "kansas": quarter_amount_ks, "due": "Sep 15", "status": "planned"},
        {"period": "Q4", "federal": quarter_amount_fed, "kansas": quarter_amount_ks, "due": "Jan 15", "status": "planned"},
    ]

    kpis = [
        {"label": "Book net income", "value": book, "tone": "info", "hint": period_label or "QuickBooks import"},
        {"label": "Modeled officer W-2", "value": selected_w2, "tone": "info", "hint": "Planning scenario"},
        {"label": "Est. K-1 ordinary", "value": k1_ordinary, "tone": "success", "hint": "After book-to-tax adj."},
        {"label": "Est. owner tax", "value": total_owner_tax, "tone": "warning", "hint": "Federal + Kansas · CPA review"},
    ]

    plan = {
        "taxYear": tax_year,
        "entity": ENTITY,
        "state": STATE,
        "periodLabel": period_label,
        "memoAiTopics": MEMOAI_TAX_TOPICS,
        "disclaimer": "Planning estimate only — not a filed return. CPA review required.",
        "bookNetIncome": book,
        "modeledOfficerW2": selected_w2,
        "k1Ordinary": k1_ordinary,
        "federalTaxEstimate": federal_tax,
        "kansasTaxEstimate": kansas_tax,
        "totalOwnerTaxEstimate": total_owner_tax,
        "federalRateLabel": f"{int(FEDERAL_PLANNING_RATE * 100)}% planning",
        "kansasRateLabel": f"{KANSAS_PLANNING_RATE * 100:.1f}% planning",
        "bridgeLines": bridge_lines,
        "compScenarios": scenarios,
        "taxSplit": [
            {"id": "federal", "label": "Federal income (est.)", "amount": federal_tax},
            {"id": "kansas", "label": "Kansas income (est.)", "amount": kansas_tax},
        ],
        "quarterlyEstimates": quarterly,
        "memoCitationIds": [
            "scorp-reasonable-compensation-dental",
            "scorp-section-199a-qbi",
            "kansas-pte-tax-election",
            "scorp-quickbooks-readonly-prep",
            "nr2-taxes-page-scope",
            "scorp-1120s-deadline",
        ],
        "kpis": kpis,
        "hasBookData": book > 0,
    }
    plan["memoCitations"] = resolve_memory_citations(plan.pop("memoCitationIds", []))
    return plan


def build_tax_plan_from_bundle(bundle: dict[str, Any] | None) -> dict[str, Any]:
    bundle = bundle or {}
    qb = bundle.get("quickbooks") or {}
    pl_rows = ((qb.get("profitAndLoss") or {}).get("rows") or []) if isinstance(qb, dict) else []
    revenue_rows = ((qb.get("revenue") or {}).get("rows") or []) if isinstance(qb, dict) else []
    expense_rows = ((qb.get("expenses") or {}).get("rows") or []) if isinstance(qb, dict) else []

    def _pick(row: dict, keys: tuple[str, ...]) -> float | None:
        for key in keys:
            raw = row.get(key)
            if raw is None or raw == "":
                continue
            try:
                return float(str(raw).replace("$", "").replace(",", ""))
            except ValueError:
                continue
        return None

    net_income: float | None = None
    if pl_rows:
        latest = pl_rows[-1]
        net_income = _pick(latest, ("NetIncome", "net_income", "Net Income"))
        period = str(latest.get("Period") or latest.get("period") or "")
    else:
        period = ""

    if net_income is None and revenue_rows and expense_rows:
        rev = _pick(revenue_rows[-1], ("TotalIncome", "Income", "Revenue", "Amount")) or 0.0
        exp = _pick(expense_rows[-1], ("TotalExpense", "Expenses", "Expense", "Amount")) or 0.0
        net_income = rev - exp

    add_backs = 0.0
    cat_rows = ((qb.get("expenseCategories") or {}).get("rows") or []) if isinstance(qb, dict) else []
    for row in cat_rows[:6]:
        label = str(row.get("Category") or row.get("category") or "").lower()
        if any(token in label for token in ("depreciation", "amort", "owner", "add-back")):
            amt = _pick(row, ("Amount", "amount"))
            if amt:
                add_backs += amt

    return build_tax_plan(
        book_net_income=net_income,
        ebitda_add_backs=add_backs,
        period_label=period or "QuickBooks import",
    )


def compute_ebitda_walk(
    bundle: dict[str, Any] | None,
    *,
    planning: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Owner-normalized EBITDA walk from QB imports only — never invent missing lines.

    Optional `planning` overrides (operator scrubber): salaryBand (display only),
    depreciation, interest, oneTime — never written to QuickBooks.
    """
    bundle = bundle or {}
    plan = build_tax_plan_from_bundle(bundle)
    qb = bundle.get("quickbooks") if isinstance(bundle.get("quickbooks"), dict) else {}
    cat_rows = ((qb.get("expenseCategories") or {}).get("rows") or []) if isinstance(qb, dict) else []

    def _pick(row: dict, keys: tuple[str, ...]) -> float | None:
        for key in keys:
            raw = row.get(key)
            if raw is None or raw == "":
                continue
            try:
                return float(str(raw).replace("$", "").replace(",", ""))
            except ValueError:
                continue
        return None

    dep = 0.0
    interest = 0.0
    dep_found = False
    interest_found = False
    for row in cat_rows:
        if not isinstance(row, dict):
            continue
        label = str(row.get("Category") or row.get("Account") or row.get("Name") or "").lower()
        amt = _pick(row, ("Amount", "amount", "Total"))
        if amt is None:
            continue
        if any(t in label for t in ("depreci", "amort", "§179", "section 179")):
            dep += abs(float(amt))
            dep_found = True
        if any(t in label for t in ("interest", "loan interest", "mortgage interest")):
            interest += abs(float(amt))
            interest_found = True

    book = plan.get("bookNetIncome")
    has_book = isinstance(book, (int, float)) and float(book) != 0
    if plan.get("hasBookData") and isinstance(book, (int, float)):
        has_book = True

    book_steps: list[dict[str, Any]] = []
    missing: list[str] = []
    if has_book:
        book_steps.append({"label": "Net Income (QB)", "value": float(book), "kind": "start"})
    else:
        missing.append("QB net income")

    if dep_found:
        book_steps.append({"label": "Add: Depreciation / Amort", "value": float(dep), "kind": "positive"})
    else:
        missing.append("Depreciation (enter via CPA / add-backs)")

    if interest_found:
        book_steps.append({"label": "Add: Interest", "value": float(interest), "kind": "positive"})
    else:
        missing.append("Interest expense")

    book_ebitda = None
    if has_book:
        book_ebitda = float(book) + (float(dep) if dep_found else 0.0) + (float(interest) if interest_found else 0.0)
        book_steps.append({"label": "EBITDA (book)", "value": float(book_ebitda), "kind": "total"})

    # Planning column — operator scrubber only
    plan_in = planning if isinstance(planning, dict) else {}
    plan_dep = plan_in.get("depreciation")
    plan_int = plan_in.get("interest")
    plan_one = plan_in.get("oneTime")
    salary = plan_in.get("officerSalary")  # scenario note only — not added to EBITDA unless oneTime

    use_dep = float(plan_dep) if isinstance(plan_dep, (int, float)) else (float(dep) if dep_found else 0.0)
    use_int = float(plan_int) if isinstance(plan_int, (int, float)) else (float(interest) if interest_found else 0.0)
    use_one = float(plan_one) if isinstance(plan_one, (int, float)) else 0.0

    plan_steps: list[dict[str, Any]] = []
    plan_ebitda = None
    if has_book:
        plan_steps.append({"label": "Net Income (QB)", "value": float(book), "kind": "start"})
        plan_steps.append({"label": "Add: Depreciation (planning)", "value": use_dep, "kind": "positive"})
        plan_steps.append({"label": "Add: Interest (planning)", "value": use_int, "kind": "positive"})
        if use_one:
            plan_steps.append({"label": "One-time adj (planning)", "value": use_one, "kind": "positive" if use_one >= 0 else "negative"})
        plan_ebitda = float(book) + use_dep + use_int + use_one
        plan_steps.append({"label": "EBITDA (planning)", "value": float(plan_ebitda), "kind": "total"})

    modeled_w2 = plan.get("modeledOfficerW2")
    salary_default = int(modeled_w2) if isinstance(modeled_w2, (int, float)) else 220_000
    salary_default = max(180_000, min(280_000, salary_default))

    return {
        "available": has_book,
        "ebitda": book_ebitda,
        "planningEbitda": plan_ebitda,
        "bookNetIncome": float(book) if isinstance(book, (int, float)) else None,
        "depreciation": float(dep) if dep_found else None,
        "interest": float(interest) if interest_found else None,
        "steps": book_steps,
        "planningSteps": plan_steps,
        "missing": missing,
        "periodLabel": plan.get("periodLabel") or "",
        "disclaimer": "Management calculation from QuickBooks imports — not GAAP; CPA review for valuation use.",
        "scrubber": {
            "officerSalary": {
                "min": 180_000,
                "max": 280_000,
                "step": 10_000,
                "default": salary_default,
                "value": int(salary) if isinstance(salary, (int, float)) else salary_default,
                "label": "Officer Compensation Scenario",
                "hint": "Planning band only — not payroll import; does not change book EBITDA unless you use one-time adj.",
            },
            "depreciation": {
                "min": 0,
                "max": max(float(dep) if dep_found else 0.0, 1.0),
                "step": 500,
                "default": float(dep) if dep_found else 0.0,
                "value": use_dep,
                "label": "Depreciation / Amort Add-Back",
                "lockedMaxFromImport": dep_found,
            },
            "interest": {
                "min": 0,
                "max": max(float(interest) if interest_found else 0.0, 1.0),
                "step": 100,
                "default": float(interest) if interest_found else 0.0,
                "value": use_int,
                "label": "Interest Add-Back",
                "lockedMaxFromImport": interest_found,
            },
            "oneTime": {
                "min": -50_000,
                "max": 50_000,
                "step": 500,
                "default": 0,
                "value": use_one,
                "label": "Discretionary / One-Time Items",
            },
        },
    }
