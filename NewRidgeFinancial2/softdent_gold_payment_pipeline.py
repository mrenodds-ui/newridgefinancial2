"""HAL-10588 — Gold insurance payment-line pipeline audit & repair.

Moonshot Expert SE NEXT: investigate ``sd_insurance_payment_lines=0``, harden
ingest (Insurance Payment Analysis CSV + related drops), cross-check exact usable
spine cells, couple BUILD_ID.

Honesty: empty != $0. Missing SoftDent Insurance Payment Analysis CSV is the
root cause when no file is on disk — do not invent gold lines from ledger spine.
No SoftDent write-back.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from softdent_treatment_planning import (
    _PAYMENT_GLOBS,
    find_newest_csv,
    resolve_analytics_db,
    resolve_exports_dir,
    run_treatment_planning_ingest,
    _search_roots,
)

DEF_ID = "HAL-10588"
PACKAGE_BUILD_ID = "hal-10588"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (name,),
    ).fetchone()
    return bool(row)


def _count(conn: sqlite3.Connection, table: str) -> int:
    if not _table_exists(conn, table):
        return 0
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] or 0)
    except sqlite3.Error:
        return 0


def find_gold_payment_candidates(*, search_dir: Path | None = None) -> list[dict[str, Any]]:
    """Recursive hunt for Insurance Payment Analysis / related drops."""
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for root in _search_roots(search_dir):
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            name = path.name.lower()
            if not any(
                token in name
                for token in (
                    "insurance_payment",
                    "insurancepayment",
                    "payment_analysis",
                    "paymentanalysis",
                    "inspay",
                    "ins_pay",
                )
            ):
                continue
            if path.suffix.lower() not in {".csv", ".xls", ".xlsx"}:
                continue
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            found.append(
                {
                    "path": str(path),
                    "name": path.name,
                    "suffix": path.suffix.lower(),
                    "bytes": path.stat().st_size,
                    "mtime": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
                }
            )
    found.sort(key=lambda r: r.get("mtime") or "", reverse=True)
    return found


def audit_gold_payment_pipeline(
    *,
    db_path: Path | None = None,
    search_dir: Path | None = None,
) -> dict[str, Any]:
    """Diagnose why gold payment lines are empty (or not)."""
    target = Path(db_path) if db_path else resolve_analytics_db()
    out: dict[str, Any] = {
        "ok": True,
        "def": DEF_ID,
        "checkedAt": _utc_now(),
        "dbPath": str(target) if target else None,
        "gapCode": None,
        "rootCause": None,
        "paymentLines": 0,
        "treatmentEstimates": 0,
        "candidates": [],
        "searchRoots": [str(r) for r in _search_roots(search_dir)],
        "playbook": {
            "softDentMenu": "Reports → Insurance → Insurance Payment Analysis",
            "params": "Last 24 months (or max), all carriers, include write-offs",
            "format": "CSV (Excel often unavailable — CSV preferred)",
            "saveAs": r"C:\SoftDentFinancialExports\insurance_payments_YYYYMMDD.csv",
            "optional": r"procedure_codes_YYYYMMDD.csv from Procedure Code Listing",
            "then": "Sync / run_gold_payment_pipeline_repair — empty != $0 until file lands",
        },
        "honesty": "empty != $0; missing CSV is not zero insurance payments",
    }
    if not target or not target.is_file():
        out["ok"] = False
        out["gapCode"] = "ANALYTICS_DB_MISSING"
        out["rootCause"] = "softdent_financial_analytics.db missing"
        return out

    conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        out["paymentLines"] = _count(conn, "sd_insurance_payment_lines")
        out["treatmentEstimates"] = _count(conn, "treatment_planning_estimates")
        out["era835Payments"] = _count(conn, "era_835_payments")
        out["sdPayments"] = _count(conn, "sd_payments")
    finally:
        conn.close()

    candidates = find_gold_payment_candidates(search_dir=search_dir)
    out["candidates"] = candidates
    newest_csv = find_newest_csv(_PAYMENT_GLOBS, search_dir=search_dir)
    out["newestPaymentCsv"] = str(newest_csv) if newest_csv else None

    if out["paymentLines"] > 0:
        out["gapCode"] = "GOLD_OK"
        out["rootCause"] = f"Gold path populated ({out['paymentLines']} lines)"
    elif candidates:
        out["gapCode"] = "GOLD_FILE_PRESENT_NOT_INGESTED"
        out["rootCause"] = (
            "Payment-analysis file(s) found on disk but sd_insurance_payment_lines still 0 — "
            "run ingest/repair (possible schema/header mismatch)."
        )
    else:
        out["gapCode"] = "GOLD_CSV_MISSING"
        out["rootCause"] = (
            "No SoftDent Insurance Payment Analysis CSV/XLS on disk under export roots. "
            "ETL ingest path is ready; SoftDent export has not been dropped. "
            "DaySheet/sd_payments are not ADA×InsCo gold lines. empty != $0."
        )
    return out


def validate_exact_usable_cells(*, db_path: Path | None = None) -> dict[str, Any]:
    """Cross-check exact usable spine cells for internal consistency (remittance optional)."""
    target = Path(db_path) if db_path else resolve_analytics_db()
    out: dict[str, Any] = {
        "ok": False,
        "def": DEF_ID,
        "checkedAt": _utc_now(),
        "cellsChecked": 0,
        "passCount": 0,
        "flagCount": 0,
        "remittanceAvailable": False,
        "method": (
            "Spine-consistency only when remittance/gold lines absent: "
            "flag if paid_median+write_off_median > 1.35*billed_avg or negative."
        ),
        "rows": [],
        "honesty": "Not EOB remittance truth until gold/ERA lines exist. empty != $0.",
    }
    if not target or not target.is_file():
        out["error"] = "analytics_db_missing"
        return out

    conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        if not _table_exists(conn, "insco_ada_probabilistic_estimates"):
            out["error"] = "spine_table_missing"
            return out
        gold_n = _count(conn, "sd_insurance_payment_lines")
        out["remittanceAvailable"] = gold_n > 0
        rows = conn.execute(
            """
            SELECT insurance_company, ada_code, sample_size, credibility,
                   paid_median, write_off_median, billed_avg
            FROM insco_ada_probabilistic_estimates
            WHERE tier='exact' AND credibility IN ('high','usable')
            ORDER BY sample_size DESC
            """
        ).fetchall()
    finally:
        conn.close()

    checked = []
    passes = 0
    flags = 0
    for r in rows:
        carrier, ada, n, cred, paid, wo, billed = r
        paid_f = float(paid) if paid is not None else None
        wo_f = float(wo) if wo is not None else None
        billed_f = float(billed) if billed is not None else None
        status = "pass"
        reasons: list[str] = []
        if paid_f is not None and paid_f < 0:
            status = "flag"
            reasons.append("negative_paid")
        if wo_f is not None and wo_f < 0:
            status = "flag"
            reasons.append("negative_writeoff")
        if billed_f is not None and billed_f > 0 and paid_f is not None and wo_f is not None:
            if (paid_f + wo_f) > billed_f * 1.35:
                status = "flag"
                reasons.append("paid_plus_wo_exceeds_billed_1_35x")
        if status == "pass":
            passes += 1
        else:
            flags += 1
        checked.append(
            {
                "insuranceCompany": carrier,
                "adaCode": ada,
                "sampleSize": n,
                "credibility": cred,
                "paidMedian": paid_f,
                "writeOffMedian": wo_f,
                "billedAvg": billed_f,
                "status": status,
                "reasons": reasons,
                "goldRemittanceCompared": False,
            }
        )
    out.update(
        {
            "ok": True,
            "cellsChecked": len(checked),
            "passCount": passes,
            "flagCount": flags,
            "rows": checked,
        }
    )
    return out


def export_gold_pipeline_report(
    *,
    db_path: Path | None = None,
    dest: Path | None = None,
    search_dir: Path | None = None,
) -> dict[str, Any]:
    out_dir = Path(dest) if dest else resolve_exports_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    audit = audit_gold_payment_pipeline(db_path=db_path, search_dir=search_dir)
    validation = validate_exact_usable_cells(db_path=db_path)
    stamp = date.today().isoformat()
    payload = {
        "ok": True,
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "checkedAt": _utc_now(),
        "audit": audit,
        "exactUsableValidation": validation,
    }
    json_path = out_dir / f"gold_payment_pipeline_report_{stamp}.json"
    md_path = out_dir / f"gold_payment_pipeline_report_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        f"# Gold Payment Pipeline Audit ({stamp}) — {DEF_ID}",
        "",
        f"**gapCode:** `{audit.get('gapCode')}`",
        f"**rootCause:** {audit.get('rootCause')}",
        f"**paymentLines:** {audit.get('paymentLines')} · estimates: {audit.get('treatmentEstimates')}",
        f"**candidates on disk:** {len(audit.get('candidates') or [])}",
        "",
        "## Playbook (SoftDent)",
        "",
        f"- {audit.get('playbook', {}).get('softDentMenu')}",
        f"- Save: `{audit.get('playbook', {}).get('saveAs')}`",
        f"- Then Sync. empty != $0 until CSV lands.",
        "",
        "## Exact usable spine validation",
        "",
        f"Checked **{validation.get('cellsChecked')}** · pass **{validation.get('passCount')}** · "
        f"flag **{validation.get('flagCount')}** · remittanceAvailable={validation.get('remittanceAvailable')}",
        "",
        "| Carrier | ADA | n | Paid$ | WO$ | Status |",
        "|---|---|---:|---:|---:|---|",
    ]
    for row in (validation.get("rows") or [])[:50]:
        lines.append(
            f"| {row['insuranceCompany']} | {row['adaCode']} | {row['sampleSize']} | "
            f"{row.get('paidMedian')} | {row.get('writeOffMedian')} | {row['status']} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = {
        "ok": True,
        "jsonPath": str(json_path),
        "mdPath": str(md_path),
        "gapCode": audit.get("gapCode"),
        "paymentLines": audit.get("paymentLines"),
        "exactChecked": validation.get("cellsChecked"),
        "exactPass": validation.get("passCount"),
        "exactFlag": validation.get("flagCount"),
    }
    try:
        from import_loader import softdent_import_dir

        inbox = softdent_import_dir()
        inbox.mkdir(parents=True, exist_ok=True)
        slim = {
            "ok": True,
            "def": DEF_ID,
            "gapCode": audit.get("gapCode"),
            "rootCause": audit.get("rootCause"),
            "paymentLines": audit.get("paymentLines"),
            "playbook": audit.get("playbook"),
            "fullReport": str(json_path),
            "honesty": audit.get("honesty"),
        }
        path = inbox / "softdent_gold_payment_pipeline.json"
        path.write_text(json.dumps(slim, indent=2), encoding="utf-8")
        result["inboxPath"] = str(path)
    except Exception as exc:  # noqa: BLE001
        result["inboxError"] = f"{type(exc).__name__}:{exc}"
    return result


def run_gold_payment_pipeline_repair(
    *,
    db_path: Path | None = None,
    search_dir: Path | None = None,
) -> dict[str, Any]:
    """Attempt gold ingest, then audit + exact-cell validation report."""
    ingest = run_treatment_planning_ingest(db_path=db_path, search_dir=search_dir)
    # If candidate files exist but globs missed them, try first CSV candidate
    audit_pre = audit_gold_payment_pipeline(db_path=db_path, search_dir=search_dir)
    if int(ingest.get("paymentLines") or 0) == 0:
        for cand in audit_pre.get("candidates") or []:
            path = Path(str(cand.get("path") or ""))
            if path.is_file() and path.suffix.lower() == ".csv":
                from softdent_treatment_planning import (
                    ingest_insurance_payment_csv,
                    rebuild_treatment_planning_estimates,
                )

                target = Path(db_path) if db_path else resolve_analytics_db()
                if target and target.is_file():
                    conn = sqlite3.connect(str(target))
                    try:
                        n = ingest_insurance_payment_csv(path, conn)
                        est = rebuild_treatment_planning_estimates(conn) if n else 0
                        if n:
                            try:
                                from softdent_settlement_matrix import hydrate_settlement_matrix

                                hydrate_settlement_matrix(db_path=target, conn=conn)
                            except Exception:
                                pass
                        conn.commit()
                        ingest["paymentLines"] = n
                        ingest["estimates"] = est
                        ingest["paymentFile"] = str(path)
                        ingest["ok"] = True
                        if n:
                            ingest.setdefault("warnings", []).append(
                                f"Ingested via candidate scan: {path.name}"
                            )
                    except Exception as exc:  # noqa: BLE001
                        ingest.setdefault("warnings", []).append(
                            f"Candidate ingest failed {path.name}: {type(exc).__name__}:{exc}"
                        )
                    finally:
                        conn.close()
                if int(ingest.get("paymentLines") or 0) > 0:
                    break

    # HAL-10605: always attempt hydrate (clears matrix honestly when gold missing)
    try:
        from softdent_settlement_matrix import hydrate_settlement_matrix

        matrix = hydrate_settlement_matrix(db_path=db_path)
    except Exception as exc:  # noqa: BLE001
        matrix = {"ok": False, "error": f"{type(exc).__name__}:{exc}"}

    report = export_gold_pipeline_report(
        db_path=db_path, search_dir=search_dir
    )
    audit = audit_gold_payment_pipeline(db_path=db_path, search_dir=search_dir)
    return {
        "ok": True,
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "ingest": ingest,
        "audit": audit,
        "export": report,
        "settlementMatrix": matrix,
    }


def format_gold_pipeline_reply(audit: dict[str, Any] | None = None) -> str:
    st = audit if isinstance(audit, dict) else audit_gold_payment_pipeline()
    return (
        f"Gold payment pipeline ({DEF_ID}): gapCode={st.get('gapCode')}; "
        f"lines={st.get('paymentLines')}; estimates={st.get('treatmentEstimates')}; "
        f"candidates={len(st.get('candidates') or [])}. "
        f"Root cause: {st.get('rootCause')} "
        f"Playbook: SoftDent {st.get('playbook', {}).get('softDentMenu')} → "
        f"{st.get('playbook', {}).get('saveAs')}. empty != $0."
    )


def gold_payment_pipeline_widget() -> dict[str, Any]:
    audit = audit_gold_payment_pipeline()
    lines = int(audit.get("paymentLines") or 0)
    gap = str(audit.get("gapCode") or "")
    play = audit.get("playbook") if isinstance(audit.get("playbook"), dict) else {}
    if lines > 0:
        status, tone = "ok", "ok"
        message = f"Gold payment lines={lines} · estimates={audit.get('treatmentEstimates')}"
    elif gap == "GOLD_FILE_PRESENT_NOT_INGESTED":
        status, tone = "warn", "warn"
        message = "Payment file on disk but not ingested — run Sync / gold pipeline repair"
    else:
        # SoftDent pull playbook is known (v19 often Print Preview only) — surface as
        # warn with data, not blank empty. paymentLines stay 0 until real CSV lands.
        status, tone = "warn", "warn"
        menu = play.get("softDentMenu") or (
            "Reports → Practice Management → Insurance Reports → Insurance Income"
        )
        save_as = play.get("saveAs") or r"C:\SoftDentFinancialExports\insurance_payments_YYYYMMDD.csv"
        message = (
            f"SoftDent pull ready: {menu} → Excel if offered else Print Preview "
            f"(never Printer). Drop CSV to {save_as}. "
            f"gapCode={gap or 'GOLD_CSV_MISSING'} · paymentLines=0 (empty ≠ $0; display=—)"
        )
    return {
        "id": "softdent-gold-payment-pipeline",
        "type": "status",
        "label": "Gold Payment Pipeline (HAL-10588)",
        "size": "full",
        "status": status,
        "tone": tone,
        "message": message,
        "hint": str(audit.get("rootCause") or ""),
        "gapCode": gap,
        "paymentLines": lines,
        "goldPaymentLinesDisplay": "—" if lines == 0 else str(lines),
        "emptyIsNotZero": True,
        "playbook": audit.get("playbook"),
        "halChips": [
            {"label": "Gold payment pipeline status", "query": "gold payment pipeline status"},
            {
                "label": "How do I export Insurance Payment Analysis?",
                "query": "How do I export SoftDent Insurance Payment Analysis CSV?",
            },
        ],
        "honesty": audit.get("honesty"),
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "honestyDef": "HAL-10591",
    }


if __name__ == "__main__":
    print(json.dumps(run_gold_payment_pipeline_repair(), indent=2, default=str)[:5000])
