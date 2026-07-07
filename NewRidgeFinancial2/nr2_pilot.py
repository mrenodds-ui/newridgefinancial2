"""Operator pilot phase gates — Moonshot financial report shadow/cutover criteria."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent

PILOT_STATE_PATH = REPO_ROOT / "app_data" / "nr2" / "pilot_phase.json"
CUTOVER_ATTESTATION_PATH = REPO_ROOT / "app_data" / "nr2" / "pilot_cutover.json"

VALID_PHASES = frozenset({"shadow", "supervised", "cutover"})
DEFAULT_PHASE = "shadow"

# Moonshot operational guidance: parallel SoftDent reconcile before system-of-record cutover.
DEFAULT_MIN_SHADOW_DAYS = 30
DEFAULT_MIN_SUPERVISED_DAYS = 30


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def _days_since(value: str | None) -> int | None:
    started = _parse_ts(value)
    if not started:
        return None
    delta = datetime.now(timezone.utc) - started
    return max(0, delta.days)


def _min_shadow_days() -> int:
    raw = os.environ.get("NR2_PILOT_MIN_SHADOW_DAYS", "").strip()
    if raw.isdigit():
        return max(0, int(raw))
    return DEFAULT_MIN_SHADOW_DAYS


def _min_supervised_days() -> int:
    raw = os.environ.get("NR2_PILOT_MIN_SUPERVISED_DAYS", "").strip()
    if raw.isdigit():
        return max(0, int(raw))
    return DEFAULT_MIN_SUPERVISED_DAYS


def _skip_day_checks() -> bool:
    return os.environ.get("NR2_PILOT_SKIP_DAY_CHECKS", "").strip().lower() in {"1", "true", "yes", "on"}


def load_pilot_state() -> dict[str, Any]:
    if not PILOT_STATE_PATH.is_file():
        return {"phase": DEFAULT_PHASE}
    try:
        data = json.loads(PILOT_STATE_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"phase": DEFAULT_PHASE}
        phase = str(data.get("phase") or DEFAULT_PHASE).strip().lower()
        if phase not in VALID_PHASES:
            phase = DEFAULT_PHASE
        return {**data, "phase": phase}
    except (OSError, json.JSONDecodeError):
        return {"phase": DEFAULT_PHASE}


def save_pilot_state(state: dict[str, Any]) -> dict[str, Any]:
    phase = str(state.get("phase") or DEFAULT_PHASE).strip().lower()
    if phase not in VALID_PHASES:
        raise ValueError(f"invalid pilot phase: {phase}")
    payload = {**state, "phase": phase, "updated_at_utc": _utc_now()}
    PILOT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PILOT_STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def resolve_pilot_phase() -> str:
    env = os.environ.get("NR2_PILOT_PHASE", "").strip().lower()
    if env in VALID_PHASES:
        return env
    return str(load_pilot_state().get("phase") or DEFAULT_PHASE)


def is_system_of_record() -> bool:
    return resolve_pilot_phase() == "cutover"


def load_cutover_attestation() -> dict[str, Any] | None:
    if not CUTOVER_ATTESTATION_PATH.is_file():
        return None
    try:
        data = json.loads(CUTOVER_ATTESTATION_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def pilot_info() -> dict[str, Any]:
    state = load_pilot_state()
    phase = resolve_pilot_phase()
    attestation = load_cutover_attestation()
    shadow_days = _days_since(str(state.get("shadow_started_at") or ""))
    supervised_days = _days_since(str(state.get("supervised_started_at") or ""))
    return {
        "phase": phase,
        "systemOfRecord": phase == "cutover",
        "shadowStartedAt": state.get("shadow_started_at"),
        "supervisedStartedAt": state.get("supervised_started_at"),
        "cutoverAt": state.get("cutover_at") or (attestation or {}).get("signed_at_utc"),
        "shadowDaysElapsed": shadow_days,
        "supervisedDaysElapsed": supervised_days,
        "minShadowDays": _min_shadow_days(),
        "minSupervisedDays": _min_supervised_days(),
        "cutoverAttested": bool(attestation and attestation.get("signed_by")),
        "attestationSignedBy": (attestation or {}).get("signed_by"),
    }


def ensure_phase_started(phase: str) -> dict[str, Any]:
    phase = phase.strip().lower()
    if phase not in VALID_PHASES:
        raise ValueError(f"invalid pilot phase: {phase}")
    state = load_pilot_state()
    now = _utc_now()
    if phase == "shadow" and not state.get("shadow_started_at"):
        state["shadow_started_at"] = now
    if phase == "supervised":
        if not state.get("shadow_started_at"):
            state["shadow_started_at"] = now
        if not state.get("supervised_started_at"):
            state["supervised_started_at"] = now
    if phase == "cutover":
        if not state.get("shadow_started_at"):
            state["shadow_started_at"] = now
        if not state.get("supervised_started_at"):
            state["supervised_started_at"] = now
        state["cutover_at"] = now
    state["phase"] = phase
    return save_pilot_state(state)


def check_posting_gate(operation: str) -> dict[str, Any] | None:
    """Return an error payload when the pilot phase blocks a posting mutation."""
    phase = resolve_pilot_phase()
    op = str(operation or "").strip().lower()

    if phase == "shadow":
        if op in {"posting_queue_export_approved", "posting_queue_bulk_review"}:
            return {
                "ok": False,
                "error": "pilot_phase_blocked",
                "pilotPhase": phase,
                "detail": "Shadow mode: export and bulk approve stay disabled until supervised pilot.",
            }
    if op == "posting_queue_export_approved" and phase != "cutover":
        return {
            "ok": False,
            "error": "pilot_phase_blocked",
            "pilotPhase": phase,
            "detail": "Approved posting export is allowed only after Phase 3 cutover attestation.",
        }
    return None


def cutover_readiness_checks() -> dict[str, Any]:
    """Validator checks aligned with Moonshot conditional-approve pilot guidance."""
    checks: list[dict[str, Any]] = []

    def _check(name: str, ok: bool, detail: str = "") -> dict[str, Any]:
        return {"name": name, "ok": bool(ok), "detail": detail}

    from scripts.validate_supervised_pilot import run_checks as supervised_checks

    supervised = supervised_checks()
    checks.append(
        _check(
            "supervised_pilot",
            bool(supervised.get("ok")),
            f"{supervised.get('passed')}/{supervised.get('total')}",
        )
    )

    state = load_pilot_state()
    phase = resolve_pilot_phase()
    checks.append(_check("pilot_phase_cutover", phase == "cutover", phase))

    attestation = load_cutover_attestation()
    signed_by = str((attestation or {}).get("signed_by") or "").strip()
    checks.append(_check("cutover_attestation", bool(signed_by), signed_by or "missing pilot_cutover.json"))

    role_ok = False
    role_path = REPO_ROOT / "app_data" / "nr2" / "workstation_role.json"
    if role_path.is_file():
        try:
            role = str(json.loads(role_path.read_text(encoding="utf-8")).get("role") or "")
            role_ok = role in {"office_manager", "admin", "dentist"}
            checks.append(_check("cutover_role", role_ok, role or "missing"))
        except json.JSONDecodeError:
            checks.append(_check("cutover_role", False, "invalid workstation_role.json"))
    else:
        checks.append(_check("cutover_role", False, "workstation_role.json missing"))

    if not _skip_day_checks():
        shadow_days = _days_since(str(state.get("shadow_started_at") or ""))
        supervised_days = _days_since(str(state.get("supervised_started_at") or ""))
        min_shadow = _min_shadow_days()
        min_supervised = _min_supervised_days()
        checks.append(
            _check(
                "shadow_duration",
                shadow_days is not None and shadow_days >= min_shadow,
                f"{shadow_days or 0}/{min_shadow} days",
            )
        )
        checks.append(
            _check(
                "supervised_duration",
                supervised_days is not None and supervised_days >= min_supervised,
                f"{supervised_days or 0}/{min_supervised} days",
            )
        )
    else:
        checks.append(_check("shadow_duration", True, "NR2_PILOT_SKIP_DAY_CHECKS=1"))
        checks.append(_check("supervised_duration", True, "NR2_PILOT_SKIP_DAY_CHECKS=1"))

    optional = set()
    required_ok = all(c["ok"] for c in checks if c["name"] not in optional)
    return {
        "ok": required_ok,
        "phase": "cutover",
        "systemOfRecord": phase == "cutover" and required_ok,
        "passed": sum(1 for c in checks if c["ok"]),
        "total": len(checks),
        "checks": checks,
        "pilot": pilot_info(),
    }
