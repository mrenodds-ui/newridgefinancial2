"""Switch SoftDent Account Mode to Donna Nickel, then Excel from Account Transactions."""
from __future__ import annotations

import json
import time
from pathlib import Path

import win32con
import win32gui
import win32process
from pywinauto import Application, mouse
from pywinauto.keyboard import send_keys

OUTBOX = Path(r"C:\SoftDentReportExports")
LOG = Path(r"C:\SoftDentFinancialExports\donna_nickel_account_tx_tab.json")
SAVE = r"C:\SOFTDE~1\donna_nickel_account_tx.xls"


def tops():
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
    snap = k.CreateToolhelp32Snapshot(2, 0)
    pe = PE()
    pe.dwSize = ctypes.sizeof(PE)
    pids = set()
    if k.Process32FirstW(snap, ctypes.byref(pe)):
        while True:
            if (pe.szExeFile or "").upper().startswith("SDWIN"):
                pids.add(int(pe.th32ProcessID))
            if not k.Process32NextW(snap, ctypes.byref(pe)):
                break
    k.CloseHandle(snap)
    out = []

    def cb(h, _):
        if win32gui.IsWindowVisible(h):
            _, pid = win32process.GetWindowThreadProcessId(h)
            if pid in pids:
                out.append((int(h), win32gui.GetWindowText(h) or "", win32gui.GetClassName(h) or ""))
        return True

    win32gui.EnumWindows(cb, None)
    return out


def main_hwnd() -> int:
    for h, t, _ in tops():
        if "SoftDent Software" in t:
            return h
    raise RuntimeError("no SoftDent main")


def fg(h: int) -> None:
    try:
        win32gui.SetForegroundWindow(h)
    except Exception:
        send_keys("%")
        time.sleep(0.05)
        try:
            win32gui.SetForegroundWindow(h)
        except Exception:
            pass
    time.sleep(0.2)


def walk(h):
    stack = [h]
    while stack:
        cur = stack.pop()
        yield cur
        try:
            ch = win32gui.GetWindow(cur, win32con.GW_CHILD)
        except Exception:
            continue
        kids = []
        while ch:
            kids.append(ch)
            ch = win32gui.GetWindow(ch, win32con.GW_HWNDNEXT)
        stack.extend(reversed(kids))


