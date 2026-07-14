"""SoftDent Insurance Company master → insurance_company_reference.

Loads the downloaded SoftDent company list CSV (likely_active / discontinued)
into analytics SQLite. Does not invent gold payment lines or InsCo×ADA dollars.
empty != $0.
"""

from __future__ import annotations

import csv
import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from softdent_treatment_planning import resolve_analytics_db, resolve_exports_dir

DEF_ID = "HAL-10598"
PACKAGE_BUILD_ID = "hal-10598"

DEFAULT_CSV_CANDIDATES = (
    Path(r"C:\New folder\artifacts\softdent_insurance_companies_2026-06-06.csv"),
    Path(r"C:\SoftDentFinancialExports\softdent_insurance_companies.csv"),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def resolve_insurance_companies_csv(path: Path | None = None) -> Path | None:
    if path is not None and Path(path).is_file():
        return Path(path)
    for cand in DEFAULT_CSV_CANDIDATES:
        if cand.is_file():
            return cand
    exports = resolve_exports_dir()
    for pat in ("softdent_insurance_companies*.csv", "*insurance_companies*.csv"):
        hits = sorted(exports.glob(pat), reverse=True)
        if hits:
            return hits[0]
    return None


def ensure_insurance_company_reference_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS insurance_company_reference (
            id INTEGER PRIMARY KEY,
            row_sha256 TEXT UNIQUE,
            business_key TEXT,
            insurance_company TEXT,
            company_id TEXT,
            payer_id TEXT,
            active_status TEXT,
            source_file TEXT,
            imported_at_utc TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_insco_ref_status "
        "ON insurance_company_reference(active_status)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_insco_ref_name "
        "ON insurance_company_reference(insurance_company)"
    )


def _row_hash(payload: dict[str, str]) -> str:
    blob = "|".join(
        [
            payload.get("company_id") or "",
            payload.get("insurance_company") or "",
            payload.get("active_status") or "",
            payload.get("source_file") or "",
        ]
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def ingest_insurance_companies_csv(
    *,
    csv_path: Path | None = None,
    db_path: Path | None = None,
    copy_to_exports: bool = True,
) -> dict[str, Any]:
    """Replace insurance_company_reference from SoftDent company CSV."""
    src = resolve_insurance_companies_csv(csv_path)
    out: dict[str, Any] = {
        "ok": False,
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "csvPath": str(src) if src else None,
        "inserted": 0,
        "likelyActive": 0,
        "discontinued": 0,
        "placeholder": 0,
        "triggersGoldIngest": False,
        "emptyIsNotZero": True,
    }
    if src is None:
        out["error"] = "insurance_companies_csv_missing"
        out["message"] = (
            "No SoftDent insurance companies CSV found "
            "(expected New folder\\artifacts or SoftDentFinancialExports)."
        )
        return out

    db = Path(db_path) if db_path else resolve_analytics_db()
    if db is None or not Path(db).is_file():
        out["error"] = "analytics_db_missing"
        return out

    if copy_to_exports:
        try:
            dest_dir = resolve_exports_dir()
            dest_dir.mkdir(parents=True, exist_ok=True)
            stable = dest_dir / "softdent_insurance_companies.csv"
            stable.write_bytes(src.read_bytes())
            out["exportsCopy"] = str(stable)
        except Exception as exc:  # noqa: BLE001
            out["exportsCopyError"] = f"{type(exc).__name__}:{exc}"

    rows_in: list[dict[str, str]] = []
    with src.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for raw in reader:
            name = str(raw.get("company_name") or "").strip()
            if not name:
                continue
            status = str(raw.get("status") or "").strip().lower() or "unknown"
            company_id = str(raw.get("record_number") or "").strip()
            rows_in.append(
                {
                    "insurance_company": name,
                    "company_id": company_id,
                    "payer_id": "",
                    "active_status": status,
                    "business_key": f"insco:{company_id or name}",
                    "source_file": str(src),
                }
            )

    stamp = _utc_now()
    conn = sqlite3.connect(str(db), timeout=30.0)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        ensure_insurance_company_reference_schema(conn)
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM insurance_company_reference")
        inserted = 0
        counts = {"likely_active": 0, "discontinued": 0, "placeholder": 0, "unknown": 0}
        for row in rows_in:
            payload = {**row, "imported_at_utc": stamp}
            sha = _row_hash(payload)
            conn.execute(
                """
                INSERT OR REPLACE INTO insurance_company_reference (
                    row_sha256, business_key, insurance_company, company_id,
                    payer_id, active_status, source_file, imported_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sha,
                    payload["business_key"],
                    payload["insurance_company"],
                    payload["company_id"] or None,
                    payload["payer_id"] or None,
                    payload["active_status"],
                    payload["source_file"],
                    stamp,
                ),
            )
            inserted += 1
            key = payload["active_status"] if payload["active_status"] in counts else "unknown"
            counts[key] = counts.get(key, 0) + 1
        conn.commit()
        out.update(
            {
                "ok": True,
                "inserted": inserted,
                "likelyActive": counts.get("likely_active", 0),
                "discontinued": counts.get("discontinued", 0),
                "placeholder": counts.get("placeholder", 0),
                "unknown": counts.get("unknown", 0),
                "dbPath": str(db),
                "importedAt": stamp,
                "message": (
                    f"Loaded {inserted} SoftDent insurance companies "
                    f"({counts.get('likely_active', 0)} likely_active). "
                    "Master list only — does not invent InsCo×ADA dollars."
                ),
            }
        )
        return out
    except Exception as exc:  # noqa: BLE001
        try:
            conn.rollback()
        except Exception:
            pass
        out["error"] = f"{type(exc).__name__}:{exc}"
        return out
    finally:
        conn.close()


def insurance_company_reference_status(*, db_path: Path | None = None) -> dict[str, Any]:
    db = Path(db_path) if db_path else resolve_analytics_db()
    out: dict[str, Any] = {
        "ok": False,
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "total": 0,
        "likelyActive": 0,
        "discontinued": 0,
        "spineOverlapLikelyActive": 0,
        "likelyActiveNotInSpine": 0,
        "emptyIsNotZero": True,
        "triggersGoldIngest": False,
    }
    if db is None or not Path(db).is_file():
        out["error"] = "analytics_db_missing"
        return out
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='insurance_company_reference'"
        ).fetchone()
        if not exists:
            out["error"] = "table_missing"
            out["message"] = "Run scripts/import_softdent_insurance_companies_csv.py"
            return out
        total = int(
            conn.execute("SELECT COUNT(*) FROM insurance_company_reference").fetchone()[0] or 0
        )
        likely = int(
            conn.execute(
                "SELECT COUNT(*) FROM insurance_company_reference WHERE active_status='likely_active'"
            ).fetchone()[0]
            or 0
        )
        disc = int(
            conn.execute(
                "SELECT COUNT(*) FROM insurance_company_reference WHERE active_status='discontinued'"
            ).fetchone()[0]
            or 0
        )
        spine_names: set[str] = set()
        if conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='insco_ada_probabilistic_estimates'"
        ).fetchone():
            spine_names = {
                str(r[0]).strip().upper()
                for r in conn.execute(
                    "SELECT DISTINCT insurance_company FROM insco_ada_probabilistic_estimates"
                )
                if r[0]
            }
        likely_names = {
            str(r[0]).strip().upper()
            for r in conn.execute(
                "SELECT insurance_company FROM insurance_company_reference "
                "WHERE active_status='likely_active'"
            )
            if r[0]
        }
        overlap = len(likely_names & spine_names)
        missing_exact = sorted(likely_names - spine_names)
        # HAL-10600: after accepted aliases, gap shrinks without inventing dollars
        alias_status: dict[str, Any] = {}
        missing_after_alias = list(missing_exact)
        try:
            from softdent_carrier_alias import carrier_alias_status, load_accepted_alias_maps

            alias_status = carrier_alias_status(db_path=db)
            maps = load_accepted_alias_maps(db_path=db)
            linked = set(maps.get("masterToSpine") or {})
            missing_after_alias = sorted(n for n in missing_exact if n.upper() not in linked)
        except Exception as exc:  # noqa: BLE001
            alias_status = {"ok": False, "error": f"{type(exc).__name__}:{exc}"}
        src = conn.execute(
            "SELECT source_file, imported_at_utc FROM insurance_company_reference "
            "ORDER BY imported_at_utc DESC LIMIT 1"
        ).fetchone()
        out.update(
            {
                "ok": True,
                "total": total,
                "likelyActive": likely,
                "discontinued": disc,
                "spineCarriers": len(spine_names),
                "spineOverlapLikelyActive": overlap,
                "likelyActiveNotInSpineExact": len(missing_exact),
                "likelyActiveNotInSpine": len(missing_after_alias),
                "likelyActiveNotInSpineSample": missing_after_alias[:25],
                "carrierAlias": {
                    "ok": alias_status.get("ok"),
                    "autoAccepted": alias_status.get("autoAccepted"),
                    "fuzzyAutoAccepted": alias_status.get("fuzzyAutoAccepted"),
                    "manualPending": alias_status.get("manualPending"),
                    "rejected": alias_status.get("rejected"),
                    "acceptanceGateMet": alias_status.get("acceptanceGateMet"),
                },
                "sourceFile": src[0] if src else None,
                "importedAt": src[1] if src else None,
                "dbPath": str(db),
                "honesty": (
                    "Company master from SoftDent CSV. Accepted aliases join existing "
                    "spine settlements only — empty != $0; no gold invent."
                ),
            }
        )
        return out
    finally:
        conn.close()


def list_likely_active_companies(
    *,
    db_path: Path | None = None,
    limit: int = 500,
) -> list[str]:
    db = Path(db_path) if db_path else resolve_analytics_db()
    if db is None or not Path(db).is_file():
        return []
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            """
            SELECT insurance_company FROM insurance_company_reference
            WHERE active_status='likely_active'
            ORDER BY insurance_company
            LIMIT ?
            """,
            (max(1, int(limit)),),
        ).fetchall()
        return [str(r[0]) for r in rows if r[0]]
    except sqlite3.Error:
        return []
    finally:
        conn.close()
