"""Analytics endpoints - computed from recorded rows. Fresh install -> has_data=false."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.analytics.metrics import cost_report, overview
from app.core.security import tenant_id
from app.database import get_db

router = APIRouter(prefix="/metrics", tags=["analytics"])


@router.get("/overview")
def get_overview(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db), tenant: str = Depends(tenant_id)):
    return overview(db, tenant, days)


@router.get("/costs")
def get_costs(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db), tenant: str = Depends(tenant_id)):
    return cost_report(db, tenant, days)
