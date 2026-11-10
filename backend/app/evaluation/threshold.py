"""Adaptive Similarity Threshold Optimizer.

Uses labelled question pairs (same intent / different intent). For each
candidate threshold it MEASURES, with the real embedding model:
  * reuse rate        - share of same-intent pairs that would hit the cache
  * false-match rate  - share of different-intent pairs that would WRONGLY hit
  * the same false-match rate after NEXUS AI's intent guard (category /
    numbers / negation / qualifier checks), which runs on top of similarity
Recommendation rule (safety first, never "maximise hits"):
  the LOWEST threshold whose false-match rate is 0 on this dataset when the
  intent guard is applied (that is how the cache really decides), plus a
  0.02 safety margin, never below 0.85. If no threshold is
  safe, recommend the highest tested threshold.
Projected latency uses the MEASURED average hit/miss latencies from your own
request history when available, and is labelled "projected".
"""
from __future__ import annotations

import numpy as np

from app.cache.semantic_cache import intent_conflicts
from app.embeddings import Embedder
from app.router.query_intelligence import analyze

THRESHOLDS = [round(0.70 + 0.02 * i, 2) for i in range(15)]   # 0.70 ... 0.98


def run_threshold_experiment(pairs: list[dict], embedder: Embedder, measured_hit_ms: float | None = None,
                             measured_miss_ms: float | None = None, current: float | None = None) -> dict:
    a = embedder.embed([p["a"] for p in pairs])
    b = embedder.embed([p["b"] for p in pairs])
    sims = np.sum(a * b, axis=1) / (np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1))
    rows = []
    for p, s in zip(pairs, sims):
        guard = intent_conflicts(p["b"], p["a"], analyze(p["b"]).category, analyze(p["a"]).category)
        rows.append({"a": p["a"], "b": p["b"], "same_intent": p["same_intent"], "similarity": round(float(s), 4),
                     "guard_blocks": guard})
    pos = [r for r in rows if r["same_intent"]]
    neg = [r for r in rows if not r["same_intent"]]
    results = []
    for t in THRESHOLDS:
        tp = sum(r["similarity"] >= t for r in pos)
        fp = sum(r["similarity"] >= t for r in neg)
        fp_guarded = sum(r["similarity"] >= t and not r["guard_blocks"] for r in neg)
        tp_guarded = sum(r["similarity"] >= t and not r["guard_blocks"] for r in pos)
        reuse = tp_guarded / len(pos) if pos else 0.0
        res = {"threshold": t, "reuse_rate": round(tp / len(pos), 4) if pos else None,
               "false_match_rate": round(fp / len(neg), 4) if neg else None,
               "reuse_rate_with_guard": round(reuse, 4),
               "false_match_rate_with_guard": round(fp_guarded / len(neg), 4) if neg else None,
               "precision": round(tp / (tp + fp), 4) if (tp + fp) else None}
        if measured_hit_ms is not None and measured_miss_ms is not None:
            res["projected_avg_latency_ms"] = round(reuse * measured_hit_ms + (1 - reuse) * measured_miss_ms, 1)
        results.append(res)

    # Recommendation measures the WHOLE safety system NEXUS AI uses (similarity + intent guard).
    safe = [r for r in results if r["false_match_rate_with_guard"] == 0]
    if safe:
        rec = max(0.85, min(0.99, round(safe[0]["threshold"] + 0.02, 2)))
        why = (f"{safe[0]['threshold']:.2f} is the lowest tested threshold at which no different-intent pair was "
               f"wrongly matched (similarity + intent guard). A 0.02 safety margin is added and the result is never "
               f"below 0.85, so correctness is preferred over a higher hit rate.")
    else:
        rec = THRESHOLDS[-1]
        why = ("Even the strictest tested threshold let a different-intent pair through, so the strictest threshold "
               "is recommended. Review the failing pairs below.")
    unsafe_embedding_only = [r["threshold"] for r in results if r["false_match_rate"]]
    if unsafe_embedding_only:
        why += (f" Note: similarity alone produced wrong matches up to {max(unsafe_embedding_only):.2f} - "
                "the intent guard is what makes cache reuse safe on this dataset.")
    return {"pairs": rows, "results": results, "recommended_threshold": rec, "recommendation_reason": why,
            "current_threshold": current, "positives": len(pos), "negatives": len(neg),
            "latency_note": ("Projected from your measured average cache-hit and LLM-miss latencies."
                             if measured_hit_ms is not None and measured_miss_ms is not None
                             else "Latency projection appears after you have both cache hits and LLM misses recorded."),
            "embedding_model": getattr(embedder, "name", "unknown")}
