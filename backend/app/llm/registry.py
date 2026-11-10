"""Model catalog, provider construction, availability and cost calculation.

PRICING RULES (never fabricated):
* Claude prices: Anthropic first-party API list prices as published in
  Anthropic's API reference (cached 2026-10-06). Editable in Settings.
* Gemini / OpenAI-compatible prices: NOT pre-filled. Until you enter them
  (Settings page or .env), costs for those models are reported as "unpriced".
* Mock models: cost is "simulated" using the list price of the real model
  they stand in for, so test runs show realistic *relative* costs. Simulated
  costs are always labelled as such and never counted as real spend.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.llm.base import LLMProvider
from app.llm.mock import MockProvider
from app.models import ModelConfig

ANTHROPIC_PRICE_SOURCE = "Anthropic API list price (Claude API reference, cached 2026-10-06)"

CLAUDE_CATALOG = [
    dict(model_name="claude-haiku-5-5", display_name="Claude Haiku 5.5", tier="small",
         input_price_per_mtok=0.10, output_price_per_mtok=0.50, long_context_threshold=100_000,
         long_input_price_per_mtok=0.50, long_output_price_per_mtok=2.50, effort="low"),
    dict(model_name="claude-sonnet-5-5", display_name="Claude Sonnet 5.5", tier="medium",
         input_price_per_mtok=2.00, output_price_per_mtok=10.00, effort="medium"),
    dict(model_name="claude-opus-5-5", display_name="Claude Opus 5.5", tier="large",
         input_price_per_mtok=4.00, output_price_per_mtok=20.00, effort="medium"),
]
MOCK_CATALOG = [
    dict(model_name="mock-small", display_name="Mock small (test mode)", tier="small",
         simulates="anthropic:claude-haiku-5-5"),
    dict(model_name="mock-medium", display_name="Mock medium (test mode)", tier="medium",
         simulates="anthropic:claude-sonnet-5-5"),
    dict(model_name="mock-large", display_name="Mock large (test mode)", tier="large",
         simulates="anthropic:claude-opus-5-5"),
]
TIERS = ("small", "medium", "large")


def model_id(provider: str, name: str) -> str:
    return f"{provider}:{name}"


def seed_models(db: Session, settings: Settings | None = None) -> None:
    """Insert catalog rows that are missing. Never overwrites prices or flags a user edited."""
    s = settings or get_settings()
    wanted: list[dict] = []
    for m in CLAUDE_CATALOG:
        wanted.append({**m, "provider": "anthropic", "price_source": ANTHROPIC_PRICE_SOURCE})
    for m in MOCK_CATALOG:
        wanted.append({**m, "provider": "mock", "is_mock": True,
                       "price_source": f"Simulated using the list price of {m['simulates']}"})
    for name, tier in ((s.gemini_small_model, "small"), (s.gemini_large_model, "large")):
        if name:
            wanted.append(dict(provider="gemini", model_name=name, display_name=f"Gemini {name}", tier=tier,
                               price_source="Not set - enter the price from ai.google.dev/gemini-api/docs/pricing"))
    if s.openai_compat_model:
        priced = s.openai_compat_input_price_per_mtok is not None and s.openai_compat_output_price_per_mtok is not None
        wanted.append(dict(provider="openai_compatible", model_name=s.openai_compat_model,
                           display_name=f"{s.openai_compat_model} (OpenAI-compatible)", tier=s.openai_compat_tier,
                           input_price_per_mtok=s.openai_compat_input_price_per_mtok,
                           output_price_per_mtok=s.openai_compat_output_price_per_mtok,
                           price_source=".env OPENAI_COMPAT_*_PRICE_PER_MTOK" if priced else "Not set"))
    existing = {m.id for m in db.scalars(select(ModelConfig))}
    for w in wanted:
        mid = model_id(w["provider"], w["model_name"])
        if mid not in existing:
            db.add(ModelConfig(id=mid, **w))
    db.commit()


@dataclass
class ModelInfo:
    id: str
    provider: str
    model_name: str
    display_name: str
    tier: str
    is_mock: bool
    enabled: bool
    available: bool
    unavailable_reason: str | None
    effort: str | None
    input_price_per_mtok: float | None
    output_price_per_mtok: float | None
    price_source: str | None
    simulates: str | None


class ModelRegistry:
    """Builds provider clients from settings and answers 'which models can run right now?'"""

    def __init__(self, settings: Settings | None = None, providers: dict[str, LLMProvider] | None = None):
        self.settings = settings or get_settings()
        self._providers: dict[str, LLMProvider] = dict(providers or {})

    def provider(self, name: str) -> LLMProvider:
        if name not in self._providers:
            s = self.settings
            if name == "mock":
                self._providers[name] = MockProvider()
            elif name == "anthropic" and s.anthropic_api_key:
                from app.llm.anthropic_provider import AnthropicProvider
                self._providers[name] = AnthropicProvider(s.anthropic_api_key, s.anthropic_server_fallbacks)
            elif name == "gemini" and s.gemini_api_key:
                from app.llm.gemini_provider import GeminiProvider
                self._providers[name] = GeminiProvider(s.gemini_api_key)
            elif name == "openai_compatible" and s.openai_compat_base_url:
                from app.llm.openai_compat import OpenAICompatProvider
                self._providers[name] = OpenAICompatProvider(s.openai_compat_base_url, s.openai_compat_api_key)
            else:
                raise KeyError(f"Provider '{name}' is not configured")
        return self._providers[name]

    def _availability(self, m: ModelConfig) -> tuple[bool, str | None]:
        if not m.enabled:
            return False, "disabled in Settings"
        mock = self.settings.mock_mode
        if m.is_mock:
            return (True, None) if mock else (False, "mock models only run in test mode")
        if mock:
            return False, "test mode is on (no provider keys, or LLM_MOCK_MODE=true)"
        if not self.settings.provider_status.get(m.provider, False):
            return False, f"no API key / URL configured for {m.provider}"
        return True, None

    def models(self, db: Session) -> list[ModelInfo]:
        out = []
        for m in db.scalars(select(ModelConfig).order_by(ModelConfig.provider, ModelConfig.tier)):
            ok, why = self._availability(m)
            out.append(ModelInfo(m.id, m.provider, m.model_name, m.display_name, m.tier, m.is_mock, m.enabled, ok, why,
                                 m.effort, m.input_price_per_mtok, m.output_price_per_mtok, m.price_source, m.simulates))
        return out

    def available(self, db: Session) -> list[ModelInfo]:
        return [m for m in self.models(db) if m.available]


def compute_cost(db: Session, model_cfg_id: str, input_tokens: int, output_tokens: int) -> tuple[float | None, str]:
    """Return (usd, status). status: priced | simulated | unpriced."""
    m = db.get(ModelConfig, model_cfg_id)
    if m is None:
        return None, "unpriced"
    status = "priced"
    if m.is_mock:
        ref = db.get(ModelConfig, m.simulates) if m.simulates else None
        if ref is None:
            return None, "unpriced"
        m, status = ref, "simulated"
    if m.input_price_per_mtok is None or m.output_price_per_mtok is None:
        return None, "unpriced"
    pin, pout = m.input_price_per_mtok, m.output_price_per_mtok
    if m.long_context_threshold and input_tokens > m.long_context_threshold \
            and m.long_input_price_per_mtok is not None and m.long_output_price_per_mtok is not None:
        pin, pout = m.long_input_price_per_mtok, m.long_output_price_per_mtok
    return round(input_tokens / 1e6 * pin + output_tokens / 1e6 * pout, 8), status


_registry: ModelRegistry | None = None


def get_registry() -> ModelRegistry:
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry


def set_registry(reg: ModelRegistry | None) -> None:
    global _registry
    _registry = reg
