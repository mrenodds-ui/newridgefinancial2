#!/usr/bin/env python3
"""SoftDent daily master GUI pull — Sign On → Phase-1 catalog → status → refresh.

Read-only SoftDent UI exports into C:\\SoftDentReportExports, then hands off to the
existing daily refresh / period import path. Never prints passwords.

Intended schedule: interactive desktop Task Scheduler at 5:00 PM.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
NR2 = REPO / "NewRidgeFinancial2"
sys.path.insert(0, str(NR2))

from softdent_gui_export import (  # noqa: E402
    EXPORT_ROOT,
    PHASE1_IDS,
    STATUS_ROOT,
    load_menu_map,
    run_catalog_exports,
    softdent_main_running,
)
from softdent_master_reports import (  # noqa: E402
    gui_export_ids_required,
    verify_master_reports,
)
from softdent_signon import softdent_signon_status  # noqa: E402

DEFAULT_STATUS = STATUS_ROOT / "softdent_daily_gui_pull_status.json"
DEFAULT_REFRESH_PS1 = Path(
    r"C:\New folder\ops\softdent\automation\run_daily_softdent_refresh.ps1"
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _interactive_session_ok() -> dict[str, Any]:
    """Best-effort check that we are not in a pure Session-0 / service context."""
    info: dict[str, Any] = {"ok": True, "hints": []}
    try:
        import ctypes

        # GetSystemMetrics(SM_REMOTESESSION)=0x1000 — informational only
        remote = bool(ctypes.windll.user32.GetSystemMetrics(0x1000))
        info["remoteSession"] = remote
    except Exception:
        info["hints"].append("could_not_query_remote_session")
    session_name = str(os.environ.get("SESSIONNAME") or "").strip()
    info["sessionName"] = session_name or None
    if session_name.upper() == "SERVICES":
        info["ok"] = False
        info["hints"].append("SESSIONNAME=Services — GUI SoftDent pull needs interactive desktop")
    return info


def _preflight() -> dict[str, Any]:
    exe = Path(r"C:\SoftDent\SDWIN.EXE")
    signon = softdent_signon_status()
    session = _interactive_session_ok()
    try:
        from softdent_signon import resolve_softdent_launch_shortcut

        shortcut = resolve_softdent_launch_shortcut()
    except Exception:
        shortcut = None
    return {
        "softdentExePresent": exe.is_file(),
        "softdentExe": str(exe),
        "softdentShortcut": str(shortcut) if shortcut else None,
        "softdentShortcutPresent": bool(shortcut),
        "launchPolicy": "desktop_or_programs_shortcut_only",
        "softdentMainRunning": softdent_main_running(),
        "exportRootWritable": EXPORT_ROOT.exists() or True,
        "passwordConfigured": bool(signon.get("passwordConfigured")),
        "signOnUser": signon.get("user"),
        "interactiveSession": session,
        "ok": bool(
            (shortcut or softdent_main_running())
            and signon.get("passwordConfigured")
            and session.get("ok")
        ),
    }


def _scrub(obj: Any) -> Any:
    """Defense in depth: strip secret-looking keys from status payload."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            lk = str(k).lower()
            if lk in {"password", "pwd", "secret", "token"} or lk.endswith("password"):
                continue
            out[k] = _scrub(v)
        return out
    if isinstance(obj, list):
        return [_scrub(x) for x in obj]
    return obj


def _write_status(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = _scrub(payload)
    path.write_text(json.dumps(clean, indent=2), encoding="utf-8")
    # Mirror under dashboard_logs
    log_dir = STATUS_ROOT / "dashboard_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    mirror = log_dir / f"softdent_daily_gui_pull_{stamp}.json"
    mirror.write_text(json.dumps(clean, indent=2), encoding="utf-8")
    return path


def _run_refresh(*, skip_refresh: bool, refresh_ps1: Path) -> dict[str, Any]:
    if skip_refresh:
        return {"skipped": True, "ok": True}
    out: dict[str, Any] = {"skipped": False, "ok": False}
    # Prefer ops daily refresh when present; else NR2 period refresh
    if refresh_ps1.is_file():
        try:
            proc = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(refresh_ps1),
                ],
                capture_output=True,
                text=True,
                timeout=7200,
                cwd=str(refresh_ps1.parent),
            )
            out["runner"] = "ops_daily_refresh_ps1"
            out["exitCode"] = proc.returncode
            out["ok"] = proc.returncode == 0
            out["stdoutTail"] = (proc.stdout or "")[-2000:]
            out["stderrTail"] = (proc.stderr or "")[-1000:]
            return out
        except Exception as exc:  # noqa: BLE001
            out["runner"] = "ops_daily_refresh_ps1"
            out["error"] = f"{type(exc).__name__}:{exc}"
            # fall through to Python refresh

    try:
        from apex_backend import refresh_softdent_period_imports

        r = refresh_softdent_period_imports()
        out["runner"] = "refresh_softdent_period_imports"
        out["ok"] = bool(r.get("ok"))
        out["collectionsGap"] = {
            "gapCode": (r.get("collectionsGap") or {}).get("gapCode"),
            "collectionsGapCode": (r.get("collectionsGap") or {}).get("collectionsGapCode"),
            "coversOpenMonth": (r.get("collectionsGap") or {}).get("coversOpenMonth"),
            "period": (r.get("collectionsGap") or {}).get("period"),
        }
        out["nextStep"] = (r.get("nextStep") or "")[:240]
    except Exception as exc:  # noqa: BLE001
        out["runner"] = "refresh_softdent_period_imports"
        out["error"] = f"{type(exc).__name__}:{exc}"
        out["ok"] = False
    return out


