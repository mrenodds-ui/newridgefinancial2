#!/usr/bin/env python3
"""Validate how to get data from each SoftDent master report (Excel or Print Preview only).

Opens each GUI report via SoftDent menu, inspects Output Options buttons, and records
the correct path. HARD RULE: Excel prompt or Print Preview prompt only — never Printer.
Never invents dollars. Cancels dialogs after each probe.
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

OUT = Path(r"C:\SoftDentFinancialExports\softdent_report_howto_validation.json")


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _focus() -> int:
    hwnd = _main_softdent_hwnd()
    _force_foreground(hwnd)
    time.sleep(0.3)
    return hwnd


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
                        time.sleep(0.25)
                        break
                    except Exception:
                        continue
        except Exception:
            continue
    cancel_printer_dialogs(max_rounds=2)
    dismiss_softdent_alerts(max_rounds=2)


def _output_options() -> dict[str, Any]:
    from pywinauto import Application

    info: dict[str, Any] = {
        "present": False,
        "buttons": [],
        "hasExcel": False,
        "hasPrintPreview": False,
        "hasPrinter": False,
    }
    out = find_dialog("Output Options")
    if not out:
        return info
    info["present"] = True
    app = Application(backend="win32").connect(handle=out.handle)
    d = app.window(handle=out.handle)
    for b in d.descendants(class_name="Button"):
        lab = (b.window_text() or "").replace("&", "").strip()
        if lab:
            info["buttons"].append(lab)
    labs = [x.lower() for x in info["buttons"]]
    info["hasExcel"] = "excel" in labs
    info["hasPrintPreview"] = any("preview" in x for x in labs)
    info["hasPrinter"] = "printer" in labs
    return info


def _howto(oo: dict[str, Any], *, menu: str, label: str) -> list[str]:
    steps: list[str] = [
        f"Sign On SoftDent → open {menu or label}.",
    ]
    if oo.get("hasExcel"):
        steps.append(
            "FILE (preferred for NR2 widgets): click the Excel prompt → Enter → "
            "fill Setup (dates, provider 999) → save under C:\\SoftDentReportExports → "
            "run SoftDent period refresh. NR2 parses the XLS/CSV."
        )
    if oo.get("hasPrintPreview"):
        steps.append(
            "VISUAL: click the Print Preview prompt → Enter → Setup if shown → "
            "go to the LAST page for exact totals (do not invent from page 1)."
        )
    steps.append("NEVER click Printer (offline hang). Excel or Print Preview only.")
    return steps


def validate_one(rid: str, meta: dict[str, Any]) -> dict[str, Any]:
    from pywinauto import Application

    entry: dict[str, Any] = {
        "id": rid,
        "label": meta.get("label"),
        "menuPath": meta.get("guiWin32Path") or meta.get("guiMenuPath"),
        "ok": False,
        "preferredHow": None,
        "howToGetData": [],
        "passRuleNeverPrinter": True,
    }
    if meta.get("preferredSource") == "database":
        entry["ok"] = True
        entry["preferredHow"] = "database"
        entry["howToGetData"] = [
            "Use SoftDent ODBC / Sensei / sd_* SQLite when populated (fast ops detail). "
            "Not a SoftDent GUI Output Options report."
        ]
        return entry

    path = str(meta.get("guiWin32Path") or "").strip()
    if not path:
        entry["error"] = "no_guiWin32Path"
        return entry

    _cancel_modals()
    hwnd = _focus()
    try:
        app = Application(backend="win32").connect(handle=hwnd)
        app.window(handle=hwnd).menu_select(path)
    except Exception as exc:
        entry["error"] = f"menu_select:{type(exc).__name__}:{exc}"
        _cancel_modals()
        return entry

    oo: dict[str, Any] = {"present": False}
    for _ in range(28):
        cancel_printer_dialogs(max_rounds=1)
        oo = _output_options()
        if oo.get("present"):
            break
        time.sleep(0.25)

    entry["outputOptions"] = oo
    if not oo.get("present"):
        entry["error"] = "output_options_missing"
        entry["howToGetData"] = [
            "Output Options did not appear — cancel any Setup and retry the menu path. "
            "When it appears: Excel or Print Preview only."
        ]
        _cancel_modals()
        return entry

    # Rule: SoftDent may SHOW Printer as an option, but we must never choose it
    entry["printerShownButForbidden"] = bool(oo.get("hasPrinter"))
    entry["howToGetData"] = _howto(oo, menu=path, label=str(meta.get("label") or rid))
    if oo.get("hasExcel"):
        entry["preferredHow"] = "excel"
        entry["ok"] = True
    elif oo.get("hasPrintPreview"):
        entry["preferredHow"] = "print_preview"
        entry["ok"] = True
    else:
        entry["preferredHow"] = "unknown"
        entry["ok"] = False
        entry["error"] = "no_excel_or_preview_button"
        entry["passRuleNeverPrinter"] = False

    # Validation gate: must have Excel and/or Preview; must document never Printer
    if entry["ok"] and not (oo.get("hasExcel") or oo.get("hasPrintPreview")):
        entry["ok"] = False
    _cancel_modals()
    try:
        _focus()
    except Exception:
        pass
    time.sleep(0.4)
    return entry


def main() -> int:
    payload: dict[str, Any] = {
        "ok": False,
        "validatedAt": _utc(),
        "hardRule": "Output Options: Excel prompt OR Print Preview prompt only — NEVER Printer.",
        "reports": {},
        "summary": [],
    }
    if not softdent_main_running():
        sign = ensure_softdent_signed_on(timeout_s=60.0, force_change_login=False)
    else:
        sign = ensure_softdent_signed_on(timeout_s=20.0, force_change_login=False)
    payload["signOn"] = {
        "ok": bool(sign.get("ok")),
        "signedOn": bool(sign.get("signedOn")),
        "steps": sign.get("steps"),
    }
    if not softdent_main_running():
        payload["error"] = "SoftDent not running"
        OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps(payload, indent=2))
        return 2

    catalog = load_master_reports()
    for rid in catalog.get("masterOrder") or []:
        meta = (catalog.get("reports") or {}).get(rid) or {}
        print(f"VALIDATE {rid} …", flush=True)
        entry = validate_one(rid, meta)
        payload["reports"][rid] = entry
        how = entry.get("preferredHow")
        payload["summary"].append(
            {
                "id": rid,
                "ok": bool(entry.get("ok")),
                "preferredHow": how,
                "hasExcel": (entry.get("outputOptions") or {}).get("hasExcel"),
                "hasPrintPreview": (entry.get("outputOptions") or {}).get("hasPrintPreview"),
                "neverUsePrinter": True,
            }
        )
        for tip in (entry.get("howToGetData") or [])[:2]:
            print(f"  - {tip[:140]}", flush=True)
        time.sleep(0.5)

    payload["ok"] = all(bool(v.get("ok")) for v in payload["reports"].values())
    payload["finishedAt"] = _utc()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"ok": payload["ok"], "summary": payload["summary"]}, indent=2))
    print(f"Wrote {OUT}", flush=True)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
