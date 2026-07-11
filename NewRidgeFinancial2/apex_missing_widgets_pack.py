"""
NR2 Apex — Missing widgets W-01..W-10 (Moonshot MISSING_WIDGETS_CODING_HAL consult 2026-07-11).

Paste-faithful builders from the consult. Never invents dollar amounts.
Honest empty when SoftDent/QB export fields are missing.
PHI: patient display uses initials + em-dash only (no full names).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def _parse_money(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("$", "")
    if not text or text in {"—", "-", "N/A", "n/a"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip().replace(",", "")
    try:
        return int(float(text))
    except ValueError:
        return None


def _section_rows(bundle: dict[str, Any], system: str, key: str) -> list[dict[str, Any]]:
    """Local copy of apex_backend._section_rows — avoid circular import."""
    root = bundle.get(system) if isinstance(bundle.get(system), dict) else {}
    if not isinstance(root, dict):
        return []
    block = root.get(key)
    if isinstance(block, dict):
        rows = block.get("rows")
        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, dict)]
        data = block.get("data")
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]
        return []
    if isinstance(block, list):
        return [r for r in block if isinstance(r, dict)]
    datasets = root.get("datasets") if isinstance(root.get("datasets"), dict) else {}
    if isinstance(datasets, dict) and key in datasets:
        ds = datasets[key]
        if isinstance(ds, dict):
            rows = ds.get("rows")
            if isinstance(rows, list):
                return [r for r in rows if isinstance(r, dict)]
        if isinstance(ds, list):
            return [r for r in ds if isinstance(r, dict)]
    return []


def _initials(raw_name: str) -> str:
    parts = [x for x in str(raw_name or "").split() if x]
    letters = "".join(p[0] for p in parts[:2] if p).upper()
    return f"{letters or 'P'}—"


def _wrap(
    *,
    widget_id: str,
    type_: str,
    title: str,
    page: str,
    size: str,
    status: str,
    data: dict[str, Any],
    hint: str = "",
    collapse_when_empty: bool = False,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Consult payload shape + Apex id/label compatibility."""
    empty_msg = str(data.get("emptyMessage") or "No data")
    out: dict[str, Any] = {
        "id": widget_id,
        "widgetId": widget_id,
        "type": type_,
        "label": title,
        "title": title,
        "page": page,
        "size": size,
        "status": status,
        "data": data,
        "emptyMessage": empty_msg,
        "hint": hint or empty_msg,
        "collapseWhenEmpty": collapse_when_empty,
    }
    if extra:
        out.update(extra)
    return out


# ——— W-01 Expense Category Treemap ———


def build_expense_treemap(bundle: dict[str, Any], *, page: str = "financial") -> dict[str, Any]:
    qb = bundle.get("quickbooks") if isinstance(bundle.get("quickbooks"), dict) else {}
    coa = qb.get("chart_of_accounts") if isinstance(qb.get("chart_of_accounts"), dict) else {}
    rows = coa.get("rows") if isinstance(coa.get("rows"), list) else []
    if not rows:
        # Honest fallback: flat expenseCategories as single-level tree (no invented nesting)
        flat = _section_rows(bundle, "quickbooks", "expenseCategories")
        categories: list[dict[str, Any]] = []
        for row in flat[:6]:
            if not isinstance(row, dict):
                continue
            name = str(row.get("Category") or row.get("Account") or row.get("Name") or "Category—").strip()
            amt = _parse_money(row.get("Amount") or row.get("amount") or row.get("Total"))
            categories.append({"name": name[:40] or "Category—", "value": amt, "children": []})
    else:
        categories = []
        for parent in rows[:6]:
            if not isinstance(parent, dict):
                continue
            children_raw = parent.get("children") if isinstance(parent.get("children"), list) else []
            children = [
                {
                    "name": str(c.get("name") or c.get("Name") or "Sub—")[:40],
                    "value": _parse_money(c.get("value") or c.get("Amount") or c.get("amount")),
                }
                for c in children_raw[:4]
                if isinstance(c, dict)
            ]
            categories.append(
                {
                    "name": str(parent.get("name") or parent.get("Name") or "Category—")[:40],
                    "value": _parse_money(parent.get("value") or parent.get("Amount") or parent.get("amount")),
                    "children": children,
                }
            )

    status = "empty" if not categories else "ok"
    # If all values null, still show structure but mark empty for honesty when no amounts
    if categories and all(c.get("value") is None for c in categories):
        status = "empty"

    data = {
        "total": None,
        "categories": categories,
        "currency": "$",
        "emptyMessage": "Expense hierarchy unavailable",
    }
    return _wrap(
        widget_id="expense-treemap",
        type_="treemap",
        title="Expense Concentration",
        page=page,
        size="l",
        status=status,
        data=data,
        hint="QuickBooks expense hierarchy — amounts only when imported; never invented.",
        collapse_when_empty=status == "empty",
    )


