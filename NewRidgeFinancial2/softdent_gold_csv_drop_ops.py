"""HAL-10597 / gold-ops-v19-honest — SoftDent gold path for Print Preview reality.

SoftDent v19.1.4: no 'Insurance Payment Analysis' menu; Excel unavailable for
Insurance Income / related reports → Print Preview only (never Printer).
Visual audit (HAL-10590) records last-page totals but does NOT create gold lines.
If a real line-item CSV later appears, schema verify + ingest still apply.

Honesty: empty != $0. gapCode stays GOLD_CSV_MISSING / paymentLines=0 until real CSV.
No SoftDent write-back. Never invent gold from ledger/DaySheet.
"""

from __future__ import annotations

import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from softdent_gold_payment_pipeline import (
    audit_gold_payment_pipeline,
    run_gold_payment_pipeline_repair,
    validate_exact_usable_cells,
)
from softdent_treatment_planning import (
    _PAYMENT_COLMAP,
    _PAYMENT_GLOBS,
    find_newest_csv,
    resolve_exports_dir,
)

DEF_ID = "HAL-10597"
PACKAGE_BUILD_ID = "hal-10597"
PRIOR_DEF_ID = "HAL-10589"

# Required semantic fields for gold ingest (aliases in _PAYMENT_COLMAP)
_REQUIRED_FIELDS = ("insurance_company", "ada_code", "paid_amount")
_RECOMMENDED_FIELDS = ("write_off_amount", "submitted_fee", "allowed_amount", "payment_date")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def gold_csv_drop_playbook() -> dict[str, Any]:
    return {
        "package": DEF_ID,
        "softDentVersion": "v19.1.4",
        "softDentMenuDiscovered": (
            "SoftDent v19.1.4 has NO menu item named 'Insurance Payment Analysis'. "
            "Use Insurance Income / Contractual Plan Analysis / Payment Allocation."
        ),
        "softDentMenu": (
            "Reports → Practice Management → Insurance Reports → Insurance Income "
            "(primary candidate)"
        ),
        "altMenus": [
            "Reports → Practice Management → Insurance Reports → Contractual Plan Analysis",
            "Reports → Practice Management → Production Reports → Payment Allocation",
            "Reports → Accounting → Insurance Payment Distribution",
        ],
        "f10Sequences": {
            "insurance_income": "F10 r m i i",
            "contractual_plan_analysis": "F10 r m i a",
            "payment_allocation": "F10 r m p p",
            "insurance_payment_distribution": "F10 r a i",
        },
        "params": "Last 12 months (1 year), all carriers, include write-offs when offered",
        "format": "Print Preview only — Excel not available on this SoftDent for these reports. NEVER Printer.",
        "outputMode": "print_preview_only",
        "excelAvailable": False,
        "visualRead": (
            "After Print Preview opens, page through with Next/PageDown — detail often "
            "continues on later pages. Then go to the LAST page for exact totals. "
            "Do not invent dollars from page 1 alone."
        ),
        "saveAs": (
            "No Excel/CSV from SoftDent for this report on v19.1.4 — Print Preview is visual truth. "
            "sd_insurance_payment_lines stays 0 until a real line-item file exists (empty != $0)."
        ),
        "visualAuditBridge": {
            "def": "HAL-10590",
            "widget": "softdent-print-preview-audit",
            "records": "lastPageAggregateTotal only (Insurance Income)",
            "doesNotCreateGoldLines": True,
            "triggersGoldIngest": False,
            "then": "Optional visual×ledger recon (HAL-10592+) — flag variance only",
        },
        "optional": r"procedure_codes_YYYYMMDD.csv from Procedure Code Listing (if Excel offered elsewhere)",
        "ifRealCsvAppears": (
            "Place insurance_payments*.csv under SoftDentFinancialExports → Sync / "
            "run_ops_10589_gold_csv_drop — schema verify then ingest. Never invent CSV from ledger."
        ),
        "then": (
            "1) Print Preview → page-through → last page  "
            "2) Record Print Preview Visual Audit (HAL-10590)  "
            "3) Checklist records status; gapCode stays GOLD_CSV_MISSING until real CSV"
        ),
        "never": (
            "Printer; Esc on SoftDent main; invent gold from ledger/DaySheet/sd_payments; "
            "pretend Excel exists; treat visual audit as payment lines"
        ),
        "launch": "Desktop/Start Menu 'CS SoftDent Software.lnk' (-sus) only — never bare SDWIN.EXE",
        "signOn": "COMPUTE / computer (or SOFTDENT_SIGNON_* env)",
        "note": (
            "Operator: Excel is not available for Insurance Income / related reports — "
            "use Print Preview (click Print Preview → Enter → Next pages as needed → last page). "
            "Visual audit does NOT populate gold payment lines."
        ),
        "whenPrintPreviewOnly": {
            "title": "When Print Preview is the Only Option",
            "f10": "F10 r m i i",
            "steps": [
                "Launch SoftDent via CS SoftDent Software.lnk (Sign On COMPUTE)",
                "Reports → Practice Management → Insurance Reports → Insurance Income",
                "Output Options → Print Preview → Enter (never Printer; Excel unavailable)",
                "PageDown/Next through pages — page 1 alone is incomplete",
                "LAST page → read Total Insurance Income (aggregate only)",
                "Record via Print Preview Visual Audit widget (HAL-10590) — does NOT create gold lines",
                "Confirm gold pipeline still shows gapCode=GOLD_CSV_MISSING / paymentLines=0",
            ],
            "seeAlso": "softdent_print_preview_audit.py / policy:print-preview-audit",
            "honesty": "gapCode stays GOLD_CSV_MISSING; paymentLines stays 0; empty != $0; triggersGoldIngest=false",
        },
        "honesty": "empty != $0; Print Preview ≠ gold ingest; no SoftDent write-back",
    }


