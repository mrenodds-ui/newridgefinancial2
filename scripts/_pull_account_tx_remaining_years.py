"""Pull remaining SoftDent year TX chunks using proven Select-File-Name Edit path."""
from __future__ import annotations

import json
import shutil
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path

import win32con
import win32gui
from pywinauto import Application
from pywinauto.keyboard import send_keys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "NewRidgeFinancial2"))

from softdent_gui_export import (  # noqa: E402
    EXPORT_ROOT_SHORT,
    _main_softdent_hwnd,
    _open_accounting_report,
    cancel_printer_dialogs,
    dismiss_softdent_alerts,
    find_dialog,
)

DEST = Path(r"C:\SoftDentReportExports")
TEMP = Path(r"C:\Users\mreno\AppData\Local\Temp")
LOG = Path(r"C:\SoftDentFinancialExports\softdent_account_tx_year_chunks.json")


def titles() -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []

    def cb(h, _):
        if win32gui.IsWindowVisible(h):
            t = win32gui.GetWindowText(h) or ""
            if t:
                out.append((int(h), t))
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
    time.sleep(0.3)


def analyze(path: Path) -> dict:
    raw = path.read_bytes()
    years: Counter[int] = Counter()
    range_header = ""
    if raw[:4] == b"\xd0\xcf\x11\xe0":
        import xlrd

        wb = xlrd.open_workbook(file_contents=raw)
        sheet = wb.sheet_by_index(0)
        if sheet.nrows > 2:
            range_header = str(sheet.cell_value(2, 0) or "")
        for r in range(12, sheet.nrows):
            cell = sheet.cell_value(r, 0)
            if isinstance(cell, float) and cell > 20000:
                try:
                    y = xlrd.xldate_as_tuple(cell, wb.datemode)[0]
                    years[y] += 1
                except Exception:
                    pass
            else:
                part = str(cell).strip()
                bits = part.split("/")
                if len(bits) == 3 and bits[0].isdigit() and bits[2].isdigit():
                    yy = int(bits[2])
                    y = yy if yy > 99 else (2000 + yy if yy < 50 else 1900 + yy)
                    years[y] += 1
    else:
        text = raw.decode("latin-1", errors="ignore").splitlines()
        range_header = (text[2] if len(text) > 2 else "").split(",")[0]
        for ln in text[12:]:
            part = ln.split(",", 1)[0].strip().strip('"')
            bits = part.split("/")
            if len(bits) == 3 and bits[0].isdigit() and bits[2].isdigit():
                yy = int(bits[2])
                y = yy if yy > 99 else (2000 + yy if yy < 50 else 1900 + yy)
                years[y] += 1
    return {
        "rangeHeader": range_header,
        "rows": sum(years.values()),
        "years": dict(sorted(years.items())),
        "yearMin": min(years) if years else None,
        "yearMax": max(years) if years else None,
    }


