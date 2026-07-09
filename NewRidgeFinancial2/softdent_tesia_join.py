"""High-confidence SoftDent InsCo ↔ Tesia/Vyne payer-ID join.

Uses exact payer ID overlap only (no fuzzy name matching that maps every Delta to CDKS1).
SoftDent ECSPayorId / office Vyne IDs are treated as the office Desktop Tesia enrollment truth.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from payer_reference_store import load_payer_reference
from tesia_payer_list_store import find_payer_by_any_id, import_payer_rows, load_payer_list, reload_payer_list

NR2_ROOT = Path(__file__).resolve().parent
PAYER_REFERENCE_PATH = NR2_ROOT / "data" / "payer_reference.json"
JOIN_REPORT_PATH = NR2_ROOT / "data" / "softdent_tesia_join_report.json"

# SoftDent sometimes stores labels / phones as payerIds — skip those.
_ID_RE = re.compile(r"^[A-Za-z0-9]{3,8}$")
_SKIP_IDS = {
    "00004",
    "0000E",
    "0000W",
    "00001",
    "SOFTDENT",
    "INSURANCE",
    "N/A",
    "NA",
}


def _is_payer_id(value: str) -> bool:
    s = str(value or "").strip()
    if not s or s.upper() in _SKIP_IDS:
        return False
    if " " in s or "/" in s or "@" in s:
        return False
    # SoftDent carrier labels often ALL CAPS with spaces already filtered; reject long words
    if not _ID_RE.match(s):
        return False
    # Reject pure soft names mistaken as ids
    if s.isalpha() and len(s) > 6 and s.upper() in {"METLIFE", "HUMANA", "GUARDIAN", "AMERITAS", "CIGNA"}:
        return False
    return True


def _is_ecs_like(value: str) -> bool:
    """Prefer real clearinghouse tokens (digits / letter+digit) over bare name stubs."""
    s = str(value or "").strip()
    if not _is_payer_id(s):
        return False
    if any(ch.isdigit() for ch in s):
        return True
    # SoftDent alpha ECS codes (DELAR, DOMIN) — allow only when 4–5 letters
    return bool(re.fullmatch(r"[A-Za-z]{4,5}", s))


def _pick_primary(ids: list[str], *, known_tesia: set[str] | None = None) -> str:
    """Prefer known Tesia IDs, then letter+digit ECS, then first remaining (notes-first order)."""
    if not ids:
        return ""
    known = known_tesia or set()
    for item in ids:
        if item.upper() in known:
            return item
    for item in ids:
        if any(c.isalpha() for c in item) and any(c.isdigit() for c in item):
            return item
    for item in ids:
        if any(c.isdigit() for c in item):
            return item
    return ids[0]


def _add_id(out: list[str], seen: set[str], value: str) -> None:
    s = str(value or "").strip()
    if not s:
        return
    # SoftDent often stores "65978 OR 0000E" as one payerIds entry
    parts = re.split(r"\s+OR\s+", s, flags=re.I) if " OR " in s.upper() else [s]
    for part in parts:
        part = part.strip()
        if not _is_payer_id(part):
            continue
        key = part.upper()
        if key in seen:
            continue
        seen.add(key)
        out.append(part)


def _candidate_ids(payer: dict[str, Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    # Prefer Vyne/e-claim tokens from notes first (office Desktop Tesia truth)
    notes = str(payer.get("narrativeNotes") or "")
    for match in re.finditer(r"Vyne/e-claim\s+([A-Za-z0-9]{3,8}(?:\s+OR\s+[A-Za-z0-9]{3,8})?)", notes, re.I):
        _add_id(out, seen, match.group(1))
    for raw in payer.get("payerIds") or []:
        _add_id(out, seen, str(raw or ""))
    return out


def build_join_plan() -> dict[str, Any]:
    pref = load_payer_reference()
    tesia = {str(p.get("payerId") or "").upper(): p for p in (load_payer_list().get("payers") or []) if p.get("payerId")}
    known = set(tesia.keys())
    payers = [p for p in (pref.get("payers") or []) if isinstance(p, dict)]

    exact: list[dict[str, Any]] = []
    expand: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []

    for payer in payers:
        ids = _candidate_ids(payer)
        # Match primary Tesia ID or office alt_ids (SoftDent 65978 → Vyne 0000E).
        # Prefer office Desktop Tesia/Vyne import resolution over seed rows.
        resolved: list[tuple[str, dict[str, Any]]] = []
        for cand in ids:
            hit = find_payer_by_any_id(cand) or tesia.get(cand.upper())
            if hit:
                resolved.append((cand, hit))
        if resolved:
            # Prefer office primary when SoftDent used a national/alt ID
            hit0 = resolved[0][1]
            primary = str(hit0.get("payerId") or resolved[0][0])
            for cand, hit in resolved:
                src = str(hit.get("source") or "")
                if src in {"office-tesia-import", "office-vyne-import"}:
                    primary = str(hit.get("payerId") or cand)
                    hit0 = hit
                    break
            exact.append(
                {
                    "payerReferenceId": payer.get("id"),
                    "name": payer.get("name"),
                    "source": payer.get("source"),
                    "tesiaPayerId": primary,
                    "matchedSoftDentId": resolved[0][0],
                    "allMatchingIds": [c for c, _ in resolved],
                    "kansasRelevant": bool(hit0.get("kansasRelevant")),
                }
            )
            continue
        # Expand Tesia catalog from SoftDent/office ECS IDs, or curated IDs that include digits.
        # Exact ID only — never invent IDs from fuzzy names / alpha stubs (CARE, SELF).
        source = str(payer.get("source") or "")
        softdentish = source in {"softdent-insco-sensei", "office-insurance-xlsx"}
        if softdentish:
            ecs_ids = [i for i in ids if _is_payer_id(i)]
        else:
            ecs_ids = [i for i in ids if _is_ecs_like(i) and any(ch.isdigit() for ch in i)]
        if ecs_ids:
            primary = _pick_primary(ecs_ids, known_tesia=known)
            expand.append(
                {
                    "payerReferenceId": payer.get("id"),
                    "name": payer.get("name"),
                    "source": source or "payer-reference",
                    "tesiaPayerId": primary,
                    "candidateIds": ecs_ids,
                    "kansasRelevant": bool(
                        re.search(r"\bkansas\b|\bks\b", str(payer.get("name") or ""), re.I)
                        or primary.upper() in {"CDKS1", "47163", "47171", "BKC01"}
                    ),
                }
            )
        else:
            unmatched.append(
                {
                    "payerReferenceId": payer.get("id"),
                    "name": payer.get("name"),
                    "source": payer.get("source"),
                    "candidateIds": ids,
                }
            )

    return {
        "ok": True,
        "builtAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "exactMatches": exact,
        "expandFromSoftDent": expand,
        "unmatched": unmatched,
        "counts": {
            "exact": len(exact),
            "expand": len(expand),
            "unmatched": len(unmatched),
            "payerReference": len(payers),
            "tesiaSeed": len(tesia),
        },
    }


def apply_softdent_tesia_join(*, write_payer_reference: bool = True, expand_tesia: bool = True) -> dict[str, Any]:
    """Expand Tesia list from SoftDent ECS IDs and stamp tesiaPayerId on payer_reference."""
    plan = build_join_plan()
    expanded = 0
    stamped = 0

    if expand_tesia:
        rows = []
        for row in plan["expandFromSoftDent"]:
            rows.append(
                {
                    "payerId": row["tesiaPayerId"],
                    "name": row["name"],
                    "aliases": [],
                    "claimsStatus": None,
                    "eligibility270": None,
                    "era835": None,
                    "notes": f"Imported from SoftDent/office ECS id via softdent_tesia_join ({row.get('source')})",
                    "kansasRelevant": row.get("kansasRelevant"),
                    "source": "softdent-ecs-import",
                }
            )
        if rows:
            result = import_payer_rows(rows, merge=True)
            expanded = int(result.get("added") or 0) + int(result.get("updated") or 0)

    if write_payer_reference:
        data = json.loads(PAYER_REFERENCE_PATH.read_text(encoding="utf-8"))
        by_id = {str(p.get("id")): p for p in (data.get("payers") or []) if isinstance(p, dict)}
        # Recompute after expand so exact set includes new IDs
        reload_payer_list()
        plan = build_join_plan()
        for row in plan["exactMatches"] + [
            {
                "payerReferenceId": r["payerReferenceId"],
                "tesiaPayerId": r["tesiaPayerId"],
                "name": r["name"],
            }
            for r in plan["expandFromSoftDent"]
        ]:
            cur = by_id.get(str(row.get("payerReferenceId") or ""))
            if not cur:
                continue
            tid = str(row.get("tesiaPayerId") or "").strip()
            if not tid:
                continue
            ids = list(cur.get("payerIds") or [])
            if tid not in ids and tid.upper() not in {str(x).upper() for x in ids}:
                ids.insert(0, tid)
                cur["payerIds"] = ids[:12]
            if cur.get("tesiaPayerId") != tid:
                cur["tesiaPayerId"] = tid
                stamped += 1
            notes = str(cur.get("narrativeNotes") or "")
            tag = f"Tesia/Vyne ID {tid}"
            if tag not in notes:
                cur["narrativeNotes"] = (notes + f" {tag}.").strip()[:400]
        data["updatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        note = str(data.get("sourceNote") or "")
        if "softdent_tesia_join" not in note:
            data["sourceNote"] = (note + " SoftDent↔Tesia join applied (exact ECS/Vyne IDs).").strip()
        PAYER_REFERENCE_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        try:
            from payer_reference_store import load_payer_reference

            load_payer_reference.cache_clear()
        except Exception:
            pass

    report = {
        **plan,
        "appliedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expandedTesiaRows": expanded,
        "stampedPayerReference": stamped,
    }
    JOIN_REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "expandedTesiaRows": expanded,
        "stampedPayerReference": stamped,
        "counts": report["counts"],
        "reportPath": str(JOIN_REPORT_PATH),
        "kansasExact": [r for r in report["exactMatches"] if r.get("kansasRelevant")][:10],
        "sampleExpanded": report["expandFromSoftDent"][:8],
        "sampleUnmatched": report["unmatched"][:8],
    }


def format_join_summary(result: dict[str, Any] | None = None) -> str:
    result = result or apply_softdent_tesia_join(write_payer_reference=False, expand_tesia=False)
    counts = result.get("counts") or {}
    lines = [
        "SoftDent <-> Tesia/Vyne join (exact payer IDs only - no fuzzy name matching):",
        f"- Exact ID matches: {counts.get('exact', result.get('stampedPayerReference', 0))}",
        f"- SoftDent ECS IDs to add to Tesia list: {counts.get('expand', result.get('expandedTesiaRows', 0))}",
        f"- Unmatched (no ECS-like ID): {counts.get('unmatched', 0)}",
    ]
    for row in (result.get("kansasExact") or [])[:5]:
        lines.append(f"  KS: {row.get('name')} → {row.get('tesiaPayerId')}")
    if result.get("reportPath"):
        lines.append(f"- Report: {result['reportPath']}")
    return "\n".join(lines)


if __name__ == "__main__":
    out = apply_softdent_tesia_join(write_payer_reference=True, expand_tesia=True)
    print(format_join_summary(out))
    print(json.dumps(out["counts"], indent=2))
