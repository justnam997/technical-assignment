"""Employee search service — orchestrates repos + business rules.

The service is what's tested at the unit level — it composes repos
(mocked in tests) and applies the column-config business rule.
"""
from __future__ import annotations

import base64

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.allowed_fields import AllowedField, expand_columns
from app.repositories.employee import EmployeeRepository
from app.repositories.organization import OrganizationRepository
from app.schemas.column_config import ColumnConfig
from app.schemas.employee import SearchPage, build_response_model
from app.schemas.filters import SearchFilters


class EmployeeSearchService:
    def __init__(self, session: AsyncSession) -> None:
        self.employee_repo = EmployeeRepository(session)
        self.org_repo = OrganizationRepository(session)

    async def search(self, filters: SearchFilters) -> SearchPage:
        # 1. Resolve which columns this org wants.
        org = await self.org_repo.get_current()
        if org is None:
            # Tenant header points at a non-existent org.
            return SearchPage(results=[], next_cursor=None, has_more=False)

        config = ColumnConfig.model_validate(org.column_config or {"list_columns": ["first_name", "last_name"]})
        columns: list[AllowedField] = expand_columns(config.list_columns)

        if not columns:
            # Misconfigured org — empty allowed columns. Don't leak default fields.
            return SearchPage(results=[], next_cursor=None, has_more=False)

        # 2. Decode cursor.
        decoded_cursor = self._decode_cursor(filters.cursor)
        decoded_filters = filters.model_copy(update={"cursor": decoded_cursor})

        # 3. Run query.
        rows, next_cursor_id = await self.employee_repo.search(decoded_filters, columns)

        # 4. Project to dynamic Pydantic model — defense in depth: even
        #    if the repo accidentally returned an extra column, the
        #    model has `extra="forbid"` so it'd raise.
        model_cls = build_response_model(tuple(columns))
        # Rows always include `id` for the cursor; if `id` isn't in the
        # org's columns, drop it from the response payload.
        emit_id = AllowedField.ID in columns
        validated = []
        for row in rows:
            payload = dict(row)
            if not emit_id:
                payload.pop("id", None)
            validated.append(model_cls.model_validate(payload).model_dump(exclude_none=False))

        return SearchPage(
            results=validated,
            next_cursor=self._encode_cursor(next_cursor_id),
            has_more=next_cursor_id is not None,
        )

    @staticmethod
    def _encode_cursor(last_id: int | None) -> str | None:
        if last_id is None:
            return None
        return base64.urlsafe_b64encode(str(last_id).encode()).decode()

    @staticmethod
    def _decode_cursor(cursor: str | None) -> str | None:
        if not cursor:
            return None
        try:
            return base64.urlsafe_b64decode(cursor.encode()).decode()
        except Exception:
            # Bad cursor: treat as start of list. (We could raise 400; this
            # is a UX call — the spec didn't mandate strict cursor validation.)
            return None
