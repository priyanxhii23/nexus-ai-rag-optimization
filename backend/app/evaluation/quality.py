"""Automatic answer-quality heuristics (transparent, reproducible, free).

These are NOT human judgements. They are simple measurable proxies:
  retrieval_hit  1 if the gold document is among the cited sources, else 0
  correctness    share of expected keyword groups found in the answer
  faithfulness   share of answer sentences whose embedding is close (cos >= 0.5)
                 to at least one retrieved passage - i.e. "grounded in context"
"""
from __future__ import annotations

import re

import numpy as np

from app.embeddings import Embedder
from app.llm.mock import MOCK_BANNER

FAITHFUL_SIM = 0.5


def _sentences(answer: str) -> list[str]:
    text = answer.replace(MOCK_BANNER, " ")
    text = re.sub(r"\[\d+\]", " ", text)
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip(" -*\t") for p in parts if len(p.strip(" -*\t")) >= 15]


def correctness(answer: str, expected: list[list[str]]) -> float | None:
    if not expected:
        return None
    a = answer.lower()
    return round(sum(any(k.lower() in a for k in group) for group in expected) / len(expected), 4)


def retrieval_hit(citations: list[dict], gold: str | None) -> float | None:
    if not gold:
        return None
    return 1.0 if any(c.get("filename") == gold for c in citations) else 0.0


def faithfulness(answer: str, context_texts: list[str], embedder: Embedder) -> float | None:
    sents = _sentences(answer)
    if not sents or not context_texts:
        return None
    s_vecs = embedder.embed(sents)
    c_vecs = embedder.embed(context_texts)
    sims = s_vecs @ c_vecs.T
    return round(float(np.mean(sims.max(axis=1) >= FAITHFUL_SIM)), 4)


def citation_count(answer: str) -> int:
    return len(set(re.findall(r"\[(\d+)\]", answer)))
