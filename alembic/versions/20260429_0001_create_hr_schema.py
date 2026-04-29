"""create hr schema

Revision ID: 0001_create_hr_schema
Revises:
Create Date: 2026-04-29 00:01:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0001_create_hr_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


employee_status = postgresql.ENUM(
    "ACTIVE",
    "NOT_STARTED",
    "TERMINATED",
    name="employee_status",
    create_type=False,
    _create_events=False,
)


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE employee_status AS ENUM (
                'ACTIVE',
                'NOT_STARTED',
                'TERMINATED'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END
        $$;
        """
    )

    op.create_table(
        "organizations",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("column_config", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("org_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_companies_org_id"), "companies", ["org_id"])

    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("org_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_departments_org_id"), "departments", ["org_id"])

    op.create_table(
        "locations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("org_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_locations_org_id"), "locations", ["org_id"])

    op.create_table(
        "positions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("org_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_positions_org_id"), "positions", ["org_id"])

    op.create_table(
        "employees",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("org_id", sa.String(length=64), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("status", employee_status, nullable=False),
        sa.Column("hired_at", sa.Date(), nullable=True),
        sa.Column("terminated_at", sa.Date(), nullable=True),
        sa.Column("location_id", sa.Integer(), nullable=True),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("position_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["position_id"], ["positions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_emp_org_company", "employees", ["org_id", "company_id"])
    op.create_index("ix_emp_org_department", "employees", ["org_id", "department_id"])
    op.create_index("ix_emp_org_id_asc", "employees", ["org_id", "id"])
    op.create_index("ix_emp_org_location", "employees", ["org_id", "location_id"])
    op.create_index("ix_emp_org_position", "employees", ["org_id", "position_id"])
    op.create_index("ix_emp_org_status", "employees", ["org_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_emp_org_status", table_name="employees")
    op.drop_index("ix_emp_org_position", table_name="employees")
    op.drop_index("ix_emp_org_location", table_name="employees")
    op.drop_index("ix_emp_org_id_asc", table_name="employees")
    op.drop_index("ix_emp_org_department", table_name="employees")
    op.drop_index("ix_emp_org_company", table_name="employees")
    op.drop_table("employees")

    op.drop_index(op.f("ix_positions_org_id"), table_name="positions")
    op.drop_table("positions")

    op.drop_index(op.f("ix_locations_org_id"), table_name="locations")
    op.drop_table("locations")

    op.drop_index(op.f("ix_departments_org_id"), table_name="departments")
    op.drop_table("departments")

    op.drop_index(op.f("ix_companies_org_id"), table_name="companies")
    op.drop_table("companies")

    op.drop_table("organizations")
    op.execute("DROP TYPE IF EXISTS employee_status")
