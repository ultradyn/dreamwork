"""Shared SQLite connection and transaction policy for Dreamwork stores.

The public handle deliberately does not expose SQLite connections or cursors.
Domain repositories receive a private session object when a ``StoreSpec`` is
opened; callers only see those repositories and the unit-of-work boundary.
"""

from __future__ import annotations

import os
import sqlite3
import weakref
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Iterator, Mapping, Optional, Union
from urllib.parse import quote


PathLike = Union[str, os.PathLike[str]]
BUSY_TIMEOUT_MS = 5_000


class Access(Enum):
    """The capabilities requested for one short-lived database handle."""

    READ = "read"
    WRITE = "write"


class DatabaseError(RuntimeError):
    """Base class for errors adapters can translate without parsing text."""


class NotFound(DatabaseError):
    """A requested domain object does not exist."""


class Conflict(DatabaseError):
    """The command conflicts with current persisted state."""


class ValidationError(DatabaseError):
    """A command or API use is invalid."""


class Busy(DatabaseError):
    """SQLite could not obtain the required lock before the timeout."""


class SchemaMismatch(DatabaseError):
    """The store schema is not the exact version this process supports."""


RepositoryFactory = Callable[["_RepositorySession"], object]
Initializer = Callable[[sqlite3.Connection], None]


@dataclass(frozen=True, slots=True)
class StoreSpec:
    """Connection-independent description of one SQLite store.

    ``initializer`` is the package-internal schema entry point for a store.
    It runs only for WRITE opens, after connection pragmas and before a handle
    is exposed; the legacy task store supplies ``dreamwork_db.migrate``'s
    ordered ladder here.
    Repository factories are trusted package internals: each receives a
    private session, while API consumers receive only the resulting object.
    """

    path: PathLike
    repositories: Mapping[str, RepositoryFactory] = field(
        default_factory=dict, repr=False, compare=False
    )
    initializer: Optional[Initializer] = field(
        default=None, repr=False, compare=False
    )
    busy_timeout_ms: int = BUSY_TIMEOUT_MS

    def __post_init__(self) -> None:
        path = Path(self.path)
        if not path.name:
            raise ValidationError(f"store path must name a file, got {path}")
        if self.busy_timeout_ms < 0:
            raise ValidationError(
                f"busy_timeout_ms must be >= 0, got {self.busy_timeout_ms}"
            )
        reserved = {"access", "path", "transaction", "conn", "execute"}
        for name, factory in self.repositories.items():
            if not name.isidentifier() or name.startswith("_") or name in reserved:
                raise ValidationError(f"invalid repository name {name!r}")
            if not callable(factory):
                raise ValidationError(f"repository factory {name!r} is not callable")
        object.__setattr__(self, "path", path)
        object.__setattr__(
            self, "repositories", MappingProxyType(dict(self.repositories))
        )


@dataclass(slots=True)
class _HandleState:
    connection: sqlite3.Connection
    spec: StoreSpec
    access: Access
    repositories: dict[str, object] = field(default_factory=dict)
    transaction_active: bool = False
    closed: bool = False


