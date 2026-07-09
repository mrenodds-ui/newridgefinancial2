"""Pre-submit ERA denial risk — rule-based scoring from claim fields + fee/payer stores."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MODELS_DIR = Path(__file__).resolve().parent / "models" / "era"
DENIAL_RULES_PATH = MODELS_DIR / "denial_rules.json"

HIGH_RISK_REMARK_PREFIXES = ("N4", "N30", "N130", "CO", "PR")
COMMON_DENIAL_CDT_PAIRS = {
    ("D2740", "missing_narrative"),
    ("D4341", "frequency"),
    ("D6010", "missing_narrative"),
    ("D3330", "missing_narrative"),
}
CDT_RE = re.compile(r"\b(D\d{4})\b", re.IGNORECASE)
GENERIC_PAYERS = frozenset({"", "insurance", "unknown", "n/a", "-", "—"})


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_denial_rules() -> dict[str, Any]:
    if DENIAL_RULES_PATH.is_file():
        try:
            data = json.loads(DENIAL_RULES_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            pass
    return {
        "payerRisk": {"delta": 0.15, "metlife": 0.12, "guardian": 0.1, "cigna": 0.1, "default": 0.08},
        "cdtRisk": {"D2740": 0.2, "D4341": 0.18, "D6010": 0.16, "D3330": 0.14},
    }


def _extract_cdt_codes(raw: list[str] | None, procedure: str = "") -> list[str]:
    codes: list[str] = []
    for item in raw or []:
        text = str(item or "").strip().upper()
        if CDT_RE.fullmatch(text):
            codes.append(text)
        else:
            found = CDT_RE.findall(text)
            codes.extend(c.upper() for c in found)
    if procedure:
        codes.extend(c.upper() for c in CDT_RE.findall(procedure))
    # de-dupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for code in codes:
        if code not in seen:
            seen.add(code)
            out.append(code)
    return out


def _is_generic_payer(payer: str) -> bool:
    return str(payer or "").strip().lower() in GENERIC_PAYERS


def predict_denial_risk(
    *,
    cdt_codes: list[str] | None = None,
    payer_id: str = "",
    has_narrative: bool = True,
    prior_denials: int = 0,
    procedure: str = "",
    claim_status: str = "",
    denial_reason: str = "",
    claim: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Rule-based denial risk score (0–1) with actionable flags from claim fields."""
    snap = claim if isinstance(claim, dict) else {}
    procedure = procedure or str(snap.get("procedure") or snap.get("Procedure") or "")
    claim_status = claim_status or str(snap.get("status") or snap.get("Status") or "")
    denial_reason = denial_reason or str(snap.get("denialReason") or snap.get("DenialReason") or "")
    payer_raw = str(
        payer_id
        or snap.get("payerId")
        or snap.get("payer")
        or snap.get("Payer")
        or ""
    ).strip()
    if "hasNarrative" in snap:
        has_narrative = bool(snap.get("hasNarrative"))
    elif "narrative" in snap or "clinicalNote" in snap:
        has_narrative = bool(snap.get("narrative") or snap.get("clinicalNote"))
    codes = _extract_cdt_codes(cdt_codes or snap.get("cdtCodes") or snap.get("cdt_codes"), procedure)
    if not codes and snap.get("cdt"):
        codes = _extract_cdt_codes([str(snap.get("cdt"))], "")

    rules = load_denial_rules()
    payer_key = payer_raw.lower()[:32] or "default"
    generic_payer = _is_generic_payer(payer_raw)
    payer_map = rules.get("payerRisk") if isinstance(rules.get("payerRisk"), dict) else {}
    risk = float(payer_map.get(payer_key) or payer_map.get("default") or 0.08)
    cdt_map = rules.get("cdtRisk") if isinstance(rules.get("cdtRisk"), dict) else {}
    flags: list[str] = []

    for code in codes:
        bump = float(cdt_map.get(code, 0))
        risk += bump
        for pair_code, theme in COMMON_DENIAL_CDT_PAIRS:
            if code == pair_code:
                flags.append(f"{code}:{theme}")
                if theme == "missing_narrative" and not has_narrative:
                    risk += 0.12

    if not has_narrative:
        risk += 0.25
        flags.append("missing_narrative")
    if generic_payer:
        risk += 0.18
        flags.append("generic_payer")
    if str(snap.get("id") or snap.get("ClaimId") or "").upper().startswith("DS-"):
        flags.append("daysheet_derived")
        risk += 0.05
    if prior_denials > 0:
        risk += min(0.3, 0.1 * prior_denials)
        flags.append(f"prior_denials:{prior_denials}")
    status_l = str(claim_status or "").lower()
    if "denied" in status_l:
        risk += 0.2
        flags.append("already_denied")
    reason_l = str(denial_reason or "").lower()
    if any(token in reason_l for token in ("missing", "insufficient", "documentation", "narrative", "x-ray", "radiograph")):
        risk += 0.1
        flags.append("denial_reason_docs")

    # Fee schedule presence softens risk slightly when CDT+named payer known
    fee_hit = None
    if codes and not generic_payer:
        try:
            from fee_schedule_store import lookup_cdt

            fee_hit = lookup_cdt(codes[0], payer_raw)
            if fee_hit.get("ok") and fee_hit.get("amounts"):
                flags.append(f"fee_schedule:{codes[0]}")
                risk = max(0.0, risk - 0.05)
        except Exception:
            fee_hit = None

    risk = max(0.0, min(1.0, risk))
    # de-dupe flags
    seen_f: set[str] = set()
    uniq_flags: list[str] = []
    for flag in flags:
        if flag not in seen_f:
            seen_f.add(flag)
            uniq_flags.append(flag)

    return {
        "ok": True,
        "riskScore": round(risk, 3),
        "highRisk": risk >= 0.65,
        "model": "rules_v2_claim_fields",
        "cdtCodes": codes,
        "payer": payer_raw or None,
        "genericPayer": generic_payer,
        "flags": uniq_flags,
        "feeScheduleHit": bool(fee_hit and fee_hit.get("ok") and fee_hit.get("amounts")),
        "evaluatedAt": _utc_now(),
    }


def train_denial_model(conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Stub trainer — persists rules metadata when xgboost/sklearn unavailable."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    meta = {"trainedAt": _utc_now(), "backend": "rules_v2_claim_fields", "rows": 0}
    if conn:
        try:
            cur = conn.execute(
                "SELECT COUNT(*) FROM era_match_feedback WHERE operator_verified = 0"
            )
            row = cur.fetchone()
            meta["rows"] = int(row[0]) if row else 0
        except sqlite3.Error:
            pass
    out = MODELS_DIR / "denial_model_meta.json"
    out.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return {"ok": True, "trained": True, "metaPath": str(out), **meta}
