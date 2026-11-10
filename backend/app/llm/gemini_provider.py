"""Google Gemini adapter (official `google-genai` SDK, streaming).

Token usage comes from `usage_metadata` on the streamed chunks
(prompt_token_count / candidates_token_count + thoughts_token_count, which
Google bills as output).
"""
from __future__ import annotations

from collections.abc import Generator

from app.llm.base import LLMError, LLMProvider, LLMRequest, LLMUsage, estimate_tokens


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str):
        from google import genai

        self._genai = genai
        self._client = genai.Client(api_key=api_key)

    def stream(self, req: LLMRequest) -> Generator[str, None, LLMUsage]:
        from google.genai import errors, types

        config = types.GenerateContentConfig(
            system_instruction=req.system,
            max_output_tokens=req.max_output_tokens,
            http_options=types.HttpOptions(timeout=int(req.timeout_s * 1000)),
        )
        parts: list[str] = []
        usage = None
        try:
            for chunk in self._client.models.generate_content_stream(model=req.model, contents=req.user, config=config):
                if chunk.usage_metadata is not None:
                    usage = chunk.usage_metadata
                text = chunk.text or ""
                if text:
                    parts.append(text)
                    yield text
        except errors.ClientError as e:
            code = getattr(e, "code", 400)
            kind = {401: "auth_error", 403: "auth_error", 404: "model_not_found", 429: "rate_limited"}.get(code, "bad_request")
            raise LLMError(f"Gemini rejected the request ({code}).", kind, retryable=True) from e
        except errors.ServerError as e:
            raise LLMError("Gemini server error.", "server_error", retryable=True) from e
        except Exception as e:  # network errors from the HTTP layer
            raise LLMError(f"Gemini call failed: {type(e).__name__}", "connection_error", retryable=True) from e

        if usage is not None and usage.prompt_token_count is not None:
            out = (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)
            return LLMUsage(int(usage.prompt_token_count), int(out), "provider", req.model, None)
        return LLMUsage(estimate_tokens(req.system + req.user), estimate_tokens("".join(parts)), "estimated",
                        req.model, None)

    def list_models(self) -> list[str]:
        try:
            names = []
            for m in self._client.models.list():
                actions = getattr(m, "supported_actions", None) or []
                if not actions or "generateContent" in actions:
                    names.append(m.name.removeprefix("models/"))
            return names
        except Exception:
            return []
