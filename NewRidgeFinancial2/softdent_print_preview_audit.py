"""HAL-10590 / OPS-10590 — SoftDent Print Preview visual-audit protocol.

Accept Print Preview as SoftDent financial truth when Excel/CSV is unavailable.
Record PHI-safe last-page aggregates only. Never invent gold payment lines.
Never SoftDent write-back. empty != $0 — gapCode stays GOLD_CSV_MISSING until
a real insurance payment-line file exists.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from softdent_gold_payment_pipeline import audit_gold_payment_pipeline
from softdent_treatment_planning import resolve_exports_dir

DEF_ID = "HAL-10590"
PACKAGE_BUILD_ID = "hal-10590"

REPORT_TYPES = (
    "InsuranceIncome",
    "ContractualPlanAnalysis",
    "PaymentAllocation",
    "InsurancePaymentDistribution",
)

SOURCE_TAG = "print_preview_visual"
AUDIT_LOG_NAME = "print_preview_audit_log.jsonl"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def print_preview_audit_playbook() -> dict[str, Any]:
    return {
        "when": "When Print Preview is the only SoftDent option (Excel unavailable)",
        "softDentMenu": (
            "Reports → Practice Management → Insurance Reports → Insurance Income"
        ),
        "f10": "F10 r m i i",
        "output": "Print Preview only — never Excel (unavailable), never Printer",
        "pages": (
            "Enter → PageDown/Next through pages for detail → LAST page for "
            "Total Insurance Income (page 1 alone is incomplete)"
        ),
        "record": (
            "Enter PHI-safe aggregate last-page total into Print Preview Audit widget. "
            "This does NOT create sd_insurance_payment_lines."
        ),
        "honesty": (
            "Visual audit only (source_tag=print_preview_visual). "
            "gapCode remains GOLD_CSV_MISSING; paymentLines stays 0; empty != $0."
        ),
        "never": (
            "SoftDent write-back; invent gold lines from DaySheet/ledger; "
            "capture patient names/account numbers/procedure dates; coerce empty to $0.00"
        ),
    }


def _audit_log_path(*, dest: Path | None = None) -> Path:
    root = Path(dest) if dest else resolve_exports_dir()
    root.mkdir(parents=True, exist_ok=True)
    return root / AUDIT_LOG_NAME


def validate_print_preview_audit_record(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate PHI-safe visual audit record. Does not invent dollars."""
    out: dict[str, Any] = {
        "ok": False,
        "def": DEF_ID,
        "errors": [],
        "record": None,
        "triggersGoldIngest": False,
    }
    report_type = str(raw.get("reportType") or raw.get("report_type") or "").strip()
    if report_type not in REPORT_TYPES:
        out["errors"].append(
            f"reportType must be one of {REPORT_TYPES} (got {report_type!r})"
        )

    total_raw = raw.get("lastPageAggregateTotal")
    if total_raw is None:
        total_raw = raw.get("last_page_aggregate_total")
    total: float | None
    try:
        if total_raw is None or str(total_raw).strip() == "":
            total = None
            out["errors"].append("lastPageAggregateTotal required (empty != $0)")
        else:
            total = float(total_raw)
            if total < 0:
                out["errors"].append("lastPageAggregateTotal must be >= 0")
            # Explicit zero is allowed only when operator saw $0.00 on last page
            # Missing/null is rejected above (empty != $0)
    except (TypeError, ValueError):
        total = None
        out["errors"].append("lastPageAggregateTotal must be a number")

    page_count_raw = raw.get("pageCount", raw.get("page_count"))
    page_count: int | None = None
    if page_count_raw is not None and str(page_count_raw).strip() != "":
        try:
            page_count = int(page_count_raw)
            if page_count < 1:
                out["errors"].append("pageCount must be >= 1 when provided")
        except (TypeError, ValueError):
            out["errors"].append("pageCount must be an integer")

    # PHI guard: reject obvious patient/account payloads
    carrier = str(raw.get("carrierBreakdownIfVisible") or raw.get("carrier_breakdown_if_visible") or "").strip()
    notes = str(raw.get("notes") or "").strip()
    combined = f"{carrier} {notes}".lower()
    if re.search(r"\b(patient|account\s*#|acct\s*#|ssn|dob|date of birth)\b", combined):
        out["errors"].append(
            "PHI-safe aggregates only — do not record patient/account/DOB detail"
        )

    date_range = str(raw.get("dateRange") or raw.get("date_range") or "").strip()
    operator_id = str(raw.get("operatorId") or raw.get("operator_id") or "staff").strip() or "staff"

    if out["errors"]:
        return out

    record = {
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "reportType": report_type,
        "dateRange": date_range or None,
        "lastPageAggregateTotal": total,
        "carrierBreakdownIfVisible": carrier or None,
        "pageCount": page_count,
        "previewTimestamp": str(raw.get("previewTimestamp") or raw.get("preview_timestamp") or _utc_now()),
        "operatorId": operator_id,
        "sourceTag": SOURCE_TAG,
        "notes": notes or None,
        "recordedAt": _utc_now(),
        "honesty": (
            "print_preview_visual audit only — does not create gold payment lines; "
            "gapCode remains GOLD_CSV_MISSING until a real CSV exists; empty != $0"
        ),
        "triggersGoldIngest": False,
    }
    out.update({"ok": True, "record": record, "errors": []})
    return out


