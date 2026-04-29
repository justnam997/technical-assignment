"""seed demo hr data

Revision ID: 0002_seed_demo_hr_data
Revises: 0001_create_hr_schema
Create Date: 2026-04-29 04:48:53.599450

"""
import datetime as dt
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002_seed_demo_hr_data'
down_revision: Union[str, None] = '0001_create_hr_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


employee_status = sa.Enum(
    'ACTIVE',
    'NOT_STARTED',
    'TERMINATED',
    name='employee_status',
)

organizations = sa.table(
    'organizations',
    sa.column('id', sa.String),
    sa.column('name', sa.String),
    sa.column('column_config', sa.JSON),
)
locations = sa.table(
    'locations',
    sa.column('id', sa.Integer),
    sa.column('org_id', sa.String),
    sa.column('name', sa.String),
    sa.column('city', sa.String),
    sa.column('country', sa.String),
)
companies = sa.table(
    'companies',
    sa.column('id', sa.Integer),
    sa.column('org_id', sa.String),
    sa.column('name', sa.String),
)
departments = sa.table(
    'departments',
    sa.column('id', sa.Integer),
    sa.column('org_id', sa.String),
    sa.column('name', sa.String),
)
positions = sa.table(
    'positions',
    sa.column('id', sa.Integer),
    sa.column('org_id', sa.String),
    sa.column('title', sa.String),
)
employees = sa.table(
    'employees',
    sa.column('id', sa.Integer),
    sa.column('org_id', sa.String),
    sa.column('first_name', sa.String),
    sa.column('last_name', sa.String),
    sa.column('email', sa.String),
    sa.column('phone', sa.String),
    sa.column('status', employee_status),
    sa.column('hired_at', sa.Date),
    sa.column('terminated_at', sa.Date),
    sa.column('location_id', sa.Integer),
    sa.column('company_id', sa.Integer),
    sa.column('department_id', sa.Integer),
    sa.column('position_id', sa.Integer),
)

ORG_ALPHA_CONFIG = {
    'version': 1,
    'list_columns': [
        'first_name',
        'last_name',
        'contact_info',
        'department',
        'position',
        'location',
        'status',
    ],
}

ORG_BETA_CONFIG = {
    'version': 1,
    'list_columns': ['first_name', 'last_name', 'department', 'location', 'position'],
}


def _employee_rows() -> list[dict[str, object]]:
    first_names = ['Ada', 'Linus', 'Grace', 'Edsger', 'Donald', 'Margaret']
    last_names = ['Lovelace', 'Torvalds', 'Hopper', 'Dijkstra', 'Knuth', 'Hamilton']
    statuses = ['ACTIVE', 'NOT_STARTED', 'TERMINATED']
    rows: list[dict[str, object]] = []

    for org_index, org_id in enumerate(('org_alpha', 'org_beta')):
        id_offset = org_index * 50
        related_offset = org_index * 2

        for i in range(50):
            rows.append(
                {
                    'id': id_offset + i + 1,
                    'org_id': org_id,
                    'first_name': first_names[i % len(first_names)],
                    'last_name': f'{last_names[i % len(last_names)]}{i}',
                    'email': f'emp{i}@{org_id}.example',
                    'phone': f'+65-{10000000 + id_offset + i}',
                    'status': statuses[i % len(statuses)],
                    'hired_at': dt.date(2020 + i % 5, 1, 1),
                    'terminated_at': None,
                    'location_id': related_offset + (i % 2) + 1,
                    'company_id': org_index + 1,
                    'department_id': related_offset + (i % 2) + 1,
                    'position_id': related_offset + (i % 2) + 1,
                }
            )

    return rows


def _sync_sequences() -> None:
    bind = op.get_bind()
    for table_name in ('locations', 'companies', 'departments', 'positions', 'employees'):
        bind.execute(
            sa.text(
                'SELECT setval('
                "pg_get_serial_sequence(:table_name, 'id'), "
                f'(SELECT MAX(id) FROM {table_name})'
                ')'
            ),
            {'table_name': table_name},
        )


def upgrade() -> None:
    op.bulk_insert(
        organizations,
        [
            {'id': 'org_alpha', 'name': 'Alpha Inc.', 'column_config': ORG_ALPHA_CONFIG},
            {'id': 'org_beta', 'name': 'Beta Co.', 'column_config': ORG_BETA_CONFIG},
        ],
    )
    op.bulk_insert(
        locations,
        [
            {
                'id': 1,
                'org_id': 'org_alpha',
                'name': 'HQ',
                'city': 'Singapore',
                'country': 'SG',
            },
            {
                'id': 2,
                'org_id': 'org_alpha',
                'name': 'EU Hub',
                'city': 'Berlin',
                'country': 'DE',
            },
            {
                'id': 3,
                'org_id': 'org_beta',
                'name': 'HQ',
                'city': 'Singapore',
                'country': 'SG',
            },
            {
                'id': 4,
                'org_id': 'org_beta',
                'name': 'EU Hub',
                'city': 'Berlin',
                'country': 'DE',
            },
        ],
    )
    op.bulk_insert(
        companies,
        [
            {'id': 1, 'org_id': 'org_alpha', 'name': 'Org_Alpha Holdings'},
            {'id': 2, 'org_id': 'org_beta', 'name': 'Org_Beta Holdings'},
        ],
    )
    op.bulk_insert(
        departments,
        [
            {'id': 1, 'org_id': 'org_alpha', 'name': 'Engineering'},
            {'id': 2, 'org_id': 'org_alpha', 'name': 'Sales'},
            {'id': 3, 'org_id': 'org_beta', 'name': 'Engineering'},
            {'id': 4, 'org_id': 'org_beta', 'name': 'Sales'},
        ],
    )
    op.bulk_insert(
        positions,
        [
            {'id': 1, 'org_id': 'org_alpha', 'title': 'Senior Engineer'},
            {'id': 2, 'org_id': 'org_alpha', 'title': 'Account Executive'},
            {'id': 3, 'org_id': 'org_beta', 'title': 'Senior Engineer'},
            {'id': 4, 'org_id': 'org_beta', 'title': 'Account Executive'},
        ],
    )
    op.bulk_insert(employees, _employee_rows())
    _sync_sequences()


def downgrade() -> None:
    org_filter = "('org_alpha', 'org_beta')"
    op.execute(sa.text(f'DELETE FROM employees WHERE org_id IN {org_filter}'))
    op.execute(sa.text(f'DELETE FROM positions WHERE org_id IN {org_filter}'))
    op.execute(sa.text(f'DELETE FROM departments WHERE org_id IN {org_filter}'))
    op.execute(sa.text(f'DELETE FROM companies WHERE org_id IN {org_filter}'))
    op.execute(sa.text(f'DELETE FROM locations WHERE org_id IN {org_filter}'))
    op.execute(sa.text(f'DELETE FROM organizations WHERE id IN {org_filter}'))
