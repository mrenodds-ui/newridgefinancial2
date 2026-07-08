"""CPA packet export — zip key financial widgets for external accountant review (hal-10074)."""

from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from financial_reports import build_financial_reports
from import_loader import load_import_bundle
from nr2_analytics import production_reconciliation
from nr2_qb_reports import _bundle_qb, _monthly_pl_rows, _parse_money, net_income_summary

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
DATA_DIR = REPO_ROOT / "app_data" / "nr2"
OUTPUT_DIR = DATA_DIR / "cpa_exports"

WIDGET_KEYS = (
    "quickbooksProfitLossDetail",
    "nr2ProductionReconciliation",
    "arAgingAndCollections",
    "quickbooksNetIncomeSummary",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _profit_loss_detail(*, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    bundle = bundle or load_import_bundle(sync=False)
    qb = _bundle_qb(bundle)
    pl = qb.get("profitAndLoss") if isinstance(qb.get("profitAndLoss"), dict) else {}
    detail_rows = pl.get("rows") if isinstance(pl.get("rows"), list) else []
    monthly = _monthly_pl_rows(bundle)
    ytd_revenue = sum(_parse_money(row.get("TotalIncome")) for row in monthly)
    ytd_expense = sum(_parse_money(row.get("TotalExpense")) for row in monthly)
    ytd_net = sum(_parse_money(row.get("NetIncome")) for row in monthly)
    if ytd_net == 0 and (ytd_revenue or ytd_expense):
        ytd_net = ytd_revenue - ytd_expense
    return {
        "widgetKey": "quickbooksProfitLossDetail",
        "detailRows": detail_rows,
        "monthlyRows": monthly,
        "ytd": {
            "revenue": round(ytd_revenue, 2),
            "expenses": round(ytd_expense, 2),
            "netIncome": round(ytd_net, 2),
        },
        "hasData": bool(monthly or detail_rows),
    }


def _ar_aging_collections() -> dict[str, Any]:
    reports = build_financial_reports()
    summary = reports.get("arAging") if isinstance(reports.get("arAging"), dict) else {}
    buckets = reports.get("arAgingBuckets") if isinstance(reports.get("arAgingBuckets"), list) else []
    return {
        "widgetKey": "arAgingAndCollections",
        "summary": summary,
        "buckets": buckets,
        "collectionsNote": reports.get("collectionsNote"),
        "hasData": bool(summary.get("totalOutstanding")),
    }


def collect_cpa_payloads(*, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    bundle = bundle or load_import_bundle(sync=False)
    return {
        "generatedAt": _utc_now(),
        "widgets": {
            "quickbooksProfitLossDetail": _profit_loss_detail(bundle=bundle),
            "nr2ProductionReconciliation": {
                **production_reconciliation(bundle=bundle),
                "widgetKey": "nr2ProductionReconciliation",
            },
            "arAgingAndCollections": _ar_aging_collections(),
            "quickbooksNetIncomeSummary": {
                **net_income_summary(bundle=bundle),
                "widgetKey": "quickbooksNetIncomeSummary",
            },
        },
    }


def build_cpa_packet(*, write_disk: bool = True) -> dict[str, Any]:
    payloads = collect_cpa_payloads()
    stamp = _utc_stamp()
    filename = f"nr2-cpa-packet-{stamp}.zip"
    manifest = {
        "generatedAt": payloads["generatedAt"],
        "widgetKeys": list(WIDGET_KEYS),
        "practice": "New Ridge Family Dental",
        "note": "Read-only import snapshot for CPA review — no PHI claim narratives included.",
    }
    zip_bytes = _zip_payloads(payloads, manifest)
    out_path: Path | None = None
    if write_disk:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUTPUT_DIR / filename
        out_path.write_bytes(zip_bytes)
    return {
        "ok": True,
        "filename": filename,
        "path": str(out_path) if out_path else None,
        "sizeBytes": len(zip_bytes),
        "generatedAt": payloads["generatedAt"],
        "widgetKeys": list(WIDGET_KEYS),
        "zipBytes": zip_bytes,
    }


def build_cpa_packet_zip_bytes() -> tuple[str, bytes]:
    result = build_cpa_packet(write_disk=True)
    return str(result["filename"]), bytes(result["zipBytes"])


def _zip_payloads(payloads: dict[str, Any], manifest: dict[str, Any]) -> bytes:
    from io import BytesIO

    buffer = BytesIO()
    widgets = payloads.get("widgets") if isinstance(payloads.get("widgets"), dict) else {}
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        for key in WIDGET_KEYS:
            archive.writestr(f"{key}.json", json.dumps(widgets.get(key) or {}, indent=2, ensure_ascii=False))
    return buffer.getvalue()
