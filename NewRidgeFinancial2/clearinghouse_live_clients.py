"""Live HTTP clients for DentalXChange and Optum/Change Healthcare eligibility."""

from __future__ import annotations

import os
import random
import time
from typing import Any

from clearinghouse_271_mapper import map_dentalxchange_eligibility_response, map_optum_eligibility_response
from clearinghouse_http import env_bool, http_json, redact_member_id
from eligibility_cache_store import upsert_eligibility_entry

_TOKEN_CACHE: dict[str, Any] = {"token": "", "expires_at": 0.0, "base": ""}


def _env(name: str, default: str = "") -> str:
    return str(os.environ.get(name) or default).strip()


def _optum_base_url() -> str:
    if env_bool("CHANGE_HEALTHCARE_USE_SANDBOX", default=True):
        return _env("CHANGE_HEALTHCARE_SANDBOX_URL", "https://sandbox-apigw.optum.com").rstrip("/")
    return _env("CHANGE_HEALTHCARE_BASE_URL", "https://apigw.optum.com").rstrip("/")


def _dxc_base_url() -> str:
    return _env("DENTALXCHANGE_BASE_URL", "https://api.dentalxchange.com").rstrip("/")


def _dxc_eligibility_url() -> str:
    explicit = _env("DENTALXCHANGE_ELIGIBILITY_URL")
    if explicit:
        return explicit
    path = _env("DENTALXCHANGE_ELIGIBILITY_PATH", "/xconnect/eligibility/v1")
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{_dxc_base_url()}{path}"


def _require_live_member_id(req: dict[str, Any]) -> str:
    member_id = str(req.get("memberId") or "").strip()
    if member_id and not member_id.startswith("***"):
        return member_id
    raise ValueError("memberId_required_for_live_271")


def _require_payer_id(req: dict[str, Any]) -> str:
    payer_id = str(req.get("payerId") or "").strip()
    if payer_id:
        return payer_id
    raise ValueError("payerId_required_for_live_271")


def _require_provider_npi(req: dict[str, Any]) -> str:
    npi = str(req.get("providerNpi") or _env("NR2_PROVIDER_NPI") or _env("CHANGE_HEALTHCARE_PROVIDER_NPI")).strip()
    if npi:
        return npi
    raise ValueError("providerNpi_required_for_live_271")


