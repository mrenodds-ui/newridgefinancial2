"""HAL-10607 — PWImages eligibility/benefits → alias + plan-parameter staging.

Moonshot: MOONSHOT_PWIMAGES_EOB_MINE_CONSULT_2026-07-13.md (operator: proceed)

- Ingest ELIGIBILITY_BENEFITS from eob_mine_all.json
- Fuzzy-match carrier strings to spine / carrier_alias (propose pending only)
- Parse plan design params into staging_eligibility_parameters (NULL ≠ $0)
- Warehouse remittance EOB paths only — NO OCR dollar columns
- Never write settlement_matrix / sd_insurance_payment_lines / SoftDent
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from softdent_carrier_alias import (
    AUTO_MIN,
    MANUAL_MIN,
    confidence_band,
    ensure_carrier_alias_schema,
    list_spine_carriers,
    load_accepted_alias_maps,
    match_score,
    normalize_carrier_name,
)
from softdent_treatment_planning import resolve_analytics_db

DEF_ID = "HAL-10607"
PACKAGE_BUILD_ID = "hal-10607"

NR2_ROOT = Path(__file__).resolve().parent
DEFAULT_MINE_JSON = NR2_ROOT / "docs" / "_pwimages_eob_mine" / "eob_mine_all.json"
DEFAULT_REMIT_DIR = NR2_ROOT / "docs" / "_pwimages_eob_mine" / "remittance_eobs"

HONESTY_BANNER = (
    "UNVERIFIED SCANNED ESTIMATE — DO NOT POST. "
    "AWAIT GOLD CSV OR ERA 835 FOR SETTLEMENT TRUTH."
)

CARRIER_FROM_TEXT = re.compile(
    r"(?i)\b("
    r"delta dental(?:\s+of\s+[a-z]+)?|"
    r"delta dental ks|ddks|"
    r"aetna(?:\s+dental)?|"
    r"cigna(?:\s+dental(?:\s+health\s+of\s+[a-z]+)?)?|"
    r"met\s*life|"
    r"guardian|"
    r"humana(?:\s+dental)?|"
    r"geha|"
    r"united\s*concordia|"
    r"united\s*healthcare|u\.?h\.?c\.?|"
    r"blue cross|blue shield|bcbs|"
    r"sun life|"
    r"principal(?:\s+dental)?|"
    r"dentaquest|"
    r"ameritas|"
    r"lincoln financial|"
    r"assurant|"
    r"renaissance"
    r")\b"
)

# Plan-design parsers — amounts stored as REAL NULL when missing (never invent 0)
DED_IND = re.compile(
    r"(?i)(?:individual|member|employee)\s*(?:plan\s*)?deductible[^$0-9]{0,40}\$?\s*([\d,]+(?:\.\d{2})?)"
)
DED_FAM = re.compile(
    r"(?i)(?:family)\s*(?:plan\s*)?deductible[^$0-9]{0,40}\$?\s*([\d,]+(?:\.\d{2})?)"
)
DED_GENERIC = re.compile(
    r"(?i)(?:annual\s*)?deductible[^$0-9]{0,40}\$?\s*([\d,]+(?:\.\d{2})?)"
)
ANNUAL_MAX = re.compile(
    r"(?i)(?:annual|calendar\s*year|benefit)\s*(?:maximum|max|limit)[^$0-9]{0,40}\$?\s*([\d,]+(?:\.\d{2})?)"
)
PCT_PREV = re.compile(
    r"(?i)(?:preventive|diagnostic|routine)\D{0,40}(\d{1,3})\s*%"
)
PCT_BASIC = re.compile(
    r"(?i)(?:basic|restorative|intermediate)\D{0,40}(\d{1,3})\s*%"
)
PCT_MAJOR = re.compile(
    r"(?i)(?:major|prosthodontic|crowns?)\D{0,40}(\d{1,3})\s*%"
)
FREQ = re.compile(
    r"(?i)((?:once|twice|two|four|\d+)\s+(?:per|during|in)\s+(?:calendar\s+)?(?:year|months?|lifetime)[^.\\n]{0,80})"
)
WAITING = re.compile(
    r"(?i)(waiting\s+period[^.\\n]{0,100})"
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _money_or_none(raw: str | None) -> float | None:
    if raw is None:
        return None
    s = str(raw).replace(",", "").replace("$", "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _pct_or_none(raw: str | None) -> float | None:
    if raw is None:
        return None
    try:
        v = float(str(raw).strip())
    except ValueError:
        return None
    if v < 0 or v > 100:
        return None
    return v


def resolve_mine_json(path: Path | None = None) -> Path:
    return Path(path) if path else DEFAULT_MINE_JSON


def ensure_pwimages_eligibility_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS staging_eligibility_parameters (
            id INTEGER PRIMARY KEY,
            source_path TEXT NOT NULL,
            account_or_claim_id TEXT,
            lane TEXT,
            raw_carrier TEXT,
            matched_spine TEXT,
            matched_master TEXT,
            match_score REAL,
            match_status TEXT,
            deductible_individual REAL,
            deductible_family REAL,
            annual_max REAL,
            pct_preventive REAL,
            pct_basic REAL,
            pct_major REAL,
            frequency_notes TEXT,
            waiting_period_notes TEXT,
            markers_json TEXT,
            ocr_preview TEXT,
            parse_confidence REAL,
            review_status TEXT NOT NULL DEFAULT 'pending',
            ingested_at TEXT NOT NULL,
            UNIQUE(source_path)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_staging_elig_spine "
        "ON staging_eligibility_parameters(matched_spine)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_staging_elig_status "
        "ON staging_eligibility_parameters(match_status, review_status)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS warehouse_remittance_eobs (
            id INTEGER PRIMARY KEY,
            source_path TEXT NOT NULL,
            warehouse_copy_path TEXT,
            account_or_claim_id TEXT,
            category TEXT NOT NULL,
            confidence REAL,
            carriers_json TEXT,
            markers_json TEXT,
            mtime TEXT,
            ingested_at TEXT NOT NULL,
            UNIQUE(source_path)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_warehouse_remit_acct "
        "ON warehouse_remittance_eobs(account_or_claim_id)"
    )


def _read_source_text(path_str: str, preview: str, *, max_bytes: int = 120_000) -> str:
    chunks = [str(preview or "")]
    p = Path(path_str)
    if p.is_file() and p.suffix.lower() in {".htm", ".html", ".mht", ".txt"}:
        try:
            raw = p.read_bytes()[:max_bytes].decode("latin-1", "replace")
            plain = re.sub(r"<script[\s\S]*?</script>", " ", raw, flags=re.I)
            plain = re.sub(r"<style[\s\S]*?</style>", " ", plain, flags=re.I)
            plain = re.sub(r"<[^>]+>", " ", plain)
            plain = re.sub(r"&\w+;", " ", plain)
            plain = re.sub(r"\s+", " ", plain)
            chunks.append(plain[:20000])
        except OSError:
            pass
    return " ".join(chunks)


def extract_carrier_candidates(row: dict[str, Any], text: str) -> list[str]:
    seen: list[str] = []
    for c in row.get("carriers") or []:
        n = str(c or "").strip()
        if n and n.lower() not in {x.lower() for x in seen}:
            seen.append(n)
    for m in CARRIER_FROM_TEXT.findall(text or ""):
        n = str(m).strip()
        if n and n.lower() not in {x.lower() for x in seen}:
            seen.append(n)
    # Eligibility Benefits header: "Eligibility Benefits DELTA DENTAL KS #"
    m = re.search(
        r"(?i)eligibility\s+benefits\s+([A-Z][A-Z0-9 .&'-]{3,60}?)\s*[#\d]",
        text or "",
    )
    if m:
        n = m.group(1).strip(" -.")
        if n and n.lower() not in {x.lower() for x in seen}:
            seen.insert(0, n)
    return seen


def parse_plan_parameters(text: str) -> dict[str, Any]:
    t = text or ""
    ded_i = _money_or_none(DED_IND.search(t).group(1) if DED_IND.search(t) else None)
    ded_f = _money_or_none(DED_FAM.search(t).group(1) if DED_FAM.search(t) else None)
    if ded_i is None:
        ded_i = _money_or_none(
            DED_GENERIC.search(t).group(1) if DED_GENERIC.search(t) else None
        )
    annual = _money_or_none(ANNUAL_MAX.search(t).group(1) if ANNUAL_MAX.search(t) else None)
    pct_p = _pct_or_none(PCT_PREV.search(t).group(1) if PCT_PREV.search(t) else None)
    pct_b = _pct_or_none(PCT_BASIC.search(t).group(1) if PCT_BASIC.search(t) else None)
    pct_m = _pct_or_none(PCT_MAJOR.search(t).group(1) if PCT_MAJOR.search(t) else None)
    freqs = [m.strip() for m in FREQ.findall(t)[:5]]
    waits = [m.strip() for m in WAITING.findall(t)[:3]]

    filled = sum(
        1
        for v in (ded_i, ded_f, annual, pct_p, pct_b, pct_m)
        if v is not None
    ) + (1 if freqs else 0) + (1 if waits else 0)
    conf = min(0.95, 0.35 + 0.1 * filled)

    return {
        "deductible_individual": ded_i,
        "deductible_family": ded_f,
        "annual_max": annual,
        "pct_preventive": pct_p,
        "pct_basic": pct_b,
        "pct_major": pct_m,
        "frequency_notes": "; ".join(freqs) if freqs else None,
        "waiting_period_notes": "; ".join(waits) if waits else None,
        "parse_confidence": round(conf, 3),
    }


def best_spine_match(
    raw_carrier: str,
    spine: list[str],
    *,
    accepted_master_to_spine: dict[str, str] | None = None,
) -> dict[str, Any]:
    raw = str(raw_carrier or "").strip()
    if not raw:
        return {
            "matched_spine": None,
            "matched_master": None,
            "match_score": 0.0,
            "match_status": "reject",
        }
    maps = accepted_master_to_spine or {}
    # Exact accepted master hit
    for master, spine_name in maps.items():
        if normalize_carrier_name(master) == normalize_carrier_name(raw):
            return {
                "matched_spine": spine_name,
                "matched_master": master,
                "match_score": 100.0,
                "match_status": "auto",
            }
    best_name = None
    best_score = 0.0
    for s in spine:
        sc = match_score(raw, s)
        if sc > best_score:
            best_score = sc
            best_name = s
    band = confidence_band(best_score)
    status = "auto" if band == "auto" else ("pending" if band == "manual" else "reject")
    return {
        "matched_spine": best_name if best_score >= MANUAL_MIN else None,
        "matched_master": None,
        "match_score": float(best_score),
        "match_status": status if best_score >= MANUAL_MIN else "reject",
    }


def _propose_pending_alias(
    conn: sqlite3.Connection,
    *,
    raw_carrier: str,
    spine_name: str,
    score: float,
) -> bool:
    """Insert pending carrier_alias row for manual review — never SoftDent write-back."""
    if not raw_carrier or not spine_name or score < MANUAL_MIN:
        return False
    ensure_carrier_alias_schema(conn)
    name = str(raw_carrier).strip()
    band = confidence_band(score)
    if band == "reject":
        return False
    review = "accepted" if band == "auto" and score > AUTO_MIN else "pending"
    conf = "auto" if review == "accepted" else "manual"
    try:
        conn.execute(
            """
            INSERT INTO carrier_alias (
                spine_carrier_name, master_company_id, master_company_name,
                match_score, confidence, review_status, match_method, created_at_utc
            ) VALUES (?, '', ?, ?, ?, ?, 'pwimages_eligibility_10607', ?)
            ON CONFLICT(master_company_name) DO NOTHING
            """,
            (spine_name, name, float(score), conf, review, _utc_now()),
        )
        return True
    except sqlite3.Error:
        return False


def warehouse_copy_for(source_path: str, account_id: str) -> str | None:
    src = Path(source_path)
    if not src.is_file():
        # already copied under remittance_eobs/
        cand = DEFAULT_REMIT_DIR / f"{account_id}__{src.name}"
        if cand.is_file():
            return str(cand)
        return None
    DEFAULT_REMIT_DIR.mkdir(parents=True, exist_ok=True)
    dest = DEFAULT_REMIT_DIR / f"{account_id or 'unknown'}__{src.name}"
    try:
        if not dest.exists():
            dest.write_bytes(src.read_bytes())
        return str(dest)
    except OSError:
        return None


def run_hal10607_ingest(
    *,
    mine_json: Path | None = None,
    db_path: Path | None = None,
    propose_aliases: bool = True,
    limit: int | None = None,
) -> dict[str, Any]:
    target = Path(db_path) if db_path else resolve_analytics_db()
    mine = resolve_mine_json(mine_json)
    out: dict[str, Any] = {
        "ok": False,
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "mineJson": str(mine),
        "dbPath": str(target) if target else None,
        "inventedGold": False,
        "emptyIsNotZero": True,
        "writesSettlementMatrix": False,
        "writesPaymentLines": False,
        "softDentWriteBack": False,
        "honestyBanner": HONESTY_BANNER,
    }
    if not mine.is_file():
        out["error"] = "mine_json_missing"
        return out
    if not target:
        out["error"] = "analytics_db_missing"
        return out

    rows = json.loads(mine.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        out["error"] = "mine_json_not_array"
        return out

    elig = [r for r in rows if str(r.get("category") or "") == "ELIGIBILITY_BENEFITS"]
    remit = [
        r
        for r in rows
        if str(r.get("category") or "")
        in ("REMITTANCE_EOB", "REMITTANCE_EOB_CANDIDATE")
    ]
    if limit is not None:
        elig = elig[: max(0, int(limit))]

    spine = list_spine_carriers(db_path=target)
    maps = load_accepted_alias_maps(db_path=target)
    master_to_spine = dict(maps.get("masterToSpine") or {})

    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target), timeout=60.0)
    try:
        ensure_pwimages_eligibility_schema(conn)
        ensure_carrier_alias_schema(conn)

        elig_upserted = 0
        matched = 0
        pending_alias = 0
        for row in elig:
            path = str(row.get("path") or "")
            if not path:
                continue
            text = _read_source_text(path, str(row.get("ocr_preview") or ""))
            carriers = extract_carrier_candidates(row, text)
            raw = carriers[0] if carriers else ""
            match = best_spine_match(
                raw, spine, accepted_master_to_spine=master_to_spine
            )
            params = parse_plan_parameters(text)
            review = (
                "auto"
                if match["match_status"] == "auto" and (params["parse_confidence"] or 0) >= 0.55
                else "pending"
            )
            if match["match_status"] in ("auto", "pending") and match.get("matched_spine"):
                matched += 1
            if propose_aliases and match.get("matched_spine") and raw:
                if _propose_pending_alias(
                    conn,
                    raw_carrier=raw,
                    spine_name=str(match["matched_spine"]),
                    score=float(match["match_score"] or 0),
                ):
                    pending_alias += 1

            conn.execute(
                """
                INSERT INTO staging_eligibility_parameters (
                    source_path, account_or_claim_id, lane, raw_carrier,
                    matched_spine, matched_master, match_score, match_status,
                    deductible_individual, deductible_family, annual_max,
                    pct_preventive, pct_basic, pct_major,
                    frequency_notes, waiting_period_notes, markers_json,
                    ocr_preview, parse_confidence, review_status, ingested_at
                ) VALUES (
                    ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                )
                ON CONFLICT(source_path) DO UPDATE SET
                    raw_carrier=excluded.raw_carrier,
                    matched_spine=excluded.matched_spine,
                    matched_master=excluded.matched_master,
                    match_score=excluded.match_score,
                    match_status=excluded.match_status,
                    deductible_individual=excluded.deductible_individual,
                    deductible_family=excluded.deductible_family,
                    annual_max=excluded.annual_max,
                    pct_preventive=excluded.pct_preventive,
                    pct_basic=excluded.pct_basic,
                    pct_major=excluded.pct_major,
                    frequency_notes=excluded.frequency_notes,
                    waiting_period_notes=excluded.waiting_period_notes,
                    markers_json=excluded.markers_json,
                    ocr_preview=excluded.ocr_preview,
                    parse_confidence=excluded.parse_confidence,
                    review_status=excluded.review_status,
                    ingested_at=excluded.ingested_at
                """,
                (
                    path,
                    str(row.get("account_or_claim_id") or ""),
                    str(row.get("lane") or ""),
                    raw or None,
                    match.get("matched_spine"),
                    match.get("matched_master"),
                    match.get("match_score"),
                    match.get("match_status"),
                    params["deductible_individual"],
                    params["deductible_family"],
                    params["annual_max"],
                    params["pct_preventive"],
                    params["pct_basic"],
                    params["pct_major"],
                    params["frequency_notes"],
                    params["waiting_period_notes"],
                    json.dumps(row.get("markers") or []),
                    (str(row.get("ocr_preview") or ""))[:800],
                    params["parse_confidence"],
                    review,
                    _utc_now(),
                ),
            )
            elig_upserted += 1

        remit_upserted = 0
        for row in remit:
            path = str(row.get("path") or "")
            if not path:
                continue
            acct = str(row.get("account_or_claim_id") or "")
            copy_path = warehouse_copy_for(path, acct)
            # Schema intentionally has NO amount / paid / patient_responsibility columns
            conn.execute(
                """
                INSERT INTO warehouse_remittance_eobs (
                    source_path, warehouse_copy_path, account_or_claim_id,
                    category, confidence, carriers_json, markers_json, mtime, ingested_at
                ) VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(source_path) DO UPDATE SET
                    warehouse_copy_path=excluded.warehouse_copy_path,
                    category=excluded.category,
                    confidence=excluded.confidence,
                    carriers_json=excluded.carriers_json,
                    markers_json=excluded.markers_json,
                    mtime=excluded.mtime,
                    ingested_at=excluded.ingested_at
                """,
                (
                    path,
                    copy_path,
                    acct,
                    str(row.get("category") or ""),
                    float(row.get("confidence") or 0),
                    json.dumps(row.get("carriers") or []),
                    json.dumps(row.get("markers") or []),
                    str(row.get("mtime") or ""),
                    _utc_now(),
                ),
            )
            remit_upserted += 1

        conn.commit()

        match_rate = (matched / elig_upserted) if elig_upserted else 0.0
        out.update(
            {
                "ok": True,
                "eligibilityInMine": len(
                    [r for r in rows if r.get("category") == "ELIGIBILITY_BENEFITS"]
                ),
                "eligibilityUpserted": elig_upserted,
                "eligibilityMatched": matched,
                "fuzzyMatchRate": round(match_rate, 4),
                "fuzzyMatchGate80": match_rate >= 0.80,
                "aliasProposalsTouched": pending_alias,
                "remittanceUpserted": remit_upserted,
                "remittanceWarehouseDir": str(DEFAULT_REMIT_DIR),
                "spineCarriers": len(spine),
                "checkedAt": _utc_now(),
                "honesty": (
                    "Plan design staging only. Remittance paths warehouse — no OCR $. "
                    "Gold CSV / ERA 835 remain sole settlement truth. empty != $0."
                ),
            }
        )
        return out
    finally:
        conn.close()


def pwimages_eligibility_status(*, db_path: Path | None = None) -> dict[str, Any]:
    target = Path(db_path) if db_path else resolve_analytics_db()
    out: dict[str, Any] = {
        "ok": True,
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "mineJsonExists": DEFAULT_MINE_JSON.is_file(),
        "mineJson": str(DEFAULT_MINE_JSON),
        "eligibilityRows": 0,
        "remittanceRows": 0,
        "matchedRows": 0,
        "pendingReview": 0,
        "honestyBanner": HONESTY_BANNER,
        "emptyIsNotZero": True,
        "writesSettlementMatrix": False,
        "writesPaymentLines": False,
    }
    if not target or not target.is_file():
        out["dbPath"] = str(target) if target else None
        out["dbMissing"] = True
        return out
    conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:

        def _count(sql: str) -> int:
            try:
                return int(conn.execute(sql).fetchone()[0] or 0)
            except sqlite3.Error:
                return 0

        out["dbPath"] = str(target)
        out["eligibilityRows"] = _count("SELECT COUNT(*) FROM staging_eligibility_parameters")
        out["remittanceRows"] = _count("SELECT COUNT(*) FROM warehouse_remittance_eobs")
        out["matchedRows"] = _count(
            "SELECT COUNT(*) FROM staging_eligibility_parameters "
            "WHERE match_status IN ('auto','pending') AND matched_spine IS NOT NULL"
        )
        out["pendingReview"] = _count(
            "SELECT COUNT(*) FROM staging_eligibility_parameters WHERE review_status='pending'"
        )
        try:
            cols = [
                r[1]
                for r in conn.execute(
                    "PRAGMA table_info(warehouse_remittance_eobs)"
                ).fetchall()
            ]
        except sqlite3.Error:
            cols = []
        moneyish = [
            c
            for c in cols
            if re.search(r"(?i)amount|paid|payment|responsibility|allowed|write.?off", c)
        ]
        out["remittanceMoneyColumns"] = moneyish
        out["remittanceHasNoMoneyColumns"] = (not cols) or (len(moneyish) == 0)
    finally:
        conn.close()
    return out


def format_hal10607_reply(result: dict[str, Any] | None = None) -> str:
    r = result if isinstance(result, dict) else pwimages_eligibility_status()
    if r.get("eligibilityUpserted") is not None:
        return (
            f"PWImages eligibility bridge ({DEF_ID}): "
            f"elig={r.get('eligibilityUpserted')} matched={r.get('eligibilityMatched')} "
            f"rate={r.get('fuzzyMatchRate')} remitWarehouse={r.get('remittanceUpserted')}. "
            f"No OCR $ → settlement/Gold. empty != $0. {HONESTY_BANNER}"
        )
    return (
        f"PWImages eligibility status ({DEF_ID}): "
        f"eligRows={r.get('eligibilityRows')} remitRows={r.get('remittanceRows')} "
        f"matched={r.get('matchedRows')}. empty != $0."
    )


def pwimages_eligibility_widget() -> dict[str, Any]:
    return {
        "id": "softdent-pwimages-eligibility-hal10607",
        "title": "PWImages eligibility / remittance warehouse (HAL-10607)",
        "def": DEF_ID,
        "packageBuildId": PACKAGE_BUILD_ID,
        "apiStatus": "/api/apex/pwimages-eligibility/status",
        "apiRun": "/api/apex/pwimages-eligibility/run",
        "honesty": HONESTY_BANNER,
        "honestyShort": "empty != $0; remittance paths only — no OCR $ into Gold/settlement",
        "prior": "Builds on PWImages mine + carrier_alias; complement to Gold CSV / ERA 835",
    }
