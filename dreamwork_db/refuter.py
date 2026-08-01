"""The claimant-independent input boundary for goal refuters."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

from .goals import GoalRepository, PANEL_LENSES
from .groups import EmptyGroup, GroupRepository
from .tasks import TaskRepository


@dataclass(frozen=True, slots=True)
class RefuterPopulation:
    criteria: tuple[str, ...]
    member_task_ids: tuple[int, ...]
    landed_shas: tuple[str, ...]

    @property
    def examined(self) -> dict[str, int]:
        return {"criteria": len(self.criteria), "members": len(self.member_task_ids)}


@dataclass(frozen=True, slots=True)
class RefuterBrief:
    lens: str
    population: RefuterPopulation


_CRITERION = re.compile(
    r"\s*(?:[-*+]\s+(?:\[[ xX]\]\s+)?|\d+[.)]\s+)(.+)"
)


def _criteria(details: str) -> tuple[str, ...]:
    """Read only the store's ``Done when`` contract."""
    result: list[str] = []
    active = False
    for line in details.splitlines():
        if line.startswith("## "):
            active = line.strip().casefold() == "## done when"
            continue
        if active:
            match = _CRITERION.match(line)
            if match:
                result.append(match.group(1).strip())
    return tuple(result)


class RefuterAdapter:
    """Build refuter inputs from stored goal/tree state, never claim prose."""

    def __init__(self, goals: GoalRepository, groups: GroupRepository,
                 tasks: TaskRepository) -> None:
        self._goals = goals
        self._groups = groups
        self._tasks = tasks

    def population(self, goal_id: int) -> RefuterPopulation:
        goal = self._groups.get(goal_id)
        try:
            progress = self._groups.progress(goal_id)
        except EmptyGroup:
            # Preserve the zero denominator for the refuter's examined field;
            # the adapter must not turn an unjudgeable population into silence.
            return RefuterPopulation(_criteria(goal.description), (), ())
        return RefuterPopulation(
            criteria=_criteria(goal.description),
            member_task_ids=progress.member_task_ids,
            landed_shas=self._tasks.landed_shas(progress.landed_task_ids),
        )

    def briefs(self, goal_id: int) -> tuple[RefuterBrief, ...]:
        population = self.population(goal_id)
        return tuple(RefuterBrief(lens, population) for lens in PANEL_LENSES)

    def normalize_verdict(self, claim_id: int, lens: str, result: object):
        """Store a valid result, or a non-empty synthetic refutation."""
        claim = self._goals._claim(claim_id)
        population = self.population(claim.group_id)
        valid = isinstance(result, Mapping)
        if valid:
            valid = (
                result.get("lens") == lens
                and isinstance(result.get("refuted"), bool)
                and isinstance(result.get("findings"), (list, tuple))
                and isinstance(result.get("corroborated"), (list, tuple))
                and bool(result.get("findings")) == bool(result.get("refuted"))
                and bool(result.get("corroborated")) == (not result.get("refuted"))
            )
        if not valid:
            return self._goals.append_verdict(
                claim_id, lens=lens, refuted=True,
                findings=[{"synthetic": True, "reason": "malformed or missing refuter verdict"}],
                corroborated=[], examined=population.examined, synthetic=True,
            )
        return self._goals.append_verdict(
            claim_id, lens=lens, refuted=result["refuted"],
            findings=result["findings"], corroborated=result["corroborated"],
            examined=population.examined,
            blocking=result.get("blocking", "none"),
        )
