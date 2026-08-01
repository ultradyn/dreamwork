"""Principled, reusable database API for Dreamwork stores."""

from .core import (
    Access,
    Busy,
    Conflict,
    ConstraintViolation,
    Corrupt,
    DatabaseError,
    DatabaseHandle,
    NotFound,
    SchemaMismatch,
    StoreSpec,
    ValidationError,
    open_database,
)
from .store import dreamwork_store_spec

__all__ = [
    "Access",
    "Busy",
    "Conflict",
    "ConstraintViolation",
    "Corrupt",
    "DatabaseError",
    "DatabaseHandle",
    "NotFound",
    "SchemaMismatch",
    "StoreSpec",
    "ValidationError",
    "open_database",
    "dreamwork_store_spec",
]
