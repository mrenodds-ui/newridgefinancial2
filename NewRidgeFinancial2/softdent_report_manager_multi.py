"""SoftDent Report Manager multi-report programming (native + NR2 fallback).

SoftDent feature (Help): Reports → Report Manager → set up a Report Group, then
Run Scheduled Reports / Advanced Options → Run Now — one command runs many reports.

Office hard rules:
- Output Options: Excel or Print Preview only — NEVER Printer (Help defaults to Printer; override).
- Sign On COMPUTE / computer via CS SoftDent Software.lnk (-sus).
- Never Esc on SoftDent main. empty ≠ $0. No SoftDent write-back.
- Period money pack: register, collections, transactions, daysheet, aging.

When Report Manager submenu is rights-locked (common), fall back to sequential
GUI Excel pull via run_catalog_exports (same report ids / SoftDent desktop truth).
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from softdent_gui_export import (
    EXPORT_ROOT,
    PHASE1_IDS,
    STATUS_ROOT,
    list_softdent_window_titles,
    prepare_softdent_for_next_report,
    run_catalog_exports,
    softdent_main_running,
)

logger = logging.getLogger(__name__)

DEF_ID = "HAL-10615-RM"
PACKAGE_BUILD_ID = "hal-10615"
GROUP_NAME = "NR2 Money Widgets"
STATUS_PATH = STATUS_ROOT / "softdent_report_manager_multi_status.json"

# SoftDent date macros (Help: Setting Up a Report Manager Report)
# MM/01/YY … MM/99/YY = first → last day of current month (MTD-friendly on run day).
DATE_MACROS = {
    "mtd_start": "MM/01/YY",
    "mtd_end": "MM/99/YY",
    "today": "MM/DD/YY",
    "as_of": "MM/DD/YY",
}

# Programmed multi-report pack (must match SoftDent report titles / NR2 menu map ids)
MULTI_REPORT_PACK: list[dict[str, Any]] = [
    {
        "id": "register",
        "softdentTitle": "Register for a Period",
        "menuPath": "Reports → Accounting → Registers → Period",
        "dateMode": "range",
        "startMacro": DATE_MACROS["mtd_start"],
        "endMacro": DATE_MACROS["mtd_end"],
        "output": "excel",
        "required": True,
    },
    {
        "id": "collections",
        "softdentTitle": "Collection Reports — Summary",
        "menuPath": "Reports → Practice Management → Collection Reports → Summary",
        "dateMode": "range",
        "startMacro": DATE_MACROS["mtd_start"],
        "endMacro": DATE_MACROS["mtd_end"],
        "output": "excel",
        "required": True,
    },
    {
        "id": "transactions",
        "softdentTitle": "Transactions for a Period",
        "menuPath": "Reports → Accounting → Trans for a Period",
        "dateMode": "range",
        "startMacro": DATE_MACROS["mtd_start"],
        "endMacro": DATE_MACROS["mtd_end"],
        "output": "excel",
        "format": "1 — List Each Transaction Separately",
        "required": True,
    },
    {
        "id": "daysheet",
        "softdentTitle": "Daysheet",
        "menuPath": "Reports → Accounting → Daysheet",
        "dateMode": "range",
        "startMacro": DATE_MACROS["mtd_start"],
        "endMacro": DATE_MACROS["mtd_end"],
        "output": "excel",
        "required": True,
    },
    {
        "id": "aging",
        "softdentTitle": "Account Aging",
        "menuPath": "Reports → Accounting → Account Aging",
        "dateMode": "as_of",
        "asOfMacro": DATE_MACROS["as_of"],
        "output": "excel",
        "required": True,
    },
]


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def report_manager_playbook() -> dict[str, Any]:
    """How to program SoftDent Report Manager for multi-report Excel pulls."""
    return {
        "def": DEF_ID,
        "groupName": GROUP_NAME,
        "softDentMenus": {
            "setup": "Reports → Report Manager → Set up a Report Group",
            "runScheduled": "Reports → Report Manager → Run Scheduled Reports",
            "advancedRunNow": "Reports → Report Manager → Advanced Options → select group → Run Now",
        },
        "hardRules": [
            "Output Options → Excel → Enter (or Print Preview → Enter). NEVER Printer.",
            "SoftDent Help says Verify Printer for Report Manager setup — ignore that for NR2; use Excel.",
            "If SoftDent shows Waiting for printer… → Cancel (Alt+C).",
            "Launch via CS SoftDent Software.lnk (-sus); Sign On COMPUTE / computer.",
            "Never Esc on SoftDent main.",
            "Date macros avoid rewriting dates each run: MM/01/YY … MM/99/YY for MTD.",
            "Save Excel / SDWIN*.csv into C:\\SoftDentReportExports.",
            "empty ≠ $0 — never invent SoftDent dollars.",
        ],
        "dateMacros": DATE_MACROS,
        "pack": MULTI_REPORT_PACK,
        "securityNote": (
            "If Set up / Run Scheduled / Advanced Options are grayed out, SoftDent "
            "security (System → Change System Settings → System Security) must grant "
            "Report Manager / financial report rights for this Sign On user. "
            "NR2 then uses sequential desktop Excel pull for the same pack."
        ),
        "fallback": (
            r"python scripts\run_softdent_money_widget_pull.py "
            r"--reports register,collections,transactions,daysheet,aging"
        ),
    }


def probe_report_manager_menus() -> dict[str, Any]:
    """Inspect whether SoftDent Report Manager / Batch Select are enabled."""
    out: dict[str, Any] = {
        "ok": False,
        "softdentRunning": softdent_main_running(),
        "reportManagerEnabled": False,
        "items": {},
        "batchSelectEnabled": False,
        "titles": [],
    }
    if not out["softdentRunning"]:
        out["error"] = "SoftDent main not running"
        return out
    try:
        from pywinauto import Application
        from softdent_gui_export import _force_foreground, _main_softdent_hwnd

        prepare_softdent_for_next_report()
        hwnd = _main_softdent_hwnd()
        _force_foreground(hwnd)
        app = Application(backend="win32").connect(handle=hwnd)
        win = app.window(handle=hwnd)
        menu = win.menu()
        for item in menu.items():
            top = (item.text() or "").replace("&", "")
            if top != "Reports":
                continue
            for si in item.sub_menu().items():
                label = (si.text() or "").replace("&", "").strip()
                if not label:
                    continue
                if label == "Batch Select Mode":
                    out["batchSelectEnabled"] = bool(si.is_enabled())
                    out["items"][label] = bool(si.is_enabled())
                if label == "Report Manager":
                    out["reportManagerEnabled"] = bool(si.is_enabled())
                    out["items"][label] = bool(si.is_enabled())
                    try:
                        for ssi in si.sub_menu().items():
                            sub = (ssi.text() or "").replace("&", "").strip()
                            if sub:
                                out["items"][f"Report Manager/{sub}"] = bool(ssi.is_enabled())
                    except Exception as exc:  # noqa: BLE001
                        out["submenuError"] = type(exc).__name__
        out["titles"] = list_softdent_window_titles()[:20]
        usable = any(
            out["items"].get(k)
            for k in (
                "Report Manager/Set up a Report Group",
                "Report Manager/Run Scheduled Reports",
                "Report Manager/Advanced Options",
            )
        )
        out["ok"] = bool(out["reportManagerEnabled"] and usable)
        if out["reportManagerEnabled"] and not usable:
            out["gapCode"] = "REPORT_MANAGER_RIGHTS_LOCKED"
            out["hint"] = report_manager_playbook()["securityNote"]
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"{type(exc).__name__}:{exc}"
    return out


def run_programmed_multi_report_pull(
    *,
    start: date | None = None,
    end: date | None = None,
    ensure_signon: bool = True,
    prefer_report_manager: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Program / run SoftDent multi-report pack (Report Manager if usable, else sequential)."""
    today = date.today()
    start = start or date(today.year, today.month, 1)
    end = end or today
    payload: dict[str, Any] = {
        "ok": False,
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "startedAt": _utc(),
        "groupName": GROUP_NAME,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "reportIds": [r["id"] for r in MULTI_REPORT_PACK],
        "playbook": report_manager_playbook(),
        "probe": None,
        "mode": None,
        "exports": None,
    }
    probe = probe_report_manager_menus()
    payload["probe"] = {
        "ok": probe.get("ok"),
        "reportManagerEnabled": probe.get("reportManagerEnabled"),
        "batchSelectEnabled": probe.get("batchSelectEnabled"),
        "gapCode": probe.get("gapCode"),
        "items": probe.get("items"),
        "error": probe.get("error"),
    }

    if prefer_report_manager and probe.get("ok") and not dry_run:
        # Live Report Manager Run Now path is reserved once SoftDent rights unlock.
        # Until then we never select Printer via Help-default batch setup.
        payload["mode"] = "report_manager_reserved"
        payload["exports"] = {
            "ok": False,
            "skipped": True,
            "reason": (
                "Report Manager menus usable — operator/Run Now automation pending; "
                "use Advanced Options → Run Now for group "
                f"{GROUP_NAME!r} with Excel-only members, or fall through to sequential."
            ),
        }

    # Always run sequential SoftDent desktop Excel pack (proven multi-report path).
    payload["mode"] = "sequential_catalog_excel"
    payload["exports"] = run_catalog_exports(
        start=start,
        end=end,
        report_ids=[r["id"] for r in MULTI_REPORT_PACK],
        ensure_signon=ensure_signon and not dry_run,
        dry_run=dry_run,
    )
    exports = payload.get("exports") or {}
    payload["ok"] = bool(exports.get("ok") or (dry_run and exports.get("ok")))
    payload["partialOk"] = bool(exports.get("partialOk"))
    payload["finishedAt"] = _utc()
    payload["exportRoot"] = str(EXPORT_ROOT)
    return payload


