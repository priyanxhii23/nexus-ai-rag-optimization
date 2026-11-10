from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.analytics.metrics import monitoring_stats
from app.core.security import tenant_id
from app.database import get_db
from app.models import SystemEvent

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/events")
def events(after_id: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500), type: str | None = None,
           level: str | None = None, db: Session = Depends(get_db), tenant: str = Depends(tenant_id)):
    """Poll with ?after_id=<last id you have> to receive only new events."""
    q = select(SystemEvent).where(or_(SystemEvent.tenant_id == tenant, SystemEvent.tenant_id.is_(None)))
    if after_id:
        q = q.where(SystemEvent.id > after_id).order_by(SystemEvent.id.asc())
    else:
        q = q.order_by(SystemEvent.id.desc())
    if type:
        q = q.where(SystemEvent.type == type)
    if level:
        q = q.where(SystemEvent.level == level)
    rows = list(db.scalars(q.limit(limit)))
    if not after_id:
        rows.reverse()
    return [{"id": e.id, "type": e.type, "level": e.level, "message": e.message, "request_id": e.request_id,
             "data": e.data, "created_at": e.created_at.isoformat()} for e in rows]


@router.get("/stats")
def stats(db: Session = Depends(get_db), tenant: str = Depends(tenant_id)):
    return monitoring_stats(db, tenant)
