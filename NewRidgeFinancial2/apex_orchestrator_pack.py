"""
Phase I0 — AI Orchestrator shell (Moonshot AI Program Manager plan).

Routes HAL queries to chat8b (fast) vs escalate30b (deep) after board-actions miss.
Feature-flagged: NR2_AI_ORCHESTRATOR=1|true|on (default OFF — existing evaluate-query path).

Does not invent dollars; does not SoftDent write-back. Structured JSON is Phase I1.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any, Literal

LaneType = Literal["chat8b", "reason21b", "escalate30b", "coder32b", "local"]

# Fast path: widget parse / short summaries / UI routing language
_FAST_LANE_RE = re.compile(
    r"\b("
    r"parse|summarize|summary|highlight|focus|navigate|open|show|list|"
    r"what('?s| is) on|widget|chip|route|brief reply|one.?line"
    r")\b",
    re.I,
)

# Deep path: forecasting, audits, SoftDent×QB cross-reference
_DEEP_LANE_RE = re.compile(
    r"\b("
    r"forecast|predict|projection|outlook|"
    r"monthly (practice )?health|practice health audit|health audit|"
    r"cross[- ]?ref(erence)?|reconcile|reconciliation|"
    r"compare .{0,40}(quickbooks|qb|softdent|ledger|payroll|p&l)|"
    r"why .{0,30}(trend|drop|spike|decline|increase)|"
    r"deep (review|analysis|dive)|second opinion"
    r")\b",
    re.I,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def orchestrator_enabled() -> bool:
    raw = str(os.getenv("NR2_AI_ORCHESTRATOR") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def classify_intent(
    query: str,
    context: dict[str, Any] | None = None,
    *,
    store: Any = None,
) -> dict[str, Any]:
    """
    Program-manager lane selection.

    Priority:
      1) Explicit deep patterns → escalate30b
      2) Explicit fast patterns → chat8b
      3) Existing gateway.route_by_complexity (preserves reason21b financial math)
    """
    q = str(query or "").strip()
    ctx = context if isinstance(context, dict) else None
    if not q:
        return {
            "lane": "chat8b",
            "reason": "empty_query_default",
            "timeoutMs": 2000,
            "ok": True,
        }

    if _DEEP_LANE_RE.search(q):
        return {
            "lane": "escalate30b",
            "reason": "program_manager_deep",
            "timeoutMs": 60000,
            "ok": True,
        }

    if _FAST_LANE_RE.search(q) and len(q) < 220:
        return {
            "lane": "chat8b",
            "reason": "program_manager_fast",
            "timeoutMs": 2000,
            "ok": True,
        }

    try:
        from nr2_hal_gateway import resolve_lane, route_by_complexity

        lane = route_by_complexity(q, shift_context=ctx, store=store)
        resolved = resolve_lane(lane)
        timeout = 8000
        if resolved["lane"] == "escalate30b":
            timeout = 60000
        elif resolved["lane"] == "chat8b":
            timeout = 2000
        return {
            "lane": resolved["lane"],
            "reason": "gateway_route_by_complexity",
            "timeoutMs": timeout,
            "model": resolved.get("model"),
            "ok": True,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "lane": "chat8b",
            "reason": f"fallback_chat8b:{exc}",
            "timeoutMs": 2000,
            "ok": True,
        }


def orchestrator_status() -> dict[str, Any]:
    base = {
        "ok": True,
        "enabled": orchestrator_enabled(),
        "phase": "S3",
        "flag": "NR2_AI_ORCHESTRATOR",
        "lanes": ["chat8b", "reason21b", "escalate30b"],
        "structuredInsights": True,
        "unifiedDb": True,
        "mustWaveComplete": True,
        "shouldWaveComplete": True,
        "orchestratorDefault": "OFF",
        "note": (
            "When enabled, Apex HAL chat uses /api/apex/hal/orchestrate after board-actions. "
            "MUST I0–I4 + SHOULD S0–S3 complete. Flag default OFF."
        ),
        "refreshedAt": _utc_now(),
    }
    try:
        from apex_orchestrator_polish_pack import merge_orchestrator_status

        return merge_orchestrator_status(base)
    except Exception:
        return base



def orchestrate(
    query: str,
    *,
    readiness: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    system_prompt: str = "",
    messages: list[dict[str, Any]] | None = None,
    options: dict[str, Any] | None = None,
    store: Any = None,
    classify_only: bool = False,
    force_enabled: bool | None = None,
    require_structured: bool = False,
) -> dict[str, Any]:
    """
    Classify → (optional) evaluate_query with requested_lane → (I1) parse structured insight.

    classify_only=True never calls Ollama — used for unit validation.
    """
    enabled = orchestrator_enabled() if force_enabled is None else bool(force_enabled)
    classification = classify_intent(query, context, store=store)
    lane = str(classification.get("lane") or "chat8b")

    # Phase I3 — attach unified DB snapshot for deep lanes (no PHI)
    unified_ctx = None
    if lane in {"escalate30b", "reason21b"}:
        try:
            from apex_unified_db_pack import orchestrator_context_snapshot

            unified_ctx = orchestrator_context_snapshot(limit=6)
        except Exception:
            unified_ctx = None

    try:
        from apex_structured_insight_pack import wants_structured_insight

        want_struct = bool(require_structured) or wants_structured_insight(query)
    except Exception:
        want_struct = bool(require_structured)

    base: dict[str, Any] = {
        "ok": True,
        "orchestrator": True,
        "enabled": enabled,
        "phase": "S3",
        "lane": lane,
        "classification": classification,
        "structured": False,
        "requireStructured": want_struct,
        "unifiedContext": unified_ctx,
        "refreshedAt": _utc_now(),
    }

    if not enabled and force_enabled is None:
        return {
            **base,
            "ok": False,
            "error": "orchestrator_disabled",
            "hint": "Set NR2_AI_ORCHESTRATOR=1 to enable Phase I0/I1 routing.",
        }

    if classify_only:
        return {**base, "classifyOnly": True, "text": ""}

    from nr2_hal_gateway import evaluate_query, resolve_lane

    resolved = resolve_lane(lane)
    ready = readiness if isinstance(readiness, dict) else {"level": "unknown"}

    sys_prompt = str(system_prompt or "")
    if want_struct:
        try:
            from apex_structured_insight_pack import build_structured_system_prompt

            sys_prompt = build_structured_system_prompt(sys_prompt)
        except Exception:
            pass
    if unified_ctx and isinstance(unified_ctx.get("periods"), list) and unified_ctx["periods"]:
        # Compact non-PHI period table for deep model context
        lines = ["Unified DB period snapshot (import-mirrored; empty collections stay null):"]
        for row in unified_ctx["periods"][:6]:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"- {row.get('period')}: prod={row.get('production')} coll={row.get('collections')} "
                f"qbExp={row.get('totalExpenses')} gap={row.get('gapCode')}"
            )
        sys_prompt = (sys_prompt + "\n\n" + "\n".join(lines)).strip()

    result = evaluate_query(
        query=query,
        readiness=ready,
        model=resolved.get("model"),
        system_prompt=sys_prompt,
        messages=messages,
        options=options,
        shift_context=context if isinstance(context, dict) else None,
        requested_lane=lane,
        store=store,
    )
    out = {**base, **(result if isinstance(result, dict) else {})}
    out["orchestrator"] = True
    out["lane"] = result.get("resolvedLane") or lane
    out["classification"] = classification
    out["phase"] = "S3"
    out["unifiedContext"] = unified_ctx
    if "ok" not in out:
        out["ok"] = bool(result.get("ok")) if isinstance(result, dict) else False

    try:
        from apex_structured_insight_pack import attach_insight_to_orchestrator_result

        out = attach_insight_to_orchestrator_result(
            out, query=query, require_structured=want_struct
        )
    except Exception as exc:  # noqa: BLE001
        out["structured"] = False
        out["insightError"] = str(exc)
    return out
