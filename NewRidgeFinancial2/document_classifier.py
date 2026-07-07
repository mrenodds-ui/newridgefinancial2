"""Document mail classification — Phase 2 Moonshot Priority J."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

CATEGORY_PATTERNS: dict[str, re.Pattern[str]] = {
    "EOB_ERA": re.compile(r"(?i)\b(835|eob|era|remittance|claim payment)\b"),
    "EFT_Notice": re.compile(r"(?i)\b(eft|ach|electronic funds|deposit notice|bank transfer)\b"),
    "Credentialing": re.compile(r"(?i)\b(credential|provider enrollment|npi|recredential)\b"),
    "Invoice": re.compile(r"(?i)\b(invoice|statement due|amount due|payable)\b"),
    "Correspondence": re.compile(r"(?i)\b(dear|letter|regarding|please contact)\b"),
}


def classify_document_text(text: str) -> dict[str, Any]:
    content = str(text or "")
    if not content.strip():
        return {"ok": True, "category": "Unknown", "confidence": 0.0, "method": "empty"}
    best_cat = "Unknown"
    best_score = 0.0
    for cat, pattern in CATEGORY_PATTERNS.items():
        if pattern.search(content):
            score = 0.88 if cat in ("EOB_ERA", "EFT_Notice") else 0.82
            if score > best_score:
                best_score = score
                best_cat = cat
    if best_cat == "Unknown" and len(content) > 40:
        best_cat = "Correspondence"
        best_score = 0.55
    return {
        "ok": True,
        "category": best_cat,
        "confidence": round(best_score, 3),
        "method": "heuristic",
        "requiresHumanInbox": best_score < 0.85,
    }


def classify_document_path(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        return {"ok": False, "error": "file_not_found"}
    suffix = p.suffix.lower()
    if suffix in (".txt", ".csv", ".835", ".edi"):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")[:12000]
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
        result = classify_document_text(text)
        result["path"] = str(p)
        return result
    name_hint = classify_document_text(p.name)
    name_hint["path"] = str(p)
    name_hint["method"] = "filename_heuristic"
    return name_hint


def route_for_category(category: str) -> str:
    routes = {
        "EOB_ERA": "parse_era_835",
        "EFT_Notice": "draft_deposit_reconciliation",
        "Credentialing": "human_inbox",
        "Invoice": "human_inbox",
        "Correspondence": "human_inbox",
        "Unknown": "human_inbox",
    }
    return routes.get(str(category or "Unknown"), "human_inbox")
