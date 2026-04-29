"""Search filter schema — what the API accepts as query params."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.config import settings
from app.models.employee import EmployeeStatus


class SearchFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Free-text — searches first_name + last_name only (PII safety).
    q: str | None = Field(default=None, max_length=200)

    # Faceted filters (UI dropdowns from the spec).
    statuses: list[EmployeeStatus] | None = None
    location_ids: list[int] | None = None
    company_ids: list[int] | None = None
    department_ids: list[int] | None = None
    position_ids: list[int] | None = None

    # Pagination.
    cursor: str | None = None  # opaque base64 of last_id
    limit: int = Field(default_factory=lambda: settings.default_page_size)

    @classmethod
    def __get_validators__(cls):  # pragma: no cover  (legacy hook stub)
        yield from []

    def normalised_limit(self) -> int:
        return min(max(1, self.limit), settings.max_page_size)