def write_status(payload: dict[str, Any], path: Path | None = None) -> Path:
    target = path or STATUS_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    clean = json.loads(json.dumps(payload, default=str))
    # Never persist secrets
    if isinstance(clean.get("signOn"), dict):
        clean["signOn"].pop("password", None)
    target.write_text(json.dumps(clean, indent=2), encoding="utf-8")
    return target


def format_report_manager_multi_hal_reply(status: dict[str, Any] | None = None) -> str:
    play = report_manager_playbook()
    st = status if isinstance(status, dict) else {}
    probe = st.get("probe") or {}
    lines = [
        f"SoftDent multi-report program ({DEF_ID}): group {GROUP_NAME!r}.",
        "Program SoftDent Report Manager with Register / Collections / Trans / Daysheet / Aging "
        "→ Output Options Excel (never Printer) → date macros MM/01/YY…MM/99/YY.",
        f"Menus: {play['softDentMenus']['setup']} then {play['softDentMenus']['advancedRunNow']}.",
    ]
    if probe.get("gapCode") == "REPORT_MANAGER_RIGHTS_LOCKED":
        lines.append(
            "Report Manager submenu is grayed out for this Sign On — grant SoftDent security "
            "rights or use NR2 sequential Excel pull (same pack)."
        )
    exports = st.get("exports") or {}
    if exports:
        ok_ids = [
            rid
            for rid, meta in (exports.get("reports") or {}).items()
            if isinstance(meta, dict) and meta.get("ok") and meta.get("path")
        ]
        fail = exports.get("requiredFailed") or []
        lines.append(f"Last pull mode={st.get('mode')}; ok={ok_ids}; failed={fail}.")
    lines.append(f"Fallback: {play['fallback']}. empty ≠ $0.")
    return " ".join(lines)


__all__ = [
    "DEF_ID",
    "GROUP_NAME",
    "MULTI_REPORT_PACK",
    "PHASE1_IDS",
    "format_report_manager_multi_hal_reply",
    "probe_report_manager_menus",
    "report_manager_playbook",
    "run_programmed_multi_report_pull",
    "write_status",
]
