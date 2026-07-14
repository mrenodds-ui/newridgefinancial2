"""Validate SoftDent Trans-for-a-Period → Excel (Carestream job aid), mouse/keyboard only."""
from __future__ import annotations

import json
import sys
import time
from datetime import date
from pathlib import Path

import win32con
import win32gui
from pywinauto import Application, mouse
from pywinauto.keyboard import send_keys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "NewRidgeFinancial2"))

from softdent_gui_export import (  # noqa: E402
    EXPORT_ROOT_SHORT,
    _main_softdent_hwnd,
    _open_accounting_report,
    cancel_printer_dialogs,
    dismiss_softdent_alerts,
    find_dialog,
)

LOG = Path(r"C:\SoftDentFinancialExports\softdent_account_tx_excel_validation.json")
DEST = Path(r"C:\SoftDentReportExports")


def force_sd(hwnd: int) -> None:
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        send_keys("%")
        time.sleep(0.05)
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
    time.sleep(0.2)


def click_excel(oo_hwnd: int) -> list[str]:
    force_sd(oo_hwnd)
    r = win32gui.GetWindowRect(oo_hwnd)
    # click dialog to own focus
    mouse.click(coords=((r[0] + r[2]) // 2, (r[1] + r[3]) // 2 - 20))
    time.sleep(0.2)
    buttons: list[str] = []
    app = Application(backend="win32").connect(handle=oo_hwnd)
    dlg = app.window(handle=oo_hwnd)
    for b in dlg.descendants(class_name="Button"):
        lab = (b.window_text() or "").replace("&", "").strip()
        buttons.append(lab)
        if lab.lower() == "excel":
            b.click_input()
            time.sleep(0.25)
            # Enter via mouse on OK if present
            for b2 in dlg.descendants(class_name="Button"):
                if (b2.window_text() or "").replace("&", "").strip().lower() == "ok":
                    b2.click_input()
                    return buttons
            send_keys("{ENTER}", pause=0.05)
            return buttons
    raise RuntimeError(f"Excel button missing; buttons={buttons}")


def main() -> None:
    learned = {
        "primaryExcelPath": "Reports → Accounting → Trans for a Period → Output Options → Excel",
        "jobAid": "Carestream SD_Trans_for_a_Period_JA_FINAL.pdf",
        "lineLevelFormat": "List Each Transaction Separately",
        "singleAccountPath": "Account/Patient → Transactions tab → Print Transactions → Output Options",
    }
    result: dict = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "learnedFromWeb": learned, "steps": []}

    dismiss_softdent_alerts()
    cancel_printer_dialogs()
    main_h = _main_softdent_hwnd()
    force_sd(main_h)

    start = date(2026, 1, 1)
    end = date.today()
    print("open Trans for a Period", flush=True)
    _open_accounting_report("transactions", "t")
    result["steps"].append("opened_trans_for_period")

    oo = None
    for _ in range(40):
        cancel_printer_dialogs(max_rounds=1)
        oo = find_dialog("Output Options")
        if oo:
            break
        time.sleep(0.25)
    if not oo:
        result["ok"] = False
        result["error"] = "Output Options missing"
        LOG.write_text(json.dumps(result, indent=2), encoding="utf-8")
        raise SystemExit(2)

    buttons = click_excel(int(oo.handle))
    result["outputOptionButtons"] = buttons
    result["excelButtonPresent"] = "Excel" in buttons
    result["steps"].append("excel_clicked")
    print("Excel OK buttons", buttons, flush=True)
    time.sleep(1.2)

    # Report Setup
    setup = None
    for _ in range(50):
        cancel_printer_dialogs(max_rounds=1)
        setup = find_dialog("Report Setup")
        if not setup:
            # title contains Setup
            for title_hint in ("Setup", "Transactions"):
                # scan via find_dialog exact only — use win32 enum
                pass
        if setup:
            break
        # SoftDent may title it differently
        from softdent_gui_export import _desktop_dialogs

        for w in _desktop_dialogs():
            t = (w.window_text() or "").lower()
            if "setup" in t or "transactions for a period" in t:
                setup = w
                break
        if setup:
            break
        time.sleep(0.25)

    if not setup:
        result["ok"] = False
        result["error"] = "Report Setup missing after Excel"
        LOG.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        raise SystemExit(3)

    force_sd(int(setup.handle))
    sh = int(setup.handle)
    start_txt = start.strftime("%m/%d/%y")
    end_txt = end.strftime("%m/%d/%y")
    # mouse click setup then tab fields
    r = win32gui.GetWindowRect(sh)
    mouse.click(coords=((r[0] + r[2]) // 2, (r[1] + r[3]) // 2))
    time.sleep(0.2)
    send_keys("{TAB}", pause=0.05)
    send_keys("^a", pause=0.03)
    send_keys(start_txt, pause=0.03)
    send_keys("{TAB}", pause=0.05)
    send_keys("^a", pause=0.03)
    send_keys(end_txt, pause=0.03)
    send_keys("{TAB}", pause=0.05)
    send_keys("^a", pause=0.03)
    send_keys("999", pause=0.03)
    # OK button mouse
    try:
        app = Application(backend="win32").connect(handle=sh)
        for b in app.window(handle=sh).descendants(class_name="Button"):
            if (b.window_text() or "").replace("&", "").strip().lower() == "ok":
                b.click_input()
                break
        else:
            send_keys("{ENTER}", pause=0.05)
    except Exception:
        send_keys("{ENTER}", pause=0.05)
    result["steps"].append(f"setup_{start_txt}_{end_txt}")
    print("setup submitted", start_txt, end_txt, flush=True)
    time.sleep(1.5)

    save = None
    for _ in range(60):
        cancel_printer_dialogs(max_rounds=1)
        save = find_dialog("Select File Name")
        if save:
            break
        time.sleep(0.25)
    if not save:
        result["ok"] = False
        result["error"] = "Select File Name missing"
        LOG.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        raise SystemExit(4)

    force_sd(int(save.handle))
    stem = f"TXN{start.strftime('%y%m%d')}"
    short = rf"{EXPORT_ROOT_SHORT}\{stem}"
    r = win32gui.GetWindowRect(int(save.handle))
    mouse.click(coords=((r[0] + r[2]) // 2, (r[1] + r[3]) // 2))
    time.sleep(0.15)
    send_keys("^a", pause=0.03)
    send_keys(short, pause=0.03)
    try:
        app = Application(backend="win32").connect(handle=int(save.handle))
        for b in app.window(handle=int(save.handle)).descendants(class_name="Button"):
            if (b.window_text() or "").replace("&", "").strip().lower() == "ok":
                b.click_input()
                break
        else:
            send_keys("{ENTER}", pause=0.05)
    except Exception:
        send_keys("{ENTER}", pause=0.05)
    result["steps"].append(f"save_{short}")
    print("save", short, flush=True)
    time.sleep(4.0)
    cancel_printer_dialogs()

    produced = None
    for cand in list(DEST.glob(f"{stem}.*")) + list(DEST.glob("transactions_for_period*")):
        if cand.is_file() and cand.stat().st_mtime > time.time() - 120:
            produced = cand
            break
    if not produced:
        # any new file in DEST
        newest = sorted(DEST.glob("*"), key=lambda p: p.stat().st_mtime if p.is_file() else 0, reverse=True)
        for p in newest[:5]:
            if p.is_file() and p.stat().st_mtime > time.time() - 120:
                produced = p
                break

    result["saved"] = str(produced) if produced else None
    result["ok"] = bool(produced)
    if produced:
        raw = produced.read_bytes().decode("latin-1", errors="ignore")
        low = raw.lower()
        lines = [ln.strip() for ln in raw.splitlines() if "nickel" in ln.lower()]
        result["bytes"] = produced.stat().st_size
        result["nickelMentions"] = low.count("nickel")
        result["hasDonnaNickel"] = "donna" in low and "nickel" in low
        result["sampleNickelLines"] = lines[:12]
        print("nickel", result["nickelMentions"], "donna", result["hasDonnaNickel"], flush=True)
        for ln in lines[:8]:
            print("HIT", ln[:140], flush=True)

    LOG.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print("WROTE", LOG, "ok=", result["ok"], flush=True)
    raise SystemExit(0 if result["ok"] else 5)


if __name__ == "__main__":
    main()