def click(h: int) -> None:
    r = win32gui.GetWindowRect(h)
    mouse.click(coords=((r[0] + r[2]) // 2, (r[1] + r[3]) // 2))
    time.sleep(0.35)


def find_text(root: int, needle: str, classes=None) -> int | None:
    n = needle.lower().replace("&", "")
    for h in walk(root):
        try:
            t = (win32gui.GetWindowText(h) or "").replace("&", "")
            c = win32gui.GetClassName(h) or ""
        except Exception:
            continue
        if n in t.lower() and (classes is None or c in classes):
            return int(h)
    return None


def account_mode_patient(root: int) -> dict:
    """Read Account:/Patient: static pairs near Account Mode."""
    labels = []
    for h in walk(root):
        try:
            t = win32gui.GetWindowText(h) or ""
            c = win32gui.GetClassName(h) or ""
        except Exception:
            continue
        if c == "Static" and t.strip():
            labels.append(t.strip())
    blob = " | ".join(labels)
    return {
        "hasDonna": "Donna" in blob and "Nickel" in blob,
        "hasNickel": "Nickel" in blob,
        "sample": [x for x in labels if any(k in x for k in ("Donna", "Nickel", "Account Mode", "Dorsey", "529"))][:20],
        "blobHit": ("Donna Nickel" in blob) or ("Nickel" in blob and "Donna" in blob),
    }


def dismiss_clock_out() -> None:
    for h, t, _ in tops():
        if "clock" in t.lower():
            fg(h)
            send_keys("%c", pause=0.05)
            time.sleep(0.4)


def find_dialog(title: str) -> int | None:
    for h, t, c in tops():
        if t == title:
            return h
    return None


def select_excel() -> bool:
    oo = find_dialog("Output Options")
    if not oo:
        return False
    fg(oo)
    try:
        app = Application(backend="win32").connect(handle=oo)
        for b in app.window(handle=oo).descendants(class_name="Button"):
            lab = (b.window_text() or "").replace("&", "").strip().lower()
            if lab == "printer":
                continue
            if lab == "excel":
                b.click_input()
                time.sleep(0.2)
                send_keys("{ENTER}", pause=0.05)
                return True
    except Exception:
        pass
    send_keys("e", pause=0.05)
    time.sleep(0.15)
    send_keys("{ENTER}", pause=0.05)
    return True


def main() -> None:
    dismiss_clock_out()
    m = main_hwnd()
    fg(m)
    before = {p.name: p.stat().st_mtime for p in OUTBOX.glob("*") if p.is_file()}
    result: dict = {"patient": "Donna Nickel", "id": "27002", "at": time.strftime("%Y-%m-%dT%H:%M:%S")}

    # Close leftover FIND Account
    for h in list(walk(m)):
        try:
            if win32gui.GetWindowText(h) == "FIND Account":
                cbtn = find_text(h, "Cancel", {"Button"})
                if cbtn:
                    click(cbtn)
        except Exception:
            pass

    # F3 → FIND Account → Find By ID → 27002
    fg(m)
    send_keys("{F3}", pause=0.05)
    time.sleep(1.2)
    find_mdi = find_text(m, "FIND Account", {"AfxFrameOrView140"})
    print("FIND", find_mdi, flush=True)
    if find_mdi:
        fg(find_mdi)
        click(find_mdi)

    # Click Find By to switch to ID search if available
    fb = find_text(m, "Find By", {"Button"})
    if fb:
        click(fb)
        time.sleep(0.6)
        print("clicked Find By", flush=True)
        # After Find By, may get a choice dialog — pick ID with keyboard
        send_keys("i", pause=0.05)  # ID
        time.sleep(0.3)
        send_keys("{ENTER}", pause=0.05)
        time.sleep(0.6)

    # Type ID 27002 into focused edit
    send_keys("^a", pause=0.03)
    send_keys("27002", pause=0.05)
    print("typed 27002", flush=True)
    time.sleep(0.2)
    # OK
    ok = find_text(m, "OK", {"Button"})
    if ok:
        click(ok)
    else:
        send_keys("{ENTER}", pause=0.05)
    time.sleep(2.0)

    info = account_mode_patient(m)
    result["accountMode"] = info
    print("accountMode", info, flush=True)

    # If still not Donna, try name search in FIND
    if not info.get("blobHit"):
        fg(m)
        send_keys("{F3}", pause=0.05)
        time.sleep(1.0)
        find_mdi = find_text(m, "FIND Account", {"AfxFrameOrView140"})
        if find_mdi:
            click(find_mdi)
        send_keys("^a", pause=0.03)
        send_keys("Nickel", pause=0.05)
        send_keys("{TAB}", pause=0.05)
        send_keys("^a", pause=0.03)
        send_keys("Donna", pause=0.05)
        ok = find_text(m, "OK", {"Button"})
        if ok:
            click(ok)
        else:
            send_keys("{ENTER}", pause=0.05)
        time.sleep(2.0)
        info = account_mode_patient(m)
        result["accountModeNameSearch"] = info
        print("after name search", info, flush=True)

    # Ensure Account Mode / transactions view is active
    am = find_text(m, "Account Mode")
    result["accountModeLabel"] = bool(am)
    # If we landed on account list, click Transactions
    if not am:
        tx = find_text(m, "Transactions", {"AfxWnd140"})
        if tx:
            click(tx)
            time.sleep(1.2)
            info = account_mode_patient(m)
            result["afterTransactionsClick"] = info
            print("after Transactions click", info, flush=True)

    # Print Transactions from Account Transaction view
    # SoftDent Account Mode options often via right-click or menu letter
    fg(m)
    # Focus account mode frame if present
    for h in walk(m):
        try:
            if win32gui.GetWindowText(h) == "SoftDent" and win32gui.GetClassName(h).startswith("AfxFrame"):
                # Prefer one that contains Account Mode
                if find_text(h, "Account Mode"):
                    click(h)
                    break
        except Exception:
            pass

    got = False
    for attempt, seq in enumerate(
        (
            "%p",  # Print menu?
            "%o",  # Options
            "{F10}p",
            "+{F10}",  # context menu
        )
    ):
        send_keys(seq, pause=0.05)
        time.sleep(0.5)
        if seq == "+{F10}":
            # arrow to Print Transactions
            for _ in range(8):
                send_keys("p", pause=0.05)
                time.sleep(0.2)
                if find_dialog("Output Options"):
                    break
                send_keys("{DOWN}", pause=0.05)
                time.sleep(0.15)
        else:
            send_keys("p", pause=0.05)
            time.sleep(0.4)
            # Print Transactions full phrase — type more letters
            if not find_dialog("Output Options"):
                send_keys("t", pause=0.05)  # Print Transactions
                time.sleep(0.5)
        if find_dialog("Output Options"):
            got = True
            result["printAttempt"] = seq
            break
        # Cancel any opened menu without Esc on SoftDent main: click main center
        if attempt < 3:
            send_keys("%c", pause=0.05)
            time.sleep(0.2)

    print("Output Options", find_dialog("Output Options"), "attempt", result.get("printAttempt"), flush=True)
    result["outputOptions"] = bool(find_dialog("Output Options"))

    if got:
        select_excel()
        time.sleep(1.0)
        for _ in range(6):
            h = find_dialog("Select File Name") or find_dialog("Save As")
            if h:
                fg(h)
                send_keys("^a", pause=0.03)
                send_keys(SAVE, pause=0.03)
                send_keys("{ENTER}", pause=0.05)
                time.sleep(1.5)
                break
            send_keys("{ENTER}", pause=0.05)
            time.sleep(0.5)
        saved = None
        for _ in range(25):
            for p in OUTBOX.glob("*"):
                if p.is_file() and (p.name not in before or p.stat().st_mtime > before.get(p.name, 0)):
                    saved = str(p)
                    break
            if saved:
                break
            for h, t, _ in tops():
                if "printer" in t.lower() or "waiting" in t.lower():
                    fg(h)
                    send_keys("%c", pause=0.05)
            time.sleep(0.4)
        result["saved"] = saved
        result["ok"] = bool(saved)
    else:
        # Capture on-screen Account Mode fields for Donna as visual proof if loaded
        result["ok"] = False
        result["error"] = "Could not open Output Options from Account Transaction view"
        result["hint"] = "Account Transaction tab is Account Mode; need Print Transactions → Excel"

    result["tops"] = tops()
    LOG.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print("RESULT", {k: result.get(k) for k in ("ok", "saved", "accountMode", "accountModeNameSearch", "error")}, flush=True)
    print("WROTE", LOG, flush=True)
    raise SystemExit(0 if result.get("ok") else 3)


if __name__ == "__main__":
    main()
