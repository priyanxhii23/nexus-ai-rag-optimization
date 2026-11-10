"""Question answering API (blocking JSON and streaming Server-Sent Events)."""
import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import embedder_dep, registry_dep, store_dep
from app.core.errors import AppError
from app.core.logging import get_logger
from app.core.security import tenant_id
from app.database import SessionLocal, get_db
from app.models import RequestLog
from app.router.model_router import NoModelAvailable, route
from app.router.query_intelligence import analyze
from app.schemas import AnalyzeRequest, QueryRequest
from app.services.pipeline import QueryInput, QueryPipeline, serialize_request
from app.services.runtime_settings import get_runtime

router = APIRouter(prefix="/query", tags=["query"])
log = get_logger("api.query")


def _input(body: QueryRequest, tenant: str) -> QueryInput:
    return QueryInput(tenant=tenant, query=body.query, document_ids=body.document_ids, model_id=body.model_id,
                      mode=body.mode, conversation_id=body.conversation_id)


@router.post("")
def ask(body: QueryRequest, db: Session = Depends(get_db), tenant: str = Depends(tenant_id), store=Depends(store_dep),
        embedder=Depends(embedder_dep), registry=Depends(registry_dep)):
    return QueryPipeline(db, store, embedder, registry).execute(_input(body, tenant))


@router.post("/stream")
def ask_stream(body: QueryRequest, tenant: str = Depends(tenant_id), store=Depends(store_dep),
               embedder=Depends(embedder_dep), registry=Depends(registry_dep)):
    """Server-Sent Events: started -> stage/cache/analysis/retrieval/routing -> token* -> done (or error)."""
    inp = _input(body, tenant)

    def events():
        db = SessionLocal()   # own session: lives exactly as long as the stream
        try:
            for ev in QueryPipeline(db, store, embedder, registry).run(inp):
                yield f"data: {json.dumps(ev, default=str)}\n\n"
        except AppError as e:
            yield f"data: {json.dumps({'type': 'error', 'code': e.code, 'message': e.message})}\n\n"
        except Exception as e:  # noqa: BLE001
            log.exception("Streaming query failed: %s", type(e).__name__)
            yield f"data: {json.dumps({'type': 'error', 'code': 'internal_error', 'message': 'The server failed while answering. See data/logs/nexus.log.'})}\n\n"
        finally:
            db.close()

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/analyze")
def analyze_query(body: AnalyzeRequest, db: Session = Depends(get_db), registry=Depends(registry_dep)):
    """Query intelligence + routing preview. Does not call any LLM."""
    a = analyze(body.query, has_documents=body.has_documents)
    rt = get_runtime(db)
    available = registry.available(db)
    try:
        decision = route(a, available, rt["routing_strategy"], body.model_id).to_dict()
    except NoModelAvailable as e:
        decision = {"error": str(e)}
    return {"analysis": a.to_dict(), "routing": decision, "strategy": rt["routing_strategy"]}


@router.get("/history")
def history(conversation_id: str | None = None, limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_db),
            tenant: str = Depends(tenant_id)):
    q = select(RequestLog).where(RequestLog.tenant_id == tenant, RequestLog.source == "playground")
    if conversation_id:
        q = q.where(RequestLog.conversation_id == conversation_id)
    rows = list(db.scalars(q.order_by(RequestLog.created_at.desc()).limit(limit)))
    return [serialize_request(r) for r in reversed(rows)]


@router.get("/{request_id}")
def get_request(request_id: int, db: Session = Depends(get_db), tenant: str = Depends(tenant_id)):
    r = db.get(RequestLog, request_id)
    if r is None or r.tenant_id != tenant:
        raise AppError("Request not found.", 404, "not_found")
    out = serialize_request(r)
    out["llm_calls"] = [{"provider": c.provider, "model": c.model, "success": c.success, "error_type": c.error_type,
                         "input_tokens": c.input_tokens, "output_tokens": c.output_tokens,
                         "usage_source": c.usage_source, "cost_usd": c.estimated_cost_usd,
                         "cost_status": c.cost_status, "latency_ms": c.latency_ms} for c in r.llm_calls]
    return out