class DatabaseHandle:
    """Repository-bearing database handle with no raw-SQL public surface."""

    __slots__ = ("__weakref__",)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        raise TypeError("DatabaseHandle is final; compose a repository instead")

    @property
    def access(self) -> Access:
        return _state_for(self).access

    @property
    def path(self) -> Path:
        return Path(_state_for(self).spec.path)

    def __getattr__(self, name: str) -> object:
        state = _state_for(self)
        try:
            return state.repositories[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __dir__(self) -> list[str]:
        state = _state_for(self)
        return sorted(set(super().__dir__()) | set(state.repositories))

    @contextmanager
    def transaction(self, *, immediate: bool = True) -> Iterator["DatabaseHandle"]:
        """Run one WRITE unit of work, committing or rolling back atomically."""

        state = _state_for(self)
        if state.access is not Access.WRITE:
            raise ValidationError(
                "READ handles already own one deferred snapshot transaction"
            )
        if state.transaction_active or state.connection.in_transaction:
            raise Conflict("nested database transactions are not supported")

        begin = "BEGIN IMMEDIATE" if immediate else "BEGIN"
        try:
            state.connection.execute(begin)
        except sqlite3.OperationalError as exc:
            _raise_busy(exc, operation=begin)
            raise
        state.transaction_active = True
        try:
            yield self
        except BaseException:
            state.connection.rollback()
            raise
        else:
            try:
                state.connection.commit()
            except sqlite3.OperationalError as exc:
                state.connection.rollback()
                _raise_busy(exc, operation="COMMIT")
                raise
        finally:
            state.transaction_active = False


class _RepositorySession:
    """Raw-SQL capability supplied only to repository implementations."""

    __slots__ = ("__weakref__",)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        raise TypeError("_RepositorySession is final")

    def execute(self, sql: str, parameters: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        state = _session_state_for(self)
        if state.access is Access.WRITE and not state.transaction_active:
            raise ValidationError("WRITE repository calls require transaction()")
        try:
            return state.connection.execute(sql, parameters)
        except sqlite3.OperationalError as exc:
            _raise_busy(exc, operation="SQL")
            raise

    def executemany(
        self, sql: str, parameters: list[tuple[Any, ...]]
    ) -> sqlite3.Cursor:
        state = _session_state_for(self)
        if state.access is Access.WRITE and not state.transaction_active:
            raise ValidationError("WRITE repository calls require transaction()")
        try:
            return state.connection.executemany(sql, parameters)
        except sqlite3.OperationalError as exc:
            _raise_busy(exc, operation="SQL")
            raise


_HANDLE_STATES: "weakref.WeakKeyDictionary[DatabaseHandle, _HandleState]" = (
    weakref.WeakKeyDictionary()
)
_SESSION_STATES: "weakref.WeakKeyDictionary[_RepositorySession, _HandleState]" = (
    weakref.WeakKeyDictionary()
)


def _state_for(handle: DatabaseHandle) -> _HandleState:
    try:
        state = _HANDLE_STATES[handle]
    except KeyError as exc:
        raise ValidationError("database handle is not open") from exc
    if state.closed:
        raise ValidationError("database handle is closed")
    return state


def _session_state_for(session: _RepositorySession) -> _HandleState:
    try:
        state = _SESSION_STATES[session]
    except KeyError as exc:
        raise ValidationError("repository session is not open") from exc
    if state.closed:
        raise ValidationError("repository session is closed")
    return state


def _ensure_parent_durable(path: Path) -> None:
    parent = path.parent
    if parent == Path("."):
        return
    parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(parent), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _raise_busy(exc: sqlite3.OperationalError, *, operation: str) -> None:
    busy_codes = {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}
    code = getattr(exc, "sqlite_errorcode", None)
    if code in busy_codes or "locked" in str(exc).lower() or "busy" in str(exc).lower():
        raise Busy(f"database busy during {operation}: {exc}") from exc


def _connect(spec: StoreSpec, access: Access) -> sqlite3.Connection:
    """Open one configured connection; package-internal compatibility seam."""

    path = Path(spec.path)
    timeout = spec.busy_timeout_ms / 1_000
    if access is Access.READ:
        uri = f"file:{quote(str(path.absolute()), safe='/')}?mode=ro"
        connection = sqlite3.connect(
            uri, uri=True, isolation_level=None, timeout=timeout
        )
    else:
        _ensure_parent_durable(path)
        connection = sqlite3.connect(
            str(path), isolation_level=None, timeout=timeout
        )

    try:
        if access is Access.WRITE:
            connection.execute("PRAGMA journal_mode=WAL")
            # Pin a value transition so deleting FULL is observable even when
            # SQLite's compile-time default already happens to be FULL.
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute("PRAGMA synchronous=FULL")
        connection.execute(f"PRAGMA busy_timeout={spec.busy_timeout_ms}")
        connection.execute("PRAGMA foreign_keys=ON")
        if access is Access.READ:
            connection.execute("PRAGMA query_only=ON")
        elif spec.initializer is not None:
            spec.initializer(connection)
    except BaseException:
        connection.close()
        raise
    return connection


@contextmanager
def open_database(
    target: Union[PathLike, StoreSpec], *, access: Access = Access.READ
) -> Iterator[DatabaseHandle]:
    """Open one short-lived READ snapshot or WRITE unit-of-work handle."""

    if not isinstance(access, Access):
        raise ValidationError(f"access must be an Access value, got {access!r}")
    spec = target if isinstance(target, StoreSpec) else StoreSpec(target)
    connection = _connect(spec, access)
    handle = DatabaseHandle()
    state = _HandleState(connection=connection, spec=spec, access=access)
    _HANDLE_STATES[handle] = state
    session = _RepositorySession()
    _SESSION_STATES[session] = state
    try:
        if access is Access.READ:
            connection.execute("BEGIN")
        for name, factory in spec.repositories.items():
            state.repositories[name] = factory(session)
        yield handle
    finally:
        if connection.in_transaction:
            connection.rollback()
        state.transaction_active = False
        state.closed = True
        connection.close()
