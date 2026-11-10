"""Context-aware semantic cache.

LOOKUP (in order):
 1. Exact match   - same normalised question text + same tenant + same document scope.
 2. Semantic match - nearest cached questions by cosine similarity (ChromaDB),
                     restricted to the same tenant AND document scope.
Every candidate must then pass ALL safety checks before it is reused:
   * similarity >= threshold
   * not expired (TTL) and not invalidated
   * every source document still exists, has the SAME version, and belongs
     to the caller's tenant (permission check)
   * same answer mode (a mock answer is never served when real LLMs are on)
   * compatible intent: same query category, same numbers, same negation
The first candidate that passes is a hit; every rejection reason is recorded
so the UI can explain why a question did or did not match.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import timedelta

import numpy as np
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import CacheEntry, Document, utcnow
from app.rag.vector_store import VectorStore
from app.router.query_intelligence import analyze

_NEGATIONS = re.compile(r"\b(not|no|never|without|except|cannot|can't|isn't|aren't|doesn't|don't|won't)\b", re.I)
_NUMBERS = re.compile(r"\d+(?:\.\d+)?")
# Words that flip or narrow the meaning of otherwise identical questions
# ("refund AFTER 30 days" vs "refund WITHIN 30 days" have cosine similarity ~0.98).
_QUALIFIERS = re.compile(r"\b(after|before|within|more than|less than|at least|at most|over|under|above|below|"
                         r"except|only|earliest|latest|minimum|maximum|first|last)\b", re.I)


def normalize_query(q: str) -> str:
    q = q.lower().strip()
    q = re.sub(r"[\s]+", " ", q)
    return re.sub(r"[?.!\s]+$", "", q)


def query_hash(q: str) -> str:
    return hashlib.sha256(normalize_query(q).encode()).hexdigest()


def scope_key(document_ids: list[int] | None) -> str:
    """Identifies WHICH documents a question was asked against. 'all' = whole library."""
    if not document_ids:
        return "all"
    return "docs:" + hashlib.sha256(",".join(str(i) for i in sorted(set(document_ids))).encode()).hexdigest()[:24]


@dataclass
class CacheCandidate:
    entry_id: int
    query_text: str
    similarity: float
    accepted: bool
    reasons: list[str]


@dataclass
class CacheLookup:
    status: str                    # exact_hit | semantic_hit | miss | disabled
    entry: CacheEntry | None
    similarity: float | None       # best similarity seen (even on a miss)
    reason: str
    candidates: list[CacheCandidate] = field(default_factory=list)

    @property
    def hit(self) -> bool:
        return self.status in ("exact_hit", "semantic_hit")


def intent_conflicts(new_q: str, cached_q: str, new_category: str, cached_category: str | None) -> list[str]:
    reasons = []
    if cached_category and new_category != cached_category:
        reasons.append(f"different intent ({new_category} vs {cached_category})")
    if sorted(_NUMBERS.findall(new_q)) != sorted(_NUMBERS.findall(cached_q)):
        reasons.append("different numbers in the question")
    if bool(_NEGATIONS.search(new_q)) != bool(_NEGATIONS.search(cached_q)):
        reasons.append("negation differs (e.g. 'not' in one question only)")
    qa = {m.lower() for m in _QUALIFIERS.findall(new_q)}
    qb = {m.lower() for m in _QUALIFIERS.findall(cached_q)}
    if qa and qb and qa != qb:   # both constrain the question, but differently -> conflicting intent
        reasons.append(f"different qualifier ({', '.join(sorted(qa))} vs {', '.join(sorted(qb))})")
    return reasons


class SemanticCache:
    def __init__(self, db: Session, store: VectorStore):
        self.db, self.store = db, store

    # ------------------------------------------------------------ validation
    def _validate(self, entry: CacheEntry, tenant: str, is_mock_mode: bool) -> list[str]:
        reasons: list[str] = []
        now = utcnow()
        if entry.status != "active":
            reasons.append(f"entry is {entry.status}")
        if entry.expires_at <= now:
            reasons.append("expired (TTL)")
            if entry.status == "active":
                entry.status = "expired"
        if entry.tenant_id != tenant:
            reasons.append("belongs to another tenant")
        if bool(entry.is_mock) != is_mock_mode:
            reasons.append("answer came from " + ("mock test mode" if entry.is_mock else "a real LLM") +
                           ", current mode differs")
        for doc_id, version in (entry.source_versions or {}).items():
            doc = self.db.get(Document, int(doc_id))
            if doc is None:
                reasons.append(f"source document {doc_id} was deleted")
            elif doc.tenant_id != tenant:
                reasons.append(f"no permission for source document {doc_id}")
            elif doc.version != version:
                reasons.append(f"source document '{doc.filename}' changed (v{version} -> v{doc.version})")
        return reasons

    # ------------------------------------------------------------ lookup
    def lookup(self, query: str, vector: np.ndarray, tenant: str, scope: str, threshold: float,
               is_mock_mode: bool, k: int = 5) -> CacheLookup:
        category = analyze(query).category
        candidates: list[CacheCandidate] = []

        # 1) exact match
        exact = self.db.scalars(
            select(CacheEntry).where(CacheEntry.tenant_id == tenant, CacheEntry.scope_key == scope,
                                     CacheEntry.query_hash == query_hash(query), CacheEntry.status == "active")
            .order_by(CacheEntry.created_at.desc())).first()
        if exact is not None:
            reasons = self._validate(exact, tenant, is_mock_mode)
            candidates.append(CacheCandidate(exact.id, exact.query_text, 1.0, not reasons, reasons))
            if not reasons:
                return CacheLookup("exact_hit", exact, 1.0, "Exact match of a previously answered question.", candidates)

        # 2) semantic match
        best = None
        for r in self.store.query(self.store.cache, vector, k,
                                  {"$and": [{"tenant_id": tenant}, {"scope_key": scope}]}):
            entry = self.db.get(CacheEntry, int(r["metadata"]["entry_id"]))
            if entry is None or (exact is not None and entry.id == exact.id):
                continue
            sim = round(r["similarity"], 4)
            best = sim if best is None else max(best, sim)
            reasons = []
            if sim < threshold:
                reasons.append(f"similarity {sim:.3f} below threshold {threshold:.2f}")
            reasons += self._validate(entry, tenant, is_mock_mode)
            reasons += intent_conflicts(query, entry.query_text, category, entry.intent_category)
            candidates.append(CacheCandidate(entry.id, entry.query_text, sim, not reasons, reasons))
            if not reasons:
                self.db.commit()  # persist any status changes made during validation
                return CacheLookup("semantic_hit", entry, sim,
                                   f"Semantically equivalent to a cached question (cosine similarity {sim:.3f} "
                                   f">= threshold {threshold:.2f}); documents unchanged, not expired, same intent.",
                                   candidates)
        self.db.commit()
        if candidates:
            top = max(candidates, key=lambda c: c.similarity)
            reason = "No safe match. Closest cached question rejected: " + "; ".join(top.reasons) + "."
        else:
            reason = "No cached question for this tenant and document scope yet."
        return CacheLookup("miss", None, best if best is not None else (1.0 if exact else None), reason, candidates)

    def record_hit(self, entry: CacheEntry, similarity: float) -> None:
        entry.hit_count += 1
        entry.last_hit_at = utcnow()
        entry.last_similarity = similarity
        self.db.commit()

    # ------------------------------------------------------------ store
    def store_answer(self, *, query: str, vector: np.ndarray, tenant: str, scope: str, answer: str,
                     citations: list[dict], source_versions: dict[str, int], model: str, provider: str,
                     is_mock: bool, input_tokens: int, output_tokens: int, cost_usd: float, latency_ms: float,
                     ttl_hours: int, request_id: int | None) -> CacheEntry:
        entry = CacheEntry(
            tenant_id=tenant, query_text=query, normalized_query=normalize_query(query), query_hash=query_hash(query),
            scope_key=scope, source_versions=source_versions, intent_category=analyze(query).category,
            response_text=answer, citations=citations, model=model, provider=provider, is_mock=is_mock,
            input_tokens=input_tokens, output_tokens=output_tokens, original_cost_usd=cost_usd,
            original_latency_ms=latency_ms, expires_at=utcnow() + timedelta(hours=ttl_hours), request_id=request_id)
        self.db.add(entry)
        self.db.commit()
        self.store.add(self.store.cache, [f"cache-{entry.id}"], vector.reshape(1, -1),
                       [{"tenant_id": tenant, "scope_key": scope, "entry_id": entry.id}])
        return entry

    # ------------------------------------------------------------ invalidation / admin
    def invalidate_for_document(self, tenant: str, document_id: int, reason: str) -> int:
        """Called when a document is updated or deleted: every answer that used it becomes invalid."""
        n = 0
        for e in self.db.scalars(select(CacheEntry).where(CacheEntry.tenant_id == tenant,
                                                          CacheEntry.status == "active")):
            if str(document_id) in (e.source_versions or {}):
                e.status, e.invalidated_reason = "invalidated", reason
                self.store.delete(self.store.cache, ids=[f"cache-{e.id}"])
                n += 1
        self.db.commit()
        return n

    def delete_entry(self, entry: CacheEntry) -> None:
        self.store.delete(self.store.cache, ids=[f"cache-{entry.id}"])
        self.db.delete(entry)
        self.db.commit()

    def clear(self, tenant: str) -> int:
        ids = [e.id for e in self.db.scalars(select(CacheEntry).where(CacheEntry.tenant_id == tenant))]
        if ids:
            self.store.delete(self.store.cache, ids=[f"cache-{i}" for i in ids])
            self.db.query(CacheEntry).filter(CacheEntry.tenant_id == tenant).delete()
            self.db.commit()
        return len(ids)

    def expire_stale(self, tenant: str | None = None) -> int:
        stmt = update(CacheEntry).where(CacheEntry.status == "active", CacheEntry.expires_at <= utcnow())
        if tenant:
            stmt = stmt.where(CacheEntry.tenant_id == tenant)
        n = self.db.execute(stmt.values(status="expired")).rowcount or 0
        self.db.commit()
        return n
