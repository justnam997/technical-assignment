# HR Employee Search API

A multi-tenant FastAPI service that powers an employee-search directory for an HR SaaS.
Each organization sees its own employees through a configurable column layout.

> Senior Backend technical assignment — see `DESIGN.md` for architecture decisions.

## Quick start

```bash
# Boot DB + API
docker compose up --build

# Open OpenAPI docs
open http://localhost:8000/docs

# Run the demo script (curls + a rate-limit trigger)
./demo.sh
```

## Project layout

```
app/
├── main.py              # FastAPI app factory + lifespan
├── config.py            # Settings (pydantic-settings)
├── database.py          # SQLAlchemy async engine + session
├── api/
│   ├── deps.py          # Tenant context dependency
│   └── v1/employees.py  # Search endpoint
├── services/
│   └── employee.py      # Business orchestration
├── repositories/
│   ├── base.py          # Tenant-safe base class
│   └── employee.py      # SQL with cursor pagination
├── models/              # SQLAlchemy 2.x ORM
│   ├── organization.py
│   ├── employee.py
│   ├── location.py
│   ├── company.py
│   ├── department.py
│   └── position.py
├── schemas/
│   ├── column_config.py # Per-org config + validator
│   └── employee.py      # Dynamic Pydantic via create_model
├── core/
│   ├── rate_limiter.py  # Token bucket — own implementation
│   └── tenant.py        # ContextVar + middleware
└── constants/
    └── allowed_fields.py # Whitelist (defense in depth)

alembic/                 # Migrations (kept outside app/)
tests/                   # pytest
demo.sh                  # End-to-end demo
```

## How the search works (one screen)

1. Request arrives at `GET /v1/employees/search` with auth header → `X-Org-Id`.
2. `TenantMiddleware` extracts `org_id`, sets it in a `ContextVar`.
3. The endpoint depends on `RateLimiter` (token bucket, keyed by `(org_id, user_id)`).
4. The service:
   - Loads the org's `column_config` (cached LRU keyed by `(org_id, version)`).
   - Validates config against `ALLOWED_FIELDS` whitelist (defense in depth).
   - Calls `EmployeeRepository.search(filters, columns, cursor)`.
5. The repository builds a SQL query with `with_only_columns` — projects only what the org needs. Cursor pagination via `(id > last_id ORDER BY id LIMIT N+1)`.
6. The service maps the rows to a Pydantic model built dynamically via `create_model` from the org's column list.
7. Response: `{ "results": [...], "next_cursor": "..." }`.

## Multi-tenant safety

Three layers of defense (see `tests/test_security_isolation.py`):

1. **`org_id` is a required parameter** on every repository method — there is no method that lets you fetch without it. This is enforced by the `TenantSafeRepository` base class.
2. **Tenant context middleware** extracts `org_id` from the auth header at request entry, before the service layer ever sees data.
3. **Whitelist filter** at serialization — even if a wrong field accidentally enters the query, it's filtered out by `ALLOWED_FIELDS`.

## Performance choices for "millions of users"

| Choice | Why |
|---|---|
| **Cursor (keyset) pagination** | OFFSET on millions is `O(offset)`. Cursor is `O(log n)`. |
| **Composite indexes** on `(org_id, status)`, `(org_id, location_id)`, `(org_id, department_id)`, `(org_id, position_id)` | Sharding key is `org_id`; every query starts with it. |
| **`with_only_columns` projection** | Don't fetch what the org's config doesn't ask for. |
| **`selectinload` for joins** | Avoid N+1; one extra query per related table, not per row. |
| **LRU cache for column-config & whitelist intersection** | Hot orgs don't re-validate their JSON on every request. |
| **In-memory token-bucket rate limiter (interface)** | Pluggable backend; production swap → Redis with a Lua-script atomic decrement. |

## Rate limiter

**Algorithm**: token bucket. Default: 10 requests / 1 second per `(org_id, principal)`, burst capacity 20.

**Why token bucket** (vs sliding window log / fixed window):

- Allows bursts that match dashboard usage (page through 5 screens fast, then idle).
- O(1) memory per key vs sliding-log's O(N) timestamps.
- Simpler than sliding-window-counter; close enough accuracy for dashboard ops.

**Limitation (called out)**: in-memory store loses state on restart. For production replace `InMemoryBucketStore` with `RedisBucketStore` (interface already abstracted).

## Run tests

```bash
docker compose run --rm api sh -c "alembic upgrade head && python -m app.seed && pytest -v --cov=app"
```

Migrations manage schema only. Demo data is seeded separately with `python -m app.seed`.
Production rollback example:

```bash
docker compose run --rm api alembic downgrade base
```

Key tests:

- `test_rate_limiter.py` — token refill, burst, denial under sustained load, threading correctness.
- `test_column_config.py` — whitelist enforcement, dynamic Pydantic model gen, malformed config rejection.
- `test_security_isolation.py` — org A cannot see org B rows even with crafted requests.
- `test_employee_search.py` — end-to-end with cursor pagination.

## OpenAPI

Auto-served at `/docs` (Swagger) and `/redoc` (ReDoc). Static export at `/openapi.json`.

## Trade-offs I'd revisit with more time

- Replace in-memory rate limiter with Redis backend.
- Add `BackgroundTasks`-based audit logger for search events.
- Replace per-request column-config validation with `(org_id, config_version)` cache.
- Add row-level security in Postgres for compliance-critical deployments.
- Migrate to async SQLAlchemy across the board (currently sync in some hot paths).

## License

Private — interview submission.
