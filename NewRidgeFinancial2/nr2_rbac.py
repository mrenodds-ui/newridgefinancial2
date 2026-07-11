"""Minimal workstation RBAC — Moonshot Sprint 3 (env + signed role file)."""

from __future__ import annotations

import json
import os
from functools import wraps
from pathlib import Path
from typing import Any, Callable

import bottle

REPO_ROOT = Path(__file__).resolve().parent.parent
ROLE_PATH = REPO_ROOT / "app_data" / "nr2" / "workstation_role.json"

ROLE_CAPS: dict[str, set[str]] = {
    "front_desk": {"read_non_financial", "read_schedule"},
    "hygienist": {"read_schedule", "read_clinical"},
    "office_manager": {
        "read_financial",
        "write_posting",
        "override_import",
        "manage_ocr",
        "read_ar",
        "cloud_hal",
        "approve_writeoff_tier1",
        "read_patient_dossier",  # Moonshot: Dentist/OM/InsCo — maps hal:patient-dossier:read
    },
    "dentist": {
        "read_all",
        "write_clinical",
        "approve_closeout",
        "read_financial",
        "approve_writeoff_tier2",
        "read_patient_dossier",
    },
    "admin": {"*"},
}

WRITEOFF_TIER1_MAX_USD = float(os.environ.get("NR2_WRITEOFF_TIER1_MAX_USD", "250"))
WRITEOFF_DUAL_APPROVAL_MIN_USD = float(os.environ.get("NR2_WRITEOFF_DUAL_APPROVAL_MIN_USD", "250"))


def current_role() -> str:
    if ROLE_PATH.is_file():
        try:
            cfg = json.loads(ROLE_PATH.read_text(encoding="utf-8"))
            role = str(cfg.get("role") or "").strip().lower()
            if role in ROLE_CAPS:
                return role
        except json.JSONDecodeError:
            pass
    return str(os.environ.get("NR2_WORKSTATION_ROLE", "office_manager")).strip().lower() or "office_manager"


def capabilities_for_role(role: str | None = None) -> list[str]:
    r = str(role or current_role()).lower()
    caps = ROLE_CAPS.get(r, ROLE_CAPS["front_desk"])
    if "*" in caps:
        return sorted({c for s in ROLE_CAPS.values() for c in s if c != "*"} | {"*"})
    return sorted(caps)


def has_capability(cap: str, role: str | None = None) -> bool:
    r = str(role or current_role()).lower()
    caps = ROLE_CAPS.get(r, set())
    return "*" in caps or cap in caps


def require_role(*roles: str) -> Callable:
    allowed = {str(r).lower() for r in roles}

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any):
            role = current_role()
            if role != "admin" and role not in allowed:
                bottle.abort(403, json.dumps({"ok": False, "error": "insufficient_privilege", "role": role}))
            return func(*args, **kwargs)

        return wrapper

    return decorator


def require_capability(cap: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any):
            if not has_capability(cap):
                bottle.abort(
                    403,
                    json.dumps({"ok": False, "error": "capability_rejected", "capability": cap, "role": current_role()}),
                )
            return func(*args, **kwargs)

        return wrapper

    return decorator


def app_info_rbac() -> dict[str, Any]:
    role = current_role()
    return {"role": role, "capabilities": capabilities_for_role(role)}


def evaluate_writeoff_approval(
    *,
    amount_usd: float,
    role: str | None = None,
    prior_approvals: list[str] | None = None,
) -> dict[str, Any]:
    """Approval chain: office_manager tier1 up to WRITEOFF_TIER1_MAX; dual dentist+OM above."""
    amt = abs(float(amount_usd or 0))
    r = str(role or current_role()).lower()
    prior = {str(a).lower() for a in (prior_approvals or [])}
    if r == "admin" or has_capability("*", r):
        return {"ok": True, "allowed": True, "chain": "admin_override", "amountUsd": amt}
    if amt <= WRITEOFF_TIER1_MAX_USD:
        if has_capability("approve_writeoff_tier1", r) or has_capability("approve_writeoff_tier2", r):
            return {"ok": True, "allowed": True, "chain": "tier1_single", "amountUsd": amt}
        return {
            "ok": True,
            "allowed": False,
            "chain": "tier1_single",
            "requiredCapability": "approve_writeoff_tier1",
            "amountUsd": amt,
        }
    if amt >= WRITEOFF_DUAL_APPROVAL_MIN_USD:
        need = {"office_manager", "dentist"}
        have = prior | {r}
        if need.issubset(have):
            return {"ok": True, "allowed": True, "chain": "dual_approval", "amountUsd": amt}
        missing = sorted(need - have)
        return {
            "ok": True,
            "allowed": False,
            "chain": "dual_approval",
            "missingRoles": missing,
            "amountUsd": amt,
            "message": f"Write-off ${amt:.2f} requires office_manager and dentist approval.",
        }
    if has_capability("approve_writeoff_tier2", r):
        return {"ok": True, "allowed": True, "chain": "tier2_single", "amountUsd": amt}
    return {"ok": True, "allowed": False, "chain": "tier2_single", "requiredCapability": "approve_writeoff_tier2", "amountUsd": amt}
