"""In-app program help topics for NR2 (portal-style operator guidance)."""

from __future__ import annotations

import re
from typing import Any

TOPICS: list[dict[str, Any]] = [
    {
        "id": "imports",
        "keywords": ["import", "sync", "softdent export", "quickbooks export", "refresh import", "stale"],
        "page": "office-manager",
        "answer": (
            "Use Refresh imports in HAL or run Sync-HAL-Imports.ps1. NR2 reads SoftDent and QuickBooks export "
            "folders only — nothing is written back. Ask HAL for import status or integration health for stale datasets."
        ),
    },
    {
        "id": "widgets",
        "keywords": ["widget", "degraded", "no data", "dashboard", "feed"],
        "page": "hal-command-center",
        "answer": (
            "Widgets turn DEGRADED when upstream exports are stale, partial, or missing. Run import sync, then document "
            "sync if documents are empty. HAL can show widget feed status and missing dataset hints."
        ),
    },
    {
        "id": "documents",
        "keywords": ["document", "posting queue", "journal", "month end", "accounting document"],
        "page": "documents",
        "answer": (
            "Documents sync merges SoftDent/QuickBooks summaries into a local review queue. Journal posting remains "
            "draft-only — staff review before any QuickBooks write-back outside HAL."
        ),
    },
    {
        "id": "claims",
        "keywords": ["claim", "denied", "appeal", "resubmit", "insurance follow"],
        "page": "claims",
        "answer": (
            "Claims workbench uses imported SoftDent claims exports. For denied claims aging past 30 days, verify denial "
            "reason in SoftDent and plan resubmit or appeal — HAL will not submit payer actions."
        ),
    },
    {
        "id": "ar",
        "keywords": ["a/r", "ar", "aging", "outstanding", "collections trailing"],
        "page": "ar",
        "answer": (
            "Dental A/R comes from SoftDent imports; QuickBooks GL is separate. When collections trail production, start "
            "with aging/outstanding balances and insurance delays — not the same total as QuickBooks revenue."
        ),
    },
    {
        "id": "support",
        "keywords": ["support bundle", "diagnostics", "troubleshoot", "export logs"],
        "page": "hal-command-center",
        "answer": (
            "Ask HAL to build a support bundle. NR2 packages redacted env keys, integration health, automation runs, and "
            "import diagnostics into app_data/nr2/support_bundles for operator review."
        ),
    },
    {
        "id": "daily-closeout",
        "keywords": ["daily closeout", "morning checklist", "end of day", "closeout"],
        "page": "office-manager",
        "answer": (
            "Daily closeout checks import freshness, local AI, documents queue, denied claims, A/R 90+ exposure, and "
            "treatment plan exports. Ask HAL for daily closeout or run it from the Office Manager tools."
        ),
    },
    {
        "id": "hal-chat",
        "keywords": ["hal", "chat", "model", "ollama", "local ai"],
        "page": "hal-command-center",
        "answer": (
            "HAL chat uses local Ollama lanes (hal-chat:8b + qwen3:30b GPU-pinned) on this machine only. External submit, email, "
            "fax, upload, and QuickBooks posting are blocked — human review required."
        ),
    },
]


def match_program_help(query: str) -> dict[str, Any] | None:
    text = " ".join(str(query or "").lower().split())
    if not text:
        return None
    best: dict[str, Any] | None = None
    best_score = 0
    for topic in TOPICS:
        score = 0
        for keyword in topic.get("keywords") or []:
            if keyword in text:
                score += 2
            elif re.search(rf"\b{re.escape(keyword)}\b", text):
                score += 1
        if score > best_score:
            best_score = score
            best = topic
    if best_score <= 0:
        return None
    return {**best, "score": best_score}


def format_program_help(query: str) -> str:
    match = match_program_help(query)
    if not match:
        return (
            "I can help with imports, widgets, documents, claims, A/R, daily closeout, support bundles, and local HAL chat. "
            "Try: 'How do I refresh imports?' or 'Why is my widget degraded?'"
        )
    page = match.get("page")
    prefix = f"({page} page) " if page else ""
    return prefix + str(match.get("answer") or "")