def _optum_token(base_url: str) -> tuple[str | None, str | None]:
    now = time.time()
    if _TOKEN_CACHE.get("token") and _TOKEN_CACHE.get("base") == base_url and float(_TOKEN_CACHE.get("expires_at") or 0) > now + 30:
        return str(_TOKEN_CACHE["token"]), None

    client_id = _env("CHANGE_HEALTHCARE_CLIENT_ID")
    client_secret = _env("CHANGE_HEALTHCARE_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None, "missing_change_healthcare_credentials"

    token_url = _env("CHANGE_HEALTHCARE_TOKEN_URL") or f"{base_url}/apip/auth/v2/token"
    status, payload, err = http_json(
        method="POST",
        url=token_url,
        body={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret},
        timeout=30.0,
    )
    if err:
        return None, err
    if status >= 400 or not isinstance(payload, dict):
        return None, f"token_http_{status}"
    token = str(payload.get("access_token") or "")
    if not token:
        return None, "token_missing"
    expires_in = float(payload.get("expires_in") or 3600)
    _TOKEN_CACHE.update({"token": token, "expires_at": now + expires_in, "base": base_url})
    return token, None


def _build_optum_request(req: dict[str, Any]) -> dict[str, Any]:
    member_id = _require_live_member_id(req)
    payer_id = _require_payer_id(req)
    npi = _require_provider_npi(req)
    service_date = str(req.get("serviceDate") or "").strip() or time.strftime("%Y%m%d")
    control = str(req.get("controlNumber") or random.randint(100000000, 999999999))

    subscriber: dict[str, Any] = {"memberId": member_id}
    if req.get("subscriberFirstName"):
        subscriber["firstName"] = str(req["subscriberFirstName"])
    if req.get("subscriberLastName"):
        subscriber["lastName"] = str(req["subscriberLastName"])
    if req.get("subscriberDob"):
        subscriber["dateOfBirth"] = str(req["subscriberDob"]).replace("-", "")

    provider: dict[str, Any] = {"npi": npi}
    org = _env("NR2_PROVIDER_ORG_NAME", "New Ridge Family Dental")
    if org:
        provider["organizationName"] = org

    return {
        "controlNumber": control,
        "tradingPartnerServiceId": payer_id,
        "provider": provider,
        "subscriber": subscriber,
        "encounter": {
            "beginningDateOfService": service_date,
            "endDateOfService": service_date,
            "serviceTypeCodes": ["35"],
        },
    }


def _build_dxc_request(req: dict[str, Any]) -> dict[str, Any]:
    member_id = _require_live_member_id(req)
    payer_id = _require_payer_id(req)
    npi = _require_provider_npi(req)
    service_date = str(req.get("serviceDate") or "").strip() or time.strftime("%Y-%m-%d")

    body: dict[str, Any] = {
        "payerId": payer_id,
        "payerName": req.get("payerName"),
        "providerNpi": npi,
        "memberId": member_id,
        "dateOfService": service_date,
    }
    if req.get("subscriberFirstName"):
        body["subscriberFirstName"] = req["subscriberFirstName"]
    if req.get("subscriberLastName"):
        body["subscriberLastName"] = req["subscriberLastName"]
    if req.get("subscriberDob"):
        body["subscriberDateOfBirth"] = req["subscriberDob"]
    return body


def _cache_mapped_entry(entry: dict[str, Any], *, vendor: str, raw: Any) -> dict[str, Any]:
    cached = upsert_eligibility_entry(entry)
    return {
        "ok": True,
        "configured": True,
        "vendor": vendor,
        "message": f"{vendor} 271 cached (PHI-redacted snapshot).",
        "entry": cached.get("entry"),
        "raw271": raw if isinstance(raw, dict) else {"text": str(raw)[:2000]},
    }


def fetch_change_healthcare_271(req: dict[str, Any]) -> dict[str, Any]:
    try:
        body = _build_optum_request(req)
    except ValueError as exc:
        return {
            "ok": False,
            "configured": True,
            "vendor": "change_healthcare",
            "error": str(exc),
            "message": "Missing required fields for live 271 (memberId, payerId, providerNpi).",
        }

    base = _optum_base_url()
    token, token_err = _optum_token(base)

    if token_err or not token:
        return {
            "ok": False,
            "configured": True,
            "vendor": "change_healthcare",
            "error": token_err or "token_failed",
            "message": "Change Healthcare/Optum token request failed.",
        }

    eligibility_url = _env("CHANGE_HEALTHCARE_ELIGIBILITY_URL") or f"{base}/medicalnetwork/eligibility/v3/"
    status, payload, err = http_json(
        method="POST",
        url=eligibility_url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        body=body,
        timeout=60.0,
    )
    if err:
        return {"ok": False, "configured": True, "vendor": "change_healthcare", "error": err, "message": "271 HTTP error."}
    if status >= 400:
        detail = payload if isinstance(payload, dict) else {"body": str(payload)[:500]}
        return {
            "ok": False,
            "configured": True,
            "vendor": "change_healthcare",
            "error": f"eligibility_http_{status}",
            "message": "Optum eligibility request rejected.",
            "raw271": detail,
        }
    if not isinstance(payload, dict):
        return {
            "ok": False,
            "configured": True,
            "vendor": "change_healthcare",
            "error": "invalid_json_response",
            "message": "Unexpected Optum response format.",
        }

    entry = map_optum_eligibility_response(payload, req)
    entry["memberIdRedacted"] = redact_member_id(str(req.get("memberId") or ""))
    return _cache_mapped_entry(entry, vendor="change_healthcare", raw=payload)


def fetch_dentalxchange_271(req: dict[str, Any]) -> dict[str, Any]:
    api_key = _env("DENTALXCHANGE_API_KEY")
    api_secret = _env("DENTALXCHANGE_API_SECRET")
    if not api_key:
        return {
            "ok": False,
            "configured": False,
            "vendor": "dentalxchange",
            "error": "missing_dentalxchange_credentials",
            "message": "Set DENTALXCHANGE_API_KEY and DENTALXCHANGE_API_SECRET.",
        }

    try:
        body = _build_dxc_request(req)
    except ValueError as exc:
        return {
            "ok": False,
            "configured": True,
            "vendor": "dentalxchange",
            "error": str(exc),
            "message": "Missing required fields for live 271 (memberId, payerId, providerNpi).",
        }

    headers = {
        "Accept": "application/json",
        "apiKey": api_key,
    }
    if api_secret:
        headers["apiSecret"] = api_secret

    status, payload, err = http_json(
        method="POST",
        url=_dxc_eligibility_url(),
        headers=headers,
        body=body,
        timeout=60.0,
    )
    if err:
        return {"ok": False, "configured": True, "vendor": "dentalxchange", "error": err, "message": "271 HTTP error."}
    if status >= 400:
        detail = payload if isinstance(payload, dict) else {"body": str(payload)[:500]}
        return {
            "ok": False,
            "configured": True,
            "vendor": "dentalxchange",
            "error": f"eligibility_http_{status}",
            "message": "DentalXChange eligibility request rejected. Verify DENTALXCHANGE_ELIGIBILITY_PATH.",
            "raw271": detail,
        }
    if not isinstance(payload, dict):
        return {
            "ok": False,
            "configured": True,
            "vendor": "dentalxchange",
            "error": "invalid_json_response",
            "message": "Unexpected DentalXChange response format.",
        }

    entry = map_dentalxchange_eligibility_response(payload, req)
    entry["memberIdRedacted"] = redact_member_id(str(req.get("memberId") or ""))
    return _cache_mapped_entry(entry, vendor="dentalxchange", raw=payload)


def vendor_endpoints() -> dict[str, Any]:
    return {
        "dentalxchange": {
            "eligibilityUrl": _dxc_eligibility_url(),
            "baseUrl": _dxc_base_url(),
        },
        "change_healthcare": {
            "baseUrl": _optum_base_url(),
            "eligibilityUrl": _env("CHANGE_HEALTHCARE_ELIGIBILITY_URL")
            or f"{_optum_base_url()}/medicalnetwork/eligibility/v3/",
            "sandbox": env_bool("CHANGE_HEALTHCARE_USE_SANDBOX", default=True),
        },
    }