# ——— W-02 Procedure Profitability Scatter ———


def build_procedure_scatter(bundle: dict[str, Any]) -> dict[str, Any]:
    proc_rows = _section_rows(bundle, "softdent", "procedures")
    points: list[dict[str, Any]] = []
    for row in proc_rows[:50]:
        if not isinstance(row, dict):
            continue
        code = str(row.get("code") or row.get("Code") or row.get("ADACode") or row.get("Procedure") or "D—").strip()
        fee = _parse_money(
            row.get("billed_fee") or row.get("Fee") or row.get("Amount") or row.get("Production") or row.get("Billed")
        )
        collected = _parse_money(
            row.get("net_collection") or row.get("Collected") or row.get("Payment") or row.get("Net")
        )
        volume = _parse_int(row.get("count") or row.get("Count") or row.get("Qty") or row.get("Quantity")) or 5
        # Only plot when at least one axis has import-backed value
        if fee is None and collected is None:
            continue
        points.append(
            {
                "code": code[:12] or "D—",
                "x": fee,
                "y": collected,
                "r": min(max(volume, 3), 20),
                "label": code[:12] or "D—",
            }
        )

    status = "empty" if not points else "ok"
    # Honest: if no collection side, still empty overlay per consult
    if points and all(p.get("y") is None for p in points):
        status = "empty"

    data = {
        "points": points,
        "xLabel": "Billed Fee",
        "yLabel": "Net Collection",
        "medianX": None,
        "medianY": None,
        "emptyMessage": "Cost data unavailable",
    }
    return _wrap(
        widget_id="procedure-profitability-scatter",
        type_="scatter-plot",
        title="Procedure Profitability",
        page="financial",
        size="l",
        status=status,
        data=data,
        hint="SoftDent procedure fee vs collection — empty until both axes exist.",
        collapse_when_empty=status == "empty",
    )


# ——— W-03 Denial Reason Pareto ———


