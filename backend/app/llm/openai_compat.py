"""OpenAI-compatible adapter (works with OpenAI, Ollama, LM Studio, vLLM, OpenRouter, Groq ...).

Uses the official `openai` SDK with a custom base_url. Usage is requested with
stream_options.include_usage; servers that don't support it fall back to
labelled *estimated* tokens.
"""
from __future__ import annotations

from collections.abc import Generator

from app.llm.base import LLMError, LLMProvider, LLMRequest, LLMUsage, estimate_tokens


class OpenAICompatProvider(LLMProvider):
    name = "openai_compatible"

    def __init__(self, base_url: str, api_key: str):
        import openai

        self._openai = openai
        self._client = openai.OpenAI(base_url=base_url, api_key=api_key or "not-needed", max_retries=1)

    def stream(self, req: LLMRequest) -> Generator[str, None, LLMUsage]:
        o = self._openai
        parts: list[str] = []
        usage = None
        try:
            resp = self._client.with_options(timeout=req.timeout_s).chat.completions.create(
                model=req.model, max_tokens=req.max_output_tokens, stream=True,
                stream_options={"include_usage": True},
                messages=[{"role": "system", "content": req.system}, {"role": "user", "content": req.user}],
            )
            for chunk in resp:
                if getattr(chunk, "usage", None):
                    usage = chunk.usage
                for choice in chunk.choices or []:
                    delta = choice.delta.content if choice.delta else None
                    if delta:
                        parts.append(delta)
                        yield delta
        except o.AuthenticationError as e:
            raise LLMError("The OpenAI-compatible server rejected the API key.", "auth_error") from e
        except o.NotFoundError as e:
            raise LLMError(f"Model '{req.model}' not found on the OpenAI-compatible server.", "model_not_found") from e
        except o.RateLimitError as e:
            raise LLMError("OpenAI-compatible rate limit reached.", "rate_limited") from e
        except o.APITimeoutError as e:
            raise LLMError("OpenAI-compatible request timed out.", "timeout") from e
        except o.APIConnectionError as e:
            raise LLMError("Could not connect to the OpenAI-compatible server.", "connection_error") from e
        except o.APIStatusError as e:
            raise LLMError(f"OpenAI-compatible API error {e.status_code}.", "server_error") from e

        if usage is not None and getattr(usage, "prompt_tokens", None) is not None:
            return LLMUsage(int(usage.prompt_tokens), int(usage.completion_tokens or 0), "provider", req.model, None)
        return LLMUsage(estimate_tokens(req.system + req.user), estimate_tokens("".join(parts)), "estimated",
                        req.model, None)

    def list_models(self) -> list[str]:
        try:
            return [m.id for m in self._client.models.list()]
        except Exception:
            return []
