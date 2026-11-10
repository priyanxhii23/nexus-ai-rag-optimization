"""Provider-independent LLM interface.

Every adapter implements `stream()`, which yields text pieces as they arrive
and finally returns an `LLMUsage`. `generate()` is built on top of it, so each
provider has exactly one code path to maintain.
"""
from __future__ import annotations

import time
from collections.abc import Generator, Iterator
from dataclasses import dataclass, field


@dataclass
class LLMRequest:
    model: str                      # provider-side model name, e.g. "claude-haiku-5-5"
    system: str
    user: str
    max_output_tokens: int = 8192
    timeout_s: float = 60.0
    effort: str | None = None       # Claude effort level (low|medium|high...), ignored elsewhere
    # extra data only the mock provider uses to produce an honest extractive answer
    mock_context: list[dict] = field(default_factory=list)


@dataclass
class LLMUsage:
    input_tokens: int
    output_tokens: int
    source: str                    # "provider" (reported by the API) | "estimated" | "mock"
    served_model: str | None = None
    stop_reason: str | None = None


@dataclass
class LLMResult:
    text: str
    usage: LLMUsage
    latency_ms: float
    is_mock: bool


class LLMError(Exception):
    """Raised by adapters; `retryable` tells the router whether a fallback makes sense."""

    def __init__(self, message: str, kind: str = "provider_error", retryable: bool = True):
        super().__init__(message)
        self.kind, self.retryable = kind, retryable


def estimate_tokens(text: str) -> int:
    """Rough estimate (~4 characters per token for English). Used ONLY when a provider
    does not report usage; such numbers are always labelled 'estimated'."""
    return max(1, round(len(text) / 4))


class LLMProvider:
    name: str = "base"
    is_mock: bool = False

    def stream(self, req: LLMRequest) -> Generator[str, None, LLMUsage]:  # pragma: no cover - interface
        raise NotImplementedError
        yield ""

    def generate(self, req: LLMRequest) -> LLMResult:
        t0 = time.perf_counter()
        parts: list[str] = []
        gen = self.stream(req)
        try:
            while True:
                parts.append(next(gen))
        except StopIteration as stop:
            usage = stop.value
        return LLMResult("".join(parts), usage, (time.perf_counter() - t0) * 1000, self.is_mock)

    def list_models(self) -> list[str]:
        return []


def drain(gen: Iterator[str]) -> tuple[str, LLMUsage]:
    parts: list[str] = []
    try:
        while True:
            parts.append(next(gen))
    except StopIteration as stop:
        return "".join(parts), stop.value