def build_denial_pareto(bundle: dict[str, Any]) -> dict[str, Any]:
    claims = bundle.get("claims") if isinstance(bundle.get("claims"), dict) else {}
    denials = claims.get("denial_codes") if isinstance(claims.get("denial_codes"), list) else []

    if not denials:
        # Aggregate denial-ish codes from SoftDent claim rows when present
        tallies: dict[str, dict[str, Any]] = {}
        for row in _section_rows(bundle, "softdent", "claims") or _section_rows(bundle, "softdent", "claimStatus"):
            if not isinstance(row, dict):
                continue
            code = str(
                row.get("DenialCode")
                or row.get("denial_code")
                or row.get("ReasonCode")
                or row.get("CARC")
                or ""
            ).strip()
            status = str(row.get("Status") or row.get("status") or "").lower()
            if not code and "den" not in status:
                continue
            if not code:
                code = "DENIED"
            bucket = tallies.setdefault(code, {"code": code, "count": 0, "amount": 0.0, "has_amt": False})
            bucket["count"] += 1
            amt = _parse_money(row.get("Amount") or row.get("Balance") or row.get("Denied"))
            if amt is not None:
                bucket["amount"] += amt
                bucket["has_amt"] = True
        denials = []
        for code, b in sorted(tallies.items(), key=lambda kv: kv[1]["count"], reverse=True)[:8]:
            denials.append(
                {
                    "code": code,
                    "count": b["count"],
                    "amount": b["amount"] if b["has_amt"] else None,
                    "pct": 0,
                }
            )
        total_count = sum(int(d["count"] or 0) for d in denials) or 0
        if total_count:
            for d in denials:
                d["pct"] = round((int(d["count"] or 0) / total_count) * 100, 1)

    bars: list[dict[str, Any]] = []
    cumulative: list[float] = []
    running = 0.0
    for d in denials[:8]:
        if not isinstance(d, dict):
            continue
        code = str(d.get("code") or "CO—")
        count = _parse_int(d.get("count"))
        amt = _parse_money(d.get("amount"))
        pct = float(d.get("pct") or 0)
        running += pct
        bars.append({"code": code, "amount": amt, "count": count, "pct": pct})
        cumulative.append(min(running, 100.0))

    status = "empty" if not bars else "ok"
    data = {
        "bars": bars,
        "cumulative": cumulative,
        "threshold": 80,
        "emptyMessage": "No denials recorded",
    }
    return _wrap(
        widget_id="denial-pareto",
        type_="pareto-chart",
        title="Denial Pareto",
        page="claims",
        size="l",
        status=status,
        data=data,
        hint="Denial codes from SoftDent/ERA when present — never invented.",
        collapse_when_empty=status == "empty",
        extra={"denialCodes": [b["code"] for b in bars]},
    )


# ——— W-04 Treatment Plan Conversion Pipeline (funnel reuse) ———


def build_treatment_pipeline(bundle: dict[str, Any], *, page: str = "financial") -> dict[str, Any]:
    sd = bundle.get("softdent") if isinstance(bundle.get("softdent"), dict) else {}
    plans_block = sd.get("treatment_plans") if isinstance(sd.get("treatment_plans"), dict) else {}
    by_status = plans_block.get("by_status") if isinstance(plans_block.get("by_status"), dict) else {}

    if not by_status:
        # Try flat treatment plan rows with Status column
        tallies: dict[str, dict[str, Any]] = {
            "Presented": {"count": 0, "value": 0.0, "has": False},
            "Accepted": {"count": 0, "value": 0.0, "has": False},
            "Scheduled": {"count": 0, "value": 0.0, "has": False},
            "Completed": {"count": 0, "value": 0.0, "has": False},
        }
        for row in _section_rows(bundle, "softdent", "treatmentPlans") or _section_rows(
            bundle, "softdent", "treatment_plans"
        ):
            if not isinstance(row, dict):
                continue
            st = str(row.get("Status") or row.get("status") or row.get("Stage") or "").strip().title()
            if st not in tallies:
                # Map common SoftDent wording
                low = st.lower()
                if "present" in low or "proposed" in low:
                    st = "Presented"
                elif "accept" in low:
                    st = "Accepted"
                elif "sched" in low:
                    st = "Scheduled"
                elif "complete" in low or "done" in low:
                    st = "Completed"
                else:
                    continue
            tallies[st]["count"] += 1
            tallies[st]["has"] = True
            amt = _parse_money(row.get("Amount") or row.get("Fee") or row.get("Value") or row.get("Total"))
            if amt is not None:
                tallies[st]["value"] += amt
        by_status = {
            k: {"count": v["count"] if v["has"] else None, "value": v["value"] if v["has"] else None}
            for k, v in tallies.items()
        }

    stages: list[dict[str, Any]] = []
    prev_count: int | None = None
    for status_name in ["Presented", "Accepted", "Scheduled", "Completed"]:
        block = by_status.get(status_name) if isinstance(by_status.get(status_name), dict) else {}
        count = _parse_int(block.get("count"))
        value = _parse_money(block.get("value"))
        rate = None
        if prev_count and count is not None and prev_count > 0:
            rate = round((count / prev_count) * 100, 1)
        stages.append(
            {
                "name": status_name,
                "stage": status_name,  # Apex funnel renderer field
                "count": count,
                "value": value,
                "conversionRate": rate,
            }
        )
        if count is not None:
            prev_count = count

    status = "empty" if not any(s.get("count") for s in stages) else "ok"
    data = {
        "stages": stages,
        "emptyMessage": "No treatment plan data",
    }
    return _wrap(
        widget_id="treatment-conversion-pipeline",
        type_="funnel",
        title="Treatment Conversion",
        page=page,
        size="l",
        status=status,
        data=data,
        hint="SoftDent treatment plan status pipeline — honest empty without export.",
        collapse_when_empty=status == "empty",
        extra={"stages": stages},
    )


