"""Pytest fixtures shared across test modules."""
from __future__ import annotations

import pytest

from app.database import engine
from app.core.tenant import _current_org_id, _current_principal_id


@pytest.fixture(autouse=True)
async def reset_db_pool():
    """Avoid reusing asyncpg connections across TestClient event loops."""
    yield
    await engine.dispose()


@pytest.fixture
def tenant_context():
    """Set tenant ContextVars for tests that hit the repo layer."""
    org_token = _current_org_id.set("org_alpha")
    p_token = _current_principal_id.set("test-user")
    yield "org_alpha"
    _current_org_id.reset(org_token)
    _current_principal_id.reset(p_token)
