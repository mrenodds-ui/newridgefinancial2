"""NR2 Apex subpages — Phase 1 drill-downs + Phase 2 workflow benches.

CONSULT: MOONSHOT_SUBPAGES_EXPAND_CONSULT_2026-07-11.md
Honesty: never invent dollars; PHI-safe patient initials; local SQLite only for notes/tasks.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def patient_initials(name: str | None) -> str:
    """PHI-safe display: initials only (Last, First → F.L. / First Last → F.L.)."""
    raw = str(name or "").strip()
    if not raw or raw == "—":
        return "—"
    if "," in raw:
        parts = [p.strip() for p in raw.split(",", 1)]
        last = parts[0]
        first = parts[1] if len(parts) > 1 else ""
        fi = (first[:1] + ".") if first else ""
        li = (last[:1] + ".") if last else ""
        out = f"{fi}{li}"
        return out if out.replace(".", "") else "—"
    tokens = [t for t in raw.split() if t]
    if len(tokens) >= 2:
        return f"{tokens[0][:1]}.{tokens[-1][:1]}."
    return f"{tokens[0][:1]}." if tokens else "—"


def _parse_money(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace("$", "").replace(",", ""))
    except (TypeError, ValueError):
        return None


def _section_rows(bundle: dict[str, Any], system: str, key: str) -> list[dict[str, Any]]:
    sys = bundle.get(system) if isinstance(bundle.get(system), dict) else {}
    sec = sys.get(key) if isinstance(sys.get(key), dict) else {}
    rows = sec.get("rows") if isinstance(sec.get("rows"), list) else None
    if rows is None:
        rows = sec.get("data") if isinstance(sec.get("data"), list) else []
    return [r for r in rows if isinstance(r, dict)]


def build_financial_workpapers(
    reports: dict[str, Any],
    bundle: dict[str, Any],
    *,
    workpaper_widget: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]] | None = None,
    variance_widget: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """FIN-WP: CPA workpaper drill-down with citation categories (import-backed only)."""
    del reports
    widgets: list[dict[str, Any]] = []

    try:
        from tax_engine import build_tax_plan_from_bundle

        plan = build_tax_plan_from_bundle(bundle) or {}
    except Exception:
        plan = {}

    has_book = bool(plan.get("hasBookData"))
    widgets.append(
        {
            "id": "subpage-fin-wp-nav",
            "type": "status",
            "label": "Financial · Workpapers",
            "size": "strip",
            "status": "ok",
            "message": "Drill-down from Executive Console · Back via Overview",
            "hint": "Hash route #financial/workpapers — citations from QB/SoftDent imports only.",
        }
    )

    categories: list[dict[str, Any]] = []
    rows = _section_rows(bundle, "quickbooks", "expenseCategories")
    for row in rows:
        name = str(row.get("Category") or row.get("Account") or row.get("Name") or "").strip()
        if not name:
            continue
        amt = _parse_money(row.get("Amount") or row.get("amount") or row.get("Total"))
        categories.append(
            {
                "id": name.lower().replace(" ", "-")[:48],
                "label": name[:60],
                "amount": amt,
                "citation": "QB expenseCategories",
                "flaggable": True,
            }
        )
    categories.sort(key=lambda c: float(c["amount"] or 0), reverse=True)
    categories = categories[:24]

    bridge = plan.get("bridgeLines") if isinstance(plan.get("bridgeLines"), list) else []
    for line in bridge:
        if not isinstance(line, dict):
            continue
        lab = str(line.get("line") or "").strip()
        if not lab:
            continue
        amt_f = _parse_money(line.get("amount"))
        categories.insert(
            0,
            {
                "id": f"bridge-{lab.lower().replace(' ', '-')[:40]}",
                "label": lab[:60],
                "amount": amt_f,
                "citation": "tax_engine book-to-tax (planning)",
                "flaggable": True,
            },
        )

    widgets.append(
        {
            "id": "workpaper-scrubber",
            "type": "workpaper-scrubber",
            "label": "Workpaper Categories",
            "size": "full",
            "status": "ok" if categories else "empty",
            "emptyMessage": "No QB categories or bridge lines — import QuickBooks P&L",
            "categories": categories,
            "hint": "Import-backed lines only. Flag for CPA is local session — never invents dollars.",
        }
    )

    if workpaper_widget:
        try:
            widgets.append(workpaper_widget(plan, bundle))
        except Exception:
            pass
    else:
        widgets.append(
            {
                "id": "cpa-workpaper",
                "type": "workpaper",
                "label": "CPA Workpaper Export",
                "size": "l",
                "status": "ok" if has_book else "empty",
                "emptyMessage": "Need QB book income",
                "exportUrl": "/api/apex/workpapers/generate",
                "hint": "Printable workpaper with book-to-tax + EBITDA citations.",
            }
        )

    if variance_widget:
        try:
            widgets.append(variance_widget(bundle))
        except Exception:
            pass

    return widgets


def build_provider_view(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """FIN-PRO: Provider production detail from SoftDent procedures."""
    del reports
    widgets: list[dict[str, Any]] = [
        {
            "id": "subpage-fin-pro-nav",
            "type": "status",
            "label": "Financial · Providers",
            "size": "strip",
            "status": "ok",
            "message": "Provider production from SoftDent procedures",
            "hint": "Hash route #financial/providers — honest empty when Provider field missing.",
        }
    ]

    rows = _section_rows(bundle, "softdent", "procedures")
    totals: dict[str, float] = {}
    counts: dict[str, int] = {}
    for row in rows:
        prov = str(row.get("Provider") or row.get("provider") or row.get("Doctor") or "").strip()
        if not prov:
            continue
        amt = _parse_money(row.get("Production") or row.get("Amount") or row.get("Fee") or row.get("Total"))
        if amt is None:
            continue
        totals[prov] = totals.get(prov, 0.0) + float(amt)
        counts[prov] = counts.get(prov, 0) + 1

    bars = [
        {"label": k[:40], "value": v, "meta": f"{counts.get(k, 0)} tx"}
        for k, v in sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:16]
    ]

    if not bars:
        widgets.append(
            {
                "id": "provider-metric-bars",
                "type": "horizontal-bar",
                "label": "Provider Production",
                "size": "l",
                "bars": [],
                "status": "empty",
                "emptyMessage": "No provider breakdown available",
                "hint": "Import SoftDent procedures with Provider + Production to populate.",
            }
        )
        widgets.append(
            {
                "id": "provider-count-kpi",
                "type": "kpi",
                "label": "Providers",
                "size": "s",
                "value": None,
                "status": "empty",
                "emptyMessage": "—",
                "hint": "Awaiting SoftDent provider field.",
            }
        )
        return widgets

    widgets.append(
        {
            "id": "provider-metric-bars",
            "type": "horizontal-bar",
            "label": "Provider Production",
            "size": "xl",
            "bars": bars,
            "status": "ok",
            "hint": "Aggregated SoftDent procedure Production by Provider (top 16).",
        }
    )
    widgets.append(
        {
            "id": "provider-count-kpi",
            "type": "kpi",
            "label": "Providers",
            "size": "s",
            "value": len(totals),
            "status": "ok",
            "hint": f"Distinct providers with production in import · {len(rows)} procedure rows scanned.",
        }
    )
    top = bars[0]
    widgets.append(
        {
            "id": "provider-top-kpi",
            "type": "kpi",
            "label": "Top provider",
            "size": "s",
            "value": top.get("value"),
            "format": "money",
            "status": "ok",
            "deltaLabel": str(top.get("label") or "")[:28],
            "hint": "Highest SoftDent production total in current import.",
        }
    )
    return widgets


def build_claim_detail(
    reports: dict[str, Any],
    bundle: dict[str, Any],
    *,
    claim_id: str | None = None,
) -> list[dict[str, Any]]:
    """CLM-DET: Individual claim detail mosaic (PHI-safe initials)."""
    del reports
    cid = str(claim_id or "").strip()
    widgets: list[dict[str, Any]] = [
        {
            "id": "subpage-clm-det-nav",
            "type": "status",
            "label": "Claims · Detail",
            "size": "strip",
            "status": "ok",
            "message": f"Claim {cid}" if cid else "Select a claim from the workbench",
            "hint": "Hash route #claims/detail?id=… · patient shown as initials only.",
        }
    ]

    if not cid:
        widgets.append(
            {
                "id": "claim-detail-card",
                "type": "claim-detail-card",
                "label": "Claim Detail",
                "size": "full",
                "status": "empty",
                "emptyMessage": "No claim selected — open a card from Claims workbench",
                "hint": "Click a claim tile/row to open this subpage.",
                "claim": None,
            }
        )
        return widgets

    try:
        from apex_claims_narratives_pack import find_claim_by_id

        rows = _section_rows(bundle, "softdent", "claims") or _section_rows(bundle, "softdent", "claimStatus")
        claim = find_claim_by_id(rows, cid)
    except Exception:
        claim = None

    if not claim:
        widgets.append(
            {
                "id": "claim-detail-card",
                "type": "claim-detail-card",
                "label": "Claim Detail",
                "size": "full",
                "status": "empty",
                "emptyMessage": "Claim not found in SoftDent import",
                "hint": "Sync SoftDent claims, then reopen from the workbench.",
                "claimId": cid,
                "claim": None,
            }
        )
        return widgets

    safe = dict(claim)
    safe["patientInitials"] = patient_initials(str(safe.get("patientName") or ""))
    safe["patientName"] = safe["patientInitials"]

    widgets.append(
        {
            "id": "claim-detail-card",
            "type": "claim-detail-card",
            "label": "Claim Detail",
            "size": "full",
            "status": "ok",
            "claimId": safe.get("claimId") or cid,
            "claim": safe,
            "hint": "Source: SoftDent import · patient initials only · never invented.",
        }
    )
    billed = safe.get("billedAmount")
    widgets.append(
        {
            "id": "claim-detail-billed",
            "type": "kpi",
            "label": "Billed",
            "size": "s",
            "value": billed if isinstance(billed, (int, float)) else None,
            "format": "money",
            "status": "ok" if isinstance(billed, (int, float)) else "empty",
            "emptyMessage": "— (not on import)",
            "hint": "Import field only.",
        }
    )
    age = safe.get("ageDays")
    widgets.append(
        {
            "id": "claim-detail-age",
            "type": "kpi",
            "label": "Age (days)",
            "size": "s",
            "value": age if isinstance(age, int) else None,
            "status": "ok" if isinstance(age, int) else "empty",
            "emptyMessage": "—",
            "hint": "Computed from service date on import.",
        }
    )
    return widgets


def build_collections_workbench(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """AR-COL: Active collection task workbench (local notes + SoftDent A/R/claims)."""
    del reports
    widgets: list[dict[str, Any]] = [
        {
            "id": "subpage-ar-col-nav",
            "type": "status",
            "label": "A/R · Collections",
            "size": "strip",
            "status": "ok",
            "message": "Local collection notes · SoftDent aging seeds · never invents $",
            "hint": "Hash route #ar/collections — notes stay in local SQLite only.",
        }
    ]

    try:
        from apex_claims_narratives_pack import build_aging_buckets, normalize_claim_row

        rows = _section_rows(bundle, "softdent", "claims") or _section_rows(bundle, "softdent", "claimStatus")
        aging = build_aging_buckets(rows)
        seeds: list[dict[str, Any]] = []
        for bucket_key in ("90", "60", "30"):
            tiles = (aging.get("buckets") or {}).get(bucket_key) or []
            if not isinstance(tiles, list):
                continue
            for tile in tiles[:12]:
                if not isinstance(tile, dict):
                    continue
                seeds.append(
                    {
                        "claimId": tile.get("claimId"),
                        "patientInitials": patient_initials(str(tile.get("patientName") or "")),
                        "ageDays": tile.get("ageDays"),
                        "bucket": bucket_key,
                        "payer": tile.get("payer"),
                        "status": "suggested",
                        "billedAmount": tile.get("billedAmount"),
                    }
                )
        if not seeds:
            for row in rows[:20]:
                tile = normalize_claim_row(row)
                if not tile:
                    continue
                seeds.append(
                    {
                        "claimId": tile.get("claimId"),
                        "patientInitials": patient_initials(str(tile.get("patientName") or "")),
                        "ageDays": tile.get("ageDays"),
                        "bucket": tile.get("bucket"),
                        "payer": tile.get("payer"),
                        "status": "suggested",
                        "billedAmount": tile.get("billedAmount"),
                    }
                )
    except Exception:
        seeds = []

    try:
        from nr2_local_db import list_collection_notes

        notes = list_collection_notes(limit=100)
    except Exception:
        notes = []

    widgets.append(
        {
            "id": "collection-task-list",
            "type": "collection-task-list",
            "label": "Collections Workbench",
            "size": "full",
            "status": "ok" if (seeds or notes) else "empty",
            "emptyMessage": "No aged claims or local notes — import SoftDent claims/A/R",
            "seeds": seeds[:40],
            "notes": notes,
            "hint": "Statuses: called / promised / disputed · local SQLite only · PHI = initials.",
        }
    )
    return widgets


def build_huddle_dashboard(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """OM-HUD: Daily huddle command dashboard + local history/tasks."""
    widgets: list[dict[str, Any]] = [
        {
            "id": "subpage-om-hud-nav",
            "type": "status",
            "label": "Office Mgr · Huddle",
            "size": "strip",
            "status": "ok",
            "message": "Morning command center",
            "hint": "Hash route #office-manager/huddle — priorities import-backed; history local.",
        }
    ]

    try:
        from apex_program_improve_pack import build_daily_huddle_widget

        huddle = build_daily_huddle_widget(reports, bundle)
        huddle = dict(huddle)
        huddle["id"] = "huddle-mosaic"
        huddle["type"] = "huddle-mosaic"
        huddle["label"] = "Daily Huddle Mosaic"
    except Exception:
        huddle = {
            "id": "huddle-mosaic",
            "type": "huddle-mosaic",
            "label": "Daily Huddle Mosaic",
            "size": "full",
            "priorities": ["Import health unavailable"],
            "status": "empty",
            "emptyMessage": "Unable to build huddle priorities",
            "hint": "Check SoftDent/QB imports.",
        }

    try:
        from nr2_local_db import list_huddle_history, list_tasks

        history = list_huddle_history(limit=5)
        tasks = list_tasks(include_done=False, limit=20)
    except Exception:
        history = []
        tasks = []

    huddle["history"] = history
    huddle["tasks"] = tasks
    widgets.append(huddle)
    widgets.append(
        {
            "id": "huddle-task-strip",
            "type": "status",
            "label": "Open office tasks",
            "size": "m",
            "status": "ok" if tasks else "empty",
            "message": f"{len(tasks)} open" if tasks else "No open tasks",
            "hint": "Tasks stored in local SQLite (nr2_local.sqlite3) — never leaves localhost.",
        }
    )
    return widgets


def build_batch_narrative(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """CLM-BAT: Multi-select denied/open claims for bulk narrative generation."""
    del reports
    widgets: list[dict[str, Any]] = [
        {
            "id": "subpage-clm-bat-nav",
            "type": "status",
            "label": "Claims · Batch",
            "size": "strip",
            "status": "ok",
            "message": "Select denied/open claims for batch narratives",
            "hint": "Hash route #claims/batch — seeds Narratives; no invented clinical text.",
        }
    ]

    candidates: list[dict[str, Any]] = []
    try:
        from apex_claims_narratives_pack import normalize_claim_row

        rows = _section_rows(bundle, "softdent", "claims") or _section_rows(bundle, "softdent", "claimStatus")
        for row in rows:
            tile = normalize_claim_row(row)
            if not tile:
                continue
            status = str(tile.get("status") or "").lower()
            age = tile.get("ageDays")
            risky = "den" in status or "reject" in status or (isinstance(age, int) and age >= 60)
            if not risky and "open" not in status and "pend" not in status:
                continue
            candidates.append(
                {
                    "claimId": tile.get("claimId"),
                    "patientInitials": patient_initials(str(tile.get("patientName") or "")),
                    "payer": tile.get("payer"),
                    "status": tile.get("status"),
                    "ageDays": age,
                    "billedAmount": tile.get("billedAmount"),
                }
            )
        candidates.sort(key=lambda c: (-(c.get("ageDays") if isinstance(c.get("ageDays"), int) else -1)))
        candidates = candidates[:80]
    except Exception:
        candidates = []

    widgets.append(
        {
            "id": "batch-selector",
            "type": "batch-selector",
            "label": "Batch Narrative Selector",
            "size": "full",
            "status": "ok" if candidates else "empty",
            "emptyMessage": "No denied/open aged claims in SoftDent import",
            "candidates": candidates,
            "hint": "Multi-select → Seed Narratives workspace. Patient initials only.",
        }
    )
    return widgets


def build_claim_docs(
    reports: dict[str, Any],
    bundle: dict[str, Any],
    *,
    claim_id: str | None = None,
) -> list[dict[str, Any]]:
    """DOC-CLM: Claim-centric document repository with attachment dropzone."""
    del reports, bundle
    cid = str(claim_id or "").strip() or None
    widgets: list[dict[str, Any]] = [
        {
            "id": "subpage-doc-clm-nav",
            "type": "status",
            "label": "Documents · Claim Docs",
            "size": "strip",
            "status": "ok",
            "message": f"Claim {cid}" if cid else "Upload / browse claim attachments",
            "hint": "Hash #documents/claim-docs?id=… · PDF/PNG/JPG · max 10MB · local app_data/nr2/claim_attachments.",
        }
    ]
    try:
        from apex_program_improve_pack import list_claim_attachments
        from document_sync import NR2_DATA_DIR

        items = list_claim_attachments(cid)
        storage = str(Path(NR2_DATA_DIR) / "claim_attachments").replace("\\", "/")
    except Exception:
        items = []
        storage = "app_data/nr2/claim_attachments"

    widgets.append(
        {
            "id": "attachment-dropzone",
            "type": "attachment-dropzone",
            "label": "Claim Attachment Dropzone",
            "size": "full",
            "status": "ok" if items else "empty",
            "emptyMessage": "No attachments yet — drop PDF/PNG/JPG (≤10MB)",
            "claimId": cid or "",
            "items": items[:50],
            "allowedTypes": [".pdf", ".png", ".jpg", ".jpeg"],
            "maxBytes": 10 * 1024 * 1024,
            "storageRoot": storage,
            "hint": "Local only · content sniff (PDF/PNG/JPEG) · not a full antivirus scan.",
        }
    )
    return widgets


def build_payer_library(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """LIB-PAY: Payer guidelines library (manual entry, local SQLite)."""
    del reports, bundle
    widgets: list[dict[str, Any]] = [
        {
            "id": "subpage-lib-pay-nav",
            "type": "status",
            "label": "Library · Payers",
            "size": "strip",
            "status": "ok",
            "message": "Manual payer guidelines (local only)",
            "hint": "Hash #library/payers — appeal deadlines / contacts / notes. No cloud sync.",
        }
    ]
    try:
        from nr2_local_db import list_payer_guidelines

        payers = list_payer_guidelines(limit=100)
    except Exception:
        payers = []

    widgets.append(
        {
            "id": "payer-reference-card",
            "type": "payer-reference-card",
            "label": "Payer Reference Library",
            "size": "full",
            "status": "ok" if payers else "empty",
            "emptyMessage": "No payer guidelines yet — add Delta, MetLife, etc.",
            "payers": payers,
            "hint": "Manual entry only · stored in nr2_local.sqlite3.",
        }
    )
    return widgets


def build_claims_era(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """CLM-ERA: ERA 835 matching table — live when matches exist; awaiting otherwise."""
    del reports, bundle
    widgets: list[dict[str, Any]] = [
        {
            "id": "subpage-clm-era-nav",
            "type": "status",
            "label": "Claims · ERA",
            "size": "strip",
            "status": "ok",
            "message": "ERA 835 match workbench",
            "hint": "Hash #claims/era · IMP-004 parser · upload .835/.txt · never invents remits.",
        }
    ]
    try:
        from apex_program_improve_pack import STORE_KEY_ERA_MATCHES, era_matches_map, _load_json

        matches_map = era_matches_map()
        store = _load_json(STORE_KEY_ERA_MATCHES)
        history = store.get("history") if isinstance(store.get("history"), list) else []
    except Exception:
        matches_map = {}
        history = []

    rows: list[dict[str, Any]] = []
    for cid, m in sorted(matches_map.items(), key=lambda kv: str(kv[0])):
        if not isinstance(m, dict):
            continue
        rows.append(
            {
                "claimId": cid,
                "patientInitials": patient_initials(str(m.get("patientName") or "")),
                "confidence": m.get("confidence"),
                "paidAmount": m.get("paidAmount"),
                "denialCode": m.get("denialCode"),
                "matchedAt": m.get("matchedAt"),
                "sourceFile": m.get("sourceFile"),
            }
        )

    widgets.append(
        {
            "id": "era-matching-table",
            "type": "era-matching-table",
            "label": "ERA Matching Table",
            "size": "full",
            "status": "ok" if rows else "empty",
            "emptyMessage": "Awaiting ERA 835 Pipeline — upload an 835/ERA file to match claims",
            "blocked": not bool(rows),
            "blockedReason": "IMP-004 ERA 835 — ingest required" if not rows else None,
            "rows": rows[:100],
            "history": history[-10:],
            "hint": (
                "Matches from local ERA ingest (confidence ≥0.55). "
                "Patient shown as initials only. No invented remittance dollars."
            ),
        }
    )
    return widgets


def build_ar_forecast_subpage(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """AR-FOR: A/R forecast trend — ERA velocity when matches exist; else honest blocked."""
    del bundle
    widgets: list[dict[str, Any]] = [
        {
            "id": "subpage-ar-for-nav",
            "type": "status",
            "label": "A/R · Forecast",
            "size": "strip",
            "status": "ok",
            "message": "Payer-velocity forecast (ERA-backed when available)",
            "hint": "Hash #ar/forecast · blocked without ERA 835 matches (IMP-004).",
        }
    ]
    try:
        from apex_program_improve_pack import STORE_KEY_ERA_MATCHES, era_matches_map, _load_json

        era = era_matches_map()
        store = _load_json(STORE_KEY_ERA_MATCHES)
        history = store.get("history") if isinstance(store.get("history"), list) else []
    except Exception:
        era = {}
        history = []

    # Build import-backed series from ERA ingest history (matched counts) — never invent $.
    points: list[dict[str, Any]] = []
    for h in history:
        if not isinstance(h, dict):
            continue
        at = str(h.get("at") or "")[:10]
        mc = h.get("matchedCount")
        if at and isinstance(mc, (int, float)):
            points.append({"label": at, "value": float(mc)})

    ar = reports.get("arAging") if isinstance(reports.get("arAging"), dict) else {}
    buckets = reports.get("arAgingBuckets") if isinstance(reports.get("arAgingBuckets"), list) else []
    bucket_bars: list[dict[str, Any]] = []
    for b in buckets:
        if not isinstance(b, dict):
            continue
        amt = b.get("amount")
        if isinstance(amt, (int, float)):
            bucket_bars.append({"label": str(b.get("bucket") or "")[:24], "value": float(amt)})

    has_era = bool(era) and len(points) >= 1
    if has_era:
        widgets.append(
            {
                "id": "forecast-trend-line",
                "type": "forecast-trend-line",
                "label": "ERA Match Velocity",
                "size": "xl",
                "status": "ok",
                "points": points[-24:],
                "eraMatchCount": len(era),
                "hint": (
                    f"{len(era)} ERA-matched claim(s) on file. "
                    "Line = matchedCount per ingest event — not a cash forecast."
                ),
            }
        )
        if bucket_bars:
            widgets.append(
                {
                    "id": "forecast-ar-buckets",
                    "type": "horizontal-bar",
                    "label": "Current A/R Aging (import)",
                    "size": "l",
                    "bars": bucket_bars,
                    "status": "ok",
                    "hint": "SoftDent A/R buckets — companion to ERA velocity (not projected).",
                }
            )
    else:
        ninety = ar.get("ninetyPlusOutstanding")
        widgets.append(
            {
                "id": "forecast-trend-line",
                "type": "forecast-trend-line",
                "label": "A/R Forecast (ERA Velocity)",
                "size": "full",
                "status": "empty",
                "points": [],
                "blocked": True,
                "blockedReason": "IMP-004 ERA 835 payer velocity",
                "emptyMessage": "Awaiting ERA 835 Pipeline — ingest ERA to unlock velocity trend",
                "hint": (
                    "Moonshot Phase 4: no illustrative decay dollars. "
                    f"Current 90+ outstanding shown only when imported"
                    + (
                        f" (${float(ninety):,.0f})."
                        if isinstance(ninety, (int, float))
                        else "."
                    )
                ),
                "importedNinetyPlus": float(ninety) if isinstance(ninety, (int, float)) else None,
            }
        )
    return widgets


def build_financial_periods(reports: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """FIN-PER: Historical period comparison — needs ≥2 SoftDent dashboard periods."""
    del reports
    widgets: list[dict[str, Any]] = [
        {
            "id": "subpage-fin-per-nav",
            "type": "status",
            "label": "Financial · Periods",
            "size": "strip",
            "status": "ok",
            "message": "MoM / multi-period comparison",
            "hint": "Hash #financial/periods · blocked until ≥2 SoftDent dashboard periods imported.",
        }
    ]

    rows = _section_rows(bundle, "softdent", "dashboard")
    if not rows:
        # Some bundles nest dashboard under alternate keys
        softdent = bundle.get("softdent") if isinstance(bundle.get("softdent"), dict) else {}
        for key in ("dashboard", "Dashboard", "daysheet", "Daysheet"):
            sec = softdent.get(key)
            if isinstance(sec, dict):
                maybe = sec.get("rows") if isinstance(sec.get("rows"), list) else sec.get("data")
                if isinstance(maybe, list):
                    rows = [r for r in maybe if isinstance(r, dict)]
                    break
            elif isinstance(sec, list):
                rows = [r for r in sec if isinstance(r, dict)]
                break

    by_period: dict[str, dict[str, float]] = {}
    for row in rows:
        p = str(row.get("period") or row.get("year_month") or row.get("Period") or "").strip()
        if not p:
            continue
        prod = _parse_money(row.get("production") or row.get("Production") or row.get("Prod"))
        coll = _parse_money(row.get("collections") or row.get("Collections") or row.get("Coll"))
        slot = by_period.setdefault(p, {"production": 0.0, "collections": 0.0})
        if prod is not None:
            slot["production"] += float(prod)
        if coll is not None:
            slot["collections"] += float(coll)

    series: list[dict[str, Any]] = []
    for p in sorted(by_period.keys()):
        series.append(
            {
                "period": p,
                "production": by_period[p]["production"] or None,
                "collections": by_period[p]["collections"] or None,
            }
        )

    variance_bars: list[dict[str, Any]] = []
    if len(series) >= 2:
        for i in range(1, len(series)):
            prev = series[i - 1].get("production")
            cur = series[i].get("production")
            if isinstance(prev, (int, float)) and isinstance(cur, (int, float)):
                variance_bars.append(
                    {
                        "label": f"{series[i - 1]['period']}→{series[i]['period']}"[:28],
                        "value": float(cur) - float(prev),
                    }
                )

    if len(series) >= 2 and variance_bars:
        widgets.append(
            {
                "id": "period-variance-chart",
                "type": "period-variance-chart",
                "label": "Production Period Variance",
                "size": "xl",
                "status": "ok",
                "bars": variance_bars,
                "series": series,
                "hint": "Import-backed SoftDent dashboard production deltas only — never invented.",
            }
        )
        widgets.append(
            {
                "id": "period-dual-trend",
                "type": "dual-axis-trend",
                "label": "Production vs Collections by Period",
                "size": "l",
                "status": "ok",
                "production": [
                    {"label": s["period"], "value": s["production"]}
                    for s in series
                    if isinstance(s.get("production"), (int, float))
                ],
                "collections": [
                    {"label": s["period"], "value": s["collections"]}
                    for s in series
                    if isinstance(s.get("collections"), (int, float))
                ],
                "hint": "SoftDent dashboard periods only.",
            }
        )
    else:
        widgets.append(
            {
                "id": "period-variance-chart",
                "type": "period-variance-chart",
                "label": "Production Period Variance",
                "size": "full",
                "status": "empty",
                "bars": [],
                "series": series,
                "blocked": True,
                "blockedReason": "Multi-period SoftDent/QB pipeline",
                "emptyMessage": "Awaiting multi-period imports — need ≥2 SoftDent dashboard periods",
                "hint": (
                    f"Found {len(series)} period(s) with production. "
                    "Export additional SoftDent dashboard periods to unlock MoM variance."
                ),
            }
        )
    return widgets


def resolve_subpage_builder(parent: str, sub: str):
    key = (str(parent or "").strip().lower(), str(sub or "").strip().lower())
    mapping: dict[tuple[str, str], Callable[..., list[dict[str, Any]]]] = {
        ("financial", "workpapers"): build_financial_workpapers,
        ("financial", "providers"): build_provider_view,
        ("financial", "periods"): build_financial_periods,
        ("claims", "detail"): build_claim_detail,
        ("claims", "batch"): build_batch_narrative,
        ("claims", "era"): build_claims_era,
        ("ar", "collections"): build_collections_workbench,
        ("ar", "forecast"): build_ar_forecast_subpage,
        ("office-manager", "huddle"): build_huddle_dashboard,
        ("documents", "claim-docs"): build_claim_docs,
        ("library", "payers"): build_payer_library,
    }
    if key in mapping:
        return mapping[key]
    try:
        from apex_subpages_wave5_pack import WAVE5_BUILDERS

        return WAVE5_BUILDERS.get(key)
    except Exception:
        return None
