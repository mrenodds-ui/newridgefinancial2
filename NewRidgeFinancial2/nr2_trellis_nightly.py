"""Nightly next-day Vyne Trellis dental eligibility verify (Mon–Thu clinical days).

Learned ops flow:
  SoftDent tomorrow schedule → worklist → Trellis Add Patient → Verify → results JSON.

Runs at 22:00 Mon–Thu (local). Target date = next clinical day (Mon–Thu);
Thu night jumps to Monday (skip Fri–Sun chairs).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
NR2_ROOT = Path(__file__).resolve().parent
SCRIPTS = NR2_ROOT / "scripts"
OUT_DIR = REPO_ROOT / "app_data" / "nr2" / "vyne_pulls"
ENV_FILE = REPO_ROOT / ".env.vyne.local"

# Mon=0 … Sun=6
CLINICAL_WEEKDAYS = {0, 1, 2, 3}  # Mon–Thu


def next_clinical_day(today: date | None = None) -> date | None:
    """Following clinical day for a Mon–Thu chair schedule.

    Mon→Tue, Tue→Wed, Wed→Thu, Thu→Mon (skip weekend).
    Fri/Sat/Sun callers get Monday (or None if not a run night — callers decide).
    """
    today = today or date.today()
    # Walk forward until Mon–Thu and strictly after today
    cursor = today + timedelta(days=1)
    for _ in range(8):
        if cursor.weekday() in CLINICAL_WEEKDAYS:
            return cursor
        cursor += timedelta(days=1)
    return None


def should_run_tonight(today: date | None = None) -> bool:
    """True on Mon–Thu local nights (10pm job nights)."""
    today = today or date.today()
    return today.weekday() in CLINICAL_WEEKDAYS


def _iso(d: date) -> str:
    return d.isoformat()


def build_worklist(target: date) -> dict[str, Any]:
    sys.path.insert(0, str(SCRIPTS))
    from _build_trellis_add_worklist import build_trellis_worklist  # noqa: WPS433

    return build_trellis_worklist(target_date=_iso(target), out_dir=OUT_DIR)


def build_pending_from_worklist(worklist: dict[str, Any]) -> dict[str, Any]:
    sys.path.insert(0, str(SCRIPTS))
    from _trellis_carrier_map import CARRIER_MAP  # noqa: WPS433

    target = str(worklist.get("date") or "")
    patients: list[dict[str, Any]] = []
    for row in worklist.get("patients") or []:
        if not row.get("ready"):
            continue
        demo = row.get("demo") or {}
        ins = row.get("insurance") or {}
        softdent = str(ins.get("insurance_name") or "").strip()
        trellis = CARRIER_MAP.get(softdent) or softdent
        member = str(ins.get("trellis_subscriber_id") or ins.get("member_id") or "").strip()
        sub_raw = str(ins.get("subscriber_id") or "").strip()
        # SoftDent often stores Sensei person ref in subscriber_id (RP0-…)
        subscriber_ref = sub_raw if sub_raw.upper().startswith("RP") else ""
        rel = str(ins.get("relationship_code") or "").upper()
        is_self = rel in {"", "SELF", "01", "1"} or bool(demo.get("is_subscriber"))
        patients.append(
            {
                "patient_name": row.get("patient_name"),
                "first": demo.get("first") or "",
                "last": demo.get("last") or "",
                "dob": demo.get("dob") or "",
                "gender": demo.get("gender") or "",
                "is_self": is_self,
                "softdent_carrier": softdent,
                "trellis_carrier": trellis,
                "subscriber_id": member,
                "relationship": "SELF" if is_self else (rel or "OTHER"),
                "subscriber_ref": subscriber_ref,
                "patient_id": row.get("patient_id"),
            }
        )
    payload = {
        "date": target,
        "builtAt": datetime.now(timezone.utc).isoformat(),
        "patients": patients,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"tomorrow_trellis_pending_batch_{target}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {"ok": True, "path": str(path), "count": len(patients), "payload": payload}


def ensure_results_shell(target: date) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"tomorrow_trellis_verify_results_{_iso(target)}.json"
    if not path.is_file():
        path.write_text(
            json.dumps(
                {
                    "date": _iso(target),
                    "updatedAt": datetime.now(timezone.utc).isoformat(),
                    "results": [],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    return path


def _summarize_results(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"count": 0, "byStatus": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("results") or []
    by: dict[str, int] = {}
    for r in rows:
        st = str(r.get("status") or "Unknown")
        by[st] = by.get(st, 0) + 1
    return {"count": len(rows), "byStatus": by, "path": str(path)}


def run_verify_batch(target: date, *, timeout_sec: int = 10800) -> dict[str, Any]:
    """Spawn Playwright batch (headed). Requires interactive desktop + .env.vyne.local.

    Timeout default 3h — ClearCoverage full ADA expand is slower than status-only verify.
    """
    if not ENV_FILE.is_file():
        return {
            "ok": False,
            "error": "missing_env",
            "detail": f"Create {ENV_FILE.name} with VYNE_AUTOMATION_USERNAME / PASSWORD (Wichita).",
        }
    script = SCRIPTS / "vyne_trellis_add_verify_batch.py"
    if not script.is_file():
        return {"ok": False, "error": "missing_batch_script", "path": str(script)}
    env = os.environ.copy()
    env["NR2_TRELLIS_TARGET_DATE"] = _iso(target)
    env.setdefault("PYTHONUNBUFFERED", "1")
    # Prefer repo venv playwright
    py = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    if not py.is_file():
        py = Path(sys.executable)
    log_path = OUT_DIR / f"trellis_verify_batch_{_iso(target)}.log"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with log_path.open("w", encoding="utf-8") as log_fp:
            proc = subprocess.run(
                [str(py), "-u", str(script)],
                cwd=str(REPO_ROOT),
                env=env,
                stdout=log_fp,
                stderr=subprocess.STDOUT,
                timeout=timeout_sec,
                check=False,
            )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": "verify_timeout",
            "timeoutSec": timeout_sec,
            "log": str(log_path),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "verify_spawn_failed", "detail": str(exc)[:400]}
    tail = ""
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
        tail = text[-2000:]
    except Exception:
        pass
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "log": str(log_path),
        "stdoutTail": tail,
    }


def insurance_verify_tick(
    store=None,
    *,
    force: bool = False,
    run_verify: bool | None = None,
) -> dict[str, Any]:
    """Build next-day Trellis worklist (+ optional Playwright verify) and upsert HAL work.

    Env:
      NR2_TRELLIS_VERIFY=1  — run headed Playwright verify after building worklist
      (override with run_verify=)
    """
    today = date.today()
    if not force and not should_run_tonight(today):
        return {
            "ok": True,
            "skipped": True,
            "reason": "not_mon_thu_night",
            "weekday": today.strftime("%A"),
        }

    target = next_clinical_day(today)
    if target is None:
        return {"ok": False, "error": "no_clinical_day"}

    # Idempotency: one nightly build per target date unless force
    state_key_day = _iso(target)
    if store and not force:
        try:
            from nr2_scheduler import _load_state, _save_state  # noqa: WPS433

            state = _load_state(store)
            if state.get("trellisVerifyDay") == state_key_day:
                return {
                    "ok": True,
                    "skipped": True,
                    "reason": "already_ran_for_target",
                    "targetDate": state_key_day,
                }
        except Exception:
            pass

    do_verify = (
        bool(run_verify)
        if run_verify is not None
        else str(os.environ.get("NR2_TRELLIS_VERIFY") or "").strip().lower()
        in {"1", "true", "yes", "on"}
    )

    steps: list[dict[str, Any]] = []
    try:
        wl = build_worklist(target)
        steps.append(
            {
                "step": "build_worklist",
                "ok": True,
                "total": wl.get("total"),
                "ready": wl.get("ready"),
                "path": wl.get("path"),
            }
        )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "worklist_failed", "detail": str(exc)[:500], "steps": steps}

    try:
        pending = build_pending_from_worklist(wl)
        steps.append({"step": "build_pending", "ok": True, "count": pending.get("count")})
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "pending_failed", "detail": str(exc)[:500], "steps": steps}

    results_path = ensure_results_shell(target)
    verify_result: dict[str, Any] | None = None
    if do_verify:
        verify_result = run_verify_batch(target)
        steps.append({"step": "verify_batch", **verify_result})
    else:
        steps.append(
            {
                "step": "verify_batch",
                "skipped": True,
                "reason": "NR2_TRELLIS_VERIFY not set — worklist/pending only; "
                "enable env or Task Scheduler headed job to drive Trellis UI",
            }
        )

    report_result: dict[str, Any] | None = None
    if do_verify:
        try:
            sys.path.insert(0, str(SCRIPTS))
            from build_trellis_eligibility_report import (  # noqa: WPS433
                build_report_for_date,
            )

            report_result = build_report_for_date(_iso(target))
            steps.append({"step": "eligibility_report", **report_result})
        except Exception as exc:  # noqa: BLE001
            report_result = {"ok": False, "error": "report_failed", "detail": str(exc)[:400]}
            steps.append({"step": "eligibility_report", **report_result})

    summary = _summarize_results(results_path)
    ready = int(wl.get("ready") or 0)
    verified = int(summary.get("count") or 0)
    by = summary.get("byStatus") or {}
    detail = (
        f"Target {_iso(target)} · worklist ready {ready}/{wl.get('total')} · "
        f"verified {verified} · statuses {by}"
    )
    work = None
    if store:
        try:
            from nr2_scheduler import upsert_autonomous_work  # noqa: WPS433

            work = upsert_autonomous_work(
                store,
                {
                    "kind": "insurance_verify",
                    "sourceId": f"trellis-{_iso(target)}",
                    "title": f"Trellis eligibility for {_iso(target)} "
                    f"({verified} verified / {ready} ready)",
                    "detail": detail,
                    "priority": "high" if by.get("Failed") or by.get("Insurance Info Issue") else "normal",
                    "meta": {
                        "targetDate": _iso(target),
                        "worklistReady": ready,
                        "worklistTotal": wl.get("total"),
                        "results": summary,
                        "verifyRan": do_verify,
                        "report": report_result,
                        "steps": steps,
                    },
                    "forceReopen": True,
                },
            )
            from nr2_scheduler import _load_state, _save_state  # noqa: WPS433

            state = _load_state(store)
            state["trellisVerifyDay"] = state_key_day
            state["lastTrellisVerifyAt"] = datetime.now(timezone.utc).isoformat()
            _save_state(store, state)
        except Exception as exc:  # noqa: BLE001
            steps.append({"step": "upsert_work", "error": str(exc)[:240]})

    return {
        "ok": True,
        "targetDate": _iso(target),
        "runNight": _iso(today),
        "worklistReady": ready,
        "worklistTotal": wl.get("total"),
        "verifyRan": do_verify,
        "results": summary,
        "report": report_result,
        "work": work,
        "steps": steps,
    }


def format_hal_trellis_nightly_reply(query: str = "") -> str:
    """Teach / status reply for HAL local policy."""
    today = date.today()
    target = next_clinical_day(today)
    results_note = ""
    if target:
        path = OUT_DIR / f"tomorrow_trellis_verify_results_{_iso(target)}.json"
        if not path.is_file():
            # also check "tomorrow" if different naming from last run
            for p in sorted(OUT_DIR.glob("tomorrow_trellis_verify_results_*.json"), reverse=True)[:1]:
                path = p
        if path.is_file():
            summary = _summarize_results(path)
            results_note = (
                f"\nLatest results file: {path.name} - "
                f"{summary.get('count')} rows · {summary.get('byStatus')}"
            )
    return (
        "HAL nightly dental insurance verification (Vyne Trellis)\n\n"
        "Schedule: Mon-Thu 10:00 PM local (APScheduler job nr2-trellis-verify "
        "+ optional Windows Task Scheduler headed Playwright).\n"
        "Scope: SoftDent next clinical day (Mon-Thu chairs; Thu night -> Monday).\n"
        "Flow: SoftDent appts -> Trellis Add Patient -> Verify -> ClearCoverage scrape "
        "(deductible/max/ADA %) -> results JSON + printable HTML report under "
        "app_data/nr2/vyne_pulls/ (trellis_eligibility_report_YYYY-MM-DD.html).\n"
        "Staff open: OM Tomorrow · Trellis → Open benefits report "
        "(GET /api/trellis/eligibility-report.html) — huddle list stays initials+hash, no $ invent.\n"
        "Credentials: gitignored .env.vyne.local (Wichita password only - never Emporia).\n"
        "Gating: set NR2_TRELLIS_VERIFY=1 to drive the Trellis UI; without it HAL still "
        "builds the worklist/pending batch and opens a work item for staff.\n"
        f"Tonight run? {'yes' if should_run_tonight(today) else 'no'} "
        f"({today.strftime('%A')}). Next clinical day: "
        f"{_iso(target) if target else 'none'}."
        f"{results_note}\n"
        "Manual: POST /api/scheduler/insurance-verify-run or "
        "python scripts/run_trellis_nightly_verify.py."
    )


def query_touches_trellis_nightly(raw: str) -> bool:
    import re

    q = str(raw or "").lower()
    return bool(
        re.search(
            r"\b("
            r"trellis\s+(nightly|verify|eligibility)|"
            r"nightly\s+(insurance|eligibility|trellis)|"
            r"insurance\s+verif(y|ication)\s+(tonight|nightly|schedule)|"
            r"10\s*pm\s+(insurance|trellis|eligibility)|"
            r"tomorrow.?s?\s+(insurance|eligibility)\s+verif"
            r")\b",
            q,
        )
    )


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else None
    except Exception:
        return None


def tomorrow_insurance_snapshot(
    *,
    target_date: str | None = None,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    """PHI-safe OM panel: tomorrow Trellis worklist + verify status (no names, no $0 money)."""
    root = Path(out_dir) if out_dir else OUT_DIR
    target: date | None = None
    if target_date:
        try:
            target = date.fromisoformat(str(target_date).strip()[:10])
        except ValueError:
            target = None
    if target is None:
        target = next_clinical_day()
    if target is None:
        return {
            "ok": False,
            "hasData": False,
            "error": "no_clinical_day",
            "emptyNotZero": True,
            "patients": [],
        }

    iso = _iso(target)
    work_path = root / f"tomorrow_trellis_add_worklist_{iso}.json"
    results_path = root / f"tomorrow_trellis_verify_results_{iso}.json"
    work = _load_json(work_path)
    results = _load_json(results_path)

    try:
        from patient_dossier import patient_hash
    except Exception:

        def patient_hash(pid: str) -> str:  # type: ignore[misc]
            import hashlib

            raw = str(pid or "").strip()
            return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:4].upper() if raw else "——"

    def _initials(name: str, first: str = "", last: str = "") -> str:
        f = str(first or "").strip()
        l = str(last or "").strip()
        if f or l:
            letters = ((f[:1] if f else "") + (l[:1] if l else "")).upper()
            return f"{letters or 'P'}—"
        parts = [x for x in str(name or "").replace(",", " ").split() if x]
        letters = "".join(p[0] for p in parts[:2] if p).upper()
        return f"{letters or 'P'}—"

    by_id: dict[str, dict[str, Any]] = {}
    by_name: dict[str, dict[str, Any]] = {}
    for row in (results or {}).get("results") or []:
        if not isinstance(row, dict):
            continue
        pid = str(row.get("patient_id") or "").strip()
        nm = str(row.get("patient_name") or "").strip().lower()
        if pid:
            by_id[pid] = row
        if nm:
            by_name[nm] = row

    patients_out: list[dict[str, Any]] = []
    ready_count = 0
    verified_count = 0
    by_status: dict[str, int] = {}

    for row in (work or {}).get("patients") or []:
        if not isinstance(row, dict):
            continue
        pid = str(row.get("patient_id") or "").strip()
        if not pid:
            continue
        demo = row.get("demo") if isinstance(row.get("demo"), dict) else {}
        ins = row.get("insurance") if isinstance(row.get("insurance"), dict) else {}
        ready = bool(row.get("ready"))
        if ready:
            ready_count += 1
        name = str(row.get("patient_name") or "")
        initials = _initials(
            name,
            str(demo.get("first") or ""),
            str(demo.get("last") or ""),
        )
        ph = patient_hash(pid)
        match = by_id.get(pid) or by_name.get(name.strip().lower())
        status = "—"
        carrier = str(ins.get("insurance_name") or "").strip() or "—"
        if match:
            status = str(match.get("status") or "—").strip() or "—"
            carrier = str(match.get("carrier") or carrier).strip() or "—"
            verified_count += 1
        elif not ready:
            status = "Not ready"
        skip = str(row.get("skip_reason") or "").strip() or None
        by_status[status] = by_status.get(status, 0) + 1
        patients_out.append(
            {
                "patientHash": ph,
                "initials": initials,
                "ready": ready,
                "verifyStatus": status,
                "carrier": carrier[:80],
                "skipReason": skip,
            }
        )

    has_data = bool(work) and bool(patients_out)
    return {
        "ok": True,
        "hasData": has_data,
        "emptyNotZero": True,
        "targetDate": iso,
        "builtAt": (work or {}).get("builtAt"),
        "updatedAt": (results or {}).get("updatedAt"),
        "worklistPath": str(work_path) if work_path.is_file() else None,
        "resultsPath": str(results_path) if results_path.is_file() else None,
        "total": int((work or {}).get("total") or len(patients_out) or 0),
        "readyCount": ready_count,
        "verifiedCount": verified_count,
        "byStatus": by_status,
        "patients": patients_out,
        "signal": "ok" if has_data else ("NO SIGNAL — worklist missing" if not work else "NO SIGNAL — empty worklist"),
    }


def eligibility_report_snapshot(
    *,
    target_date: str | None = None,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    """Metadata for printable Trellis ClearCoverage HTML report (staff; OM board stays PHI-safe)."""
    root = Path(out_dir) if out_dir else OUT_DIR
    target: date | None = None
    if target_date:
        try:
            target = date.fromisoformat(str(target_date).strip()[:10])
        except ValueError:
            target = None
    if target is None:
        target = next_clinical_day()
    if target is None:
        return {
            "ok": False,
            "hasReport": False,
            "error": "no_clinical_day",
            "emptyNotZero": True,
        }

    iso = _iso(target)
    path = root / f"trellis_eligibility_report_{iso}.html"
    has = path.is_file()
    size = 0
    if has:
        try:
            size = int(path.stat().st_size)
        except OSError:
            size = 0

    # Counts only — never copy deductible/$ into the OM huddle API.
    patients = 0
    with_benefits = 0
    results = _load_json(root / f"tomorrow_trellis_verify_results_{iso}.json")
    if results:
        rows = results.get("results") or []
        patients = len(rows)
        for row in rows:
            if not isinstance(row, dict):
                continue
            ben = row.get("benefits")
            if not isinstance(ben, dict):
                continue
            if ben.get("scrapeOk") is True:
                with_benefits += 1
                continue
            cats = ben.get("categories") or {}
            if any(cats.get(k) for k in ("preventive", "basic", "major", "ortho")):
                with_benefits += 1
                continue
            if any(
                ben.get(k) is not None
                for k in (
                    "deductibleRemaining",
                    "annualMaxRemaining",
                    "planName",
                )
            ):
                with_benefits += 1

    return {
        "ok": True,
        "hasReport": has and size > 64,
        "emptyNotZero": True,
        "targetDate": iso,
        "path": str(path) if has else None,
        "bytes": size if has else 0,
        "patients": patients,
        "withBenefits": with_benefits,
        "statusOnly": max(0, patients - with_benefits),
        "reportUrl": f"/api/trellis/eligibility-report.html?date={iso}",
        "boardPhi": "initials+hash",
        "note": (
            "Staff printable ClearCoverage report — may show full names for chairside use. "
            f"Verified rows {patients}; ClearCoverage benefits captured {with_benefits} "
            f"(status-only {max(0, patients - with_benefits)}). "
            "OM huddle list stays initials+hash · empty ≠ $0."
            if has
            else "NO SIGNAL — run Trellis verify / build_trellis_eligibility_report for this date."
        ),
    }


def eligibility_report_html(
    *,
    target_date: str | None = None,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    """Load report HTML bytes for authenticated OM/staff serve (no SoftDent write-back)."""
    meta = eligibility_report_snapshot(target_date=target_date, out_dir=out_dir)
    if not meta.get("hasReport"):
        return {**meta, "html": None, "error": meta.get("error") or "report_missing"}
    path = Path(str(meta.get("path") or ""))
    try:
        html_doc = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {**meta, "hasReport": False, "html": None, "error": f"read_failed:{exc}"}
    if len(html_doc.strip()) < 64:
        return {**meta, "hasReport": False, "html": None, "error": "report_empty", "emptyNotZero": True}
    return {**meta, "html": html_doc, "error": None}
