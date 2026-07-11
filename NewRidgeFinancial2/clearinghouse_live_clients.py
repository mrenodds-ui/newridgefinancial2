"""Live HTTP clients for DentalXChange and Optum/Change Healthcare eligibility."""

from __future__ import annotations

import os
import random
import time
from typing import Any

from clearinghouse_271_mapper import (
    map_availity_eligibility_response,
    map_dentalxchange_eligibility_response,
    map_optum_eligibility_response,
    map_vyne_eligibility_response,
)
from clearinghouse_http import env_bool, http_json, redact_member_id, resolve_env
from eligibility_cache_store import upsert_eligibility_entry

_TOKEN_CACHE: dict[str, Any] = {"token": "", "expires_at": 0.0, "base": ""}
_AVAILITY_TOKEN_CACHE: dict[str, Any] = {"token": "", "expires_at": 0.0, "scope": ""}


def _env(name: str, default: str = "") -> str:
    return resolve_env(name, default)


def _optum_base_url() -> str:
    if env_bool("CHANGE_HEALTHCARE_USE_SANDBOX", default=True):
        return _env("CHANGE_HEALTHCARE_SANDBOX_URL", "https://sandbox-apigw.optum.com").rstrip("/")
    return _env("CHANGE_HEALTHCARE_BASE_URL", "https://apigw.optum.com").rstrip("/")


def _dxc_base_url() -> str:
    return _env("DENTALXCHANGE_BASE_URL", "https://api.dentalxchange.com").rstrip("/")


def _vyne_base_url() -> str:
    return _env("VYNE_BASE_URL", _env("TESIA_BASE_URL", "https://api.vynedental.com")).rstrip("/")


def _vyne_eligibility_url() -> str:
    explicit = _env("VYNE_ELIGIBILITY_URL") or _env("TESIA_ELIGIBILITY_URL")
    if explicit:
        return explicit
    path = _env("VYNE_ELIGIBILITY_PATH", "/eligibility/v1")
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{_vyne_base_url()}{path}"


def _availity_base_url() -> str:
    return _env("AVAILITY_BASE_URL", "https://api.availity.com").rstrip("/")


def _availity_use_demo() -> bool:
    # Default demo=true — current office keys are Demo-plan only.
    if "AVAILITY_USE_DEMO" in os.environ:
        return env_bool("AVAILITY_USE_DEMO", default=True)
    user_flag = resolve_env("AVAILITY_USE_DEMO")
    if user_flag:
        return user_flag.strip().lower() in ("1", "true", "yes", "on")
    return True


def _availity_scope() -> str:
    explicit = _env("AVAILITY_SCOPE")
    if explicit:
        return explicit
    if _availity_use_demo():
        return "healthcare-hipaa-transactions-demo"
    return "healthcare-hipaa-transactions"


def _availity_token_url() -> str:
    return _env("AVAILITY_TOKEN_URL") or f"{_availity_base_url()}/v1/token"


def _availity_coverages_url() -> str:
    explicit = _env("AVAILITY_COVERAGES_URL") or _env("AVAILITY_ELIGIBILITY_URL")
    if explicit:
        return explicit.rstrip("/")
    path = _env("AVAILITY_COVERAGES_PATH", "/availity/v1/coverages")
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{_availity_base_url()}{path}"


def _availity_credentials() -> tuple[str, str]:
    client_id = _env("AVAILITY_KEY_CODE") or _env("AVAILITY_CLIENT_ID") or _env("AVAILITY_API_KEY")
    client_secret = _env("AVAILITY_SECRET") or _env("AVAILITY_CLIENT_SECRET") or _env("AVAILITY_API_SECRET")
    return client_id, client_secret


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


