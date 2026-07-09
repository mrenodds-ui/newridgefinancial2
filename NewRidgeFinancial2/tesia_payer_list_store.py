"""Tesia / Vyne Dental clearinghouse payer list — routing IDs, not member benefits."""

from __future__ import annotations

import csv
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

NR2_ROOT = Path(__file__).resolve().parent
PAYER_LIST_PATH = NR2_ROOT / "data" / "tesia_payer_list.json"
IMPORT_DIR = NR2_ROOT / "data" / "imports"

TOKEN_RE = re.compile(r"[a-z0-9]{2,}")


def _tokenize(text: str) -> set[str]:
    return set(TOKEN_RE.findall(str(text or "").lower()))


@lru_cache(maxsize=1)
def load_payer_list() -> dict[str, Any]:
    if not PAYER_LIST_PATH.is_file():
        return {"version": 0, "payers": [], "catchAllPayerId": "06126"}
    try:
        data = json.loads(PAYER_LIST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": 0, "payers": [], "catchAllPayerId": "06126"}
    if not isinstance(data, dict):
        return {"version": 0, "payers": [], "catchAllPayerId": "06126"}
    if not isinstance(data.get("payers"), list):
        data["payers"] = []
    data.setdefault("catchAllPayerId", "06126")
    return data


def reload_payer_list() -> dict[str, Any]:
    load_payer_list.cache_clear()
    return load_payer_list()


def payer_list_summary() -> dict[str, Any]:
    data = load_payer_list()
    payers = data.get("payers") or []
    ks = sum(1 for p in payers if isinstance(p, dict) and p.get("kansasRelevant"))
    elig = sum(1 for p in payers if isinstance(p, dict) and p.get("eligibility270") is True)
    return {
        "ok": True,
        "version": data.get("version"),
        "updatedAt": data.get("updatedAt"),
        "count": len(payers),
        "kansasRelevantCount": ks,
        "eligibility270TrueCount": elig,
        "catchAllPayerId": data.get("catchAllPayerId") or "06126",
        "sourceNote": data.get("sourceNote"),
        "path": str(PAYER_LIST_PATH),
        "importDir": str(IMPORT_DIR),
    }


def _score(query: str, query_tokens: set[str], payer: dict[str, Any]) -> int:
    haystack = " ".join(
        [
            str(payer.get("name") or ""),
            str(payer.get("payerId") or ""),
            " ".join(str(a) for a in (payer.get("aliases") or [])),
            str(payer.get("notes") or ""),
        ]
    ).lower()
    score = len(query_tokens & _tokenize(haystack))
    q_norm = re.sub(r"\s+", " ", str(query or "").strip().lower())
    name = str(payer.get("name") or "").lower()
    pid = str(payer.get("payerId") or "").lower()
    if q_norm and q_norm == pid:
        score += 14
    if q_norm and q_norm == name:
        score += 12
    elif q_norm and (q_norm in name or name in q_norm):
        score += 6
    if q_norm and q_norm in pid:
        score += 8
    if payer.get("kansasRelevant") and ("kansas" in query_tokens or "ks" in query_tokens):
        score += 3
    return score


def search_tesia_payers(query: str, *, limit: int = 8, kansas_only: bool = False) -> list[dict[str, Any]]:
    q = str(query or "").strip()
    q_tokens = _tokenize(q)
    payers = [p for p in (load_payer_list().get("payers") or []) if isinstance(p, dict)]
    if kansas_only:
        payers = [p for p in payers if p.get("kansasRelevant")]
    if not q_tokens:
        return payers[: max(1, min(int(limit or 8), 100))]
    scored: list[tuple[int, dict[str, Any]]] = []
    for payer in payers:
        score = _score(q, q_tokens, payer)
        if score > 0:
            scored.append((score, payer))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [p for _, p in scored[: max(1, int(limit))]]


def lookup_payer_id(query: str) -> dict[str, Any] | None:
    by_id = find_payer_by_any_id(query)
    if by_id:
        return by_id
    hits = search_tesia_payers(query, limit=1)
    return hits[0] if hits else None


def format_tesia_hits(payers: list[dict[str, Any]]) -> str:
    if not payers:
        return ""
    catch_all = str(load_payer_list().get("catchAllPayerId") or "06126")
    lines = [
        "Tesia/Vyne payer list matches (clearinghouse routing — not member benefits; "
        f"unlisted payers often use catch-all {catch_all} with full payer name + address):"
    ]
    for payer in payers:
        name = str(payer.get("name") or "Unknown")
        pid = str(payer.get("payerId") or "?")
        bits = [f"- {name} (Tesia ID: {pid})"]
        if payer.get("claimsStatus"):
            bits.append(f"claims={payer['claimsStatus']}")
        if payer.get("eligibility270") is True:
            bits.append("270=yes")
        elif payer.get("eligibility270") is False:
            bits.append("270=no/verify")
        if payer.get("era835") is True:
            bits.append("835=yes")
        elif payer.get("era835") is False:
            bits.append("835=no/verify")
        if payer.get("kansasRelevant"):
            bits.append("KS-relevant")
        lines.append(" · ".join(bits) if len(bits) > 1 else bits[0])
        notes = str(payer.get("notes") or "").strip()
        if notes:
            lines.append(f"  Notes: {notes[:180]}")
    return "\n".join(lines)


def _flag_bool(val: Any) -> bool | None:
    if val is None or val == "":
        return None
    s = str(val).strip().lower()
    if s in {"1", "true", "yes", "y", "t"}:
        return True
    if s in {"0", "false", "no", "n", "f"}:
        return False
    return None


def _split_alt_ids(raw: Any) -> list[str]:
    if isinstance(raw, list):
        parts = [str(x).strip() for x in raw]
    else:
        parts = [p.strip() for p in re.split(r"[\n,;]+", str(raw or ""))]
    out: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if not part or part.upper() in seen:
            continue
        seen.add(part.upper())
        out.append(part)
    return out


def _normalize_import_row(row: dict[str, Any]) -> dict[str, Any] | None:
    # Accept common Desktop Tesia / Vyne export column names (incl. office vyne_payers.json)
    pid = (
        row.get("payerId")
        or row.get("Payer ID")
        or row.get("Payor ID")
        or row.get("payer_id")
        or row.get("PayerID")
        or row.get("ID")
    )
    name = (
        row.get("name")
        or row.get("insurance_name")
        or row.get("Payer Name")
        or row.get("Payor Name")
        or row.get("payer_name")
        or row.get("Payer")
        or row.get("Name")
    )
    pid_s = str(pid or "").strip()
    name_s = str(name or "").strip()
    if not pid_s or not name_s:
        return None

    features = str(row.get("features") or "")
    feat_u = features.upper()
    elig = _flag_bool(row.get("eligibility270") if "eligibility270" in row else row.get("270s Available"))
    if elig is None and feat_u:
        elig = "ELIGIBILITY" in feat_u
    era = _flag_bool(row.get("era835") if "era835" in row else row.get("835s Available"))

    aliases: list[str] = []
    if isinstance(row.get("aliases"), list):
        aliases.extend(str(a).strip() for a in row["aliases"] if str(a).strip())
    aliases.extend(_split_alt_ids(row.get("alt_ids") or row.get("altIds") or row.get("Alt IDs")))
    vyne_name = str(row.get("vyne_payer_id") or row.get("vynePayerId") or "").strip()
    if vyne_name:
        aliases.append(vyne_name)
    # Drop self-alias noise
    aliases = [a for a in dict.fromkeys(aliases) if a.upper() != pid_s.upper()][:40]

    notes_bits = [
        str(row.get("notes") or row.get("Notes") or row.get("Eligibility Notes") or "").strip(),
    ]
    if features:
        notes_bits.append(f"Vyne features: {features.replace(chr(10), ', ')[:120]}")
    if vyne_name:
        notes_bits.append(f"Vyne key: {vyne_name}")
    notes = " ".join(b for b in notes_bits if b)[:240]

    return {
        "payerId": pid_s,
        "name": name_s,
        "aliases": aliases,
        "claimsStatus": str(row.get("claimsStatus") or row.get("Claims Status") or row.get("Status") or "").strip()
        or None,
        "eligibility270": elig,
        "era835": era,
        "notes": notes,
        "kansasRelevant": bool(row.get("kansasRelevant"))
        or bool(re.search(r"\bkansas\b|\bks\b", name_s, re.I)),
        "source": str(row.get("source") or "office-tesia-import"),
    }


def find_payer_by_any_id(payer_id: str) -> dict[str, Any] | None:
    """Resolve by primary Tesia/Vyne payerId or alt_ids/aliases (e.g. SoftDent 65978 → MetLife 0000E).

    Prefers office Desktop Tesia/Vyne import rows over seed/SoftDent-inferred rows.
    """
    key = str(payer_id or "").strip().upper()
    if not key:
        return None
    payers = [p for p in (load_payer_list().get("payers") or []) if isinstance(p, dict)]

    def _is_office(p: dict[str, Any]) -> bool:
        return str(p.get("source") or "") in {"office-tesia-import", "office-vyne-import"}

    primary_office = None
    primary_other = None
    alias_office = None
    alias_other = None
    for payer in payers:
        if str(payer.get("payerId") or "").upper() == key:
            if _is_office(payer):
                primary_office = payer
            elif primary_other is None:
                primary_other = payer
            continue
        for alias in payer.get("aliases") or []:
            if str(alias).strip().upper() == key:
                if _is_office(payer):
                    alias_office = payer
                elif alias_other is None:
                    alias_other = payer
                break
    # SoftDent often stores national IDs that are alt_ids on the office Vyne primary
    return primary_office or alias_office or primary_other or alias_other


def import_payer_rows(rows: list[dict[str, Any]], *, merge: bool = True) -> dict[str, Any]:
    """Merge imported Desktop Tesia/Vyne rows into tesia_payer_list.json."""
    data = reload_payer_list()
    existing = {str(p.get("payerId")).upper(): dict(p) for p in (data.get("payers") or []) if isinstance(p, dict)}
    added = 0
    updated = 0
    for raw in rows or []:
        if not isinstance(raw, dict):
            continue
        norm = _normalize_import_row(raw)
        if not norm:
            continue
        key = norm["payerId"].upper()
        if key in existing and merge:
            prev = existing[key]
            prev.update({k: v for k, v in norm.items() if v not in (None, "", [])})
            existing[key] = prev
            updated += 1
        else:
            existing[key] = norm
            added += 1
    payers = sorted(existing.values(), key=lambda p: str(p.get("name") or "").lower())
    data["payers"] = payers
    data["version"] = int(data.get("version") or 1) + (1 if added or updated else 0)
    from datetime import datetime, timezone

    data["updatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    note = str(data.get("sourceNote") or "")
    if "office-tesia-import" not in note:
        data["sourceNote"] = (note + " Office Desktop Tesia/Vyne import merged.").strip()
    PAYER_LIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    PAYER_LIST_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    reload_payer_list()
    return {
        "ok": True,
        "added": added,
        "updated": updated,
        "count": len(payers),
        "path": str(PAYER_LIST_PATH),
    }


def import_payer_list_file(path: str | Path, *, merge: bool = True) -> dict[str, Any]:
    """Import CSV or JSON export from Desktop Tesia / Vyne."""
    p = Path(path)
    if not p.is_file():
        # Also try imports folder by filename
        alt = IMPORT_DIR / str(path)
        if alt.is_file():
            p = alt
        else:
            return {"ok": False, "error": "file_not_found", "path": str(path)}
    text = p.read_text(encoding="utf-8-sig", errors="replace")
    rows: list[dict[str, Any]] = []
    if p.suffix.lower() == ".json":
        payload = json.loads(text)
        if isinstance(payload, list):
            rows = [r for r in payload if isinstance(r, dict)]
        elif isinstance(payload, dict):
            maybe = payload.get("payers") or payload.get("items") or payload.get("rows")
            if isinstance(maybe, list):
                rows = [r for r in maybe if isinstance(r, dict)]
    else:
        reader = csv.DictReader(text.splitlines())
        rows = [dict(r) for r in reader]
    if not rows:
        return {"ok": False, "error": "no_rows", "path": str(p)}
    result = import_payer_rows(rows, merge=merge)
    result["importedFrom"] = str(p)
    return result


def enrich_payer_reference_from_tesia(*, limit: int = 50) -> dict[str, Any]:
    """Best-effort: attach Tesia IDs into matching payer_reference narrative notes (in-memory report only)."""
    try:
        from payer_reference_store import load_payer_reference, search_payers
    except ImportError:
        return {"ok": False, "error": "payer_reference_unavailable"}
    matches = []
    for payer in (load_payer_list().get("payers") or [])[: max(1, int(limit))]:
        if not isinstance(payer, dict):
            continue
        hits = search_payers(str(payer.get("name") or ""), limit=1)
        if not hits:
            continue
        ref = hits[0]
        matches.append(
            {
                "tesiaId": payer.get("payerId"),
                "tesiaName": payer.get("name"),
                "payerReferenceId": ref.get("id"),
                "payerReferenceName": ref.get("name"),
                "existingPayerIds": list(ref.get("payerIds") or [])[:4],
            }
        )
    return {"ok": True, "joined": matches, "count": len(matches)}
