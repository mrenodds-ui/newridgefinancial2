"""Shared HAL answer-quality scoring for eval runners."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_NR2 = _ROOT / "NewRidgeFinancial2"
if str(_NR2) not in sys.path:
    sys.path.insert(0, str(_NR2))

_YES_NO_LEAD_RE = re.compile(r"^\s*(yes|no)\b", re.IGNORECASE)
_READ_ONLY_RE = re.compile(r"\bread[\s-]?only\b", re.IGNORECASE)
_CONSENT_RE = re.compile(r"\bconsent\b", re.IGNORECASE)
_DIRECT_ANSWER_RE = re.compile(
    r"(\*\*Direct Answer:\*\*|Direct answer:|^\s*(Yes|No)\b)",
    re.IGNORECASE | re.MULTILINE,
)
_DELIVERABLE_RE = re.compile(
    r"("
    r"\*\*Direct Answer:\*\*|Direct answer:|"
    r"\b(next step|safe next|priority order|ordered steps|journal entry|"
    r"risk flag|verified basis|staff should)\b"
    r")",
    re.IGNORECASE,
)
_STRUCTURED_PLAN_OPENER_RE = re.compile(
    r"^\s*(here(?:'s| is) a structured plan|here is a (?:brief )?(?:numbered )?plan|structured plan:)\b",
    re.IGNORECASE,
)
# Leading or mid-body CoT / scratchpad leaks
_COT_LEAK_RE = re.compile(
    r"("
    r"<think>|</think>|"
    r"(?:Okay|Hmm),?\s+the user|"
    r"(?:^|\n)\s*First,?\s+I need to|"
    r"(?:^|\n)\s*Let me (?:break|think|verify)|"
    r"(?:^|\n)\s*\*Double-checking|"
    r"(?:^|\n)\s*\*Lightbulb|"
    r"The user is asking"
    r")",
    re.IGNORECASE | re.MULTILINE,
)

# Gold facts from office fee/payer stores — fail eval when answers invent or omit them.
_GOLD_CASES: list[dict[str, Any]] = [
    {
        "id": "fee-d2740-delta",
        "match": re.compile(r"(?=.*\bD2740\b)(?=.*\bdelta\b)", re.IGNORECASE),
        "require_any": ("845", "$845"),
        "require_token": ("delta",),
    },
    {
        "id": "fee-d0120-metlife",
        "match": re.compile(r"(?=.*\bD0120\b)(?=.*\bmetlife\b)", re.IGNORECASE),
        "require_any": ("29", "$29"),
        "require_token": ("metlife",),
    },
    {
        "id": "fee-d1110-delta",
        "match": re.compile(r"(?=.*\bD1110\b)(?=.*\bdelta\b)", re.IGNORECASE),
        "require_any": ("68", "$68"),
        "require_token": ("delta",),
    },
    {
        "id": "fee-d2740-metlife",
        "match": re.compile(r"(?=.*\bD2740\b)(?=.*\bmetlife\b)", re.IGNORECASE),
        "require_any": ("740", "$740"),
        "require_token": ("metlife",),
    },
    {
        "id": "fee-d4341-guardian",
        "match": re.compile(r"(?=.*\bD4341\b)(?=.*\bguardian\b)", re.IGNORECASE),
        "require_any": ("125", "$125"),
        "require_token": ("guardian",),
    },
    {
        "id": "fee-d0120-cigna",
        "match": re.compile(r"(?=.*\bD0120\b)(?=.*\bcigna\b)", re.IGNORECASE),
        "require_any": ("29", "$29"),
        "require_token": ("cigna",),
    },
    {
        "id": "payer-metlife-phone",
        "match": re.compile(
            r"(?=.*\bmetlife\b)(?=.*\b(elig(?:ibility|ible)?\s*phone|phone\s*(?:number|for\s+elig)|claim\s*phone)\b)",
            re.IGNORECASE,
        ),
        "require_any": ("638-5433", "6385433", "(800) 638-5433"),
        "require_token": ("metlife",),
    },
    {
        "id": "payer-cigna-phone",
        "match": re.compile(
            r"(?=.*\bcigna\b)(?=.*\b(elig(?:ibility|ible)?\s*phone|phone\s*(?:number|for\s+elig)|claim\s*phone)\b)",
            re.IGNORECASE,
        ),
        "require_any": ("244-6224", "2446224", "(800) 244-6224"),
        "require_token": ("cigna",),
    },
    {
        "id": "payer-humana-phone",
        "match": re.compile(
            r"(?=.*\bhumana\b)(?=.*\b(elig(?:ibility|ible)?\s*phone|phone\s*(?:number|for\s+elig)|claim\s*phone)\b)",
            re.IGNORECASE,
        ),
        "require_any": ("833-2223", "8332223", "(800) 833-2223"),
        "require_token": ("humana",),
    },
    {
        "id": "payer-aetna-phone",
        "match": re.compile(
            r"(?=.*\baetna\b)(?=.*\b(elig(?:ibility|ible)?\s*phone|phone\s*(?:number|for\s+elig)|claim\s*phone)\b)",
            re.IGNORECASE,
        ),
        "require_any": ("451-7715", "4517715", "(800) 451-7715"),
        "require_token": ("aetna",),
    },
    {
        "id": "payer-geha-phone",
        "match": re.compile(
            r"(?=.*\bgeha\b)(?=.*\b(elig(?:ibility|ible)?\s*phone|phone\s*(?:number|for\s+elig)|claim\s*phone)\b)",
            re.IGNORECASE,
        ),
        "require_any": ("434-2336", "4342336", "(877) 434-2336"),
        "require_token": ("geha",),
    },
    {
        # Honesty: when claims only say generic Insurance, answer must acknowledge the gap
        "id": "generic-insurance-no-invent",
        "match": re.compile(
            r"(?=.*\b(generic|labeled)\b.*\binsurance\b)|"
            r"(?=.*\bclaims?\b.*\bsay\b.*\binsurance\b)|"
            r"(?=.*\bwhich payer\b.*\bclaim\b)|"
            r"(?=.*\bcarrier (?:on|for) (?:the )?claim\b)",
            re.IGNORECASE,
        ),
        "require_any": (
            "Insurance",
            "generic",
            "cannot",
            "can't",
            "InsCo",
            "export",
            "daysheet",
            "verify",
            "unavailable",
        ),
        "require_token": (),
    },
]
_YES_NO_QUERY_RE = re.compile(
    r"^(can you|are you|do you|does |is |was |will you|would you|could you|"
    r"should i|may i|have you|did you|yes or no|short answer:|short:)\b",
    re.IGNORECASE,
)
_OUTBOUND_QUERY_RE = re.compile(
    r"\b(email|fax|upload|send|deliver)\b|"
    r"\bsubmit\b.*\b(claim|payer|portal|narrative)\b|"
    r"\bwithout (?:staff )?consent\b",
    re.IGNORECASE,
)
_READONLY_QUERY_RE = re.compile(
    r"\b(post|write|write[\s-]?back|push)\b.*\b(quickbooks|qb|softdent|ledger|journal)\b|"
    r"\b(write to softdent|post to quickbooks|post journal)\b",
    re.IGNORECASE,
)


def has_yes_no_lead(text: str) -> bool:
    return bool(_YES_NO_LEAD_RE.match(str(text or "")))


def has_read_only_mention(text: str) -> bool:
    return bool(_READ_ONLY_RE.search(str(text or "")))


def has_consent_mention(text: str) -> bool:
    return bool(_CONSENT_RE.search(str(text or "")))


def has_direct_answer(text: str) -> bool:
    body = str(text or "").strip()
    if not body:
        return False
    if _DIRECT_ANSWER_RE.search(body):
        return True
    # Staff-facing prose that leads with a clear claim counts as a direct answer.
    first = re.split(r"[.!?]\s+", body, maxsplit=1)[0]
    return len(first) >= 12 and not _COT_LEAK_RE.search(first)


def has_deliverable(text: str) -> bool:
    body = str(text or "").strip()
    if not body:
        return False
    if _DELIVERABLE_RE.search(body):
        return True
    lower = body.lower()
    return has_direct_answer(body) and any(
        token in lower
        for token in ("next", "staff", "verify", "draft", "locally", "refresh", "open ")
    )


def has_structured_plan_opener(text: str) -> bool:
    return bool(_STRUCTURED_PLAN_OPENER_RE.match(str(text or "")))


def has_cot_leak(text: str) -> bool:
    return bool(_COT_LEAK_RE.search(str(text or "")))


def is_yes_no_query(query: str) -> bool:
    return bool(_YES_NO_QUERY_RE.match(str(query or "").strip()))


def needs_read_only_lead(query: str) -> bool:
    return bool(_READONLY_QUERY_RE.search(str(query or "")))


def needs_consent_lead(query: str) -> bool:
    return bool(_OUTBOUND_QUERY_RE.search(str(query or "")))


def matching_gold_cases(query: str) -> list[dict[str, Any]]:
    q = str(query or "")
    return [case for case in _GOLD_CASES if case["match"].search(q)]


def score_grounding(query: str, text: str) -> dict[str, Any]:
    """Check answer against known fee/payer gold facts when the query matches."""
    body = str(text or "")
    body_compact = re.sub(r"[\s\-().]", "", body.lower())
    cases = matching_gold_cases(query)
    if not cases:
        return {
            "applicable": False,
            "grounded": None,
            "caseIds": [],
            "missing": [],
        }
    missing: list[str] = []
    for case in cases:
        ok_any = False
        for token in case.get("require_any") or ():
            tok = re.sub(r"[\s\-().]", "", str(token).lower())
            if tok and tok in body_compact:
                ok_any = True
                break
            if str(token).lower() in body.lower():
                ok_any = True
                break
        if not ok_any:
            missing.append(f"{case['id']}:expected_one_of={list(case.get('require_any') or ())}")
        for token in case.get("require_token") or ():
            if str(token).lower() not in body.lower():
                missing.append(f"{case['id']}:missing_token={token}")
    return {
        "applicable": True,
        "grounded": not missing,
        "caseIds": [str(c["id"]) for c in cases],
        "missing": missing,
    }


def score_answer(query: str, text: str) -> dict[str, Any]:
    body = str(text or "").strip()
    q = str(query or "").strip()
    grounding = score_grounding(q, body)
    quality = (
        bool(body)
        and has_direct_answer(body)
        and has_deliverable(body)
        and not has_cot_leak(body)
        and not has_structured_plan_opener(body)
        and (has_yes_no_lead(body) if is_yes_no_query(q) else True)
        and (has_read_only_mention(body) if needs_read_only_lead(q) else True)
        and (has_consent_mention(body) if needs_consent_lead(q) else True)
        and (grounding["grounded"] is not False)
    )
    return {
        "hasDirectAnswer": has_direct_answer(body),
        "hasDeliverable": has_deliverable(body),
        "hasYesNoLead": has_yes_no_lead(body) if is_yes_no_query(q) else None,
        "hasReadOnlyMention": has_read_only_mention(body) if needs_read_only_lead(q) else None,
        "hasConsentMention": has_consent_mention(body) if needs_consent_lead(q) else None,
        "hasStructuredPlanOpener": has_structured_plan_opener(body),
        "hasCotLeak": has_cot_leak(body),
        "groundingApplicable": grounding["applicable"],
        "grounded": grounding["grounded"],
        "groundingCaseIds": grounding["caseIds"],
        "groundingMissing": grounding["missing"],
        "qualityPass": quality,
    }
