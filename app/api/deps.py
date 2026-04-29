"""FastAPI dependencies."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.rate_limiter import RateLimiter
from app.core.tenant import current_org_id, current_principal_id
from app.database import get_session
from app.services.employee import EmployeeSearchService


# A single process-wide limiter instance. State lives in its store.
_limiter = RateLimiter(
    capacity=settings.rate_limit_burst,
    refill_per_sec=float(settings.rate_limit_per_second),
)


def rate_limit(_: Request) -> None:
    """Enforce token-bucket rate limit, keyed by (org_id, principal)."""
    org_id = current_org_id()
    principal = current_principal_id()
    key = f"{org_id}:{principal}"
    if not _limiter.allow(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate limit exceeded",
            headers={"Retry-After": "1"},
        )


async def get_employee_service(
    session: AsyncSession = Depends(get_session),
) -> EmployeeSearchService:
    return EmployeeSearchService(session)
