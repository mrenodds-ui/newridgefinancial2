"""Desk smoke / confidence loop for NR2 shadow period-close.

Validates:
- period-close status present
- money beams + dataBeamHash
- Force Close availability vs lasers/stalled
- beam desk proof (in-process + optional HTTP /api/hal/tools/beam-verify)
- Mon–Thu → HAL patient-context bind → “this patient” / unbound intents

Writes app_data/nr2/ops/desk_smoke_log.jsonl. SoftDent write-back forbidden. empty ≠ $0.
"""

from __future__ import annotations

import json
import os
import ssl
import sys
import types
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

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


def _with_smoke_rbac(fn: Callable[[], Any]) -> Any:
    """Allow in-process dossier policy during smoke when bottle/RBAC is unavailable."""
    try:
        from nr2_rbac import has_capability  # noqa: F401

        return fn()
    except Exception:
        fake = types.ModuleType("nr2_rbac")
        fake.has_capability = lambda *_a, **_k: True  # type: ignore[attr-defined]
        fake.current_role = lambda: "office_manager"  # type: ignore[attr-defined]
        prev = sys.modules.get("nr2_rbac")
        sys.modules["nr2_rbac"] = fake
        try:
            return fn()
        finally:
            if prev is None:
                sys.modules.pop("nr2_rbac", None)
            else:
                sys.modules["nr2_rbac"] = prev


