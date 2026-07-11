"""
Phase I1 — Structured JSON insights for HAL / orchestrator.

Validates LLM (or staff) insight payloads against schemas so Apex widgets
never break on markdown drift. Honesty: numeric insights need source_refs;
PHI patterns rejected.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

SCHEMA_DIR = Path(__file__).resolve().parent / "data" / "insight_schemas"
WIDGET_TYPES = ("kpi-card", "trend-chart", "alert-banner")

PHI_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
PHI_DOB_RE = re.compile(
    r"\b(?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])[/-](?:19|20)\d{2}\b"
)
JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.I)
SOURCE_REF_RE = re.compile(
    r"^(softdent|qb|nr2|import):[a-z0-9_./-]+:[0-9]{4}-[0-9]{2}(-[0-9]{2})?$"
)

STRUCTURED_SYSTEM_HINT = (
    "When asked for a structured insight, reply with ONLY a single JSON object "
    "(no markdown prose). Allowed widget_type: kpi-card | trend-chart | alert-banner. "
    "Every insight MUST include source_refs like softdent:register:YYYY-MM-DD or "
    "qb:expenses:YYYY-MM. If import data is missing, set data.value to null and "
    "confidence to low — never invent dollars. No patient names, SSN, or DOB."
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _contains_phi(text: str) -> bool:
    return bool(PHI_SSN_RE.search(text or "") or PHI_DOB_RE.search(text or ""))


@lru_cache(maxsize=8)
def load_schema(widget_type: str) -> dict[str, Any]:
    wt = str(widget_type or "").strip()
    path = SCHEMA_DIR / f"{wt}.json"
    if not path.is_file():
        raise FileNotFoundError(f"schema not found: {wt}")
    return json.loads(path.read_text(encoding="utf-8"))


def extract_json_object(text: str) -> dict[str, Any] | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    fence = JSON_FENCE_RE.search(raw)
    if fence:
        raw = fence.group(1).strip()
    # Direct object
    if raw.startswith("{") and raw.endswith("}"):
        try:
            obj = json.loads(raw)
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            pass
    # First {...} slice
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(raw[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _walk_strings(obj: Any) -> list[str]:
    out: list[str] = []
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            out.extend(_walk_strings(v))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(_walk_strings(v))
    return out


def _has_numeric_claim(insight: dict[str, Any]) -> bool:
    data = insight.get("data") if isinstance(insight.get("data"), dict) else {}
    if data.get("value") is not None and isinstance(data.get("value"), (int, float)):
        return True
    series = data.get("series")
    if isinstance(series, list):
        for row in series:
            if isinstance(row, dict) and isinstance(row.get("value"), (int, float)):
                return True
    return False


def validate_insight(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Validate + sanitize. Returns {ok, insight?} or {ok:false, error}."""
    if not isinstance(payload, dict):
        return {"ok": False, "error": "insight must be an object", "structured": False}

    for s in _walk_strings(payload):
        if _contains_phi(s):
            return {"ok": False, "error": "Potential PHI detected — insight rejected", "structured": False}

    wt = str(payload.get("widget_type") or "").strip()
    if wt not in WIDGET_TYPES:
        return {
            "ok": False,
            "error": f"widget_type must be one of {', '.join(WIDGET_TYPES)}",
            "structured": False,
        }

    try:
        schema = load_schema(wt)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"schema load failed: {exc}", "structured": False}

    try:
        import jsonschema

        jsonschema.validate(instance=payload, schema=schema)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"schema validation failed: {exc}", "structured": False}

    refs = payload.get("source_refs") if isinstance(payload.get("source_refs"), list) else []
    if _has_numeric_claim(payload):
        if not refs:
            return {
                "ok": False,
                "error": "numeric insights require source_refs (never invent dollars)",
                "structured": False,
            }
        for ref in refs:
            if not SOURCE_REF_RE.match(str(ref)):
                return {"ok": False, "error": f"invalid source_ref: {ref}", "structured": False}

    clean = json.loads(json.dumps(payload))  # deep copy via JSON
    clean["validatedAt"] = _utc_now()
    return {"ok": True, "insight": clean, "structured": True, "widget_type": wt}


def parse_and_validate_insight_text(text: str) -> dict[str, Any]:
    obj = extract_json_object(text)
    if obj is None:
        return {
            "ok": False,
            "error": "no_json_object",
            "structured": False,
            "fallback": "markdown",
        }
    return validate_insight(obj)


