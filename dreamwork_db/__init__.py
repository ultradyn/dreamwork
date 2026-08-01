"""Principled, reusable database API for Dreamwork stores."""

from .core import (
    Access,
    Busy,
    Conflict,
    Corrupt,
    DatabaseError,
    DatabaseHandle,
    NotFound,
    SchemaMismatch,
    StoreSpec,
    ValidationError,
    open_database,
)

__all__ = [
    "Access",
    "Busy",
    "Conflict",
    "Corrupt",
    "DatabaseError",
    "DatabaseHandle",
    "NotFound",
    "SchemaMismatch",
    "StoreSpec",
    "ValidationError",
    "open_database",
]