def smoke_patient_context_path() -> dict[str, Any]:
    """Mon–Thu slot → bind → this-patient / unbound policy (PHI = hash/initials only)."""
    from patient_dossier import (
        format_hal_patient_summary_reply,
        patient_hash,
        query_refers_to_bound_patient,
        query_touches_patient_summary,
    )
    from hal_session_store import (
        active_patient_context,
        create_session,
        set_patient_context,
    )

    detail: dict[str, Any] = {
        "detectionOk": False,
        "bindOk": False,
        "unboundOk": False,
        "boundOk": False,
        "monThuOk": False,
        "emptyNotZero": True,
        "phiSafe": True,
        "initials": None,
        "patientHash": None,
        "unboundIntent": None,
        "boundIntent": None,
        "monThuDays": 0,
        "error": None,
    }

    try:
        detection_ok = query_refers_to_bound_patient("Tell me about this patient") and query_touches_patient_summary(
            "What's the copay for this patient?"
        )
        detail["detectionOk"] = bool(detection_ok)
        if not detection_ok:
            return {"ok": False, "covered": False, **detail, "error": "this_patient_detection_failed"}

        pid = ""
        initials = "SM"
        ph = "SMOK"
        mon_thu_days = 0
        try:
            from nr2_softdent_daily import appointments_range_snapshot, monday_of_week_iso

            snap = appointments_range_snapshot(monday_of_week_iso(), days=4)
            days = snap.get("days") if isinstance(snap, dict) else None
            if isinstance(days, list):
                mon_thu_days = len(days)
                detail["monThuDays"] = mon_thu_days
                detail["monThuOk"] = mon_thu_days >= 1
                for day in days:
                    if not isinstance(day, dict):
                        continue
                    for slot in day.get("slots") or []:
                        if not isinstance(slot, dict):
                            continue
                        cand = str(slot.get("patientId") or "").strip()
                        if cand:
                            pid = cand
                            initials = str(slot.get("initials") or initials)[:8]
                            ph = str(slot.get("patientHash") or patient_hash(pid)).replace("#", "")[:4]
                            break
                    if pid:
                        break
        except Exception as exc:  # noqa: BLE001
            detail["monThuError"] = f"{type(exc).__name__}: {exc}"[:160]

        if not pid:
            pid = "desk-smoke-patient"
            ph = patient_hash(pid)
            initials = "DS"
            detail["monThuOk"] = detail["monThuOk"] or mon_thu_days >= 1

        detail["initials"] = initials
        detail["patientHash"] = ph

        created = create_session(meta={"source": "desk_smoke", "purpose": "this_patient"})
        sid = str(created.get("sessionId") or "").strip()
        if not sid:
            return {"ok": False, "covered": False, **detail, "error": "session_create_failed"}

        bound = set_patient_context(
            sid,
            patient_id=pid,
            patient_hash=ph,
            initials=initials,
        )
        ctx = active_patient_context(sid)
        bind_ok = bool(bound.get("ok")) and isinstance(ctx, dict) and str(ctx.get("patientId") or "") == pid
        detail["bindOk"] = bind_ok
        # Smoke trail keeps SoftDent id server-side; public fields are hash/initials only.
        detail["phiSafe"] = bool(ph) and bool(initials) and " " not in str(initials)
        if not bind_ok:
            return {"ok": False, "covered": False, **detail, "error": "patient_context_bind_failed"}

        def _unbound() -> dict[str, str]:
            return format_hal_patient_summary_reply(
                "What's the copay for this patient?",
                session_id="desk-smoke-missing-session",
            )

        unbound = _with_smoke_rbac(_unbound)
        unbound_intent = str(unbound.get("intent") or "")
        detail["unboundIntent"] = unbound_intent
        detail["unboundOk"] = unbound_intent == "policy:patient-summary-unbound"
        if not detail["unboundOk"]:
            return {
                "ok": False,
                "covered": False,
                **detail,
                "error": f"unbound_intent={unbound_intent or 'missing'}",
            }

        try:
            from patient_dossier import _RATE

            _RATE.clear()
        except Exception:
            pass

        def _bound() -> dict[str, str]:
            return format_hal_patient_summary_reply(
                "What is the insurance for this patient?",
                session_id=sid,
            )

        bound_reply = _with_smoke_rbac(_bound)
        bound_intent = str(bound_reply.get("intent") or "")
        bound_text = str(bound_reply.get("text") or "")
        detail["boundIntent"] = bound_intent
        # Bound path proves session resolution; rate-limit is acceptable after bind.
        bound_ok = bound_intent in (
            "policy:patient-summary-bound",
            "policy:patient-summary-rate",
        )
        if bound_intent == "policy:patient-summary-bound":
            bound_ok = "Using bound patient context" in bound_text
        detail["boundOk"] = bound_ok
        if bound_intent == "policy:patient-summary-bound":
            compact = bound_text.replace(" ", "")
            detail["emptyNotZero"] = "empty≠$0" in compact or "empty≠$0" in bound_text
            if not detail["emptyNotZero"]:
                return {
                    "ok": False,
                    "covered": False,
                    **detail,
                    "error": "missing_empty_ne_zero_footer",
                }

        if not bound_ok:
            return {
                "ok": False,
                "covered": False,
                **detail,
                "error": f"bound_intent={bound_intent or 'missing'}",
            }

        covered = bool(
            detail["detectionOk"]
            and detail["bindOk"]
            and detail["unboundOk"]
            and detail["boundOk"]
            and detail["emptyNotZero"]
            and detail["phiSafe"]
        )
        return {"ok": covered, "covered": covered, **detail}
    except Exception as exc:  # noqa: BLE001
        detail["error"] = f"{type(exc).__name__}: {exc}"[:240]
        return {"ok": False, "covered": False, **detail}


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

        # Trellis tomorrow panel — detect stale server missing the route
        tr_probe = _http_get("/api/trellis/tomorrow-insurance", base=http_base)
        tr_ok = bool(tr_probe.get("ok")) and int(tr_probe.get("status") or 0) == 200
        tr_data = tr_probe.get("data") if isinstance(tr_probe.get("data"), dict) else {}
        checks.append(
            {
                "id": "trellis_tomorrow_http",
                "ok": tr_ok,
                "status": tr_probe.get("status"),
                "hasData": tr_data.get("hasData") if tr_ok else None,
                "targetDate": tr_data.get("targetDate") if tr_ok else None,
                "error": tr_probe.get("error"),
                "hint": None
                if tr_ok
                else "Restart NR2 browser/workstation server to load /api/trellis/tomorrow-insurance",
            }
        )
        if not tr_ok:
            failures.append("trellis_tomorrow_http")

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

    # --- Mon–Thu → bind → this-patient / unbound (patient-context beam path) ---
    try:
        patient_ctx = smoke_patient_context_path()
    except Exception as exc:  # noqa: BLE001
        patient_ctx = {"ok": False, "covered": False, "error": str(exc)[:200]}
    patient_ctx_ok = bool(patient_ctx.get("ok")) and bool(patient_ctx.get("covered"))
    checks.append(
        {
            "id": "this_patient_shortcut",
            "ok": patient_ctx_ok,
            "covered": bool(patient_ctx.get("covered")),
            "detectionOk": patient_ctx.get("detectionOk"),
            "bindOk": patient_ctx.get("bindOk"),
            "unboundOk": patient_ctx.get("unboundOk"),
            "boundOk": patient_ctx.get("boundOk"),
            "monThuOk": patient_ctx.get("monThuOk"),
            "unboundIntent": patient_ctx.get("unboundIntent"),
            "boundIntent": patient_ctx.get("boundIntent"),
            "initials": patient_ctx.get("initials"),
            "patientHash": patient_ctx.get("patientHash"),
            "emptyNotZero": patient_ctx.get("emptyNotZero", True),
            "deskProof": proof_status,
            "forceCloseAvailable": bool(fc_available),
            "error": patient_ctx.get("error"),
        }
    )
    if not patient_ctx_ok:
        failures.append("this_patient_shortcut")

    # --- Mon–Thu appt_time coverage (honest — only when extract has times) ---
    try:
        from nr2_softdent_daily import appointments_range_snapshot, monday_of_week_iso

        snap = appointments_range_snapshot(monday_of_week_iso(), days=4)
        slots: list[dict[str, Any]] = []
        for day in snap.get("days") or []:
            if isinstance(day, dict):
                for slot in day.get("slots") or []:
                    if isinstance(slot, dict):
                        slots.append(slot)
        with_time = sum(1 for s in slots if str(s.get("time") or "").strip() not in ("", "—"))
        total = len(slots)
        ratio = (with_time / total) if total else 0.0
        # Soft threshold: empty week is ok; when slots exist expect majority times (Sensei lane).
        time_ok = total == 0 or ratio >= 0.5
        checks.append(
            {
                "id": "mon_thu_appt_time",
                "ok": time_ok,
                "slotCount": total,
                "withTime": with_time,
                "ratio": round(ratio, 3),
                "apptTimeColumn": bool(snap.get("apptTimeColumn"))
                if isinstance(snap, dict)
                else None,
                "note": "Informational floor 50% when slots exist; empty≠invent 09:00.",
            }
        )
        if not time_ok:
            failures.append("mon_thu_appt_time")
        row_time_covered = time_ok
    except Exception as exc:  # noqa: BLE001
        checks.append(
            {
                "id": "mon_thu_appt_time",
                "ok": False,
                "error": str(exc)[:200],
            }
        )
        failures.append("mon_thu_appt_time")
        row_time_covered = False

    # Morning confidence: GREEN+MATCH is healthy; period Force Close stays laser-gated.
    # Trellis withBenefits is informational only (no $) — does not fail smoke / Force Close.
    trellis_benefits: dict[str, Any] = {
        "ok": False,
        "hasReport": False,
        "patients": None,
        "withBenefits": None,
        "statusOnly": None,
        "targetDate": None,
        "note": "counts only · empty ≠ $0 · board PHI stays initials+hash",
    }
    try:
        from datetime import date as _date
        from datetime import timedelta as _timedelta

        from nr2_trellis_nightly import eligibility_report_snapshot

        # Prefer tomorrow (Mon–Thu huddle target); fall back to today.
        today = _date.today()
        for offset in (1, 0, 2, 3):
            day = today + _timedelta(days=offset)
            if day.weekday() >= 5:  # skip Sat/Sun
                continue
            snap = eligibility_report_snapshot(target_date=day.isoformat())
            if isinstance(snap, dict) and snap.get("hasReport"):
                trellis_benefits = {
                    "ok": True,
                    "hasReport": True,
                    "patients": snap.get("patients"),
                    "withBenefits": snap.get("withBenefits"),
                    "statusOnly": snap.get("statusOnly"),
                    "targetDate": snap.get("targetDate") or day.isoformat(),
                    "reportUrl": snap.get("reportUrl"),
                    "note": "counts only · empty ≠ $0 · board PHI stays initials+hash",
                }
                break
            if isinstance(snap, dict) and trellis_benefits.get("targetDate") is None:
                trellis_benefits["targetDate"] = snap.get("targetDate") or day.isoformat()
                trellis_benefits["patients"] = snap.get("patients")
                trellis_benefits["withBenefits"] = snap.get("withBenefits")
                trellis_benefits["statusOnly"] = snap.get("statusOnly")
                trellis_benefits["ok"] = bool(snap.get("ok"))
    except Exception as exc:  # noqa: BLE001
        trellis_benefits["error"] = str(exc)[:200]

    morning_confidence = {
        "deskProof": proof_status,
        "status": "GREEN" if len(failures) == 0 else "RED",
        "forceCloseAvailable": bool(fc_available),
        "patientAttestEligible": patient_attest_eligible,
        "forceCloseLaserGated": True,
        "trellisBenefits": trellis_benefits,
        "note": (
            "GREEN + MATCH does not enable period Force Close; "
            "use patientAttestEligible for MATCH-gated patient ATTEST REVIEW. "
            "trellisBenefits is informational (withBenefits counts, no $)."
        ),
    }
    checks.append(
        {
            "id": "morning_confidence",
            "ok": True,
            **morning_confidence,
        }
    )
    overall = len(failures) == 0
    row = {
        "ok": overall,
        "emptyNotZero": True if patient_ctx.get("emptyNotZero", True) else False,
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
        "thisPatientShortcutCovered": bool(patient_ctx.get("covered")),
        "monThuApptTimeOk": bool(row_time_covered),
        "morningConfidence": morning_confidence,
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
            "thisPatientShortcutCovered": bool(patient_ctx.get("covered")),
            "monThuApptTimeOk": bool(row_time_covered),
        }
    )
    return row


if __name__ == "__main__":
    import sys

    probe = "--no-http" not in sys.argv
    result = run_desk_smoke(probe_http=probe)
    print(json.dumps(result, indent=2, default=str))
    raise SystemExit(0 if result.get("ok") else 1)
