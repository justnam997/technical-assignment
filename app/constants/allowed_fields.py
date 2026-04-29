"""Whitelist of fields that may be exposed via the search API.

This is layer 1 of the dynamic-column-config defense in depth.
Even if an organization's `column_config` is misconfigured (or
maliciously crafted), only fields listed here can ever appear in a
response.

To expose a new field:
  1. Add it here.
  2. Add it to the SQL projection map in `repositories/employee.py`.
  3. Optionally add it to `FIELD_GROUPS` if it's part of a logical group.
"""
from __future__ import annotations

from enum import StrEnum


class AllowedField(StrEnum):
    """Single source of truth for safely-exposable fields."""

    # Identity
    ID = "id"
    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"

    # Contact
    EMAIL = "email"
    PHONE = "phone"

    # Status
    STATUS = "status"
    HIRED_AT = "hired_at"
    TERMINATED_AT = "terminated_at"

    # Relations (compound — see FIELD_GROUPS)
    DEPARTMENT_NAME = "department_name"
    POSITION_TITLE = "position_title"
    LOCATION_NAME = "location_name"
    LOCATION_CITY = "location_city"
    LOCATION_COUNTRY = "location_country"
    COMPANY_NAME = "company_name"


# Logical groups — a column key like "location" expands to all member fields.
# Lets an org config say "location" instead of listing 3 individual fields.
FIELD_GROUPS: dict[str, tuple[AllowedField, ...]] = {
    "contact_info": (AllowedField.EMAIL, AllowedField.PHONE),
    "location": (
        AllowedField.LOCATION_NAME,
        AllowedField.LOCATION_CITY,
        AllowedField.LOCATION_COUNTRY,
    ),
    "department": (AllowedField.DEPARTMENT_NAME,),
    "position": (AllowedField.POSITION_TITLE,),
    "company": (AllowedField.COMPANY_NAME,),
}


def expand_columns(column_keys: list[str]) -> list[AllowedField]:
    """Resolve a config's column keys into concrete AllowedField values.

    Accepts both individual field names ("first_name") and group keys
    ("location"). Drops anything not in the whitelist or groups —
    silent drop is intentional: a misconfigured column should not leak,
    not crash. (Validation that surfaces the misconfiguration happens
    earlier, in `schemas/column_config.py`.)
    """
    resolved: list[AllowedField] = []
    seen: set[AllowedField] = set()
    for key in column_keys:
        if key in FIELD_GROUPS:
            for field in FIELD_GROUPS[key]:
                if field not in seen:
                    resolved.append(field)
                    seen.add(field)
        else:
            try:
                field = AllowedField(key)
            except ValueError:
                continue  # skip unknowns
            if field not in seen:
                resolved.append(field)
                seen.add(field)
    return resolved
