"""Per-organization column-config schema + validator.

This is layer 2 of the dynamic-column-config defense in depth (the
whitelist in `constants/allowed_fields.py` is layer 1).

Validation rules
----------------
1. `version` is an int (allows future migration of config shape).
2. `list_columns` is a non-empty list of strings.
3. Each entry resolves to at least one whitelisted field — entries
   that don't are flagged. The repo silently drops them at query time
   (DEFENSE), but the validator complains LOUDLY (FAIL FAST) so misconfigs
   are caught at admin-save time, not at customer-request time.
4. No duplicate columns.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.constants.allowed_fields import FIELD_GROUPS, AllowedField


class ColumnConfig(BaseModel):
    version: int = Field(default=1, ge=1)
    list_columns: list[str] = Field(min_length=1)

    @field_validator("list_columns")
    @classmethod
    def _validate_columns_against_whitelist(cls, value: list[str]) -> list[str]:
        # Disallow duplicates (case-insensitive).
        seen: set[str] = set()
        for col in value:
            lower = col.lower()
            if lower in seen:
                raise ValueError(f"duplicate column key: {col!r}")
            seen.add(lower)

        valid_keys = set(FIELD_GROUPS.keys()) | {f.value for f in AllowedField}
        invalid = [c for c in value if c not in valid_keys]
        if invalid:
            raise ValueError(
                f"unknown column keys: {invalid}. "
                f"Valid keys are individual fields ({sorted(f.value for f in AllowedField)}) "
                f"or groups ({sorted(FIELD_GROUPS.keys())})."
            )
        return value
