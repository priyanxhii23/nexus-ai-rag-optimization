"""Document Library API: upload, list, inspect, update (new version), delete."""
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.analytics.events import emit
from app.api.deps import embedder_dep, store_dep
from app.cache.semantic_cache import SemanticCache
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import tenant_id
from app.database import get_db
from app.models import Document, DocumentChunk
from app.rag.service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])
MAX_FILES = 20


def _doc(d: Document) -> dict:
    return {"id": d.id, "filename": d.filename, "file_type": d.file_type, "version": d.version,
            "size_bytes": d.size_bytes, "chunk_count": d.chunk_count, "page_count": d.page_count,
            "char_count": d.char_count, "status": d.status, "flagged_chunks": d.flagged_chunks or 0,
            "content_hash": d.content_hash[:12], "error": d.error,
            "created_at": d.created_at.isoformat(), "updated_at": d.updated_at.isoformat()}


async def _read(upload: UploadFile) -> bytes:
    limit = get_settings().max_upload_mb * 1_000_000
    data = await upload.read(limit + 1)
    if len(data) > limit:
        raise AppError(f"'{upload.filename}' is larger than the {limit // 1_000_000} MB limit.", 413, "file_too_large")
    return data


@router.get("")
def list_documents(db: Session = Depends(get_db), tenant: str = Depends(tenant_id), store=Depends(store_dep),
                   embedder=Depends(embedder_dep)):
    return [_doc(d) for d in DocumentService(db, store, embedder).list(tenant)]


@router.post("", status_code=201)
async def upload_documents(files: list[UploadFile] = File(...), db: Session = Depends(get_db),
                           tenant: str = Depends(tenant_id), store=Depends(store_dep), embedder=Depends(embedder_dep)):
    if len(files) > MAX_FILES:
        raise AppError(f"Upload at most {MAX_FILES} files at a time.", 422, "too_many_files")
    svc = DocumentService(db, store, embedder)
    results = []
    for f in files:
        name = f.filename or "document"
        try:
            data = await _read(f)
            doc, created = svc.upload(tenant, name, data)
            results.append({"filename": name, "status": "created" if created else "duplicate",
                            "document": _doc(doc),
                            "message": None if created else f"Identical content already uploaded as '{doc.filename}'."})
            if created:
                emit(db, "document_uploaded", f"Indexed '{doc.filename}' ({doc.chunk_count} chunks)", tenant=tenant,
                     data={"document_id": doc.id, "chunks": doc.chunk_count, "flagged": doc.flagged_chunks})
                if doc.flagged_chunks:
                    emit(db, "security", f"'{doc.filename}': {doc.flagged_chunks} chunk(s) contain instruction-like "
                         "text; they are wrapped as untrusted data", tenant=tenant, level="warning",
                         data={"document_id": doc.id})
        except AppError as e:
            results.append({"filename": name, "status": "rejected", "message": e.message, "code": e.code})
    return {"results": results}


@router.get("/{doc_id}")
def get_document(doc_id: int, db: Session = Depends(get_db), tenant: str = Depends(tenant_id),
                 store=Depends(store_dep), embedder=Depends(embedder_dep)):
    return _doc(DocumentService(db, store, embedder).get(tenant, doc_id))


@router.get("/{doc_id}/chunks")
def get_chunks(doc_id: int, limit: int = 50, offset: int = 0, db: Session = Depends(get_db),
               tenant: str = Depends(tenant_id), store=Depends(store_dep), embedder=Depends(embedder_dep)):
    doc = DocumentService(db, store, embedder).get(tenant, doc_id)
    q = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).order_by(DocumentChunk.chunk_index)
    return {"total": q.count(), "chunks": [
        {"index": c.chunk_index, "page": c.page, "text": c.text, "chars": len(c.text), "flagged": bool(c.flagged)}
        for c in q.offset(max(0, offset)).limit(min(max(1, limit), 200))]}


@router.put("/{doc_id}")
async def update_document(doc_id: int, file: UploadFile = File(...), db: Session = Depends(get_db),
                          tenant: str = Depends(tenant_id), store=Depends(store_dep), embedder=Depends(embedder_dep)):
    data = await _read(file)
    doc, invalidated = DocumentService(db, store, embedder).update(tenant, doc_id, file.filename or "document", data,
                                                                    SemanticCache(db, store))
    emit(db, "document_updated", f"'{doc.filename}' updated to v{doc.version}; {invalidated} cached answer(s) invalidated",
         tenant=tenant, data={"document_id": doc.id, "version": doc.version, "invalidated": invalidated})
    return {"document": _doc(doc), "cache_entries_invalidated": invalidated}


@router.delete("/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db), tenant: str = Depends(tenant_id),
                    store=Depends(store_dep), embedder=Depends(embedder_dep)):
    invalidated = DocumentService(db, store, embedder).delete(tenant, doc_id, SemanticCache(db, store))
    emit(db, "document_deleted", f"Document {doc_id} deleted; {invalidated} cached answer(s) invalidated",
         tenant=tenant, data={"document_id": doc_id, "invalidated": invalidated})
    return {"deleted": doc_id, "cache_entries_invalidated": invalidated}
