"""SoftDent desktop pull — keyboard/mouse Sign On COMPUTE/computer, then Donna Nickel txs.

Hard rules: SoftDent UI only (no DB). Keyboard or mouse. Never Esc. Never Printer.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import win32con
import win32gui
import win32process
from pywinauto.keyboard import send_keys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "NewRidgeFinancial2"))

USER = "COMPUTE"
PASSWORD = "computer"  # SoftDent case-sensitive lowercase
PATIENT_ID = "27002"
PATIENT_NAME = "Donna Nickel"
OUTBOX = Path(r"C:\SoftDentReportExports")
LOG = Path(r"C:\SoftDentFinancialExports\donna_nickel_desktop_pull.json")


def sd_pids() -> set[int]:
    import ctypes
    from ctypes import wintypes

    class PE(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    k = ctypes.windll.kernel32
    snap = k.CreateToolhelp32Snapshot(0x00000002, 0)
    pe = PE()
    pe.dwSize = ctypes.sizeof(PE)
    out: set[int] = set()
    try:
        if k.Process32FirstW(snap, ctypes.byref(pe)):
            while True:
                if (pe.szExeFile or "").upper().startswith("SDWIN"):
                    out.add(int(pe.th32ProcessID))
                if not k.Process32NextW(snap, ctypes.byref(pe)):
                    break
    finally:
        k.CloseHandle(snap)
    return out


def enum_sd() -> list[dict]:
    pids = sd_pids()
    wins: list[dict] = []

    def cb(h, _):
        if not win32gui.IsWindowVisible(h):
            return True
        try:
            _, pid = win32process.GetWindowThreadProcessId(h)
        except Exception:
            return True
        if pid not in pids:
            return True
        wins.append(
            {
                "hwnd": int(h),
                "title": win32gui.GetWindowText(h) or "",
                "class": win32gui.GetClassName(h) or "",
            }
        )
        return True

    win32gui.EnumWindows(cb, None)
    return wins


def force_fg(hwnd: int) -> None:
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    except Exception:
        pass
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        try:
            send_keys("%")
            time.sleep(0.05)
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
    time.sleep(0.25)


def find_title(substr: str) -> int | None:
    s = substr.lower()
    for w in enum_sd():
        if s in w["title"].lower():
            return w["hwnd"]
    return None


def find_main() -> int | None:
    for w in enum_sd():
        if "SoftDent Software" in w["title"]:
            return w["hwnd"]
    return None


def find_login() -> int | None:
    for w in enum_sd():
        t = w["title"].lower()
        if "login" in t or "sign on" in t:
            return w["hwnd"]
    return None


def dismiss_alerts() -> int:
    """Enter/Alt+C on SoftDent #32770 alerts. Never Esc."""
    n = 0
    for _ in range(8):
        hit = False
        for w in enum_sd():
            if w["class"] != "#32770":
                continue
            title = w["title"]
            low = title.lower()
            if "login" in low or "sign on" in low:
                continue
            if "output options" in low or "select file" in low or "report setup" in low:
                continue
            # SoftDent message / leftover Account prompt titled "SoftDent"
            force_fg(w["hwnd"])
            send_keys("%c", pause=0.05)  # Cancel if present
            time.sleep(0.25)
            if find_title(title) == w["hwnd"] or any(
                x["hwnd"] == w["hwnd"] for x in enum_sd()
            ):
                force_fg(w["hwnd"])
                send_keys("{ENTER}", pause=0.05)
                time.sleep(0.3)
            n += 1
            hit = True
            break
        if not hit:
            break
    return n


def mouse_click_center(hwnd: int) -> None:
    """Mouse click SoftDent dialog center (allowed)."""
    try:
        from pywinauto import mouse

        rect = win32gui.GetWindowRect(hwnd)
        x = (rect[0] + rect[2]) // 2
        y = (rect[1] + rect[3]) // 2
        mouse.click(coords=(x, y))
        time.sleep(0.2)
    except Exception as exc:
        print("mouse click fail", type(exc).__name__, flush=True)