def _build_vyne_request(req: dict[str, Any]) -> dict[str, Any]:
    member_id = _require_live_member_id(req)
    payer_id = _require_payer_id(req)
    npi = _require_provider_npi(req)
    service_date = str(req.get("serviceDate") or "").strip() or time.strftime("%Y-%m-%d")
    body: dict[str, Any] = {
        "payerId": payer_id,
        "payorId": payer_id,
        "payerName": req.get("payerName"),
        "providerNpi": npi,
        "npi": npi,
        "memberId": member_id,
        "subscriberId": member_id,
        "dateOfService": service_date,
        "serviceDate": service_date,
    }
    if req.get("subscriberFirstName"):
        body["subscriberFirstName"] = req["subscriberFirstName"]
        body["firstName"] = req["subscriberFirstName"]
    if req.get("subscriberLastName"):
        body["subscriberLastName"] = req["subscriberLastName"]
        body["lastName"] = req["subscriberLastName"]
    if req.get("subscriberDob"):
        body["subscriberDateOfBirth"] = req["subscriberDob"]
        body["dateOfBirth"] = req["subscriberDob"]
    return body


def fetch_vyne_tesia_271(req: dict[str, Any]) -> dict[str, Any]:
    """Live eligibility via Vyne Dental / Desktop Tesia API credentials when configured."""
    api_key = _env("VYNE_API_KEY") or _env("TESIA_API_KEY")
    api_secret = _env("VYNE_API_SECRET") or _env("TESIA_API_SECRET")
    bearer = _env("VYNE_BEARER_TOKEN") or _env("TESIA_BEARER_TOKEN")
    if not api_key and not bearer:
        return {
            "ok": False,
            "configured": False,
            "vendor": "vyne_tesia",
            "error": "missing_vyne_tesia_credentials",
            "message": (
                "Set VYNE_API_KEY (or TESIA_API_KEY) and optional VYNE_API_SECRET, "
                "or VYNE_BEARER_TOKEN. Desktop Tesia UI can still be used manually; "
                "import payer list via /api/tesia-payers/import."
            ),
        }

    try:
        body = _build_vyne_request(req)
    except ValueError as exc:
        return {
            "ok": False,
            "configured": True,
            "vendor": "vyne_tesia",
            "error": str(exc),
            "message": "Missing required fields for live 271 (memberId, payerId, providerNpi).",
        }

    # Resolve Tesia payer ID from local list when name-only
    if not str(req.get("payerId") or "").strip():
        try:
            from tesia_payer_list_store import lookup_payer_id

            hit = lookup_payer_id(str(req.get("payerName") or ""))
            if hit and hit.get("payerId"):
                body["payerId"] = hit["payerId"]
                body["payorId"] = hit["payerId"]
        except Exception:
            pass

    headers = {"Accept": "application/json"}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    if api_key:
        headers["apiKey"] = api_key
        headers["X-Api-Key"] = api_key
    if api_secret:
        headers["apiSecret"] = api_secret
        headers["X-Api-Secret"] = api_secret

    status, payload, err = http_json(
        method="POST",
        url=_vyne_eligibility_url(),
        headers=headers,
        body=body,
        timeout=60.0,
    )
    if err:
        return {"ok": False, "configured": True, "vendor": "vyne_tesia", "error": err, "message": "271 HTTP error."}
    if status >= 400:
        detail = payload if isinstance(payload, dict) else {"body": str(payload)[:500]}
        return {
            "ok": False,
            "configured": True,
            "vendor": "vyne_tesia",
            "error": f"eligibility_http_{status}",
            "message": (
                "Vyne/Tesia eligibility request rejected. Verify VYNE_ELIGIBILITY_URL / "
                "VYNE_ELIGIBILITY_PATH for your Desktop Tesia / Trellis API contract, "
                "or continue using Desktop Tesia UI + eligibility cache."
            ),
            "raw271": detail,
        }
    if not isinstance(payload, dict):
        return {
            "ok": False,
            "configured": True,
            "vendor": "vyne_tesia",
            "error": "invalid_json_response",
            "message": "Unexpected Vyne/Tesia response format.",
        }

    entry = map_vyne_eligibility_response(payload, req)
    entry["memberIdRedacted"] = redact_member_id(str(req.get("memberId") or ""))
    return _cache_mapped_entry(entry, vendor="vyne_tesia", raw=payload)


