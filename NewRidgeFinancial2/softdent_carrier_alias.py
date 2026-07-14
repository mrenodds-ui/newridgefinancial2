"""HAL-10600 — Spine ↔ SoftDent company-master carrier alias reconciliation.

Fuzzy match (Jaro-Winkler + token_set) with first-4 / distinctive-token blocking.
Confidence bands (Moonshot):
  >0.85 → auto-accept
  0.60–0.85 → manual (HAL chip / pending review)
  <0.60 → reject

Does NOT invent InsCo×ADA dollars or gold payment lines. empty != $0.
No SoftDent write-back.
"""

from __future__ import annotations

import csv
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz
from rapidfuzz.distance import JaroWinkler

from softdent_insco_ada_spine import _table_exists
from softdent_treatment_planning import resolve_analytics_db, resolve_exports_dir

DEF_ID = "HAL-10600"
PACKAGE_BUILD_ID = "hal-10600"

AUTO_MIN = 85.0
MANUAL_MIN = 60.0

STOPWORDS = frozenset(
    {
        "OF",
        "THE",
        "AND",
        "CO",
        "COMPANY",
        "INSURANCE",
        "LIFE",
        "HEALTH",
        "DENTAL",
        "PLAN",
        "PLANS",
        "BENEFITS",
        "BENEFIT",
        "GROUP",
        "CARE",
        "INC",
        "LLC",
        "CLAIMS",
        "SERVICES",
        "SERVICE",
        "NATIONAL",
        "MUTUAL",
        "FINANCIAL",
        "AMERICA",
        "AMERICAN",
        "ASSOC",
        "ASSOCIATION",
        "ADMINISTRATORS",
        "ADMINISTRATOR",
        "SOLUTIONS",
        "SYSTEMS",
        "SYSTEM",
        "DEPT",
        "DEPARTMENT",
        "FOR",
        "TO",
        "IN",
    }
)

STATE_NAMES = {
    "ALABAMA": "AL",
    "ARIZONA": "AZ",
    "ARKANSAS": "AR",
    "CALIFORNIA": "CA",
    "COLORADO": "CO",
    "CONNECTICUT": "CT",
    "FLORIDA": "FL",
    "GEORGIA": "GA",
    "ILLINOIS": "IL",
    "INDIANA": "IN",
    "IOWA": "IA",
    "KANSAS": "KS",
    "KENTUCKY": "KY",
    "LOUISIANA": "LA",
    "MAINE": "ME",
    "MARYLAND": "MD",
    "MASSACHUSETTS": "MA",
    "MICHIGAN": "MI",
    "MINNESOTA": "MN",
    "MISSISSIPPI": "MS",
    "MISSOURI": "MO",
    "NEBRASKA": "NE",
    "NEVADA": "NV",
    "NEWJERSEY": "NJ",
    "NEWMEXICO": "NM",
    "NEWYORK": "NY",
    "NORTHCAROLINA": "NC",
    "OHIO": "OH",
    "OKLAHOMA": "OK",
    "OREGON": "OR",
    "PENNSYLVANIA": "PA",
    "SOUTHCAROLINA": "SC",
    "TENNESSEE": "TN",
    "TEXAS": "TX",
    "UTAH": "UT",
    "VIRGINIA": "VA",
    "WASHINGTON": "WA",
    "WESTVIRGINIA": "WV",
    "WISCONSIN": "WI",
}