def main() -> int:
    today = date.today()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default=f"{today.year:04d}-{today.month:02d}-01")
    parser.add_argument("--end", default=today.isoformat())
    parser.add_argument(
        "--reports",
        default="",
        help="Comma list of GUI report ids (default: master GUI required / Phase-1)",
    )
    parser.add_argument("--skip-signon", action="store_true")
    parser.add_argument("--skip-refresh", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--require-inbox", action="store_true")
    parser.add_argument("--status-path", default=str(DEFAULT_STATUS))
    parser.add_argument("--refresh-ps1", default=str(DEFAULT_REFRESH_PS1))
    args = parser.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    if str(args.reports).strip():
        report_ids = [x.strip() for x in str(args.reports).split(",") if x.strip()]
    else:
        try:
            report_ids = gui_export_ids_required() or list(PHASE1_IDS)
        except Exception:
            report_ids = list(PHASE1_IDS)

    payload: dict[str, Any] = {
        "ok": False,
        "startedAt": _utc_now(),
        "start": start.isoformat(),
        "end": end.isoformat(),
        "reportIds": report_ids,
        "dataAccessDoctrine": (
            "Prefer SoftDent DB/ODBC/Sensei/sd_*; Sign On + UI Excel only when DB cannot supply."
        ),
        "preflight": _preflight(),
        "masterVerify": None,
        "exports": None,
        "refresh": None,
        "menuMapVersion": None,
    }
    try:
        payload["menuMapVersion"] = (load_menu_map() or {}).get("version")
    except Exception as exc:  # noqa: BLE001
        payload["preflight"]["menuMapError"] = f"{type(exc).__name__}:{exc}"
        payload["preflight"]["ok"] = False

    try:
        payload["masterVerify"] = verify_master_reports(
            start=start,
            end=end,
            require_inbox_files=bool(args.require_inbox),
        )
    except Exception as exc:  # noqa: BLE001
        payload["masterVerify"] = {"ok": False, "error": f"{type(exc).__name__}:{exc}"}

    if args.verify_only:
        payload["ok"] = bool((payload.get("masterVerify") or {}).get("ok"))
        payload["finishedAt"] = _utc_now()
        _write_status(Path(args.status_path), payload)
        print(json.dumps(_scrub(payload), indent=2))
        return 0 if payload["ok"] else 1

    if args.dry_run:
        exports = run_catalog_exports(
            start=start,
            end=end,
            report_ids=report_ids,
            ensure_signon=False,
            dry_run=True,
        )
        payload["exports"] = exports
        payload["refresh"] = {"skipped": True, "ok": True, "reason": "dry-run"}
        payload["ok"] = True
        payload["finishedAt"] = _utc_now()
        _write_status(Path(args.status_path), payload)
        print(json.dumps(_scrub(payload), indent=2))
        return 0

    if not payload["preflight"].get("ok") and not payload["preflight"].get("softdentMainRunning"):
        # Allow continue if SoftDent already running even if password missing (already signed on)
        if not payload["preflight"].get("softdentMainRunning"):
            payload["error"] = "preflight_failed"
            payload["finishedAt"] = _utc_now()
            _write_status(Path(args.status_path), payload)
            print(json.dumps(_scrub(payload), indent=2))
            return 2

    exports = run_catalog_exports(
        start=start,
        end=end,
        report_ids=report_ids,
        ensure_signon=not args.skip_signon,
        dry_run=False,
    )
    payload["exports"] = exports

    refresh = _run_refresh(
        skip_refresh=args.skip_refresh,
        refresh_ps1=Path(args.refresh_ps1),
    )
    payload["refresh"] = refresh
    # Re-verify after pull so status shows which master reports are still missing
    try:
        payload["masterVerifyAfter"] = verify_master_reports(
            start=start,
            end=end,
            require_inbox_files=True,
        )
    except Exception as exc:  # noqa: BLE001
        payload["masterVerifyAfter"] = {"ok": False, "error": f"{type(exc).__name__}:{exc}"}
    payload["ok"] = bool(exports.get("ok")) and bool(refresh.get("ok"))
    payload["partialOk"] = bool(exports.get("partialOk") or (exports.get("ok") and not refresh.get("ok")))
    payload["finishedAt"] = _utc_now()
    _write_status(Path(args.status_path), payload)
    print(json.dumps(_scrub(payload), indent=2))
    if payload["ok"]:
        return 0
    if exports.get("ok") or exports.get("partialOk"):
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