def _availity_token(scope: str) -> tuple[str | None, str | None]:
    now = time.time()
    if (
        _AVAILITY_TOKEN_CACHE.get("token")
        and _AVAILITY_TOKEN_CACHE.get("scope") == scope
        and float(_AVAILITY_TOKEN_CACHE.get("expires_at") or 0) > now + 30
    ):
        return str(_AVAILITY_TOKEN_CACHE["token"]), None

    client_id, client_secret = _availity_credentials()
    if not client_id or not client_secret:
        return None, "missing_availity_credentials"

    status, payload, err = http_json(
        method="POST",
        url=_availity_token_url(),
        form={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope,
        },
        timeout=30.0,
    )
    if err:
        return None, err
    if not isinstance(payload, dict):
        return None, f"token_http_{status}"
    # Availity sometimes returns 200 with error payload
    if payload.get("error") or status >= 400:
        desc = str(payload.get("error_description") or payload.get("error") or f"token_http_{status}")
        return None, desc
    token = str(payload.get("access_token") or "")
    if not token:
        return None, "token_missing"
    expires_in = float(payload.get("expires_in") or 300)
    _AVAILITY_TOKEN_CACHE.update({"token": token, "expires_at": now + expires_in, "scope": scope})
    return token, None


def _build_availity_form(req: dict[str, Any], *, demo: bool) -> dict[str, Any]:
    if demo:
        member_id = str(req.get("memberId") or "").strip()
        if not member_id or member_id.startswith("***"):
            member_id = "AETNA12345"
        payer_id = str(req.get("payerId") or "").strip() or "BCBSF"
        npi = str(req.get("providerNpi") or _env("NR2_PROVIDER_NPI") or "1234567893").strip()
    else:
        member_id = _require_live_member_id(req)
        payer_id = _require_payer_id(req)
        npi = _require_provider_npi(req)

    service_date = str(req.get("serviceDate") or "").strip() or time.strftime("%Y-%m-%d")
    form: dict[str, Any] = {
        "payerId": payer_id,
        "providerNpi": npi,
        "memberId": member_id,
        "asOfDate": service_date,
        "serviceType": "35",  # dental
        "patientLastName": str(req.get("subscriberLastName") or "DOE").strip() or "DOE",
        "patientFirstName": str(req.get("subscriberFirstName") or "JOHN").strip() or "JOHN",
        "patientBirthDate": str(req.get("subscriberDob") or "1980-01-01").strip() or "1980-01-01",
    }
    return form


def _availity_coverage_id(payload: dict[str, Any]) -> str:
    if str(payload.get("id") or "").strip():
        return str(payload["id"]).strip()
    coverages = payload.get("coverages")
    if isinstance(coverages, list) and coverages and isinstance(coverages[0], dict):
        return str(coverages[0].get("id") or "").strip()
    links = payload.get("links") if isinstance(payload.get("links"), dict) else {}
    self_link = links.get("self") if isinstance(links.get("self"), dict) else {}
    href = str(self_link.get("href") or "")
    if "/coverages/" in href:
        return href.rstrip("/").split("/coverages/")[-1].split("?")[0]
    return ""


def _availity_fetch_detail(token: str, coverage_id: str, *, demo: bool) -> dict[str, Any] | None:
    if not coverage_id:
        return None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if demo:
        headers["X-Api-Mock-Response"] = "true"
        headers["X-Api-Mock-Scenario-ID"] = _env("AVAILITY_MOCK_SCENARIO", "Coverages-Complete-i")
    status, payload, err = http_json(
        method="GET",
        url=f"{_availity_coverages_url()}/{coverage_id}",
        headers=headers,
        timeout=60.0,
    )
    if err or status >= 400 or not isinstance(payload, dict):
        return None
    return payload


