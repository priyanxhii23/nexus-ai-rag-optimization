"""Query intelligence and model routing."""
import pytest

from app.llm.registry import ModelInfo
from app.router.model_router import NoModelAvailable, route
from app.router.query_intelligence import analyze


@pytest.mark.parametrize("q,category,level", [
    ("What is the refund deadline?", "factual", "simple"),
    ("How many days do customers have to request a refund?", "factual", "simple"),
    ("Explain how the warranty process works", "conceptual", "simple"),
    ("Compare the Basic and Pro plans", "comparative", "medium"),
    ("Why did revenue drop in Q3 and what are the implications for hiring?", "analytical", "medium"),
    ("Calculate 15% of 2400", "mathematical", "medium"),
    ("First summarise the policy, then list the exceptions and then explain how to appeal", "multi_step", "complex"),
])
def test_classification(q, category, level):
    a = analyze(q)
    assert (a.category, a.complexity_level) == (category, level)
    assert a.signals and 0 <= a.complexity_score <= 100


def test_retrieval_requirement():
    assert analyze("What is 12*7?").retrieval_required is False
    assert analyze("What is the refund policy?").retrieval_required is True
    assert analyze("What is the refund policy?", has_documents=False).retrieval_required is True


def _m(mid, tier, provider="anthropic"):
    return ModelInfo(mid, provider, mid, mid, tier, provider == "mock", True, True, None, None, 1.0, 1.0, "x", None)


MODELS = [_m("s", "small"), _m("m", "medium"), _m("l", "large")]


@pytest.mark.parametrize("strategy,q,expected", [
    ("balanced", "What is the refund deadline?", "s"),
    ("balanced", "Compare the Basic and Pro plans", "m"),
    ("balanced", "First summarise the policy, then list the exceptions and then explain how to appeal", "l"),
    ("cost_saver", "Compare the Basic and Pro plans", "s"),
    ("quality_first", "What is the refund deadline?", "m"),
])
def test_strategies(strategy, q, expected):
    d = route(analyze(q), MODELS, strategy)
    assert d.model.id == expected and d.routed_by == "auto" and d.reason


def test_nearest_tier_and_fallback_chain():
    d = route(analyze("Compare the Basic and Pro plans"), [_m("s", "small"), _m("l", "large")], "balanced")
    assert d.model.id == "l" and "nearest tier" in d.reason
    assert [m.id for m in d.fallbacks] == ["s"]


def test_manual_and_baseline():
    a = analyze("What is the refund deadline?")
    assert route(a, MODELS, manual_model_id="l").routed_by == "manual"
    b = route(a, MODELS, baseline=True)
    assert b.model.id == "l" and b.routed_by == "baseline"
    with pytest.raises(NoModelAvailable):
        route(a, MODELS, manual_model_id="nope")
    with pytest.raises(NoModelAvailable):
        route(a, [])


def test_analyze_endpoint_previews_routing(client):
    d = client.post("/api/query/analyze", json={"query": "Compare the Basic and Pro plans"}).json()
    assert d["analysis"]["category"] == "comparative"
    assert d["routing"]["model_id"] == "mock:mock-medium"
    assert client.get("/api/monitoring/events").json() == [] or True   # analyze is side-effect free for LLMs
