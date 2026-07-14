#!/usr/bin/env python3
"""HAL-10596/10599 — One-shot InsCo×ADA catalog rebuild (spine → $ → % → matrix).

Order:
  1) probabilistic $ estimates (builds from spine samples)
  2) pct variance
  3) catalog matrix export (JSON/MD/CSV + inbox)
     staff CSV expands SoftDent company master × ADA (HAL-10599)

Does not invent gold payment lines. empty != $0. No SoftDent write-back.
"""


from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NR2 = REPO / "NewRidgeFinancial2"
sys.path.insert(0, str(NR2))

from softdent_insco_ada_catalog_matrix import (  # noqa: E402
    PACKAGE_BUILD_ID,
    catalog_matrix_status,
    run_insco_ada_catalog_matrix_report,
)
from softdent_insco_ada_pct_variance import run_insco_ada_pct_variance_report  # noqa: E402
from softdent_insco_ada_probabilistic import run_insco_ada_probabilistic_report  # noqa: E402


def rebuild_insco_ada_catalog(*, db_path: Path | None = None, years: int = 5) -> dict:
    db = Path(db_path) if db_path else None
    steps: dict = {"packageBuildId": PACKAGE_BUILD_ID, "ok": False}
    prob = run_insco_ada_probabilistic_report(db_path=db)
    steps["probabilistic"] = {
        "ok": bool(prob.get("ok")),
        "build": (prob.get("build") or {}),
        "error": prob.get("error"),
    }
    pct = run_insco_ada_pct_variance_report(db_path=db, years=years)
    steps["pctVariance"] = {
        "ok": bool(pct.get("ok")),
        "build": (pct.get("build") or {}),
        "error": pct.get("error"),
    }
    cat = run_insco_ada_catalog_matrix_report(db_path=db)
    steps["catalog"] = {
        "ok": bool(cat.get("ok")),
        "status": cat.get("status"),
        "export": {
            k: (cat.get("export") or {}).get(k)
            for k in (
                "csvPath",
                "jsonPath",
                "mdPath",
                "inboxCsvPath",
                "inboxPath",
                "cellCount",
                "exactUsable",
                "insufficient",
                "uncoveredCount",
            )
        },
    }
    st = catalog_matrix_status(db_path=db)
    steps["status"] = st
    steps["ok"] = bool(prob.get("ok")) and bool(pct.get("ok")) and bool(cat.get("ok"))
    return steps


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild InsCo×ADA catalog (HAL-10596)")
    parser.add_argument("--db", type=Path, default=None, help="Analytics SQLite path")
    parser.add_argument("--years", type=int, default=5, help="Pct variance window years")
    args = parser.parse_args()
    result = rebuild_insco_ada_catalog(db_path=args.db, years=args.years)
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