# ——— W-05 Pre-Authorization Aging Lanes ———


def build_preauth_lanes(bundle: dict[str, Any]) -> dict[str, Any]:
    sd = bundle.get("softdent") if isinstance(bundle.get("softdent"), dict) else {}
    preauths = sd.get("preauthorizations") if isinstance(sd.get("preauthorizations"), list) else []
    if not preauths:
        preauths = _section_rows(bundle, "softdent", "preauthorizations") or _section_rows(
            bundle, "softdent", "preAuths"
        )

    by_code: dict[str, dict[str, int]] = defaultdict(lambda: {"0-30": 0, "31-60": 0, "61-90": 0, "90+": 0})
    for p in preauths:
        if not isinstance(p, dict):
            continue
        code = str(p.get("procedure_code") or p.get("Code") or p.get("ADACode") or "D—").strip() or "D—"
        age = _parse_int(p.get("age_days") or p.get("Age") or p.get("Days") or p.get("AgeDays")) or 0
        if age <= 30:
            by_code[code]["0-30"] += 1
        elif age <= 60:
            by_code[code]["31-60"] += 1
        elif age <= 90:
            by_code[code]["61-90"] += 1
        else:
            by_code[code]["90+"] += 1

    color_map = {"0-30": "cyan", "31-60": "amber", "61-90": "magenta", "90+": "alert"}
    lanes: list[dict[str, Any]] = []
    for code, segs in sorted(by_code.items()):
        total = sum(segs.values())
        lanes.append(
            {
                "code": code[:12],
                "total": total if total > 0 else None,
                "segments": [
                    {"bucket": k, "count": v, "color": color_map[k]} for k, v in segs.items()
                ],
            }
        )

    status = "empty" if not lanes else "ok"
    data = {
        "lanes": lanes,
        "emptyMessage": "No pending pre-auths",
    }
    return _wrap(
        widget_id="preauth-aging-lanes",
        type_="timeline-lanes",
        title="Pre-Auth Lanes",
        page="claims",
        size="m",
        status=status,
        data=data,
        hint="Pre-authorization aging by procedure code — empty without SoftDent pre-auth export.",
        collapse_when_empty=status == "empty",
    )


# ——— W-06 Unapplied Credit Float Strip ———


