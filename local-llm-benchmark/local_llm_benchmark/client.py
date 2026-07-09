from __future__ import annotations

import time
from dataclasses import asdict, dataclass

from openai import OpenAI

from .config import Settings
from .router import RouteDecision, route_prompt
from .server import ensure_server_ready


@dataclass(frozen=True)
class BenchmarkResult:
    model: str
    prompt: str
    route_reason: str
    complexity: str
    ttft_ms: float | None
    generation_ms: float
    total_ms: float
    output_tokens: int
    tokens_per_second: float | None
    response_preview: str
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _estimate_tokens(text: str) -> int:
  # OpenAI-compatible servers may not return usage during streaming.
  # Whitespace split is a stable fallback for relative throughput comparisons.
    if not text:
        return 0
    return max(1, len(text.split()))


class LocalLLMClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = OpenAI(base_url=settings.base_url, api_key=settings.api_key)

    def chat(self, prompt: str, model: str | None = None, *, stream: bool = True) -> str:
        chosen = model or self.settings.model_fast
        if stream:
            return self._chat_stream(prompt, chosen)
        response = self._client.chat.completions.create(
            model=chosen,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self.settings.max_tokens,
            temperature=self.settings.temperature,
            stream=False,
        )
        return (response.choices[0].message.content or "").strip()

    def _chat_stream(self, prompt: str, model: str) -> str:
        chunks: list[str] = []
        stream = self._client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self.settings.max_tokens,
            temperature=self.settings.temperature,
            stream=True,
        )
        for event in stream:
            delta = event.choices[0].delta.content if event.choices else None
            if delta:
                chunks.append(delta)
        return "".join(chunks).strip()

    def benchmark(
        self,
        prompt: str,
        *,
        model: str | None = None,
        route_reason: str = "manual",
        complexity: str = "manual",
    ) -> BenchmarkResult:
        chosen = model or self.settings.model_fast
        start = time.perf_counter()
        ttft_ms: float | None = None
        parts: list[str] = []

        try:
            stream = self._client.chat.completions.create(
                model=chosen,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.settings.max_tokens,
                temperature=self.settings.temperature,
                stream=True,
            )
            for event in stream:
                delta = event.choices[0].delta.content if event.choices else None
                if not delta:
                    continue
                if ttft_ms is None:
                    ttft_ms = (time.perf_counter() - start) * 1000
                parts.append(delta)
        except Exception as exc:  # noqa: BLE001 - surface provider errors to caller
            total_ms = (time.perf_counter() - start) * 1000
            return BenchmarkResult(
                model=chosen,
                prompt=prompt,
                route_reason=route_reason,
                complexity=complexity,
                ttft_ms=ttft_ms,
                generation_ms=total_ms,
                total_ms=total_ms,
                output_tokens=0,
                tokens_per_second=None,
                response_preview="",
                error=str(exc),
            )

        total_ms = (time.perf_counter() - start) * 1000
        text = "".join(parts)
        output_tokens = _estimate_tokens(text)
        generation_ms = total_ms - (ttft_ms or 0)
        tps = None
        if output_tokens > 0 and generation_ms > 0:
            tps = output_tokens / (generation_ms / 1000)

        return BenchmarkResult(
            model=chosen,
            prompt=prompt,
            route_reason=route_reason,
            complexity=complexity,
            ttft_ms=ttft_ms,
            generation_ms=generation_ms,
            total_ms=total_ms,
            output_tokens=output_tokens,
            tokens_per_second=tps,
            response_preview=text[:240],
        )

    def routed_chat(self, prompt: str) -> tuple[str, RouteDecision]:
        decision = route_prompt(prompt, self.settings)
        text = self.chat(prompt, model=decision.model, stream=True)
        return text, decision

    def routed_benchmark(self, prompt: str) -> BenchmarkResult:
        decision = route_prompt(prompt, self.settings)
        return self.benchmark(
            prompt,
            model=decision.model,
            route_reason=decision.reason,
            complexity=decision.complexity.value,
        )


def run_benchmark_suite(settings: Settings) -> list[BenchmarkResult]:
    ensure_server_ready(settings, [settings.model_fast, settings.model_heavy])
    client = LocalLLMClient(settings)

    # Warmup reduces cold-start skew for the fast model.
    client.benchmark(settings.warmup_prompt, model=settings.model_fast, route_reason="warmup", complexity="warmup")

    simple_prompt = "Summarize in two sentences: Local LLMs run on your workstation GPU without sending prompts to the cloud."
    complex_prompt = (
        "Write a Python function that computes the longest increasing subsequence in O(n log n) time. "
        "Include a short explanation of the approach."
    )

    return [
        client.benchmark(simple_prompt, model=settings.model_fast, route_reason="suite:simple", complexity="simple"),
        client.benchmark(complex_prompt, model=settings.model_heavy, route_reason="suite:complex", complexity="complex"),
        client.routed_benchmark(simple_prompt),
        client.routed_benchmark(complex_prompt),
    ]
