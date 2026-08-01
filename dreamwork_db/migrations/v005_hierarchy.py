"""Version 5 nested collections, an open kind vocabulary, and dependencies.

Three changes, one object: the work-organisation graph.

1. ``task_group_kind`` replaces v004's inline ``CHECK (kind IN (...))``.  Every
   other controlled vocabulary in this schema is a seeded lookup table with an
   FK (``priority_band``, ``task_state_kind``, ``task_cause``, ``task_type``);
   v004's inline check was the sole exception, and it rejected ``feature`` —
   a kind named in the very request that asked for this (#841).
2. ``task_group.parent_id`` — an adjacency list, so depth is data rather than
   schema.  Cycles are refused by the repository at write time; SQLite cannot
   state "acyclic" declaratively.
3. ``task_group_dependency`` — every dependency edge with at least one GROUP
   endpoint.  ``task -> task`` edges keep their v001 home in ``depends`` (23
   live rows at the time of writing) and a CHECK here refuses to become a
   second way to say the same thing (#440).

The task population is never read, rewritten, or referenced: all 730 task rows
(543 landed, 187 open) are untouched, as are ``depends`` and ``related``.

Why a table rebuild.  SQLite cannot drop a CHECK constraint via ALTER TABLE,
so the kind FK requires rebuilding ``task_group``.  ``PRAGMA foreign_keys`` is
already ON when the initialiser runs (``core.py``) and is a no-op inside a
transaction, and the ladder runs inside BEGIN (``migrate.py``), so the
textbook ``foreign_keys=OFF`` twelve-step is unavailable.  Dropping
``task_group`` while its children exist would fire ``task_group_member``'s
ON DELETE CASCADE and destroy membership, so the children are copied out to
plain backup tables and dropped first, and restored afterwards.

``downgrade`` follows v004's model: it counts what a rollback would destroy
FIRST and raises ``SchemaMismatch`` naming each non-empty case rather than
silently discarding it.
"""

from __future__ import annotations

import sqlite3

from ..core import SchemaMismatch


#: v004's three, plus the two #841 needs.  ``feature`` is the kind his request
#: named that v004's CHECK rejected; ``batch`` is a delivery-sized collection,
#: which an open vocabulary plus arbitrary depth makes a *seed row* rather than
#: a table of its own.
KIND_SEEDS = ("lane", "epic", "milestone", "feature", "batch", "goal")

#: The kinds v004's CHECK could express.  A downgrade cannot represent any
#: other kind, so it refuses rather than rewrite or drop those rows.
V004_KINDS = ("lane", "epic", "milestone")

_TASK_GROUP_V5 = """
CREATE TABLE {name} (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT NOT NULL REFERENCES task_group_kind(kind),
    title       TEXT NOT NULL CHECK (length(trim(title)) > 0),
    description TEXT NOT NULL DEFAULT '',
    created_by  TEXT NOT NULL CHECK (length(trim(created_by)) > 0),
    created_at  TEXT NOT NULL CHECK (length(trim(created_at)) > 0),
    -- Self-reference written against the BUILD name: `ALTER TABLE ... RENAME`
    -- rewrites references to the renamed table (including its own), so this
    -- becomes `REFERENCES task_group(id)` after the swap.  Naming the final
    -- table here instead would point the new table at the OLD one for the
    -- window before the drop.
    parent_id   INTEGER REFERENCES {name}(id),
    CHECK (parent_id IS NULL OR parent_id <> id)
)
"""

_TASK_GROUP_V4 = """
CREATE TABLE {name} (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT NOT NULL CHECK (kind IN ('lane','epic','milestone')),
    title       TEXT NOT NULL CHECK (length(trim(title)) > 0),
    description TEXT NOT NULL DEFAULT '',
    created_by  TEXT NOT NULL CHECK (length(trim(created_by)) > 0),
    created_at  TEXT NOT NULL CHECK (length(trim(created_at)) > 0)
)
"""

#: Recreated verbatim from v004 after the parent rebuild — same columns, same
#: cascade, same index.
_MEMBER_SQL = """
CREATE TABLE task_group_member (
    group_id INTEGER NOT NULL REFERENCES task_group(id) ON DELETE CASCADE,
    task_id  INTEGER NOT NULL REFERENCES task(id),
    added_by TEXT NOT NULL CHECK (length(trim(added_by)) > 0),
    added_at TEXT NOT NULL CHECK (length(trim(added_at)) > 0),
    PRIMARY KEY (group_id, task_id)
)
"""

