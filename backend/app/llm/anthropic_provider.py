"""Anthropic Claude adapter (official `anthropic` SDK, streaming).

* Streams with `messages.stream()` and reads the final message for the
  provider-reported token usage.
* Effort (low|medium|high) is set per model tier via `output_config`.
* For claude-opus-5-5 / claude-sonnet-5-5, the server-side refusal fallback
  (`fallbacks="default"`, beta header server-side-fallback-2026-07-01) is on by
  default (ANTHROPIC_SERVER_FALLBACKS=false disables it). If it triggers, the
  final message reports the model that actually answered and we record that.
"""
from __future__ import annotations

from collections.abc import Generator

from app.llm.base import LLMError, LLMProvider, LLMRequest, LLMUsage

_SERVER_FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5"}


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, server_fallbacks: bool = True):
        import anthropic

        self._anthropic = anthropic
        self._client = anthropic.Anthropic(api_key=api_key, max_retries=1)
        self._server_fallbacks = server_fallbacks

    def stream(self, req: LLMRequest) -> Generator[str, None, LLMUsage]:
        a = self._anthropic
        params = dict(model=req.model, max_tokens=req.max_output_tokens, system=req.system,
                      messages=[{"role": "user", "content": req.user}])
        if req.effort:
            params["output_config"] = {"effort": req.effort}
        client = self._client.with_options(timeout=req.timeout_s)
        try:
            if self._server_fallbacks and req.model in _SERVER_FALLBACK_MODELS:
                ctx = client.beta.messages.stream(**params, betas=["server-side-fallback-2026-07-01"],
                                                  fallbacks="default")
            else:
                ctx = client.messages.stream(**params)
            with ctx as stream:
                for text in stream.text_stream:
                    yield text
                final = stream.get_final_message()
        except a.AuthenticationError as e:
            raise LLMError("Anthropic rejected the API key.", "auth_error", retryable=True) from e
        except a.NotFoundError as e:
            raise LLMError(f"Unknown Anthropic model '{req.model}'.", "model_not_found", retryable=True) from e
        except a.RateLimitError as e:
            raise LLMError("Anthropic rate limit reached.", "rate_limited", retryable=True) from e
        except a.BadRequestError as e:
            raise LLMError(f"Anthropic rejected the request: {e.message}"[:300], "bad_request", retryable=True) from e
        except a.APITimeoutError as e:
            raise LLMError("Anthropic request timed out.", "timeout", retryable=True) from e
        except a.APIConnectionError as e:
            raise LLMError("Could not connect to Anthropic.", "connection_error", retryable=True) from e
        except a.APIStatusError as e:
            raise LLMError(f"Anthropic API error {e.status_code}.", "server_error", retryable=True) from e

        if final.stop_reason == "refusal":
            raise LLMError("The model declined this request (refusal).", "refusal", retryable=True)
        u = final.usage
        return LLMUsage(int(u.input_tokens or 0), int(u.output_tokens or 0), "provider",
                        getattr(final, "model", req.model), final.stop_reason)

    def list_models(self) -> list[str]:
        try:
            return [m.id for m in self._client.models.list()]
        except Exception:
            return []
