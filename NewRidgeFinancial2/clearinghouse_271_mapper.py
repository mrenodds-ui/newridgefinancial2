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
