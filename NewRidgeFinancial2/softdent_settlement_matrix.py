"""HAL-10605 — Gold payment lines → settlement_matrix hydration.

Moonshot: MOONSHOT_DENTAL_INSURANCE_INDUSTRY_KNOWLEDGE_2026-07-13.md
- Prefer viaGold > viaAlias > viaLedger
- Map payment InsCo → spine via accepted aliases
- Do NOT invent gold lines when CSV missing (empty != $0)
- No SoftDent write-back
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from softdent_treatment_planning import resolve_analytics_db

DEF_ID = "HAL-10605"
PACKAGE_BUILD_ID = "hal-10605"
MIN_N_FOR_DOLLAR = 10


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return bool(
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            (name,),
        ).fetchone()
    )


def ensure_settlement_matrix_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS settlement_matrix (
            spine_carrier TEXT NOT NULL,
            ada_code TEXT NOT NULL,
            avg_paid REAL,
            n_payments INTEGER NOT NULL DEFAULT 0,
            std_dev REAL,
            last_updated TEXT,
            PRIMARY KEY (spine_carrier, ada_code)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_settlement_matrix_ada "
        "ON settlement_matrix(ada_code)"
    )


def _resolve_spine_name(
    company: str,
    *,
    master_to_spine: dict[str, str],
    spine_upper: dict[str, str],
) -> str | None:
    raw = str(company or "").strip()
    if not raw:
        return None
    u = raw.upper()
    if u in spine_upper:
        return spine_upper[u]
    mapped = master_to_spine.get(u)
    if mapped:
        return mapped
    return None


def hydrate_settlement_matrix(
    *,
    db_path: Path | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Aggregate sd_insurance_payment_lines → settlement_matrix via aliases.

    Does not invent rows when payment lines are empty.
    """
    owns = conn is None
    target = Path(db_path) if db_path else resolve_analytics_db()
    out: dict[str, Any] = {
        "ok": False,
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "paymentLines": 0,
        "matrixCells": 0,
        "cellsNge10": 0,
        "orphans": 0,
        "linked": 0,
        "gapCode": None,
        "emptyIsNotZero": True,
        "triggersGoldIngest": False,
        "inventedGold": False,
    }
    if owns:
        if not target or not target.is_file():
            out["error"] = "analytics_db_missing"
            out["gapCode"] = "ANALYTICS_DB_MISSING"
            return out
        conn = sqlite3.connect(str(target), timeout=30.0)
    assert conn is not None
    try:
        ensure_settlement_matrix_schema(conn)
        if not _table_exists(conn, "sd_insurance_payment_lines"):
            conn.execute("DELETE FROM settlement_matrix")
            if owns:
                conn.commit()
            out.update(
                {
                    "ok": True,
                    "gapCode": "GOLD_CSV_MISSING",
                    "message": "No payment lines table — settlement_matrix cleared. empty != $0.",
                }
            )
            return out

        n_lines = int(
            conn.execute("SELECT COUNT(*) FROM sd_insurance_payment_lines").fetchone()[0]
            or 0
        )
        out["paymentLines"] = n_lines
        if n_lines == 0:
            conn.execute("DELETE FROM settlement_matrix")
            if owns:
                conn.commit()
            out.update(
                {
                    "ok": True,
                    "gapCode": "GOLD_CSV_MISSING",
                    "message": (
                        "sd_insurance_payment_lines=0 — no settlement_matrix hydration. "
                        "Drop SoftDent Insurance Payment Analysis CSV then Sync. empty != $0."
                    ),
                }
            )
            return out

        from softdent_carrier_alias import list_spine_carriers, load_accepted_alias_maps

        map_db = Path(db_path) if db_path else target
        maps = load_accepted_alias_maps(db_path=map_db)
        master_to_spine = {
            str(k).upper(): str(v)
            for k, v in (maps.get("masterToSpine") or {}).items()
            if k and v
        }
        spine_upper = {
            s.upper(): s for s in list_spine_carriers(db_path=map_db) if s
        }

        buckets: dict[tuple[str, str], list[Decimal]] = {}
        orphans = 0
        linked = 0
        zero_paid_excluded = 0
        from decimal import Decimal, ROUND_HALF_EVEN
        from money_cents import TWOPLACES, money_as_sqlite_real, to_money
        import math

        for company, ada, paid in conn.execute(
            """
            SELECT insurance_company, ada_code, paid_amount
            FROM sd_insurance_payment_lines
            WHERE insurance_company IS NOT NULL AND trim(insurance_company) != ''
              AND ada_code IS NOT NULL AND trim(ada_code) != ''
              AND paid_amount IS NOT NULL
            """
        ):
            spine = _resolve_spine_name(
                str(company),
                master_to_spine=master_to_spine,
                spine_upper=spine_upper,
            )
            if not spine:
                orphans += 1
                continue
            paid_d = to_money(paid)
            if paid_d is None:
                orphans += 1
                continue
            # $0 paid lines are observed denials — exclude from avg_paid (do not invent)
            if paid_d == Decimal("0.00"):
                zero_paid_excluded += 1
                continue
            linked += 1
            key = (spine, str(ada).strip().upper())
            buckets.setdefault(key, []).append(paid_d)

        stamp = _utc_now()
        conn.execute("DELETE FROM settlement_matrix")
        cells = 0
        nge10 = 0
        for (spine, ada), pays in buckets.items():
            n = len(pays)
            if n < 1:
                continue
            total = sum(pays, Decimal("0.00"))
            avg = (total / Decimal(n)).quantize(TWOPLACES, rounding=ROUND_HALF_EVEN)
            if n == 1:
                std = Decimal("0.00")
            else:
                mean = avg
                var = sum((p - mean) ** 2 for p in pays) / Decimal(n - 1)
                std = Decimal(str(math.sqrt(float(var)))).quantize(
                    TWOPLACES, rounding=ROUND_HALF_EVEN
                )
            conn.execute(
                """
                INSERT INTO settlement_matrix (
                    spine_carrier, ada_code, avg_paid, n_payments, std_dev, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    spine,
                    ada,
                    money_as_sqlite_real(avg),
                    n,
                    money_as_sqlite_real(std),
                    stamp,
                ),
            )
            cells += 1
            if n >= MIN_N_FOR_DOLLAR:
                nge10 += 1
        if owns:
            conn.commit()
        link_pct = (linked / n_lines * 100.0) if n_lines else 0.0
        out.update(
            {
                "ok": True,
                "gapCode": "GOLD_OK",
                "matrixCells": cells,
                "cellsNge10": nge10,
                "orphans": orphans,
                "linked": linked,
                "zeroPaidExcluded": zero_paid_excluded,
                "spineLinkPct": round(link_pct, 2),
                "lastUpdated": stamp,
                "message": (
                    f"Hydrated settlement_matrix: {cells} cells "
                    f"({nge10} with n>={MIN_N_FOR_DOLLAR}); "
                    f"spine link {link_pct:.1f}% "
                    f"(excluded {zero_paid_excluded} $0 paid lines from avg)."
                ),
            }
        )
        return out
    finally:
        if owns:
            conn.close()


def lookup_settlement_matrix(
    *,
    payer: str,
    ada_code: str,
    db_path: Path | None = None,
    min_sample: int = MIN_N_FOR_DOLLAR,
) -> dict[str, Any]:
    """Lookup viaGold settlement cell. Never invents dollars."""
    from softdent_treatment_planning import normalize_ada_code
    from softdent_carrier_alias import resolve_accepted_alias_for_tp

    ada = normalize_ada_code(ada_code)
    out: dict[str, Any] = {
        "ok": True,
        "found": False,
        "sufficient": False,
        "viaGold": False,
        "source": None,
        "spineCarrierName": None,
        "avgPaid": None,
        "sampleSize": 0,
        "stdDev": None,
        "emptyIsNotZero": True,
        "def": DEF_ID,
    }
    target = Path(db_path) if db_path else resolve_analytics_db()
    if not target or not target.is_file() or not ada:
        return out

    alias = resolve_accepted_alias_for_tp(payer, db_path=target)
    if alias.get("blockedPending"):
        out["blockedPending"] = True
        return out

    candidates = []
    spine = alias.get("spineCarrierName")
    if spine:
        candidates.append(str(spine))
    raw = str(payer or "").strip()
    if raw:
        candidates.append(raw)

    conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        if not _table_exists(conn, "settlement_matrix"):
            return out
        for name in candidates:
            row = conn.execute(
                """
                SELECT spine_carrier, ada_code, avg_paid, n_payments, std_dev, last_updated
                FROM settlement_matrix
                WHERE upper(ada_code)=upper(?)
                  AND upper(spine_carrier)=upper(?)
                LIMIT 1
                """,
                (ada, name),
            ).fetchone()
            if row:
                n = int(row[3] or 0)
                out.update(
                    {
                        "found": True,
                        "viaGold": True,
                        "source": "viaGold",
                        "spineCarrierName": row[0],
                        "avgPaid": row[2],
                        "sampleSize": n,
                        "stdDev": row[4],
                        "lastUpdated": row[5],
                        "sufficient": n >= min_sample,
                        "viaAlias": bool(alias.get("viaAlias")),
                    }
                )
                return out
        return out
    finally:
        conn.close()


def settlement_matrix_status(*, db_path: Path | None = None) -> dict[str, Any]:
    target = Path(db_path) if db_path else resolve_analytics_db()
    out: dict[str, Any] = {
        "ok": False,
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "emptyIsNotZero": True,
    }
    if not target or not target.is_file():
        out["error"] = "analytics_db_missing"
        return out
    conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        pay_n = 0
        if _table_exists(conn, "sd_insurance_payment_lines"):
            pay_n = int(
                conn.execute("SELECT COUNT(*) FROM sd_insurance_payment_lines").fetchone()[0]
                or 0
            )
        cells = 0
        nge10 = 0
        if _table_exists(conn, "settlement_matrix"):
            cells = int(conn.execute("SELECT COUNT(*) FROM settlement_matrix").fetchone()[0] or 0)
            nge10 = int(
                conn.execute(
                    "SELECT COUNT(*) FROM settlement_matrix WHERE n_payments >= ?",
                    (MIN_N_FOR_DOLLAR,),
                ).fetchone()[0]
                or 0
            )
        out.update(
            {
                "ok": True,
                "paymentLines": pay_n,
                "matrixCells": cells,
                "cellsNge10": nge10,
                "gapCode": "GOLD_OK" if pay_n > 0 else "GOLD_CSV_MISSING",
                "acceptanceCellsNge10Target": 200,
                "acceptanceGateMet": pay_n >= 1000 and nge10 >= 200,
            }
        )
        return out
    finally:
        conn.close()


def run_hal10605_gold_settlement_package(
    *,
    db_path: Path | None = None,
    search_dir: Path | None = None,
) -> dict[str, Any]:
    """Full HAL-10605: industry HIGH apply + gold repair + matrix hydrate."""
    from softdent_carrier_alias import apply_moonshot_industry_aliases
    from softdent_gold_payment_pipeline import run_gold_payment_pipeline_repair

    aliases = apply_moonshot_industry_aliases(
        db_path=db_path, include_medium_as_pending=True
    )
    repair = run_gold_payment_pipeline_repair(db_path=db_path, search_dir=search_dir)
    matrix = hydrate_settlement_matrix(db_path=db_path)
    status = settlement_matrix_status(db_path=db_path)
    return {
        "ok": True,
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "aliases": aliases,
        "goldRepair": {
            "gapCode": (repair.get("audit") or {}).get("gapCode"),
            "paymentLines": (repair.get("audit") or {}).get("paymentLines"),
            "ingestPaymentLines": (repair.get("ingest") or {}).get("paymentLines"),
        },
        "matrix": matrix,
        "status": status,
        "emptyIsNotZero": True,
        "inventedGold": False,
        "coventryRemainsPending": True,
        "rejectedForceMatched": False,
    }
