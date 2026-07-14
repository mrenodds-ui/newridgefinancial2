"""Compare SoftDent DB lane vs desktop GUI for correctness/coverage/speed."""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "NewRidgeFinancial2"))

from softdent_odbc_extract import SD_TABLES, odbc_configured, odbc_dsn, resolve_sd_sqlite_db
from softdent_practice_exports import parse_softdent_register_xls

OUT = Path(r"C:\SoftDentFinancialExports\softdent_path_comparison.json")


def main() -> int:
    info: dict = {
        "question": "desktop GUI vs database — which is better/faster for correct SoftDent data?",
        "measuredAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    # DB
    t0 = time.perf_counter()
    db = resolve_sd_sqlite_db()
    db_info = {
        "odbcConfigured": bool(odbc_configured()),
        "odbcDsn": odbc_dsn() or None,
        "dbPath": str(db) if db else None,
        "tables": {},
        "julyPeriodRows": {},
    }
    if db and db.is_file():
        con = sqlite3.connect(str(db))
        cur = con.cursor()
        for name in SD_TABLES:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {name}")
                db_info["tables"][name] = int(cur.fetchone()[0])
            except Exception as exc:
                db_info["tables"][name] = f"ERR:{type(exc).__name__}"
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY 1")
        tables = [r[0] for r in cur.fetchall()]
        for tname in tables:
            low = tname.lower()
            if "period" not in low and "dashboard" not in low:
                continue
            try:
                cur.execute(f"PRAGMA table_info({tname})")
                cols = [r[1] for r in cur.fetchall()]
                pcol = next(
                    (c for c in cols if c.lower() in {"period", "year_month", "month", "ym"}),
                    None,
                )
                if not pcol:
                    continue
                cur.execute(
                    f"SELECT * FROM {tname} WHERE CAST({pcol} AS TEXT) LIKE ? LIMIT 3",
                    ("%2026-07%",),
                )
                rows = cur.fetchall()
                if not rows:
                    continue
                sample = dict(zip(cols, rows[0]))
                # scrub huge blobs
                sample = {k: (str(v)[:80] if v is not None else None) for k, v in sample.items()}
                db_info["julyPeriodRows"][tname] = {
                    "countSampled": len(rows),
                    "cols": cols,
                    "sample": sample,
                }
            except Exception:
                continue
        con.close()
    db_info["readMs"] = round((time.perf_counter() - t0) * 1000, 1)
    info["database"] = db_info

    # Excel Register already exported
    reg = Path(r"C:\SoftDentReportExports\register_for_period_2026-07-01_2026-07-12.xls")
    t1 = time.perf_counter()
    parsed = parse_softdent_register_xls(reg) if reg.is_file() else None
    info["desktopExcel"] = {
        "registerFilePresent": reg.is_file(),
        "parseMs": round((time.perf_counter() - t1) * 1000, 1),
        "july": None
        if not parsed
        else {
            k: parsed.get(k)
            for k in (
                "production",
                "collections",
                "insPlanCollections",
                "regularCollections",
                "insuranceSplitReported",
                "collectionsFormatRequired",
            )
        },
        "guiLearnAllReportsSec": None,
        "singleRegisterExportSecObserved": "~28 (prior successful July Register export)",
        "masterLearnOpenAllMenusSec": None,
    }
    learn = Path(r"C:\SoftDentFinancialExports\softdent_master_report_learn.json")
    if learn.is_file():
        L = json.loads(learn.read_text(encoding="utf-8"))
        try:
            a = datetime.fromisoformat(L["startedAt"].replace("Z", "+00:00"))
            b = datetime.fromisoformat(L["finishedAt"].replace("Z", "+00:00"))
            info["desktopExcel"]["masterLearnOpenAllMenusSec"] = round((b - a).total_seconds(), 1)
        except Exception:
            pass

    # Recommendation
    odbc = db_info["odbcConfigured"]
    has_sd = any(isinstance(v, int) and v > 0 for v in db_info["tables"].values())
    july_from_db = bool(db_info["julyPeriodRows"])
    july_from_xls = bool(info["desktopExcel"]["july"])

    info["verdict"] = {
        "correctnessSourceOfTruth": "desktop_app",
        "reasonCorrectness": (
            "User-confirmed SoftDent desktop reports produce all correct figures. "
            "Register Excel already yields SoftDent's own Productions/Collections/Ins Plan labels. "
            "DB lane here has sd_* operational tables but ODBC is not configured; "
            "period Ins Plan / Register-equivalent totals are not a reliable primary from DB alone."
        ),
        "speedWinner": "database_when_populated",
        "reasonSpeed": (
            f"DB/sqlite read ~{db_info['readMs']}ms vs Excel parse ~{info['desktopExcel']['parseMs']}ms "
            f"once file exists; full GUI export is tens of seconds per report + interactive desktop. "
            "But speed only matters if the DB row is the *correct* SoftDent total — today financial "
            "close figures still come from desktop Excel."
        ),
        "recommendedOperatingModel": "hybrid",
        "recommendation": [
            "Use desktop SoftDent Excel (Register/Daysheet/etc.) as the source of truth for period "
            "financial totals and Ins Plan/Regular — you know that path is complete and correct.",
            "Use database/Sensei/sd_* for fast operational detail (patients, procedures, claims, "
            "payments) when those tables are populated — much faster for lists/widgets.",
            "Do not treat DB as primary for period close until ODBC/Sensei is proven to reproduce "
            "the same Register totals SoftDent prints (side-by-side check).",
            "Daily: desktop Excel pull for master financial reports (5 PM interactive); "
            "DB/Sensei refresh for operational sd_* whenever available.",
        ],
        "thisWorkstation": {
            "odbcConfigured": odbc,
            "sdTablesPopulated": has_sd,
            "julyPeriodFromDb": july_from_db,
            "julyRegisterFromExcel": july_from_xls,
        },
    }

    OUT.write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(json.dumps(info["verdict"], indent=2))
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
