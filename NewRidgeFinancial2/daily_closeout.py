"""Daily closeout checklist for NR2 operators."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from financial_reports import build_financial_reports
from integration_health import integration_health_snapshot


def _item(item_id: str, label: str, status: str, detail: str) -> dict[str, str]:
    return {"id": item_id, "label": label, "status": status, "detail": detail}


def build_daily_closeout(store: Any | None = None) -> dict[str, Any]:
    health = integration_health_snapshot(store, deep_diagnostics=False)
    reports = build_financial_reports(sync_exports=False)
    items: list[dict[str, str]] = []

    import_row = next((r for r in health.get("integrations") or [] if r.get("id") == "imports"), {})
    items.append(
        _item(
            "imports",
            "Import freshness",
            "ok" if import_row.get("ok") else "warn" if health.get("ok_count", 0) else "fail",
            str(import_row.get("detail") or "Import status unknown."),
        )
    )

    ollama_row = next((r for r in health.get("integrations") or [] if r.get("id") == "ollama"), {})
    items.append(
        _item(
            "local-ai",
            "Local AI reachable",
            "ok" if ollama_row.get("ok") else "fail",
            str(ollama_row.get("detail") or "Ollama status unknown."),
        )
    )

    docs_row = next((r for r in health.get("integrations") or [] if r.get("id") == "documents"), {})
    doc_count = 0
    if store is not None:
        try:
            raw = store.get("nr2:v2:documents")
            if raw:
                payload = json.loads(raw)
                doc_count = len(payload.get("queue") or [])
        except Exception:
            doc_count = 0
    items.append(
        _item(
            "documents",
            "Documents queue reviewed",
            "warn" if doc_count > 0 else "ok",
            f"{doc_count} document(s) pending review." if doc_count else "No documents waiting in local queue.",
        )
    )

    ct = reports.get("claimTracking") or {}
    denied_30 = int(ct.get("deniedAgingPast30Days") or 0)
    items.append(
        _item(
            "claims",
            "Denied claims aging past 30 days",
            "warn" if denied_30 else "ok",
            f"{denied_30} claim(s) flagged for follow-up." if denied_30 else "No denied 30+ day claims flagged in import.",
        )
    )

    ar = reports.get("arAging") or {}
    ninety_pct = float(ar.get("ninetyPlusPct") or 0)
    items.append(
        _item(
            "ar",
            "A/R 90+ day exposure",
            "warn" if ninety_pct >= 15 else "ok",
            f"90+ day balances are {ninety_pct}% of outstanding A/R in the import snapshot.",
        )
    )

    tp = reports.get("treatmentPlans") or {}
    items.append(
        _item(
            "treatment-plans",
            "Treatment plan exports",
            "ok" if tp.get("available") else "warn",
            "Treatment plan summary loaded." if tp.get("available") else "Treatment plan export missing — run practice exports.",
        )
    )

    fail_count = sum(1 for row in items if row["status"] == "fail")
    warn_count = sum(1 for row in items if row["status"] == "warn")
    overall = "fail" if fail_count else ("warn" if warn_count else "ok")

    return {
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "period": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "overall": overall,
        "summary": f"{len(items) - fail_count - warn_count} clear, {warn_count} warning(s), {fail_count} blocker(s).",
        "items": items,
        "integrationHealth": health,
        "financialReports": reports,
    }


def format_daily_closeout_text(payload: dict[str, Any]) -> str:
    lines = [
        f"Daily closeout ({payload.get('period')}): {str(payload.get('overall', '')).upper()} — {payload.get('summary')}",
        "",
    ]
    for row in payload.get("items") or []:
        lines.append(f"- [{str(row.get('status')).upper()}] {row.get('label')}: {row.get('detail')}")
    return "\n".join(lines)
