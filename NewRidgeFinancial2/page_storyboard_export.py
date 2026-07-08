"""Per-page print/PDF storyboard export — zip HTML + JSON widget payloads (hal-10084)."""

from __future__ import annotations

import html
import json
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from cpa_packet_export import collect_cpa_payloads
from financial_reports import build_financial_reports
from import_loader import load_import_bundle
from nr2_analytics import (
    alert_ticker,
    collection_lag,
    goal_scorecard,
    kpi_ribbon,
    monthly_trend_combo,
    production_reconciliation,
    provider_compensation,
)
from nr2_qb_reports import net_income_summary

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
OUTPUT_DIR = REPO_ROOT / "app_data" / "nr2" / "storyboard_exports"

STAFF_PAGES = (
    "financial",
    "taxes",
    "softdent",
    "quickbooks",
    "ar",
    "claims",
    "documents",
    "library",
    "narratives",
    "office-manager",
)

PAGE_TITLES = {
    "financial": "Owner Financial Dashboard",
    "taxes": "S Corp Tax Planning",
    "softdent": "Clinical & Practice Performance",
    "quickbooks": "QuickBooks Financial Detail",
    "ar": "A/R & Collections",
    "claims": "Claims Workbench",
    "documents": "Accounting Documents",
    "library": "Document Library",
    "narratives": "Clinical Narratives",
    "office-manager": "Office Manager",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _financial_payload(bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "kpiRibbon": kpi_ribbon(bundle=bundle),
        "goalScorecard": goal_scorecard(bundle=bundle),
        "alertTicker": alert_ticker(bundle=bundle),
        "monthlyTrendCombo": monthly_trend_combo(bundle=bundle),
        "productionReconciliation": production_reconciliation(bundle=bundle),
        "collectionLag": collection_lag(bundle=bundle),
        "providerCompensation": provider_compensation(bundle=bundle),
        "financialReports": build_financial_reports(),
    }


def _taxes_payload(bundle: dict[str, Any]) -> dict[str, Any]:
    cpa = collect_cpa_payloads(bundle=bundle)
    return {
        "profitLoss": cpa["widgets"].get("quickbooksProfitLossDetail"),
        "netIncome": net_income_summary(bundle=bundle),
        "note": "Planning estimates only — CPA review required before filing.",
    }


def _quickbooks_payload(bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "netIncome": net_income_summary(bundle=bundle),
        "cpaWidgets": collect_cpa_payloads(bundle=bundle)["widgets"],
    }


def _ar_payload() -> dict[str, Any]:
    reports = build_financial_reports()
    return {
        "arAging": reports.get("arAging"),
        "arAgingBuckets": reports.get("arAgingBuckets"),
        "collectionsNote": reports.get("collectionsNote"),
    }


def _generic_payload(page_id: str, bundle: dict[str, Any]) -> dict[str, Any]:
    return {"pageId": page_id, "importBundleKeys": sorted(bundle.keys()) if isinstance(bundle, dict) else []}


def collect_page_storyboard(page_id: str, *, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    page_id = str(page_id or "financial").strip().lower()
    if page_id not in STAFF_PAGES:
        page_id = "financial"
    bundle = bundle or load_import_bundle(sync=False)
    builders = {
        "financial": lambda: _financial_payload(bundle),
        "taxes": lambda: _taxes_payload(bundle),
        "quickbooks": lambda: _quickbooks_payload(bundle),
        "ar": lambda: _ar_payload(),
    }
    data = builders.get(page_id, lambda: _generic_payload(page_id, bundle))()
    return {
        "pageId": page_id,
        "title": PAGE_TITLES.get(page_id, page_id),
        "generatedAt": _utc_now(),
        "practice": "New Ridge Family Dental",
        "note": "Open storyboard.html in a browser and use Print → Save as PDF for CPA or operator review.",
        "data": data,
    }


def _rows_from_payload(payload: dict[str, Any]) -> list[list[str]]:
    rows: list[list[str]] = [["Section", "Detail"]]
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    if "kpiRibbon" in data:
        tiles = (data["kpiRibbon"] or {}).get("tiles") or []
        for tile in tiles[:8]:
            if isinstance(tile, dict):
                rows.append(["KPI", f"{tile.get('label', '—')}: {tile.get('value', '—')}"])
    if "productionReconciliation" in data:
        recon_rows = (data["productionReconciliation"] or {}).get("rows") or []
        for row in recon_rows[:6]:
            if isinstance(row, dict):
                rows.append(
                    [
                        "Reconciliation",
                        f"{row.get('period', '—')} · SD {row.get('softdentProduction')} · QB {row.get('quickbooksRevenue')}",
                    ]
                )
    if "netIncome" in data and isinstance(data["netIncome"], dict):
        ni = data["netIncome"]
        rows.append(["Net income", str(ni.get("netIncome") or ni.get("value") or "—")])
    if "arAging" in data and isinstance(data["arAging"], dict):
        rows.append(["A/R total", str(data["arAging"].get("totalOutstanding") or "—")])
    if len(rows) == 1:
        rows.append(["Snapshot", "Import data available — see data.json in this zip for full widget payloads."])
    return rows


def build_storyboard_html(payload: dict[str, Any]) -> str:
    title = _esc(payload.get("title") or "Page storyboard")
    stamp = _esc(payload.get("generatedAt") or _utc_now())
    rows = _rows_from_payload(payload)
    body_rows = "".join(
        f"<tr><td>{_esc(c[0])}</td><td>{_esc(c[1])}</td></tr>" for c in rows[1:]
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>{title} — Storyboard</title>
<style>
@page {{ margin: 0.75in; }}
body {{ font-family: "Segoe UI", system-ui, sans-serif; color: #111; margin: 24px; }}
h1 {{ color: #1a5276; margin: 0 0 8px; font-size: 20pt; }}
.meta {{ color: #555; font-size: 10pt; margin-bottom: 20px; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ border: 1px solid #ccc; padding: 6px 10px; text-align: left; }}
th {{ background: #f0f4f8; }}
.note {{ margin-top: 16px; font-size: 10pt; color: #444; }}
</style>
</head>
<body>
<h1>{title}</h1>
<p class="meta">New Ridge Family Dental · Generated {stamp} · Local data only</p>
<table>
<thead><tr><th>Section</th><th>Detail</th></tr></thead>
<tbody>{body_rows}</tbody>
</table>
<p class="note">{_esc(payload.get("note") or "")}</p>
</body>
</html>"""


def build_page_storyboard(*, page_id: str, write_disk: bool = True) -> dict[str, Any]:
    payload = collect_page_storyboard(page_id)
    stamp = _utc_stamp()
    safe_page = payload["pageId"]
    filename = f"nr2-storyboard-{safe_page}-{stamp}.zip"
    html_doc = build_storyboard_html(payload)
    manifest = {
        "generatedAt": payload["generatedAt"],
        "pageId": safe_page,
        "title": payload["title"],
        "practice": payload["practice"],
        "note": payload["note"],
    }
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        archive.writestr("data.json", json.dumps(payload, indent=2, ensure_ascii=False))
        archive.writestr("storyboard.html", html_doc)
        archive.writestr("README.txt", "Open storyboard.html and Print → Save as PDF.\n")
    zip_bytes = buffer.getvalue()
    out_path: Path | None = None
    if write_disk:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUTPUT_DIR / filename
        out_path.write_bytes(zip_bytes)
    return {
        "ok": True,
        "pageId": safe_page,
        "filename": filename,
        "path": str(out_path) if out_path else None,
        "sizeBytes": len(zip_bytes),
        "generatedAt": payload["generatedAt"],
        "zipBytes": zip_bytes,
    }


def build_page_storyboard_zip_bytes(page_id: str) -> tuple[str, bytes]:
    result = build_page_storyboard(page_id=page_id, write_disk=True)
    return str(result["filename"]), bytes(result["zipBytes"])