def _field_lookup(headers: list[str]) -> dict[str, str]:
    return {str(h).strip().lower(): str(h) for h in headers if h}


def _has_alias(lookup: dict[str, str], aliases: tuple[str, ...]) -> bool:
    return any(a.lower() in lookup for a in aliases)


def verify_gold_csv_schema(path: Path) -> dict[str, Any]:
    """Validate Insurance Payment Analysis CSV for ingest readiness."""
    out: dict[str, Any] = {
        "ok": False,
        "path": str(path),
        "bytes": 0,
        "dataRows": 0,
        "headers": [],
        "requiredPresent": {},
        "recommendedPresent": {},
        "missingRequired": [],
        "sampleRows": 0,
        "honesty": "empty != $0; invalid/missing schema is not zero payments",
    }
    if not path.is_file():
        out["error"] = "file_missing"
        return out
    out["bytes"] = path.stat().st_size
    if out["bytes"] < 8:
        out["error"] = "file_empty"
        return out
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            headers = list(reader.fieldnames or [])
            out["headers"] = headers
            if not headers:
                out["error"] = "no_headers"
                return out
            lookup = _field_lookup(headers)
            req: dict[str, bool] = {}
            missing: list[str] = []
            for field in _REQUIRED_FIELDS:
                ok = _has_alias(lookup, _PAYMENT_COLMAP[field])
                req[field] = ok
                if not ok:
                    missing.append(field)
            out["requiredPresent"] = req
            out["missingRequired"] = missing
            out["recommendedPresent"] = {
                f: _has_alias(lookup, _PAYMENT_COLMAP[f]) for f in _RECOMMENDED_FIELDS
            }
            n = 0
            for _ in reader:
                n += 1
                if n > 500000:
                    break
            out["dataRows"] = n
            out["sampleRows"] = min(n, 3)
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"{type(exc).__name__}:{exc}"
        return out

    out["ok"] = not missing and out["dataRows"] > 0
    if missing:
        out["error"] = "missing_required_columns"
    elif out["dataRows"] <= 0:
        out["error"] = "no_data_rows"
    return out


