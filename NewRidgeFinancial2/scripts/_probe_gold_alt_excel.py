"""OPS probe: SoftDent alternate menus for Excel availability.

Never Esc on SoftDent main. Never Printer. Never invent gold.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

NR2 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(NR2))

from softdent_gui_export import (
    _focus_main,
    _open_report_via_win32_menu,
    _select_output_option_prompt,
    _send_softdent_keys,
    cancel_printer_dialogs,
    dismiss_softdent_alerts,
    find_dialog,
    list_softdent_window_titles,
    softdent_report_preview_visible,
)


def titles() -> list[str]:
    return list_softdent_window_titles()


def close_mdi_preview() -> dict:
    """Close active SoftDent MDI report with Ctrl+F4 (not Esc on main)."""
    if not softdent_report_preview_visible():
        return {"closed": False, "reason": "no_preview"}
    _focus_main()
    _send_softdent_keys("^({F4})")
    time.sleep(0.8)
    return {"closed": not softdent_report_preview_visible(), "titles": titles()[:8]}


def excel_enabled_in_output_options() -> dict:
    dlg = find_dialog("Output Options")
    if not dlg:
        return {"dialog": False, "excelEnabled": None}
    info: dict = {"dialog": True, "excelEnabled": None, "labels": []}
    try:
        for c in dlg.descendants():
            try:
                cls = (c.class_name() or "").lower()
                txt = (c.window_text() or "").strip()
                if not txt:
                    continue
                low = txt.lower()
                if "excel" in low or "preview" in low or "printer" in low:
                    en = None
                    try:
                        en = bool(c.is_enabled())
                    except Exception:
                        pass
                    info["labels"].append({"text": txt, "class": cls, "enabled": en})
                    if "excel" in low:
                        info["excelEnabled"] = en if en is not None else True
            except Exception:
                continue
    except Exception as e:  # noqa: BLE001
        info["error"] = f"{type(e).__name__}:{e}"
    return info


def main() -> int:
    out: dict = {
        "ok": True,
        "probes": [],
        "honesty": "excel probe only — does not invent gold CSV",
    }
    out["closePreview"] = close_mdi_preview()
    dismiss_softdent_alerts()
    cancel_printer_dialogs()

    paths = [
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
    ]

    for rid, path in paths:
        entry: dict = {"id": rid, "path": path}
        try:
            dismiss_softdent_alerts()
            cancel_printer_dialogs()
            _focus_main()
            if softdent_report_preview_visible():
                close_mdi_preview()
                time.sleep(0.4)
            opened = False
            try:
                opened = bool(_open_report_via_win32_menu(path))
            except Exception as e:  # noqa: BLE001
                entry["openError"] = f"{type(e).__name__}:{e}"
            time.sleep(0.6)
            oo = find_dialog("Output Options") or find_dialog("Report Setup")
            entry["opened"] = opened or bool(oo)
            entry["outputOptions"] = excel_enabled_in_output_options()
            excel_en = entry["outputOptions"].get("excelEnabled")
            if oo and excel_en:
                entry["attempt"] = "excel_selected"
                try:
                    _select_output_option_prompt("excel")
                    time.sleep(1.0)
                    entry["afterExcelTitles"] = titles()[:10]
                    entry["excelLikelyAvailable"] = True
                except Exception as e:  # noqa: BLE001
                    entry["excelSelectError"] = f"{type(e).__name__}:{e}"
                    entry["excelLikelyAvailable"] = False
                    try:
                        _send_softdent_keys("%c")
                    except Exception:
                        pass
            elif oo:
                entry["attempt"] = "excel_unavailable_cancel"
                entry["excelLikelyAvailable"] = False
                try:
                    _send_softdent_keys("%c")
                    time.sleep(0.4)
                except Exception as e:  # noqa: BLE001
                    entry["cancelError"] = f"{type(e).__name__}:{e}"
            else:
                entry["excelLikelyAvailable"] = False
                entry["titles"] = titles()[:10]
            if softdent_report_preview_visible():
                close_mdi_preview()
        except Exception as e:  # noqa: BLE001
            entry["error"] = f"{type(e).__name__}:{e}"
        out["probes"].append(entry)

    out["finalTitles"] = titles()[:12]
    out["anyExcel"] = any(p.get("excelLikelyAvailable") for p in out["probes"])

    dest = Path(r"C:\SoftDentFinancialExports\gold_csv_procurement_alt_menu_probe_2026-07-13.json")
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2)[:7000])
    print("WROTE", dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
