from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.main import app
from app.data_pipeline import recompute_cache
from fastapi.testclient import TestClient


def _period_key() -> str:
    today = date.today()
    return f"{today.year:04d}-{today.month:02d}"


def _kpi_for_period(rows: list[dict], period: str) -> dict:
    for row in rows:
        if str(row.get("period") or "") == period:
            return row
    return {}


def _as_float(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def main() -> int:
    source_dir = Path("app/data/test_ingest_source/softdent").resolve()
    source_dir.mkdir(parents=True, exist_ok=True)

    file_name = "controlled_softdent_ingest_check.csv"
    source_file = source_dir / file_name

    period = _period_key()
    production_bump = 7777.0
    collections_bump = 6666.0

    with TestClient(app):
        settings = app.state.settings
        original_source_dir = settings.softdent_source_dir
        original_auto_pull = settings.softdent_auto_pull_enabled

        settings.softdent_source_dir = source_dir
        settings.softdent_auto_pull_enabled = True

        target_files = [
            settings.softdent_import_dir / "softdent_dashboard_data.csv",
            settings.softdent_import_dir / "softdent_dashboard_data.json",
        ]
        source_file.unlink(missing_ok=True)
        for target_file in target_files:
            target_file.unlink(missing_ok=True)

        try:
            recompute_cache(app)
            baseline_status = dict((app.state.report_pull_status or {}).get("softdent", {}))
            baseline_row = _kpi_for_period(list(app.state.current_kpis or []), period)
            baseline_production = _as_float(baseline_row.get("production"))
            baseline_collections = _as_float(baseline_row.get("collections"))

            source_file.write_text(
                "Month,Metric,Amount\n"
                f"{period},Production,{production_bump:.2f}\n"
                f"{period},Collections,{collections_bump:.2f}\n",
                encoding="utf-8",
            )

            recompute_cache(app)
            after_status = dict((app.state.report_pull_status or {}).get("softdent", {}))
            after_row = _kpi_for_period(list(app.state.current_kpis or []), period)
            after_production = _as_float(after_row.get("production"))
            after_collections = _as_float(after_row.get("collections"))

            delta_production = after_production - baseline_production
            delta_collections = after_collections - baseline_collections

            copied_delta = int(after_status.get("copied", 0) or 0) - int(baseline_status.get("copied", 0) or 0)
            scanned_delta = int(after_status.get("scanned", 0) or 0) - int(baseline_status.get("scanned", 0) or 0)

            checks = {
                "counter_change": scanned_delta >= 1 and copied_delta >= 1,
                "kpi_production_change": abs(delta_production - production_bump) < 0.001,
                "kpi_collections_change": abs(delta_collections - collections_bump) < 0.001,
            }

            out = {
                "period": period,
                "source_file": str(source_file),
                "import_file": str(target_files[0]),
                "baseline": {
                    "softdent_pull": baseline_status,
                    "production": baseline_production,
                    "collections": baseline_collections,
                },
                "after": {
                    "softdent_pull": after_status,
                    "production": after_production,
                    "collections": after_collections,
                },
                "delta": {
                    "softdent_scanned": scanned_delta,
                    "softdent_copied": copied_delta,
                    "production": delta_production,
                    "collections": delta_collections,
                },
                "checks": checks,
            }

            print(json.dumps(out, indent=2))
            return 0 if all(checks.values()) else 1
        finally:
            source_file.unlink(missing_ok=True)
            for target_file in target_files:
                target_file.unlink(missing_ok=True)
            settings.softdent_source_dir = original_source_dir
            settings.softdent_auto_pull_enabled = original_auto_pull
            recompute_cache(app)


if __name__ == "__main__":
    raise SystemExit(main())