def checklist_pre_drop(*, db_path: Path | None = None, search_dir: Path | None = None) -> dict[str, Any]:
    audit = audit_gold_payment_pipeline(db_path=db_path, search_dir=search_dir)
    newest = find_newest_csv(_PAYMENT_GLOBS, search_dir=search_dir)
    schema = verify_gold_csv_schema(newest) if newest else None
    steps = [
        {
            "id": "file_present",
            "ok": newest is not None,
            "detail": str(newest) if newest else "No insurance_payments*.csv under export roots",
        },
        {
            "id": "schema_valid",
            "ok": bool(schema and schema.get("ok")),
            "detail": (schema or {}).get("error") or f"rows={(schema or {}).get('dataRows')}",
        },
        {
            "id": "gap_not_missing",
            "ok": audit.get("gapCode") != "GOLD_CSV_MISSING",
            "detail": f"gapCode={audit.get('gapCode')}",
        },
        {
            "id": "payment_lines_gt_0",
            "ok": int(audit.get("paymentLines") or 0) > 0,
            "detail": f"paymentLines={audit.get('paymentLines')}",
        },
    ]
    return {
        "ok": True,
        "def": DEF_ID,
        "phase": "pre",
        "checkedAt": _utc_now(),
        "playbook": gold_csv_drop_playbook(),
        "audit": {
            "gapCode": audit.get("gapCode"),
            "paymentLines": audit.get("paymentLines"),
            "candidates": len(audit.get("candidates") or []),
            "newestPaymentCsv": audit.get("newestPaymentCsv"),
        },
        "schema": schema,
        "steps": steps,
        "passCount": sum(1 for s in steps if s["ok"]),
        "stepCount": len(steps),
        "readyForIngest": bool(schema and schema.get("ok")),
        "honesty": "empty != $0 until GOLD_OK",
    }


def checklist_post_ingest(*, db_path: Path | None = None, search_dir: Path | None = None) -> dict[str, Any]:
    audit = audit_gold_payment_pipeline(db_path=db_path, search_dir=search_dir)
    validation = validate_exact_usable_cells(db_path=db_path)
    newest = find_newest_csv(_PAYMENT_GLOBS, search_dir=search_dir)
    spine_err = str(validation.get("error") or "")
    if validation.get("ok"):
        spine_ok = int(validation.get("flagCount") or 0) == 0
        spine_detail = (
            f"checked={validation.get('cellsChecked')} "
            f"pass={validation.get('passCount')} flag={validation.get('flagCount')}"
        )
    elif spine_err in {"spine_table_missing", "analytics_db_missing"}:
        spine_ok = True
        spine_detail = f"skipped ({spine_err}) — not a regression"
    else:
        spine_ok = int(validation.get("flagCount") or 0) == 0
        spine_detail = spine_err or "spine_validation_incomplete"
    steps = [
        {
            "id": "file_present",
            "ok": newest is not None or bool(audit.get("candidates")),
            "detail": audit.get("newestPaymentCsv") or f"candidates={len(audit.get('candidates') or [])}",
        },
        {
            "id": "gap_gold_ok",
            "ok": audit.get("gapCode") == "GOLD_OK",
            "detail": f"gapCode={audit.get('gapCode')}",
        },
        {
            "id": "payment_lines_gt_0",
            "ok": int(audit.get("paymentLines") or 0) > 0,
            "detail": f"paymentLines={audit.get('paymentLines')}",
        },
        {
            "id": "exact_spine_no_regression",
            "ok": spine_ok,
            "detail": spine_detail,
        },
    ]
    all_ok = all(s["ok"] for s in steps)
    return {
        "ok": all_ok,
        "def": DEF_ID,
        "phase": "post",
        "checkedAt": _utc_now(),
        "audit": {
            "gapCode": audit.get("gapCode"),
            "paymentLines": audit.get("paymentLines"),
            "newestPaymentCsv": audit.get("newestPaymentCsv"),
        },
        "exactUsableValidation": {
            "cellsChecked": validation.get("cellsChecked"),
            "passCount": validation.get("passCount"),
            "flagCount": validation.get("flagCount"),
            "remittanceAvailable": validation.get("remittanceAvailable"),
            "error": validation.get("error"),
        },
        "steps": steps,
        "passCount": sum(1 for s in steps if s["ok"]),
        "stepCount": len(steps),
        "honesty": "empty != $0; GOLD_OK requires real SoftDent payment lines",
    }


