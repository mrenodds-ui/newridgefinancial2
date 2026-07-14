"""HAL-10606 — SoftDent Gold CSV drop facilitation for settlement_matrix hydrate.

Moonshot: MOONSHOT_WHATS_NEXT_AFTER_HAL10605_2026-07-13.md
Builds ON HAL-10589/10597 gold drop OPS + HAL-10605 settlement_matrix.
Does NOT invent gold lines. empty != $0. No SoftDent write-back.

SoftDent v19.1.4 honesty (unchanged): no menu named Insurance Payment Analysis;
Insurance Income / related reports are Print Preview only (≠ gold lines).
A real line-item CSV elsewhere still drops under SoftDentFinancialExports → Sync.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from softdent_gold_csv_drop_ops import (
    checklist_post_ingest,
    checklist_pre_drop,
    export_ops_checklist_report,
    gold_csv_drop_playbook,
    run_ops_10589_gold_csv_drop,
)
from softdent_gold_payment_pipeline import audit_gold_payment_pipeline
from softdent_treatment_planning import resolve_exports_dir

DEF_ID = "HAL-10606"
PACKAGE_BUILD_ID = "hal-10606"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def staff_briefing() -> dict[str, Any]:
    """Moonshot approval checklist — staff briefing for gold drop."""
    return {
        "title": "Staff briefing — Gold CSV drop (HAL-10606)",
        "do": [
            "Drop raw SoftDent insurance payment line-item CSV under "
            r"C:\SoftDentFinancialExports\ as insurance_payments_YYYYMMDD.csv",
            "Do not edit the CSV before drop",
            "After drop, run Sync (or gold-csv-drop-ops / HAL-10606 run)",
            "Expect TP source viaGold only after settlement_matrix hydrates",
        ],
        "doNot": [
            "Invent payment lines from DaySheet / ledger / Print Preview totals",
            "Treat Print Preview visual audit as gold lines (empty != $0)",
            "Force-match rejected carrier aliases to invent TP dollars",
            "Write estimates back into SoftDent",
        ],
        "v19Reality": (
            "SoftDent v19.1.4 has no menu named Insurance Payment Analysis; "
            "Insurance Income is Print Preview only and does NOT create gold lines. "
            "Place a real line-item CSV if obtained from SoftDent or another export path."
        ),
        "acceptanceTargets": {
            "paymentLinesMin": 1000,
            "matrixCellsNge10Min": 200,
            "gapCodeTarget": "GOLD_OK",
        },
        "honesty": "empty != $0; inventedGold=false",
    }


def verify_export_path_writable(*, dest: Path | None = None) -> dict[str, Any]:
    root = Path(dest) if dest else resolve_exports_dir()
    out: dict[str, Any] = {
        "ok": False,
        "path": str(root),
        "exists": False,
        "writable": False,
        "emptyIsNotZero": True,
    }
    try:
        root.mkdir(parents=True, exist_ok=True)
        out["exists"] = root.is_dir()
        probe = root / f".hal10606_write_probe_{os.getpid()}.tmp"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        out["writable"] = True
        out["ok"] = True
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"{type(exc).__name__}:{exc}"
    return out


def settlement_matrix_gate(*, db_path: Path | None = None) -> dict[str, Any]:
    from softdent_settlement_matrix import settlement_matrix_status

    st = settlement_matrix_status(db_path=db_path)
    steps = [
        {
            "id": "export_path_writable",
            "ok": False,  # filled by caller
            "detail": "",
        },
        {
            "id": "payment_lines_gt_0",
            "ok": int(st.get("paymentLines") or 0) > 0,
            "detail": f"paymentLines={st.get('paymentLines')}",
        },
        {
            "id": "matrix_cells_gt_0",
            "ok": int(st.get("matrixCells") or 0) > 0,
            "detail": f"matrixCells={st.get('matrixCells')}",
        },
        {
            "id": "cells_nge10_target_200",
            "ok": int(st.get("cellsNge10") or 0) >= 200,
            "detail": f"cellsNge10={st.get('cellsNge10')} target=200",
        },
        {
            "id": "hal10605_acceptance_gate",
            "ok": bool(st.get("acceptanceGateMet")),
            "detail": f"acceptanceGateMet={st.get('acceptanceGateMet')} gap={st.get('gapCode')}",
        },
    ]
    return {
        "ok": True,
        "def": DEF_ID,
        "matrix": st,
        "steps": steps,
        "passCount": sum(1 for s in steps if s["ok"]),
        "stepCount": len(steps),
        "honesty": "empty != $0 until GOLD_OK + matrix hydrate",
    }


def gold_drop_facilitation_playbook() -> dict[str, Any]:
    base = gold_csv_drop_playbook()
    return {
        **base,
        "package": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "priorPackages": ["HAL-10589", "HAL-10597", "HAL-10605"],
        "purpose": (
            "Unblock HAL-10605 settlement_matrix by landing a real insurance payment "
            "line-item CSV; Print Preview alone never hydrates gold."
        ),
        "staffBriefing": staff_briefing(),
        "afterSync": (
            "run_ops_10606_gold_drop_facilitation → repair ingest → hydrate settlement_matrix "
            "→ TP prefers viaGold"
        ),
        "saveAsLineItemCsv": r"C:\SoftDentFinancialExports\insurance_payments_YYYYMMDD.csv",
        "ifOnlyPrintPreview": (
            "Record visual audit (HAL-10590); gapCode stays GOLD_CSV_MISSING; "
            "matrixCells stay 0 — empty != $0."
        ),
    }


def run_ops_10606_gold_drop_facilitation(
    *,
    attempt_gui_export: bool = False,
    db_path: Path | None = None,
    search_dir: Path | None = None,
) -> dict[str, Any]:
    """OPS facilitation: path check + 10589 drop/ingest + 10605 matrix gate + briefing."""
    path_check = verify_export_path_writable()
    ops = run_ops_10589_gold_csv_drop(
        attempt_gui_export=attempt_gui_export,
        db_path=db_path,
        search_dir=search_dir,
    )
    matrix_gate = settlement_matrix_gate(db_path=db_path)
    if matrix_gate.get("steps"):
        matrix_gate["steps"][0] = {
            "id": "export_path_writable",
            "ok": bool(path_check.get("ok")),
            "detail": path_check.get("path")
            if path_check.get("ok")
            else path_check.get("error") or path_check.get("path"),
        }
        matrix_gate["passCount"] = sum(1 for s in matrix_gate["steps"] if s["ok"])

    audit = audit_gold_payment_pipeline(db_path=db_path, search_dir=search_dir)
    pre = checklist_pre_drop(db_path=db_path, search_dir=search_dir)
    post = checklist_post_ingest(db_path=db_path, search_dir=search_dir)

    payload = {
        "ok": True,
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "checkedAt": _utc_now(),
        "exportPath": path_check,
        "priorOps10589": {
            "ok": ops.get("ok"),
            "gapCode": ((ops.get("post") or {}).get("audit") or {}).get("gapCode"),
            "paymentLines": ((ops.get("post") or {}).get("audit") or {}).get("paymentLines"),
            "export": ops.get("export"),
        },
        "pre": pre,
        "post": post,
        "matrixGate": matrix_gate,
        "audit": {
            "gapCode": audit.get("gapCode"),
            "paymentLines": audit.get("paymentLines"),
            "newestPaymentCsv": audit.get("newestPaymentCsv"),
            "treatmentEstimates": audit.get("treatmentEstimates"),
        },
        "playbook": gold_drop_facilitation_playbook(),
        "staffBriefing": staff_briefing(),
        "acceptance": {
            "paymentLines": int(audit.get("paymentLines") or 0),
            "matrixCells": int((matrix_gate.get("matrix") or {}).get("matrixCells") or 0),
            "cellsNge10": int((matrix_gate.get("matrix") or {}).get("cellsNge10") or 0),
            "acceptanceGateMet": bool(
                (matrix_gate.get("matrix") or {}).get("acceptanceGateMet")
            ),
            "gapCode": audit.get("gapCode"),
            "blockedReason": (
                None
                if audit.get("gapCode") == "GOLD_OK"
                else "GOLD_CSV_MISSING — drop real line-item CSV; Print Preview != gold"
            ),
        },
        "inventedGold": False,
        "emptyIsNotZero": True,
        "triggersGoldIngest": False,
        "honesty": (
            "Facilitation only — does not invent gold. "
            "HAL-10605 matrix stays empty until real payment CSV lands."
        ),
    }
    payload["export"] = export_hal10606_report(payload)
    return payload


def export_hal10606_report(payload: dict[str, Any], *, dest: Path | None = None) -> dict[str, Any]:
    out_dir = Path(dest) if dest else resolve_exports_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = date.today().isoformat()
    json_path = out_dir / f"gold_drop_facilitation_hal10606_{stamp}.json"
    md_path = out_dir / f"gold_drop_facilitation_hal10606_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    acc = payload.get("acceptance") or {}
    briefing = payload.get("staffBriefing") or staff_briefing()
    matrix_steps = ((payload.get("matrixGate") or {}).get("steps")) or []
    lines = [
        f"# HAL-10606 Gold Drop Facilitation ({stamp})",
        "",
        f"**packageBuildId:** `{PACKAGE_BUILD_ID}`",
        f"**gapCode:** `{acc.get('gapCode')}`",
        f"**paymentLines:** {acc.get('paymentLines')}",
        f"**matrixCells:** {acc.get('matrixCells')} · cellsNge10: {acc.get('cellsNge10')}",
        f"**acceptanceGateMet:** {acc.get('acceptanceGateMet')}",
        f"**blockedReason:** {acc.get('blockedReason')}",
        f"**exportPathOk:** {(payload.get('exportPath') or {}).get('ok')}",
        "",
        "## Staff briefing",
        "",
        f"- {briefing.get('v19Reality')}",
        "",
        "### Do",
    ]
    for item in briefing.get("do") or []:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### Do not")
    for item in briefing.get("doNot") or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Matrix / acceptance steps", ""])
    for step in matrix_steps:
        mark = "PASS" if step.get("ok") else "FAIL"
        lines.append(f"- [{mark}] `{step.get('id')}` — {step.get('detail')}")
    lines.extend(
        [
            "",
            "## Honesty",
            "",
            "- empty != $0",
            "- inventedGold=false",
            "Print Preview != sd_insurance_payment_lines",
            "",
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")

    result = {"ok": True, "jsonPath": str(json_path), "mdPath": str(md_path)}
    try:
        from import_loader import softdent_import_dir

        inbox = softdent_import_dir()
        inbox.mkdir(parents=True, exist_ok=True)
        slim = {
            "ok": True,
            "def": DEF_ID,
            "packageBuildId": PACKAGE_BUILD_ID,
            "gapCode": acc.get("gapCode"),
            "paymentLines": acc.get("paymentLines"),
            "acceptanceGateMet": acc.get("acceptanceGateMet"),
            "blockedReason": acc.get("blockedReason"),
            "staffBriefing": briefing,
            "fullReport": str(json_path),
            "honesty": "empty != $0; facilitation only",
        }
        path = inbox / "softdent_gold_drop_facilitation_hal10606.json"
        path.write_text(json.dumps(slim, indent=2), encoding="utf-8")
        result["inboxPath"] = str(path)
    except Exception as exc:  # noqa: BLE001
        result["inboxError"] = f"{type(exc).__name__}:{exc}"
    # Also refresh classic 10589 checklist companion if present
    try:
        export_ops_checklist_report(
            {
                "ok": False,
                "def": DEF_ID,
                "packageBuildId": PACKAGE_BUILD_ID,
                "pre": payload.get("pre"),
                "post": payload.get("post"),
                "exportAttempt": None,
            }
        )
    except Exception:
        pass
    return result


def format_hal10606_reply(result: dict[str, Any] | None = None) -> str:
    r = result if isinstance(result, dict) else run_ops_10606_gold_drop_facilitation()
    acc = r.get("acceptance") or {}
    return (
        f"Gold drop facilitation ({DEF_ID}): gapCode={acc.get('gapCode')}; "
        f"lines={acc.get('paymentLines')}; matrixCells={acc.get('matrixCells')}; "
        f"cellsNge10={acc.get('cellsNge10')}; acceptanceGateMet={acc.get('acceptanceGateMet')}. "
        f"{acc.get('blockedReason') or 'GOLD_OK path ready'}. "
        "empty != $0; Print Preview != gold lines."
    )


def gold_drop_facilitation_widget() -> dict[str, Any]:
    return {
        "id": "softdent-gold-drop-facilitation-hal10606",
        "title": "Gold CSV drop facilitation (HAL-10606)",
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "apiStatus": "/api/apex/gold-drop-facilitation/status",
        "apiRun": "/api/apex/gold-drop-facilitation/run",
        "honesty": "empty != $0; does not invent gold",
        "prior": "Builds on softdent-gold-csv-drop-ops + settlement_matrix",
    }
