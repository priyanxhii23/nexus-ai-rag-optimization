# Evaluation

## Dataset
`backend/app/evaluation/datasets/nexus_demo_v1.json` - a fictional SaaS handbook (3 documents, one with a
planted prompt-injection sentence), 22 questions with expected keywords and gold documents (including
paraphrases and one exact repeat so the cache can be exercised), and 20 labelled question pairs
(10 same intent, 10 different intent) for threshold tuning.

## Configurations
| Config | Cache | Routing |
|---|---|---|
| A. Baseline RAG | off | off (most capable available model) |
| B. RAG + cache | on | off |
| C. RAG + cache + routing | on | on |

Each run uses an isolated tenant and an empty cache per configuration; identical questions, documents and settings.

## Metrics
Average / median / p95 latency, cache hit/miss rate, LLM calls made/avoided, input/output tokens, cost,
cost and latency reduction vs A, retrieval relevance (gold document cited), answer correctness (share of
expected keyword groups present), answer faithfulness (share of answer sentences with embedding
similarity ≥ 0.5 to a retrieved passage). Quality metrics are automatic heuristics, not human ratings.

## Measured results so far (development container, TEST MODE)

These numbers come from an actual run, but with the **mock** provider, so they demonstrate the
pipeline, not real LLM performance. Costs are **simulated** with Claude list prices.

| Metric | A. Baseline | B. + cache | C. + cache + routing |
|---|---|---|---|
| Cache hit rate | 0% | 13.6% | 13.6% |
| LLM calls (of 22) | 22 | 19 | 19 |
| Simulated cost | $0.0909 | $0.0791 | $0.0115 |
| Cost reduction vs A | - | 13.0% | 87.3% |
| Avg latency | 25 ms | 33 ms | 32 ms |
| Retrieval relevance / correctness / faithfulness | 0.95 / 0.90 / 0.64 | 0.95 / 0.90 / 0.64 | 0.95 / 0.90 / 0.64 |

(Run on 2026-11-09 from a fresh install of the v4.0 ZIP.)

Honest reading: in test mode the "LLM" answers instantly, so the cache lookup is pure overhead and B/C
are slower. With real LLMs (seconds per answer) a cache hit saves that time; this must be measured on
your laptop with real keys before any latency claim is made. The hit rate is low because the threshold
(0.92) is conservative.

Threshold experiment with the real MiniLM model: similarity alone produced wrong matches at every
threshold up to 0.98; with the intent guard, zero wrong matches from 0.80 upward. Recommended threshold: 0.85.

**Real-LLM results: not measured yet.** Run the Benchmarking Lab with API keys and add the numbers here.
