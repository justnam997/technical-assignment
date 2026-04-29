# DESIGN.md — Architecture Decision Record

> **Read this with the interviewer.** Each section is one decision, with the alternatives I considered and the trade-off.
> Format inspired by Michael Nygard's ADR.

---

## ADR-001: Layered architecture (api / service / repository / model)

**Decision**: Four-layer split — `api` (HTTP transport), `service` (business orchestration), `repository` (DB access), `model` (ORM).

**Alternatives considered**:
1. **Active record** — `Employee.find_by_org(...)` directly. Simpler for a 200-LoC project; bleeds DB concerns into business logic at scale.
2. **Hexagonal / ports-and-adapters** — Better isolation but heavy ceremony for a 4-hour exercise.

**Why this**: gives me a clean boundary for unit testing (mock the repo, test the service); future-proofs caching and read-replica routing without rewrites.

**Trade-off**: more files for trivial CRUD. Acceptable past ~10 entities.

---

## ADR-002: Cursor pagination over OFFSET

**Decision**: Keyset cursor on `(id ASC)` for the search endpoint. `next_cursor` is a base64-encoded `last_id`.

**Alternatives**:
1. **OFFSET/LIMIT** — User-friendly (`page=47`) but `O(offset)` scan. Spec says "millions of users" — at page 1000 of 50, Postgres scans 50K rows.
2. **Cursor + denormalized `total_count`** — Best of both worlds; needs a counter cache invalidation strategy.

**Why this**: HR directory UX is search-then-browse, not random-page-jump. Trade jumps for performance.

**Trade-off**: lose "jump to page 47". If product needs it, hybrid (cursor for hot path, capped offset for "browse" with a "narrow your search" prompt past page 100).

---

## ADR-003: Two-layer column config (whitelist + per-org JSON)

**Decision**:
- `app/constants/allowed_fields.py` — hard-coded whitelist of every field that's ever safe to expose.
- `Organization.column_config` — JSON column listing the subset (and order) for that org, plus a `field_groups` mapping for compound columns like `location → [name, city, country]`.

**Alternatives**:
1. **Just per-org JSON** — Simpler. A single bug in admin UI or a malicious config leaks PII (`ssn`, internal `notes`, etc).
2. **Per-org Postgres view** — Strongest isolation but high operational cost (one view per org × number of orgs).
3. **GraphQL with field-level auth** — Right tool for highly variable shapes; overkill for an HR list page.

**Why this**: defense in depth — even if someone misconfigures, the whitelist catches it. Cheap to evolve.

**Trade-off**: validation runs on every request (cached by `(org_id, config_version)` so amortized cost is ~zero).

---

## ADR-004: Token bucket for rate limiting

**Decision**: Token bucket, in-memory, keyed by `(org_id, principal_id)`. Default 10 req/sec, burst 20. Pluggable backend interface for Redis swap.

**Alternatives**:
1. **Sliding window log** — Most accurate. Stores per-request timestamps → O(N) memory per key.
2. **Fixed window** — Simplest. Suffers boundary-burst (2× limit at minute boundaries).
3. **Sliding window counter** — Approximation of #1 in O(1) memory. Good alternative.

**Why this**: matches dashboard burst pattern (page-page-page-idle), O(1) memory, simple math.

**Constraint compliance**: zero external dependencies (`threading.Lock`, `time.monotonic` — stdlib only).

**Trade-off**: in-memory loses state on restart. Documented in README. Production swap = `RedisBucketStore` with Lua-script atomic check-and-decrement.

---

## ADR-005: Tenant context via ContextVar + middleware

**Decision**: A FastAPI middleware extracts `org_id` from `X-Org-Id` (or JWT claim) at request entry and sets a `contextvars.ContextVar`. The repository base class reads from this ContextVar on every query.

**Alternatives**:
1. **Pass `org_id` as parameter everywhere** — Explicit, but boilerplate. Easy to forget on a new method → tenant leak.
2. **Postgres row-level security (RLS)** — Strongest. Requires per-connection `SET app.current_org_id = ...` and Postgres policies. I'd add this for HIPAA-tier compliance.
3. **Middleware sets a thread-local / SQLAlchemy session info** — Same idea but ContextVar is the asyncio-correct primitive.

**Why this**: middleware enforces it once; can't forget.

**Trade-off**: implicit context — debugging "why did this query fetch wrong tenant?" requires checking middleware order. Mitigated by:
- `TenantSafeRepository.execute()` raises `TenantContextMissing` if `ContextVar` is unset.
- Test in `test_security_isolation.py` exercises the bypass attempt.

---

## ADR-006: Dynamic response model via `pydantic.create_model`

**Decision**: Per-request, build a Pydantic model whose fields = `intersect(org.column_config, ALLOWED_FIELDS)`. Cached LRU keyed by `(org_id, config_version)`.

