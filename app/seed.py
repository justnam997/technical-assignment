"""Seed script — creates two orgs with different column configs and ~100 employees.

Run via: `python -m app.seed`. Idempotent — safe to re-run.

The two orgs simulate the dynamic-column-config story:
  - org_alpha shows: first_name, last_name, contact_info, department, position, location, status
  - org_beta  shows: first_name, last_name, department, location, position
"""
from __future__ import annotations

import asyncio
import datetime as dt
import random
from itertools import cycle

from sqlalchemy import select

from app.database import SessionLocal, engine, Base
from app.models import (
    Company,
    Department,
    Employee,
    EmployeeStatus,
    Location,
    Organization,
    Position,
)


ORG_ALPHA_CONFIG = {
    "version": 1,
    "list_columns": [
        "first_name",
        "last_name",
        "contact_info",
        "department",
        "position",
        "location",
        "status",
    ],
}

ORG_BETA_CONFIG = {
    "version": 1,
    "list_columns": ["first_name", "last_name", "department", "location", "position"],
}


async def seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        existing = (
            await session.execute(select(Organization).where(Organization.id == "org_alpha"))
        ).scalar_one_or_none()
        if existing is not None:
            print("seed: already populated, skipping")
            return

        alpha = Organization(id="org_alpha", name="Alpha Inc.", column_config=ORG_ALPHA_CONFIG)
        beta = Organization(id="org_beta", name="Beta Co.", column_config=ORG_BETA_CONFIG)
        session.add_all([alpha, beta])
        await session.flush()

        for org_id in ("org_alpha", "org_beta"):
            locations = [
                Location(org_id=org_id, name="HQ", city="Singapore", country="SG"),
                Location(org_id=org_id, name="EU Hub", city="Berlin", country="DE"),
            ]
            departments = [
                Department(org_id=org_id, name="Engineering"),
                Department(org_id=org_id, name="Sales"),
            ]
            companies = [
                Company(org_id=org_id, name=f"{org_id.title()} Holdings"),
            ]
            positions = [
                Position(org_id=org_id, title="Senior Engineer"),
                Position(org_id=org_id, title="Account Executive"),
            ]
            session.add_all(locations + departments + companies + positions)
            await session.flush()

            statuses = cycle([EmployeeStatus.ACTIVE, EmployeeStatus.NOT_STARTED, EmployeeStatus.TERMINATED])
            first_names = ["Ada", "Linus", "Grace", "Edsger", "Donald", "Margaret"]
            last_names = ["Lovelace", "Torvalds", "Hopper", "Dijkstra", "Knuth", "Hamilton"]
            for i in range(50):
                emp = Employee(
                    org_id=org_id,
                    first_name=random.choice(first_names),
                    last_name=random.choice(last_names) + str(i),
                    email=f"emp{i}@{org_id}.example",
                    phone=f"+65-{random.randint(10000000, 99999999)}",
                    status=next(statuses),
                    hired_at=dt.date(2020 + i % 5, 1, 1),
                    location_id=random.choice(locations).id,
                    company_id=companies[0].id,
                    department_id=random.choice(departments).id,
                    position_id=random.choice(positions).id,
                )
                session.add(emp)

        await session.commit()
        print("seed: populated org_alpha + org_beta")


if __name__ == "__main__":
    asyncio.run(seed())