_MEMBER_INDEX_SQL = (
    "CREATE INDEX task_group_member_task ON task_group_member(task_id)"
)

_TRIGGER_SQL = """
CREATE TABLE task_group_trigger (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id      INTEGER NOT NULL REFERENCES task_group(id) ON DELETE CASCADE,
    event         TEXT NOT NULL CHECK (event = 'completed'),
    task_title    TEXT NOT NULL CHECK (length(trim(task_title)) > 0),
    task_priority TEXT REFERENCES priority_band(band),
    task_type     TEXT NOT NULL DEFAULT 'task'
                  CHECK (length(trim(task_type)) > 0),
    created_by    TEXT NOT NULL CHECK (length(trim(created_by)) > 0),
    created_at    TEXT NOT NULL CHECK (length(trim(created_at)) > 0),
    UNIQUE (group_id, event, task_title)
)
"""

_DEPENDENCY_SQL = """
CREATE TABLE task_group_dependency (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    dependent_group_id INTEGER REFERENCES task_group(id) ON DELETE CASCADE,
    dependent_task_id  INTEGER REFERENCES task(id),
    needs_group_id     INTEGER REFERENCES task_group(id) ON DELETE CASCADE,
    needs_task_id      INTEGER REFERENCES task(id),
    created_by TEXT NOT NULL CHECK (length(trim(created_by)) > 0),
    created_at TEXT NOT NULL CHECK (length(trim(created_at)) > 0),
    CHECK ((dependent_group_id IS NOT NULL)
           + (dependent_task_id IS NOT NULL) = 1),
    CHECK ((needs_group_id IS NOT NULL) + (needs_task_id IS NOT NULL) = 1),
    -- task -> task edges live in v001's `depends`.  Refusing them here is
    -- #440 written into the schema: there is no second way to say it.
    CHECK (dependent_group_id IS NOT NULL OR needs_group_id IS NOT NULL),
    CHECK (dependent_group_id IS NULL OR needs_group_id IS NULL
           OR dependent_group_id <> needs_group_id)
)
"""

#: SQLite treats NULLs as distinct in UNIQUE, so a plain UNIQUE over four
#: nullable columns would admit duplicate edges.  Fold NULL to a sentinel.
_DEPENDENCY_INDEX_SQL = """
CREATE UNIQUE INDEX task_group_dependency_edge ON task_group_dependency (
    ifnull(dependent_group_id, -1), ifnull(dependent_task_id, -1),
    ifnull(needs_group_id, -1),     ifnull(needs_task_id, -1))
"""

_MEMBER_COLUMNS = "group_id, task_id, added_by, added_at"
_TRIGGER_COLUMNS = (
    "id, group_id, event, task_title, task_priority, task_type,"
    " created_by, created_at"
)


def _sequence(conn: sqlite3.Connection, table: str) -> int | None:
    """The AUTOINCREMENT high-water mark, or ``None`` if none was issued."""
    row = conn.execute(
        "SELECT seq FROM sqlite_sequence WHERE name = ?", (table,)
    ).fetchone()
    return None if row is None else int(row[0])


def _restore_sequence(
    conn: sqlite3.Connection, table: str, seq: int | None
) -> None:
    """Re-pin a rebuilt table's high-water mark.

    A rebuild resets ``sqlite_sequence`` to ``max(id)``, so a deleted
    high-water id would be reissued — and ``task_group_member`` references
    group ids, exactly the reuse v001 calls load-bearing for ``task``.
    """
    if seq is None:
        return
    updated = conn.execute(
        "UPDATE sqlite_sequence SET seq = ? WHERE name = ?", (seq, table)
    ).rowcount
    if not updated:
        conn.execute(
            "INSERT INTO sqlite_sequence (name, seq) VALUES (?, ?)", (table, seq)
        )


