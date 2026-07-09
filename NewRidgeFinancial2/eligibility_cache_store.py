"""Per-patient eligibility snapshots — 270/271 or manual import, PHI-redacted."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = REPO_ROOT / "app_data" / "nr2" / "eligibility_cache"
INDEX_PATH = CACHE_DIR / "index.jsonl"
DEFAULT_TTL_HOURS = 72

TOKEN_RE = re.compile(r"[a-z0-9]{2,}")
ELIGIBILITY_QUERY_RE = re.compile(
    r"\b("
    r"eligibility|elig(?:ible)?|"
    r"deductible|annual\s*max|benefit(?:s)?\s*(?:check|remaining)|"
    r"coinsurance|copay|waiting\s*period|"
    r"270|271|member\s*id|subscriber|"
    r"coverage\s*(?:left|remaining)|max\s*remaining"
    r")\b",
    re.IGNORECASE,
)
# "eligibility phone / website / contact" is payer routing, not member-benefit cache
ELIGIBILITY_CONTACT_ONLY_RE = re.compile(
    r"\belig(?:ibility|ible)?\s*(?:phone|tel|number|website|portal|url|fax|contact|address)\b|"
    r"\b(?:phone|tel|website|portal|fax|contact)\s*(?:for\s+)?elig(?:ibility|ible)?\b",
    re.IGNORECASE,
)
FORBIDDEN_PATTERNS = (
    "patientname,mrn",
    "ssn",
    "password=",
    "api_key",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ensure_cache_dir() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _read_index() -> list[dict[str, Any]]:
    if not INDEX_PATH.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in INDEX_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _write_index(rows: list[dict[str, Any]]) -> None:
    _ensure_cache_dir()
    INDEX_PATH.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def _tokenize(text: str) -> set[str]:
    return set(TOKEN_RE.findall(str(text or "").lower()))


def _contains_forbidden(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(pattern in lowered for pattern in FORBIDDEN_PATTERNS)


def _age_hours(cached_at: str) -> float | None:
    try:
        dt = datetime.fromisoformat(str(cached_at).replace("Z", "+00:00"))
    except ValueError:
        return None
    delta = datetime.now(timezone.utc) - dt.astimezone(timezone.utc)
    return delta.total_seconds() / 3600.0


def _is_fresh(entry: dict[str, Any]) -> bool:
    ttl = entry.get("ttlHours")
    try:
        ttl_hours = float(ttl if ttl is not None else DEFAULT_TTL_HOURS)
    except (TypeError, ValueError):
        ttl_hours = float(DEFAULT_TTL_HOURS)
    age = _age_hours(str(entry.get("cachedAt") or ""))
    if age is None:
        return False
    return age <= ttl_hours


def normalize_eligibility_entry(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate and redact an eligibility snapshot for local cache storage."""
    if not isinstance(raw, dict):
        raise ValueError("entry must be an object")
    blob = json.dumps(raw)
    if _contains_forbidden(blob):
        raise ValueError("entry contains forbidden PHI patterns")

    entry_id = str(raw.get("id") or uuid.uuid4().hex[:16])
    cached_at = str(raw.get("cachedAt") or _utc_now())
    payer_name = str(raw.get("payerName") or raw.get("payer") or "").strip()
    if not payer_name:
        raise ValueError("payerName is required")

    entry: dict[str, Any] = {
        "id": entry_id,
        "cachedAt": cached_at,
        "source": str(raw.get("source") or "manual").strip()[:40],
        "payerName": payer_name,
        "payerId": str(raw.get("payerId") or "").strip()[:32],
        "planDescription": str(raw.get("planDescription") or "").strip()[:120],
        "memberIdRedacted": str(raw.get("memberIdRedacted") or raw.get("memberId") or "").strip()[:32],
        "subscriberRedacted": str(raw.get("subscriberRedacted") or "").strip()[:40],
        "deductibleIndividual": raw.get("deductibleIndividual"),
        "deductibleRemaining": raw.get("deductibleRemaining"),
        "annualMax": raw.get("annualMax"),
        "annualMaxRemaining": raw.get("annualMaxRemaining"),
        "coinsurancePreventive": raw.get("coinsurancePreventive"),
        "coinsuranceBasic": raw.get("coinsuranceBasic"),
        "coinsuranceMajor": raw.get("coinsuranceMajor"),
        "orthoCoverage": raw.get("orthoCoverage"),
        "waitingPeriods": str(raw.get("waitingPeriods") or "").strip()[:300],
        "limitations": str(raw.get("limitations") or "").strip()[:400],
        "ttlHours": raw.get("ttlHours", DEFAULT_TTL_HOURS),
    }
    return entry


