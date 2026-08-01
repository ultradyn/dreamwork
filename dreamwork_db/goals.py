"""Goal persistence over the canonical Dreamwork database handle."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .core import NotFound, SchemaMismatch, ValidationError


# One closed graph is the authority for every state write.  ``complete`` is
# terminal; direct completion is the principal's recorded force-complete path.
LEGAL_STATE_TRANSITIONS = {
    None: frozenset({"open"}),
    "open": frozenset({"claimed", "blocked", "complete"}),
    "claimed": frozenset({"open", "blocked", "complete"}),
    "blocked": frozenset({"open", "complete"}),
    "complete": frozenset(),
}

CLAIM_OUTCOMES = frozenset({"complete", "refuted", "unrun"})
VERDICT_LENSES = frozenset({"criteria", "evidence", "use"})
BLOCKING_KINDS = frozenset({"none", "contradiction", "unverifiable"})


@dataclass(frozen=True, slots=True)
class GoalClaim:
    id: int
    group_id: int
    claimed_by: str
    claimed_at: str
    summary: str
    base_sha: str | None
    details_sha: str
    outcome: str | None
    round: int


@dataclass(frozen=True, slots=True)
class GoalVerdict:
    id: int
    claim_id: int
    lens: str
    refuted: bool
    blocking: str
    findings: tuple[Any, ...]
    corroborated: tuple[Any, ...]
    examined: dict[str, int]


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{label} must be non-empty text, got {value!r}")
    return value.strip()


def _json_array(value: object, label: str) -> tuple[tuple[Any, ...], str]:
    if not isinstance(value, (list, tuple)):
        raise ValidationError(f"{label} must be a JSON array, got {value!r}")
    items = tuple(value)
    try:
        encoded = json.dumps(
            items, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        )
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{label} must contain JSON values: {exc}") from exc
    return items, encoded


def _examined(value: object) -> tuple[dict[str, int], str]:
    if not isinstance(value, dict) or set(value) != {"criteria", "members"}:
        raise ValidationError(
            "examined must be exactly {'criteria': n, 'members': n}"
        )
    counts = {"criteria": value["criteria"], "members": value["members"]}
    if any(isinstance(n, bool) or not isinstance(n, int) or n < 0
           for n in counts.values()):
        raise ValidationError(
            f"examined counts must be non-negative integers, got {counts!r}"
        )
    if counts["criteria"] == 0 or counts["members"] == 0:
        raise ValidationError(
            "DID NOT JUDGE: verdict examined "
            f"criteria={counts['criteria']} members={counts['members']}"
        )
    return counts, json.dumps(counts, separators=(",", ":"))


class GoalRepository:
    """Goal reads and writes over one handle-owned connection."""

    def __init__(self, session: Any) -> None:
        self._session = session

    def _goal(self, group_id: int) -> tuple[Any, ...]:
        row = self._session.execute(
            "SELECT id, kind, title, goal_state, goal_rank, parent_id"
            " FROM task_group WHERE id = ?", (group_id,),
        ).fetchone()
        if row is None:
            raise NotFound(f"no task group #{group_id}")
        if row[1] != "goal":
            raise ValidationError(
                f"{row[1]} #{group_id} {row[2]!r} is not a goal"
            )
        return row

    def current_goal_id(self) -> int | None:
        row = self._session.execute(
            "SELECT value FROM meta WHERE key = 'current_goal_id'"
        ).fetchone()
        if row is None:
            raise SchemaMismatch("goal schema has no current_goal_id pointer")
        if row[0] == "":
            return None
        try:
            group_id = int(row[0])
        except (TypeError, ValueError) as exc:
            raise SchemaMismatch(
                f"current_goal_id pointer is malformed: {row[0]!r}"
            ) from exc
        self._goal(group_id)
        return group_id

    def set_current_goal_id(self, group_id: int | None) -> str:
        if group_id is None:
            value = ""
            disposition = "cleared"
        else:
            self._goal(group_id)
            value = str(group_id)
            disposition = "set"
        existing = self._session.execute(
            "SELECT value FROM meta WHERE key = 'current_goal_id'"
        ).fetchone()
        if existing is None:
            raise SchemaMismatch("goal schema has no current_goal_id pointer")
        if existing[0] == value:
            return "unchanged"
        self._session.execute(
            "UPDATE meta SET value = ? WHERE key = 'current_goal_id'", (value,)
        )
        return disposition

    def state(self, group_id: int) -> str:
        state = self._goal(group_id)[3]
        if state not in LEGAL_STATE_TRANSITIONS:
            raise SchemaMismatch(
                f"goal #{group_id} has invalid stored goal_state {state!r}"
            )
        if state is None:
            raise SchemaMismatch(f"goal #{group_id} has no goal_state")
        return state

    def set_state(self, group_id: int, state: str) -> str:
        state = _text(state, "goal state")
        if state not in LEGAL_STATE_TRANSITIONS:
            raise ValidationError(
                f"unknown goal state {state!r}; expected"
                f" {tuple(s for s in LEGAL_STATE_TRANSITIONS if s is not None)}"
            )
        previous = self._goal(group_id)[3]
        if previous == state:
            return "unchanged"
        if previous not in LEGAL_STATE_TRANSITIONS:
            raise SchemaMismatch(
                f"goal #{group_id} has invalid stored goal_state {previous!r}"
            )
        if state not in LEGAL_STATE_TRANSITIONS[previous]:
            raise ValidationError(
                f"illegal goal state transition {previous} -> {state}"
            )
        self._session.execute(
            "UPDATE task_group SET goal_state = ? WHERE id = ?",
            (state, group_id),
        )
        return "changed"

    def rank(self, group_id: int) -> int | None:
        value = self._goal(group_id)[4]
        return None if value is None else int(value)

    def set_rank(self, group_id: int, rank: int | None) -> str:
        self._goal(group_id)
        if rank is not None and (isinstance(rank, bool) or not isinstance(rank, int)):
            raise ValidationError(f"goal rank must be an integer or None, got {rank!r}")
        existing = self.rank(group_id)
        if existing == rank:
            return "unchanged"
        self._session.execute(
            "UPDATE task_group SET goal_rank = ? WHERE id = ?", (rank, group_id)
        )
        return "changed"

    def ranked_children(self, parent_id: int | None) -> tuple[int, ...]:
        if parent_id is not None:
            self._goal(parent_id)
            where = "g.parent_id = ?"
            parameters = (parent_id,)
        else:
            # A goal parented under a non-goal is a root of the goal projection,
            # not an invisible row omitted from the total order.
            where = (
                "(g.parent_id IS NULL OR NOT EXISTS ("
                " SELECT 1 FROM task_group p"
                " WHERE p.id = g.parent_id AND p.kind = 'goal'))"
            )
            parameters = ()
        rows = self._session.execute(
            "SELECT g.id FROM task_group g WHERE g.kind = 'goal' AND "
            + where
            + " ORDER BY g.goal_rank IS NULL, g.goal_rank, g.id",
            parameters,
        ).fetchall()
        return tuple(int(row[0]) for row in rows)

    def preorder(self, root_id: int | None = None) -> tuple[int, ...]:
        roots = (root_id,) if root_id is not None else self.ranked_children(None)
        if root_id is not None:
            self._goal(root_id)
        ordered: list[int] = []
        stack = list(reversed(roots))
        while stack:
            group_id = stack.pop()
            ordered.append(group_id)
            stack.extend(reversed(self.ranked_children(group_id)))
        return tuple(ordered)

    def append_claim(
        self, group_id: int, *, claimed_by: str, claimed_at: str,
        summary: str, base_sha: str | None, details_sha: str, round: int,
        outcome: str | None = None,
    ) -> GoalClaim:
        self._goal(group_id)
        claimed_by = _text(claimed_by, "claimed_by")
        claimed_at = _text(claimed_at, "claimed_at")
        summary = _text(summary, "claim summary")
        details_sha = _text(details_sha, "details_sha")
        if base_sha is not None:
            base_sha = _text(base_sha, "base_sha")
        if outcome is not None and outcome not in CLAIM_OUTCOMES:
            raise ValidationError(
                f"unknown claim outcome {outcome!r}; expected {tuple(CLAIM_OUTCOMES)}"
            )
        if isinstance(round, bool) or not isinstance(round, int) or round < 1:
            raise ValidationError(f"claim round must be a positive integer, got {round!r}")
        cur = self._session.execute(
            "INSERT INTO goal_claim"
            " (group_id,claimed_by,claimed_at,summary,base_sha,details_sha,"
            " outcome,round) VALUES (?,?,?,?,?,?,?,?)",
            (group_id, claimed_by, claimed_at, summary, base_sha, details_sha,
             outcome, round),
        )
        return GoalClaim(
            int(cur.lastrowid), group_id, claimed_by, claimed_at, summary,
            base_sha, details_sha, outcome, round,
        )

    def claims(self, group_id: int) -> tuple[GoalClaim, ...]:
        self._goal(group_id)
        rows = self._session.execute(
            "SELECT id,group_id,claimed_by,claimed_at,summary,base_sha,"
            " details_sha,outcome,round FROM goal_claim"
            " WHERE group_id = ? ORDER BY round, id", (group_id,),
        ).fetchall()
        return tuple(GoalClaim(*row) for row in rows)

    def append_verdict(
        self, claim_id: int, *, lens: str, refuted: bool,
        findings: object, corroborated: object, examined: object,
        blocking: str = "none",
    ) -> GoalVerdict:
        claim = self._session.execute(
            "SELECT group_id FROM goal_claim WHERE id = ?", (claim_id,)
        ).fetchone()
        if claim is None:
            raise NotFound(f"no goal claim #{claim_id}")
        self._goal(int(claim[0]))
        lens = _text(lens, "verdict lens")
        if lens not in VERDICT_LENSES:
            raise ValidationError(
                f"unknown verdict lens {lens!r}; expected {tuple(VERDICT_LENSES)}"
            )
        blocking = _text(blocking, "verdict blocking")
        if blocking not in BLOCKING_KINDS:
            raise ValidationError(
                f"unknown blocking kind {blocking!r}; expected {tuple(BLOCKING_KINDS)}"
            )
        if not isinstance(refuted, bool):
            raise ValidationError(f"refuted must be bool, got {refuted!r}")
        finding_items, findings_json = _json_array(findings, "findings")
        corroborated_items, corroborated_json = _json_array(
            corroborated, "corroborated"
        )
        examined_counts, examined_json = _examined(examined)
        if refuted and not finding_items:
            raise ValidationError("malformed refutation: findings array is empty")
        if not refuted and not corroborated_items:
            raise ValidationError("malformed pass: corroborated array is empty")
        duplicate = self._session.execute(
            "SELECT id FROM goal_verdict WHERE claim_id = ? AND lens = ?",
            (claim_id, lens),
        ).fetchone()
        if duplicate is not None:
            raise ValidationError(
                f"goal claim #{claim_id} already has a {lens!r} verdict"
            )
        cur = self._session.execute(
            "INSERT INTO goal_verdict"
            " (claim_id,lens,refuted,blocking,findings,corroborated,examined)"
            " VALUES (?,?,?,?,?,?,?)",
            (claim_id, lens, int(refuted), blocking, findings_json,
             corroborated_json, examined_json),
        )
        return GoalVerdict(
            int(cur.lastrowid), claim_id, lens, refuted, blocking,
            finding_items, corroborated_items, examined_counts,
        )

    def verdicts(self, claim_id: int) -> tuple[GoalVerdict, ...]:
        claim = self._session.execute(
            "SELECT group_id FROM goal_claim WHERE id = ?", (claim_id,)
        ).fetchone()
        if claim is None:
            raise NotFound(f"no goal claim #{claim_id}")
        self._goal(int(claim[0]))
        rows = self._session.execute(
            "SELECT id,claim_id,lens,refuted,blocking,findings,corroborated,"
            " examined FROM goal_verdict WHERE claim_id = ? ORDER BY id",
            (claim_id,),
        ).fetchall()
        verdicts = []
        for row in rows:
            try:
                findings = json.loads(row[5])
                corroborated = json.loads(row[6])
                examined = json.loads(row[7])
            except (TypeError, json.JSONDecodeError) as exc:
                raise SchemaMismatch(
                    f"goal verdict #{row[0]} has malformed JSON"
                ) from exc
            finding_items, _ = _json_array(findings, "stored findings")
            corroborated_items, _ = _json_array(
                corroborated, "stored corroborated"
            )
            examined_counts, _ = _examined(examined)
            if bool(row[3]) and not finding_items:
                raise SchemaMismatch(
                    f"goal verdict #{row[0]} is a refutation with no findings"
                )
            if not bool(row[3]) and not corroborated_items:
                raise SchemaMismatch(
                    f"goal verdict #{row[0]} is a malformed pass with no corroboration"
                )
            verdicts.append(GoalVerdict(
                int(row[0]), int(row[1]), row[2], bool(row[3]), row[4],
                finding_items, corroborated_items, examined_counts,
            ))
        return tuple(verdicts)
