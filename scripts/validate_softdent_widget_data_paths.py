"""Validate SoftDent widget data-path claims against live bundle / DB / inbox."""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "NewRidgeFinancial2"))

OUT = Path(r"C:\SoftDentFinancialExports\softdent_widget_path_validation.json")
EXPORTS = Path(r"C:\SoftDentReportExports")


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _inbox_files() -> dict[str, Any]:
    if not EXPORTS.is_dir():
        return {"ok": False, "error": "inbox_missing"}
    names = sorted(p.name for p in EXPORTS.iterdir() if p.is_file())
    kinds = {
        "registerXls": [n for n in names if n.lower().startswith("register") and n.lower().endswith((".xls", ".xlsx"))],
        "registerCsv": [n for n in names if "register" in n.lower() and n.lower().endswith(".csv")],
        "daysheet": [n for n in names if "daysheet" in n.lower()],
        "aging": [n for n in names if "aging" in n.lower()],
        "transactions": [n for n in names if "trans" in n.lower()],
        "writeoff": [n for n in names if "writeoff" in n.lower()],
        "collections": [n for n in names if "collection" in n.lower()],
    }
    return {"ok": True, "fileCount": len(names), "kinds": kinds, "sample": names[:20]}


def _db_snapshot() -> dict[str, Any]:
    from softdent_odbc_extract import SD_TABLES, odbc_configured, resolve_sd_sqlite_db

    db = resolve_sd_sqlite_db()
    out: dict[str, Any] = {
        "odbcConfigured": bool(odbc_configured()),
        "dbPath": str(db) if db else None,
        "sdTables": {},
        "julyDashboard": None,
    }
    if not db or not db.is_file():
        out["ok"] = False
        return out
    con = sqlite3.connect(str(db))
    cur = con.cursor()
    for name in SD_TABLES:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {name}")
            out["sdTables"][name] = int(cur.fetchone()[0])
        except Exception:
            out["sdTables"][name] = None
    # daysheet_totals / dashboard-like
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY 1")
    tables = [r[0] for r in cur.fetchall()]
    for tname in tables:
        low = tname.lower()
        if "daysheet" not in low and "dashboard" not in low and "period" not in low:
            continue
        try:
            cur.execute(f"PRAGMA table_info({tname})")
            cols = [r[1] for r in cur.fetchall()]
            pcol = next((c for c in cols if c.lower() in {"period", "year_month", "month", "ym"}), None)
            if not pcol:
                continue
            cur.execute(
                f"SELECT * FROM {tname} WHERE CAST({pcol} AS TEXT) LIKE ? ORDER BY 1 DESC LIMIT 1",
                ("%2026-07%",),
            )
            row = cur.fetchone()
            if row:
                sample = {k: row[i] for i, k in enumerate(cols)}
                # keep money-ish fields only
                keep = {
                    k: sample[k]
                    for k in cols
                    if any(
                        x in k.lower()
                        for x in (
                            "period",
                            "prod",
                            "coll",
                            "insur",
                            "patient",
                            "year",
                            "month",
                        )
                    )
                }
                out["julyDashboard"] = {"table": tname, "fields": keep}
                break
        except Exception:
            continue
    con.close()
    out["ok"] = any(isinstance(v, int) and v > 0 for v in out["sdTables"].values())
    return out


def _register_parse() -> dict[str, Any]:
    from softdent_practice_exports import parse_softdent_register_xls

    path = EXPORTS / "register_for_period_2026-07-01_2026-07-12.xls"
    if not path.is_file():
        # any july register xls
        cands = sorted(EXPORTS.glob("register_for_period_2026-07*.xls"))
        path = cands[-1] if cands else path
    if not path.is_file():
        return {"ok": False, "error": "july_register_xls_missing"}
    parsed = parse_softdent_register_xls(path)
    if not parsed:
        return {"ok": False, "error": "parse_failed", "path": str(path)}
    return {
        "ok": True,
        "path": str(path),
        "production": parsed.get("production"),
        "collections": parsed.get("collections"),
        "insPlanCollections": parsed.get("insPlanCollections"),
        "regularCollections": parsed.get("regularCollections"),
        "insuranceSplitReported": parsed.get("insuranceSplitReported"),
        "collectionsFormatRequired": parsed.get("collectionsFormatRequired"),
    }


def _widget_builders() -> dict[str, Any]:
    """Confirm key widget builders exist and what they read (static import check)."""
    checks: dict[str, Any] = {}
    try:
        from apex_softdent_hardening_pack import assess_collections_gap, collections_gap_widget

        checks["collections_gap"] = {
            "ok": True,
            "assess": callable(assess_collections_gap),
            "widget": callable(collections_gap_widget),
            "claimedSource": "desktop_excel + dashboard",
        }
    except Exception as exc:
        checks["collections_gap"] = {"ok": False, "error": type(exc).__name__}

    try:
        from apex_backend import build_collection_bullet, build_ins_patient_split, build_payer_donut

        checks["money_widgets"] = {
            "ok": True,
            "build_ins_patient_split": callable(build_ins_patient_split),
            "build_payer_donut": callable(build_payer_donut),
            "build_collection_bullet": callable(build_collection_bullet),
            "claimedSource": "analytics_db / inbox_csv",
        }
    except Exception as exc:
        checks["money_widgets"] = {"ok": False, "error": type(exc).__name__}

    try:
        from apex_financial_console_pack import build_dual_axis_trend

        checks["dual_trend"] = {"ok": True, "fn": callable(build_dual_axis_trend)}
    except Exception as exc:
        checks["dual_trend"] = {"ok": False, "error": type(exc).__name__}

    # Live gap assessment if bundle loadable
    try:
        from apex_backend import _load_reports_and_bundle
        from apex_softdent_hardening_pack import assess_collections_gap

        _reports, bundle, _err = _load_reports_and_bundle()
        gap = assess_collections_gap(bundle)
        dash = (bundle or {}).get("softdent") or {}
        dashboard = dash.get("dashboard") or {}
        rows = dashboard.get("rows") if isinstance(dashboard, dict) else None
        latest = None
        if isinstance(rows, list) and rows:
            latest = rows[-1] if isinstance(rows[-1], dict) else None
        elif isinstance(dashboard, dict):
            latest = dashboard.get("latest") if isinstance(dashboard.get("latest"), dict) else None
        checks["liveGap"] = {
            "ok": True,
            "gapCode": gap.get("gapCode") or gap.get("collectionsGapCode"),
            "coversOpenMonth": gap.get("coversOpenMonth"),
            "period": gap.get("period"),
            "collectionsFormatRequired": gap.get("collectionsFormatRequired"),
            "latestDashboardKeys": sorted(latest.keys())[:20] if isinstance(latest, dict) else None,
            "latestProduction": (latest or {}).get("production") if isinstance(latest, dict) else None,
            "latestCollections": (latest or {}).get("collections") if isinstance(latest, dict) else None,
        }
    except Exception as exc:
        checks["liveGap"] = {"ok": False, "error": f"{type(exc).__name__}:{exc}"}

    return checks


