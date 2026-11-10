"""Provider adapters tested with fake SDK clients - no network, no paid calls."""
from types import SimpleNamespace

import pytest

from app.llm.base import LLMError, LLMRequest, drain
from app.llm.mock import MOCK_BANNER, MockProvider

REQ = LLMRequest(model="m", system="sys", user="QUESTION: hi", max_output_tokens=100, timeout_s=5)


def test_mock_provider_is_labelled_and_extractive():
    req = LLMRequest(model="mock-small", system="s", user="QUESTION: refund window?",
                     mock_context=[{"index": 1, "text": "The refund window is 30 days from purchase."}])
    text, usage = drain(MockProvider().stream(req))
    assert text.startswith(MOCK_BANNER) and "30 days" in text and "[1]" in text
    assert usage.source == "mock"


class _FakeAnthropicStream:
    def __init__(self, final):
        self.final, self.text_stream = final, iter(["Hello ", "world"])

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self.final


def _anthropic(final, captured):
    from app.llm.anthropic_provider import AnthropicProvider

    p = AnthropicProvider.__new__(AnthropicProvider)
    import anthropic
    p._anthropic, p._server_fallbacks = anthropic, True

    class Msgs:
        def stream(self, **kw):
            captured.update(kw)
            return _FakeAnthropicStream(final)

    client = SimpleNamespace(messages=Msgs(), beta=SimpleNamespace(messages=Msgs()))
    p._client = SimpleNamespace(with_options=lambda **kw: client)
    return p


def test_anthropic_adapter_reports_provider_usage():
    final = SimpleNamespace(stop_reason="end_turn", model="claude-haiku-5-5",
                            usage=SimpleNamespace(input_tokens=120, output_tokens=7))
    captured = {}
    text, usage = drain(_anthropic(final, captured).stream(LLMRequest(
        model="claude-haiku-5-5", system="s", user="u", effort="low")))
    assert text == "Hello world"
    assert (usage.input_tokens, usage.output_tokens, usage.source) == (120, 7, "provider")
    assert captured["output_config"] == {"effort": "low"} and "fallbacks" not in captured


def test_anthropic_server_fallbacks_on_opus():
    final = SimpleNamespace(stop_reason="end_turn", model="claude-opus-5-5",
                            usage=SimpleNamespace(input_tokens=1, output_tokens=1))
    captured = {}
    drain(_anthropic(final, captured).stream(LLMRequest(model="claude-opus-5-5", system="s", user="u")))
    assert captured["fallbacks"] == "default" and captured["betas"] == ["server-side-fallback-2026-07-01"]


def test_anthropic_refusal_becomes_llm_error():
    final = SimpleNamespace(stop_reason="refusal", model="x", usage=SimpleNamespace(input_tokens=1, output_tokens=0))
    with pytest.raises(LLMError) as e:
        drain(_anthropic(final, {}).stream(REQ))
    assert e.value.kind == "refusal"


def test_openai_compatible_adapter_usage_and_estimate():
    from app.llm.openai_compat import OpenAICompatProvider

    def chunks(with_usage):
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="Hi"))], usage=None)
        yield SimpleNamespace(choices=[], usage=SimpleNamespace(prompt_tokens=50, completion_tokens=2) if with_usage else None)

    for with_usage, source in ((True, "provider"), (False, "estimated")):
        p = OpenAICompatProvider.__new__(OpenAICompatProvider)
        import openai
        p._openai = openai
        completions = SimpleNamespace(create=lambda **kw: chunks(with_usage))
        p._client = SimpleNamespace(with_options=lambda **kw: SimpleNamespace(chat=SimpleNamespace(completions=completions)))
        text, usage = drain(p.stream(REQ))
        assert text == "Hi" and usage.source == source


def test_gemini_adapter_usage():
    from app.llm.gemini_provider import GeminiProvider

    meta = SimpleNamespace(prompt_token_count=30, candidates_token_count=5, thoughts_token_count=3)
    stream = [SimpleNamespace(text="Ok", usage_metadata=None), SimpleNamespace(text="", usage_metadata=meta)]
    p = GeminiProvider.__new__(GeminiProvider)
    p._client = SimpleNamespace(models=SimpleNamespace(generate_content_stream=lambda **kw: iter(stream)))
    text, usage = drain(p.stream(REQ))
    assert text == "Ok" and (usage.input_tokens, usage.output_tokens, usage.source) == (30, 8, "provider")


def test_registry_refuses_unconfigured_provider(env):
    with pytest.raises(KeyError):
        env.registry.provider("anthropic")
