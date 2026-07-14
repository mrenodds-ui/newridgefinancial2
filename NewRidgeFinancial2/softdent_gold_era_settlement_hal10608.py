"""HAL-10608 — Gold CSV ∪ ERA 835 settlement hydration readiness (STOP PWImages OCR).

Moonshot: MOONSHOT_PWIMAGES_JPEG_PDF_EOB_CONSULT_2026-07-13.md (operator: proceed)

- Explicit STOP on further JPEG/PDF OCR for settlement
- Single readiness surface: Gold payment lines OR ERA inbox/enrollment
- Delegates to HAL-10606 / gold repair / ERA inbox — no greenfield redo
- empty ≠ $0; no SoftDent write-back; no OCR $ → settlement/Gold
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from softdent_gold_drop_facilitation_hal10606 import (
    gold_drop_facilitation_playbook,
    settlement_matrix_gate,
    staff_briefing as staff_briefing_10606,
    verify_export_path_writable,
)
from softdent_gold_payment_pipeline import (
    audit_gold_payment_pipeline,
    run_gold_payment_pipeline_repair,
)
from softdent_treatment_planning import resolve_exports_dir

DEF_ID = "HAL-10608"
PACKAGE_BUILD_ID = "hal-10608"

HONESTY_BANNER = (
    "UNVERIFIED SCANNED ESTIMATE — DO NOT POST. "
    "AWAIT GOLD CSV OR ERA 835 FOR SETTLEMENT TRUTH."
)

STOP_OCR_POLICY: dict[str, Any] = {
    "ocrExpansionStopped": True,
    "writesFromOcr": False,
    "pdfRemittanceYield": 0,
    "pdfNote": "All PWImages PDFs are Check-In_Package forms — zero remittance EOBs.",
    "accountJpgRemittanceYieldApprox": "16/2646 (~0.6%) — vein exhausted for settlement",
    "patientJpgOcrBlocked": True,
    "patientJpgNote": "~88k Patient Other JPGs are clinical; OCR banned for settlement.",
    "banner": HONESTY_BANNER,
    "consult": "MOONSHOT_PWIMAGES_JPEG_PDF_EOB_CONSULT_2026-07-13.md",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def staff_briefing_10608() -> dict[str, Any]:
    base = staff_briefing_10606()
    return {
        "title": "Staff briefing — Gold ∪ ERA settlement hydration (HAL-10608)",
        "do": list(base.get("do") or [])
        + [
            r"Drop ERA 835/EDI under C:\SoftDentFinancialExports\era\ (or NR2_ERA835_INBOX)",
            "After Gold CSV or ERA drop, run Sync / HAL-10608 run (not PWImages OCR)",
        ],
        "doNot": list(base.get("doNot") or [])
        + [
            "OCR more PWImages Patient JPGs or PDFs for settlement dollars",
            "Treat scanned remittance JPEGs as Gold/ERA substitutes",
            "Invent InsCo×ADA averages from 16 warehoused remittance scans",
        ],
        "stopOcr": STOP_OCR_POLICY,
        "v19Reality": base.get("v19Reality"),
        "acceptanceTargets": {
            **(base.get("acceptanceTargets") or {}),
            "readyVia": "GOLD_OK paymentLines>0 OR ERA inbox files / ingested 835 rows",
        },
        "honesty": "empty != $0; inventedGold=false; writesFromOcr=false",
    }


def gold_lane_status(*, db_path: Path | None = None) -> dict[str, Any]:
    audit = audit_gold_payment_pipeline(db_path=db_path)
    matrix = settlement_matrix_gate(db_path=db_path)
    path = verify_export_path_writable()
    if matrix.get("steps"):
        matrix["steps"][0] = {
            "id": "export_path_writable",
            "ok": bool(path.get("ok")),
            "detail": path.get("path") if path.get("ok") else path.get("error"),
        }
        matrix["passCount"] = sum(1 for s in matrix["steps"] if s["ok"])
    return {
        "gapCode": audit.get("gapCode"),
        "paymentLines": int(audit.get("paymentLines") or 0),
        "newestPaymentCsv": audit.get("newestPaymentCsv"),
        "candidates": len(audit.get("candidates") or []),
        "matrixCells": int((matrix.get("matrix") or {}).get("matrixCells") or 0),
        "cellsNge10": int((matrix.get("matrix") or {}).get("cellsNge10") or 0),
        "acceptanceGateMet": bool((matrix.get("matrix") or {}).get("acceptanceGateMet")),
        "exportPath": path,
        "matrixGate": matrix,
        "rootCause": audit.get("rootCause"),
    }


def era_lane_status() -> dict[str, Any]:
    try:
        from apex_era835_pack import (
            GAP_ERA835_PENDING,
            assess_era835_gap,
            era_inbox_status,
            era835_enabled,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": f"{type(exc).__name__}:{exc}",
            "gapCode": "ERA835_PENDING",
            "fileCount": 0,
            "empty": True,
            "enabled": False,
        }

    inbox = era_inbox_status(ensure_dirs=True)
    gap = assess_era835_gap()
    file_count = int(inbox.get("fileCount") or 0)
    ingested = int(gap.get("rowCount") or 0)
    pending = bool(gap.get("pending"))
    latest = gap.get("latest") if isinstance(gap.get("latest"), dict) else {}
    return {
        "ok": True,
        "enabled": era835_enabled(),
        "gapCode": gap.get("gapCode") or (None if not pending else GAP_ERA835_PENDING),
        "pending": pending,
        "fileCount": file_count,
        "empty": bool(inbox.get("empty")),
        "chipStatus": inbox.get("chipStatus"),
        "chipLabel": inbox.get("chipLabel"),
        "ingestedRowSample": ingested,
        "latestTotalPaid": latest.get("totalPaid"),
        "latestPayerName": latest.get("payerName"),
        "latestSourceFile": latest.get("sourceFile"),
        "inboxRoots": [str(r) for r in (inbox.get("inbox") or {}).get("roots") or []],
        "fixHint": gap.get("fixHint"),
    }


def settlement_hydration_readiness_gate(
    *,
    gold: dict[str, Any] | None = None,
    era: dict[str, Any] | None = None,
) -> dict[str, Any]:
    g = gold if isinstance(gold, dict) else gold_lane_status()
    e = era if isinstance(era, dict) else era_lane_status()

    gold_ready = str(g.get("gapCode") or "") == "GOLD_OK" and int(g.get("paymentLines") or 0) > 0

    # ERA ops readiness: real inbox files OR non-pending ingest with a paid aggregate.
    # Stale fixture rows (e.g. t.835 / totalPaid null) must NOT ghost-ready the gate.
    file_count = int(e.get("fileCount") or 0)
    ingested = int(e.get("ingestedRowSample") or 0)
    era_pending = bool(e.get("pending"))
    era_gap = e.get("gapCode")
    latest_paid = e.get("latestTotalPaid")
    from money_cents import to_money
    from decimal import Decimal

    paid_d = to_money(latest_paid)
    has_paid = paid_d is not None and paid_d > Decimal("0.00")

    era_inbox_ready = file_count > 0
    era_ingest_ready = (
        (not era_pending)
        and era_gap is None
        and ingested > 0
        and has_paid
    )
    era_ready = era_inbox_ready or era_ingest_ready

    lanes: list[str] = []
    if gold_ready:
        lanes.append("gold")
    if era_ready:
        lanes.append("era")

    # Matrix hydrate is Gold-only (ERA readiness ≠ invent settlement_matrix cells)
    settlement_matrix_ready = gold_ready

    ready = bool(lanes)
    if settlement_matrix_ready:
        reason = "settlement_matrix ready via gold payment lines"
    elif era_inbox_ready:
        reason = f"ERA inbox has {file_count} file(s) — ingest available (matrix still needs Gold)"
    elif era_ingest_ready:
        reason = "ERA aggregates present with paid amount — ops lane only (matrix still needs Gold)"
    else:
        reason = (
            f"blocked — gold={g.get('gapCode') or 'UNKNOWN'}; "
            f"era={era_gap or 'ERA835_PENDING'} "
            f"(inbox empty / no paid ERA aggregate; empty != $0)"
        )

    return {
        "ready": ready,
        "reason": reason,
        "lanes": lanes,
        "goldReady": gold_ready,
        "eraReady": era_ready,
        "settlementMatrixReady": settlement_matrix_ready,
        "matrixHydrateFrom": "gold_csv_only",
        "note": (
            "ERA inbox/ingest enables structured remittance ops; "
            "settlement_matrix hydrates only from sd_insurance_payment_lines (Gold). "
            "Stale ERA fixtures with null paid do not count. empty != $0."
        ),
    }


def run_ops_10608_gold_era_settlement(
    *,
    db_path: Path | None = None,
    attempt_era_ingest: bool = True,
    attempt_gold_repair: bool = True,
) -> dict[str, Any]:
    """Assemble readiness; optionally repair Gold / ingest ERA inbox. Never OCR."""
    gold = gold_lane_status(db_path=db_path)
    era = era_lane_status()
    actions: dict[str, Any] = {"goldRepair": None, "eraIngest": None}

    if attempt_gold_repair and (
        gold.get("gapCode") == "GOLD_FILE_PRESENT_NOT_INGESTED"
        or (gold.get("candidates") and int(gold.get("paymentLines") or 0) == 0)
    ):
        try:
            actions["goldRepair"] = run_gold_payment_pipeline_repair(db_path=db_path)
            gold = gold_lane_status(db_path=db_path)
        except Exception as exc:  # noqa: BLE001
            actions["goldRepair"] = {"ok": False, "error": f"{type(exc).__name__}:{exc}"}

    if attempt_era_ingest and int(era.get("fileCount") or 0) > 0:
        try:
            from apex_era835_pack import ingest_era_inbox

            actions["eraIngest"] = ingest_era_inbox(limit=20, ensure_dirs=True)
            era = era_lane_status()
        except Exception as exc:  # noqa: BLE001
            actions["eraIngest"] = {"ok": False, "error": f"{type(exc).__name__}:{exc}"}

    readiness = settlement_hydration_readiness_gate(gold=gold, era=era)
    briefing = staff_briefing_10608()
    payload = {
        "ok": True,
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "checkedAt": _utc_now(),
        "gold": gold,
        "era": era,
        "readiness": readiness,
        "actions": actions,
        "ocrPolicy": STOP_OCR_POLICY,
        "playbook": {
            "gold": gold_drop_facilitation_playbook(),
            "eraDrop": r"C:\SoftDentFinancialExports\era\*.835|*.edi|*.x12",
            "stopOcr": True,
        },
        "staffBriefing": briefing,
        "acceptance": {
            "ready": readiness.get("ready"),
            "reason": readiness.get("reason"),
            "paymentLines": gold.get("paymentLines"),
            "matrixCells": gold.get("matrixCells"),
            "eraFileCount": era.get("fileCount"),
            "gapGold": gold.get("gapCode"),
            "gapEra": era.get("gapCode"),
        },
        "inventedGold": False,
        "emptyIsNotZero": True,
        "softDentWriteBack": False,
        "writesFromOcr": False,
        "ocrExpansionStopped": True,
        "honesty": (
            "STOP PWImages JPEG/PDF OCR for settlement. "
            "Gold CSV hydrates settlement_matrix; ERA is structured remittance lane. "
            "empty != $0."
        ),
        "honestyBanner": HONESTY_BANNER,
    }
    payload["export"] = export_hal10608_report(payload)
    return payload


def export_hal10608_report(payload: dict[str, Any], *, dest: Path | None = None) -> dict[str, Any]:
    out_dir = Path(dest) if dest else resolve_exports_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = date.today().isoformat()
    json_path = out_dir / f"gold_era_settlement_hal10608_{stamp}.json"
    md_path = out_dir / f"gold_era_settlement_hal10608_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    acc = payload.get("acceptance") or {}
    readiness = payload.get("readiness") or {}
    lines = [
        f"# HAL-10608 Gold ∪ ERA Settlement Hydration ({stamp})",
        "",
        f"**packageBuildId:** `{PACKAGE_BUILD_ID}`",
        f"**ready:** {readiness.get('ready')} — {readiness.get('reason')}",
        f"**gold gap:** `{acc.get('gapGold')}` · paymentLines={acc.get('paymentLines')} · matrixCells={acc.get('matrixCells')}",
        f"**era gap:** `{acc.get('gapEra')}` · fileCount={acc.get('eraFileCount')}",
        "",
        "## STOP OCR policy",
        "",
        f"- ocrExpansionStopped: `{STOP_OCR_POLICY.get('ocrExpansionStopped')}`",
        f"- writesFromOcr: `{STOP_OCR_POLICY.get('writesFromOcr')}`",
        f"- {STOP_OCR_POLICY.get('pdfNote')}",
        f"- {STOP_OCR_POLICY.get('patientJpgNote')}",
        "",
        "## Honesty",
        "",
        "- empty != $0",
        "- inventedGold=false",
        "- SoftDent write-back=false",
        f"- {HONESTY_BANNER}",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    result: dict[str, Any] = {"ok": True, "jsonPath": str(json_path), "mdPath": str(md_path)}
    try:
        from import_loader import softdent_import_dir

        inbox = softdent_import_dir()
        inbox.mkdir(parents=True, exist_ok=True)
        slim = {
            "ok": True,
            "def": DEF_ID,
            "packageBuildId": PACKAGE_BUILD_ID,
            "ready": readiness.get("ready"),
            "reason": readiness.get("reason"),
            "gapGold": acc.get("gapGold"),
            "gapEra": acc.get("gapEra"),
            "ocrExpansionStopped": True,
            "writesFromOcr": False,
            "fullReport": str(json_path),
            "honesty": "empty != $0; STOP PWImages OCR for settlement",
        }
        path = inbox / "softdent_gold_era_settlement_hal10608.json"
        path.write_text(json.dumps(slim, indent=2), encoding="utf-8")
        result["inboxPath"] = str(path)
    except Exception as exc:  # noqa: BLE001
        result["inboxError"] = f"{type(exc).__name__}:{exc}"
    return result


def gold_era_settlement_status(*, db_path: Path | None = None) -> dict[str, Any]:
    gold = gold_lane_status(db_path=db_path)
    era = era_lane_status()
    readiness = settlement_hydration_readiness_gate(gold=gold, era=era)
    return {
        "ok": True,
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "gold": gold,
        "era": era,
        "readiness": readiness,
        "ocrPolicy": STOP_OCR_POLICY,
        "inventedGold": False,
        "emptyIsNotZero": True,
        "softDentWriteBack": False,
        "writesFromOcr": False,
        "ocrExpansionStopped": True,
        "honestyBanner": HONESTY_BANNER,
        "checkedAt": _utc_now(),
    }


def format_hal10608_reply(result: dict[str, Any] | None = None) -> str:
    r = result if isinstance(result, dict) else gold_era_settlement_status()
    acc = r.get("acceptance") or r.get("readiness") or {}
    ready = acc.get("ready") if "ready" in acc else (r.get("readiness") or {}).get("ready")
    reason = acc.get("reason") or (r.get("readiness") or {}).get("reason")
    gold = r.get("gold") or {}
    era = r.get("era") or {}
    return (
        f"Gold/ERA settlement ({DEF_ID}): ready={ready} ({reason}). "
        f"gold={gold.get('gapCode')} lines={gold.get('paymentLines')}; "
        f"era={era.get('gapCode')} files={era.get('fileCount')}. "
        f"OCR expansion STOPPED. empty != $0."
    )


def gold_era_settlement_widget() -> dict[str, Any]:
    return {
        "id": "softdent-gold-era-settlement-hal10608",
        "title": "Gold ∪ ERA settlement hydration (HAL-10608)",
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "apiStatus": "/api/apex/gold-era-settlement/status",
        "apiRun": "/api/apex/gold-era-settlement/run",
        "honesty": "empty != $0; STOP PWImages JPEG/PDF OCR for settlement",
        "honestyBanner": HONESTY_BANNER,
        "prior": "Unifies HAL-10606 Gold facilitation + ERA inbox; no OCR expansion",
    }
