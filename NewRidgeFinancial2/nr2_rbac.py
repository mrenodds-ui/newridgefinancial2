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
    },
    "dentist": {"read_all", "write_clinical", "approve_closeout", "read_financial"},
    "admin": {"*"},
}


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
