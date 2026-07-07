"""Pre-submit ERA denial risk stub — Moonshot Phase 2A."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MODELS_DIR = Path(__file__).resolve().parent / "models" / "era"
DENIAL_RULES_PATH = MODELS_DIR / "denial_rules.json"

HIGH_RISK_REMARK_PREFIXES = ("N4", "N30", "N130", "CO", "PR")
COMMON_DENIAL_CDT_PAIRS = {("D2740", "missing_narrative"), ("D4341", "frequency")}


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
        "payerRisk": {"delta": 0.15, "metlife": 0.12, "default": 0.08},
        "cdtRisk": {"D2740": 0.2, "D4341": 0.18},
    }


def predict_denial_risk(
    *,
    cdt_codes: list[str] | None = None,
    payer_id: str = "",
    has_narrative: bool = True,
    prior_denials: int = 0,
) -> dict[str, Any]:
    """Rule-based denial risk score (0–1). XGBoost hook when training data exists."""
    rules = load_denial_rules()
    payer_key = str(payer_id or "default").strip().lower()[:32] or "default"
    payer_map = rules.get("payerRisk") if isinstance(rules.get("payerRisk"), dict) else {}
    risk = float(payer_map.get(payer_key) or payer_map.get("default") or 0.08)
    cdt_map = rules.get("cdtRisk") if isinstance(rules.get("cdtRisk"), dict) else {}
    for code in cdt_codes or []:
        risk += float(cdt_map.get(str(code).upper(), 0))
    if not has_narrative:
        risk += 0.25
    if prior_denials > 0:
        risk += min(0.3, 0.1 * prior_denials)
    risk = max(0.0, min(1.0, risk))
    return {
        "ok": True,
        "riskScore": round(risk, 3),
        "highRisk": risk >= 0.65,
        "model": "rules_stub",
        "evaluatedAt": _utc_now(),
    }


def train_denial_model(conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Stub trainer — persists rules metadata when xgboost/sklearn unavailable."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    meta = {"trainedAt": _utc_now(), "backend": "rules_stub", "rows": 0}
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
