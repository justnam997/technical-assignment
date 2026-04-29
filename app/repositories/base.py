"""Tenant-safe repository base class.

Every concrete repo inherits from this. Two protections:

  1. The constructor stores the session — no method may bring its own.
  2. `_org_filter()` is the only way to scope to a tenant. Concrete
     repos must build their queries by ANDing this clause in. A code
     review that approves a query without `_org_filter` is a bug.
"""
from __future__ import annotations

from sqlalchemy import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import current_org_id


class TenantSafeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _org_filter(org_id_column: ColumnElement) -> ColumnElement:
        """Return a SQLAlchemy filter clause that scopes by current tenant.

        Raises TenantContextMissing if used outside a request.
        """
        return org_id_column == current_org_id()
