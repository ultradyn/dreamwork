"""Connection-policy and unit-of-work tests for :mod:`dreamwork_db.core`."""

from __future__ import annotations

import sqlite3

import pytest

import ledger_store
from dreamwork_db import (
    Access,
    DatabaseHandle,
    StoreSpec,
    ValidationError,
    open_database,
)
from dreamwork_db import core as db_core


class _Values:
    """Tiny test repository: callers never receive its SQL session."""

    __slots__ = ("_session",)

    def __init__(self, session):
        self._session = session

    def all(self) -> list[str]:
        return [row[0] for row in self._session.execute(
            "SELECT value FROM sample ORDER BY id"
        ).fetchall()]

    def add(self, value: str) -> None:
        self._session.execute("INSERT INTO sample(value) VALUES (?)", (value,))


def _initialize_sample(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sample ("
        "id INTEGER PRIMARY KEY, value TEXT NOT NULL)"
    )


def _spec(path, *, initialize: bool = False) -> StoreSpec:
    return StoreSpec(
        path=path,
        repositories={"values": _Values},
        initializer=_initialize_sample if initialize else None,
    )


def _create_sample(path, *values: str) -> None:
    with open_database(_spec(path, initialize=True), access=Access.WRITE) as db:
        with db.transaction() as tx:
            for value in values:
                tx.values.add(value)


def test_write_uses_immediate_transaction_and_commits(tmp_path):
    path = tmp_path / "store.sqlite3"
    _create_sample(path, "one")

    with open_database(_spec(path), access=Access.WRITE) as db:
        with pytest.raises(ValidationError, match=r"require transaction\(\)"):
            db.values.add("outside")
        with db.transaction(immediate=True) as tx:
            tx.values.add("two")

    with open_database(_spec(path), access=Access.READ) as db:
        assert db.values.all() == ["one", "two"]


def test_transaction_exception_rolls_back_instead_of_committing(tmp_path):
    path = tmp_path / "store.sqlite3"
    _create_sample(path, "before")

    with open_database(_spec(path), access=Access.WRITE) as db:
        with pytest.raises(RuntimeError, match="abort command"):
            with db.transaction() as tx:
                tx.values.add("must roll back")
                raise RuntimeError("abort command")

    with open_database(_spec(path), access=Access.READ) as db:
        got = db.values.all()
    assert got == ["before"], (
        f"transaction swallowed an exception or committed after rollback: {got!r}"
    )


def test_read_handle_query_only_rejects_a_constructed_write(tmp_path):
    path = tmp_path / "store.sqlite3"
    _create_sample(path, "before")

    with open_database(_spec(path), access=Access.READ) as db:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            db.values.add("forbidden")
        assert db.values.all() == ["before"]


def test_read_handle_holds_one_generation_snapshot(tmp_path):
    path = tmp_path / "store.sqlite3"
    _create_sample(path, "generation-n")

    with open_database(_spec(path), access=Access.READ) as first:
        assert first.values.all() == ["generation-n"]
        with open_database(_spec(path), access=Access.WRITE) as writer:
            with writer.transaction() as tx:
                tx.values.add("generation-n-plus-one")
        assert first.values.all() == ["generation-n"], (
            "READ handle combined generation N with N+1 inside one snapshot"
        )

    with open_database(_spec(path), access=Access.READ) as second:
        assert second.values.all() == ["generation-n", "generation-n-plus-one"]


def test_second_handle_cannot_see_first_handles_uncommitted_data(tmp_path):
    path = tmp_path / "store.sqlite3"
    _create_sample(path, "committed")

    with open_database(_spec(path), access=Access.WRITE) as writer:
        with writer.transaction() as tx:
            tx.values.add("uncommitted")
            with open_database(_spec(path), access=Access.READ) as reader:
                got = reader.values.all()
                assert got == ["committed"], (
                    f"second handle observed uncommitted data: {got!r}"
                )


def test_handle_does_not_expose_connection_execute_or_subclass_escape(tmp_path):
    path = tmp_path / "store.sqlite3"
    _create_sample(path)

    with open_database(_spec(path), access=Access.READ) as db:
        for forbidden in ("conn", "execute", "__dict__"):
            assert not hasattr(db, forbidden), (
                f"database handle leaks forbidden attribute {forbidden!r}"
            )
        assert "conn" not in dir(db) and "execute" not in dir(db)

        with pytest.raises(TypeError, match="final"):
            class _LeakyHandle(DatabaseHandle):
                pass


def test_read_connection_pragmas_are_explicit(tmp_path):
    path = tmp_path / "store.sqlite3"
    _create_sample(path)

    observed = {}

    def inspect(session):
        class _Pragmas:
            def read(self):
                for name in ("query_only", "foreign_keys", "busy_timeout"):
                    observed[name] = session.execute(f"PRAGMA {name}").fetchone()[0]
        return _Pragmas()

    spec = StoreSpec(path, repositories={"pragmas": inspect})
    with open_database(spec, access=Access.READ) as db:
        db.pragmas.read()
    assert observed == {
        "query_only": 1,
        "foreign_keys": 1,
        "busy_timeout": 5_000,
    }, f"READ connection has wrong pragmas: {observed!r}"


def test_legacy_open_store_delegates_with_exact_connection_policy(
    tmp_path, monkeypatch
):
    real_connect = db_core._connect
    observed = {}

    def recording_connect(spec, access):
        observed["spec"] = spec
        observed["access"] = access
        conn = real_connect(spec, access)
        observed["isolation_level"] = conn.isolation_level
        observed["foreign_keys"] = conn.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0]
        return conn

    monkeypatch.setattr(db_core, "_connect", recording_connect)
    store = ledger_store.open_store(
        tmp_path / "ledger.sqlite3", seed_next_id=10
    )
    try:
        assert observed["access"] is Access.WRITE, (
            f"legacy facade delegated with wrong access: {observed['access']!r}"
        )
        assert observed["isolation_level"] is None, (
            "legacy facade delegated with wrong isolation_level: "
            f"{observed['isolation_level']!r}, expected None"
        )
        assert observed["foreign_keys"] == 1, (
            "legacy facade delegated with wrong foreign_keys pragma: "
            f"{observed['foreign_keys']!r}, expected 1"
        )
        assert store.read_pragmas() == {
            "journal_mode": "wal",
            "synchronous": 2,
            "busy_timeout": 5_000,
            "foreign_keys": 1,
        }
    finally:
        store.close()


def test_connect_closes_connection_when_initializer_raises_baseexception(
    tmp_path, monkeypatch
):
    real_connect = db_core.sqlite3.connect
    observed = {}

    class RecordingConnection:
        def __init__(self, connection):
            self._connection = connection
            self.closed = False

        def execute(self, *args, **kwargs):
            return self._connection.execute(*args, **kwargs)

        def close(self):
            self.closed = True
            self._connection.close()

    def recording_connect(*args, **kwargs):
        wrapper = RecordingConnection(real_connect(*args, **kwargs))
        observed["connection"] = wrapper
        return wrapper

    def interrupt(_connection):
        raise KeyboardInterrupt("initializer interrupted")

    monkeypatch.setattr(db_core.sqlite3, "connect", recording_connect)
    spec = StoreSpec(tmp_path / "store.sqlite3", initializer=interrupt)
    with pytest.raises(KeyboardInterrupt, match="initializer interrupted"):
        db_core._connect(spec, Access.WRITE)
    assert observed["connection"].closed, (
        "_connect must close its connection when an initializer raises a "
        "BaseException"
    )