ABBREV = (
    (r"\bBCBS\b", "BLUE CROSS BLUE SHIELD"),
    (r"\bB C B S\b", "BLUE CROSS BLUE SHIELD"),
    (r"\bUHC\b", "UNITED HEALTHCARE"),
    (r"\bUMR\b", "UNITED MEDICAL RESOURCES"),
    (r"\bDDIC\b", "DELTA DENTAL"),
    (r"\bGEHA\b", "GOVERNMENT EMPLOYEES HEALTH ASSOCIATION"),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_carrier_name(name: str) -> str:
    s = str(name or "").upper().strip()
    s = re.sub(r"^\d{4}\s*[-–]\s*", "", s)
    s = s.replace("&", " AND ")
    s = re.sub(r"[^A-Z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    for pat, repl in ABBREV:
        s = re.sub(pat, repl, s)
    # Expand full state names to codes for comparison
    parts = []
    for tok in s.split():
        parts.append(STATE_NAMES.get(tok, tok))
    s = " ".join(parts)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _tokens(s: str) -> set[str]:
    return {t for t in s.split() if len(t) >= 2}


def _distinctive(s: str) -> set[str]:
    return {t for t in _tokens(s) if t not in STOPWORDS and len(t) >= 3}


def _state_codes(s: str) -> set[str]:
    out: set[str] = set()
    for tok in s.split():
        if len(tok) == 2 and tok.isalpha() and tok in set(STATE_NAMES.values()):
            out.add(tok)
    return out


def _plan_codes(raw: str) -> set[str]:
    return set(re.findall(r"\b\d{3,}\b", str(raw or "").upper()))


def blocked_pair(a_norm: str, b_norm: str) -> bool:
    """Moonshot blocking: first-4 chars and/or distinctive-token overlap."""
    if not a_norm or not b_norm:
        return False
    if a_norm[:4] == b_norm[:4]:
        return True
    da, db = _distinctive(a_norm), _distinctive(b_norm)
    if da & db:
        return True
    # Prefix containment of full normalized string
    if len(a_norm) >= 4 and (a_norm.startswith(b_norm) or b_norm.startswith(a_norm)):
        return True
    return False


def match_score(master_name: str, spine_name: str) -> float:
    """0–100 score. 0 if blocked-out, state conflict, or plan-code conflict."""
    a = normalize_carrier_name(master_name)
    b = normalize_carrier_name(spine_name)
    if not a or not b:
        return 0.0
    if a == b:
        return 100.0
    if not blocked_pair(a, b):
        return 0.0
    sa, sb = _state_codes(a), _state_codes(b)
    if sa and sb and sa.isdisjoint(sb):
        return 0.0
    pa, pb = _plan_codes(master_name), _plan_codes(spine_name)
    # Different numeric plan suffixes → cap later into manual band
    plan_conflict = bool(pa and pb and pa.isdisjoint(pb))

    jw = JaroWinkler.normalized_similarity(a, b) * 100.0
    ts = float(fuzz.token_set_ratio(a, b))
    # Blend; require distinctive overlap already via block
    score = max(jw, 0.55 * ts + 0.45 * jw)
    if plan_conflict:
        score = min(score, AUTO_MIN - 0.01)  # force manual review
    # Cognate trap: GUARANTEE vs GUARDIAN — high JW, different distinctive
    da, db = _distinctive(a), _distinctive(b)
    if da and db and not (da & db) and jw < 92.0:
        return 0.0
    return float(score)


def confidence_band(score: float) -> str:
    """Moonshot bands: >0.85 auto · 0.60–0.85 manual · <0.60 reject."""
    if score > AUTO_MIN:
        return "auto"
    if score >= MANUAL_MIN:
        return "manual"
    return "reject"


def ensure_carrier_alias_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS carrier_alias (
            id INTEGER PRIMARY KEY,
            spine_carrier_name TEXT NOT NULL,
            master_company_id TEXT,
            master_company_name TEXT NOT NULL,
            match_score REAL NOT NULL,
            confidence TEXT NOT NULL,
            review_status TEXT NOT NULL,
            match_method TEXT,
            created_at_utc TEXT NOT NULL,
            UNIQUE(master_company_name)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_carrier_alias_spine "
        "ON carrier_alias(spine_carrier_name)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_carrier_alias_status "
        "ON carrier_alias(review_status, confidence)"
    )


def list_spine_carriers(*, db_path: Path | None = None) -> list[str]:
    target = Path(db_path) if db_path else resolve_analytics_db()
    if not target or not target.is_file():
        return []
    conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        if not _table_exists(conn, "insco_ada_probabilistic_estimates"):
            return []
        return [
            str(r[0]).strip()
            for r in conn.execute(
                "SELECT DISTINCT insurance_company FROM insco_ada_probabilistic_estimates"
            )
            if r[0]
        ]
    finally:
        conn.close()


def list_master_companies_with_ids(
    *, db_path: Path | None = None, likely_active_only: bool = True
) -> list[dict[str, str]]:
    target = Path(db_path) if db_path else resolve_analytics_db()
    if not target or not target.is_file():
        return []
    conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        if not _table_exists(conn, "insurance_company_reference"):
            return []
        sql = """
            SELECT insurance_company, company_id, active_status
            FROM insurance_company_reference
        """
        if likely_active_only:
            sql += " WHERE active_status='likely_active'"
        sql += " ORDER BY insurance_company"
        return [
            {
                "insurance_company": str(r[0]).strip(),
                "company_id": str(r[1] or "").strip(),
                "active_status": str(r[2] or "").strip(),
            }
            for r in conn.execute(sql)
            if r[0]
        ]
    finally:
        conn.close()


def propose_alias_matches(
    *,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Propose best spine match for each likely_active master name."""
    spine = list_spine_carriers(db_path=db_path)
    masters = list_master_companies_with_ids(db_path=db_path, likely_active_only=True)
    spine_by_upper = {s.upper(): s for s in spine}
    proposals: list[dict[str, Any]] = []
    for m in masters:
        name = m["insurance_company"]
        # Exact overlap → identity alias
        if name.upper() in spine_by_upper:
            proposals.append(
                {
                    "spine_carrier_name": spine_by_upper[name.upper()],
                    "master_company_id": m["company_id"] or None,
                    "master_company_name": name,
                    "match_score": 100.0,
                    "confidence": "auto",
                    "review_status": "accepted",
                    "match_method": "exact",
                }
            )
            continue
        best_spine = None
        best_score = 0.0
        for s in spine:
            sc = match_score(name, s)
            if sc > best_score:
                best_score = sc
                best_spine = s
        band = confidence_band(best_score)
        if band == "reject" or best_spine is None:
            proposals.append(
                {
                    "spine_carrier_name": "",
                    "master_company_id": m["company_id"] or None,
                    "master_company_name": name,
                    "match_score": float(best_score),
                    "confidence": "reject",
                    "review_status": "rejected",
                    "match_method": "fuzzy_blocked_jw",
                }
            )
            continue
        proposals.append(
            {
                "spine_carrier_name": best_spine,
                "master_company_id": m["company_id"] or None,
                "master_company_name": name,
                "match_score": float(best_score),
                "confidence": band,
                "review_status": "accepted" if band == "auto" else "pending",
                "match_method": "fuzzy_blocked_jw",
            }
        )
    return proposals


def persist_carrier_aliases(
    proposals: list[dict[str, Any]],
    *,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Replace carrier_alias with proposals (read-only SoftDent; local SQLite only)."""
    target = Path(db_path) if db_path else resolve_analytics_db()
    out: dict[str, Any] = {
        "ok": False,
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "inserted": 0,
        "autoAccepted": 0,
        "manualPending": 0,
        "rejected": 0,
        "exactIdentity": 0,
        "emptyIsNotZero": True,
        "triggersGoldIngest": False,
    }
    if not target or not target.is_file():
        out["error"] = "analytics_db_missing"
        return out
    stamp = _utc_now()
    conn = sqlite3.connect(str(target), timeout=30.0)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        ensure_carrier_alias_schema(conn)
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM carrier_alias")
        inserted = 0
        for p in proposals:
            # Skip pure rejects from table? Moonshot wants mapping for the 144 gap —
            # keep pending+auto+exact; optionally keep rejects for audit.
            conf = str(p.get("confidence") or "")
            status = str(p.get("review_status") or "")
            if conf == "reject":
                out["rejected"] = int(out["rejected"]) + 1
                # still store rejects for audit trail
            spine = str(p.get("spine_carrier_name") or "").strip()
            master = str(p.get("master_company_name") or "").strip()
            if not master:
                continue
            conn.execute(
                """
                INSERT OR REPLACE INTO carrier_alias (
                    spine_carrier_name, master_company_id, master_company_name,
                    match_score, confidence, review_status, match_method, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    spine,
                    p.get("master_company_id"),
                    master,
                    float(p.get("match_score") or 0),
                    conf,
                    status,
                    p.get("match_method"),
                    stamp,
                ),
            )
            inserted += 1
            if conf == "auto" and status == "accepted":
                out["autoAccepted"] = int(out["autoAccepted"]) + 1
                if p.get("match_method") == "exact":
                    out["exactIdentity"] = int(out["exactIdentity"]) + 1
            elif conf == "manual" and status == "pending":
                out["manualPending"] = int(out["manualPending"]) + 1
        conn.commit()
        out.update({"ok": True, "inserted": inserted, "dbPath": str(target), "createdAt": stamp})
        return out
    except Exception as exc:  # noqa: BLE001
        try:
            conn.rollback()
        except Exception:
            pass
        out["error"] = f"{type(exc).__name__}:{exc}"
        return out
    finally:
        conn.close()


def export_carrier_alias_mapping_csv(
    *,
    db_path: Path | None = None,
    dest: Path | None = None,
) -> dict[str, Any]:
    target = Path(db_path) if db_path else resolve_analytics_db()
    out_dir = Path(dest) if dest else resolve_exports_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "carrier_alias_mapping.csv"
    out: dict[str, Any] = {"ok": False, "csvPath": str(path), "rows": 0}
    if not target or not target.is_file():
        out["error"] = "analytics_db_missing"
        return out
    conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        if not _table_exists(conn, "carrier_alias"):
            out["error"] = "carrier_alias_missing"
            return out
        rows = conn.execute(
            """
            SELECT spine_carrier_name, master_company_id, master_company_name,
                   match_score, confidence, review_status, match_method, created_at_utc
            FROM carrier_alias
            ORDER BY
              CASE confidence WHEN 'auto' THEN 0 WHEN 'manual' THEN 1 ELSE 2 END,
              match_score DESC,
              master_company_name
            """
        ).fetchall()
    finally:
        conn.close()
    cols = [
        "spine_carrier_name",
        "master_company_id",
        "master_company_name",
        "match_score",
        "confidence",
        "review_status",
        "match_method",
        "created_at_utc",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            w.writerow(list(r))
    out.update({"ok": True, "rows": len(rows), "csvPath": str(path)})
    return out


def reconcile_carrier_aliases(
    *,
    db_path: Path | None = None,
    dest: Path | None = None,
) -> dict[str, Any]:
    """Full reconcile: propose → persist → CSV. No synthetic payment lines."""
    proposals = propose_alias_matches(db_path=db_path)
    persisted = persist_carrier_aliases(proposals, db_path=db_path)
    exported = export_carrier_alias_mapping_csv(db_path=db_path, dest=dest)
    status = carrier_alias_status(db_path=db_path)
    return {
        "ok": bool(persisted.get("ok")) and bool(exported.get("ok")),
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "persist": persisted,
        "export": exported,
        "status": status,
        "honesty": (
            "Alias map only — does not invent InsCo×ADA dollars or gold lines. "
            "empty != $0."
        ),
        "triggersGoldIngest": False,
        "emptyIsNotZero": True,
    }


def load_accepted_alias_maps(
    *, db_path: Path | None = None
) -> dict[str, Any]:
    """Maps for catalog join: master_upper→spine, spine_upper→master ids/names."""
    target = Path(db_path) if db_path else resolve_analytics_db()
    empty = {
        "masterToSpine": {},
        "masterToId": {},
        "spineToMasters": {},
        "pending": [],
    }
    if not target or not target.is_file():
        return empty
    conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        if not _table_exists(conn, "carrier_alias"):
            return empty
        master_to_spine: dict[str, str] = {}
        master_to_id: dict[str, str] = {}
        spine_to_masters: dict[str, list[dict[str, str]]] = {}
        pending: list[dict[str, Any]] = []
        for row in conn.execute(
            """
            SELECT spine_carrier_name, master_company_id, master_company_name,
                   match_score, confidence, review_status
            FROM carrier_alias
            """
        ):
            spine, mid, mname, score, conf, status = row
            mname = str(mname or "").strip()
            spine = str(spine or "").strip()
            if not mname:
                continue
            if conf == "manual" and status == "pending":
                pending.append(
                    {
                        "masterCompanyName": mname,
                        "masterCompanyId": mid,
                        "spineCarrierName": spine,
                        "matchScore": score,
                        "confidence": conf,
                        "reviewStatus": status,
                    }
                )
            if status != "accepted" or not spine:
                continue
            master_to_spine[mname.upper()] = spine
            if mid:
                master_to_id[mname.upper()] = str(mid)
            spine_to_masters.setdefault(spine.upper(), []).append(
                {"masterCompanyName": mname, "masterCompanyId": str(mid or "")}
            )
        return {
            "masterToSpine": master_to_spine,
            "masterToId": master_to_id,
            "spineToMasters": spine_to_masters,
            "pending": pending,
        }
    finally:
        conn.close()


def carrier_alias_status(*, db_path: Path | None = None) -> dict[str, Any]:
    target = Path(db_path) if db_path else resolve_analytics_db()
    out: dict[str, Any] = {
        "ok": False,
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "emptyIsNotZero": True,
        "triggersGoldIngest": False,
    }
    if not target or not target.is_file():
        out["error"] = "analytics_db_missing"
        return out
    conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        if not _table_exists(conn, "carrier_alias"):
            out["error"] = "carrier_alias_missing"
            out["message"] = "Run scripts/reconcile_carrier_aliases.py"
            return out

        def _count(where: str) -> int:
            return int(conn.execute(f"SELECT COUNT(*) FROM carrier_alias WHERE {where}").fetchone()[0] or 0)

        total = int(conn.execute("SELECT COUNT(*) FROM carrier_alias").fetchone()[0] or 0)
        auto_acc = _count("confidence='auto' AND review_status='accepted'")
        exact = _count("match_method='exact' AND review_status='accepted'")
        fuzzy_auto = _count(
            "confidence='auto' AND review_status='accepted' AND match_method!='exact'"
        )
        pending = _count("confidence='manual' AND review_status='pending'")
        rejected = _count("confidence='reject' OR review_status='rejected'")

        # Gap after accepted aliases (exact + fuzzy auto + accepted manual)
        from softdent_insurance_company_reference import list_likely_active_companies

        likely = list_likely_active_companies(db_path=target, limit=5000)
        spine = {
            s.upper()
            for s in list_spine_carriers(db_path=target)
        }
        maps = load_accepted_alias_maps(db_path=target)
        master_to_spine = maps["masterToSpine"]
        still_missing = []
        for name in likely:
            u = name.upper()
            if u in spine:
                continue
            if u in master_to_spine:
                continue
            still_missing.append(name)
        pending_names = {
            str(p.get("masterCompanyName") or "").upper() for p in maps["pending"]
        }
        unmatched_no_candidate = [
            n for n in still_missing if n.upper() not in pending_names
        ]
        out.update(
            {
                "ok": True,
                "totalRows": total,
                "autoAccepted": auto_acc,
                "exactIdentity": exact,
                "fuzzyAutoAccepted": fuzzy_auto,
                "manualPending": pending,
                "rejected": rejected,
                "likelyActive": len(likely),
                "spineCarriers": len(spine),
                "likelyActiveNotInSpine": len(still_missing),
                "likelyActiveNotInSpineSample": still_missing[:25],
                "pendingManualSample": maps["pending"][:15],
                "unmatchedNoCandidate": len(unmatched_no_candidate),
                "unmatchedNoCandidateSample": unmatched_no_candidate[:25],
                "acceptanceLikelyActiveNotInSpineMax": 20,
                "acceptanceGateMet": len(still_missing) <= 20,
                "dbPath": str(target),
                "honesty": (
                    "Accepted aliases join existing spine settlements only — "
                    "no invented dollars; pending manuals need HAL confirmation."
                ),
            }
        )
        return out
    finally:
        conn.close()


def resolve_accepted_alias_for_tp(
    payer: str,
    *,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Resolve staff payer → spine carrier for TP (HAL-10601 / HAL-10604).

    Any ``review_status='accepted'`` row resolves (auto or operator/Moonshot
    manual-accepted). Pending manuals (``confidence='manual'`` +
    ``review_status='pending'``) are blocked — never auto-used.
    Does not invent dollars.
    """
    out: dict[str, Any] = {
        "viaAlias": False,
        "blockedPending": False,
        "spineCarrierName": None,
        "masterCompanyId": None,
        "masterCompanyName": None,
    }
    raw = str(payer or "").strip()
    if not raw:
        return out
    maps = load_accepted_alias_maps(db_path=db_path)
    payer_u = raw.upper()

    for pend in maps.get("pending") or []:
        mname = str(pend.get("masterCompanyName") or "").strip()
        mid = str(pend.get("masterCompanyId") or "").strip()
        if mname.upper() == payer_u or (mid and mid == raw):
            out.update(
                {
                    "blockedPending": True,
                    "pending": pend,
                    "masterCompanyName": mname or raw,
                    "masterCompanyId": mid or None,
                    "spineCarrierName": pend.get("spineCarrierName"),
                }
            )
            return out

    master_to_spine = maps.get("masterToSpine") or {}
    master_to_id = maps.get("masterToId") or {}

    # Exact master name
    if payer_u in master_to_spine:
        out.update(
            {
                "viaAlias": True,
                "spineCarrierName": master_to_spine[payer_u],
                "masterCompanyId": master_to_id.get(payer_u),
                "masterCompanyName": raw,
            }
        )
        return out

    # master_company_id match (Moonshot step 1)
    target = Path(db_path) if db_path else resolve_analytics_db()
    if target and target.is_file():
        conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
        try:
            if _table_exists_alias(conn):
                row = conn.execute(
                    """
                    SELECT spine_carrier_name, master_company_id, master_company_name
                    FROM carrier_alias
                    WHERE review_status='accepted'
                      AND (
                        master_company_id = ?
                        OR upper(master_company_name) = upper(?)
                      )
                    LIMIT 1
                    """,
                    (raw, raw),
                ).fetchone()
                if row and row[0]:
                    out.update(
                        {
                            "viaAlias": True,
                            "spineCarrierName": str(row[0]),
                            "masterCompanyId": str(row[1] or "") or None,
                            "masterCompanyName": str(row[2] or raw),
                        }
                    )
                    return out
                # Pending by id
                pend_row = conn.execute(
                    """
                    SELECT spine_carrier_name, master_company_id, master_company_name,
                           match_score, confidence, review_status
                    FROM carrier_alias
                    WHERE confidence='manual' AND review_status='pending'
                      AND (master_company_id = ? OR upper(master_company_name)=upper(?))
                    LIMIT 1
                    """,
                    (raw, raw),
                ).fetchone()
                if pend_row:
                    out.update(
                        {
                            "blockedPending": True,
                            "spineCarrierName": pend_row[0],
                            "masterCompanyId": pend_row[1],
                            "masterCompanyName": pend_row[2] or raw,
                            "pending": {
                                "masterCompanyName": pend_row[2],
                                "masterCompanyId": pend_row[1],
                                "spineCarrierName": pend_row[0],
                                "matchScore": pend_row[3],
                                "confidence": pend_row[4],
                                "reviewStatus": pend_row[5],
                            },
                        }
                    )
                    return out
        finally:
            conn.close()
    return out


def _table_exists_alias(conn: sqlite3.Connection) -> bool:
    return bool(
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='carrier_alias'"
        ).fetchone()
    )


# HAL-10604 / HAL-10605 — Moonshot industry HIGH (+ optional MEDIUM pending)
MOONSHOT_INDUSTRY_HIGH: list[tuple[str, str]] = [
    ("Assurant", "SUN LIFE FINANCIAL"),
    ("Connecticut General", "CIGNA DENTAL"),
    ("Met Life", "METLIFE DENTAL"),
    ("Met Life /dental Claims", "METLIFE DENTAL"),
    ("Met Life/ Pepsico", "METLIFE DENTAL"),
    ("UniCare", "ANTHEM - 1115"),
    ("Unicare Life & Health Insurance Co", "ANTHEM - 1115"),
    # HAL-10605 industry knowledge consult — NEW HIGH only
    ("Great-west", "CIGNA DENTAL"),
    ("Kanawha Benefit Solutions, Inc", "HUMANA DENTAL"),
]
MOONSHOT_INDUSTRY_MEDIUM: list[tuple[str, str]] = [
    ("Coventry", "AETNA"),
    ("Coventry Health Care Of Kansas", "AETNA"),
]


def apply_moonshot_industry_aliases(
    *,
    db_path: Path | None = None,
    include_medium_as_pending: bool = True,
) -> dict[str, Any]:
    """HAL-10604 — accept Moonshot HIGH industry aliases; MEDIUM → pending.

    Does not invent settlement dollars. Spine names must exist in spine list.
    """
    target = Path(db_path) if db_path else resolve_analytics_db()
    out: dict[str, Any] = {
        "ok": False,
        "def": "HAL-10604",
        "packageBuildId": "hal-10604",
        "highAccepted": 0,
        "mediumPending": 0,
        "emptyIsNotZero": True,
        "triggersGoldIngest": False,
    }
    if not target or not target.is_file():
        out["error"] = "analytics_db_missing"
        return out
    spine_map = {s.upper(): s for s in list_spine_carriers(db_path=target)}
    conn = sqlite3.connect(str(target), timeout=30.0)
    try:
        ensure_carrier_alias_schema(conn)
        high_n = 0
        for master, spine_name in MOONSHOT_INDUSTRY_HIGH:
            exact = spine_map.get(spine_name.upper())
            master_exists = conn.execute(
                "SELECT 1 FROM carrier_alias WHERE upper(master_company_name)=upper(?) LIMIT 1",
                (master,),
            ).fetchone()
            if not exact:
                if master_exists:
                    out.setdefault("errors", []).append(f"spine_missing:{spine_name}")
                continue
            if not master_exists:
                continue
            cur = conn.execute(
                """
                UPDATE carrier_alias
                SET spine_carrier_name=?,
                    match_score=90.0,
                    confidence='manual',
                    review_status='accepted',
                    match_method='moonshot_industry'
                WHERE upper(master_company_name)=upper(?)
                """,
                (exact, master),
            )
            high_n += int(cur.rowcount or 0)
        med_n = 0
        if include_medium_as_pending:
            for master, spine_name in MOONSHOT_INDUSTRY_MEDIUM:
                exact = spine_map.get(spine_name.upper())
                master_exists = conn.execute(
                    "SELECT 1 FROM carrier_alias WHERE upper(master_company_name)=upper(?) LIMIT 1",
                    (master,),
                ).fetchone()
                if not exact:
                    if master_exists:
                        out.setdefault("errors", []).append(f"spine_missing:{spine_name}")
                    continue
                if not master_exists:
                    continue
                cur = conn.execute(
                    """
                    UPDATE carrier_alias
                    SET spine_carrier_name=?,
                        match_score=75.0,
                        confidence='manual',
                        review_status='pending',
                        match_method='moonshot_industry_medium'
                    WHERE upper(master_company_name)=upper(?)
                    """,
                    (exact, master),
                )
                med_n += int(cur.rowcount or 0)
        conn.commit()
        out.update(
            {
                "ok": not bool(out.get("errors")),
                "highAccepted": high_n,
                "mediumPending": med_n,
                "highExpected": len(MOONSHOT_INDUSTRY_HIGH),
                "dbPath": str(target),
            }
        )
        return out
    finally:
        conn.close()


def accept_pending_alias(
    master_company_name: str,
    *,
    db_path: Path | None = None,
    accept: bool = True,
) -> dict[str, Any]:
    """HAL confirmation for 0.60–0.85 band."""
    target = Path(db_path) if db_path else resolve_analytics_db()
    out: dict[str, Any] = {"ok": False, "def": DEF_ID}
    if not target or not target.is_file():
        out["error"] = "analytics_db_missing"
        return out
    name = str(master_company_name or "").strip()
    conn = sqlite3.connect(str(target), timeout=30.0)
    try:
        ensure_carrier_alias_schema(conn)
        status = "accepted" if accept else "rejected"
        cur = conn.execute(
            """
            UPDATE carrier_alias
            SET review_status=?, confidence=CASE WHEN ?='accepted' THEN 'manual' ELSE 'reject' END
            WHERE upper(master_company_name)=upper(?)
              AND confidence='manual' AND review_status='pending'
            """,
            (status, status, name),
        )
        conn.commit()
        out.update(
            {
                "ok": cur.rowcount > 0,
                "masterCompanyName": name,
                "reviewStatus": status,
                "updated": cur.rowcount,
            }
        )
        return out
    finally:
        conn.close()
