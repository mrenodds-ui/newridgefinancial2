"""Re-check SoftDent gold-candidate reports with explicit 1-year date range.

Never Printer. Never Esc on SoftDent main. Never invent gold.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import date
from pathlib import Path

NR2 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(NR2))

from softdent_gui_export import (  # noqa: E402
    _focus_main,
    _keyboard_activate_dialog,
    _keyboard_press_ok,
    _open_report_via_win32_menu,
    _select_output_option_prompt,
    _send_softdent_keys,
    _softdent_pids,
    _type_keys_clear_and_text,
    _window_pid,
    cancel_printer_dialogs,
    dismiss_softdent_alerts,
    find_dialog,
    list_softdent_window_titles,
    navigate_softdent_print_preview_pages,
    softdent_report_preview_visible,
)


def titles() -> list[str]:
    return list_softdent_window_titles()


def close_mdi() -> None:
    if softdent_report_preview_visible():
        _focus_main()
        _send_softdent_keys("^({F4})")
        time.sleep(0.7)


def cancel_output_options() -> None:
    oo = find_dialog("Output Options")
    if not oo:
        return
    try:
        _keyboard_activate_dialog(oo)
        for c in oo.descendants():
            try:
                t = (c.window_text() or "").strip().lower()
                if t in {"cancel", "&cancel"}:
                    c.click_input()
                    time.sleep(0.4)
                    return
            except Exception:
                continue
        _send_softdent_keys("%c")
        time.sleep(0.4)
    except Exception:
        pass


def output_options_labels() -> dict:
    dlg = find_dialog("Output Options")
    if not dlg:
        return {"dialog": False}
    labels = []
    excel = None
    for c in dlg.descendants():
        try:
            txt = (c.window_text() or "").strip()
            if not txt:
                continue
            low = txt.lower()
            if any(k in low for k in ("excel", "preview", "printer")):
                en = None
                try:
                    en = bool(c.is_enabled())
                except Exception:
                    pass
                labels.append({"text": txt, "enabled": en})
                if "excel" in low:
                    excel = en if en is not None else True
        except Exception:
            continue
    return {"dialog": True, "excelEnabled": excel, "labels": labels}


def find_setup():
    from pywinauto import Desktop

    pids = _softdent_pids()
    for w in Desktop(backend="win32").windows():
        try:
            t = (w.window_text() or "").strip()
            if pids and _window_pid(int(w.handle)) not in pids:
                continue
            if "setup" in t.lower() and "softdent software" not in t.lower():
                return w
        except Exception:
            continue
    return None


def fill_setup_dates(start: date, end: date) -> dict:
    setup = None
    for _ in range(50):
        cancel_printer_dialogs(max_rounds=2)
        setup = find_setup()
        if setup or softdent_report_preview_visible() or find_dialog("Print Preview"):
            break
        time.sleep(0.2)
    if not setup:
        return {"ok": False, "error": "setup_missing", "titles": titles()[:10]}
    _keyboard_activate_dialog(setup)
    h = int(setup.handle)
    start_txt = start.strftime("%m/%d/%y")
    end_txt = end.strftime("%m/%d/%y")
    _send_softdent_keys("{TAB}", hwnd=h)
    time.sleep(0.15)
    _type_keys_clear_and_text(start_txt, hwnd=h)
    _send_softdent_keys("{TAB}", hwnd=h)
    time.sleep(0.15)
    _type_keys_clear_and_text(end_txt, hwnd=h)
    _send_softdent_keys("{TAB}", hwnd=h)
    time.sleep(0.15)
    _type_keys_clear_and_text("999", hwnd=h)
    time.sleep(0.2)
    _keyboard_press_ok(hwnd=h)
    time.sleep(1.5)
    cancel_printer_dialogs()
    for _ in range(90):
        ts = titles()
        if any("sorting" in t.lower() for t in ts):
            time.sleep(0.5)
            continue
        break
    return {
        "ok": True,
        "startTyped": start_txt,
        "endTyped": end_txt,
        "titles": titles()[:12],
        "preview": softdent_report_preview_visible(),
    }


def probe_report(report_id: str, path: str, start: date, end: date, *, do_preview: bool) -> dict:
    entry: dict = {"id": report_id, "path": path, "dateRangeRequested": f"{start}..{end}"}
    dismiss_softdent_alerts()
    cancel_printer_dialogs()
    cancel_output_options()
    close_mdi()
    _focus_main()
    time.sleep(0.3)
    try:
        opened = bool(_open_report_via_win32_menu(path))
    except Exception as e:  # noqa: BLE001
        entry["openError"] = f"{type(e).__name__}:{e}"
        opened = False
    time.sleep(0.7)
    oo = output_options_labels()
    entry["opened"] = opened or bool(oo.get("dialog"))
    entry["outputOptions"] = oo
    excel = oo.get("excelEnabled")
    if not oo.get("dialog"):
        entry["error"] = "no_output_options"
        entry["titles"] = titles()[:10]
        return entry

    if excel:
        entry["attempt"] = "excel"
        try:
            _select_output_option_prompt("excel")
            time.sleep(0.8)
            setup = fill_setup_dates(start, end)
            entry["setup"] = setup
            entry["excelLikelyAvailable"] = True
        except Exception as e:  # noqa: BLE001
            entry["excelError"] = f"{type(e).__name__}:{e}"
            entry["excelLikelyAvailable"] = False
            cancel_output_options()
    else:
        entry["excelLikelyAvailable"] = False
        entry["attempt"] = "print_preview" if do_preview else "excel_unavailable_cancel"
        if do_preview:
            try:
                _select_output_option_prompt("print_preview")
                time.sleep(0.5)
                setup = fill_setup_dates(start, end)
                entry["setup"] = setup
                if setup.get("preview"):
                    nav = navigate_softdent_print_preview_pages(max_next_pages=80)
                    entry["pageNavigation"] = nav
                    entry["finalTitles"] = titles()[:12]
            except Exception as e:  # noqa: BLE001
                entry["previewError"] = f"{type(e).__name__}:{e}"
                cancel_output_options()
        else:
            cancel_output_options()
    return entry


def main() -> int:
    end = date.today()  # 2026-07-13 expected
    start = date(end.year - 1, end.month, end.day)  # ONE year, not two
    out = {
        "ok": True,
        "datePolicy": "1_year_not_2",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "honesty": "does not invent gold; Print Preview != payment lines",
        "probes": [],
    }

    # Full preview only for Insurance Income (primary gold candidate)
    out["probes"].append(
        probe_report(
            "insurance_income",
            "Reports->Practice Management->Insurance Reports->Insurance Income",
            start,
            end,
            do_preview=True,
        )
    )
    # Excel availability only for alts (avoid long multi-preview)
    for rid, path in (
        (
            "payment_allocation",
            "Reports->Practice Management->Production Reports->Payment Allocation",
        ),
        (
            "contractual_plan_analysis",
            "Reports->Practice Management->Insurance Reports->Contractual Plan Analysis",
        ),
        (
            "insurance_payment_distribution",
            "Reports->Accounting->Insurance Payment Distribution",
        ),
    ):
        out["probes"].append(probe_report(rid, path, start, end, do_preview=False))

    dest = Path(r"C:\SoftDentFinancialExports\gold_csv_softdent_1year_report_check_2026-07-13.json")
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2)[:8000])
    print("WROTE", dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