def upsert_eligibility_entry(raw: dict[str, Any]) -> dict[str, Any]:
    entry = normalize_eligibility_entry(raw)
    rows = _read_index()
    rows = [row for row in rows if str(row.get("id")) != entry["id"]]
    rows.append(entry)
    rows.sort(key=lambda row: str(row.get("cachedAt") or ""), reverse=True)
    _write_index(rows[:500])
    return {"ok": True, "entry": entry}


def list_eligibility_entries(*, limit: int = 20, fresh_only: bool = True) -> list[dict[str, Any]]:
    rows = _read_index()
    if fresh_only:
        rows = [row for row in rows if _is_fresh(row)]
    cap = max(1, min(int(limit or 20), 100))
    return rows[:cap]


def query_wants_eligibility(query: str) -> bool:
    """True when the user is asking about member benefits / eligibility cache."""
    q = str(query or "")
    if ELIGIBILITY_CONTACT_ONLY_RE.search(q) and not re.search(
        r"\b(deductible|annual\s*max|coinsurance|copay|270|271|remaining|benefit(?:s)?\s*check)\b",
        q,
        re.I,
    ):
        return False
    return bool(ELIGIBILITY_QUERY_RE.search(q))


def search_eligibility_cache(query: str, *, limit: int = 2) -> list[dict[str, Any]]:
    """Search fresh cache rows. Never fall back to unrelated payers on zero overlap."""
    q_tokens = _tokenize(query)
    if not q_tokens:
        return []
    scored: list[tuple[int, dict[str, Any]]] = []
    for entry in _read_index():
        if not _is_fresh(entry):
            continue
        hay = " ".join(
            [
                str(entry.get("payerName") or ""),
                str(entry.get("payerId") or ""),
                str(entry.get("planDescription") or ""),
            ]
        ).lower()
        overlap = len(q_tokens & _tokenize(hay))
        if overlap > 0:
            scored.append((overlap, entry))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [entry for _, entry in scored[: max(1, int(limit))]]


def format_eligibility_hits(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return ""
    lines = [
        "Cached eligibility context (verify before acting — member-specific; may be stale):"
    ]
    for entry in entries:
        payer = str(entry.get("payerName") or "Unknown")
        plan = str(entry.get("planDescription") or "")
        cached = str(entry.get("cachedAt") or "")
        parts = [f"- {payer}"]
        if plan:
            parts.append(f"plan {plan}")
        if entry.get("deductibleRemaining") is not None:
            parts.append(f"deductible remaining ${entry.get('deductibleRemaining')}")
        if entry.get("annualMaxRemaining") is not None:
            parts.append(f"annual max remaining ${entry.get('annualMaxRemaining')}")
        if entry.get("coinsuranceBasic") is not None:
            parts.append(f"basic {entry.get('coinsuranceBasic')}%")
        if entry.get("coinsuranceMajor") is not None:
            parts.append(f"major {entry.get('coinsuranceMajor')}%")
        if entry.get("limitations"):
            lim = str(entry["limitations"])
            if len(lim) > 100:
                lim = lim[:100].rstrip() + "…"
            parts.append(f"limits: {lim}")
        parts.append(f"cached {cached}")
        lines.append(" · ".join(parts))
    return "\n".join(lines)


def eligibility_cache_summary() -> dict[str, Any]:
    rows = _read_index()
    fresh = [row for row in rows if _is_fresh(row)]
    return {
        "ok": True,
        "total": len(rows),
        "fresh": len(fresh),
        "cacheDir": str(CACHE_DIR),
        "defaultTtlHours": DEFAULT_TTL_HOURS,
    }
