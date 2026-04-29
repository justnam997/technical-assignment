"""End-to-end search tests — pagination, filters, dynamic columns."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_basic_search_returns_results(client: TestClient):
    res = client.get(
        "/v1/employees/search?limit=10",
        headers={"X-Org-Id": "org_alpha"},
    )
    assert res.status_code == 200
    body = res.json()
    assert "results" in body
    assert "next_cursor" in body
    assert "has_more" in body
    assert len(body["results"]) <= 10


def test_status_filter(client: TestClient):
    res = client.get(
        "/v1/employees/search?statuses=active&limit=50",
        headers={"X-Org-Id": "org_alpha"},
    )
    assert res.status_code == 200
    for row in res.json()["results"]:
        if "status" in row:
            assert row["status"] == "active"


def test_cursor_pagination_advances(client: TestClient):
    """Cursor must advance — page 2 doesn't include page 1's rows."""
    page1 = client.get(
        "/v1/employees/search?limit=5",
        headers={"X-Org-Id": "org_alpha"},
    ).json()
    if not page1["has_more"]:
        pytest.skip("not enough seeded data for pagination")
    page2 = client.get(
        f"/v1/employees/search?limit=5&cursor={page1['next_cursor']}",
        headers={"X-Org-Id": "org_alpha"},
    ).json()
    p1_keys = {tuple(sorted(r.items())) for r in page1["results"]}
    p2_keys = {tuple(sorted(r.items())) for r in page2["results"]}
    assert p1_keys.isdisjoint(p2_keys)


def test_dynamic_columns_match_org_config(client: TestClient):
    """org_alpha exposes email; org_beta does not."""
    alpha = client.get(
        "/v1/employees/search?limit=1",
        headers={"X-Org-Id": "org_alpha"},
    ).json()
    beta = client.get(
        "/v1/employees/search?limit=1",
        headers={"X-Org-Id": "org_beta"},
    ).json()
    if alpha["results"]:
        assert "email" in alpha["results"][0]
    if beta["results"]:
        assert "email" not in beta["results"][0]


def test_limit_capped_at_max(client: TestClient):
    """Asking for limit=10000 must be rejected by Pydantic at the route."""
    res = client.get(
        "/v1/employees/search?limit=10000",
        headers={"X-Org-Id": "org_alpha"},
    )
    assert res.status_code == 422


def test_openapi_spec_available(client: TestClient):
    res = client.get("/openapi.json")
    assert res.status_code == 200
    spec = res.json()
    assert "/v1/employees/search" in spec["paths"]
