#!/usr/bin/env python3
"""SoftDent money-widget Excel pull — Register/Daysheet/Aging/Collections only.

Desktop SoftDent is source of truth for period $. Pull Excel reports that feed
Vital Signs / Ins-Patient / A/R / DEF-001, refresh period imports, then check
Register vs daysheet_totals drift. Never prints passwords.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "NewRidgeFinancial2"))

from softdent_gui_export import run_catalog_exports, softdent_main_running  # noqa: E402
from softdent_period_money_drift import compare_register_to_daysheet_totals  # noqa: E402
from softdent_signon import softdent_signon_status  # noqa: E402

# Reports that feed period money / A/R widgets (Excel path)
MONEY_REPORT_IDS = ("register", "daysheet", "aging", "collections")
STATUS = Path(r"C:\SoftDentFinancialExports\softdent_money_widget_pull_status.json")


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _scrub(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: _scrub(v)
            for k, v in obj.items()
            if str(k).lower() not in {"password", "pwd", "secret", "token"}
            and not str(k).lower().endswith("password")
        }
    if isinstance(obj, list):
        return [_scrub(x) for x in obj]
    return obj


def main() -> int:
    today = date.today()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default=f"{today.year:04d}-{today.month:02d}-01")
    parser.add_argument("--end", default=today.isoformat())
    parser.add_argument(
        "--reports",
        default=",".join(MONEY_REPORT_IDS),
        help="Comma list from register,daysheet,aging,collections",
    )
    parser.add_argument("--skip-signon", action="store_true")
    parser.add_argument("--skip-refresh", action="store_true")
    parser.add_argument("--skip-export", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    report_ids = [x.strip() for x in str(args.reports).split(",") if x.strip()]

    payload: dict[str, Any] = {
        "ok": False,
        "startedAt": _utc(),
        "start": start.isoformat(),
        "end": end.isoformat(),
        "reportIds": report_ids,
        "purpose": "period money widgets (desktop Excel source of truth)",
        "signOn": softdent_signon_status(),
        "softdentRunning": softdent_main_running(),
        "exports": None,
        "refresh": None,
        "drift": None,
    }

    if args.dry_run or args.skip_export:
        if args.dry_run:
            payload["exports"] = run_catalog_exports(
                start=start,
                end=end,
                report_ids=report_ids,
                ensure_signon=False,
                dry_run=True,
            )
        else:
            payload["exports"] = {"skipped": True}
    else:
        payload["exports"] = run_catalog_exports(
            start=start,
            end=end,
            report_ids=report_ids,
            ensure_signon=not args.skip_signon,
            dry_run=False,
        )

    if not args.skip_refresh and not args.dry_run:
        try:
            from apex_backend import refresh_softdent_period_imports

            refresh = refresh_softdent_period_imports()
            payload["refresh"] = {
                "ok": bool(refresh.get("ok")),
                "collectionsGap": {
                    "gapCode": (refresh.get("collectionsGap") or {}).get("gapCode"),
                    "collectionsFormatRequired": (refresh.get("collectionsGap") or {}).get(
                        "collectionsFormatRequired"
                    ),
                    "coversOpenMonth": (refresh.get("collectionsGap") or {}).get("coversOpenMonth"),
                    "period": (refresh.get("collectionsGap") or {}).get("period"),
                },
            }
        except Exception as exc:  # noqa: BLE001
            payload["refresh"] = {"ok": False, "error": f"{type(exc).__name__}:{exc}"}
    else:
        payload["refresh"] = {"skipped": True, "ok": True}

    payload["drift"] = compare_register_to_daysheet_totals(start=start, end=end)
    exports = payload.get("exports") or {}
    required_failed = list(exports.get("requiredFailed") or [])
    exports_ok = bool(exports.get("ok")) or bool(exports.get("skipped")) or bool(args.dry_run)
    refresh_ok = bool((payload.get("refresh") or {}).get("ok"))
    # Multi-report: partial Ok only when some paths landed and required failures remain.
    payload["ok"] = bool(exports_ok and refresh_ok and (payload.get("drift") or {}).get("ok") and not required_failed)
    payload["partialOk"] = bool(
        not payload["ok"]
        and (
            any(bool((exports.get("reports") or {}).get(r, {}).get("path")) for r in report_ids)
            or bool(exports.get("partialOk"))
        )
    )
    payload["finishedAt"] = _utc()

    STATUS.parent.mkdir(parents=True, exist_ok=True)
    clean = _scrub(payload)
    STATUS.write_text(json.dumps(clean, indent=2), encoding="utf-8")
    print(json.dumps(clean, indent=2))
    if payload["ok"]:
        return 0
    if payload.get("partialOk"):
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
