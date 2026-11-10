from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import embedder_dep, registry_dep, store_dep
from app.core.errors import AppError
from app.core.security import tenant_id
from app.database import get_db
from app.evaluation.compare import comparison_report, run_comparison
from app.models import Comparison
from app.schemas import CompareRequest

router = APIRouter(prefix="/compare", tags=["comparison"])


def _out(c: Comparison) -> dict:
    return {"id": c.id, "query": c.query_text, "document_ids": c.document_ids, "context": c.context,
            "results": c.results, "is_mock": c.is_mock, "created_at": c.created_at.isoformat()}


@router.post("")
def compare(body: CompareRequest, db: Session = Depends(get_db), tenant: str = Depends(tenant_id),
            store=Depends(store_dep), embedder=Depends(embedder_dep), registry=Depends(registry_dep)):
    return _out(run_comparison(db, store, embedder, registry, tenant, body.query, body.model_ids, body.document_ids,
                               body.reference_answer))


@router.get("")
def list_comparisons(db: Session = Depends(get_db), tenant: str = Depends(tenant_id)):
    rows = db.scalars(select(Comparison).where(Comparison.tenant_id == tenant)
                      .order_by(Comparison.created_at.desc()).limit(50))
    return [{"id": c.id, "query": c.query_text, "models": [r["model"] for r in c.results], "is_mock": c.is_mock,
             "created_at": c.created_at.isoformat()} for c in rows]


def _get(cid: int, db: Session, tenant: str) -> Comparison:
    c = db.get(Comparison, cid)
    if c is None or c.tenant_id != tenant:
        raise AppError("Comparison not found.", 404, "not_found")
    return c


@router.get("/{cid}")
def get_comparison(cid: int, db: Session = Depends(get_db), tenant: str = Depends(tenant_id)):
    return _out(_get(cid, db, tenant))


@router.get("/{cid}/report", response_class=PlainTextResponse)
def report(cid: int, db: Session = Depends(get_db), tenant: str = Depends(tenant_id)):
    return PlainTextResponse(comparison_report(_get(cid, db, tenant)), media_type="text/markdown",
                             headers={"Content-Disposition": f'attachment; filename="nexus-comparison-{cid}.md"'})
