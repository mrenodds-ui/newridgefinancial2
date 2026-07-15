"""HAL-10580 — Outstanding Claims by Carrier Bridge.

Joins SoftDent Account Aging (period AR truth) with sd_claims (ops detail).
Honesty: empty != $0; unnamed payer stays unnamed (no invented carriers);
NULL balance is unbilled/unknown — never coerced to $0.
No SoftDent write-back.
"""

from __future__ import annotations

import csv
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPORTS = Path(r"C:\SoftDentReportExports")
DEFAULT_FINANCIAL = Path(r"C:\SoftDentFinancialExports")

GAP_OK = "OK"
GAP_AGING_MISSING = "AGING_EXPORT_MISSING"
GAP_CLAIMS_MISSING = "SD_CLAIMS_MISSING"
GAP_PAYER_ATTRIBUTION = "CLAIMS_PAYER_ATTRIBUTION_REQUIRED"
GAP_RECONCILE_MISMATCH = "CLAIMS_AR_RECONCILE_MISMATCH"

_GENERIC_PAYERS = {"", "insurance", "unknown", "n/a", "-", "—", "(blank)", "(unnamed)"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_money(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).replace("$", "").replace(",", "").strip()
    if not raw or raw in {".", "-", "—"}:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _is_generic_payer(value: str | None) -> bool:
    return str(value or "").strip().lower() in _GENERIC_PAYERS


def resolve_account_transactions_db(db_path: Path | str | None = None) -> Path | None:
    """Alias for analytics DB that holds sd_account_transactions / sd_claims (hal-10580)."""
    if db_path:
        target = Path(db_path)
        return target if target.is_file() else None
    try:
        from softdent_transaction_extract import resolve_analytics_db

        return resolve_analytics_db()
    except Exception:
        cand = DEFAULT_FINANCIAL / "softdent_financial_analytics.db"
        return cand if cand.is_file() else None


def ensure_sd_claims_bridge_columns(conn: sqlite3.Connection) -> None:
    """Add optional total_fee / balance columns; NULL balance = unknown (not $0)."""
    cols = {str(r[1]) for r in conn.execute("PRAGMA table_info(sd_claims)").fetchall()}
    if "total_fee" not in cols:
        conn.execute("ALTER TABLE sd_claims ADD COLUMN total_fee REAL")
    if "balance" not in cols:
        conn.execute("ALTER TABLE sd_claims ADD COLUMN balance REAL")
    conn.commit()
    # Backfill total_fee from claim_amount when total_fee is NULL (not inventing balance).
    try:
        conn.execute(
            """
            UPDATE sd_claims
            SET total_fee = claim_amount
            WHERE total_fee IS NULL AND claim_amount IS NOT NULL
            """
        )
        conn.commit()
    except sqlite3.Error:
        pass


def find_account_aging_export(*, roots: list[Path] | None = None) -> Path | None:
    """Locate SoftDent Account Aging export (not NR2's derived softdent_ar_aging.csv)."""
    search_roots = roots or [
        DEFAULT_EXPORTS,
        DEFAULT_FINANCIAL,
    ]
    try:
        from import_loader import softdent_import_dir

        search_roots.append(softdent_import_dir())
    except Exception:
        pass
    # Exact SoftDent export names first; globs last. Never treat NR2 AR buckets as aging truth.
    exact_patterns = (
        "account_aging.csv",
        "account_aging.xls",
        "account_aging.xlsx",
        "AGE*.CSV",
        "AGE*.XLS",
        "AGE*.XLSX",
    )
    loose_patterns = (
        "*aging*.csv",
        "*Aging*.csv",
    )
    skip_names = {"softdent_ar_aging.csv", "softdent_ar_aging.jsonl"}

    def _collect(patterns: tuple[str, ...]) -> list[Path]:
        found: list[Path] = []
        for root in search_roots:
            if not root or not Path(root).is_dir():
                continue
            root_p = Path(root)
            for pat in patterns:
                for p in root_p.glob(pat):
                    if p.is_file() and p.name.lower() not in skip_names:
                        found.append(p)
        return found

    candidates = _collect(exact_patterns)
    if not candidates:
        candidates = _collect(loose_patterns)
    if not candidates:
        return None
    # Prefer a file that actually parses as SoftDent Account Aging; else newest exact/loose hit.
    parsed_ok: list[Path] = []
    for cand in candidates:
        try:
            if parse_account_aging_export(cand).get("ok"):
                parsed_ok.append(cand)
        except Exception:
            continue
    pool = parsed_ok or candidates
    return max(pool, key=lambda p: p.stat().st_mtime)


def parse_account_aging_export(path: Path | str) -> dict[str, Any]:
    """Parse SoftDent Account Aging CSV/Excel-ish CSV into AR totals (empty ≠ $0)."""
    target = Path(path)
    result: dict[str, Any] = {
        "ok": False,
        "path": str(target),
        "sourceKind": "account_aging",
        "accountCount": 0,
        "balanceTotal": None,
        "insAmtTotal": None,
        "amtDueTotal": None,
        "outstandingInsuranceTotal": None,
        "trueReceivablesTotal": None,
        "buckets": {},
        "honesty": "empty != $0",
    }
    if not target.is_file():
        result["error"] = "missing"
        return result

    text = target.read_text(encoding="utf-8-sig", errors="replace")
    lines = text.splitlines()

    # Footer labels (SoftDent Account Aging Report)
    for line in lines:
        low = line.lower()
        if "outstanding insurance breakdown" in low:
            continue
        m = re.search(r",\s*Total\s*,\s*\"?\$?([\d,]+\.?\d*)\"?", line, re.I)
        if m and "outstanding" in "\n".join(lines[max(0, lines.index(line) - 8) : lines.index(line) + 1]).lower():
            # handled below via sequential scan
            pass
        if ",Total (Net 30)," in line or "total (net 30)" in low:
            amt = _parse_money(line.split(",")[2] if len(line.split(",")) > 2 else None)
            if amt is not None:
                result["trueReceivablesTotal"] = amt
        if "true receivables" in low:
            # prior numeric cell often on same or previous money line
            pass
        if re.search(r",\s*Total outstanding income,", line, re.I):
            parts = next(csv.reader([line]))
            for i, cell in enumerate(parts):
                if "total outstanding income" in str(cell).lower() and i + 1 < len(parts):
                    result["trueReceivablesTotal"] = _parse_money(parts[i + 1]) or result.get(
                        "trueReceivablesTotal"
                    )

    # Outstanding Insurance Breakdown → Total row
    in_ins = False
    for line in lines:
        low = line.lower()
        if "outstanding insurance breakdown" in low:
            in_ins = True
            continue
        if in_ins and re.match(r",\s*Total,", line, re.I):
            parts = next(csv.reader([line]))
            # ,Total,$0.00,100%,
            for i, cell in enumerate(parts):
                if str(cell).strip().lower() == "total" and i + 1 < len(parts):
                    result["outstandingInsuranceTotal"] = _parse_money(parts[i + 1])
                    break
            in_ins = False

    # Detail rows under Acct ID header
    reader = csv.reader(lines)
    header: list[str] | None = None
    accounts = 0
    bal_sum = 0.0
    ins_sum = 0.0
    due_sum = 0.0
    bal_seen = False
    ins_seen = False
    due_seen = False
    for row in reader:
        if not row:
            continue
        cells = [str(c).strip() for c in row]
        joined = ",".join(cells).lower()
        if cells and cells[0].lower() == "acct id":
            header = [c.lower() for c in cells]
            continue
        if not header:
            continue
        if not cells[0] or not re.match(r"^\d+", cells[0]):
            continue
        def _col(name: str) -> Any:
            try:
                idx = header.index(name)
            except ValueError:
                return None
            return cells[idx] if idx < len(cells) else None

        bal = _parse_money(_col("balance"))
        ins = _parse_money(_col("ins amt"))
        due = _parse_money(_col("amt due"))
        accounts += 1
        if bal is not None:
            bal_sum += bal
            bal_seen = True
        if ins is not None:
            ins_sum += ins
            ins_seen = True
        if due is not None:
            due_sum += due
            due_seen = True

    result["accountCount"] = accounts
    if bal_seen:
        result["balanceTotal"] = round(bal_sum, 2)
    if ins_seen:
        result["insAmtTotal"] = round(ins_sum, 2)
    if due_seen:
        result["amtDueTotal"] = round(due_sum, 2)
    if result.get("trueReceivablesTotal") is None and bal_seen:
        result["trueReceivablesTotal"] = result["balanceTotal"]
    # SoftDent printed Outstanding Insurance Total takes precedence for insurance AR.
    if result.get("outstandingInsuranceTotal") is None and ins_seen:
        result["outstandingInsuranceTotal"] = result["insAmtTotal"]
    result["ok"] = accounts > 0 or result.get("trueReceivablesTotal") is not None
    return result


def aggregate_sd_claims_by_carrier(
    *,
    db_path: Path | str | None = None,
    outstanding_only: bool = True,
) -> dict[str, Any]:
    """Group sd_claims by payer. Generic payers stay in an unnamed bucket (not invented)."""
    target = resolve_account_transactions_db(db_path)
    out: dict[str, Any] = {
        "ok": False,
        "dbPath": str(target) if target else None,
        "claimCount": 0,
        "namedPayerClaimCount": 0,
        "unnamedPayerClaimCount": 0,
        "billedTotal": None,
        "balanceTotal": None,
        "unbilledCount": 0,
        "byCarrier": [],
        "honesty": "empty != $0; unnamed payer not invented",
    }
    if not target or not target.is_file():
        out["error"] = "analytics_db_missing"
        return out
    conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        tables = {
            str(r[0])
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "sd_claims" not in tables:
            out["error"] = "sd_claims_missing"
            return out
        cols = {str(r[1]) for r in conn.execute("PRAGMA table_info(sd_claims)").fetchall()}
        has_balance = "balance" in cols
        has_fee = "total_fee" in cols
        fee_expr = "COALESCE(total_fee, claim_amount)" if has_fee else "claim_amount"
        bal_expr = "balance" if has_balance else "NULL"
        status_filter = ""
        if outstanding_only:
            status_filter = (
                " AND ("
                "claim_status IS NULL OR TRIM(claim_status)='' OR "
                "lower(claim_status) NOT IN ('paid','closed','complete','completed','denied-final')"
                ")"
            )
        rows = conn.execute(
            f"""
            SELECT
              COALESCE(NULLIF(TRIM(payer), ''), '(unnamed)'),
              COUNT(*),
              SUM({fee_expr}),
              SUM({bal_expr}),
              SUM(CASE WHEN {bal_expr} IS NULL THEN 1 ELSE 0 END)
            FROM sd_claims
            WHERE 1=1 {status_filter}
            GROUP BY 1
            ORDER BY 3 DESC
            """
        ).fetchall()
    finally:
        conn.close()

    carriers: list[dict[str, Any]] = []
    billed = 0.0
    billed_seen = False
    balance_sum = 0.0
    balance_seen = False
    unbilled = 0
    named = 0
    unnamed = 0
    total_claims = 0
    for payer, count, fee_sum, bal_sum, null_bal in rows:
        total_claims += int(count or 0)
        generic = _is_generic_payer(str(payer))
        if generic:
            unnamed += int(count or 0)
            label = "(unnamed / Insurance)"
        else:
            named += int(count or 0)
            label = str(payer)
        entry: dict[str, Any] = {
            "carrier": label,
            "claimCount": int(count or 0),
            "namedPayer": not generic,
        }
        if fee_sum is not None:
            entry["billedTotal"] = round(float(fee_sum), 2)
            billed += float(fee_sum)
            billed_seen = True
        else:
            entry["billedTotal"] = None
        if bal_sum is not None:
            entry["balanceTotal"] = round(float(bal_sum), 2)
            balance_sum += float(bal_sum)
            balance_seen = True
        else:
            entry["balanceTotal"] = None
        entry["unbilledCount"] = int(null_bal or 0)
        unbilled += int(null_bal or 0)
        carriers.append(entry)

    out.update(
        {
            "ok": total_claims > 0,
            "claimCount": total_claims,
            "namedPayerClaimCount": named,
            "unnamedPayerClaimCount": unnamed,
            "billedTotal": round(billed, 2) if billed_seen else None,
            "balanceTotal": round(balance_sum, 2) if balance_seen else None,
            "unbilledCount": unbilled,
            "byCarrier": carriers,
        }
    )
    if total_claims <= 0:
        out["error"] = "no_claims_rows"
    return out


def reconcile_claims_to_aging(
    claims: dict[str, Any],
    aging: dict[str, Any],
    *,
    tolerance: float = 1.00,
) -> dict[str, Any]:
    """Compare claims billed/balance to Account Aging insurance / AR totals."""
    result: dict[str, Any] = {
        "ok": True,
        "gapCode": GAP_OK,
        "tolerance": tolerance,
        "issues": [],
        "honesty": "empty != $0; no invented insurance AR",
    }
    if not aging.get("ok"):
        result["ok"] = False
        result["gapCode"] = GAP_AGING_MISSING
        result["issues"].append("Account Aging export missing or unparsed.")
        return result
    if not claims.get("ok"):
        result["ok"] = False
        result["gapCode"] = GAP_CLAIMS_MISSING
        result["issues"].append("sd_claims missing or empty.")
        return result

    aging_ins = aging.get("outstandingInsuranceTotal")
    aging_ar = aging.get("trueReceivablesTotal")
    claims_billed = claims.get("billedTotal")
    claims_bal = claims.get("balanceTotal")
    result["agingOutstandingInsurance"] = aging_ins
    result["agingTrueReceivables"] = aging_ar
    result["claimsBilledTotal"] = claims_billed
    result["claimsBalanceTotal"] = claims_bal

    unnamed = int(claims.get("unnamedPayerClaimCount") or 0)
    named = int(claims.get("namedPayerClaimCount") or 0)
    if unnamed > 0 and named == 0:
        result["ok"] = False
        result["gapCode"] = GAP_PAYER_ATTRIBUTION
        result["issues"].append(
            f"{unnamed} claim(s) lack named payer (SoftDent shows generic Insurance) — "
            "carrier drill-down blocked until ODBC/claims export includes real payers "
            "or sd_patient_insurance is populated."
        )
    elif unnamed > named:
        result["ok"] = False
        result["gapCode"] = GAP_PAYER_ATTRIBUTION
        result["issues"].append(
            f"Most claims lack named payers (named={named}, unnamed={unnamed})."
        )

    # Prefer balance when present; else billed vs aging insurance.
    compare_claims = claims_bal if claims_bal is not None else claims_billed
    compare_aging = aging_ins
    result["comparedClaimsAmount"] = compare_claims
    result["comparedAgingAmount"] = compare_aging

    if compare_aging is None:
        result["issues"].append("Aging outstanding-insurance total unavailable.")
    elif compare_claims is None:
        result["issues"].append("Claims amount unavailable (empty ≠ $0).")
    else:
        delta = abs(float(compare_claims) - float(compare_aging))
        result["delta"] = round(delta, 2)
        # SoftDent may print insurance outstanding $0 while daysheet-derived claims exist.
        if float(compare_aging) == 0.0 and float(compare_claims) > 0:
            result["ok"] = False
            if result["gapCode"] == GAP_OK:
                result["gapCode"] = GAP_RECONCILE_MISMATCH
            result["issues"].append(
                f"Account Aging Outstanding Insurance = $0.00 but sd_claims shows "
                f"${float(compare_claims):,.2f} (daysheet/pending claims) — do not invent "
                "Ins Plan collections; treat aging insurance $0 as SoftDent print truth for "
                "insurance AR buckets and keep claims as ops detail."
            )
        elif delta > tolerance:
            result["ok"] = False
            if result["gapCode"] == GAP_OK:
                result["gapCode"] = GAP_RECONCILE_MISMATCH
            result["issues"].append(
                f"Claims vs aging insurance delta ${delta:,.2f} exceeds tolerance ${tolerance:.2f}."
            )

    return result


def build_outstanding_claims_by_carrier_bridge(
    *,
    db_path: Path | str | None = None,
    aging_path: Path | str | None = None,
    write_inbox: bool = True,
) -> dict[str, Any]:
    """Full bridge payload for HAL / widgets / inbox JSON."""
    if aging_path:
        aging_file = Path(aging_path)
    else:
        aging_file = find_account_aging_export()
    aging = (
        parse_account_aging_export(aging_file)
        if aging_file
        else {"ok": False, "error": "aging_not_found", "path": None}
    )
    # Ensure bridge columns on writable DB when possible
    target = resolve_account_transactions_db(db_path)
    if target and target.is_file():
        try:
            wconn = sqlite3.connect(str(target))
            try:
                ensure_sd_claims_bridge_columns(wconn)
            finally:
                wconn.close()
        except sqlite3.Error:
            pass

    claims = aggregate_sd_claims_by_carrier(db_path=target)
    recon = reconcile_claims_to_aging(claims, aging)
    payload: dict[str, Any] = {
        "ok": True,
        "def": "HAL-10580",
        "checkedAt": _utc_now(),
        "aging": aging,
        "claims": claims,
        "reconcile": recon,
        "gapCode": recon.get("gapCode") or GAP_OK,
        "suggestedAction": (
            "refresh_sensei_claims_payer_attribution"
            if recon.get("gapCode") == GAP_PAYER_ATTRIBUTION
            else (
                "export_account_aging"
                if recon.get("gapCode") == GAP_AGING_MISSING
                else "review_claims_ar_bridge"
            )
        ),
        "honesty": "empty != $0; no SoftDent write-back; no invented carriers",
    }
    if write_inbox:
        try:
            from import_loader import softdent_import_dir

            dest = softdent_import_dir()
            dest.mkdir(parents=True, exist_ok=True)
            out_path = dest / "softdent_outstanding_claims_by_carrier.json"
            out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            payload["inboxPath"] = str(out_path)
        except Exception as exc:  # noqa: BLE001
            payload["inboxWriteError"] = f"{type(exc).__name__}:{exc}"
    return payload


def format_outstanding_claims_hal_reply(bridge: dict[str, Any] | None) -> str:
    b = bridge if isinstance(bridge, dict) else {}
    aging = b.get("aging") if isinstance(b.get("aging"), dict) else {}
    claims = b.get("claims") if isinstance(b.get("claims"), dict) else {}
    recon = b.get("reconcile") if isinstance(b.get("reconcile"), dict) else {}
    lines = [
        "Outstanding Claims by Carrier Bridge (HAL-10580).",
        f"gapCode=`{b.get('gapCode') or recon.get('gapCode') or '—'}` · "
        f"suggestedAction=`{b.get('suggestedAction') or '—'}` · empty ≠ $0.",
    ]
    if aging.get("ok"):
        ar = aging.get("trueReceivablesTotal")
        ins = aging.get("outstandingInsuranceTotal")
        lines.append(
            f"Account Aging: true receivables "
            f"{('$' + format(float(ar), ',.2f')) if ar is not None else '(empty)'} · "
            f"outstanding insurance "
            f"{('$' + format(float(ins), ',.2f')) if ins is not None else '(empty)'} · "
            f"accounts={aging.get('accountCount') or 0}."
        )
        if aging.get("path"):
            lines.append(f"Aging source: `{aging.get('path')}`.")
    else:
        lines.append(
            "Account Aging export not found — SoftDent Reports → Accounting → "
            "Account Aging → Excel (NEVER type SoftDentReportExports into SoftDent "
            "Select File Name — keep SoftDent's folder; NR2 copies after save)."
        )

    if claims.get("ok"):
        billed = claims.get("billedTotal")
        lines.append(
            f"sd_claims: {claims.get('claimCount') or 0} outstanding-ish rows · "
            f"named payers={claims.get('namedPayerClaimCount') or 0} · "
            f"unnamed={claims.get('unnamedPayerClaimCount') or 0} · "
            f"billed "
            f"{('$' + format(float(billed), ',.2f')) if billed is not None else '(empty)'}."
        )
        for row in (claims.get("byCarrier") or [])[:8]:
            if not isinstance(row, dict):
                continue
            amt = row.get("billedTotal")
            amt_s = f"${float(amt):,.2f}" if amt is not None else "(empty)"
            flag = "" if row.get("namedPayer") else " · payer unnamed"
            lines.append(
                f"- {row.get('carrier')}: {row.get('claimCount')} claims · billed {amt_s}{flag}"
            )
    else:
        lines.append("sd_claims empty/missing — run SoftDent ODBC extract or claims CSV ingest.")

    for issue in (recon.get("issues") or [])[:5]:
        lines.append(f"- {issue}")
    lines.append(
        "Do not invent carrier names or Ins Plan dollars. "
        "ERA-835 still required for insurance collections detail when Register Ins Plan is $0."
    )
    return "\n".join(lines)


def outstanding_claims_bridge_widget(bridge: dict[str, Any] | None = None) -> dict[str, Any]:
    b = bridge if isinstance(bridge, dict) else build_outstanding_claims_by_carrier_bridge(write_inbox=False)
    code = str(b.get("gapCode") or GAP_OK)
    aging = b.get("aging") if isinstance(b.get("aging"), dict) else {}
    claims = b.get("claims") if isinstance(b.get("claims"), dict) else {}
    healthy = code == GAP_OK and bool(b.get("ok"))
    has_sides = bool(aging.get("ok")) and int(claims.get("claimCount") or 0) > 0
    if healthy:
        message = (
            f"Claims/AR bridge OK · named payers={claims.get('namedPayerClaimCount') or 0} · "
            f"AR "
            f"{('$' + format(float(aging.get('trueReceivablesTotal')), ',.2f')) if aging.get('trueReceivablesTotal') is not None else '—'}"
        )
        status = "ok"
    elif has_sides:
        # SoftDent aging Excel + claims are present — show data with honest mismatch warn
        # (do not look "empty"; dollars not invented to force GAP_OK).
        message = (
            f"{code} · claims={claims.get('claimCount') or 0} · "
            f"named={claims.get('namedPayerClaimCount') or 0} · "
            f"AR "
            f"{('$' + format(float(aging.get('trueReceivablesTotal')), ',.2f')) if aging.get('trueReceivablesTotal') is not None else '—'}"
        )
        status = "warn"
    else:
        message = f"{code} · claims={claims.get('claimCount') or 0} · unnamed={claims.get('unnamedPayerClaimCount') or 0}"
        status = "empty"
    return {
        "id": "softdent-outstanding-claims-bridge",
        "type": "status",
        "label": "Outstanding Claims by Carrier (HAL-10580)",
        "size": "full",
        "status": status,
        "message": message,
        "gapCode": code,
        "hint": (
            "Refresh SoftDent ODBC claims with named payers, or drop Account Aging Excel."
            if status == "empty"
            else (
                "sd_claims vs Account Aging present — review carrier reconcile mismatch (empty ≠ $0)."
                if status == "warn"
                else "sd_claims reconciled to Account Aging insurance buckets."
            )
        ),
        "bridge": b,
        "halChips": [
            {"label": "Outstanding claims by carrier", "query": "Show outstanding claims by carrier"},
            {"label": "A/R aging totals", "query": "What is SoftDent account aging total?"},
            {"label": "Collections gap", "query": "Why are collections empty?"},
        ],
        "suggestedAction": b.get("suggestedAction"),
    }
