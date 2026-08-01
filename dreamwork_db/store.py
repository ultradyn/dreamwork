"""Canonical composition of the Dreamwork SQLite store.

The reusable boundary is the core's ``StoreSpec`` plus repository factories,
not a public SQL helper and not one store description per domain.  Tasks,
questions, and reviews share one schema ladder, connection policy, transaction
boundary, and classified error ladder while retaining domain-specific APIs.

Keeping this composition in one module prevents a task-only spec and a
question-aware spec for the same file from drifting into two definitions of
the store.  The older domain-named builders delegate here for compatibility.
"""

from __future__ import annotations

from pathlib import Path

from .core import StoreSpec
from .goals import GoalRepository
from .groups import GroupRepository
from .migrate import initialize_legacy_store
from .questions import QuestionRepository
from .reviews import ReviewRepository
from .settings import SettingRepository
from .tasks import TaskRepository


PathLike = str | Path


def dreamwork_store_spec(path: PathLike) -> StoreSpec:
    """Bind every Dreamwork repository through the core's one factory seam."""

    return StoreSpec(
        path,
        repositories={
            "tasks": TaskRepository,
            "questions": QuestionRepository,
            "reviews": ReviewRepository,
            "groups": GroupRepository,
            "settings": SettingRepository,
            "goals": GoalRepository,
        },
        initializer=initialize_legacy_store,
    )
