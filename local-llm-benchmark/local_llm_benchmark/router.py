from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from .config import Settings


class TaskComplexity(str, Enum):
    SIMPLE = "simple"
    COMPLEX = "complex"


@dataclass(frozen=True)
class RouteDecision:
    complexity: TaskComplexity
    model: str
    reason: str


_CODE_FENCE = re.compile(r"```")
_COMPLEX_PATTERNS = (
    re.compile(r"\b(write|implement|debug|refactor|fix)\b.+\b(code|function|class|script)\b", re.I),
    re.compile(r"\b(o\(n|time complexity|space complexity|big[- ]o)\b", re.I),
    re.compile(r"\b(proof|theorem|derive|deduce)\b", re.I),
)
_SIMPLE_PATTERNS = (
    re.compile(r"\b(summarize|summary|classify|classification|categorize|label)\b", re.I),
    re.compile(r"\b(extract|bullet points?|tl;dr|shorten|paraphrase)\b", re.I),
    re.compile(r"\b(sentiment|yes/no|true/false)\b", re.I),
)


def route_prompt(prompt: str, settings: Settings, force: TaskComplexity | None = None) -> RouteDecision:
    if force is not None:
        model = settings.model_fast if force is TaskComplexity.SIMPLE else settings.model_heavy
        return RouteDecision(complexity=force, model=model, reason=f"forced:{force.value}")

    text = (prompt or "").strip()
    lowered = text.lower()

    if _CODE_FENCE.search(text):
        return _decision(TaskComplexity.COMPLEX, settings, "markdown code fence detected")

    for pattern in _COMPLEX_PATTERNS:
        if pattern.search(text):
            return _decision(TaskComplexity.COMPLEX, settings, f"pattern:{pattern.pattern}")

    for pattern in _SIMPLE_PATTERNS:
        if pattern.search(text):
            return _decision(TaskComplexity.SIMPLE, settings, f"pattern:{pattern.pattern}")

    complex_hits = sum(1 for kw in settings.complex_keywords if kw in lowered)
    simple_hits = sum(1 for kw in settings.simple_keywords if kw in lowered)

    if complex_hits > simple_hits and complex_hits > 0:
        return _decision(TaskComplexity.COMPLEX, settings, f"keywords:complex={complex_hits}")

    if simple_hits > 0:
        return _decision(TaskComplexity.SIMPLE, settings, f"keywords:simple={simple_hits}")

    # Long prompts with technical tokens lean heavy; short prompts lean fast.
    if len(text) > 400 or len(re.findall(r"\b(def|class|import|SELECT|async|await)\b", text)) >= 2:
        return _decision(TaskComplexity.COMPLEX, settings, "length_or_technical_tokens")

    return _decision(TaskComplexity.SIMPLE, settings, "default_simple")


def _decision(complexity: TaskComplexity, settings: Settings, reason: str) -> RouteDecision:
    model = settings.model_fast if complexity is TaskComplexity.SIMPLE else settings.model_heavy
    return RouteDecision(complexity=complexity, model=model, reason=reason)