def fetch_availity_271(req: dict[str, Any]) -> dict[str, Any]:
    """Live / demo eligibility via Availity Coverages API (270/271)."""
    client_id, client_secret = _availity_credentials()
    if not client_id or not client_secret:
        return {
            "ok": False,
            "configured": False,
            "vendor": "availity",
            "error": "missing_availity_credentials",
            "message": "Set AVAILITY_KEY_CODE and AVAILITY_SECRET (or AVAILITY_CLIENT_ID / AVAILITY_CLIENT_SECRET).",
        }

    demo = _availity_use_demo()
    try:
        form = _build_availity_form(req, demo=demo)
    except ValueError as exc:
        return {
            "ok": False,
            "configured": True,
            "vendor": "availity",
            "error": str(exc),
            "message": "Missing required fields for live Availity 271 (memberId, payerId, providerNpi).",
        }

    scope = _availity_scope()
    token, token_err = _availity_token(scope)
    if token_err or not token:
        return {
            "ok": False,
            "configured": True,
            "vendor": "availity",
            "error": token_err or "token_failed",
            "message": (
                "Availity token request failed. Demo keys need scope "
                "healthcare-hipaa-transactions-demo (AVAILITY_USE_DEMO=1)."
            ),
        }

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if demo:
        headers["X-Api-Mock-Response"] = "true"
        headers["X-Api-Mock-Scenario-ID"] = _env("AVAILITY_MOCK_SCENARIO", "Coverages-Complete-i")

    status, payload, err = http_json(
        method="POST",
        url=_availity_coverages_url(),
        headers=headers,
        form=form,
        timeout=60.0,
    )
    if err:
        return {"ok": False, "configured": True, "vendor": "availity", "error": err, "message": "271 HTTP error."}
    if status >= 400:
        detail = payload if isinstance(payload, dict) else {"body": str(payload)[:500]}
        return {
            "ok": False,
            "configured": True,
            "vendor": "availity",
            "error": f"eligibility_http_{status}",
            "message": "Availity coverages request rejected.",
            "raw271": detail,
        }
    if not isinstance(payload, dict):
        return {
            "ok": False,
            "configured": True,
            "vendor": "availity",
            "error": "invalid_json_response",
            "message": "Unexpected Availity response format.",
        }

    coverage_id = _availity_coverage_id(payload)
    detail = _availity_fetch_detail(token, coverage_id, demo=demo) if coverage_id else None
    mapped_source = detail or payload

    # Keep request member id for redaction when demo response substitutes member ids
    map_req = dict(req)
    if not map_req.get("memberId"):
        map_req["memberId"] = form.get("memberId")

    entry = map_availity_eligibility_response(mapped_source, map_req)
    entry["memberIdRedacted"] = redact_member_id(str(map_req.get("memberId") or ""))
    if demo:
        entry["limitations"] = (
            (str(entry.get("limitations") or "") + "; Availity demo mock — not live patient data.").strip("; ").strip()
        )[:400]
    result = _cache_mapped_entry(entry, vendor="availity", raw=mapped_source)
    result["demo"] = demo
    result["coverageId"] = coverage_id
    return result


def vendor_endpoints() -> dict[str, Any]:
    return {
        "availity": {
            "baseUrl": _availity_base_url(),
            "tokenUrl": _availity_token_url(),
            "eligibilityUrl": _availity_coverages_url(),
            "demo": _availity_use_demo(),
            "scope": _availity_scope(),
        },
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
        "vyne_tesia": {
            "eligibilityUrl": _vyne_eligibility_url(),
            "baseUrl": _vyne_base_url(),
            "desktopNote": "Desktop Tesia (Vyne) remains the staff UI; API path is optional when credentials exist.",
        },
    }
