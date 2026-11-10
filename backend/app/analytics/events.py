"""System event log - the data behind Live Monitoring.

Events describe what happened (ids, scores, timings, models), never the
content of documents or answers.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import SystemEvent

log = get_logger("events")


def emit(db: Session, type_: str, message: str, *, tenant: str | None = "local", request_id: int | None = None,
         level: str = "info", data: dict | None = None, commit: bool = True) -> SystemEvent:
    ev = SystemEvent(tenant_id=tenant, request_id=request_id, type=type_, level=level, message=message[:500],
                     data=data)
    db.add(ev)
    if commit:
        db.commit()
    if level == "error":
        log.error("%s: %s", type_, message[:200])
    return ev