def export_year(start: date, end: date, stem: str) -> dict:
    out = DEST / f"{stem}.xls"
    if out.is_file() and out.stat().st_size > 100_000:
        meta = analyze(out)
        if meta.get("years", {}).get(start.year, 0) > 10:
            print("SKIP", stem, meta.get("rows"), meta.get("rangeHeader"), flush=True)
            return {"ok": True, "skipped": True, "stem": stem, "saved": str(out), **meta}

    dismiss_softdent_alerts()
    cancel_printer_dialogs()
    fg(_main_softdent_hwnd())
    print("OPEN", start, end, stem, flush=True)
    _open_accounting_report("transactions", "t")
    oo = None
    for _ in range(40):
        oo = find_dialog("Output Options")
        if oo:
            break
        time.sleep(0.25)
    if not oo:
        return {"ok": False, "error": "no Output Options", "stem": stem}

    oh = int(oo.handle)
    fg(oh)
    dlg = Application(backend="win32").connect(handle=oh).window(handle=oh)
    for b in dlg.descendants(class_name="Button"):
        if (b.window_text() or "").replace("&", "").strip().lower() == "excel":
            b.click()
            time.sleep(0.4)
            break
    for b in dlg.descendants(class_name="Button"):
        if (b.window_text() or "").replace("&", "").strip().lower() == "ok":
            b.click()
            break
    else:
        send_keys("{ENTER}", pause=0.05)
    time.sleep(1.2)

    setup = None
    for _ in range(50):
        setup = find_dialog("Transactions For A Period")
        if setup:
            break
        time.sleep(0.25)
    if not setup:
        return {"ok": False, "error": "no setup", "stem": stem}

    sh = int(setup.handle)
    fg(sh)
    w = Application(backend="win32").connect(handle=sh).window(handle=sh)
    edits = w.descendants(class_name="Edit")
    edits[1].set_edit_text(start.strftime("%m/%d/%Y"))
    edits[2].set_edit_text(end.strftime("%m/%d/%Y"))
    edits[3].set_edit_text("1")
    print("fields", edits[1].window_text(), edits[2].window_text(), flush=True)
    for b in w.descendants(class_name="Button"):
        if (b.window_text() or "").replace("&", "").strip().lower() == "ok":
            b.click()
            break
    print("setup OK", flush=True)

    t0 = time.time()
    known_before = {p.resolve() for p in TEMP.glob("SDWIN*") if p.is_file()}
    save_done = False
    tracked: Path | None = None
    last = -1
    stable = 0

    for i in range(240):
        save_h = next((h for h, t in titles() if t in {"Select File Name", "Save As"}), None)
        if save_h and not save_done:
            fg(save_h)
            sdlg = Application(backend="win32").connect(handle=save_h).window(handle=save_h)
            short = rf"{EXPORT_ROOT_SHORT}\{stem}"
            sedits = sdlg.descendants(class_name="Edit")
            if sedits:
                sedits[0].set_edit_text(short)
            for b in sdlg.descendants(class_name="Button"):
                if (b.window_text() or "").replace("&", "").strip().lower() == "ok":
                    b.click()
                    break
            else:
                send_keys("{ENTER}", pause=0.05)
            print("save", short, flush=True)
            save_done = True
            time.sleep(1.5)
            for h, t in titles():
                if t.strip() == "SoftDent" or "replace" in t.lower() or "already" in t.lower():
                    fg(h)
                    send_keys("{ENTER}", pause=0.05)

        printing = any(t == "Print File" for _, t in titles())
        # Track NEW SDWIN*.csv created after start
        try:
            for p in TEMP.glob("SDWIN*"):
                try:
                    if not p.is_file() or p.stat().st_size < 100_000:
                        continue
                    if p.resolve() in known_before and p.stat().st_mtime < t0:
                        continue
                    if p.stat().st_mtime >= t0 - 1:
                        if tracked is None or p.stat().st_size >= tracked.stat().st_size:
                            tracked = p
                except OSError:
                    continue
        except OSError:
            pass
        # Also accept DEST stem if SoftDent wrote it
        for p in DEST.glob(f"{stem}.*"):
            try:
                if p.is_file() and p.stat().st_mtime >= t0 and p.stat().st_size > 100_000:
                    tracked = p
            except OSError:
                continue

        size = tracked.stat().st_size if tracked and tracked.is_file() else 0
        if i % 8 == 0:
            print(
                i,
                "print",
                printing,
                "file",
                tracked.name if tracked else None,
                "MB",
                round(size / 1e6, 2),
                "stable",
                stable,
                flush=True,
            )

        if size == last and size > 200_000 and not printing:
            stable += 1
        else:
            stable = 0
        last = size

        if tracked and not printing and stable >= 3 and i > 6:
            # Verify year before accepting
            try:
                meta = analyze(tracked)
            except Exception as exc:
                print("analyze fail", type(exc).__name__, flush=True)
                stable = 0
                continue
            if meta.get("years", {}).get(start.year, 0) > 10:
                break
            print("reject", tracked.name, meta.get("rangeHeader"), meta.get("years"), flush=True)
            known_before.add(tracked.resolve())
            tracked = None
            stable = 0
        time.sleep(2)

    if not tracked or not tracked.is_file():
        return {"ok": False, "error": "no output", "stem": stem}

    # SoftDent often writes DEST\STEMxls already — avoid SameFileError on Windows
    try:
        same = tracked.resolve() == out.resolve()
    except OSError:
        same = str(tracked).lower() == str(out).lower()
    if not same:
        shutil.copy2(tracked, out)
    csv_out = DEST / f"{stem}.csv"
    try:
        if tracked.resolve() != csv_out.resolve():
            shutil.copy2(tracked if tracked.suffix.lower() == ".csv" else out, csv_out)
    except Exception:
        pass
    canon = DEST / f"transactions_for_period_{start.isoformat()}_{end.isoformat()}.xls"
    try:
        if out.resolve() != canon.resolve():
            shutil.copy2(out, canon)
    except Exception:
        pass
    meta = analyze(out)
    ok = meta.get("years", {}).get(start.year, 0) > 10
    result = {
        "ok": ok,
        "stem": stem,
        "saved": str(out),
        "bytes": out.stat().st_size,
        "source": str(tracked),
        **meta,
    }
    print("CHUNK", json.dumps({k: result.get(k) for k in ("ok", "stem", "rows", "rangeHeader", "years", "bytes")}, indent=2), flush=True)
    return result


def main() -> None:
    today = date.today()
    chunks = [
        (date(2024, 1, 1), date(2024, 12, 31), "TXN2024"),
        (date(2025, 1, 1), date(2025, 12, 31), "TXN2025"),
        (date(today.year, 1, 1), today, f"TXN{today.year}YTD"),
    ]
    results = []
    for stem, year in (
        ("TXN2017H2", 2017),
        ("TXN2018", 2018),
        ("TXN2019", 2019),
        ("TXN2020", 2020),
        ("TXN2021", 2021),
        ("TXN2022", 2022),
        ("TXN2023", 2023),
    ):
        p = next((DEST / n for n in (f"{stem}.xls", f"{stem}.XLS") if (DEST / n).is_file()), None)
        if p is not None:
            meta = analyze(p)
            results.append(
                {
                    "ok": meta.get("years", {}).get(year, 0) > 10,
                    "skipped": True,
                    "stem": stem,
                    "saved": str(p),
                    **meta,
                }
            )

    for start, end, stem in chunks:
        try:
            results.append(export_year(start, end, stem))
        except Exception as exc:
            print("FAIL", stem, type(exc).__name__, exc, flush=True)
            results.append({"ok": False, "stem": stem, "error": f"{type(exc).__name__}: {exc}"})
            for h, t in titles():
                if t in {"Select File Name", "Output Options", "Print File"} or "transactions" in t.lower():
                    fg(h)
                    send_keys("%c", pause=0.05)
                    time.sleep(0.4)
        print("pause…", flush=True)
        time.sleep(4)

    summary = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ok": all(r.get("ok") for r in results),
        "okCount": sum(1 for r in results if r.get("ok")),
        "failCount": sum(1 for r in results if not r.get("ok")),
        "chunks": results,
    }
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("SUMMARY", json.dumps({"ok": summary["ok"], "okCount": summary["okCount"], "failCount": summary["failCount"]}, indent=2), flush=True)
    raise SystemExit(0 if summary["ok"] else 4)


if __name__ == "__main__":
    main()