def build_unapplied_float(bundle: dict[str, Any]) -> dict[str, Any]:
    sd = bundle.get("softdent") if isinstance(bundle.get("softdent"), dict) else {}
    payments = sd.get("unapplied_payments") if isinstance(sd.get("unapplied_payments"), list) else []
    used_generic = False
    if not payments:
        payments = _section_rows(bundle, "softdent", "unappliedPayments")
    if not payments:
        payments = _section_rows(bundle, "softdent", "payments")
        used_generic = True

    credits: list[dict[str, Any]] = []
    total = 0.0
    any_amt = False
    for p in payments[:20]:
        if not isinstance(p, dict):
            continue
        unapplied_flag = p.get("Unapplied") if "Unapplied" in p else p.get("unapplied")
        if unapplied_flag is None:
            unapplied_flag = p.get("IsUnapplied")
        amt = _parse_money(
            p.get("UnappliedAmount")
            or p.get("amount")
            or p.get("Amount")
            or p.get("Credit")
            or p.get("Balance")
        )
        if unapplied_flag in (False, "N", "n", "0", 0) and p.get("UnappliedAmount") is None:
            continue
        if amt is None or amt == 0:
            continue
        if used_generic:
            kind = str(p.get("Type") or p.get("PaymentType") or p.get("Status") or "").lower()
            has_explicit = (
                p.get("UnappliedAmount") is not None
                or p.get("unapplied") is not None
                or p.get("Unapplied") is not None
            )
            if not has_explicit and not any(k in kind for k in ("unapplied", "credit", "overpay", "float")):
                continue
        total += amt
        any_amt = True
        raw_name = str(p.get("patient_name") or p.get("Patient") or p.get("PatientName") or "Patient")
        credits.append({"patientHash": _initials(raw_name), "amount": amt})

    status = "empty" if not credits else "ok"
    data = {
        "credits": credits,
        "total": total if any_amt else None,
        "count": len(credits),
        "emptyMessage": "No unapplied credits",
    }
    return _wrap(
        widget_id="unapplied-credit-float",
        type_="credit-float",
        title="Unapplied Float",
        page="ar",
        size="strip",
        status=status,
        data=data,
        hint="Unapplied SoftDent payments — patient initials only (PHI-safe).",
        collapse_when_empty=True,
    )


# ——— W-07 Cash Flow Bridge Waterfall ———


def build_cash_bridge(bundle: dict[str, Any]) -> dict[str, Any]:
    qb = bundle.get("quickbooks") if isinstance(bundle.get("quickbooks"), dict) else {}
    ar = bundle.get("ar") if isinstance(bundle.get("ar"), dict) else {}

    start = _parse_money(qb.get("cash_balance") or qb.get("cashBalance") or qb.get("CashBalance"))
    if start is None:
        # Try balance sheet / bank rows without inventing
        for row in _section_rows(bundle, "quickbooks", "balanceSheet") or _section_rows(
            bundle, "quickbooks", "bankAccounts"
        ):
            if not isinstance(row, dict):
                continue
            name = str(row.get("Account") or row.get("Name") or "").lower()
            if "cash" in name or "checking" in name or "bank" in name:
                start = _parse_money(row.get("Balance") or row.get("Amount") or row.get("Total"))
                if start is not None:
                    break

    projected_collections = _parse_money(
        ar.get("projected_30d_collections") or ar.get("projected30dCollections")
    )
    overhead = _parse_money(qb.get("scheduled_overhead") or qb.get("scheduledOverhead"))
    debt_service = _parse_money(qb.get("debt_service") or qb.get("debtService"))

    projected = None
    if all(v is not None for v in (start, projected_collections, overhead, debt_service)):
        projected = float(start) + float(projected_collections) - float(overhead) - float(debt_service)

    steps = [
        {"label": "Start Cash", "value": start, "type": "start", "kind": "start"},
        {"label": "Expected Collections", "value": projected_collections, "type": "add", "kind": "add"},
        {"label": "Overhead", "value": overhead, "type": "sub", "kind": "sub"},
        {"label": "Loan Service", "value": debt_service, "type": "sub", "kind": "sub"},
        {"label": "Projected Cash", "value": projected, "type": "end", "kind": "end"},
    ]

    status = "empty" if start is None else "ok"
    # Intermediate projection still honest-empty when incomplete
    if start is not None and projected is None:
        status = "empty"

    data = {
        "steps": steps,
        "start": start,
        "projected": projected,
        "emptyMessage": "Cash projection unavailable",
    }
    return _wrap(
        widget_id="cash-flow-bridge",
        type_="waterfall",
        title="Cash Flow Bridge — 30 Day",
        page="financial",
        size="l",
        status=status,
        data=data,
        hint="Liquidity bridge from QB cash + A/R projection — incomplete inputs stay empty.",
        collapse_when_empty=status == "empty",
        extra={"steps": steps},
    )


