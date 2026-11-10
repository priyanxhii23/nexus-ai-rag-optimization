from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.events import emit
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import tenant_id
from app.database import get_db
from app.evaluation import benchmark
from app.evaluation.datasets import list_datasets, load_dataset
from app.models import BenchmarkRun
from app.schemas import BenchmarkCreate

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])


def _run(r: BenchmarkRun, results: bool = False) -> dict:
    out = {"id": r.id, "name": r.name, "dataset": r.dataset, "configs": r.configs, "settings": r.settings,
           "status": r.status, "progress": r.progress, "is_simulated": r.is_simulated, "summary": r.summary,
           "error": r.error, "created_at": r.created_at.isoformat(),
           "finished_at": r.finished_at.isoformat() if r.finished_at else None}
    if results:
        out["results"] = [{"config": x.config, "question_id": x.question_id, "question": x.question,
                           "cache_status": x.cache_status, "model": x.model, "complexity": x.complexity,
                           "latency_ms": x.latency_ms, "input_tokens": x.input_tokens, "output_tokens": x.output_tokens,
                           "cost_usd": x.cost_usd, "llm_called": x.llm_called, "retrieval_hit": x.retrieval_hit,
                           "correctness": x.correctness, "faithfulness": x.faithfulness} for x in r.results]
    return out


@router.get("/datasets")
def datasets():
    return list_datasets()


@router.post("/runs", status_code=202)
def create_run(body: BenchmarkCreate, db: Session = Depends(get_db), tenant: str = Depends(tenant_id)):
    try:
        ds = load_dataset(body.dataset)
    except KeyError:
        raise AppError("Unknown dataset.", 404, "not_found")
    if benchmark.is_running():
        raise AppError("A benchmark is already running. Wait for it to finish.", 409, "busy")
    s = get_settings()
    if not s.mock_mode and not body.confirm_cost:
        calls = len(ds["questions"]) * len(body.configs)
        raise AppError(f"This run will make up to {calls} paid LLM calls. Confirm the cost to continue.", 402,
                       "confirm_cost", {"max_llm_calls": calls})
    run = BenchmarkRun(tenant_id=tenant, name=body.name, dataset=body.dataset, configs=list(body.configs),
                       settings={"threshold": body.threshold}, status="queued", is_simulated=s.mock_mode)
    db.add(run)
    db.commit()
    emit(db, "benchmark_queued", f"Benchmark #{run.id} queued", tenant=tenant)
    benchmark.start_run(run.id)
    return _run(run)


@router.get("/runs")
def runs(db: Session = Depends(get_db), tenant: str = Depends(tenant_id)):
    rows = db.scalars(select(BenchmarkRun).where(BenchmarkRun.tenant_id == tenant)
                      .order_by(BenchmarkRun.created_at.desc()).limit(50))
    return [_run(r) for r in rows]


def _get(run_id: int, db: Session, tenant: str) -> BenchmarkRun:
    r = db.get(BenchmarkRun, run_id)
    if r is None or r.tenant_id != tenant:
        raise AppError("Benchmark run not found.", 404, "not_found")
    return r


@router.get("/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db), tenant: str = Depends(tenant_id)):
    return _run(_get(run_id, db, tenant), results=True)


@router.get("/runs/{run_id}/report")
def get_report(run_id: int, format: str = Query("md", pattern="^(md|csv)$"), db: Session = Depends(get_db),
               tenant: str = Depends(tenant_id)):
    r = _get(run_id, db, tenant)
    body, media = benchmark.report(r, format)
    return Response(body, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="nexus-benchmark-{run_id}.{format}"'})


@router.delete("/runs/{run_id}")
def delete_run(run_id: int, db: Session = Depends(get_db), tenant: str = Depends(tenant_id)):
    r = _get(run_id, db, tenant)
    if r.status in ("queued", "running"):
        raise AppError("Cannot delete a running benchmark.", 409, "busy")
    db.delete(r)
    db.commit()
    return {"deleted": run_id}
