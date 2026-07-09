"""Clearinghouse 270/271 eligibility adapters."""

from __future__ import annotations

import os
from typing import Any

from clearinghouse_live_clients import (
    fetch_change_healthcare_271,
    fetch_dentalxchange_271,
    fetch_vyne_tesia_271,
    vendor_endpoints,
)
from eligibility_cache_store import upsert_eligibility_entry

VENDORS = ("dentalxchange", "change_healthcare", "vyne_tesia", "tesia", "vyne", "mock")

_VENDOR_ENV = {
    "dentalxchange": ("DENTALXCHANGE_API_KEY", "DENTALXCHANGE_API_SECRET"),
    "change_healthcare": ("CHANGE_HEALTHCARE_CLIENT_ID", "CHANGE_HEALTHCARE_CLIENT_SECRET"),
    "vyne_tesia": ("VYNE_API_KEY", "TESIA_API_KEY", "VYNE_BEARER_TOKEN", "TESIA_BEARER_TOKEN"),
}


def _vendor_configured(vendor: str) -> bool:
    keys = _VENDOR_ENV.get(vendor) or ()
    return any(os.environ.get(key, "").strip() for key in keys)


def _mock_enabled() -> bool:
    return os.environ.get("CLEARINGHOUSE_MOCK", "").strip().lower() in ("1", "true", "yes")


def normalize_eligibility_request(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("request_must_be_object")
    payer_name = str(payload.get("payerName") or payload.get("payer_name") or "").strip()
    if not payer_name:
        raise ValueError("payerName_required")
    return {
        "payerName": payer_name,
        "payerId": str(payload.get("payerId") or payload.get("payer_id") or "").strip(),
        "memberId": str(payload.get("memberId") or payload.get("member_id") or "").strip(),
        "memberIdRedacted": str(payload.get("memberIdRedacted") or "").strip(),
        "subscriberRedacted": str(payload.get("subscriberRedacted") or payload.get("subscriber") or "").strip(),
        "subscriberFirstName": str(payload.get("subscriberFirstName") or payload.get("firstName") or "").strip(),
        "subscriberLastName": str(payload.get("subscriberLastName") or payload.get("lastName") or "").strip(),
        "subscriberDob": str(payload.get("subscriberDob") or payload.get("dateOfBirth") or "").strip(),
        "providerNpi": str(payload.get("providerNpi") or payload.get("npi") or "").strip(),
        "serviceDate": str(payload.get("serviceDate") or payload.get("dateOfService") or "").strip(),
        "vendor": str(payload.get("vendor") or "auto").strip().lower(),
    }


def _normalize_vendor_alias(vendor: str) -> str:
    v = str(vendor or "").strip().lower()
    if v in {"tesia", "vyne", "desktop_tesia", "desktop-tesia"}:
        return "vyne_tesia"
    return v


def _pick_vendor(requested: str) -> str:
    vendor = _normalize_vendor_alias(requested or "auto")
    if vendor in VENDORS and vendor != "mock":
        return vendor
    if _mock_enabled():
        return "mock"
    for name in ("vyne_tesia", "dentalxchange", "change_healthcare"):
        if _vendor_configured(name):
            return name
    return ""


def _stub_not_configured(vendor: str) -> dict[str, Any]:
    status = clearinghouse_status()
    return {
        "ok": False,
        "configured": False,
        "vendor": vendor or "none",
        "error": "clearinghouse_not_configured",
        "message": (
            "Live 271 fetch is not configured. Set VYNE_API_KEY / TESIA_API_KEY "
            "(Desktop Tesia), DENTALXCHANGE_API_KEY, or CHANGE_HEALTHCARE_CLIENT_ID, "
            "or CLEARINGHOUSE_MOCK=1 for local testing."
        ),
        "hint": (
            "Staff can use Desktop Tesia UI for eligibility, search_tesia_payers for "
            "payer IDs, cached eligibility (list_eligibility_cache), or POST a "
            "PHI-redacted snapshot to /api/eligibility-cache. Live 271 needs memberId, "
            "payerId, and providerNpi once credentials are set."
        ),
        "status": status,
    }


def _mock_271_response(req: dict[str, Any]) -> dict[str, Any]:
    """Deterministic mock 271 payload for dev/test when CLEARINGHOUSE_MOCK=1."""
    entry = {
        "payerName": req["payerName"],
        "payerId": req.get("payerId") or "MOCK271",
        "source": "clearinghouse_mock_271",
        "memberIdRedacted": req.get("memberIdRedacted") or "***0000",
        "subscriberRedacted": req.get("subscriberRedacted") or req.get("subscriberLastName") or "—",
        "deductibleIndividual": 50,
        "deductibleRemaining": 50,
        "annualMax": 1500,
        "annualMaxRemaining": 1500,
        "coinsurancePreventive": 100,
        "coinsuranceBasic": 80,
        "coinsuranceMajor": 50,
        "limitations": "Mock 271 — verify before quoting patient financials.",
        "ttlHours": 72,
    }
    cached = upsert_eligibility_entry(entry)
    return {
        "ok": True,
        "configured": True,
        "vendor": "mock",
        "message": "Mock 271 cached (CLEARINGHOUSE_MOCK=1).",
        "entry": cached.get("entry"),
        "raw271": {"status": "mock", "payerName": req["payerName"]},
    }


def fetch_eligibility_271(payload: dict[str, Any]) -> dict[str, Any]:
    """Request eligibility via clearinghouse; caches redacted snapshot on success."""
    req = normalize_eligibility_request(payload)
    # Resolve Tesia/Vyne payer ID from local list when missing
    if not req.get("payerId") and req.get("payerName"):
        try:
            from tesia_payer_list_store import lookup_payer_id

            hit = lookup_payer_id(req["payerName"])
            if hit and hit.get("payerId"):
                req["payerId"] = str(hit["payerId"])
        except Exception:
            pass
    vendor = _pick_vendor(req.get("vendor") or "auto")
    if not vendor:
        return _stub_not_configured("")
    if vendor == "mock":
        return _mock_271_response(req)
    if not _vendor_configured(vendor):
        return _stub_not_configured(vendor)
    if vendor == "change_healthcare":
        return fetch_change_healthcare_271(req)
    if vendor == "dentalxchange":
        return fetch_dentalxchange_271(req)
    if vendor == "vyne_tesia":
        return fetch_vyne_tesia_271(req)
    return _stub_not_configured(vendor)


def clearinghouse_status() -> dict[str, Any]:
    endpoints = vendor_endpoints()
    vendor_names = ("vyne_tesia", "dentalxchange", "change_healthcare")
    return {
        "vendors": {
            name: {
                "configured": _vendor_configured(name),
                "envKeys": list(_VENDOR_ENV.get(name) or ()),
                **(endpoints.get(name) or {}),
            }
            for name in vendor_names
        },
        "mockEnabled": _mock_enabled(),
        "liveReady": any(_vendor_configured(name) for name in vendor_names),
        "preferredOfficeVendor": "vyne_tesia",
        "requiredLiveFields": ["memberId", "payerId", "providerNpi"],
        "desktopTesiaNote": (
            "Office uses Desktop Tesia (Vyne). Import payer list via "
            "/api/tesia-payers/import; live API needs VYNE_*/TESIA_* credentials."
        ),
    }
