"""Server-side HAL gateway — Moonshot Sprint 2 (all LLM via loopback)."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from nr2_browser_security import classify_financial_query

OLLAMA_CHAT = os.environ.get("NR2_OLLAMA_CHAT_URL", "http://127.0.0.1:11434/api/chat")
SOFT_STALE_TTL_HOURS = float(os.environ.get("NR2_SOFT_STALE_TTL_HOURS", "24"))
SOFT_STALE_WATERMARK = (
    "[DATA SOFT-STALE — analytical guidance only; verify amounts against fresh imports before acting]"
)
LANE_MODELS = {
    "chat8b": "hal-chat:8b",
    # R9700 32 GB: reason + escalation share GPU-pinned hal-escalate:30b (no Mistral 24B load).
    "reason21b": "hal-escalate:30b",
    "escalate30b": "hal-escalate:30b",
}
LANE_HISTORY_KEY = "nr2:hal:lane-history"
LANE_OVERRIDE_KEY = "nr2:hal:lane-override-log"
_STALE_ACK_KEY = "nr2:hal:stale-ack"
_FINANCIAL_MATH_PATTERN = re.compile(
    r"(?i)(\$\d+|\b\d{5}\b|\badjustment\b|\bposting\b|\bledger\b|\bdeposit\b|\breconcile\b|\bwrite[\s-]?off\b)"
)

FINANCIAL_OBFUSCATION = re.compile(
    r"(?i)\b(owe|balance|paid|bill|money|amount\s*due|outstanding|insurance|eob|era|adjustment|write[\s-]?off)\b"
)
_AMOUNT_PATTERN = re.compile(r"\$\s*\d[\d,]*(?:\.\d{2})?|\d+\.\d{2}\s*%")
_CLINICAL_PATTERN = re.compile(
    r"(?i)\b(clinical|procedure|tooth|quadrant|cdt|crown|extraction|prophy|periodontal|narrative|"
    r"denial|appeal|d2740|d4341|d6010|d3330|d1110|srp|implant|endo|payer|insurance|claim|eob|era)\b"
)
_ANALYTICAL_PATTERN = re.compile(
    r"(?i)\b(why|how|explain|analyze|trend|pattern|compare|summary|overview|what if|strategy|plan)\b"
)
_COMPLEXITY_PATTERN = re.compile(
    r"(?i)\b(escalat|complex|multi-step|deep dive|root cause|reconcil|investigate)\b"
)
_OUTBOUND_ACTION_RE = re.compile(
    r"(?i)\b(submit|submits|submitting|send|sends|sending|email|emails|emailing|e-?mail|fax|faxes|faxing|upload|uploads|uploading|transmit|transmits|transmitting|pay|pays|paying|approve|approves|approving|deny|denies|denying|delete|deletes|deleting|remove|removes|removing|writeback|write back|dispatch|dispatches|dispatching|mail|mailing|wire|wires|wiring)\b|\b(contact|contacts|contacting)\b.*\b(payer|insurance)\b|\b(payer|insurance)\b.*\b(contact|email|fax|call)\b"
)
_OUTBOUND_PHRASES_RE = re.compile(
    r"(?i)\bpost(s|ing|ed)?\s+(?:(?:a|an|the|this|that)\s+)?(?:[a-z]+\s+){0,3}?(journal|entry|entries|payment|charge|transaction|invoice|claim|note|statement|ledger|document|documents|record|records|refund|refunds|narrative|narratives|deposit|bill|check|payer)\b|\bpost(s|ing|ed)?\s+to\s+quickbooks\b|\bquickbooks\s+post(ing|ed)?\b|\b(record|make|process)\s+((a|an|the)\s+)?(payment|charge|refund|transaction)\b|\bwrite\s+(it\s+)?back\b|\bwrite(s|ing)?\s+to\s+softdent\b|\bsoftdent\s+write(s|ing|back)?\b|\bupdate\s+softdent\b|\b(sync\s+to\s+softdent)\b"
)
_PAGE_SYNONYMS: dict[str, tuple[str, ...]] = {
    "financial": ("financial dashboard", "financial", "dashboard", "ebitda", "owner", "production"),
    "taxes": ("taxes", "tax plan", "book to tax", "book-to-tax"),
    "softdent": ("softdent", "soft dent", "practice management"),
    "quickbooks": ("quickbooks", "quick books", "p&l", "profit and loss", "posting queue"),
    "ar": ("a/r", "accounts receivable", "receivable", "collections", "aging"),
    "claims": ("claims workbench", "claims", "claim", "workbench", "denied"),
    "narratives": ("narratives", "narrative", "insurance narrative"),
    "documents": ("accounting documents", "documents", "document intake"),
    "library": ("document library", "library", "repository"),
    "office-manager": ("office manager", "office-manager", "office attention"),
    "hal": ("hal", "command center"),
}
_PAGE_LABELS = {
    "financial": "Financial dashboard",
    "taxes": "Taxes",
    "softdent": "SoftDent",
    "quickbooks": "QuickBooks",
    "ar": "A/R",
    "claims": "Claims workbench",
    "narratives": "Insurance narratives",
    "documents": "Accounting documents",
    "library": "Document library",
    "office-manager": "Office manager",
    "hal": "HAL command center",
}
_MONOLOGUE_START_RE = re.compile(
    r"^(?:Okay|Sure|Certainly|Hmm|Let me|Wait|Alright)[,.]?\s*(?:let me\s+)?(?:break this down|think|see|check|start|walk through)[^.!?]*[.!?]?\s*",
    re.IGNORECASE,
)
_MEMORY_GUIDANCE_MARKERS = (
    "Governed memory matches:",
    "Durable HAL knowledge (guidance only",
)
_PAYER_GUIDANCE_MARKER = "Payer reference matches ("
_ELIGIBILITY_GUIDANCE_MARKER = "Cached eligibility context ("
_DEFAULT_MEMORY_LIMIT = 6
_DEFAULT_PAYER_LIMIT = 4
_DEFAULT_ELIGIBILITY_LIMIT = 2


def is_outbound_action_phrase(query: str) -> bool:
    q = str(query or "").strip().lower()
    if re.search(r"\b(approve all|bulk approve)\b.*\b(journal|posting queue)\b", q):
        return False
    if re.search(r"\b(journal|posting queue)\b.*\b(approve all|bulk approve)\b", q):
        return False
    return bool(
        _OUTBOUND_ACTION_RE.search(q)
        or _OUTBOUND_PHRASES_RE.search(q)
        or re.search(r"\bpush\b.*\b(live|to quickbooks)\b", q)
        or re.search(r"\bpush\b.*\b(journal|entry|entries)\b.*\blive\b", q)
    )


def find_page(query: str) -> str | None:
    q = str(query or "").lower()
    best: str | None = None
    best_len = 0
    for page_id, synonyms in _PAGE_SYNONYMS.items():
        for synonym in synonyms:
            syn = synonym.lower()
            if len(syn) <= 4:
                hit = re.search(r"\b" + re.escape(syn) + r"\b", q)
            else:
                hit = syn in q
            if hit and len(syn) > best_len:
                best = page_id
                best_len = len(syn)
    return best


def clean_gateway_text(text: str) -> str:
    out = str(text or "").strip()
    out = re.sub(r"<think>[\s\S]*?</think>", "", out, flags=re.IGNORECASE)
    out = re.sub(r"</?think>", "", out, flags=re.IGNORECASE)
    out = _MONOLOGUE_START_RE.sub("", out)
    out = re.sub(
        r"^(?:Okay|Sure|Certainly)[,.]?\s*(?:from my (?:local )?)?(?:read-?only )?(?:monitoring )?perspective[,:]?\s*",
        "",
        out,
        flags=re.IGNORECASE,
    )
    return out.strip()


def extract_ollama_message_text(message: dict[str, Any] | None) -> str:
    msg = message or {}
    content = str(msg.get("content") or "").strip()
    thinking = str(msg.get("thinking") or "").strip()
    combined = content or thinking
    return clean_gateway_text(combined)


def try_local_policy_reply(query: str) -> dict[str, str] | None:
    """Deterministic consent/navigation answers — mirrors hal-core before model calls."""
    raw = str(query or "").strip()
    if not raw:
        return None
    q = re.sub(r"^hal[,:]\s+", "", raw, flags=re.IGNORECASE).lower().strip()
    wants_explain = bool(
        re.search(
            r"\b(explain|what is|what's|whats|what does|tell me about|describe|purpose of|what happens when|what happens if|what if|what would happen)\b",
            q,
        )
    )

    if re.search(r"\b(open|go to|navigate to|take me to|launch)\b", q) and not wants_explain:
        page = find_page(q)
        if page:
            label = _PAGE_LABELS.get(page, page.replace("-", " ").title())
            return {
                "text": f"Yes. I can open {label} from here — it loads the local import view for that page.",
                "intent": f"navigate:{page}",
            }

    hyp = re.match(r"^what happens if i ask you to (.+?)\??$", q)
    if hyp:
        action = hyp.group(1).strip()
        if is_outbound_action_phrase(action):
            return {
                "text": (
                    f"No — I won't {action} without explicit consent. "
                    'I can prepare a local draft and checklist; say "I consent" when staff are ready for outbound delivery.'
                ),
                "intent": "consent:required",
            }

    can = re.match(r"^(?:are you allowed to|can you) (.+?)(?:\s+without (?:staff approval|consent))?\??$", q)
    if can:
        action = can.group(1).strip()
        without_consent = "without consent" in q or "without staff approval" in q
        if without_consent:
            return {
                "text": (
                    f"No — I won't {action} without your explicit consent. "
                    'I can prepare a local draft; say "I consent" when you are ready.'
                ),
                "intent": "consent:required",
            }
        if is_outbound_action_phrase(action) or is_outbound_action_phrase(raw):
            if re.search(r"\bpost\b", action) and re.search(r"\bquickbooks\b", action):
                return {
                    "text": (
                        "No — I cannot click Post inside QuickBooks from NR2. "
                        'I can draft entries locally or export IIF after you say "I consent"; staff still post inside QuickBooks.'
                    ),
                    "intent": "consent:qb-post-blocked",
                }
            return {
                "text": (
                    f"No — I won't {action} without explicit consent. "
                    'I can prepare local drafts; say "I consent" when staff are ready.'
                ),
                "intent": "consent:required",
            }

    if re.search(r"\b(yes or no|short answer)\b", q) and re.search(r"\bsubmit\b.*\b(portal|payer|claims?)\b", q):
        return {
            "text": "No. HAL cannot submit claims to payer portals — staff upload after explicit consent and review.",
            "intent": "consent:payer-submit",
        }
    if re.search(r"\bpayer submission allowed\b", q) or re.search(r"\bis payer submission allowed\b", q):
        return {
            "text": "No. Payer submission is not allowed from NR2 — HAL prepares packets locally; staff transmit outside the program after consent.",
            "intent": "consent:payer-submit",
        }
    if re.search(r"\bcan hal write to softdent\b", q) or (
        re.search(r"\bwrite to softdent\b", q) and re.search(r"\b(can|short)\b", q)
    ):
        return {
            "text": "No. HAL cannot write to SoftDent — NR2 stays read-only; staff update SoftDent directly.",
            "intent": "consent:writeback-blocked",
        }
    return None


def build_import_readiness_context(readiness: dict[str, Any]) -> str:
    lines = [
        "[IMPORT_CONTEXT]",
        f"Status: {str(readiness.get('level') or 'unknown').upper()}",
        f"LoadedAt: {readiness.get('loadedAt') or 'unknown'}",
        f"AgeHours: {readiness.get('ageHours') if readiness.get('ageHours') is not None else 'unknown'}",
        f"Ok: {'yes' if readiness.get('ok') else 'no'}",
    ]
    if readiness.get("error"):
        lines.append(f"Error: {readiness['error']}")
    lines.append("You must not provide numeric projections or financial advice when Status is not FRESH.")
    lines.append("[END_IMPORT_CONTEXT]")
    return "\n".join(lines)


def is_financial_query(query: str) -> bool:
    q = str(query or "")
    return classify_financial_query(q) or bool(FINANCIAL_OBFUSCATION.search(q))


def classify_query_intent(query: str) -> str:
    q = str(query or "")
    if _CLINICAL_PATTERN.search(q):
        return "clinical"
    if is_financial_query(q) and not _ANALYTICAL_PATTERN.search(q):
        return "transactional"
    if _ANALYTICAL_PATTERN.search(q) or not is_financial_query(q):
        return "analytical"
    return "transactional"


def is_soft_stale(readiness: dict[str, Any]) -> bool:
    level = str(readiness.get("level") or "unknown")
    if level == "fresh":
        return False
    age = readiness.get("ageHours")
    if age is None:
        return False
    try:
        return float(age) <= SOFT_STALE_TTL_HOURS
    except (TypeError, ValueError):
        return False


def requires_financial_reasoning(query: str) -> bool:
    q = str(query or "")
    if _FINANCIAL_MATH_PATTERN.search(q):
        return True
    if is_financial_query(q) and (_AMOUNT_PATTERN.search(q) or _FINANCIAL_MATH_PATTERN.search(q)):
        return True
    return False


def append_lane_override_log(store, *, query: str, from_lane: str, to_lane: str, reason: str) -> None:
    if not store:
        return
    raw = store.get(LANE_OVERRIDE_KEY)
    try:
        items = json.loads(raw) if raw else []
    except json.JSONDecodeError:
        items = []
    if not isinstance(items, list):
        items = []
    items.append(
        {
            "queryPreview": str(query or "")[:120],
            "fromLane": from_lane,
            "toLane": to_lane,
            "reason": reason,
        }
    )
    store.set(LANE_OVERRIDE_KEY, json.dumps(items[-200:]))


def reject_financial_lane_downgrade(query: str, override_header: str | None) -> bool:
    if str(override_header or "").strip().lower() != "chat8b":
        return False
    return requires_financial_reasoning(query)


def financial_lane_policy_status() -> dict[str, Any]:
    return {
        "ok": True,
        "policy": "financial_math_reason21b_minimum",
        "minimumLane": "reason21b",
        "enforced": True,
    }


def route_by_complexity(
    query: str,
    *,
    shift_context: dict[str, Any] | None = None,
    store=None,
) -> str:
    q = str(query or "")
    tier = max(1, min(int((shift_context or {}).get("tier") or 1), 7))
    intent = classify_query_intent(q)
    if tier >= 5 or _COMPLEXITY_PATTERN.search(q) or len(q) > 400 or intent == "clinical":
        return "escalate30b"
    if requires_financial_reasoning(q):
        append_lane_override_log(
            store,
            query=q,
            from_lane="chat8b",
            to_lane="reason21b",
            reason="financial_math_policy",
        )
        return "reason21b"
    if len(q) < 80 and not _ANALYTICAL_PATTERN.search(q) and not _COMPLEXITY_PATTERN.search(q):
        return "chat8b"
    if tier >= 3 or intent == "analytical" or bool(re.search(r"(?i)\b(reason|plan|prioriti|compare)\b", q)):
        return "reason21b"
    return "chat8b"


def resolve_lane(lane_key: str) -> dict[str, str]:
    key = str(lane_key or "chat8b").lower()
    if key not in LANE_MODELS:
        key = "chat8b"
    return {"lane": key, "model": LANE_MODELS[key]}


def redact_financial_numbers(text: str) -> str:
    return _AMOUNT_PATTERN.sub("[AMOUNT REDACTED - STALE DATA]", str(text or ""))


def append_lane_history(store, *, lane: str, model: str, query: str, intent: str) -> None:
    if not store:
        return
    raw = store.get(LANE_HISTORY_KEY)
    try:
        items = json.loads(raw) if raw else []
    except json.JSONDecodeError:
        items = []
    if not isinstance(items, list):
        items = []
    items.append(
        {
            "lane": lane,
            "model": model,
            "intent": intent,
            "queryPreview": str(query or "")[:120],
        }
    )
    store.set(LANE_HISTORY_KEY, json.dumps(items[-100:]))


def list_lane_history(store=None, *, limit: int = 20) -> dict[str, Any]:
    cap = max(1, min(int(limit or 20), 100))
    if not store:
        return {"ok": True, "items": [], "count": 0}
    raw = store.get(LANE_HISTORY_KEY)
    try:
        items = json.loads(raw) if raw else []
    except json.JSONDecodeError:
        items = []
    if not isinstance(items, list):
        items = []
    return {"ok": True, "items": list(reversed(items[-cap:])), "count": len(items)}


def acknowledge_stale(store, *, actor: str = "Staff", reason: str = "") -> dict[str, Any]:
    if not store:
        return {"ok": False, "error": "no_store"}
    from datetime import datetime, timezone

    payload = {
        "at": datetime.now(timezone.utc).isoformat(),
        "actor": str(actor or "Staff"),
        "reason": str(reason or "")[:500],
    }
    store.set(_STALE_ACK_KEY, json.dumps(payload))
    return {"ok": True, "acknowledged": payload}


def system_prompt_has_memory_guidance(system_prompt: str) -> bool:
    text = str(system_prompt or "")
    return any(marker in text for marker in _MEMORY_GUIDANCE_MARKERS)


def _memory_limit_for_intent(intent: str) -> int:
    if intent == "clinical":
        return 10
    if intent == "analytical":
        return 8
    return _DEFAULT_MEMORY_LIMIT


def compile_memory_guidance(query: str, system_prompt: str = "", *, limit: int = _DEFAULT_MEMORY_LIMIT) -> str:
    """MemoAI: inject governed memory hits unless caller already supplied guidance."""
    if system_prompt_has_memory_guidance(system_prompt):
        return ""
    try:
        from knowledge_memory_index import format_memory_hits, search_memories
    except ImportError:
        return ""
    hits = search_memories(str(query or ""), limit=max(1, int(limit)))
    return format_memory_hits(hits)


def system_prompt_has_payer_guidance(system_prompt: str) -> bool:
    return _PAYER_GUIDANCE_MARKER in str(system_prompt or "")


def compile_payer_guidance(query: str, system_prompt: str = "", *, limit: int = _DEFAULT_PAYER_LIMIT) -> str:
    """Inject curated payer routing/narrative hints (not member benefits)."""
    if system_prompt_has_payer_guidance(system_prompt):
        return ""
    try:
        from payer_reference_store import format_payer_hits, search_payers
    except ImportError:
        return ""
    hits = search_payers(str(query or ""), limit=max(1, int(limit)))
    return format_payer_hits(hits)


def compile_eligibility_context(query: str, system_prompt: str = "", *, limit: int = _DEFAULT_ELIGIBILITY_LIMIT) -> str:
    """Inject fresh PHI-redacted eligibility snapshots when available."""
    if _ELIGIBILITY_GUIDANCE_MARKER in str(system_prompt or ""):
        return ""
    try:
        from eligibility_cache_store import format_eligibility_hits, search_eligibility_cache
    except ImportError:
        return ""
    hits = search_eligibility_cache(str(query or ""), limit=max(1, int(limit)))
    return format_eligibility_hits(hits)


def build_chat_messages(
    *,
    query: str,
    readiness: dict[str, Any],
    system_prompt: str = "",
    messages: list[dict[str, Any]] | None = None,
    memory_limit: int = _DEFAULT_MEMORY_LIMIT,
    payer_limit: int = _DEFAULT_PAYER_LIMIT,
    eligibility_limit: int = _DEFAULT_ELIGIBILITY_LIMIT,
) -> tuple[list[dict[str, Any]], str, bool, str]:
    level = str(readiness.get("level") or "unknown")
    intent = classify_query_intent(query)
    soft_stale = is_soft_stale(readiness)
    effective_memory_limit = memory_limit if memory_limit != _DEFAULT_MEMORY_LIMIT else _memory_limit_for_intent(intent)
    chat_messages: list[dict[str, Any]] = []
    if system_prompt:
        chat_messages.append({"role": "system", "content": system_prompt})
    memory_guidance = compile_memory_guidance(query, system_prompt, limit=effective_memory_limit)
    if memory_guidance:
        chat_messages.append({"role": "system", "content": memory_guidance})
    try:
        from hal_learning import format_session_context_block

        session_block = format_session_context_block()
        if session_block:
            chat_messages.append({"role": "system", "content": session_block})
    except ImportError:
        pass
    payer_guidance = compile_payer_guidance(query, system_prompt, limit=payer_limit)
    if payer_guidance:
        chat_messages.append({"role": "system", "content": payer_guidance})
    eligibility_guidance = compile_eligibility_context(query, system_prompt, limit=eligibility_limit)
    if eligibility_guidance:
        chat_messages.append({"role": "system", "content": eligibility_guidance})
    if level != "fresh":
        chat_messages.append({"role": "system", "content": build_import_readiness_context(readiness)})
        if soft_stale and intent in ("analytical", "clinical"):
            chat_messages.append({"role": "system", "content": SOFT_STALE_WATERMARK})
    if messages:
        chat_messages.extend(messages)
    else:
        chat_messages.append({"role": "user", "content": str(query or "")})
    return chat_messages, intent, soft_stale, level


def iter_ollama_sse_tokens(
    *,
    model: str,
    messages: list[dict[str, Any]],
    lane: str,
    options: dict[str, Any] | None = None,
    timeout: float = 120.0,
):
    """Yield SSE frames: meta event first, then token data events."""
    yield f"event: meta\ndata: {json.dumps({'lane': lane, 'model': model, 'done': False})}\n\n"
    payload: dict[str, Any] = {"model": model, "messages": messages, "stream": True}
    think = _ollama_think_flag(model)
    if think is not None:
        payload["think"] = think
    if options:
        payload["options"] = options
    req = urllib.request.Request(
        OLLAMA_CHAT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for line in resp:
                try:
                    obj = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError:
                    continue
                delta = str((obj.get("message") or {}).get("content") or "")
                if delta:
                    yield f"data: {json.dumps({'token': delta, 'done': False})}\n\n"
                if obj.get("done"):
                    break
        yield f"data: {json.dumps({'token': '', 'done': True})}\n\n"
    except Exception as exc:
        yield f"event: error\ndata: {json.dumps({'error': str(exc), 'done': True})}\n\n"


def _ollama_think_flag(model: str) -> bool | None:
    """Staff-facing lanes disable hidden reasoning (DeepSeek-R1 / Qwen3)."""
    name = str(model or "").lower()
    if name.startswith("hal-escalate") or name.startswith("qwen3:"):
        return False
    if name.startswith("hal-chat") or name.startswith("deepseek"):
        return False
    return None


def call_ollama_chat(
    *,
    model: str,
    messages: list[dict[str, Any]],
    stream: bool = False,
    options: dict[str, Any] | None = None,
    timeout: float = 120.0,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"model": model, "messages": messages, "stream": bool(stream)}
    think = _ollama_think_flag(model)
    if think is not None:
        payload["think"] = think
    if options:
        payload["options"] = options
    req = urllib.request.Request(
        OLLAMA_CHAT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if stream:
                chunks: list[str] = []
                for line in resp:
                    try:
                        obj = json.loads(line.decode("utf-8"))
                    except json.JSONDecodeError:
                        continue
                    delta = str((obj.get("message") or {}).get("content") or "")
                    if delta:
                        chunks.append(delta)
                full = "".join(chunks)
                return {"ok": True, "body": {"message": {"content": full}}, "streamed": True}
            body = json.loads(resp.read().decode("utf-8"))
            message = body.get("message") or {}
            if not str(message.get("content") or "").strip():
                text = extract_ollama_message_text(message)
                if text:
                    body = dict(body)
                    body["message"] = dict(message)
                    body["message"]["content"] = text
        return {"ok": True, "body": body}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "error": f"ollama_http_{exc.code}", "detail": detail[:2000]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def evaluate_query_stream(
    *,
    query: str,
    readiness: dict[str, Any],
    model: str | None = None,
    system_prompt: str = "",
    messages: list[dict[str, Any]] | None = None,
    options: dict[str, Any] | None = None,
    shift_context: dict[str, Any] | None = None,
    requested_lane: str | None = None,
    store=None,
) -> dict[str, Any]:
    """Gateway gates + Ollama streaming aggregation (server-side)."""
    financial = is_financial_query(query)
    level = str(readiness.get("level") or "unknown")
    intent = classify_query_intent(query)
    soft_stale = is_soft_stale(readiness)
    lane_key = str(
        requested_lane or route_by_complexity(query, shift_context=shift_context, store=store)
    )
    resolved = resolve_lane(lane_key)
    model = str(model or resolved["model"])
    routing_reason = "financial_math_policy" if requires_financial_reasoning(query) else ""

    if financial and level != "fresh":
        if intent == "transactional" or not soft_stale:
            return {
                "ok": False,
                "error": "HAL_UNAVAILABLE_STALE_DATA",
                "readiness": readiness,
                "blocked": True,
                "intent": intent,
                "resolvedLane": resolved["lane"],
            }

    local = try_local_policy_reply(query)
    if local:
        text = local["text"]
        append_lane_history(store, lane="local", model="policy", query=query, intent=local.get("intent", "local:policy"))
        return {
            "ok": True,
            "text": text,
            "message": {"content": text},
            "model": "local-policy",
            "readinessLevel": level,
            "intent": local.get("intent", "local:policy"),
            "softStale": soft_stale,
            "resolvedLane": "local",
            "routingReason": "local_policy",
            "streamed": False,
        }

    chat_messages, intent, soft_stale, level = build_chat_messages(
        query=query,
        readiness=readiness,
        system_prompt=system_prompt,
        messages=messages,
    )

    result = call_ollama_chat(model=model, messages=chat_messages, stream=True, options=options)
    if not result.get("ok"):
        return {
            "ok": False,
            "error": result.get("error"),
            "detail": result.get("detail"),
            "resolvedLane": resolved["lane"],
        }

    body = result.get("body") or {}
    text = extract_ollama_message_text(body.get("message") or {})
    if level != "fresh" and intent == "transactional":
        text = redact_financial_numbers(text)
    elif level != "fresh" and soft_stale and intent in ("analytical", "clinical"):
        if SOFT_STALE_WATERMARK not in text:
            text = f"{SOFT_STALE_WATERMARK}\n\n{text}"
        text = redact_financial_numbers(text)

    append_lane_history(store, lane=resolved["lane"], model=model, query=query, intent=intent)
    return {
        "ok": True,
        "text": text,
        "message": {"content": text},
        "model": model,
        "readinessLevel": level,
        "intent": intent,
        "softStale": soft_stale,
        "resolvedLane": resolved["lane"],
        "routingReason": routing_reason or None,
        "streamed": True,
    }


def evaluate_query_sse_frames(
    *,
    query: str,
    readiness: dict[str, Any],
    model: str | None = None,
    system_prompt: str = "",
    messages: list[dict[str, Any]] | None = None,
    options: dict[str, Any] | None = None,
    shift_context: dict[str, Any] | None = None,
    requested_lane: str | None = None,
    store=None,
):
    """Generator of SSE frames for true browser token streaming."""
    financial = is_financial_query(query)
    level = str(readiness.get("level") or "unknown")
    intent = classify_query_intent(query)
    soft_stale = is_soft_stale(readiness)
    lane_key = str(
        requested_lane or route_by_complexity(query, shift_context=shift_context, store=store)
    )
    resolved = resolve_lane(lane_key)
    model = str(model or resolved["model"])

    if financial and level != "fresh" and (intent == "transactional" or not soft_stale):
        yield f"event: error\ndata: {json.dumps({'error': 'HAL_UNAVAILABLE_STALE_DATA', 'blocked': True, 'done': True})}\n\n"
        return

    local = try_local_policy_reply(query)
    if local:
        text = local["text"]
        append_lane_history(store, lane="local", model="policy", query=query, intent=local.get("intent", "local:policy"))
        yield f"event: meta\ndata: {json.dumps({'lane': 'local', 'model': 'local-policy', 'done': False})}\n\n"
        yield f"data: {json.dumps({'token': text, 'done': False})}\n\n"
        yield f"data: {json.dumps({'token': '', 'done': True})}\n\n"
        return

    chat_messages, intent, soft_stale, level = build_chat_messages(
        query=query,
        readiness=readiness,
        system_prompt=system_prompt,
        messages=messages,
    )
    append_lane_history(store, lane=resolved["lane"], model=model, query=query, intent=intent)
    yield from iter_ollama_sse_tokens(
        model=model,
        messages=chat_messages,
        lane=resolved["lane"],
        options=options,
    )


def evaluate_query(
    *,
    query: str,
    readiness: dict[str, Any],
    model: str | None = None,
    system_prompt: str = "",
    messages: list[dict[str, Any]] | None = None,
    options: dict[str, Any] | None = None,
    shift_context: dict[str, Any] | None = None,
    requested_lane: str | None = None,
    store=None,
) -> dict[str, Any]:
    financial = is_financial_query(query)
    level = str(readiness.get("level") or "unknown")
    intent = classify_query_intent(query)
    soft_stale = is_soft_stale(readiness)
    lane_key = str(
        requested_lane or route_by_complexity(query, shift_context=shift_context, store=store)
    )
    resolved = resolve_lane(lane_key)
    model = str(model or resolved["model"])
    routing_reason = "financial_math_policy" if requires_financial_reasoning(query) else ""

    if financial and level != "fresh":
        if intent == "transactional" or (not soft_stale):
            return {
                "ok": False,
                "error": "HAL_UNAVAILABLE_STALE_DATA",
                "readiness": readiness,
                "blocked": True,
                "intent": intent,
                "resolvedLane": resolved["lane"],
            }
        if intent == "analytical" and not soft_stale:
            return {
                "ok": False,
                "error": "HAL_UNAVAILABLE_STALE_DATA",
                "readiness": readiness,
                "blocked": True,
                "intent": intent,
                "resolvedLane": resolved["lane"],
            }

    local = try_local_policy_reply(query)
    if local:
        text = local["text"]
        append_lane_history(store, lane="local", model="policy", query=query, intent=local.get("intent", "local:policy"))
        return {
            "ok": True,
            "text": text,
            "message": {"content": text},
            "model": "local-policy",
            "readinessLevel": level,
            "intent": local.get("intent", "local:policy"),
            "softStale": soft_stale,
            "resolvedLane": "local",
            "routingReason": "local_policy",
        }

    chat_messages, intent, soft_stale, level = build_chat_messages(
        query=query,
        readiness=readiness,
        system_prompt=system_prompt,
        messages=messages,
    )

    result = call_ollama_chat(model=model, messages=chat_messages, stream=False, options=options)
    if not result.get("ok"):
        return {
            "ok": False,
            "error": result.get("error"),
            "detail": result.get("detail"),
            "resolvedLane": resolved["lane"],
        }

    body = result.get("body") or {}
    message = body.get("message") or {}
    text = extract_ollama_message_text(message)
    if level != "fresh" and intent == "transactional":
        text = redact_financial_numbers(text)
    elif level != "fresh" and soft_stale and intent in ("analytical", "clinical"):
        if SOFT_STALE_WATERMARK not in text:
            text = f"{SOFT_STALE_WATERMARK}\n\n{text}"
        text = redact_financial_numbers(text)

    append_lane_history(store, lane=resolved["lane"], model=model, query=query, intent=intent)

    out_message = dict(message)
    out_message["content"] = text
    return {
        "ok": True,
        "text": text,
        "message": out_message,
        "model": model,
        "readinessLevel": level,
        "intent": intent,
        "softStale": soft_stale,
        "resolvedLane": resolved["lane"],
        "routingReason": routing_reason or None,
    }
