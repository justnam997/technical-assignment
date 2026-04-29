"""Employee repository — SQL only, no business logic.

Performance choices (millions of rows):
  - Cursor pagination: WHERE id > :last_id ORDER BY id LIMIT N+1
  - Projection via with_only_columns — fetch only what the org asks for
  - Joins built lazily — only when a related field is requested
"""
from __future__ import annotations

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.orm import aliased

from app.constants.allowed_fields import AllowedField
from app.models.company import Company
from app.models.department import Department
from app.models.employee import Employee
from app.models.location import Location
from app.models.position import Position
from app.repositories.base import TenantSafeRepository
from app.schemas.filters import SearchFilters


# Map response field → SQL expression. Keys are AllowedField values.
# This is the single source of truth for "how do I get this column from
# the DB?" — adding a new field means: (1) AllowedField enum,
# (2) entry here, (3) entry in `_FIELD_TYPES` in schemas/employee.py.
def _build_projection_map() -> dict[AllowedField, "tuple"]:
    """Return mapping field → (sql_expr, joins_required).

    `joins_required` is a tuple of join targets to add when this field
    is in the projection. We avoid hard-coding all joins — only join
    what we actually need.
    """
    LocAlias = aliased(Location)
    CompAlias = aliased(Company)
    DeptAlias = aliased(Department)
    PosAlias = aliased(Position)

    return {
        # Employee table — no joins
        AllowedField.ID: (Employee.id.label("id"), ()),
        AllowedField.FIRST_NAME: (Employee.first_name.label("first_name"), ()),
        AllowedField.LAST_NAME: (Employee.last_name.label("last_name"), ()),
        AllowedField.EMAIL: (Employee.email.label("email"), ()),
        AllowedField.PHONE: (Employee.phone.label("phone"), ()),
        AllowedField.STATUS: (Employee.status.label("status"), ()),
        AllowedField.HIRED_AT: (Employee.hired_at.label("hired_at"), ()),
        AllowedField.TERMINATED_AT: (Employee.terminated_at.label("terminated_at"), ()),
        # Joined fields
        AllowedField.LOCATION_NAME: (
            LocAlias.name.label("location_name"),
            ((LocAlias, Employee.location_id == LocAlias.id),),
        ),
        AllowedField.LOCATION_CITY: (
            LocAlias.city.label("location_city"),
            ((LocAlias, Employee.location_id == LocAlias.id),),
        ),
        AllowedField.LOCATION_COUNTRY: (
            LocAlias.country.label("location_country"),
            ((LocAlias, Employee.location_id == LocAlias.id),),
        ),
        AllowedField.COMPANY_NAME: (
            CompAlias.name.label("company_name"),
            ((CompAlias, Employee.company_id == CompAlias.id),),
        ),
        AllowedField.DEPARTMENT_NAME: (
            DeptAlias.name.label("department_name"),
            ((DeptAlias, Employee.department_id == DeptAlias.id),),
        ),
        AllowedField.POSITION_TITLE: (
            PosAlias.title.label("position_title"),
            ((PosAlias, Employee.position_id == PosAlias.id),),
        ),
    }


class EmployeeRepository(TenantSafeRepository):
    async def search(
        self,
        filters: SearchFilters,
        columns: list[AllowedField],
    ) -> tuple[list[dict], int | None]:
        """Run the search.

        Returns (rows_as_dicts, next_cursor_id). `next_cursor_id` is None
        when the page is the last one.
        """
        # Always need ID (for cursor) even if not requested.
        select_fields = list(dict.fromkeys([AllowedField.ID, *columns]))

        proj_map = _build_projection_map()
        sql_exprs = []
        joins_to_add: list = []
        seen_join_targets: set = set()

        for field in select_fields:
            expr, joins = proj_map[field]
            sql_exprs.append(expr)
            for target, on_clause in joins:
                # Dedupe joins on the alias identity.
                if target not in seen_join_targets:
                    joins_to_add.append((target, on_clause))
                    seen_join_targets.add(target)

        stmt: Select = select(*sql_exprs).select_from(Employee)
        for target, on_clause in joins_to_add:
            stmt = stmt.outerjoin(target, on_clause)

        # Tenant filter — required.
        stmt = stmt.where(self._org_filter(Employee.org_id))

        # Apply user filters.
        stmt = self._apply_filters(stmt, filters)

        # Cursor pagination.
        if filters.cursor is not None:
            try:
                last_id = int(filters.cursor)
            except ValueError:
                last_id = 0
            stmt = stmt.where(Employee.id > last_id)

        limit = filters.normalised_limit()
        # Fetch one extra to determine has_more.
        stmt = stmt.order_by(Employee.id.asc()).limit(limit + 1)

        result = await self.session.execute(stmt)
        rows = [dict(r._mapping) for r in result.all()]

        next_cursor_id: int | None = None
        if len(rows) > limit:
            extra = rows.pop()  # noqa: F841 — drop the peek row
            # The cursor is the last row of the returned page.
            next_cursor_id = rows[-1]["id"]

        return rows, next_cursor_id

    @staticmethod
    def _apply_filters(stmt: Select, f: SearchFilters) -> Select:
        if f.q:
            pattern = f"%{f.q}%"
            stmt = stmt.where(
                or_(Employee.first_name.ilike(pattern), Employee.last_name.ilike(pattern))
            )
        if f.statuses:
            stmt = stmt.where(Employee.status.in_(f.statuses))
        if f.location_ids:
            stmt = stmt.where(Employee.location_id.in_(f.location_ids))
        if f.company_ids:
            stmt = stmt.where(Employee.company_id.in_(f.company_ids))
        if f.department_ids:
            stmt = stmt.where(Employee.department_id.in_(f.department_ids))
        if f.position_ids:
            stmt = stmt.where(Employee.position_id.in_(f.position_ids))
        return stmt
