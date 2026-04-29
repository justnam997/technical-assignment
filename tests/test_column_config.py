"""Unit tests for column-config validation + dynamic Pydantic model.

Covers the "no PII leak via misconfigured column" threat.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.constants.allowed_fields import AllowedField, expand_columns
from app.schemas.column_config import ColumnConfig
from app.schemas.employee import build_response_model


def test_valid_config_accepts_individual_fields():
    cfg = ColumnConfig(list_columns=["first_name", "last_name", "email"])
    assert cfg.list_columns == ["first_name", "last_name", "email"]


def test_valid_config_accepts_groups():
    cfg = ColumnConfig(list_columns=["first_name", "location", "department"])
    expanded = expand_columns(cfg.list_columns)
    assert AllowedField.LOCATION_NAME in expanded
    assert AllowedField.LOCATION_CITY in expanded
    assert AllowedField.LOCATION_COUNTRY in expanded
    assert AllowedField.DEPARTMENT_NAME in expanded


def test_unknown_field_rejected():
    """A column key outside the whitelist must FAIL FAST at validation."""
    with pytest.raises(ValidationError) as exc:
        ColumnConfig(list_columns=["first_name", "ssn"])  # ssn not whitelisted
    assert "ssn" in str(exc.value)


def test_duplicate_columns_rejected():
    with pytest.raises(ValidationError):
        ColumnConfig(list_columns=["first_name", "first_name"])


def test_empty_columns_rejected():
    with pytest.raises(ValidationError):
        ColumnConfig(list_columns=[])


def test_dynamic_model_forbids_extra_fields():
    """Even if the repo accidentally returns ssn, the dynamic model strips it."""
    model = build_response_model((AllowedField.FIRST_NAME, AllowedField.LAST_NAME))
    with pytest.raises(ValidationError):
        model(first_name="Ada", last_name="Lovelace", ssn="123-45-6789")


def test_dynamic_model_caches_per_column_set():
    a = build_response_model((AllowedField.FIRST_NAME, AllowedField.LAST_NAME))
    b = build_response_model((AllowedField.FIRST_NAME, AllowedField.LAST_NAME))
    c = build_response_model((AllowedField.FIRST_NAME,))
    assert a is b  # cache hit
    assert a is not c
