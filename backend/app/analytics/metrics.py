"""Analytics computed from recorded rows only (no invented numbers).

Cost vocabulary used everywhere:
  actual_cost_usd      tokens of real LLM calls x list price (an ESTIMATE of the bill)
  simulated_cost_usd   same calculation for mock-mode calls (never real spend)
  unpriced_calls       calls whose model has no price configured
  saved_by_cache_usd   counterfactual: what cache hits would have cost
  saved_by_routing_usd counterfactual: baseline-model cost minus routed-model cost
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CacheEntry, LLMCall, RequestLog, SystemEvent

HITS = ("exact_hit", "semantic_hit")


def _pct(values: list[float], p: float) -> float | None:
    return round(float(np.percentile(values, p)), 1) if values else None


def _requests(db: Session, tenant: str, days: int | None = None, limit: int = 50_000) -> list[RequestLog]:
    q = select(RequestLog).where(RequestLog.tenant_id == tenant)
    if days:
        q = q.where(RequestLog.created_at >= datetime.now(timezone.utc) - timedelta(days=days))
    return list(db.scalars(q.order_by(RequestLog.created_at.desc()).limit(limit)))


def _day(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")


def _tier(model_id: str | None, tiers: dict[str, str]) -> str | None:
    return tiers.get(model_id or "")


def overview(db: Session, tenant: str, days: int = 30) -> dict:
    from app.models import ModelConfig
    tiers = {m.id: m.tier for m in db.scalars(select(ModelConfig))}
    names = {m.id: m.display_name for m in db.scalars(select(ModelConfig))}
    reqs = _requests(db, tenant, days)
    ok = [r for r in reqs if r.cache_status != "error"]
    total = len(reqs)
    hits = [r for r in ok if r.cache_status in HITS]
    cacheable = [r for r in ok if r.cache_status in (*HITS, "miss")]
    latencies = [r.total_latency_ms for r in ok if r.total_latency_ms]
    sims = [r.similarity for r in ok if r.similarity is not None]
    llm_rows = [r for r in ok if r.selected_model and r.cache_status not in HITS]
    actual = sum((r.cost_usd or 0) for r in ok if r.cost_status == "priced")
    simulated = sum((r.cost_usd or 0) for r in ok if r.cost_status == "simulated")
    tier_counts = Counter(_tier(r.selected_model, tiers) for r in llm_rows)

    # ---- daily series
    daily: dict[str, dict] = defaultdict(lambda: {"queries": 0, "hits": 0, "misses": 0, "errors": 0, "cost": 0.0,
                                                  "simulated_cost": 0.0, "saved": 0.0, "lat": []})
    for r in reqs:
        d = daily[_day(r.created_at)]
        d["queries"] += 1
        if r.cache_status in HITS:
            d["hits"] += 1
        elif r.cache_status == "error":
            d["errors"] += 1
        else:
            d["misses"] += 1
        if r.cost_status == "priced":
            d["cost"] += r.cost_usd or 0
        elif r.cost_status == "simulated":
            d["simulated_cost"] += r.cost_usd or 0
        d["saved"] += (r.saved_cost_cache or 0) + (r.saved_cost_routing or 0)
        if r.total_latency_ms and r.cache_status != "error":
            d["lat"].append(r.total_latency_ms)
    series = []
    for day in sorted(daily):
        d = daily[day]
        series.append({"date": day, "queries": d["queries"], "hits": d["hits"], "misses": d["misses"],
                       "errors": d["errors"], "cost_usd": round(d["cost"], 6),
                       "simulated_cost_usd": round(d["simulated_cost"], 6), "saved_usd": round(d["saved"], 6),
                       "avg_latency_ms": round(float(np.mean(d["lat"])), 1) if d["lat"] else None,
                       "p95_latency_ms": _pct(d["lat"], 95)})

    model_dist = Counter(r.selected_model for r in llm_rows)
    routing = [r for r in reqs if r.routed_by][:8]
    calls_q = select(func.count(LLMCall.id)).join(RequestLog, LLMCall.request_id == RequestLog.id) \
        .where(RequestLog.tenant_id == tenant, LLMCall.success.is_(True))
    return {
        "has_data": total > 0,
        "window_days": days,
        "total_queries": total,
        "errors": total - len(ok),
        "cache_hit_rate": round(len(hits) / len(cacheable), 4) if cacheable else None,
        "cache_miss_rate": round(1 - len(hits) / len(cacheable), 4) if cacheable else None,
        "avg_latency_ms": round(float(np.mean(latencies)), 1) if latencies else None,
        "p95_latency_ms": _pct(latencies, 95),
        "avg_similarity": round(float(np.mean(sims)), 4) if sims else None,
        "actual_cost_usd": round(actual, 6),
        "simulated_cost_usd": round(simulated, 6),
        "saved_by_cache_usd": round(sum(r.saved_cost_cache or 0 for r in ok), 6),
        "saved_by_routing_usd": round(sum(r.saved_cost_routing or 0 for r in ok), 6),
        "llm_calls": db.scalar(calls_q) or 0,
        "llm_calls_avoided": len(hits),
        "small_model_queries": tier_counts.get("small", 0),
        "medium_model_queries": tier_counts.get("medium", 0),
        "large_model_queries": tier_counts.get("large", 0),
        "mock_queries": sum(1 for r in ok if r.is_mock),
        "daily": series,
        "model_distribution": [{"model_id": m, "name": names.get(m, m), "tier": tiers.get(m), "count": c}
                               for m, c in model_dist.most_common()],
        "cache_breakdown": {"exact_hit": sum(r.cache_status == "exact_hit" for r in ok),
                            "semantic_hit": sum(r.cache_status == "semantic_hit" for r in ok),
                            "miss": sum(r.cache_status == "miss" for r in ok),
                            "bypass": sum(r.cache_status == "bypass" for r in ok)},
        "recent_activity": [{"id": r.id, "query_text": r.query_text[:160], "cache_status": r.cache_status,
                             "total_latency_ms": r.total_latency_ms, "model": r.selected_model,
                             "cost_usd": r.cost_usd or 0.0, "cost_status": r.cost_status, "is_mock": bool(r.is_mock),
                             "created_at": r.created_at.isoformat()} for r in reqs[:10]],
        "recent_routing": [{"id": r.id, "query_text": r.query_text[:120], "category": r.category,
                            "complexity": r.complexity, "complexity_score": r.complexity_score,
                            "model": r.selected_model, "model_name": names.get(r.selected_model or "", r.selected_model),
                            "routed_by": r.routed_by, "reason": r.routing_reason,
                            "created_at": r.created_at.isoformat()} for r in routing],
    }


def cost_report(db: Session, tenant: str, days: int = 30) -> dict:
    from app.models import ModelConfig
    cfg = {m.id: m for m in db.scalars(select(ModelConfig))}
    reqs = _requests(db, tenant, days)
    calls = list(db.scalars(select(LLMCall).join(RequestLog, LLMCall.request_id == RequestLog.id)
                            .where(RequestLog.tenant_id == tenant,
                                   RequestLog.created_at >= datetime.now(timezone.utc) - timedelta(days=days))))
    per_model: dict[str, dict] = {}
    for c in calls:
        mid = f"{c.provider}:{c.model}"
        m = per_model.setdefault(mid, {"model_id": mid, "name": cfg[mid].display_name if mid in cfg else mid,
                                       "tier": cfg[mid].tier if mid in cfg else None, "calls": 0, "failed_calls": 0,
                                       "input_tokens": 0, "output_tokens": 0, "provider_reported_calls": 0,
                                       "estimated_usage_calls": 0, "cost_usd": 0.0, "cost_status": c.cost_status,
                                       "lat": []})
        if not c.success:
            m["failed_calls"] += 1
            continue
        m["calls"] += 1
        m["input_tokens"] += c.input_tokens
        m["output_tokens"] += c.output_tokens
        m["provider_reported_calls" if c.usage_source == "provider" else "estimated_usage_calls"] += 1
        m["cost_usd"] += c.estimated_cost_usd or 0
        m["cost_status"] = c.cost_status or m["cost_status"]
        m["lat"].append(c.latency_ms)
    models = []
    for m in per_model.values():
        lat = m.pop("lat")
        m["avg_latency_ms"] = round(float(np.mean(lat)), 1) if lat else None
        m["p95_latency_ms"] = _pct(lat, 95)
        m["cost_usd"] = round(m["cost_usd"], 6)
        models.append(m)

    weekly: dict[str, dict] = defaultdict(lambda: {"cost_usd": 0.0, "simulated_cost_usd": 0.0, "saved_usd": 0.0,
                                                   "queries": 0})
    for r in reqs:
        y, w, _ = r.created_at.isocalendar()
        k = f"{y}-W{w:02d}"
        weekly[k]["queries"] += 1
        weekly[k]["cost_usd" if r.cost_status == "priced" else "simulated_cost_usd"] += (
            r.cost_usd or 0) if r.cost_status in ("priced", "simulated") else 0
        weekly[k]["saved_usd"] += (r.saved_cost_cache or 0) + (r.saved_cost_routing or 0)
    ov = overview(db, tenant, days)
    actual = ov["actual_cost_usd"] + ov["simulated_cost_usd"]
    saved_c, saved_r = ov["saved_by_cache_usd"], ov["saved_by_routing_usd"]
    llm_reqs = [r for r in reqs if r.cost_status in ("priced", "simulated") and (r.cost_usd or 0) > 0]
    return {
        "window_days": days,
        "has_data": bool(reqs),
        "is_simulated": ov["simulated_cost_usd"] > 0 and ov["actual_cost_usd"] == 0,
        "actual_cost_usd": ov["actual_cost_usd"],
        "simulated_cost_usd": ov["simulated_cost_usd"],
        "unpriced_calls": sum(1 for c in calls if c.success and c.cost_status == "unpriced"),
        "saved_by_cache_usd": saved_c,
        "saved_by_routing_usd": saved_r,
        "baseline_estimate_usd": round(actual + saved_c + saved_r, 6),
        "savings_pct": round((saved_c + saved_r) / (actual + saved_c + saved_r), 4) if (actual + saved_c + saved_r) else None,
        "avg_cost_per_llm_query_usd": round(sum(r.cost_usd for r in llm_reqs) / len(llm_reqs), 8) if llm_reqs else None,
        "total_input_tokens": sum(m["input_tokens"] for m in models),
        "total_output_tokens": sum(m["output_tokens"] for m in models),
        "daily": ov["daily"],
        "weekly": [{"week": k, **{kk: round(vv, 6) if isinstance(vv, float) else vv for kk, vv in v.items()}}
                   for k, v in sorted(weekly.items())],
        "models": sorted(models, key=lambda m: -m["cost_usd"]),
        "notes": [
            "Costs are estimates: provider-reported (or estimated) token counts x configured list price.",
            "Savings are counterfactual: what cache hits and routed queries would have cost on the baseline path.",
            "Simulated costs come from test mode (mock models) and are never real spend.",
        ],
    }


def cache_stats(db: Session, tenant: str) -> dict:
    rows = list(db.scalars(select(CacheEntry).where(CacheEntry.tenant_id == tenant)))
    status = Counter(r.status for r in rows)
    reqs = _requests(db, tenant, 30)
    cacheable = [r for r in reqs if r.cache_status in (*HITS, "miss")]
    hits = [r for r in cacheable if r.cache_status in HITS]
    return {
        "entries": len(rows), "active": status.get("active", 0), "expired": status.get("expired", 0),
        "invalidated": status.get("invalidated", 0), "total_hits_served": sum(r.hit_count for r in rows),
        "hit_rate_30d": round(len(hits) / len(cacheable), 4) if cacheable else None,
        "exact_hits_30d": sum(r.cache_status == "exact_hit" for r in reqs),
        "semantic_hits_30d": sum(r.cache_status == "semantic_hit" for r in reqs),
        "misses_30d": sum(r.cache_status == "miss" for r in reqs),
        "saved_usd_30d": round(sum(r.saved_cost_cache or 0 for r in reqs), 6),
        "avg_hit_latency_ms": round(float(np.mean([r.total_latency_ms for r in hits])), 1) if hits else None,
        "avg_miss_latency_ms": (round(float(np.mean([r.total_latency_ms for r in cacheable if r.cache_status == "miss"
                                                     and r.selected_model])), 1)
                                if any(r.cache_status == "miss" and r.selected_model for r in cacheable) else None),
    }


def monitoring_stats(db: Session, tenant: str) -> dict:
    now = datetime.now(timezone.utc)
    last_hour = [r for r in _requests(db, tenant, 1) if r.created_at >= now - timedelta(hours=1)]
    lat = [r.total_latency_ms for r in last_hour if r.total_latency_ms and r.cache_status != "error"]
    errors = db.scalar(select(func.count(SystemEvent.id)).where(
        SystemEvent.level == "error", SystemEvent.created_at >= now - timedelta(hours=24))) or 0
    total = db.scalar(select(func.count(RequestLog.id)).where(RequestLog.tenant_id == tenant)) or 0
    per_min: Counter = Counter()
    for r in last_hour:
        per_min[r.created_at.astimezone(timezone.utc).strftime("%H:%M")] += 1
    minutes = [(now - timedelta(minutes=i)).strftime("%H:%M") for i in range(29, -1, -1)]
    cacheable = [r for r in last_hour if r.cache_status in (*HITS, "miss")]
    return {
        "total_processed": total,
        "queries_last_hour": len(last_hour),
        "errors_last_24h": errors,
        "hit_rate_last_hour": round(sum(r.cache_status in HITS for r in cacheable) / len(cacheable), 4) if cacheable else None,
        "avg_latency_last_hour_ms": round(float(np.mean(lat)), 1) if lat else None,
        "p95_latency_last_hour_ms": _pct(lat, 95),
        "cost_last_hour_usd": round(sum(r.cost_usd or 0 for r in last_hour if r.cost_status == "priced"), 6),
        "simulated_cost_last_hour_usd": round(sum(r.cost_usd or 0 for r in last_hour if r.cost_status == "simulated"), 6),
        "per_minute": [{"minute": m, "queries": per_min.get(m, 0)} for m in minutes],
        "model_usage_last_hour": dict(Counter(r.selected_model for r in last_hour
                                              if r.selected_model and r.cache_status not in HITS)),
    }