def append_print_preview_audit(
    raw: dict[str, Any],
    *,
    dest: Path | None = None,
) -> dict[str, Any]:
    """Append validated visual-audit record to JSONL. Never triggers gold ingest."""
    validated = validate_print_preview_audit_record(raw)
    result: dict[str, Any] = {
        "ok": False,
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "triggersGoldIngest": False,
        "paymentLinesUnchanged": True,
    }
    if not validated.get("ok") or not validated.get("record"):
        result["errors"] = validated.get("errors") or ["validation_failed"]
        return result

    path = _audit_log_path(dest=dest)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(validated["record"], ensure_ascii=True) + "\n")

    gold = audit_gold_payment_pipeline()
    result.update(
        {
            "ok": True,
            "record": validated["record"],
            "logPath": str(path),
            "gapCode": gold.get("gapCode"),
            "paymentLines": int(gold.get("paymentLines") or 0),
            "visualAuditAvailable": True,
            "visualAuditLastPageTotal": validated["record"]["lastPageAggregateTotal"],
            "honesty": validated["record"]["honesty"],
        }
    )
    return result


def list_print_preview_audits(
    *,
    dest: Path | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    path = _audit_log_path(dest=dest)
    rows: list[dict[str, Any]] = []
    if path.is_file():
        lines = path.read_text(encoding="utf-8").splitlines()
        for line in lines[-max(1, int(limit)) :]:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    gold = audit_gold_payment_pipeline()
    latest = rows[-1] if rows else None
    return {
        "ok": True,
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "logPath": str(path),
        "count": len(rows),
        "rows": rows,
        "latest": latest,
        "visualAuditAvailable": bool(latest),
        "visualAuditLastPageTotal": (latest or {}).get("lastPageAggregateTotal"),
        "gapCode": gold.get("gapCode"),
        "paymentLines": int(gold.get("paymentLines") or 0),
        "triggersGoldIngest": False,
        "honesty": (
            "Visual audit log is not gold payment-line ingest. "
            f"gapCode={gold.get('gapCode')}; paymentLines={gold.get('paymentLines')}; empty != $0"
        ),
        "playbook": print_preview_audit_playbook(),
    }


def run_ops_10590_print_preview_audit(
    raw: dict[str, Any] | None = None,
    *,
    dest: Path | None = None,
) -> dict[str, Any]:
    """OPS runner: optional record append + status snapshot (no SoftDent write-back)."""
    appended = None
    if isinstance(raw, dict) and raw:
        appended = append_print_preview_audit(raw, dest=dest)
    status = list_print_preview_audits(dest=dest, limit=20)
    gold = audit_gold_payment_pipeline()
    return {
        "ok": True if appended is None else bool(appended.get("ok")),
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "appended": appended,
        "status": status,
        "gapCode": gold.get("gapCode"),
        "paymentLines": int(gold.get("paymentLines") or 0),
        "visualAuditAvailable": bool(status.get("visualAuditAvailable")),
        "visualAuditLastPageTotal": status.get("visualAuditLastPageTotal"),
        "triggersGoldIngest": False,
        "playbook": print_preview_audit_playbook(),
        "honesty": status.get("honesty"),
    }


def format_print_preview_audit_reply(status: dict[str, Any] | None = None) -> str:
    from ui_honesty_policy import SOURCE_PRINT_PREVIEW_VISUAL, enforce_empty_not_zero

    st = status if isinstance(status, dict) else list_print_preview_audits()
    total = st.get("visualAuditLastPageTotal")
    total_disp = enforce_empty_not_zero(total, source_tag=SOURCE_PRINT_PREVIEW_VISUAL)
    total_txt = str(total_disp.get("display") or "—")
    if total_disp.get("badge") == "visual" and total_disp.get("showDollars"):
        total_txt = f"[visual] {total_txt}"
    return (
        f"Print Preview visual audit ({DEF_ID}): available={st.get('visualAuditAvailable')}; "
        f"lastPageTotal={total_txt}; records={st.get('count')}; "
        f"gapCode={st.get('gapCode')}; paymentLines={st.get('paymentLines')} "
        f"(gold money display={'—' if int(st.get('paymentLines') or 0) == 0 else 'lines present'}). "
        "Visual audit only — does not create gold lines. "
        f"Playbook: {print_preview_audit_playbook()['f10']} → Print Preview → "
        "PageDown → last page. empty != $0."
    )


def print_preview_audit_widget() -> dict[str, Any]:
    from ui_honesty_policy import SOURCE_PRINT_PREVIEW_VISUAL, enforce_empty_not_zero

    st = list_print_preview_audits(limit=5)
    available = bool(st.get("visualAuditAvailable"))
    total = st.get("visualAuditLastPageTotal")
    total_honesty = enforce_empty_not_zero(total, source_tag=SOURCE_PRINT_PREVIEW_VISUAL)
    if available and total_honesty.get("showDollars"):
        status, tone = "ok", "ok"
        message = (
            f"Visual audit recorded · last-page total [visual] {total_honesty.get('display')} · "
            f"gap still {st.get('gapCode')} (not gold lines; gold=—)"
        )
    else:
        status, tone = "empty", "warn"
        message = (
            "No Print Preview visual audit yet — Insurance Income → Print Preview → "
            "PageDown → last page → record aggregate (empty != $0; gold=— not $0.00)"
        )
    return {
        "id": "softdent-print-preview-audit",
        "type": "status",
        "label": "Print Preview Visual Audit (HAL-10590)",
        "size": "full",
        "status": status,
        "tone": tone,
        "message": message,
        "hint": print_preview_audit_playbook()["pages"],
        "playbook": print_preview_audit_playbook(),
        "visualAuditAvailable": available,
        "visualAuditLastPageTotal": total,
        "visualAuditLastPageTotalDisplay": total_honesty.get("display"),
        "visualBadge": total_honesty.get("badge"),
        "visualTooltip": total_honesty.get("tooltip"),
        "gapCode": st.get("gapCode"),
        "paymentLines": st.get("paymentLines"),
        "goldPaymentLinesDisplay": "—" if int(st.get("paymentLines") or 0) == 0 else str(st.get("paymentLines")),
        "confirmation": (
            "This is a visual audit only; no payment lines will be created"
        ),
        "halChips": [
            {"label": "Print Preview audit status", "query": "print preview audit status"},
            {
                "label": "How do I record Insurance Income Print Preview?",
                "query": "How do I record SoftDent Insurance Income Print Preview last page total?",
            },
        ],
        "honesty": st.get("honesty"),
        "emptyIsNotZero": True,
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "triggersGoldIngest": False,
    }


if __name__ == "__main__":
    print(json.dumps(run_ops_10590_print_preview_audit(), indent=2, default=str)[:4000])
