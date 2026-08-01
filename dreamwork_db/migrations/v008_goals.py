"""Version 8 adds goal state, panel history, the current pointer, and rank.

Goals are ``task_group`` rows with ``kind='goal'``: v005 deliberately made
group kinds an open vocabulary and arbitrary depth already supplies the tree.
``task_group.description`` remains the one details body.

Four additions carry the decided semantics:

1. Goal state is stored, never derived from member tasks.  A goal is complete
   only when the panel says so (or the principal records a bypass; v009 stores
   that attribution).
2. Claims and verdicts retain every round.  ``base_sha`` may be NULL but is
   never evidence of a clean base; verdict JSON records every finding,
   corroboration, and the criteria/member population actually examined.
3. ``meta.current_goal_id`` is one pointer, making a stale second ``current``
   unrepresentable instead of relying on a per-row flag.
4. ``goal_rank`` is sibling-scoped; NULL sorts last and rank plus id gives a
   deterministic pre-order without storing a second whole-tree order.

``downgrade`` counts every fact it would destroy first and refuses with all
non-empty populations named, following v004/v005 rather than silently losing
goal history or state.
"""

from __future__ import annotations

import sqlite3

from ..core import SchemaMismatch


GOAL_STATES = ("open", "claimed", "complete", "blocked")


def upgrade(conn: sqlite3.Connection) -> None:
    """Add the decided goal schema without touching existing task rows."""
    conn.execute("CREATE TABLE goal_state_kind (state TEXT PRIMARY KEY)")
    conn.executemany(
        "INSERT INTO goal_state_kind (state) VALUES (?)",
        [(state,) for state in GOAL_STATES],
    )
    conn.execute(
        "ALTER TABLE task_group ADD COLUMN goal_state TEXT"
        " REFERENCES goal_state_kind(state)"
    )
    conn.execute(
        """
        CREATE TABLE goal_claim (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id    INTEGER NOT NULL REFERENCES task_group(id)
                        ON DELETE CASCADE,
            claimed_by  TEXT NOT NULL,
            claimed_at  TEXT NOT NULL,
            summary     TEXT NOT NULL,
            base_sha    TEXT,
            details_sha TEXT NOT NULL,
            outcome     TEXT,
            round       INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE goal_verdict (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            claim_id     INTEGER NOT NULL REFERENCES goal_claim(id)
                         ON DELETE CASCADE,
            lens         TEXT NOT NULL,
            refuted      INTEGER NOT NULL CHECK (refuted IN (0, 1)),
            blocking     TEXT NOT NULL DEFAULT 'none',
            findings     TEXT NOT NULL,
            corroborated TEXT NOT NULL,
            examined     TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT INTO meta (key, value) VALUES ('current_goal_id', '')"
    )
    conn.execute("ALTER TABLE task_group ADD COLUMN goal_rank INTEGER")
    # v005 seeds v005's kinds and this seeds v008's, so one version's shape is
    # one version's statement and ``downgrade`` removes exactly what it added.
    # Widening ``KIND_SEEDS`` instead would give version 5 two meanings and make
    # this INSERT unfalsifiable: every path reaches v008 through v005.
    conn.execute("INSERT INTO task_group_kind (kind) VALUES ('goal')")


def downgrade(conn: sqlite3.Connection) -> None:
    """Remove an unused v008 schema, refusing to discard any goal fact."""
    populations = {
        "goal_claim": int(conn.execute(
            "SELECT COUNT(*) FROM goal_claim"
        ).fetchone()[0]),
        "goal_verdict": int(conn.execute(
            "SELECT COUNT(*) FROM goal_verdict"
        ).fetchone()[0]),
        "goal_state values": int(conn.execute(
            "SELECT COUNT(*) FROM task_group WHERE goal_state IS NOT NULL"
        ).fetchone()[0]),
        "goal_rank values": int(conn.execute(
            "SELECT COUNT(*) FROM task_group WHERE goal_rank IS NOT NULL"
        ).fetchone()[0]),
        "current_goal_id pointer": int(conn.execute(
            "SELECT COUNT(*) FROM meta"
            " WHERE key = 'current_goal_id' AND value <> ''"
        ).fetchone()[0]),
        "goal task_group rows": int(conn.execute(
            "SELECT COUNT(*) FROM task_group WHERE kind = 'goal'"
        ).fetchone()[0]),
    }
    nonempty = {name: count for name, count in populations.items() if count}
    if nonempty:
        detail = ", ".join(f"{name}={count}" for name, count in nonempty.items())
        raise SchemaMismatch(
            f"cannot downgrade goal schema without losing data: {detail}"
        )

    conn.execute("DELETE FROM meta WHERE key = 'current_goal_id'")
    conn.execute("DROP TABLE goal_verdict")
    conn.execute("DROP TABLE goal_claim")
    conn.execute("ALTER TABLE task_group DROP COLUMN goal_rank")
    conn.execute("ALTER TABLE task_group DROP COLUMN goal_state")
    conn.execute("DROP TABLE goal_state_kind")
    conn.execute("DELETE FROM task_group_kind WHERE kind = 'goal'")
    conn.execute("UPDATE meta SET value = '7' WHERE key = 'schema_version'")