def _rebuild_task_group(conn: sqlite3.Connection, *, ddl: str, columns: str,
                        select: str) -> None:
    """Swap ``task_group`` for a differently-shaped table, keeping children.

    The children are copied to plain (FK-free, cascade-free) backups and
    dropped before the parent, because ``DROP TABLE task_group`` with rows
    still referencing it would fire ``ON DELETE CASCADE`` and delete
    membership.  Everything runs inside the ladder's transaction, so any
    failure rolls the whole swap back.
    """
    group_seq = _sequence(conn, "task_group")
    trigger_seq = _sequence(conn, "task_group_trigger")

    conn.execute("CREATE TABLE _v005_member AS SELECT * FROM task_group_member")
    conn.execute(
        "CREATE TABLE _v005_trigger AS SELECT * FROM task_group_trigger"
    )
    conn.execute("DROP TABLE task_group_trigger")
    conn.execute("DROP TABLE task_group_member")

    conn.execute(ddl.format(name="_v005_task_group"))
    conn.execute(
        f"INSERT INTO _v005_task_group ({columns})"
        f" SELECT {select} FROM task_group"
    )
    conn.execute("DROP TABLE task_group")
    conn.execute("ALTER TABLE _v005_task_group RENAME TO task_group")
    _restore_sequence(conn, "task_group", group_seq)

    conn.execute(_MEMBER_SQL)
    conn.execute(_MEMBER_INDEX_SQL)
    conn.execute(_TRIGGER_SQL)
    conn.execute(
        f"INSERT INTO task_group_member ({_MEMBER_COLUMNS})"
        f" SELECT {_MEMBER_COLUMNS} FROM _v005_member"
    )
    conn.execute(
        f"INSERT INTO task_group_trigger ({_TRIGGER_COLUMNS})"
        f" SELECT {_TRIGGER_COLUMNS} FROM _v005_trigger"
    )
    _restore_sequence(conn, "task_group_trigger", trigger_seq)
    conn.execute("DROP TABLE _v005_member")
    conn.execute("DROP TABLE _v005_trigger")


def _refuse_broken_references(conn: sqlite3.Connection, *, phase: str) -> None:
    violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise SchemaMismatch(
            f"{phase} left {len(violations)} broken foreign-key reference(s):"
            f" {violations[:5]}"
        )


def upgrade(conn: sqlite3.Connection) -> None:
    """Open the kind vocabulary, nest groups, and add group dependencies."""
    conn.execute("CREATE TABLE task_group_kind (kind TEXT PRIMARY KEY)")
    conn.executemany(
        "INSERT INTO task_group_kind (kind) VALUES (?)",
        [(kind,) for kind in KIND_SEEDS],
    )
    _rebuild_task_group(
        conn,
        ddl=_TASK_GROUP_V5,
        columns="id, kind, title, description, created_by, created_at, parent_id",
        select="id, kind, title, description, created_by, created_at, NULL",
    )
    conn.execute(_DEPENDENCY_SQL)
    conn.execute(_DEPENDENCY_INDEX_SQL)
    _refuse_broken_references(conn, phase="v005 upgrade")


def downgrade(conn: sqlite3.Connection) -> None:
    """Restore the v004 shape, refusing to discard hierarchy or dependencies."""
    blocking = {
        "task_group_dependency": int(conn.execute(
            "SELECT COUNT(*) FROM task_group_dependency"
        ).fetchone()[0]),
        "nested task_group rows": int(conn.execute(
            "SELECT COUNT(*) FROM task_group WHERE parent_id IS NOT NULL"
        ).fetchone()[0]),
        "task_group rows of a kind v004 cannot express": int(conn.execute(
            "SELECT COUNT(*) FROM task_group WHERE kind NOT IN"
            " ('lane','epic','milestone')"
        ).fetchone()[0]),
        # The v005 SEEDS are schema and go with the table; a kind somebody
        # DEFINED is data, and v004 has nowhere to put it.
        "operator-defined task_group_kind rows": int(conn.execute(
            "SELECT COUNT(*) FROM task_group_kind WHERE kind NOT IN"
            f" ({','.join('?' * len(KIND_SEEDS))})", KIND_SEEDS
        ).fetchone()[0]),
    }
    nonempty = {name: count for name, count in blocking.items() if count}
    if nonempty:
        detail = ", ".join(f"{name}={count}" for name, count in nonempty.items())
        raise SchemaMismatch(
            f"cannot downgrade hierarchy schema without losing data: {detail}"
        )
    conn.execute("DROP INDEX task_group_dependency_edge")
    conn.execute("DROP TABLE task_group_dependency")
    _rebuild_task_group(
        conn,
        ddl=_TASK_GROUP_V4,
        columns="id, kind, title, description, created_by, created_at",
        select="id, kind, title, description, created_by, created_at",
    )
    conn.execute("DROP TABLE task_group_kind")
    _refuse_broken_references(conn, phase="v005 downgrade")
    conn.execute("UPDATE meta SET value = '4' WHERE key = 'schema_version'")
