"""Dynamic Pydantic response model — built per org.

Why dynamic
-----------
The response shape varies per org (column_config). Three options:
  A. Static `EmployeeOut` with everything Optional → 30 nullable fields,
     OpenAPI lies, frontend has to handle "this org doesn't have phone".
  B. dict serialization → loses validation + correct types.
  C. `pydantic.create_model` with the org's columns → correct shape,
     validated, fast (LRU-cached).

We use C. See DESIGN.md ADR-006.

Caching
-------
`build_response_model` is LRU-cached. The cache key is a tuple of
`AllowedField` enum values (hashable, deterministic order). Two orgs
with the same column set share a model.
"""
from __future__ import annotations

import datetime as dt
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, ConfigDict, create_model

from app.constants.allowed_fields import AllowedField


# Map field → Pydantic type. The whitelist drives this.
_FIELD_TYPES: dict[AllowedField, type] = {
    AllowedField.ID: int,
    AllowedField.FIRST_NAME: str,
    AllowedField.LAST_NAME: str,
    AllowedField.EMAIL: str,
    AllowedField.PHONE: str,
    AllowedField.STATUS: str,
    AllowedField.HIRED_AT: dt.date,
    AllowedField.TERMINATED_AT: dt.date,
    AllowedField.DEPARTMENT_NAME: str,
    AllowedField.POSITION_TITLE: str,
    AllowedField.LOCATION_NAME: str,
    AllowedField.LOCATION_CITY: str,
    AllowedField.LOCATION_COUNTRY: str,
    AllowedField.COMPANY_NAME: str,
}


@lru_cache(maxsize=512)
def build_response_model(columns: tuple[AllowedField, ...]) -> type[BaseModel]:
    """Construct a Pydantic model from a tuple of AllowedField values.

    Cached: identical column tuples reuse the same class.
    """
    fields: dict[str, tuple[type, Any]] = {}
    for col in columns:
        py_type = _FIELD_TYPES[col]
        # All fields are Optional in the model — a row may legitimately
        # have NULL (e.g., terminated_at on an active employee).
        fields[col.value] = (py_type | None, None)

    model = create_model(
        "EmployeeOut",
        __config__=ConfigDict(from_attributes=True, extra="forbid"),
        **fields,
    )
    return model


class SearchPage(BaseModel):
    """Wrapper around dynamic results — pagination metadata is static."""

    model_config = ConfigDict(extra="forbid")

    results: list[dict[str, Any]]  # validated by EmployeeOut at service layer
    next_cursor: str | None = None
    has_more: bool = False