# ——— W-08 Insurance Verification Matrix ———


def build_verification_matrix(bundle: dict[str, Any], *, page: str = "claims") -> dict[str, Any]:
    sd = bundle.get("softdent") if isinstance(bundle.get("softdent"), dict) else {}
    appts = sd.get("appointments_next_3d") if isinstance(sd.get("appointments_next_3d"), list) else []
    if not appts:
        appts = _section_rows(bundle, "softdent", "appointments") or _section_rows(
            bundle, "softdent", "schedule"
        )

    patients: list[dict[str, Any]] = []
    for a in appts[:12]:
        if not isinstance(a, dict):
            continue
        name = str(a.get("patient_name") or a.get("Patient") or a.get("PatientName") or "Patient")
        patients.append(
            {
                "hash": _initials(name),
                "elig": a.get("eligibility_status") or a.get("Eligibility") or a.get("EligStatus"),
                "ben": a.get("benefits_status") or a.get("Benefits") or a.get("BenStatus"),
                "breakdown": a.get("breakdown_status") or a.get("Breakdown") or a.get("BreakdownStatus"),
            }
        )

    # If no verification fields at all, treat as empty tracking
    has_tracking = any(
        p.get("elig") is not None or p.get("ben") is not None or p.get("breakdown") is not None
        for p in patients
    )
    status = "empty" if (not patients or not has_tracking) else "ok"
    data = {
        "patients": patients if has_tracking else [],
        "columns": ["Elig", "Ben", "Breakdown"],
        "nextDays": 3,
        "emptyMessage": "Verification tracking disabled",
    }
    return _wrap(
        widget_id="verification-matrix",
        type_="status-matrix",
        title="Verification Matrix — Next 3D",
        page=page,
        size="m",
        status=status,
        data=data,
        hint="Eligibility/benefits flags from SoftDent — initials only.",
        collapse_when_empty=status == "empty",
    )


# ——— W-09 Operatory Utilization Board ———


def build_operatory_board(bundle: dict[str, Any]) -> dict[str, Any]:
    sd = bundle.get("softdent") if isinstance(bundle.get("softdent"), dict) else {}
    schedule = sd.get("schedule_today") if isinstance(sd.get("schedule_today"), dict) else {}
    ops = schedule.get("operatories") if isinstance(schedule.get("operatories"), list) else []

    if not ops:
        # Build from flat schedule / operatory rows when present
        by_op: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in _section_rows(bundle, "softdent", "schedule") or _section_rows(
            bundle, "softdent", "appointments"
        ):
            if not isinstance(row, dict):
                continue
            op_name = str(row.get("Operatory") or row.get("Op") or row.get("Chair") or row.get("Room") or "Op—")
            name = str(row.get("patient_name") or row.get("Patient") or row.get("PatientName") or "")
            initials = _initials(name) if name else None
            status_raw = str(row.get("status") or row.get("Status") or "open").lower()
            if "block" in status_raw:
                st = "blocked"
            elif "open" in status_raw or "avail" in status_raw or not name:
                st = "open"
            else:
                st = "booked"
            by_op[op_name].append(
                {
                    "time": str(row.get("time") or row.get("Time") or row.get("Start") or "—")[:5],
                    "status": st,
                    "patientHash": initials if st == "booked" else None,
                }
            )
        ops = [{"name": k, "slots": v[:8]} for k, v in list(by_op.items())[:6]]

    operatories: list[dict[str, Any]] = []
    for op in ops[:6]:
        if not isinstance(op, dict):
            continue
        slots: list[dict[str, Any]] = []
        for slot in op.get("slots") or []:
            if not isinstance(slot, dict):
                continue
            name = str(slot.get("patient_name") or slot.get("Patient") or "")
            initials = "".join(x[0] for x in name.split()[:2] if x).upper() if name else None
            slots.append(
                {
                    "time": str(slot.get("time") or "—"),
                    "status": str(slot.get("status") or "open"),
                    "patientHash": f"{initials}—" if initials else slot.get("patientHash"),
                }
            )
        operatories.append({"name": str(op.get("name") or "Op—"), "slots": slots})

    status = "empty" if not operatories else "ok"
    data = {
        "operatories": operatories,
        "date": schedule.get("date"),
        "emptyMessage": "No schedule data",
    }
    return _wrap(
        widget_id="operatory-util-board",
        type_="utilization-board",
        title="Operatory Board",
        page="office-manager",
        size="l",
        status=status,
        data=data,
        hint="Today's SoftDent schedule by operatory — patient initials only.",
        collapse_when_empty=status == "empty",
    )