def wants_structured_insight(query: str, *, explicit: bool = False) -> bool:
    if explicit:
        return True
    q = str(query or "")
    return bool(
        re.search(
            r"\b("
            r"structured insight|as json|json insight|kpi.?card|"
            r"alert banner|trend chart|widget.?safe|"
            r"monthly (practice )?health audit|practice health audit"
            r")\b",
            q,
            re.I,
        )
    )


def build_structured_system_prompt(base: str = "") -> str:
    base = str(base or "").strip()
    if not base:
        return STRUCTURED_SYSTEM_HINT
    return f"{base}\n\n{STRUCTURED_SYSTEM_HINT}"


def ai_insight_widget(insight: dict[str, Any] | None = None, *, empty_hint: str | None = None) -> dict[str, Any]:
    """Apex widget spec — renders without executing raw HTML from the model."""
    if insight is None:
        insight = load_last_insight()
    if isinstance(insight, dict) and insight.get("widget_type"):
        return {
            "id": "hal-ai-insight",
            "type": "ai-insight",
            "label": str(insight.get("title") or "AI Insight"),
            "size": "l",
            "status": "ok",
            "insight": insight,
            "hint": "Schema-validated HAL insight · source_refs required for numbers.",
        }
    return {
        "id": "hal-ai-insight",
        "type": "ai-insight",
        "label": "AI Insight",
        "size": "l",
        "status": "empty",
        "insight": None,
        "emptyMessage": empty_hint or "No structured insight yet — ask HAL for a JSON insight / health audit.",
        "hint": "Phase I1: orchestrator may attach insight when model returns valid JSON.",
    }


STORE_KEY_LAST_INSIGHT = "nr2:v2:hal:last-insight"


def save_last_insight(insight: dict[str, Any]) -> None:
    try:
        from document_sync import NR2_DATA_DIR
        from local_store import LocalStore

        LocalStore(NR2_DATA_DIR).set(STORE_KEY_LAST_INSIGHT, json.dumps(insight))
    except Exception:
        try:
            path = Path(__file__).resolve().parent / "app_data" / "nr2" / "last_insight.json"
            # Prefer document_sync NR2_DATA_DIR when available
            from document_sync import NR2_DATA_DIR

            path = Path(NR2_DATA_DIR) / "last_insight.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(insight, indent=2), encoding="utf-8")
        except Exception:
            pass


def load_last_insight() -> dict[str, Any] | None:
    try:
        from document_sync import NR2_DATA_DIR
        from local_store import LocalStore

        raw = LocalStore(NR2_DATA_DIR).get(STORE_KEY_LAST_INSIGHT)
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str) and raw.strip():
            obj = json.loads(raw)
            return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    try:
        from document_sync import NR2_DATA_DIR

        path = Path(NR2_DATA_DIR) / "last_insight.json"
        if path.is_file():
            obj = json.loads(path.read_text(encoding="utf-8"))
            return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    return None


def attach_insight_to_orchestrator_result(result: dict[str, Any], *, query: str, require_structured: bool) -> dict[str, Any]:
    """Mutate/return orchestrate result with insight fields."""
    out = dict(result) if isinstance(result, dict) else {"ok": False}
    text = str(out.get("text") or out.get("answer") or out.get("reply") or "")
    if not require_structured and not wants_structured_insight(query):
        out["structured"] = False
        return out

    parsed = parse_and_validate_insight_text(text)
    if parsed.get("ok") and parsed.get("insight"):
        out["structured"] = True
        out["insight"] = parsed["insight"]
        save_last_insight(parsed["insight"])
        out["insightWidget"] = ai_insight_widget(parsed["insight"])
        # Prefer a short human line for chat bubble
        title = parsed["insight"].get("title")
        expl = parsed["insight"].get("explanation") or ""
        out["text"] = f"{title}" + (f" — {expl}" if expl else "")
        out["rawModelText"] = text
        return out

    out["structured"] = False
    out["insightError"] = parsed.get("error") or "structured_output_failed"
    if require_structured:
        out["insightWidget"] = ai_insight_widget(
            None,
            empty_hint="AI insight unavailable (invalid or missing JSON). Showing markdown fallback.",
        )
    return out
