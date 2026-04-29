"""Organization repository — read column_config (cached)."""
from __future__ import annotations

from sqlalchemy import select

from app.models.organization import Organization
from app.repositories.base import TenantSafeRepository


class OrganizationRepository(TenantSafeRepository):
    async def get_current(self) -> Organization | None:
        """Fetch the org row for the current tenant."""
        stmt = select(Organization).where(self._org_filter(Organization.id))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
