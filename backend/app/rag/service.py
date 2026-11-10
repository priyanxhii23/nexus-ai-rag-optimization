"""Document ingestion and retrieval (the RAG engine)."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import get_logger
from app.core.security import looks_like_injection, safe_filename, validate_upload
from app.embeddings import Embedder
from app.models import Document, DocumentChunk, utcnow
from app.rag.chunker import chunk_pages
from app.rag.extract import extract_pages
from app.rag.vector_store import VectorStore

log = get_logger("rag")


@dataclass
class RetrievedChunk:
    chunk_id: int
    document_id: int
    document_version: int
    filename: str
    page: int | None
    chunk_index: int
    text: str
    score: float
    flagged: bool

    def citation(self, index: int) -> dict:
        snippet = self.text if len(self.text) <= 400 else self.text[:400].rsplit(" ", 1)[0] + " ..."
        return {"index": index, "document_id": self.document_id, "filename": self.filename, "page": self.page,
                "chunk_index": self.chunk_index, "score": round(self.score, 4), "snippet": snippet,
                "document_version": self.document_version}


class DocumentService:
    def __init__(self, db: Session, store: VectorStore, embedder: Embedder):
        self.db, self.store, self.embedder = db, store, embedder
        self.settings = get_settings()

    # ------------------------------------------------------------ helpers
    def _storage_dir(self, tenant: str) -> Path:
        d = self.settings.resolve(self.settings.documents_path) / tenant
        d.mkdir(parents=True, exist_ok=True)
        return d

    def get(self, tenant: str, doc_id: int) -> Document:
        doc = self.db.get(Document, doc_id)
        if doc is None or doc.tenant_id != tenant:   # other tenants' documents look like 404
            raise AppError("Document not found.", 404, "not_found")
        return doc

    def _index(self, doc: Document, data: bytes, ext: str) -> None:
        pages = extract_pages(data, ext)
        chunks = chunk_pages(pages, self.settings.chunk_size_chars, self.settings.chunk_overlap_chars)
        if not chunks:
            raise AppError("No usable text was found in this file.", 422, "no_text")
        vectors = self.embedder.embed([c.text for c in chunks])
        rows, flagged = [], 0
        for c in chunks:
            is_flagged = looks_like_injection(c.text)
            flagged += is_flagged
            rows.append(DocumentChunk(document_id=doc.id, tenant_id=doc.tenant_id, document_version=doc.version,
                                      chunk_index=c.index, text=c.text, page=c.page, char_start=c.char_start,
                                      char_end=c.char_end, flagged=is_flagged))
        self.db.add_all(rows)
        self.db.flush()
        for r in rows:
            r.vector_id = f"doc{doc.id}-v{doc.version}-c{r.chunk_index}"
        self.store.add(self.store.docs, [r.vector_id for r in rows], vectors,
                       [{"tenant_id": doc.tenant_id, "document_id": doc.id, "version": doc.version,
                         "chunk_id": r.id} for r in rows])
        doc.chunk_count = len(rows)
        doc.page_count = len(pages) if ext == ".pdf" else None
        doc.char_count = sum(len(p.text) for p in pages)
        doc.flagged_chunks = flagged
        doc.status, doc.error = "indexed", None
        if flagged:
            log.warning("Document %s: %d chunk(s) matched prompt-injection patterns (content not logged)",
                        doc.id, flagged)

    def _remove_vectors_and_chunks(self, doc: Document) -> None:
        self.store.delete(self.store.docs, where={"document_id": doc.id})
        self.db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).delete()

    # ------------------------------------------------------------ public API
    def upload(self, tenant: str, filename: str, data: bytes) -> tuple[Document, bool]:
        """Returns (document, created). Identical content already uploaded -> (existing, False)."""
        ext = validate_upload(filename, data, self.settings.max_upload_mb * 1_000_000)
        digest = hashlib.sha256(data).hexdigest()
        dup = self.db.scalars(select(Document).where(Document.tenant_id == tenant, Document.content_hash == digest)).first()
        if dup is not None:
            return dup, False

        name = safe_filename(filename)
        doc = Document(tenant_id=tenant, filename=name, content_hash=digest, size_bytes=len(data),
                       file_type=ext.lstrip("."), status="pending")
        self.db.add(doc)
        self.db.flush()
        path = self._storage_dir(tenant) / f"{doc.id}_v1{ext}"
        path.write_bytes(data)
        doc.stored_path = str(path.relative_to(self.settings.resolve(self.settings.documents_path)))
        try:
            self._index(doc, data, ext)
        except Exception:
            self.db.rollback()
            path.unlink(missing_ok=True)
            self.store.delete(self.store.docs, where={"document_id": doc.id})
            raise
        self.db.commit()
        return doc, True

    def update(self, tenant: str, doc_id: int, filename: str, data: bytes, cache) -> tuple[Document, int]:
        """Replace a document's content -> new version, re-index, invalidate cached answers.
        Returns (document, number_of_cache_entries_invalidated)."""
        doc = self.get(tenant, doc_id)
        ext = validate_upload(filename, data, self.settings.max_upload_mb * 1_000_000)
        digest = hashlib.sha256(data).hexdigest()
        if digest == doc.content_hash:
            raise AppError("The new file is identical to the current version.", 409, "unchanged")
        other = self.db.scalars(select(Document).where(Document.tenant_id == tenant, Document.content_hash == digest,
                                                       Document.id != doc.id)).first()
        if other is not None:
            raise AppError(f"This content is already uploaded as '{other.filename}'.", 409, "duplicate",
                           {"existing_id": other.id})
        self._remove_vectors_and_chunks(doc)
        doc.version += 1
        doc.content_hash, doc.size_bytes, doc.file_type = digest, len(data), ext.lstrip(".")
        doc.filename = safe_filename(filename)
        doc.updated_at = utcnow()
        path = self._storage_dir(tenant) / f"{doc.id}_v{doc.version}{ext}"
        path.write_bytes(data)
        doc.stored_path = str(path.relative_to(self.settings.resolve(self.settings.documents_path)))
        self.db.flush()
        try:
            self._index(doc, data, ext)
        except Exception:
            self.db.rollback()
            raise
        self.db.commit()
        n = cache.invalidate_for_document(tenant, doc.id, f"document '{doc.filename}' updated to v{doc.version}")
        return doc, n

    def delete(self, tenant: str, doc_id: int, cache) -> int:
        doc = self.get(tenant, doc_id)
        self._remove_vectors_and_chunks(doc)
        root = self.settings.resolve(self.settings.documents_path)
        for p in (root / tenant).glob(f"{doc.id}_v*"):
            p.unlink(missing_ok=True)
        name = doc.filename
        self.db.delete(doc)
        self.db.commit()
        return cache.invalidate_for_document(tenant, doc_id, f"document '{name}' deleted")

    def list(self, tenant: str) -> list[Document]:
        return list(self.db.scalars(select(Document).where(Document.tenant_id == tenant)
                                    .order_by(Document.created_at.desc())))

    def indexed_ids(self, tenant: str, requested: list[int] | None) -> list[int]:
        """Documents the caller may search. Unknown / other-tenant IDs are rejected."""
        q = select(Document.id).where(Document.tenant_id == tenant, Document.status == "indexed")
        ids = list(self.db.scalars(q))
        if requested:
            missing = set(requested) - set(ids)
            if missing:
                raise AppError(f"Unknown document id(s): {sorted(missing)}", 404, "not_found")
            return sorted(set(requested))
        return ids

    # ------------------------------------------------------------ retrieval
    def retrieve(self, tenant: str, vector: np.ndarray, document_ids: list[int], k: int,
                 min_score: float) -> list[RetrievedChunk]:
        if not document_ids:
            return []
        where = {"$and": [{"tenant_id": tenant}, {"document_id": {"$in": document_ids}}]}
        hits = self.store.query(self.store.docs, vector, k, where)
        out: list[RetrievedChunk] = []
        for h in hits:
            if h["similarity"] < min_score:
                continue
            chunk = self.db.get(DocumentChunk, int(h["metadata"]["chunk_id"]))
            if chunk is None or chunk.tenant_id != tenant:
                continue
            doc = chunk.document
            if doc.version != chunk.document_version:   # stale vector from an old version - never use
                continue
            out.append(RetrievedChunk(chunk.id, doc.id, doc.version, doc.filename, chunk.page, chunk.chunk_index,
                                      chunk.text, h["similarity"], bool(chunk.flagged)))
        return out
