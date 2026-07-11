"""Financial Executive Console — Moonshot Option A (hal-10430).

Consult: MOONSHOT_FINANCIAL_PRO_PRESENTATION_CONSULT_2026-07-10.md
Composite strips, conditional empty collapse, dual-axis trend, EBITDA station.
Import-backed only — never invents dollars.
"""

from __future__ import annotations

from typing import Any


def _parse_money(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("$", "")
    if not text or text in {"—", "-", "n/a", "N/A"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _dashboard_rows(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        from apex_backend import _dashboard_rows as _rows

        return _rows(bundle)
    except Exception:
        return []


def _latest_period_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    try:
        from apex_backend import _latest_period_row as _latest

        return _latest(rows)
    except Exception:
        return rows[-1] if rows else None


def _spark_from_rows(rows: list[dict[str, Any]], key: str) -> list[float]:
    try:
        from apex_backend import _spark_from_rows as _spark

        return _spark(rows, key)
    except Exception:
        out: list[float] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            v = _parse_money(row.get(key))
            if v is not None:
                out.append(float(v))
        return out


def build_morning_financial_brief(bundle: dict[str, Any], reports: dict[str, Any]) -> dict[str, Any]:
    """Proactive morning brief text + flags for command strip / HAL (FIN-004/001/007)."""
    diag = bundle.get("diagnostics") if isinstance(bundle.get("diagnostics"), dict) else {}
    summary = diag.get("summary") if isinstance(diag.get("summary"), dict) else {}
    connected = summary.get("connected")
    total = summary.get("total")
    missing = summary.get("missing")
    stale = summary.get("stale")
    loaded = str(bundle.get("loadedAt") or "").strip()

    rows = _dashboard_rows(bundle)
    latest = _latest_period_row(rows)
    period = ""
    collections_pending = False
    prod = None
    coll = None
    if latest:
        period = str(latest.get("period") or latest.get("year_month") or "")
        collections_pending = bool(
            latest.get("collectionsPending") or latest.get("collectionsReported") is False
        )
        prod = _parse_money(latest.get("production"))
        if not collections_pending and "collections" in latest:
            coll = _parse_money(latest.get("collections"))

    ar = reports.get("arAging") if isinstance(reports.get("arAging"), dict) else {}
    ar_total = ar.get("totalOutstanding")
    ninety = ar.get("ninetyPlusOutstanding")
    if not isinstance(ninety, (int, float)):
        ninety = None

    parts: list[str] = []
    if isinstance(connected, int) and isinstance(total, int) and total > 0:
        parts.append(f"Imports {connected}/{total}")
        if isinstance(missing, int) and missing:
            parts.append(f"{missing} missing")
        if isinstance(stale, int) and stale:
            parts.append(f"{stale} stale")
    else:
        parts.append("Imports unknown — run Sync")

    if prod is not None:
        parts.append(f"Production reported{f' ({period})' if period else ''}")
    if collections_pending:
        parts.append("Collections pending — export SoftDent Collections/Daysheet")
    elif coll is not None:
        parts.append("Collections reported")
    if isinstance(ar_total, (int, float)):
        ar_bit = f"A/R ${float(ar_total):,.0f}"
        if isinstance(ninety, (int, float)) and float(ninety) > 0:
            ar_bit += f" (90+ ${float(ninety):,.0f})"
        parts.append(ar_bit)

    # FIN-005: depreciation gap on EBITDA walk
    dep_missing = False
    try:
        from tax_engine import compute_ebitda_walk

        walk = compute_ebitda_walk(bundle) or {}
        missing_lines = walk.get("missing") if isinstance(walk.get("missing"), list) else []
        if any("deprec" in str(m).lower() for m in missing_lines):
            dep_missing = True
            parts.append("Import QB Fixed Asset / Depreciation for EBITDA add-back")
    except Exception:
        pass

    message = " · ".join(parts) if parts else "Financial brief unavailable"
    tone = "warn" if collections_pending or (isinstance(missing, int) and missing) or (
        isinstance(stale, int) and stale
    ) else "ok"
    actions: list[dict[str, str]] = []
    if collections_pending:
        actions.append(
            {
                "id": "refresh_softdent_period",
                "label": "Sync SoftDent Collections/Daysheet",
            }
        )
    if isinstance(stale, int) and stale:
        actions.append({"id": "sync_imports", "label": "Refresh imports"})
    if dep_missing:
        actions.append({"id": "focus_ebitda", "label": "Open EBITDA station"})

    return {
        "message": message,
        "tone": tone,
        "collectionsPending": collections_pending,
        "period": period,
        "production": prod,
        "collections": coll,
        "arTotal": float(ar_total) if isinstance(ar_total, (int, float)) else None,
        "ninetyPlus": float(ninety) if isinstance(ninety, (int, float)) else None,
        "loadedAt": loaded,
        "depreciationMissing": dep_missing,
        "actions": actions,
        "hint": "At-a-glance from SoftDent/QB import diagnostics — not a bank forecast.",
    }


def build_financial_command_strip(bundle: dict[str, Any], reports: dict[str, Any]) -> dict[str, Any]:
    """Strip 1: Import health + period chips + morning brief (FIN-003/007)."""
    from apex_backend import build_import_freshness, build_period_scrubber

    freshness = build_import_freshness(bundle)
    scrubber = build_period_scrubber(bundle, page="financial")
    brief = build_morning_financial_brief(bundle, reports)

    import_status = str(freshness.get("status") or "empty")
    periods = scrubber.get("periods") if isinstance(scrubber.get("periods"), list) else []
    active = str(scrubber.get("active") or "")

    return {
        "id": "financial-command-strip",
        "type": "financial-command-strip",
        "label": "Financial Command",
        "size": "strip",
        "compact": True,
        "importMessage": freshness.get("message") or "Imports unknown",
        "importStatus": import_status,
        "importHint": freshness.get("hint") or "",
        "periods": periods,
        "activePeriod": active,
        "briefMessage": brief.get("message") or "",
        "briefTone": brief.get("tone") or "ok",
        "briefActions": brief.get("actions") or [],
        "collectionsPending": bool(brief.get("collectionsPending")),
        "status": "ok" if import_status == "ok" or periods else "empty",
        "emptyMessage": "Run Apex Sync to verify SoftDent + QuickBooks",
        "hint": brief.get("hint") or freshness.get("hint") or "",
        "aliasIds": [
            "import-freshness",
            "financial-period-scrubber",
            "morning-brief",
        ],
        "loadedAt": brief.get("loadedAt") or "",
    }


def build_financial_vital_signs(reports: dict[str, Any], bundle: dict[str, Any]) -> dict[str, Any]:
    """Strip 2: Production / Collections / A/R / Efficiency — dense exec pills."""
    from apex_backend import build_collection_bullet

    rows = _dashboard_rows(bundle)
    latest = _latest_period_row(rows)
    period = ""
    prod = None
    coll = None
    coll_pending = False
    if latest:
        period = str(latest.get("period") or latest.get("year_month") or "")
        prod = _parse_money(latest.get("production"))
        coll_pending = bool(
            latest.get("collectionsPending") or latest.get("collectionsReported") is False
        )
        if not coll_pending and "collections" in latest:
            coll = _parse_money(latest.get("collections"))

    ar = reports.get("arAging") if isinstance(reports.get("arAging"), dict) else {}
    ar_total = ar.get("totalOutstanding")
    ninety_pct = ar.get("ninetyPlusPct")

    bullet = build_collection_bullet(bundle)
    eff = bullet.get("value") if bullet.get("status") == "ok" else None

    pills = [
        {
            "id": "prod-mtd",
            "label": "Production",
            "value": prod,
            "format": "money",
            "tone": "success",
            "empty": prod is None,
            "sub": period or "",
        },
        {
            "id": "collections-mtd",
            "label": "Collections",
            "value": coll,
            "format": "money",
            "tone": "warning" if coll_pending else "success",
            "empty": coll is None,
            "pending": coll_pending,
            "sub": "Pending — sync Daysheet" if coll_pending else (period or ""),
        },
        {
            "id": "ar-outstanding",
            "label": "A/R Outstanding",
            "value": float(ar_total) if isinstance(ar_total, (int, float)) else None,
            "format": "money",
            "tone": "danger"
            if isinstance(ninety_pct, (int, float)) and float(ninety_pct) > 20
            else "",
            "empty": not isinstance(ar_total, (int, float)),
            "sub": f"90+ {float(ninety_pct):.0f}%"
            if isinstance(ninety_pct, (int, float))
            else "",
        },
        {
            "id": "collection-bullet",
            "label": "Efficiency",
            "value": eff,
            "format": "pct_points",
            "tone": "success" if isinstance(eff, (int, float)) and float(eff) >= 85 else "warning",
            "empty": eff is None,
            "sub": bullet.get("hint", "")[:48] if eff is None else "",
        },
    ]
    any_data = any(not p.get("empty") for p in pills)
    return {
        "id": "financial-vital-signs",
        "type": "executive-strip",
        "label": "Vital Signs",
        "size": "strip",
        "pills": pills,
        "status": "ok" if any_data else "empty",
        "emptyMessage": "Import SoftDent dashboard for vital signs",
        "hint": "Dense financial vitals · never invents dollars.",
        "aliasIds": ["prod-mtd", "collections-mtd", "ar-outstanding", "collection-bullet"],
    }


def build_revenue_composition(bundle: dict[str, Any]) -> dict[str, Any]:
    """Strip 4: Ins/Patient + Payer Mix, or compact action card when empty (FIN-002)."""
    from apex_backend import build_ins_patient_split, build_payer_donut

    split = build_ins_patient_split(bundle)
    donut = build_payer_donut(bundle)
    segs = split.get("segments") if isinstance(split.get("segments"), list) else []
    slices = donut.get("slices") if isinstance(donut.get("slices"), list) else []
    has_split = split.get("status") == "ok" and len(segs) >= 2
    has_donut = donut.get("status") == "ok" and len(slices) >= 1

    if has_split or has_donut:
        return {
            "id": "revenue-composition",
            "type": "revenue-composition",
            "label": "Revenue Composition",
            "size": "l",
            "segments": segs if has_split else [],
            "slices": slices if has_donut else [],
            "unit": donut.get("unit") or "money",
            "status": "ok",
            "hint": "Insurance/patient + payer mix from SoftDent — not invented.",
            "aliasIds": ["ins-patient-split", "payer-donut"],
        }

    # Compact empty action card — not a 300px tombstone
    pending = "collectionsPending" in str(split.get("emptyMessage") or "") or "pending" in str(
        split.get("hint") or ""
    ).lower()
    return {
        "id": "revenue-composition",
        "type": "revenue-composition",
        "label": "Revenue Composition",
        "size": "strip",
        "collapseWhenEmpty": True,
        "segments": [],
        "slices": [],
        "status": "empty",
        "emptyMessage": "Collections/Daysheet export needed for revenue split",
        "hint": split.get("hint") or donut.get("hint") or "",
        "halAction": "refresh_softdent_period",
        "halActionLabel": "Sync SoftDent Collections",
        "collectionsPending": pending,
        "aliasIds": ["ins-patient-split", "payer-donut"],
    }


def build_dual_axis_trend(bundle: dict[str, Any]) -> dict[str, Any]:
    """Strip 3 left: Production + Collections dual series (FIN-006)."""
    rows = _dashboard_rows(bundle)
    prod_vals = _spark_from_rows(rows, "production")
    coll_vals: list[float] = []
    labels: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        lab = str(row.get("period") or row.get("year_month") or "")[:7]
        if lab:
            labels.append(lab)
        if row.get("collectionsReported") is False or row.get("collectionsPending") is True:
            continue
        if "collections" not in row:
            continue
        v = _parse_money(row.get("collections"))
        if v is not None:
            coll_vals.append(float(v))

    # Align labels to production spark length
    if not labels and prod_vals:
        labels = [f"P{i + 1}" for i in range(len(prod_vals))]
    if len(labels) > len(prod_vals) and prod_vals:
        labels = labels[-len(prod_vals) :]
    elif len(labels) < len(prod_vals):
        labels = [f"P{i + 1}" for i in range(len(prod_vals))]

    series_prod = [
        {"label": labels[i] if i < len(labels) else f"P{i + 1}", "value": float(v)}
        for i, v in enumerate(prod_vals)
    ]
    series_coll = [
        {"label": labels[i] if i < len(labels) else f"P{i + 1}", "value": float(v)}
        for i, v in enumerate(coll_vals[-len(prod_vals) :] if prod_vals else coll_vals)
    ]

    if len(series_prod) < 2 and len(series_coll) < 2:
        return {
            "id": "financial-dual-trend",
            "type": "dual-axis-trend",
            "label": "Production & Collections Trend",
            "size": "m",
            "collapseWhenEmpty": True,
            "production": [],
            "collections": [],
            "status": "empty",
            "emptyMessage": "Need ≥2 SoftDent dashboard periods",
            "hint": "Import SoftDent dashboard periods for dual-axis trend.",
            "aliasIds": ["prod-trend", "liquidity-pulse"],
        }

    return {
        "id": "financial-dual-trend",
        "type": "dual-axis-trend",
        "label": "Production & Collections Trend",
        "size": "m",
        "production": series_prod,
        "collections": series_coll,
        "status": "ok",
        "hint": "Solid = production · dashed = collections (when reported). SoftDent dashboard only.",
        "aliasIds": ["prod-trend", "liquidity-pulse"],
    }


def build_ebitda_station(bundle: dict[str, Any]) -> dict[str, Any]:
    """Strip 6: Waterfall + scrubber + trend header (Phase 4)."""
    from apex_backend import build_ebitda_scrubber, build_ebitda_waterfall

    waterfall = build_ebitda_waterfall(bundle)
    scrubber = build_ebitda_scrubber(bundle)
    trend_series: list[dict[str, Any]] = []
    try:
        from apex_program_improve_pack import build_ebitda_trend_widget

        trend = build_ebitda_trend_widget(bundle)
        raw = trend.get("series") if isinstance(trend.get("series"), list) else []
        trend_series = [s for s in raw if isinstance(s, dict)]
    except Exception:
        trend_series = []

    steps = waterfall.get("steps") if isinstance(waterfall.get("steps"), list) else []
    available = waterfall.get("status") == "ok" and bool(steps)
    missing_dep = "deprec" in str(waterfall.get("hint") or "").lower()

    return {
        "id": "ebitda-station",
        "type": "ebitda-station",
        "label": "EBITDA Command Station",
        "size": "full",
        "steps": steps,
        "value": waterfall.get("value"),
        "showCitations": bool(waterfall.get("showCitations")),
        "bookNetIncome": scrubber.get("bookNetIncome"),
        "bookEbitda": scrubber.get("bookEbitda"),
        "planningEbitda": scrubber.get("planningEbitda"),
        "scrubber": scrubber.get("scrubber") or {},
        "periodLabel": scrubber.get("periodLabel") or "",
        "locked": bool(scrubber.get("locked")),
        "disclaimer": scrubber.get("disclaimer")
        or "PLANNING ONLY — NOT BOOKED TO QUICKBOOKS. CPA review required.",
        "trend": trend_series[-12:],
        "status": "ok" if available else "empty",
        "emptyMessage": waterfall.get("emptyMessage") or scrubber.get("emptyMessage") or "Need QB net income",
        "hint": str(waterfall.get("hint") or scrubber.get("hint") or "")
        + (
            " · Import QB Fixed Asset Report for depreciation add-back."
            if missing_dep
            else ""
        ),
        "depreciationMissing": missing_dep,
        "aliasIds": ["ebitda-waterfall", "ebitda-scrubber", "ebitda-trend"],
    }


def collapse_empty_large(widget: dict[str, Any]) -> dict[str, Any]:
    """FIN-002: empty l/xl widgets become strip-sized compact cards."""
    if not isinstance(widget, dict):
        return widget
    if widget.get("status") != "empty":
        return widget
    size = str(widget.get("size") or "")
    if size not in {"l", "xl", "full", "large"}:
        return widget
    if widget.get("collapseWhenEmpty") is False:
        return widget
    out = dict(widget)
    out["collapseWhenEmpty"] = True
    out["size"] = "strip"
    out["compact"] = True
    return out


def format_hal_morning_financial_reply(brief: dict[str, Any]) -> str:
    """HAL reply for morning financial brief / why widgets empty."""
    msg = str(brief.get("message") or "No brief available.")
    lines = [f"Morning Financial Brief: {msg}"]
    if brief.get("collectionsPending"):
        lines.append(
            "Action: Export SoftDent Collections/Daysheet for the current period to "
            "C:\\SoftDentReportExports, then ask HAL to refresh SoftDent period imports. "
            "That unblocks Collections MTD, Insurance vs Patient, and Payer Mix."
        )
    if brief.get("depreciationMissing"):
        lines.append(
            "EBITDA tip: Import QuickBooks Fixed Asset / Depreciation so the add-back is not blank."
        )
    actions = brief.get("actions") if isinstance(brief.get("actions"), list) else []
    if actions:
        lines.append("Suggested: " + "; ".join(str(a.get("label") or a.get("id")) for a in actions))
    lines.append("Honesty: no invented dollars — empty widgets stay empty until imports report real values.")
    return " ".join(lines)
