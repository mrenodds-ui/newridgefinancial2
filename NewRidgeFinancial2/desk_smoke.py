"""Desk smoke / confidence loop for NR2 shadow period-close.

Validates:
- period-close status present
- money beams + dataBeamHash
- Force Close availability vs lasers/stalled
- beam desk proof (in-process + optional HTTP /api/hal/tools/beam-verify)

Writes app_data/nr2/ops/desk_smoke_log.jsonl. SoftDent write-back forbidden. empty ≠ $0.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
OPS_DIR = REPO_ROOT / "app_data" / "nr2" / "ops"
SMOKE_LOG_PATH = OPS_DIR / "desk_smoke_log.jsonl"
SMOKE_STATE_PATH = OPS_DIR / "desk_smoke_state.json"


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _ensure_ops() -> None:
    OPS_DIR.mkdir(parents=True, exist_ok=True)


def _append_log(row: dict[str, Any]) -> None:
    _ensure_ops()
    with SMOKE_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, default=str) + "\n")


def _write_state(row: dict[str, Any]) -> None:
    _ensure_ops()
    SMOKE_STATE_PATH.write_text(json.dumps(row, indent=2, default=str) + "\n", encoding="utf-8")


def last_smoke_state() -> dict[str, Any] | None:
    if not SMOKE_STATE_PATH.is_file():
        return None
    try:
        raw = json.loads(SMOKE_STATE_PATH.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else None
    except Exception:
        return None


def _http_get(path: str, *, base: str | None = None, timeout: float = 20.0) -> dict[str, Any]:
    root = (base or os.getenv("NR2_BROWSER", "https://127.0.0.1:8765")).rstrip("/")
    url = root + path
    ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(url, context=ctx, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8", "replace"))
            return {"ok": True, "status": int(resp.status), "data": body}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": int(exc.code), "error": f"HTTP {exc.code}", "data": None}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "status": 0, "error": f"{type(exc).__name__}: {exc}"[:200], "data": None}


def run_desk_smoke(
    *,
    probe_http: bool = True,
    http_base: str | None = None,
    readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run desk confidence checks. ok=True only when all critical checks pass."""
    checks: list[dict[str, Any]] = []
    failures: list[str] = []

    # --- period close ---
    try:
        from daily_closeout import force_close_available, period_close_status

        close = period_close_status()
    except Exception as exc:  # noqa: BLE001
        close = {"ok": False, "error": str(exc)[:200]}
    close_ok = bool(close.get("ok")) and bool(close.get("status"))
    checks.append(
        {
            "id": "period_close_status",
            "ok": close_ok,
            "status": close.get("status"),
            "beamHash": close.get("beamHash"),
            "completedAt": close.get("completedAt"),
        }
    )
    if not close_ok:
        failures.append("period_close_status")

    # --- readiness / lasers ---
    ready = readiness
    if not isinstance(ready, dict):
        try:
            from import_diagnostics import assess_import_readiness
            from daily_closeout import merge_period_close_into_readiness

            ready = assess_import_readiness()
            ready = merge_period_close_into_readiness(ready)
        except Exception as exc:  # noqa: BLE001
            ready = {"ok": False, "error": str(exc)[:200], "blocking": [], "alignmentLasers": {"red": True}}

    lasers = ready.get("alignmentLasers") if isinstance(ready.get("alignmentLasers"), dict) else {}
    lasers_red = lasers.get("red") is True or bool(ready.get("blocking"))
    try:
        from daily_closeout import force_close_available

        fc_available = force_close_available(ready, status=str(close.get("status") or ""))
    except Exception:
        fc_available = False
    # When healthy (green + idle/completed), Force Close should be unavailable.
    # When troubled (red/stalled/blocked), Force Close should be available.
    close_status = str(close.get("status") or "").lower()
    expect_force = lasers_red or close_status in ("stalled", "blocked")
    force_ok = bool(fc_available) == bool(expect_force)
    checks.append(
        {
            "id": "force_close_availability",
            "ok": force_ok,
            "available": bool(fc_available),
            "expectedAvailable": bool(expect_force),
            "lasersRed": bool(lasers_red),
            "closeStatus": close_status,
        }
    )
    if not force_ok:
        failures.append("force_close_availability")

    # --- money beams ---
    try:
        from hal_brain_tools import money_beam_attestation

        beams = money_beam_attestation(readiness=ready)
    except Exception as exc:  # noqa: BLE001
        beams = {"ok": False, "error": str(exc)[:200]}
    data_hash = str(beams.get("dataBeamHash") or "")
    beam_hash = str(beams.get("beamHash") or "")
    beams_ok = bool(beams.get("ok")) and bool(data_hash) and bool(beam_hash)
    checks.append(
        {
            "id": "money_beams",
            "ok": beams_ok,
            "beamHash": beam_hash or None,
            "dataBeamHash": data_hash or None,
            "softdentDisplay": (beams.get("softdent") or {}).get("display")
            if isinstance(beams.get("softdent"), dict)
            else None,
            "qbDisplay": (beams.get("quickbooks") or {}).get("display")
            if isinstance(beams.get("quickbooks"), dict)
            else None,
        }
    )
    if not beams_ok:
        failures.append("money_beams")

    # --- beam desk proof (in-process — works even if HTTP route not yet reloaded) ---
    try:
        from hal_brain_tools import beam_desk_proof

        proof = beam_desk_proof(readiness=ready)
    except Exception as exc:  # noqa: BLE001
        proof = {"ok": False, "error": str(exc)[:200], "deskProof": "ERROR"}
    proof_status = str(proof.get("deskProof") or "")
    # MATCH or NO CLOSE HASH (no close yet) are acceptable; MISMATCH / ERROR fail.
    proof_ok = bool(proof.get("ok")) and proof_status in ("MATCH", "NO CLOSE HASH")
    checks.append(
        {
            "id": "beam_desk_proof",
            "ok": proof_ok,
            "deskProof": proof_status,
            "liveDataBeamHash": (proof.get("live") or {}).get("dataBeamHash")
            if isinstance(proof.get("live"), dict)
            else None,
            "closeDataBeamHash": (proof.get("periodClose") or {}).get("dataBeamHash")
            if isinstance(proof.get("periodClose"), dict)
            else None,
        }
    )
    if not proof_ok:
        failures.append("beam_desk_proof")

    # --- HTTP beam-verify probe (detect stale server process) ---
    http_probe: dict[str, Any] | None = None
    if probe_http:
        http_probe = _http_get("/api/hal/tools/beam-verify", base=http_base)
        http_ok = bool(http_probe.get("ok")) and int(http_probe.get("status") or 0) == 200
        checks.append(
            {
                "id": "beam_verify_http",
                "ok": http_ok,
                "status": http_probe.get("status"),
                "error": http_probe.get("error"),
                "hint": None
                if http_ok
                else "Restart NR2 browser/workstation server to load /api/hal/tools/beam-verify",
            }
        )
        if not http_ok:
            failures.append("beam_verify_http")

    # Patient attest is MATCH-gated (sibling of laser-gated period Force Close).
    patient_attest_eligible = proof_status == "MATCH"
    checks.append(
        {
            "id": "patient_attest_eligible",
            "ok": True,
            "eligible": patient_attest_eligible,
            "deskProof": proof_status,
            "note": "Informational — does not fail smoke; period forceCloseAvailable stays laser-gated.",
        }
    )

    overall = len(failures) == 0
    row = {
        "ok": overall,
        "emptyNotZero": True,
        "at": _iso_now(),
        "status": "GREEN" if overall else "RED",
        "failures": failures,
        "checks": checks,
        "periodClose": {
            "status": close.get("status"),
            "beamHash": close.get("beamHash"),
            "completedAt": close.get("completedAt"),
        },
        "deskProof": proof_status,
        "dataBeamHash": data_hash or None,
        "beamHash": beam_hash or None,
        "forceCloseAvailable": bool(fc_available),
        "patientAttestEligible": patient_attest_eligible,
        "logPath": str(SMOKE_LOG_PATH),
        "buildHint": None,
    }
    try:
        build_path = Path(__file__).resolve().parent / "nr2-build.json"
        if build_path.is_file():
            row["buildHint"] = json.loads(build_path.read_text(encoding="utf-8")).get("BUILD_ID")
    except Exception:
        pass

    _append_log(row)
    _write_state(
        {
            "ok": overall,
            "status": row["status"],
            "at": row["at"],
            "failures": failures,
            "deskProof": proof_status,
            "dataBeamHash": data_hash or None,
            "forceCloseAvailable": bool(fc_available),
            "patientAttestEligible": patient_attest_eligible,
        }
    )
    return row


if __name__ == "__main__":
    import sys

    probe = "--no-http" not in sys.argv
    result = run_desk_smoke(probe_http=probe)
    print(json.dumps(result, indent=2, default=str))
    raise SystemExit(0 if result.get("ok") else 1)