def attempt_softdent_insurance_payment_analysis_export(
    *,
    start: date | None = None,
    end: date | None = None,
    dest_root: Path | None = None,
) -> dict[str, Any]:
    """Open SoftDent insurance payment candidate via Print Preview (Excel not available).

    SoftDent v19.1.4: no 'Insurance Payment Analysis'; Excel unavailable for these
    reports — Output Options → Print Preview → Enter → Next/PageDown through pages →
    last page for totals. Never Printer. Never Esc on SoftDent main.
    Does not invent gold CSV/dollars.
    """
    import time

    out: dict[str, Any] = {
        "ok": False,
        "def": DEF_ID,
        "attemptedAt": _utc_now(),
        "path": None,
        "outputMode": "print_preview_only",
        "excelAvailable": False,
        "playbook": gold_csv_drop_playbook(),
        "menuDiscovery": "no Insurance Payment Analysis on SoftDent v19.1.4",
        "honesty": (
            "Print Preview is visual truth only — does not populate "
            "sd_insurance_payment_lines. Page through for detail; last page for totals. "
            "empty != $0."
        ),
    }
    end = end or date.today()
    start = start or date(end.year - 1, end.month, end.day)
    _ = dest_root

    try:
        from softdent_gui_export import (
            _focus_main,
            _open_report_via_keys,
            _open_report_via_win32_menu,
            _select_output_option_prompt,
            _send_softdent_keys,
            _type_keys_clear_and_text,
            _keyboard_activate_dialog,
            _keyboard_press_ok,
            cancel_printer_dialogs,
            dismiss_softdent_alerts,
            find_dialog,
            list_softdent_window_titles,
            navigate_softdent_print_preview_pages,
            open_report_print_preview,
            softdent_main_running,
            softdent_report_preview_visible,
            _softdent_pids,
            _window_pid,
        )
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"gui_import_failed:{type(exc).__name__}:{exc}"
        out["hint"] = "Sign On SoftDent, then Print Preview Insurance Income manually."
        return out

    if not softdent_main_running():
        out["error"] = "softdent_not_running"
        out["hint"] = "Launch CS SoftDent Software.lnk (-sus), Sign On, then retry."
        return out

    try:
        _focus_main()
    except Exception as exc:  # noqa: BLE001
        out["focusError"] = f"{type(exc).__name__}:{exc}"
        out["hint"] = "Bring SoftDent to foreground, then retry."
        return out

    dismiss_softdent_alerts()
    cancel_printer_dialogs()

    preview_result: dict[str, Any] | None = None
    try:
        preview_result = open_report_print_preview(
            "insurance_payment_analysis",
            start=start,
            end=end,
            page_through=True,
            max_next_pages=40,
        )
        out["menuPathUsed"] = "insurance_payment_analysis → Insurance Income"
        out["openMethod"] = "open_report_print_preview"
    except Exception as exc:  # noqa: BLE001
        out["catalogPreviewError"] = f"{type(exc).__name__}:{exc}"

    if not softdent_report_preview_visible((preview_result or {}).get("titles")):
        # Manual open: Output Options → Print Preview (never Excel / Printer)
        win32_paths = [
            "Reports->Practice Management->Insurance Reports->Insurance Income",
            "Reports->Practice Management->Insurance Reports->Contractual Plan Analysis",
            "Reports->Practice Management->Production Reports->Payment Allocation",
            "Reports->Accounting->Insurance Payment Distribution",
        ]
        opened = False
        for path in win32_paths:
            try:
                dismiss_softdent_alerts()
                cancel_printer_dialogs()
                _focus_main()
                if _open_report_via_win32_menu(path):
                    out["menuPathUsed"] = path
                    out["openMethod"] = "win32_menu+print_preview"
                    opened = True
                    break
            except Exception as menu_exc:  # noqa: BLE001
                out.setdefault("menuAttempts", []).append(
                    {"path": path, "error": f"{type(menu_exc).__name__}:{menu_exc}"}
                )
        if not opened:
            try:
                _open_report_via_keys("i")
                out["menuPathUsed"] = "F10 r a i (Insurance Payment Distribution)"
                out["openMethod"] = "f10_keyboard+print_preview"
                opened = bool(find_dialog("Output Options") or find_dialog("Report Setup"))
            except Exception as key_exc:  # noqa: BLE001
                out["keyFallbackError"] = f"{type(key_exc).__name__}:{key_exc}"

        if not find_dialog("Output Options") and not find_dialog("Report Setup"):
            # May already be on an MDI report from a prior open
            titles_now = list_softdent_window_titles()
            if softdent_report_preview_visible(titles_now):
                preview_result = {
                    "ok": True,
                    "printPreviewOpen": True,
                    "titles": titles_now[:12],
                    "outputMode": "print_preview",
                }
            else:
                out["error"] = "output_options_missing"
                out["hint"] = (
                    "Open SoftDent → Insurance Income → Output Options → "
                    "Print Preview (Excel not available) → Enter → Next pages → last page."
                )
                return out

        if not (preview_result or {}).get("printPreviewOpen"):
            try:
                _select_output_option_prompt("print_preview")
            except Exception as sel_exc:  # noqa: BLE001
                out["error"] = f"print_preview_select_failed:{type(sel_exc).__name__}:{sel_exc}"
                out["hint"] = "Click Print Preview (not Excel/Printer), then Enter."
                return out

            setup = None
            for _ in range(40):
                cancel_printer_dialogs(max_rounds=2)
                from pywinauto import Desktop

                pids = _softdent_pids()
                for w in Desktop(backend="win32").windows():
                    try:
                        t = (w.window_text() or "").strip()
                        if pids and _window_pid(int(w.handle)) not in pids:
                            continue
                        if "setup" in t.lower() and "softdent software" not in t.lower():
                            setup = w
                            break
                    except Exception:
                        continue
                if setup or find_dialog("Print Preview") or softdent_report_preview_visible():
                    break
                time.sleep(0.25)
            if setup:
                _keyboard_activate_dialog(setup)
                h = int(setup.handle)
                start_txt = start.strftime("%m/%d/%y")
                end_txt = end.strftime("%m/%d/%y")
                _send_softdent_keys("{TAB}", hwnd=h)
                time.sleep(0.1)
                _type_keys_clear_and_text(start_txt, hwnd=h)
                _send_softdent_keys("{TAB}", hwnd=h)
                time.sleep(0.1)
                _type_keys_clear_and_text(end_txt, hwnd=h)
                _send_softdent_keys("{TAB}", hwnd=h)
                time.sleep(0.1)
                _type_keys_clear_and_text("999", hwnd=h)
                time.sleep(0.15)
                _keyboard_press_ok(hwnd=h)
                time.sleep(1.2)
                cancel_printer_dialogs()

            for _ in range(60):
                titles = list_softdent_window_titles()
                if any("sorting" in t.lower() for t in titles):
                    time.sleep(0.5)
                    continue
                break
            titles = list_softdent_window_titles()
            preview_result = {
                "ok": True,
                "printPreviewOpen": softdent_report_preview_visible(titles),
                "titles": titles[:12],
                "outputMode": "print_preview",
            }

    # Page through (Next/PageDown) then last page — detail is often not on page 1
    nav = (preview_result or {}).get("pageNavigation")
    if not isinstance(nav, dict) or not nav.get("ok"):
        nav = navigate_softdent_print_preview_pages(max_next_pages=40)
    out["pageNavigation"] = nav
    titles = list_softdent_window_titles()
    if preview_result is None:
        preview_result = {}
    preview_result["titles"] = titles[:12]
    preview_open = softdent_report_preview_visible(titles) or bool(
        preview_result.get("printPreviewOpen")
    )
    out["preview"] = preview_result
    out["printPreviewOpen"] = preview_open
    out["mdiReportOpen"] = any("[" in t and "report" in t.lower() for t in titles)
    out["ok"] = preview_open
    if preview_open:
        out["nextStep"] = (
            "Insurance report open via Print Preview — page through for detail, "
            "LAST page for exact totals. Excel not available; no gold CSV ingest. empty != $0."
        )
        out.pop("error", None)
    else:
        out["error"] = out.get("error") or "print_preview_not_detected"
        out["hint"] = (
            "Output Options → click Print Preview → Enter → Next/PageDown as needed → "
            "last page. Never Printer. Excel is not available for this report."
        )
    try:
        notes = resolve_exports_dir()
        notes.mkdir(parents=True, exist_ok=True)
        note_path = notes / f"gold_print_preview_ops_{date.today().isoformat()}.json"
        note_path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
        out["notePath"] = str(note_path)
    except Exception as note_exc:  # noqa: BLE001
        out["noteError"] = f"{type(note_exc).__name__}:{note_exc}"
    return out


