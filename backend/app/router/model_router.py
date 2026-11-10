"""Cost-aware model router.

Maps query complexity to a model *tier*, then picks an available model in that
tier. Strategies (Settings page):
  balanced      simple->small, medium->medium, complex->large
  cost_saver    simple/medium->small, complex->medium
  quality_first simple->medium, medium/complex->large
If the wanted tier has no available model, the nearest tier is used (and the
reason says so). The full ordered fallback chain is returned so the pipeline
can retry on another model when a provider call fails.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.llm.registry import TIERS, ModelInfo
from app.router.query_intelligence import QueryAnalysis

STRATEGY_TIERS = {
    "balanced": {"simple": "small", "medium": "medium", "complex": "large"},
    "cost_saver": {"simple": "small", "medium": "small", "complex": "medium"},
    "quality_first": {"simple": "medium", "medium": "large", "complex": "large"},
}
_PROVIDER_PREF = ("anthropic", "gemini", "openai_compatible", "mock")


@dataclass
class RoutingDecision:
    model: ModelInfo
    routed_by: str              # auto | manual | baseline
    wanted_tier: str
    reason: str
    fallbacks: list[ModelInfo] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"model_id": self.model.id, "model": self.model.display_name, "provider": self.model.provider,
                "tier": self.model.tier, "wanted_tier": self.wanted_tier, "routed_by": self.routed_by,
                "reason": self.reason, "fallback_chain": [m.id for m in self.fallbacks]}


class NoModelAvailable(Exception):
    pass


def _tier_order(wanted: str) -> list[str]:
    i = TIERS.index(wanted)
    # wanted first, then nearest tiers - prefer going UP in capability over down
    return sorted(TIERS, key=lambda t: (abs(TIERS.index(t) - i), -TIERS.index(t)))


def _sorted(models: list[ModelInfo], wanted: str) -> list[ModelInfo]:
    order = _tier_order(wanted)
    return sorted(models, key=lambda m: (order.index(m.tier),
                                         _PROVIDER_PREF.index(m.provider) if m.provider in _PROVIDER_PREF else 9))


def route(analysis: QueryAnalysis, available: list[ModelInfo], strategy: str = "balanced",
          manual_model_id: str | None = None, baseline: bool = False) -> RoutingDecision:
    if not available:
        raise NoModelAvailable("No model is available. Add an API key in .env or enable test mode (LLM_MOCK_MODE=auto).")

    if manual_model_id:
        chosen = next((m for m in available if m.id == manual_model_id), None)
        if chosen is None:
            raise NoModelAvailable(f"Model '{manual_model_id}' is not available right now.")
        rest = [m for m in _sorted(available, chosen.tier) if m.id != chosen.id]
        return RoutingDecision(chosen, "manual", chosen.tier, "Selected manually by the user.", rest)

    if baseline:
        ordered = _sorted(available, "large")
        return RoutingDecision(ordered[0], "baseline", "large",
                               "Baseline configuration: routing disabled, always the most capable available model.",
                               ordered[1:])

    tiers = STRATEGY_TIERS.get(strategy, STRATEGY_TIERS["balanced"])
    wanted = tiers[analysis.complexity_level]
    ordered = _sorted(available, wanted)
    chosen = ordered[0]
    reason = (f"Query is {analysis.complexity_level} (score {analysis.complexity_score:g}, "
              f"{analysis.category}); strategy '{strategy}' maps it to the {wanted} tier")
    if chosen.tier != wanted:
        reason += f"; no {wanted}-tier model is available, so the nearest tier ({chosen.tier}) was used"
    reason += f" -> {chosen.display_name}."
    return RoutingDecision(chosen, "auto", wanted, reason, ordered[1:])
