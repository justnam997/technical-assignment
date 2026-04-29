"""Employee model — the searchable entity.

Indexes
-------
Every secondary index leads with `org_id` because it's the shard/tenant
key — Postgres can use the index for both filtered queries (by status,
location, etc.) and the unfiltered "all employees of org X" case.
See DESIGN.md ADR-007.
"""
from __future__ import annotations

import datetime as dt
import enum

from sqlalchemy import (
    Date,
    Enum,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EmployeeStatus(str, enum.Enum):
    ACTIVE = "active"
    NOT_STARTED = "not_started"
    TERMINATED = "terminated"


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id"), nullable=False
    )

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(50))

    status: Mapped[EmployeeStatus] = mapped_column(
        Enum(EmployeeStatus, name="employee_status"), nullable=False
    )
    hired_at: Mapped[dt.date | None] = mapped_column(Date)
    terminated_at: Mapped[dt.date | None] = mapped_column(Date)

    # FKs are nullable to allow "no department / no location" rows
    # (matches the UI in the spec).
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"))
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    position_id: Mapped[int | None] = mapped_column(ForeignKey("positions.id"))

    __table_args__ = (
        # Composite indexes lead with org_id (shard key).
        Index("ix_emp_org_status", "org_id", "status"),
        Index("ix_emp_org_location", "org_id", "location_id"),
        Index("ix_emp_org_company", "org_id", "company_id"),
        Index("ix_emp_org_department", "org_id", "department_id"),
        Index("ix_emp_org_position", "org_id", "position_id"),
        # Cursor pagination uses (org_id, id ASC).
        Index("ix_emp_org_id_asc", "org_id", "id"),
    )
