"""GET /v1/employees/search — the only endpoint required by the spec."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_employee_service, rate_limit
from app.models.employee import EmployeeStatus
from app.schemas.employee import SearchPage
from app.schemas.filters import SearchFilters
from app.services.employee import EmployeeSearchService


router = APIRouter(prefix="/v1/employees", tags=["employees"])


@router.get(
    "/search",
    response_model=SearchPage,
    summary="Search employees in your organization",
    description=(
        "Returns a page of employees scoped to the caller's organization "
        "(via `X-Org-Id`). Result columns follow the org's configuration. "
        "Pagination is cursor-based; pass `cursor` from the previous "
        "response's `next_cursor` to fetch the next page."
    ),
    dependencies=[Depends(rate_limit)],
)
async def search_employees(
    q: str | None = Query(None, max_length=200, description="Free-text on name"),
    statuses: list[EmployeeStatus] | None = Query(None),
    location_ids: list[int] | None = Query(None),
    company_ids: list[int] | None = Query(None),
    department_ids: list[int] | None = Query(None),
    position_ids: list[int] | None = Query(None),
    cursor: str | None = Query(None, description="Opaque pagination cursor"),
    limit: int = Query(50, ge=1, le=100),
    service: EmployeeSearchService = Depends(get_employee_service),
) -> SearchPage:
    filters = SearchFilters(
        q=q,
        statuses=statuses,
        location_ids=location_ids,
        company_ids=company_ids,
        department_ids=department_ids,
        position_ids=position_ids,
        cursor=cursor,
        limit=limit,
    )
    return await service.search(filters)
