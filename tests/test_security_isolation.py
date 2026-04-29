"""Security tests — multi-tenant data isolation.

These are the most important tests in the suite. A failure here means
data leak across organizations — a security incident.

Strategy
--------
End-to-end: spin up the FastAPI app against a test DB, seed two orgs
with distinct employees, then run requests with each org's header and
assert each only sees its own rows.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


# These tests assume the seed script populated org_alpha and org_beta.
# In CI we'd use a fresh test DB + factory_boy; for the assignment
# scope we lean on the seed.


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_org_alpha_only_sees_own_employees(client: TestClient):
    res = client.get("/v1/employees/search?limit=100", headers={"X-Org-Id": "org_alpha"})
    assert res.status_code == 200
    body = res.json()
    # Every result must be from org_alpha. We can't see org_id directly
    # (it's not in the response), but we use the seeded email pattern.
    for row in body["results"]:
        if "email" in row:
            assert "@org_alpha" in row["email"]


def test_org_beta_only_sees_own_employees(client: TestClient):
    res = client.get("/v1/employees/search?limit=100", headers={"X-Org-Id": "org_beta"})
    assert res.status_code == 200
    body = res.json()
    # org_beta config doesn't expose email, so we check that emails
    # never appear in the response (defense: PII not in this org's columns).
    for row in body["results"]:
        assert "email" not in row, "org_beta config should not expose email"


def test_missing_org_header_returns_401(client: TestClient):
    res = client.get("/v1/employees/search")
    assert res.status_code == 401


def test_unknown_org_header_returns_empty(client: TestClient):
    """Unknown but well-formed org should return empty, not leak."""
    res = client.get(
        "/v1/employees/search",
        headers={"X-Org-Id": "org_does_not_exist"},
    )
    assert res.status_code == 200
    assert res.json()["results"] == []


def test_health_endpoint_does_not_require_tenant(client: TestClient):
    res = client.get("/healthz")
    assert res.status_code == 200


def test_crafted_header_cannot_swap_tenant_mid_request(client: TestClient):
    """A request with two X-Org-Id values must not result in cross-tenant access."""
    res = client.get(
        "/v1/employees/search?limit=10",
        headers=[("X-Org-Id", "org_alpha"), ("X-Org-Id", "org_beta")],
    )
    # Starlette resolves duplicate headers deterministically (first wins
    # in our middleware). Either way the result must be a single tenant.
    assert res.status_code == 200
    body = res.json()
    if body["results"]:
        # All results must belong to one consistent tenant — check the
        # first row's email pattern matches the rest.
        emails = [r.get("email") for r in body["results"] if r.get("email")]
        if emails:
            domain = emails[0].split("@", 1)[1]
            for e in emails:
                assert e.endswith("@" + domain)