**Alternatives**:
1. **Single `EmployeeOut` with `Optional[...]` everywhere** — Static. Org with 5 columns still serializes 30 nullable fields (and OpenAPI shows them).
2. **Manual `dict` serialization, no Pydantic** — Simple, but loses validation, OpenAPI docs become wrong.
3. **GraphQL** — Right shape for variable response structures; not a fit for "FastAPI" requirement.

**Why this**: types stay correct, OpenAPI per-org could even be served, and `create_model` cost is amortized via LRU.

**Trade-off**: OpenAPI shows the union of all possible fields (static doc); per-org doc would require additional work.

---

## ADR-007: Composite index strategy `(org_id, X)` not `(X, org_id)`

**Decision**: Every secondary index leads with `org_id`. E.g., `idx_employees_org_status (org_id, status)`, not `(status, org_id)`.

**Why this**: shard key is `org_id`. Every query starts with `WHERE org_id = ?`. Putting it first means the index can serve both filtered (`status='active'`) and unfiltered (`org_id` only) queries.

**Trade-off**: cross-org analytics (`SELECT count(*) FROM employees WHERE status = 'active' GROUP BY org_id`) won't use these indexes well. Such queries belong in an OLAP system anyway.

---

## ADR-008: SQLAlchemy 2.x `mapped_column` + `Mapped[T]` annotations

**Decision**: New 2.0 style throughout. Async engine for the API hot path.

**Alternatives**:
1. **SQLAlchemy 1.x classic** — Familiar but soon-EOL. No reason to start new code there.
2. **Raw asyncpg** — Lowest latency. Loses ORM ergonomics; would have to hand-roll the column-projection logic and the test factories.

**Why this**: type checking catches column-name typos at lint time; async unlocks higher concurrency on the same hardware.

**Trade-off**: async sessions can't be used in some libraries (e.g., older test fixtures). Test base class handles the bridge.

---

## ADR-009: Alembic migrations live outside `app/`

**Decision**: `alembic/` at the repo root, not `app/alembic/`.

**Why this**: migrations have a different release cadence (often hand-run by a DBA pre-deploy). Mixing them with application code blurs ownership.

**Trade-off**: slight import-path awkwardness (`alembic/env.py` adds `app/` to `sys.path`). Worth it for the clarity signal.

---

## ADR-010: No `utils/` until needed

**Decision**: Currently no `app/utils/` folder. Helpers live in the module that uses them.

**Why this**: `utils/` becomes a junk drawer. Adding it preemptively encourages dumping unrelated code together.

**Trade-off**: when the second module needs the same helper, I lift it out — at that point I'll create either `app/utils/<topic>.py` (if pure stateless) or `app/core/<topic>.py` (if it has lifecycle/config).

---

## Threats considered

| Threat | Mitigation |
|---|---|
| Tenant leak (org A sees org B rows) | 3-layer defense — see "Multi-tenant safety" in README |
| Field leak (PII like SSN exposed via crafted config) | `ALLOWED_FIELDS` whitelist intersected with org config |
| Rate-limit bypass (header spoofing) | Bucket key uses authenticated principal, not request-derived value |
| SQL injection via filter values | All queries use bound parameters via SQLAlchemy core/ORM — no string interpolation |
| Resource exhaustion (huge `limit=`) | Hard cap `MAX_PAGE_SIZE = 100` enforced at the schema layer |
| Slow query DoS via expensive filters | Indexed columns only; `?sort=` whitelist; query timeout via Postgres `statement_timeout` |
| Open-redirect / SSRF | N/A — no outbound URLs accepted |

---

## What I did NOT build (and why)

- **Auth (JWT issuance)**: spec didn't require it; assumed an upstream gateway provides identity via headers.
- **Admin UI for column config**: spec explicitly said "no CRUD for entities".
- **Real Redis rate-limiter backend**: scoped to in-memory with a clean swap interface.
- **Sharding plumbing**: noted in spec as "after sharding"; design respects it (`org_id` as shard key in every query) but doesn't implement multi-shard routing.
- **Audit logging**: out of scope but would be a `BackgroundTasks` decorator on the search service.

---

## Questions I'd ask the PM/stakeholder before iterating

1. What's the per-org column-config change frequency? (Drives caching strategy.)
2. What's the target P99 latency under the "millions of users" load? (Drives index strategy and possibly read-replica setup.)
3. Is there a hard PII boundary (e.g., GDPR Article 9 fields)? (Drives field-level encryption requirements.)
4. Single-region or multi-region? (Drives connection-pool topology.)
5. Burst traffic profile — bot scrapers, end-of-quarter spikes, etc.? (Drives rate-limit tuning.)
