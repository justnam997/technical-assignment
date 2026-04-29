"""Organization model — tenant root.

`column_config` JSON shape (validated by schemas/column_config.py):
{
  "version": 1,
  "list_columns": ["first_name", "last_name", "contact_info", "department", "location"]
}
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    column_config: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
