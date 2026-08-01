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
from typing import Any, Callable, Iterator, Mapping, NoReturn, Optional, Union
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


class Corrupt(DatabaseError):
    """The store file is not a readable SQLite database (code 26)."""


class ConstraintViolation(DatabaseError):
    """Caller data violated a store constraint (FK, unique, CHECK, NOT NULL).

    Unlike ``Busy``, ``Corrupt`` and ``SchemaMismatch`` — which are *store*
    conditions, the store unable to serve the request — this is the store
    working correctly and rejecting caller data.  sqlite raises it as
    ``IntegrityError`` (a ``DatabaseError`` child); the ladder names what it
    can prove (#651) rather than declaring a precisely-classified error
    unclassifiable (#702).  The original sqlite error is carried as
    ``__cause__``.

    Callers should validate before the write (#681 built that validation
    into ``ledger_write``) rather than catch this as control flow.
    """


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
        except sqlite3.DatabaseError as exc:
            _raise_classified(exc, operation=begin)
        state.transaction_active = True
        try:
            yield self
        except BaseException:
            state.connection.rollback()
            raise
        else:
            try:
                state.connection.commit()
            except sqlite3.DatabaseError as exc:
                state.connection.rollback()
                _raise_classified(exc, operation="COMMIT")
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
        except sqlite3.DatabaseError as exc:
            _raise_classified(exc, operation="SQL")

    def executemany(
        self, sql: str, parameters: list[tuple[Any, ...]]
    ) -> sqlite3.Cursor:
        state = _session_state_for(self)
        if state.access is Access.WRITE and not state.transaction_active:
            raise ValidationError("WRITE repository calls require transaction()")
        try:
            return state.connection.executemany(sql, parameters)
        except sqlite3.DatabaseError as exc:
            _raise_classified(exc, operation="SQL")


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


def _raise_classified(
    exc: sqlite3.DatabaseError, *, operation: str
) -> NoReturn:
    """Translate one ``sqlite3.DatabaseError`` into a named ladder outcome.

    The ladder is total: a caller that reaches here never sees a raw
    sqlite error escape unnamed (#702). Busy locks, schema-shaped errors,
    corruption, constraint violations, and every remaining case each
    become a distinct, honest name (#651): the unclassified case is a
    plain ``DatabaseError`` that carries the original, never relabelled
    as something it was not proven to be.

    The catch surface widened from ``OperationalError`` to
    ``DatabaseError`` so the ladder is total over the full error tree,
    not just one subclass (#782): ``DatabaseError`` is the *parent* of
    ``OperationalError``, so a corrupt-store ``file is not a database``
    (code 26) escaped the old ``OperationalError``-only handlers unnamed.
    """
    text = str(exc).lower()
    busy_codes = {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}
    code = getattr(exc, "sqlite_errorcode", None)
    if code in busy_codes or "locked" in text or "busy" in text:
        raise Busy(f"database busy during {operation}: {exc}") from exc
    if code == getattr(sqlite3, "SQLITE_NOTADB", 26) or (
        "file is not a database" in text
    ):
        raise Corrupt(
            f"store file is corrupt or not a database during {operation}: {exc}"
        ) from exc
    if "no such column" in text or "no such table" in text:
        raise SchemaMismatch(
            f"store schema mismatch during {operation}: {exc}"
        ) from exc
    if isinstance(exc, sqlite3.IntegrityError):
        # A constraint violation is caller data the store rejected, not a
        # store condition: sqlite classified it precisely (IntegrityError),
        # so the ladder names it rather than calling it unclassified (#702).
        raise ConstraintViolation(
            f"caller data violated a store constraint during {operation}: {exc}"
        ) from exc
    raise DatabaseError(
        f"unclassified store error during {operation}: {exc}"
    ) from exc


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
    except sqlite3.DatabaseError as exc:
        connection.close()
        _raise_classified(exc, operation="connect")
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
            try:
                connection.execute("BEGIN")
            except sqlite3.DatabaseError as exc:
                _raise_classified(exc, operation="BEGIN")
        for name, factory in spec.repositories.items():
            state.repositories[name] = factory(session)
        yield handle
    finally:
        if connection.in_transaction:
            connection.rollback()
        state.transaction_active = False
        state.closed = True
        connection.close()