def sign_on_keyboard_or_mouse() -> dict:
    """Sign On: keyboard or mouse. User COMPUTE / password computer."""
    dismiss_alerts()
    login = find_login()
    if login is None:
        main = find_main()
        if main:
            # May need Change Login — only if main is usable
            return {"ok": True, "signedOn": True, "already": True, "windows": enum_sd()}
        # Untitled SoftDent dialog may be login-like — check for Edit fields
        soft = find_title("SoftDent")
        if soft and soft != find_main():
            login = soft
        else:
            return {"ok": False, "error": "no login dialog", "windows": enum_sd()}

    print(f"Sign On hwnd={login} titles={[w['title'] for w in enum_sd()]}", flush=True)
    force_fg(login)
    mouse_click_center(login)  # focus with mouse
    time.sleep(0.2)

    # Keyboard: clear user, type COMPUTE, Tab, computer, Enter
    send_keys("^a", pause=0.04)
    time.sleep(0.08)
    send_keys("{BACKSPACE}", pause=0.04)
    time.sleep(0.08)
    send_keys(USER, pause=0.05)
    print("typed COMPUTE", flush=True)
    time.sleep(0.2)
    send_keys("{TAB}", pause=0.05)
    time.sleep(0.15)
    send_keys(PASSWORD, pause=0.05)
    print("typed computer", flush=True)
    time.sleep(0.2)
    send_keys("{ENTER}", pause=0.05)
    print("Enter Sign On", flush=True)

    for i in range(40):
        time.sleep(0.4)
        dismiss_alerts()
        if find_login() is None and find_main():
            return {"ok": True, "signedOn": True, "wait_s": round((i + 1) * 0.4, 1)}
    return {"ok": False, "error": "still not signed on", "windows": enum_sd()}


def open_change_login_if_needed() -> None:
    """If main is up but menus disabled, open File→Change Login via keyboard."""
    main = find_main()
    if not main:
        return
    force_fg(main)
    # F10 File menu → look for Change Login (often under File)
    send_keys("{F10}", pause=0.05)
    time.sleep(0.35)
    send_keys("f", pause=0.05)
    time.sleep(0.35)
    send_keys("c", pause=0.05)  # Change Login if accelerator
    time.sleep(0.8)


def f10_reports_trans_period() -> dict:
    """Keyboard: F10 → Reports → Accounting → Trans for a Period. Never Alt+R (AMD)."""
    main = find_main()
    if not main:
        return {"ok": False, "error": "no main"}
    force_fg(main)
    mouse_click_center(main)
    time.sleep(0.2)
    send_keys("{F10}", pause=0.05)
    time.sleep(0.4)
    send_keys("r", pause=0.05)  # Reports
    time.sleep(0.4)
    send_keys("a", pause=0.05)  # Accounting
    time.sleep(0.4)
    # Trans for a Period — letter varies; try T then arrows
    send_keys("t", pause=0.05)
    time.sleep(0.8)
    for _ in range(30):
        if find_title("Output Options"):
            return {"ok": True, "via": "F10 r a t"}
        time.sleep(0.2)
    # Arrow through Accounting submenu looking for Trans
    force_fg(main)
    send_keys("{F10}", pause=0.05)
    time.sleep(0.35)
    send_keys("r", pause=0.05)
    time.sleep(0.35)
    send_keys("a", pause=0.05)
    time.sleep(0.5)
    for _ in range(12):
        send_keys("{DOWN}", pause=0.05)
        time.sleep(0.15)
    send_keys("{ENTER}", pause=0.05)
    time.sleep(1.0)
    if find_title("Output Options"):
        return {"ok": True, "via": "F10 r a Down Enter"}
    return {"ok": False, "error": "no Output Options", "titles": [w["title"] for w in enum_sd()]}


def select_excel() -> dict:
    hwnd = find_title("Output Options")
    if not hwnd:
        return {"ok": False, "error": "no Output Options"}
    force_fg(hwnd)
    # Prefer mouse click on Excel button if present
    try:
        from pywinauto import Application

        app = Application(backend="win32").connect(handle=hwnd)
        dlg = app.window(handle=hwnd)
        for b in dlg.descendants(class_name="Button"):
            lab = (b.window_text() or "").replace("&", "").strip().lower()
            if lab == "printer":
                continue
            if lab == "excel":
                b.click_input()
                time.sleep(0.25)
                send_keys("{ENTER}", pause=0.05)
                return {"ok": True, "method": "mouse_excel"}
    except Exception as exc:
        print("excel mouse fail", type(exc).__name__, flush=True)
    # Keyboard: E then Enter — never P
    send_keys("e", pause=0.05)
    time.sleep(0.2)
    send_keys("{ENTER}", pause=0.05)
    return {"ok": True, "method": "keyboard_e"}


def open_donna_f3() -> dict:
    main = find_main()
    if not main:
        return {"ok": False, "error": "no main"}
    force_fg(main)
    mouse_click_center(main)
    send_keys("{F3}", pause=0.05)  # Account
    time.sleep(1.0)
    send_keys("^a", pause=0.04)
    send_keys(PATIENT_ID, pause=0.05)
    time.sleep(0.2)
    send_keys("{ENTER}", pause=0.05)
    time.sleep(1.5)
    return {"ok": True, "titles": [w["title"] for w in enum_sd()]}


