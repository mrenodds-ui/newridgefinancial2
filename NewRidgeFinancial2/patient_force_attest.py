"""Patient-level OM attest review (sibling of period Force Close).

SoftDent READ-ONLY. Gate on deskProof MATCH (not laser-red).
empty ≠ $0. Does not call force_period_close or SoftDent write-back.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
OPS_DIR = REPO_ROOT / "app_data" / "nr2" / "ops"
ATTEST_LOG_PATH = OPS_DIR / "patient_force_attest_log.jsonl"


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _ensure_ops() -> None:
    OPS_DIR.mkdir(parents=True, exist_ok=True)


def _append_attest_log(entry: dict[str, Any]) -> None:
    _ensure_ops()
    with ATTEST_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, default=str) + "\n")


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def patient_attest_eligible(*, readiness: dict[str, Any] | None = None) -> dict[str, Any]:
    """Eligible when live SoftDent/QB dataBeamHash MATCHES last period-close snapshot."""
    try:
        from hal_brain_tools import beam_desk_proof

        proof = beam_desk_proof(readiness=readiness)
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "eligible": False,
            "deskProof": "ERROR",
            "error": str(exc)[:200],
            "emptyNotZero": True,
        }
    desk_proof = str(proof.get("deskProof") or "")
    eligible = bool(proof.get("ok")) and desk_proof == "MATCH"
    live = proof.get("live") if isinstance(proof.get("live"), dict) else {}
    return {
        "ok": True,
        "eligible": eligible,
        "deskProof": desk_proof,
        "dataBeamHash": live.get("dataBeamHash") or proof.get("dataBeamHash"),
        "beamHash": live.get("beamHash") or proof.get("beamHash"),
        "emptyNotZero": True,
        "note": "Patient attest requires deskProof MATCH (period Force Close stays laser-gated).",
    }


def last_patient_attest(patient_hash: str) -> dict[str, Any] | None:
    ph = str(patient_hash or "").replace("#", "").strip().lower()
    if not ph or not ATTEST_LOG_PATH.is_file():
        return None
    try:
        lines = [
            ln.strip()
            for ln in ATTEST_LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
            if ln.strip()
        ]
    except OSError:
        return None
    for raw in reversed(lines):
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        row_ph = str(row.get("patientHash") or "").replace("#", "").strip().lower()
        if row_ph == ph or row_ph.startswith(ph) or ph.startswith(row_ph[:4]):
            return row
    return None


def patient_attest_status_today(patient_hash: str) -> dict[str, Any]:
    last = last_patient_attest(patient_hash)
    if not last:
        return {"ok": True, "attestedToday": False, "attest": None, "emptyNotZero": True}
    ts = str(last.get("timestamp") or "")
    day = ts[:10] if len(ts) >= 10 else ""
    attested = day == _today_utc()
    return {
        "ok": True,
        "attestedToday": attested,
        "attest": {
            "timestamp": last.get("timestamp"),
            "actor": last.get("actor"),
            "patientHash": last.get("patientHash"),
            "deskProof": last.get("deskProof"),
            "dataBeamHash": last.get("dataBeamHash"),
            "accountBalanceDisplay": last.get("accountBalanceDisplay"),
        }
        if attested
        else None,
        "emptyNotZero": True,
    }


def force_attest_patient(
    patient_id: str,
    *,
    actor: str = "optical-om",
    readiness: dict[str, Any] | None = None,
    session_id: str = "",
) -> dict[str, Any]:
    """Record OM review attestation for one SoftDent patient (read-only)."""
    from patient_dossier import patient_hash
    from om_patient_dossier import get_patient_dossier_mini

    pid = str(patient_id or "").strip()
    if not pid:
        return {"ok": False, "error": "patient_id_required", "emptyNotZero": True}

    gate = patient_attest_eligible(readiness=readiness)
    if not gate.get("eligible"):
        return {
            "ok": False,
            "error": "desk_proof_not_match",
            "deskProof": gate.get("deskProof"),
            "eligible": False,
            "status": 409,
            "hint": "VERIFY BEAM / reconcile first — patient attest requires MATCH",
            "emptyNotZero": True,
            "live": gate,
        }

    mini = get_patient_dossier_mini(pid)
    if not isinstance(mini, dict) or not mini.get("ok"):
        return {
            "ok": False,
            "error": "mini_dossier_unavailable",
            "detail": (mini or {}).get("error") if isinstance(mini, dict) else None,
            "emptyNotZero": True,
            "status": 404,
        }

    ph = str(mini.get("patientHash") or patient_hash(pid)).replace("#", "")
    bal = mini.get("accountBalance")
    if bal is None or bal == "" or str(bal).lower() in ("unavailable", "no signal", "n/a"):
        bal_disp = "unavailable"
    else:
        bal_disp = str(bal)

    already = patient_attest_status_today(ph)
    if already.get("attestedToday"):
        return {
            "ok": True,
            "closed": True,
            "idempotent": True,
            "patientHash": ph,
            "deskProof": gate.get("deskProof"),
            "dataBeamHash": gate.get("dataBeamHash"),
            "beamHash": gate.get("beamHash"),
            "accountBalanceDisplay": bal_disp,
            "attest": already.get("attest"),
            "shadowMode": True,
            "systemOfRecord": False,
            "emptyNotZero": True,
            "readOnly": True,
        }

    row = {
        "timestamp": _iso_now(),
        "actor": str(actor or "optical-om").strip() or "optical-om",
        "patientHash": ph,
        "sessionId": str(session_id or "").strip() or None,
        "deskProof": gate.get("deskProof"),
        "dataBeamHash": gate.get("dataBeamHash"),
        "beamHash": gate.get("beamHash"),
        "miniOk": True,
        "accountBalanceDisplay": bal_disp,
        "initials": mini.get("initials"),
        "shadowMode": True,
        "systemOfRecord": False,
        "emptyNotZero": True,
        "readOnly": True,
    }
    try:
        _append_attest_log(row)
    except OSError as exc:
        return {"ok": False, "error": f"log_write_failed: {exc}"[:200], "emptyNotZero": True}

    return {
        "ok": True,
        "closed": True,
        "idempotent": False,
        "patientHash": ph,
        "deskProof": row["deskProof"],
        "dataBeamHash": row["dataBeamHash"],
        "beamHash": row["beamHash"],
        "accountBalanceDisplay": bal_disp,
        "attest": {
            "timestamp": row["timestamp"],
            "actor": row["actor"],
            "patientHash": ph,
            "deskProof": row["deskProof"],
            "dataBeamHash": row["dataBeamHash"],
            "accountBalanceDisplay": bal_disp,
        },
        "shadowMode": True,
        "systemOfRecord": False,
        "emptyNotZero": True,
        "readOnly": True,
        "logPath": str(ATTEST_LOG_PATH),
    }
