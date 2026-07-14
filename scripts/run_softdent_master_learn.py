"""Live SoftDent: run master GUI reports and learn Output Options (Excel vs Print Preview).

Uses SoftDent Win32 menu_select only (avoids keystrokes stolen by Cursor Agents).
After each report: record Output Options buttons, Cancel, move on.
Never Esc on SoftDent main. Never invent dollars.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "NewRidgeFinancial2"))

from softdent_gui_export import (  # noqa: E402
    _force_foreground,
    _main_softdent_hwnd,
    _softdent_click,
    _softdent_pids,
    _window_pid,
    cancel_printer_dialogs,
    dismiss_softdent_alerts,
    find_dialog,
    softdent_main_running,
)
from softdent_master_reports import load_master_reports  # noqa: E402
from softdent_signon import ensure_softdent_signed_on  # noqa: E402

STATUS = Path(r"C:\SoftDentFinancialExports\softdent_master_report_learn.json")


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _focus_sd() -> int:
    hwnd = _main_softdent_hwnd()
    _force_foreground(hwnd)
    time.sleep(0.35)
    return hwnd


def _titles() -> list[str]:
    from pywinauto import Desktop

    pids = _softdent_pids()
    out: list[str] = []
    for w in Desktop(backend="win32").windows():
        try:
            t = (w.window_text() or "").strip()
            if not t:
                continue
            if pids and _window_pid(int(w.handle)) not in pids:
                continue
            if t in {"DDE Server Window", "Socket Notification Sink", "Default IME", "M"}:
                continue
            out.append(t)
        except Exception:
            continue
    return out


def _cancel_modals() -> None:
    from pywinauto import Application, Desktop

    cancel_printer_dialogs(max_rounds=4)
    pids = _softdent_pids()
    for w in list(Desktop(backend="win32").windows()):
        try:
            t = (w.window_text() or "").strip()
            if not t or "softdent software" in t.lower():
                continue
            if pids and _window_pid(int(w.handle)) not in pids:
                continue
            low = t.lower()
            if not any(
                k in low
                for k in (
                    "output options",
                    "setup",
                    "select file",
                    "print preview",
                    "waiting for printer",
                    "collection",
                    "register",
                    "daysheet",
                    "aging",
                    "writeoff",
                    "trans",
                )
            ):
                continue
            app = Application(backend="win32").connect(handle=w.handle)
            d = app.window(handle=w.handle)
            for b in d.descendants(class_name="Button"):
                lab = (b.window_text() or "").replace("&", "").strip().lower()
                if lab in {"cancel", "close", "no"}:
                    try:
                        _softdent_click(b)
                        time.sleep(0.3)
                        break
                    except Exception:
                        continue
        except Exception:
            continue
    cancel_printer_dialogs(max_rounds=2)
    dismiss_softdent_alerts(max_rounds=2)


def _output_options_info() -> dict[str, Any]:
    from pywinauto import Application

    info: dict[str, Any] = {
        "present": False,
        "buttons": [],
        "hasExcel": False,
        "hasPrintPreview": False,
        "hasPrinter": False,
        "hasFile": False,
        "howToGetInfo": [],
    }
    out = find_dialog("Output Options")
    if not out:
        return info
    info["present"] = True
    try:
        app = Application(backend="win32").connect(handle=out.handle)
        d = app.window(handle=out.handle)
        for b in d.descendants(class_name="Button"):
            lab = (b.window_text() or "").replace("&", "").strip()
            if lab:
                info["buttons"].append(lab)
    except Exception as exc:
        info["error"] = type(exc).__name__
        return info
    blob = " ".join(info["buttons"]).lower()
    info["hasExcel"] = "excel" in blob
    info["hasPrintPreview"] = "preview" in blob
    info["hasPrinter"] = any(x in blob for x in ("printer",)) and "preview" not in "printer"
    # hasPrinter: look for exact Printer button
    info["hasPrinter"] = any(b.lower() == "printer" for b in info["buttons"])
    info["hasFile"] = any(b.lower() == "file" for b in info["buttons"])
    if info["hasExcel"]:
        info["howToGetInfo"].append(
            "FILE INGEST: click Excel prompt → Enter → fill Setup dates/provider 999 → "
            "save under C:\\SoftDentReportExports → NR2 parses XLS (Productions/Collections/"
            "Ins Plan/Regular when Register)."
        )
    if info["hasPrintPreview"]:
        info["howToGetInfo"].append(
            "VISUAL READ: click Print Preview prompt → Enter → fill Setup if shown → "
            "go to LAST page of preview for exact totals (do not invent from page 1)."
        )
    if info["hasPrinter"]:
        info["howToGetInfo"].append("AVOID Printer (offline hang — Cancel with Alt+C if it appears).")
    return info


def learn_one(rid: str, meta: dict[str, Any]) -> dict[str, Any]:
    from pywinauto import Application

    entry: dict[str, Any] = {
        "id": rid,
        "label": meta.get("label"),
        "menuPath": meta.get("guiWin32Path"),
        "ok": False,
        "preferredPath": None,
        "howToGetInfo": [],
    }
    path = str(meta.get("guiWin32Path") or "").strip()
    if not path:
        entry["error"] = "no_menu_path"
        return entry

    _cancel_modals()
    hwnd = _focus_sd()
    try:
        app = Application(backend="win32").connect(handle=hwnd)
        win = app.window(handle=hwnd)
        win.menu_select(path)
    except Exception as exc:
        entry["error"] = f"menu_select:{type(exc).__name__}:{exc}"
        _cancel_modals()
        return entry

    # Wait for Output Options or Setup
    mode = "unknown"
    for _ in range(30):
        cancel_printer_dialogs(max_rounds=1)
        oo = _output_options_info()
        if oo.get("present"):
            entry["outputOptions"] = oo
            entry["howToGetInfo"] = list(oo.get("howToGetInfo") or [])
            if oo.get("hasExcel"):
                mode = "excel_preferred"
                entry["preferredPath"] = "excel"
            elif oo.get("hasPrintPreview"):
                mode = "print_preview"
                entry["preferredPath"] = "print_preview"
            else:
                mode = "other_output_options"
            entry["ok"] = True
            entry["inferredMode"] = mode
            break
        titles = _titles()
        entry["titles"] = titles
        if any("setup" in t.lower() for t in titles):
            entry["setupBeforeOutputOptions"] = True
            entry["howToGetInfo"].append(
                "Setup dialog opened first — fill dates/provider then OK; "
                "if Output Options appears next, choose Excel or Print Preview."
            )
            # Don't OK Setup here (can hang on printer); Cancel and note.
            mode = "setup_first"
            entry["inferredMode"] = mode
            entry["ok"] = True
            entry["preferredPath"] = "excel_if_offered_after_setup_else_preview"
            break
        if any("preview" in t.lower() for t in titles):
            mode = "print_preview_direct"
            entry["inferredMode"] = mode
            entry["preferredPath"] = "print_preview"
            entry["howToGetInfo"].append(
                "Print Preview opened — go to LAST page for exact totals."
            )
            entry["ok"] = True
            break
        time.sleep(0.25)
    else:
        entry["inferredMode"] = "unknown"
        entry["titles"] = _titles()
        entry["error"] = entry.get("error") or "no_output_options_or_setup"

    _cancel_modals()
    try:
        _focus_sd()
    except Exception:
        pass
    time.sleep(0.4)
    return entry


def main() -> int:
    payload: dict[str, Any] = {
        "ok": False,
        "startedAt": _utc(),
        "doctrine": (
            "DB first. Else SoftDent Sign On + Output Options: "
            "Excel→Enter for file parse, or Print Preview→Enter then LAST page visual read."
        ),
        "reports": {},
        "lessonSummary": [],
    }
    if not softdent_main_running():
        sign = ensure_softdent_signed_on(timeout_s=60.0, force_change_login=False)
        payload["signOn"] = {
            "ok": bool(sign.get("ok")),
            "signedOn": bool(sign.get("signedOn")),
            "steps": sign.get("steps"),
        }
        time.sleep(1.0)
    else:
        sign = ensure_softdent_signed_on(timeout_s=20.0, force_change_login=False)
        payload["signOn"] = {
            "ok": bool(sign.get("ok")),
            "signedOn": bool(sign.get("signedOn")),
            "steps": sign.get("steps"),
        }

    if not softdent_main_running():
        payload["error"] = "SoftDent not running after Sign On"
        STATUS.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload, indent=2))
        return 2

    catalog = load_master_reports()
    for rid in catalog.get("masterOrder") or []:
        meta = (catalog.get("reports") or {}).get(rid) or {}
        if meta.get("preferredSource") == "database":
            payload["reports"][rid] = {
                "id": rid,
                "ok": True,
                "preferredPath": "database",
                "howToGetInfo": [
                    "Use SoftDent ODBC / Sensei / sd_* SQLite — no SoftDent GUI report."
                ],
            }
            payload["lessonSummary"].append(f"{rid}: database (sd_*)")
            continue
        print(f"LEARN {rid} …", flush=True)
        entry = learn_one(rid, meta)
        payload["reports"][rid] = entry
        path = entry.get("preferredPath") or entry.get("inferredMode")
        payload["lessonSummary"].append(f"{rid}: {path}")
        for tip in entry.get("howToGetInfo") or []:
            print(f"  - {tip[:120]}", flush=True)
        time.sleep(0.6)

    payload["finishedAt"] = _utc()
    payload["ok"] = all(bool(v.get("ok")) for v in payload["reports"].values())
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"ok": payload["ok"], "lessonSummary": payload["lessonSummary"]}, indent=2))
    print(f"Wrote {STATUS}", flush=True)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
