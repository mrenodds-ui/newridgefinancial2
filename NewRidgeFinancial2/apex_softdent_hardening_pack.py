"""
Phase I2 — SoftDent Collections/Daysheet honesty (DEF-001).

Centralizes collections-gap detection so widgets, import health, and HAL
share one gap code — never invent collections dollars.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# Stable gap codes for UI / HAL / tests
GAP_OK = "OK"
GAP_COLLECTIONS_PENDING = "COLLECTIONS_PENDING"
GAP_COLLECTIONS_UNREPORTED = "COLLECTIONS_UNREPORTED"  # reported=false (past period)
GAP_DAYSHEET_ZERO = "COLLECTIONS_ZERO_ON_DAYSHEET"
GAP_REGISTER_ONLY = "REGISTER_ONLY"  # production without collections key
GAP_NO_PERIOD = "NO_PERIOD_ROW"

FIX_HINT = (
    "Import SoftDent daysheet / complete Register for a Period, then Sync "
    "(or ask HAL: refresh SoftDent period). Empty ≠ $0."
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _latest_period_from_bundle(bundle: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(bundle, dict):
        return None
    try:
        from apex_backend import _dashboard_rows, _latest_period_row

        return _latest_period_row(_dashboard_rows(bundle))
    except Exception:
        softdent = bundle.get("softdent") if isinstance(bundle.get("softdent"), dict) else {}
        dash = softdent.get("dashboard") if isinstance(softdent.get("dashboard"), dict) else {}
        rows = dash.get("rows") if isinstance(dash.get("rows"), list) else []
        for row in reversed(rows):
            if isinstance(row, dict) and (row.get("period") or row.get("year_month")):
                return row
        return None


def assess_collections_gap(bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Single source of truth for DEF-001 Collections/Daysheet gap.

    Returns gapCode, period, flags, fixHint, issues[] — never invents $.
    """
    latest = _latest_period_from_bundle(bundle)
    period = str((latest or {}).get("period") or (latest or {}).get("year_month") or "") or None
    issues: list[str] = []
    gap = GAP_NO_PERIOD
    pending = False
    reported: bool | None = None
    has_collections_key = False
    production = None
    collections = None

    if latest:
        pending = bool(latest.get("collectionsPending"))
        if "collectionsReported" in latest:
            reported = bool(latest.get("collectionsReported"))
        has_collections_key = "collections" in latest
        try:
            production = float(latest.get("production")) if latest.get("production") is not None else None
        except (TypeError, ValueError):
            production = None
        try:
            collections = float(latest.get("collections")) if has_collections_key else None
        except (TypeError, ValueError):
            collections = None

        if pending:
            gap = GAP_COLLECTIONS_PENDING
            issues.append(
                f"{period or 'latest'}: collectionsPending — daysheet/collections not reported for this period."
            )
        elif reported is False:
            gap = GAP_COLLECTIONS_UNREPORTED
            issues.append(
                f"{period or 'latest'}: collectionsReported=false — SoftDent closed period without collections."
            )
        elif production and production > 0 and not has_collections_key:
            gap = GAP_REGISTER_ONLY
            issues.append(
                f"{period or 'latest'}: production present without collections key (register-only view)."
            )
        elif (
            has_collections_key
            and collections is not None
            and collections <= 0
            and production
            and production > 0
        ):
            gap = GAP_DAYSHEET_ZERO
            issues.append(
                f"{period or 'latest'}: daysheet/collections present but collections are zero — rerun final daysheet."
            )
        else:
            gap = GAP_OK

    # Optional analytics-db diagnosis (extra issues; does not override gap from bundle)
    try:
        from softdent_dashboard_period_sync import diagnose_collections_gap, resolve_analytics_db

        diag = diagnose_collections_gap(resolve_analytics_db())
        for issue in (diag.get("issues") or [])[:8]:
            if issue not in issues:
                issues.append(str(issue))
    except Exception:
        pass

    healthy = gap == GAP_OK
    return {
        "ok": True,
        "gapCode": gap,
        "healthy": healthy,
        "period": period,
        "collectionsPending": pending,
        "collectionsReported": reported,
        "hasCollectionsKey": has_collections_key,
        "production": production,
        "collections": collections if gap == GAP_OK else None,  # never surface unverified $ as truth
        "honesty": "empty_not_zero" if not healthy else "reported",
        "fixHint": None if healthy else FIX_HINT,
        "issues": issues[:12],
        "def": "DEF-001",
        "checkedAt": _utc_now(),
    }