def export_ops_checklist_report(
    payload: dict[str, Any],
    *,
    dest: Path | None = None,
) -> dict[str, Any]:
    out_dir = Path(dest) if dest else resolve_exports_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = date.today().isoformat()
    json_path = out_dir / f"gold_csv_drop_ops_checklist_{stamp}.json"
    md_path = out_dir / f"gold_csv_drop_ops_checklist_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    pre = payload.get("pre") or {}
    post = payload.get("post") or {}
    lines = [
        f"# Gold CSV Drop OPS Checklist ({stamp}) — {DEF_ID}",
        "",
        f"**packageBuildId:** `{PACKAGE_BUILD_ID}`",
        f"**attemptGui:** {bool((payload.get('exportAttempt') or {}).get('ok') is not None)}",
        f"**exportOk:** {(payload.get('exportAttempt') or {}).get('ok')}",
        f"**pre readyForIngest:** {pre.get('readyForIngest')}",
        f"**post GOLD_OK:** {(post.get('audit') or {}).get('gapCode') == 'GOLD_OK'}",
        f"**paymentLines:** {(post.get('audit') or pre.get('audit') or {}).get('paymentLines')}",
        "",
        "## Playbook",
        "",
        f"- {gold_csv_drop_playbook()['softDentMenu']}",
        f"- Save: `{gold_csv_drop_playbook()['saveAs']}`",
        f"- empty != $0 until GOLD_OK",
        "",
        "## Post steps",
        "",
    ]
    for step in post.get("steps") or pre.get("steps") or []:
        mark = "PASS" if step.get("ok") else "FAIL"
        lines.append(f"- [{mark}] `{step.get('id')}` — {step.get('detail')}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = {"ok": True, "jsonPath": str(json_path), "mdPath": str(md_path)}
    try:
        from import_loader import softdent_import_dir

        inbox = softdent_import_dir()
        inbox.mkdir(parents=True, exist_ok=True)
        slim = {
            "ok": bool(post.get("ok")),
            "def": DEF_ID,
            "gapCode": (post.get("audit") or pre.get("audit") or {}).get("gapCode"),
            "paymentLines": (post.get("audit") or pre.get("audit") or {}).get("paymentLines"),
            "fullReport": str(json_path),
            "honesty": "empty != $0",
        }
        path = inbox / "softdent_gold_csv_drop_ops.json"
        path.write_text(json.dumps(slim, indent=2), encoding="utf-8")
        result["inboxPath"] = str(path)
    except Exception as exc:  # noqa: BLE001
        result["inboxError"] = f"{type(exc).__name__}:{exc}"
    return result


def run_ops_10589_gold_csv_drop(
    *,
    attempt_gui_export: bool = True,
    db_path: Path | None = None,
    search_dir: Path | None = None,
) -> dict[str, Any]:
    """Facilitate SoftDent gold CSV drop + verify ingest. Never invents gold lines."""
    pre = checklist_pre_drop(db_path=db_path, search_dir=search_dir)
    export_attempt: dict[str, Any] | None = None
    if attempt_gui_export and not pre.get("readyForIngest"):
        export_attempt = attempt_softdent_insurance_payment_analysis_export()
        # Re-check after GUI attempt
        pre = checklist_pre_drop(db_path=db_path, search_dir=search_dir)

    ingest = None
    if pre.get("readyForIngest") or int((pre.get("audit") or {}).get("paymentLines") or 0) == 0:
        # Always attempt repair when a candidate/file may exist; safe no-op if missing
        ingest = run_gold_payment_pipeline_repair(db_path=db_path, search_dir=search_dir)

    post = checklist_post_ingest(db_path=db_path, search_dir=search_dir)
    payload = {
        "ok": bool(post.get("ok")),
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "checkedAt": _utc_now(),
        "pre": pre,
        "exportAttempt": export_attempt,
        "ingest": {
            "ok": bool((ingest or {}).get("ok")),
            "paymentLines": ((ingest or {}).get("audit") or {}).get("paymentLines"),
            "gapCode": ((ingest or {}).get("audit") or {}).get("gapCode"),
            "jsonPath": ((ingest or {}).get("export") or {}).get("jsonPath"),
        }
        if ingest
        else None,
        "post": post,
        "playbook": gold_csv_drop_playbook(),
        "honesty": "empty != $0; do not invent gold from ledger spine",
    }
    payload["export"] = export_ops_checklist_report(payload)
    return payload


def format_gold_csv_drop_ops_reply(result: dict[str, Any] | None = None) -> str:
    r = result if isinstance(result, dict) else run_ops_10589_gold_csv_drop(attempt_gui_export=False)
    post = r.get("post") or checklist_post_ingest()
    audit = post.get("audit") or {}
    play = gold_csv_drop_playbook()
    return (
        f"Gold OPS ({DEF_ID} / v19 Print Preview honest): gapCode={audit.get('gapCode')}; "
        f"lines={audit.get('paymentLines')}; "
        f"postPass={post.get('passCount')}/{post.get('stepCount')}; "
        f"outputMode={play.get('outputMode')}; excelAvailable={play.get('excelAvailable')}. "
        f"Playbook: SoftDent {play['softDentMenu']} → Print Preview → page-through → "
        f"HAL-10590 visual audit (does NOT create gold lines). "
        f"{play['saveAs']} empty != $0. "
        r"Ticket pack: C:\SoftDentFinancialExports\CARESTREAM_GOLD_CSV_TICKET_PACK_2026-07-13 · "
        "carestreamCaseNumber pending · drop insurance_payments_*.csv → Sync → settlement fills."
    )


def gold_csv_drop_ops_widget() -> dict[str, Any]:
    post = checklist_post_ingest()
    audit = post.get("audit") or {}
    play = gold_csv_drop_playbook()
    lines = int(audit.get("paymentLines") or 0)
    gap = str(audit.get("gapCode") or "")
    if gap == "GOLD_OK" and lines > 0:
        status, tone = "ok", "ok"
        message = f"Gold CSV ingested · lines={lines}"
    elif gap == "GOLD_FILE_PRESENT_NOT_INGESTED":
        status, tone = "warn", "warn"
        message = "Gold file on disk — run Sync / OPS verify ingest"
    else:
        # SoftDent v19 Insurance Income is Print Preview only — surface that OPS
        # knowledge as warn (not blank empty) while keeping GOLD_CSV_MISSING honesty.
        status, tone = "warn", "warn"
        message = (
            "SoftDent pull ready: Reports → Practice Management → Insurance Reports → "
            "Insurance Income → Print Preview (never Printer) → last page. "
            f"gapCode={gap or 'GOLD_CSV_MISSING'} · paymentLines=0 (Preview ≠ gold CSV; empty ≠ $0)"
        )
    return {
        "id": "softdent-gold-csv-drop-ops",
        "type": "status",
        "label": "Gold OPS v19 Print Preview (HAL-10597)",
        "size": "full",
        "status": status,
        "tone": tone,
        "message": message,
        "hint": (
            f"{play['softDentMenu']} → Print Preview (never Printer) → page-through → "
            f"last page → HAL-10590 visual audit. Does NOT populate payment lines."
        ),
        "gapCode": gap,
        "paymentLines": lines,
        "outputMode": play.get("outputMode"),
        "excelAvailable": False,
        "triggersGoldIngest": False,
        "visualAuditBridge": play.get("visualAuditBridge"),
        "checklist": post.get("steps"),
        "playbook": play,
        "halChips": [
            {"label": "Gold CSV drop status", "query": "gold csv drop ops status"},
            {
                "label": "How do I export Insurance Payment Analysis?",
                "query": "How do I export SoftDent Insurance Payment Analysis CSV?",
            },
            {
                "label": "Print Preview visual audit",
                "query": "SoftDent Print Preview visual audit status",
            },
            {
                "label": "Pull SoftDent reports",
                "query": "How do I pull SoftDent reports?",
            },
        ],
        "honesty": play.get("honesty") or "empty != $0",
        "emptyIsNotZero": True,
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "priorDef": PRIOR_DEF_ID,
    }


# Back-compat alias
run_ops_10597_gold_ops_v19 = run_ops_10589_gold_csv_drop


if __name__ == "__main__":
    print(json.dumps(run_ops_10589_gold_csv_drop(attempt_gui_export=True), indent=2, default=str)[:6000])
