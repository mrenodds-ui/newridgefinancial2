"""Proceed: cancel SoftDent Print, Excel-only Trans for a Period (Feb 2026), scan Donna."""
from __future__ import annotations

import json
import time
from pathlib import Path

import win32con
import win32gui
from pywinauto import Application, mouse
from pywinauto.keyboard import send_keys

DEST = Path(r"C:\SoftDentReportExports")
LOG = Path(r"C:\SoftDentFinancialExports\softdent_account_tx_excel_validation.json")


def titles():
    out = []

    def cb(h, _):
        if win32gui.IsWindowVisible(h):
            t = win32gui.GetWindowText(h) or ""
            if t:
                out.append((int(h), t, win32gui.GetClassName(h)))
        return True

    win32gui.EnumWindows(cb, None)
    return out


def fg(h: int) -> None:
    try:
        win32gui.ShowWindow(h, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(h)
    except Exception:
        send_keys("%")
        time.sleep(0.05)
        try:
            win32gui.SetForegroundWindow(h)
        except Exception:
            pass
    time.sleep(0.2)


def cancel_print_dialogs() -> int:
    n = 0
    for _ in range(10):
        hit = False
        for h, t, _c in titles():
            low = t.lower()
            if low in {"print", "printing"} or "printer" in low or "waiting" in low:
                print(f"CANCEL {t!r}", flush=True)
                fg(h)
                send_keys("%c", pause=0.05)
                time.sleep(0.45)
                n += 1
                hit = True
        if not hit:
            break
    return n


def click_button(dlg, label: str) -> bool:
    want = label.lower()
    for b in dlg.descendants(class_name="Button"):
        lab = (b.window_text() or "").replace("&", "").strip()
        if lab.lower() == want:
            r = b.rectangle()
            mouse.click(coords=((r.left + r.right) // 2, (r.top + r.bottom) // 2))
            time.sleep(0.3)
            return True
    return False


def main() -> None:
    print("START proceed SoftDent Excel", flush=True)
    before = {p.name: p.stat().st_mtime for p in DEST.glob("*") if p.is_file()}
    cancel_print_dialogs()
    print("windows", [(t, c) for _h, t, c in titles() if "Soft" in t or c == "#32770"], flush=True)

    main_h = next(h for h, t, _c in titles() if "SoftDent Software" in t)
    fg(main_h)
    send_keys("{F10}", pause=0.05)
    time.sleep(0.4)
    send_keys("r", pause=0.05)
    time.sleep(0.35)
    send_keys("a", pause=0.05)
    time.sleep(0.4)
    send_keys("t", pause=0.05)
    time.sleep(1.2)

    oo = next((h for h, t, _c in titles() if t == "Output Options"), None)
    print("Output Options", oo, flush=True)
    if not oo:
        raise SystemExit("no Output Options")
    fg(oo)
    dlg = Application(backend="win32").connect(handle=oo).window(handle=oo)
    if not click_button(dlg, "Excel"):
        raise SystemExit("Excel button missing")
    print("Excel clicked", flush=True)
    time.sleep(0.25)
    click_button(dlg, "OK")
    print("OO OK", flush=True)
    time.sleep(1.2)
    cancel_print_dialogs()

    setup = next((h for h, t, _c in titles() if "Transactions For A Period" in t), None)
    print("setup", setup, flush=True)
    if not setup:
        raise SystemExit("no setup")
    fg(setup)
    w = Application(backend="win32").connect(handle=setup).window(handle=setup)
    edits = w.descendants(class_name="Edit")
    edits[1].set_edit_text("02/01/2026")
    edits[2].set_edit_text("02/28/2026")
    edits[3].set_edit_text("1")
    print("Feb 2026 format 1", flush=True)
    click_button(w, "OK")
    print("setup OK clicked", flush=True)

    produced = None
    for i in range(100):
        cancel_print_dialogs()
        ts = titles()
        setup_now = next((h for h, t, _c in ts if "Transactions For A Period" in t), None)
        save = next((h for h, t, _c in ts if t in {"Select File Name", "Save As"}), None)
        print(i, "setup", bool(setup_now), "save", save, flush=True)
        if save:
            fg(save)
            send_keys("^a", pause=0.03)
            send_keys(r"C:\SOFTDE~1\TXN260201", pause=0.03)
            sdlg = Application(backend="win32").connect(handle=save).window(handle=save)
            if not click_button(sdlg, "OK"):
                send_keys("{ENTER}", pause=0.05)
            print("save OK", flush=True)
            time.sleep(12)
            break
        if not setup_now and not save:
            time.sleep(6)
            break
        time.sleep(0.5)

    for p in sorted(DEST.glob("*"), key=lambda x: x.stat().st_mtime if x.is_file() else 0, reverse=True):
        if p.is_file() and (p.name not in before or p.stat().st_mtime > before.get(p.name, 0)):
            produced = p
            break

    result = json.loads(LOG.read_text(encoding="utf-8")) if LOG.is_file() else {}
    vl = result.setdefault("validatedLive", {})
    vl["proceed3"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    vl["saved"] = str(produced) if produced else None
    vl["printDialogSeen"] = True
    result["ok"] = bool(produced)
    if produced:
        raw = produced.read_bytes().decode("latin-1", errors="ignore")
        low = raw.lower()
        lines = [ln.strip() for ln in raw.splitlines() if "nickel" in ln.lower()]
        donna = [ln for ln in lines if "donna" in ln.lower()]
        result.update(
            {
                "bytes": produced.stat().st_size,
                "nickelMentions": low.count("nickel"),
                "hasDonnaNickel": bool(donna) or ("donna" in low and "nickel" in low),
                "sampleNickelLines": lines[:20],
                "donnaLines": donna[:10],
            }
        )
        for ln in (donna or lines)[:15]:
            print("HIT", ln[:180], flush=True)
    LOG.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("RESULT ok=", result["ok"], "saved=", produced, "donna=", result.get("hasDonnaNickel"), flush=True)


if __name__ == "__main__":
    main()
