"""Ingest SoftDent PRODUCTION/TRANSACTIONS BY CODE Excel (PRODBYADA.xls).

Honesty:
- SoftDent internal CODE rollups by provider (qty + $) — NOT InsCo×ADA Gold.
- Does NOT write sd_insurance_payment_lines / settlement_matrix.
- empty != $0; inventedGold=false; no SoftDent write-back.

Typical path: D:\\PRODBYADA.xls or C:\\SoftDentFinancialExports\\production_by_ada_*.xls
Period on report (e.g. 07/13/25 TO 07/13/26) = 1 year.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from money_cents import money_as_sqlite_real, to_money_from_csv
from softdent_treatment_planning import normalize_ada_code, resolve_analytics_db, resolve_exports_dir

DEF_ID = "HAL-10609"
PACKAGE_BUILD_ID = "hal-10609"
SOURCE_TAG = "softdent_prodbyada_xls"

_CANDIDATE_NAMES = (
    "PRODBYADA.xls",
    "PRODBYADA.XLS",
    "production_by_ada_*.xls",
    "ProdByAda*.xls",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha(*parts: Any) -> str:
    payload = "|".join("" if p is None else str(p) for p in parts)
    return hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()


def find_prodbyada_xls(*, search_dirs: list[Path] | None = None) -> Path | None:
    roots: list[Path] = []
    for r in search_dirs or []:
        roots.append(Path(r))
    roots.extend(
        [
            Path(r"D:\\"),
            resolve_exports_dir(),
            Path(r"C:\SoftDentReportExports"),
            Path.home() / "Downloads",
        ]
    )
    files: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        try:
            if not root.exists() or not root.is_dir():
                continue
        except OSError:
            continue
        candidates: list[Path] = []
        for name in ("PRODBYADA.xls", "PRODBYADA.XLS"):
            p = root / name
            if p.is_file():
                candidates.append(p)
        for pat in ("production_by_ada_*.xls", "ProdByAda*.xls"):
            try:
                candidates.extend(root.glob(pat))
            except OSError:
                pass
        for p in candidates:
            try:
                key = str(p.resolve()).lower()
            except OSError:
                continue
            if key in seen:
                continue
            seen.add(key)
            files.append(p)
    if not files:
        return None
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0]


def _parse_period(text: str) -> tuple[date | None, date | None]:
    raw = str(text or "").strip().upper().replace("–", " TO ").replace("-", " TO ")
    m = re.search(
        r"(\d{1,2}/\d{1,2}/\d{2,4})\s+TO\s+(\d{1,2}/\d{1,2}/\d{2,4})",
        raw,
    )
    if not m:
        return None, None

    def _d(s: str) -> date | None:
        for fmt in ("%m/%d/%y", "%m/%d/%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        return None

    return _d(m.group(1)), _d(m.group(2))


def _parse_provider(text: str) -> tuple[str, str]:
    raw = re.sub(r"\s+", " ", str(text or "").strip())
    m = re.match(r"PROVIDER\s+(\d+)\s+(.*)$", raw, flags=re.I)
    if m:
        return m.group(1), m.group(2).strip()
    return "", raw


def _is_detail_sheet(name: str) -> bool:
    # SoftDent pairs detail + trailing-space totals sheets
    return bool(name) and not str(name).endswith(" ")


def _cell_money(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, str) and "*" in value:
        return None
    return money_as_sqlite_real(to_money_from_csv(value))


def _cell_qty(value: Any) -> int:
    if value is None or value == "":
        return 0
    if isinstance(value, str) and "*" in value:
        return 0
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def parse_prodbyada_xls(path: Path) -> dict[str, Any]:
    try:
        import xlrd
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("xlrd required to parse SoftDent PRODBYADA.xls") from exc

    book = xlrd.open_workbook(str(path))
    rows_out: list[dict[str, Any]] = []
    period_start: date | None = None
    period_end: date | None = None
    file_hash = _sha(path.read_bytes()[:65536], path.stat().st_size)

    for sheet_name in book.sheet_names():
        if not _is_detail_sheet(sheet_name):
            continue
        sh = book.sheet_by_name(sheet_name)
        if sh.nrows < 8:
            continue
        ps, pe = _parse_period(str(sh.cell_value(1, 0)))
        if ps and pe:
            period_start, period_end = ps, pe
        provider_id, provider_name = _parse_provider(str(sh.cell_value(3, 0)))
        if not provider_name:
            provider_name = sheet_name.strip()

        for r in range(7, sh.nrows):
            code_raw = sh.cell_value(r, 0)
            desc = str(sh.cell_value(r, 1) or "").strip()
            if code_raw in ("", None) or not desc or desc.lower() == "totals":
                continue
            # SoftDent codes may be float (2.0, 2.01, 120.0)
            if isinstance(code_raw, float):
                if code_raw.is_integer():
                    code_str = str(int(code_raw))
                else:
                    code_str = f"{code_raw:.10g}"
            else:
                code_str = str(code_raw).strip()
            if not code_str:
                continue

            qty = _cell_qty(sh.cell_value(r, 3))  # PRVDR QTY (avoid duplicating GROUP across sheets)
            amt = _cell_money(sh.cell_value(r, 6))  # PRVDR AMNT $
            fee = _cell_money(sh.cell_value(r, 2))
            if qty <= 0 and (amt is None or amt == 0):
                continue

            ada = normalize_ada_code(code_str)
            rows_out.append(
                {
                    "softdent_code": code_str,
                    "ada_code": ada or code_str,
                    "procedure_code": code_str,
                    "description": desc,
                    "procedure_count": qty,
                    "gross_production": amt,
                    "adjusted_production": amt,
                    "net_production": amt,
                    "fee": fee,
                    "provider_id": provider_id,
                    "provider_name": provider_name,
                    "sheet": sheet_name,
                    "amountBasis": "provider",
                }
            )

    # Practice-level GROUP rollup once (first detail sheet) for insurance recon
    group_rollups: list[dict[str, Any]] = []
    for sheet_name in book.sheet_names():
        if not _is_detail_sheet(sheet_name):
            continue
        sh = book.sheet_by_name(sheet_name)
        if sh.nrows < 8:
            continue
        for r in range(7, sh.nrows):
            code_raw = sh.cell_value(r, 0)
            desc = str(sh.cell_value(r, 1) or "").strip()
            if code_raw in ("", None) or not desc or desc.lower() == "totals":
                continue
            if isinstance(code_raw, float):
                code_str = (
                    str(int(code_raw)) if code_raw.is_integer() else f"{code_raw:.10g}"
                )
            else:
                code_str = str(code_raw).strip()
            qty = _cell_qty(sh.cell_value(r, 4))
            amt = _cell_money(sh.cell_value(r, 8))
            if qty <= 0 and (amt is None or amt == 0):
                continue
            group_rollups.append(
                {
                    "code": code_str,
                    "description": desc,
                    "groupQty": qty,
                    "groupAmt": amt,
                }
            )
        break  # one practice-level GROUP snapshot only

    return {
        "ok": True,
        "path": str(path),
        "fileHash": file_hash,
        "periodStart": period_start.isoformat() if period_start else None,
        "periodEnd": period_end.isoformat() if period_end else None,
        "rowCount": len(rows_out),
        "rows": rows_out,
        "groupRollups": group_rollups,
    }


def ensure_production_by_ada_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS production_by_ada (
            id INTEGER PRIMARY KEY,
            row_sha256 TEXT,
            business_key TEXT,
            period_start TEXT,
            period_end TEXT,
            report_period_start TEXT,
            report_period_end TEXT,
            report_date TEXT,
            calendar_year INTEGER,
            calendar_month INTEGER,
            year_month TEXT,
            ada_code TEXT,
            procedure_code TEXT,
            description TEXT,
            procedure_description TEXT,
            procedure_count INTEGER,
            gross_production REAL,
            adjusted_production REAL,
            net_production REAL,
            adjustments REAL,
            collections REAL,
            provider_id TEXT,
            provider_name TEXT,
            source_file_hash TEXT,
            source_file TEXT,
            imported_at_utc TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_production_by_ada_code "
        "ON production_by_ada(ada_code)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_production_by_ada_source "
        "ON production_by_ada(source_file)"
    )


def ingest_prodbyada_xls(
    path: Path | None = None,
    *,
    db_path: Path | None = None,
    copy_to_exports: bool = True,
) -> dict[str, Any]:
    """Parse PRODBYADA.xls → production_by_ada (source-tagged; Sensei rows kept)."""
    target = Path(path) if path else find_prodbyada_xls()
    out: dict[str, Any] = {
        "ok": False,
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "inventedGold": False,
        "writesPaymentLines": False,
        "settlementMatrixHydrated": False,
        "emptyIsNotZero": True,
        "sourceTag": SOURCE_TAG,
        "honesty": (
            "SoftDent Production/Transactions by Code Excel — CODE rollups only; "
            "NOT InsCo×ADA gold; does not populate sd_insurance_payment_lines."
        ),
    }
    if not target or not target.is_file():
        out["error"] = "PRODBYADA_XLS_MISSING"
        out["hint"] = (
            r"Export SoftDent Reports→Practice Management→Production Reports→"
            r"Production by ADA Code → Excel; save as D:\PRODBYADA.xls"
        )
        return out

    parsed = parse_prodbyada_xls(target)
    if int(parsed.get("rowCount") or 0) <= 0:
        out["error"] = "PRODBYADA_EMPTY"
        out["path"] = str(target)
        return out

    exports = resolve_exports_dir()
    exports.mkdir(parents=True, exist_ok=True)
    copied: Path | None = None
    if copy_to_exports:
        stamp = (parsed.get("periodStart") or "unknown").replace("-", "")
        stamp2 = (parsed.get("periodEnd") or "unknown").replace("-", "")
        copied = exports / f"production_by_ada_{stamp}_{stamp2}.xls"
        if target.resolve() != copied.resolve():
            shutil.copy2(target, copied)

    db = Path(db_path) if db_path else resolve_analytics_db()
    if not db:
        out["error"] = "analytics_db_missing"
        return out

    period_start = parsed.get("periodStart")
    period_end = parsed.get("periodEnd")
    end_d = None
    try:
        end_d = date.fromisoformat(str(period_end)) if period_end else None
    except ValueError:
        end_d = None
    year_month = f"{end_d.year:04d}-{end_d.month:02d}" if end_d else "unknown"
    imported_at = _utc_now()
    source_label = f"{SOURCE_TAG}:{copied.name if copied else target.name}"

    conn = sqlite3.connect(str(db), timeout=30.0)
    try:
        ensure_production_by_ada_schema(conn)
        conn.execute("BEGIN IMMEDIATE")
        # Replace only prior PRODBYADA ingest — keep Sensei-derived rows
        conn.execute(
            "DELETE FROM production_by_ada WHERE source_file LIKE ?",
            (f"{SOURCE_TAG}:%",),
        )
        insert_rows: list[dict[str, Any]] = []
        for row in parsed["rows"]:
            biz = "|".join(
                [
                    SOURCE_TAG,
                    str(period_start or ""),
                    str(period_end or ""),
                    str(row.get("provider_id") or ""),
                    str(row.get("procedure_code") or ""),
                    str(row.get("description") or ""),
                ]
            )
            row_sha = _sha(biz, row.get("procedure_count"), row.get("net_production"))
            insert_rows.append(
                {
                    "row_sha256": row_sha,
                    "business_key": biz,
                    "period_start": period_start,
                    "period_end": period_end,
                    "report_period_start": period_start,
                    "report_period_end": period_end,
                    "report_date": period_end,
                    "calendar_year": end_d.year if end_d else None,
                    "calendar_month": end_d.month if end_d else None,
                    "year_month": year_month,
                    "ada_code": row.get("ada_code"),
                    "procedure_code": row.get("procedure_code"),
                    "description": row.get("description"),
                    "procedure_description": row.get("description"),
                    "procedure_count": row.get("procedure_count"),
                    "gross_production": row.get("gross_production"),
                    "adjusted_production": row.get("adjusted_production"),
                    "net_production": row.get("net_production"),
                    "adjustments": None,
                    "collections": None,
                    "provider_id": row.get("provider_id"),
                    "provider_name": row.get("provider_name"),
                    "source_file_hash": parsed.get("fileHash"),
                    "source_file": source_label,
                    "imported_at_utc": imported_at,
                }
            )
        conn.executemany(
            """
            INSERT INTO production_by_ada (
                row_sha256, business_key, period_start, period_end,
                report_period_start, report_period_end, report_date,
                calendar_year, calendar_month, year_month,
                ada_code, procedure_code, description, procedure_description,
                procedure_count, gross_production, adjusted_production, net_production,
                adjustments, collections, provider_id, provider_name,
                source_file_hash, source_file, imported_at_utc
            ) VALUES (
                :row_sha256, :business_key, :period_start, :period_end,
                :report_period_start, :report_period_end, :report_date,
                :calendar_year, :calendar_month, :year_month,
                :ada_code, :procedure_code, :description, :procedure_description,
                :procedure_count, :gross_production, :adjusted_production, :net_production,
                :adjustments, :collections, :provider_id, :provider_name,
                :source_file_hash, :source_file, :imported_at_utc
            )
            """,
            insert_rows,
        )
        conn.commit()
        total = int(conn.execute("SELECT COUNT(*) FROM production_by_ada").fetchone()[0] or 0)
        tagged = int(
            conn.execute(
                "SELECT COUNT(*) FROM production_by_ada WHERE source_file LIKE ?",
                (f"{SOURCE_TAG}:%",),
            ).fetchone()[0]
            or 0
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    # Insurance code rollup from practice GROUP snapshot (recon only — not gold)
    ins_codes = {"2", "2.01", "11.93", "12.93", "51", "33"}
    ins_rollups = []
    for row in parsed.get("groupRollups") or []:
        code = str(row.get("code") or "")
        desc = str(row.get("description") or "").lower()
        if code in ins_codes or "insurance" in desc:
            ins_rollups.append(
                {
                    "code": code,
                    "description": row.get("description"),
                    "qty": row.get("groupQty"),
                    "amount": row.get("groupAmt"),
                    "basis": "practice_group",
                }
            )

    out.update(
        {
            "ok": True,
            "path": str(target),
            "copiedTo": str(copied) if copied else None,
            "periodStart": period_start,
            "periodEnd": period_end,
            "rowsIngested": len(insert_rows),
            "productionByAdaTagged": tagged,
            "productionByAdaTotal": total,
            "insuranceCodeRollups": ins_rollups[:40],
            "checkedAt": imported_at,
        }
    )
    # Export slim report
    report = {
        k: out[k]
        for k in out
        if k != "insuranceCodeRollups"
    }
    report["insuranceCodeRollups"] = ins_rollups[:40]
    (exports / f"prodbyada_ingest_{date.today().isoformat()}.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    return out


def format_prodbyada_reply(result: dict[str, Any] | None = None) -> str:
    r = result if isinstance(result, dict) else ingest_prodbyada_xls()
    if not r.get("ok"):
        return (
            f"PRODBYADA ingest ({DEF_ID}): blocked ({r.get('error')}). "
            f"{r.get('hint') or ''} empty != $0; not gold."
        )
    return (
        f"PRODBYADA ingest ({DEF_ID}): {r.get('rowsIngested')} code rows "
        f"for {r.get('periodStart')}->{r.get('periodEnd')}. "
        f"NOT gold / payment lines untouched. empty != $0."
    )