def try_print_tx_excel() -> dict:
    before = {p.name: p.stat().st_mtime for p in OUTBOX.glob("*") if p.is_file()}
    main = find_main()
    if main:
        force_fg(main)
    # Options → Print Transactions (keyboard)
    for seq in ("%o", "o"):
        send_keys(seq, pause=0.05)
        time.sleep(0.5)
        send_keys("p", pause=0.05)
        time.sleep(0.7)
        if find_title("Output Options"):
            break
    if not find_title("Output Options"):
        return {"ok": False, "error": "no Output Options after Print Transactions", "titles": [w["title"] for w in enum_sd()]}
    oo = select_excel()
    time.sleep(1.0)
    send_keys("{ENTER}", pause=0.05)
    time.sleep(1.0)
    # Save path
    for title in ("Select File Name", "Save As"):
        h = find_title(title)
        if h:
            force_fg(h)
            send_keys("^a", pause=0.03)
            send_keys(r"C:\SOFTDE~1\donna_nickel_27002.xls", pause=0.03)
            send_keys("{ENTER}", pause=0.05)
            time.sleep(1.5)
    saved = None
    for _ in range(25):
        for p in OUTBOX.glob("*"):
            if p.is_file() and (p.name not in before or p.stat().st_mtime > before.get(p.name, 0)):
                saved = str(p)
                break
        if saved:
            break
        time.sleep(0.4)
    return {"ok": bool(saved), "saved": saved, "outputOptions": oo, "titles": [w["title"] for w in enum_sd()]}


def complete_trans_period_excel() -> dict:
    before = {p.name: p.stat().st_mtime for p in OUTBOX.glob("*") if p.is_file()}
    opened = f10_reports_trans_period()
    if not opened.get("ok"):
        return opened
    oo = select_excel()
    time.sleep(1.2)
    # Dates covering Donna last visit 2026-02-18
    send_keys("^a", pause=0.03)
    send_keys("01/01/2024", pause=0.04)
    send_keys("{TAB}", pause=0.05)
    send_keys("^a", pause=0.03)
    send_keys(time.strftime("%m/%d/%Y"), pause=0.04)
    send_keys("{ENTER}", pause=0.05)
    time.sleep(2.0)
    for title in ("Select File Name", "Save As", "Report Setup"):
        h = find_title(title)
        if not h:
            continue
        force_fg(h)
        if "file" in title.lower() or "save" in title.lower():
            send_keys("^a", pause=0.03)
            send_keys(r"C:\SOFTDE~1\transactions_for_period_all.xls", pause=0.03)
            send_keys("{ENTER}", pause=0.05)
        else:
            send_keys("{ENTER}", pause=0.05)
        time.sleep(1.2)
    saved = None
    for _ in range(40):
        for p in OUTBOX.glob("*"):
            if p.is_file() and (p.name not in before or p.stat().st_mtime > before.get(p.name, 0)):
                saved = str(p)
                break
        if saved:
            break
        # Cancel printer if SoftDent misfires
        for w in enum_sd():
            if "printer" in w["title"].lower() or "waiting for" in w["title"].lower():
                force_fg(w["hwnd"])
                send_keys("%c", pause=0.05)
        time.sleep(0.5)
    return {
        "ok": bool(saved),
        "saved": saved,
        "opened": opened,
        "outputOptions": oo,
        "titles": [w["title"] for w in enum_sd()],
    }


def main() -> None:
    print("SoftDent desktop: keyboard/mouse Sign On COMPUTE/computer", flush=True)
    print("windows", enum_sd(), flush=True)
    result: dict = {
        "source": "softdent_desktop_ui_only",
        "signOnUser": USER,
        "patientId": PATIENT_ID,
        "patientName": PATIENT_NAME,
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    so = sign_on_keyboard_or_mouse()
    result["signOn"] = {k: v for k, v in so.items() if k != "windows"}
    print("signOn", result["signOn"], flush=True)

    if not so.get("ok"):
        # Try Change Login then retry
        open_change_login_if_needed()
        time.sleep(0.8)
        so = sign_on_keyboard_or_mouse()
        result["signOnRetry"] = {k: v for k, v in so.items() if k != "windows"}
        print("signOnRetry", result["signOnRetry"], flush=True)

    if not so.get("ok") and not result.get("signOnRetry", {}).get("ok"):
        LOG.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        raise SystemExit(2)

    time.sleep(1.0)
    dismiss_alerts()

    # Test path 1: Donna account F3 → Print Transactions → Excel
    donna = open_donna_f3()
    result["openDonna"] = donna
    print("openDonna", donna, flush=True)
    pt = try_print_tx_excel()
    result["printTransactions"] = pt
    print("printTransactions", pt, flush=True)

    if not pt.get("saved"):
        send_keys("%c", pause=0.05)
        time.sleep(0.4)
        dismiss_alerts()
        tx = complete_trans_period_excel()
        result["transForPeriod"] = tx
        print("transForPeriod", tx, flush=True)

    result["ok"] = bool(
        (result.get("printTransactions") or {}).get("saved")
        or (result.get("transForPeriod") or {}).get("saved")
    )
    result["windowsFinal"] = enum_sd()
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print("WROTE", LOG, "ok=", result["ok"], flush=True)
    raise SystemExit(0 if result["ok"] else 3)


if __name__ == "__main__":
    main()