def _path_claims() -> list[dict[str, Any]]:
    """Validate each mapped claim with evidence."""
    inbox = _inbox_files()
    db = _db_snapshot()
    reg = _register_parse()
    widgets = _widget_builders()

    claims = []

    # Money path: desktop excel → parse
    claims.append(
        {
            "claim": "Period $ widgets ultimately depend on SoftDent desktop Excel Register in SoftDentReportExports",
            "expectedSource": "desktop_excel → analytics_db",
            "pass": bool(reg.get("ok")) and reg.get("production") is not None,
            "evidence": {
                "registerParse": reg,
                "inboxHasRegister": bool((inbox.get("kinds") or {}).get("registerXls")),
            },
        }
    )

    # DEF-001 / collections gap
    live = widgets.get("liveGap") or {}
    claims.append(
        {
            "claim": "Collections gap widget reads live bundle + inbox (desktop export path)",
            "expectedSource": "desktop_excel",
            "pass": bool(widgets.get("collections_gap", {}).get("ok")) and bool(live.get("ok")),
            "evidence": {"liveGap": live, "builder": widgets.get("collections_gap")},
        }
    )

    # Analytics dashboard for vital signs style data
    claims.append(
        {
            "claim": "Analytics DB / dashboard periods exist for July money KPIs (or gap explains missing)",
            "expectedSource": "analytics_db",
            "pass": bool(db.get("julyDashboard"))
            or bool(live.get("period"))
            or bool(live.get("gapCode")),
            "evidence": {
                "julyDashboard": db.get("julyDashboard"),
                "livePeriod": live.get("period"),
                "gapCode": live.get("gapCode"),
            },
        }
    )

    # Ops path sd_*
    sd_ok = any(isinstance(v, int) and v > 0 for v in (db.get("sdTables") or {}).values())
    claims.append(
        {
            "claim": "OM/schedule widgets can use sd_* (Sensei/ODBC lane) — tables populated",
            "expectedSource": "sd_sqlite",
            "pass": sd_ok,
            "evidence": {"sdTables": db.get("sdTables"), "odbcConfigured": db.get("odbcConfigured")},
        }
    )

    # Inbox CSV for claims/AR/aging
    kinds = inbox.get("kinds") or {}
    claims.append(
        {
            "claim": "Claims/AR/procedure-style widgets have SoftDent inbox CSV/exports available",
            "expectedSource": "inbox_csv",
            "pass": bool(kinds.get("aging") or kinds.get("transactions") or kinds.get("daysheet")),
            "evidence": {
                "aging": kinds.get("aging"),
                "transactions": kinds.get("transactions"),
                "daysheet": kinds.get("daysheet"),
            },
        }
    )

    # Money widgets builders exist
    claims.append(
        {
            "claim": "Ins/Patient, payer donut, collection bullet builders are wired",
            "expectedSource": "analytics_db / inbox_csv",
            "pass": bool((widgets.get("money_widgets") or {}).get("ok")),
            "evidence": widgets.get("money_widgets"),
        }
    )

    # Cross-check: Register Excel dollars match honesty (Ins Plan 0 → format required)
    if reg.get("ok"):
        honest = True
        if reg.get("insPlanCollections") == 0 and reg.get("collections"):
            honest = bool(reg.get("collectionsFormatRequired"))
        claims.append(
            {
                "claim": "Register Excel parse is honest (Ins Plan $0 ⇒ collectionsFormatRequired)",
                "expectedSource": "desktop_excel",
                "pass": honest,
                "evidence": {
                    "insPlan": reg.get("insPlanCollections"),
                    "collections": reg.get("collections"),
                    "collectionsFormatRequired": reg.get("collectionsFormatRequired"),
                },
            }
        )

    return claims


def main() -> int:
    inbox = _inbox_files()
    db = _db_snapshot()
    reg = _register_parse()
    widgets = _widget_builders()
    claims = _path_claims()
    passed = sum(1 for c in claims if c.get("pass"))
    payload = {
        "ok": passed == len(claims),
        "validatedAt": _utc(),
        "summary": {"passed": passed, "total": len(claims)},
        "inbox": inbox,
        "database": db,
        "registerExcel": reg,
        "widgets": widgets,
        "claims": claims,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"ok": payload["ok"], "summary": payload["summary"], "claims": [
        {"claim": c["claim"][:80], "pass": c["pass"]} for c in claims
    ]}, indent=2))
    print(f"Wrote {OUT}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
