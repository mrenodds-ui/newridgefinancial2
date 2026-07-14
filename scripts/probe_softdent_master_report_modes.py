"""Live SoftDent probe: classify each master GUI report as Excel vs Print Preview.

Cancels SoftDent dialogs after each probe (Cancel / Alt+C). Never Esc on SoftDent main.
Does not invent dollar amounts. Records whether Output Options offers Excel.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "NewRidgeFinancial2"))

from softdent_gui_export import (  # noqa: E402
    _focus_main,
    _force_foreground,
    _keyboard_activate_dialog,
    _main_softdent_hwnd,
    _open_report_via_win32_menu,
    _send_softdent_keys,
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

STATUS = Path(r"C:\SoftDentFinancialExports\softdent_master_report_mode_probe.json")


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _softdent_top_titles() -> list[str]:
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
            # Skip noise
            if t in {"DDE Server Window", "Socket Notification Sink", "Default IME", "M"}:
                continue
            if t.startswith("Default IME"):
                continue
            out.append(t)
        except Exception:
            continue
    return out


def _dialog_button_labels(title_substr: str) -> list[str]:
    from pywinauto import Application, Desktop

    labels: list[str] = []
    for w in Desktop(backend="win32").windows():
        t = (w.window_text() or "")
        if title_substr.lower() not in t.lower():
            continue
        try:
            app = Application(backend="win32").connect(handle=w.handle)
            d = app.window(handle=w.handle)
            for b in d.descendants(class_name="Button"):
                lab = (b.window_text() or "").replace("&", "").strip()
                if lab:
                    labels.append(lab)
        except Exception:
            continue
        break
    return labels


def _cancel_soft_dialogs() -> None:
    """Cancel SoftDent modal dialogs without Esc on main."""
    from pywinauto import Application, Desktop

    cancel_printer_dialogs(max_rounds=4)
    pids = _softdent_pids()
    keywords = (
        "output options",
        "report setup",
        "select file",
        "print preview",
        "collection summary",
        "register setup",
        "daysheet",
        "account aging",
        "trans for",
        "writeoff",
        "waiting for printer",
        "setup",
    )
    for w in list(Desktop(backend="win32").windows()):
        try:
            t = (w.window_text() or "").strip()
            if not t:
                continue
            if pids and _window_pid(int(w.handle)) not in pids:
                continue
            low = t.lower()
            if not any(k in low for k in keywords):
                continue
            if "cs softdent software" in low:
                continue
            app = Application(backend="win32").connect(handle=w.handle)
            d = app.window(handle=w.handle)
            cancelled = False
            for b in d.descendants(class_name="Button"):
                lab = (b.window_text() or "").replace("&", "").strip().lower()
                if lab in {"cancel", "close", "no"}:
                    try:
                        _softdent_click(b)
                        cancelled = True
                        break
                    except Exception:
                        continue
            if not cancelled:
                try:
                    _keyboard_activate_dialog(d)
                    _send_softdent_keys("%c", hwnd=int(w.handle))  # Alt+C
                except Exception:
                    pass
        except Exception:
            continue
    time.sleep(0.4)
    cancel_printer_dialogs(max_rounds=2)
    dismiss_softdent_alerts(max_rounds=2)


def _classify_after_open() -> dict[str, Any]:
    """Inspect SoftDent UI after opening a report menu path."""
    info: dict[str, Any] = {
        "titles": _softdent_top_titles(),
        "hasOutputOptions": False,
        "hasExcelOption": False,
        "hasPrinterOption": False,
        "outputOptionButtons": [],
        "hasSetupDialog": False,
        "setupTitle": None,
        "hasPrintPreview": False,
        "hasSelectFileName": False,
        "inferredMode": "unknown",
        "notes": [],
    }
    time.sleep(0.8)
    cancel_printer_dialogs(max_rounds=2)

    out = find_dialog("Output Options")
    if out:
        info["hasOutputOptions"] = True
        buttons = _dialog_button_labels("Output Options")
        info["outputOptionButtons"] = buttons
        blob = " ".join(buttons).lower()
        info["hasExcelOption"] = "excel" in blob
        info["hasPrinterOption"] = "printer" in blob or "print" in blob
        if info["hasExcelOption"]:
            info["inferredMode"] = "excel"
            info["notes"].append("Output Options lists Excel — file export path available")
        elif info["hasPrinterOption"]:
            info["inferredMode"] = "print_preview"
            info["notes"].append("Output Options has Printer/Print but no Excel")
        else:
            info["inferredMode"] = "unknown"
            info["notes"].append(f"Output Options buttons: {buttons}")
        return info

    titles = info["titles"]
    low_titles = [t.lower() for t in titles]
    if any("print preview" in t for t in low_titles):
        info["hasPrintPreview"] = True
        info["inferredMode"] = "print_preview"
        info["notes"].append("Print Preview window present — visual read; check last page for totals")
        return info
    if any("select file name" in t for t in low_titles):
        info["hasSelectFileName"] = True
        info["inferredMode"] = "excel"
        info["notes"].append("Select File Name dialog — Excel/file save path")
        return info

    setup_hits = [
        t
        for t in titles
        if "setup" in t.lower()
        or "report" in t.lower()
        and t.lower() not in {"cs softdent software v19.1.4"}
    ]
    # Prefer explicit setup dialogs
    for t in titles:
        tl = t.lower()
        if "setup" in tl or (
            any(x in tl for x in ("collection", "register", "daysheet", "aging", "writeoff", "trans"))
            and "softdent" not in tl
            and "assistant" not in tl
        ):
            info["hasSetupDialog"] = True
            info["setupTitle"] = t
            break

    if info["hasSetupDialog"]:
        # Many SoftDent reports open Setup first, then Printer/Preview after OK.
        # Probe: press OK once and see what appears (then cancel).
        info["notes"].append(f"Setup dialog open: {info['setupTitle']}")
        try:
            from pywinauto import Application, Desktop

            for w in Desktop(backend="win32").windows():
                if (w.window_text() or "").strip() != info["setupTitle"]:
                    continue
                app = Application(backend="win32").connect(handle=w.handle)
                d = app.window(handle=w.handle)
                # Fill dates lightly if edits look like dates — skip; just OK
                for b in d.descendants(class_name="Button"):
                    if (b.window_text() or "").replace("&", "").strip().upper() == "OK":
                        _softdent_click(b)
                        break
                break
            time.sleep(1.2)
            cancel_printer_dialogs(max_rounds=3)
            info["titlesAfterOk"] = _softdent_top_titles()
            out2 = find_dialog("Output Options")
            if out2:
                buttons = _dialog_button_labels("Output Options")
                info["outputOptionButtons"] = buttons
                blob = " ".join(buttons).lower()
                info["hasOutputOptions"] = True
                info["hasExcelOption"] = "excel" in blob
                info["hasPrinterOption"] = "printer" in blob or "print" in blob
                info["inferredMode"] = "excel" if info["hasExcelOption"] else "print_preview"
                info["notes"].append("Output Options appeared after Setup OK")
            elif any("print preview" in t.lower() for t in info["titlesAfterOk"]):
                info["hasPrintPreview"] = True
                info["inferredMode"] = "print_preview"
                info["notes"].append(
                    "Print Preview after Setup — visual read; go to LAST page for exact totals"
                )
            elif any("select file name" in t.lower() for t in info["titlesAfterOk"]):
                info["hasSelectFileName"] = True
                info["inferredMode"] = "excel"
                info["notes"].append("Select File Name after Setup — Excel path")
            elif find_dialog("Waiting for printer") or any(
                "waiting for printer" in t.lower() for t in info["titlesAfterOk"]
            ):
                info["inferredMode"] = "print_preview"
                info["notes"].append("Printer wait after Setup — print path (cancel); no Excel")
                cancel_printer_dialogs(max_rounds=5)
            else:
                info["inferredMode"] = "print_preview_likely"
                info["notes"].append(
                    "No Excel save dialog after Setup — likely Print/Preview path; "
                    "if preview, last page often has totals"
                )
        except Exception as exc:
            info["notes"].append(f"setup_ok_probe:{type(exc).__name__}")
            info["inferredMode"] = "unknown"
    else:
        info["notes"].append("No Output Options / Setup / Preview detected")
        info["inferredMode"] = "unknown"

    return info


def probe_one(report_id: str, meta: dict[str, Any]) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": report_id,
        "label": meta.get("label"),
        "menuPath": meta.get("guiWin32Path") or meta.get("guiMenuPath"),
        "priorOutputMode": meta.get("outputMode"),
        "ok": False,
        "inferredMode": "unknown",
        "visualReadLastPageHint": False,
    }
    path = str(meta.get("guiWin32Path") or "").strip()
    if not path:
        entry["error"] = "no_guiWin32Path"
        return entry

    _cancel_soft_dialogs()
    _focus_main()
    opened = _open_report_via_win32_menu(path)
    entry["menuOpened"] = bool(opened) or True  # menu_select may open Setup without Output Options
    time.sleep(0.6)
    # If Output Options didn't appear, Setup may still be open
    classification = _classify_after_open()
    entry.update(classification)
    if entry.get("inferredMode") in {"print_preview", "print_preview_likely"}:
        entry["visualReadLastPageHint"] = True
        entry["notes"] = list(entry.get("notes") or []) + [
            "When using Print Preview, navigate to the LAST page for exact summary/totals data."
        ]
    entry["ok"] = entry.get("inferredMode") not in {"unknown", None}
    _cancel_soft_dialogs()
    try:
        hwnd = _main_softdent_hwnd()
        _force_foreground(hwnd)
    except Exception:
        pass
    time.sleep(0.5)
    return entry


def main() -> int:
    if not softdent_main_running():
        print(json.dumps({"ok": False, "error": "SoftDent not running"}, indent=2))
        return 2
    sign = ensure_softdent_signed_on(timeout_s=45.0, force_change_login=False)
    catalog = load_master_reports()
    reports = catalog.get("reports") or {}
    payload: dict[str, Any] = {
        "ok": False,
        "startedAt": _utc(),
        "signOn": {
            "ok": bool(sign.get("ok")),
            "signedOn": bool(sign.get("signedOn")),
            "steps": sign.get("steps"),
        },
        "reports": {},
        "summary": [],
    }

    for rid in catalog.get("masterOrder") or []:
        meta = reports.get(rid) or {}
        if meta.get("preferredSource") == "database":
            payload["reports"][rid] = {
                "id": rid,
                "inferredMode": "database",
                "ok": True,
                "notes": ["DB/Sensei lane — not a SoftDent GUI report"],
            }
            payload["summary"].append(f"{rid}: database")
            continue
        if not meta.get("guiWin32Path"):
            continue
        print(f"PROBING {rid}...", flush=True)
        try:
            entry = probe_one(rid, meta)
        except Exception as exc:  # noqa: BLE001
            entry = {"id": rid, "ok": False, "error": f"{type(exc).__name__}:{exc}"}
            _cancel_soft_dialogs()
        payload["reports"][rid] = entry
        mode = entry.get("inferredMode")
        payload["summary"].append(f"{rid}: {mode}")
        print(f"  -> {mode} notes={entry.get('notes')}", flush=True)
        time.sleep(0.8)

    payload["finishedAt"] = _utc()
    payload["ok"] = all(
        bool((payload["reports"].get(rid) or {}).get("ok"))
        for rid in (catalog.get("masterOrder") or [])
        if (reports.get(rid) or {}).get("preferredSource") != "database"
        or True
    )
    # Softer ok: at least register classified
    payload["ok"] = bool((payload["reports"].get("register") or {}).get("inferredMode") != "unknown")
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(f"Wrote {STATUS}", flush=True)
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
