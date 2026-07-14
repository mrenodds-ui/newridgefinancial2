"""SoftDent Trans for a Period → Excel, year-sized chunks (Format 1).

Fills the post-2017-06-28 gap SoftDent truncates on full-history pulls.
Desktop SoftDent only. Never Printer. Never Esc on SoftDent main.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
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
    _escape_pywinauto_keys,
    _excel_sdwin_workbook_open,
    _main_softdent_hwnd,
    _open_accounting_report,
    _save_excel_sdwin_copy,
    cancel_printer_dialogs,
    dismiss_softdent_alerts,
    find_dialog,
)
from softdent_signon import ensure_softdent_signed_on  # noqa: E402

DEST = Path(r"C:\SoftDentReportExports")
TEMP = Path(r"C:\Users\mreno\AppData\Local\Temp")
LOG = Path(r"C:\SoftDentFinancialExports\softdent_account_tx_year_chunks.json")


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
    time.sleep(0.25)


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


def dismiss_simple() -> None:
    for h, t in titles():
        if t.strip() != "SoftDent":
            continue
        try:
            app = Application(backend="win32").connect(handle=h)
            for b in app.window(handle=h).descendants(class_name="Button"):
                if (b.window_text() or "").replace("&", "").strip().lower() in {"ok", "cancel"}:
                    b.click()
                    time.sleep(0.35)
                    break
        except Exception:
            fg(h)
            send_keys("{ENTER}", pause=0.05)
            time.sleep(0.35)


def keyboard_sign_on() -> dict:
    user = os.environ.get("SOFTDENT_SIGNON_USER") or os.environ.get("SOFTDENT_GUI_USER") or "COMPUTE"
    password = (
        os.environ.get("SOFTDENT_SIGNON_PASSWORD")
        or os.environ.get("SOFTDENT_GUI_PASSWORD")
        or "computer"
    )
    # Prefer hard-rule COMPUTE/computer when env user is COMPUTE
    if str(user).upper() == "COMPUTE":
        password = password or "computer"
    login = next((h for h, t in titles() if "login" in t.lower() or "sign on" in t.lower()), None)
    if login is None:
        if any("SoftDent Software" in t for _, t in titles()):
            return {"ok": True, "already": True}
        return {"ok": False, "error": "no login dialog"}
    fg(login)
    send_keys("^a{BACKSPACE}", pause=0.03)
    send_keys(user, pause=0.04)
    send_keys("{TAB}", pause=0.05)
    send_keys("^a{BACKSPACE}", pause=0.03)
    send_keys(password, pause=0.04)
    send_keys("{ENTER}", pause=0.05)
    for i in range(50):
        time.sleep(0.4)
        dismiss_simple()
        if any("SoftDent Software" in t for _, t in titles()) and not any(
            "login" in t.lower() for _, t in titles()
        ):
            return {"ok": True, "signedOn": True, "wait": round((i + 1) * 0.4, 1)}
    return {"ok": False, "error": "still on login"}


def ensure_signed() -> None:
    assist = ensure_softdent_signed_on(timeout_s=20.0)
    if assist.get("ok") or assist.get("signedOn"):
        print("SIGNON ensure ok", flush=True)
        return
    print("SIGNON ensure failed — keyboard fallback", assist.get("error"), flush=True)
    kb = keyboard_sign_on()
    print("SIGNON kb", {k: kb.get(k) for k in ("ok", "signedOn", "already", "error")}, flush=True)
    if not kb.get("ok"):
        raise SystemExit(f"signon failed: {kb}")
    dismiss_simple()


def click_excel_ok(oo_hwnd: int) -> bool:
    fg(oo_hwnd)
    dlg = Application(backend="win32").connect(handle=oo_hwnd).window(handle=oo_hwnd)
    excel_ok = False
    for b in dlg.descendants(class_name="Button"):
        if (b.window_text() or "").replace("&", "").strip().lower() == "excel":
            try:
                b.click()
            except Exception:
                try:
                    b.click_input()
                except Exception:
                    send_keys("e", pause=0.05)
            excel_ok = True
            time.sleep(0.35)
            break
    if not excel_ok:
        return False
    for b in dlg.descendants(class_name="Button"):
        if (b.window_text() or "").replace("&", "").strip().lower() == "ok":
            try:
                b.click()
            except Exception:
                try:
                    b.click_input()
                except Exception:
                    send_keys("{ENTER}", pause=0.05)
            return True
    send_keys("{ENTER}", pause=0.05)
    return True


def safe_cancel_printer() -> None:
    try:
        cancel_printer_dialogs(max_rounds=1)
    except Exception as exc:
        print("cancel_printer skip", type(exc).__name__, flush=True)


def close_locking_excel(stems: list[str]) -> None:
    try:
        import win32com.client

        excel = win32com.client.GetObject(Class="Excel.Application")
    except Exception:
        return
    want = tuple(s.upper() for s in stems)
    for i in range(int(excel.Workbooks.Count), 0, -1):
        wb = excel.Workbooks(i)
        name = str(wb.Name or "").upper()
        full = str(wb.FullName or "").upper()
        if any(s in name or s in full for s in want) or "SDWIN" in name or "SDWIN" in full:
            try:
                wb.Close(SaveChanges=False)
                print("closed excel", name, flush=True)
            except Exception as exc:
                print("excel close", type(exc).__name__, flush=True)
    time.sleep(0.5)


def clear_stale_dialogs() -> None:
    for _ in range(8):
        dismiss_simple()
        safe_cancel_printer()
        hit = False
        for h, t in titles():
            low = t.lower()
            if t in {"Select File Name", "Save As", "Output Options", "Print File"} or (
                "transactions for a period" in low
            ):
                print("cancel stale", t, flush=True)
                fg(h)
                send_keys("%c", pause=0.05)
                time.sleep(0.45)
                hit = True
                break
        if not hit:
            break


def year_span(path: Path) -> dict:
    raw = path.read_bytes()
    magic = raw[:8]
    years: dict[int, int] = {}
    first = last = None
    range_header = ""
    total_lines = 0

    def add_token(part: str) -> None:
        nonlocal first, last
        part = str(part).strip().strip('"')
        if len(part) >= 8 and part[2] == "/" and part[5] == "/":
            yy = int(part[-2:])
            y = 2000 + yy if yy < 50 else 1900 + yy
            years[y] = years.get(y, 0) + 1
            if first is None:
                first = part
            last = part

    if magic[:4] == b"\xd0\xcf\x11\xe0":
        import xlrd

        wb = xlrd.open_workbook(file_contents=raw)
        sheet = wb.sheet_by_index(0)
        total_lines = sheet.nrows
        if sheet.nrows > 2:
            range_header = str(sheet.cell_value(2, 0) or "")
        header_i = next(
            (
                r
                for r in range(min(30, sheet.nrows))
                if str(sheet.cell_value(r, 0)).strip().lower() == "date"
            ),
            11,
        )
        for r in range(header_i + 1, sheet.nrows):
            cell = sheet.cell_value(r, 0)
            if isinstance(cell, float) and cell > 20000:
                try:
                    y, m, d, *_ = xlrd.xldate_as_tuple(cell, wb.datemode)
                    years[y] = years.get(y, 0) + 1
                    token = f"{m:02d}/{d:02d}/{y % 100:02d}"
                    if first is None:
                        first = token
                    last = token
                except Exception:
                    pass
            else:
                add_token(str(cell))
    else:
        text = raw.decode("latin-1", errors="ignore").splitlines()
        total_lines = len(text)
        range_header = text[2] if len(text) > 2 else ""
        header_i = next(
            (i for i, ln in enumerate(text[:40]) if ln.split(",")[0].strip().upper() == "DATE"),
            11,
        )
        for ln in text[header_i + 1 :]:
            add_token(ln.split(",", 1)[0])

    return {
        "rangeHeader": range_header,
        "first": first,
        "last": last,
        "rows": sum(years.values()),
        "years": dict(sorted(years.items())),
        "yearMin": min(years) if years else None,
        "yearMax": max(years) if years else None,
        "totalLines": total_lines,
        "isXls": magic[:4] == b"\xd0\xcf\x11\xe0",
    }


def range_matches(meta: dict, start: date, end: date) -> bool:
    y0, y1 = meta.get("yearMin"), meta.get("yearMax")
    if y0 is not None and y1 is not None:
        return not (y1 < start.year or y0 > end.year)
    hdr = str(meta.get("rangeHeader") or "").replace("-", "/")
    return f"{start.year % 100:02d}" in hdr or str(start.year)[-2:] in hdr


def export_range(start: date, end: date, stem: str) -> dict:
    dismiss_softdent_alerts()
    clear_stale_dialogs()
    close_locking_excel([stem, "TXN", "SDWIN", "TRANSACTION"])
    for p in DEST.glob(f"{stem}.*"):
        try:
            p.unlink()
            print("removed stale", p.name, flush=True)
        except OSError as exc:
            print("unlink", p.name, type(exc).__name__, flush=True)

    main_h = _main_softdent_hwnd()
    if not main_h:
        return {"ok": False, "error": "no SoftDent main"}
    fg(main_h)

    print("OPEN", start, end, stem, flush=True)
    _open_accounting_report("transactions", "t")
    oo = None
    for _ in range(50):
        oo = find_dialog("Output Options")
        if oo:
            break
        time.sleep(0.2)
    if not oo:
        return {"ok": False, "error": "no Output Options"}
    if not click_excel_ok(int(oo.handle)):
        return {"ok": False, "error": "Excel missing"}
    time.sleep(1.0)

    setup = None
    for _ in range(60):
        setup = find_dialog("Transactions For A Period")
        if setup:
            break
        time.sleep(0.25)
    if not setup:
        return {"ok": False, "error": "no setup"}

    sh = int(setup.handle)
    fg(sh)
    w = Application(backend="win32").connect(handle=sh).window(handle=sh)
    edits = w.descendants(class_name="Edit")
    start_txt = start.strftime("%m/%d/%Y")
    end_txt = end.strftime("%m/%d/%Y")
    edits[1].set_edit_text(start_txt)
    edits[2].set_edit_text(end_txt)
    edits[3].set_edit_text("1")
    time.sleep(0.2)
    seen_start = (edits[1].window_text() or "").strip()
    seen_end = (edits[2].window_text() or "").strip()
    print(
        "fields want",
        start_txt,
        end_txt,
        "got",
        seen_start,
        seen_end,
        "fmt",
        (edits[3].window_text() or "").strip(),
        "doctors",
        (edits[4].window_text() if len(edits) > 4 else ""),
        flush=True,
    )
    for b in w.descendants(class_name="Button"):
        if (b.window_text() or "").replace("&", "").strip().lower() == "ok":
            try:
                b.click()
            except Exception:
                try:
                    b.click_input()
                except Exception:
                    send_keys("%o", pause=0.05)
            break
    print("setup OK — waiting generation", flush=True)

    before_temp: dict[str, int] = {}
    for p in TEMP.glob("SDWIN*"):
        try:
            if p.is_file():
                before_temp[p.name] = p.stat().st_size
        except OSError:
            pass
    t0 = time.time()
    saw_print = False
    best: Path | None = None
    last = -1
    stable = 0
    save_done = False

    for i in range(400):
        dismiss_simple()
        safe_cancel_printer()
        wins = titles()
        if any("login" in t.lower() for _, t in wins):
            kb = keyboard_sign_on()
            if not kb.get("ok"):
                return {"ok": False, "error": "signed out mid-export", "stem": stem}
        printing = any(t == "Print File" for _, t in wins)
        if printing:
            saw_print = True

        save_h = next((h for h, t in wins if t in {"Select File Name", "Save As"}), None)
        if save_h and not save_done:
            fg(save_h)
            short = rf"{EXPORT_ROOT_SHORT}\{stem}"
            send_keys("^a", pause=0.03)
            send_keys(_escape_pywinauto_keys(short), pause=0.03)
            time.sleep(0.15)
            send_keys("{ENTER}", pause=0.05)
            print("save", short, flush=True)
            save_done = True
            time.sleep(1.0)
            for h, t in titles():
                if t.strip() == "SoftDent" or "replace" in t.lower() or "already" in t.lower():
                    fg(h)
                    send_keys("{ENTER}", pause=0.05)

        cands: list[Path] = []
        try:
            for p in TEMP.glob("SDWIN*"):
                try:
                    if not p.is_file() or p.stat().st_size < 50_000:
                        continue
                    grown = (
                        p.name not in before_temp
                        or p.stat().st_size > before_temp.get(p.name, 0) + 5_000
                    )
                    recent = p.stat().st_mtime >= t0 - 2
                    if grown or recent:
                        cands.append(p)
                except OSError:
                    continue
        except OSError:
            pass
        for p in DEST.glob(f"{stem}.*"):
            try:
                if p.is_file() and p.stat().st_mtime >= t0 - 2 and p.stat().st_size > 50_000:
                    cands.append(p)
            except OSError:
                continue

        if cands:
            try:
                best = max(cands, key=lambda p: (p.stat().st_mtime, p.stat().st_size))
            except OSError:
                best = None
        size = 0
        if best is not None:
            try:
                size = best.stat().st_size
            except OSError:
                best = None

        if i % 10 == 0:
            print(
                i,
                "MB",
                round(size / 1e6, 2),
                "print",
                printing,
                "sawPrint",
                saw_print,
                "file",
                best.name if best else None,
                "stable",
                stable,
                flush=True,
            )

        if size == last and size > 100_000 and not printing:
            stable += 1
        else:
            stable = 0
        last = size

        if _excel_sdwin_workbook_open() and not printing and (saw_print or i > 20):
            copied = _save_excel_sdwin_copy(DEST / f"{stem}.xls")
            if copied and copied.is_file() and copied.stat().st_size > 100_000:
                try:
                    meta0 = year_span(copied)
                    if range_matches(meta0, start, end) and meta0["rows"] > 10:
                        best = copied
                        break
                    print(
                        "SaveCopyAs mismatch",
                        meta0.get("rangeHeader"),
                        meta0.get("yearMin"),
                        meta0.get("yearMax"),
                        flush=True,
                    )
                except Exception as exc:
                    print("SaveCopyAs parse", type(exc).__name__, flush=True)

        if not printing and stable >= 5 and best is not None and (saw_print or i > 25):
            try:
                meta0 = year_span(best)
                if range_matches(meta0, start, end) and meta0["rows"] > 10:
                    break
                print(
                    "reject",
                    best.name,
                    meta0.get("rangeHeader"),
                    meta0.get("rows"),
                    meta0.get("yearMin"),
                    meta0.get("yearMax"),
                    flush=True,
                )
                # Don't keep rejecting forever on wrong file — delete stem and keep waiting
                if best.parent == DEST and best.name.startswith(stem):
                    try:
                        best.unlink()
                    except OSError:
                        pass
                best = None
                stable = 0
            except Exception as exc:
                print("parse", type(exc).__name__, flush=True)
                stable = 0
        time.sleep(2)

    if best is None or not best.is_file():
        return {
            "ok": False,
            "error": "no output",
            "stem": stem,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "sawPrint": saw_print,
        }

    out_csv = DEST / f"{stem}.csv"
    out_xls = DEST / f"{stem}.xls"
    try:
        if best.resolve() != out_csv.resolve():
            shutil.copy2(best, out_csv)
    except OSError:
        out_csv.write_bytes(best.read_bytes())
    shutil.copy2(out_csv, out_xls)
    canonical = DEST / f"transactions_for_period_{start.isoformat()}_{end.isoformat()}.xls"
    shutil.copy2(out_csv, canonical)

    meta = year_span(out_csv)
    matched = range_matches(meta, start, end)
    result = {
        "ok": bool(meta["rows"] > 10 and matched),
        "rangeMatched": matched,
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "stem": stem,
        "range": f"{start.isoformat()}_{end.isoformat()}",
        "saved": str(out_csv),
        "canonical": str(canonical),
        "source": str(best),
        "bytes": out_csv.stat().st_size,
        "sawPrint": saw_print,
        **meta,
    }
    print(
        "CHUNK",
        json.dumps(
            {
                k: result.get(k)
                for k in (
                    "ok",
                    "stem",
                    "rows",
                    "yearMin",
                    "yearMax",
                    "rangeHeader",
                    "rangeMatched",
                    "bytes",
                    "sawPrint",
                )
            },
            indent=2,
        ),
        flush=True,
    )
    return result


def year_ranges() -> list[tuple[date, date, str]]:
    today = date.today()
    out: list[tuple[date, date, str]] = [
        (date(2017, 6, 29), date(2017, 12, 31), "TXN2017H2"),
    ]
    for y in range(2018, today.year):
        out.append((date(y, 1, 1), date(y, 12, 31), f"TXN{y}"))
    out.append((date(today.year, 1, 1), today, f"TXN{today.year}YTD"))
    return out


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    print("signon", flush=True)
    ensure_signed()
    clear_stale_dialogs()
    results: list[dict] = []
    for start, end, stem in year_ranges():
        existing = DEST / f"{stem}.csv"
        if existing.is_file() and existing.stat().st_size > 100_000:
            try:
                meta = year_span(existing)
                if range_matches(meta, start, end) and meta.get("rows", 0) > 10:
                    print("SKIP existing", stem, meta.get("rows"), meta.get("rangeHeader"), flush=True)
                    results.append(
                        {"ok": True, "skipped": True, "stem": stem, **meta, "saved": str(existing)}
                    )
                    continue
            except Exception:
                pass
        try:
            results.append(export_range(start, end, stem))
        except Exception as exc:
            print("FAIL", stem, type(exc).__name__, exc, flush=True)
            results.append({"ok": False, "stem": stem, "error": f"{type(exc).__name__}: {exc}"})
            clear_stale_dialogs()
        time.sleep(1.5)

    summary = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ok": all(r.get("ok") for r in results),
        "chunks": results,
        "okCount": sum(1 for r in results if r.get("ok")),
        "failCount": sum(1 for r in results if not r.get("ok")),
    }
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(
        "SUMMARY",
        json.dumps(
            {"ok": summary["ok"], "okCount": summary["okCount"], "failCount": summary["failCount"]},
            indent=2,
        ),
        flush=True,
    )
    print("WROTE", LOG, flush=True)
    raise SystemExit(0 if summary["ok"] else 4)


if __name__ == "__main__":
    main()
