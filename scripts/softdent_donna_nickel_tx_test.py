"""SoftDent desktop test: sign on, open Donna Nickel (27002), attempt account tx export."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "NewRidgeFinancial2"))

import win32gui
import win32process
from pywinauto.keyboard import send_keys

from softdent_signon import (
    get_softdent_signon_password,
    load_softdent_signon_env_files,
    resolve_softdent_signon_credentials,
)
from softdent_gui_export import (
    _force_foreground,
    _main_softdent_hwnd,
    _open_report_via_win32_menu,
    _select_output_option_prompt,
    _send_softdent_keys,
    _softdent_pids,
    cancel_printer_dialogs,
    dismiss_softdent_alerts,
    find_dialog,
)

PATIENT_ID = "27002"
PATIENT_NAME = "Donna Nickel"
LOG = Path(r"C:\SoftDentFinancialExports\donna_nickel_account_tx_test.json")
OUTBOX = Path(r"C:\SoftDentReportExports")


def enum_sd_windows() -> list[dict]:
    pids = _softdent_pids()
    out: list[dict] = []

    def cb(h, _):
        if not win32gui.IsWindowVisible(h):
            return True
        try:
            _, pid = win32process.GetWindowThreadProcessId(h)
        except Exception:
            return True
        if pids and pid not in pids:
            return True
        out.append(
            {
                "hwnd": int(h),
                "pid": pid,
                "title": win32gui.GetWindowText(h) or "",
                "class": win32gui.GetClassName(h),
            }
        )
        return True

    win32gui.EnumWindows(cb, None)
    return out


def find_login_hwnd() -> int | None:
    for w in enum_sd_windows():
        if "login" in w["title"].lower():
            return w["hwnd"]
    return None


def sign_on() -> dict:
    load_softdent_signon_env_files()
    creds = resolve_softdent_signon_credentials()
    user = str(creds.get("user") or "COMPUTE")
    password = get_softdent_signon_password()
    if not password:
        return {"ok": False, "error": "no password configured"}

    login = find_login_hwnd()
    if not login:
        try:
            main = _main_softdent_hwnd()
        except Exception:
            main = 0
        if main:
            return {"ok": True, "signedOn": True, "already": True, "main": int(main)}
        return {"ok": False, "error": "no login and no main", "windows": enum_sd_windows()}

    _force_foreground(login)
    time.sleep(0.35)
    send_keys("^a{BACKSPACE}", pause=0.04)
    time.sleep(0.1)
    send_keys(user, pause=0.03)
    time.sleep(0.15)
    send_keys("{TAB}", pause=0.05)
    time.sleep(0.1)
    send_keys(password, pause=0.03)
    time.sleep(0.15)
    send_keys("{ENTER}", pause=0.05)

    for i in range(50):
        time.sleep(0.4)
        if find_login_hwnd() is None:
            return {"ok": True, "signedOn": True, "wait_s": round((i + 1) * 0.4, 1)}
        # SoftDent sometimes shows alert after login
        try:
            dismiss_softdent_alerts()
            cancel_printer_dialogs(max_rounds=1)
        except Exception:
            pass
    return {"ok": False, "error": "login still open", "windows": enum_sd_windows()}


def menu_select_path(menu_path: str) -> bool:
    from pywinauto import Application

    hwnd = _main_softdent_hwnd()
    _force_foreground(hwnd)
    time.sleep(0.2)
    try:
        app = Application(backend="win32").connect(handle=hwnd)
        win = app.window(handle=hwnd)
        win.menu_select(menu_path)
        return True
    except Exception as exc:
        print(f"menu_select fail {menu_path}: {type(exc).__name__}: {exc}", flush=True)
        return False


def open_patient(patient_id: str) -> dict:
    dismiss_softdent_alerts()
    cancel_printer_dialogs()
    hwnd = _main_softdent_hwnd()
    _force_foreground(hwnd)
    time.sleep(0.25)

    steps: list[str] = []
    opened = False
    for path in ("File->Account", "List->Account", "List->Patient", "List->Patients"):
        if menu_select_path(path):
            steps.append(f"menu_ok:{path}")
            opened = True
            break
        steps.append(f"menu_fail:{path}")

    if not opened:
        _send_softdent_keys("{F3}", hwnd=hwnd)
        steps.append("keys:F3")
        time.sleep(0.8)

    time.sleep(0.8)
    # Type patient id
    send_keys("^a", pause=0.05)
    time.sleep(0.1)
    send_keys(patient_id, pause=0.04)
    steps.append(f"typed:{patient_id}")
    time.sleep(0.2)
    send_keys("{ENTER}", pause=0.05)
    time.sleep(1.2)

    wins = enum_sd_windows()
    return {
        "ok": True,
        "steps": steps,
        "titles": [w["title"] for w in wins],
        "windows": wins,
    }


def try_print_transactions_excel() -> dict:
    """From open Account/Patient window, try Print Transactions → Excel."""
    before = {p.name: p.stat().st_mtime for p in OUTBOX.glob("*") if p.is_file()}
    hwnd = _main_softdent_hwnd()
    _force_foreground(hwnd)
    time.sleep(0.2)

    # Common SoftDent accelerators / menu on Account Transactions window
    attempts = []
    for keys, label in (
        ("%p", "alt_p"),  # often Print menu
        ("%t", "alt_t"),  # Transactions?
    ):
        try:
            _send_softdent_keys(keys, hwnd=hwnd)
            attempts.append(label)
            time.sleep(0.6)
            if find_dialog("Output Options"):
                break
        except Exception as exc:
            attempts.append(f"{label}:fail:{type(exc).__name__}")

    # Also try right-click-ish Options via keyboard: Alt then letters for Print Transactions
    # SoftDent Account window often has Options button / menu with Print Transactions
    if not find_dialog("Output Options"):
        for seq in ("o", "%o", "{F10}o"):
            try:
                _send_softdent_keys(seq, hwnd=hwnd)
                attempts.append(f"seq:{seq}")
                time.sleep(0.5)
                # arrow to Print Transactions if a menu opened — type P
                _send_softdent_keys("p", hwnd=hwnd)
                time.sleep(0.4)
                if find_dialog("Output Options"):
                    break
            except Exception as exc:
                attempts.append(f"seq_fail:{type(exc).__name__}")

    out = find_dialog("Output Options")
    if not out:
        return {
            "ok": False,
            "error": "Output Options not found after Print Transactions attempts",
            "attempts": attempts,
            "titles": [w["title"] for w in enum_sd_windows()],
        }

    try:
        _select_output_option_prompt("excel")
    except Exception as exc:
        return {
            "ok": False,
            "error": f"output_options:{type(exc).__name__}:{exc}",
            "attempts": attempts,
        }

    # Wait for new file in outbox
    saved = None
    for _ in range(40):
        time.sleep(0.5)
        cancel_printer_dialogs(max_rounds=1)
        for p in OUTBOX.glob("*"):
            if not p.is_file():
                continue
            m = p.stat().st_mtime
            if p.name not in before or m > before.get(p.name, 0):
                saved = str(p)
                break
        if saved:
            break
        # SoftDent Save dialog?
        for title in ("Select File Name", "Save As", "Report Setup"):
            dlg = find_dialog(title)
            if dlg:
                attempts.append(f"dialog:{title}")

    return {
        "ok": bool(saved),
        "saved": saved,
        "attempts": attempts,
        "titles": [w["title"] for w in enum_sd_windows()],
    }


def try_trans_for_period_excel() -> dict:
    """Fallback path: Reports → Accounting → Trans for a Period → Excel (all patients)."""
    before = {p.name: p.stat().st_mtime for p in OUTBOX.glob("*") if p.is_file()}
    ok = _open_report_via_win32_menu("Reports->Accounting->Trans for a Period")
    if not ok and not find_dialog("Output Options"):
        return {"ok": False, "error": "could not open Trans for a Period", "titles": [w["title"] for w in enum_sd_windows()]}
    try:
        _select_output_option_prompt("excel")
    except Exception as exc:
        return {"ok": False, "error": f"output:{type(exc).__name__}:{exc}"}

    # Report setup — use broad dates covering Donna activity; Tab through and OK
    time.sleep(1.0)
    setup = find_dialog("Report Setup") or find_dialog("Transactions for a Period") or find_dialog("Transactions For a Period")
    hwnd = _main_softdent_hwnd()
    # Type start 01/01/2024 end today-ish — SoftDent often has start focused
    send_keys("^a", pause=0.03)
    send_keys("01/01/2024", pause=0.03)
    send_keys("{TAB}", pause=0.05)
    send_keys("^a", pause=0.03)
    send_keys(time.strftime("%m/%d/%Y"), pause=0.03)
    send_keys("{ENTER}", pause=0.05)
    time.sleep(2.0)

    saved = None
    for _ in range(60):
        time.sleep(0.5)
        cancel_printer_dialogs(max_rounds=1)
        for p in OUTBOX.glob("*"):
            if not p.is_file():
                continue
            if p.name not in before or p.stat().st_mtime > before.get(p.name, 0):
                # also SoftDent may drop .xls on desktop / default excel path
                saved = str(p)
                break
        if saved:
            break

    return {
        "ok": bool(saved) or bool(find_dialog("Select File Name")),
        "saved": saved,
        "setup_seen": bool(setup),
        "titles": [w["title"] for w in enum_sd_windows()],
    }


def main() -> None:
    print("START", flush=True)
    result: dict = {
        "patientId": PATIENT_ID,
        "patientName": PATIENT_NAME,
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    so = sign_on()
    result["signOn"] = so
    print("SIGNON", json.dumps(so, default=str), flush=True)
    if not so.get("ok"):
        LOG.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        raise SystemExit(2)

    time.sleep(1.0)
    dismiss_softdent_alerts()
    cancel_printer_dialogs()

    opened = open_patient(PATIENT_ID)
    result["openPatient"] = {k: v for k, v in opened.items() if k != "windows"}
    print("OPEN titles", opened.get("titles"), flush=True)

    # Prefer patient Print Transactions if an account/patient window is open
    titles_l = " | ".join(opened.get("titles") or []).lower()
    if any(x in titles_l for x in ("account", "patient", "transaction", "nickel")):
        pt = try_print_transactions_excel()
        result["printTransactions"] = pt
        print("PRINT_TX", json.dumps(pt, default=str)[:1500], flush=True)
    else:
        result["printTransactions"] = {"skipped": True, "reason": "no account/patient window title"}

    # If patient path failed, still try period Trans (all patients) as the scale path
    if not (result.get("printTransactions") or {}).get("ok"):
        print("FALLBACK Trans for a Period", flush=True)
        # Close stray dialogs first without Esc on main
        cancel_printer_dialogs()
        dismiss_softdent_alerts()
        # Try Alt+C / Enter to clear lookup if needed
        try:
            hwnd = _main_softdent_hwnd()
            _force_foreground(hwnd)
            send_keys("%c", pause=0.05)
            time.sleep(0.3)
        except Exception:
            pass
        tx = try_trans_for_period_excel()
        result["transForPeriod"] = tx
        print("TRANS_PERIOD", json.dumps(tx, default=str)[:1500], flush=True)

    result["ok"] = bool(
        (result.get("printTransactions") or {}).get("ok")
        or (result.get("transForPeriod") or {}).get("ok")
    )
    result["windowsFinal"] = enum_sd_windows()
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print("WROTE", LOG, "ok=", result["ok"], flush=True)


if __name__ == "__main__":
    main()
