"""Map clearinghouse 271 JSON into PHI-redacted eligibility cache entries."""

from __future__ import annotations

import re
from typing import Any

from clearinghouse_http import redact_member_id

_MONEY_RE = re.compile(r"(\d+(?:\.\d+)?)")


def _as_number(value: Any) -> float | int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    text = str(value).replace("$", "").replace(",", "").strip()
    if not text:
        return None
    try:
        num = float(text)
        return int(num) if num.is_integer() else num
    except ValueError:
        match = _MONEY_RE.search(text)
        if match:
            num = float(match.group(1))
            return int(num) if num.is_integer() else num
    return None


def _walk(node: Any, path: str = "") -> list[tuple[str, Any]]:
    hits: list[tuple[str, Any]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            child_path = f"{path}.{key}" if path else str(key)
            hits.append((child_path, value))
            hits.extend(_walk(value, child_path))
    elif isinstance(node, list):
        for idx, item in enumerate(node):
            hits.extend(_walk(item, f"{path}[{idx}]"))
    return hits


def _find_first(node: Any, *needles: str) -> Any:
    lowered = [n.lower() for n in needles]
    for path, value in _walk(node):
        key = path.split(".")[-1].lower()
        if any(n in key for n in lowered):
            num = _as_number(value)
            if num is not None:
                return num
    return None


def _find_benefit_amount(benefits: list[Any], *keywords: str) -> float | int | None:
    keys = [k.lower() for k in keywords]
    for item in benefits:
        if not isinstance(item, dict):
            continue
        label = " ".join(
            str(item.get(field) or "")
            for field in ("name", "code", "serviceTypeCodes", "serviceTypes", "coverageLevel", "benefitAmount")
        ).lower()
        if not any(k in label for k in keys):
            continue
        for field in ("benefitAmount", "amount", "monetaryAmount", "patientResponsibilityAmount", "remainingAmount"):
            num = _as_number(item.get(field))
            if num is not None:
                return num
    return None


def map_optum_eligibility_response(data: dict[str, Any], req: dict[str, Any]) -> dict[str, Any]:
    benefits = data.get("benefitsInformation")
    if not isinstance(benefits, list):
        benefits = []

    payer = data.get("payer") if isinstance(data.get("payer"), dict) else {}
    plan = data.get("planInformation") if isinstance(data.get("planInformation"), dict) else {}
    plan_status = data.get("planStatus") if isinstance(data.get("planStatus"), dict) else {}

    deductible_remaining = _find_benefit_amount(benefits, "deductible", "remaining") or _find_first(
        data, "deductibleRemaining", "deductibleAmount"
    )
    annual_max_remaining = _find_benefit_amount(benefits, "annual", "maximum", "max") or _find_first(
        data, "annualMaxRemaining", "maximumRemaining"
    )
    basic_coins = _find_benefit_amount(benefits, "basic", "coinsurance") or _find_first(data, "coinsuranceBasic")
    major_coins = _find_benefit_amount(benefits, "major", "coinsurance") or _find_first(data, "coinsuranceMajor")
    preventive = _find_benefit_amount(benefits, "preventive", "diagnostic") or _find_first(data, "coinsurancePreventive")

    limitations: list[str] = []
    for item in benefits[:12]:
        if not isinstance(item, dict):
            continue
        text = str(item.get("name") or item.get("additionalInformation") or "").strip()
        if text and len(text) > 3:
            limitations.append(text[:120])
    if plan_status.get("status"):
        limitations.insert(0, f"Plan status: {plan_status.get('status')}")

    member_id = str(req.get("memberId") or req.get("memberIdRedacted") or "")
    return {
        "payerName": str(req.get("payerName") or payer.get("name") or "").strip(),
        "payerId": str(req.get("payerId") or data.get("tradingPartnerServiceId") or payer.get("payorIdentification") or "").strip(),
        "planDescription": str(plan.get("groupDescription") or plan.get("planDescription") or plan.get("groupNumber") or "").strip()[:120],
        "memberIdRedacted": redact_member_id(member_id),
        "subscriberRedacted": str(req.get("subscriberRedacted") or req.get("subscriberLastName") or "").strip()[:40],
        "deductibleRemaining": deductible_remaining,
        "annualMaxRemaining": annual_max_remaining,
        "coinsurancePreventive": preventive,
        "coinsuranceBasic": basic_coins,
        "coinsuranceMajor": major_coins,
        "limitations": "; ".join(limitations[:4])[:400],
        "source": "change_healthcare_271",
        "ttlHours": 72,
    }


def map_vyne_eligibility_response(data: dict[str, Any], req: dict[str, Any]) -> dict[str, Any]:
    """Map Vyne / Desktop Tesia-style eligibility JSON into cache entry shape."""
    # Reuse DXC field walkers; Vyne payloads vary by product (Trellis / ClearCoverage / API).
    entry = map_dentalxchange_eligibility_response(data, req)
    entry["source"] = "vyne_tesia_271"
    if not entry.get("payerId"):
        entry["payerId"] = str(req.get("payerId") or data.get("payorId") or data.get("tradingPartnerId") or "").strip()
    return entry


def _availity_coverage_root(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize list vs single coverage payloads from Availity Coverages API."""
    if isinstance(data.get("coverages"), list) and data["coverages"]:
        first = data["coverages"][0]
        if isinstance(first, dict):
            return first
    return data


def _availity_plan_block(coverage: dict[str, Any]) -> dict[str, Any]:
    plans = coverage.get("plans")
    if isinstance(plans, list) and plans and isinstance(plans[0], dict):
        return plans[0]
    plan = coverage.get("plan")
    return plan if isinstance(plan, dict) else {}


def _availity_collect_amounts(plan: dict[str, Any]) -> list[dict[str, Any]]:
    amounts: list[dict[str, Any]] = []
    raw = plan.get("amounts")
    if isinstance(raw, list):
        amounts.extend(item for item in raw if isinstance(item, dict))
    elif isinstance(raw, dict):
        amounts.append(raw)
    for benefit in plan.get("benefits") or []:
        if not isinstance(benefit, dict):
            continue
        detail = benefit.get("benefitDetail") if isinstance(benefit.get("benefitDetail"), dict) else {}
        for block in (benefit.get("amounts"), detail.get("amounts"), detail.get("deductibles"), detail):
            if isinstance(block, list):
                amounts.extend(item for item in block if isinstance(item, dict))
            elif isinstance(block, dict):
                amounts.append(block)
                for nested_key in ("deductibles", "coInsurance", "coPayment", "outOfPocket"):
                    nested = block.get(nested_key)
                    if isinstance(nested, dict):
                        amounts.append(nested)
                    elif isinstance(nested, list):
                        amounts.extend(item for item in nested if isinstance(item, dict))
    return amounts


def _amount_label(item: dict[str, Any]) -> str:
    return " ".join(
        str(item.get(field) or "")
        for field in ("name", "description", "amountQualifier", "amountQualifierCode", "units", "coverageLevel")
    ).lower()


def _pick_amount(amounts: list[dict[str, Any]], *keywords: str, require_all: bool = False) -> float | int | None:
    keys = [k.lower() for k in keywords]
    for item in amounts:
        label = _amount_label(item)
        if require_all:
            if not all(k in label for k in keys):
                continue
        elif not any(k in label for k in keys):
            continue
        for field in ("amount", "remaining", "remainingAmount", "benefitAmount", "monetaryAmount", "value"):
            num = _as_number(item.get(field))
            if num is not None:
                return num
    return None


def map_availity_eligibility_response(data: dict[str, Any], req: dict[str, Any]) -> dict[str, Any]:
    """Map Availity Coverages (270/271) JSON into PHI-redacted cache entry."""
    coverage = _availity_coverage_root(data)
    payer = coverage.get("payer") if isinstance(coverage.get("payer"), dict) else {}
    plan = _availity_plan_block(coverage)
    amounts = _availity_collect_amounts(plan)
    benefits = plan.get("benefits") if isinstance(plan.get("benefits"), list) else []

    deductible_remaining = (
        _pick_amount(amounts, "deductible", "remaining", require_all=True)
        or _pick_amount(amounts, "deductible")
        or _find_first(coverage, "remainingDeductible", "deductibleRemaining")
        or _find_benefit_amount(benefits, "deductible")
    )
    deductible_individual = (
        _pick_amount(amounts, "deductible") or _find_first(coverage, "totalDeductible", "deductibleIndividual")
    )
    annual_max_remaining = (
        _pick_amount(amounts, "annual", "maximum", "remaining", require_all=True)
        or _pick_amount(amounts, "annual", "maximum", require_all=True)
        or _pick_amount(amounts, "annual", "max", require_all=True)
        or _find_first(coverage, "annualMaxRemaining", "maximumRemaining")
        or _find_benefit_amount(benefits, "annual", "maximum")
    )
    annual_max = (
        _pick_amount(amounts, "annual", "maximum", require_all=True)
        or _find_first(coverage, "annualMax", "annualMaximum")
    )
    preventive = _find_benefit_amount(benefits, "preventive", "diagnostic", "dental care") or _pick_amount(
        amounts, "preventive", "coinsurance"
    )
    basic_coins = _find_benefit_amount(benefits, "basic", "restorative") or _pick_amount(amounts, "basic")
    major_coins = _find_benefit_amount(benefits, "major", "prosth") or _pick_amount(amounts, "major")

    limitations: list[str] = []
    status = str(coverage.get("status") or plan.get("status") or "").strip()
    if status:
        limitations.append(f"Plan status: {status}")
    for item in benefits[:10]:
        if not isinstance(item, dict):
            continue
        label = str(item.get("name") or item.get("status") or "").strip()
        if label and len(label) > 2:
            limitations.append(label[:120])

    member_id = str(req.get("memberId") or req.get("memberIdRedacted") or "")
    subscriber = coverage.get("subscriber") if isinstance(coverage.get("subscriber"), dict) else {}
    if not member_id and subscriber.get("memberId"):
        member_id = str(subscriber.get("memberId"))

    plan_name = str(
        plan.get("planName")
        or plan.get("description")
        or plan.get("groupName")
        or coverage.get("planName")
        or ""
    ).strip()

    return {
        "payerName": str(req.get("payerName") or payer.get("name") or payer.get("displayName") or "").strip(),
        "payerId": str(req.get("payerId") or payer.get("payerId") or payer.get("id") or "").strip(),
        "planDescription": plan_name[:120],
        "memberIdRedacted": redact_member_id(member_id),
        "subscriberRedacted": str(req.get("subscriberRedacted") or req.get("subscriberLastName") or "").strip()[:40],
        "deductibleIndividual": deductible_individual,
        "deductibleRemaining": deductible_remaining,
        "annualMax": annual_max,
        "annualMaxRemaining": annual_max_remaining,
        "coinsurancePreventive": preventive,
        "coinsuranceBasic": basic_coins,
        "coinsuranceMajor": major_coins,
        "limitations": "; ".join(limitations[:4])[:400],
        "source": "availity_271",
        "ttlHours": 72,
    }


def map_dentalxchange_eligibility_response(data: dict[str, Any], req: dict[str, Any]) -> dict[str, Any]:
    benefits = data.get("benefits") or data.get("benefitDetails") or data.get("benefitsInformation")
    if not isinstance(benefits, list):
        benefits = []

    payer_block = data.get("payer") if isinstance(data.get("payer"), dict) else {}
    plan_block = data.get("plan") if isinstance(data.get("plan"), dict) else data.get("planInformation")
    if not isinstance(plan_block, dict):
        plan_block = {}

    deductible_remaining = _find_first(data, "deductibleRemaining", "deductible") or _find_benefit_amount(
        benefits if isinstance(benefits, list) else [], "deductible"
    )
    annual_max_remaining = _find_first(data, "annualMaxRemaining", "annualMaximum", "maximumRemaining") or _find_benefit_amount(
        benefits if isinstance(benefits, list) else [], "annual", "maximum"
    )

    member_id = str(req.get("memberId") or req.get("memberIdRedacted") or "")
    return {
        "payerName": str(req.get("payerName") or payer_block.get("name") or data.get("payerName") or "").strip(),
        "payerId": str(req.get("payerId") or payer_block.get("id") or data.get("payerId") or "").strip(),
        "planDescription": str(plan_block.get("description") or plan_block.get("name") or data.get("planName") or "").strip()[:120],
        "memberIdRedacted": redact_member_id(member_id),
        "subscriberRedacted": str(req.get("subscriberRedacted") or req.get("subscriberLastName") or "").strip()[:40],
        "deductibleRemaining": deductible_remaining,
        "annualMaxRemaining": annual_max_remaining,
        "coinsurancePreventive": _find_first(data, "preventive", "diagnostic"),
        "coinsuranceBasic": _find_first(data, "basic", "restorative"),
        "coinsuranceMajor": _find_first(data, "major", "prosth"),
        "limitations": str(data.get("limitations") or data.get("message") or "")[:400],
        "source": "dentalxchange_271",
        "ttlHours": 72,
    }
