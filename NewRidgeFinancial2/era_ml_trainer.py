"""ERA match ML training hook — Phase 2 Moonshot Priority B."""

from __future__ import annotations

import json
import pickle
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MODELS_DIR = Path(__file__).resolve().parent / "models" / "era"
MODEL_PATH = MODELS_DIR / "era_match_model.pkl"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_match_feedback(
    conn: sqlite3.Connection,
    *,
    era_line_id: str,
    predicted_claim_id: str,
    corrected_claim_id: str | None = None,
    approved: bool = True,
    confidence_at_prediction: float | None = None,
) -> dict[str, Any]:
    conn.execute(
        """
        INSERT INTO era_match_feedback
            (id, era_line_id, predicted_claim_id, corrected_claim_id,
             confidence_at_prediction, operator_verified, feedback_ts)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"fb-{era_line_id}-{datetime.now(timezone.utc).timestamp():.0f}",
            str(era_line_id or ""),
            str(predicted_claim_id or ""),
            str(corrected_claim_id or "") if corrected_claim_id else None,
            float(confidence_at_prediction or 0),
            1 if approved else 0,
            _utc_now(),
        ),
    )
    conn.commit()
    return {"ok": True, "recorded": True}


def fetch_feedback_rows(conn: sqlite3.Connection, *, min_rows: int = 1) -> list[dict[str, Any]]:
    cur = conn.execute(
        """
        SELECT era_line_id, predicted_claim_id, corrected_claim_id,
               confidence_at_prediction, operator_verified
        FROM era_match_feedback
        WHERE operator_verified IS NOT NULL
        ORDER BY feedback_ts DESC
        LIMIT 5000
        """
    )
    rows = [
        {
            "era_line_id": r[0],
            "predicted_claim_id": r[1],
            "corrected_claim_id": r[2],
            "confidence_at_prediction": r[3],
            "operator_verified": r[4],
        }
        for r in cur.fetchall()
    ]
    return rows if len(rows) >= min_rows else []


def train_era_model(conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    rows = fetch_feedback_rows(conn, min_rows=1) if conn else []
    if len(rows) < 3:
        return {
            "ok": True,
            "trained": False,
            "reason": "insufficient_feedback",
            "count": len(rows),
        }
    try:
        from sklearn.linear_model import LogisticRegression
        import numpy as np

        x_rows = []
        y_rows = []
        for row in rows:
            conf = float(row.get("confidence_at_prediction") or 0)
            approved = int(row.get("operator_verified") or 0)
            corrected = row.get("corrected_claim_id")
            match = 1 if approved and not corrected else 0
            x_rows.append([conf, len(str(row.get("predicted_claim_id") or ""))])
            y_rows.append(match)
        model = LogisticRegression(max_iter=200)
        model.fit(np.array(x_rows), np.array(y_rows))
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        with MODEL_PATH.open("wb") as fh:
            pickle.dump(model, fh)
        return {"ok": True, "trained": True, "count": len(rows), "modelPath": str(MODEL_PATH)}
    except ImportError:
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        stub = {"weights": {"confidence": 0.7}, "trainedAt": _utc_now(), "count": len(rows)}
        with MODEL_PATH.with_suffix(".json").open("w", encoding="utf-8") as fh:
            json.dump(stub, fh)
        return {"ok": True, "trained": True, "count": len(rows), "modelPath": str(MODEL_PATH.with_suffix(".json")), "fallback": "heuristic_json"}


def predict_match_confidence(features: dict[str, Any]) -> float:
    conf = float(features.get("confidence") or features.get("heuristicConfidence") or 0.5)
    if MODEL_PATH.is_file():
        try:
            with MODEL_PATH.open("rb") as fh:
                model = pickle.load(fh)
            import numpy as np

            vec = np.array([[conf, len(str(features.get("predicted_claim_id") or ""))]])
            prob = float(model.predict_proba(vec)[0][1])
            return max(0.0, min(1.0, prob))
        except Exception:
            pass
    json_path = MODEL_PATH.with_suffix(".json")
    if json_path.is_file():
        try:
            stub = json.loads(json_path.read_text(encoding="utf-8"))
            weight = float((stub.get("weights") or {}).get("confidence") or 0.7)
            return max(0.0, min(1.0, conf * weight))
        except Exception:
            pass
    return conf
