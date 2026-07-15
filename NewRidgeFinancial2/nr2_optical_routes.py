"""Optical page routes — HAL board-actions navigate (empty ≠ $0 · no invent).

Maps apex board page keys to NR2 optical HTML paths so consent navigate
can open SoftDent/QB/AR benches from HAL chat without fake dollars.
"""

from __future__ import annotations

import re
from typing import Any

# Apex board page keys → live optical pages (CSP self only).
OPTICAL_PAGE_HREFS: dict[str, str] = {
    "main": "/nr2-optical-beam-touch-mockup.html",
    "landing": "/nr2-optical-beam-touch-mockup.html",
    "financial": "/nr2-optical-beam-touch-mockup.html",
    "hub": "/nr2-optical-pages-hub.html",
    "pages": "/nr2-optical-pages-hub.html",
    "softdent": "/nr2-optical-page-softdent.html",
    "soft-dent": "/nr2-optical-page-softdent.html",
    "quickbooks": "/nr2-optical-page-quickbooks.html",
    "qb": "/nr2-optical-page-quickbooks.html",
    "ar": "/nr2-optical-page-ar.html",
    "aging": "/nr2-optical-page-ar.html",
    "a-r": "/nr2-optical-page-ar.html",
    "claims": "/nr2-optical-page-claims.html",
    "era": "/nr2-optical-page-claims.html",
    "hal": "/nr2-optical-page-hal.html",
    "taxes": "/nr2-optical-page-taxes.html",
    "tax": "/nr2-optical-page-taxes.html",
    "office-manager": "/nr2-optical-page-office-manager.html",
    "om": "/nr2-optical-page-office-manager.html",
    "office": "/nr2-optical-page-office-manager.html",
    "narratives": "/nr2-optical-page-narratives.html",
    "content": "/nr2-optical-page-content.html",
    "documents": "/nr2-optical-page-content.html",
    "library": "/nr2-optical-page-content.html",
    "docs": "/nr2-optical-page-content.html",
}


def normalize_page_key(page: str | None) -> str:
    return re.sub(r"[^a-z0-9\-]", "", str(page or "").strip().lower())


def resolve_optical_href(page_or_href: str | None) -> str:
    """Return an optical href, or '' if unknown (never invent a dollar path)."""
    raw = str(page_or_href or "").strip()
    if not raw:
        return ""
    if raw.startswith("/nr2-optical") or raw.startswith("/nr2-optical-"):
        return raw.split("?", 1)[0]
    if raw.startswith("/") and "optical" in raw:
        return raw.split("?", 1)[0]
    key = normalize_page_key(raw)
    aliases = {
        "softdentpage": "softdent",
        "accountaging": "ar",
        "receivables": "ar",
        "officemanager": "office-manager",
    }
    key = aliases.get(key, key)
    return OPTICAL_PAGE_HREFS.get(key, "")


def enrich_navigate_actions(actions: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Attach href to each navigate action for optical clients."""
    out: list[dict[str, Any]] = []
    for act in actions or []:
        if not isinstance(act, dict):
            continue
        row = dict(act)
        if str(row.get("type") or "") == "navigate":
            page = str(row.get("page") or row.get("target") or "")
            href = str(row.get("href") or "").strip() or resolve_optical_href(page)
            if href:
                row["href"] = href
            if page and not row.get("page"):
                row["page"] = normalize_page_key(page) or page
            row["clientMustNavigate"] = True
            row["emptyNotZero"] = True
        out.append(row)
    return out
