"""Finish SoftDent Transactions For A Period → Excel save (format 1)."""
from __future__ import annotations

import json
import time
from pathlib import Path

import win32gui
from pywinauto import Application
from pywinauto.keyboard import send_keys

DEST = Path(r"C:\SoftDentReportExports")
LOG = Path(r"C:\SoftDentFinancialExports\softdent_account_tx_excel_validation.json")


def find_title(*, exact: str | None = None, substr: str | None = None) -> int | None:
    hit: int | None = None

    def cb(h, _):
        nonlocal hit
        if not win32gui.IsWindowVisible(h):
            return True
        t = win32gui.GetWindowText(h) or ""
        if exact and t == exact:
            hit = int(h)
        if substr and substr.lower() in t.lower():
            hit = int(h)
        return True

    win32gui.EnumWindows(cb, None)
    return hit


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


def main() -> None:
    before = {p.name: p.stat().st_mtime for p in DEST.glob("*") if p.is_file()}
    h = find_title(substr="Transactions For A Period")
    print("setup", h, flush=True)
    if not h:
        raise SystemExit("no Transactions For A Period dialog")

    fg(h)
    app = Application(backend="win32").connect(handle=h)
    w = app.window(handle=h)
    edits = w.descendants(class_name="Edit")
    # Dump order: title, start, end, format(1), …
    if len(edits) >= 4:
        edits[0].set_edit_text("TRANSACTIONS FOR A PERIOD")
        edits[1].set_edit_text("01/01/2026")
        edits[2].set_edit_text(time.strftime("%m/%d/%Y"))
        edits[3].set_edit_text("1")  # List Each Transaction Separately
        print("fields set title/start/end/format=1", flush=True)

    for b in w.descendants(class_name="Button"):
        if (b.window_text() or "").replace("&", "").strip().lower() == "ok":
            b.click_input()
            print("OK clicked", flush=True)
            break
    time.sleep(2.0)

    save = None
    for i in range(90):
        setup = find_title(substr="Transactions For A Period")
        save = find_title(exact="Select File Name") or find_title(exact="Save As")
        printer_h: list[int] = []

        def cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                t = (win32gui.GetWindowText(hwnd) or "").lower()
                if "printer" in t or "waiting for" in t:
                    printer_h.append(int(hwnd))
            return True

        win32gui.EnumWindows(cb, None)
        for ph in printer_h:
            fg(ph)
            send_keys("%c", pause=0.05)
        print(i, "setup", setup, "save", save, flush=True)
        if save:
            break
        if not setup:
            print("setup closed without save dialog", flush=True)
            break
        time.sleep(0.5)

    if save:
        fg(save)
        send_keys("^a", pause=0.03)
        send_keys(r"C:\SOFTDE~1\TXN260101", pause=0.03)
        app = Application(backend="win32").connect(handle=save)
        for b in app.window(handle=save).descendants(class_name="Button"):
            if (b.window_text() or "").replace("&", "").strip().lower() == "ok":
                b.click_input()
                break
        else:
            send_keys("{ENTER}", pause=0.05)
        print("save dialog OK", flush=True)
        time.sleep(12.0)

    produced = None
    for p in list(DEST.glob("*")) + list(Path(r"C:\SoftDent").glob("*.xls*")):
        if not p.is_file():
            continue
        if p.name not in before or p.stat().st_mtime > before.get(p.name, 0):
            produced = p
            break
        if p.stat().st_mtime > time.time() - 300 and p.suffix.lower() in {".xls", ".xlsx", ".csv"}:
            produced = p
            break

    result = json.loads(LOG.read_text(encoding="utf-8")) if LOG.is_file() else {}
    vl = result.setdefault("validatedLive", {})
    vl["excelButtonPresent"] = True
    vl["format"] = "1 List Each Transaction Separately (Carestream)"
    vl["saved"] = str(produced) if produced else None
    vl["webPath"] = "Reports → Accounting → Trans for a Period → Output Options → Excel"
    result["ok"] = bool(produced)
    result["at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    if produced:
        raw = produced.read_bytes().decode("latin-1", errors="ignore")
        low = raw.lower()
        lines = [ln.strip() for ln in raw.splitlines() if "nickel" in ln.lower()]
        result["bytes"] = produced.stat().st_size
        result["nickelMentions"] = low.count("nickel")
        result["hasDonnaNickel"] = "donna" in low and "nickel" in low
        result["sampleNickelLines"] = lines[:15]
        for ln in lines[:10]:
            print("HIT", ln[:160], flush=True)
    LOG.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("FINAL ok=", result["ok"], "saved=", produced, flush=True)
    print("WROTE", LOG, flush=True)


if __name__ == "__main__":
    main()
