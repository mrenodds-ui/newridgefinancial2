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
# Hard single-GPU policy: the office program may only call this local model.
APPROVED_LOCAL_MODEL = "hal-local:30b-a3b"
LANE_MODELS = {
    # R9700 32 GB single-model layout: all approved local lanes → MoE pin
    # (qwen3:30b-a3b Q4_K_M). Lane keys preserved; do not load dense 32B concurrently.
    "chat8b": APPROVED_LOCAL_MODEL,
    "reason21b": APPROVED_LOCAL_MODEL,
    "escalate30b": APPROVED_LOCAL_MODEL,
    "coder32b": APPROVED_LOCAL_MODEL,
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
# True clinical / chart / treatment narrative work (heavy lane).
_CLINICAL_PATTERN = re.compile(
    r"(?i)\b(clinical|procedure|tooth|quadrant|periodontal|perio\b|extraction|prophy|"
    r"srp|implant|endo(?:dontic)?|radiograph|periapical|bitewing|"
    r"chart(?:ing)?|probing|bop\b|treatment\s*plan)\b|"
    r"\b(draft|write|prepare)\b.*\b(narrative|clinical\s*note)\b|"
    r"\bnarrative\b.*\b(claim|crown|tooth)\b|"
    r"\bcrown\b.*\btooth\b|\btooth\b.*\bcrown\b"
)
# Payer routing, fee schedule, phones, CO-45 — tool-first, not 30B clinical.
_INSURANCE_OPS_PATTERN = re.compile(
    r"(?i)\b("
    r"payer|insurance|eob|era|claim(?:s)?|denial|appeal|"
    r"fee\s*schedule|allowed\s*amount|allowed\s*fee|contracted\s*fee|practice\s*amount|"
    r"co-?45|underpay(?:ment)?|ucr|"
    r"elig(?:ibility|ible)?\s*(?:phone|tel|number|website|portal|contact)|"
    r"(?:phone|tel|website|portal|fax|contact)\s*(?:for\s+)?elig(?:ibility|ible)?|"
    r"claim\s*phone|payer\s*id|routing\s*id|vyne|clearinghouse|"
    r"delta\s*dental|metlife|cigna|guardian|aetna|humana|bcbs|blue\s*cross|"
    r"united\s*concordia|careington|geha|dentemax|dentaquest"
    r")\b|"
    r"\bD\d{4}\b"
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
_STRUCTURED_PLAN_OPENER_RE = re.compile(
    r"^(?:here(?:'s| is) a structured plan|here is a (?:brief )?(?:numbered )?plan|structured plan:)\s*[:.\u2014-]?\s*",
    re.IGNORECASE,
)
_COT_PARAGRAPH_RE = re.compile(
    r"^(?:First,?\s+I need to|Let me (?:break|think|verify|re-evaluate|reconsider|check|start)|"
    r"We are given|Okay,?\s+the user|Hmm,?\s+the user|The user is asking|"
    r"\*Double-checking|\*Lightbulb|\*Verifying|\*Structure check|"
    r"\*Final verification|\*Why Friday|\*Critical constraint|\*Ordered steps)",
    re.IGNORECASE,
)
_DIRECT_ANSWER_MARKER_RE = re.compile(
    r"\*\*Direct Answer:\*\*\s*|^Direct answer:\s*|\*\*Here's (?:the|a) (?:direct )?answer:\*\*\s*",
    re.IGNORECASE | re.MULTILINE,
)
_WANTS_PLAN_RE = re.compile(
    r"prioriti[sz]e|make a plan|draft a plan|\bplan (my|for|the)\b|"
    r"analy[sz]e (?:this|the|my|our|it)|reason through|think through|\bstrategy\b|"
    r"focus first|where (do|should) (i|we) start|"
    r"\b(step[\s-]?by[\s-]?step plan|numbered plan|work plan|action plan)\b",
    re.IGNORECASE,
)
_SENTENCE_LIMIT_RE = re.compile(
    r"\b(?:in|with|using)?\s*(one|two|three|1|2|3)\s+sentences?\b|"
    r"\b(one|two|three|1|2|3)\s+sentences?\b|"
    r"\bin one sentence\b|\bin two sentences\b|\ba single sentence\b",
    re.IGNORECASE,
)
_PLAIN_LANGUAGE_RE = re.compile(r"\bplain(?:\s|-)?language\b|\bin plain english\b", re.IGNORECASE)
_DELIVERABLE_REQUEST_RE = re.compile(
    r"(?i)\b("
    r"next\s+steps?|ordered\s+steps?|step[\s-]?by[\s-]?step|"
    r"checklist|procedure|"
    r"how\s+(?:do|to|can)\s+(?:i|we)|"
    r"walk\s+me\s+through|"
    r"what\s+(?:are|is)\s+the\s+(?:steps?|path)|"
    r"provide\s+(?:the\s+)?(?:steps?|path|checklist)|"
    r"action\s+items?|"
    r"paths?\s+to\b"
    r")\b"
)
_DELIVERABLE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "steps": {"type": "array", "items": {"type": "string"}},
        "caution": {"type": "string"},
        "references": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["steps"],
}
_WRITE_INTENT_RE = re.compile(
    r"(?i)\b("
    r"(?:can|could|will|would|may|should)\s+(?:hal|you)\s+(?:please\s+)?"
    r"(?:post|write|write[\s-]?back|modify|delete|update|change|edit|submit)|"
    r"(?:post|write|write[\s-]?back|modify|delete|update)\b.{0,40}\b"
    r"(?:quickbooks|qb\b|softdent|fee\s*schedule|patient\s*record|ledger|journal)|"
    r"(?:quickbooks|softdent|fee\s*schedule).{0,40}\b"
    r"(?:post|write|write[\s-]?back|modify|delete|update)\b"
    r")\b"
)
_CARC_CODE_RE = re.compile(
    r"\b(?:CARC|CAS|adjustment\s+code|denial\s+code)\s*"
    r"(?:code\s*)?([A-Z]{2})[-\s]?(\d{1,4}|[A-Z]\d{1,3})\b|"
    r"\b([A-Z]{2})-(\d{1,4}|[A-Z]\d{1,3})\b",
    re.IGNORECASE,
)
_WORD_TO_N = {"one": 1, "two": 2, "three": 3, "1": 1, "2": 2, "3": 3}
_MEMORY_GUIDANCE_MARKERS = (
    "Governed memory matches:",
    "Durable HAL knowledge (guidance only",
)
_PAYER_GUIDANCE_MARKER = "Payer reference matches ("
_FEE_GUIDANCE_MARKER = "Fee schedule matches ("
_ELIGIBILITY_GUIDANCE_MARKER = "Cached eligibility context ("
_CLAIM_PAYER_GUIDANCE_MARKER = "Claim ↔ payer reference joins"
_DEFAULT_MEMORY_LIMIT = 6
_DEFAULT_PAYER_LIMIT = 4
_DEFAULT_FEE_LIMIT = 3
_DEFAULT_ELIGIBILITY_LIMIT = 2
_DEFAULT_CLAIM_JOIN_LIMIT = 8
_CLAIM_SCOPED_RE = re.compile(
    r"\b(claim|claims|denied|denial|appeal|pre-?submit|packet readiness|carrier on)\b",
    re.IGNORECASE,
)


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


_MID_BODY_COT_RE = re.compile(
    r"(?:^|\n+)\s*(?:Okay|Hmm),?\s+the user[^\n]*|"
    r"(?:^|\n+)\s*The user is asking[^\n]*|"
    r"(?:^|\n+)\s*First,?\s+I need to[^\n]*|"
    r"(?:^|\n+)\s*Let me (?:break|think|verify|re-evaluate|reconsider|check|start)[^\n]*|"
    r"(?:^|\n+)\s*\*(?:Double-checking|Lightbulb|Verifying|Structure check|Final verification)[^\n]*",
    re.IGNORECASE,
)


def strip_chain_of_thought_prose(text: str) -> str:
    out = str(text or "").strip()
    if not out:
        return out
    marker = _DIRECT_ANSWER_MARKER_RE.search(out)
    if marker:
        out = out[marker.end() :].strip()
    for _ in range(8):
        trimmed = out.strip()
        if not _COT_PARAGRAPH_RE.match(trimmed) and not re.match(
            r"^(?:Okay|Hmm|Let me|Wait|Pauses|Nods|Double-checks|Starts structuring)\b",
            trimmed,
            flags=re.IGNORECASE,
        ):
            break
        parts = re.split(r"\n\n+", trimmed, maxsplit=1)
        if len(parts) == 2 and len(parts[1]) > 40:
            out = parts[1].strip()
            continue
        sentence = re.search(r"[.!?]+\s+(?=[A-Z*\"])", trimmed)
        if sentence and 0 < sentence.start() < min(480, len(trimmed) - 60):
            out = trimmed[sentence.end() :].strip()
            continue
        out = _COT_PARAGRAPH_RE.sub("", trimmed, count=1).strip()
        out = re.sub(
            r"^(?:Okay|Hmm|Let me|Wait)[^.!?]*[.!?]?\s*",
            "",
            out,
            count=1,
            flags=re.IGNORECASE,
        ).strip()
        break
    # Drop mid-body scratchpad lines that survive leading-strip.
    out = _MID_BODY_COT_RE.sub("\n", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out.strip()


def sentence_limit_from_query(query: str) -> int | None:
    m = _SENTENCE_LIMIT_RE.search(str(query or ""))
    if not m:
        return None
    raw = next((g for g in m.groups() if g), None)
    if not raw:
        return None
    return _WORD_TO_N.get(str(raw).lower())


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", str(text or "").strip())
    parts = [p.strip() for p in parts if p.strip()]
    # Keep leading Yes./No. attached so a 1–2 sentence cap is not "No." alone.
    if len(parts) >= 2 and re.fullmatch(r"(?i)(?:yes|no)\.?", parts[0]):
        parts = [f"{parts[0]} {parts[1]}"] + parts[2:]
    return parts


def apply_response_constraints(query: str | None, text: str) -> str:
    """Post-generation hard filters: sentence caps, plain-language strip, no plan openers."""
    out = str(text or "").strip()
    if not out:
        return out
    q = str(query or "")
    # Structured deliverables keep list shape — do not collapse to a sentence cap.
    if is_deliverable_request(q):
        if not _WANTS_PLAN_RE.search(q):
            out = _STRUCTURED_PLAN_OPENER_RE.sub("", out).strip()
        return out.strip()
    limit = sentence_limit_from_query(q)
    if limit:
        # Drop markdown headings that inflate "sentence" dumps
        out = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", out)
        out = re.sub(r"(?m)^\s*[-*]\s+", "", out)
        sents = _split_sentences(out)
        if len(sents) > limit:
            out = " ".join(sents[:limit])
            if out and out[-1] not in ".!?":
                out += "."
    elif _PLAIN_LANGUAGE_RE.search(q):
        out = re.sub(r"(?m)^\s{0,3}#{1,6}\s+.*$", "", out)
        out = re.sub(r"(?m)^\s*\d+\.\s+", "", out)
        out = re.sub(r"\n{3,}", "\n\n", out).strip()
    if not (q and _WANTS_PLAN_RE.search(q)):
        out = _STRUCTURED_PLAN_OPENER_RE.sub("", out).strip()
    return out.strip()


def is_deliverable_request(query: str) -> bool:
    """True when staff asked for actionable steps/paths (Phase 2 structured output)."""
    return bool(_DELIVERABLE_REQUEST_RE.search(str(query or "")))


def deliverable_system_instruction() -> str:
    return (
        "Staff asked for actionable steps. Reply with JSON only using keys: "
        'steps (array of short action strings), caution (read-only/consent warning when relevant), '
        "references (optional existing page/file names — never invent paths or dollars). "
        "Do not invent CARC meanings or PHI. Empty ≠ $0. One sentence per step."
    )


def format_deliverable_markdown(data: dict[str, Any]) -> str:
    steps_raw = data.get("steps") if isinstance(data, dict) else None
    steps: list[str] = []
    if isinstance(steps_raw, list):
        steps = [str(s).strip() for s in steps_raw if str(s).strip()]
    elif isinstance(steps_raw, str) and steps_raw.strip():
        steps = [steps_raw.strip()]
    lines: list[str] = [f"{i}. {step}" for i, step in enumerate(steps[:12], 1)]
    caution = str((data or {}).get("caution") or "").strip()
    if caution:
        lines.append(f"Caution: {caution}")
    refs = (data or {}).get("references") if isinstance(data, dict) else None
    if isinstance(refs, list):
        cleaned = [str(r).strip() for r in refs if str(r).strip()]
        if cleaned:
            lines.append("References: " + "; ".join(cleaned[:6]))
    return "\n".join(lines).strip()


def normalize_deliverable_reply(query: str | None, text: str) -> str:
    """JSON schema → numbered steps; prose fallback to bullets when ask is deliverable."""
    q = str(query or "")
    out = str(text or "").strip()
    if not out or not is_deliverable_request(q):
        return out
    candidate = out
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", out, re.IGNORECASE)
    if fenced:
        candidate = fenced.group(1).strip()
    blob = re.search(r"\{[\s\S]*\}", candidate)
    if blob:
        try:
            obj = json.loads(blob.group(0))
            if isinstance(obj, dict) and obj.get("steps") is not None:
                formatted = format_deliverable_markdown(obj)
                if formatted:
                    return formatted
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    if re.search(r"(?m)^\s*(?:\d+\.|[-*•])\s+\S", out):
        return out
    sents = _split_sentences(out)
    if len(sents) >= 2:
        return "\n".join(f"{i}. {s}" for i, s in enumerate(sents[:8], 1))
    return out


def clean_gateway_text(text: str, *, query: str | None = None) -> str:
    out = str(text or "").strip()
    out = re.sub(r"<think>[\s\S]*?</think>", "", out, flags=re.IGNORECASE)
    out = re.sub(r"</?think>", "", out, flags=re.IGNORECASE)
    out = re.sub(r"<reasoning>[\s\S]*?</reasoning>", "", out, flags=re.IGNORECASE)
    out = re.sub(r"</?reasoning>", "", out, flags=re.IGNORECASE)
    if not (query and _WANTS_PLAN_RE.search(str(query))):
        out = _STRUCTURED_PLAN_OPENER_RE.sub("", out)
    out = strip_chain_of_thought_prose(out)
    out = _MONOLOGUE_START_RE.sub("", out)
    out = re.sub(
        r"^(?:Okay|Sure|Certainly)[,.]?\s*(?:from my (?:local )?)?(?:read-?only )?(?:monitoring )?perspective[,:]?\s*",
        "",
        out,
        flags=re.IGNORECASE,
    )
    out = apply_response_constraints(query, out)
    out = normalize_deliverable_reply(query, out)
    return out.strip()


def extract_ollama_message_text(message: dict[str, Any] | None, *, query: str | None = None) -> str:
    msg = message or {}
    content = str(msg.get("content") or "").strip()
    # Prefer visible content only — never surface raw thinking as the staff reply.
    # DeepSeek-R1 often fills `thinking` and leaves `content` empty; CoT strip then
    # yields "" — callers should fall back to try_local_policy_reply, not thinking.
    if content:
        return clean_gateway_text(content, query=query)
    return ""


def options_for_query(query: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
    """Cap generation for short / constrained asks to cut cold latency."""
    opts = dict(options or {})
    q = str(query or "")
    limit = sentence_limit_from_query(q)
    yes_no = bool(
        re.match(
            r"(?i)^(can you|are you|do you|does |is |yes or no|short answer:|short:)\b",
            q.strip(),
        )
    )
    if is_deliverable_request(q):
        opts.setdefault("num_predict", 384)
    elif limit is not None and limit <= 2:
        opts.setdefault("num_predict", 96)
    elif yes_no or _WRITE_INTENT_RE.search(q):
        opts.setdefault("num_predict", 128)
    elif len(q) < 80 and not _WANTS_PLAN_RE.search(q):
        opts.setdefault("num_predict", 160)
    return opts


def inject_deliverable_messages(messages: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    if not is_deliverable_request(query):
        return messages
    out = list(messages or [])
    instruction = {"role": "system", "content": deliverable_system_instruction()}
    # Insert after the first system prompt when present.
    if out and out[0].get("role") == "system":
        out.insert(1, instruction)
    else:
        out.insert(0, instruction)
    return out


def query_account_transactions(
    account_num: str | int | None = None,
    patient_name: str | None = None,
    date_range: Any = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """HAL gateway: query parsed SoftDent TXN Excel (fallback: data not yet exported)."""
    from softdent_transaction_extract import (
        query_account_transactions as _query_account_transactions,
    )

    return _query_account_transactions(
        account_num=account_num,
        patient_name=patient_name,
        date_range=date_range,
        **kwargs,
    )


def _extract_account_tx_query_filters(query: str) -> dict[str, Any] | None:
    """Detect patient-ledger asks (Donna-style / multi-year) and extract filters; else None."""
    q = str(query or "").strip()
    if not q:
        return None
    low = q.lower()
    wants_ledger = bool(
        re.search(
            r"\b("
            r"account\s+transactions?|patient\s+transactions?|patient\s+ledger|"
            r"account\s+history|ledger\s+for|history\s+for\s+account|"
            r"transactions?\s+for|"
            r"(what|show|list|pull|get).{0,40}transactions?"
            r")\b",
            low,
        )
    )
    if not wants_ledger:
        return None
    # How-to / export playbook asks stay on Excel doctrine, not ledger data
    if re.search(
        r"\b(how (do|to)|export|excel path|output options|trans for a period|print transactions)\b",
        low,
    ) and not re.search(r"\b(donna|nickel|\d{4,})\b", low):
        return None
    filters: dict[str, Any] = {}
    acct = re.search(r"\b(?:account|acct|id)\s*[#: ]?\s*(\d{4,})\b", low)
    if not acct:
        acct = re.search(r"\b(27002)\b", low)
    if acct:
        filters["account_num"] = acct.group(1)
    # "Donna Nickel" / "Nickel, Donna" — skip command verbs / ledger nouns
    _name_stop = {
        "show",
        "list",
        "what",
        "pull",
        "get",
        "are",
        "account",
        "accounts",
        "history",
        "transaction",
        "transactions",
        "patient",
        "ledger",
        "softdent",
        "from",
        "for",
        "with",
        "the",
        "and",
        "in",
        "to",
    }
    name = re.search(
        r"\b([A-Za-z]{2,})\s+([A-Za-z]{2,})(?:'s)?\b(?=.*\btransactions?\b)|"
        r"\b([A-Za-z]{2,})\s*,\s*([A-Za-z]{2,})\b",
        q,
    )
    if name:
        if name.group(1) and name.group(2):
            a, b = name.group(1).lower(), name.group(2).lower()
            if a not in _name_stop and b not in _name_stop:
                filters["patient_name"] = f"{name.group(2)}, {name.group(1)}"
        elif name.group(3) and name.group(4):
            a, b = name.group(3).lower(), name.group(4).lower()
            if a not in _name_stop and b not in _name_stop:
                filters["patient_name"] = f"{name.group(3)}, {name.group(4)}"
    if "donna" in low and "nickel" in low:
        filters["patient_name"] = "Nickel, Donna"
        filters.setdefault("account_num", "27002")
    # February 2026 / 2026-02 / Feb 2026
    month = re.search(
        r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
        r"dec(?:ember)?)\s+(20\d{2})\b",
        low,
    )
    if month:
        mon_map = {
            "jan": "01",
            "january": "01",
            "feb": "02",
            "february": "02",
            "mar": "03",
            "march": "03",
            "apr": "04",
            "april": "04",
            "may": "05",
            "jun": "06",
            "june": "06",
            "jul": "07",
            "july": "07",
            "aug": "08",
            "august": "08",
            "sep": "09",
            "sept": "09",
            "september": "09",
            "oct": "10",
            "october": "10",
            "nov": "11",
            "november": "11",
            "dec": "12",
            "december": "12",
        }
        filters["date_range"] = f"{month.group(2)}-{mon_map[month.group(1)]}"
    else:
        span = re.search(
            r"\b((?:19|20)\d{2})\s*(?:to|-|–|—|/)\s*((?:19|20)\d{2})\b",
            low,
        )
        if span:
            filters["date_range"] = f"{span.group(1)}:{span.group(2)}"
        else:
            ym = re.search(r"\b(20\d{2})-(\d{2})\b", low)
            if ym:
                filters["date_range"] = f"{ym.group(1)}-{ym.group(2)}"
            else:
                year_only = re.search(
                    r"\b(?:in|for|during|year)\s+((?:19|20)\d{2})\b|\b((?:19|20)\d{2})\b(?!\s*-\d{2})",
                    low,
                )
                if year_only:
                    filters["date_range"] = year_only.group(1) or year_only.group(2)
    if not filters.get("account_num") and not filters.get("patient_name"):
        return None
    filters["prefer_db"] = True
    return filters


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

    # Parsed SoftDent TXN Excel / sd_account_transactions patient-ledger — prefer DB
    ledger_filters = _extract_account_tx_query_filters(raw)
    if ledger_filters is not None:
        try:
            from softdent_transaction_extract import format_account_transactions_hal_reply

            result = query_account_transactions(**ledger_filters)
            return {
                "text": format_account_transactions_hal_reply(result),
                "intent": "policy:softdent-account-tx-ledger",
            }
        except Exception:
            return {
                "text": "Account transaction data not yet exported.",
                "intent": "policy:softdent-account-tx-ledger",
            }

    # Teach SoftDent desktop report pulls (Output Options Excel/Preview) — before
    # generic product KB so “how do I pull SoftDent reports?” gets the playbook.
    # Account-tx Excel asks stay on softdent-signon-env (Format 1 Trans playbook).
    try:
        from softdent_report_pull import (
            format_softdent_report_pull_hal_reply,
            query_touches_softdent_report_pull,
        )
        from softdent_signon import _query_touches_softdent_account_tx

        if query_touches_softdent_report_pull(raw) and not _query_touches_softdent_account_tx(raw):
            return {
                "text": format_softdent_report_pull_hal_reply(raw),
                "intent": "policy:softdent-report-pull",
            }
    except Exception:
        pass

    # SoftDent full product KB (Carestream Help TOC + topic bodies) — before
    # InsCo×ADA "catalog" and other SoftDent ops policies that share keywords.
    # Skip account-tx Excel playbook asks (those stay on softdent-signon-env).
    try:
        from softdent_product_kb import (
            format_softdent_product_kb_hal_reply,
            query_touches_softdent_product,
        )
        from softdent_signon import _query_touches_softdent_account_tx

        if query_touches_softdent_product(raw) and not _query_touches_softdent_account_tx(raw):
            # Credential-only Sign On questions stay on sign-on policy
            if not re.search(
                r"\b(sign\s*on|sign-on|password|credential|change login)\b",
                q,
            ) or re.search(
                r"\b(product|help|manual|module|report|charting|era|how\s+(does|do)|inside)\b",
                q,
            ):
                return {
                    "text": format_softdent_product_kb_hal_reply(raw),
                    "intent": "policy:softdent-product-kb",
                }
    except Exception:
        pass

    # Outstanding Claims by Carrier ↔ Account Aging bridge (HAL-10580)
    if re.search(
        r"\b("
        r"outstanding\s+claims?\s+by\s+(carrier|payer|co)|"
        r"claims?\s+by\s+(carrier|payer)|"
        r"claims?\s*/?\s*a/?r\s+bridge|"
        r"account\s+aging\s+total|"
        r"aging\s+outstanding\s+insurance"
        r")\b",
        q,
    ):
        try:
            from softdent_outstanding_claims_bridge import (
                build_outstanding_claims_by_carrier_bridge,
                format_outstanding_claims_hal_reply,
            )

            bridge = build_outstanding_claims_by_carrier_bridge(write_inbox=True)
            return {
                "text": format_outstanding_claims_hal_reply(bridge),
                "intent": "policy:outstanding-claims-by-carrier",
                "suggestedAction": str(bridge.get("suggestedAction") or ""),
                "gapCode": str(bridge.get("gapCode") or ""),
            }
        except Exception:
            return {
                "text": (
                    "Outstanding Claims by Carrier bridge unavailable. "
                    "Ensure softdent_financial_analytics.db has sd_claims and "
                    r"Account Aging Excel is in C:\SoftDentReportExports. Empty != $0."
                ),
                "intent": "policy:outstanding-claims-by-carrier",
            }

    # InsCo × ADA probabilistic ledger estimates (HAL-10582/83) — exact default
    try:
        from softdent_insco_ada_probabilistic import (
            format_probabilistic_estimate_reply,
            format_probabilistic_status_reply,
            log_inferred_view_audit,
            lookup_probabilistic_estimate,
            parse_probabilistic_estimate_query,
            probabilistic_report_status,
        )

        parsed_p = parse_probabilistic_estimate_query(raw)
        if parsed_p and parsed_p.get("kind") == "status":
            return {
                "text": format_probabilistic_status_reply(probabilistic_report_status()),
                "intent": "policy:insco-ada-estimates",
            }
        if parsed_p and parsed_p.get("kind") == "lookup":
            include_inf = bool(parsed_p.get("includeInferred"))
            if include_inf:
                log_inferred_view_audit(
                    payer=str(parsed_p.get("payer") or ""),
                    ada=str(parsed_p.get("adaCode") or ""),
                    source="hal-gateway",
                )
            est = lookup_probabilistic_estimate(
                payer=str(parsed_p.get("payer") or ""),
                ada_code=str(parsed_p.get("adaCode") or ""),
                include_inferred=include_inf,
            )
            return {
                "text": format_probabilistic_estimate_reply(
                    est,
                    payer=str(parsed_p.get("payer") or ""),
                    ada=str(parsed_p.get("adaCode") or ""),
                    include_inferred=include_inf,
                ),
                "intent": "policy:insco-ada-estimates",
                "includeInferred": include_inf,
                "credibility": (est or {}).get("credibility"),
                "tier": (est or {}).get("tier"),
            }
    except Exception:
        pass

    # InsCo × ADA pay/write-off % +/- variance (HAL-10584) — 5yr code 2/51 pairing
    try:
        from softdent_insco_ada_pct_variance import (
            format_pct_variance_reply,
            format_pct_variance_status_reply,
            lookup_pct_variance,
            pct_variance_status,
        )

        raw_l = raw.lower()
        if re.search(
            r"\b(pay|paid|write[\s-]?off|wo)\s*%|percent(age)?\s*(pay|write)|"
            r"insco.{0,20}(pct|percent|variance)|"
            r"(ada|code).{0,30}(pay|write).{0,20}%|"
            r"5\s*year.{0,40}(insurance|insco|pay|write)",
            raw_l,
        ):
            if re.search(r"\bstatus\b|how many|summary|report", raw_l):
                return {
                    "text": format_pct_variance_status_reply(pct_variance_status()),
                    "intent": "policy:insco-ada-pct-variance",
                }
            # crude payer + ADA extract
            ada_m = re.search(r"\b(d?\d{3,5})\b", raw_l, re.I)
            ada = (ada_m.group(1) if ada_m else "").upper()
            payer = ""
            for name in (
                "DELTA DENTAL OF KS",
                "METLIFE DENTAL",
                "CIGNA DENTAL",
                "BCBS OF KS",
                "GUARDIAN",
                "AETNA",
            ):
                if name.lower() in raw_l or name.split()[0].lower() in raw_l:
                    payer = name
                    break
            if payer and ada:
                include_inf = bool(re.search(r"infer|uncertain|multi", raw_l))
                row = lookup_pct_variance(
                    payer=payer, ada_code=ada, include_inferred=include_inf
                )
                return {
                    "text": format_pct_variance_reply(row, payer=payer, ada=ada),
                    "intent": "policy:insco-ada-pct-variance",
                    "tier": (row or {}).get("tier"),
                    "credibility": (row or {}).get("credibility"),
                }
            return {
                "text": format_pct_variance_status_reply(pct_variance_status()),
                "intent": "policy:insco-ada-pct-variance",
            }
    except Exception:
        pass

    # InsCo × ADA full catalog matrix (HAL-10586) — includes insufficient
    try:
        from softdent_insco_ada_catalog_matrix import (
            format_catalog_status_reply,
            catalog_matrix_status,
            list_catalog_matrix_rows,
            uncovered_ledger_cdts,
        )

        raw_l = raw.lower()
        if re.search(
            r"\b(catalog|full\s+matrix|matrix\s+catalog|insco.{0,20}catalog|"
            r"every\s+(ada|cdt|code)|insufficient\s+cells|"
            r"uncovered\s+(ledger\s+)?(cdt|ada)|catalog\s+csv|"
            r"where\s+is\s+the\s+catalog)",
            raw_l,
        ):
            if re.search(r"csv|export|where\s+is\s+the\s+catalog", raw_l):
                from softdent_insco_ada_catalog_matrix import insco_ada_catalog_widget

                w = insco_ada_catalog_widget()
                return {
                    "text": (
                        f"InsCo×ADA catalog CSV ({w.get('def')}): "
                        f"csvPath={w.get('csvPath') or '—'}; "
                        f"inboxCsvPath={w.get('inboxCsvPath') or '—'}; "
                        f"cells={w.get('totalCells')}; exact usable={w.get('exactUsableCells')}; "
                        f"uncovered={w.get('uncoveredCount')}. "
                        "Ledger-inferred only — does not invent gold payment lines. empty≠$0."
                    ),
                    "intent": "policy:insco-ada-catalog-matrix",
                    "csvPath": w.get("csvPath"),
                    "inboxCsvPath": w.get("inboxCsvPath"),
                }
            if re.search(r"uncovered|no spine|without settlement", raw_l):
                uncovered = uncovered_ledger_cdts()
                return {
                    "text": (
                        f"Ledger CDTs with no InsCo×ADA spine settlement cell yet "
                        f"({len(uncovered)}): "
                        + (", ".join(uncovered[:40]) + ("…" if len(uncovered) > 40 else ""))
                        + ". empty≠$0 — not the same as $0 write-off."
                    ),
                    "intent": "policy:insco-ada-catalog-matrix",
                    "uncoveredCount": len(uncovered),
                }
            if re.search(r"insufficient", raw_l):
                rows = list_catalog_matrix_rows(
                    include_insufficient=True,
                    credibility="insufficient",
                    limit=15,
                )
                lines = [
                    f"InsCo×ADA insufficient sample (showing {len(rows)}; empty≠$0):",
                ]
                for r in rows:
                    lines.append(
                        f"- {r['insuranceCompany']} × {r['adaCode']} "
                        f"n={r['sampleSize']} tier={r['tier']}"
                    )
                return {
                    "text": "\n".join(lines),
                    "intent": "policy:insco-ada-catalog-matrix",
                }
            return {
                "text": format_catalog_status_reply(catalog_matrix_status()),
                "intent": "policy:insco-ada-catalog-matrix",
            }
    except Exception:
        pass

    # Print Preview visual audit (HAL-10590)
    try:
        from softdent_print_preview_audit import (
            format_print_preview_audit_reply,
            list_print_preview_audits,
            print_preview_audit_playbook,
        )

        raw_l = raw.lower()
        if re.search(
            r"\b(print\s+preview\s+audit|visual\s+audit|ops-?10590|"
            r"record.{0,30}(insurance\s+income|last\s+page)|"
            r"how.{0,40}record.{0,40}print\s+preview)",
            raw_l,
        ):
            st = list_print_preview_audits()
            play = print_preview_audit_playbook()
            text = format_print_preview_audit_reply(st)
            text += (
                f" When Print Preview only: {play.get('f10')} → Print Preview → "
                f"{play.get('pages')}."
            )
            return {
                "text": text,
                "intent": "policy:print-preview-audit",
                "gapCode": st.get("gapCode"),
                "visualAuditLastPageTotal": st.get("visualAuditLastPageTotal"),
                "playbook": play,
            }
    except Exception:
        pass

    # UI honesty empty≠$0 (HAL-10591 / HON-001)
    try:
        from ui_honesty_policy import (
            audit_ui_honesty_surfaces,
            format_honesty_audit_reply,
        )

        raw_l = raw.lower()
        if re.search(
            r"\b(empty\s*(!=|≠|not)\s*\$?0|hon-?001|ops-?10591|hal-?10591|"
            r"ui\s+honesty|honesty\s+audit|"
            r"what\s+does\s+empty.{0,20}\$?0)",
            raw_l,
        ):
            result = audit_ui_honesty_surfaces()
            return {
                "text": format_honesty_audit_reply(result),
                "intent": "policy:empty-not-zero",
                "passCount": result.get("passCount"),
                "failCount": result.get("failCount"),
                "ok": result.get("ok"),
            }
    except Exception:
        pass

    # Visual×ledger reconciliation (HAL-10592 / HON-002)
    try:
        from softdent_visual_ledger_recon import (
            format_visual_ledger_recon_reply,
            reconcile_visual_vs_ledger,
        )

        raw_l = raw.lower()
        if re.search(
            r"\b(visual\s*(x|×|\-| )?ledger|hon-?002|ops-?10592|hal-?10592|"
            r"visual\s+ledger\s+recon|"
            r"visual\s+audit\s+vs\s+ledger|"
            r"what\s+does\s+visual.{0,40}reconcil)",
            raw_l,
        ):
            result = reconcile_visual_vs_ledger()
            return {
                "text": format_visual_ledger_recon_reply(result),
                "intent": "policy:visual-ledger-recon",
                "result": result.get("result")
                or (result.get("comparison") or {}).get("result"),
                "thresholdViolated": result.get("thresholdViolated")
                or (result.get("comparison") or {}).get("thresholdViolated"),
                "gapCode": result.get("gapCode"),
            }
    except Exception:
        pass

    # Gold CSV drop OPS (HAL-10589) — prefer before generic gold pipeline for drop asks
    try:
        from softdent_gold_csv_drop_ops import (
            checklist_post_ingest,
            format_gold_csv_drop_ops_reply,
            gold_csv_drop_playbook,
        )

        raw_l = raw.lower()
        if re.search(
            r"\b(gold\s+csv\s+drop|ops-?10589|csv\s+drop\s+ops|"
            r"drop.{0,20}insurance\s+payment|"
            r"how.{0,40}export.{0,40}insurance\s+payment\s+analysis)",
            raw_l,
        ):
            st = checklist_post_ingest()
            play = gold_csv_drop_playbook()
            text = format_gold_csv_drop_ops_reply({"post": st})
            try:
                from apex_32b_program_fixes_pack import gold_csv_ops_staff_reply

                text = gold_csv_ops_staff_reply()
            except Exception:
                text += f" Steps: {play.get('softDentMenu')} → {play.get('saveAs')} → Sync."
            return {
                "text": text,
                "intent": "policy:gold-csv-drop-ops",
                "gapCode": (st.get("audit") or {}).get("gapCode"),
                "playbook": play,
            }
    except Exception:
        pass

    # Gold payment pipeline (HAL-10588)
    try:
        from softdent_gold_payment_pipeline import (
            audit_gold_payment_pipeline,
            format_gold_pipeline_reply,
        )

        raw_l = raw.lower()
        if re.search(
            r"\b(gold\s+payment|payment\s+pipeline|insurance\s+payment\s+analysis|"
            r"why.{0,20}payment\s+lines|export.{0,40}insurance\s+payment)",
            raw_l,
        ):
            st = audit_gold_payment_pipeline()
            return {
                "text": format_gold_pipeline_reply(st),
                "intent": "policy:gold-payment-pipeline",
                "gapCode": st.get("gapCode"),
            }
    except Exception:
        pass

    # SoftDent GUI Sign On — credentials in env vars (never echo password)
    # Also: data not in DB → Sign On + UI; widget data paths; period $ drift;
    # account transactions → Excel playbook
    if re.search(
        r"\b("
        r"sign\s*on|sign-on|change login|"
        r"softdent\s+(login|password|credential|sign\s*on)|"
        r"log\s*in\s+(to\s+)?softdent|"
        r"where.{0,30}(softdent|sign\s*on).{0,30}(password|credential|env)|"
        r"(password|credential).{0,30}softdent|"
        r"(cannot be reached|can'?t (be )?reach|not in (the )?(database|db|odbc)|"
        r"only (way|via|through).{0,24}(ui|gui|sign\s*on)|"
        r"softdent.{0,40}(ui|gui).{0,20}(export|report)|"
        r"how.{0,40}softdent.{0,40}(not|without).{0,20}(database|odbc|db)|"
        r"source of truth|"
        r"(where|how).{0,40}(vital signs|ins.?patient|collections gap|widget).{0,40}(data|from|get)|"
        r"softdent.{0,30}widget.{0,30}(data|path|source)|"
        r"(register|daysheet).{0,24}(drift|disagree|mismatch)|"
        r"account\s+transactions?|patient\s+transactions?|"
        r"trans(actions?)?\s+for\s+(a\s+)?period|"
        r"print\s+transactions?|"
        r"(pull|export|get).{0,40}(account|patient|transaction).{0,30}(excel|softdent|ledger)|"
        r"softdent.{0,40}(transaction|ledger).{0,30}(excel|export|pull)|"
        r"list\s+each\s+transaction\s+separately|"
        r"account\s+(mode|transaction)\s+tab)"
        r")\b",
        q,
    ):
        try:
            from softdent_signon import (
                format_softdent_account_tx_excel_hal_reply,
                format_softdent_signon_hal_reply,
                format_softdent_widget_path_hal_reply,
                softdent_signon_status,
            )

            text = format_softdent_signon_hal_reply(softdent_signon_status())
            if re.search(
                r"\b(widget|vital signs|ins.?patient|drift|mismatch|data path|where.{0,20}data)\b",
                q,
            ):
                text = text + " " + format_softdent_widget_path_hal_reply()
                try:
                    from softdent_period_money_drift import (
                        compare_register_to_daysheet_totals,
                        format_drift_hal_reply,
                    )

                    text = text + " " + format_drift_hal_reply(compare_register_to_daysheet_totals())
                except Exception:
                    pass
            if re.search(
                r"\b("
                r"account\s+transactions?|patient\s+transactions?|"
                r"trans(actions?)?\s+for\s+(a\s+)?period|print\s+transactions?|"
                r"(pull|export|get).{0,40}(account|patient|transaction).{0,30}(excel|softdent|ledger)|"
                r"softdent.{0,40}(transaction|ledger).{0,30}(excel|export|pull)|"
                r"list\s+each\s+transaction|account\s+(mode|transaction)\s+tab"
                r")\b",
                q,
            ):
                text = text + " " + format_softdent_account_tx_excel_hal_reply()
            return {
                "text": text,
                "intent": "policy:softdent-signon-env",
            }
        except Exception:
            return {
                "text": (
                    "SoftDent GUI Sign On credentials live in environment variables "
                    "SOFTDENT_SIGNON_USER / SOFTDENT_SIGNON_PASSWORD "
                    r"(also C:\New folder\.env). "
                    "Desktop SoftDent Excel is the source of truth for period financial totals; "
                    "sd_*/Sensei is faster for operational detail. "
                    "Account txs: Reports → Accounting → Trans for a Period → Excel "
                    "(Format 1 = List Each Transaction Separately); save into "
                    r"C:\SoftDentReportExports (SoftDent may open temp SDWIN*.csv in Excel). "
                    "HAL will not print the password."
                ),
                "intent": "policy:softdent-signon-env",
            }

    # CARC/CAS whitelist (Phase 4) — known briefs only; unknown hard-refuse (no LLM).
    if re.search(r"\b(what|signify|mean|explain)\b", q) and (
        "carc" in q or "cas" in q or "adjustment code" in q or "denial code" in q
    ):
        from era835_parser import (
            carc_unknown_refusal,
            extract_carc_codes_from_text,
            format_carc_brief_reply,
            is_known_carc_code,
            lookup_carc_brief,
        )

        codes = extract_carc_codes_from_text(raw)
        if codes:
            unknown = [c for c in codes if not is_known_carc_code(c)]
            if unknown:
                return {
                    "text": carc_unknown_refusal(unknown),
                    "intent": "policy:carc-unknown",
                }
            code = codes[0]
            brief = format_carc_brief_reply(code) or lookup_carc_brief(code)
            if brief:
                return {"text": brief, "intent": f"policy:carc-{code.lower()}"}
            return {
                "text": carc_unknown_refusal([code]),
                "intent": "policy:carc-unknown",
            }
    # Empty payroll/AP honesty
    if re.search(r"\bempty\b", q) and re.search(r"\b(payroll|wages|ap\b|unpaid bills)\b", q):
        if re.search(r"\b(\$0|0\$|zero|same as)\b", q) or "empty" in q:
            return {
                "text": (
                    "No. An empty payroll/AP export is not the same as $0 wages or balances — "
                    "empty ≠ $0. Drop a real QuickBooks export or mark an empty-batch sidecar; "
                    "do not invent amounts."
                ),
                "intent": "policy:empty-not-zero",
            }

    # DEF-001 — empty revenue-composition / collections ≠ $0 (local, no LLM)
    # Also: Register Ins Plan $0 → ERA-835 honesty (hal-10571)
    # Also: Refresh Inbox / ERA inbox ingest guidance (hal-10576)
    # Also: remittance discovery scan (hal-10576)
    # Also: Collections Excel-temp health (hal-10576)
    if re.search(
        r"\b("
        r"collections?\s+export\s+(health|ready|status)|"
        r"excel[- ]?temp|"
        r"temp_file_locked|"
        r"(sdwin|excel).{0,20}(lock|locked|sharing)"
        r")\b",
        q,
    ):
        try:
            from softdent_excel_temp import collections_export_health

            health = collections_export_health()
            ready = bool(health.get("collectionsExportReady"))
            code = health.get("errorCode") or "ok"
            return {
                "text": (
                    f"Collections Excel-temp health: ready={ready} · errorCode=`{code}`.\n"
                    f"{health.get('hint') or ''}\n"
                    "Reliability only — empty ≠ $0; do not re-export Register hoping Ins Plan > 0; "
                    "ERA-835 still required for insurance detail when Ins Plan is $0."
                ),
                "intent": "policy:collections-excel-temp",
            }
        except Exception:
            return {
                "text": (
                    "Collections Excel-temp uses retry/backoff when SoftDent holds SDWIN* locks. "
                    "Check GET /api/apex/hal/collections-export/health. Empty ≠ $0."
                ),
                "intent": "policy:collections-excel-temp",
            }

    if re.search(
        r"\b("
        r"scan\s+for\s+(era|835|remit)|"
        r"discover\s+(era|835|remit)|"
        r"find\s+(era|835|remittance)|"
        r"era\s+files?\s+on\s+disk|"
        r"local\s+era"
        r")\b",
        q,
    ):
        try:
            from apex_era835_pack import discover_era_candidates

            found = discover_era_candidates(limit=8)
            count = int(found.get("candidateCount") or 0)
            chip = found.get("chipLabel") or ""
            lines = [
                f"ERA remittance discovery (read-only): {chip} (empty ≠ $0).",
                f"Scanned roots: {', '.join((found.get('scannedRoots') or [])[:4]) or '—'}.",
            ]
            for row in list(found.get("candidates") or [])[:5]:
                lines.append(
                    f"- {row.get('path')} · {row.get('sizeBytes')}B · {row.get('matchReason')}"
                    f"{' · in-inbox' if row.get('inInbox') else ''}"
                )
            if count == 0:
                lines.append(
                    "No local candidates — staff must procure real payer 835 files into "
                    r"C:\SoftDentFinancialExports\era. Do not invent dollars or re-export Register."
                )
            else:
                lines.append(
                    "Verify candidates, copy into the ERA inbox, then Refresh Inbox. "
                    "Discovery does not move files or write SoftDent."
                )
            return {"text": "\n".join(lines), "intent": "policy:era-discover"}
        except Exception:
            return {
                "text": (
                    "Use Collections Gap → Scan for ERA Files (read-only discovery across "
                    r"SoftDent/export roots). Empty ≠ $0; no SoftDent write-back."
                ),
                "intent": "policy:era-discover",
            }

    if re.search(
        r"\b("
        r"refresh\s+(era|835|inbox)|"
        r"(era|835)\s+inbox\s+(ingest|refresh|status)|"
        r"ingest\s+(era|835)|"
        r"awaiting\s+first\s+835"
        r")\b",
        q,
    ):
        try:
            from apex_era835_pack import scan_era_inbox

            scanned = scan_era_inbox(ensure_dirs=True)
            chip = scanned.get("chipLabel") or "Awaiting first 835 drop"
            files = scanned.get("fileCount") or 0
            return {
                "text": (
                    f"ERA inbox: {chip} (files={files}; empty ≠ $0). "
                    "Use Collections Gap → Refresh Inbox (session token / CSRF) or "
                    "`scripts/run_era_inbox_ingest_ops.py` after dropping real payer 835 files "
                    "into C:\\SoftDentFinancialExports\\era. No SoftDent write-back; "
                    "do not re-export Register hoping Ins Plan > 0."
                ),
                "intent": "policy:era-inbox-refresh",
            }
        except Exception:
            return {
                "text": (
                    "ERA inbox Refresh Inbox uses the browser session token "
                    "(X-NR2-Session-Token). Drop real 835 files, then click Refresh Inbox "
                    "or run scripts/run_era_inbox_ingest_ops.py. Empty ≠ $0."
                ),
                "intent": "policy:era-inbox-refresh",
            }

    if re.search(
        r"\b("
        r"re[- ]?export\s+(?:the\s+)?(?:july\s+)?register|"
        r"export\s+(?:the\s+)?(?:july\s+)?register\s+again|"
        r"(hope|hoping|want|need).{0,40}ins\s*plan.{0,20}(>\s*0|greater|positive)|"
        r"register.{0,30}ins\s*plan.{0,20}(>\s*0|again)"
        r")\b",
        q,
    ):
        try:
            from nr2_contracts.softdent_hardening import (
                SUGGESTED_ACTION_ERA_835_PROCURE,
                assess_collections_gap,
                format_collections_gap_reply,
                register_ins_plan_zero_blocks_reexport,
            )

            bundle = None
            try:
                from apex_backend import _load_reports_and_bundle

                _reports, bundle, _err = _load_reports_and_bundle()
            except Exception:
                bundle = None
            gap = assess_collections_gap(bundle)
            if register_ins_plan_zero_blocks_reexport(gap):
                return {
                    "text": (
                        format_collections_gap_reply(gap)
                        + "\nRefused: Register re-export for Ins Plan > 0 is blocked "
                        f"(suggestedAction=`{gap.get('suggestedAction') or SUGGESTED_ACTION_ERA_835_PROCURE}`)."
                    ),
                    "intent": "policy:forbid-register-reexport",
                    "suggestedAction": str(
                        gap.get("suggestedAction") or SUGGESTED_ACTION_ERA_835_PROCURE
                    ),
                }
        except Exception:
            return {
                "text": (
                    "Do not re-export SoftDent Register hoping Ins Plan Collections > 0 — "
                    "July Register already reported Ins Plan $0.00 (SoftDent truth). "
                    "Procure ERA-835 for insurance detail. Empty ≠ $0."
                ),
                "intent": "policy:forbid-register-reexport",
                "suggestedAction": "era_835_procure",
            }

    if re.search(
        r"\b("
        r"revenue.?composition|payer mix|insurance.?patient|"
        r"collections?\s+(empty|pending|missing|gap)|"
        r"why .{0,40}(collections|revenue.?composition)|"
        r"def-?001|daysheet|"
        r"(july|open.?month).{0,30}(insurance|ins.?plan).{0,20}collections?|"
        r"ins.?plan\s+collections?|"
        r"era.?835|"
        r"regular\s+collections"
        r")\b",
        q,
    ) and re.search(
        r"\b(empty|pending|missing|gap|\$0|zero|why|july|insurance|ins.?plan|era|collections?|regular)\b",
        q,
    ):
        try:
            from nr2_contracts.softdent_hardening import assess_collections_gap, format_collections_gap_reply

            bundle = None
            try:
                from apex_backend import _load_reports_and_bundle

                _reports, bundle, _err = _load_reports_and_bundle()
            except Exception:
                bundle = None
            gap = assess_collections_gap(bundle)
            return {
                "text": format_collections_gap_reply(gap),
                "intent": "policy:def-001-collections",
                "suggestedAction": str(gap.get("suggestedAction") or "era_835_procure"),
            }
        except Exception:
            return {
                "text": (
                    "SoftDent Register reports Ins Plan Collections $0.00; proceed with ERA-835 "
                    "for insurance detail. Empty ≠ $0; do not re-export Register hoping Ins Plan > 0."
                ),
                "intent": "policy:def-001-collections",
                "suggestedAction": "era_835_procure",
            }

    # Two-sentence HAL summary (constraint-friendly local answer)
    if re.search(r"\bwhat hal does\b", q) or (
        re.search(r"\bsummarize\b", q) and re.search(r"\bhal\b", q) and re.search(r"\b(program|does|do)\b", q)
    ):
        if sentence_limit_from_query(raw) == 2 or "two sentence" in q:
            return {
                "text": (
                    "HAL is the local read-only office assistant in NR2 Apex for imports, claims, and narratives. "
                    "It never writes SoftDent/QuickBooks or submits to payers without explicit staff consent."
                ),
                "intent": "policy:hal-summary",
            }

    # Hard write-intent preflight (P1) — block before LLM.
    if _WRITE_INTENT_RE.search(raw) or _WRITE_INTENT_RE.search(q):
        if re.search(r"\b(softdent|patient|fee\s*schedule|chart)\b", q):
            return {
                "text": (
                    "No. HAL cannot modify SoftDent, fee schedules, or patient records — "
                    "NR2 stays read-only; staff update SoftDent directly."
                ),
                "intent": "consent:writeback-blocked",
            }
        if re.search(r"\b(quickbooks|qb\b|journal|ledger|iif)\b", q):
            return {
                "text": (
                    "No — I cannot post or write inside QuickBooks from NR2 (read-only). "
                    'I can draft locally or export IIF after you say "I consent"; staff still post in QuickBooks.'
                ),
                "intent": "consent:qb-post-blocked",
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

    can = re.match(r"^(?:are you allowed to|can you|can hal) (.+?)(?:\s+without (?:staff approval|consent))?\??$", q)
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
                        "No — I cannot click Post inside QuickBooks from NR2 (read-only). "
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
    if re.search(r"\bare imports read-?only\b", q) or (
        re.search(r"\bimports?\b", q) and re.search(r"\bread-?only\b", q) and re.search(r"\b(are|is)\b", q)
    ):
        return {
            "text": (
                "Yes. Imports are read-only — SoftDent and QuickBooks exports load into the local "
                "bundle for dashboards and HAL; nothing writes back from NR2."
            ),
            "intent": "policy:imports-readonly",
        }
    return None


def build_live_claims_money_context() -> str:
    """Inject live SoftDent claims totals so HAL cannot invent $0 against real signal."""
    try:
        from nr2_softdent_daily import claims_outstanding

        raw = claims_outstanding(limit=50)
    except Exception as exc:  # noqa: BLE001
        return (
            "[LIVE_CLAIMS_CONTEXT]\n"
            f"signal=NO_SIGNAL error={exc}\n"
            "If asked for claims dollars: say NO SIGNAL — do not invent $0.\n"
            "[END_LIVE_CLAIMS_CONTEXT]"
        )
    if not isinstance(raw, dict) or not raw.get("hasData"):
        return (
            "[LIVE_CLAIMS_CONTEXT]\n"
            "hasData=false · empty ≠ $0 · say ∅ / NO SIGNAL, never invent dollars.\n"
            "[END_LIVE_CLAIMS_CONTEXT]"
        )
    total = raw.get("totalOutstanding")
    claims = raw.get("claims") if isinstance(raw.get("claims"), list) else []
    count = len(claims)
    try:
        total_n = float(total) if total is not None else None
    except (TypeError, ValueError):
        total_n = None
    if total_n is None and claims:
        total_n = 0.0
        for c in claims:
            if isinstance(c, dict) and c.get("amount") is not None:
                try:
                    total_n += float(c.get("amount") or 0)
                except (TypeError, ValueError):
                    pass
    lines = [
        "[LIVE_CLAIMS_CONTEXT]",
        f"hasData=true count={count}",
        f"totalOutstanding={total_n if total_n is not None else 'unknown'}",
        "Authority: use this total for SoftDent claims/outstanding questions.",
        "Never say $0 or 0 when totalOutstanding > 0. empty ≠ $0.",
        "HAL estimates — verify against live SoftDent claims beam.",
        "[END_LIVE_CLAIMS_CONTEXT]",
    ]
    return "\n".join(lines)


def try_live_claims_total_reply(query: str) -> dict[str, str] | None:
    """Deterministic claims-total honesty — prefer live API over model guess."""
    q = re.sub(r"^hal[,:]\s+", "", str(query or ""), flags=re.IGNORECASE).lower().strip()
    if not re.search(
        r"\b("
        r"outstanding\s+claims?\s*(total|sum|amount)?|"
        r"claims?\s+outstanding|"
        r"total\s+(softdent\s+)?claims?|"
        r"how\s+much\s+.*\bclaims?\b|"
        r"claims?\s+total"
        r")\b",
        q,
    ):
        return None
    try:
        from nr2_softdent_daily import claims_outstanding

        raw = claims_outstanding(limit=200)
    except Exception as exc:  # noqa: BLE001
        return {
            "text": f"SoftDent claims signal unavailable ({exc}). empty ≠ $0 — do not invent a total.",
            "intent": "policy:claims-total-nosignal",
        }
    if not isinstance(raw, dict) or not raw.get("hasData"):
        return {
            "text": "No SoftDent claims signal (∅). empty ≠ $0 — not $0.00.",
            "intent": "policy:claims-total-empty",
        }
    total = raw.get("totalOutstanding")
    claims = raw.get("claims") if isinstance(raw.get("claims"), list) else []
    try:
        total_n = float(total) if total is not None else None
    except (TypeError, ValueError):
        total_n = None
    if total_n is None:
        total_n = 0.0
        for c in claims:
            if isinstance(c, dict) and c.get("amount") is not None:
                try:
                    total_n += float(c.get("amount") or 0)
                except (TypeError, ValueError):
                    pass
    return {
        "text": (
            f"Live SoftDent claims outstanding: ${total_n:,.0f} "
            f"across {len(claims)} claim(s) (read-only API). "
            "empty ≠ $0 · verify against SoftDent beam · HAL does not invent dollars."
        ),
        "intent": "policy:claims-total-live",
    }


def build_import_readiness_context(readiness: dict[str, Any]) -> str:
    lines = [
        "[IMPORT_CONTEXT]",
        f"Status: {str(readiness.get('level') or 'unknown').upper()}",
        f"LoadedAt: {readiness.get('loadedAt') or 'unknown'}",
        f"AgeHours: {readiness.get('ageHours') if readiness.get('ageHours') is not None else 'unknown'}",
        f"Ok: {'yes' if readiness.get('ok') else 'no'}",
    ]
    summary = readiness.get("summary") if isinstance(readiness.get("summary"), dict) else {}
    if summary:
        lines.append(
            "Counts: connected={c} missing={m} stale={s} (missingOptional={mo})".format(
                c=summary.get("connected"),
                m=summary.get("missing"),
                s=summary.get("stale"),
                mo=summary.get("missingOptional"),
            )
        )
    gaps = readiness.get("datasetGaps") if isinstance(readiness.get("datasetGaps"), list) else []
    if gaps:
        lines.append("Named gaps (use these exact keys — do not invent a generic checklist):")
        for g in gaps[:12]:
            if not isinstance(g, dict):
                continue
            lines.append(
                f"- {g.get('datasetKey')} [{g.get('severity')}/{g.get('status')}]"
                + (f" — {g.get('detail')}" if g.get("detail") else "")
            )
    else:
        lines.append("Named gaps: none — do not claim datasets are missing.")
    blocking = readiness.get("blocking") if isinstance(readiness.get("blocking"), list) else []
    if blocking:
        lines.append("Blocking critical gaps:")
        for b in blocking[:8]:
            if isinstance(b, dict):
                lines.append(f"- {b.get('datasetKey') or b.get('detail') or b}")
    comp = readiness.get("completeness") if isinstance(readiness.get("completeness"), dict) else {}
    if comp:
        lines.append(
            f"Critical completeness: {comp.get('scorePct')}% "
            f"(required={comp.get('required')} connected={comp.get('connected')} ok={comp.get('ok')})"
        )
    if readiness.get("error"):
        lines.append(f"Error: {readiness['error']}")
    lines.append("You must not provide numeric projections or financial advice when Status is not FRESH.")
    lines.append(
        "When staff ask about missing imports or KPI reliability: name exact datasetKey values "
        "from Named gaps; say optional gaps do not fail the money-read gate; never invent dollars."
    )
    lines.append("[END_IMPORT_CONTEXT]")
    return "\n".join(lines)


def try_import_gap_reply(query: str, readiness: dict[str, Any] | None) -> dict[str, str] | None:
    """Deterministic import-gap answers — name live dataset keys, no generic checklists."""
    raw = str(query or "").strip()
    if not raw:
        return None
    q = re.sub(r"^hal[,:]\s+", "", raw, flags=re.IGNORECASE).lower().strip()
    if not re.search(
        r"\b("
        r"missing\s+import|import\s+datasets?\s+missing|datasets?\s+missing|"
        r"missing\s+datasets?|import\s+health|why\s+.*\bmissing\b|"
        r"kpi[s]?\s+(are\s+)?reliable|reliable\s+kpi|widgets?\s+empty|"
        r"which\s+(?:import\s+)?datasets?\s+(?:are\s+)?missing|"
        r"which\s+imports?\s+(?:are\s+)?missing|"
        r"address\s+the\s+issue\s+of\s+.*\bmissing\b"
        r")\b",
        q,
    ):
        return None

    ready = readiness if isinstance(readiness, dict) else {}
    gaps = [g for g in (ready.get("datasetGaps") or []) if isinstance(g, dict)]
    summary = ready.get("summary") if isinstance(ready.get("summary"), dict) else {}
    comp = ready.get("completeness") if isinstance(ready.get("completeness"), dict) else {}
    level = str(ready.get("level") or "unknown")

    if not gaps:
        text = (
            f"No named import gaps right now (readiness {level}). "
            f"Connected={summary.get('connected')} missing={summary.get('missing') or 0}. "
            "Critical completeness is fine — do not treat old sync log 'missing=4' lines as current."
        )
        if comp.get("ok") is True:
            text += " Money-read KPIs are not blocked."
        return {"text": text, "intent": "import:gaps-none"}

    critical = [g for g in gaps if str(g.get("severity") or "") == "critical"]
    warning = [g for g in gaps if str(g.get("severity") or "") == "warning"]
    optional = [g for g in gaps if str(g.get("severity") or "") == "optional"]

    def _fmt(items: list[dict[str, Any]]) -> str:
        return ", ".join(
            f"{g.get('datasetKey')} ({g.get('status')})" for g in items if g.get("datasetKey")
        )

    parts: list[str] = []
    parts.append(
        f"Live import gaps ({len(gaps)}): "
        + "; ".join(
            f"{g.get('datasetKey')} [{g.get('severity')}/{g.get('status')}]" for g in gaps[:12]
        )
        + "."
    )
    if critical:
        parts.append(f"Critical (blocks money reads until fixed): {_fmt(critical)}.")
    else:
        parts.append("No critical gaps — money-read completeness is not failed by these.")
    if warning:
        parts.append(f"Warning (honesty chips only): {_fmt(warning)}.")
    if optional:
        parts.append(
            f"Optional (widgets stay empty — not $0): {_fmt(optional)}. "
            "Drop matching CSV/JSON into the QuickBooks/SoftDent import inbox and sync."
        )
    if optional and not critical:
        # Concrete file hints for known optional QB gaps
        hints: list[str] = []
        keys = {str(g.get("datasetKey") or "") for g in optional}
        if "quickbooks.payroll" in keys:
            hints.append("quickbooks_payroll.csv (or payroll_detail.csv)")
        if "quickbooks.ap" in keys:
            hints.append("quickbooks_ap.csv (or unpaid_bills.csv)")
        if hints:
            parts.append("Expected filenames: " + "; ".join(hints) + ".")
    parts.append(
        "Ignore stale Jul-log 'missing=4' narratives unless those counts match live Named gaps."
    )
    return {"text": " ".join(parts), "intent": "import:gaps-named"}


def is_financial_query(query: str) -> bool:
    q = str(query or "")
    return classify_financial_query(q) or bool(FINANCIAL_OBFUSCATION.search(q))


def classify_query_intent(query: str) -> str:
    q = str(query or "")
    clinical = bool(_CLINICAL_PATTERN.search(q))
    insurance_ops = bool(_INSURANCE_OPS_PATTERN.search(q))
    # Prefer insurance_ops when the ask is payer/fee/phone/claim ops without chart work.
    if insurance_ops and not clinical:
        return "insurance_ops"
    if clinical and insurance_ops and not re.search(
        r"(?i)\b(tooth|quadrant|chart(?:ing)?|probing|radiograph|periapical|bitewing|"
        r"draft|write|prepare|clinical\s*note|treatment\s*plan)\b",
        q,
    ):
        # e.g. "Delta denial code 16 on D2740" — ops/tools, not clinical charting
        return "insurance_ops"
    if clinical:
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
    # Insurance ops: tool-first on reason21b (or chat8b for short phone/fee lookups).
    if intent == "insurance_ops":
        if len(q) < 100 and re.search(
            r"(?i)\b(phone|tel|allowed|fee\s*schedule|D\d{4}|payer\s*id|routing)\b",
            q,
        ):
            return "chat8b"
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
    return {"lane": key, "model": APPROVED_LOCAL_MODEL}


def is_approved_local_model(model: str | None) -> bool:
    return str(model or "").strip().lower() == APPROVED_LOCAL_MODEL.lower()


def enforce_approved_local_model(
    model: str | None = None,
    *,
    override_header: str | None = None,
    allow_missing: bool = True,
) -> dict[str, Any]:
    """Hard allowlist: only hal-local:30b-a3b (MoE) may run on the office GPU.

    Explicit payload.model / X-HAL-Model-Override that name another model → reject.
    Missing override → force APPROVED_LOCAL_MODEL.
    """
    explicit = str(model or "").strip()
    header = str(override_header or "").strip()
    # Header historically carried a *lane* id (e.g. chat8b); treat known lanes as non-model.
    if header and header.lower() not in LANE_MODELS and ":" in header:
        if not is_approved_local_model(header):
            return {
                "ok": False,
                "error": "model_not_allowed",
                "approvedModel": APPROVED_LOCAL_MODEL,
                "requestedModel": header,
                "source": "X-HAL-Model-Override",
            }
    if explicit:
        if not is_approved_local_model(explicit):
            return {
                "ok": False,
                "error": "model_not_allowed",
                "approvedModel": APPROVED_LOCAL_MODEL,
                "requestedModel": explicit,
                "source": "payload.model",
            }
        return {"ok": True, "model": APPROVED_LOCAL_MODEL}
    if not allow_missing:
        return {
            "ok": False,
            "error": "model_not_allowed",
            "approvedModel": APPROVED_LOCAL_MODEL,
            "requestedModel": "",
        }
    return {"ok": True, "model": APPROVED_LOCAL_MODEL}


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
    if intent in ("analytical", "insurance_ops"):
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


def system_prompt_has_fee_guidance(system_prompt: str) -> bool:
    return _FEE_GUIDANCE_MARKER in str(system_prompt or "")


def compile_fee_guidance(query: str, system_prompt: str = "", *, limit: int = _DEFAULT_FEE_LIMIT) -> str:
    """Inject office fee-schedule CDT amounts when the query asks for fees/allowed."""
    if system_prompt_has_fee_guidance(system_prompt):
        return ""
    try:
        from fee_schedule_store import format_fee_hits, lookup_fees, query_wants_fee_lookup
    except ImportError:
        return ""
    if not query_wants_fee_lookup(str(query or "")):
        return ""
    hits = lookup_fees(str(query or ""), limit=max(1, int(limit)))
    return format_fee_hits(hits)


def compile_eligibility_context(query: str, system_prompt: str = "", *, limit: int = _DEFAULT_ELIGIBILITY_LIMIT) -> str:
    """Inject fresh PHI-redacted eligibility snapshots only when the query asks for benefits."""
    if _ELIGIBILITY_GUIDANCE_MARKER in str(system_prompt or ""):
        return ""
    try:
        from eligibility_cache_store import (
            format_eligibility_hits,
            query_wants_eligibility,
            search_eligibility_cache,
        )
    except ImportError:
        return ""
    if not query_wants_eligibility(str(query or "")):
        return ""
    hits = search_eligibility_cache(str(query or ""), limit=max(1, int(limit)))
    return format_eligibility_hits(hits)


def _load_inbox_claim_rows(*, limit: int = 20) -> list[dict[str, Any]]:
    """Best-effort load of SoftDent claims export rows for claim↔payer join."""
    try:
        from import_loader import softdent_import_dir
    except ImportError:
        return []
    import csv

    dest = softdent_import_dir()
    for name in ("softdent_claims_export.csv", "claims_export.csv"):
        path = dest / name
        if not path.is_file():
            continue
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = [dict(row) for row in csv.DictReader(handle) if row]
        except OSError:
            return []
        out: list[dict[str, Any]] = []
        for row in rows[: max(1, int(limit))]:
            out.append(
                {
                    "id": row.get("ClaimId") or row.get("claimId") or row.get("id") or "",
                    "payer": row.get("Payer") or row.get("payer") or "",
                    "status": row.get("ClaimStatus") or row.get("status") or "",
                    "procedure": row.get("Procedure") or row.get("procedure") or "",
                    "patient": row.get("PatientName") or row.get("patient") or "",
                }
            )
        return out
    return []


def query_wants_claim_payer_join(query: str) -> bool:
    q = str(query or "")
    if not _CLAIM_SCOPED_RE.search(q):
        return False
    return bool(
        re.search(
            r"\b(payer|carrier|insurance|insco|join|phone|elig|denial|appeal|denied|ready|review)\b",
            q,
            re.I,
        )
        or classify_query_intent(q) == "insurance_ops"
    )


def compile_claim_payer_guidance(
    query: str, system_prompt: str = "", *, limit: int = _DEFAULT_CLAIM_JOIN_LIMIT
) -> str:
    """Inject claim-row → office payer reference joins for claim-scoped asks."""
    if _CLAIM_PAYER_GUIDANCE_MARKER in str(system_prompt or ""):
        return ""
    if not query_wants_claim_payer_join(str(query or "")):
        return ""
    try:
        from payer_reference_store import format_claim_payer_joins
    except ImportError:
        return ""
    rows = _load_inbox_claim_rows(limit=max(4, int(limit) * 2))
    if not rows:
        return ""
    text = format_claim_payer_joins(rows)
    if text:
        return text
    # Still useful: surface generic-Insurance honesty when join finds nothing
    generic = sum(
        1
        for r in rows
        if str(r.get("payer") or "").strip().lower() in {"", "insurance", "unknown", "n/a", "-", "—"}
    )
    if generic:
        return (
            "Claim ↔ payer reference joins (routing hints — verify card/InsCo before submit):\n"
            f"- {generic} claim(s) in the SoftDent claims import have generic/missing Payer labels "
            "(e.g. 'Insurance') — SoftDent claims export / ODBC with real Payer is required for join."
        )
    return ""


def build_chat_messages(
    *,
    query: str,
    readiness: dict[str, Any],
    system_prompt: str = "",
    messages: list[dict[str, Any]] | None = None,
    memory_limit: int = _DEFAULT_MEMORY_LIMIT,
    payer_limit: int = _DEFAULT_PAYER_LIMIT,
    fee_limit: int = _DEFAULT_FEE_LIMIT,
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
    fee_guidance = compile_fee_guidance(query, system_prompt, limit=fee_limit)
    if fee_guidance:
        chat_messages.append({"role": "system", "content": fee_guidance})
    eligibility_guidance = compile_eligibility_context(query, system_prompt, limit=eligibility_limit)
    if eligibility_guidance:
        chat_messages.append({"role": "system", "content": eligibility_guidance})
    claim_payer_guidance = compile_claim_payer_guidance(query, system_prompt)
    if claim_payer_guidance:
        chat_messages.append({"role": "system", "content": claim_payer_guidance})
    try:
        ledger_filters = _extract_account_tx_query_filters(query)
        if ledger_filters is not None:
            from softdent_transaction_extract import format_account_transactions_hal_reply

            ledger = query_account_transactions(**ledger_filters)
            ledger_text = format_account_transactions_hal_reply(ledger)
            if ledger_text:
                chat_messages.append(
                    {
                        "role": "system",
                        "content": "SOFTDENT ACCOUNT TX LEDGER (parsed TXN Excel; empty != $0):\n"
                        + ledger_text,
                    }
                )
    except Exception:
        pass
    try:
        from softdent_signon import compile_softdent_signon_guidance

        signon_guidance = compile_softdent_signon_guidance(query, system_prompt)
        if signon_guidance:
            chat_messages.append({"role": "system", "content": signon_guidance})
    except ImportError:
        pass
    if level != "fresh":
        chat_messages.append({"role": "system", "content": build_import_readiness_context(readiness)})
        if soft_stale and intent in ("analytical", "clinical", "insurance_ops"):
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
    format: Any | None = None,
):
    """Yield SSE frames: meta event first, then token data events."""
    yield f"event: meta\ndata: {json.dumps({'lane': lane, 'model': model, 'done': False})}\n\n"
    payload: dict[str, Any] = {"model": model, "messages": messages, "stream": True}
    think = _ollama_think_flag(model)
    if think is not None:
        payload["think"] = think
    if options:
        payload["options"] = options
    if format is not None:
        payload["format"] = format
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
    # hal-local:* Qwen3 aliases — must disable think or content stays empty.
    if (
        name.startswith("hal-escalate")
        or name.startswith("hal-local")
        or name.startswith("qwen3:")
    ):
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
    timeout: float = 180.0,
    keep_alive: int | str | None = None,
    format: Any | None = None,
) -> dict[str, Any]:
    gate = enforce_approved_local_model(model)
    if not gate.get("ok"):
        return {
            "ok": False,
            "error": "model_not_allowed",
            "detail": f"only {APPROVED_LOCAL_MODEL} is permitted",
            "approvedModel": APPROVED_LOCAL_MODEL,
            "requestedModel": str(model or ""),
        }
    model = APPROVED_LOCAL_MODEL
    payload: dict[str, Any] = {"model": model, "messages": messages, "stream": bool(stream)}
    think = _ollama_think_flag(model)
    if think is not None:
        payload["think"] = think
    if options:
        payload["options"] = options
    if format is not None:
        payload["format"] = format
    # REC-007 HAL keep-alive: default forever (-1) so MoE stays GPU-resident.
    if keep_alive is None:
        raw = str(os.environ.get("NR2_OLLAMA_KEEP_ALIVE") or "-1").strip()
        if raw.lstrip("-").isdigit():
            keep_alive = int(raw)
        elif raw:
            keep_alive = raw
        else:
            keep_alive = -1
    payload["keep_alive"] = keep_alive
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
                    # Content only — ignore thinking deltas (R1 often streams think-only).
                    delta = str((obj.get("message") or {}).get("content") or "")
                    if delta:
                        chunks.append(delta)
                full = "".join(chunks)
                return {"ok": True, "body": {"message": {"content": full}}, "streamed": True}
            body = json.loads(resp.read().decode("utf-8"))
            message = body.get("message") or {}
            # Normalize: never leave thinking-only payloads as if they were answers.
            text = extract_ollama_message_text(message)
            body = dict(body)
            body["message"] = dict(message)
            body["message"]["content"] = text
            # Preserve raw thinking length for diagnostics (never staff-facing).
            thinking_len = len(str(message.get("thinking") or ""))
            return {
                "ok": True,
                "body": body,
                "diag": {
                    "contentChars": len(text),
                    "thinkingChars": thinking_len,
                    "thinkFlag": think,
                    "stream": False,
                },
            }
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
    model_gate = enforce_approved_local_model(model)
    if not model_gate.get("ok"):
        return {
            "ok": False,
            "error": "model_not_allowed",
            "approvedModel": APPROVED_LOCAL_MODEL,
            "requestedModel": model_gate.get("requestedModel"),
            "resolvedLane": resolved["lane"],
            "blocked": True,
        }
    model = APPROVED_LOCAL_MODEL
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

    import_gap = try_import_gap_reply(query, readiness)
    if import_gap:
        text = import_gap["text"]
        append_lane_history(
            store,
            lane="local",
            model="import-gaps",
            query=query,
            intent=import_gap.get("intent", "import:gaps"),
        )
        return {
            "ok": True,
            "text": text,
            "message": {"content": text},
            "model": "local-import-gaps",
            "readinessLevel": level,
            "intent": import_gap.get("intent", "import:gaps"),
            "softStale": soft_stale,
            "resolvedLane": "local",
            "routingReason": "import_gap_policy",
            "streamed": False,
        }

    chat_messages, intent, soft_stale, level = build_chat_messages(
        query=query,
        readiness=readiness,
        system_prompt=system_prompt,
        messages=messages,
    )

    chat_messages = inject_deliverable_messages(chat_messages, query)
    opts = options_for_query(query, options)
    fmt = _DELIVERABLE_JSON_SCHEMA if is_deliverable_request(query) else None
    result = call_ollama_chat(
        model=model, messages=chat_messages, stream=True, options=opts, format=fmt
    )
    if not result.get("ok"):
        return {
            "ok": False,
            "error": result.get("error"),
            "detail": result.get("detail"),
            "resolvedLane": resolved["lane"],
        }

    body = result.get("body") or {}
    text = extract_ollama_message_text(body.get("message") or {}, query=query)
    if level != "fresh" and intent == "transactional":
        text = redact_financial_numbers(text)
    elif level != "fresh" and soft_stale and intent in ("analytical", "clinical", "insurance_ops"):
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
    model_gate = enforce_approved_local_model(model)
    if not model_gate.get("ok"):
        yield f"event: error\ndata: {json.dumps({'error': 'model_not_allowed', 'approvedModel': APPROVED_LOCAL_MODEL, 'requestedModel': model_gate.get('requestedModel'), 'done': True})}\n\n"
        return
    model = APPROVED_LOCAL_MODEL

    if financial and level != "fresh" and (intent == "transactional" or not soft_stale):
        yield f"event: error\ndata: {json.dumps({'error': 'HAL_UNAVAILABLE_STALE_DATA', 'blocked': True, 'done': True})}\n\n"
        return

    # Phase 3 TTFT: emit typing meta before local policy / Ollama so clients can paint immediately.
    yield f"event: meta\ndata: {json.dumps({'lane': resolved['lane'], 'model': model, 'done': False, 'status': 'typing', 'ttft': True})}\n\n"

    local = try_local_policy_reply(query)
    if local:
        text = local["text"]
        append_lane_history(store, lane="local", model="policy", query=query, intent=local.get("intent", "local:policy"))
        yield f"event: meta\ndata: {json.dumps({'lane': 'local', 'model': 'local-policy', 'done': False})}\n\n"
        yield f"data: {json.dumps({'token': text, 'done': False})}\n\n"
        yield f"data: {json.dumps({'token': '', 'done': True})}\n\n"
        return

    import_gap = try_import_gap_reply(query, readiness)
    if import_gap:
        text = import_gap["text"]
        append_lane_history(
            store,
            lane="local",
            model="import-gaps",
            query=query,
            intent=import_gap.get("intent", "import:gaps"),
        )
        yield f"event: meta\ndata: {json.dumps({'lane': 'local', 'model': 'local-import-gaps', 'done': False})}\n\n"
        yield f"data: {json.dumps({'token': text, 'done': False})}\n\n"
        yield f"data: {json.dumps({'token': '', 'done': True})}\n\n"
        return

    chat_messages, intent, soft_stale, level = build_chat_messages(
        query=query,
        readiness=readiness,
        system_prompt=system_prompt,
        messages=messages,
    )
    # Deliverable asks: aggregate first so JSON→markdown normalize runs before SSE emit.
    if is_deliverable_request(query):
        result = evaluate_query(
            query=query,
            readiness=readiness,
            model=model,
            system_prompt=system_prompt,
            messages=messages,
            options=options,
            shift_context=shift_context,
            requested_lane=requested_lane,
            store=store,
        )
        if not result.get("ok"):
            yield f"event: error\ndata: {json.dumps({'error': result.get('error'), 'done': True})}\n\n"
            return
        text = str(result.get("text") or "")
        yield f"event: meta\ndata: {json.dumps({'lane': result.get('resolvedLane') or resolved['lane'], 'model': result.get('model') or model, 'done': False, 'deliverable': True})}\n\n"
        yield f"data: {json.dumps({'token': text, 'done': False})}\n\n"
        yield f"data: {json.dumps({'token': '', 'done': True})}\n\n"
        return

    append_lane_history(store, lane=resolved["lane"], model=model, query=query, intent=intent)
    yield from iter_ollama_sse_tokens(
        model=model,
        messages=chat_messages,
        lane=resolved["lane"],
        options=options_for_query(query, options),
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
    model_gate = enforce_approved_local_model(model)
    if not model_gate.get("ok"):
        return {
            "ok": False,
            "error": "model_not_allowed",
            "approvedModel": APPROVED_LOCAL_MODEL,
            "requestedModel": model_gate.get("requestedModel"),
            "resolvedLane": resolved["lane"],
            "blocked": True,
        }
    model = APPROVED_LOCAL_MODEL
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

    claims_total = try_live_claims_total_reply(query)
    if claims_total:
        text = claims_total["text"]
        append_lane_history(
            store,
            lane="local",
            model="claims-live",
            query=query,
            intent=claims_total.get("intent", "policy:claims-total-live"),
        )
        return {
            "ok": True,
            "text": text,
            "message": {"content": text},
            "model": "local-claims-live",
            "readinessLevel": level,
            "intent": claims_total.get("intent", "policy:claims-total-live"),
            "softStale": soft_stale,
            "resolvedLane": "local",
            "routingReason": "live_claims_money_gate",
        }

    # Period-close OPS — cite daily_close_log.jsonl only (nr2-12025)
    try:
        from daily_closeout import try_deterministic_period_close_reply

        close_det = try_deterministic_period_close_reply(query)
    except Exception:
        close_det = None
    if close_det and close_det.get("text"):
        text = str(close_det["text"])
        append_lane_history(
            store,
            lane="local",
            model="period-close-ops",
            query=query,
            intent=str(close_det.get("routingReason") or "period_close_status"),
        )
        return {
            "ok": True,
            "text": text,
            "message": {"content": text},
            "model": "period-close-ops",
            "readinessLevel": level,
            "intent": close_det.get("routingReason") or "period_close_status",
            "softStale": soft_stale,
            "resolvedLane": "local",
            "routingReason": close_det.get("routingReason") or "period_close_status",
            "beamHash": close_det.get("beamHash"),
            "periodClose": close_det.get("periodClose"),
        }

    # Money honesty pre-flight — SoftDent AR / QB revenue from live beams (nr2-12019)
    try:
        from hal_brain_tools import try_deterministic_money_reply

        money_det = try_deterministic_money_reply(query)
    except Exception:
        money_det = None
    if money_det and money_det.get("text"):
        text = str(money_det["text"])
        append_lane_history(
            store,
            lane="local",
            model="money-beam-live",
            query=query,
            intent=str(money_det.get("routingReason") or "money_honesty_deterministic"),
        )
        return {
            "ok": True,
            "text": text,
            "message": {"content": text},
            "model": "money-beam-live",
            "readinessLevel": level,
            "intent": money_det.get("routingReason") or "money_honesty_deterministic",
            "softStale": soft_stale,
            "resolvedLane": "local",
            "routingReason": money_det.get("routingReason") or "money_honesty_deterministic",
            "moneyGrounded": True,
            "beamHash": money_det.get("beamHash"),
            "beamTimestamp": money_det.get("beamTimestamp"),
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

    import_gap = try_import_gap_reply(query, readiness)
    if import_gap:
        text = import_gap["text"]
        append_lane_history(
            store, lane="local", model="import-gaps", query=query, intent=import_gap.get("intent", "import:gaps")
        )
        return {
            "ok": True,
            "text": text,
            "message": {"content": text},
            "model": "local-import-gaps",
            "readinessLevel": level,
            "intent": import_gap.get("intent", "import:gaps"),
            "softStale": soft_stale,
            "resolvedLane": "local",
            "routingReason": "import_gap_policy",
        }

    money_sys = system_prompt or ""
    if financial or re.search(r"(?i)\b(claim|claims|revenue|ar\b|dollar|\$)\b", query or ""):
        money_sys = (money_sys + "\n\n" + build_live_claims_money_context()).strip()

    chat_messages, intent, soft_stale, level = build_chat_messages(
        query=query,
        readiness=readiness,
        system_prompt=money_sys,
        messages=messages,
    )

    chat_messages = inject_deliverable_messages(chat_messages, query)
    opts = options_for_query(query, options)
    fmt = _DELIVERABLE_JSON_SCHEMA if is_deliverable_request(query) else None
    # Phase 5: 180s ceiling — analytical reason21b prompts can exceed 60s on Q4_K_M.
    timeout = float(os.environ.get("NR2_OLLAMA_CHAT_TIMEOUT") or "180")
    result = call_ollama_chat(
        model=model,
        messages=chat_messages,
        stream=False,
        options=opts,
        format=fmt,
        timeout=timeout,
    )
    if not result.get("ok"):
        return {
            "ok": False,
            "error": result.get("error"),
            "detail": result.get("detail"),
            "resolvedLane": resolved["lane"],
            "model": model,
            "intent": intent,
            "routingReason": routing_reason or None,
        }

    body = result.get("body") or {}
    message = body.get("message") or {}
    text = extract_ollama_message_text(message, query=query)
    diag = dict(result.get("diag") or {})

    # Qwen3 / think-only race: non-stream sometimes returns empty content — retry once via stream.
    if not str(text or "").strip():
        retry = call_ollama_chat(
            model=model,
            messages=chat_messages,
            stream=True,
            options=opts,
            format=fmt,
            timeout=timeout,
        )
        diag["emptyRetryStream"] = True
        diag["retryOk"] = bool(retry.get("ok"))
        if retry.get("ok"):
            body = retry.get("body") or {}
            message = body.get("message") or {}
            text = extract_ollama_message_text(message, query=query)
            diag["retryContentChars"] = len(str(text or ""))
        else:
            diag["retryError"] = retry.get("error")

    if not str(text or "").strip():
        return {
            "ok": False,
            "error": "empty_response",
            "detail": diag,
            "text": "",
            "message": {"content": ""},
            "model": model,
            "readinessLevel": level,
            "intent": intent,
            "softStale": soft_stale,
            "resolvedLane": resolved["lane"],
            "routingReason": routing_reason or None,
        }

    if level != "fresh" and intent == "transactional":
        text = redact_financial_numbers(text)
    elif level != "fresh" and soft_stale and intent in ("analytical", "clinical", "insurance_ops"):
        if SOFT_STALE_WATERMARK not in text:
            text = f"{SOFT_STALE_WATERMARK}\n\n{text}"
        text = redact_financial_numbers(text)

    money_meta: dict[str, Any] = {}
    try:
        from hal_brain_tools import validate_money_reply

        gate = validate_money_reply(text, query=query)
        if gate.get("rewritten") or gate.get("violation") or gate.get("moneyGrounded"):
            text = str(gate.get("text") or text)
            money_meta = {
                "moneyGrounded": gate.get("moneyGrounded"),
                "beamHash": gate.get("beamHash"),
                "beamTimestamp": gate.get("beamTimestamp"),
                "moneyHonesty": {
                    "grounded": bool(gate.get("moneyGrounded")),
                    "violation": bool(gate.get("violation")),
                    "rewritten": bool(gate.get("rewritten")),
                    "staleBanner": bool(gate.get("staleBanner")),
                },
            }
    except Exception:
        pass

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
        "diag": diag or None,
        **money_meta,
    }