def collections_gap_widget(bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    gap = assess_collections_gap(bundle)
    healthy = bool(gap.get("healthy"))
    code = str(gap.get("gapCode") or GAP_NO_PERIOD)
    period = gap.get("period") or "—"
    if healthy:
        return {
            "id": "softdent-collections-gap",
            "type": "status",
            "label": "Collections Gap (DEF-001)",
            "size": "full",
            "status": "ok",
            "message": f"Collections reported · {period}",
            "hint": "SoftDent period has reported collections — revenue split may populate.",
            "gapCode": code,
            "gap": gap,
        }
    return {
        "id": "softdent-collections-gap",
        "type": "status",
        "label": "Collections Gap (DEF-001)",
        "size": "full",
        "status": "empty",
        "message": f"{code} · {period}",
        "emptyMessage": code,
        "hint": gap.get("fixHint") or FIX_HINT,
        "gapCode": code,
        "gap": gap,
        "halChips": [
            {"label": "Collections gap", "query": "Why are collections empty?"},
            {"label": "Refresh SoftDent period", "query": "Refresh SoftDent period imports"},
            {"label": "Sync imports", "query": "Sync imports and populate the widgets"},
        ],
    }


def enrich_widget_with_collections_gap(widget: dict[str, Any], gap: dict[str, Any] | None) -> dict[str, Any]:
    """Stamp gapCode / fixHint onto empty collection-related widgets."""
    if not isinstance(widget, dict) or not isinstance(gap, dict):
        return widget
    if gap.get("healthy"):
        return widget
    out = dict(widget)
    if out.get("status") == "empty" or out.get("value") is None:
        out.setdefault("gapCode", gap.get("gapCode"))
        out.setdefault("def", "DEF-001")
        hint = str(out.get("hint") or "")
        fix = str(gap.get("fixHint") or FIX_HINT)
        if "daysheet" not in hint.lower() and "pending" not in hint.lower():
            out["hint"] = f"{hint} · {fix}".strip(" ·") if hint else fix
        out.setdefault("emptyMessage", out.get("emptyMessage") or str(gap.get("gapCode")))
    return out


def import_health_collections_alert(bundle: dict[str, Any] | None = None) -> dict[str, Any] | None:
    gap = assess_collections_gap(bundle)
    if gap.get("healthy"):
        return None
    return {
        "id": "def-001-collections-gap",
        "severity": "warn",
        "message": f"DEF-001 {gap.get('gapCode')}: SoftDent collections/daysheet gap ({gap.get('period') or 'latest'})",
        "hint": gap.get("fixHint") or FIX_HINT,
        "halQuery": "Why are collections empty?",
        "gapCode": gap.get("gapCode"),
        "pending": gap.get("issues") or [],
    }


def format_collections_gap_reply(gap: dict[str, Any] | None = None) -> str:
    g = gap if isinstance(gap, dict) else {}
    if g.get("healthy"):
        return (
            f"Collections look reported for period `{g.get('period') or 'latest'}` "
            f"(gapCode={g.get('gapCode')}). Revenue split can populate from import — not invented."
        )
    issues = g.get("issues") if isinstance(g.get("issues"), list) else []
    lines = [
        f"DEF-001 SoftDent collections gap: `{g.get('gapCode')}` · period `{g.get('period') or '—'}`.",
        "Honesty: empty Collections is not $0.",
        str(g.get("fixHint") or FIX_HINT),
    ]
    for issue in issues[:5]:
        lines.append(f"- {issue}")
    return "\n".join(lines)