# ——— W-10 Recall Gauge ———


def build_recall_gauge(bundle: dict[str, Any]) -> dict[str, Any]:
    sd = bundle.get("softdent") if isinstance(bundle.get("softdent"), dict) else {}
    recall = sd.get("recall_stats") if isinstance(sd.get("recall_stats"), dict) else {}
    if not recall:
        # Flat recall rows → counts only
        rows = _section_rows(bundle, "softdent", "recall") or _section_rows(bundle, "softdent", "recalls")
        due = 0
        scheduled = 0
        contacted = 0
        any_row = False
        for row in rows:
            if not isinstance(row, dict):
                continue
            any_row = True
            st = str(row.get("Status") or row.get("status") or "").lower()
            due += 1
            if "sched" in st:
                scheduled += 1
            if "contact" in st or "called" in st:
                contacted += 1
        if any_row:
            recall = {
                "due_count": due,
                "scheduled_count": scheduled,
                "contacted_count": contacted,
                "total_active": due,
            }

    due = _parse_int(recall.get("due_count") or recall.get("due"))
    scheduled = _parse_int(recall.get("scheduled_count") or recall.get("scheduled"))
    contacted = _parse_int(recall.get("contacted_count") or recall.get("contacted"))
    total = _parse_int(recall.get("total_active") or recall.get("totalActive"))

    pct = None
    if due and scheduled is not None and due > 0:
        pct = round((scheduled / due) * 100, 1)

    status = "empty" if due is None else "ok"
    data = {
        "due": due,
        "scheduled": scheduled,
        "contacted": contacted,
        "totalActive": total,
        "pctScheduled": pct,
        "emptyMessage": "Recall tracking unavailable",
    }
    return _wrap(
        widget_id="recall-gauge",
        type_="radial-gauge",
        title="Recall Status",
        page="office-manager",
        size="m",
        status=status,
        data=data,
        hint="SoftDent recall due vs scheduled — empty without recall export.",
        collapse_when_empty=status == "empty",
    )


def append_financial_missing(widgets: list[dict[str, Any]], bundle: dict[str, Any]) -> None:
    widgets.append(build_expense_treemap(bundle, page="financial"))
    widgets.append(build_procedure_scatter(bundle))
    widgets.append(build_treatment_pipeline(bundle, page="financial"))
    widgets.append(build_cash_bridge(bundle))


def append_quickbooks_missing(widgets: list[dict[str, Any]], bundle: dict[str, Any]) -> None:
    widgets.append(build_expense_treemap(bundle, page="quickbooks"))


def append_ar_missing(widgets: list[dict[str, Any]], bundle: dict[str, Any]) -> None:
    widgets.append(build_unapplied_float(bundle))


def append_claims_missing(widgets: list[dict[str, Any]], bundle: dict[str, Any]) -> None:
    widgets.append(build_denial_pareto(bundle))
    widgets.append(build_preauth_lanes(bundle))
    widgets.append(build_verification_matrix(bundle, page="claims"))


def append_office_manager_missing(widgets: list[dict[str, Any]], bundle: dict[str, Any]) -> None:
    widgets.append(build_operatory_board(bundle))
    widgets.append(build_recall_gauge(bundle))
    widgets.append(build_treatment_pipeline(bundle, page="office-manager"))
    widgets.append(build_verification_matrix(bundle, page="office-manager"))
